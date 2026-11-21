"""Receptor HTTP de telemetria. Python 3.8+, somente biblioteca padrao."""
import argparse
import csv
from contextlib import closing
import hmac
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from .painel import consultar_painel, estacoes, filtros, linhas_csv

STATIC = Path(__file__).with_name("static")


def inicializar_banco(caminho):
    with closing(sqlite3.connect(caminho)) as banco, banco:
        banco.execute("""CREATE TABLE IF NOT EXISTS medicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo TEXT NOT NULL, inicializacao TEXT NOT NULL,
            sequencia INTEGER NOT NULL, recebido_ms INTEGER NOT NULL,
            recebido_em TEXT NOT NULL, temp_aht REAL NOT NULL,
            umidade REAL NOT NULL, pressao REAL, temp_bmp REAL,
            UNIQUE(dispositivo, inicializacao, sequencia))""")
        banco.execute("CREATE INDEX IF NOT EXISTS idx_medicoes_estacao_tempo ON medicoes(dispositivo, recebido_em)")


def validar(dados):
    if not isinstance(dados, dict):
        raise ValueError("O corpo precisa ser um objeto JSON.")
    for campo in ("dispositivo", "inicializacao"):
        valor = dados.get(campo)
        if not isinstance(valor, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", valor):
            raise ValueError("Identificador invalido: " + campo)
    for campo in ("sequencia", "recebido_ms"):
        valor = dados.get(campo)
        if type(valor) is not int or not 0 <= valor <= 0xffffffff:
            raise ValueError("Inteiro invalido: " + campo)
    for campo in ("temp_aht", "umidade", "pressao", "temp_bmp"):
        if campo not in dados:
            raise ValueError("Campo ausente: " + campo)
        valor = dados[campo]
        if campo in ("pressao", "temp_bmp") and valor is None:
            continue
        if type(valor) not in (int, float):
            raise ValueError("Numero invalido: " + campo)
        try:
            finito = math.isfinite(valor)
        except OverflowError:
            finito = False
        if not finito:
            raise ValueError("Numero nao finito: " + campo)
    if not -40 <= dados["temp_aht"] <= 85 or not 0 <= dados["umidade"] <= 100:
        raise ValueError("Temperatura ou umidade fora dos limites.")
    return dados


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, endereco, banco, token=""):
        self.banco = str(banco)
        self.token = token
        inicializar_banco(self.banco)
        super().__init__(endereco, Receptor)


class Receptor(BaseHTTPRequestHandler):
    # Resposta pequena: agrupa cabecalhos e JSON e envia com flush explicito.
    wbufsize = 4096
    disable_nagle_algorithm = True

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def responder(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.responder_bytes(codigo, corpo, "application/json; charset=utf-8")

    def responder_bytes(self, codigo, corpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        self.wfile.write(corpo)
        self.wfile.flush()

    def autorizado(self):
        esperado = "Bearer " + self.server.token
        recebido = self.headers.get("Authorization", "")
        return not self.server.token or hmac.compare_digest(recebido.encode(), esperado.encode())

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/health":
            self.responder(200, {"status": "ok"})
            return
        arquivos = {"/": ("index.html", "text/html; charset=utf-8"),
                    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
                    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if url.path in arquivos:
            nome, tipo = arquivos[url.path]
            try:
                self.responder_bytes(200, (STATIC / nome).read_bytes(), tipo)
            except FileNotFoundError:
                self.responder(503, {"erro": "Arquivos do painel nao instalados."})
            return
        if url.path not in ("/api/estacoes", "/api/painel", "/api/exportar.csv"):
            self.responder(404, {"erro": "Rota nao encontrada."})
            return
        if not self.autorizado():
            self.responder(401, {"erro": "Token invalido."})
            return
        try:
            parametros = parse_qs(url.query, keep_blank_values=True, max_num_fields=12)
            with closing(sqlite3.connect(self.server.banco, timeout=10)) as banco:
                banco.row_factory = sqlite3.Row
                if url.path == "/api/estacoes":
                    self.responder(200, estacoes(banco))
                elif url.path == "/api/painel":
                    self.responder(200, consultar_painel(banco, parametros))
                else:
                    filtros(parametros)  # Valida antes de iniciar o download.
                    self.exportar_csv(banco, parametros)
        except ValueError as erro:
            self.responder(400, {"erro": str(erro)})
        except sqlite3.Error:
            self.responder(503, {"erro": "Historico indisponivel."})

    def exportar_csv(self, banco, parametros):
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="medicoes.csv"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        self.wfile.write(b"\xef\xbb\xbf")
        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=";")
        escritor.writerow(["Data/hora UTC", "Dispositivo", "Inicializacao", "Sequencia", "Recebido ms",
                           "Temperatura C", "Umidade %", "Pressao hPa", "Temperatura BMP C"])
        for linha in linhas_csv(banco, parametros):
            def texto(valor):
                return "'" + valor if valor.startswith(("=", "+", "-", "@")) else valor
            def numero(valor):
                return "" if valor is None else format(valor, ".2f").replace(".", ",")
            escritor.writerow([linha["recebido_em"], texto(linha["dispositivo"]), texto(linha["inicializacao"]),
                               linha["sequencia"], linha["recebido_ms"], numero(linha["temp_aht"]),
                               numero(linha["umidade"]), numero(linha["pressao"]), numero(linha["temp_bmp"])])
            if buffer.tell() > 32768:
                self.wfile.write(buffer.getvalue().encode("utf-8"))
                buffer.seek(0)
                buffer.truncate(0)
        self.wfile.write(buffer.getvalue().encode("utf-8"))
        self.wfile.flush()

    def do_POST(self):
        if urlsplit(self.path).path != "/api/medicoes":
            self.responder(404, {"erro": "Rota nao encontrada."})
            return
        if not self.autorizado():
            self.responder(401, {"erro": "Token invalido."})
            return
        if self.headers.get_content_type() != "application/json":
            self.responder(415, {"erro": "Use Content-Type: application/json."})
            return
        inicio_corpo = time.perf_counter()
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if not 0 < tamanho <= 4096 or self.headers.get("Transfer-Encoding"):
                raise ValueError("Corpo vazio, muito grande ou codificacao nao suportada.")
            def rejeitar_constante(valor):
                raise ValueError("Constante JSON invalida: " + valor)
            dados = validar(json.loads(self.rfile.read(tamanho).decode("utf-8"),
                                       parse_constant=rejeitar_constante))
            corpo_ms = (time.perf_counter() - inicio_corpo) * 1000
        except (ValueError, UnicodeError):
            self.responder(400, {"erro": "JSON invalido ou campos fora do contrato."})
            return
        except (TimeoutError, OSError):
            self.responder(408, {"erro": "Tempo de leitura esgotado."})
            return
        try:
            inicio_banco = time.perf_counter()
            with closing(sqlite3.connect(self.server.banco, timeout=10)) as banco, banco:
                cursor = banco.execute("""INSERT INTO medicoes
                    (dispositivo, inicializacao, sequencia, recebido_ms, recebido_em,
                     temp_aht, umidade, pressao, temp_bmp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dispositivo, inicializacao, sequencia) DO NOTHING""",
                    (dados["dispositivo"], dados["inicializacao"], dados["sequencia"],
                     dados["recebido_ms"], datetime.now(timezone.utc).isoformat(),
                     dados["temp_aht"], dados["umidade"], dados["pressao"], dados["temp_bmp"]))
                inserido = cursor.rowcount == 1
            banco_ms = (time.perf_counter() - inicio_banco) * 1000
        except sqlite3.Error:
            self.log_error("Falha ao persistir medicao.")
            self.responder(503, {"erro": "Armazenamento indisponivel; tente novamente."})
            return
        inicio_envio = time.perf_counter()
        try:
            self.responder(201 if inserido else 200,
                           {"status": "gravado" if inserido else "ja_recebido",
                            "sequencia": dados["sequencia"]})
        except (BrokenPipeError, ConnectionResetError):
            self.log_error("[REDE] seq=%d gravada; conexao encerrada ao responder.", dados["sequencia"])
        finally:
            self.log_message(
                "[TEMPO_SERVIDOR] dispositivo=%s boot=%s seq=%d corpo=%.1f ms banco=%.1f ms envio=%.1f ms",
                dados["dispositivo"], dados["inicializacao"], dados["sequencia"],
                corpo_ms, banco_ms, (time.perf_counter() - inicio_envio) * 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=49173)
    parser.add_argument("--db", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "dados.sqlite3")
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    servidor = Servidor((args.host, args.port), args.db, os.environ.get("ESTACAO_API_TOKEN", ""))
    print("Receptor em http://{}:{}/api/medicoes | Banco: {}".format(
        args.host, args.port, args.db.resolve()), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()

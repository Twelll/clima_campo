"""Consultas do painel e exportacao; mantem o banco e o protocolo existentes."""
from datetime import datetime, timedelta, timezone
import math
import re

UTC = timezone.utc
COLUNAS = "id, dispositivo, inicializacao, sequencia, recebido_ms, recebido_em, temp_aht, umidade, pressao, temp_bmp"


def agora():
    return datetime.now(UTC)


def data_iso(valor):
    if len(valor) > 64:
        raise ValueError("Data invalida.")
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if data.tzinfo is None:
        raise ValueError("Informe o fuso horario nas datas.")
    return data.astimezone(UTC)


def filtros(parametros):
    def unico(nome, padrao=""):
        valores = parametros.get(nome, [padrao])
        if len(valores) != 1:
            raise ValueError("Parametro repetido: " + nome)
        return valores[0]
    dispositivo = unico("dispositivo")
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", dispositivo):
        raise ValueError("Selecione uma estacao valida.")
    fim = data_iso(unico("fim")) if unico("fim") else agora()
    inicio = data_iso(unico("inicio")) if unico("inicio") else fim - timedelta(days=1)
    if not inicio < fim or fim - inicio > timedelta(days=366):
        raise ValueError("O periodo deve ter entre um instante e 366 dias.")
    turno = unico("turno", "todos")
    if turno not in ("todos", "dia", "noite"):
        raise ValueError("Turno invalido.")
    sql = "dispositivo = ? AND recebido_em >= ? AND recebido_em < ?"
    args = [dispositivo, inicio.isoformat(), fim.isoformat()]
    # Convencao do painel: Brasilia UTC-3, dia 06:00-17:59; noite 18:00-05:59.
    hora = "CAST(strftime('%H', recebido_em, '-3 hours') AS INTEGER)"
    if turno == "dia":
        sql += " AND " + hora + " >= 6 AND " + hora + " < 18"
    elif turno == "noite":
        sql += " AND (" + hora + " < 6 OR " + hora + " >= 18)"
    meses = unico("meses")
    if meses:
        try:
            numeros = sorted(set(int(x) for x in meses.split(",")))
        except ValueError:
            raise ValueError("Meses invalidos.")
        if not numeros or any(x < 1 or x > 12 for x in numeros) or len(meses) > 40:
            raise ValueError("Meses invalidos.")
        sql += " AND CAST(strftime('%m', recebido_em, '-3 hours') AS INTEGER) IN (" + ",".join("?" for _ in numeros) + ")"
        args.extend(numeros)
    return sql, args, {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "turno": turno,
                       "fuso": "UTC-3", "dispositivo": dispositivo}


def idade(timestamp, instante):
    return max(0, (instante - data_iso(timestamp)).total_seconds())


def ponto_orvalho(temperatura, umidade):
    # Inversa da aproximacao August-Roche-Magnus (NOAA TMY Tech User Guide).
    if temperatura is None or umidade is None or not -40 <= temperatura <= 60 or not 0 < umidade <= 100:
        return None
    gamma = math.log(umidade / 100) + 17.625 * temperatura / (243.04 + temperatura)
    return round(243.04 * gamma / (17.625 - gamma), 2)


def estacoes(banco):
    instante = agora()
    linhas = banco.execute("""SELECT dispositivo, COUNT(*) AS total,
        MIN(recebido_em) AS primeira_leitura, MAX(recebido_em) AS ultima_leitura
        FROM medicoes GROUP BY dispositivo ORDER BY ultima_leitura DESC, dispositivo""").fetchall()
    resultado = []
    for linha in linhas:
        item = dict(linha)
        item["idade_segundos"] = idade(item["ultima_leitura"], instante)
        resultado.append(item)
    return {"servidor_em": instante.isoformat(), "estacoes": resultado}


def consultar_painel(banco, parametros):
    sql, args, periodo = filtros(parametros)
    instante = agora()
    ultima = banco.execute("SELECT " + COLUNAS + " FROM medicoes WHERE dispositivo = ? ORDER BY recebido_em DESC, id DESC LIMIT 1",
                           (periodo["dispositivo"],)).fetchone()
    resumo = dict(banco.execute("""SELECT COUNT(*) AS total,
        MIN(temp_aht) AS temperatura_min, MAX(temp_aht) AS temperatura_max, AVG(temp_aht) AS temperatura_media,
        MIN(umidade) AS umidade_min, MAX(umidade) AS umidade_max, AVG(umidade) AS umidade_media,
        MIN(pressao) AS pressao_min, MAX(pressao) AS pressao_max, AVG(pressao) AS pressao_media,
        COALESCE(SUM(CASE WHEN pressao IS NOT NULL AND (pressao < 300 OR pressao > 1100) THEN 1 ELSE 0 END),0) AS pressao_fora_faixa,
        MIN(recebido_em) AS primeiro, MAX(recebido_em) AS ultimo
        FROM medicoes WHERE """ + sql, args).fetchone())
    agrupamento = 0
    if resumo["total"] > 600:
        amplitude = (data_iso(resumo["ultimo"]) - data_iso(resumo["primeiro"])).total_seconds()
        agrupamento = max(60, math.ceil((amplitude + 1) / 600))
        serie = banco.execute("""SELECT MIN(recebido_em) AS recebido_em, AVG(temp_aht) AS temp_aht,
            AVG(umidade) AS umidade, AVG(pressao) AS pressao, AVG(temp_bmp) AS temp_bmp, COUNT(*) AS amostras
            FROM medicoes WHERE """ + sql + " GROUP BY CAST(strftime('%s', recebido_em) AS INTEGER) / ? ORDER BY recebido_em",
            args + [agrupamento]).fetchall()
    else:
        serie = banco.execute("SELECT recebido_em, temp_aht, umidade, pressao, temp_bmp, 1 AS amostras FROM medicoes WHERE " +
                              sql + " ORDER BY recebido_em, id", args).fetchall()
    registros = banco.execute("SELECT " + COLUNAS + " FROM medicoes WHERE " + sql +
                              " ORDER BY recebido_em DESC, id DESC LIMIT 100", args).fetchall()
    return {"servidor_em": instante.isoformat(), "periodo": periodo,
            "atual": dict(ultima) if ultima else None,
            "ponto_orvalho": ponto_orvalho(ultima["temp_aht"], ultima["umidade"]) if ultima else None,
            "idade_segundos": idade(ultima["recebido_em"], instante) if ultima else None,
            "resumo": resumo, "serie": [dict(linha) for linha in serie],
            "agrupamento_segundos": agrupamento, "registros": [dict(linha) for linha in registros]}


def linhas_csv(banco, parametros):
    sql, args, _ = filtros(parametros)
    return banco.execute("SELECT " + COLUNAS + " FROM medicoes WHERE " + sql + " ORDER BY recebido_em, id", args)

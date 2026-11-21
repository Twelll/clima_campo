from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from app.servidor import Servidor


class TestReceptor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "teste.sqlite3"
        cls.http = Servidor(("127.0.0.1", 0), cls.db, "token-teste")
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def setUp(self):
        with closing(sqlite3.connect(self.db)) as banco, banco:
            banco.execute("DELETE FROM medicoes")
        self.dados = dict(dispositivo="aabbccddeeff", inicializacao="boot01", sequencia=1,
                          recebido_ms=2000, temp_aht=25.12, umidade=60.25,
                          pressao=1013.25, temp_bmp=26.0)

    def requisitar(self, dados=None, token="token-teste", tipo="application/json",
                   rota="/api/medicoes", metodo="POST", bruto=None):
        corpo = bruto if bruto is not None else json.dumps(dados)
        cliente = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            cliente.request(metodo, rota, body=corpo,
                            headers={"Content-Type": tipo, "Authorization": "Bearer " + token})
            resposta = cliente.getresponse()
            return resposta.status, json.loads(resposta.read())
        finally:
            cliente.close()

    def test_grava_todos_os_campos_e_timestamp(self):
        self.assertEqual(self.requisitar(self.dados)[0], 201)
        with closing(sqlite3.connect(self.db)) as banco, banco:
            linha = banco.execute("SELECT temp_aht, umidade, pressao, temp_bmp, recebido_ms, recebido_em FROM medicoes").fetchone()
        self.assertEqual(linha[:5], (25.12, 60.25, 1013.25, 26.0, 2000))
        self.assertTrue(linha[5].endswith("+00:00"))

    def test_reenvio_nao_duplica(self):
        self.assertEqual(self.requisitar(self.dados)[0], 201)
        self.assertEqual(self.requisitar(self.dados), (200, {"status": "ja_recebido", "sequencia": 1}))
        with closing(sqlite3.connect(self.db)) as banco, banco:
            self.assertEqual(banco.execute("SELECT COUNT(*) FROM medicoes").fetchone()[0], 1)

    def test_reinicio_permite_mesma_sequencia(self):
        self.assertEqual(self.requisitar(self.dados)[0], 201)
        self.dados["inicializacao"] = "boot02"
        self.assertEqual(self.requisitar(self.dados)[0], 201)

    def test_bmp_ausente_aceita_null(self):
        self.dados.update(pressao=None, temp_bmp=None)
        self.assertEqual(self.requisitar(self.dados)[0], 201)

    def test_rejeita_dados_invalidos(self):
        for campo, valor in (("umidade", 110), ("temp_aht", -41), ("sequencia", True),
                              ("temp_aht", None), ("pressao", "1013"),
                              ("dispositivo", ""), ("recebido_ms", -1),
                              ("pressao", 10**400)):
            with self.subTest(campo=campo, valor=str(valor)[:20]):
                dados = dict(self.dados, **{campo: valor})
                self.assertEqual(self.requisitar(dados)[0], 400)

    def test_rejeita_json_invalido_nao_finito_e_campo_ausente(self):
        for bruto in ("{", "[]", json.dumps(dict(self.dados, umidade=float("nan"))),
                      json.dumps(dict(self.dados, pressao=float("inf")))):
            self.assertEqual(self.requisitar(bruto=bruto)[0], 400)
        del self.dados["pressao"]
        self.assertEqual(self.requisitar(self.dados)[0], 400)

    def test_auth_content_type_e_rotas(self):
        self.assertEqual(self.requisitar(self.dados, token="errado")[0], 401)
        self.assertEqual(self.requisitar(self.dados, tipo="text/plain")[0], 415)
        self.assertEqual(self.requisitar(self.dados, rota="/inexistente")[0], 404)
        self.assertEqual(self.requisitar(metodo="GET", rota="/health"), (200, {"status": "ok"}))

    def test_tamanho_maximo(self):
        self.assertEqual(self.requisitar(bruto=" " * 4097)[0], 400)

    def test_dados_persistem_apos_reabrir_servidor(self):
        self.assertEqual(self.requisitar(self.dados)[0], 201)
        outro = Servidor(("127.0.0.1", 0), self.db)
        outro.server_close()
        with closing(sqlite3.connect(self.db)) as banco, banco:
            self.assertEqual(banco.execute("SELECT COUNT(*) FROM medicoes").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

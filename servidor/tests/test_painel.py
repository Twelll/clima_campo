from contextlib import closing
from datetime import datetime, timedelta, timezone
import csv
import http.client
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from app.painel import ponto_orvalho
from app.servidor import Servidor


class TestPainel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / 'painel.sqlite3'
        cls.http = Servidor(('127.0.0.1', 0), cls.db, 'teste')
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
            banco.execute('DELETE FROM medicoes')
            for seq, (hora, temperatura, pressao) in enumerate([
                ('2026-11-01T02:00:00+00:00', 10, 1000),
                ('2026-11-01T09:00:00+00:00', 20, 1000),
                ('2026-11-01T23:00:00+00:00', 21, 1454.5),
                ('2026-11-02T04:00:00+00:00', 22, None)], 1):
                banco.execute('INSERT INTO medicoes (dispositivo,inicializacao,sequencia,recebido_ms,recebido_em,temp_aht,umidade,pressao,temp_bmp) VALUES (?,?,?,?,?,?,?,?,?)',
                              ('campo', 'boot', seq, seq*60000, hora, temperatura, 60, pressao, None))
        self.params = dict(dispositivo='campo', inicio='2026-11-01T03:00:00Z', fim='2026-11-02T03:00:00Z')

    def get(self, path, token='teste'):
        cliente = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            cliente.request('GET', path, headers={'Authorization': 'Bearer '+token})
            resposta = cliente.getresponse()
            return resposta.status, dict(resposta.getheaders()), resposta.read()
        finally:
            cliente.close()

    def painel(self, **extra):
        status, _, body = self.get('/api/painel?' + urlencode(dict(self.params, **extra)))
        return status, json.loads(body)

    def test_resumo_filtrado_e_ultima_leitura_independente_do_periodo(self):
        status, data = self.painel()
        self.assertEqual(status, 200)
        self.assertEqual(data['resumo']['total'], 2)
        self.assertEqual(data['resumo']['temperatura_media'], 20.5)
        self.assertEqual(data['resumo']['pressao_fora_faixa'], 1)
        self.assertEqual(data['atual']['temp_aht'], 22)
        self.assertEqual([p['temp_aht'] for p in data['serie']], [20, 21])
        self.assertEqual([p['sequencia'] for p in data['registros']], [3, 2])

    def test_turnos_e_meses_usam_brasilia(self):
        self.assertEqual(self.painel(turno='dia')[1]['serie'][0]['temp_aht'], 20)
        self.assertEqual(self.painel(turno='noite')[1]['serie'][0]['temp_aht'], 21)
        self.assertEqual(self.painel(meses='10')[1]['resumo']['total'], 0)
        self.assertEqual(self.painel(meses='11')[1]['resumo']['total'], 2)

    def test_entrada_invalida_e_injecao(self):
        for args in (dict(dispositivo="campo' OR 1=1"), dict(turno='x'), dict(meses='13'),
                     dict(inicio='sem-data'), dict(inicio='2026-11-01'),
                     dict(inicio='2020-01-01T00:00:00Z'), dict(fim=self.params['inicio'])):
            with self.subTest(args=args):
                self.assertEqual(self.painel(**args)[0], 400)
        self.assertEqual(self.get('/api/painel?dispositivo=campo&dispositivo=outro')[0], 400)

    def test_sem_dados_e_estacoes(self):
        data = self.painel(dispositivo='inexistente')[1]
        self.assertIsNone(data['atual'])
        self.assertEqual(data['serie'], [])
        self.assertEqual(data['resumo']['total'], 0)
        data = json.loads(self.get('/api/estacoes')[2])
        self.assertEqual(data['estacoes'][0]['total'], 4)
        self.assertEqual(data['estacoes'][0]['dispositivo'], 'campo')

    def test_csv_exporta_registros_originais_no_periodo(self):
        status, headers, body = self.get('/api/exportar.csv?' + urlencode(self.params))
        self.assertEqual(status, 200)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertTrue(body.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(io.StringIO(body.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[2][7], '1454,50')
        self.assertEqual(linhas[1][5], '20,00')

    def test_auth_e_arquivos_locais(self):
        for rota in ('/api/estacoes', '/api/painel', '/api/exportar.csv'):
            self.assertEqual(self.get(rota, token='errado')[0], 401)
        for rota in ('/', '/static/style.css', '/static/app.js', '/favicon.svg'):
            status, _, body = self.get(rota, token='')
            self.assertEqual(status, 200)
            self.assertTrue(body)
        self.assertEqual(self.get('/static/../servidor.py')[0], 404)
        self.assertEqual(self.get('/.env')[0], 404)

    def test_agregacao_preserva_contagem_e_csv_completo(self):
        inicio = datetime(2026, 11, 1, 3, tzinfo=timezone.utc)
        with closing(sqlite3.connect(self.db)) as banco, banco:
            banco.execute('DELETE FROM medicoes')
            banco.executemany('INSERT INTO medicoes (dispositivo,inicializacao,sequencia,recebido_ms,recebido_em,temp_aht,umidade,pressao,temp_bmp) VALUES (?,?,?,?,?,?,?,?,?)',
                [('campo','boot',i,i*60000,(inicio+timedelta(minutes=i)).isoformat(),20,60,1000,21) for i in range(1000)])
        data = self.painel()[1]
        self.assertEqual(data['resumo']['total'], 1000)
        self.assertEqual(sum(p['amostras'] for p in data['serie']), 1000)
        self.assertLessEqual(len(data['serie']), 601)
        self.assertEqual(len(data['registros']), 100)
        self.assertGreater(data['agrupamento_segundos'], 0)
        body = self.get('/api/exportar.csv?' + urlencode(self.params))[2]
        self.assertEqual(len(list(csv.reader(io.StringIO(body.decode('utf-8-sig')), delimiter=';'))), 1001)

    def test_orvalho_estimado(self):
        self.assertEqual(ponto_orvalho(25, 100), 25)
        self.assertAlmostEqual(ponto_orvalho(25, 60), 16.7, delta=0.1)
        self.assertIsNone(ponto_orvalho(25, 0))
        self.assertIsNone(ponto_orvalho(80, 60))


if __name__ == '__main__':
    unittest.main()

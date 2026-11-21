# Desenvolvimento e manutenção

Execute os comandos na raiz de `servidor/`. Não há dependências pip/npm.

## Aplicação local

```bash
python3 -m app --host 127.0.0.1 --port 49173
```

A entrada fica em `app/__main__.py`. `app/servidor.py` trata HTTP, validação,
autenticação e gravação; `app/painel.py` concentra as consultas. Os arquivos
públicos ficam em `app/static/` e são servidos por uma lista explícita de rotas.

O banco local usa `data/dados.sqlite3`. O banco Docker usa `/dados/dados.sqlite3`
no volume existente. Não copie um banco de desenvolvimento sobre o histórico.
A atualização cria índices e tabelas ausentes sem apagar registros.

## Testes

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Os 17 testes usam HTTP em loopback e bancos temporários. Cobrem recebimento,
validação, autenticação, persistência, reenvio sem duplicação, consultas,
filtros, agrupamento dos gráficos, arquivos públicos e exportação CSV.

Confira também no navegador os estados sem dados, erros de acesso, filtros,
CSV, avisos visualizados e disposição em telas estreitas. Os testes locais
não substituem a execução real do Docker nem o teste com Arduino/ESP32.

## Organização

- Código e recursos públicos: `app/`.
- Testes automatizados: `tests/`.
- Guias por assunto: `docs/`.
- Configuração Docker: raiz de `servidor/`, permitindo `docker compose up` direto.
- Dados locais: `data/`, ignorados pelo Git e excluídos da imagem.

A imagem recebe somente `app/`; testes, documentação, `.env`, bancos e caches
ficam fora dela. O modelo systemd e o guia manual antigo foram removidos para
manter Docker Compose como o único roteiro de implantação. A execução Python
local continua disponível para desenvolvimento.

# Servidor da estação meteorológica

Recebe as leituras do ESP32, armazena em SQLite e disponibiliza o painel
HTML, CSS e JavaScript. Python 3.8+; somente biblioteca padrão.

## Estrutura

```text
servidor/
├── app/
│   ├── __init__.py
│   ├── __main__.py       # Entrada: python -m app
│   ├── servidor.py       # HTTP, validação e persistência
│   ├── painel.py         # Consultas, filtros e resumos
│   └── static/           # HTML, CSS, JavaScript e ícone
├── tests/                # Testes do receptor e do painel
├── docs/
│   ├── OPERACAO.md       # Docker, rede, apresentação e diagnóstico
│   ├── PAINEL.md         # Uso da interface e API de consulta
│   └── DESENVOLVIMENTO.md
├── data/                 # Banco da execução local; não vai para a imagem
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .env.example
└── README.md
```

O `.env` real fica na raiz de `servidor/`, junto ao Compose, e não é versionado.
Todos os comandos abaixo devem ser executados **dentro de `servidor/`**.

## Executar no Ubuntu ou Pop!_OS

Com Docker Engine e Compose v2 disponíveis:

```bash
test -f .env || cp .env.example .env
docker compose up -d --build
docker compose ps
```

Abra `http://IP_DO_SERVIDOR:49173/`. A API usada pelo ESP32 continua em
`http://IP_DO_SERVIDOR:49173/api/medicoes`. Porta e token são configurados no `.env`.

O histórico Docker permanece em `/dados/dados.sqlite3`, no volume `medicoes`
do projeto Compose `estacao-meteorologica`. A organização das pastas não muda
esse volume. **Não use `docker compose down -v` se quiser preservar o histórico.**
O banco em `data/` é separado: pertence à execução local sem Docker.

## Atualizar a instalação existente

No PowerShell do Windows, envie o conteúdo atualizado sem copiar configurações,
banco local ou caches:

```powershell
$arquivos = Get-ChildItem -Force "C:\Meus_documentos\Estacao_Metereologica\servidor" -Exclude ".env","data","__pycache__","*.sqlite3*"
scp -r $arquivos.FullName well@192.168.1.100:~/docker/servidor/
```

No Ubuntu:

```bash
cd ~/docker/servidor
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:49173/health
```

Abra o painel e atualize com Ctrl + F5. Não é necessário regravar os firmwares.
O Dockerfile agora copia `app/` e inicia `python -m app`; envie ambos juntos.
O Compose mantém o nome do projeto e do volume para reutilizar os dados existentes.

O SCP copia arquivos, mas não remove os arquivos antigos do destino. Depois de
confirmar que o container atualizado está saudável, os arquivos legados abaixo
podem ser removidos da raiz de `~/docker/servidor`:

```bash
rm -f -- servidor.py painel.py test_servidor.py test_painel.py EXECUCAO_MANUAL.md estacao-meteorologica.service
```

A antiga pasta `static/` e os caches `__pycache__/` da raiz também são obsoletos;
esta versão usa `app/static/`. Não remova `.env`, bancos ou volumes. Mesmo se
restarem arquivos antigos no destino, eles não são copiados para a imagem:
`.dockerignore` permite somente a aplicação e o Dockerfile.

## Desenvolvimento e testes

```bash
python3 -m app --host 127.0.0.1 --port 49173
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Na execução local, o banco padrão é `data/dados.sqlite3`; a pasta é criada
automaticamente. Use `--db /caminho/banco.sqlite3` para escolher outro destino.
O `.env` é carregado pelo Compose. Sem Docker, exporte `ESTACAO_API_TOKEN`
no terminal se quiser autenticação.

## Documentação

- [Operação, Wi-Fi e apresentação](docs/OPERACAO.md)
- [Painel e consultas da API](docs/PAINEL.md)
- [Desenvolvimento e manutenção](docs/DESENVOLVIMENTO.md)
- [Configuração do ESP32](../esp32/README.md)

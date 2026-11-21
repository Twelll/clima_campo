# Operação do servidor

Execute os comandos deste guia dentro da pasta `servidor/`. Consulte também o [README](../README.md).

Pré-requisitos: Docker Engine funcionando e plugin Docker Compose v2. Verifique:

```bash
docker --version
docker compose version
```

O container é Linux e não depende de serviços, caminhos ou bibliotecas do host
além do Docker. Usa imagem oficial Python para a arquitetura da máquina, sem
fixar arquitetura. No Pop!_OS, instale o Docker correspondente à versão Ubuntu
base da distribuição, se necessário; instalação de Docker em distribuições
derivadas não tem a mesma garantia de suporte oficial do Ubuntu.
Referência: https://docs.docker.com/engine/install/ubuntu/

Copie somente a pasta `servidor` para a máquina que servirá os dados. Todos os
arquivos de implantação ficam juntos nela: `docker-compose.yml`, `Dockerfile`,
`.env`, `.env.example` e `app/`. No Ubuntu, entre em `~/docker/servidor`:

```bash
test -f .env || cp .env.example .env
docker compose config
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:49173/health
```

O comando de cópia preserva seu `.env` se ele já contiver ajustes. O retorno
do teste deve ser `{"status":"ok"}`
(com ou sem espaços). Em `docker compose ps`, o serviço deve ficar `healthy`.

### Porta

Foi escolhida a porta externa **49173**, fora da 8000 que já está em uso. A porta
8080 pertence apenas ao container. O notebook/Ubuntu publica a 49173 em suas
interfaces de rede para que o ESP32 consiga alcançá-lo.

Se 49173 também estiver ocupada, edite `.env`:

```dotenv
PORTA_HTTP=49174
ESTACAO_API_TOKEN=
```

Depois execute `docker compose up -d` e atualize a URL no ESP32 por serial.
A porta foi escolhida arbitrariamente, mas permanece fixa entre reinícios:
isso evita mudar o destino do ESP32 a cada apresentação. A troca é configurável
sem editar o Compose. Consulte o mapeamento com `docker compose port receptor 8080`.

Se já tiver iniciado o receptor antigo manualmente/systemd, pare-o antes de
usar Docker na mesma porta. Se Docker exigir privilégios no seu ambiente,
use `sudo docker ...` nos comandos correspondentes.

### Dados e token

O histórico fica em `/dados/dados.sqlite3`, em um **volume nomeado Docker**.
Recriar a imagem, reiniciar o serviço ou usar `docker compose down` preserva
esse volume. **`docker compose down -v` apaga o volume e o histórico.**
O volume é local a cada máquina: copiar o projeto entre casa e notebook não
copia automaticamente o banco. Também não importa um banco antigo que esteja
fora do Docker.

Opcionalmente, preencha `ESTACAO_API_TOKEN` no `.env` e configure o mesmo valor
no ESP32 com `token VALOR` e `salvar`. O `.env` não deve ser publicado. Esta API
HTTP foi preparada para rede local; o token não é criptografado pelo HTTP.

## Trocar Wi-Fi e servidor sem recompilar

Carregue `esp32.ino`, que está na pasta irmã `esp32`, com seus arquivos `.h` juntos. No monitor serial,
use **115200 baud**, termine os comandos com **nova linha** e envie um por vez:

```text
ssid NOME_DA_REDE
senha SENHA_DA_REDE
servidor http://IP_DO_UBUNTU_OU_NOTEBOOK:49173/api/medicoes
salvar
status
```

Use valores reais no lugar dos exemplos, sem aspas. O SSID pode conter espaços.
O comando `senha` sem argumento configura uma rede aberta. `token VALOR`
configura o token; `token` sem argumento limpa-o. `ajuda` mostra os comandos.

O ESP32 aplica os valores sem reiniciar e salva em NVS. A configuração permanece
após desligar e tem prioridade sobre os valores iniciais de `../../esp32/config.h`.
A configuração, recepção RF e reconexão são tratadas no loop principal do
ESP32, sem light sleep. O Arduino coleta/envia a cada 60 s (ou 30 s, ajustável);
o gateway encaminha somente novas leituras, usando o HTTPClient padrão.

Use o IP de rede do **host**, não o IP interno do container, nem `localhost`.
Após trocar de Wi-Fi/hotspot, o IP do notebook pode mudar: consulte o endereço
da conexão ativa nas configurações de rede do Pop!_OS e atualize `servidor ...`.
`hostname -I` também mostra endereços, mas pode incluir IPs de bridges Docker e
Tailscale; esses não são o destino local do ESP32.

## Apresentação na faculdade: usar o notebook como servidor

Recomendação: **levar o servidor Docker no notebook Pop!_OS** e conectar notebook
e ESP32 ao mesmo hotspot do celular, em **2,4 GHz**.

```text
Arduino + sensores → NRF24L01 → ESP32
                                 │
                         hotspot do celular
                                 │
                     notebook Pop!_OS + Docker
```

1. Em casa, construa a imagem no próprio notebook: `docker compose build`.
   A primeira construção precisa baixar a imagem Python; faça isso antes da aula.
2. Teste com o mesmo celular, SSID, senha e modo 2,4 GHz que usará na apresentação.
3. Conecte notebook e ESP32 ao hotspot. No ESP32, salve a rede e o IP atual do notebook.
4. Suba o serviço com `docker compose up -d`, teste `/health` no notebook e acompanhe
   `docker compose logs -f receptor`.
5. Confira `[HTTP] ... HTTP 201` no monitor serial e consulte as medições no banco.

Com a imagem já construída, a coleta e a API local não precisam acessar a
internet. O hotspot fornece a rede local mesmo quando não há tráfego externo,
desde que o aparelho mantenha a rede ativa. Desative desligamento automático
do hotspot e suspensão do notebook durante a apresentação.

Alguns celulares isolam clientes conectados. Se `/health` funciona no notebook,
mas o ESP32 não alcança o IP dele, verifique isolamento do hotspot e firewall
do host. Teste isso em casa. Alternativa: o notebook criar uma rede hotspot para
o ESP32, se seu adaptador Wi-Fi suportar; nesse caso, use o IP do notebook nessa
nova rede. Não dependa de trocar essa configuração pela primeira vez na aula.

### E o Tailscale?

Tailscale é útil para administrar o Ubuntu de casa, mas não é necessário para
a apresentação local. Instalar Tailscale apenas no notebook e no Ubuntu não
faz o ESP32 alcançar automaticamente o IP Tailscale do servidor: seria preciso
uma ponte/proxy no notebook ou roteamento adicional.

Usar o Ubuntu remoto também adiciona dependência da internet móvel, da conexão
de casa e do túnel. Mantenha esse caminho como alternativa futura; o servidor
no notebook permite demonstrar o sistema sem depender dessas conexões.

## Testes do receptor e do painel

### 1. API e persistência

Envie uma leitura fictícia no notebook/Ubuntu (se habilitar token, adicione
`-H 'Authorization: Bearer SEU_TOKEN'`):

```bash
curl -i http://127.0.0.1:49173/api/medicoes \
  -H 'Content-Type: application/json' \
  -d '{"dispositivo":"teste","inicializacao":"teste01","sequencia":1,"recebido_ms":2000,"temp_aht":25.12,"umidade":60.25,"pressao":1013.25,"temp_bmp":26.0}'
```

Esperado: HTTP 201 no primeiro envio; 200 ao repetir, sem duplicar a medição.
Depois reinicie com `docker compose restart receptor` e repita a mesma leitura:
deve continuar retornando 200, comprovando a preservação do histórico.

Para consultar o banco dentro do container:

```bash
docker compose exec -T receptor python -c "import sqlite3; c=sqlite3.connect('/dados/dados.sqlite3'); print(*c.execute('SELECT recebido_em,temp_aht,umidade,pressao,temp_bmp FROM medicoes ORDER BY id DESC LIMIT 10'), sep='\n')"
```

### 2. Hardware e mudança de rede

- Teste Arduino → rádio → ESP32 → container e confirme a gravação real.
- Desconecte temporariamente a rede e depois reconecte: confira o reenvio sem
  duplicar registros. O ESP32 mantém somente a medição mais recente em RAM;
  uma leitura nova substitui a pendente antiga. Não há fila de histórico.
- Confira pelo menos dois ciclos de coleta/envio de 60 s. Atualize ambos os
  firmwares, que agora configuram payload RF explícito de 16 bytes.
- Troque SSID, senha e servidor pelo monitor serial, salve e confira a nova conexão.
- Reinicie o ESP32 e confirme que a configuração foi mantida. Reiniciar perde
  as leituras pendentes em RAM, mas não a configuração nem o banco do servidor.

### Diagnóstico de demora nas confirmações

O receptor agrupa cabeçalhos e corpo das respostas em uma escrita com `flush`,
usa TCP_NODELAY e fecha a conexão após a resposta. Assim, o JSON pequeno não
depende de uma segunda escrita TCP separada dos cabeçalhos.

Os logs `[TEMPO_SERVIDOR]` identificam dispositivo, boot e sequência e mostram:

- `corpo`: leitura e validação do JSON após a interpretação dos cabeçalhos.
- `banco`: abertura do SQLite, inserção/checagem de repetição e commit.
- `envio`: preparação e escrita da resposta no socket. Não comprova a chegada
  nem o recebimento da confirmação pelo ESP32.

Compare a sequência com a linha `[HTTP]` do ESP32 (o detalhamento TCP foi removido). Se banco/envio forem rápidos
e o ESP32 continuar esperando segundos, investigue entrega/recepção TCP; se
`corpo` demorar, parte da espera ocorreu recebendo o JSON. Esses logs não medem
o tempo anterior à entrada do handler (por exemplo, chegada dos cabeçalhos).

### 3. Suíte automática do receptor

Dentro da pasta `servidor`, com Python 3 disponível:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Os testes usam servidor HTTP em loopback e banco temporário. Não substituem
os testes físicos do ESP32, do hotspot nem a execução real do container.

A suíte contém 17 testes: nove do recebimento existente e oito do painel,
cobrindo autenticação, arquivos locais, filtros, ausência de dados, resumo,
agrupamento, ponto de orvalho e exportação integral. O painel também foi
verificado no navegador em layout estreito e desktop, com dados sintéticos em
um banco temporário separado. A construção Docker deve ser confirmada no
Ubuntu/Pop!_OS; não havia Docker disponível na máquina de desenvolvimento.

## Observações do protocolo

Os firmwares Arduino e ESP32 foram refatorados para coleta periódica. O
pacote mantém os **quatro floats/16 bytes**, com tamanho RF explícito nos dois;
o pacote de 5 bytes da atividade anterior é outro protocolo.

O Arduino continua coletando temperatura/umidade se o BMP280 não inicializar;
nesse caso, envia NaN nos campos BMP e o ESP32 os converte para null. Um sensor
que inicializa mas produz pressão incorreta ainda precisa ser investigado.

O horário `recebido_em` é UTC de chegada ao servidor; `recebido_ms` é o tempo
desde o boot do ESP32 na recepção RF. Reenvios atrasados não representam coleta
no instante de chegada ao servidor. Pressão está em hPa; temperaturas em °C.

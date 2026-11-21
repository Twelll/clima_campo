# Gateway ESP32: encaminhamento de leituras periódicas

O ESP32 fica acordado, com Wi-Fi e NRF24 disponíveis. O Arduino define a
frequência: coleta/transmite a cada **60 segundos**, ajustável para 30 segundos.
Cada leitura válida recebida gera um POST ao servidor. Leituras já confirmadas
não são enviadas novamente em intervalos fixos.

O loop trata rádio, configuração serial e reconexão/reenvio por `millis()`.
Não há light sleep, tarefa adicional, fila de 60 itens nem transporte HTTP
personalizado. O envio usa `WiFiClient` e `HTTPClient` da plataforma. A chamada
HTTP é síncrona e tem timeout; a redução de frequência não a torna assíncrona
nem garante eliminar uma eventual latência da rede.

## Carregar os dois firmwares

Atualize também `../arduino/arduino.ino`. Os dois agora configuram explicitamente
o payload RF em 16 bytes e devem ser carregados juntos. Pinos, endereço, canal e
ordem dos quatro floats foram mantidos. O contrato JSON e o servidor não mudam.

Abra `esp32.ino` na Arduino IDE com estes arquivos na mesma pasta:

```text
esp32.ino
config.h
configuracao_rede.h
envio_rede.h
```

Os arquivos `requisicao_http.h` e seu teste antigo foram removidos da arquitetura.
Se você estiver usando uma cópia em outra pasta, substitua pelos arquivos atuais.

## Configurar pelo monitor serial

115200 baud, finalizar com nova linha, um comando por vez:

```text
ssid NOME_DO_WIFI_OU_HOTSPOT
senha SENHA_DO_WIFI
servidor http://IP_DO_NOTEBOOK:49173/api/medicoes
salvar
status
```

Não coloque aspas; espaços no nome/senha são preservados. `senha` sem argumento
configura rede aberta. `token VALOR` configura autenticação e `token` sem argumento
remove o token. `ajuda` lista os comandos. Senha e token não são impressos.

As configurações existentes em NVS continuam válidas, com prioridade sobre
`config.h`. Não é necessário reconfigurar após upload normal sem apagar NVS.
O monitor serial permanece disponível; não há janela de configuração ou reset
obrigatório para digitar. Durante um POST, os comandos podem aguardar até o timeout.

## Falhas

Há somente **uma medição pendente**. Se o envio falhar, ela pode ser reenviada
após 30 s; se chegar uma medição nova antes da confirmação, substitui a anterior,
com aviso no serial. Essa política privilegia o valor atual e não preserva todo
o histórico durante quedas. Reiniciar perde a medição pendente em RAM.

O servidor continua evitando duplicações por dispositivo, boot e sequência.
HTTP 201 indica nova gravação; HTTP 200 indica medição já gravada. Os logs agora
são curtos: `[RF]`, `[WiFi]` e `[HTTP]`; os diagnósticos detalhados TCP foram retirados.

## Teste físico

1. Suba o container conforme `../servidor/README.md`.
2. Ligue o ESP32, configure se necessário e aguarde conexão Wi-Fi.
3. Ligue/reinicie o Arduino. Ele faz uma coleta imediata e as próximas a cada 60 s.
4. Confira um `[RF]` e uma confirmação HTTP por coleta.
5. Espere pelo menos dois ciclos completos e teste reconexão/mudança de rede.

O backend não precisa ser reenviado/reconstruído por causa desta refatoração.
O pacote de 5 bytes da atividade anterior é outro protocolo e não deve ser
usado com estes firmwares de quatro floats/16 bytes.

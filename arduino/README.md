# Arduino Uno: coleta e transmissão periódicas

Abra `arduino.ino` e carregue no Uno. Monitor serial: **9600 baud**.

No começo do sketch:

```cpp
constexpr unsigned long INTERVALO_LEITURA_MS = 60000UL;
```

Use `30000UL` para coletar/transmitir a cada 30 segundos. O agendamento usa
`millis()`, com subtração sem sinal para lidar com transbordamento, sem um
`delay(60000)` nem leituras contínuas. A primeira coleta é imediata; um ciclo
atrasado não dispara várias leituras de recuperação em sequência.

Sensores e rádio só são acionados pelo ciclo de coleta/envio. O NRF24 do Uno
fica em power-down entre transmissões; `millis()` não coloca a CPU do Uno em sono.

A ausência do BMP280 não trava o AHT20: os campos BMP ficam NaN e o gateway
os representa como null no JSON. Se o AHT20 falhar, não transmite essa leitura
e tenta inicializá-lo novamente no próximo ciclo. Isso não calibra nem corrige
um BMP280 que responde mas produz valores incorretos.

Atualize também o ESP32: ambos configuram explicitamente payload RF de 16 bytes.
Ligue primeiro o receptor ESP32 e depois o Uno para receber a primeira coleta.
Não houve mudança de pinos, endereço RF, canal ou ordem dos quatro floats.

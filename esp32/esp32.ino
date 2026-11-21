#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

constexpr uint8_t CE_PIN = 4;
constexpr uint8_t CSN_PIN = 5;
RF24 radio(CE_PIN, CSN_PIN);
const byte endereco[6] = "00001";

struct __attribute__((packed)) DadosClima {
  float temp_aht;
  float umidade;
  float pressao;
  float temp_bmp;
};
static_assert(sizeof(float) == 4 && sizeof(DadosClima) == 16, "Pacote RF deve ter 16 bytes.");

#include "envio_rede.h"

void setup() {
  Serial.setRxBufferSize(1024);
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- Gateway: envia somente quando chega uma nova leitura ---");
  SPI.begin();
  if (!radio.begin()) {
    Serial.println("[RF] Erro de inicializacao; verifique SPI e alimentacao.");
    while (true) delay(1000);
  }
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(108);
  radio.setPayloadSize(sizeof(DadosClima));
  radio.openReadingPipe(0, endereco);
  radio.startListening();
  iniciarEnvioRede();
  Serial.println("[RF] Aguardando leituras periodicas do Arduino. Sem light sleep.");
}

void loop() {
  if (lerComandosRede()) aplicarNovaConfiguracao();
  while (radio.available()) {
    DadosClima dados;
    radio.read(&dados, sizeof(dados));
    registrarLeitura(dados);
  }
  // Reconexao e reenvio usam millis(). Nao repete leituras ja confirmadas.
  processarEnvioRede();
  delay(5);
}

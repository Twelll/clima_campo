#include <Wire.h>
#include <SPI.h>
#include <Adafruit_AHTX0.h>
#include <Adafruit_BMP280.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <math.h>

// Altere para 30000UL para coletar/enviar a cada 30 segundos.
constexpr unsigned long INTERVALO_LEITURA_MS = 60000UL;
constexpr uint8_t CE_PIN = 9;
constexpr uint8_t CSN_PIN = 10;

RF24 radio(CE_PIN, CSN_PIN);
Adafruit_AHTX0 aht;
Adafruit_BMP280 bmp;
const byte endereco[6] = "00001";

struct __attribute__((packed)) DadosClima {
  float temp_aht;
  float umidade;
  float pressao;
  float temp_bmp;
};
static_assert(sizeof(float) == 4 && sizeof(DadosClima) == 16, "Pacote RF deve ter 16 bytes.");

bool ahtDisponivel = false;
bool bmpDisponivel = false;
unsigned long ultimaLeitura = 0;

void coletarETransmitir() {
  if (!ahtDisponivel) ahtDisponivel = aht.begin();
  if (!ahtDisponivel) {
    Serial.println(F("[SENSOR] AHT20 indisponivel; nova tentativa no proximo ciclo."));
    return;
  }
  sensors_event_t umidade = {}, temperatura = {};
  if (!aht.getEvent(&umidade, &temperatura) ||
      !isfinite(temperatura.temperature) || !isfinite(umidade.relative_humidity) ||
      temperatura.temperature < -40 || temperatura.temperature > 85 ||
      umidade.relative_humidity < 0 || umidade.relative_humidity > 100) {
    ahtDisponivel = false;
    Serial.println(F("[SENSOR] Leitura AHT20 invalida; ciclo descartado."));
    return;
  }
  DadosClima pacote = {temperatura.temperature, umidade.relative_humidity, NAN, NAN};
  // A falta do BMP280 nao impede o envio de temperatura e umidade.
  if (!bmpDisponivel) bmpDisponivel = bmp.begin(0x77) || bmp.begin(0x76);
  if (bmpDisponivel) {
    pacote.pressao = bmp.readPressure() / 100.0f;
    pacote.temp_bmp = bmp.readTemperature();
  }
  Serial.print(F("[LEITURA] T=")); Serial.print(pacote.temp_aht, 2);
  Serial.print(F(" C | UR=")); Serial.print(pacote.umidade, 2);
  Serial.print(F(" % | P=")); Serial.print(pacote.pressao, 2);
  Serial.println(F(" hPa"));

  radio.powerUp();  // A biblioteca aguarda a estabilizacao do radio.
  const bool confirmado = radio.write(&pacote, sizeof(pacote));
  radio.powerDown();
  Serial.println(confirmado ? F("[RF] Pacote confirmado pelo receptor.") :
                              F("[RF] Sem ACK; nova leitura no proximo ciclo."));
}

void setup() {
  Serial.begin(9600);
  Serial.println(F("--- Transmissor: coleta periodica por millis() ---"));
  Wire.begin();
  ahtDisponivel = aht.begin();
  bmpDisponivel = bmp.begin(0x77) || bmp.begin(0x76);
  if (!bmpDisponivel) Serial.println(F("[SENSOR] BMP280 ausente; campos BMP serao NaN."));
  if (!radio.begin()) {
    Serial.println(F("[RF] Erro de inicializacao; verifique SPI e alimentacao."));
    while (true) delay(1000);
  }
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(108);  // Mesmo canal no receptor.
  radio.setPayloadSize(sizeof(DadosClima));
  radio.setRetries(5, 15);
  radio.openWritingPipe(endereco);
  radio.stopListening();
  radio.powerDown();
  // Primeira coleta imediata; as demais respeitam o intervalo, sem rajadas.
  ultimaLeitura = millis() - INTERVALO_LEITURA_MS;
  Serial.print(F("[CONFIG] Intervalo de coleta/envio (ms): "));
  Serial.println(INTERVALO_LEITURA_MS);
}

void loop() {
  const unsigned long agora = millis();
  // Subtracao sem sinal continua correta quando millis() transborda.
  if (agora - ultimaLeitura < INTERVALO_LEITURA_MS) return;
  ultimaLeitura = agora;
  coletarETransmitir();
}

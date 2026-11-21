#pragma once
#include <stdint.h>

// Valores iniciais. A configuracao salva pelo monitor serial tem prioridade.
const char WIFI_SSID[] = "";
const char WIFI_SENHA[] = "";
const char SERVIDOR_URL[] = "http://192.168.1.100:49173/api/medicoes";
const char API_TOKEN[] = "";

// O Arduino define a frequencia de coleta/envio (60 s por padrao).
// No ESP32, estes intervalos so controlam recuperacao de falhas, por millis().
constexpr uint32_t INTERVALO_REENVIO_MS = 30000;
constexpr uint32_t INTERVALO_RECONEXAO_MS = 15000;
constexpr int32_t HTTP_CONEXAO_TIMEOUT_MS = 5000;
constexpr uint16_t HTTP_RESPOSTA_TIMEOUT_MS = 10000;

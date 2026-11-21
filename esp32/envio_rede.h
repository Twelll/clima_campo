#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <esp_system.h>
#include <math.h>
#include "configuracao_rede.h"

// Uma unica medicao pendente. Nao ha fila nem tarefa de rede adicional.
struct LeituraPendente {
  DadosClima dados;
  uint32_t sequencia;
  uint32_t recebidoMs;
};
LeituraPendente pendente;
bool temPendente = false;
bool tentarImediato = false;
bool conexaoIniciada = false;
bool estavaConectado = false;
uint32_t sequencia = 0;
uint32_t ultimaReconexao = 0;
uint32_t ultimaTentativa = 0;
char dispositivo[18];
char inicializacao[17];

bool redeConfigurada() {
  return rede.ssid[0] != '\0' && urlValida(rede.url);
}

String numeroJson(float valor) {
  return isfinite(valor) ? String(valor, 2) : String("null");
}

bool enviarAoServidor(const LeituraPendente& leitura) {
  String json;
  json.reserve(320);
  json = "{\"dispositivo\":\""; json += dispositivo;
  json += "\",\"inicializacao\":\""; json += inicializacao;
  json += "\",\"sequencia\":"; json += String(leitura.sequencia);
  json += ",\"recebido_ms\":"; json += String(leitura.recebidoMs);
  json += ",\"temp_aht\":"; json += numeroJson(leitura.dados.temp_aht);
  json += ",\"umidade\":"; json += numeroJson(leitura.dados.umidade);
  json += ",\"pressao\":"; json += numeroJson(leitura.dados.pressao);
  json += ",\"temp_bmp\":"; json += numeroJson(leitura.dados.temp_bmp);
  json += "}";

  // Cliente padrao da plataforma, sem transporte ou buffer HTTP personalizados.
  WiFiClient cliente;
  HTTPClient http;
  http.setConnectTimeout(HTTP_CONEXAO_TIMEOUT_MS);
  http.setTimeout(HTTP_RESPOSTA_TIMEOUT_MS);
  http.setReuse(false);
  if (!http.begin(cliente, rede.url)) {
    Serial.println("[HTTP] URL invalida.");
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  if (rede.token[0]) http.addHeader("Authorization", String("Bearer ") + rede.token);
  const uint32_t inicio = millis();
  const int codigo = http.POST(json);
  const bool confirmado = codigo == 200 || codigo == 201;
  if (codigo > 0) {
    Serial.printf("[HTTP] Leitura %lu: HTTP %d, %lu ms (%s).\n",
                  static_cast<unsigned long>(leitura.sequencia), codigo,
                  static_cast<unsigned long>(millis() - inicio),
                  confirmado ? "confirmada" : "nao confirmada");
  } else {
    Serial.printf("[HTTP] Leitura %lu: %s.\n",
                  static_cast<unsigned long>(leitura.sequencia),
                  HTTPClient::errorToString(codigo).c_str());
  }
  http.end();
  return confirmado;
}

void iniciarEnvioRede() {
  carregarConfiguracao();
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  const uint64_t mac = ESP.getEfuseMac();
  snprintf(dispositivo, sizeof(dispositivo), "%04lx%08lx",
           static_cast<unsigned long>((mac >> 32) & 0xffff),
           static_cast<unsigned long>(mac & 0xffffffff));
  snprintf(inicializacao, sizeof(inicializacao), "%08lx%08lx",
           static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()));
  ajudaRede();
}

void registrarLeitura(const DadosClima& dados) {
  if (!isfinite(dados.temp_aht) || !isfinite(dados.umidade) ||
      dados.temp_aht < -40 || dados.temp_aht > 85 || dados.umidade < 0 || dados.umidade > 100) {
    Serial.println("[RF] Temperatura/umidade invalida; pacote descartado.");
    return;
  }
  if (temPendente) Serial.println("[REDE] Leitura anterior pendente substituida pela mais recente.");
  pendente = {dados, ++sequencia, millis()};
  temPendente = true;
  tentarImediato = true;
  Serial.printf("[RF] Leitura %lu: T=%.2f C UR=%.2f %% P=%.2f hPa T_BMP=%.2f C\n",
                static_cast<unsigned long>(pendente.sequencia), dados.temp_aht,
                dados.umidade, dados.pressao, dados.temp_bmp);
}

void aplicarNovaConfiguracao() {
  WiFi.disconnect(false, false);
  conexaoIniciada = false;
  estavaConectado = false;
  tentarImediato = temPendente;
}

void processarEnvioRede() {
  if (!redeConfigurada()) return;
  if (!conexaoIniciada) {
    WiFi.begin(rede.ssid, rede.senha);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    conexaoIniciada = true;
    ultimaReconexao = millis();
    Serial.printf("[WiFi] Conectando a %s...\n", rede.ssid);
  }
  if (WiFi.status() != WL_CONNECTED) {
    estavaConectado = false;
    if (static_cast<uint32_t>(millis() - ultimaReconexao) >= INTERVALO_RECONEXAO_MS) {
      WiFi.reconnect();
      ultimaReconexao = millis();
      Serial.println("[WiFi] Tentando reconectar...");
    }
    return;
  }
  if (!estavaConectado) {
    Serial.printf("[WiFi] Conectado. IP=%s RSSI=%ld dBm\n",
                  WiFi.localIP().toString().c_str(), static_cast<long>(WiFi.RSSI()));
    estavaConectado = true;
  }
  if (!temPendente) return;
  if (!tentarImediato && static_cast<uint32_t>(millis() - ultimaTentativa) < INTERVALO_REENVIO_MS) return;
  tentarImediato = false;
  if (enviarAoServidor(pendente)) temPendente = false;
  else Serial.println("[REDE] Ultima leitura mantida para tentativa posterior.");
  ultimaTentativa = millis();
}

#pragma once
#include <Preferences.h>
#include "config.h"

// Um unico registro NVS evita misturar valores novos e antigos em caso de
// interrupcao entre as escritas. Apenas o loop principal acessa estas variaveis.
struct ConfiguracaoRede {
  uint32_t versao;
  char ssid[33];
  char senha[65];
  char url[256];
  char token[129];
};
ConfiguracaoRede rede = {};
ConfiguracaoRede rascunhoRede = {};

bool urlValida(const char* url) {
  const String valor(url);
  if (!valor.startsWith("http://") || !valor.endsWith("/api/medicoes") ||
      valor.length() <= 7 + String("/api/medicoes").length()) return false;
  for (size_t i = 0; i < valor.length(); ++i) {
    if (static_cast<unsigned char>(valor[i]) <= 32 || valor[i] == '@') return false;
  }
  return true;
}

void carregarConfiguracao() {
  rede.versao = 1;
  snprintf(rede.ssid, sizeof(rede.ssid), "%s", WIFI_SSID);
  snprintf(rede.senha, sizeof(rede.senha), "%s", WIFI_SENHA);
  snprintf(rede.url, sizeof(rede.url), "%s", SERVIDOR_URL);
  snprintf(rede.token, sizeof(rede.token), "%s", API_TOKEN);
  Preferences memoria;
  if (memoria.begin("estacao-rede", false)) {
    if (memoria.isKey("config") && memoria.getBytesLength("config") == sizeof(rede)) {
      ConfiguracaoRede salva = {};
      if (memoria.getBytes("config", &salva, sizeof(salva)) == sizeof(salva) &&
          salva.versao == 1 && salva.ssid[32] == '\0' && salva.senha[64] == '\0' &&
          salva.url[255] == '\0' && salva.token[128] == '\0' && urlValida(salva.url)) {
        rede = salva;
      }
    }
    memoria.end();
  } else {
    Serial.println("[CONFIG] NVS indisponivel; usando valores de config.h.");
  }
  rascunhoRede = rede;
}

void ajudaRede() {
  Serial.println("[CONFIG] Comandos (115200 baud, finalizar com nova linha):");
  Serial.println("  ssid NOME_DA_REDE");
  Serial.println("  senha SENHA_DA_REDE   (senha sem argumento = rede aberta)");
  Serial.println("  servidor http://IP_DO_NOTEBOOK:49173/api/medicoes");
  Serial.println("  token SEU_TOKEN      (token sem argumento = sem token)");
  Serial.println("  salvar               (grava e aplica sem reiniciar)");
  Serial.println("  status               (mostra configuracao ativa, sem segredos)");
  Serial.println("  ajuda");
}

bool definirCampo(const String& valor, char* campo, size_t tamanho) {
  if (valor.length() >= tamanho) {
    Serial.println("[CONFIG] Valor longo demais; campo nao alterado.");
    return false;
  }
  valor.toCharArray(campo, tamanho);
  Serial.println("[CONFIG] Campo atualizado no rascunho. Digite salvar para aplicar.");
  return true;
}

bool executarComandoRede(const String& linha) {
  if (linha == "ajuda") ajudaRede();
  else if (linha == "status") {
    Serial.printf("[CONFIG] SSID ativo: %s | Servidor: %s | Token: %s\n",
                  rede.ssid, rede.url, rede.token[0] ? "configurado" : "nao configurado");
    Serial.printf("[CONFIG] Wi-Fi: %s | IP: %s\n",
                  WiFi.status() == WL_CONNECTED ? "conectado" : "desconectado",
                  WiFi.localIP().toString().c_str());
  } else if (linha.startsWith("ssid ")) {
    definirCampo(linha.substring(5), rascunhoRede.ssid, sizeof(rascunhoRede.ssid));
  } else if (linha == "senha" || linha.startsWith("senha ")) {
    definirCampo(linha == "senha" ? String("") : linha.substring(6),
                 rascunhoRede.senha, sizeof(rascunhoRede.senha));
  } else if (linha.startsWith("servidor ")) {
    const String valor = linha.substring(9);
    if (urlValida(valor.c_str())) definirCampo(valor, rascunhoRede.url, sizeof(rascunhoRede.url));
    else Serial.println("[CONFIG] Use http://IP:PORTA/api/medicoes, sem espacos.");
  } else if (linha == "token" || linha.startsWith("token ")) {
    definirCampo(linha == "token" ? String("") : linha.substring(6),
                 rascunhoRede.token, sizeof(rascunhoRede.token));
  } else if (linha == "salvar") {
    if (rascunhoRede.ssid[0] == '\0' || !urlValida(rascunhoRede.url)) {
      Serial.println("[CONFIG] Informe SSID e servidor validos antes de salvar.");
      return false;
    }
    Preferences memoria;
    bool salvo = false;
    if (memoria.begin("estacao-rede", false)) {
      salvo = memoria.putBytes("config", &rascunhoRede, sizeof(rascunhoRede)) == sizeof(rascunhoRede);
      memoria.end();
    }
    if (!salvo) {
      Serial.println("[CONFIG] Falha ao gravar NVS; configuracao ativa preservada.");
      return false;
    }
    rede = rascunhoRede;
    Serial.println("[CONFIG] Salvo. Aplicando rede/servidor sem reiniciar.");
    return true;
  } else if (linha.length()) Serial.println("[CONFIG] Comando desconhecido. Digite ajuda.");
  return false;
}

bool lerComandosRede() {
  static String linha;
  static bool excedeu = false;
  bool aplicar = false;
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (!excedeu) aplicar = executarComandoRede(linha) || aplicar;
      else Serial.println("[CONFIG] Comando longo demais; descartado.");
      linha = "";
      excedeu = false;
    } else if (!excedeu) {
      if (linha.length() >= 384) excedeu = true;
      else if (static_cast<unsigned char>(c) >= 32) linha += c;
    }
  }
  return aplicar;
}

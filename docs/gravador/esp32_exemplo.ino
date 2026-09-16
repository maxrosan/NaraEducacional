/*
 * Exemplo mínimo de integração do gravador NARA — ESP32 (Arduino core).
 *
 * Usa apenas bibliotecas que já vêm com o core do ESP32:
 *   WiFi.h, HTTPClient.h, Preferences.h  (nenhuma dependência externa)
 *
 * O que este sketch faz:
 *   1. conecta no WiFi;
 *   2. se ainda não houver token salvo, troca um CÓDIGO DE PAREAMENTO por um
 *      token permanente e o guarda na NVS (sobrevive a reboot);
 *   3. envia um WAV (aqui, um buffer de exemplo) via multipart/form-data;
 *   4. trata as respostas: 201/200 = ok, 401 = reparear, demais = erro.
 *
 * O JSON de resposta é lido com busca de substring de propósito — para não
 * exigir ArduinoJson. Em produção, use um parser de verdade.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>

// ----------------------------------------------------------------------------
// Configuração
// ----------------------------------------------------------------------------
const char* WIFI_SSID     = "REDE_DA_ESCOLA";
const char* WIFI_SENHA    = "senha";
const char* API_BASE      = "http://192.168.0.10:8001";  // host da API NARA
const char* DEVICE_ID     = "AA:BB:CC:11:22:33";         // use o MAC real
const char* NOME_APARELHO = "Gravador Sala 5C";

// Código gerado na plataforma (Cadastros -> Dispositivos). Só é usado no
// primeiro boot / re-pareamento; depois o token salvo assume.
const char* CODIGO_PAREAMENTO = "RHFF89";

Preferences prefs;
String token;

// ----------------------------------------------------------------------------
// Utilidades
// ----------------------------------------------------------------------------

// Extrai o valor de uma chave string simples do JSON: {"chave":"valor"}
String extrairCampo(const String& json, const String& chave) {
  String marcador = "\"" + chave + "\":\"";
  int i = json.indexOf(marcador);
  if (i < 0) return "";
  i += marcador.length();
  int fim = json.indexOf('"', i);
  if (fim < 0) return "";
  return json.substring(i, fim);
}

// UUID v4 a partir do gerador de aleatórios do chip (esp_random()).
String gerarUUID() {
  char buf[37];
  uint8_t b[16];
  for (int i = 0; i < 16; i++) b[i] = (uint8_t)(esp_random() & 0xFF);
  b[6] = (b[6] & 0x0F) | 0x40;  // versão 4
  b[8] = (b[8] & 0x3F) | 0x80;  // variante
  snprintf(buf, sizeof(buf),
           "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           b[0],b[1],b[2],b[3], b[4],b[5], b[6],b[7], b[8],b[9],
           b[10],b[11],b[12],b[13],b[14],b[15]);
  return String(buf);
}

// ----------------------------------------------------------------------------
// 1. Pareamento — POST /api/dispositivos/parear/  (sem token)
// ----------------------------------------------------------------------------
bool parear() {
  HTTPClient http;
  http.begin(String(API_BASE) + "/api/dispositivos/parear/");
  http.addHeader("Content-Type", "application/json");

  String corpo = String("{\"codigo\":\"") + CODIGO_PAREAMENTO +
                 "\",\"device_id\":\"" + DEVICE_ID +
                 "\",\"nome\":\"" + NOME_APARELHO + "\"}";

  int status = http.POST(corpo);
  String resposta = http.getString();
  http.end();

  Serial.printf("[PAREAR] HTTP %d\n", status);
  Serial.println(resposta);

  if (status == 201) {
    token = extrairCampo(resposta, "token");
    if (token.length() > 0) {
      prefs.putString("token", token);   // persiste na NVS
      Serial.println("[PAREAR] Token salvo.");
      return true;
    }
  }
  // codigo_invalido = expirado (10 min) ou já usado -> gerar outro na plataforma
  return false;
}

// ----------------------------------------------------------------------------
// 2. Envio do áudio — POST /api/dispositivos/audio/  (Bearer token)
//
// multipart/form-data montado à mão. Estrutura de cada parte:
//   --BOUNDARY\r\n
//   Content-Disposition: form-data; name="campo"\r\n
//   \r\n
//   valor\r\n
// e o corpo termina em --BOUNDARY--\r\n
// ----------------------------------------------------------------------------
int enviarAudio(const uint8_t* wav, size_t tamanho, const String& uploadId) {
  const String boundary = "----NaraBoundary7d91";
  const String hifens   = "--";
  const String crlf     = "\r\n";

  String cabecalho;
  cabecalho += hifens + boundary + crlf;
  cabecalho += "Content-Disposition: form-data; name=\"upload_id\"" + crlf + crlf;
  cabecalho += uploadId + crlf;

  cabecalho += hifens + boundary + crlf;
  cabecalho += "Content-Disposition: form-data; name=\"arquivo\"; filename=\"rec.wav\"" + crlf;
  cabecalho += "Content-Type: audio/wav" + crlf + crlf;

  String rodape = crlf + hifens + boundary + hifens + crlf;

  size_t total = cabecalho.length() + tamanho + rodape.length();
  uint8_t* corpo = (uint8_t*)malloc(total);
  if (!corpo) {
    Serial.println("[ENVIO] Sem memória — envie em blocos ou reduza o buffer.");
    return -1;
  }
  memcpy(corpo, cabecalho.c_str(), cabecalho.length());
  memcpy(corpo + cabecalho.length(), wav, tamanho);
  memcpy(corpo + cabecalho.length() + tamanho, rodape.c_str(), rodape.length());

  HTTPClient http;
  http.begin(String(API_BASE) + "/api/dispositivos/audio/");
  http.addHeader("Authorization", "Bearer " + token);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  int status = http.POST(corpo, total);
  String resposta = http.getString();
  http.end();
  free(corpo);

  Serial.printf("[ENVIO] HTTP %d\n", status);
  Serial.println(resposta);
  return status;
}

// ----------------------------------------------------------------------------
// 3. Feedback — GET /api/dispositivos/audio/<upload_id>/
//
// O aparelho não tem tela, e a turma/criança só são conhecidas DEPOIS da
// transcrição (assíncrona no servidor). Então: envia, espera, consulta até
// feedback.sinal sair de "aguardando" e acende o LED correspondente.
//
// A professora fala tudo na MESMA gravação:
//   "Estou na turma Nível 3A. Alice Marreiro brincou muito hoje."
// O servidor identifica a turma pela fala, confere se ela é permitida a este
// gravador e só então registra a criança.
// ----------------------------------------------------------------------------
void aguardarFeedback(const String& uploadId, int tentativas = 20, int esperaMs = 3000) {
  for (int i = 0; i < tentativas; i++) {
    delay(esperaMs);

    HTTPClient http;
    http.begin(String(API_BASE) + "/api/dispositivos/audio/" + uploadId + "/");
    http.addHeader("Authorization", "Bearer " + token);
    int status = http.GET();
    String resposta = http.getString();
    http.end();

    if (status != 200) {
      Serial.printf("[FEEDBACK] HTTP %d — tentando de novo\n", status);
      continue;
    }

    String sinal = extrairCampo(resposta, "sinal");
    String mensagem = extrairCampo(resposta, "mensagem");

    if (sinal == "aguardando") {
      Serial.println("[FEEDBACK] ainda processando...");
      continue;
    }

    Serial.printf("[FEEDBACK] %s: %s\n", sinal.c_str(), mensagem.c_str());
    if (sinal == "ok") {
      Serial.println(">>> LED VERDE: turma e criança registradas.");
    } else if (sinal == "atencao") {
      // turma não autorizada, turma não anunciada, ou nome não reconhecido
      Serial.println(">>> LED AMARELO: a professora precisa repetir/ajustar.");
    } else {
      Serial.println(">>> LED VERMELHO: nada foi registrado.");
    }
    return;
  }
  Serial.println("[FEEDBACK] servidor demorou demais; consultar mais tarde.");
}

// ----------------------------------------------------------------------------
// WAV de exemplo (silêncio) — no aparelho real, use o buffer vindo do I2S.
// Cabeçalho: PCM 16 bits, mono, 16 kHz.
// ----------------------------------------------------------------------------
void montarCabecalhoWav(uint8_t* buf, uint32_t amostras, uint32_t sampleRate) {
  uint32_t bytesDados = amostras * 2;
  uint32_t byteRate   = sampleRate * 2;
  memcpy(buf, "RIFF", 4);
  *(uint32_t*)(buf + 4)  = 36 + bytesDados;
  memcpy(buf + 8, "WAVEfmt ", 8);
  *(uint32_t*)(buf + 16) = 16;      // tamanho do bloco fmt
  *(uint16_t*)(buf + 20) = 1;       // PCM
  *(uint16_t*)(buf + 22) = 1;       // mono
  *(uint32_t*)(buf + 24) = sampleRate;
  *(uint32_t*)(buf + 28) = byteRate;
  *(uint16_t*)(buf + 32) = 2;       // block align
  *(uint16_t*)(buf + 34) = 16;      // bits por amostra
  memcpy(buf + 36, "data", 4);
  *(uint32_t*)(buf + 40) = bytesDados;
}

// ----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);

  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.print("Conectando ao WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println(" ok!");

  prefs.begin("nara", false);
  token = prefs.getString("token", "");

  if (token.length() == 0) {
    Serial.println("Sem token — pareando...");
    if (!parear()) {
      Serial.println("Pareamento falhou. Gere outro código na plataforma.");
      return;
    }
  } else {
    Serial.println("Token recuperado da NVS.");
  }

  // --- Envio de teste: 1 segundo de silêncio ---
  const uint32_t sampleRate = 16000;
  const uint32_t amostras   = sampleRate;            // 1 s
  const size_t   tamanho    = 44 + amostras * 2;
  uint8_t* wav = (uint8_t*)calloc(tamanho, 1);
  montarCabecalhoWav(wav, amostras, sampleRate);

  String uploadId = gerarUUID();   // MESMO id em todos os retries deste áudio
  int status = enviarAudio(wav, tamanho, uploadId);

  // Política de retry: só timeout e 5xx justificam reenviar — sempre com o
  // mesmo upload_id (o servidor devolve 200 com "duplicado": true).
  int tentativas = 0;
  while ((status < 0 || status >= 500) && tentativas < 3) {
    tentativas++;
    Serial.printf("[RETRY] tentativa %d\n", tentativas);
    delay(2000 * tentativas);                 // backoff simples
    status = enviarAudio(wav, tamanho, uploadId);
  }

  if (status == 201 || status == 200) {
    Serial.println(">>> Áudio recebido pelo servidor. Aguardando o processamento...");
    // O "recebido" só diz que o arquivo chegou. Quem diz se a TURMA foi
    // reconhecida e se a CRIANÇA entrou no relato é o feedback abaixo.
    aguardarFeedback(uploadId);
  } else if (status == 401) {
    Serial.println(">>> Token inválido/revogado: apagar NVS e parear de novo.");
    prefs.remove("token");
  } else {
    Serial.println(">>> LED VERMELHO: erro definitivo (ver 'codigo' na resposta).");
  }

  free(wav);
}

void loop() {
  delay(10000);
}

/**
 * Smart-Stua Sensor Node Firmware v2
 * Hardware: ESP32 + DHT22 + SIM800L + Relay (GPIO)
 *
 * Dual Connectivity Strategy:
 *   1. WiFi (Primary)  — ESP32 built-in; faster, free after setup
 *   2. GSM/GPRS (Fallback) — SIM800L; used when WiFi unavailable
 *
 * Communication: HTTP POST JSON → Django REST API /api/readings/
 * Interval: Deep sleep between 15-minute readings (battery/solar optimised)
 */

#include <Arduino.h>
#include <DHT.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <HardwareSerial.h>
#include "esp_sleep.h"

// ─── Pin Definitions ─────────────────────────────────────────────────────────
#define DHT_PIN      4       // DHT22 data pin
#define DHT_TYPE     DHT22
#define RELAY_PIN    26      // Grain dryer relay (HIGH = ON)
#define SIM800_TX    17      // ESP32 TX → SIM800L RX
#define SIM800_RX    16      // ESP32 RX ← SIM800L TX

// ─── Node Configuration ───────────────────────────────────────────────────────
#define NODE_ID   "NODE_001"
#define API_KEY   "REPLACE_WITH_YOUR_API_KEY"

// ─── WiFi Credentials ─────────────────────────────────────────────────────────
// Primary network (e.g. office/store router)
#define WIFI_SSID_1  "Rafy"
#define WIFI_PASS_1  "edwinocaya2"
// Secondary fallback WiFi (optional — leave blank to skip)
#define WIFI_SSID_2  ""
#define WIFI_PASS_2  ""

// ─── Server Configuration ─────────────────────────────────────────────────────
#define SERVER_HOST      "192.168.1.179"
#define SERVER_PORT      8000
#define READINGS_PATH    "/api/readings/"
#define COMMAND_PATH     "/api/devices/" NODE_ID "/command/?api_key=" API_KEY

// Full URLs
#define READINGS_URL  "http://" SERVER_HOST READINGS_PATH
#define COMMAND_URL   "http://" SERVER_HOST COMMAND_PATH

// ─── GSM APN (SIM card data plan) ────────────────────────────────────────────
// Change "internet" to your SIM provider's APN (e.g. "safaricom", "mtn", "airtel")
#define GSM_APN  "internet"

// ─── Timing ───────────────────────────────────────────────────────────────────
#define SLEEP_MINUTES    15
#define SLEEP_US         (SLEEP_MINUTES * 60ULL * 1000000ULL)
#define WIFI_TIMEOUT_MS  12000
#define HTTP_TIMEOUT_MS  15000

// ─── Globals ──────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
HardwareSerial sim800(1);

enum ConnMethod { CONN_NONE, CONN_WIFI, CONN_GSM };

// ─── Function Declarations ────────────────────────────────────────────────────
bool     readSensor(float &temp, float &hum);
ConnMethod connectivity_init();
bool     wifi_connect(const char *ssid, const char *pass);
bool     gsm_init();
bool     gsm_gprs_connect();
bool     http_post_wifi(const char *payload);
bool     http_post_gsm(const char *payload);
String   http_get_wifi(const char *url);
String   http_get_gsm(const char *path);
bool     gsm_send_at(const char *cmd, const char *expected, unsigned long timeout_ms);
String   gsm_send_at_resp(const char *cmd, unsigned long timeout_ms);
String   build_payload(float temp, float hum);
void     process_command(const String &body);
void     dryer_set(bool on);
void     go_sleep();

// ─── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println(F("\n=============================================="));
  Serial.println(F("  Smart-Stua Node v2.0 — Dual Connectivity"));
  Serial.println(F("  Node: " NODE_ID));
  Serial.println(F("=============================================="));

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  // 1. Read sensor
  float temperature, humidity;
  if (!readSensor(temperature, humidity)) {
    Serial.println(F("[FATAL] Sensor failed — sleeping"));
    go_sleep();
    return;
  }
  Serial.printf("[SENSOR] Temp=%.2f°C  Humidity=%.2f%%\n", temperature, humidity);

  // 2. Establish connectivity (WiFi preferred, GSM fallback)
  ConnMethod conn = connectivity_init();
  if (conn == CONN_NONE) {
    Serial.println(F("[ERROR] No connectivity available — sleeping"));
    go_sleep();
    return;
  }

  // 3. Build JSON payload
  String payload = build_payload(temperature, humidity);
  Serial.println(F("[HTTP] Sending reading..."));
  Serial.println(payload);

  // 4. POST reading
  bool posted = (conn == CONN_WIFI)
    ? http_post_wifi(payload.c_str())
    : http_post_gsm(payload.c_str());

  Serial.printf("[HTTP] POST %s\n", posted ? "OK" : "FAILED");

  // 5. Poll for dryer command
  Serial.println(F("[HTTP] Polling for dryer command..."));
  String cmd_body = (conn == CONN_WIFI)
    ? http_get_wifi(COMMAND_URL)
    : http_get_gsm(COMMAND_PATH);

  if (cmd_body.length() > 0) {
    process_command(cmd_body);
  }

  // 6. Sleep
  go_sleep();
}

void loop() { /* Deep sleep handles timing */ }

// ─── Sensor Read ──────────────────────────────────────────────────────────────
bool readSensor(float &temp, float &hum) {
  dht.begin();
  delay(2500);  // DHT22 warm-up

  for (int attempt = 0; attempt < 3; attempt++) {
    temp = dht.readTemperature();
    hum  = dht.readHumidity();
    if (!isnan(temp) && !isnan(hum) &&
        temp >= -40.0 && temp <= 80.0 &&
        hum  >=   0.0 && hum  <= 100.0) {
      return true;
    }
    Serial.printf("[SENSOR] Read attempt %d failed — retrying...\n", attempt + 1);
    delay(2000);
  }
  return false;
}

// ─── Connectivity Init ────────────────────────────────────────────────────────
ConnMethod connectivity_init() {
  // Try WiFi first (primary)
  Serial.println(F("\n[NET] Trying WiFi (primary)..."));
  if (wifi_connect(WIFI_SSID_1, WIFI_PASS_1)) {
    Serial.println(F("[NET] ✓ Connected via WiFi"));
    return CONN_WIFI;
  }

  // Try secondary WiFi (if configured)
  if (strlen(WIFI_SSID_2) > 0) {
    Serial.println(F("[NET] Trying WiFi (secondary)..."));
    if (wifi_connect(WIFI_SSID_2, WIFI_PASS_2)) {
      Serial.println(F("[NET] ✓ Connected via secondary WiFi"));
      return CONN_WIFI;
    }
  }

  // Fall back to GSM/GPRS
  Serial.println(F("[NET] WiFi unavailable — falling back to SIM800L GSM"));
  sim800.begin(9600, SERIAL_8N1, SIM800_RX, SIM800_TX);
  delay(1000);

  if (gsm_init() && gsm_gprs_connect()) {
    Serial.println(F("[NET] ✓ Connected via GSM/GPRS"));
    return CONN_GSM;
  }

  Serial.println(F("[NET] ✗ All connectivity methods failed"));
  return CONN_NONE;
}

// ─── WiFi Connection ──────────────────────────────────────────────────────────
bool wifi_connect(const char *ssid, const char *pass) {
  if (!ssid || strlen(ssid) == 0) return false;

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, pass);

  Serial.printf("[WiFi] Connecting to '%s'", ssid);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT_MS) {
      Serial.println(F(" TIMEOUT"));
      WiFi.disconnect(true);
      return false;
    }
    delay(500);
    Serial.print('.');
  }
  Serial.printf(" OK — IP: %s\n", WiFi.localIP().toString().c_str());
  return true;
}

// ─── HTTP POST via WiFi ───────────────────────────────────────────────────────
bool http_post_wifi(const char *payload) {
  HTTPClient http;
  http.begin(READINGS_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_MS);

  int code = http.POST(payload);
  http.end();

  Serial.printf("[WiFi HTTP] POST status: %d\n", code);
  return (code == 200 || code == 201);
}

// ─── HTTP GET via WiFi ────────────────────────────────────────────────────────
String http_get_wifi(const char *url) {
  HTTPClient http;
  http.begin(url);
  http.setTimeout(HTTP_TIMEOUT_MS);

  int code = http.GET();
  String body = "";
  if (code > 0) body = http.getString();
  http.end();

  Serial.printf("[WiFi HTTP] GET status: %d\n", code);
  return body;
}

// ─── GSM Init ─────────────────────────────────────────────────────────────────
bool gsm_init() {
  Serial.println(F("[GSM] Initialising SIM800L..."));
  for (int i = 0; i < 5; i++) {
    if (gsm_send_at("AT", "OK", 2000)) {
      gsm_send_at("ATE0", "OK", 2000);
      gsm_send_at("AT+CMEE=2", "OK", 2000);
      break;
    }
    if (i == 4) return false;
    delay(1000);
  }

  // Wait for network registration
  for (int i = 0; i < 30; i++) {
    String r = gsm_send_at_resp("AT+CREG?", 3000);
    if (r.indexOf("+CREG: 0,1") != -1 || r.indexOf("+CREG: 0,5") != -1) {
      Serial.println(F("[GSM] Network registered"));
      return true;
    }
    Serial.printf("[GSM] Registering... %d/30\n", i + 1);
    delay(2000);
  }
  return false;
}

// ─── GPRS Connect ─────────────────────────────────────────────────────────────
bool gsm_gprs_connect() {
  Serial.printf("[GPRS] Connecting with APN: %s\n", GSM_APN);
  gsm_send_at("AT+SAPBR=3,1,\"Contype\",\"GPRS\"", "OK", 5000);
  String cmd = "AT+SAPBR=3,1,\"APN\",\"";
  cmd += GSM_APN; cmd += "\"";
  gsm_send_at(cmd.c_str(), "OK", 5000);
  gsm_send_at("AT+SAPBR=1,1", "OK", 30000);
  String s = gsm_send_at_resp("AT+SAPBR=2,1", 5000);
  if (s.indexOf(",1,") != -1) { Serial.println(F("[GPRS] Connected")); return true; }
  return false;
}

// ─── HTTP POST via GSM ────────────────────────────────────────────────────────
bool http_post_gsm(const char *payload) {
  gsm_send_at("AT+HTTPINIT", "OK", 5000);
  gsm_send_at("AT+HTTPPARA=\"CID\",1", "OK", 3000);

  String url = "AT+HTTPPARA=\"URL\",\"http://";
  url += SERVER_HOST; url += READINGS_PATH; url += "\"";
  gsm_send_at(url.c_str(), "OK", 5000);
  gsm_send_at("AT+HTTPPARA=\"CONTENT\",\"application/json\"", "OK", 3000);

  String dl = "AT+HTTPDATA="; dl += strlen(payload); dl += ",10000";
  gsm_send_at(dl.c_str(), "DOWNLOAD", 5000);
  sim800.print(payload);
  delay(500);

  gsm_send_at("AT+HTTPACTION=1", "+HTTPACTION:", HTTP_TIMEOUT_MS);
  String st = gsm_send_at_resp("AT+HTTPSTATUS", 3000);
  gsm_send_at("AT+HTTPTERM", "OK", 3000);
  return st.indexOf(",200,") != -1 || st.indexOf(",201,") != -1;
}

// ─── HTTP GET via GSM ─────────────────────────────────────────────────────────
String http_get_gsm(const char *path) {
  gsm_send_at("AT+HTTPINIT", "OK", 5000);
  gsm_send_at("AT+HTTPPARA=\"CID\",1", "OK", 3000);
  String url = "AT+HTTPPARA=\"URL\",\"http://";
  url += SERVER_HOST; url += path; url += "\"";
  gsm_send_at(url.c_str(), "OK", 5000);
  gsm_send_at("AT+HTTPACTION=0", "+HTTPACTION:", HTTP_TIMEOUT_MS);
  String r = gsm_send_at_resp("AT+HTTPREAD", 5000);
  gsm_send_at("AT+HTTPTERM", "OK", 3000);
  return r;
}

// ─── AT Command Helpers ───────────────────────────────────────────────────────
bool gsm_send_at(const char *cmd, const char *expected, unsigned long timeout_ms) {
  sim800.println(cmd);
  unsigned long start = millis();
  String buf = "";
  while (millis() - start < timeout_ms) {
    while (sim800.available()) buf += (char)sim800.read();
    if (buf.indexOf(expected) != -1) return true;
  }
  return false;
}

String gsm_send_at_resp(const char *cmd, unsigned long timeout_ms) {
  sim800.println(cmd);
  unsigned long start = millis();
  String buf = "";
  while (millis() - start < timeout_ms) {
    while (sim800.available()) buf += (char)sim800.read();
  }
  return buf;
}

// ─── Payload Builder ──────────────────────────────────────────────────────────
String build_payload(float temp, float hum) {
  String j = "{";
  j += "\"node_id\":\"" NODE_ID "\",";
  j += "\"temperature\":" + String(temp, 2) + ",";
  j += "\"humidity\":"    + String(hum,  2) + ",";
  j += "\"api_key\":\"" API_KEY "\"";
  j += "}";
  return j;
}

// ─── Dryer Command ────────────────────────────────────────────────────────────
void process_command(const String &body) {
  if (body.indexOf("\"ON\"") != -1) {
    Serial.println(F("[DRYER] → ON"));
    dryer_set(true);
  } else if (body.indexOf("\"OFF\"") != -1) {
    Serial.println(F("[DRYER] → OFF"));
    dryer_set(false);
  } else {
    Serial.println(F("[DRYER] No pending command"));
  }
}

void dryer_set(bool on) {
  digitalWrite(RELAY_PIN, on ? HIGH : LOW);
  Serial.printf("[RELAY] Dryer %s\n", on ? "ACTIVATED" : "DEACTIVATED");
}

// ─── Deep Sleep ───────────────────────────────────────────────────────────────
void go_sleep() {
  Serial.printf("[SLEEP] Deep sleep for %d min...\n", SLEEP_MINUTES);
  Serial.flush();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  // Put SIM800L to sleep if it was used
  sim800.println("AT+CSCLK=2");
  esp_sleep_enable_timer_wakeup(SLEEP_US);
  esp_deep_sleep_start();
}

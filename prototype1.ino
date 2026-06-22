/**
 * Project: SMART-STUA / SmartSilo Grain Monitoring Node
 * Hardware: ESP32, DHT22, Analog Moisture Sensor
 * Protocol: MQTTS over TLS/SSL → HiveMQ Cloud (port 8883)
 *
 * Requires libraries (install via Arduino Library Manager):
 *   - PubSubClient  (by Nick O'Leary)
 *   - ArduinoJson   (by Benoit Blanchon)
 *   - DHT sensor library + Adafruit Unified Sensor
 *
 * TLS Note:
 *   WiFiClientSecure is used for the encrypted connection to HiveMQ Cloud.
 *   setInsecure() skips root CA verification — acceptable for field nodes
 *   where flashing a cert bundle is impractical. For stricter deployments,
 *   replace setInsecure() with setCACert(hivemq_root_ca) using the
 *   ISRG Root X1 / DST Root CA X3 certificate.
 **/

#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// ==========================================
// 1. CONFIGURATION — fill these in before flashing
// ==========================================

// Node Identity — must match node_identifier registered in the dashboard
const char *NODE_ID = "WIFI_NODE_002";

// Wi-Fi Settings
const char *ssid     = "Rafy";
const char *password = "edwinocaya2";

// ── HiveMQ Cloud Broker Settings ────────────────────────────────────────────
// Cluster address from HiveMQ dashboard → Overview → Connection Settings
const char *mqtt_server = "5d2b4f49284d429da0268114f3839cc4.s1.eu.hivemq.cloud";
const int   mqtt_port   = 8883;   // TLS/SSL port (mandatory for HiveMQ Cloud)

// HiveMQ Cloud credentials — create in HiveMQ dashboard → Access Management
// These must match the user you created in the HiveMQ Cloud console.
const char *mqtt_user = "your_hivemq_username";   // REPLACE with your HiveMQ username
const char *mqtt_pass = "your_hivemq_password";   // REPLACE with your HiveMQ password

// Topic is built dynamically in setup() as: nodes/<NODE_ID>/telemetry
char mqtt_topic[64];

// Node Authentication — API key returned by POST /api/devices/register/
const char *API_KEY =
    "402fcaacdfa8799b7cf5d8886683c64337aa31ffaabd504777f57a87a1dd74e1";

// Reading interval (milliseconds)
#define READ_INTERVAL_MS 5000  // 5 seconds → real-time dashboard

// Pin Definitions
#define DHT_PIN      15
#define MOISTURE_PIN 34
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

// DHT22 Settings
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

// ── TLS-enabled MQTT client ────────────────────────────────────────────────
// WiFiClientSecure handles the SSL/TLS handshake with HiveMQ Cloud.
WiFiClientSecure espClient;
PubSubClient     client(espClient);

// Tracks last publish time (non-blocking interval via millis())
unsigned long lastPublishMs = 0;

// ==========================================
// 2. HELPER FUNCTIONS
// ==========================================

void statusBlink(int count, int speedMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(speedMs);
    digitalWrite(LED_BUILTIN, LOW);
    delay(speedMs);
  }
}

// ─── Wi-Fi Connection ─────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.print(F("[WIFI] Connecting to "));
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(F("."));
  }
  Serial.println();
  Serial.print(F("[WIFI] Connected. IP: "));
  Serial.println(WiFi.localIP());
  statusBlink(2, 200);
}

// ─── MQTT Reconnect ───────────────────────────────────────────────────────────
// Called from loop() whenever the broker connection drops.
// Authenticates with HiveMQ Cloud credentials.
void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print(F("[MQTT] Connecting to HiveMQ Cloud..."));

    // Authenticate with HiveMQ Cloud username + password
    bool connected = client.connect(NODE_ID, mqtt_user, mqtt_pass);

    if (connected) {
      Serial.println(F(" Connected!"));
      statusBlink(2, 300);

      // Subscribe to command topic for dryer control
      char cmd_topic[64];
      snprintf(cmd_topic, sizeof(cmd_topic), "nodes/%s/commands", NODE_ID);
      client.subscribe(cmd_topic, 1);
      Serial.print(F("[MQTT] Subscribed to: "));
      Serial.println(cmd_topic);
    } else {
      Serial.print(F(" failed. rc="));
      Serial.print(client.state());
      // Common error codes:
      //  -2 = CONNECT_FAILED (wrong host/port or TLS handshake failure)
      //  -4 = CONNECTION_TIMEOUT
      //   4 = BAD_CREDENTIALS (wrong username/password)
      //   5 = UNAUTHORIZED
      Serial.println(F(" — retrying in 5s"));
      delay(5000);
    }
  }
}

// ─── Command Callback ─────────────────────────────────────────────────────────
// Called when a message arrives on nodes/<NODE_ID>/commands.
// Backend publishes "ON" or "OFF" to control the grain dryer.
void commandCallback(char *topic, byte *payload, unsigned int length) {
  String cmd = "";
  for (unsigned int i = 0; i < length; i++) {
    cmd += (char)payload[i];
  }
  cmd.trim();

  Serial.print(F("[CMD] Received dryer command: "));
  Serial.println(cmd);

  if (cmd == "ON") {
    Serial.println(F("[CMD] Dryer relay → ON"));
    statusBlink(3, 100);
  } else if (cmd == "OFF") {
    Serial.println(F("[CMD] Dryer relay → OFF"));
    statusBlink(1, 500);
  }
}

// ==========================================
// 3. SETUP — runs once on power-on / reset
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(LED_BUILTIN, OUTPUT);
  dht.begin();

  snprintf(mqtt_topic, sizeof(mqtt_topic), "nodes/%s/telemetry", NODE_ID);

  Serial.println(F("\n[SYSTEM] Smart-Stua Node starting (HiveMQ Cloud / TLS mode)"));
  Serial.print(F("[SYSTEM] Publishing to topic: "));
  Serial.println(mqtt_topic);
  Serial.print(F("[SYSTEM] Broker: "));
  Serial.print(mqtt_server);
  Serial.print(F(":"));
  Serial.println(mqtt_port);

  connectWiFi();

  // ── TLS Configuration ───────────────────────────────────────────────────
  // setInsecure() skips server certificate verification.
  // This is acceptable for sensor nodes. For full cert pinning, replace with:
  //   espClient.setCACert(hivemq_root_ca_pem);
  espClient.setInsecure();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(commandCallback);
  // HiveMQ Cloud may send large ACK packets — increase buffer if payloads > 256 bytes
  client.setBufferSize(512);

  Serial.println(F("[SYSTEM] Real-time streaming mode active (TLS)."));
}

// ==========================================
// 4. MAIN LOOP — reads and publishes every READ_INTERVAL_MS
// ==========================================
void loop() {
  // Maintain MQTT connection
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  // Non-blocking publish interval
  unsigned long now = millis();
  if (now - lastPublishMs >= READ_INTERVAL_MS) {
    lastPublishMs = now;

    // Read sensors
    float temp     = dht.readTemperature();
    float hum      = dht.readHumidity();
    int   rawMoist = analogRead(MOISTURE_PIN);

    const int DRY_ADC = 3500;
    const int WET_ADC = 1200;
    float moistPct = map(rawMoist, DRY_ADC, WET_ADC, 0, 100);
    moistPct = constrain(moistPct, 0.0f, 100.0f);

    Serial.printf("[SENSOR] T=%.1f°C  H=%.1f%%  Moist=%.1f%%\n", temp, hum, moistPct);

    if (isnan(temp) || isnan(hum)) {
      Serial.println(F("[SENSOR] DHT read error — skipping publish"));
      statusBlink(3, 100);
      return;
    }

    // Build JSON payload (field names match SensorPayloadSerializer)
#if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
#else
    StaticJsonDocument<256> doc;
#endif
    doc["node_id"]     = NODE_ID;
    doc["temperature"] = temp;
    doc["humidity"]    = hum;
    doc["moisture_pct"] = moistPct;
    doc["api_key"]     = API_KEY;

    char buffer[256];
    serializeJson(doc, buffer);

    if (client.publish(mqtt_topic, buffer, false)) {
      Serial.println(F("[MQTT] Published successfully"));
      statusBlink(1, 150);
    } else {
      Serial.println(F("[MQTT] Publish failed — check TLS/credentials"));
      statusBlink(5, 100);
    }
  }
}
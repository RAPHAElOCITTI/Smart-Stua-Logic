/**
 * Project: SMART-STUA / SmartSilo Grain Monitoring Node
 * Hardware: ESP32, DHT22, Analog Moisture Sensor
 * Protocol: MQTT over Wi-Fi (Continuous Real-Time Loop)
 *
 * Refactored from deep-sleep duty-cycle to a persistent MQTT connection
 * that publishes telemetry every READ_INTERVAL_MS for a live dashboard.
 **/

#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <PubSubClient.h>
#include <WiFi.h>

// ==========================================
// 1. CONFIGURATION — fill these in before flashing
// ==========================================

// Node Identity — must match node_identifier registered in the dashboard
const char *NODE_ID = "WIFI_NODE_001";

// Wi-Fi Settings
const char *ssid     = "YOUR_SSID";
const char *password = "YOUR_PASSWORD";

// MQTT Broker Settings
// Set mqtt_server to the LAN IP of the machine running docker compose.
// Find it with: ip addr (Linux/Mac) or ipconfig (Windows)
const char *mqtt_server = "192.168.X.X";
const int   mqtt_port   = 1883;
// Topic is built dynamically in setup() as: nodes/<NODE_ID>/telemetry
char mqtt_topic[64];

// Node Authentication
// Paste the api_key returned by POST /api/devices/register/ here.
const char *API_KEY = "YOUR_64_CHAR_HEX_KEY_FROM_DASHBOARD";

// Reading interval — how often to sample sensors and publish (milliseconds)
#define READ_INTERVAL_MS 5000   // 5 seconds → real-time dashboard

// Pin Definitions
#define DHT_PIN      15
#define MOISTURE_PIN 34
#define LED_BUILTIN  2

// DHT22 Settings
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

WiFiClient   espClient;
PubSubClient client(espClient);

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

// ─── Wi-Fi Connection ────────────────────────────────────────────────────────
// Blocks until Wi-Fi is established. In continuous-loop mode this is only
// called once at startup; reconnection is handled by the OS TCP stack.
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
// Retries indefinitely with a 2-second backoff.
void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print(F("[MQTT] Connecting to broker..."));

    // For anonymous broker (allow_anonymous true in mosquitto.conf):
    bool connected = client.connect(NODE_ID);

    // ── Uncomment below when MQTT auth is enabled (production) ────────────────
    // const char *mqtt_user = "smartstua_node";
    // const char *mqtt_pass = "your_mqtt_password";
    // bool connected = client.connect(NODE_ID, mqtt_user, mqtt_pass);

    if (connected) {
      Serial.println(F(" Connected!"));
      statusBlink(2, 300);

      // ── Subscribe to command topic for dryer control ───────────────────────
      char cmd_topic[64];
      snprintf(cmd_topic, sizeof(cmd_topic), "nodes/%s/commands", NODE_ID);
      client.subscribe(cmd_topic, 1);
      Serial.print(F("[MQTT] Subscribed to: "));
      Serial.println(cmd_topic);
    } else {
      Serial.print(F(" failed. rc="));
      Serial.print(client.state());
      Serial.println(F(" — retrying in 2s"));
      delay(2000);
    }
  }
}

// ─── Command Callback ─────────────────────────────────────────────────────────
// Called when a message arrives on nodes/<NODE_ID>/commands.
// The backend publishes "ON" or "OFF" to control the grain dryer.
void commandCallback(char *topic, byte *payload, unsigned int length) {
  String cmd = "";
  for (unsigned int i = 0; i < length; i++) {
    cmd += (char)payload[i];
  }
  cmd.trim();

  Serial.print(F("[CMD] Received dryer command: "));
  Serial.println(cmd);

  if (cmd == "ON") {
    // TODO: activate dryer relay on GPIO pin
    Serial.println(F("[CMD] Dryer relay → ON"));
    statusBlink(3, 100);
  } else if (cmd == "OFF") {
    // TODO: deactivate dryer relay
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

  // Build the MQTT topic string dynamically from NODE_ID
  snprintf(mqtt_topic, sizeof(mqtt_topic), "nodes/%s/telemetry", NODE_ID);

  Serial.println(F("\n[SYSTEM] Smart-Stua Node starting (real-time mode)"));
  Serial.print(F("[SYSTEM] Publishing to topic: "));
  Serial.println(mqtt_topic);

  connectWiFi();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(commandCallback);

  Serial.println(F("[SYSTEM] Real-time streaming mode active."));
}

// ==========================================
// 4. MAIN LOOP — reads and publishes every READ_INTERVAL_MS
// ==========================================
void loop() {
  // ── Maintain MQTT connection ────────────────────────────────────────────────
  if (!client.connected()) {
    reconnectMQTT();
  }
  // Must be called regularly to process incoming messages (commands)
  client.loop();

  // ── Non-blocking publish interval ──────────────────────────────────────────
  unsigned long now = millis();
  if (now - lastPublishMs >= READ_INTERVAL_MS) {
    lastPublishMs = now;

    // Read sensors
    float temp     = dht.readTemperature();
    float hum      = dht.readHumidity();
    int   rawMoist = analogRead(MOISTURE_PIN);
    float moistPct = (rawMoist / 4095.0f) * 100.0f;

    Serial.printf("[SENSOR] T=%.1f°C  H=%.1f%%  Moist=%.1f%%\n",
                  temp, hum, moistPct);

    // Skip publish on DHT22 read error
    if (isnan(temp) || isnan(hum)) {
      Serial.println(F("[SENSOR] DHT22 read error — skipping publish"));
      statusBlink(3, 100);
      return;
    }

    // Build JSON payload (field names match SensorPayloadSerializer)
    StaticJsonDocument<256> doc;
    doc["node_id"]      = NODE_ID;
    doc["temperature"]  = temp;
    doc["humidity"]     = hum;
    doc["moisture_pct"] = moistPct;
    doc["api_key"]      = API_KEY;

    char buffer[256];
    serializeJson(doc, buffer);

    // Publish with QOS-0 (fire-and-forget; QOS-1 needs persistent session)
    if (client.publish(mqtt_topic, buffer, /*retained=*/false)) {
      Serial.println(F("[MQTT] Published successfully"));
      statusBlink(1, 150);
    } else {
      Serial.println(F("[MQTT] Publish failed"));
      statusBlink(5, 100);
    }
  }
}
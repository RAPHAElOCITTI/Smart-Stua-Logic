/**
 * Project: SMART-STUA / SmartSilo Grain Monitoring Node (MQTT Version)
 * Hardware: ESP32, DHT22, Analog Moisture Sensor
 * Protocol: MQTT over Wi-Fi
 **/

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <Adafruit_Sensor.h>

// ==========================================
// 1. CONFIGURATION SECTION
// ==========================================

// Node Identity
const char* NODE_ID = "WIFI_NODE_001";

// Wi-Fi Settings
const char* ssid     = "SSID;
const char* password = "PASSWORD";

// MQTT Broker Settings
const char* mqtt_server = "IPv4_ADDRESS"; // Put your AWS Public IPv4 Address here
const int   mqtt_port   = 1883;
const char* mqtt_topic  = "gulu_university/grain/readings"; 

// Pin Definitions
#define DHT_PIN          15
#define MOISTURE_PIN     34
#define LED_BUILTIN      2
#define BATTERY_ADC_PIN  35

// DHT22 Settings
#define DHT_TYPE         DHT22
DHT dht(DHT_PIN, DHT_TYPE);

// Deep Sleep Settings
#define uS_TO_S_FACTOR 1000000ULL
#define SLEEP_DURATION 900 // 15 minutes
#define WIFI_MAX_ATTEMPTS 20
#define WIFI_DELAY_MS 500
#define MQTT_MAX_ATTEMPTS 5
#define MQTT_RETRY_DELAY_MS 2000

WiFiClient espClient;
PubSubClient client(espClient);

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

void goToSleep() {
  Serial.println(F("[SYSTEM] Entering deep sleep..."));
  Serial.flush();
  delay(100);
  client.disconnect();
  WiFi.disconnect(true);
  esp_sleep_enable_timer_wakeup(SLEEP_DURATION * uS_TO_S_FACTOR);
  esp_deep_sleep_start();
}

bool connectWiFi() {
  Serial.print(F("[WIFI] Connecting to "));
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < WIFI_MAX_ATTEMPTS) {
    delay(WIFI_DELAY_MS);
    Serial.print(F("."));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print(F("[WIFI] Connected, IP: "));
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println();
  Serial.println(F("[WIFI] Connection failed"));
  return false;
}

bool connectMQTT() {
  int attempts = 0;
  while (!client.connected() && attempts < MQTT_MAX_ATTEMPTS) {
    Serial.print(F("[MQTT] Attempting connection..."));
    if (client.connect(NODE_ID)) {
      Serial.println(F(" Connected!"));
      return true;
    }

    Serial.print(F(" failed, rc="));
    Serial.print(client.state());
    Serial.println(F(", retrying in 2 seconds"));
    delay(MQTT_RETRY_DELAY_MS);
    attempts++;
  }

  Serial.println(F("[MQTT] Unable to connect to broker"));
  return false;
}

// ==========================================
// 3. MAIN LOGIC (SETUP)
// ==========================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(LED_BUILTIN, OUTPUT);
  dht.begin();

  Serial.println(F("[SYSTEM] Setup started"));

  // 1. Read Sensors
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  int rawMoist = analogRead(MOISTURE_PIN);
  float moistPct = (rawMoist / 4095.0) * 100.0;

  Serial.print(F("[SENSOR] Temperature: "));
  Serial.print(temp);
  Serial.print(F(" C, Humidity: "));
  Serial.print(hum);
  Serial.print(F(" %, Moisture ADC: "));
  Serial.println(rawMoist);

  // 2. Connect Wi-Fi
  if (!connectWiFi()) {
    statusBlink(3, 200);
    goToSleep();
  }

  // 3. Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  if (!connectMQTT()) {
    statusBlink(5, 100);
    goToSleep();
  }

  // 4. Send Data
  StaticJsonDocument<256> doc;
  doc["node_id"] = NODE_ID;
  doc["temp"] = isnan(temp) ? -99 : temp;
  doc["hum"] = isnan(hum) ? -99 : hum;
  doc["moist"] = moistPct;

  char buffer[256];
  serializeJson(doc, buffer);

  if (client.publish(mqtt_topic, buffer)) {
    Serial.println(F("[MQTT] Data published successfully"));
    statusBlink(2, 300);
  } else {
    Serial.println(F("[MQTT] Publish failed"));
    statusBlink(5, 100);
  }

  client.loop();
  delay(500);

  // 5. Sleep
  goToSleep();
}

void loop() {
  // Never reached
}
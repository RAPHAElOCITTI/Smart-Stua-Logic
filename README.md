# Smart-Stua — IoT Aflatoxin Prevention System

> Grain storage environmental monitoring for aflatoxin prevention in Gulu District, Uganda

---

## System Overview

| Layer | Technology |
|-------|-----------|
| **Sensor Node** | ESP32 + DHT22 + SIM800L (WiFi primary, GSM fallback) |
| **Backend API** | Django 4.2 + SQLite + Celery/Redis + Twilio SMS |
| **Mobile App** | React Native (Expo) — runs on Android & iOS via Expo Go |

---

## Quick Start

### 1. Backend (Django)

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env — set SECRET_KEY, TWILIO credentials, SENSOR_API_KEY

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start development server
python manage.py runserver 0.0.0.0:8000
```

Access the admin panel at **http://localhost:8000/admin/**

> Register your sensor nodes via the admin panel before flashing firmware.

---

### 2. Mobile App (Expo)

```bash
cd mobile
npm install
npx expo start
```

1. Install **Expo Go** on your Android/iOS phone
2. Scan the QR code shown in the terminal
3. Go to **Settings tab** → set the server URL to your machine's local IP
   - e.g., `http://192.168.1.100:8000` (both phone and PC must be on same WiFi)

---

### 3. Hardware (ESP32 Firmware)

**Connectivity:** ESP32 tries **WiFi first** (faster, free). Falls back to **SIM800L GSM** automatically if WiFi is unavailable.

Edit `hardware/sensor_node/sensor_node.ino`:
```cpp
#define NODE_ID      "NODE_001"         // Must match admin panel registration
#define API_KEY      "your-api-key"     // From .env SENSOR_API_KEY
#define WIFI_SSID_1  "YourWiFiName"
#define WIFI_PASS_1  "YourWiFiPassword"
#define SERVER_HOST  "your-server.com"
#define GSM_APN      "internet"         // Your SIM card APN
```

Flash via Arduino IDE with `ESP32 Dev Module` board selected.

---

## Aflatoxin Risk Index (ARI)

| Range | Risk | Action |
|-------|------|--------|
| 0–30 | 🟢 Low | Normal — log reading |
| 31–70 | 🟡 Medium | Warning — advisory SMS sent |
| 71–100 | 🔴 High | Critical — dryer ON + urgent SMS |

---

## Running Tests

```bash
cd backend
python manage.py test monitoring
```

---

## Project Structure

```
Smart-stua/
├── hardware/sensor_node/sensor_node.ino   # ESP32 firmware (WiFi + GSM)
├── backend/
│   ├── requirements.txt
│   ├── manage.py
│   ├── smartstua/                         # Django project config
│   └── monitoring/                        # Core app
│       ├── models.py                      # DB models
│       ├── ari_algorithm.py               # ARI engine
│       ├── tasks.py                       # Celery tasks
│       ├── views.py                       # REST API
│       └── tests.py                       # Unit tests
├── mobile/
│   ├── app.json                           # Expo config
│   ├── App.js                             # Root navigator
│   └── src/
│       ├── api.js
│       ├── screens/Dashboard.js
│       ├── screens/DeviceList.js
│       ├── screens/AlertHistory.js
│       ├── screens/Settings.js
│       └── components/
└── docs/                                  # Architecture diagrams
```

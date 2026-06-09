Smart-Stua: IoT-Based Aflatoxin Prevention System — Implementation Plan (v2)
Background
Smart-Stua is an integrated IoT system for aflatoxin contamination monitoring and prevention in grain storage, targeting small-to-medium scale facilities in Uganda's Gulu District. The system uses DHT22 sensors on ESP32 microcontrollers with GSM/GPRS (SIM800L) communication, a Django cloud backend with a custom Aflatoxin Risk Index (ARI) algorithm, and a React Native mobile dashboard.
[!IMPORTANT] Key architecture change from v1: Your diagrams reveal the system uses GSM/GPRS (SIM800L module) for sensor-to-cloud communication — NOT LoRaWAN. The ESP32 nodes transmit JSON payloads directly to the Django REST API over cellular data. This is a critical design decision that simplifies the architecture (no TTN gateway needed) and is practical for Gulu District where cellular coverage exists.
--------------------------------------------------------------------------------
Reference Architecture (From Your Diagrams)
High-Level Architecture
![High-Level Architecture Diagram](C:\Users\William Opio.gemini\antigravity\brain\9a84939d-171c-48ca-b742-dbc2739f875c\high-level_architecture_diagram.png)
Logical Data Flow
![Logical Architecture Diagram](C:\Users\William Opio.gemini\antigravity\brain\9a84939d-171c-48ca-b742-dbc2739f875c\logical_architecture_diagram.png)
Physical Deployment
![Physical Architecture Diagram](C:\Users\William Opio.gemini\antigravity\brain\9a84939d-171c-48ca-b742-dbc2739f875c\physical_architecture_diagram.png)
--------------------------------------------------------------------------------
Entity Relationship Model (From ER Diagram)
erDiagram
    Users {
        int user_id PK
        varchar full_name
        varchar phone_number
        varchar email
        enum role
        varchar password_hash
    }
    SensorNodes {
        int node_id PK
        varchar location_label
        varchar gateway_id
        enum status
        datetime last_reading_at
    }
    Readings {
        bigint reading_id PK
        int node_id FK
        float temperature_c
        float humidity_pct
        datetime recorded_at
    }
    AlertLogs {
        int alert_id PK
        int node_id FK
        bigint reading_id FK
        float ari_value
        varchar risk_level
        text message
        varchar sent_to
        datetime sent_at
        boolean action_taken
    }
    Thresholds {
        int threshold_id PK
        int node_id FK
        float min_temp
        float max_temp
        float min_humidity
        float max_humidity
        int risk_duration
    }
    SensorNodes ||--o{ Readings : "records"
    Readings ||--o| AlertLogs : "may trigger"
    SensorNodes ||--o{ AlertLogs : "belongs to"
    SensorNodes ||--|| Thresholds : "configured by"
Use Case Model (From Use Case Diagram)
Actor
Use Cases
Farmer
View Dashboard / ARI, Receive SMS/Email Alert
Store Manager
View Dashboard / ARI, Receive SMS/Email Alert, View Historical Reports, Configure Alert Thresholds
System Admin
Configure Alert Thresholds, Manage User Accounts
Data Flow (From DFD)
Process
Input
Output
Data Store
1.0 Capture Sensor Data
raw_temp_humid_data from Sensor Nodes
store_reading → D1, validated_reading → P2
D1 Readings DB
2.0 Process ARI
validated_reading from P1
ari_result → D2, risk_decision → P3
D2 Risk Log
3.0 Generate Alerts
risk_decision from P2
alert_message → SMS/Email Gateway, alert_log_entry → D1
D1 Readings DB
Dashboard Query
query_readings from Mobile Dashboard
live_historical_data + risk_trends → Dashboard
D1, D2
--------------------------------------------------------------------------------
Proposed Changes
1. Hardware — ESP32 + DHT22 + SIM800L Sensor Node
[NEW] [sensor_node.ino](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/hardware/sensor_node/sensor_node.ino)
Complete ESP32 firmware for the GSM-based sensor node:
Sensor Layer: DHT22 temperature & humidity reads every 15 minutes
Communication Layer: SIM800L GSM/GPRS module sends JSON payloads via HTTP POST to Django API (/api/readings/)
Control Layer: Digital output (GPIO relay) for grain dryer activation; controlled via API polling for pending commands
Power Management: Deep sleep between readings for solar/battery optimization
Payload Format: {"node_id": "NODE_001", "temperature": 28.5, "humidity": 72.3, "api_key": "xxx"}
Dryer Control Polling: After sending data, checks /api/devices/<node_id>/command/ for dryer ON/OFF instructions
Error Handling: Retry logic for GSM connection failures, sensor read validation
[!NOTE] Per your physical architecture diagram, each node consists of: ESP32 + DHT22 + SIM800L module + Battery/Solar power, deployed inside grain storage facilities in Gulu District.
--------------------------------------------------------------------------------
2. Backend — Django REST API + PostgreSQL
[NEW] [requirements.txt](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/requirements.txt)
Django>=4.2,<5.0
djangorestframework>=3.14
django-cors-headers>=4.3
psycopg2-binary>=2.9
celery>=5.3
redis>=5.0
twilio>=8.0
gunicorn>=21.2
python-dotenv>=1.0
dj-database-url>=2.1
--------------------------------------------------------------------------------
[NEW] [manage.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/manage.py)
Standard Django management script.
--------------------------------------------------------------------------------
[NEW] [smartstua/__init__.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/smartstua/init.py)
Celery app auto-discovery.
--------------------------------------------------------------------------------
[NEW] [smartstua/settings.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/smartstua/settings.py)
PostgreSQL database via dj-database-url
Celery broker (Redis)
CORS for React Native
REST framework config with pagination
Twilio credentials from environment variables
INSTALLED_APPS: rest_framework, corsheaders, monitoring
--------------------------------------------------------------------------------
[NEW] [smartstua/urls.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/smartstua/urls.py)
Root URL config routing to the monitoring app under /api/.
--------------------------------------------------------------------------------
[NEW] [smartstua/celery.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/smartstua/celery.py)
Celery app with Redis broker, auto-discovers tasks from monitoring.tasks.
--------------------------------------------------------------------------------
[NEW] [monitoring/models.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/models.py)
Matches your ER diagram exactly:
Model
DB Table
Fields
Purpose
User
users
user_id (PK), full_name, phone_number, email, role (enum: farmer/store_manager/admin), password_hash
System users with role-based access
SensorNode
sensor_nodes
node_id (PK), location_label, gateway_id, status (enum: active/inactive/maintenance), last_reading_at
Registered ESP32+SIM800L sensor devices
Reading
readings
reading_id (PK bigint), node_id (FK→SensorNode), temperature_c, humidity_pct, recorded_at
Raw sensor data from GSM transmissions
AlertLog
alert_logs
alert_id (PK), node_id (FK→SensorNode), reading_id (FK→Reading), ari_value, risk_level, message, sent_to, sent_at, action_taken
Alert history with ARI scores
Threshold
thresholds
threshold_id (PK), node_id (FK→SensorNode), min_temp, max_temp, min_humidity, max_humidity, risk_duration
Per-node configurable alert thresholds
--------------------------------------------------------------------------------
[NEW] [monitoring/serializers.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/serializers.py)
DRF serializers for all 5 models + a SensorPayloadSerializer for validating incoming GSM node JSON.
--------------------------------------------------------------------------------
[NEW] [monitoring/views.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/views.py)
Maps directly to your Data Flow Diagram processes:
Endpoint
Method
DFD Process
Purpose
/api/readings/
POST
1.0 Capture Sensor Data
Receive JSON from GSM node, validate, store in Readings table, trigger ARI calculation
/api/devices/
GET
—
List registered sensor nodes with status
/api/devices/<id>/readings/
GET
Dashboard query
Historical readings for a device (paginated)
/api/devices/<id>/latest/
GET
Dashboard query
Latest reading + current ARI score
/api/devices/<id>/command/
GET
Control flow
Return pending dryer command for ESP32 polling
/api/dashboard/summary/
GET
Dashboard query
Aggregate data: all nodes' latest readings, ARI scores, active alerts
/api/alerts/
GET
Dashboard query
Alert history with risk levels
/api/thresholds/<node_id>/
GET/PUT
Configure Thresholds (UC3)
View/update per-node threshold configuration
/api/auth/login/
POST
Manage Users (UC4)
User authentication
/api/auth/register/
POST
Manage Users (UC4)
User registration (admin only)
--------------------------------------------------------------------------------
[NEW] [monitoring/ari_algorithm.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/ari_algorithm.py)
Standalone calculate_ari(temperature, humidity, duration_hours) function.
Maps to DFD Process 2.0 (Process ARI) and the ARI Algorithm Engine in the logical flow diagram:
def calculate_ari(temperature: float, humidity: float, duration_hours: float) -> dict:
    """
    Aflatoxin Risk Index based on Aspergillus flavus growth parameters.
    
    Returns: {"ari_score": float, "risk_level": str, "factors": dict}
    """
Scientific basis:
Temperature Factor F(T): A. flavus grows optimally at 25–35°C (peak ≈ 30°C). Gaussian model: F(T) = exp(-0.5 * ((T - 30) / 5)²). Below 10°C or above 45°C → negligible growth.
Humidity Factor F(H): Growth requires RH > 70%, accelerates above 85%. Sigmoid model: F(H) = 1 / (1 + exp(-0.3 * (H - 75))). Below 65% → near-zero risk.
Duration Factor F(D): Logarithmic accumulation capturing that prolonged exposure at risky conditions compounds danger: F(D) = log₂(1 + D/6), where D = hours of continuous high-risk exposure. Capped at a maximum multiplier.
Weighted ARI: ARI = 100 × (0.35 × F(T) + 0.45 × F(H) + 0.20 × F(D))
Risk Levels (maps to ER diagram's risk_level field):
ARI Range
Risk Level
Color
Action
0–30
Low
🟢 Green
Normal — log reading
31–70
Medium
🟡 Amber
Warning — send advisory SMS
71–100
High
🔴 Red
Critical — trigger dryer + send urgent SMS
--------------------------------------------------------------------------------
[NEW] [monitoring/tasks.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/tasks.py)
Maps to DFD Process 3.0 (Generate Alerts) and the Scheduler & Alert Dispatcher in the high-level architecture:
Celery Task
Trigger
Purpose
process_sensor_data(reading_id)
On new reading POST
Calculate ARI → store in AlertLogs if threshold exceeded → dispatch alert
send_sms_alert(alert_id)
From process_sensor_data
Send SMS via Twilio API to farmer/store manager phone numbers
send_dryer_command(node_id, action)
From process_sensor_data
Set pending dryer command for ESP32 polling
calculate_cumulative_duration(node_id)
Periodic (every 15 min)
Calculate continuous hours of high-risk exposure for duration factor
--------------------------------------------------------------------------------
[NEW] [monitoring/admin.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/admin.py)
Django admin registration for all 5 models.
--------------------------------------------------------------------------------
[NEW] [monitoring/urls.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/urls.py)
App-level URL routing for all API endpoints.
--------------------------------------------------------------------------------
[NEW] [monitoring/apps.py](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/monitoring/apps.py)
Django app configuration.
--------------------------------------------------------------------------------
3. Frontend — React Native Mobile Dashboard
[NEW] [package.json](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/package.json)
Dependencies:
react-native (0.73+)
@react-navigation/native + @react-navigation/bottom-tabs
axios
react-native-chart-kit
react-native-svg
react-native-vector-icons
@react-native-async-storage/async-storage
--------------------------------------------------------------------------------
[NEW] [App.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/App.js)
Root app with React Navigation bottom tab navigator:
🏠 Dashboard tab
📊 History tab
🔔 Alerts tab
⚙️ Settings tab
--------------------------------------------------------------------------------
[NEW] [src/api.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/api.js)
Axios-based API client with methods for all backend endpoints:
fetchDashboardSummary()
fetchDeviceReadings(nodeId, params)
fetchLatestReading(nodeId)
fetchAlerts(params)
updateThresholds(nodeId, data)
login(credentials) / register(userData)
Auto-refresh polling (30-second interval)
--------------------------------------------------------------------------------
[NEW] [src/screens/Dashboard.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/screens/Dashboard.js)
Main screen — maps to Use Case "View Dashboard / ARI":
Circular Gauges: Real-time temperature (°C) and humidity (%) for selected node
ARI Risk Indicator: Large color-coded badge (Green/Amber/Red) with numeric ARI score
Dryer Status: Active/Inactive indicator with manual override button
7-Day Trend Chart: Historical line chart showing temp, humidity, and ARI over time
Node Selector: Dropdown to switch between registered sensor nodes
Pull-to-Refresh: Manual data refresh
Auto-Refresh: Polls /api/dashboard/summary/ every 30 seconds
--------------------------------------------------------------------------------
[NEW] [src/screens/DeviceList.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/screens/DeviceList.js)
List of registered silo devices with:
Node ID, location label, status badge (active/inactive)
Last reading timestamp
Current ARI risk level color indicator
Tap to navigate to device-specific Dashboard view
--------------------------------------------------------------------------------
[NEW] [src/screens/AlertHistory.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/screens/AlertHistory.js)
Maps to Use Case "Receive SMS/Email Alert" + "View Historical Reports":
Paginated list of alerts with risk-level color badges
Each alert shows: timestamp, node location, ARI value, risk level, message, action taken status
Filter by risk level (Low/Medium/High) and date range
--------------------------------------------------------------------------------
[NEW] [src/screens/Settings.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/screens/Settings.js)
Maps to Use Case "Configure Alert Thresholds":
Per-node threshold configuration (min/max temp, min/max humidity, risk duration)
User profile management
Server URL configuration
--------------------------------------------------------------------------------
[NEW] [src/components/GaugeChart.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/components/GaugeChart.js)
Reusable SVG-based circular gauge with animated needle, color gradient arc, and value label.
--------------------------------------------------------------------------------
[NEW] [src/components/RiskIndicator.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/components/RiskIndicator.js)
Color-coded risk level badge component:
Low → Green with checkmark icon
Medium → Amber with warning icon
High → Red with danger icon + pulsing animation
--------------------------------------------------------------------------------
[NEW] [src/components/TrendChart.js](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/mobile/src/components/TrendChart.js)
Historical line chart using react-native-chart-kit showing overlaid temperature, humidity, and ARI trend lines with legend and tooltip.
--------------------------------------------------------------------------------
4. Configuration & Documentation
[NEW] [README.md](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/README.md)
Comprehensive deployment guide:
System architecture overview (referencing your diagrams)
Hardware assembly: ESP32 + DHT22 + SIM800L wiring
Arduino IDE setup and firmware flashing
Backend: Django + PostgreSQL + Redis + Celery deployment
Twilio SMS setup and configuration
React Native mobile app build (Android/iOS)
ARI algorithm documentation
API endpoint reference
[NEW] [.env.example](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/backend/.env.example)
Template environment variables for Django, PostgreSQL, Redis, and Twilio.
[NEW] [.gitignore](file:///c:/Users/William Opio/Desktop/Projects/Smart-Silo/.gitignore)
Standard ignores for Python, Node.js, Arduino, and environment files.
--------------------------------------------------------------------------------
Complete File Tree
Smart-Silo/
├── README.md
├── .gitignore
├── hardware/
│   └── sensor_node/
│       └── sensor_node.ino          # ESP32 + DHT22 + SIM800L firmware
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── manage.py
│   └── smartstua/
│       ├── __init__.py
│       ├── settings.py
│       ├── urls.py
│       ├── celery.py
│       └── wsgi.py
│   └── monitoring/
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py               # Users, SensorNodes, Readings, AlertLogs, Thresholds
│       ├── serializers.py
│       ├── views.py                 # API endpoints
│       ├── urls.py
│       ├── ari_algorithm.py         # ARI calculation engine
│       ├── tasks.py                 # Celery tasks: alerts, dryer commands
│       └── admin.py
├── mobile/
│   ├── package.json
│   ├── App.js
│   └── src/
│       ├── api.js                   # Axios API client
│       ├── screens/
│       │   ├── Dashboard.js         # Main dashboard with gauges + charts
│       │   ├── DeviceList.js        # Sensor node listing
│       │   ├── AlertHistory.js      # Alert log viewer
│       │   └── Settings.js          # Threshold configuration
│       └── components/
│           ├── GaugeChart.js        # Circular gauge component
│           ├── RiskIndicator.js     # Risk level badge
│           └── TrendChart.js        # Historical line chart
└── docs/                           # Your existing diagrams
    ├── data_flow_diagram.svg
    ├── entity_relationship_diagram.svg
    ├── high-level_architecture_diagram.png
    ├── logical_architecture_diagram.png
    ├── physical_architecture_diagram.png
    └── use_case_diagram.svg
--------------------------------------------------------------------------------
Verification Plan
Automated Tests
Django unit tests for calculate_ari() with known input/output boundary cases
API endpoint tests using DRF's test client (POST reading → verify ARI calculation + alert generation)
Model relationship tests (FK constraints match ER diagram)
Arduino code compilation check via arduino-cli compile
Manual Verification
Review generated models against ER diagram entity/field names
Verify data flow matches logical architecture diagram
Confirm API endpoints cover all use cases from use case diagram
Test ARI algorithm produces correct risk levels at boundary values (30, 70)
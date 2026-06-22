---
# Rule Name: 01-Architecture & File Structure

## Context & Scope
This rule applies when modifying or extending the directory structure, adding new modules, integrating services, or introducing new communication pathways across the Smart-Stua codebase. It covers the Django backend, Expo React Native mobile client, and ESP32 Arduino firmware.

## Core Directives
1. **Directory Integrity**: Maintain the separation of concerns between components:
   - `/backend/`: Main Django REST framework application, Celery tasks, and MQTT bridge command.
   - `/expo/`: React Native Expo mobile frontend (using `src/screens`, `src/components`, `src/api.js`).
   - `/hardware/`: ESP32 Arduino firmware code (main sketch `hardware/sensor_node/sensor_node.ino`).
   - `/mosquitto/`: Configs and persistent directories for the MQTT broker.
   - `/simulator/`: Python scripts for simulated load testing and local network node tests.
2. **Service Isolation**: Services (PostgreSQL database, Redis, Mosquitto, Django API, Celery worker) MUST run in independent containers.
   - Database and Redis MUST NOT expose ports to the host system.
   - Django API (port 8000) and Mosquitto Broker (port 1883) are the only externally accessible network ports.
3. **Data Ingestion Boundary**: Telemetry data from hardware/simulator nodes MUST be ingested via:
   - **MQTT Bridge**: Listening on Mosquitto and writing to the Django PostgreSQL database via the Django ORM.
   - **REST API (`POST /api/readings/`)**: Accept payloads from hardware nodes using a verified `api_key` payload parameter.
4. **No Direct Database Queries from Outside Django**: Only the Django backend (including Celery and management commands) is allowed to read/write to the PostgreSQL database directly. Mobile apps and IoT components must access the database solely through REST API endpoints.

## Code Examples

### ❌ Bad Pattern
```python
# In backend/monitoring/management/commands/mqtt_bridge.py
# NEVER bypass the Django ORM to run direct SQL or connect to a separate database client
import psycopg2

def handle_message(msg):
    # BAD: Directly writing to Postgres bypassing Django Models and validation logic
    conn = psycopg2.connect("dbname=smartstua_db user=smartstua")
    cur = conn.cursor()
    cur.execute("INSERT INTO readings (temperature_c, humidity_pct) VALUES (%s, %s)", (25.0, 60.0))
    conn.commit()
```

### ❌ Bad Pattern
```javascript
// In expo/src/screens/Dashboard.js
// NEVER hardcode local API addresses or attempt to connect to Mosquitto MQTT broker directly from the frontend UI
import init from 'react_native_mqtt'; // BAD

const fetchDashboardData = () => {
  // BAD: Hardcoded development IP address instead of using configurable Axios client from api.js
  return fetch('http://192.168.1.100:8000/api/dashboard/summary/');
}
```

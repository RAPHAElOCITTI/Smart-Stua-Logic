---
# Rule Name: 03-Testing & Error Handling

## Context & Scope
This rule applies when writing unit tests for the backend, developing API endpoints, or implementing device error handling and network fallback mechanisms.

## Core Directives

### 1. Backend Testing
- **Framework**: Use Django's standard `TestCase` from `django.test` and `APIClient` from `rest_framework.test` to write backend tests.
- **Location**: Test files must be placed in `<app>/tests.py` or inside a `<app>/tests/` directory.
- **Execution Command**: Run tests via `python manage.py test <app_name>` (e.g., `python manage.py test monitoring`).
- **Edge Cases**: Always assert boundary limits (e.g., ARI algorithm boundary scores 30 and 70, temperature ranges, and negative/out-of-bounds inputs).

### 2. API Error Boundaries
- **Status Codes**: Return appropriate HTTP status codes (200/201 for success, 400 for bad parameters/validation, 401 for unauthorized key/token, 403 for forbidden role, 404 for missing resource).
- **Error Payloads**: Always return errors as structured JSON rather than raw text or HTML. For example: `{"error": "description", "details": ...}`.
- **Exceptions**: Wrap model query lookups with `get_object_or_404` or handle `DoesNotExist` exceptions explicitly to prevent 500 Server Errors.

### 3. ESP32 Firmware Error Resilience
- **DHT22 Failures**: The DHT22 sensor can fail or return `NaN`. Retry reading at least 3 times with a 2000ms delay between attempts. If it fails entirely, log a fatal error and go to deep sleep immediately to preserve battery.
- **Connection Timeouts**: Never block indefinitely trying to connect to a network. Set explicit timeout limits (e.g., 12 seconds for WiFi, 15 seconds for HTTP requests).
- **Network Fallback**: Attempt connectivity in this priority: Primary WiFi → Secondary WiFi (if set) → GSM/GPRS.
- **SPIFFS Telemetry Buffer**: When all connectivity checks fail, buffer reading payloads locally in SPIFFS. On next successful transmission, dump the local buffer to the server in chronological order.

---

## Code Examples

### ❌ Bad Pattern
```python
# In backend/monitoring/views.py
# BAD: Catching general exception and returning raw string with 200 OK status code
@api_view(['POST'])
def process_data(request):
    try:
        node_id = request.data['node_id']
        node = SensorNode.objects.get(node_identifier=node_id)
        # Process...
        return Response("Success") # BAD: No status=201, returning plain text instead of JSON
    except Exception as e:
        return Response(str(e))   # BAD: Exposing raw error details and returning status 200 for a failure
```

### ❌ Bad Pattern
```cpp
// In hardware/sensor_node/sensor_node.ino
// BAD: Indefinite block, no validation on NaN values, and ignoring sensor reading failures
void setup() {
  dht.begin();
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  
  // BAD: Proceeding to send telemetry even if readings are NaN
  String payload = "{\"temperature\":" + String(t) + ",\"humidity\":" + String(h) + "}";
  
  // BAD: Indefinite while loop blocking code execution if WiFi is down
  WiFi.begin("SSID", "PASS");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); 
  }
}
```

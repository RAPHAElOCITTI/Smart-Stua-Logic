---
# Rule Name: 02-Coding Standards & Conventions

## Context & Scope
This rule applies when writing or refactoring source code in the Django backend (`/backend`), Expo React Native app (`/expo`), or ESP32 C++ firmware (`/hardware`).

## Core Directives

### 1. Python (Django Backend)
- **Naming Conventions**: Use `snake_case` for variables, function names, and database fields. Use `PascalCase` for classes (Models, Views, Serializers).
- **Django Views**: Prefer functional views decorated with `@api_view` for simplicity, readability, and consistency with the existing API. Use explicit permission decorators (`@permission_classes`).
- **Django Models**: Always define custom table names (`db_table`) under `class Meta`. Include `help_text` and docstrings for all models and fields. Use explicit primary keys (e.g., `models.AutoField(primary_key=True)`).
- **Serializers**: Explicitly define fields in `class Meta.fields` (never use `'__all__'`). Put custom validations inside `validate_<field>` methods.

### 2. JavaScript / React Native (Expo Frontend)
- **Naming Conventions**: Use `camelCase` for variables, properties, and hooks. Use `PascalCase` for React components.
- **Component Design**: Write functional components with React Hooks (e.g., `useState`, `useEffect`). Avoid class components.
- **Secure Token Storage**: Use `expo-secure-store` to read/write authentication tokens. Never store tokens in standard `AsyncStorage` or plain state.
- **API Calls**: Always run requests through the central Axios instance configured in `src/api.js`. Do not import `axios` directly in screen files.

### 3. C++ (Arduino ESP32 Firmware)
- **Naming Conventions**: Use `camelCase` for variables and function names. Use `UPPER_CASE` with underscores for `#define` macros, pins, and constants.
- **Dynamic Allocations**: Avoid excessive usage of the `String` class to prevent heap fragmentation. Use static `char` buffers or the `F()` macro for static serial print messages where possible.
- **Sleep & Power Management**: Always explicitly shut down the WiFi (`WiFi.mode(WIFI_OFF)`) and SIM800L module (`AT+CSCLK=2`) before entering deep sleep (`esp_deep_sleep_start()`) to maximize battery lifespan.
- **Explicit Pin Allocations**: Define all hardware pins explicitly at the top of the file.

---

## Code Examples

### ❌ Bad Pattern
```python
# In backend/monitoring/models.py
# BAD: Non-explicit database table name, missing docstrings, and missing help_text
class node(models.Model):
    name = models.CharField(max_length=50) # BAD: Should be node_identifier or location_label
    mac = models.CharField(max_length=17)  # BAD: Missing validation or help_text
    # Missing custom db_table in Meta class
```

### ❌ Bad Pattern
```javascript
// In expo/src/screens/LoginScreen.js
// BAD: Storing authentication token insecurely in AsyncStorage and importing axios directly
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';

const saveAuthData = async (token) => {
  // BAD: Insecure storage of JWT/Auth tokens
  await AsyncStorage.setItem('userToken', token);
};
```

### ❌ Bad Pattern
```cpp
// In hardware/sensor_node/sensor_node.ino
// BAD: Blocking delays in loop/setup, allocating infinite String objects, and leaving radios on during sleep
void loop() {
  // BAD: String concatenation in loop creates heap fragmentation
  String data = "Temp: " + String(dht.readTemperature()); 
  Serial.println(data);
  delay(10000); // BAD: Blocks the MCU thread completely
  
  // BAD: Going to sleep without shutting down WiFi or cellular modules
  esp_deep_sleep_start(); 
}
```

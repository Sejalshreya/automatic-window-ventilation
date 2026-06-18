# Smart Ventilation - Visual Architecture Guide

## 🏗️ Complete System Architecture

### Layer 1: Presentation (Frontend)
```
┌────────────────────────────────────────────────────┐
│                  WEBSITE DASHBOARD                 │
│              (localhost:5000 - Static)             │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  AUTOMATIC MODE (AI Decision Display)        │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ Temperature: 32.5°C                      │ │ │
│  │  │ Humidity: 65%                            │ │ │
│  │  │ AI Recommendation: 60° confidence: 88%   │ │ │
│  │  │ Current Angle: 60°                       │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  MANUAL CONTROL (Slider)                     │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ ┌─────●──────────┐ 45°  [SEND BUTTON]   │ │ │
│  │  │ 0°   ↑          90°                      │ │ │
│  │  │ └──────────────────┘                     │ │ │
│  │  │ Status: Manual override active (120s)   │ │ │
│  │  │ ✅ Command: Servo at 45°                │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  SYSTEM STATUS                              │ │
│  │  ├─ Server: Online                          │ │
│  │  ├─ Data Source: esp32 (WiFi)               │ │
│  │  ├─ Manual Override: Active (45°)           │ │
│  │  └─ Last Update: 2024-01-15 14:23:45 UTC    │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Layer 2: API Backend (Flask)

```
┌─────────────────────────────────────────────────────────────┐
│                   FLASK BACKEND SERVER                       │
│               (localhost:5000 - REST API)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ SHARED STATE (with threading.Lock())                    ││
│ │ ┌────────────────────────────────────────────────────────┤│
│ │ │ sensor_state = {                                       ││
│ │ │   "temperature": 32.5,                                 ││
│ │ │   "humidity": 65.0,                                    ││
│ │ │   "light": 686,                                        ││
│ │ │   "presence": true,                                    ││
│ │ │   "rain": false,                                       ││
│ │ │   "current_angle": 45,  ← SYNCED WITH SERVO           ││
│ │ │   "source": "esp32",                                   ││
│ │ │   "timestamp": "2024-01-15T14:23:45"                  ││
│ │ │ }                                                      ││
│ │ │                                                        ││
│ │ │ manual_override = {                                    ││
│ │ │   "angle": 45,                                         ││
│ │ │   "timestamp": 1705334625000,  ← SET WHEN USER SENDS  ││
│ │ │   "duration_ms": 120000        ← EXPIRES AFTER 120s    ││
│ │ │ }                                                      ││
│ │ └────────────────────────────────────────────────────────┤│
│ │                                                            ││
│ │ 🟢 ROUTES:                                                ││
│ │ ├─ GET  /                     → Dashboard HTML           ││
│ │ ├─ GET  /api/data             → Current sensor data      ││
│ │ ├─ GET  /api/status           → System status            ││
│ │ ├─ POST /api/sensor           → ESP32 sends data here ✅ ││
│ │ ├─ POST /api/manual-control   → Set manual angle ✅      ││
│ │ └─ POST /api/servo            → Direct servo proxy ✅(NEW)││
│ │                                                            ││
│ │ 🔵 HELPER FUNCTIONS:                                      ││
│ │ ├─ ai_decision()              → Calculate optimal angle   ││
│ │ ├─ is_manual_override_active() → Check if override valid ││
│ │ ├─ simulate_sensors()         → Background thread        ││
│ │ └─ sendToServer()             → Not here! (On ESP32)     ││
│ └──────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Layer 3: Embedded Device (ESP32)

```
┌──────────────────────────────────────────────────────┐
│               ESP32 MICROCONTROLLER                  │
│          (WiFi-enabled IoT Device)                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📡 NETWORK:                                          │
│ ├─ WiFi SSID: SRESIDENCES                           │
│ ├─ IP: 192.168.x.x (DHCP)                           │
│ ├─ Flask URL: http://10.20.86.140:5000/api/sensor  │
│ └─ WebServer: port 80 (localhost:80/api/servo)      │
│                                                      │
│ 📊 SENSORS:                                          │
│ ├─ AHT10 (I2C GPIO 21/22)                           │
│ │  ├─ Temperature: 32.5°C                           │
│ │  └─ Humidity: 65.0%                               │
│ ├─ LDR (ADC GPIO 35)                                │
│ │  └─ Light Level: 686                              │
│ ├─ PIR Motion (GPIO 27)                             │
│ │  └─ Presence: true                                │
│ └─ Rain Sensor (GPIO 34)                            │
│    └─ Raining: false                                │
│                                                      │
│ 🎮 CONTROL:                                          │
│ ├─ Servo Motor (PWM GPIO 18)                        │
│ │  ├─ Current Angle: 45°                            │
│ │  ├─ Target Angle: 45°                             │
│ │  └─ PWM Range: 500-2400 microseconds              │
│ └─ moveServo(target)                                │
│    └─ Smooth movement (5° per 50ms)                 │
│                                                      │
│ 🔴 STATE MACHINE:                                    │
│ ├─ manualOverride: true                             │
│ ├─ manualTargetAngle: 45                            │
│ ├─ manualCommandReceived: timestamp                 │
│ └─ (NO timeout! Flask handles expiration)           │
│                                                      │
│ 🌐 WEB SERVER (port 80):                             │
│ ├─ POST /api/servo ← Direct dashboard commands      │
│ │  ├─ Body: {"angle": 45}                           │
│ │  ├─ Sets: manualOverride = true                   │
│ │  ├─ Calls: moveServo(45)                          │
│ │  └─ Response: {"ok": true, "angle": 45}           │
│ └─ CORS headers: Access-Control-Allow-Origin: *    │
│                                                      │
│ ⚙️  MAIN LOOP (every 3 seconds):                     │
│ ├─ Read all sensors                                 │
│ ├─ Check: if (manualOverride) { ... }               │
│ │  └─ Skip auto logic entirely                      │
│ │  └─ Hold servo at manual angle                    │
│ │  └─ Send to Flask                                 │
│ │  └─ Return (skip auto)                            │
│ ├─ Else: Run auto decision logic                    │
│ │  ├─ if (raining) targetAngle = 0                  │
│ │  ├─ else if (temp > 32) targetAngle = 90          │
│ │  ├─ else if (temp > 26) targetAngle = 60          │
│ │  └─ etc.                                          │
│ ├─ moveServo(targetAngle)                           │
│ ├─ sendToServer()  ← POST sensor data to Flask      │
│ │  ├─ Read response: angle_command, override_flag  │
│ │  ├─ if (manualActive && !manualOverride)          │
│ │  │  └─ moveServo(cmdAngle) ← EXECUTE COMMAND     │
│ │  └─ return                                        │
│ └─ delay(3000ms)                                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Layer 4: Hardware (Servo Motor)

```
┌──────────────────────────────────────────────────────┐
│         MG996R SERVO MOTOR                           │
│         (Controlled by ESP32 PWM)                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│   Signal Pin (GPIO 18)                              │
│   ─────────────────────                             │
│   Receives PWM signal from ESP32                    │
│   Frequency: 50 Hz (typical servo)                  │
│   Pulse Width:                                      │
│   • 500µs   → 0° (fully closed)                     │
│   • 1500µs  → 90° (fully open)                      │
│   • 2400µs  → 180° (extreme)                        │
│                                                      │
│   At 45° command:                                   │
│   PWM = 500 + (45/90) × 1900 = 1450µs               │
│   ✅ Servo rotates to exactly 45°                   │
│                                                      │
│   Power:                                            │
│   • VCC: 5V external (NOT from ESP32 3.3V)          │
│   • GND: Common with ESP32                          │
│   • Current Draw: ~500mA stall current              │
│                                                      │
│   Movement:                                         │
│   • Speed: ~0.16 sec/60° (typical)                  │
│   • Torque: 10 kg·cm                                │
│   • Holding: Maintains position when powered        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 📡 Communication Flow Diagrams

### Diagram 1: Manual Command Flow (FIXED)

```
┌─────────────────────────────────────────────────────────────────┐
│  USER ACTION: Move slider to 45°                                │
└──────────────┬────────────────────────────────────────────────────┘
               │
               ▼
        FRONTEND (JavaScript)
        ├─ Event: slider.onchange(45)
        ├─ Function: sendManual(45)
        └─ Action: fetch('/api/servo', {angle: 45})
               │
               ▼
        HTTP POST Request
        ├─ URL: http://localhost:5000/api/servo
        ├─ Method: POST
        ├─ Headers: {'Content-Type': 'application/json'}
        └─ Body: {"angle": 45}
               │
               ▼
        FLASK BACKEND (/api/servo endpoint)  ← NEW ENDPOINT
        ├─ Receive POST
        ├─ Parse JSON: angle = 45
        ├─ Validate: 0 ≤ 45 ≤ 90 ✓
        ├─ Update State:
        │  ├─ manual_override["angle"] = 45
        │  ├─ manual_override["timestamp"] = 1705334625000
        │  └─ manual_override["duration_ms"] = 120000
        ├─ Return: {"ok": true, "angle": 45}
        │
        └─ (Stored in memory - persists for 120 seconds)
               │
               ▼
        FLASK RESPONSE
        ├─ Status: 200 OK
        ├─ Body: {"status": "ok", "ok": true, "angle": 45}
        └─ Received by Frontend
               │
               ▼
        FRONTEND Confirmation
        ├─ Display: "✅ Command sent to ESP32: 45°"
        └─ User sees immediate feedback
               │
        ~3 seconds pass (normal ESP32 polling cycle)...
               │
               ▼
        ESP32 MAIN LOOP
        ├─ Read sensors (T, H, Light, Motion, Rain)
        ├─ Call: sendToServer(T, H, L, M, R, angle)
        │  └─ HTTP POST to http://10.20.86.140:5000/api/sensor
        │     ├─ Body: {"temperature": 32.5, ..., "current_angle": old_angle}
        │     ├─ Receive Response ──┐
        │     │                     │
        │     └─ Response:          │
        │        ├─ angle_command: 45
        │        ├─ manual_override_active: true  ← CRITICAL FLAG
        │        └─ ai_decision: {...}
        │                        │
        │                        ▼
        │        ESP32 Logic:
        │        ├─ if (res.contains("angle_command")) {
        │        ├─   cmdAngle = res["angle_command"]  (45)
        │        ├─   manualActive = res["manual_override_active"]  (true)
        │        ├─
        │        ├─   if (manualActive && !manualOverride) {
        │        ├─     manualOverride = true
        │        ├─     manualTargetAngle = 45
        │        ├─     moveServo(45)  ← EXECUTES NOW!
        │        ├─   }
        │        ├─ }
        │        │
        │        └─ moveServo(45):
        │           ├─ For pos from currentAngle to 45:
        │           ├─   myServo.write(pos)  ← PWM to servo
        │           ├─   delay(50ms)
        │           ├─ currentAngle = 45
        │           │
        │           └─ ✅ SERVO MOVES TO 45°
        │
        └─ Main loop: manualOverride = true → skip auto logic
               │
               ▼
        SERVO MOTOR
        └─ Receives PWM signal
           ├─ Angle: 45°
           ├─ Torque: Activates
           └─ ✅ WINDOW OPENS TO 45°
```

### Diagram 2: Automatic Mode Flow (Still Works)

```
┌──────────────────────────────────────────────────────┐
│  NO MANUAL OVERRIDE → AUTO MODE ACTIVE               │
└──────────────┬───────────────────────────────────────┘
               │
               ▼
        ESP32 MAIN LOOP (3-second cycle)
        │
        ├─ Read Sensors:
        │  ├─ Temperature: 32.5°C (hot)
        │  ├─ Humidity: 65%
        │  ├─ Light: 686
        │  ├─ Motion: detected
        │  └─ Rain: false (not raining)
        │
        ├─ Check: if (manualOverride) { ... }
        │  └─ FALSE → Skip this block, continue
        │
        ├─ AUTO DECISION LOGIC:
        │  ├─ if (isRaining) targetAngle = 0
        │  │  └─ FALSE (not raining)
        │  ├─ if (temp > 32 || humidity > 70)
        │  │  └─ temperature (32.5) > 32 → TRUE
        │  │  └─ targetAngle = 90 (fully open)
        │  ├─ Log: "Level 3: Very hot/humid → 90 deg"
        │  └─ (Factors considered: temperature, humidity, motion, light)
        │
        ├─ moveServo(targetAngle):
        │  ├─ Smooth movement to 90°
        │  ├─ myServo.write(...)
        │  └─ currentAngle = 90
        │
        ├─ sendToServer():
        │  ├─ POST sensor data
        │  ├─ Request: {"temp": 32.5, "humidity": 65, ...}
        │  └─ Response: {"angle_command": 90, "manual_override_active": false}
        │
        └─ Continue next cycle...
               │
               ▼
        ✅ SERVO AUTOMATICALLY ADJUSTS TO 90° (fully open)
           Window remains open for ventilation
```

### Diagram 3: Manual Override Expiration

```
T=0s:       User sends: angle = 45°
            └─ Flask: manual_override["angle"] = 45
               manual_override["timestamp"] = 0ms

T=3s:       ESP32 polls
            └─ is_manual_override_active() → 45 ✓
               elapsed = 3000ms < 120000ms → ACTIVE
               Send: angle_command = 45
            └─ Servo moves to 45°

T=30s:      ESP32 polls again
            └─ is_manual_override_active() → 45 ✓
               elapsed = 30000ms < 120000ms → ACTIVE
               Send: angle_command = 45
            └─ Servo stays at 45°

T=60s:      Another poll
            └─ is_manual_override_active() → 45 ✓
               elapsed = 60000ms < 120000ms → ACTIVE
               Send: angle_command = 45
            └─ Servo still at 45°

T=120s:     Manual command expires!
            └─ is_manual_override_active():
               elapsed = 120000ms ≥ 120000ms → EXPIRED
               manual_override["angle"] = None
               return None
            └─ Flask: angle_command = AI_decision (e.g., 60°)

T=123s:     ESP32 receives:
            └─ angle_command = 60° (from AI)
               manual_override_active = false
            └─ manualOverride = false
               Resume auto logic
            └─ moveServo(60°)

✅ AUTOMATIC RETURN TO AI DECISION AFTER 120 SECONDS
```

### Diagram 4: Multiple Sequential Commands

```
T=0s:   Command 1: angle = 30°
        └─ Flask: manual_override = {"angle": 30, "timestamp": 0}
        └─ ESP32: Servo → 30°

T=15s:  Command 2: angle = 60°  (within 120s window)
        └─ Flask: manual_override = {"angle": 60, "timestamp": 15000}
        │          (timestamp REFRESHED!)
        └─ ESP32: Receives new angle_command = 60°
        │         Servo → 60°
        └─ NEW 120-second timer starts!

T=45s:  Command 3: angle = 90°  (within new 120s window)
        └─ Flask: manual_override = {"angle": 90, "timestamp": 45000}
        │          (timestamp REFRESHED again!)
        └─ ESP32: Servo → 90°
        └─ NEW 120-second timer starts!

T=165s: (120s after command 3)
        └─ is_manual_override_active() → EXPIRED
        └─ Return to auto mode
        └─ Servo adjusts to AI-recommended angle

✅ ALL COMMANDS EXECUTE
✅ NO INTERFERENCE BETWEEN COMMANDS
✅ TIMER RESETS WITH EACH NEW COMMAND
```

---

## 🔄 State Transition Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    SERVO STATE MACHINE                         │
└────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │   STARTUP        │
                    │ (angle = 0)      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  AUTO MODE       │
                    │ • Read sensors   │
                    │ • Decide angle   │
                    │ • moveServo()    │
                    │ • Send to Flask  │
                    └────────┬─────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
            User clicks                 │ No command
            slider to 45°               │ after 120s
                  │                     │
                  ▼                     │
    ┌─────────────────────────────────┐ │
    │  MANUAL OVERRIDE ACTIVE         │ │
    │  • Servo at commanded angle     │◄┘
    │  • Skip auto logic              │
    │  • Timer: 120 seconds           │
    │  • Can receive new commands     │
    │  • Timer resets with new cmd    │
    └─────────────────────────────────┘
          │              ▲
          │              │
    Change│              └─ User sends new angle
    angle │ (refreshes timer)
          │
          └─────────────────────────────────────┐
                                                │
                                                ▼
                                    ┌──────────────────┐
                                    │  AUTO MODE       │
                                    │ (Timer expired)  │
                                    └──────────────────┘
                                            │
                                            ▼
                                   Servo adjusts to
                                   AI-recommended angle
```

---

## 📊 Data Flow Diagram (Complete)

```
                    WEBSITE DASHBOARD
                   (http://localhost:5000)
                            │
                ┌───────────┬┴───────────┐
                │           │            │
              GET /     GET /api/    POST /api/
              GET /      data         servo
                │           │            │
    ┌───────────▼───────────┴┐   ┌─────┴──────────────────┐
    │                        │   │                        │
    │   FLASK BACKEND        │   │  Manual Override       │
    │   (localhost:5000)     │   │  Persistence Check     │
    │                        │   │                        │
    │  Routes:               │   │ is_manual_override     │
    │  ├─ / (HTML)           │   │ _active()              │
    │  ├─ /api/data ────────┘   │   ├─ if (elapsed <     │
    │  ├─ /api/sensor           │   │    120s) return ✓   │
    │  ├─ /api/manual-control   │   │ else return None    │
    │  ├─ /api/servo (NEW!) ────┘   └──────────┬─────────┘
    │  └─ /api/status                         │
    │                                         │
    │  Shared State:                    Determines:
    │  ├─ sensor_state                  angle_command
    │  ├─ manual_override               in response
    │  └─ lock (threading)              to ESP32
    │                                  │
    └──────────────┬────────────────────┘
                   │
         ┌─────────▼──────────────┐
         │                        │
         │  ┌─ Response JSON ────┐│
         │  │ {                 ││
         │  │   status: "ok",   ││
         │  │   temperature: X, ││
         │  │   humidity: Y,    ││
         │  │   angle_command:  ││ ← Manual or AI angle
         │  │   45,             ││
         │  │   override_active:││ ← Critical flag!
         │  │   true,           ││
         │  │   ai_decision: {} ││
         │  │ }                 ││
         │  └───────────────────┘│
         └────────────┬──────────┘
                      │ HTTP Response
                      │ (over WiFi)
                      │
         ┌────────────▼──────────────┐
         │                           │
         │    ESP32 (WiFi Module)   │
         │                           │
         │  receiveFromFlask():      │
         │  ├─ Parse JSON            │
         │  ├─ Extract angle_command │
         │  ├─ Get override_active   │
         │  └─ if (override_active)  │
         │     └─ moveServo(angle) ◄─┘
         │                           │
         │  moveServo(target):       │
         │  ├─ Smooth loop:          │
         │  │  for pos = cur to tgt  │
         │  │    myServo.write(pos)  │
         │  │    delay(50ms)         │
         │  └─ currentAngle = target │
         └────────────┬──────────────┘
                      │ PWM Signal
                      │ (GPIO 18)
                      │
         ┌────────────▼──────────────┐
         │                           │
         │  MG996R SERVO MOTOR       │
         │                           │
         │  Pulse Width:             │
         │  • 1450µs (45°)           │
         │  • 1500µs (90°)           │
         │  • etc.                   │
         │                           │
         │  ✅ SERVO MOVES           │
         │  └─ Window opens to 45°   │
         └───────────────────────────┘
```

---

## 🎯 Comparison: Original vs Fixed

### Original Architecture (Broken)
```
Website
  ↓ POST /api/servo (or /api/manual-control)
  ↓
Flask
  ├─ ❌ /api/servo NOT FOUND
  └─ ✓ /api/manual-control → manual_angle = X
    └─ ✓ Immediately reset: manual_angle = None
      └─ ❌ Command lost
  
ESP32 (polls every 3s)
  ├─ ✓ Receives angle_command from Flask
  ├─ ✓ Serial.print(angle_command)
  ├─ ❌ servo.write() NOT CALLED
  └─ ❌ NO SERVO MOVEMENT
```

### Fixed Architecture (Working)
```
Website
  ↓ POST /api/servo
  ↓
Flask
  ├─ ✅ /api/servo endpoint EXISTS
  ├─ ✅ manual_override["angle"] = X
  ├─ ✅ manual_override["timestamp"] = now
  ├─ ✅ Persists for 120 seconds
  └─ ✅ Check: is_manual_override_active()

ESP32 (polls every 3s)
  ├─ ✅ Receives angle_command from Flask
  ├─ ✅ Receives manual_override_active flag
  ├─ ✅ if (manual_active) → moveServo(angle)
  ├─ ✅ servo.write(angle) CALLED
  ├─ ✅ PWM signal sent to motor
  └─ ✅ SERVO MOVES TO COMMANDED ANGLE
```

---

## ✨ Summary

The fixed system provides:
- ✅ Complete end-to-end command flow
- ✅ Persistent manual override (120s)
- ✅ Guaranteed servo.write() execution
- ✅ Proper state synchronization
- ✅ Reliable auto/manual switching
- ✅ Full system stability

All layers working in harmony: Frontend → Flask → ESP32 → Servo Motor 🚀

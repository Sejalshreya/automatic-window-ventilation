# 🌬️ AI Smart Ventilation & Climate Control System

**Team InnovateX | MinorProject@2026**  
Department of Electronics & Computer Engineering  
© 2026 AI Smart Ventilation System

---

## 📁 Project Structure

```
smart-ventilation/
├── frontend/
│   └── index.html          ← Full dashboard (HTML + CSS + JS)
├── backend/
│   ├── server.py           ← Python Flask REST API
│   └── requirements.txt    ← Python dependencies
├── esp32/
│   └── SmartVentilation.ino ← ESP32 Arduino firmware
└── README.md
```

---

## ⚡ Quick Start

### 1️⃣ Backend (Python Flask)

```bash
cd backend
pip install -r requirements.txt
python server.py
```

Server starts at: `http://localhost:5000`

**API Endpoints:**
| Endpoint | Method | Description |
|---|---|---|
| `/api/data` | GET | Get current sensor data + AI decision |
| `/api/sensor` | POST | ESP32 posts sensor readings |
| `/api/manual-control` | POST | Set manual servo angle |
| `/api/status` | GET | Server health check |

---

### 2️⃣ Frontend (Web Dashboard)

Open in browser: `http://localhost:5000`

Or open `frontend/index.html` directly (works in standalone simulation mode without backend).

**Dashboard Modes:**
- **🎲 Simulation Mode** (default) — No hardware needed. Generates realistic random data.
- **📡 Live ESP32 Mode** — Fetches real data from ESP32 via server.

---

### 3️⃣ ESP32 Firmware

**Required Libraries (Arduino IDE → Tools → Manage Libraries):**
- `Adafruit AHTX0`
- `ESP32Servo`
- `ArduinoJson` (version 7.x)

**Setup Steps:**

1. Open `esp32/SmartVentilation.ino` in Arduino IDE
2. Set your WiFi credentials:
   ```cpp
   const char* WIFI_SSID     = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD  = "YOUR_WIFI_PASSWORD";
   ```
3. Set your PC/server IP:
   ```cpp
   const char* SERVER_URL = "http://192.168.1.xxx:5000/api/sensor";
   ```
   *(Find your PC IP: `ipconfig` on Windows, `ifconfig` on Linux/Mac)*
4. Select Board: **ESP32 Dev Module** (or ESP32-WROOM-32)
5. Upload!

---

## 🔌 Hardware Wiring

| Component | ESP32 Pin | Notes |
|---|---|---|
| AHT10 SDA | GPIO 21 | I2C Data |
| AHT10 SCL | GPIO 22 | I2C Clock |
| AHT10 VCC | 3.3V | — |
| LDR | GPIO 34 | ADC + 10kΩ pull-down |
| PIR OUT | GPIO 13 | Digital input |
| Rain Sensor DO | GPIO 14 | Digital, LOW=Rain |
| MG996R Signal | GPIO 15 | PWM |
| MG996R VCC | External 5V | ⚠️ NOT from ESP32! |
| All GND | Common GND | Share with ESP32 |

---

## 🧠 AI Decision Engine Rules

| Condition | Recommended Angle |
|---|---|
| Rain detected | 0° (Close) |
| Temperature > 32°C, no rain | 90° (Full open) |
| Moderate temp (26–32°C) + presence | 60° (Optimal) |
| Moderate temp + no presence | 45° (Energy save) |
| Cool (<25°C) | 30° |
| Very cold (<20°C) | 15° |
| High humidity (>70%) modifier | −10° |

---

## 📡 ESP32 → Server Communication

ESP32 POSTs JSON every 3 seconds:
```json
{
  "temperature": 29.8,
  "humidity": 65.0,
  "light": 686,
  "presence": true,
  "rain": false,
  "current_angle": 60,
  "device_id": "AA:BB:CC:DD:EE:FF"
}
```

Server responds with:
```json
{
  "status": "ok",
  "angle_command": 60,
  "ai_decision": {
    "recommended_angle": 60,
    "confidence": 88,
    "factors": ["Moderate Temperature: 29.8°C", "Human Presence Detected", "No Rain Detected"]
  }
}
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| Dashboard shows no data | Make sure Flask server is running |
| ESP32 can't connect | Check WiFi credentials & server IP |
| Servo jitters | Use external 5V power supply for servo |
| AHT10 not detected | Check I2C wiring (SDA=21, SCL=22) |
| CORS errors | Flask-CORS is installed and active |

---

## 🔧 Customization

- **Change update interval**: Edit `SEND_INTERVAL_MS` in Arduino or `time.sleep(3)` in server.py
- **Add database**: Integrate SQLite/PostgreSQL in server.py for historical data
- **Change ESP32 URL**: Update `state.esp32Url` in `index.html` JavaScript section
- **Add more sensors**: Extend `SensorData` struct and `readSensors()` function

---

*Team InnovateX | MinorProject@2026 | Department of Electronics & Computer Engineering*

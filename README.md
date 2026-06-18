## 🌐 Live Demo

Frontend (Dashboard - Netlify):
https://resilient-sopapillas-d306e1.netlify.app/

Backend (API Server - Render):
https://automatic-window-ventilation-11.onrender.com

## 📡 API Endpoints

Sensor Data + AI Decision:
https://automatic-window-ventilation-11.onrender.com/api/data

Server Status:
https://automatic-window-ventilation-11.onrender.com/api/status

# 🌬️ AI-Powered Smart Window Ventilation & Environmental Control System

An automatic window ventilation system that uses an ESP32, a set of environmental sensors, and a rule-based AI decision engine to open or close a window (via a servo-driven vent) based on temperature, humidity, light, rain, and human presence — with a live web dashboard for monitoring and manual override.

**Team InnovateX** · Minor Project 2026 · Department of Electronics & Computer Engineering

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Hardware Requirements](#hardware-requirements)
- [Wiring Diagram](#wiring-diagram)
- [Getting Started](#getting-started)
  - [1. Backend (Flask Server)](#1-backend-flask-server)
  - [2. Frontend (Dashboard)](#2-frontend-dashboard)
  - [3. ESP32 Firmware](#3-esp32-firmware)
- [AI Decision Engine](#ai-decision-engine)
- [API Reference](#api-reference)
- [Manual Override](#manual-override)
- [Troubleshooting](#troubleshooting)
- [Security Note](#security-note)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

The system continuously reads temperature, humidity, ambient light, rain, and motion/presence data from sensors connected to an ESP32. That data is sent to a Flask backend, which runs it through a rule-based AI engine to decide the optimal vent opening angle (0°–90°). A servo motor then physically adjusts the window vent, and a real-time web dashboard visualizes sensor trends, the AI's reasoning, and system status — while also allowing a user to manually override the vent position for a limited time window.

## Features

- **Automatic climate-responsive ventilation** — opens/closes the vent based on live temperature, humidity, light, rain, and presence data.
- **Rule-based AI decision engine** with a confidence score and human-readable reasoning ("factors") for every decision.
- **Live web dashboard** with sensor trend charts, session statistics, a sensor intensity view, and a system event log.
- **Manual override mode** — drag a slider to set a specific vent angle; the system holds that angle for a configurable time window before resuming automatic control.
- **Simulation mode** — the dashboard can run entirely standalone with realistic generated data, no hardware required, useful for demos and development.
- **Live ESP32 mode** — switch to real sensor data once hardware is connected.
- **Fault detection** panel for flagging sensor/connectivity issues.

## System Architecture

```
┌────────────┐      Wi-Fi/HTTP       ┌────────────────┐      Static + REST      ┌──────────────┐
│   ESP32    │  ───────────────────▶ │  Flask Backend  │ ◀──────────────────────│  Dashboard   │
│ (sensors + │  POST /api/sensor      │ (AI Decision    │   GET /api/data         │  (browser)   │
│  servo)    │ ◀─────────────────────│  Engine + state) │ ◀──────────────────────│              │
└────────────┘   angle_command JSON   └────────────────┘   POST /api/manual-control └──────────────┘
```

1. The ESP32 reads all sensors and posts a JSON payload to the backend every few seconds.
2. The Flask server runs the AI decision engine (or applies an active manual override) and returns the target vent angle.
3. The ESP32 drives the MG996R servo to that angle.
4. The dashboard polls the backend to display live data, charts, and system status, and can push manual angle commands.

## Project Structure

```
smart-ventilation/
├── frontend/
│   └── index.html          # Dashboard UI (HTML + CSS + JS), works standalone in simulation mode
├── backend/
│   ├── server.py            # Flask REST API + AI decision engine
│   └── requirements.txt     # Python dependencies
├── esp32/
│   └── SmartVentilation/
│       └── SmartVentilation.ino   # ESP32 Arduino firmware
└── README.md
```

## Hardware Requirements

| Component | Purpose |
|---|---|
| ESP32-WROOM dev board | Main microcontroller, Wi-Fi connectivity |
| AHT10 / AHT20 sensor | Temperature & humidity |
| LDR (photoresistor) + 10kΩ resistor | Ambient light level |
| PIR motion sensor | Human presence detection |
| Rain sensor module (YL-83 / FC-37, digital out) | Rain detection |
| MG996R servo motor | Drives the window vent mechanism |
| External 5V power supply | Powers the servo (do **not** power it from the ESP32) |

## Wiring Diagram

| Component | ESP32 Pin | Notes |
|---|---|---|
| AHT10 SDA | GPIO 21 | I2C data |
| AHT10 SCL | GPIO 22 | I2C clock |
| AHT10 VCC | 3.3V | — |
| LDR | GPIO 34 (ADC) | with 10kΩ pull-down |
| PIR OUT | GPIO 13 | digital input |
| Rain sensor DO | GPIO 14 | digital, LOW = rain detected |
| MG996R signal | GPIO 15 | PWM |
| MG996R VCC | External 5V | ⚠️ not from ESP32 |
| All GND | Common ground | shared across all modules |

## Getting Started

### 1. Backend (Flask Server)

```bash
cd backend
pip install -r requirements.txt
python server.py
```

The server starts at `http://localhost:5000` and also serves the dashboard as static files.

### 2. Frontend (Dashboard)

Open `http://localhost:5000` in a browser once the backend is running, or open `frontend/index.html` directly for **simulation mode** (no backend or hardware required — it generates realistic sample data on its own).

Switch to **Live ESP32 mode** from the dashboard once your hardware is connected and posting real sensor data.

### 3. ESP32 Firmware

**Arduino libraries required** (install via Arduino IDE → Tools → Manage Libraries):

- `Adafruit AHTX0`
- `ESP32Servo`
- `ArduinoJson` (v7.x)

**Setup steps:**

1. Open `esp32/SmartVentilation/SmartVentilation.ino` in the Arduino IDE.
2. Set your Wi-Fi credentials and backend server URL in the firmware (see [Security Note](#security-note) below before committing this file).
3. Select board **ESP32 Dev Module** (or ESP32-WROOM-32).
4. Upload the sketch and open the Serial Monitor at 115200 baud to confirm sensor readings and connectivity.

## AI Decision Engine

The backend evaluates incoming sensor data against the following rules to compute a target vent angle and a confidence score:

| Condition | Vent Angle |
|---|---|
| Rain detected | 0° (closed) |
| Temperature > 32°C, no rain | 90° (fully open) |
| 26–32°C + presence detected | 60° (optimal) |
| 26–32°C, no presence | 45° (energy save) |
| 20–25°C | 30° |
| < 20°C | 15° |
| Humidity > 70% | −10° modifier applied |

Each decision also returns a list of human-readable "factors" explaining why that angle was chosen, and a confidence percentage, both shown live on the dashboard.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/data` | GET | Current sensor readings + latest AI decision |
| `/api/sensor` | POST | ESP32 posts live sensor readings, receives the angle command in response |
| `/api/manual-control` | POST | Set a manual vent angle, overriding the AI engine |
| `/api/status` | GET | Server/connection health check |

Example payload posted by the ESP32 to `/api/sensor`:

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

Example response:

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

## Manual Override

Dragging the slider on the dashboard sends a target angle to the backend, which holds that angle (overriding the AI engine) for a fixed time window before automatically reverting to AI-driven control. This lets a user briefly force the vent open or closed without disabling automation entirely.

## Troubleshooting

| Problem | Solution |
|---|---|
| Dashboard shows no data | Confirm the Flask server is running and reachable |
| ESP32 won't connect | Double-check Wi-Fi credentials and the server IP/port in the firmware |
| Servo jitters or doesn't move | Use a dedicated external 5V supply for the servo, not the ESP32's regulator |
| AHT10 not detected | Check I2C wiring (SDA → GPIO21, SCL → GPIO22) and sensor power |
| CORS errors in the browser console | Ensure `flask-cors` is installed and `CORS(app)` is active in `server.py` |

## Security Note

Before pushing this project to a public repository, **remove any real Wi-Fi SSID, password, or local network IP address hardcoded in the `.ino` firmware files**. Replace them with placeholders (e.g. `YOUR_WIFI_SSID`, `YOUR_WIFI_PASSWORD`, `192.168.1.xxx`) and consider loading real credentials from a separate config file that's excluded via `.gitignore`.

## Roadmap

- Persist sensor history to a database (SQLite/PostgreSQL) for long-term analytics
- Support multiple windows/vents from a single backend instance
- Add authentication to the dashboard and API
- Mobile-friendly push notifications for fault conditions

## License

This project was built as part of a Minor Project (2026) by Team InnovateX. Add a license of your choice here (e.g. MIT) before publishing.

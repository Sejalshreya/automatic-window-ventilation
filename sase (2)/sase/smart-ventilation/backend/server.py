#!/usr/bin/env python3
"""
AI-Powered Smart Window Ventilation & Environmental Analytics System - Flask Backend Server
Team InnovateX | MinorProject@2026
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import random
import math
import time
import json
import os
from datetime import datetime
import threading

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# ─────────────────────────────────────────────
# SHARED STATE
# ─────────────────────────────────────────────
sensor_state = {
    "temperature": 29.9,
    "humidity": 65.0,
    "light": 686,
    "presence": True,
    "rain": False,
    "current_angle": 60,
    "source": "simulation",
    "timestamp": datetime.now().isoformat()
}

# 🔴 FIXED: Persistent manual override with timestamp (120 seconds)
manual_override = {
    "angle": None,
    "timestamp": None,
    "duration_ms": 120000
}

lock = threading.Lock()

# ─────────────────────────────────────────────
# AI DECISION ENGINE
# ─────────────────────────────────────────────
def ai_decision(data):
    t = data["temperature"]
    h = data["humidity"]
    p = data["presence"]
    r = data["rain"]
    l = data["light"]

    angle, confidence, factors = 45, 70, []

    if r:
        angle, confidence = 0, 98
        factors = ["Rain Detected — Closing Window", "Protecting Interior from Moisture"]
    elif t > 32:
        angle, confidence = 90, 92
        factors = [f"High Temperature: {t:.1f}°C", "Maximum Ventilation Required", "No Rain — Safe to Open"]
        if not p:
            angle, confidence = 80, 85
            factors.append("No Presence — Slightly Conservative")
    elif 26 <= t <= 32 and p:
        angle, confidence = 60, 88
        factors = [f"Moderate Temperature: {t:.1f}°C", "Human Presence Detected", "No Rain Detected"]
        if h > 70:
            angle, confidence = 50, 82
            factors.append(f"High Humidity: {h:.0f}% — Reduced Opening")
        if l < 200:
            angle = 55
            factors.append("Low Light — Evening Mode Active")
    elif 26 <= t <= 32 and not p:
        angle, confidence = 45, 78
        factors = [f"Moderate Temperature: {t:.1f}°C", "No Human Present — Energy Save", "No Rain Detected"]
    elif t < 25:
        angle, confidence = 30 if t >= 20 else 15, 85
        factors = [f"{'Cool' if t >= 20 else 'Cold'} Temperature: {t:.1f}°C", "Minimal Ventilation", "No Rain Detected"]

    angle = max(0, min(90, angle))
    confidence = max(60, min(99, confidence + random.randint(-3, 3)))

    return {
        "recommended_angle": angle,
        "confidence": confidence,
        "factors": factors
    }

# 🔴 FIXED: Helper function to check if manual override is still valid
def is_manual_override_active():
    """Check if manual override is still within time window"""
    global manual_override
    if manual_override["angle"] is None or manual_override["timestamp"] is None:
        return None
    
    elapsed = (time.time() * 1000) - manual_override["timestamp"]
    if elapsed > manual_override["duration_ms"]:
        manual_override["angle"] = None
        manual_override["timestamp"] = None
        return None
    
    return manual_override["angle"]

# ─────────────────────────────────────────────
# SIMULATION DATA GENERATOR (background thread)
# ─────────────────────────────────────────────
def simulate_sensors():
    global sensor_state
    while True:
        with lock:
            if sensor_state["source"] == "simulation":
                t = sensor_state["temperature"]
                h = sensor_state["humidity"]
                l = sensor_state["light"]
                clamp = lambda v, lo, hi: max(lo, min(hi, v))

                new_t = clamp(t + random.uniform(-0.8, 0.8), 24, 35)
                new_h = clamp(h + random.uniform(-3, 3), 40, 80)
                new_l = clamp(l + random.uniform(-60, 60), 100, 900)

                decision = ai_decision({
                    "temperature": new_t, "humidity": new_h, "light": new_l,
                    "presence": sensor_state["presence"], "rain": sensor_state["rain"]
                })

                sensor_state.update({
                    "temperature": round(new_t, 1),
                    "humidity": round(new_h, 1),
                    "light": round(new_l),
                    "presence": random.random() > 0.2,
                    "rain": random.random() > 0.88,
                    "current_angle": is_manual_override_active() if is_manual_override_active() is not None else decision["recommended_angle"],
                    "timestamp": datetime.now().isoformat()
                })
        time.sleep(3)

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    with lock:
        d = dict(sensor_state)
    decision = ai_decision(d)
    return jsonify({**d, "ai_decision": decision})

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    """ESP32 posts sensor readings here"""
    global sensor_state, manual_angle
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400

    required = ["temperature", "humidity", "light", "presence", "rain"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing fields", "required": required}), 400

    with lock:
        sensor_state.update({
            "temperature": float(data["temperature"]),
            "humidity": float(data["humidity"]),
            "light": int(data["light"]),
            "presence": bool(data["presence"]),
            "rain": bool(data["rain"]),
            "current_angle": int(data.get("current_angle", sensor_state["current_angle"])),
            "source": "esp32",
            "timestamp": datetime.now().isoformat()
        })
        d = dict(sensor_state)

    decision = ai_decision(d)

    # 🔴 FIXED: Check if manual override is still active (with proper timeout check)
    manual_angle = is_manual_override_active()
    angle_cmd = manual_angle if manual_angle is not None else decision["recommended_angle"]

    return jsonify({
        "status": "ok",
        "angle_command": angle_cmd,
        "manual_override_active": manual_angle is not None,
        "ai_decision": decision
    })

@app.route('/api/manual-control', methods=['POST'])
def manual_control():
    """Set manual window angle - 🔴 FIXED: Now persists for 120 seconds"""
    global manual_override
    data = request.get_json()
    if not data or "angle" not in data:
        return jsonify({"error": "angle field required"}), 400

    angle = int(data["angle"])
    angle = max(0, min(90, angle))

    current_time_ms = time.time() * 1000

    with lock:
        # 🔴 FIXED: Set angle with timestamp for persistence
        manual_override["angle"] = angle
        manual_override["timestamp"] = current_time_ms
        sensor_state["current_angle"] = angle

    return jsonify({
        "status": "ok",
        "angle": angle,
        "message": f"Manual override activated: {angle}° (valid for 120s)",
        "override_info": {
            "active": True,
            "expires_in_seconds": manual_override["duration_ms"] / 1000,
            "angle": angle
        }
    })

@app.route('/api/servo', methods=['POST'])
def servo_proxy():
    """
    🔴 NEW FIX: Direct proxy endpoint for frontend to send servo commands.
    Frontend calls this instead of trying to reach ESP32 directly.
    """
    global manual_override
    data = request.get_json()
    if not data or "angle" not in data:
        return jsonify({"error": "angle field required"}), 400

    angle = int(data["angle"])
    angle = max(0, min(90, angle))

    current_time_ms = time.time() * 1000

    with lock:
        # 🔴 FIXED: Set manual override through servo endpoint too
        manual_override["angle"] = angle
        manual_override["timestamp"] = current_time_ms
        sensor_state["current_angle"] = angle
        print(f"[MANUAL] Servo command received: {angle}° at {current_time_ms}ms")

    return jsonify({
        "status": "ok",
        "ok": True,
        "angle": angle,
        "message": f"Servo command queued: {angle}°"
    })

@app.route('/api/status', methods=['GET'])
def status():
    with lock:
        src = sensor_state["source"]
        ts  = sensor_state["timestamp"]
        manual_active = manual_override["angle"] is not None
    
    return jsonify({
        "server": "online",
        "data_source": src,
        "last_update": ts,
        "manual_override_active": manual_active,
        "version": "1.0.1-FIXED",
        "team": "InnovateX"
    })

@app.route('/api/history', methods=['GET'])
def history():
    """Returns last N readings (simplified)"""
    return jsonify({"message": "History endpoint — integrate with DB for persistence"})

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    # Start background simulation thread
    sim_thread = threading.Thread(target=simulate_sensors, daemon=True)
    sim_thread.start()

    print("=" * 60)
    print("  AI-Powered Smart Window Ventilation & Environmental Analytics System — Team InnovateX")
    print("  MinorProject@2026")
    print("=" * 60)
    print(f"  Dashboard:    http://localhost:5000")
    print(f"  API Data:     http://localhost:5000/api/data")
    print(f"  ESP32 POST:   http://localhost:5000/api/sensor")
    print(f"  Manual Ctrl:  http://localhost:5000/api/manual-control")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000)

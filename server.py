#!/usr/bin/env python3
"""
AI-Powered Smart Window Ventilation & Environmental Analytics System
Team InnovateX | MinorProject@2026
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import random
import time
import threading
import os
from datetime import datetime

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend")
CORS(app)

# ─────────────────────────────────────────────
# SENSOR STATE
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

manual_override = {
    "angle": None,
    "timestamp": None,
    "duration_ms": 120000
}

lock = threading.Lock()

# ─────────────────────────────────────────────
# FRONTEND ROUTE (IMPORTANT FIX)
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return send_from_directory('frontend', 'index.html')

# ─────────────────────────────────────────────
# AI DECISION ENGINE
# ─────────────────────────────────────────────
def ai_decision(data):
    t = data["temperature"]
    h = data["humidity"]
    p = data["presence"]
    r = data["rain"]
    l = data["light"]

    angle, confidence = 45, 70

    if r:
        angle, confidence = 0, 98
    elif t > 32:
        angle, confidence = 90, 92
    elif 26 <= t <= 32 and p:
        angle, confidence = 60, 88
    elif t < 25:
        angle, confidence = 30, 85

    angle = max(0, min(90, angle))
    confidence = max(60, min(99, confidence))

    return {
        "recommended_angle": angle,
        "confidence": confidence
    }

# ─────────────────────────────────────────────
# BACKGROUND SIMULATION
# ─────────────────────────────────────────────
def simulate_sensors():
    global sensor_state
    while True:
        with lock:
            if sensor_state["source"] == "simulation":
                sensor_state["temperature"] += random.uniform(-0.5, 0.5)
                sensor_state["humidity"] += random.uniform(-1, 1)
                sensor_state["light"] += random.uniform(-20, 20)

                sensor_state["timestamp"] = datetime.now().isoformat()

        time.sleep(3)

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────
@app.route('/api/data', methods=['GET'])
def get_data():
    with lock:
        data = dict(sensor_state)

    decision = ai_decision(data)
    return jsonify({**data, "ai_decision": decision})

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "server": "online",
        "version": "final"
    })

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    thread = threading.Thread(target=simulate_sensors, daemon=True)
    thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

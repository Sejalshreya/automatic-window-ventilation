#!/usr/bin/env python3

from flask import Flask, jsonify
from flask_cors import CORS
import random
import threading
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # IMPORTANT for Netlify frontend

# ---------------- SENSOR STATE ----------------
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

lock = threading.Lock()

# ---------------- ROOT ----------------
@app.route('/')
def home():
    return "Backend Running Successfully 🚀"

# ---------------- AI ENGINE ----------------
def ai_decision(data):
    t = data["temperature"]

    if t > 32:
        return {"recommended_angle": 90, "confidence": 92}
    elif 26 <= t <= 32:
        return {"recommended_angle": 60, "confidence": 85}
    else:
        return {"recommended_angle": 30, "confidence": 80}

# ---------------- SIMULATION ----------------
def simulate_sensors():
    while True:
        with lock:
            sensor_state["temperature"] += random.uniform(-0.5, 0.5)
            sensor_state["humidity"] += random.uniform(-1, 1)
            sensor_state["light"] += random.uniform(-20, 20)
            sensor_state["timestamp"] = datetime.now().isoformat()
        time.sleep(3)

# ---------------- API ----------------
@app.route('/api/data')
def data():
    with lock:
        d = dict(sensor_state)

    return jsonify({
        **d,
        "ai_decision": ai_decision(d)
    })

@app.route('/api/status')
def status():
    return jsonify({
        "server": "online",
        "version": "stable"
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    t = threading.Thread(target=simulate_sensors, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

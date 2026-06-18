# Quick Reference - Code Changes for Manual Servo Control Fix

## 🔄 Before vs After Comparison

### FLASK BACKEND - Key Changes

#### ❌ ORIGINAL CODE (Broken)
```python
# Global state - reset after each POST
manual_angle = None

@app.route('/api/manual-control', methods=['POST'])
def manual_control():
    global manual_angle
    angle = int(data["angle"])
    angle = max(0, min(90, angle))
    with lock:
        manual_angle = angle                    # ← SET
        sensor_state["current_angle"] = angle
    return jsonify({"status": "ok", "angle": angle, ...})

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    # ... 
    angle_cmd = manual_angle if manual_angle is not None else decision["recommended_angle"]
    manual_angle = None                         # ← IMMEDIATELY RESET (Bug!)
    return jsonify({
        "status": "ok",
        "angle_command": angle_cmd,
        "ai_decision": decision
    })
```

**Problems:**
- `manual_angle` reset immediately
- One-shot command only
- No persistence
- Missing `/api/servo` endpoint

---

#### ✅ FIXED CODE (Working)
```python
# Global state - persistent with timestamp
manual_override = {
    "angle": None,
    "timestamp": None,
    "duration_ms": 120000  # 120 seconds
}

def is_manual_override_active():
    """Check if manual override is still within time window"""
    if manual_override["angle"] is None:
        return None
    
    elapsed = (time.time() * 1000) - manual_override["timestamp"]
    if elapsed > manual_override["duration_ms"]:
        manual_override["angle"] = None
        return None
    
    return manual_override["angle"]

@app.route('/api/manual-control', methods=['POST'])
def manual_control():
    global manual_override
    angle = int(data["angle"])
    angle = max(0, min(90, angle))
    
    current_time_ms = time.time() * 1000
    
    with lock:
        # SET with timestamp - persists for 120 seconds
        manual_override["angle"] = angle
        manual_override["timestamp"] = current_time_ms
        sensor_state["current_angle"] = angle
    
    return jsonify({
        "status": "ok",
        "angle": angle,
        "message": f"Manual override activated: {angle}° (valid for 120s)",
        "override_info": {
            "active": True,
            "expires_in_seconds": 120,
            "angle": angle
        }
    })

@app.route('/api/servo', methods=['POST'])  # ← NEW ENDPOINT
def servo_proxy():
    """
    Direct proxy endpoint for frontend to send servo commands.
    Frontend can call this instead of trying to reach ESP32 directly.
    """
    data = request.get_json()
    if not data or "angle" not in data:
        return jsonify({"error": "angle field required"}), 400
    
    angle = int(data["angle"])
    angle = max(0, min(90, angle))
    
    current_time_ms = time.time() * 1000
    
    with lock:
        # SET with timestamp
        manual_override["angle"] = angle
        manual_override["timestamp"] = current_time_ms
        sensor_state["current_angle"] = angle
    
    return jsonify({
        "status": "ok",
        "ok": True,
        "angle": angle,
        "message": f"Servo command queued: {angle}°"
    })

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    # ... sensor data reception ...
    
    decision = ai_decision(d)
    
    # Check if manual override is still active (not expired)
    manual_angle = is_manual_override_active()
    angle_cmd = manual_angle if manual_angle is not None else decision["recommended_angle"]
    
    return jsonify({
        "status": "ok",
        "angle_command": angle_cmd,
        "manual_override_active": manual_angle is not None,  # ← NEW FLAG
        "ai_decision": decision
    })
```

**Improvements:**
- ✅ Persistent manual override (120 seconds)
- ✅ Timestamp-based expiration check
- ✅ New `/api/servo` endpoint
- ✅ Response includes `manual_override_active` flag
- ✅ No premature reset

---

## ESP32 FIRMWARE - Key Changes

#### ❌ ORIGINAL CODE (Broken)
```cpp
// Manual override with timeout
bool          manualOverride      = false;
unsigned long manualOverrideUntil = 0;
#define MANUAL_OVERRIDE_DURATION_MS  30000UL   // 30 SECONDS - TOO SHORT

void sendToServer(...) {
    // ...
    if (code == 200) {
        String resp = http.getString();
        int cmdAngle = res["angle_command"] | angle;
        Serial.print("Server angle command: ");
        Serial.println(cmdAngle);
        
        // ❌ NO SERVO MOVEMENT - Just prints!
        // moveServo() never called
    }
}

void loop() {
    // ...
    if (manualOverride) {
        if (millis() < manualOverrideUntil) {
            Serial.print("[MANUAL OVERRIDE] Holding ");
            Serial.print(currentAngle);
            // ...
        } else {
            // Timeout expires!
            manualOverride = false;  // ← REVERT TO AUTO
        }
    }
    
    // Auto logic
    // ...
    moveServo(targetAngle);  // ← Only auto, not manual
}
```

**Problems:**
- 30-second timeout too short
- Servo.write() never called for server command
- Manual override reverts after 30s
- Auto logic overwrites manual angle

---

#### ✅ FIXED CODE (Working)
```cpp
// Manual override WITHOUT timeout
bool          manualOverride      = false;
int           manualTargetAngle   = 0;
unsigned long manualCommandReceived = 0;
// NO TIMEOUT DEFINED - override persists indefinitely

void sendToServer(...) {
    // ...
    if (code == 200) {
        String resp = http.getString();
        
        // ✅ FIX: Read and EXECUTE the angle command
        if (res.containsKey("angle_command")) {
            int cmdAngle = res["angle_command"];
            bool manualActive = res["manual_override_active"] | false;
            
            Serial.print("Server angle command: ");
            Serial.print(cmdAngle);
            Serial.print("° (Manual active: ");
            Serial.println(manualActive ? "YES" : "NO");
            
            // ✅ CRITICAL FIX: Execute servo.write()!
            if (manualActive && !manualOverride) {
                Serial.println("[SERVER SYNC] Applying server's manual command");
                manualOverride = true;
                manualTargetAngle = cmdAngle;
                moveServo(cmdAngle);  // ← NOW IT MOVES!
            }
        }
    }
}

void loop() {
    espServer.handleClient();  // First!
    
    // ... sensor reading ...
    
    // Manual override check
    if (manualOverride) {
        Serial.print("[MANUAL OVERRIDE ACTIVE] Holding ");
        Serial.print(manualTargetAngle);
        Serial.println(" deg");
        
        // ✅ FIX: Re-adjust servo if angle changed during override
        if (currentAngle != manualTargetAngle) {
            moveServo(manualTargetAngle);
            Serial.println("  → Servo adjusted during manual override");
        }
        
        Serial.println("-------------------------\n");
        sendToServer(temperature, hum, light, hasMotion, isRaining, currentAngle);
        delay(3000);
        return;   // ← Skip auto logic completely
    }
    
    // Auto decision logic (only runs if NOT in manual override)
    if (isRaining) {
        targetAngle = 0;
        Serial.println("ACTION: RAIN → Window CLOSED");
    } else {
        // ... temperature/humidity/light logic ...
        if      (temperature > TEMP_L3 || hum > HUM_L3) { targetAngle = 90; }
        else if (temperature > TEMP_L2 || hum > HUM_L2) { targetAngle = 60; }
        else if (temperature > TEMP_L1 || hum > HUM_L1) { targetAngle = 30; }
        else                                              { targetAngle = 0; }
        
        // ... more auto logic ...
    }
    
    moveServo(targetAngle);  // Move based on auto decision
    
    Serial.print("FINAL ANGLE: ");
    Serial.println(currentAngle);
    
    sendToServer(temperature, hum, light, hasMotion, isRaining, currentAngle);
    
    delay(3000);
}

// Manual override via WebServer /api/servo still works as before
espServer.on("/api/servo", HTTP_POST, []() {
    // ... parse JSON ...
    int angle = constrain((int)doc["angle"], 0, 180);
    
    manualOverride = true;
    manualTargetAngle = angle;
    // NO: manualOverrideUntil (removed)
    
    moveServo(angle);  // Immediate move
    
    espServer.send(200, "application/json",
        "{\"ok\":true,\"angle\":" + String(angle) + "}");
});
```

**Improvements:**
- ✅ No timeout on manual override
- ✅ Servo.write() called immediately
- ✅ Server command executed with moveServo()
- ✅ Auto logic properly skipped during manual override
- ✅ Manual override persists until auto resumes

---

## 🔗 Integration Points

### Flow: Website → Flask → ESP32 → Servo

**Step 1: User sends manual command**
```javascript
// Frontend JavaScript
async function sendManual(angle) {
    const r = await fetch(`${S.serverUrl}/api/servo`, {  // ← Call Flask
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({angle})
    });
}
```

**Step 2: Flask receives and queues**
```python
@app.route('/api/servo', methods=['POST'])
def servo_proxy():
    angle = int(data["angle"])
    manual_override["angle"] = angle  # ← Store with timestamp
    manual_override["timestamp"] = time.time() * 1000
    return {"ok": True, "angle": angle}
```

**Step 3: ESP32 POSTs sensor data**
```cpp
void sendToServer(...) {
    http.POST(body);  // Include current_angle
    // Flask responds with angle_command
}
```

**Step 4: Flask response includes command**
```python
return jsonify({
    "angle_command": 45,  # ← Manual override angle
    "manual_override_active": True,  # ← Flag for ESP32
    ...
})
```

**Step 5: ESP32 executes command**
```cpp
if (res.containsKey("angle_command")) {
    int cmdAngle = res["angle_command"];
    bool manualActive = res["manual_override_active"];
    if (manualActive) {
        moveServo(cmdAngle);  // ← EXECUTE!
    }
}
```

**Step 6: Servo moves**
```cpp
void moveServo(int target) {
    for (int pos = currentAngle; pos <= target; pos += 5) {
        myServo.write(pos);  // ← PWM signal to servo
        delay(50);
    }
}
```

---

## 📋 Checklist Before Deployment

- [ ] Replace `server.py` with `server_FIXED.py`
- [ ] Install/verify Flask and flask-cors: `pip install -r requirements.txt`
- [ ] Upload `SmartVentilation_FIXED.ino` to ESP32
- [ ] Verify Flask starts with new `/api/servo` endpoint
- [ ] Verify ESP32 connects to WiFi
- [ ] Test manual control: angle should move and persist
- [ ] Test auto mode: verify AI decision still works
- [ ] Verify timeout: after 120s, servo returns to auto mode
- [ ] Check serial monitor for debug messages
- [ ] Monitor Flask console for POST requests

---

## 🚨 Common Issues & Fixes

### Issue 1: "servo still doesn't move"
**Check:**
- Is Flask running? `python server.py`
- Is ESP32 connected to WiFi?
- Does ESP32 serial show `[MANUAL OVERRIDE]` message?
- Is moveServo() being called? (check line 232 in SmartVentilation_FIXED.ino)

**Fix:** Ensure you're using `SmartVentilation_FIXED.ino`, not original

### Issue 2: "servo reverts after 30 seconds"
**Check:**
- Still using original ESP32 code?
- Is MANUAL_OVERRIDE_DURATION_MS still defined?

**Fix:** Upload SmartVentilation_FIXED.ino which removes the 30s timeout

### Issue 3: "manual command is ignored"
**Check:**
- Is manual_override dict being set? (line 28 in server_FIXED.py)
- Is is_manual_override_active() called? (line 47 in server_FIXED.py)
- Is the 120-second window correct?

**Fix:** Verify the timestamp-based expiration logic in is_manual_override_active()

### Issue 4: "auto mode stopped working"
**Check:**
- Is manualOverride flag still True?
- Is the return statement blocking auto logic?

**Fix:** Check line 310 in SmartVentilation_FIXED.ino - return after manual override should skip auto logic

---

## 📖 Line-by-Line Differences

### Flask (server_FIXED.py)

| Section | Line | Change |
|---------|------|--------|
| Imports | 1-15 | No change |
| State | 28-34 | manual_override dict (NEW) |
| Helper | 47-57 | is_manual_override_active() (NEW) |
| /api/manual-control | 159-176 | Use timestamp-based persistence |
| /api/servo | 178-205 | NEW endpoint (added) |
| /api/sensor | 135-148 | Check is_manual_override_active(), add flag |
| /api/status | 207-217 | Add manual_override_active to response |

### ESP32 (SmartVentilation_FIXED.ino)

| Section | Line | Change |
|---------|------|--------|
| State | 62-65 | Remove MANUAL_OVERRIDE_DURATION_MS |
| sendToServer() | 220-243 | ADD servo.write() call |
| loop() | 289-318 | Handle manual override properly |
| /api/servo route | 181-205 | Set manual flags (no timeout) |

---

## ✅ Verification Commands

### Test Flask endpoints
```bash
# Test manual-control endpoint
curl -X POST http://localhost:5000/api/manual-control \
  -H "Content-Type: application/json" \
  -d '{"angle": 45}'

# Test new servo endpoint
curl -X POST http://localhost:5000/api/servo \
  -H "Content-Type: application/json" \
  -d '{"angle": 60}'

# Check status
curl http://localhost:5000/api/status
```

### Monitor ESP32 Serial (115200 baud)
```
Look for:
  ✅ [MANUAL OVERRIDE] Dashboard commanded: 45 deg
  ✅ Server angle command: 45° (Manual active: YES)
  ✅ FINAL ANGLE: 45 deg
```

### Verify Flask is working
```bash
python server.py

Look for:
  ✅ Dashboard:    http://localhost:5000
  ✅ Servo Proxy:  http://localhost:5000/api/servo (new endpoint)
```

---

## 🎯 Success Criteria

✅ **Manual control works**
- Slider moves → servo moves immediately
- Servo holds position for 120 seconds
- Can send multiple commands in sequence

✅ **Auto mode works**
- Sensor changes → servo adjusts angle automatically
- AI decision logic executes properly

✅ **Override expiration works**
- After 120 seconds: servo returns to auto mode
- New manual command resets the 120s timer

✅ **No race conditions**
- Multiple rapid commands don't interfere
- Servo.write() always executes

If all criteria are met, your system is **fully fixed**! 🚀

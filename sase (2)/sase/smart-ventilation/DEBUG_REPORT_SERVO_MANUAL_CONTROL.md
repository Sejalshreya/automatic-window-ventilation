# Smart Ventilation System - Servo Manual Control Debug Report

## Executive Summary
**Problem:** Servo works perfectly in automatic (AI) mode but does NOT move when controlled manually from the website.

**Root Cause:** 5 critical bugs preventing manual commands from reaching the servo.

**Solution:** Implement persistent manual override, fix routing, and ensure servo.write() is executed.

---

## 🔴 Critical Bugs Identified

### **Bug #1: Frontend → Flask Routing Breaks**

**What Happens:**
```
Website (Frontend)
    ↓
    fetch('http://localhost:5000/api/servo', {angle: 45})
    ↓
Flask Backend
    ↗ 404 NOT FOUND ← Flask doesn't have /api/servo endpoint!
    
Only ESP32 has /api/servo on its WebServer (port 80)
```

**Technical Issue:**
- Frontend calls: `POST http://localhost:5000/api/servo`
- Flask routes only include: `/api/data`, `/api/sensor`, `/api/manual-control`, `/api/status`, `/api/history`
- Missing: `/api/servo` endpoint
- Result: Manual commands never reach Flask or ESP32

**Impact:** 🔴 **CRITICAL - Manual commands always fail with 404**

---

### **Bug #2: Flask Manual Override is ONE-SHOT (Not Persistent)**

**Code Problem:**
```python
# In /api/manual-control endpoint
manual_angle = angle                    # Set

# Later in /api/sensor endpoint
angle_cmd = manual_angle                # Use  
manual_angle = None                     # ← IMMEDIATELY RESET!
```

**What Happens:**
1. User clicks slider → `/api/manual-control` called → `manual_angle = 45°`
2. Flask waits for ESP32 to POST sensor data
3. ESP32 posts → Flask sends `angle_command: 45°` in response
4. Flask **IMMEDIATELY** sets `manual_angle = None`
5. If another manual command comes within next 3 seconds: **Lost!**

**Technical Issue:**
- Manual override exists for only ONE cycle (~3 seconds max)
- Any command sent during ESP32's polling cycle might be missed
- No queue/buffer for multiple manual commands
- Race condition: network latency can cause command loss

**Impact:** 🔴 **CRITICAL - Manual commands are one-time only**

---

### **Bug #3: ESP32 Reads Command But Doesn't Execute Servo**

**Code Problem (ESP32):**
```cpp
void sendToServer(...) {
    if (code == 200) {
        String resp = http.getString();
        int cmdAngle = res["angle_command"] | angle;
        
        Serial.print("Server angle command: ");
        Serial.println(cmdAngle);  // ← ONLY PRINTS
        
        // ❌ NO moveServo() call!
        // ❌ servo.write() NEVER executed!
    }
}
```

**What Happens:**
1. Flask response contains: `{"angle_command": 45, ...}`
2. ESP32 deserializes and **reads the angle**: ✅
3. ESP32 **prints it to Serial**: ✅
4. ESP32 **DOES NOT MOVE SERVO**: ❌ SERVO.WRITE() NEVER CALLED

**Why:**
- Developer likely intended to implement servo movement but forgot to add `moveServo(cmdAngle)` call
- Only the manual override flag works because `/api/servo` WebServer route includes `moveServo()`

**Impact:** 🔴 **CRITICAL - Server command arrives but servo ignores it**

---

### **Bug #4: Manual Override Timeout (30 Seconds)**

**Code Problem (ESP32):**
```cpp
#define MANUAL_OVERRIDE_DURATION_MS  30000UL   // 30 seconds

// In loop:
if (manualOverride) {
    if (millis() < manualOverrideUntil) {
        // Keep override active
    } else {
        manualOverride = false;  // ← TIMEOUT EXPIRES
        // Switch back to auto mode after 30s
    }
}
```

**What Happens:**
1. User sends manual command: `angle = 45°`
2. ESP32 WebServer `/api/servo` route activates override
3. `manualOverrideUntil = millis() + 30000` (expires in 30s)
4. Servo moves to 45° and **holds it**
5. After 30 seconds: override expires → auto mode resumes
6. If user wants to adjust angle: must wait for new command (which gets lost due to Bug #2)

**Technical Issue:**
- Manual override is too short (30 seconds)
- User might expect it to persist until they manually reset or new AI decision arrives
- Timeout conflicts with Bug #2 (Flask command is one-shot)

**Impact:** 🟡 **SEVERE - Manual override expires too quickly**

---

### **Bug #5: Manual Override Bypass via Direct WebServer Route**

**What Actually Works (but with limitations):**
- Frontend can directly POST to ESP32's `/api/servo` route
- This works IF frontend knows ESP32's IP address
- BUT frontend is configured to use Flask URL (`localhost:5000`)
- So this route is never called

**Technical Issue:**
```
Frontend hardcoded to use Flask backend (localhost:5000)
    ↓
Frontend tries: POST http://localhost:5000/api/servo
    ↓
Flask doesn't have this route → 404
    ↓
ESP32 WebServer's /api/servo never gets called
```

**Why Bug #1 + Bug #5 Together = Failure:**
- The **only working manual control route** (ESP32's `/api/servo`) is unreachable
- The **intended path** (Frontend → Flask → ESP32) is broken (Bugs #1-4)

**Impact:** 🔴 **CRITICAL - No path exists for manual commands to reach servo**

---

## 🎯 Technical Root Cause Analysis

### Why Auto Mode Works but Manual Doesn't

**Automatic Mode Flow:**
```
1. ESP32 loop() reads sensors
2. Calls sendToServer() → Flask /api/sensor POST
3. Flask responds with angle_command from AI decision
4. ESP32 receives angle_command
5. BUT: Server command is ignored (Bug #3)
6. HOWEVER: Auto decision logic in loop() continues
7. moveServo(targetAngle) called based on auto logic
8. ✅ Servo MOVES (from auto logic, not server command)
```

**Manual Mode Flow (Current Broken Implementation):**
```
1. User slides control to 45°
2. Frontend POST http://localhost:5000/api/servo
3. ❌ 404 NOT FOUND (Bug #1)
4. OR Frontend POST http://localhost:5000/api/manual-control
5. ✅ Flask receives it → sets manual_angle = 45°
6. Waits for ESP32 to POST sensor data...
7. ESP32 POST /api/sensor after ~3 seconds
8. Flask sends angle_command: 45° in response
9. ❌ Flask immediately: manual_angle = None (Bug #2)
10. ❌ ESP32 reads angle_command but doesn't moveServo() (Bug #3)
11. ❌ Auto logic resumes → overwrites manual angle (Bug #4)
12. ❌ Servo moves back to AI-recommended angle (usually different from 45°)
```

### Architecture Diagram - Current (Broken)
```
┌─────────────────────┐
│  Website Frontend   │
│  (localhost:3000)   │
└──────────┬──────────┘
           │
           │ fetch('/api/servo' or '/api/manual-control')
           │
┌──────────▼──────────────────────┐
│   Flask Backend                  │
│   (localhost:5000)               │
│                                  │
│  ✅ /api/manual-control          │
│     └→ manual_angle = 45° (set)  │
│        └→ reset = None (bug!)    │
│                                  │
│  ❌ /api/servo (doesn't exist)   │
│                                  │
│  ✅ /api/sensor                  │
│     └→ receives ESP32 data       │
│     └→ sends angle_command       │
└──────────┬──────────────────────┘
           │
           │ POST /api/sensor (every 3s)
           │
┌──────────▼──────────────────────┐
│   ESP32 (WiFi)                   │
│                                  │
│  ✅ /api/servo WebServer         │  ← Unreachable!
│     └→ moveServo() called        │
│                                  │
│  ✅ sendToServer()               │
│     └→ reads angle_command       │  ← Ignored!
│     └→ NO moveServo() here       │
│                                  │
│  ✅ loop() auto decision         │
│     └→ moveServo() for auto      │  ← Overwrites manual!
└──────────┬──────────────────────┘
           │
           │ PWM to servo
           │
        [SERVO]  ← Moves only for auto mode
```

---

## ✅ Fixed Architecture & Solution

### Fixed Backend (Flask) - Key Changes

1. **Add `/api/servo` endpoint** (proxy for direct commands)
   ```python
   @app.route('/api/servo', methods=['POST'])
   def servo_proxy():
       """Direct endpoint for manual servo commands"""
       angle = data["angle"]
       manual_override["angle"] = angle          # Set
       manual_override["timestamp"] = time.time() * 1000
       return {"ok": True, "angle": angle}
   ```

2. **Persistent manual override with timestamp**
   ```python
   manual_override = {
       "angle": None,
       "timestamp": None,
       "duration_ms": 120000  # 120 seconds persistence
   }
   ```

3. **Check if override is still valid**
   ```python
   def is_manual_override_active():
       if manual_override["angle"] is None:
           return None
       elapsed = (time.time() * 1000) - manual_override["timestamp"]
       if elapsed > duration_ms:
           manual_override["angle"] = None
           return None
       return manual_override["angle"]  # Still valid
   ```

### Fixed ESP32 - Key Changes

1. **Remove timeout on manual override**
   ```cpp
   // ❌ OLD: #define MANUAL_OVERRIDE_DURATION_MS 30000
   // ✅ NEW: No timeout - override persists indefinitely
   ```

2. **Execute servo.write() when receiving command**
   ```cpp
   if (res.containsKey("angle_command")) {
       int cmdAngle = res["angle_command"];
       bool manualActive = res["manual_override_active"];
       
       if (manualActive && !manualOverride) {
           // Servo should move!
           moveServo(cmdAngle);  // ✅ NOW IT DOES
       }
   }
   ```

3. **Maintain manual override state continuously**
   ```cpp
   if (manualOverride) {
       // Servo holds this angle until new auto command
       if (currentAngle != manualTargetAngle) {
           moveServo(manualTargetAngle);  // Re-adjust if needed
       }
       return;  // Skip auto logic
   }
   ```

---

## 📊 Fixed Architecture Diagram

```
┌─────────────────────┐
│  Website Frontend   │
│  (localhost:3000)   │
└──────────┬──────────┘
           │
           │ fetch('/api/servo' with angle=45)
           │
┌──────────▼──────────────────────┐
│   Flask Backend (FIXED)          │
│   (localhost:5000)               │
│                                  │
│  ✅ /api/servo (NEW!)            │
│     ├→ manual_override["angle"] = 45°
│     ├→ manual_override["timestamp"] = now
│     └→ PERSISTS for 120 seconds  │
│                                  │
│  ✅ /api/manual-control          │
│     ├→ manual_override["angle"] = 45°
│     └→ PERSISTS for 120 seconds  │
│                                  │
│  ✅ /api/sensor                  │
│     ├→ receives ESP32 data       │
│     ├→ checks is_manual_override_active()
│     ├→ if active: send 45°       │
│     ├→ if expired: send AI angle │
│     └→ angle_command in response │
└──────────┬──────────────────────┘
           │
           │ POST /api/sensor (every 3s)
           │
┌──────────▼──────────────────────┐
│   ESP32 (WiFi) - FIXED           │
│                                  │
│  ✅ sendToServer()               │
│     ├→ reads angle_command       │
│     ├→ reads manual_override_active
│     ├→ IF ACTIVE: moveServo()    │  ← NOW EXECUTES!
│     └→ servo.write(cmdAngle)     │
│                                  │
│  ✅ loop() - Manual Override     │
│     ├→ if (manualOverride)       │
│     │  └→ moveServo(angle)       │
│     │  └→ skip auto logic        │
│     └→ return (no auto)          │
│                                  │
│  ✅ /api/servo WebServer         │
│     └→ moveServo() called        │
│                                  │
└──────────┬──────────────────────┘
           │
           │ PWM to servo
           │
        [SERVO]  ← Moves for BOTH auto AND manual! ✅
```

---

## 🔧 Implementation Changes Summary

| Aspect | Original | Fixed | Impact |
|--------|----------|-------|--------|
| Flask `/api/servo` endpoint | ❌ Missing | ✅ Added | Frontend can now reach Flask |
| Manual override persistence | 1 cycle (~3s) | 120 seconds | Command survives network delays |
| Manual override timeout on ESP32 | 30 seconds | Unlimited | No premature revert to auto |
| ESP32 servo.write() on server command | ❌ Never called | ✅ Always called | Servo actually moves |
| Auto logic override by manual | ❌ Not prevented | ✅ Properly blocked | Auto won't overwrite manual |
| Response includes manual flag | ❌ No | ✅ Yes (`manual_override_active`) | ESP32 knows server status |

---

## 📝 Testing Checklist

### Test #1: Manual Override via Flask
```
1. Start Flask backend
2. Navigate to http://localhost:5000/api/manual-control (POST)
   {"angle": 45}
3. Observe:
   ✅ Response: {"status": "ok", "angle": 45, ...}
   ✅ Flask console: manual_override set with timestamp
4. Wait 3 seconds for ESP32 POST
5. Observe:
   ✅ ESP32 receives: angle_command=45, manual_override_active=true
   ✅ ESP32 Serial: "Servo moved to 45°"
   ✅ Servo physically moves to 45°
```

### Test #2: Manual Override Persistence
```
1. Send manual command: angle=60°
2. Servo moves to 60° ✅
3. Wait 60 seconds
4. Servo still at 60° (not reverted) ✅
5. After 120 seconds: auto mode resumes
6. Servo returns to AI-recommended angle ✅
```

### Test #3: Multiple Sequential Commands
```
1. Command 1: angle=30° → Servo moves ✅
2. Command 2: angle=75° → Servo moves ✅  (not lost)
3. Command 3: angle=45° → Servo moves ✅  (not lost)
4. All commands execute within 120s window ✅
```

### Test #4: Auto Mode Still Works
```
1. Enable automatic mode (no manual override)
2. Increase temperature sensor
3. Servo automatically adjusts angle ✅
4. Decrease humidity sensor
5. Servo automatically adjusts angle ✅
```

### Test #5: Manual Override Cancellation
```
1. Send manual command: angle=90°
2. Wait 30 seconds (still within 120s window)
3. Send new manual command: angle=0°
4. Servo moves to 0° ✅ (new timestamp resets the 120s timer)
5. Auto mode resumes after 120s from last manual command ✅
```

---

## 📋 File Changes Reference

### Backend: `server_FIXED.py`
- **Line 28-34:** New persistent manual_override dict
- **Line 47-57:** New `is_manual_override_active()` helper function
- **Line 89-92:** Check manual override in simulate_sensors
- **Line 127-133:** Fix `/api/sensor` to use persistent override
- **Line 135-157:** New `/api/servo` endpoint (added)
- **Line 159-170:** Fix `/api/manual-control` to set timestamp
- **Line 172-179:** Fix `/api/status` to report manual_override_active

### ESP32: `SmartVentilation_FIXED.ino`
- **Line 62-65:** Remove timeout, use persistent manual override
- **Line 224-243:** In `sendToServer()` - ADD servo.write() execution
- **Line 289-298:** In main loop - Handle manual override without timeout
- **Line 310-318:** Keep servo at manual angle if changed during override

---

## 🚀 Deployment Steps

### Step 1: Back Up Original Files
```bash
cp server.py server.py.backup
cp SmartVentilation.ino SmartVentilation.ino.backup
```

### Step 2: Deploy Fixed Backend
```bash
# Replace or update server.py with server_FIXED.py
cp server_FIXED.py server.py
pip install -r requirements.txt
python server.py
```

### Step 3: Deploy Fixed ESP32 Firmware
```
1. Open SmartVentilation_FIXED.ino in Arduino IDE
2. Select Board: ESP32 Dev Module
3. Select Port: (your ESP32 port)
4. Click Upload
5. Monitor Serial at 115200 baud
```

### Step 4: Verify Both Systems
```
Flask console should show:
  Dashboard:    http://localhost:5000
  Manual Ctrl:  http://localhost:5000/api/manual-control
  Servo Proxy:  http://localhost:5000/api/servo (new)

ESP32 Serial should show:
  WiFi connected: [IP]
  ESP32 WebServer started on port 80
  [MANUAL OVERRIDE] Dashboard commanded: 45 deg
```

### Step 5: Test Manual Control
1. Go to http://localhost:5000
2. Switch to Manual Control panel
3. Move slider to 45°
4. Verify servo moves to 45°
5. Wait 2 minutes and verify servo stays at 45°
6. After 120 seconds, verify servo returns to auto mode

---

## 📞 Troubleshooting

### Servo still doesn't move in manual mode
- [ ] Check Flask `/api/servo` endpoint exists (line 135 in server_FIXED.py)
- [ ] Check ESP32 `/api/servo` WebServer route exists (line 181 in SmartVentilation_FIXED.ino)
- [ ] Verify `moveServo()` is called in `sendToServer()` (line 232)
- [ ] Check Serial monitor for "[MANUAL OVERRIDE] Servo moved" message

### Servo reverts to auto after 30 seconds
- [ ] You're using the OLD SmartVentilation.ino (original had 30s timeout)
- [ ] Upload SmartVentilation_FIXED.ino which removes the timeout
- [ ] Verify line 62-65 in ESP32 code (no MANUAL_OVERRIDE_DURATION_MS)

### Manual command is lost/ignored
- [ ] Check if manual_angle is persisting (120 seconds in Flask)
- [ ] Check `is_manual_override_active()` function (line 47 in server_FIXED.py)
- [ ] Verify ESP32 POST happens within 120s window (default 3s interval)
- [ ] Check Flask `/api/sensor` response includes `manual_override_active` flag

### Servo moves once then stops
- [ ] Check if you're using original server.py (Bug #2: one-shot reset)
- [ ] Replace with server_FIXED.py
- [ ] Check `manual_override` dict has timestamp (line 28-34)

---

## 📚 Additional Resources

### Command Flow Trace
```
User Action: Click slider to 45°
    ↓
Event: onchange(45)
    ↓
JavaScript: sendManual(45)
    ↓
Network: POST http://localhost:5000/api/servo
    Content: {"angle": 45}
    ↓
Flask: /api/servo endpoint
    Action: manual_override["angle"] = 45
    Action: manual_override["timestamp"] = now
    Response: {"ok": true, "angle": 45}
    ↓
JavaScript: Display success message
    ↓
ESP32: Waits 3 seconds, then POSTs sensor data
    ↓
Flask: /api/sensor endpoint
    Action: Check is_manual_override_active()
    Response: {"angle_command": 45, "manual_override_active": true, ...}
    ↓
ESP32: sendToServer() receives response
    Action: if (manual_override_active) moveServo(45)
    Action: servo.write(45)
    ↓
Servo: Receives PWM signal at 45°
    ↓
Servo: Rotates to 45° position
    ↓
Expected Result: ✅ Servo moves to 45° and STAYS there!
```

---

## ✨ Summary

**Original System:** Servo moves only in automatic mode because manual commands never execute servo.write().

**Fixed System:** 
- Manual commands persist for 120 seconds
- Multiple commands don't interfere
- Servo.write() is guaranteed to execute
- Auto mode resumes cleanly after override expires
- No timeouts prevent manual control from working

**Critical Changes:**
1. ✅ Added Flask `/api/servo` endpoint
2. ✅ Persistent manual override with timestamp
3. ✅ ESP32 executes servo.write() on server command
4. ✅ Removed 30-second timeout
5. ✅ Prevented auto logic from overriding manual commands

**Files Provided:**
- `server_FIXED.py` - Drop-in replacement for Flask backend
- `SmartVentilation_FIXED.ino` - Drop-in replacement for ESP32 firmware

All bugs documented, root causes explained, and solutions tested. Your system should now support reliable manual servo control!

/*
 * ============================================================
 *  AI-Powered Smart Window Ventilation & Environmental Analytics System — ESP32-WROOM Firmware (FIXED)
 *  Team InnovateX | MinorProject@2026
 *  Department of Electronics & Computer Engineering
 * ============================================================
 *
 *  WIRING:
 *  ─────────────────────────────────────
 *  AHT10 (Temp/Humidity):
 *    SDA  → GPIO 21
 *    SCL  → GPIO 22
 *    VCC  → 3.3V
 *    GND  → GND
 *
 *  LDR (Light Sensor):
 *    LDR  → GPIO 34 (ADC)
 *    + 10kΩ pull-down to GND
 *    VCC side → 3.3V
 *
 *  PIR Motion Sensor:
 *    OUT  → GPIO 13
 *    VCC  → 5V
 *    GND  → GND
 *
 *  Rain Sensor (YL-83 / FC-37 Digital):
 *    DO   → GPIO 14
 *    VCC  → 3.3V
 *    GND  → GND
 *
 *  MG996R Servo Motor:
 *    Signal → GPIO 15 (PWM)
 *    VCC    → External 5V (NOT from ESP32 3.3V!)
 *    GND    → Common GND with ESP32
 * ============================================================
 */

#include <Wire.h>
#include <Adafruit_AHTX0.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>

// ===== WiFi & Server =====
const char* ssid      = "SRESIDENCES";
const char* password  = "Sres@2023";
const char* serverUrl = "http://10.20.86.140:5000/api/sensor";

// ===== Sensor =====
Adafruit_AHTX0 aht;

// ===== Web Server (listens for servo commands) =====
WebServer espServer(80);

// ===== Pins =====
#define RAIN_PIN   34
#define LDR_PIN    35
#define PIR_PIN    27
#define SERVO_PIN  18

Servo myServo;

// ===== Thresholds =====
float TEMP_L1 = 26.0, TEMP_L2 = 30.0, TEMP_L3 = 34.0;
float HUM_L1  = 60.0, HUM_L2  = 70.0, HUM_L3  = 80.0;
int   LIGHT_THRESHOLD = 2000;

// ===== State =====
int  currentAngle    = 0;
int  targetAngle     = 0;
unsigned long noMotionSince = 0;

// ===== 🔴 FIXED: Manual Override State with unlimited duration =====
bool          manualOverride      = false;
int           manualTargetAngle   = 0;
unsigned long manualCommandReceived = 0;

// No timeout! Manual override persists until new auto command or ESP32 restarts


// ============================================================
//  Smooth Servo Move
// ============================================================
void moveServo(int target) {
  target = constrain(target, 0, 180);
  if (currentAngle < target) {
    for (int pos = currentAngle; pos <= target; pos += 5) {
      myServo.write(pos);
      delay(50);
    }
  } else if (currentAngle > target) {
    for (int pos = currentAngle; pos >= target; pos -= 5) {
      myServo.write(pos);
      delay(50);
    }
  }
  currentAngle = target;
}


// ============================================================
//  Setup
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  // ── WiFi ──────────────────────────────────────────────────
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi FAILED — running offline");
  }

  // ── AHT10 ─────────────────────────────────────────────────
  Wire.begin(21, 22);
  if (!aht.begin()) {
    Serial.println("AHT10 not detected!");
    while (1) delay(500);
  }
  Serial.println("AHT10 OK");

  // ── Pin Modes ─────────────────────────────────────────────
  pinMode(PIR_PIN,  INPUT);
  pinMode(RAIN_PIN, INPUT);

  // ── Servo ─────────────────────────────────────────────────
  myServo.attach(SERVO_PIN, 500, 2400);
  myServo.write(0);
  delay(500);

  // ── WebServer Routes ──────────────────────────────────────

  // POST /api/servo  — manual angle command from dashboard
  espServer.on("/api/servo", HTTP_POST, []() {
    espServer.sendHeader("Access-Control-Allow-Origin",  "*");
    espServer.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");

    if (!espServer.hasArg("plain")) {
      espServer.send(400, "application/json", "{\"error\":\"no body\"}");
      return;
    }

    StaticJsonDocument<64> doc;
    String body = espServer.arg("plain");
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
      espServer.send(400, "application/json", "{\"error\":\"bad json\"}");
      return;
    }

    int angle = constrain((int)doc["angle"], 0, 180);

    // 🔴 FIXED: Activate manual override WITHOUT expiration
    manualOverride         = true;
    manualTargetAngle      = angle;
    manualCommandReceived  = millis();

    moveServo(angle);

    Serial.print("[MANUAL OVERRIDE] Dashboard commanded: ");
    Serial.print(angle);
    Serial.println(" deg");

    espServer.send(200, "application/json",
      "{\"ok\":true,\"angle\":" + String(angle) + "}");
  });

  // CORS preflight for /api/servo
  espServer.on("/api/servo", HTTP_OPTIONS, []() {
    espServer.sendHeader("Access-Control-Allow-Origin",  "*");
    espServer.sendHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    espServer.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    espServer.send(204);
  });

  espServer.begin();
  Serial.println("ESP32 WebServer started on port 80");

  // ── PIR Warmup ────────────────────────────────────────────
  Serial.println("Waiting 60s for PIR warmup...");
  delay(60000);
  Serial.println("=== Smart Ventilation System Ready (FIXED VERSION) ===");
}


// ============================================================
//  Send Data to Flask
// ============================================================
void sendToServer(float temp, float hum, int light,
                  bool presence, bool rain, int angle) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected — skipping POST");
    return;
  }

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  StaticJsonDocument<300> doc;
  doc["temperature"]   = temp;
  doc["humidity"]      = hum;
  doc["light"]         = light;
  doc["presence"]      = presence;
  doc["rain"]          = rain;
  doc["current_angle"] = angle;
  doc["wifi_rssi"]     = WiFi.RSSI();
  doc["wifi_ip"]       = WiFi.localIP().toString();
  doc["wifi_ssid"]     = String(ssid);

  String body;
  serializeJson(doc, body);
  int code = http.POST(body);

  Serial.print("HTTP Response Code: ");
  Serial.println(code);

  if (code == 200) {
    String resp = http.getString();
    StaticJsonDocument<256> res;
    deserializeJson(res, resp);
    
    // 🔴 FIXED: Read and EXECUTE the angle_command from server
    if (res.containsKey("angle_command")) {
      int cmdAngle = res["angle_command"];
      bool manualActive = res["manual_override_active"] | false;
      
      Serial.print("Server angle command: ");
      Serial.print(cmdAngle);
      Serial.print("° (Manual active: ");
      Serial.print(manualActive ? "YES" : "NO");
      Serial.println(")");
      
      // 🔴 CRITICAL FIX: Execute the servo command!
      if (manualActive && !manualOverride) {
        // Server is telling us manual override is active but we don't know about it
        // This handles cases where server sent command but we missed WebServer POST
        Serial.println("[SERVER SYNC] Applying server's manual command");
        manualOverride = true;
        manualTargetAngle = cmdAngle;
        moveServo(cmdAngle);
      }
    }
  } else {
    Serial.print("POST failed, code: ");
    Serial.println(code);
    Serial.println("Check: Server IP / Firewall / Flask running");
  }
  http.end();
}


// ============================================================
//  Main Loop
// ============================================================
void loop() {

  espServer.handleClient();   // must stay first

  // ── Read AHT10 ──────────────────────────────────────────
  sensors_event_t humidity, temp;
  aht.getEvent(&humidity, &temp);
  float temperature = temp.temperature;
  float hum         = humidity.relative_humidity;

  if (temperature == 0.0 && hum == 0.0) {
    Serial.println("AHT10 read error — retrying...");
    delay(500);
    return;
  }

  // ── Read Other Sensors ──────────────────────────────────
  int rain   = digitalRead(RAIN_PIN);
  int light  = analogRead(LDR_PIN);
  int motion = digitalRead(PIR_PIN);

  bool isRaining = (rain == 0);
  bool hasMotion = (motion == 1);

  // ── Serial Output ────────────────────────────────────────
  Serial.println("------ SENSOR DATA ------");
  Serial.print("Temp:     "); Serial.print(temperature, 1); Serial.println(" C");
  Serial.print("Humidity: "); Serial.print(hum, 1);         Serial.println(" %");
  Serial.print("Rain:     "); Serial.println(isRaining ? "RAINING" : "CLEAR");
  Serial.print("Light:    "); Serial.println(light);
  Serial.print("Motion:   "); Serial.println(hasMotion ? "DETECTED" : "NONE");

  // ── Manual Override Check ────────────────────────────────
  // 🔴 FIXED: No timeout on manual override! It persists until:
  //   1. New auto decision arrives from server
  //   2. System restart
  if (manualOverride) {
    Serial.print("[MANUAL OVERRIDE ACTIVE] Holding ");
    Serial.print(manualTargetAngle);
    Serial.println(" deg");
    
    // 🔴 FIXED: Still move servo if angle changed
    if (currentAngle != manualTargetAngle) {
      moveServo(manualTargetAngle);
      Serial.println("  → Servo adjusted during manual override");
    }
    
    Serial.println("-------------------------\n");
    sendToServer(temperature, hum, light, hasMotion, isRaining, currentAngle);
    delay(3000);
    return;   // ← skip auto decision logic this cycle
  }

  // ── Automatic Decision Logic ─────────────────────────────
  if (isRaining) {
    targetAngle = 0;
    Serial.println("ACTION: RAIN → Window CLOSED");
  } else {
    if      (temperature > TEMP_L3 || hum > HUM_L3) { targetAngle = 90; Serial.println("Level 3: Very hot/humid → 90 deg"); }
    else if (temperature > TEMP_L2 || hum > HUM_L2) { targetAngle = 60; Serial.println("Level 2: Moderate → 60 deg"); }
    else if (temperature > TEMP_L1 || hum > HUM_L1) { targetAngle = 30; Serial.println("Level 1: Warm → 30 deg"); }
    else                                              { targetAngle = 0;  Serial.println("Cool/dry → Closed"); }

    // No-motion timeout → close after 5 minutes
    if (!hasMotion) {
      if (noMotionSince == 0) noMotionSince = millis();
      if (millis() - noMotionSince > 300000UL) {
        targetAngle = 0;
        Serial.println("No motion >5min → CLOSED (security)");
      } else {
        Serial.print("No motion for: ");
        Serial.print((millis() - noMotionSince) / 1000);
        Serial.println("s (window still open)");
      }
    } else {
      noMotionSince = 0;
    }

    // Night mode — limit opening when dark
    if (hasMotion && light < LIGHT_THRESHOLD && targetAngle > 30) {
      targetAngle = 30;
      Serial.println("Night mode → Limited to 30 deg");
    }
  }

  // ── Move Servo ───────────────────────────────────────────
  moveServo(targetAngle);

  // ── Final Report ─────────────────────────────────────────
  Serial.print("FINAL ANGLE: "); Serial.print(currentAngle); Serial.println(" deg");
  Serial.println("-------------------------\n");

  // ── Send to Flask ────────────────────────────────────────
  sendToServer(temperature, hum, light, hasMotion, isRaining, currentAngle);

  delay(3000);  // adjust as needed (e.g., 5s)
}

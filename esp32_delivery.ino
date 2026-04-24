#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include "DHT.h"
#include <ArduinoJson.h>

#define DHTPIN 4
#define DHTTYPE DHT11
#define RAIN_PIN 33  

DHT dht(DHTPIN, DHTTYPE);
Adafruit_MPU6050 mpu;
TinyGPSPlus gps;
HardwareSerial gpsSerial(2);

// --- Configure these for your environment ---
const char* ssid = "Redmi K50i";
const char* password = "laxs2005";
String serverURL = "http://10.66.144.191:5000"; 

// --- Threshold structure ---
struct Threshold {
  String product;
  float temp_min, temp_max;
  float humidity_min, humidity_max;
  float vibration_limit; // in "g" (1.0 = 1g)
  bool rain_allowed;
};

// allow up to 40 products
Threshold thresholds[40];
int thresholdCount = 0;

// --- Alert throttling ---
struct LastAlert {
  String key;
  unsigned long t;
};
LastAlert lastAlerts[100];
int lastAlertCount = 0;
const unsigned long ALERT_THROTTLE_MS = 30UL * 1000UL;

// --- Baseline calibration variables for MPU6050 ---
float baseAx = 0, baseAy = 0, baseAz = 0;
bool baselineSet = false;

// --- Functions for throttling ---
void addOrUpdateLastAlert(const String &key) {
  for (int i=0;i<lastAlertCount;i++){
    if (lastAlerts[i].key == key) {
      lastAlerts[i].t = millis();
      return;
    }
  }
  if (lastAlertCount < (int)(sizeof(lastAlerts)/sizeof(lastAlerts[0]))) {
    lastAlerts[lastAlertCount].key = key;
    lastAlerts[lastAlertCount].t = millis();
    lastAlertCount++;
  }
}
bool canSendAlert(const String &key) {
  for (int i=0;i<lastAlertCount;i++){
    if (lastAlerts[i].key == key) {
      if (millis() - lastAlerts[i].t < ALERT_THROTTLE_MS) return false;
      return true;
    }
  }
  return true;
}

// --- WiFi helpers ---
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("Connecting to WiFi '%s' ...", ssid);
  WiFi.disconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    if (millis() - start > 20000) {
      Serial.println("\nWiFi connect timeout, retrying...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      start = millis();
    }
  }
  Serial.println();
  Serial.print("✅ WiFi Connected. IP: ");
  Serial.println(WiFi.localIP());
}

// --- Forward declarations ---
void fetchThresholds();
bool parseThresholdsJSON(const String &payload);
void sendAlertToServer(const String &product, const String &type, float value, double lat, double lon, float accelG, float temperature, int rainRaw);

// --- MPU6050 Calibration ---
void calibrateMPU() {
  Serial.println("📏 Calibrating MPU6050 (please keep still)...");
  const int samples = 100;
  float sumX = 0, sumY = 0, sumZ = 0;
  for (int i = 0; i < samples; i++) {
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    sumX += a.acceleration.x;
    sumY += a.acceleration.y;
    sumZ += a.acceleration.z;
    delay(50);
  }
  baseAx = sumX / samples;
  baseAy = sumY / samples;
  baseAz = sumZ / samples;
  baselineSet = true;
  Serial.printf("✅ Baseline set: ax=%.3f, ay=%.3f, az=%.3f\n", baseAx, baseAy, baseAz);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n--- ESP32 boot ---");

  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);
  connectWiFi();
  Wire.begin(21, 22);
  dht.begin();

  if (!mpu.begin()) {
    Serial.println("❌ MPU6050 not found! Check wiring and power.");
    while (1) delay(1000);
  }
  Serial.println("✅ MPU6050 initialized.");

  calibrateMPU(); // ✅ baseline at startup

  fetchThresholds();
}

void loop() {
  sensors_event_t a, g, temp_event;
  mpu.getEvent(&a, &g, &temp_event);

  // --- Compute vibration relative to baseline ---
  float deltaX = a.acceleration.x - baseAx;
  float deltaY = a.acceleration.y - baseAy;
  float deltaZ = a.acceleration.z - baseAz;
  float vibration_ms2 = sqrt(deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ);
  float accelG = vibration_ms2 / 9.80665f;

  // --- DHT11 ---
  float tempC = dht.readTemperature();
  float hum = dht.readHumidity();

  // --- Rain sensor ---
  int rainValue = analogRead(RAIN_PIN);
  bool isRaining = (rainValue < 3900); // ✅ tuned for your HW-103 module

  // --- GPS ---
  while (gpsSerial.available()) gps.encode(gpsSerial.read());
  double lat = gps.location.isValid() ? gps.location.lat() : 0.0;
  double lon = gps.location.isValid() ? gps.location.lng() : 0.0;

  // --- Serial output ---
  Serial.println(F("=== Sensor Data ==="));
  Serial.printf("Temp: %.2f C, Hum: %.2f %%\n", isnan(tempC) ? -999.0 : tempC, isnan(hum) ? -999.0 : hum);
  Serial.printf("Rain raw: %d (%s)\n", rainValue, isRaining ? "Wet" : "Dry");
  Serial.printf("Vibration (g): %.3f | Δx=%.2f Δy=%.2f Δz=%.2f\n", accelG, deltaX, deltaY, deltaZ);
  Serial.printf("GPS: %.6f , %.6f\n", lat, lon);
  Serial.println("====================");

  // --- Threshold re-fetch logic ---
  static unsigned long lastMissingFetch = 0;
  if (thresholdCount == 0) {
    if (millis() - lastMissingFetch > 15000) {
      Serial.println("No thresholds loaded -> requesting from server...");
      fetchThresholds();
      lastMissingFetch = millis();
    }
    delay(2500);
    return;
  }

  // --- Apply thresholds ---
  for (int i = 0; i < thresholdCount; ++i) {
    Threshold &tsh = thresholds[i];

    if (!isnan(tempC) && (tempC < tsh.temp_min || tempC > tsh.temp_max)) {
      String key = tsh.product + "|Temperature";
      if (canSendAlert(key)) {
        sendAlertToServer(tsh.product, "temperature_out_of_range", tempC, lat, lon, accelG, tempC, rainValue);
        addOrUpdateLastAlert(key);
      }
    }

    if (!isnan(hum) && (hum < tsh.humidity_min || hum > tsh.humidity_max)) {
      String key = tsh.product + "|Humidity";
      if (canSendAlert(key)) {
        sendAlertToServer(tsh.product, "humidity_out_of_range", hum, lat, lon, accelG, tempC, rainValue);
        addOrUpdateLastAlert(key);
      }
    }

    if (accelG > tsh.vibration_limit) {
      String key = tsh.product + "|Vibration";
      if (canSendAlert(key)) {
        sendAlertToServer(tsh.product, "excess_vibration", accelG, lat, lon, accelG, tempC, rainValue);
        addOrUpdateLastAlert(key);
      }
    }

    if (!tsh.rain_allowed && isRaining) {
      String key = tsh.product + "|Rain";
      if (canSendAlert(key)) {
        sendAlertToServer(tsh.product, "leak_detected", rainValue, lat, lon, accelG, tempC, rainValue);
        addOrUpdateLastAlert(key);
      }
    }
  }

  delay(5000);
}

// ------------------------- Networking / JSON parsing -------------------------

void fetchThresholds() {
  connectWiFi();

  String url = serverURL + "/get_thresholds";
  Serial.println("Fetching thresholds from: " + url);

  const int maxAttempts = 5;  // You don't need 100 attempts
  for (int attempt = 1; attempt <= maxAttempts; attempt++) {
    HTTPClient http;
    http.begin(url);
    http.setTimeout(5000);

    int httpCode = http.GET();
    if (httpCode == 200) {
      String payload = http.getString();
      Serial.printf("GET /get_thresholds -> 200, bytes=%d\n", payload.length());
      Serial.println("Response payload:");
      Serial.println(payload);  // 👈 SEE what Flask actually sends

      bool ok = parseThresholdsJSON(payload);
      http.end();

      if (ok) {
        Serial.printf("✅ Thresholds parsed: %d products loaded\n", thresholdCount);
        return;
      } else {
        Serial.println("⚠️ parseThresholdsJSON failed.");
      }
    } else {
      Serial.printf("GET /get_thresholds returned code: %d\n", httpCode);
    }

    http.end();
    delay(2000);
  }

  Serial.println("❌ Failed to fetch thresholds after attempts.");
}


bool parseThresholdsJSON(const String &payload) {
  const size_t capacity = 18 * 1024;
  StaticJsonDocument<capacity> doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.print(F("deserializeJson() failed: "));
    Serial.println(err.c_str());
    return false;
  }

  if (!doc.is<JsonArray>()) {
    Serial.println(F("Payload is not a JSON array."));
    thresholdCount = 0;
    return false;
  }

  JsonArray arr = doc.as<JsonArray>();
  thresholdCount = 0;
  for (JsonObject obj : arr) {
    if (thresholdCount >= (int)(sizeof(thresholds)/sizeof(thresholds[0]))) break;
    Threshold &t = thresholds[thresholdCount];
    t.product = obj["product"] | "Unknown";
    t.temp_min = obj["temp_min"] | -999.0f;
    t.temp_max = obj["temp_max"] | 999.0f;
    t.humidity_min = obj["humidity_min"] | -999.0f;
    t.humidity_max = obj["humidity_max"] | 999.0f;
    t.vibration_limit = obj["vibration_limit"] | 9.9f;
    t.rain_allowed = obj["rain_allowed"] | true;

    Serial.printf("Parsed: %s temp[%.2f,%.2f] hum[%.2f,%.2f] vib[%.2f] rain_allowed=%d\n",
                  t.product.c_str(), t.temp_min, t.temp_max, t.humidity_min,
                  t.humidity_max, t.vibration_limit, t.rain_allowed ? 1 : 0);
    thresholdCount++;
  }
  return thresholdCount > 0;
}

void sendAlertToServer(const String &product, const String &type, float value,
                       double lat, double lon, float accelG, float temperature, int rainRaw) {
  connectWiFi();

  String url = serverURL + "/alert";
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  StaticJsonDocument<384> doc;
  doc["product"] = product;
  doc["alert_type"] = type;
  doc["value"] = value;
  doc["latitude"] = lat;
  doc["longitude"] = lon;
  doc["accel_g"] = accelG;
  if (!isnan(temperature)) doc["temperature"] = temperature;
  doc["rain_raw"] = rainRaw;

  String out;
  serializeJson(doc, out);

  int code = http.POST(out);
  Serial.printf("🚨 Sent alert -> product:%s type:%s value:%.2f HTTP:%d\n",
                product.c_str(), type.c_str(), value, code);
  if (code != 200 && code != 201)
    Serial.println("⚠️ Server returned code " + String(code));
  http.end();
}

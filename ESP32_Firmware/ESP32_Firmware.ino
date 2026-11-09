/*
 * BioGate ESP32 firmware (ESP32_Firmware.ino)
 * ---------------------------------------------------------------------------
 * Hardware:
 *   - ESP32 dev board
 *   - AS608 / R307 fingerprint sensor on UART2 (RX 16, TX 17)
 *   - 16x2 I2C LCD (default address 0x27)
 *   - Green / Blue / Red status LEDs
 *   - Active buzzer
 *   - Enrollment button on GPIO 4 (INPUT_PULLUP, button to GND)
 *
 * Behaviour:
 *   - Idle LCD: "BioGate Ready"
 *   - Button press: find the next free AS608 slot (1-127), run the two-step
 *     enrollment, store locally, then POST status "ENROLLED" to Django.
 *   - Normal scan: local match -> POST "MEMBER"; no match -> POST "UNKNOWN".
 *
 * Required Arduino libraries:
 *   - Adafruit Fingerprint Sensor Library
 *   - LiquidCrystal I2C
 *   - ArduinoJson (v6 or v7)
 * ---------------------------------------------------------------------------
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Adafruit_Fingerprint.h>
#include <ArduinoJson.h>

// ==========================================
// 1. CONFIGURATION - EDIT THESE VALUES
// ==========================================
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_URL = "https://fingerprint-backend-7032.onrender.com/api/device/event/";
const char* DEVICE_API_KEY = "YOUR_DEVICE_API_KEY";
const char* DEVICE_ID = "ESP32-01";

// ==========================================
// 2. PIN DEFINITIONS
// ==========================================
#define RX_PIN 16
#define TX_PIN 17
#define BUZZER_PIN 13
#define GREEN_LED 25
#define BLUE_LED 26
#define RED_LED 27
#define ENROLL_BUTTON_PIN 4  // Button between GPIO 4 and GND

// ==========================================
// 3. OBJECTS & GLOBAL STATE
// ==========================================
LiquidCrystal_I2C lcd(0x27, 16, 2);
HardwareSerial mySerial(2);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

bool wifiReady = false;

// ==========================================
// 4. SETUP
// ==========================================
void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(ENROLL_BUTTON_PIN, INPUT_PULLUP);
  ledsOff();
  digitalWrite(BUZZER_PIN, LOW);

  lcd.init();
  lcd.backlight();
  showMessage("BioGate boot", "Starting...");

  connectWiFi();

  showMessage("Sensor init", "Please wait...");
  mySerial.begin(57600, SERIAL_8N1, RX_PIN, TX_PIN);
  finger.begin(57600);
  delay(300);

  while (!finger.verifyPassword()) {
    showMessage("Sensor Error", "Check wiring");
    Serial.println("Fingerprint sensor not found. Retrying...");
    delay(2000);
    finger.begin(57600);
  }

  Serial.println("Fingerprint sensor ready.");
  showMessage("Sensor Ready", "");
  delay(1000);
  showIdleScreen();
}

// ==========================================
// 5. MAIN LOOP
// ==========================================
void loop() {
  // Keep the WiFi link healthy without blocking normal scans.
  static unsigned long lastWifiCheck = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiCheck > 30000) {
    lastWifiCheck = millis();
    wifiReady = false;
    connectWiFi();
    showIdleScreen();
  }

  // Enrollment button has priority over normal scanning.
  if (buttonPressed()) {
    startEnrollmentProcess();
    return;
  }

  // Poll for a finger. Only enter the scan flow when an image is captured so
  // the idle LCD does not flicker.
  uint8_t p = finger.getImage();
  if (p == FINGERPRINT_NOFINGER) {
    delay(40);
    return;
  }
  if (p != FINGERPRINT_OK) {
    delay(100);
    return;
  }

  processScan();
  waitForFingerRemoved(4000);
  showIdleScreen();
  delay(150);
}

// ==========================================
// 6. NORMAL SCAN FLOW
// ==========================================
void processScan() {
  ledsOff();
  digitalWrite(BLUE_LED, HIGH);
  showMessage("Scanning...", "");

  uint8_t p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    digitalWrite(BLUE_LED, LOW);
    showMessage("Image error", "Try again");
    delay(1200);
    return;
  }

  p = finger.fingerSearch();

  if (p == FINGERPRINT_OK) {
    const int matchedID = finger.fingerID;

    digitalWrite(BLUE_LED, LOW);
    digitalWrite(GREEN_LED, HIGH);
    beep(1200, 180);

    showMessage("ACCESS GRANTED", "ID: " + String(matchedID));
    sendEventToDjango("MEMBER", matchedID);

    delay(2500);
    digitalWrite(GREEN_LED, LOW);
  } else if (p == FINGERPRINT_NOTFOUND) {
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, HIGH);
    beep(450, 800);

    showMessage("UNKNOWN PERSON", "Access denied");
    sendEventToDjango("UNKNOWN", 0);

    delay(2500);
    digitalWrite(RED_LED, LOW);
  } else {
    digitalWrite(BLUE_LED, LOW);
    showMessage("Scan error", "Try again");
    delay(1200);
  }
}

// ==========================================
// 7. ENROLLMENT FLOW
// ==========================================
void startEnrollmentProcess() {
  ledsOff();
  digitalWrite(BLUE_LED, HIGH);
  showMessage("Finding slot...", "");

  const int nextId = findNextFreeSlot();

  if (nextId < 0) {
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, HIGH);
    beep(400, 800);
    showMessage("Memory full", "No free slot");
    delay(2500);
    digitalWrite(RED_LED, LOW);
    showIdleScreen();
    return;
  }

  Serial.print("Enrolling into AS608 slot ");
  Serial.println(nextId);

  const uint8_t result = enrollFingerprint((uint8_t)nextId);

  if (result == FINGERPRINT_OK) {
    showMessage("Syncing...", "Slot " + String(nextId));
    const bool synced = sendEventToDjango("ENROLLED", nextId);

    if (synced) {
      digitalWrite(BLUE_LED, LOW);
      digitalWrite(GREEN_LED, HIGH);
      beep(1800, 350);
      showMessage("Enrolled OK!", "Cloud synced");
    } else {
      digitalWrite(BLUE_LED, LOW);
      digitalWrite(RED_LED, HIGH);
      beep(500, 500);
      showMessage("Enrolled OK!", "Cloud sync failed");
    }

    delay(2500);
    ledsOff();
    waitForFingerRemoved(3000);
  } else {
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, HIGH);
    beep(400, 800);
    showMessage("Enroll failed", "Try again");
    delay(2500);
    digitalWrite(RED_LED, LOW);
    waitForFingerRemoved(2000);
  }

  showIdleScreen();
}

int findNextFreeSlot() {
  for (int id = 1; id <= 127; id++) {
    const uint8_t result = finger.loadModel(id);
    if (result == FINGERPRINT_NOTFOUND) {
      return id;
    }
    delay(2);
  }
  return -1;
}

uint8_t enrollFingerprint(uint8_t id) {
  lcd.clear();
  lcdLine(0, "Enroll slot " + String(id));
  lcdLine(1, "Place finger");

  // ----- Step 1: first image -----
  uint8_t p = FINGERPRINT_NOFINGER;
  unsigned long start = millis();
  while (p != FINGERPRINT_OK && millis() - start < 20000) {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER) {
      delay(50);
    } else if (p != FINGERPRINT_OK) {
      delay(80);
    }
  }
  if (p != FINGERPRINT_OK) {
    showMessage("Enroll timeout", "Try again");
    return p;
  }

  p = finger.image2Tz(1);
  if (p != FINGERPRINT_OK) {
    showMessage("Image error", "Try again");
    return p;
  }

  // ----- Step 2: remove finger -----
  showMessage("Remove finger", "");
  beep(1200, 120);
  delay(1000);
  waitForFingerRemoved(8000);

  // ----- Step 3: second image -----
  showMessage("Place finger", "again");
  p = FINGERPRINT_NOFINGER;
  start = millis();
  while (p != FINGERPRINT_OK && millis() - start < 20000) {
    p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER) {
      delay(50);
    } else if (p != FINGERPRINT_OK) {
      delay(80);
    }
  }
  if (p != FINGERPRINT_OK) {
    showMessage("Enroll timeout", "Try again");
    return p;
  }

  p = finger.image2Tz(2);
  if (p != FINGERPRINT_OK) {
    showMessage("Image error", "Try again");
    return p;
  }

  // ----- Step 4: combine and store -----
  showMessage("Creating model", "...");
  p = finger.createModel();

  if (p == FINGERPRINT_ENROLLMISMATCH) {
    showMessage("Fingers differ", "Try again");
    return p;
  }
  if (p != FINGERPRINT_OK) {
    showMessage("Model failed", "Try again");
    return p;
  }

  p = finger.storeModel(id);
  if (p == FINGERPRINT_OK) {
    showMessage("Enrolled OK!", "Slot " + String(id));
    beep(1800, 350);
    return FINGERPRINT_OK;
  }

  showMessage("Store failed", "Slot " + String(id));
  return p;
}

// ==========================================
// 8. DJANGO SYNC
// ==========================================
bool sendEventToDjango(const String& status, int memberId) {
  if (WiFi.status() != WL_CONNECTED) {
    if (!connectWiFi()) {
      Serial.println("Cannot send event: WiFi is offline.");
      return false;
    }
  }

  WiFiClientSecure client;
  // Render serves a valid certificate. setInsecure() avoids needing to embed
  // the CA bundle on the ESP32; traffic is still encrypted.
  client.setInsecure();

  HTTPClient http;
  http.setTimeout(12000);
  if (!http.begin(client, API_URL)) {
    Serial.println("HTTP begin failed.");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-API-Key", DEVICE_API_KEY);

#if defined(ARDUINOJSON_VERSION_MAJOR) && ARDUINOJSON_VERSION_MAJOR >= 7
  JsonDocument doc;
#else
  StaticJsonDocument<256> doc;
#endif

  doc["device_id"] = DEVICE_ID;
  doc["status"] = status;
  doc["member_id"] = memberId;

  String payload;
  serializeJson(doc, payload);

  const int httpCode = http.POST(payload);
  const String response = http.getString();
  http.end();

  Serial.print("POST ");
  Serial.print(status);
  Serial.print(" -> HTTP ");
  Serial.print(httpCode);
  Serial.print(" ");
  Serial.println(response);

  return httpCode >= 200 && httpCode < 300;
}

// ==========================================
// 9. HELPERS
// ==========================================
bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiReady = true;
    return true;
  }

  showMessage("Connecting WiFi", "Please wait...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiReady = true;
    Serial.print("WiFi connected: ");
    Serial.println(WiFi.localIP());
    showMessage("WiFi Connected", WiFi.localIP().toString());
    delay(800);
    return true;
  }

  wifiReady = false;
  Serial.println("WiFi connection failed.");
  showMessage("WiFi offline", "Check network");
  delay(1200);
  return false;
}

bool buttonPressed() {
  if (digitalRead(ENROLL_BUTTON_PIN) != LOW) {
    return false;
  }

  delay(40);  // debounce
  if (digitalRead(ENROLL_BUTTON_PIN) != LOW) {
    return false;
  }

  // Wait for release so one press triggers exactly one enrollment.
  const unsigned long start = millis();
  while (digitalRead(ENROLL_BUTTON_PIN) == LOW && millis() - start < 3000) {
    delay(20);
  }
  return true;
}

void waitForFingerRemoved(unsigned long timeoutMs) {
  const unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    if (finger.getImage() == FINGERPRINT_NOFINGER) {
      return;
    }
    delay(80);
  }
}

void showIdleScreen() {
  lcd.clear();
  lcdLine(0, "BioGate Ready");
  lcdLine(1, wifiReady ? "Place finger" : "WiFi offline");
}

void showMessage(const String& line1, const String& line2) {
  lcd.clear();
  lcdLine(0, line1);
  if (line2.length() > 0) {
    lcdLine(1, line2);
  }
}

void lcdLine(uint8_t row, const String& text) {
  lcd.setCursor(0, row);
  String padded = text;
  while (padded.length() < 16) {
    padded += ' ';
  }
  lcd.print(padded.substring(0, 16));
}

void ledsOff() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(BLUE_LED, LOW);
  digitalWrite(RED_LED, LOW);
}

void beep(unsigned int frequency, unsigned long durationMs) {
  tone(BUZZER_PIN, frequency, durationMs);
}

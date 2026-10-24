/* Optional ESP32 + HC-SR04 capture endpoint. No actuator output is enabled.
   HC-SR04 ECHO is 5V: use a divider/level shifter before ESP32 GPIO.
   This firmware is provided for bench testing and has not been flashed here. */
#include <WiFi.h>
#include <WebServer.h>
#include <esp_system.h>
#include "wifi_secrets.h"

constexpr int TRIG_PIN = 22;
constexpr int ECHO_PIN = 23;
WebServer server(80);
uint32_t sequence = 0;
uint32_t bootId;

void reading() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  int distance = int(duration * 0.343f / 2.0f);
  bool valid = duration > 0 && distance >= 20 && distance <= 4000;
  String body = "{\"boot_id\":\"" + String(bootId, HEX) + "\",\"sequence\":" + String(sequence++)
    + ",\"uptime_ms\":" + String(millis()) + ",\"valid\":" + (valid ? "true" : "false")
    + ",\"distance_mm\":" + String(distance) + "}";
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", body);
}

void setup() {
  Serial.begin(115200);
  bootId = esp_random();
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  WiFi.begin(CB_WIFI_SSID, CB_WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 20000) delay(100);
  server.on("/reading", HTTP_GET, reading);
  server.begin();
  Serial.print("CausalBench sensor IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  static unsigned long lastRetry = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastRetry >= 5000) {
    lastRetry = millis();
    WiFi.reconnect();
  }
  server.handleClient();
}

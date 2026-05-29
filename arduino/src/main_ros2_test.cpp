/*
  Flashbot ROS 2 serial smoke-test firmware.

  This file is intentionally disabled by default so it can live beside the
  existing src/main.cpp without creating duplicate Arduino setup()/loop()
  functions during normal PlatformIO builds.

  To flash this test without permanently editing the project, temporarily make
  this the active PlatformIO main source, or compile with build flags/source
  filters that define FLASHBOT_ROS2_SERIAL_TEST and exclude the existing
  src/main.cpp.
*/

#ifdef FLASHBOT_ROS2_SERIAL_TEST

#include <Arduino.h>

static const unsigned long HEARTBEAT_PERIOD_MS = 1000;
static const uint8_t LED_PIN = 13;

static unsigned long last_heartbeat_ms = 0;
static String input_line;

static void publish_event(const String& name) {
  Serial.print("EVT,");
  Serial.println(name);
}

static void handle_command(const String& command) {
  if (command == "CMD,HELLO") {
    publish_event("READY");
  } else if (command == "CMD,LED_ON") {
    digitalWrite(LED_PIN, HIGH);
    publish_event("LED_ON");
  } else if (command == "CMD,LED_OFF") {
    digitalWrite(LED_PIN, LOW);
    publish_event("LED_OFF");
  } else {
    Serial.print("EVT,CMD_RECEIVED,");
    Serial.println(command);
  }
}

static void read_serial_commands() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      input_line.trim();
      if (input_line.length() > 0) {
        handle_command(input_line);
      }
      input_line = "";
      continue;
    }

    input_line += c;
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  while (!Serial && millis() < 3000) {
    delay(10);
  }

  publish_event("BOOT");
}

void loop() {
  read_serial_commands();

  unsigned long now_ms = millis();
  if (now_ms - last_heartbeat_ms >= HEARTBEAT_PERIOD_MS) {
    last_heartbeat_ms = now_ms;
    publish_event("HEARTBEAT");
  }
}

#endif  // FLASHBOT_ROS2_SERIAL_TEST

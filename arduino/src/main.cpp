#include <Arduino.h>
#include <SCServo.h>

#include "inputs.h"
#include "fsm.h"
#include "servo.h"
// #include "leds.h"
#include "neo_pxl.h"

static bool DEBUG_WITHOUT_PI = false;

void setup() {
  Serial.begin(115200);
  Inputs::begin();
  Fsm::begin(DEBUG_WITHOUT_PI);
  // Servo::begin();
  NeoPixel::begin();
  Serial.println("Setup Complete");
}

void loop() {
  Events ev = Inputs::poll();

  // if (ev.hall_left) Serial.println("LEFT HALL");
  // if (ev.hall_right) Serial.println("RIGHT HALL");
  // if (ev.limit_bumped_left) Serial.println("LEFT BUMPED");
  // if (ev.limit_released_left) Serial.println("LEFT RELEASED");
  // if (ev.limit_bumped_right) Serial.println("RIGHT BUMPED");
  // if (ev.limit_released_right) Serial.println("RIGHT RELEASED");
  // if (ev.hall_left) Serial.println("LEFT_HALL");
  // if (ev.hall_right) Serial.println("RIGHT_HALL");

  if (ev.hall_left || ev.hall_right) Servo::sync_servos(ev.hall_left, ev.hall_right, micros());

  Fsm::step(ev);
}
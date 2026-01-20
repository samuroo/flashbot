#include <Arduino.h>
#include "inputs.h"

// Pins 
static const uint8_t HALL_PIN_LEFT  = 2;
static const uint8_t HALL_PIN_RIGHT  = 3;
static const uint8_t LIMIT_PIN_LEFT = 7;
static const uint8_t LIMIT_PIN_RIGHT = 8;

// Hall
static volatile bool hall_event_left = false;
static volatile uint32_t hall_last_us_left = 0;
static volatile bool hall_event_right = false;
static volatile uint32_t hall_last_us_right = 0;

// Hall ISR 
void hallLeftISR() {
  uint32_t now = micros();
  if ((uint32_t)(now - hall_last_us_left) > 2000) {
    hall_event_left = true;
    hall_last_us_left = now;
  }
}
void hallRightISR() {
  uint32_t now = micros();
  if ((uint32_t)(now - hall_last_us_right) > 2000) {
    hall_event_right = true;
    hall_last_us_right = now;
  }
}

// Limit debounce 
static const uint32_t DEBOUNCE_MS = 50;

static bool limit_state_left = HIGH;
static bool limit_last_left = HIGH;
static uint32_t limit_last_ms_left = 0;
static bool limit_state_right = HIGH;
static bool limit_last_right = HIGH;
static uint32_t limit_last_ms_right = 0;

namespace Inputs {

void begin() {
  // Hall
  pinMode(HALL_PIN_LEFT, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_PIN_LEFT), hallLeftISR, FALLING);
  pinMode(HALL_PIN_RIGHT, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_PIN_RIGHT), hallRightISR, FALLING);

  // Limit
  pinMode(LIMIT_PIN_LEFT, INPUT_PULLUP);
  limit_state_left = digitalRead(LIMIT_PIN_LEFT);
  limit_last_left = limit_state_left;
  limit_last_ms_left = millis();

  pinMode(LIMIT_PIN_RIGHT, INPUT_PULLUP);
  limit_state_right = digitalRead(LIMIT_PIN_RIGHT);
  limit_last_right = limit_state_right;
  limit_last_ms_right = millis();

  Serial.begin(115200);
}

Events poll() {
  Events ev;

  // Hall event
  noInterrupts();
  bool hall_left = hall_event_left;
  hall_event_left = false;
  interrupts();
  if (hall_left) ev.hall_left = true;
  noInterrupts();
  bool hall_right = hall_event_right;
  hall_event_right = false;
  interrupts();
  if (hall_right) ev.hall_right = true;

  // Limit event
  bool limit_reading_left = digitalRead(LIMIT_PIN_LEFT);
  uint32_t now_ms_left = millis();
  if (limit_reading_left != limit_last_left) {
    limit_last_left = limit_reading_left;
    limit_last_ms_left = now_ms_left;
  }
  if ((uint32_t)(now_ms_left - limit_last_ms_left) >= DEBOUNCE_MS &&
      limit_reading_left != limit_state_left) {
    limit_state_left = limit_reading_left;
    if (limit_last_left == LOW)
      ev.limit_bumped_left = true;
    else
      ev.limit_released_left = true;
  }

  bool limit_reading_right = digitalRead(LIMIT_PIN_RIGHT);
  uint32_t now_ms_right = millis();
  if (limit_reading_right != limit_last_right) {
    limit_last_right = limit_reading_right;
    limit_last_ms_right = now_ms_right;
  }
  if ((uint32_t)(now_ms_right - limit_last_ms_right) >= DEBOUNCE_MS &&
      limit_reading_right != limit_state_right) {
    limit_state_right = limit_reading_right;
    if (limit_last_right == LOW)
      ev.limit_bumped_right = true;
    else
      ev.limit_released_right = true;
  }

  // Return
  return ev;
}

} // namespace Inputs

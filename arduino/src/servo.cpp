#include <math.h>
#include "servo.h"

static const uint8_t RX_PIN = 0;
static const uint8_t TX_PIN = 1;

static const uint8_t LEFT_ID = 1;
static const uint8_t RIGHT_ID = 0;
static const uint8_t LEFT_WING_ID = 3;
static const uint8_t RIGHT_WING_ID = 2;

// TEMP POSITIONS & SPEED (3/2/2026)
static const uint16_t RIGHT_WING_INIT_POS = 50;
static const uint16_t RIGHT_WING_OPEN_POS = 350;
static const uint16_t LEFT_WING_INIT_POS = 1000;
static const uint16_t LEFT_WING_OPEN_POS = 700; 
// static const uint16_t WING_OPEN_POS = 500;
static const uint16_t WING_SPEED = 1000;

// static const int16_t speed = 400;

// hall sync servos
static float base_speed = 400;
static float speed_left = base_speed;
static float speed_right = base_speed;

static uint32_t last_left_us  = 0;
static uint32_t last_right_us = 0;
static uint32_t period_left_us  = 0;
static uint32_t period_right_us = 0;

static const float KP = 0.3f;          // tune
static const float MAX_FRAC = 0.25f;   // clamp correction +/-25%


SCSCL sc;

static float clampf(float x)
{
  if (x < -MAX_FRAC) {
    return -MAX_FRAC;
  }
  if (x > MAX_FRAC) {
    return MAX_FRAC;
  }

  return x;
}

static float wrap_half(float e){
  // wrap to [-0.5, 0.5]
  if (e >  0.5f) e -= 1.0f;
  if (e < -0.5f) e += 1.0f;
  return e;
}

static void sync_reset() {
  last_left_us = 0;
  last_right_us = 0;
  period_left_us = 0;
  period_right_us = 0;
}

namespace Servo {

  void begin() {
    Serial1.begin(1000000);
    sc.pSerial = &Serial1;

    // legs
    sc.PWMMode(LEFT_ID);
    sc.EnableTorque(LEFT_ID, 1);
    sc.PWMMode(RIGHT_ID);
    sc.EnableTorque(RIGHT_ID, 1);
    stop();

    // wings -> ID, POSITION, MOVE DELAY, SPEED (Max 1500)
    sc.WritePos(LEFT_WING_ID, LEFT_WING_INIT_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, RIGHT_WING_INIT_POS, 0, WING_SPEED);
    
    delay(1000);
  }

  // LEG MOVEMENTS
  void forward() {
    sync_reset();
    sc.WritePWM(LEFT_ID, (int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, (int16_t)roundf(speed_right));
  }

  void stop() {
    sync_reset();
    sc.WritePWM(LEFT_ID, (int16_t)0);
    sc.WritePWM(RIGHT_ID, (int16_t)0);
  }

  void backward() {
    sync_reset();
    sc.WritePWM(LEFT_ID, -(int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, -(int16_t)roundf(speed_right));
  }

  void turn_right() {
    sync_reset();
    sc.WritePWM(LEFT_ID, (int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, -(int16_t)roundf(speed_right));
  }

  void turn_left() {
    sync_reset();
    sc.WritePWM(LEFT_ID, -(int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, (int16_t)roundf(speed_right));
  }

  // WINGS
  void wing_open() {
    sc.WritePos(LEFT_WING_ID, LEFT_WING_OPEN_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, RIGHT_WING_OPEN_POS, 0, WING_SPEED);
  }

  void wing_closed() {
    sc.WritePos(LEFT_WING_ID, LEFT_WING_INIT_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, RIGHT_WING_INIT_POS, 0, WING_SPEED); 
  }


  void sync_servos(bool left_event, bool right_event, uint32_t now_us) {
    // default to base speed unless we have enough timing info
    speed_left  = base_speed;
    speed_right = base_speed;

    // update timestamps / periods
    if (left_event) {
      if (last_left_us)  period_left_us  = now_us - last_left_us;
      last_left_us = now_us;
    }
    if (right_event) {
      if (last_right_us) period_right_us = now_us - last_right_us;
      last_right_us = now_us;
    }

    // need both legs to have a valid last time + period
    if (!last_left_us || !last_right_us) return;
    if (!period_left_us || !period_right_us) return;

    // If LEFT just ticked: RIGHT should be at half-cycle (anti-phase)
    if (left_event) {
      float frac_r = (float)(now_us - last_right_us) / (float)period_right_us; // 0..1ish
      frac_r -= floorf(frac_r);
      float err = wrap_half(frac_r - 0.5f); // want 0.5 -> 180 phase

      float corr = clampf(KP * err);
      // adjust RIGHT around base
      speed_right = base_speed * (1.0f - corr);
    }

    // If RIGHT just ticked: LEFT should be at half-cycle
    if (right_event) {
      float frac_l = (float)(now_us - last_left_us)  / (float)period_left_us;
      frac_l -= floorf(frac_l);
      float err = wrap_half(frac_l - 0.5f);

      float corr = clampf(KP * err);
      speed_left = base_speed * (1.0f - corr); // TURN to + corr if seems to go wrong way
    }
  }

} // name space



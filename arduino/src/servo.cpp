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
static float base_speed = 500;
static float speed_left = base_speed;
static float speed_right = base_speed;

static uint32_t last_left_us  = 0;
static uint32_t last_right_us = 0;
static uint32_t period_left_us  = 0;
static uint32_t period_right_us = 0;

static const float KP = 0.1f;          // tune
static const float MAX_FRAC = 0.25f;   // clamp correction +/-25%

static Servo::DriveMode current_mode = Servo::DriveMode::STOP;

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

static float clamp_frac(float x) {
  if (x < -MAX_FRAC) return -MAX_FRAC;
  if (x >  MAX_FRAC) return  MAX_FRAC;
  return x;
}

static float clamp_speed(float s) {
  const float MIN_S = 0.7f * base_speed;  // adjust if needed
  const float MAX_S = 1.3f * base_speed;
  if (s < MIN_S) return MIN_S;
  if (s > MAX_S) return MAX_S;
  return s;
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
  speed_left  = base_speed;
  speed_right = base_speed;
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
    if (current_mode != DriveMode::BACKWARD) sync_reset();
    setDriveMode(DriveMode::FORWARD);
    sc.WritePWM(LEFT_ID, (int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, -(int16_t)roundf(speed_right));
  }

  void stop() {
    setDriveMode(DriveMode::STOP);
    sc.WritePWM(LEFT_ID, (int16_t)0);
    sc.WritePWM(RIGHT_ID, (int16_t)0);
  }

  void backward() {
    if (current_mode != DriveMode::FORWARD) sync_reset();
    setDriveMode(DriveMode::BACKWARD);
    sc.WritePWM(LEFT_ID, -(int16_t)roundf(speed_left));
    sc.WritePWM(RIGHT_ID, (int16_t)roundf(speed_right));
  }

  void turn_right() {
    setDriveMode(DriveMode::STOP);
    sc.WritePWM(LEFT_ID, (int16_t)roundf(base_speed));
    sc.WritePWM(RIGHT_ID, (int16_t)roundf(base_speed));
  }

  void turn_left() {
    setDriveMode(DriveMode::STOP);
    sc.WritePWM(LEFT_ID, -(int16_t)roundf(base_speed));
    sc.WritePWM(RIGHT_ID, -(int16_t)roundf(base_speed));
  }

  void stop_left() {
    sc.WritePWM(LEFT_ID,  (int16_t)0);
  }
  void stop_right() {
    sc.WritePWM(RIGHT_ID,  (int16_t)0);
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

  void setDriveMode(DriveMode mode){
    current_mode = mode;
  }

  void sync_servos(bool left_event, bool right_event, uint32_t now_us) {
    // default to base speed unless we have enough timing info
    // speed_left  = base_speed;
    // speed_right = base_speed;

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
      float frac_r = (float)(now_us - last_right_us) / (float)period_right_us;
      frac_r -= floorf(frac_r);
      float err = wrap_half(frac_r - 0.0f);

      Serial.print(" frac_r=");
      Serial.print(frac_r, 3);

      float corr = clamp_frac(KP * err);

      speed_right += base_speed * corr;
      speed_left  -= base_speed * corr;

      speed_right = clamp_speed(speed_right);
      speed_left  = clamp_speed(speed_left);
    }


    // If RIGHT just ticked: LEFT should be at half-cycle
    // if (right_event) {
    //   float frac_l = (float)(now_us - last_left_us) / (float)period_left_us;
    //   frac_l -= floorf(frac_l);
    //   float err = wrap_half(frac_l - 0.0f);

    //   Serial.print(" frac_l=");
    //   Serial.print(frac_l, 3);

    //   float corr = clamp_frac(KP * err);

    //   speed_left  += base_speed * corr;
    //   speed_right -= base_speed * corr;

    //   speed_left  = clamp_speed(speed_left);
    //   speed_right = clamp_speed(speed_right);
    // }


    if (current_mode == DriveMode::FORWARD) {
      Serial.println("GOING FORWARD IN SYNC");
      sc.WritePWM(LEFT_ID,  (int16_t)roundf(speed_left));
      sc.WritePWM(RIGHT_ID, -(int16_t)roundf(speed_right));
    }
    else if (current_mode == DriveMode::BACKWARD) {
      Serial.println("GOING BACKWARD IN SYNC");
      sc.WritePWM(LEFT_ID,  -(int16_t)roundf(speed_left));
      sc.WritePWM(RIGHT_ID,  (int16_t)roundf(speed_right));
    }

    Serial.print("Speed left: ");
    Serial.println(speed_left);
    Serial.print("Speed right: ");
    Serial.println(speed_right);
  }

} // name space



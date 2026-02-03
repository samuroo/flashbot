#include "servo.h"

static const uint8_t RX_PIN = 0;
static const uint8_t TX_PIN = 1;

static const uint8_t LEFT_ID = 1;
static const uint8_t RIGHT_ID = 0;
static const uint8_t LEFT_WING_ID = 3;
static const uint8_t RIGHT_WING_ID = 2;

// TEMP POSITIONS & SPEED (3/2/2026)
static const uint16_t WING_INIT_POS = 0;
static const uint16_t WING_OPEN_POS = 500;
static const uint16_t WING_SPEED = 1000;

SCSCL sc;

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
    sc.WritePos(LEFT_WING_ID, WING_INIT_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, WING_INIT_POS, 0, WING_SPEED);
    
    delay(1000);
  }

  // LEG MOVEMENTS
  void forward(int16_t speed) {
    sc.WritePWM(LEFT_ID, speed);
    sc.WritePWM(RIGHT_ID, speed);
  }

  void stop() {
    sc.WritePWM(LEFT_ID, (int16_t)0);
    sc.WritePWM(RIGHT_ID, (int16_t)0);
  }

  void backward(int16_t speed) {
    sc.WritePWM(LEFT_ID, -speed);
    sc.WritePWM(RIGHT_ID, -speed);
  }

  void turn_right(int16_t speed) {
    sc.WritePWM(LEFT_ID, speed);
    sc.WritePWM(RIGHT_ID, -speed);
  }

  void turn_left(int16_t speed) {
    sc.WritePWM(LEFT_ID, -speed);
    sc.WritePWM(RIGHT_ID, speed);
  }

  // WINGS
  void wing_open() {
    sc.WritePos(LEFT_WING_ID, WING_INIT_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, WING_OPEN_POS, 0, WING_SPEED);
  }

  void wing_closed() {
    sc.WritePos(LEFT_WING_ID, WING_INIT_POS, 0, WING_SPEED);
    sc.WritePos(RIGHT_WING_ID, WING_INIT_POS, 0, WING_SPEED); 
  }

} // name space
#include "servo.h"

static const uint8_t RX_PIN = 0;
static const uint8_t TX_PIN = 1;

static const uint8_t LEFT_ID = 0;

SCSCL sc;

namespace Servo {

  void begin() {
    Serial1.begin(1000000);
    sc.pSerial = &Serial1;

    sc.PWMMode(LEFT_ID);
    sc.EnableTorque(LEFT_ID, 1);
    delay(1000);
    
    // turn off to start
    sc.WritePWM(LEFT_ID, (int16_t)0);
  }

  void forward() {
    sc.WritePWM(LEFT_ID, (int16_t)400);
  }

  void stop() {
    sc.WritePWM(LEFT_ID, (int16_t)0);
  }

  void backward() {
    sc.WritePWM(LEFT_ID, (int16_t)-400);
  }

  void turn_right() {
    sc.WritePWM(LEFT_ID, (int16_t)400);
  }

  void turn_left() {
    sc.WritePWM(LEFT_ID, (int16_t)400);
  }

} // name space
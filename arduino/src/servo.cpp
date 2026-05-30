#include "servo.h"

static const uint8_t LEFT_SERVO_ID = 1;
static const uint8_t RIGHT_SERVO_ID = 0;
static const uint8_t LEFT_WING_ID = 3;
static const uint8_t RIGHT_WING_ID = 2;

static const int16_t MAX_WALK_SPEED = 1500;
static const uint16_t MAX_WING_SPEED = 1500;

SCSCL sc;
static bool servo_bus_ready = false;

#if defined(HAVE_HWSERIAL1) || defined(UBRR1H)
  #define FLASHBOT_HAS_SERVO_SERIAL 1
#endif

static int16_t clampWalkSpeed(int value) {
  if (value > MAX_WALK_SPEED) {
    return MAX_WALK_SPEED;
  }
  if (value < -MAX_WALK_SPEED) {
    return -MAX_WALK_SPEED;
  }
  return static_cast<int16_t>(value);
}

static uint16_t clampWingSpeed(int value) {
  if (value < 0) {
    return 0;
  }
  if (value > MAX_WING_SPEED) {
    return MAX_WING_SPEED;
  }
  return static_cast<uint16_t>(value);
}

namespace Servo {

void begin() {
#if defined(FLASHBOT_HAS_SERVO_SERIAL)
  Serial1.begin(1000000);
  sc.pSerial = &Serial1;
  servo_bus_ready = true;

  sc.PWMMode(LEFT_SERVO_ID);
  sc.EnableTorque(LEFT_SERVO_ID, 1);
  sc.PWMMode(RIGHT_SERVO_ID);
  sc.EnableTorque(RIGHT_SERVO_ID, 1);

  setLeftSpeed(0);
  setRightSpeed(0);
#else
  servo_bus_ready = false;
#endif
}

void setLeftSpeed(int16_t speed) {
  if (!servo_bus_ready) {
    return;
  }
  sc.WritePWM(LEFT_SERVO_ID, clampWalkSpeed(speed));
}

void setRightSpeed(int16_t speed) {
  if (!servo_bus_ready) {
    return;
  }
  sc.WritePWM(RIGHT_SERVO_ID, clampWalkSpeed(speed));
}

void setLeftWing(uint16_t position, uint16_t speed) {
  if (!servo_bus_ready) {
    return;
  }
  sc.WritePos(LEFT_WING_ID, position, 0, clampWingSpeed(speed));
}

void setRightWing(uint16_t position, uint16_t speed) {
  if (!servo_bus_ready) {
    return;
  }
  sc.WritePos(RIGHT_WING_ID, position, 0, clampWingSpeed(speed));
}

}  // namespace Servo

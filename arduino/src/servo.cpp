#include "servo.h"

static const uint8_t LEFT_SERVO_ID = 1;
static const uint8_t RIGHT_SERVO_ID = 0;
static const uint8_t LEFT_WING_ID = 3;
static const uint8_t RIGHT_WING_ID = 2;

static const int16_t MAX_WALK_SPEED = 1500;
static const uint16_t MAX_WING_SPEED = 1500;
static const int16_t DRIVE_SPEED = 500;
static const int16_t ALIGN_SPEED = 250;
static const int16_t MAX_SYNC_CORRECTION = 125;
static const int32_t SYNC_US_PER_SPEED_STEP = 100;
static const uint8_t TURN_HALL_TARGET = 3;

enum class DriveMode {
  STOP,
  MANUAL,
  ALIGN_FORWARD,
  FORWARD,
  BACKWARD,
  TURN_LEFT,
  TURN_RIGHT,
};

SCSCL sc;
static bool servo_bus_ready = false;
static DriveMode drive_mode = DriveMode::STOP;
static int16_t left_drive_speed = DRIVE_SPEED;
static int16_t right_drive_speed = DRIVE_SPEED;
static uint32_t last_hall_left_us = 0;
static uint32_t last_hall_right_us = 0;
static bool new_hall_left = false;
static bool new_hall_right = false;
static bool align_left_done = false;
static bool align_right_done = false;
static bool aligned_event = false;
static uint8_t turn_left_count = 0;
static uint8_t turn_right_count = 0;
static bool turn_left_done = false;
static bool turn_right_done = false;
static bool turn_done_event = false;

static void reportServoStatus(uint8_t id, const String& status) {
  Serial.print("EVT,servo,id=");
  Serial.print(id);
  Serial.print(",");
  Serial.println(status);
}

static bool pingServo(uint8_t id) {
  bool found = sc.Ping(id) == id;
  reportServoStatus(id, found ? "ping=ok" : "ping=failed");
  return found;
}

static bool configureLegServo(uint8_t id, bool found) {
  if (!found) {
    reportServoStatus(id, "status=unavailable");
    return false;
  }

  int torque_off_result = sc.EnableTorque(id, 0);
  if (torque_off_result != 1) {
    reportServoStatus(id, "torque_off=failed");
    return false;
  }
  delay(20);

  bool configuration_ok = true;
  int mode_before = sc.ReadMode(id);
  reportServoStatus(id, String("mode_before=") + mode_before);
  if (mode_before < 0) {
    sc.EnableTorque(id, 1);
    reportServoStatus(id, "status=mode_read_failed");
    return false;
  }

  if (mode_before != 3) {
    int unlock_result = sc.unLockEprom(id);
    int pwm_result = unlock_result == 1 ? sc.PWMMode(id) : 0;
    int lock_result = unlock_result == 1 ? sc.LockEprom(id) : 0;

    if (unlock_result != 1) {
      configuration_ok = false;
      reportServoStatus(id, "eprom_unlock=failed");
    } else if (pwm_result != 1) {
      configuration_ok = false;
      reportServoStatus(id, "pwm_mode_write=failed");
    } else if (lock_result != 1) {
      configuration_ok = false;
      reportServoStatus(id, "eprom_lock=failed");
    } else {
      reportServoStatus(id, "pwm_mode_write=ok");
    }
    delay(50);
  } else {
    reportServoStatus(id, "pwm_mode_write=skipped");
  }

  int torque_on_result = sc.EnableTorque(id, 1);
  if (torque_on_result != 1) {
    reportServoStatus(id, "torque_on=failed");
    return false;
  }
  delay(20);

  int mode_after = sc.ReadMode(id);
  reportServoStatus(id, String("mode_after=") + mode_after);
  bool ready = mode_after == 3 && configuration_ok;
  if (ready) {
    reportServoStatus(id, "status=ready");
  } else if (mode_after != 3) {
    reportServoStatus(id, "status=wrong_mode");
  } else {
    reportServoStatus(id, "status=configuration_failed");
  }
  return ready;
}

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

static void writeLeftSpeed(int16_t speed) {
  if (servo_bus_ready) {
    sc.WritePWM(LEFT_SERVO_ID, clampWalkSpeed(speed));
  }
}

static void writeRightSpeed(int16_t speed) {
  if (servo_bus_ready) {
    sc.WritePWM(RIGHT_SERVO_ID, clampWalkSpeed(speed));
  }
}

static void resetHallSync() {
  left_drive_speed = DRIVE_SPEED;
  right_drive_speed = DRIVE_SPEED;
  last_hall_left_us = 0;
  last_hall_right_us = 0;
  new_hall_left = false;
  new_hall_right = false;
}

static void applyWalkingSpeeds() {
  if (drive_mode == DriveMode::FORWARD) {
    writeLeftSpeed(left_drive_speed);
    writeRightSpeed(-right_drive_speed);
  } else if (drive_mode == DriveMode::BACKWARD) {
    writeLeftSpeed(-left_drive_speed);
    writeRightSpeed(right_drive_speed);
  }
}

static void updateWalkingSync() {
  if (!new_hall_left || !new_hall_right) {
    return;
  }

  int32_t phase_error_us = static_cast<int32_t>(
      last_hall_left_us - last_hall_right_us
  );
  int32_t correction = phase_error_us / SYNC_US_PER_SPEED_STEP;
  if (correction > MAX_SYNC_CORRECTION) {
    correction = MAX_SYNC_CORRECTION;
  } else if (correction < -MAX_SYNC_CORRECTION) {
    correction = -MAX_SYNC_CORRECTION;
  }

  // A positive error means the left magnet arrived later, so speed up left.
  left_drive_speed = DRIVE_SPEED + correction;
  right_drive_speed = DRIVE_SPEED - correction;
  applyWalkingSpeeds();

  new_hall_left = false;
  new_hall_right = false;
}

namespace Servo {

void reportStatus() {
  bool servo_found[4];
  for (uint8_t id = 0; id < 4; id++) {
    servo_found[id] = pingServo(id);
  }

  configureLegServo(RIGHT_SERVO_ID, servo_found[RIGHT_SERVO_ID]);
  configureLegServo(LEFT_SERVO_ID, servo_found[LEFT_SERVO_ID]);
}

void begin() {
  Serial1.begin(1000000);
  sc.pSerial = &Serial1;
  delay(300);
  servo_bus_ready = true;

  reportStatus();
  stop();
}

void stop() {
  drive_mode = DriveMode::STOP;
  writeLeftSpeed(0);
  writeRightSpeed(0);
}

void alignForward() {
  drive_mode = DriveMode::ALIGN_FORWARD;
  align_left_done = false;
  align_right_done = false;
  aligned_event = false;
  writeLeftSpeed(ALIGN_SPEED);
  writeRightSpeed(-ALIGN_SPEED);
}

void forward() {
  resetHallSync();
  drive_mode = DriveMode::FORWARD;
  applyWalkingSpeeds();
}

void backward() {
  resetHallSync();
  drive_mode = DriveMode::BACKWARD;
  applyWalkingSpeeds();
}

void turnLeft() {
  drive_mode = DriveMode::TURN_LEFT;
  turn_left_count = 0;
  turn_right_count = 0;
  turn_left_done = false;
  turn_right_done = false;
  turn_done_event = false;
  writeLeftSpeed(-DRIVE_SPEED);
  writeRightSpeed(-DRIVE_SPEED);
}

void turnRight() {
  drive_mode = DriveMode::TURN_RIGHT;
  turn_left_count = 0;
  turn_right_count = 0;
  turn_left_done = false;
  turn_right_done = false;
  turn_done_event = false;
  writeLeftSpeed(DRIVE_SPEED);
  writeRightSpeed(DRIVE_SPEED);
}

void handleHallEvents(
    bool left_event,
    uint32_t left_us,
    bool right_event,
    uint32_t right_us
) {
  if (drive_mode == DriveMode::ALIGN_FORWARD) {
    if (left_event && !align_left_done) {
      writeLeftSpeed(0);
      align_left_done = true;
    }
    if (right_event && !align_right_done) {
      writeRightSpeed(0);
      align_right_done = true;
    }
    if (align_left_done && align_right_done) {
      drive_mode = DriveMode::STOP;
      aligned_event = true;
    }
    return;
  }

  if (drive_mode == DriveMode::TURN_LEFT ||
      drive_mode == DriveMode::TURN_RIGHT) {
    if (left_event && !turn_left_done) {
      turn_left_count++;
      if (turn_left_count >= TURN_HALL_TARGET) {
        writeLeftSpeed(0);
        turn_left_done = true;
      }
    }
    if (right_event && !turn_right_done) {
      turn_right_count++;
      if (turn_right_count >= TURN_HALL_TARGET) {
        writeRightSpeed(0);
        turn_right_done = true;
      }
    }
    if (turn_left_done && turn_right_done) {
      drive_mode = DriveMode::STOP;
      turn_done_event = true;
    }
    return;
  }

  if (drive_mode != DriveMode::FORWARD &&
      drive_mode != DriveMode::BACKWARD) {
    return;
  }

  if (left_event) {
    last_hall_left_us = left_us;
    new_hall_left = true;
  }
  if (right_event) {
    last_hall_right_us = right_us;
    new_hall_right = true;
  }
  updateWalkingSync();
}

bool consumeAligned() {
  bool event = aligned_event;
  aligned_event = false;
  return event;
}

bool consumeTurnDone() {
  bool event = turn_done_event;
  turn_done_event = false;
  return event;
}

void setLeftSpeed(int16_t speed) {
  drive_mode = DriveMode::MANUAL;
  writeLeftSpeed(speed);
}

void setRightSpeed(int16_t speed) {
  drive_mode = DriveMode::MANUAL;
  writeRightSpeed(speed);
}

void setLeftWing(uint16_t position, uint16_t speed) {
  if (servo_bus_ready) {
    sc.WritePos(LEFT_WING_ID, position, 0, clampWingSpeed(speed));
  }
}

void setRightWing(uint16_t position, uint16_t speed) {
  if (servo_bus_ready) {
    sc.WritePos(RIGHT_WING_ID, position, 0, clampWingSpeed(speed));
  }
}

}  // namespace Servo

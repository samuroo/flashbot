#pragma once
#include <Arduino.h>
#include <SCServo.h>

namespace Servo {
    void begin();
    void setLeftSpeed(int16_t speed);
    void setRightSpeed(int16_t speed);
    void setLeftWing(uint16_t position, uint16_t speed);
    void setRightWing(uint16_t position, uint16_t speed);
}

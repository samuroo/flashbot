#pragma once
#include <Arduino.h>
#include <SCServo.h>

namespace Servo {
    void begin();
    void forward(int16_t speed);
    void stop();
    void backward(int16_t speed);
    void turn_right(int16_t speed);
    void turn_left(int16_t speed);
    void wing_open();
    void wing_closed();
}

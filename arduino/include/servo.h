#pragma once
#include <Arduino.h>
#include <SCServo.h>

namespace Servo {
    void begin();
    void forward();
    void stop();
    void backward();
    void turn_right();
    void turn_left();
}

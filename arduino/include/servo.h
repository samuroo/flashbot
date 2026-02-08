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
    void wing_open();
    void wing_closed();

    void sync_servos(bool left_event, bool right_event, uint32_t now_us);
}

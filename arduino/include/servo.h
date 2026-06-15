#pragma once
#include <Arduino.h>
#include <SCServo.h>

namespace Servo {
    void begin();
    void reportStatus();
    void stop();
    void alignForward();
    void alignBackward();
    void forward();
    void backward();
    void backwardCounted();
    void turnLeft();
    void turnRight();
    void handleHallEvents(
        bool left_event,
        uint32_t left_us,
        bool right_event,
        uint32_t right_us
    );
    bool consumeAligned();
    bool consumeBackwardDone();
    bool consumeTurnDone();
    void setLeftSpeed(int16_t speed);
    void setRightSpeed(int16_t speed);
    void setLeftWing(uint16_t position, uint16_t speed);
    void setRightWing(uint16_t position, uint16_t speed);
}


#include "leds.h"

static const uint8_t LED_PIN = 6;

namespace LEDs
{
    void begin() {
        pinMode(LED_PIN, OUTPUT);
        off();
    }

    void on() {
        digitalWrite(LED_PIN, HIGH);
    }

    void off() {
        digitalWrite(LED_PIN, LOW);
    }
} // namespace LEDs

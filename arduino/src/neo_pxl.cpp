#include <Adafruit_NeoPixel.h>
#include "neo_pxl.h"

static const uint8_t NEO_PXL_PIN = 12;
static const uint8_t NUM_PXLS = 12;
static const uint8_t BRIGHTNESS = 150;

static Adafruit_NeoPixel pixels(NUM_PXLS, NEO_PXL_PIN, NEO_GRB + NEO_KHZ800);

namespace NeoPixel {

void begin() {
    pixels.begin();
    pixels.clear();
    pixels.show();
}

void white() {
    for (int i = 0; i < NUM_PXLS; i++) {
        pixels.setPixelColor(i, pixels.Color(BRIGHTNESS, BRIGHTNESS, BRIGHTNESS));
    }
    pixels.show();
}

void off() {
    pixels.clear();
    pixels.show();
}

}

#pragma once

#include <Arduino.h>

struct Events {
  bool hall_left = false;
  bool hall_right = false;
  uint32_t hall_left_us = 0;
  uint32_t hall_right_us = 0;
  bool limit_bumped_left = false;
  bool limit_released_left = false;
  bool limit_bumped_right = false;
  bool limit_released_right = false;
};

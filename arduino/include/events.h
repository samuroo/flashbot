#pragma once

struct Events {
  bool hall_left = false;
  bool hall_right = false;
  bool limit_bumped_left = false;
  bool limit_released_left = false;
  bool limit_bumped_right = false;
  bool limit_released_right = false;
};

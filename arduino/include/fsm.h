#pragma once
#include "events.h"

namespace Fsm {
  void begin(bool debug_enable);
  void step(const Events& ev);
}

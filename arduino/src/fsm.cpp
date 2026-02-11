#include <Arduino.h>
#include "fsm.h"
#include "servo.h"
// #include "leds.h"
#include "neo_pxl.h"

enum class State {
  IDLE, IDLE_DEBUG,
  WANDER,
  BACK_UP_BUMP,
  DETECT, DETECT_DEBUG,
  BACK_UP_FLASH,
  FLASH,
  TURN, DETECT_TURN
};

// PRIVATE VARIABLES
static State state = State::IDLE;
static unsigned long state_enter_ms = 0;
static bool DEBUG = false;
static bool left_bumped = false;
static bool right_bumped = false;
static bool both_bumped = false;

static unsigned long WANDER_TIME = 4000;
static unsigned long DETECT_TIME = 4000;
static unsigned long BACK_UP_FLASH_TIME = 2000;
static unsigned long BACK_UP_BUMP_TIME = 3000;
static unsigned long FLASH_TIME = 1000;
static unsigned long TURN_TIME = 5000;
static unsigned long DETECT_TURN_TIME = 0;

// PRIVATE HELPERS
// enter new state and reset timer
static inline void enter(State s) {
  state = s;
  state_enter_ms = millis();
}
// in state duration
static inline unsigned long in_state_ms() {
  return millis() - state_enter_ms;
}

// PUBLIC FUNCTIONS
namespace Fsm {

void begin(bool debug_enable) {
  DEBUG = debug_enable;
  if (DEBUG) {state = State::IDLE_DEBUG;}
  else {state = State::IDLE;} 
}

int num_faces = 0;

void step(const Events& ev) {
  switch (state) {

    // IDLE 
    // DEBUG : NO PI CONNECTED
    case State::IDLE_DEBUG: {
      if (ev.limit_released_left) {
        Serial.println("FSM: IDLE_DEBUG -> WANDER");
        Servo::forward();
        enter(State::WANDER);
      }
      break;
    }
    // IDLE : PI CONNECTED
    case State::IDLE: {
      if (Serial.available()) {
        String msg = Serial.readStringUntil('\n');
        msg.trim();

        if (msg == "PI_ON") {
          Serial.println("ARDUINO_READY");
          Serial.println("FSM: IDLE -> WANDER");
          Servo::begin(); // only startup servo when power and pi on
          // move forward and try to sync legs
          Servo::forward();
          enter(State::WANDER);
        }
      }
      break;
    }

    // WANDER
    case State::WANDER: {
      if(ev.limit_bumped_left && ev.limit_bumped_right){
        // both bumped at same time
        Serial.println("FSM: WANDER -> BACK_UP_BUMP");
        both_bumped = true;
        Servo::backward();
        enter(State::BACK_UP_BUMP);
        break;
      }
      else if (ev.limit_bumped_left) {
        // left bumped
        Serial.println("FSM: WANDER -> BACK_UP_BUMP");
        left_bumped = true;
        Servo::backward();
        enter(State::BACK_UP_BUMP);
        break;
      }
      else if (ev.limit_bumped_right) {
        // right bumped
        Serial.println("FSM: WANDER -> BACK_UP_BUMP");
        right_bumped = true;
        Servo::backward();
        enter(State::BACK_UP_BUMP);
        break;
      }

      if (in_state_ms() >= WANDER_TIME) {
        if (DEBUG) {
          Serial.println("FSM: WANDER -> DETECT_DEBUG");
          Servo::stop();
          enter(State::DETECT_DEBUG); 
        }
        else {
          Serial.println("FSM: WANDER -> DETECT");
          Servo::stop();
          enter(State::DETECT); 
        }
      }
      break;
    }

    // DETECT
    // DEBUG : NO PI CONNECTED
    case State::DETECT_DEBUG: {
      // fake : got a detection
      if (in_state_ms() >= DETECT_TIME) {
        Serial.println("FSM: DETECT -> DETECT_TURN");
        DETECT_TURN_TIME = 3000;
        enter(State::DETECT_TURN);
      }
      break;
    }
    // DETECT : PI CONNECTED
    case State::DETECT: {
      static unsigned long last_req_ms = 0;
      static bool waiting_reply = false;

      static int dx_px = 0;                 // signed pixels from center

      // Request at 5 Hz
      if (!waiting_reply && (millis() - last_req_ms > 200)) {
        Serial.println("REQ_DET");
        last_req_ms = millis();
        waiting_reply = true;
      }

      // If Pi doesn't reply soon, retry
      if (waiting_reply && (millis() - last_req_ms > 300)) {
        waiting_reply = false;
      }

      // Read reply: expects a single signed int line like "-123\n" or "0\n"
      Serial.setTimeout(5);
      if (Serial.available()) {
        int v = Serial.parseInt();          // parses signed ints fine
        while (Serial.available()) Serial.read();  // flush remainder/newline

        dx_px = v;
        waiting_reply = false;
      }

      // Person detected if dx != 0 (since Pi sends 0 when none/too small)
      bool person_detected = (dx_px != 0);

      if (person_detected) {
        const int DX_MAX = 320;                 // since width = 640
        const int CENTER_ENOUGH = DX_MAX;   // 80 px = 640/8 from center -> right now just assumes center enough every time
        const unsigned long TURN_MIN_MS = 250;
        const unsigned long TURN_MAX_MS = 2500;

        int dx = dx_px;
        int mag = abs(dx);

        // 1) If person is "center enough", skip turning and go straight to BACK_UP_FLASH
        if (mag <= CENTER_ENOUGH) {
          Serial.println("Centered enough -> BACK_UP_FLASH");
          dx_px = 0;
          waiting_reply = false;
          Servo::backward();                 // IMPORTANT: match the state we're entering
          enter(State::BACK_UP_FLASH);
          break;
        }

        // 2) Otherwise: do a turn with time mapped by |dx|
        if (mag > DX_MAX) mag = DX_MAX;

        // linear map: mag=161..320 -> time in [TURN_MIN_MS..TURN_MAX_MS]
        unsigned long t = TURN_MIN_MS + (unsigned long)(TURN_MAX_MS - TURN_MIN_MS) * mag / DX_MAX;
        DETECT_TURN_TIME = t;

        Serial.print("DETECT_TURN_TIME = ");
        Serial.println(DETECT_TURN_TIME);

        if (dx < 0) Servo::turn_left();
        else        Servo::turn_right();

        dx_px = 0;
        waiting_reply = false;
        enter(State::DETECT_TURN);
        break;

      }

      // EDIT 17:12 Sam 
      // if (in_state_ms() >= DETECT_TIME) {
      //   Serial.println("FSM: DETECT -> WANDER");
      //   Servo::forward();
      //   enter(State::WANDER);
      // }
      break;
    }

    case State::DETECT_TURN: {
      if (in_state_ms() >= DETECT_TURN_TIME) {
        Serial.println("FSM: DETECT_TURN_TIME -> BACK_UP_FLASH");
        DETECT_TURN_TIME = 0;
        Servo::backward();
        enter(State::BACK_UP_FLASH);
      }
      break;
    }

    case State::BACK_UP_FLASH: {
      if (in_state_ms() >= BACK_UP_FLASH_TIME) {
        Serial.println("FSM: BACK_UP_FLASH -> FLASH");
        Servo::wing_open();
        Servo::stop();
        NeoPixel::white();
        enter(State::FLASH);
      }
      break;
    }

    case State::FLASH: {
      if (in_state_ms() >= FLASH_TIME) {
        Serial.println("FSM: FLASH -> TURN");
        Servo::turn_right();
        NeoPixel::off();
        Servo::wing_closed();
        enter(State::TURN);
      }
      break;
    }

    // TIME BASED
    // case State::TURN: {
    //   if (in_state_ms() >= TURN_TIME) {
    //     Serial.println("FSM: TURN -> WANDER");
    //     Servo::forward();
    //     enter(State::WANDER);
    //   }
    //   break;
    // }

    //HALL EFFECT METHOD
    // case State::TURN: {
    //   static uint8_t l_count = 0;
    //   static uint8_t r_count = 0;
    //   static bool initialized = false;

    //   if (!initialized) {
    //     l_count = 0;
    //     r_count = 0;
    //     initialized = true;
    //   }

    //   if (ev.hall_left)  l_count++;
    //   if (ev.hall_right) r_count++;

    //   const uint8_t TARGET = 2;   // “2 passes” per side

    //   // Keep turning until BOTH sides hit target
    //   if (l_count >= TARGET && r_count >= TARGET) {
    //     initialized = false; // reset for next TURN

    //     Serial.println("FSM: TURN (hall-count done) -> WANDER");
    //     Servo::forward();                 // forward() should set mode internally
    //     enter(State::WANDER);
    //   }

    //   if (in_state_ms() >= TURN_TIME) {
    //     Serial.println("FSM: TURN (MISSED HALL) -> WANDER");
    //     Servo::forward();
    //     enter(State::WANDER);
    //   }

    //   break;
    // }
    case State::TURN: {
      static uint8_t l_count = 0;
      static uint8_t r_count = 0;
      static bool initialized = false;
      static bool left_stopped = false;
      static bool right_stopped = false;

      if (!initialized) {
        l_count = 0;
        r_count = 0;
        left_stopped = false;
        right_stopped = false;
        initialized = true;
      }

      if (ev.hall_left && !left_stopped) {
        l_count++;
        if (l_count >= 3) {
          Servo::stop_left();
          left_stopped = true;
        }
      }

      if (ev.hall_right && !right_stopped) {
        r_count++;
        if (r_count >= 3) {
          Servo::stop_right();
          right_stopped = true;
        }
      }

      // When BOTH finished → go to wander
      if (left_stopped && right_stopped) {
        initialized = false;
        Serial.println("FSM: TURN done -> WANDER");
        Servo::forward();
        enter(State::WANDER);
      }

      if (in_state_ms() >= TURN_TIME) {
        initialized = false;
        Serial.println("FSM: TURN timeout -> WANDER");
        Servo::forward();
        enter(State::WANDER);
      }

      break;
    }




    // BUMPED
    case State::BACK_UP_BUMP: {
      if (in_state_ms() >= BACK_UP_BUMP_TIME) {
        Serial.println("FSM: BACK_UP_BUMP -> TURN");
        if (both_bumped) {Servo::turn_right(); both_bumped = false; enter(State::TURN);}
        else if (left_bumped) {Servo::turn_left(); left_bumped = false; enter(State::TURN);}
        else if (right_bumped) {Servo::turn_right(); right_bumped = false; enter(State::TURN);}
        else {
          // safety fallback if no flag is set
          Servo::turn_right();
          enter(State::TURN);
        }
      }
      break;
    }


  }
}

} // namespace Fsm

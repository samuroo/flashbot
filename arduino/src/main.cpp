#include <Arduino.h>

#include "inputs.h"
#include "neo_pxl.h"
#include "servo.h"

static String input_line;

static void publish_event(const String& name) {
  Serial.print("EVT,");
  Serial.println(name);
}

// Parse comma-separated integer arguments from the serial command line.
static bool read_int_arg(const String& command, int start_index, int& value) {
  int end_index = command.indexOf(',', start_index);
  String token;

  if (end_index == -1) {
    token = command.substring(start_index);
  } else {
    token = command.substring(start_index, end_index);
  }

  if (token.length() == 0) {
    return false;
  }

  value = token.toInt();
  return true;
}

static void handle_wing_command(const String& command, bool left_wing) {
  int first_arg = command.indexOf(',', 4);
  if (first_arg == -1) {
    return;
  }

  int second_arg = command.indexOf(',', first_arg + 1);
  if (second_arg == -1) {
    return;
  }

  int position = 0;
  int speed = 0;
  if (!read_int_arg(command, first_arg + 1, position)) {
    return;
  }
  if (!read_int_arg(command, second_arg + 1, speed)) {
    return;
  }

  if (left_wing) {
    Servo::setLeftWing(static_cast<uint16_t>(position), static_cast<uint16_t>(speed));
  } else {
    Servo::setRightWing(static_cast<uint16_t>(position), static_cast<uint16_t>(speed));
  }
}

static void handle_servo_command(const String& command, bool left_servo) {
  int arg_start = command.indexOf(',', 4);
  if (arg_start == -1) {
    return;
  }

  int speed = 0;
  if (!read_int_arg(command, arg_start + 1, speed)) {
    return;
  }

  if (left_servo) {
    Servo::setLeftSpeed(static_cast<int16_t>(speed));
  } else {
    Servo::setRightSpeed(static_cast<int16_t>(speed));
  }
}

static void handle_drive_command(const String& command) {
  String mode = command.substring(10);
  mode.trim();

  if (mode == "STOP") {
    Servo::stop();
  } else if (mode == "ALIGN_FORWARD") {
    Servo::alignForward();
  } else if (mode == "FORWARD") {
    Servo::forward();
  } else if (mode == "BACKWARD") {
    Servo::backward();
  } else if (mode == "TURN_LEFT") {
    Servo::turnLeft();
  } else if (mode == "TURN_RIGHT") {
    Servo::turnRight();
  }
}

// Keep command handling flat so the Pi/Arduino contract is easy to inspect.
static void handle_command(const String& command) {
  if (command == "CMD,hello") {
    publish_event("ready");
  } else if (command == "CMD,servo_status") {
    Servo::reportStatus();
  } else if (command.startsWith("CMD,drive,")) {
    handle_drive_command(command);
  } else if (command.startsWith("CMD,wing_left,")) {
    handle_wing_command(command, true);
  } else if (command.startsWith("CMD,wing_right,")) {
    handle_wing_command(command, false);
  } else if (command.startsWith("CMD,servo_left,")) {
    handle_servo_command(command, true);
  } else if (command.startsWith("CMD,servo_right,")) {
    handle_servo_command(command, false);
  } else if (command == "CMD,flash_on") {
    NeoPixel::white();
  } else if (command == "CMD,flash_off") {
    NeoPixel::off();
  }
}

// Commands are newline-terminated ASCII messages from the ROS serial node.
static void read_serial_commands() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      input_line.trim();
      if (input_line.length() > 0) {
        handle_command(input_line);
      }
      input_line = "";
      continue;
    }

    input_line += c;
  }
}

// Input events are one-shot booleans from the debounced input helper.
static void publish_input_events(const Events& ev) {
  Servo::handleHallEvents(
      ev.hall_left,
      ev.hall_left_us,
      ev.hall_right,
      ev.hall_right_us
  );

  if (ev.hall_left) {
    publish_event("hall_left");
  }
  if (ev.hall_right) {
    publish_event("hall_right");
  }
  if (ev.limit_bumped_left) {
    publish_event("limit_bump_left");
  }
  if (ev.limit_released_left) {
    publish_event("limit_release_left");
  }
  if (ev.limit_bumped_right) {
    publish_event("limit_bump_right");
  }
  if (ev.limit_released_right) {
    publish_event("limit_release_right");
  }
  if (Servo::consumeAligned()) {
    publish_event("aligned");
  }
  if (Servo::consumeTurnDone()) {
    publish_event("turn_done");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {
    delay(10);
  }

  Inputs::begin();
  Servo::begin();
  NeoPixel::begin();

  publish_event("boot");
  publish_event("ready");
}

void loop() {
  read_serial_commands();
  publish_input_events(Inputs::poll());
}

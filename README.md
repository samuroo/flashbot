# Flashbot

Flashbot is a Raspberry Pi 5 robot running Ubuntu 24.04 and ROS 2 Jazzy. The
Raspberry Pi handles vision and high-level behavior, while an Arduino controls
the motors, wings, lights, hall sensors, and limit switches.

Showcased at Highlight Delft 2026 and Maker Faire Delft 2026.

## Raspberry Pi setup

These instructions assume this repository is cloned to `~/flashbot` and ROS 2
Jazzy is already installed.

Install the build tools and runtime dependencies:

```bash
sudo apt update
sudo apt install \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-opencv \
  python3-serial \
  opencv-data \
  ros-jazzy-camera-ros \
  ros-jazzy-cv-bridge \
  ros-jazzy-web-video-server
```

Install any remaining package dependencies and build the workspace:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/flashbot
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Source both ROS 2 and this workspace in every new terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot/install/setup.bash
```

To do this automatically, add those two lines to `~/.bashrc`.

### Check the camera

Confirm that Linux can see a camera before starting ROS:

```bash
ls -l /dev/video*
```

On systems with the libcamera tools installed, camera details can also be
listed with:

```bash
cam --list
```

If no camera appears, check the ribbon orientation, camera connector, and
whether the camera is enabled and supported by the installed Raspberry Pi
kernel.

## Vision bring-up

The main vision launch file starts:

- `camera_node` from `camera_ros`
- `face_detector_node` from `flashbot_vision`
- `web_video_server`

Start all three:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot/install/setup.bash
ros2 launch flashbot_bringup vision.launch.py
```

The behavior state machine and Arduino serial bridge are **not** started by
this launch file. Start those separately when needed, as described below.

Verify the running nodes and topics:

```bash
ros2 node list
ros2 topic list
ros2 topic info /camera_node/image_raw
ros2 topic info /face_bbox_image
ros2 topic hz /camera_node/image_raw
ros2 topic hz /face_bbox_image
```

Expected nodes include:

```text
/camera_node
/face_detector_node
/web_video_server
```

## Full robot bring-up

The full launch file starts the camera, face detector, browser stream, Arduino
serial bridge, and behavior state machine together:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot/install/setup.bash
ros2 launch flashbot_bringup flashbot.launch.py
```

It uses `/dev/ttyACM0` at `115200` baud by default. Override either value when
the Arduino appears on a different port:

```bash
ros2 launch flashbot_bringup flashbot.launch.py \
  serial_port:=/dev/ttyUSB0 \
  baud_rate:=115200
```

The state machine starts in `IDLE` and does not move the robot until the serial
bridge confirms the Arduino heartbeat. Stop the full system with `Ctrl+C`.

Verify all five nodes:

```bash
ros2 node list
```

Expected nodes are:

```text
/camera_node
/face_detector_node
/web_video_server
/flashbot_serial_node
/state_machine_node
```

## Streaming in a local browser

Connect the viewing device to the same network as the Raspberry Pi. Open one
of these URLs:

| Stream | Hostname URL |
| --- | --- |
| Raw camera | `http://flashbot:8080/stream?topic=/camera_node/image_raw` |
| Face bounding box | `http://flashbot:8080/stream?topic=/face_bbox_image` |

If the `flashbot` hostname does not resolve, find the Pi's IP address:

```bash
hostname -I
```

Then replace `flashbot` with that address, for example:

```text
http://192.168.1.50:8080/stream?topic=/face_bbox_image
```

The web server's topic index is available at:

```text
http://flashbot:8080/
```

## Vision topics

The vision launch exposes the following interfaces:

| Topic | Type | Direction | Description |
| --- | --- | --- | --- |
| `/camera_node/image_raw` | `sensor_msgs/msg/Image` | Camera publishes | Raw camera frames |
| `/face_detected` | `std_msgs/msg/Bool` | Vision publishes | Whether at least one face is visible |
| `/face_bbox` | `sensor_msgs/msg/RegionOfInterest` | Vision publishes | First face bounding box, or all zeros when no face is visible |
| `/face_bbox_image` | `sensor_msgs/msg/Image` | Vision publishes | Camera frame with the first detected face outlined |

Inspect face detection and bounding-box messages:

```bash
ros2 topic echo /face_detected
ros2 topic echo /face_bbox
```

Image messages are large, so use `ros2 topic hz` or the browser stream instead
of continuously echoing them:

```bash
ros2 topic hz /face_bbox_image
ros2 topic info /face_bbox_image --verbose
```

## Behavior state machine

The behavior node is a standalone node and must be started in another terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot/install/setup.bash
ros2 run flashbot_behavior state_machine_node
```

It waits in `IDLE` until `/flashbot/arduino_ready` confirms a live serial
heartbeat. It then aligns both legs at their next hall-sensor crossing, walks
forward briefly, and enters `STOP`, where the wings flutter gently.
If startup alignment does not finish within five seconds, the robot stops
instead of beginning forward motion with an unknown leg phase.

The face-response sequence is:

```text
STOP -> ALIGN_BACKWARD -> WALK_BACKWARD -> FLASH -> TURN_AROUND
-> ALIGN_AFTER_TURN -> ESCAPE_FORWARD -> STOP
```

Face detection triggers this sequence only while the robot is in `STOP`.
Detections during startup, alignment, walking, flashing, or turning are
ignored. A face that is already visible when the robot enters `STOP` triggers
the sequence immediately. One continuous detection causes only one response;
the detector must report `false` before the behavior is armed again.

Before retreating, Flashbot aligns both legs backward at their next hall
events. The retreat then counts two hall events independently for each leg
instead of using a timer. After turning, Flashbot aligns both legs forward
before walking again. Alignment, retreat, and turn timeouts send it to `STOP`
instead of continuing with uncertain leg phase.

Watch its state and low-level drive commands:

```bash
ros2 topic echo /flashbot/state
ros2 topic echo /flashbot_command
ros2 topic echo /flashbot/cmd/drive
```

Simulate a detected face without running the camera:

```bash
ros2 topic pub --once /face_detected std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /face_bbox sensor_msgs/msg/RegionOfInterest \
  "{x_offset: 100, y_offset: 80, height: 200, width: 200, do_rectify: false}"
```

Return the state machine to its normal state:

```bash
ros2 topic pub --once /face_detected std_msgs/msg/Bool "{data: false}"
```

`/flashbot_command` remains as a compatibility/debug output. The behavior node
drives the robot through `/flashbot/cmd/drive`, the wing command topics, and
`/flashbot/cmd/flash`.

## Arduino serial bridge

Connect the Arduino over USB and identify its serial port:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB*
```

The default port is `/dev/ttyACM0` at `115200` baud. Start the bridge in a
separate terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot/install/setup.bash
ros2 run flashbot_serial flashbot_serial_node
```

Override the port or baud rate when required:

```bash
ros2 run flashbot_serial flashbot_serial_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p baud_rate:=115200
```

The node reconnects automatically and logs `Arduino ready` after the serial
handshake succeeds.

At Arduino startup, the firmware pings servo IDs `0` through `3` and checks
that leg IDs `0` and `1` are in PWM mode. Monitor those diagnostics with:

```bash
ros2 topic echo --qos-durability transient_local /flashbot/servo_status
```

Expected leg messages include `ping=ok`, `mode_after=3`, and `status=ready`.
If an ID reports `ping=failed`, inspect that servo's configured ID, power, and
serial-bus connection before testing movement.

The serial node requests a fresh diagnostic report after every Arduino
connection, so these messages do not depend on catching the Arduino boot
output.

### Arduino command topics

The serial bridge subscribes to:

| Topic | Type | Payload |
| --- | --- | --- |
| `/flashbot/cmd/drive` | `std_msgs/msg/String` | `STOP`, `ALIGN_FORWARD`, `ALIGN_BACKWARD`, `FORWARD`, `BACKWARD`, `BACKWARD_COUNTED`, `TURN_LEFT`, or `TURN_RIGHT` |
| `/flashbot/cmd/wing_left` | `std_msgs/msg/Int32MultiArray` | `[position, speed]` |
| `/flashbot/cmd/wing_right` | `std_msgs/msg/Int32MultiArray` | `[position, speed]` |
| `/flashbot/cmd/servo_left` | `std_msgs/msg/Int32` | Walking motor speed |
| `/flashbot/cmd/servo_right` | `std_msgs/msg/Int32` | Walking motor speed |
| `/flashbot/cmd/flash` | `std_msgs/msg/Bool` | `true` turns the flash on |

### Hall synchronization

The hall sensors are configured as `INPUT_PULLUP` inputs with falling-edge
interrupts. A hall message therefore represents a brief magnet-crossing event,
not a persistent high state. The synchronization logic runs on the Arduino so
it can use the original microsecond timestamps instead of ROS message timing.

The current algorithm works as follows:

- `ALIGN_FORWARD` moves both legs forward at speed `250`. Each leg stops
  independently when its own hall sensor detects the next magnet crossing.
  After both legs have stopped, the Arduino publishes
  `/flashbot/events/aligned`.
- `ALIGN_BACKWARD` performs the same independent alignment while moving both
  legs backward at speed `250`.
- `FORWARD` and continuous `BACKWARD` start both legs at speed `500`. After receiving a
  new event from each hall sensor, the Arduino compares their timestamps and
  adjusts the two speeds in opposite directions.
- `BACKWARD_COUNTED` starts at speed `500`, applies the same synchronization,
  and counts hall events independently. Each leg stops after two events. When
  both have stopped, the Arduino publishes
  `/flashbot/events/backward_done`.
- Walking corrections are limited to `125` speed units above or below the base
  speed. A positive timestamp error speeds up the left leg and slows down the
  right leg; a negative error does the opposite.
- `TURN_LEFT` and `TURN_RIGHT` count hall events independently for each leg.
  Each leg stops after three events. When both have stopped, the Arduino
  publishes `/flashbot/events/turn_done`.

The speeds, correction gain, and three-event turn distance are experimental.
They will likely need tuning on the physical robot. Always lift or securely
support Flashbot for the first test, keep clear of the mechanisms, and have the
`STOP` command ready in another terminal.

### Manual drive tests

Run these tests with `flashbot_serial_node` active but
`state_machine_node` stopped. Otherwise, the behavior node may immediately
replace a manual drive command with its own command.

Keep this emergency stop command ready:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: STOP}"
```

Test startup alignment. Watch `/flashbot/events/aligned` in another terminal:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: ALIGN_FORWARD}"
```

Test backward alignment:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: ALIGN_BACKWARD}"
```

Test forward movement, then stop:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: FORWARD}"

ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: STOP}"
```

Test backward movement, then stop:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: BACKWARD}"

ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: STOP}"
```

Test the automatic two-event backward retreat. It should stop without a
separate `STOP` after both legs complete two hall events:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: BACKWARD_COUNTED}"
```

Test each turn separately. A turn should stop automatically after each leg
records three hall events, but use `STOP` immediately if the motion is wrong:

```bash
ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: TURN_LEFT}"

ros2 topic pub --once /flashbot/cmd/drive std_msgs/msg/String \
  "{data: TURN_RIGHT}"
```

Monitor alignment, turn completion, and the raw hall events:

```bash
ros2 topic echo /flashbot/events/aligned
ros2 topic echo /flashbot/events/backward_done
ros2 topic echo /flashbot/events/turn_done
ros2 topic echo /flashbot/events/hall_left
ros2 topic echo /flashbot/events/hall_right
```

Stop both walking motors:

```bash
ros2 topic pub --once /flashbot/cmd/servo_left std_msgs/msg/Int32 "{data: 0}"
ros2 topic pub --once /flashbot/cmd/servo_right std_msgs/msg/Int32 "{data: 0}"
```

Test the flash:

```bash
ros2 topic pub --once /flashbot/cmd/flash std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /flashbot/cmd/flash std_msgs/msg/Bool "{data: false}"
```

The following commands cause physical movement. Lift or secure the robot,
keep clear of the mechanisms, and substitute values that are safe for the
installed hardware:

```bash
# Walking motor speed is clamped to the range -1500 through 1500.
ros2 topic pub --once /flashbot/cmd/servo_left std_msgs/msg/Int32 \
  "{data: <speed>}"

# Wing commands contain [position, speed]; wing speed is clamped to 0-1500.
ros2 topic pub --once /flashbot/cmd/wing_left std_msgs/msg/Int32MultiArray \
  "{data: [<position>, <speed>]}"
```

The CLI placeholders above are documentation only. Replace `<position>` and
`<speed>` with tested numeric values before running a movement command.

### Arduino event topics

The serial bridge publishes:

| Topic | Type | Description |
| --- | --- | --- |
| `/flashbot/arduino_ready` | `std_msgs/msg/Bool` | Latched serial heartbeat status |
| `/flashbot/events/aligned` | `std_msgs/msg/Bool` | Both legs reached their forward or backward hall alignment point |
| `/flashbot/events/backward_done` | `std_msgs/msg/Bool` | Both legs completed the two-event counted retreat |
| `/flashbot/events/turn_done` | `std_msgs/msg/Bool` | Both legs completed the configured hall-counted turn |
| `/flashbot/servo_status` | `std_msgs/msg/String` | Servo ping and leg PWM-mode diagnostics |
| `/flashbot/events/hall_left` | `std_msgs/msg/Bool` | Short pulse from the left hall sensor |
| `/flashbot/events/hall_right` | `std_msgs/msg/Bool` | Short pulse from the right hall sensor |
| `/flashbot/events/limit_left` | `std_msgs/msg/Bool` | Left limit switch pressed or released |
| `/flashbot/events/limit_right` | `std_msgs/msg/Bool` | Right limit switch pressed or released |

Monitor all four in separate terminals, or inspect one at a time:

```bash
ros2 topic echo /flashbot/events/hall_left
ros2 topic echo /flashbot/events/hall_right
ros2 topic echo /flashbot/events/limit_left
ros2 topic echo /flashbot/events/limit_right
ros2 topic echo /flashbot/arduino_ready
```

Use these commands for a quick interface check:

```bash
ros2 node info /flashbot_serial_node
ros2 topic info /flashbot/cmd/flash --verbose
ros2 topic info /flashbot/events/limit_left --verbose
```

## Arduino to ROS 2 serial protocol

Communication over USB serial uses newline-terminated ASCII messages:

```text
<TYPE>,<NAME>[,<ARG1>,<ARG2>,...]\n
```

Commands sent to the Arduino begin with `CMD`, for example
`CMD,servo_left,0`. Events sent by the Arduino begin with `EVT`, for example
`EVT,limit_bump_left`. The ROS 2 serial bridge converts between this protocol
and the `/flashbot/cmd/*` and `/flashbot/events/*` topics documented above.

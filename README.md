# Flashbot V2 README

## Build and source

Run on the Pi, outside the Python virtual environment. Build all workspace packages:

```bash
source /opt/ros/jazzy/setup.bash && cd ~/flashbot_ws && colcon build --symlink-install
```

Source in each new terminal (and again after building):

```bash
source /opt/ros/jazzy/setup.bash && source ~/flashbot_ws/install/setup.bash && source ~/camera_ws/install/local_setup.bash
```

## Pi overview

- Hostname: `flashbot-1`
- Username: `flashbot-1`
- Password: `flashbot`
- OS: Ubuntu 24.04.5 LTS
- Serial device access enabled with `sudo usermod -aG dialout "$USER"`
- Camera device access enabled with `sudo usermod -aG video "$USER"`
- Added a alias in /.bash_aliases.
	- source_ros2: Source ros2 jazzy

### Installed on venv
Python packages installed in the repository's `venv` on the Pi:
- `ftservo-python-sdk` — servo control.

## LED

`led_driver` runs `led_node`, controlling the MOSFET gate on **BCM GPIO 13
(physical pin 33)**. The LED is powered from the Pi's 5 V supply pin;
GPIO 13 only controls the MOSFET gate. The MOSFET source connects to Pi ground.
Keep the 330 ohm gate resistor and
100 kohm pull-down. Starts OFF and switches LOW on normal shutdown.

Installed GPIO support on the Pi with `sudo apt install python3-lgpio`.

Build and run on the Pi, outside the Python virtual environment:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/flashbot_ws
colcon build --symlink-install --packages-select led_driver
source install/setup.bash
ros2 run led_driver led_node
```

In another terminal, source ROS and the workspace, then control the LED:

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot_ws/install/setup.bash
ros2 service call /led/set std_srvs/srv/SetBool "{data: true}"   # ON
ros2 service call /led/set std_srvs/srv/SetBool "{data: false}"  # OFF
ros2 topic pub --once /led/brightness std_msgs/msg/UInt8 "{data: 128}"
```

`/led/set`: `true` = fully ON, `false` = OFF. `/led/brightness`: `0` = OFF,
`255` = fully ON, `128` = about half brightness. The latest command takes effect.
Uses 500 Hz software PWM; if PWM
fails, the node logs an error and keeps ON/OFF control available. Stop with
`Ctrl+C`. The external pull-down holds the gate LOW after GPIO is released.

Defaults to `/dev/gpiochip4` (RP1 on this Pi), which your user already has
access to through `dialout`. If the RP1 controller number changes, use
`ros2 run led_driver led_node --ros-args -p gpiochip:=0` with its actual number.

## Camera

Camera sensor is the IMX708, on CAM0. The packaged camera driver failed
with `Unable to acquire a CFE instance`, so we used Raspberry Pi's libcamera
and built it together with `camera_ros` in `~/camera_ws`.

Source: [official camera_ros build instructions](https://github.com/christianrauch/camera_ros#build-instructions),
using the Raspberry Pi fork, and [libcamera build dependencies](https://libcamera.org/getting-started.html#dependencies).

### Setup on the Pi

Originally installed:

```bash
sudo apt install ros-jazzy-camera-ros ros-jazzy-web-video-server
```

Additional build dependencies installed (the other core dependencies were already present):

```bash
sudo apt update
sudo apt install -y meson ninja-build python3-colcon-meson \
  python3-ply libyaml-dev \
  ros-jazzy-ament-cmake-clang-format \
  ros-jazzy-ament-cmake-mypy \
  ros-jazzy-ament-cmake-pyflakes
```

Source download and build commands, run outside the Python virtual environment:

```bash
mkdir -p ~/camera_ws/src
cd ~/camera_ws/src
git clone https://github.com/raspberrypi/libcamera.git
git clone https://github.com/christianrauch/camera_ros.git

source /opt/ros/jazzy/setup.bash
cd ~/camera_ws
rosdep check --from-paths src --ignore-src --rosdistro jazzy --skip-keys=libcamera
colcon build --executor sequential --event-handlers console_direct+
```

Source versions used on 10 November 2026: libcamera `v0.8.0+rpt20261104`
(`9fe1678b8ad5fbae875942b55b58ade23014194c`) and camera_ros `0.8.1`
(`9e94b5b6d6cacbe77dc893d54735f06b4a2fd16f`). The original apt packages remain installed.

### Run

Source the camera workspace last in each new terminal so ROS uses the built driver.
Defaults: camera 0, 640×480, port 8080.

```bash
source /opt/ros/jazzy/setup.bash
source ~/flashbot_ws/install/setup.bash
source ~/camera_ws/install/local_setup.bash
ros2 launch flashbot_bringup camera.launch.py
```
To change the parameters.
```bash
ros2 launch flashbot_bringup camera.launch.py camera:=0 width:=1280 height:=720 port:=8081
```

View the camera at `http://flashbot-1.local:8080/stream?topic=/camera_node/image_raw`.
Use the Pi's IP address if the hostname does not work. If you change `port`,
use that port in the URL. Stop with `Ctrl+C`.

Verified on 10 November 2026: both nodes ran, `/camera_node/image_raw` published
at about 30 FPS, and the HTTP snapshot and MJPEG stream worked from the laptop
at 640×480. Both nodes stopped cleanly. The camera is not calibrated yet;
the missing calibration file message does not prevent streaming.

Checks used in another terminal with the same workspaces sourced:

```bash
ros2 pkg prefix camera_ros  # should point into ~/camera_ws/install
ros2 node list
timeout 8s ros2 topic hz /camera_node/image_raw
curl --max-time 10 -o /tmp/flashbot-camera-test.jpg 'http://127.0.0.1:8080/snapshot?topic=/camera_node/image_raw'
file /tmp/flashbot-camera-test.jpg
```

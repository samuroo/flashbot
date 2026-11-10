# Flashbot V2 README

## Pi overview

- Hostname: `flashbot-1`
- Username: `flashbot-1`
- Password: `flashbot`
- OS: Ubuntu 24.04.4 LTS
- Serial device access enabled with `sudo usermod -aG dialout "$USER"` (reconnect SSH afterward).

### Installed on venv
Python packages installed in the repository's `venv` on the Pi:
- `ftservo-python-sdk` — servo control.

## Camera

Installed the ROS 2 camera driver and browser video server on the Pi:

```bash
sudo apt install ros-jazzy-camera-ros ros-jazzy-web-video-server
```

Test the camera and web-video-server. The defaults: camera 0, 640×480, port 8080.
```bash
ros2 launch flashbot_bringup camera.launch.py
```
To change the parameters.
```bash
ros2 launch flashbot_bringup camera.launch.py camera:=0 width:=1280 height:=720 port:=8081
```

View the camera at `http://flashbot-1:8080/stream?topic=/camera_node/image_raw`. Use the Pi's IP address if the hostname does not work.

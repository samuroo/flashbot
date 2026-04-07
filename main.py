import sys
import threading
import time

try:
    import serial
except ImportError:
    serial = None

from detection.detection import capture_frame, detect_largest_person, draw_detection, setup_camera, stop_camera
from detection.frame_hub import update_frame
from detection.web_page import start_web_server

# set arudino port & baudrate
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
ARDUINO_CONNECTED = False
mode = None


# handshake function with arudino
def connect_arduino():
    if serial is None:
        return None, False

    serial_exception = getattr(serial, "SerialException", Exception)

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1, write_timeout=0.1)
    except serial_exception:
        return None, False

    # let arduino boot for a sec
    time.sleep(2.0)

    # try a short handshake so "connected" means the board is really responding
    deadline = time.time() + 5.0
    while time.time() < deadline:
        ser.write(b"PI_ON\n")
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print("Arduino:", line)
            if line == "ARDUINO_READY":
                return ser, True
        time.sleep(0.1)

    ser.close()
    return None, False


def start_stream_thread():
    thread = threading.Thread(
        target=start_web_server,
        kwargs={"host": "0.0.0.0", "port": 5000},
        daemon=True
    )
    thread.start()
    return thread


def process_frame():
    frame = capture_frame()
    det = detect_largest_person(frame, conf_th=0.5, nms_th=0.4, debug=True)
    update_frame(draw_detection(frame.copy(), det))
    return det


# start the server as a thread
start_stream_thread()
print("Web stream available on port 5000.")

# check arguments to set camera mode
if len(sys.argv) > 1:
    mode = sys.argv[1]
else:
    mode = "pi"

setup_camera(mode)
print(f"Camera mode: {mode}")

ser = None
if mode == "pi":
    ser, ARDUINO_CONNECTED = connect_arduino()
    print(f"ARDUINO_CONNECTED = {ARDUINO_CONNECTED}")

try:
    if mode == "computer-camera":
        print("Testing mode: using computer camera")
        while True:
            process_frame()
            time.sleep(0.03)

    elif mode == "pi-camera":
        while True:
            process_frame()
            time.sleep(0.03)

    elif not ARDUINO_CONNECTED:
        print(f"Arduino not detected on {SERIAL_PORT}.")

    else:
        print("Handshake complete. Waiting for REQ_DET...")

        # ---- Main loop: only respond when Arduino asks ----
        while True:
            while ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                # still need to try this, but continsuly update frame and the if line is REQ then arudin is asking for detections
                det = process_frame()

                if line == "REQ_DET":
                    # det = process_frame()

                    if det is None:
                        ser.write(b"0\n")
                        continue

                    try:
                        x1, y1, x2, y2 = det["bbox"]
                        cx, cy = det["center"]

                        w = int(x2 - x1)
                        h = int(y2 - y1)

                        # ---- size gate ----
                        W_MIN = 120
                        H_MIN = 160
                        if w < W_MIN or h < H_MIN:
                            ser.write(b"0\n")
                            continue

                        # ---- dx from image center ----
                        IMG_W = 640  # match your camera width
                        dx = int(cx - (IMG_W // 2))  # negative = left

                        ser.write(f"{dx}\n".encode())
                        print("Pi ->", dx)

                    except Exception as e:
                        ser.write(b"0\n")
                        print("Pi -> 0 (parse error)", e, "det=", det)

                else:
                    print("Arduino:", line)

            time.sleep(0.01)
finally:
    stop_camera()
    if ser is not None:
        ser.close()

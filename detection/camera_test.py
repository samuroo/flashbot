from picamera2 import Picamera2
import time

picam2 = Picamera2()

# basic config
picam2.configure(picam2.create_preview_configuration())

picam2.start()

print("Camera running... press Ctrl+C to stop")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping camera...")
    picam2.stop()
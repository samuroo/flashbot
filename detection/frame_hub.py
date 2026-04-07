import threading
import cv2

# ensures that both threads dont touch
# the shared data at the same time
_frame_lock = threading.Lock()
_latest_frame = None

# store newest frame in memory
def update_frame(frame):
    global _latest_frame
    if frame is None:
        return

    with _frame_lock:
        _latest_frame = frame.copy()

# reads the stored frame and converts it to JPEG for the browser
def get_jpeg_frame():
    with _frame_lock:
        if _latest_frame is None:
            return None
        frame = _latest_frame.copy()

    # frame = cv2.resize(frame, (320, 180))
    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
    if not success:
        return None

    return buffer.tobytes()

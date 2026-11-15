"""HTTP page and a small, read-only JSON snapshot; video is served separately."""

from collections import deque
import threading
import time

from flask import Flask, jsonify, render_template


class Status:
    WINDOW = 3.0
    STALE = 2.0

    def __init__(self):
        self.lock = threading.Lock()
        self.camera_times = deque(maxlen=1000)
        self.detection_times = deque(maxlen=1000)
        self.width = self.height = 0
        self.detected = False
        self.center = None
        self.position_time = 0.0

    def camera(self, width, height):
        with self.lock:
            self.camera_times.append(time.monotonic())
            self.width, self.height = width, height

    def detection(self, detected):
        with self.lock:
            self.detection_times.append(time.monotonic())
            self.detected = detected
            if not detected:
                self.center = None

    def position(self, coordinates):
        if len(coordinates) != 2:
            return
        with self.lock:
            self.center = list(coordinates)
            self.position_time = time.monotonic()

    def snapshot(self):
        now = time.monotonic()
        with self.lock:
            def rate(times):
                while times and times[0] < now - self.WINDOW:
                    times.popleft()
                if len(times) < 2 or now - times[-1] > self.STALE:
                    return 0.0
                return round((len(times) - 1) / max(times[-1] - times[0], 0.001), 1)

            fps, dfps = rate(self.camera_times), rate(self.detection_times)
            camera_alive = bool(self.camera_times and now - self.camera_times[-1] < self.STALE)
            detector_alive = bool(self.detection_times and now - self.detection_times[-1] < self.STALE)
            center = self.center if (
                camera_alive and detector_alive and self.detected
                and now - self.position_time < self.STALE) else None
            return dict(fps=fps, dfps=dfps, width=self.width, height=self.height,
                        center=center, camera_alive=camera_alive,
                        detector_alive=detector_alive)


def create_app(status, video_port=8080, image_topic='/camera_node/image_raw'):
    app = Flask(__name__)

    @app.get('/')
    def index():
        return render_template('index.html', video_port=video_port, image_topic=image_topic)

    @app.get('/api/status')
    def api_status():
        response = jsonify(status.snapshot())
        response.headers['Cache-Control'] = 'no-store'
        return response

    return app

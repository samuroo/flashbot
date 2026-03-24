from flask import Flask, Response
from picamera2 import Picamera2
from libcamera import Transform
import cv2

app = Flask(__name__)

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 360), "format": "RGB888"},
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(config)
picam2.start()


def generate_frames():
    while True:
        frame = picam2.capture_array()

        # Picamera2 gives RGB, but OpenCV usually expects BGR for encoding
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return """
    <html>
        <body>
            <h1>Pi Camera Stream</h1>
            <img src="/video_feed">
        </body>
    </html>
    """


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
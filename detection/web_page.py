from flask import Flask, Response
import cv2

app = Flask(__name__)

camera = cv2.VideoCapture(0)  # 0 = default camera

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break

        # encode frame as JPEG
        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        # stream frame in MJPEG format
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

# flask loop requests / and then runs index()
@app.route("/")
def index():
    return """
    <html>
        <body>
            <img src="/video_feed">
        </body>
    </html>
    """

# now flask makes second request for the /video_feed, in the main index image code
@app.route("/video_feed")
def video_feed():
    # we are now returning  a STREAM (Response with a generator)
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
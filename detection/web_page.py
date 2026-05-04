import time

from flask import Flask, Response, redirect, url_for

from detection.frame_hub import get_jpeg_frame

app = Flask(__name__)

# ask for frames from the common frame_hub threading link
def generate_frames():
    while True:
        frame_bytes = get_jpeg_frame()
        if frame_bytes is None:
            time.sleep(0.05)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return """
    <html>
        <body style="
            margin: 0;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #111;
        ">
            <img src="/video_feed" style="
                max-width: 100%;
                max-height: 100%;
            ">
        </body>
    </html>
    """

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


def start_web_server(host="0.0.0.0", port=5000):
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    print("Starting web stream server")
    start_web_server()

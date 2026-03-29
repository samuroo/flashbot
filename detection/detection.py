import os

import cv2
import numpy as np


# ---- Paths (works no matter where you run from) ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(BASE_DIR, "yolo-fastest-1.1.cfg")
WEIGHTS = os.path.join(BASE_DIR, "yolo-fastest-1.1.weights")
NAMES = os.path.join(BASE_DIR, "coco.names")

# ---- Load YOLO ----
net = cv2.dnn.readNet(WEIGHTS, CFG)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

with open(NAMES, "r") as f:
    classes = [line.strip() for line in f.readlines()]
PERSON_ID = classes.index("person")

layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]

# ---- Camera ----
camera = None
camera_mode = None


def setup_camera(mode="pi", camera_index=0):
    global camera, camera_mode

    if camera is not None and camera_mode == mode:
        return

    stop_camera()

    if mode == "testing":
        cam = cv2.VideoCapture(camera_index)
        if not cam.isOpened():
            raise RuntimeError("Could not open computer camera.")
        camera = cam
        camera_mode = "testing"
        return

    from picamera2 import Picamera2
    from libcamera import Transform

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (640, 360), "format": "RGB888"},
        transform=Transform(hflip=True, vflip=True)
    )
    picam2.configure(config)
    picam2.start()
    camera = picam2
    camera_mode = "pi"


def stop_camera():
    global camera, camera_mode

    if camera is None:
        return

    if camera_mode == "testing":
        camera.release()
    else:
        camera.stop()

    camera = None
    camera_mode = None


def capture_frame():
    if camera is None:
        setup_camera()

    if camera_mode == "testing":
        success, frame = camera.read()
        if not success:
            raise RuntimeError("Could not read frame from computer camera.")
        return frame

    frame_rgb = camera.capture_array()
    return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)


def detect_largest_person(img_bgr=None, conf_th=0.5, nms_th=0.4, debug=False):
    if not debug:
        img_bgr = capture_frame()

    h, w = img_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(img_bgr, 1 / 255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)

    boxes, confs = [], []

    for out in outputs:
        for det in out:
            scores = det[5:]
            class_id = int(np.argmax(scores))
            conf = float(scores[class_id])
            if class_id == PERSON_ID and conf > conf_th:
                cx = int(det[0] * w)
                cy = int(det[1] * h)
                bw = int(det[2] * w)
                bh = int(det[3] * h)
                x = int(cx - bw / 2)
                y = int(cy - bh / 2)
                boxes.append([x, y, bw, bh])
                confs.append(conf)

    idxs = cv2.dnn.NMSBoxes(boxes, confs, conf_th, nms_th)
    if len(idxs) == 0:
        return None

    best = None
    best_area = -1
    for i in idxs.flatten():
        x, y, bw, bh = boxes[i]
        area = bw * bh
        if area > best_area:
            best_area = area
            best = (x, y, x + bw, y + bh, confs[i], area)

    x1, y1, x2, y2, conf, area = best
    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    return {"bbox": (x1, y1, x2, y2), "center": (cx, cy), "conf": conf, "area": area}


def draw_detection(frame, det):
    if det is None:
        return frame

    x1, y1, x2, y2 = det["bbox"]
    cx, cy = det["center"]

    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
    cv2.putText(
        frame,
        f"person {det['conf']:.2f}",
        (x1, max(20, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2
    )
    return frame


if __name__ == "__main__":
    try:
        setup_camera()
        while True:
            img = capture_frame()

            det = detect_largest_person(img, debug=True)
            if det is None:
                print("People: 0")
            else:
                x1, y1, x2, y2 = det["bbox"]
                cx, cy = det["center"]
                print(f"People: 1  bbox=({x1},{y1},{x2},{y2})  center=({cx},{cy})  conf={det['conf']:.2f}")

    except KeyboardInterrupt:
        pass
    finally:
        stop_camera()

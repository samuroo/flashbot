import os
import cv2
import numpy as np
from picamera2 import Picamera2


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
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 360), "format": "RGB888"}))
picam2.start()

def detect_largest_person(img_bgr=None, conf_th=0.5, nms_th=0.4, debug=False):
    if not debug:
        frame_rgb = picam2.capture_array()
        img_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    h, w = img_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(img_bgr, 1/255.0, (416, 416), swapRB=True, crop=False)
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
        return None  # no person

    # pick largest area among kept boxes
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


if __name__ == "__main__":
    try:
        while True:
            frame_rgb = picam2.capture_array()
            img = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

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
        picam2.stop()



# import cv2
# import numpy as np
# from picamera2 import Picamera2
# from cvzone import FaceDetectionModule
# import serial
# import time

# # Initialize the Pi Camera 3
# picam2 = Picamera2()
# picam2.configure(picam2.create_preview_configuration(main={"size": (1280, 720)}))  # HD resolution
# picam2.start()


# ser = serial.Serial('/dev/ttyACM0', 115200)  # Adjust to your Arduino port
# time.sleep(2)  # Allow time for initialization

# # Initialize face detector
# face_detector = FaceDetectionModule.FaceDetector()

# # Load YOLO-Fastest model and COCO class labels
# net = cv2.dnn.readNet("yolo-fastest-1.1.weights", "yolo-fastest-1.1.cfg")
# net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
# net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

# with open("coco.names", "r") as f:
#     classes = [line.strip() for line in f.readlines()]
# person_class_id = classes.index("person")

# layer_names = net.getLayerNames()
# output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]

# def get_closest_face_coordinates():
#     """
#     Captures a frame, detects faces, and returns:
#     - num_faces
#     - (x, y) of largest face (center)
#     - face area
#     Returns zeros if no faces found.
#     """

#     frame = picam2.capture_array()
#     img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
#     img, list_faces = face_detector.findFaces(img)

#     if list_faces:
#         largest_face = None
#         largest_area = 0
#         center_x = 0
#         center_y = 0

#         for face in list_faces:
#             x, y, w, h = face["bbox"]
#             area = w * h
#             if area > largest_area:
#                 largest_area = area
#                 center_x = x + w // 2
#                 center_y = y + h // 2

#         return len(list_faces), center_x, center_y, largest_area

#     return 0, 0, 0, 0

# def get_closest_person_coordinates():
#     frame = picam2.capture_array()
#     img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

#     height, width = img.shape[:2]
#     blob = cv2.dnn.blobFromImage(img, 1/255.0, (416, 416), swapRB=True, crop=False)
#     net.setInput(blob)
#     outputs = net.forward(output_layers)

#     people = []
#     boxes = []
#     confidences = []

#     for out in outputs:
#         for detection in out:
#             scores = detection[5:]
#             class_id = np.argmax(scores)
#             confidence = scores[class_id]

#             if confidence > 0.5 and class_id == person_class_id:
#                 center_x = int(detection[0] * width)
#                 center_y = int(detection[1] * height)
#                 w = int(detection[2] * width)
#                 h = int(detection[3] * height)

#                 x = center_x - w // 2
#                 y = center_y - h // 2
#                 boxes.append([x, y, w, h])
#                 confidences.append(float(confidence))

#     # Apply Non-Maximum Suppression
#     indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

#     for i in indices:
#         i = i[0] if isinstance(i, (list, tuple, np.ndarray)) else i
#         x, y, w, h = boxes[i]
#         area = w * h
#         x1, y1, x2, y2 = x, y, x + w, y + h
#         people.append({'box': (x1, y1, x2, y2), 'area': area})

#     if not people:
#         return 0,0,0, 0

#     # Find the closest person (largest bounding box)
#     largest = max(people, key=lambda p: p['area'])
#     x1, y1, x2, y2 = largest['box']
#     center_x = int((x1 + x2) / 2)
#     top_y = int(y1)

#     return len(people), center_x, top_y, area


# def send_data(num_faces, face_x, face_y, face_size,
#               num_bodies, body_x, body_y, body_size,
#               sound_direction, emotion):
#     data = f"{num_faces},{face_x},{face_y},{face_size}," \
#            f"{num_bodies},{body_x},{body_y},{body_size}," \
#            f"{sound_direction},{emotion}\n"
#     ser.write(data.encode())


# # Example usage
# while True:
#     num_faces, face_x, face_y, face_size = get_closest_face_coordinates()
#     num_bodies,body_x,body_y,body_size = get_closest_person_coordinates()
    
#     sound_direction = 0
#     emotion = 0
    
#     #print(f"Faces: {num_faces} at ({face_x}, {face_y}) size: {face_size} | "
#       #f"Bodies: {num_bodies} at ({body_x}, {body_y}) size: {body_size} | "
#       #f"Sound Direction: {sound_direction} | Emotion: {emotion}")

#     send_data(num_faces, face_x, face_y, face_size,
#           num_bodies, body_x, body_y, body_size,
#           sound_direction, emotion)
    
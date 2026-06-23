import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image, RegionOfInterest
from std_msgs.msg import Bool
from cv_bridge import CvBridge

from ultralytics import YOLO


class FaceDetectorNode(Node):
    def __init__(self):
        super().__init__("face_detector_node")

        self.bridge = CvBridge()
        self.model = YOLO("yolov11n-face.pt")

        self.image_sub = self.create_subscription(
            Image,
            "/camera_node/image_raw",
            self.image_callback,
            1
        )

        self.face_pub = self.create_publisher(
            Bool,
            "/face_detected",
            1
        )

        self.bbox_pub = self.create_publisher(
            RegionOfInterest,
            "/face_bbox",
            1
        )

        self.bbox_image_pub = self.create_publisher(
            Image,
            "/face_bbox_image",
            1
        )

        self.get_logger().info("Face detector node started")

    def image_callback(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

        results = self.model(
            frame,
            conf=0.2,
            imgsz=320,
            device="cpu",
            verbose=False,
        )
        boxes = results[0].boxes

        detected = boxes is not None and len(boxes) > 0
        face_box = None
        if detected:
            best_index = int(boxes.conf.argmax().item())
            best_box = boxes[best_index]
            x1, y1, x2, y2 = best_box.xyxy[0].tolist()
            face_box = (
                int(x1),
                int(y1),
                int(x2 - x1),
                int(y2 - y1),
            )

        face_detected_msg = Bool()
        face_detected_msg.data = detected
        self.face_pub.publish(face_detected_msg)

        # publish a RegionOfInterest with the first detected face (or zeros if none)
        roi = RegionOfInterest()
        if detected:
            x, y, w, h = face_box
            roi.x_offset = int(x)
            roi.y_offset = int(y)
            roi.width = int(w)
            roi.height = int(h)
            roi.do_rectify = False
            self.bbox_pub.publish(roi)
            # self.get_logger().info(f"Face detected: w={w}, h={h}")
        else:
            roi.x_offset = 0
            roi.y_offset = 0
            roi.width = 0
            roi.height = 0
            roi.do_rectify = False
            self.bbox_pub.publish(roi)

        # draw the bounding box on the image (first face) and publish it
        boxed = frame.copy()
        if detected:
            x, y, w, h = face_box
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(boxed.shape[1] - 1, x1 + int(w))
            y2 = min(boxed.shape[0] - 1, y1 + int(h))
            if x2 > x1 and y2 > y1:
                boxed[y1:y1 + 2, x1:x2] = (0, 255, 0)
                boxed[y2 - 2:y2, x1:x2] = (0, 255, 0)
                boxed[y1:y2, x1:x1 + 2] = (0, 255, 0)
                boxed[y1:y2, x2 - 2:x2] = (0, 255, 0)

        img_msg = self.bridge.cv2_to_imgmsg(boxed, encoding="bgr8")
        img_msg.header = msg.header
        self.bbox_image_pub.publish(img_msg)


def main(args=None):
    rclpy.init(args=args)
    node = FaceDetectorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image, RegionOfInterest
from std_msgs.msg import Bool
from cv_bridge import CvBridge

import cv2


class FaceDetectorNode(Node):
    def __init__(self):
        super().__init__("face_detector_node")

        self.bridge = CvBridge()

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

        self.face_cascade = cv2.CascadeClassifier(
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
        )

        self.get_logger().info("Face detector node started")

    def image_callback(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(125, 125)
        )

        detected = len(faces) > 0

        face_detected_msg = Bool()
        face_detected_msg.data = detected
        self.face_pub.publish(face_detected_msg)

        # publish a RegionOfInterest with the first detected face (or zeros if none)
        roi = RegionOfInterest()
        if detected:
            x, y, w, h = faces[0]
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
            x, y, w, h = faces[0]
            x, y, w, h = int(x), int(y), int(w), int(h)
            cv2.rectangle(boxed, (x, y), (x + w, y + h), (0, 255, 0), 2)

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
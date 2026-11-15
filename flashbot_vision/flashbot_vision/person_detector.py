"""Latest-frame person detection using the existing ROS camera and NCNN."""

from pathlib import Path
import signal
import threading
import time

from cv_bridge import CvBridge
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32MultiArray


def person_center(boxes, width, height):
    """Return the highest-confidence person's center in original image pixels."""
    people = [box for box in boxes if int(box[5]) == 0]
    if not people:
        return None
    x1, y1, x2, y2, _, _ = max(people, key=lambda box: box[4])
    return [max(0, min(width - 1, int((x1 + x2) / 2))),
            max(0, min(height - 1, int((y1 + y2) / 2)))]


class PersonDetector(Node):
    def __init__(self):
        super().__init__('person_detector')
        from ultralytics import YOLO

        model_path = Path(self.declare_parameter(
            'model', str(Path.home() / 'flashbot_ws/models/yolo26n_ncnn_model')
        ).value).expanduser()
        if not all((model_path / name).is_file()
                   for name in ('model.ncnn.param', 'model.ncnn.bin')):
            raise FileNotFoundError(f'Export the NCNN model first: {model_path}')
        self.confidence = self.declare_parameter('confidence', 0.25).value
        if not 0.0 < self.confidence <= 1.0:
            raise ValueError('confidence must be in (0, 1]')

        self.max_fps = float(self.declare_parameter('max_fps', 2.0).value)
        if self.max_fps <= 0:
            raise ValueError('max_fps must be positive')
        
        topic = self.declare_parameter('image_topic', '/camera_node/image_raw').value
        self.model = YOLO(str(model_path), task='detect')
        self.bridge = CvBridge()
        self.detected_pub = self.create_publisher(Bool, '/person_detected', 1)
        self.position_pub = self.create_publisher(Int32MultiArray, '/person_position', 1)
        self.condition = threading.Condition()
        self.latest = None
        self.stopping = False
        self.subscription = self.create_subscription(
            Image, topic, self.receive,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.worker = threading.Thread(target=self.detect, name='person-inference')
        self.worker.start()
        self.get_logger().info(f'NCNN CPU, 256x256, max_fps={self.max_fps}, confidence={self.confidence}; {topic}')

    def receive(self, message):
        last_start = 0.0

        # Overwrite the pending frame while inference runs; never enqueue frames.
        with self.condition:
            self.latest = (message, time.perf_counter())
            self.condition.notify()

    def detect(self):
        report_start = time.perf_counter()
        count = 0
        inference_total = latency_total = 0.0
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.stopping or self.latest is not None)
                if self.stopping:
                    return
                message, received = self.latest
                self.latest = None
            try:
                frame = self.bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
                started = time.perf_counter()
                result = self.model.predict(
                    frame, imgsz=256 rect=False, conf=self.confidence,
                    classes=[0], device='cpu', verbose=False)[0]
                finished = time.perf_counter()
                center = person_center(
                    result.boxes.data.cpu().numpy(), message.width, message.height)
                if self.stopping or not rclpy.ok():
                    return
                self.detected_pub.publish(Bool(data=center is not None))
                if center is not None:
                    self.position_pub.publish(Int32MultiArray(data=center))
                count += 1
                inference_total += finished - started
                latency_total += finished - received
                elapsed = finished - report_start
                if elapsed >= 5.0:
                    self.get_logger().info(
                        f'person={center is not None} center={center} '
                        f'FPS={count / elapsed:.2f} '
                        f'inference={1000 * inference_total / count:.1f}ms '
                        f'frame-to-result={1000 * latency_total / count:.1f}ms')
                    report_start = finished
                    count = 0
                    inference_total = latency_total = 0.0
            except Exception as exc:
                if self.stopping or not rclpy.ok():
                    return
                self.get_logger().error(f'Person inference failed: {exc}')
                time.sleep(1.0)

    def stop(self):
        # with self.condition:
        #     self.stopping = True
        #     self.condition.notify()
        # self.worker.join()

        with self.condition:
            self.condition.wait_for(
                lambda: self.stopping or self.latest is not None
            )
            if self.stopping:
                return

        # Limit how frequently inference starts.
        remaining = 1.0 / self.max_fps - (time.perf_counter() - last_start)
        if remaining > 0:
            time.sleep(remaining)

        # Take the newest frame AFTER waiting.
        with self.condition:
            if self.stopping:
                return
            message, received = self.latest
            self.latest = None

        last_start = time.perf_counter()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = PersonDetector()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # ros2 launch may forward SIGINT after the process group received it.
        # Let the in-flight NCNN call finish before destroying its Python state.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if node is not None:
            node.stop()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

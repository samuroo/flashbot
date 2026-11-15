"""Observe ROS topics and serve the Flask interface without processing images."""

import threading

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32MultiArray
from waitress import create_server

from flashbot_web.app import Status, create_app


class WebNode(Node):
    def __init__(self):
        super().__init__('web_node')
        self.status = Status()
        self.host = self.declare_parameter('host', '0.0.0.0').value
        self.port = self.declare_parameter('port', 5000).value
        self.video_port = self.declare_parameter('video_port', 8080).value
        self.image_topic = self.declare_parameter('image_topic', '/camera_node/image_raw').value
        self.create_subscription(
            Image, self.image_topic,
            lambda msg: self.status.camera(msg.width, msg.height),
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(Bool, '/person_detected',
                                 lambda msg: self.status.detection(msg.data), 10)
        self.create_subscription(Int32MultiArray, '/person_position',
                                 lambda msg: self.status.position(msg.data), 10)


def main(args=None):
    rclpy.init(args=args)
    node = server = worker = None
    try:
        node = WebNode()
        server = create_server(create_app(node.status, node.video_port, node.image_topic),
                               host=node.host, port=node.port, threads=2)
        worker = threading.Thread(target=server.run, name='web-http', daemon=True)
        worker.start()
        node.get_logger().info(f'Interface on port {node.port}; preview starts OFF')
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if server is not None:
            server.close()
        if worker is not None:
            worker.join(timeout=2)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

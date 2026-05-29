import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool, String
from sensor_msgs.msg import RegionOfInterest


class StateMachineNode(Node):
    def __init__(self):
        super().__init__("state_machine_node")

        self.state = "NORMAL"
        self.face_detected = False
        self.face_bbox = None

        self.face_sub = self.create_subscription(
            Bool,
            "/face_detected",
            self.face_callback,
            1
        )

        self.bbox_sub = self.create_subscription(
            RegionOfInterest,
            "/face_bbox",
            self.bbox_callback,
            1
        )

        self.command_pub = self.create_publisher(
            String,
            "/flashbot_command",
            1
        )

        self.timer = self.create_timer(0.2, self.update_state)

        self.get_logger().info("State machine node started")

    def face_callback(self, msg):
        self.face_detected = msg.data

    def bbox_callback(self, msg):
        self.face_bbox = msg

    def update_state(self):
        if self.state == "NORMAL":
            if self.face_detected:
                self.state = "FACE_SEEN"
                self.publish_command("STOP")
                self.get_logger().info("State: FACE_SEEN")

        elif self.state == "FACE_SEEN":
            self.state = "BACK_UP"
            self.publish_command("BACK_UP")
            self.get_logger().info("State: BACK_UP")

        elif self.state == "BACK_UP":
            self.state = "FLASH"
            self.publish_command("FLASH")
            self.get_logger().info("State: FLASH")

        elif self.state == "FLASH":
            self.state = "TURN"
            self.publish_command("TURN")

        elif self.state == "TURN":
            self.state = "RUN_AWAY"
            self.publish_command("RUN_AWAY")

        elif self.state == "RUN_AWAY":
            if not self.face_detected:
                self.state = "NORMAL"
                self.publish_command("NORMAL")
                self.get_logger().info("State: NORMAL")

    def publish_command(self, command):
        msg = String()
        msg.data = command
        self.command_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = StateMachineNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

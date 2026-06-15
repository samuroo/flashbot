import random
import time
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import RegionOfInterest
from std_msgs.msg import Bool, Int32MultiArray, String


class State(Enum):
    IDLE = "IDLE"
    ALIGN_FORWARD = "ALIGN_FORWARD"
    WALK_FORWARD = "WALK_FORWARD"
    STOP = "STOP"
    ALIGN_BACKWARD = "ALIGN_BACKWARD"
    WALK_BACKWARD = "WALK_BACKWARD"
    FLASH = "FLASH"
    TURN_AROUND = "TURN_AROUND"
    ALIGN_AFTER_TURN = "ALIGN_AFTER_TURN"
    ESCAPE_FORWARD = "ESCAPE_FORWARD"


class StateMachineNode(Node):
    def __init__(self):
        super().__init__("state_machine_node")

        self.declare_parameter("walk_forward_sec", 3.0)
        self.declare_parameter("backward_timeout_sec", 8.0)
        self.declare_parameter("wing_raise_sec", 0.3)
        self.declare_parameter("flash_sec", 0.5)
        self.declare_parameter("turn_timeout_sec", 8.0)
        self.declare_parameter("escape_forward_sec", 3.0)
        self.declare_parameter("align_timeout_sec", 5.0)
        self.declare_parameter("flutter_period_sec", 1.0)
        self.declare_parameter("flutter_hold_sec", 0.25)
        self.declare_parameter("wing_speed", 1000)
        self.declare_parameter("left_wing_rest", 1000)
        self.declare_parameter("right_wing_rest", 50)
        self.declare_parameter("left_wing_open", 700)
        self.declare_parameter("right_wing_open", 350)
        self.declare_parameter("wing_flutter_units", 20)

        self.state = State.IDLE
        self.state_entered_at = time.monotonic()
        self.arduino_ready = False
        self.face_detected = False
        self.face_armed = True
        self.face_bbox = None
        self.aligned = False
        self.backward_done = False
        self.turn_done = False
        self.flutter_left = True
        self.flutter_active = False
        self.flash_active = False
        self.last_flutter_at = self.state_entered_at

        ready_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            Bool,
            "/flashbot/arduino_ready",
            self.ready_callback,
            ready_qos,
        )
        self.create_subscription(
            Bool,
            "/face_detected",
            self.face_callback,
            1,
        )
        self.create_subscription(
            RegionOfInterest,
            "/face_bbox",
            self.bbox_callback,
            1,
        )
        self.create_subscription(
            Bool,
            "/flashbot/events/aligned",
            self.aligned_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/flashbot/events/turn_done",
            self.turn_done_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/flashbot/events/backward_done",
            self.backward_done_callback,
            10,
        )

        self.drive_pub = self.create_publisher(
            String,
            "/flashbot/cmd/drive",
            10,
        )
        self.left_wing_pub = self.create_publisher(
            Int32MultiArray,
            "/flashbot/cmd/wing_left",
            10,
        )
        self.right_wing_pub = self.create_publisher(
            Int32MultiArray,
            "/flashbot/cmd/wing_right",
            10,
        )
        self.flash_pub = self.create_publisher(
            Bool,
            "/flashbot/cmd/flash",
            10,
        )
        self.state_pub = self.create_publisher(
            String,
            "/flashbot/state",
            10,
        )
        self.command_pub = self.create_publisher(
            String,
            "/flashbot_command",
            10,
        )

        self.timer = self.create_timer(0.05, self.update_state)
        self.publish_state()
        self.get_logger().info("State machine started in IDLE")

    def parameter(self, name):
        return self.get_parameter(name).value

    def ready_callback(self, msg):
        self.arduino_ready = msg.data

    def face_callback(self, msg):
        self.face_detected = msg.data
        if not msg.data:
            self.face_armed = True

    def bbox_callback(self, msg):
        self.face_bbox = msg

    def aligned_callback(self, msg):
        if msg.data:
            self.aligned = True

    def turn_done_callback(self, msg):
        if msg.data:
            self.turn_done = True

    def backward_done_callback(self, msg):
        if msg.data:
            self.backward_done = True

    def update_state(self):
        if not self.arduino_ready:
            if self.state != State.IDLE:
                self.get_logger().warn(
                    "Arduino unavailable; returning to IDLE"
                )
                self.enter_state(State.IDLE)
            return

        if self.state == State.IDLE:
            self.enter_state(State.ALIGN_FORWARD)
            return

        elapsed = time.monotonic() - self.state_entered_at

        if self.state == State.ALIGN_FORWARD:
            if self.aligned:
                self.enter_state(State.WALK_FORWARD)
            elif elapsed >= self.parameter("align_timeout_sec"):
                self.get_logger().warn(
                    "Initial leg alignment timed out; stopping"
                )
                self.enter_state(State.STOP)

        elif self.state == State.WALK_FORWARD:
            if elapsed >= self.parameter("walk_forward_sec"):
                self.enter_state(State.STOP)

        elif self.state == State.STOP:
            if self.face_detected and self.face_armed:
                self.face_armed = False
                self.enter_state(State.ALIGN_BACKWARD)
            else:
                self.update_flutter()

        elif self.state == State.ALIGN_BACKWARD:
            if self.aligned:
                self.enter_state(State.WALK_BACKWARD)
            elif elapsed >= self.parameter("align_timeout_sec"):
                self.get_logger().warn(
                    "Backward alignment timed out; stopping"
                )
                self.enter_state(State.STOP)

        elif self.state == State.WALK_BACKWARD:
            if self.backward_done:
                self.enter_state(State.FLASH)
            elif elapsed >= self.parameter("backward_timeout_sec"):
                self.get_logger().warn(
                    "Hall-counted backward motion timed out; stopping"
                )
                self.enter_state(State.STOP)

        elif self.state == State.FLASH:
            wing_raise_sec = self.parameter("wing_raise_sec")
            if not self.flash_active and elapsed >= wing_raise_sec:
                self.publish_flash(True)
                self.flash_active = True
            if elapsed >= wing_raise_sec + self.parameter("flash_sec"):
                self.enter_state(State.TURN_AROUND)

        elif self.state == State.TURN_AROUND:
            if self.turn_done:
                self.enter_state(State.ALIGN_AFTER_TURN)
            elif elapsed >= self.parameter("turn_timeout_sec"):
                self.get_logger().warn(
                    "Turn timed out; stopping"
                )
                self.enter_state(State.STOP)

        elif self.state == State.ALIGN_AFTER_TURN:
            if self.aligned:
                self.enter_state(State.ESCAPE_FORWARD)
            elif elapsed >= self.parameter("align_timeout_sec"):
                self.get_logger().warn(
                    "Post-turn alignment timed out; stopping"
                )
                self.enter_state(State.STOP)

        elif self.state == State.ESCAPE_FORWARD:
            if elapsed >= self.parameter("escape_forward_sec"):
                self.enter_state(State.STOP)

    def enter_state(self, state):
        self.state = state
        self.state_entered_at = time.monotonic()
        self.aligned = False
        self.backward_done = False
        self.turn_done = False
        self.flutter_active = False
        self.flash_active = False

        if state == State.IDLE:
            self.publish_drive("STOP")
            self.publish_flash(False)
            self.publish_wings_at_rest()
        elif state == State.ALIGN_FORWARD:
            self.publish_flash(False)
            self.publish_wings_at_rest()
            self.publish_drive("ALIGN_FORWARD")
        elif state == State.ALIGN_AFTER_TURN:
            self.publish_drive("ALIGN_FORWARD")
        elif state == State.ALIGN_BACKWARD:
            self.publish_flash(False)
            self.publish_wings_at_rest()
            self.publish_drive("ALIGN_BACKWARD")
        elif state in (State.WALK_FORWARD, State.ESCAPE_FORWARD):
            self.publish_drive("FORWARD")
        elif state == State.STOP:
            self.publish_drive("STOP")
            self.publish_wings_at_rest()
            self.last_flutter_at = self.state_entered_at
        elif state == State.WALK_BACKWARD:
            self.publish_flash(False)
            self.publish_wings_at_rest()
            self.publish_drive("BACKWARD_COUNTED")
        elif state == State.FLASH:
            self.publish_drive("STOP")
            self.publish_wings(
                self.parameter("left_wing_open"),
                self.parameter("right_wing_open"),
            )
            self.publish_flash(False)
        elif state == State.TURN_AROUND:
            self.publish_flash(False)
            self.publish_wings_at_rest()
            direction = random.choice(("TURN_LEFT", "TURN_RIGHT"))
            self.publish_drive(direction)

        self.publish_state()
        self.get_logger().info(f"State: {state.value}")

    def update_flutter(self):
        now = time.monotonic()
        flutter_period = self.parameter("flutter_period_sec")
        flutter_hold = self.parameter("flutter_hold_sec")

        if self.flutter_active:
            if now - self.last_flutter_at >= flutter_hold:
                self.publish_wings_at_rest()
                self.flutter_active = False
            return

        if now - self.last_flutter_at < flutter_period:
            return

        left_rest = self.parameter("left_wing_rest")
        right_rest = self.parameter("right_wing_rest")
        flutter_units = self.parameter("wing_flutter_units")
        if self.flutter_left:
            self.publish_wings(left_rest - flutter_units, right_rest)
        else:
            self.publish_wings(left_rest, right_rest + flutter_units)

        self.flutter_left = not self.flutter_left
        self.flutter_active = True
        self.last_flutter_at = now

    def publish_drive(self, command):
        msg = String()
        msg.data = command
        self.drive_pub.publish(msg)

        compatibility_msg = String()
        compatibility_msg.data = command
        self.command_pub.publish(compatibility_msg)

    def publish_flash(self, enabled):
        msg = Bool()
        msg.data = enabled
        self.flash_pub.publish(msg)

    def publish_wings_at_rest(self):
        self.publish_wings(
            self.parameter("left_wing_rest"),
            self.parameter("right_wing_rest"),
        )

    def publish_wings(self, left_position, right_position):
        speed = int(self.parameter("wing_speed"))

        left_msg = Int32MultiArray()
        left_msg.data = [int(left_position), speed]
        self.left_wing_pub.publish(left_msg)

        right_msg = Int32MultiArray()
        right_msg.data = [int(right_position), speed]
        self.right_wing_pub.publish(right_msg)

    def publish_state(self):
        msg = String()
        msg.data = self.state.value
        self.state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = StateMachineNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

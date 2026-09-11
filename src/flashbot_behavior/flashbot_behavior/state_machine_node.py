import random
import time
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Int32, Int32MultiArray, String

from sensor_msgs.msg import RegionOfInterest


class State(Enum):
    IDLE = "IDLE"
    ALIGN_FORWARD = "ALIGN_FORWARD"
    WALK_FORWARD = "WALK_FORWARD"
    STOP = "STOP"
    WALK_BACKWARD = "WALK_BACKWARD"
    FLASH = "FLASH"
    TURN_AROUND = "TURN_AROUND"
    RAISE_WINGS = "RAISE_WINGS"


class StateMachineNode(Node):
    def __init__(self):
        super().__init__("state_machine_node")

        self.drive_speed = 400             # Signed PWM magnitude for walking and turning.
        self.hall_ignore_sec = 0.5          # Ignore initial crossings after starting movement.
        self.wing_raise_sec = 0.3           # Seconds to wait after raising wings before flash.
        self.flash_sec = 0.5                # Seconds to keep the flash on.
        self.wing_speed = 1000              # Speed used for wing servo position commands.
        self.left_wing_rest = 1000          # Left wing resting servo position.
        self.right_wing_rest = 50           # Right wing resting servo position.
        self.left_wing_open = 700           # Left wing open position for flash.
        self.right_wing_open = 350          # Right wing open position for flash.

        self.min_face_width = 50
        self.min_face_height = 100

        self.state = State.IDLE
        self.state_entered_at = time.monotonic()
        self.arduino_alive = False
        self.face_detected = False
        self.aligned = False
        self.left_bumper_pressed = False
        self.right_bumper_pressed = False
        self.stop_wait_sec = 0.0
        self.after_walk = State.STOP
        self.turn_direction = "TURN_LEFT"
        self.turn_hall_target = 1
        self.hall_target = 0
        self.hall_counts = [0, 0]
        self.hall_count_after = 0.0

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
        # self.create_subscription(
        #     Bool,
        #     "/face_detected",
        #     self.face_callback,
        #     1,
        # )
        self.create_subscription(
            RegionOfInterest,
            "/face_bbox",
            self.face_bbox_callback,
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
            "/flashbot/events/hall_left",
            self.left_hall_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/flashbot/events/limit_left",
            self.left_bumper_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/flashbot/events/limit_right",
            self.right_bumper_callback,
            10,
        )

        self.drive_pub = self.create_publisher(
            String,
            "/flashbot/cmd/drive",
            10,
        )
        self.left_servo_pub = self.create_publisher(
            Int32, "/flashbot/cmd/servo_left", 10,
        )
        self.right_servo_pub = self.create_publisher(
            Int32, "/flashbot/cmd/servo_right", 10,
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
        self.timer = self.create_timer(0.05, self.update_state)
        self.create_subscription(
            Bool,
            "/flashbot/events/hall_right",
            self.right_hall_callback,
            10,
        )
        self.publish_state()
        self.get_logger().info("State machine started in IDLE")

    def ready_callback(self, msg):
        self.arduino_alive = msg.data

    # def face_callback(self, msg):
    #     self.face_detected = msg.data
    def face_bbox_callback(self, msg):
        self.face_detected = (
            msg.width >= self.min_face_width
            and msg.height >= self.min_face_height
        )

    def aligned_callback(self, msg):
        if msg.data:
            self.aligned = True

    def left_hall_callback(self, msg):
        self.count_hall(0, msg.data)

    def right_hall_callback(self, msg):
        self.count_hall(1, msg.data)

    def count_hall(self, side, triggered):
        # Every True message is a crossing; False is the bridge's pulse reset.
        if not triggered or not self.arduino_alive or self.hall_target == 0:
            return
        if time.monotonic() < self.hall_count_after:
            return
        if self.hall_counts[side] >= self.hall_target:
            return
        self.hall_counts[side] += 1
        if self.hall_counts[side] == self.hall_target:
            publisher = self.left_servo_pub if side == 0 else self.right_servo_pub
            self.publish_servo(publisher, 0)

    def left_bumper_callback(self, msg):
        self.left_bumper_pressed = msg.data

    def right_bumper_callback(self, msg):
        self.right_bumper_pressed = msg.data

    def update_state(self):
        if not self.arduino_alive:
            if self.state != State.IDLE:
                self.get_logger().warn("Arduino unavailable; returning to IDLE")
                self.enter_state(State.IDLE)
            return

        # redundant state right now, but might be useful for future IDLE behavior
        if self.state == State.IDLE:
            self.enter_state(State.ALIGN_FORWARD)
            return

        elapsed = time.monotonic() - self.state_entered_at

        if self.state == State.ALIGN_FORWARD:
            if self.aligned:
                self.enter_state(State.STOP)

        elif self.state == State.STOP:
            if self.left_bumper_pressed or self.right_bumper_pressed:
                direction = "TURN_LEFT" if self.left_bumper_pressed else "TURN_RIGHT"
                self.start_turn(direction, 1)
            elif self.face_detected:
                self.after_walk = State.RAISE_WINGS
                self.enter_state(State.WALK_BACKWARD)
            elif elapsed >= self.stop_wait_sec:
                movement = random.choice((
                    State.WALK_FORWARD, State.WALK_BACKWARD, State.TURN_AROUND,
                ))
                if movement == State.TURN_AROUND:
                    self.start_turn(random.choice(("TURN_LEFT", "TURN_RIGHT")), 1)
                else:
                    self.after_walk = State.STOP
                    self.enter_state(movement)

        elif self.state in (State.WALK_FORWARD, State.WALK_BACKWARD):
            if all(count >= self.hall_target for count in self.hall_counts):
                self.enter_state(self.after_walk)

        elif self.state == State.RAISE_WINGS:
            if elapsed >= self.wing_raise_sec:
                self.enter_state(State.FLASH)

        elif self.state == State.FLASH:
            if elapsed >= self.flash_sec:
                self.start_turn(random.choice(("TURN_LEFT", "TURN_RIGHT")), 2)

        elif self.state == State.TURN_AROUND:
            if all(count >= self.hall_target for count in self.hall_counts):
                self.enter_state(State.STOP)

    def start_turn(self, direction, hall_target):
        self.turn_direction = direction
        self.turn_hall_target = hall_target
        self.enter_state(State.TURN_AROUND)

    def start_counted_motion(self, left_speed, right_speed, hall_target):
        self.hall_target = hall_target
        self.hall_counts = [0, 0]
        self.hall_count_after = time.monotonic() + self.hall_ignore_sec
        self.publish_speeds(left_speed, right_speed)

    def enter_state(self, state):
        self.state = state
        self.state_entered_at = time.monotonic()
        self.aligned = False
        self.hall_target = 0

        if state == State.IDLE:
            self.publish_speeds(0, 0)
            self.publish_flash(False)
            self.publish_wings_at_rest()
        elif state == State.ALIGN_FORWARD:
            self.publish_drive("ALIGN_FORWARD")
        elif state == State.WALK_FORWARD:
            self.start_counted_motion(self.drive_speed, -self.drive_speed, 1)
        elif state == State.WALK_BACKWARD:
            self.start_counted_motion(-self.drive_speed, self.drive_speed, 1)
        elif state == State.STOP:
            self.stop_wait_sec = random.uniform(15.0, 30.0)
            self.publish_speeds(0, 0)
            self.publish_wings_at_rest()
        elif state == State.RAISE_WINGS:
            self.publish_speeds(0, 0)
            self.publish_wings(self.left_wing_open, self.right_wing_open)
        elif state == State.FLASH:
            self.publish_flash(True)
        elif state == State.TURN_AROUND:
            self.publish_flash(False)
            self.publish_wings_at_rest()
            speed = -self.drive_speed if self.turn_direction == "TURN_LEFT" else self.drive_speed
            self.start_counted_motion(speed, speed, self.turn_hall_target)

        self.publish_state()
        self.get_logger().info(f"State: {state.value}")

    @staticmethod
    def publish_servo(publisher, speed):
        msg = Int32()
        msg.data = int(speed)
        publisher.publish(msg)

    def publish_speeds(self, left_speed, right_speed):
        self.publish_servo(self.left_servo_pub, left_speed)
        self.publish_servo(self.right_servo_pub, right_speed)

    def publish_drive(self, command):
        msg = String()
        msg.data = command
        self.drive_pub.publish(msg)

    def publish_flash(self, enabled):
        msg = Bool()
        msg.data = enabled
        self.flash_pub.publish(msg)

    def publish_wings_at_rest(self):
        self.publish_wings(
            self.left_wing_rest,
            self.right_wing_rest,
        )

    def publish_wings(self, left_position, right_position):
        speed = int(self.wing_speed)

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

import random
import time
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Int32MultiArray, String


class State(Enum):
    IDLE = "IDLE"
    ALIGN_FORWARD = "ALIGN_FORWARD"
    WALK_FORWARD = "WALK_FORWARD"
    STOP = "STOP"
    ALIGN_BACKWARD = "ALIGN_BACKWARD"
    FLASH = "FLASH"
    TURN_AROUND = "TURN_AROUND"
    RAISE_WINGS = "RAISE_WINGS"


class StateMachineNode(Node):
    def __init__(self):
        super().__init__("state_machine_node")

        self.walk_forward_sec = 4.0         # Seconds to walk forward before stopping.
        self.wing_raise_sec = 0.3           # Seconds to wait after raising wings before flash.
        self.flash_sec = 0.5                # Seconds to keep the flash on.
        self.wing_speed = 1000              # Speed used for wing servo position commands.
        self.left_wing_rest = 1000          # Left wing resting servo position.
        self.right_wing_rest = 50           # Right wing resting servo position.
        self.left_wing_open = 700           # Left wing open position for flash.
        self.right_wing_open = 350          # Right wing open position for flash.

        self.state = State.IDLE
        self.state_entered_at = time.monotonic()
        self.arduino_alive = False
        self.face_detected = False
        self.aligned = False
        self.turn_done = False
        self.left_bumper_pressed = False
        self.right_bumper_pressed = False
        self.turn_from_walk_forward = False
        self.turn_from_stop = False
        self.turn_from_stop_direction = None

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
        self.publish_state()
        self.get_logger().info("State machine started in IDLE")

    def ready_callback(self, msg):
        self.arduino_alive = msg.data

    def face_callback(self, msg):
        self.face_detected = msg.data

    def aligned_callback(self, msg):
        if msg.data:
            self.aligned = True

    def turn_done_callback(self, msg):
        if msg.data:
            self.turn_done = True

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
        bumper_pressed = self.left_bumper_pressed or self.right_bumper_pressed

        # align forward
        if self.state == State.ALIGN_FORWARD:
            if self.aligned:
                self.enter_state(State.STOP)

        # stopped
        elif self.state == State.STOP:
            # if left bumper is pressed
            if self.left_bumper_pressed:
                self.turn_from_stop = True
                self.turn_from_stop_direction = "TURN_LEFT"
                self.enter_state(State.TURN_AROUND)

            # if right bumper is pressed
            elif self.right_bumper_pressed:
                self.turn_from_stop = True
                self.turn_from_stop_direction = "TURN_RIGHT"
                self.enter_state(State.TURN_AROUND)

            # if face detected
            elif self.face_detected:
                self.enter_state(State.ALIGN_BACKWARD)

        # align backward
        elif self.state == State.ALIGN_BACKWARD:
            # hall effects are lined up
            # if self.aligned:
                # needs to align backward before turning around
            if self.turn_from_walk_forward:
                self.enter_state(State.TURN_AROUND)
            # move onto rasing wings
            else:
                self.enter_state(State.RAISE_WINGS)

        # raise wings
        elif self.state == State.RAISE_WINGS:
            if elapsed >= self.wing_raise_sec:
                self.enter_state(State.FLASH)

        # flash
        elif self.state == State.FLASH:
            if elapsed >= self.flash_sec:
                self.enter_state(State.TURN_AROUND)

        # turning
        elif self.state == State.TURN_AROUND:
            # on arudino -> when both legs have done 2 hall-sensor events
            if self.turn_done:
                # if the bumper was hit when in STOP (kinda emergency mode)
                if self.turn_from_stop:
                    self.turn_from_stop = False
                    self.turn_from_stop_direction = None
                    self.enter_state(State.STOP)

                # if the bumper was hit while escape walking
                elif self.turn_from_walk_forward:
                    self.turn_from_walk_forward = False
                    self.enter_state(State.STOP)

                # after the turn is done otherwise, aligned already at this point
                else:
                    self.enter_state(State.WALK_FORWARD)

        # walk forward
        elif self.state == State.WALK_FORWARD:
            # if bumper is pressed when walking forward
            if bumper_pressed:
                self.turn_from_walk_forward = True
                self.enter_state(State.ALIGN_BACKWARD)

            # walking forward elapsed time
            elif elapsed >= self.walk_forward_sec:
                self.enter_state(State.STOP)


    def enter_state(self, state):
        self.state = state
        self.state_entered_at = time.monotonic()
        self.aligned = False
        self.turn_done = False

        if state == State.IDLE:
            self.publish_drive("STOP")
            self.publish_flash(False)
            self.publish_wings_at_rest()
        elif state == State.ALIGN_FORWARD:
            self.publish_drive("ALIGN_FORWARD")
        elif state == State.ALIGN_BACKWARD:
            self.publish_wings_at_rest()
            self.publish_drive("ALIGN_BACKWARD")
        elif state == State.WALK_FORWARD:
            self.publish_drive("FORWARD")
        elif state == State.STOP:
            self.publish_drive("STOP")
            self.publish_wings_at_rest()
        elif state == State.RAISE_WINGS:
            self.publish_drive("STOP")
            self.publish_wings(self.left_wing_open, self.right_wing_open)
        elif state == State.FLASH:
            self.publish_flash(True)
        elif state == State.TURN_AROUND:
            self.publish_flash(False)
            self.publish_wings_at_rest()

            direction = self.turn_from_stop_direction
            if direction is None:
                direction = random.choice(("TURN_LEFT", "TURN_RIGHT"))
            self.publish_drive(direction)

        self.publish_state()
        self.get_logger().info(f"State: {state.value}")

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

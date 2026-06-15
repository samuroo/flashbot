import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Int32, Int32MultiArray, String

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - handled at runtime with a clear log.
    serial = None
    SerialException = Exception


class FlashbotSerialNode(Node):
    def __init__(self):
        super().__init__("flashbot_serial_node")

        self.declare_parameter("port", "/dev/ttyACM0")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("reconnect_period_sec", 1.0)
        self.declare_parameter("hello_period_sec", 1.0)
        self.declare_parameter("ready_timeout_sec", 3.0)
        self.declare_parameter("hello_command", "CMD,hello")
        self.declare_parameter("hall_pulse_sec", 0.1)

        self.port = self.get_parameter("port").value
        self.baud_rate = int(self.get_parameter("baud_rate").value)
        self.reconnect_period_sec = float(
            self.get_parameter("reconnect_period_sec").value
        )
        self.hello_period_sec = float(
            self.get_parameter("hello_period_sec").value
        )
        self.ready_timeout_sec = float(
            self.get_parameter("ready_timeout_sec").value
        )
        self.hello_command = self.get_parameter("hello_command").value
        self.hall_pulse_sec = float(self.get_parameter("hall_pulse_sec").value)

        self.serial_handle = None
        self.last_connect_attempt = 0.0
        self.last_hello_sent = 0.0
        self.last_ready_received = 0.0
        self.arduino_ready = False
        self.hall_left_false_at = None
        self.hall_right_false_at = None

        ready_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.ready_pub = self.create_publisher(
            Bool,
            "/flashbot/arduino_ready",
            ready_qos,
        )
        self.hall_left_pub = self.create_publisher(
            Bool,
            "/flashbot/events/hall_left",
            10,
        )
        self.hall_right_pub = self.create_publisher(
            Bool,
            "/flashbot/events/hall_right",
            10,
        )
        self.limit_left_pub = self.create_publisher(
            Bool,
            "/flashbot/events/limit_left",
            10,
        )
        self.limit_right_pub = self.create_publisher(
            Bool,
            "/flashbot/events/limit_right",
            10,
        )
        self.aligned_pub = self.create_publisher(
            Bool,
            "/flashbot/events/aligned",
            10,
        )
        self.turn_done_pub = self.create_publisher(
            Bool,
            "/flashbot/events/turn_done",
            10,
        )

        self.create_subscription(
            String,
            "/flashbot/cmd/drive",
            self.drive_callback,
            10,
        )
        self.create_subscription(
            Int32MultiArray,
            "/flashbot/cmd/wing_left",
            self.wing_left_callback,
            10,
        )
        self.create_subscription(
            Int32MultiArray,
            "/flashbot/cmd/wing_right",
            self.wing_right_callback,
            10,
        )
        self.create_subscription(
            Int32,
            "/flashbot/cmd/servo_left",
            self.servo_left_callback,
            10,
        )
        self.create_subscription(
            Int32,
            "/flashbot/cmd/servo_right",
            self.servo_right_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/flashbot/cmd/flash",
            self.flash_callback,
            10,
        )

        self.timer = self.create_timer(0.05, self.timer_callback)
        self.publish_ready(False)
        self.get_logger().info(
            "Flashbot serial node started, "
            f"port={self.port}, baud={self.baud_rate}"
        )

    def drive_callback(self, msg):
        command = msg.data.strip().upper()
        valid_commands = {
            "STOP",
            "ALIGN_FORWARD",
            "FORWARD",
            "BACKWARD",
            "TURN_LEFT",
            "TURN_RIGHT",
        }
        if command not in valid_commands:
            self.get_logger().warn(
                f"Ignoring invalid drive command: {msg.data}"
            )
            return
        self.write_command(f"CMD,drive,{command}")

    def wing_left_callback(self, msg):
        args = self.parse_position_speed(msg, "wing_left")
        if args is not None:
            self.write_command(f"CMD,wing_left,{args[0]},{args[1]}")

    def wing_right_callback(self, msg):
        args = self.parse_position_speed(msg, "wing_right")
        if args is not None:
            self.write_command(f"CMD,wing_right,{args[0]},{args[1]}")

    def servo_left_callback(self, msg):
        self.write_command(f"CMD,servo_left,{int(msg.data)}")

    def servo_right_callback(self, msg):
        self.write_command(f"CMD,servo_right,{int(msg.data)}")

    def flash_callback(self, msg):
        if msg.data:
            self.write_command("CMD,flash_on")
        else:
            self.write_command("CMD,flash_off")

    def parse_position_speed(self, msg, name):
        if len(msg.data) < 2:
            self.get_logger().warn(
                f"Ignoring {name}: expected [position, speed], "
                f"got {list(msg.data)}"
            )
            return None

        return int(msg.data[0]), int(msg.data[1])

    def write_command(self, command):
        if self.serial_handle is None:
            self.get_logger().warn(
                f"Arduino not connected; dropped: {command}"
            )
            return
        try:
            self.serial_handle.write((command + "\n").encode("utf-8"))
            self.serial_handle.flush()
        except SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")
            self.close_serial()

    def timer_callback(self):
        if self.serial_handle is None:
            self.try_connect()
            return

        self.send_heartbeat()
        self.check_ready_timeout()

        while self.serial_handle is not None:
            try:
                raw_line = self.serial_handle.readline()
            except SerialException as exc:
                self.get_logger().warn(f"Serial read failed: {exc}")
                self.close_serial()
                return

            if not raw_line:
                self.clear_hall_pulses()
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            self.handle_event(line)

        self.clear_hall_pulses()

    def handle_event(self, line):
        if line == "EVT,ready":
            self.last_ready_received = time.monotonic()
            if not self.arduino_ready:
                self.get_logger().info("Arduino ready")
                self.publish_ready(True)
        elif line == "EVT,boot":
            self.publish_ready(False)
            self.last_hello_sent = 0.0
            self.get_logger().info("Arduino booted")
        elif line == "EVT,aligned":
            self.publish_bool(self.aligned_pub, True)
        elif line == "EVT,turn_done":
            self.publish_bool(self.turn_done_pub, True)
        elif line == "EVT,hall_left":
            self.publish_bool(self.hall_left_pub, True)
            self.hall_left_false_at = time.monotonic() + self.hall_pulse_sec
        elif line == "EVT,hall_right":
            self.publish_bool(self.hall_right_pub, True)
            self.hall_right_false_at = time.monotonic() + self.hall_pulse_sec
        elif line == "EVT,limit_bump_left":
            self.publish_bool(self.limit_left_pub, True)
        elif line == "EVT,limit_release_left":
            self.publish_bool(self.limit_left_pub, False)
        elif line == "EVT,limit_bump_right":
            self.publish_bool(self.limit_right_pub, True)
        elif line == "EVT,limit_release_right":
            self.publish_bool(self.limit_right_pub, False)
        else:
            self.get_logger().warn(f"Ignoring unknown Arduino line: {line}")

    def clear_hall_pulses(self):
        now = time.monotonic()
        if (
            self.hall_left_false_at is not None
            and now >= self.hall_left_false_at
        ):
            self.publish_bool(self.hall_left_pub, False)
            self.hall_left_false_at = None

        if (
            self.hall_right_false_at is not None
            and now >= self.hall_right_false_at
        ):
            self.publish_bool(self.hall_right_pub, False)
            self.hall_right_false_at = None

    @staticmethod
    def publish_bool(publisher, value):
        msg = Bool()
        msg.data = value
        publisher.publish(msg)

    def try_connect(self):
        now = time.monotonic()
        if now - self.last_connect_attempt < self.reconnect_period_sec:
            return
        self.last_connect_attempt = now

        if serial is None:
            self.get_logger().error(
                "pyserial is not installed. Install python3-serial "
                "or pyserial."
            )
            return

        try:
            self.serial_handle = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=0.02,
                write_timeout=0.2,
            )
            self.serial_handle.reset_input_buffer()
            self.serial_handle.reset_output_buffer()
            self.publish_ready(False)
            self.last_hello_sent = 0.0
            self.last_ready_received = 0.0
            self.get_logger().info(
                f"Connected to Arduino on {self.port}; waiting for handshake"
            )
        except SerialException as exc:
            self.serial_handle = None
            self.get_logger().warn(
                f"Waiting for Arduino on {self.port}: {exc}"
            )

    def send_heartbeat(self):
        if self.serial_handle is None:
            return

        now = time.monotonic()
        if now - self.last_hello_sent < self.hello_period_sec:
            return

        try:
            hello = (self.hello_command + "\n").encode("utf-8")
            self.serial_handle.write(hello)
            self.serial_handle.flush()
            self.last_hello_sent = now
            self.get_logger().debug(f"Sent heartbeat: {self.hello_command}")
        except SerialException as exc:
            self.get_logger().warn(f"Serial handshake failed: {exc}")
            self.close_serial()

    def check_ready_timeout(self):
        if not self.arduino_ready:
            return
        elapsed = time.monotonic() - self.last_ready_received
        if elapsed > self.ready_timeout_sec:
            self.get_logger().warn("Arduino heartbeat timed out")
            self.publish_ready(False)

    def publish_ready(self, value):
        if self.arduino_ready == value and value:
            return
        self.arduino_ready = value
        self.publish_bool(self.ready_pub, value)

    def close_serial(self):
        if self.serial_handle is not None:
            try:
                self.serial_handle.close()
            except SerialException:
                pass
        self.serial_handle = None
        self.publish_ready(False)

    def destroy_node(self):
        self.close_serial()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = FlashbotSerialNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

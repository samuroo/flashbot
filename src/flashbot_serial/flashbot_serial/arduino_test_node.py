import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - handled at runtime with a clear log.
    serial = None
    SerialException = Exception


class ArduinoTestNode(Node):
    def __init__(self):
        super().__init__("arduino_test_node")

        self.declare_parameter("port", "/dev/ttyACM0")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("reconnect_period_sec", 1.0)
        self.declare_parameter("hello_period_sec", 1.0)
        self.declare_parameter("hello_command", "CMD,HELLO")

        self.port = self.get_parameter("port").value
        self.baud_rate = int(self.get_parameter("baud_rate").value)
        self.reconnect_period_sec = float(
            self.get_parameter("reconnect_period_sec").value
        )
        self.hello_period_sec = float(self.get_parameter("hello_period_sec").value)
        self.hello_command = self.get_parameter("hello_command").value

        self.serial_handle = None
        self.last_connect_attempt = 0.0
        self.last_hello_sent = 0.0
        self.arduino_ready = False

        self.event_pub = self.create_publisher(String, "/arduino_events", 10)
        self.command_sub = self.create_subscription(
            String,
            "/arduino_commands",
            self.command_callback,
            10,
        )

        self.timer = self.create_timer(0.05, self.timer_callback)
        self.get_logger().info(
            f"Arduino test node started, port={self.port}, baud={self.baud_rate}"
        )

    def command_callback(self, msg):
        command = msg.data.strip()
        if not command:
            return

        if self.serial_handle is None:
            self.get_logger().warn(f"Arduino not connected; dropped: {command}")
            return

        try:
            self.serial_handle.write((command + "\n").encode("utf-8"))
            self.serial_handle.flush()
            self.get_logger().info(f"Sent to Arduino: {command}")
        except SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")
            self.close_serial()

    def timer_callback(self):
        if self.serial_handle is None:
            self.try_connect()
            return

        self.send_hello_until_ready()

        while self.serial_handle is not None:
            try:
                raw_line = self.serial_handle.readline()
            except SerialException as exc:
                self.get_logger().warn(f"Serial read failed: {exc}")
                self.close_serial()
                return

            if not raw_line:
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            msg = String()
            msg.data = line
            self.event_pub.publish(msg)
            self.get_logger().info(f"Received from Arduino: {line}")

            if line == "EVT,READY":
                self.arduino_ready = True
            elif line == "EVT,BOOT":
                self.arduino_ready = False
                self.last_hello_sent = 0.0

    def try_connect(self):
        now = time.monotonic()
        if now - self.last_connect_attempt < self.reconnect_period_sec:
            return
        self.last_connect_attempt = now

        if serial is None:
            self.get_logger().error(
                "pyserial is not installed. Install python3-serial or pyserial."
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
            self.arduino_ready = False
            self.last_hello_sent = 0.0
            self.get_logger().info(
                f"Connected to Arduino on {self.port}; waiting for handshake"
            )
        except SerialException as exc:
            self.serial_handle = None
            self.get_logger().warn(f"Waiting for Arduino on {self.port}: {exc}")

    def send_hello_until_ready(self):
        if self.arduino_ready or self.serial_handle is None:
            return

        now = time.monotonic()
        if now - self.last_hello_sent < self.hello_period_sec:
            return

        try:
            self.serial_handle.write((self.hello_command + "\n").encode("utf-8"))
            self.serial_handle.flush()
            self.last_hello_sent = now
            self.get_logger().info(f"Sent handshake: {self.hello_command}")
        except SerialException as exc:
            self.get_logger().warn(f"Serial handshake failed: {exc}")
            self.close_serial()

    def close_serial(self):
        if self.serial_handle is not None:
            try:
                self.serial_handle.close()
            except SerialException:
                pass
        self.serial_handle = None
        self.arduino_ready = False

    def destroy_node(self):
        self.close_serial()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ArduinoTestNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

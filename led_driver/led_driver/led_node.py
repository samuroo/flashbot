"""Control a MOSFET gate on BCM GPIO 12; never power the LED from GPIO."""

import lgpio
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import UInt8
from std_srvs.srv import Trigger


class LedNode(Node):
    PIN = 12
    PWM_HZ = 500

    def __init__(self):
        super().__init__('led_node')
        self.handle = None
        self.claimed = False
        self.pwm_active = False
        self.pwm_available = True
        chip = self.declare_parameter('gpiochip', 4).value
        try:
            self.handle = lgpio.gpiochip_open(chip)
            if lgpio.gpio_get_chip_info(self.handle)[3] != 'pinctrl-rp1':
                raise RuntimeError(f'gpiochip{chip} is not the Pi 5 RP1 controller')
            lgpio.gpio_claim_output(self.handle, self.PIN, 0)
            self.claimed = True
            self.create_service(Trigger, '/led/on', self.on)
            self.create_service(Trigger, '/led/off', self.off)
            self.create_subscription(UInt8, '/led/brightness', self.brightness, 1)
        except Exception:
            self.close_gpio()
            self.destroy_node()
            raise
        self.get_logger().info(f'LED OFF; gpiochip{chip}, BCM 12, PWM 500 Hz')

    def stop_pwm(self):
        if self.pwm_active:
            lgpio.tx_pwm(self.handle, self.PIN, 0, 0)
            self.pwm_active = False

    def set_brightness(self, value):
        if value in (0, 255):
            self.stop_pwm()
            lgpio.gpio_write(self.handle, self.PIN, int(value == 255))
            return
        if not self.pwm_available:
            raise RuntimeError('PWM unavailable; use /led/on or /led/off')
        try:
            lgpio.tx_pwm(self.handle, self.PIN, self.PWM_HZ, value * 100.0 / 255)
            self.pwm_active = True
        except (lgpio.error, AttributeError) as exc:
            self.pwm_available = False
            self.stop_pwm()
            lgpio.gpio_write(self.handle, self.PIN, 0)
            raise RuntimeError('PWM failed; LED OFF. ON/OFF still available') from exc

    def on(self, request, response):
        return self.switch(255, response)

    def off(self, request, response):
        return self.switch(0, response)

    def switch(self, value, response):
        try:
            self.set_brightness(value)
            response.success = True
            response.message = 'LED ON' if value else 'LED OFF'
        except (lgpio.error, RuntimeError) as exc:
            response.success = False
            response.message = str(exc)
        return response

    def brightness(self, message):
        try:
            self.set_brightness(message.data)
        except (lgpio.error, RuntimeError) as exc:
            self.get_logger().error(str(exc))

    def close_gpio(self):
        if self.handle is None:
            return
        # Attempt every cleanup step even if a preceding GPIO operation fails.
        if self.claimed:
            for operation in (
                self.stop_pwm,
                lambda: lgpio.gpio_write(self.handle, self.PIN, 0),
                lambda: lgpio.gpio_free(self.handle, self.PIN),
            ):
                try:
                    operation()
                except Exception as exc:
                    self.get_logger().error(f'GPIO cleanup: {exc}')
            self.claimed = False
        try:
            lgpio.gpiochip_close(self.handle)
        finally:
            self.handle = None


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = LedNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            if node is not None:
                try:
                    node.close_gpio()
                finally:
                    node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

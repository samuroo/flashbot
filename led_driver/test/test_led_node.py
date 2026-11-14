"""Check GPIO safety and ROS callbacks without driving physical hardware."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, call, patch


class TestLedNode(unittest.TestCase):
    def setUp(self):
        self.gpio = MagicMock()
        self.gpio.error = type('GPIOError', (Exception,), {})
        self.gpio.gpiochip_open.return_value = 7
        self.gpio.gpio_get_chip_info.return_value = [0, 54, 'gpiochip4', 'pinctrl-rp1']
        self.logger = MagicMock()
        logger = self.logger

        class FakeNode:
            def __init__(self, name):
                self.name = name

            def declare_parameter(self, name, default):
                return SimpleNamespace(value=default)

            def get_logger(self):
                return logger

            create_service = MagicMock()
            create_subscription = MagicMock()
            destroy_node = MagicMock()

        modules = {
            'lgpio': self.gpio,
            'rclpy': MagicMock(),
            'rclpy.node': SimpleNamespace(Node=FakeNode),
            'rclpy.executors': SimpleNamespace(ExternalShutdownException=type(
                'ExternalShutdownException', (Exception,), {})),
            'std_msgs': MagicMock(),
            'std_msgs.msg': SimpleNamespace(UInt8=object),
            'std_srvs': MagicMock(),
            'std_srvs.srv': SimpleNamespace(Trigger=object),
        }
        path = Path(__file__).parents[1] / 'led_driver' / 'led_node.py'
        spec = importlib.util.spec_from_file_location('led_node_under_test', path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', modules):
            spec.loader.exec_module(self.module)

    def test_startup_off(self):
        node = self.module.LedNode()
        self.assertEqual(node.name, 'led_node')
        self.gpio.gpio_claim_output.assert_called_once_with(7, 12, 0)
        self.gpio.tx_pwm.assert_not_called()

    def test_wrong_chip_is_released_without_claiming_pin(self):
        self.gpio.gpio_get_chip_info.return_value = [0, 32, 'gpiochip0', 'other']
        with self.assertRaises(RuntimeError):
            self.module.LedNode()
        self.gpio.gpio_claim_output.assert_not_called()
        self.gpio.gpiochip_close.assert_called_once_with(7)

    def test_pwm_and_services(self):
        node = self.module.LedNode()
        node.brightness(SimpleNamespace(data=128))
        self.gpio.tx_pwm.assert_called_with(7, 12, 500, 128 * 100.0 / 255)
        self.assertTrue(node.on(None, SimpleNamespace()).success)
        self.gpio.tx_pwm.assert_called_with(7, 12, 0, 0)
        self.gpio.gpio_write.assert_called_with(7, 12, 1)
        self.assertTrue(node.off(None, SimpleNamespace()).success)
        self.gpio.gpio_write.assert_called_with(7, 12, 0)

    def test_pwm_failure_preserves_switching(self):
        node = self.module.LedNode()
        self.gpio.tx_pwm.side_effect = self.gpio.error('not supported')
        node.brightness(SimpleNamespace(data=128))
        self.assertFalse(node.pwm_available)
        self.gpio.gpio_write.assert_called_with(7, 12, 0)
        self.assertTrue(node.on(None, SimpleNamespace()).success)
        self.assertTrue(node.off(None, SimpleNamespace()).success)

    def test_service_reports_gpio_failure(self):
        node = self.module.LedNode()
        self.gpio.gpio_write.side_effect = self.gpio.error('write failed')
        self.assertFalse(node.on(None, SimpleNamespace()).success)

    def test_shutdown_stops_pwm_then_lowers_and_releases_pin(self):
        node = self.module.LedNode()
        node.set_brightness(128)
        self.gpio.reset_mock()
        node.close_gpio()
        self.assertEqual(self.gpio.mock_calls, [
            call.tx_pwm(7, 12, 0, 0), call.gpio_write(7, 12, 0),
            call.gpio_free(7, 12), call.gpiochip_close(7),
        ])
        node.close_gpio()  # Repeated cleanup must not touch released resources.
        self.gpio.gpiochip_close.assert_called_once()

    def test_shutdown_releases_even_if_pwm_stop_fails(self):
        node = self.module.LedNode()
        node.set_brightness(128)
        self.gpio.tx_pwm.side_effect = self.gpio.error('stop failed')
        node.close_gpio()
        self.gpio.gpio_write.assert_called_with(7, 12, 0)
        self.gpio.gpio_free.assert_called_once_with(7, 12)
        self.gpio.gpiochip_close.assert_called_once_with(7)


if __name__ == '__main__':
    unittest.main()

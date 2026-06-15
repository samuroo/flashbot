from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    serial_port = LaunchConfiguration("serial_port")
    baud_rate = LaunchConfiguration("baud_rate")

    return LaunchDescription([
        DeclareLaunchArgument(
            "serial_port",
            default_value="/dev/ttyACM0",
            description="Serial port used by the Flashbot Arduino",
        ),
        DeclareLaunchArgument(
            "baud_rate",
            default_value="115200",
            description="Serial baud rate used by the Flashbot Arduino",
        ),
        Node(
            package="camera_ros",
            executable="camera_node",
            name="camera_node",
            output="screen",
        ),
        Node(
            package="flashbot_vision",
            executable="face_detector_node",
            name="face_detector_node",
            output="screen",
        ),
        Node(
            package="web_video_server",
            executable="web_video_server",
            name="web_video_server",
            output="screen",
        ),
        Node(
            package="flashbot_serial",
            executable="flashbot_serial_node",
            name="flashbot_serial_node",
            output="screen",
            parameters=[{
                "port": serial_port,
                "baud_rate": ParameterValue(baud_rate, value_type=int),
            }],
        ),
        Node(
            package="flashbot_behavior",
            executable="state_machine_node",
            name="state_machine_node",
            output="screen",
        ),
    ])

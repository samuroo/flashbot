"""Launch only the web interface; camera and detector remain independent."""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('python', default_value=str(
            Path.home() / 'flashbot_ws/src/flashbot/venv/bin/python')),
        DeclareLaunchArgument('port', default_value='5000'),
        DeclareLaunchArgument('video_port', default_value='8080'),
        DeclareLaunchArgument('image_topic', default_value='/camera_node/image_raw'),
        Node(package='flashbot_web', executable='web_node', name='web_node',
             output='screen', prefix=[LaunchConfiguration('python')], parameters=[{
                 'port': ParameterValue(LaunchConfiguration('port'), value_type=int),
                 'video_port': ParameterValue(LaunchConfiguration('video_port'), value_type=int),
                 'image_topic': LaunchConfiguration('image_topic'),
             }]),
    ])

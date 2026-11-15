"""Run person detection with the existing venv; camera is launched separately."""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    home = Path.home()
    return LaunchDescription([
        DeclareLaunchArgument('python', default_value=str(
            home / 'flashbot_ws/src/flashbot/venv/bin/python')),
        DeclareLaunchArgument('model', default_value=str(
            home / 'flashbot_ws/models/yolo26n_ncnn_model')),
        DeclareLaunchArgument('image_topic', default_value='/camera_node/image_raw'),
        DeclareLaunchArgument('confidence', default_value='0.25'),
        Node(
            package='flashbot_vision', executable='person_detector',
            name='person_detector', output='screen',
            prefix=[LaunchConfiguration('python')],
            parameters=[{
                'model': LaunchConfiguration('model'),
                'image_topic': LaunchConfiguration('image_topic'),
                'confidence': ParameterValue(LaunchConfiguration('confidence'), value_type=float),
            }],
        ),
    ])

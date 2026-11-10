"""Start the camera and browser video stream."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('camera', default_value='0',
                              description='Camera index'),
        DeclareLaunchArgument('width', default_value='640',
                              description='Image width in pixels'),
        DeclareLaunchArgument('height', default_value='480',
                              description='Image height in pixels'),
        DeclareLaunchArgument('port', default_value='8080',
                              description='HTTP video server port'),
        Node(
            package='camera_ros',
            executable='camera_node',
            name='camera_node',
            output='screen',
            parameters=[{
                key: ParameterValue(LaunchConfiguration(key), value_type=int)
                for key in ('camera', 'width', 'height')
            }],
        ),
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='web_video_server',
            output='screen',
            parameters=[{
                'port': ParameterValue(LaunchConfiguration('port'), value_type=int),
            }],
        ),
    ])

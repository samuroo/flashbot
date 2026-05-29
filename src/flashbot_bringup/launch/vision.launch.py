from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
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
    ])

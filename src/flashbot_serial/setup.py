from setuptools import find_packages, setup

package_name = "flashbot_serial"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
            ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools", "pyserial"],
    zip_safe=True,
    maintainer="flashbot",
    maintainer_email="flashbot@todo.todo",
    description="Basic ROS 2 serial test bridge for Flashbot Arduino communication.",
    license="TODO: License declaration",
    extras_require={
        "test": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "arduino_test_node = flashbot_serial.arduino_test_node:main",
        ],
    },
)

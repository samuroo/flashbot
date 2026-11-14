from setuptools import find_packages, setup

setup(
    name='led_driver',
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/led_driver']),
        ('share/led_driver', ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='flashbot-1',
    maintainer_email='flashbot-1@todo.todo',
    description='MOSFET LED control using lgpio.',
    license='Apache-2.0',
    entry_points={'console_scripts': ['led_node = led_driver.led_node:main']},
)

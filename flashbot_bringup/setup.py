from glob import glob

from setuptools import find_packages, setup

package_name = 'flashbot_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='flashbot-1',
    maintainer_email='flashbot-1@todo.todo',
    description='Launch files for Flashbot.',
    license='Apache-2.0',
)

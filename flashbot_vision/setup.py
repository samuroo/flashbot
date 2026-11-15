from setuptools import find_packages, setup

package_name = 'flashbot_vision'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='flashbot-1',
    maintainer_email='flashbot-1@todo.todo',
    description='Flashbot vision nodes.',
    license='Apache-2.0',
    entry_points={'console_scripts': [
        'person_detector = flashbot_vision.person_detector:main',
    ]},
)

from setuptools import find_packages, setup

setup(
    name='flashbot_web',
    version='0.0.0',
    packages=find_packages(),
    package_data={'flashbot_web': ['templates/*.html', 'static/*.css', 'static/*.js']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/flashbot_web']),
        ('share/flashbot_web', ['package.xml']),
    ],
    # Runtime web dependencies live in the existing venv; colcon uses system Python.
    install_requires=['setuptools'],
    zip_safe=False,
    maintainer='flashbot-1',
    maintainer_email='flashbot-1@todo.todo',
    description='Small Flask viewer for Flashbot camera and detection status.',
    license='Apache-2.0',
    entry_points={'console_scripts': ['web_node = flashbot_web.web_node:main']},
)

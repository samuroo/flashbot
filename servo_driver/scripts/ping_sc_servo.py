import time
from scservo_sdk import PortHandler, scscl, COMM_SUCCESS

PORT = "/dev/ttyACM0"  # Same port as your working ping script
SERVO_ID = 0
BAUDRATE = 1000000
SPEED = 300

# Approximately 90 degrees apart
POSITION_1 = 358
POSITION_2 = 665

port = PortHandler(PORT)
servo = scscl(port)

if not port.openPort():
    raise RuntimeError("Could not open serial port")

try:
    if not port.setBaudRate(BAUDRATE):
        raise RuntimeError("Could not set baud rate")

    for position in [POSITION_1, POSITION_2]:
        print(f"Moving to {position}")
        result, error = servo.WritePos(SERVO_ID, position, 0, SPEED)

        if result != COMM_SUCCESS or error != 0:
            raise RuntimeError(f"Servo error: {result}, {error}")

        time.sleep(3)

    while True:
        for position in [POSITION_1, POSITION_2]:
            print(f"Moving to {position}")
            result, error = servo.WritePos(SERVO_ID, position, 0, SPEED)

            if result != COMM_SUCCESS or error != 0:
                raise RuntimeError(f"Servo error: {result}, {error}")

            time.sleep(3)

except KeyboardInterrupt:
    print("\nStopped")

finally:
    port.closePort()

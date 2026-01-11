import serial
import time

### recieve
# ser = serial.Serial('/dev/ttyACM0',115200)
# s = [0]
# while True:
# 	read_serial=ser.readline()
# 	print(read_serial)

ser = serial.Serial('/dev/ttyACM0', 115200)
time.sleep(2)

num_faces = 1
while True:
    data = f"{num_faces}\n"
    ser.write(data.encode())
    time.sleep(1)
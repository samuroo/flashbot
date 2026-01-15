import serial, time
from detection.detection import detect_largest_person

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1, write_timeout=0.1)
time.sleep(2)
# detect_largest_person(img_bgr, conf_th=0.5, nms_th=0.4)

num_faces = 1  # update from your detector

while True:
    # Drain all available lines
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        

        if line == "REQ_DET":
            det = detect_largest_person(conf_th=0.5, nms_th=0.4)
            if det is None:
                num_faces = 0
            else:
                num_faces = 1

            ser.write(f"{num_faces}\n".encode())
            print("Pi sent num_faces:", num_faces)
        else:
            print("Arduino:", line)

    time.sleep(0.01)
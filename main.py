import serial, time
from detection.detection import detect_largest_person

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1, write_timeout=0.1)

# give Arduino time to reboot on serial open (common)
time.sleep(2.0)

# ---- Boot handshake: Pi announces once until Arduino replies ----
ready = False
t0 = time.time()
while not ready:
    ser.write(b"PI_ON\n")
    # drain any replies
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print("Arduino:", line)
        if line == "ARDUINO_READY":
            ready = True
            break
    # don't spam too hard
    time.sleep(0.1)

print("Handshake complete. Waiting for REQ_DET...")

# ---- Main loop: only respond when Arduino asks ----
while True:
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        if line == "REQ_DET":
            det = detect_largest_person(conf_th=0.5, nms_th=0.4)

            if det is None:
                ser.write(b"0\n")
                continue

            try:
                x1, y1, x2, y2 = det["bbox"]
                cx, cy = det["center"]

                w = int(x2 - x1)
                h = int(y2 - y1)

                # ---- size gate ----
                W_MIN = 120
                H_MIN = 160
                if w < W_MIN or h < H_MIN:
                    ser.write(b"0\n")
                    continue

                # ---- dx from image center ----
                IMG_W = 640  # match your camera width
                dx = int(cx - (IMG_W // 2))       # negative = left

                ser.write(f"{dx}\n".encode())
                
                print("Pi ->", dx)

            except Exception as e:
                ser.write(b"0\n")
                print("Pi -> 0 (parse error)", e, "det=", det)

        else:
            print("Arduino:", line)

    time.sleep(0.01)
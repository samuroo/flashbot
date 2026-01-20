// #include <Arduino.h>
// #include <SCServo.h>

// SCSCL sc2;

// const uint8_t ID = 0;
// const int16_t PWM_MAX = 1000;   // safe starting clamp; increase if needed

// int16_t clampPWM(int x) {
//   if (x > PWM_MAX) return PWM_MAX;
//   if (x < -PWM_MAX) return -PWM_MAX;
//   return (int16_t)x;
// }

// void setup() {
//   Serial.begin(115200);
//   Serial1.begin(1000000);
//   sc2.pSerial = &Serial1;
//   delay(300);

//   // Put servo into continuous/motor control mode
//   sc2.PWMMode(ID);

//   // Make sure torque is enabled (some servos need it)
//   sc2.EnableTorque(ID, 1);
//   delay(50);

//   Serial.println("Starting continuous mode drive...");
// }

// void loop() {
//   // Forward
//   sc2.WritePWM(ID, clampPWM(1700));
//   Serial.println("PWM: +400");
//   delay(3000);

//   // Stop
//   sc2.WritePWM(ID, 0);
//   Serial.println("PWM: 0");
//   delay(4000);

// //   // Reverse
// //   sc.WritePWM(ID, clampPWM(-400));
// //   Serial.println("PWM: -400");
// //   delay(3000);

// //   // Stop
// //   sc.WritePWM(ID, 0);
// //   Serial.println("PWM: 0");
// //   delay(1000);
// }

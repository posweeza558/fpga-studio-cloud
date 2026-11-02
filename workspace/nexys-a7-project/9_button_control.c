// [ตัวอย่างที่ 9] อ่านค่าปุ่มกด (Push Buttons) 5 ทิศทาง + RESET
// Address ปุ่มกดคือ 0xF000000C
// Bit 0: BTNC (ปุ่มกลาง)
// Bit 1: BTNU (ปุ่มบน)
// Bit 2: BTNL (ปุ่มซ้าย)
// Bit 3: BTNR (ปุ่มขวา)
// Bit 4: BTND (ปุ่มล่าง)
// Bit 5: RESET (ปุ่มแดง)

#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)
#define BTN     (*(volatile int*)0xF000000C)

int main() {
    int last_btn = -1;
    while (1) {
        int b = BTN; // อ่านค่าสถานะปุ่มกด 6 บิต
        if (b != last_btn) {
            last_btn = b;
            LED = b;  // ส่งค่าสถานะปุ่มออกไฟ LED
            SEG7 = b; // แสดงรหัสปุ่มออกหน้าจอ 7-Segment
        }
    }
}

// [ตัวอย่างที่ 1] อ่านค่าสวิตช์ มาบวก 1 แล้วส่งออกไฟ LED & 7-Segment
// ไฟล์นี้ถูกบันทึกอยู่ในโฟลเดอร์โปรเจกต์จริง แก้ไขและกด Ctrl+S ได้เลย!

#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int sw = SWITCH;        // 1. อ่านค่าจากสวิตช์ 16 ตัว
        int result = sw + 1;    // 2. ประมวลผลใน ALU
        LED = result;           // 3. แสดงผลออกไฟ LED 16 ดวง
        SEG7 = result;          // 4. แสดงผลออกตัวเลข 7-Segment 8 หลัก
 }
}
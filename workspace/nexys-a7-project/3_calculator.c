// ==============================================================================
// [ตัวอย่างที่ 3] เครื่องคิดเลข (สวิตช์ซ้าย 8 บิต + สวิตช์ขวา 8 บิต)
// แสดงผลออก 7-Segment Display เป็นเลขฐาน 10 ตรงตัว (BCD)
// เช่น สวิตช์ 15 ยกขึ้น (ค่า 128) -> หน้าจอจะแสดง "00000128" ตรงกับค่าคำนวณ
// ==============================================================================

#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

static inline int to_bcd(int val) {
    int bcd = 0;
    int shift = 0;
    while (val > 0 && shift < 32) {
        bcd |= ((val % 10) << shift);
        val /= 10;
        shift += 4;
    }
    return bcd;
}

int main() {
    while (1) {
        int raw = SWITCH;
        int a = (raw >> 8) & 0xFF; // ค่าจากสวิตช์ตัวที่ 8-15 (ฝั่งซ้าย: 0-255)
        int b = raw & 0xFF;        // ค่าจากสวิตช์ตัวที่ 0-7  (ฝั่งขวา: 0-255)
        int sum = a + b;           // คำนวณผลบวกใน ALU

        LED = sum;                 // แสดงผลแบบ Binary บนไฟ LED 16 ดวง
        SEG7 = to_bcd(sum);        // แสดงผลเป็นเลขฐานสิบตรงตัวบน 7-Segment
    }
}

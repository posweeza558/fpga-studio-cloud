// [ตัวอย่างที่ 2] ไฟวิ่ง Binary Counter นับเลขขึ้นเรื่อยๆ พร้อมหน่วงเวลาให้ตามองทัน
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    int count = 0;
    while (1) {
        int step = SWITCH;
        if (step == 0) {
            step = 1;
        }
        count = count + step;
        LED = count;
        SEG7 = count;

        // หน่วงเวลา ~0.2 วินาทีบนคล็อก 25 MHz ให้สายตามนุษย์มองเห็นการนับทีละจังหวะ
        for (int i = 0; i < 2000000; i++) {
            __asm__ __volatile__("" : "+r"(i));
        }
    }
}

// ไฟล์: untitled.c
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int sw = SWITCH;
        LED = sw + 1;
        SEG7 = sw + 1;
    }
}

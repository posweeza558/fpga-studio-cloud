#define LED_ADDR    (*(volatile int*)0xF0000000)
#define STATUS_ADDR (*(volatile int*)0xF0000004)

// 1. Recursive Function (ทดสอบ Stack Frame, $sp, $ra, Nested jal/jr)
int fib_recursive(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fib_recursive(n - 1) + fib_recursive(n - 2);
}

// 2. Bitwise & Logic Test (ทดสอบ sll, srl, sra, xor, and, or, nor)
unsigned int bit_manipulation(unsigned int val) {
    val = (val << 5) | (val >> 27);     // Rotate left 5
    val ^= 0x5555AAAA;
    val += ~(val & 0x00FF00FF);
    val = (val >> 3) ^ (val << 2);
    return val;
}

// 3. Array & In-place Sorting (ทดสอบ Load-use Hazard, lw/sw, Nested Loop, Pointer Arithmetic)
void bubble_sort(int *arr, int len) {
    for (int i = 0; i < len - 1; i++) {
        for (int j = 0; j < len - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}

int main(void) {
    // ----------------------------------------------------
    // TEST 1: Recursive Call & Stack Push/Pop
    // fib(10) = 55 (0x37)
    // ----------------------------------------------------
    int fib_result = fib_recursive(10);
    if (fib_result != 55) {
        LED_ADDR = 0xEEEE0001; // Error Step 1: Stack / Recursion พัง
        while (1);
    }

    // ----------------------------------------------------
    // TEST 2: ALU & Bitwise Operations
    // ----------------------------------------------------
    unsigned int bit_result = bit_manipulation(0x12345678);
    // ค่าที่คำนวณตามสูตรอย่างเป็นขั้นตอนจะได้ผลลัพธ์คงที่
    if (bit_result != 0x4E619F63) {
        LED_ADDR = 0xEEEE0002; // Error Step 2: Shifter / Logic ALU พัง
        while (1);
    }

    // ----------------------------------------------------
    // TEST 3: Memory Hazards & Array Sort
    // ----------------------------------------------------
    int data[8] = {45, -12, 89, 0, 23, -5, 78, 12};
    bubble_sort(data, 8);

    // ตรวจสอบความถูกต้องของการเรียงลำดับ: [-12, -5, 0, 12, 23, 45, 78, 89]
    int expected[8] = {-12, -5, 0, 12, 23, 45, 78, 89};
    for (int i = 0; i < 8; i++) {
        if (data[i] != expected[i]) {
            LED_ADDR = 0xEEEE0003; // Error Step 3: Data Hazard / Forwarding / Memory พัง
            while (1);
        }
    }

    // ----------------------------------------------------
    // SUCCESS: ผ่านการทดสอบครบทุกด่าน
    // ----------------------------------------------------
    LED_ADDR = 0x000000FF;        // ติดไฟ LED 8 ดวงแรก
    STATUS_ADDR = 0xCAFEBABE;     // รหัสผ่านฉลุย

    while (1) {
        // Halt loop
    }

    return 0;
}
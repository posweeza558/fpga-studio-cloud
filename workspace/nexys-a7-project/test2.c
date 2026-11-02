#define LED_ADDR    (*(volatile int*)0xF0000000)
#define SEG7_ADDR   (*(volatile int*)0xF0000008)

// -------------------------------------------------------------------------
// DUNG 1: ทดสอบ Modulo (%), Division (/), และ Recursive GCD (Euclidean Algorithm)
// ใน MIPS ต้องใช้ div ตามด้วย mfhi (สำหรับ %) และถ้าแปลงแอดเดรส jal พลาดจะค้างทันที
// -------------------------------------------------------------------------
__attribute__((noinline))
int gcd(int a, int b) {
    while (b != 0) {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}

// -------------------------------------------------------------------------
// DUNG 2: ทดสอบ Arithmetic Shift (sra) vs Logical Shift (srl) และ Multiply (mul)
// เลื่อนขวาตัวเลขติดลบ ต้องเติมบิต 1 ด้านซ้าย (Sign-extend)
// -------------------------------------------------------------------------
__attribute__((noinline))
int signed_math_torture(int x, int y) {
    int a = x >> 4;          // ต้องได้คำสั่ง srai / sra (รักษาเครื่องหมายลบ)
    unsigned int ux = (unsigned int)x;
    int b = (int)(ux >> 4);  // ต้องได้คำสั่ง srli / srl (เติม 0 ด้านซ้าย)
    
    int prod = a * y;        // ทดสอบคำสั่งคูณ (mul / mult + mflo)
    return prod ^ b;
}

// -------------------------------------------------------------------------
// DUNG 3: ทดสอบ Signed vs Unsigned Branching & 32-bit Edge-case Constants
// ค่าคงที่ 0x89ABCDEF มีทั้งบิตที่ 15 (0x8000) และบิตที่ 11 (0x0800) เป็น 1
// จะดักจับบั๊กการทำ Sign-extension ของ lui + addi ได้แม่นยำที่สุด
// -------------------------------------------------------------------------
__attribute__((noinline))
int branch_and_const_test(int signed_val, unsigned int unsigned_val) {
    int score = 0;

    // -10 < 5 (True สำหรับ Signed)
    if (signed_val < 5) {
        score += 10;
    }
    // 0xFFFFFFF6 > 5 (True สำหรับ Unsigned เพราะเลขลบเมื่อมองเป็น Unsigned จะมีค่ามหาศาล)
    if (unsigned_val > 5U) {
        score += 20;
    }
    // ทดสอบ <= และ >= (มักถูกแปลงเป็น slt + beq/bne 2 คำสั่งใน MIPS ทำให้ออฟเซ็ตเลื่อน)
    if (signed_val <= -10 && unsigned_val >= 0xFFFFFF00U) {
        score += 30;
    }

    // บวกค่าคงที่เจ้าปัญหา 0x89ABCDEF
    // ถ้าทำ lui 16-bit vs 20-bit ผิด ค่านี้จะเพี้ยนทันที
    return score ^ 0x89ABCDEF;
}

// -------------------------------------------------------------------------
// DUNG 4: ทดสอบ Nested Function Call & Pointer Array Indexing (Collatz + Checksum)
// -------------------------------------------------------------------------
__attribute__((noinline))
int collatz_steps(int n) {
    int steps = 0;
    while (n > 1) {
        if ((n & 1) == 0) {
            n = n / 2;
        } else {
            n = (n * 3) + 1;
        }
        steps++;
    }
    return steps;
}

int main(void) {
    // ใช้ volatile บังคับให้โหลดค่าและคำนวณจริงตอนรันไทม์
    volatile int a = 1071;
    volatile int b = 462;

    // ----------------------------------------------------
    // TEST 1: GCD(1071, 462)
    // 1071 % 462 = 147 -> 462 % 147 = 21 -> 147 % 21 = 0 -> คำตอบคือ 21 (0x15)
    // ----------------------------------------------------
    if (gcd(a, b) != 21) {
        LED_ADDR = 0xDEAD0001; // พังที่การหารเอาเศษ (%) หรือลูป while
        while (1);
    }

    // ----------------------------------------------------
    // TEST 2: Signed Shift (sra) vs Unsigned Shift (srl) & Multiply
    // x = -256 (0xFFFFFF00), y = 3
    // a = -256 >> 4 = -16 (0xFFFFFFF0)
    // b = 0xFFFFFF00U >> 4 = 0x0FFFFFF0 (268435440)
    // prod = -16 * 3 = -48 (0xFFFFFFD0)
    // prod ^ b = 0xFFFFFFD0 ^ 0x0FFFFFF0 = 0xF0000020 (-268435424)
    // ----------------------------------------------------
    volatile int x = -256;
    volatile int y = 3;
    if (signed_math_torture(x, y) != (int)0xF0000020) {
        LED_ADDR = 0xDEAD0002; // พังที่ sra/srl หรือคำสั่งคูณ (mul)
        while (1);
    }

    // ----------------------------------------------------
    // TEST 3: Signed/Unsigned Branch & 32-bit Constant (0x89ABCDEF)
    // signed_val = -10, unsigned_val = 0xFFFFFFF6U (-10 ในรูป unsigned)
    // เข้าทุกเงื่อนไข: score = 10 + 20 + 30 = 60 (0x3C)
    // 0x0000003C ^ 0x89ABCDEF = 0x89ABCDD3
    // ----------------------------------------------------
    volatile int s_val = -10;
    volatile unsigned int u_val = 0xFFFFFFF6U;
    if (branch_and_const_test(s_val, u_val) != (int)0x89ABCDD3) {
        LED_ADDR = 0xDEAD0003; // พังที่ slt/sltu, Branch offset, หรือ lui 0x89ABCDEF
        while (1);
    }

    // ----------------------------------------------------
    // TEST 4: Collatz Conjecture (n = 27 ต้องใช้ 111 ขั้นตอนจึงจะถึง 1)
    // ทดสอบลูปยาวๆ และการสลับคูณ/หาร/บวก/เช็กบิตคู่คี่
    // ----------------------------------------------------
    volatile int c_start = 27;
    if (collatz_steps(c_start) != 111) {
        LED_ADDR = 0xDEAD0004; // พังที่การคำนวณซ้ำๆ ในลูป
        while (1);
    }

    // ----------------------------------------------------
    // ALL PASSED!
    // ----------------------------------------------------
    LED_ADDR  = 0x0000FFFF;   // เปิดไฟ LED 16 ดวงรวด
    SEG7_ADDR = 0x12345678;   // ส่งเลขเรียงออก 7-Segment

    while (1);
    return 0;
}
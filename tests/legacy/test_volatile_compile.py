import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

// ฟังก์ชันแปลงเลขจำนวนเต็ม ans เป็น BCD 4 หลัก จากตัวแปรจริง (ไม่ล็อคค่า)
static inline int to_bcd4(int val) {
    int d3 = (val / 1000) % 10;
    int d2 = (val / 100) % 10;
    int d1 = (val / 10) % 10;
    int d0 = val % 10;
    return (d3 << 12) | (d2 << 8) | (d1 << 4) | d0;
}

// รวมค่า n, k และ ans ออกเป็นรูปแบบหน้าจอ 7-Segment 8 หลัก: [n][C][k][ans]
static inline int pack_7seg(int n, int k, int ans) {
    int n_bcd = ((n / 10) % 10 << 4) | (n % 10);
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | to_bcd4(ans);
}

int main(void) {
    volatile int n = 10;
    volatile int k = 3;
    volatile int ans = 1;

    // ขั้นที่ 1: แสดงค่า n
    LED = n;
    SEG7 = pack_7seg(n, 0, 0);

    // ขั้นที่ 2: แสดงโจทย์ n C k (10 C 3)
    LED = k;
    SEG7 = pack_7seg(n, k, 0);

    // ขั้นที่ 3: คำนวณทีละรอบด้วยลูป (ALU ทำการคูณ/หารและคำนวณ BCD จริงทุกรอบ)
    for (int i = 1; i <= k; i++) {
        ans = ans * (n - i + 1) / i;
        LED = ans;
        SEG7 = pack_7seg(n, i, ans);
    }

    while (1) {
    }

    return 0;
}
"""

try:
    asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
    print(f"Compiled successfully: {len(ins)} instructions")
    for idx, x in enumerate(ins[:35]):
        print(f"[{idx:02d}] PC: {x['pc']} | src: {x.get('src_line')} | ASM: {x['asm']}")
except Exception as e:
    print(f"Error: {e}")

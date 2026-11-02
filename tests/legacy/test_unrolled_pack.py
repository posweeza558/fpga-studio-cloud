import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

// ฟังก์ชันแปลงผลลัพธ์ ans เป็นรหัส 7-Segment จากตัวแปรจริง (Dynamic BCD)
// ไม่มีการล็อคค่าคงที่: ALU จะคำนวณแยกหลักร้อย/สิบ/หน่วย จากค่า ans ที่ได้จริง
static inline int pack_7seg(int n, int k, int ans) {
    int n_bcd   = ((n / 10) % 10 << 4) | (n % 10);
    int d3      = (ans / 1000) % 10;
    int d2      = (ans / 100) % 10;
    int d1      = (ans / 10) % 10;
    int d0      = ans % 10;
    int ans_bcd = (d3 << 12) | (d2 << 8) | (d1 << 4) | d0;
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | ans_bcd;
}

int main(void) {
    register int n = 10;
    register int k = 3;

    // ขั้นที่ 1: กำหนด n = 10 -> แปลงและแสดงผลจริง
    LED = n;
    SEG7 = pack_7seg(n, 0, 0);

    // ขั้นที่ 2: กำหนด k = 3 -> แปลงและแสดงโจทย์ 10 C 3
    LED = k;
    SEG7 = pack_7seg(n, k, 0);

    // ขั้นที่ 3: รอบที่ 1 -> 10 C 1 = 10
    register int ans = 10;
    LED = ans;
    SEG7 = pack_7seg(n, 1, ans);

    // ขั้นที่ 4: รอบที่ 2 -> 10 C 2 = (10 * 9) / 2 = 45
    ans = (ans * 9) / 2;
    LED = ans;
    SEG7 = pack_7seg(n, 2, ans);

    // ขั้นที่ 5: รอบที่ 3 -> 10 C 3 = (45 * 8) / 3 = 120
    ans = (ans * 8) / 3;
    LED = ans;
    SEG7 = pack_7seg(n, 3, ans);

    while (1) {
    }

    return 0;
}
"""

try:
    asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
    print(f"Compiled successfully: {len(ins)} instructions")
    for idx, x in enumerate(ins):
        print(f"[{idx:02d}] PC: {x['pc']} | src: {x.get('src_line')} | ASM: {x['asm']}")
except Exception as e:
    print(f"Error: {e}")

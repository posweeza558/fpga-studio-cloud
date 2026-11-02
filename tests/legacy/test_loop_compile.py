import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

// แปลงค่า n, k, ans เป็นรูปแบบ 7-Segment: [n 2หลัก] [C] [k 1หลัก] [ans 4หลัก]
// เช่น n=10, k=3, ans=120 -> แสดง "10C30120"
static inline int pack_display(int n_val, int k_val, int ans_val) {
    int d_n1 = n_val / 10;
    int d_n0 = n_val % 10;
    int d_k  = k_val % 10;
    int a3   = (ans_val / 1000) % 10;
    int a2   = (ans_val / 100) % 10;
    int a1   = (ans_val / 10) % 10;
    int a0   = ans_val % 10;
    return (d_n1 << 28) | (d_n0 << 24) | (0xC << 20) | (d_k << 16) | (a3 << 12) | (a2 << 8) | (a1 << 4) | a0;
}

int main(void) {
    register int n = 10;
    register int k = 3;

    // ขั้นที่ 1: แสดง n
    LED = n;
    SEG7 = (n / 10 << 28) | (n % 10 << 24) | (0xC << 20);

    // ขั้นที่ 2: แสดง n C k
    LED = k;
    SEG7 = (n / 10 << 28) | (n % 10 << 24) | (0xC << 20) | (k << 16);

    // ขั้นที่ 3: คำนวณทีละขั้นด้วยลูป
    register int ans = 1;
    for (register int i = 1; i <= k; i++) {
        ans = ans * (n - i + 1) / i;
        LED = ans;
        SEG7 = pack_display(n, i, ans);
    }

    while (1) {}
    return 0;
}
"""

try:
    asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
    print(f"Compiled successfully: {len(ins)} instructions")
    for idx, x in enumerate(ins):
        print(f"[{idx:02d}] 0x{x['pc']}: {x['asm']}")
except Exception as e:
    print(f"Error: {e}")

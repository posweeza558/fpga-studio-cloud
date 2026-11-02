import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

static inline int to_bcd4(int val) {
    int d3 = (val / 1000) % 10;
    int d2 = (val / 100) % 10;
    int d1 = (val / 10) % 10;
    int d0 = val % 10;
    return (d3 << 12) | (d2 << 8) | (d1 << 4) | d0;
}

static inline int pack_7seg(int n, int k, int ans) {
    int n_bcd = ((n / 10) % 10 << 4) | (n % 10);
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | to_bcd4(ans);
}

int main(void) {
    register int n = 10;
    register int k = 3;
    __asm__ __volatile__("" : "+r"(n), "+r"(k));

    LED = n;
    SEG7 = pack_7seg(n, 0, 0);

    LED = k;
    SEG7 = pack_7seg(n, k, 0);

    register int ans = n;
    LED = ans;
    SEG7 = pack_7seg(n, 1, ans);

    ans = (ans * (n - 1)) / 2;
    __asm__ __volatile__("" : "+r"(ans));
    LED = ans;
    SEG7 = pack_7seg(n, 2, ans);

    ans = (ans * (n - 2)) / 3;
    __asm__ __volatile__("" : "+r"(ans));
    LED = ans;
    SEG7 = pack_7seg(n, 3, ans);

    while (1) {}
    return 0;
}
"""

lines = code.splitlines()
asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
for i, x in enumerate(ins):
    s_line = x.get("src_line")
    c_text = lines[s_line - 1].strip() if s_line and 0 < s_line <= len(lines) else ""
    print(f"[{i:02d}] PC: {x['pc']} | src: {str(s_line):2} | code: {c_text:35} | ASM: {x['asm']}")

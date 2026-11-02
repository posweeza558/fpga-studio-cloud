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
    int n = 10;
    __asm__ __volatile__("" : "+r"(n));
    LED = n;
    SEG7 = pack_7seg(n, 0, 0);

    int k = 3;
    __asm__ __volatile__("" : "+r"(k));
    LED = k;
    SEG7 = pack_7seg(n, k, 0);

    int ans = n;
    __asm__ __volatile__("" : "+r"(ans));
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

    while (1) {
    }

    return 0;
}
"""

lines = code.splitlines()
asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
for i, x in enumerate(ins):
    s = x.get('src_line')
    txt = lines[s - 1].strip() if s and 0 < s <= len(lines) else ""
    print(f"[{i:02d}] PC: {x['pc']} | src: {str(s):2} | code: {txt:35} | ASM: {x['asm']}")

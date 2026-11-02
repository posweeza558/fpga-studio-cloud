import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

int main(void) {
    // 1. n = 10
    register int n = 10;
    LED = n;
    SEG7 = 0x10000000;

    // 2. k = 3 -> 10 C 3
    register int k = 3;
    LED = k;
    SEG7 = 0x10C30000;

    // 3. Round 1: 10 C 1 = 10
    register int ans = 10;
    LED = ans;
    SEG7 = 0x10C10010;

    // 4. Round 2: 10 C 2 = (10 * 9) / 2 = 45
    ans = (ans * 9) / 2;
    LED = ans;
    SEG7 = 0x10C20045;

    // 5. Round 3: 10 C 3 = (45 * 8) / 3 = 120
    ans = (ans * 8) / 3;
    LED = ans;
    SEG7 = 0x10C30120;

    while (1) {}
    return 0;
}
"""

asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
print(f"Compiled successfully: {len(ins)} instructions")
for x in ins:
    print(f"0x{x['pc']}: {x['asm']}")

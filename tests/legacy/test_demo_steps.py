import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000) // ไฟ LED 16 ดวง
#define SEG7    (*(volatile int*)0xF0000008) // 7-Segment Display 8 หลัก

int main(void) {
    // ขั้นที่ 1: กำหนด n = 10
    register int n = 10;
    LED = n;
    SEG7 = 0x10C00000;

    // ขั้นที่ 2: กำหนด k = 3
    register int k = 3;
    LED = k;
    SEG7 = 0x10C30000;

    // ขั้นที่ 3: รอบที่ 1 -> 10 C 1 = 10
    register int ans = 10;
    LED = ans;
    SEG7 = 0x10C10010;

    // ขั้นที่ 4: รอบที่ 2 -> 10 C 2 = (10 * 9) / 2 = 45
    ans = (ans * 9) / 2;
    LED = ans;
    SEG7 = 0x10C20045;

    // ขั้นที่ 5: รอบที่ 3 -> 10 C 3 = (45 * 8) / 3 = 120
    ans = (ans * 8) / 3;
    LED = ans;
    SEG7 = 0x10C30120;

    while (1) {
    }

    return 0;
}
"""

asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
print(f"Total instructions: {len(ins)}")
for idx, x in enumerate(ins):
    print(f"[{idx:02d}] PC: {x['pc']} | src_line: {x.get('src_line')} | ASM: {x['asm']}")

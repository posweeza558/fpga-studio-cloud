import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """// ==============================================================================
// FPGA Studio — การคำนวณ 10C3 (Combinations) = 120
// ประมวลผลด้วยวงจรคูณและหาร (MUL / DIV) ของฮาร์ดแวร์ OpenMIPS Nexys A7
// แสดงผลออก 7-Segment Display เป็นเลขฐานสิบ "00000120"
// และไฟ LED 16 ดวงติดเป็นค่าฐานสอง 120 (0b0000000001111000)
// ==============================================================================

#define LED     (*(volatile int*)0xF0000000) // ไฟ LED 16 ดวง
#define SEG7    (*(volatile int*)0xF0000008) // 7-Segment Display 8 หลัก

int main(void) {
    // 1. คำนวณ 10C3 = (10 * 9 * 8) / (1 * 2 * 3) = 120
    //    ใช้สูตรลดทอนทีละขั้นตอน โดยหารด้วยค่าคงที่ (2 และ 3)
    //    GCC จะแปลงเป็นการคูณ DSP Multiplier และ Bit-shift ที่ความเร็วสูง (>400 MHz)
    //    ทำให้จังหวะ Timing ผ่านฉลุย 100% บนคล็อก 25 MHz
    register int ans = 10;
    ans = (ans * 9) / 2;   // 10 * 9 / 2 = 45
    ans = (ans * 8) / 3;   // 45 * 8 / 3 = 120

    // ans = 120
    // 2. ส่งค่า binary 120 ออกไฟ LED (ไฟติด 0b0000_0000_0111_1000)
    LED = ans;

    // 3. แปลง 120 ให้อยู่ในรูป BCD 0x120 เพื่อให้หน้าจอ 7-Segment ขึ้นเลข "00000120" ตรงตัว
    int d2 = ans / 100;                    // d2 = 1
    int rem = ans % 100;
    int d1 = rem / 10;                     // d1 = 2
    int d0 = rem % 10;                     // d0 = 0
    int bcd = (d2 << 8) | (d1 << 4) | d0;  // bcd = 0x00000120

    SEG7 = bcd;

    // ค้างผลลัพธ์ไว้ตลอด
    while (1) {
    }

    return 0;
}
"""

lines = code.splitlines()
asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
for i, x in enumerate(ins):
    s_line = x.get("src_line")
    c_text = lines[s_line - 1].strip() if s_line and 0 < s_line <= len(lines) else ""
    print(f"[{i:02d}] PC: {x['pc']} | src_line: {str(s_line):4} | code: {c_text:30} | ASM: {x['asm']}")

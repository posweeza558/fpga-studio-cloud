import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """// ==============================================================================
// FPGA Studio — การคำนวณ n C k (10C3 = 120) ทีละขั้นตอน (Step-by-Step)
// คำนวณจริงจากตัวแปร และแปลงเป็น BCD ส่งออก 7-Segment [n][C][k][ans]
// ทุกค่าคำนวณจากตัวแปรจริงของวงจร ALU (ไม่มีการล็อคค่าคงที่)
// ==============================================================================

#define LED     (*(volatile int*)0xF0000000) // ไฟ LED 16 ดวง (Binary)
#define SEG7    (*(volatile int*)0xF0000008) // 7-Segment Display 8 หลัก

// ฟังก์ชันแปลงเลขจำนวนเต็ม ans เป็น BCD 4 หลัก จากตัวแปรจริง (คำนวณจริงจาก ALU)
// เช่น ans = 120 -> คำนวณแยกหลักได้ 0x0120 (หลักร้อย=1, สิบ=2, หน่วย=0)
static inline int to_bcd4(int val) {
    int d3 = (val / 1000) % 10;
    int d2 = (val / 100) % 10;
    int d1 = (val / 10) % 10;
    int d0 = val % 10;
    return (d3 << 12) | (d2 << 8) | (d1 << 4) | d0;
}

// รวมค่าตัวแปร n, k และผลลัพธ์ ans ออกเป็นรูปแบบหน้าจอ 7-Segment 8 หลัก:
// [n: 2 หลัก] [ 'C' ] [k: 1 หลัก] [ans: 4 หลัก BCD]
static inline int pack_7seg(int n, int k, int ans) {
    int n_bcd = ((n / 10) % 10 << 4) | (n % 10);
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | to_bcd4(ans);
}

int main(void) {
    // --------------------------------------------------------------------------
    // ขั้นที่ 1: กำหนด n = 10 และคำนวณแสดงผลออกบอร์ด
    // --------------------------------------------------------------------------
    int n = 10;
    __asm__ __volatile__("" : "+r"(n));
    LED = n;
    SEG7 = pack_7seg(n, 0, 0);

    // --------------------------------------------------------------------------
    // ขั้นที่ 2: กำหนด k = 3 และคำนวณแสดงโจทย์ 10 C 3 ออกบอร์ด
    // --------------------------------------------------------------------------
    int k = 3;
    __asm__ __volatile__("" : "+r"(k));
    LED = k;
    SEG7 = pack_7seg(n, k, 0);

    // --------------------------------------------------------------------------
    // ขั้นที่ 3: รอบที่ 1 -> คำนวณ 10 C 1 = 10
    // --------------------------------------------------------------------------
    int ans = n;
    __asm__ __volatile__("" : "+r"(ans));
    LED = ans;
    SEG7 = pack_7seg(n, 1, ans);

    // --------------------------------------------------------------------------
    // ขั้นที่ 4: รอบที่ 2 -> คำนวณ 10 C 2 = (ans * 9) / 2 = 45
    // --------------------------------------------------------------------------
    ans = (ans * (n - 1)) / 2;
    __asm__ __volatile__("" : "+r"(ans));
    LED = ans;
    SEG7 = pack_7seg(n, 2, ans);

    // --------------------------------------------------------------------------
    // ขั้นที่ 5: รอบที่ 3 -> คำนวณ 10 C 3 = (ans * 8) / 3 = 120 (คำตอบสุดท้าย!)
    // --------------------------------------------------------------------------
    ans = (ans * (n - 2)) / 3;
    __asm__ __volatile__("" : "+r"(ans));
    LED = ans;
    SEG7 = pack_7seg(n, 3, ans);

    // ค้างผลลัพธ์ไว้ตลอด
    while (1) {
    }

    return 0;
}
"""

lines = code.splitlines()
asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
print(f"Total instructions: {len(ins)}")
for i, x in enumerate(ins):
    s = x.get('src_line')
    txt = lines[s - 1].strip() if s and 0 < s <= len(lines) else ""
    if s is not None and "main" in txt or "LED" in txt or "SEG7" in txt or "ans =" in txt:
        print(f"[{i:02d}] PC: {x['pc']} | line {str(s):2}: {txt:42} | ASM: {x['asm']}")

import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

code = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

// ฟังก์ชันแปลงเลขจำนวนเต็มเป็น BCD จากตัวแปรจริง (Dynamic BCD Converter)
// ไม่มีการล็อคค่าคงที่ ทุกอย่างแปลงจากตัวแปรที่คำนวณได้จริง
static int to_bcd(int val) {
    int bcd = 0;
    int shift = 0;
    while (val > 0 && shift < 16) {
        bcd |= ((val % 10) << shift);
        val /= 10;
        shift += 4;
    }
    return bcd;
}

// รวมค่า n, k และ ans ออกเป็นรูปแบบหน้าจอ 7-Segment 8 หลัก:
// [n: 2 หลัก] [ 'C' ] [k: 1 หลัก] [ans: 4 หลัก]
static int make_display(int n, int k, int ans) {
    int n_bcd = to_bcd(n);       // แปลง n เป็น BCD (เช่น 10 -> 0x10)
    int ans_bcd = to_bcd(ans);   // แปลงผลลัพธ์เป็น BCD (เช่น 120 -> 0x0120)
    
    // รวมเข้าด้วยกัน: n อยู่ซ้ายสุด, ตามด้วยอักษร C (0xC), ตามด้วย k, และผลลัพธ์ ans
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | (ans_bcd & 0xFFFF);
}

int main(void) {
    int n = 10;
    int k = 3;

    // ขั้นที่ 1: แสดงค่า n เริ่มต้น
    LED = n;
    SEG7 = make_display(n, 0, 0);

    // ขั้นที่ 2: แสดงโจทย์ n C k
    LED = k;
    SEG7 = make_display(n, k, 0);

    // ขั้นที่ 3: คำนวณทีละรอบด้วยลูป (คำนวณจริงจากสูตรคณิตศาสตร์)
    int ans = 1;
    for (int i = 1; i <= k; i++) {
        ans = ans * (n - i + 1) / i;
        LED = ans;
        SEG7 = make_display(n, i, ans);
    }

    while (1) {
    }

    return 0;
}
"""

try:
    asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
    print(f"Compiled successfully: {len(ins)} instructions")
    for idx, x in enumerate(ins[:40]):
        print(f"[{idx:02d}] PC: {x['pc']} | src: {x.get('src_line')} | ASM: {x['asm']}")
except Exception as e:
    print(f"Error: {e}")

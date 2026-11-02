// [โหมด PyMIPS] คำนวณ nCk (5C2 = 10) บนสถาปัตยกรรมอาจารย์
// โหมดนี้ไม่ใช้พิน LED/สวิตช์ แต่จะเก็บผลลัพธ์ลงใน Data Memory (RAM) และ Registers

int nCr(int n, int r) {
    if (r > n) return 0;
    if (r == 0 || r == n) return 1;
    if (r > n - r) r = n - r;
    int num = 1;
    int den = 1;
    for (int i = 1; i <= r; i++) {
        num = num * (n - i + 1);
        den = den * i;
    }
    return num / den;
}

int main() {
    int n = 5;
    int k = 2;
    int ans = nCr(n, k); // ans = 10

    // บันทึกลงใน Data Memory ช่องแรก (RAM[0])
    volatile int* ram = (volatile int*)0x00000000;
    ram[0] = ans;
    return ans;
}

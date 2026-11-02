// ==============================================================================
// FPGA Studio — การคำนวณ n C k ภาษา C แบบ Dynamic (Standard C)
// รันบน CPU RISC-V RV32IM พร้อมวงจรฮาร์ดแวร์คูณ-หารแท้ (Hardware MUL / DIV) บนบอร์ด Nexys A7
// ==============================================================================

#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

static int to_bcd4(int val) {
    int bcd = 0;
    int shift = 0;
    while (val > 0 && shift < 16) {
        bcd |= (val % 10) << shift;
        val = val / 10;
        shift += 4;
    }
    return bcd;
}

static int pack_7seg(int n, int k, int ans) {
    int n_bcd = ((n / 10) << 4) | (n % 10);
    return (n_bcd << 24) | (0xC << 20) | ((k & 0xF) << 16) | (to_bcd4(ans) & 0xFFFF);
}

int n_choose_k(int n, int k) {
    if (k < 0 || k > n) return 0;
    if (k == 0 || k == n) return 1;
    if (k > n - k) k = n - k;
    
    int ans = 1;
    for (int i = 1; i <= k; i++) {
        ans = (ans * (n - i + 1)) / i;
    }
    return ans;
}

int main(void) {
    int n = 10;
    int k = 3;
    __asm__ __volatile__("" : "+r"(n), "+r"(k));

    int ans = n_choose_k(n, k);
    __asm__ __volatile__("" : "+r"(ans));

    LED = ans;
    SEG7 = pack_7seg(n, k, ans);

    while (1) {
    }
    return 0;
}

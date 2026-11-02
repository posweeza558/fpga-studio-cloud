// =============================================================================
// Program: 11_pure_alu_compute.c
// Target: alu_only_cpu (Minimalist Pure ALU Core)
// Description: Pure arithmetic and bitwise logic operations without any
//              peripheral MMIO (No LEDs, No Switches, No 7-Segment).
// =============================================================================

int main(void) {
    int a = 100;
    int b = 45;

    // 1. Arithmetic
    int sum  = a + b;   // 145
    int diff = a - b;   // 55

    // 2. Bitwise Logic
    int band = a & b;   // 36
    int bor  = a | b;   // 109
    int bxor = a ^ b;   // 73

    // 3. Shifts
    int shl  = a << 2;  // 400
    int shr  = a >> 1;  // 50

    // 4. Combined Accumulation
    int t1 = sum + diff;   // 200
    int t2 = t1 + band;    // 236
    int t3 = t2 + bor;     // 345
    int t4 = t3 + bxor;    // 418
    int t5 = t4 + shl;     // 818
    int total = t5 + shr;  // 868

    return total;
}

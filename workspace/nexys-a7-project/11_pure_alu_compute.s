# ==============================================================================
# Program: 11_pure_alu_compute.s
# Target: alu_only_cpu (or any MIPS/RISC core)
# Description: Pure ALU arithmetic & bitwise logic torture test.
#              Contains NO Memory Load/Store, NO MMIO.
# ==============================================================================
.text
.globl main

main:
    # 1. Load initial numbers into registers
    addi $t0, $zero, 100       # $t0 = 100
    addi $t1, $zero, 45        # $t1 = 45

    # 2. Arithmetic operations (ADD & SUB)
    add  $t2, $t0, $t1         # $t2 = 100 + 45 = 145
    sub  $t3, $t0, $t1         # $t3 = 100 - 45 = 55

    # 3. Bitwise Logic (AND, OR, XOR, NOR)
    and  $t4, $t0, $t1         # $t4 = 100 & 45 = 36
    or   $t5, $t0, $t1         # $t5 = 100 | 45 = 109
    xor  $t6, $t0, $t1         # $t6 = 100 ^ 45 = 73
    nor  $t7, $t0, $t1         # $t7 = ~(100 | 45) = -110

    # 4. Barrel Shifting (SLL & SRL)
    sll  $s0, $t0, 2           # $s0 = 100 << 2 = 400
    srl  $s1, $t0, 1           # $s1 = 100 >> 1 = 50

    # 5. Conditional Comparison (SLT)
    slt  $s2, $t1, $t0         # $s2 = (45 < 100) ? 1 : 0 = 1
    slt  $s3, $t0, $t1         # $s3 = (100 < 45) ? 1 : 0 = 0

    # 6. Accumulate results into $v0
    add  $v0, $t2, $t3         # $v0 = 145 + 55 = 200
    add  $v0, $v0, $t4         # $v0 = 200 + 36 = 236
    add  $v0, $v0, $t5         # $v0 = 236 + 109 = 345
    add  $v0, $v0, $t6         # $v0 = 345 + 73 = 418
    add  $v0, $v0, $s0         # $v0 = 418 + 400 = 818
    add  $v0, $v0, $s1         # $v0 = 818 + 50 = 868
    add  $v0, $v0, $s2         # $v0 = 868 + 1 = 869

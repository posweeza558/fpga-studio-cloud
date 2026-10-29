# -*- coding: utf-8 -*-
"""
Workspace Paths, Default Starter Files, Extensions Marketplace Catalog & ISA Reference
"""

import os
import sys
from config.theme import ACCENT_GREEN, TXT_MUTED

if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    # Check current dir, 1 level up, or 2 levels up (e.g. dist/FPGA Studio)
    for cand in [EXE_DIR, os.path.dirname(EXE_DIR), os.path.dirname(os.path.dirname(EXE_DIR))]:
        if os.path.exists(os.path.join(cand, "toolchain")) or os.path.exists(os.path.join(cand, "workspace")):
            ROOT_DIR = os.path.abspath(cand)
            break
    else:
        ROOT_DIR = EXE_DIR
else:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_asset(filename):
    """Locate an asset file in sys._MEIPASS, ROOT_DIR, or EXE_DIR."""
    candidates = [
        getattr(sys, "_MEIPASS", ""),
        os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "",
        ROOT_DIR,
        os.path.dirname(os.path.abspath(__file__)),
    ]
    for base in candidates:
        if base:
            p = os.path.join(base, filename)
            if os.path.exists(p):
                return p
    return os.path.join(ROOT_DIR, filename)


WORKSPACE_ROOT = os.path.join(ROOT_DIR, "workspace")
DEFAULT_PROJECT_DIR = os.path.join(WORKSPACE_ROOT, "nexys-a7-project")
EXTENSIONS_STATE_FILE = os.path.join(WORKSPACE_ROOT, "extensions.json")
APP_ICON_PNG = find_asset("app_icon.png")
APP_ICON_ICO = find_asset("app_icon.ico")

# ==============================================================================
# FILE EXTENSION BADGE STYLES IN EXPLORER
# ==============================================================================
BADGE_STYLES = {
    ".c":   ("C",    ACCENT_GREEN),
    ".cpp": ("C++",  "#569CD6"),
    ".s":   ("ASM",  "#FFA657"),
    ".asm": ("ASM",  "#FFA657"),
    ".py":  ("PY",   "#FFD43B"),
    ".rs":  ("RS",   "#DEA584"),
    ".vhd": ("VHD",  "#C586C0"),
    ".v":   ("V",    ACCENT_GREEN),
    ".txt": ("TEXT", TXT_MUTED),
    "":     ("TEXT", TXT_MUTED),
}

# ==============================================================================
# STARTER PROJECT FILES
# ==============================================================================
DEFAULT_FILES = {
    "nexys_a7.h": """#ifndef NEXYS_A7_H
#define NEXYS_A7_H

// Digilent Nexys A7 FPGA (Artix-7 XC7A100T) — Memory Mapped I/O Definitions
#define LED         (*(volatile int*)0xF0000000) // ขา H17, K15, J13, N14, R18, V17, U17, U16...
#define SWITCH      (*(volatile int*)0xF0000004) // ขา J15, L16, M13, R15, R17, T18, U18, R13...
#define SEG7        (*(volatile int*)0xF0000008) // 7-Segment (Cathodes CA..CG / Anodes AN0..AN7)
#define BTN         (*(volatile int*)0xF000000C) // ปุ่มกด 5 ทิศทาง + RESET (BTNC, BTNU, BTNL, BTNR, BTND)
#define BUTTON      (*(volatile int*)0xF000000C)
#define UART_TX     (*(volatile int*)0xF0000010) // ขา D4 (UART TX)
#define UART_RX     (*(volatile int*)0xF0000010) // ขา C4 (UART RX)
#define UART_STATUS (*(volatile int*)0xF0000014) // Bit 0: RX ready, Bit 1: TX ready
#define RGB_LED     (*(volatile int*)0xF0000018) // LD16, LD17
#define VGA_VRAM    ((volatile int*)0xFF000000)  // VGA Framebuffer (640x480)

#define BTN_CENTER  (1 << 0) // ปุ่มกลาง (BTNC - N17)
#define BTN_UP      (1 << 1) // ปุ่มบน   (BTNU - M18)
#define BTN_LEFT    (1 << 2) // ปุ่มซ้าย (BTNL - P17)
#define BTN_RIGHT   (1 << 3) // ปุ่มขวา (BTNR - M17)
#define BTN_DOWN    (1 << 4) // ปุ่มล่าง (BTND - P18)
#define BTN_RESET   (1 << 5) // ปุ่มแดง CPU RESET (C12)

#endif // NEXYS_A7_H
""",
    "PINOUT_GUIDE.md": """# Nexys A7 FPGA Address & Pinout Map

| MMIO Address | อุปกรณ์ | ขนาด | ขาพินบนบอร์ด Nexys A7 (Xilinx Artix-7) |
|---|---|---|---|
| `0xF0000000` | LED 16 ดวง | 16-bit | H17, K15, J13, N14, R18, V17, U17, U16, V16, T15, U14, T16, V15, V14, V12, V11 |
| `0xF0000004` | Switch 16 ตัว | 16-bit | J15, L16, M13, R15, R17, T18, U18, R13, T8, U8, R16, T13, H6, U12, U11, V10 |
| `0xF0000008` | 7-Segment 8 หลัก | 32-bit | Cathodes: T10, R10, K16, K13, P15, T11, L18, H15 / Anodes: J17, J18, T9, J14, P14, T14, K2, U13 |
| `0xF000000C` | Push Buttons (5-way + Reset) | 6-bit | BTNC=N17, BTNU=M18, BTNL=P17, BTNR=M17, BTND=P18, RESET=C12 |
| `0xF0000010` | UART TX/RX (Serial) | 8-bit | TX=D4, RX=C4 |
| `0xF0000014` | UART Status | 2-bit | Bit 0: RX ready, Bit 1: TX ready |
| `0xF0000018` | RGB LEDs (LD16, LD17) | 24-bit | LD16: R12, M16, N15 / LD17: G14, R11, N16 |
| `0xFF000000` | VGA Framebuffer 640×480 | 12-bit | Red: A3..A4, Green: C6..A6, Blue: B7..D8, HSync: B11, VSync: B12 |
""",
    "1_switch_to_led.c": """// [ตัวอย่างที่ 1] อ่านค่าสวิตช์ มาบวก 1 แล้วส่งออกไฟ LED & 7-Segment
// ไฟล์นี้ถูกบันทึกอยู่ในโฟลเดอร์โปรเจกต์จริง แก้ไขและกด Ctrl+S ได้เลย!

#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int sw = SWITCH;        // 1. อ่านค่าจากสวิตช์ 16 ตัว
        int result = sw + 1;    // 2. ประมวลผลใน ALU
        LED = result;           // 3. แสดงผลออกไฟ LED 16 ดวง
        SEG7 = result;          // 4. แสดงผลออกตัวเลข 7-Segment 8 หลัก
    }
}
""",
    "2_binary_counter.c": """// [ตัวอย่างที่ 2] ไฟวิ่ง Binary Counter นับเลขขึ้นเรื่อยๆ
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    int count = 0;
    while (1) {
        int step = SWITCH;
        if (step == 0) {
            step = 1;
        }
        count = count + step;
        LED = count;
        SEG7 = count;
    }
}
""",
    "3_calculator.c": """// [ตัวอย่างที่ 3] เครื่องคิดเลข (สวิตช์ซ้าย 8 บิต + สวิตช์ขวา 8 บิต)
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    while (1) {
        int raw = SWITCH;
        int a = raw >> 8;       // ค่าจากสวิตช์ตัวที่ 8-15 (ฝั่งซ้าย)
        int b = raw & 255;      // ค่าจากสวิตช์ตัวที่ 0-7  (ฝั่งขวา)
        int sum = a + b;        // คำนวณผลบวก
        LED = sum;
        SEG7 = sum;
    }
}
""",
    "4_fibonacci.c": """// [ตัวอย่างที่ 4] คำนวณลำดับเลข Fibonacci (0, 1, 1, 2, 3, 5, 8, 13, 21...)
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)

int main() {
    int a = 0;
    int b = 1;
    while (1) {
        LED = a;
        SEG7 = a;
        int next = a + b;
        a = b;
        b = next;
    }
}
""",
    "5_hello_world_vga.c": """// [ตัวอย่างที่ 5] แสดงข้อความด้วย printf() (Bare-Metal Sim MMIO Macro)
#include <stdio.h>

int main() {
    printf("Hello World!\\n");
    printf("Hello C Programming!\\n");
    return 0;
}
""",
    "6_direct_assembly.s": """# [ตัวอย่างที่ 6] เขียนคำสั่ง Assembly โดยตรง
lui a5, 0xF0000       # ตั้ง Base Address I/O = 0xF0000000
addi s0, x0, 0        # ตัวแปรนับ s0 = 0
loop:
lw a4, 4(a5)          # อ่านสวิตช์ (0xF0000004)
add s0, s0, a4        # บวกค่าสวิตช์เข้ากับ s0
addi s0, s0, 1        # บวกเพิ่มอีก 1
sw s0, 0(a5)          # ส่งออกไฟ LED (0xF0000000)
sw s0, 8(a5)          # ส่งออก 7-Segment (0xF0000008)
j loop                # วนลูปกลับไปทำซ้ำ
""",
    "7_pymips_nck.c": """// [โหมด PyMIPS] คำนวณ nCk (5C2 = 10) บนสถาปัตยกรรมอาจารย์
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
""",
    "8_pymips_pipeline_test.s": """# [โหมด PyMIPS] ทดสอบ Data Hazard (RAW) & Forwarding ตามโมเดลอาจารย์
# คำนวณใน 5-Stage Pipeline (IF, ID, EX, MEM, WB)
add $r1, $r2, $r3    # r1 = r2 + r3
sub $r5, $r1, $r4    # r5 = r1 - r4 (Forwarding ดึงค่า r1 จาก Stage EX มาทันที)
sw $r5, 4($r0)       # เขียนผลลัพธ์ r5 ลง Data Memory ช่องที่ 4
lw $r6, 4($r0)       # อ่านผลลัพธ์กลับมาใส่ r6
"""
}

# ==============================================================================
# EXTENSIONS MARKETPLACE CATALOG
# ==============================================================================
EXTENSIONS_CATALOG = [
    {
        "id": "cpp_baremetal",
        "name": "C++ Bare-Metal (riscv-g++)",
        "publisher": "xPack Toolchain • Official",
        "ext": ".cpp",
        "badge": "C++",
        "badge_color": "#569CD6",
        "compiler_name": "C++ Compiler (riscv-g++ 15.2)",
        "desc": "เขียนโค้ดภาษา C++ (.cpp) แบบ OOP / Struct / Class แล้วคอมไพล์ด้วย riscv-none-elf-g++ 15.2 ของจริงเป็น 32-bit Machine Code",
        "sample_file": "7_cpp_led_controller.cpp",
        "sample_code": """// [ส่วนเสริม C++ Bare-Metal] คอมไพล์ด้วย riscv-none-elf-g++ 15.2 ของจริง!
#define LED     (*(volatile int*)0xF0000000)
#define SWITCH  (*(volatile int*)0xF0000004)
#define SEG7    (*(volatile int*)0xF0000008)

struct BoardIO {
    static inline int read_switch() { return SWITCH; }
    static inline void write_output(int val) {
        LED = val;
        SEG7 = val;
    }
};

int main() {
    while (1) {
        int sw = BoardIO::read_switch();
        BoardIO::write_output(sw * 2 + 1);
    }
}
"""
    },
    {
        "id": "micropython_fpga",
        "name": "Python to Hardware (MicroPython)",
        "publisher": "FPGA Studio Labs",
        "ext": ".py",
        "badge": "PY",
        "badge_color": "#FFD43B",
        "compiler_name": "Python Transpiler (Python → RV32)",
        "desc": "เขียนโค้ดด้วยไวยากรณ์ภาษา Python (.py) ที่อ่านง่าย แล้วแปลงตรงเป็นคำสั่ง RISC-V / MIPS 32-bit ลงบอร์ด FPGA ทันที",
        "sample_file": "8_python_hardware.py",
        "sample_code": """# [ส่วนเสริม Python to Hardware] เขียน Python เพื่อควบคุมบอร์ด FPGA
count = 0
while True:
    sw = SWITCH
    count = count + sw + 1
    LED = count
    SEG7 = count
"""
    },
    {
        "id": "rust_embedded",
        "name": "Rust Embedded (#![no_std])",
        "publisher": "Rust RISC-V Working Group",
        "ext": ".rs",
        "badge": "RS",
        "badge_color": "#DEA584",
        "compiler_name": "Rust Bare-Metal (Rust → RV32)",
        "desc": "รองรับภาษา Rust แบบ Bare-Metal (#![no_std]) สำหรับงานสมองกลฝังตัว แปลงโค้ด .rs เป็น 32-bit Machine Code",
        "sample_file": "9_rust_baremetal.rs",
        "sample_code": """// [ส่วนเสริม Rust Embedded #![no_std]] สำหรับ RISC-V & MIPS FPGA
#![no_std]
#![no_main]

fn main() {
    let mut acc: i32 = 0;
    loop {
        let sw: i32 = SWITCH;
        acc = acc + sw + 1;
        LED = acc;
        SEG7 = acc;
    }
}
"""
    },
    {
        "id": "verilog_exporter",
        "name": "Verilog / SystemVerilog HDL",
        "publisher": "Xilinx Vivado Tools",
        "ext": ".v",
        "badge": "V",
        "badge_color": "#1ED760",
        "compiler_name": "Verilog HDL Synthesizer",
        "desc": "เพิ่มแท็บแสดงผลและส่งออกไฟล์ฮาร์ดแวร์เป็นภาษา Verilog HDL (instruction_memory.v) คู่กับ VHDL",
        "sample_file": None,
        "sample_code": None
    },
]

EXT_TO_CATALOG = {item["ext"]: item for item in EXTENSIONS_CATALOG if item.get("ext")}

# ==============================================================================
# ISA QUICK REFERENCE & REGISTER NAMES
# ==============================================================================
ISA_REFERENCE = {
    "lui":  "U-Type | lui rd, imm20        | โหลดค่าคงที่ 20 บิตขึ้นไปไว้ที่บิต [31:12]",
    "addi": "I-Type | addi rd, rs1, imm12  | บวกค่าคงที่ 12 บิต (Sign-Extended) เข้ากับเรจิสเตอร์",
    "add":  "R-Type | add rd, rs1, rs2     | บวกค่าเรจิสเตอร์ rs1 + rs2 เก็บลง rd",
    "sub":  "R-Type | sub rd, rs1, rs2     | ลบค่าเรจิสเตอร์ rs1 - rs2 เก็บลง rd",
    "lw":   "I-Type | lw rd, offset(rs1)   | อ่านข้อมูล 32-bit จาก Memory / พอร์ต SWITCH",
    "sw":   "S-Type | sw rs2, offset(rs1)  | เขียนข้อมูล 32-bit ลง Memory / พอร์ต LED, SEG7, UART",
    "beq":  "B-Type | beq rs1, rs2, offset | กระโดดถ้า rs1 == rs2 (PC-relative)",
    "bne":  "B-Type | bne rs1, rs2, offset | กระโดดถ้า rs1 != rs2 (PC-relative)",
    "jal":  "J-Type | jal rd, offset       | กระโดดไปยังฟังก์ชันและเก็บ Return Address ลง rd",
    "jalr": "I-Type | jalr rd, offset(rs1) | กระโดดไปยังที่อยู่ในเรจิสเตอร์ rs1 + offset",
}

RV_NAMES = [
    "x0 (zero)", "x1 (ra)", "x2 (sp)", "x3 (gp)", "x4 (tp)", "x5 (t0)", "x6 (t1)", "x7 (t2)",
    "x8 (s0)", "x9 (s1)", "x10 (a0)", "x11 (a1)", "x12 (a2)", "x13 (a3)", "x14 (a4)", "x15 (a5)",
    "x16 (a6)", "x17 (a7)", "x18 (s2)", "x19 (s3)", "x20 (s4)", "x21 (s5)", "x22 (s6)", "x23 (s7)",
    "x24 (s8)", "x25 (s9)", "x26 (s10)", "x27 (s11)", "x28 (t3)", "x29 (t4)", "x30 (t5)", "x31 (t6)"
]

MIPS_NAMES = [
    "$0 ($zero)", "$1 ($at)", "$2 ($v0)", "$3 ($v1)", "$4 ($a0)", "$5 ($a1)", "$6 ($a2)", "$7 ($a3)",
    "$8 ($t0)", "$9 ($t1)", "$10 ($t2)", "$11 ($t3)", "$12 ($t4)", "$13 ($t5)", "$14 ($t6)", "$15 ($t7)",
    "$16 ($s0)", "$17 ($s1)", "$18 ($s2)", "$19 ($s3)", "$20 ($s4)", "$21 ($s5)", "$22 ($s6)", "$23 ($s7)",
    "$24 ($t8)", "$25 ($t9)", "$26 ($k0)", "$27 ($k1)", "$28 ($gp)", "$29 ($sp)", "$30 ($fp)", "$31 ($ra)"
]

# -*- coding: utf-8 -*-
"""
32-Bit Instruction Disassembler & Memory-Mapped I/O Definitions (RISC-V RV32IM & MIPS-I)
"""

# ==============================================================================
# MEMORY-MAPPED I/O DEFINITIONS (Consistent across Compiler, Decoder & Simulator)
# ==============================================================================
MMIO_BASE = 0xF0000000
MMIO_MAP = {
    0xF0000000: ("LED",     "Sim MMIO: ไฟ LED 16 ดวง"),
    0xF0000004: ("SWITCH",  "Sim MMIO: สวิตช์ 16 ตัว"),
    0xF0000008: ("SEG7",    "Sim MMIO: 7-Segment 8 หลัก"),
    0xF000000C: ("BTN",     "Sim MMIO: ปุ่มกดบนบอร์ด"),
    0xF0000010: ("UART_TX", "Sim MMIO: พอร์ตส่งตัวอักษรของโปรเจกต์"),
    0xF0000014: ("UART_RX", "Sim MMIO: พอร์ตรับตัวอักษรของโปรเจกต์"),
    0xF0000018: ("RGB_LED", "Sim MMIO: ไฟ RGB LED 2 ดวง"),
}

RV_REG_NAMES = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"
]

MIPS_REG_NAMES = [
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
]


def sign_extend(val, bits):
    sign_bit = 1 << (bits - 1)
    return (val & (sign_bit - 1)) - (val & sign_bit)


def mask(val, bits):
    return val & ((1 << bits) - 1)


def fmt_ascii_hint(val):
    """Return human-readable ASCII character representation if printable."""
    if val == 10:
        return " ('\\n')"
    if val == 9:
        return " ('\\t')"
    if 32 <= val <= 126:
        return f" ('{chr(val)}')"
    return ""


def reg_num(name):
    """Resolve a RISC-V or MIPS register name/number into a 0..31 integer index."""
    if not name:
        return 0
    raw = name.strip().lower()
    if raw.startswith("$"):
        if raw in MIPS_REG_NAMES:
            return MIPS_REG_NAMES.index(raw)
        clean = raw[1:]
        m_names = [r.replace("$", "") for r in MIPS_REG_NAMES]
        if clean in m_names:
            return m_names.index(clean)
    name = raw.replace("$", "")
    if name.startswith("x") and name[1:].isdigit():
        return int(name[1:])
    if name.startswith("r") and name[1:].isdigit():
        return int(name[1:])
    if name.isdigit():
        return int(name)
    if name in RV_REG_NAMES:
        return RV_REG_NAMES.index(name)
    m_names = [r.replace("$", "") for r in MIPS_REG_NAMES]
    if name in m_names:
        return m_names.index(name)
    return 0


def decode_rv32_word(word, pc=0, sym_map=None, reg_tracker=None):
    """
    Decode a 32-bit RISC-V instruction word into:
      (fmt, fields_str, canonical_asm, description)
    """
    if sym_map is None:
        sym_map = {}
    if reg_tracker is None:
        reg_tracker = {}

    op = word & 0x7F
    rd = (word >> 7) & 0x1F
    f3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    f7 = (word >> 25) & 0x7F

    rd_n = RV_REG_NAMES[rd]
    rs1_n = RV_REG_NAMES[rs1]
    rs2_n = RV_REG_NAMES[rs2]

    # 1. R-TYPE (0110011)
    if op == 0b0110011:
        fmt = "R"
        fields = f"{f7:07b} {rs2:05b} {rs1:05b} {f3:03b} {rd:05b} {op:07b}"
        r_map = {
            (0b0000000, 0b000): ("add",  "+"),
            (0b0100000, 0b000): ("sub",  "-"),
            (0b0000000, 0b001): ("sll",  "<<"),
            (0b0000000, 0b010): ("slt",  "<"),
            (0b0000000, 0b011): ("sltu", "<u"),
            (0b0000000, 0b100): ("xor",  "^"),
            (0b0000000, 0b101): ("srl",  ">>u"),
            (0b0100000, 0b101): ("sra",  ">>s"),
            (0b0000000, 0b110): ("or",   "|"),
            (0b0000000, 0b111): ("and",  "&"),
            (0b0000001, 0b000): ("mul",    "*"),
            (0b0000001, 0b001): ("mulh",   "*h"),
            (0b0000001, 0b010): ("mulhsu", "*hsu"),
            (0b0000001, 0b011): ("mulhu",  "*hu"),
            (0b0000001, 0b100): ("div",    "/"),
            (0b0000001, 0b101): ("divu",   "/u"),
            (0b0000001, 0b110): ("rem",    "%"),
            (0b0000001, 0b111): ("remu",   "%u"),
        }
        mnem, sym = r_map.get((f7, f3), ("r_op", "?"))
        asm = f"{mnem} {rd_n}, {rs1_n}, {rs2_n}"
        desc = f"{rd_n} (x{rd}) = {rs1_n} (x{rs1}) {sym} {rs2_n} (x{rs2})"
        reg_tracker.pop(rd, None)
        return fmt, fields, asm, desc

    # 2. I-TYPE ALU (0010011)
    if op == 0b0010011:
        imm12 = (word >> 20) & 0xFFF
        s_imm = sign_extend(imm12, 12)
        fmt = "I"
        fields = f"{imm12:012b} {rs1:05b} {f3:03b} {rd:05b} {op:07b}"

        if f3 in (0b001, 0b101):
            shamt = rs2
            if f3 == 0b001:
                mnem, sym = "slli", "<<"
            else:
                mnem = "srai" if (f7 & 0b0100000) else "srli"
                sym = ">>"
            asm = f"{mnem} {rd_n}, {rs1_n}, {shamt}"
            desc = f"{rd_n} (x{rd}) = {rs1_n} (x{rs1}) {sym} {shamt}"
            reg_tracker.pop(rd, None)
            return fmt, fields, asm, desc

        i_map = {
            0b000: ("addi",  "+"),
            0b010: ("slti",  "<"),
            0b011: ("sltiu", "<u"),
            0b100: ("xori",  "^"),
            0b110: ("ori",   "|"),
            0b111: ("andi",  "&"),
        }
        mnem, sym = i_map.get(f3, ("addi", "+"))
        asm = f"{mnem} {rd_n}, {rs1_n}, {s_imm}"

        if mnem == "addi" and rs1 == 0:
            if rd != 0:
                reg_tracker[rd] = s_imm
            ascii_note = fmt_ascii_hint(s_imm)
            desc = f"{rd_n} (x{rd}) = {s_imm}{ascii_note}"
        elif mnem == "addi" and rs1 in reg_tracker:
            val = (reg_tracker[rs1] + s_imm) & 0xFFFFFFFF
            if rd != 0:
                reg_tracker[rd] = val
            if val in MMIO_MAP:
                io_name, io_th = MMIO_MAP[val]
                desc = f"{rd_n} (x{rd}) = 0x{val:08X} ({io_name}: {io_th})"
            else:
                desc = f"{rd_n} (x{rd}) = {rs1_n} + {s_imm} (0x{val:08X})"
        else:
            reg_tracker.pop(rd, None)
            desc = f"{rd_n} (x{rd}) = {rs1_n} (x{rs1}) {sym} {s_imm}"
        return fmt, fields, asm, desc

    # 3. I-TYPE LOAD (0000011)
    if op == 0b0000011:
        imm12 = (word >> 20) & 0xFFF
        s_imm = sign_extend(imm12, 12)
        fmt = "I"
        fields = f"{imm12:012b} {rs1:05b} {f3:03b} {rd:05b} {op:07b}"
        ld_map = {0b000: "lb", 0b001: "lh", 0b010: "lw", 0b100: "lbu", 0b101: "lhu"}
        mnem = ld_map.get(f3, "lw")
        asm = f"{mnem} {rd_n}, {s_imm}({rs1_n})"
        if rs1 in reg_tracker:
            eff_addr = (reg_tracker[rs1] + s_imm) & 0xFFFFFFFF
            if eff_addr in MMIO_MAP:
                io_name, io_th = MMIO_MAP[eff_addr]
                desc = f"{rd_n} (x{rd}) <= อ่าน {io_name} (0x{eff_addr:08X}: {io_th})"
            else:
                desc = f"{rd_n} (x{rd}) = MEM[0x{eff_addr:08X}]"
        else:
            desc = f"{rd_n} (x{rd}) = MEM[{rs1_n} + {s_imm}]"
        reg_tracker.pop(rd, None)
        return fmt, fields, asm, desc

    # 4. S-TYPE STORE (0100011)
    if op == 0b0100011:
        imm11_5 = (word >> 25) & 0x7F
        imm4_0 = (word >> 7) & 0x1F
        imm12 = (imm11_5 << 5) | imm4_0
        s_imm = sign_extend(imm12, 12)
        fmt = "S"
        fields = f"{imm11_5:07b} {rs2:05b} {rs1:05b} {f3:03b} {imm4_0:05b} {op:07b}"
        st_map = {0b000: "sb", 0b001: "sh", 0b010: "sw"}
        mnem = st_map.get(f3, "sw")
        asm = f"{mnem} {rs2_n}, {s_imm}({rs1_n})"

        val_hint = ""
        if rs2 == 0:
            val_hint = " = 0"
        elif rs2 in reg_tracker:
            v = reg_tracker[rs2]
            val_hint = f" = {v}{fmt_ascii_hint(v)}"

        if rs1 in reg_tracker:
            eff_addr = (reg_tracker[rs1] + s_imm) & 0xFFFFFFFF
            if eff_addr in MMIO_MAP:
                io_name, _ = MMIO_MAP[eff_addr]
                desc = f"MMIO[0x{eff_addr:08X}:{io_name}] <= {rs2_n}{val_hint}"
            else:
                desc = f"MEM[0x{eff_addr:08X}] <= {rs2_n}{val_hint}"
        else:
            desc = f"MEM[{rs1_n} + {s_imm}] <= {rs2_n}{val_hint}"
        return fmt, fields, asm, desc

    # 5. B-TYPE BRANCH (1100011)
    if op == 0b1100011:
        b12 = (word >> 31) & 1
        b10_5 = (word >> 25) & 0x3F
        b4_1 = (word >> 8) & 0xF
        b11 = (word >> 7) & 1
        imm13 = (b12 << 12) | (b11 << 11) | (b10_5 << 5) | (b4_1 << 1)
        s_imm = sign_extend(imm13, 13)
        target_pc = (pc + s_imm) & 0xFFFFFFFF
        fmt = "B"
        fields = f"{b12:01b}{b10_5:06b} {rs2:05b} {rs1:05b} {f3:03b} {b4_1:04b}{b11:01b} {op:07b}"
        b_map = {
            0b000: ("beq",  "=="),
            0b001: ("bne",  "!="),
            0b100: ("blt",  "<"),
            0b101: ("bge",  ">="),
            0b110: ("bltu", "<u"),
            0b111: ("bgeu", ">=u"),
        }
        mnem, sym = b_map.get(f3, ("beq", "=="))
        lbl = sym_map.get(target_pc, f"0x{target_pc:04X}")
        asm = f"{mnem} {rs1_n}, {rs2_n}, {s_imm} <{lbl}>"
        desc = f"if ({rs1_n} {sym} {rs2_n}) PC += {s_imm} (-> 0x{target_pc:04X} {lbl})"
        return fmt, fields, asm, desc

    # 6. U-TYPE LUI / AUIPC (0110111 / 0010111)
    if op in (0b0110111, 0b0010111):
        imm20 = (word >> 12) & 0xFFFFF
        fmt = "U"
        fields = f"{imm20:020b} {rd:05b} {op:07b}"
        if op == 0b0110111:
            val = (imm20 << 12) & 0xFFFFFFFF
            if rd != 0:
                reg_tracker[rd] = val
            asm = f"lui {rd_n}, 0x{imm20:X}"
            if val == MMIO_BASE:
                desc = f"{rd_n} (x{rd}) = 0x{val:08X} (ตั้ง Base Address ของ I/O)"
            else:
                desc = f"{rd_n} (x{rd}) = 0x{imm20:X} << 12 (0x{val:08X})"
        else:
            val = (pc + (imm20 << 12)) & 0xFFFFFFFF
            if rd != 0:
                reg_tracker[rd] = val
            asm = f"auipc {rd_n}, 0x{imm20:X}"
            desc = f"{rd_n} (x{rd}) = PC + (0x{imm20:X} << 12) = 0x{val:08X}"
        return fmt, fields, asm, desc

    # 7. J-TYPE JAL (1101111)
    if op == 0b1101111:
        b20 = (word >> 31) & 1
        b10_1 = (word >> 21) & 0x3FF
        b11 = (word >> 20) & 1
        b19_12 = (word >> 12) & 0xFF
        imm21 = (b20 << 20) | (b19_12 << 12) | (b11 << 11) | (b10_1 << 1)
        s_imm = sign_extend(imm21, 21)
        target_pc = (pc + s_imm) & 0xFFFFFFFF
        fmt = "J"
        fields = f"{b20:01b}{b10_1:010b}{b11:01b}{b19_12:08b} {rd:05b} {op:07b}"
        lbl = sym_map.get(target_pc, f"0x{target_pc:04X}")
        if rd == 0:
            asm = f"j {lbl} <0x{target_pc:04X}>" if lbl != f"0x{target_pc:04X}" else f"j 0x{target_pc:04X}"
            if s_imm == 0:
                desc = f"วนลูปหยุดรอที่ 0x{target_pc:04X} <{lbl}>"
            else:
                desc = f"กระโดดไปยัง 0x{target_pc:04X} <{lbl}>"
        else:
            asm = f"jal {rd_n}, {lbl} <0x{target_pc:04X}>" if lbl != f"0x{target_pc:04X}" else f"jal {rd_n}, 0x{target_pc:04X}"
            desc = f"{rd_n} = 0x{pc+4:04X}; PC = 0x{target_pc:04X} (เรียกฟังก์ชัน {lbl})"
        reg_tracker.pop(rd, None)
        return fmt, fields, asm, desc

    # 8. I-TYPE JALR (1100111)
    if op == 0b1100111:
        imm12 = (word >> 20) & 0xFFF
        s_imm = sign_extend(imm12, 12)
        fmt = "I"
        fields = f"{imm12:012b} {rs1:05b} {f3:03b} {rd:05b} {op:07b}"
        asm = f"jalr {rd_n}, {s_imm}({rs1_n})"
        if rd == 0 and rs1 == 1 and s_imm == 0:
            desc = "PC = ra (จบฟังก์ชัน กลับไปยังจุดเรียก)"
        else:
            desc = f"PC = {rs1_n} + {s_imm}"
        reg_tracker.pop(rd, None)
        return fmt, fields, asm, desc

    # 9. SYSTEM (ecall / ebreak - 1110011)
    if op == 0b1110011:
        fmt = "I"
        fields = f"{word:032b}"
        if word == 0x00100073 or (word >> 20) == 1:
            return fmt, fields, "ebreak", "Environment Break (Debugger Breakpoint)"
        return fmt, fields, "ecall", "Environment Call (System Call / Trap to OS)"

    return "R", f"{word:032b}", f".word 0x{word:08X}", "Custom / System Instruction"


def decode_mips_word(word, pc=0, sym_map=None, reg_tracker=None):
    """
    Decode a 32-bit MIPS-I instruction word into:
      (fmt, fields_str, canonical_asm, description)
    """
    if sym_map is None:
        sym_map = {}
    if reg_tracker is None:
        reg_tracker = {}

    op = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    shamt = (word >> 6) & 0x1F
    funct = word & 0x3F
    imm16 = word & 0xFFFF
    s_imm16 = sign_extend(imm16, 16)
    target26 = word & 0x03FFFFFF

    rs_n = MIPS_REG_NAMES[rs]
    rt_n = MIPS_REG_NAMES[rt]
    rd_n = MIPS_REG_NAMES[rd]

    # 1. R-Type (op == 0)
    if op == 0:
        fmt = "R"
        fields = f"{op:06b} {rs:05b} {rt:05b} {rd:05b} {shamt:05b} {funct:06b}"
        if funct == 0x00:
            if rd == 0 and rt == 0 and shamt == 0:
                return "R", fields, "nop", "No Operation"
            return "R", fields, f"sll {rd_n}, {rt_n}, {shamt}", f"{rd_n} = {rt_n} << {shamt}"
        elif funct == 0x02:
            return "R", fields, f"srl {rd_n}, {rt_n}, {shamt}", f"{rd_n} = {rt_n} >> {shamt}"
        elif funct == 0x03:
            return "R", fields, f"sra {rd_n}, {rt_n}, {shamt}", f"{rd_n} = {rt_n} >> {shamt} (arithmetic)"
        elif funct == 0x04:
            return "R", fields, f"sllv {rd_n}, {rt_n}, {rs_n}", f"{rd_n} = {rt_n} << {rs_n}"
        elif funct == 0x06:
            return "R", fields, f"srlv {rd_n}, {rt_n}, {rs_n}", f"{rd_n} = {rt_n} >> {rs_n}"
        elif funct == 0x07:
            return "R", fields, f"srav {rd_n}, {rt_n}, {rs_n}", f"{rd_n} = {rt_n} >> {rs_n} (arithmetic)"
        elif funct == 0x08:
            return "R", fields, f"jr {rs_n}", f"PC = {rs_n} (จบฟังก์ชัน / กระโดดกลับ)"
        elif funct == 0x09:
            return "R", fields, f"jalr {rd_n}, {rs_n}", f"{rd_n} = PC + 8; PC = {rs_n}"
        elif funct == 0x0C:
            return "R", fields, "syscall", "System Call (MARS / Trap to OS)"
        elif funct == 0x0D:
            code = (word >> 6) & 0xFFFFF
            return "R", fields, (f"break {code}" if code else "break"), "Breakpoint (Debugger Trap)"
        elif funct == 0x0A:
            return "R", fields, f"movz {rd_n}, {rs_n}, {rt_n}", f"if ({rt_n} == 0) {rd_n} = {rs_n}"
        elif funct == 0x0B:
            return "R", fields, f"movn {rd_n}, {rs_n}, {rt_n}", f"if ({rt_n} != 0) {rd_n} = {rs_n}"
        elif funct == 0x10:
            return "R", fields, f"mfhi {rd_n}", f"{rd_n} = HI"
        elif funct == 0x11:
            return "R", fields, f"mthi {rs_n}", f"HI = {rs_n}"
        elif funct == 0x12:
            return "R", fields, f"mflo {rd_n}", f"{rd_n} = LO"
        elif funct == 0x13:
            return "R", fields, f"mtlo {rs_n}", f"LO = {rs_n}"
        elif funct == 0x18:
            return "R", fields, f"mult {rs_n}, {rt_n}", f"HI:LO = {rs_n} * {rt_n} (signed)"
        elif funct == 0x19:
            return "R", fields, f"multu {rs_n}, {rt_n}", f"HI:LO = {rs_n} * {rt_n} (unsigned)"
        elif funct == 0x1A:
            return "R", fields, f"div {rs_n}, {rt_n}", f"LO = {rs_n} / {rt_n}, HI = {rs_n} % {rt_n}"
        elif funct == 0x1B:
            return "R", fields, f"divu {rs_n}, {rt_n}", f"LO = {rs_n} /u {rt_n}, HI = {rs_n} %u {rt_n}"
        elif funct == 0x20:
            return "R", fields, f"add {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} + {rt_n}"
        elif funct == 0x21:
            return "R", fields, f"addu {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} + {rt_n}"
        elif funct == 0x22:
            return "R", fields, f"sub {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} - {rt_n}"
        elif funct == 0x23:
            return "R", fields, f"subu {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} - {rt_n}"
        elif funct == 0x24:
            return "R", fields, f"and {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} & {rt_n}"
        elif funct == 0x25:
            return "R", fields, f"or {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} | {rt_n}"
        elif funct == 0x26:
            return "R", fields, f"xor {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} ^ {rt_n}"
        elif funct == 0x27:
            return "R", fields, f"nor {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = ~({rs_n} | {rt_n})"
        elif funct == 0x2A:
            return "R", fields, f"slt {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = ({rs_n} < {rt_n}) ? 1 : 0"
        elif funct == 0x2B:
            return "R", fields, f"sltu {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = ({rs_n} <u {rt_n}) ? 1 : 0"

    # 1B. SPECIAL2 (op == 0x1C, e.g. mul)
    elif op == 0x1C and funct == 0x02:
        fields = f"{op:06b} {rs:05b} {rt:05b} {rd:05b} {shamt:05b} {funct:06b}"
        return "R", fields, f"mul {rd_n}, {rs_n}, {rt_n}", f"{rd_n} = {rs_n} * {rt_n}"

    # 2. J-Type
    elif op == 0x02:
        fmt = "J"
        fields = f"{op:06b} {target26:026b}"
        target_byte = target26 * 4
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        asm_target = lbl if lbl != f"0x{target_byte:04X}" else f"0x{target_byte:04X}"
        return fmt, fields, f"j {asm_target}", f"PC = 0x{target_byte:04X} <{lbl}>"
    elif op == 0x03:
        fmt = "J"
        fields = f"{op:06b} {target26:026b}"
        target_byte = target26 * 4
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        asm_target = lbl if lbl != f"0x{target_byte:04X}" else f"0x{target_byte:04X}"
        return fmt, fields, f"jal {asm_target}", f"$ra = 0x{pc+8:04X}; PC = 0x{target_byte:04X} (เรียกฟังก์ชัน {lbl})"

    # 3. I-Type
    fmt = "I"
    fields = f"{op:06b} {rs:05b} {rt:05b} {imm16:016b}"
    if op == 0x01 and rt in (0x00, 0x01):
        mnem = "bltz" if rt == 0x00 else "bgez"
        sym = "<" if rt == 0x00 else ">="
        target_byte = (pc + 4 + s_imm16 * 4) & 0xFFFFFFFF
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        return fmt, fields, f"{mnem} {rs_n}, {s_imm16*4} <{lbl}>", f"if ({rs_n} {sym} 0) PC += {s_imm16*4}"
    elif op == 0x08:
        return fmt, fields, f"addi {rt_n}, {rs_n}, {s_imm16}", f"{rt_n} = {rs_n} + {s_imm16}"
    elif op == 0x09:
        return fmt, fields, f"addiu {rt_n}, {rs_n}, {s_imm16}", f"{rt_n} = {rs_n} + {s_imm16}"
    elif op == 0x0C:
        return fmt, fields, f"andi {rt_n}, {rs_n}, {imm16}", f"{rt_n} = {rs_n} & 0x{imm16:04X}"
    elif op == 0x0D:
        return fmt, fields, f"ori {rt_n}, {rs_n}, {imm16}", f"{rt_n} = {rs_n} | 0x{imm16:04X}"
    elif op == 0x0E:
        return fmt, fields, f"xori {rt_n}, {rs_n}, {imm16}", f"{rt_n} = {rs_n} ^ 0x{imm16:04X}"
    elif op == 0x0F:
        val = (imm16 << 16) & 0xFFFFFFFF
        return fmt, fields, f"lui {rt_n}, 0x{imm16:04X}", f"{rt_n} = 0x{val:08X}"
    elif op == 0x0A:
        return fmt, fields, f"slti {rt_n}, {rs_n}, {s_imm16}", f"{rt_n} = ({rs_n} < {s_imm16}) ? 1 : 0"
    elif op == 0x0B:
        return fmt, fields, f"sltiu {rt_n}, {rs_n}, {s_imm16}", f"{rt_n} = ({rs_n} <u {s_imm16 & 0xFFFFFFFF}) ? 1 : 0"
    elif op == 0x04:
        target_byte = (pc + 4 + s_imm16 * 4) & 0xFFFFFFFF
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        return fmt, fields, f"beq {rs_n}, {rt_n}, {s_imm16*4} <{lbl}>", f"if ({rs_n} == {rt_n}) PC += {s_imm16*4}"
    elif op == 0x05:
        target_byte = (pc + 4 + s_imm16 * 4) & 0xFFFFFFFF
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        return fmt, fields, f"bne {rs_n}, {rt_n}, {s_imm16*4} <{lbl}>", f"if ({rs_n} != {rt_n}) PC += {s_imm16*4}"
    elif op in (0x06, 0x07):
        mnem = "blez" if op == 0x06 else "bgtz"
        sym = "<=" if op == 0x06 else ">"
        target_byte = (pc + 4 + s_imm16 * 4) & 0xFFFFFFFF
        lbl = sym_map.get(target_byte, f"0x{target_byte:04X}")
        return fmt, fields, f"{mnem} {rs_n}, {s_imm16*4} <{lbl}>", f"if ({rs_n} {sym} 0) PC += {s_imm16*4}"
    elif op == 0x23:
        return fmt, fields, f"lw {rt_n}, {s_imm16}({rs_n})", f"{rt_n} = MEM[{rs_n} + {s_imm16}]"
    elif op == 0x2B:
        return fmt, fields, f"sw {rt_n}, {s_imm16}({rs_n})", f"MEM[{rs_n} + {s_imm16}] <= {rt_n}"
    elif op == 0x21:
        return fmt, fields, f"lh {rt_n}, {s_imm16}({rs_n})", f"{rt_n} = MEM_HALF[{rs_n} + {s_imm16}]"
    elif op == 0x25:
        return fmt, fields, f"lhu {rt_n}, {s_imm16}({rs_n})", f"{rt_n} = MEM_UHALF[{rs_n} + {s_imm16}]"
    elif op == 0x29:
        return fmt, fields, f"sh {rt_n}, {s_imm16}({rs_n})", f"MEM_HALF[{rs_n} + {s_imm16}] <= {rt_n} & 0xFFFF"
    elif op == 0x20:
        return fmt, fields, f"lb {rt_n}, {s_imm16}({rs_n})", f"{rt_n} = MEM_BYTE[{rs_n} + {s_imm16}]"
    elif op == 0x24:
        return fmt, fields, f"lbu {rt_n}, {s_imm16}({rs_n})", f"{rt_n} = MEM_UBYTE[{rs_n} + {s_imm16}]"
    elif op == 0x28:
        return fmt, fields, f"sb {rt_n}, {s_imm16}({rs_n})", f"MEM_BYTE[{rs_n} + {s_imm16}] <= {rt_n} & 0xFF"

    return "U", f"{word:032b}", f".word 0x{word:08X}", "Custom / Unknown Instruction"

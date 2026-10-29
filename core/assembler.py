# -*- coding: utf-8 -*-
"""
Direct 32-Bit Assemblers for RISC-V (RV32I/M) and MIPS (MIPS-I)
"""

import re
from core.disassembler import (
    MMIO_MAP,
    MIPS_REG_NAMES,
    sign_extend,
    mask,
    fmt_ascii_hint,
    reg_num,
    decode_rv32_word,
)


def assemble_riscv(asm_lines):
    """Assemble RV32I/M instructions into 32-bit machine code words."""
    if isinstance(asm_lines, str):
        asm_lines = asm_lines.splitlines()

    # Pass 0: Expand multi-instruction pseudo-instructions (e.g., 32-bit li) before label assignment
    expanded_lines = []
    for raw in asm_lines:
        line = raw.split("#")[0].split("//")[0].strip()
        if not line:
            continue
        lbls = []
        while re.match(r"^[A-Za-z0-9_.$]+\s*:", line):
            lbl, line = line.split(":", 1)
            lbls.append(lbl.strip() + ":")
            line = line.strip()
        for l in lbls:
            expanded_lines.append(l)
        if not line:
            continue
        line_clean = re.sub(r"\s*<[^>]+>", "", line).strip()
        if line_clean.startswith(".") and not line_clean.lower().startswith(".word"):
            continue
        parts = re.split(r"[\s,]+", line_clean, maxsplit=1)
        mnem = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []
        if (mnem == "li" and len(args) == 2) or (
            mnem in ("addi", "addiu") and len(args) == 3 and args[1].lower() in ("x0", "zero", "$zero", "$0", "0")
        ):
            imm_str = args[1] if mnem == "li" else args[2]
            try:
                imm_val = int(imm_str, 0)
                if imm_val < -2048 or imm_val > 2047:
                    val32 = imm_val & 0xFFFFFFFF
                    lo12 = sign_extend(val32 & 0xFFF, 12)
                    hi20 = ((val32 - lo12) >> 12) & 0xFFFFF
                    expanded_lines.append(f"lui {args[0]}, 0x{hi20:X}")
                    if lo12 != 0:
                        expanded_lines.append(f"addi {args[0]}, {args[0]}, {lo12}")
                    continue
            except Exception:
                pass
        expanded_lines.append(line)

    labels = {}
    sym_map = {}
    cleaned = []
    pc = 0
    for raw in expanded_lines:
        line = raw.split("#")[0].split("//")[0].strip()
        if not line:
            continue
        while re.match(r"^[A-Za-z0-9_.$]+\s*:", line):
            lbl, line = line.split(":", 1)
            lbl_name = lbl.strip()
            labels[lbl_name] = pc
            sym_map[pc] = lbl_name
            line = line.strip()
        if line:
            cleaned.append((pc, line))
            pc += 4

    out = []
    reg_tracker = {}
    for pc, line in cleaned:
        line_clean = re.sub(r"\s*<[^>]+>", "", line).strip()
        parts = re.split(r"[\s,]+", line_clean, maxsplit=1)
        mnemonic = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

        # Pseudo-instructions
        if mnemonic == "nop":
            mnemonic, args = "addi", ["x0", "x0", "0"]
        elif mnemonic in ("mv", "move") and len(args) == 2:
            mnemonic, args = "addi", [args[0], args[1], "0"]
        elif mnemonic == "li" and len(args) == 2:
            imm = int(args[1], 0)
            mnemonic, args = "addi", [args[0], "x0", str(imm)]
        elif mnemonic == "seqz" and len(args) == 2:
            mnemonic, args = "sltiu", [args[0], args[1], "1"]
        elif mnemonic == "snez" and len(args) == 2:
            mnemonic, args = "sltu", [args[0], "x0", args[1]]
        elif mnemonic in ("neg", "negu") and len(args) == 2:
            mnemonic, args = "sub", [args[0], "x0", args[1]]
        elif mnemonic == "not" and len(args) == 2:
            mnemonic, args = "xori", [args[0], args[1], "-1"]
        elif mnemonic == "beqz" and len(args) == 2:
            mnemonic, args = "beq", [args[0], "x0", args[1]]
        elif mnemonic == "bnez" and len(args) == 2:
            mnemonic, args = "bne", [args[0], "x0", args[1]]
        elif mnemonic == "ble" and len(args) == 3:
            mnemonic, args = "bge", [args[1], args[0], args[2]]
        elif mnemonic == "bgt" and len(args) == 3:
            mnemonic, args = "blt", [args[1], args[0], args[2]]
        elif mnemonic == "bleu" and len(args) == 3:
            mnemonic, args = "bgeu", [args[1], args[0], args[2]]
        elif mnemonic == "bgtu" and len(args) == 3:
            mnemonic, args = "bltu", [args[1], args[0], args[2]]
        elif mnemonic == "j" and len(args) == 1:
            mnemonic, args = "jal", ["x0", args[0]]
        elif mnemonic == "call" and len(args) == 1:
            mnemonic, args = "jal", ["ra", args[0]]
        elif mnemonic == "jr" and len(args) == 1:
            mnemonic, args = "jalr", ["x0", f"0({args[0]})"]
        elif mnemonic == "ret":
            mnemonic, args = "jalr", ["x0", "0(ra)"]

        word = 0
        r_ops = {
            "add":    (0b0000000, 0b000),
            "sub":    (0b0100000, 0b000),
            "sll":    (0b0000000, 0b001),
            "slt":    (0b0000000, 0b010),
            "sltu":   (0b0000000, 0b011),
            "xor":    (0b0000000, 0b100),
            "srl":    (0b0000000, 0b101),
            "sra":    (0b0100000, 0b101),
            "or":     (0b0000000, 0b110),
            "and":    (0b0000000, 0b111),
            "mul":    (0b0000001, 0b000),
            "mulh":   (0b0000001, 0b001),
            "mulhsu": (0b0000001, 0b010),
            "mulhu":  (0b0000001, 0b011),
            "div":    (0b0000001, 0b100),
            "divu":   (0b0000001, 0b101),
            "rem":    (0b0000001, 0b110),
            "remu":   (0b0000001, 0b111),
        }
        i_ops = {
            "addi": 0b000, "addiu": 0b000,
            "slti": 0b010, "sltiu": 0b011,
            "xori": 0b100, "ori":   0b110, "andi": 0b111,
        }
        shift_i_ops = {
            "slli": (0b0000000, 0b001),
            "srli": (0b0000000, 0b101),
            "srai": (0b0100000, 0b101),
        }
        ld_ops = {"lb": 0b000, "lh": 0b001, "lw": 0b010, "lbu": 0b100, "lhu": 0b101}
        st_ops = {"sb": 0b000, "sh": 0b001, "sw": 0b010}
        b_ops = {
            "beq": 0b000, "bne": 0b001,
            "blt": 0b100, "bge": 0b101,
            "bltu": 0b110, "bgeu": 0b111,
        }

        if mnemonic in r_ops:
            f7, f3 = r_ops[mnemonic]
            rd, rs1, rs2 = reg_num(args[0]), reg_num(args[1]), reg_num(args[2])
            word = (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0b0110011
        elif mnemonic in shift_i_ops:
            f7, f3 = shift_i_ops[mnemonic]
            rd, rs1 = reg_num(args[0]), reg_num(args[1])
            shamt = int(args[2], 0) & 0x1F
            word = (f7 << 25) | (shamt << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0b0010011
        elif mnemonic in i_ops:
            f3 = i_ops[mnemonic]
            rd, rs1 = reg_num(args[0]), reg_num(args[1])
            imm = mask(int(args[2], 0), 12)
            word = (imm << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0b0010011
        elif mnemonic in ld_ops:
            f3 = ld_ops[mnemonic]
            rd = reg_num(args[0])
            m = re.match(r"([-\dxXa-fA-F]+)\(([^)]+)\)", args[1])
            imm = mask(int(m.group(1), 0), 12) if m else 0
            rs1 = reg_num(m.group(2)) if m else 0
            word = (imm << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0b0000011
        elif mnemonic in st_ops:
            f3 = st_ops[mnemonic]
            rs2 = reg_num(args[0])
            m = re.match(r"([-\dxXa-fA-F]+)\(([^)]+)\)", args[1])
            imm_val = int(m.group(1), 0) if m else 0
            imm = mask(imm_val, 12)
            rs1 = reg_num(m.group(2)) if m else 0
            imm11_5 = (imm >> 5) & 0x7F
            imm4_0 = imm & 0x1F
            word = (imm11_5 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (imm4_0 << 7) | 0b0100011
        elif mnemonic in b_ops:
            f3 = b_ops[mnemonic]
            rs1, rs2 = reg_num(args[0]), reg_num(args[1])
            target = args[2]
            offset = (labels[target] - pc) if target in labels else int(target, 0)
            imm = mask(offset, 13)
            b12, b11 = (imm >> 12) & 1, (imm >> 11) & 1
            b10_5, b4_1 = (imm >> 5) & 0x3F, (imm >> 1) & 0xF
            word = (b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (b4_1 << 8) | (b11 << 7) | 0b1100011
        elif mnemonic == "lui":
            rd = reg_num(args[0])
            imm = mask(int(args[1], 0), 20)
            word = (imm << 12) | (rd << 7) | 0b0110111
        elif mnemonic == "auipc":
            rd = reg_num(args[0])
            imm = mask(int(args[1], 0), 20)
            word = (imm << 12) | (rd << 7) | 0b0010111
        elif mnemonic == "jal":
            if len(args) == 1:
                rd, target = 1, args[0]
            else:
                rd, target = reg_num(args[0]), args[1]
            offset = (labels[target] - pc) if target in labels else int(target, 0)
            imm = mask(offset, 21)
            b20, b19_12 = (imm >> 20) & 1, (imm >> 12) & 0xFF
            b11, b10_1 = (imm >> 11) & 1, (imm >> 1) & 0x3FF
            word = (b20 << 31) | (b10_1 << 21) | (b11 << 20) | (b19_12 << 12) | (rd << 7) | 0b1101111
        elif mnemonic == "jalr":
            rd = reg_num(args[0])
            m = re.match(r"([-\dxXa-fA-F]+)\(([^)]+)\)", args[1])
            if m:
                imm = mask(int(m.group(1), 0), 12)
                rs1 = reg_num(m.group(2))
            else:
                rs1 = reg_num(args[1])
                imm = mask(int(args[2], 0), 12) if len(args) > 2 else 0
            word = (imm << 20) | (rs1 << 15) | (0b000 << 12) | (rd << 7) | 0b1100111
        elif mnemonic in ("ecall", "syscall", "scall"):
            word = 0x00000073
        elif mnemonic in ("ebreak", "break", "sbreak"):
            word = 0x00100073
        elif mnemonic in (".word", "word") and args:
            word = int(args[0], 0) & 0xFFFFFFFF
            out.append({
                "pc": f"0x{pc:04X}",
                "pc_int": pc,
                "asm": f".word 0x{word:08X}",
                "hex": f"0x{word:08X}",
                "bin": f"{word:032b}",
                "fields": f"{word:032b}",
                "fmt": "DATA",
                "desc": f"Constant Data / String: 0x{word:08X}",
                "word": word,
            })
            continue

        fmt, fields, canonical_asm, desc = decode_rv32_word(word, pc=pc, sym_map=sym_map, reg_tracker=reg_tracker)
        out.append({
            "pc": f"0x{pc:04X}",
            "pc_int": pc,
            "asm": canonical_asm,
            "hex": f"0x{word:08X}",
            "bin": f"{word:032b}",
            "fields": fields,
            "fmt": fmt,
            "desc": desc,
            "word": word,
        })
    return out


def assemble_mips(asm_lines):
    """Assemble MIPS-I / PyMIPS instructions into 32-bit machine code words."""
    if isinstance(asm_lines, str):
        asm_lines = asm_lines.splitlines()

    # Pass 0: Pre-expansion of 3-operand mul, div, rem before label assignment
    expanded_lines = []
    for raw in asm_lines:
        line = raw.split("#")[0].split("//")[0].strip()
        if not line:
            continue
        lbls = []
        while re.match(r"^[A-Za-z0-9_.$]+\s*:", line):
            lbl, line = line.split(":", 1)
            lbls.append(lbl.strip() + ":")
            line = line.strip()
        for l in lbls:
            expanded_lines.append(l)
        if not line:
            continue

        line_clean = re.sub(r"\s*<[^>]+>", "", line).strip()
        parts = re.split(r"[\s,]+", line_clean, maxsplit=1)
        mnem = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

        if mnem == "mul" and len(args) == 3:
            rd, rs, rt = args[0], args[1], args[2]
            expanded_lines.append(f"mult {rs}, {rt}")
            expanded_lines.append(f"mflo {rd}")
        elif mnem in ("mulh", "mulhsu") and len(args) == 3:
            rd, rs, rt = args[0], args[1], args[2]
            expanded_lines.append(f"mult {rs}, {rt}")
            expanded_lines.append(f"mfhi {rd}")
        elif mnem == "mulhu" and len(args) == 3:
            rd, rs, rt = args[0], args[1], args[2]
            expanded_lines.append(f"multu {rs}, {rt}")
            expanded_lines.append(f"mfhi {rd}")
        elif mnem in ("div", "divu") and len(args) == 3:
            rd, rs, rt = args[0], args[1], args[2]
            expanded_lines.append(f"{mnem} {rs}, {rt}")
            expanded_lines.append(f"mflo {rd}")
        elif mnem in ("rem", "remu") and len(args) == 3:
            rd, rs, rt = args[0], args[1], args[2]
            div_op = "div" if mnem == "rem" else "divu"
            expanded_lines.append(f"{div_op} {rs}, {rt}")
            expanded_lines.append(f"mfhi {rd}")
        elif mnem == "seqz" and len(args) == 2:
            expanded_lines.append(f"sltiu {args[0]}, {args[1]}, 1")
        elif mnem == "snez" and len(args) == 2:
            expanded_lines.append(f"sltu {args[0]}, $zero, {args[1]}")
        elif mnem == "sltz" and len(args) == 2:
            expanded_lines.append(f"slt {args[0]}, {args[1]}, $zero")
        elif mnem == "sgtz" and len(args) == 2:
            expanded_lines.append(f"slt {args[0]}, $zero, {args[1]}")
        elif mnem == "li" and len(args) == 2:
            try:
                iv = int(args[1], 0)
                if iv < -32768 or iv > 65535:
                    val32 = iv & 0xFFFFFFFF
                    u16 = (val32 >> 16) & 0xFFFF
                    l16 = val32 & 0xFFFF
                    expanded_lines.append(f"lui {args[0]}, 0x{u16:04X}")
                    if l16 != 0:
                        expanded_lines.append(f"ori {args[0]}, {args[0]}, 0x{l16:04X}")
                    continue
            except Exception:
                pass
            expanded_lines.append(line)
        elif line_clean.startswith(".") and not line_clean.lower().startswith(".word"):
            continue
        else:
            expanded_lines.append(line)

    labels = {}
    cleaned = []
    idx_pc = 0
    for raw in expanded_lines:
        line = raw.split("#")[0].split("//")[0].strip()
        if not line:
            continue
        while re.match(r"^[A-Za-z0-9_.$]+\s*:", line):
            lbl, line = line.split(":", 1)
            labels[lbl.strip()] = idx_pc
            line = line.strip()
        if line:
            cleaned.append((idx_pc, line))
            idx_pc += 1

    out = []
    reg_tracker = {}
    for idx_pc, line in cleaned:
        line_clean = re.sub(r"\s*<[^>]+>", "", line).strip()
        parts = re.split(r"[\s,]+", line_clean, maxsplit=1)
        mnemonic = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

        word = 0
        fmt = "R"
        fields = ""
        desc = ""

        # Pseudo-instructions normalization
        if mnemonic == "nop":
            mnemonic, args = "sll", ["$zero", "$zero", "0"]
        elif mnemonic == "li" and len(args) == 2:
            try:
                iv = int(args[1], 0)
                if -32768 <= iv <= 32767:
                    mnemonic, args = "addiu", [args[0], "$zero", str(iv)]
                elif 0 <= iv <= 65535:
                    mnemonic, args = "ori", [args[0], "$zero", str(iv)]
                else:
                    mnemonic, args = "addiu", [args[0], "$zero", str(iv & 0xFFFF)]
            except Exception:
                mnemonic, args = "addiu", [args[0], "$zero", args[1]]
        elif mnemonic in ("move", "mv") and len(args) == 2:
            mnemonic, args = "addu", [args[0], args[1], "$zero"]
        elif mnemonic == "ret":
            mnemonic, args = "jr", ["$ra"]
        elif mnemonic == "bnez" and len(args) == 2:
            mnemonic, args = "bne", [args[0], "$zero", args[1]]
        elif mnemonic == "beqz" and len(args) == 2:
            mnemonic, args = "beq", [args[0], "$zero", args[1]]
        elif mnemonic == "not" and len(args) == 2:
            mnemonic, args = "nor", [args[0], args[1], "$zero"]
        elif mnemonic == "negu" and len(args) == 2:
            mnemonic, args = "subu", [args[0], "$zero", args[1]]

        r_funct = {
            "add":  (0x20, "+"),    "addu": (0x21, "+"),
            "sub":  (0x22, "-"),    "subu": (0x23, "-"),
            "and":  (0x24, "&"),    "or":   (0x25, "|"),
            "xor":  (0x26, "^"),    "nor":  (0x27, "~|"),
            "slt":  (0x2A, "<"),    "sltu": (0x2B, "<(u)"),
        }

        if mnemonic in r_funct:
            fn, sym = r_funct[mnemonic]
            rd, rs, rt = reg_num(args[0]), reg_num(args[1]), reg_num(args[2])
            op = 0
            word = (op << 26) | (rs << 21) | (rt << 16) | (rd << 11) | fn
            fmt = "R"
            fields = f"{op:06b} {rs:05b} {rt:05b} {rd:05b} 00000 {fn:06b}"
            desc = f"{MIPS_REG_NAMES[rd]} = {MIPS_REG_NAMES[rs]} {sym} {MIPS_REG_NAMES[rt]}"
            reg_tracker.pop(rd, None)

        elif mnemonic in ("sll", "srl", "sra"):
            is_var_shift = False
            if len(args) > 2:
                arg2_clean = args[2].strip()
                if arg2_clean.startswith("$") or not arg2_clean.lstrip("-").isdigit():
                    is_var_shift = True
            if is_var_shift:
                fn = {"sll": 0x04, "srl": 0x06, "sra": 0x07}[mnemonic]
                rd, rt, rs = reg_num(args[0]), reg_num(args[1]), reg_num(args[2])
                word = (rs << 21) | (rt << 16) | (rd << 11) | fn
                fmt = "R"
                fields = f"000000 {rs:05b} {rt:05b} {rd:05b} 00000 {fn:06b}"
                op_sym = "<<" if mnemonic == "sll" else (">>>" if mnemonic == "srl" else ">>")
                desc = f"{MIPS_REG_NAMES[rd]} = {MIPS_REG_NAMES[rt]} {op_sym} {MIPS_REG_NAMES[rs]}"
                reg_tracker.pop(rd, None)
            else:
                fn = {"sll": 0x00, "srl": 0x02, "sra": 0x03}[mnemonic]
                rd, rt = reg_num(args[0]), reg_num(args[1])
                try:
                    shamt = int(args[2], 0) & 0x1F
                except Exception:
                    shamt = 0
                word = (rt << 16) | (rd << 11) | (shamt << 6) | fn
                fmt = "R"
                fields = f"000000 00000 {rt:05b} {rd:05b} {shamt:05b} {fn:06b}"
                op_sym = "<<" if mnemonic == "sll" else (">>>" if mnemonic == "srl" else ">>")
                desc = f"{MIPS_REG_NAMES[rd]} = {MIPS_REG_NAMES[rt]} {op_sym} {shamt}"
                reg_tracker.pop(rd, None)

        elif mnemonic in ("sllv", "srlv", "srav"):
            fn = {"sllv": 0x04, "srlv": 0x06, "srav": 0x07}[mnemonic]
            rd, rt, rs = reg_num(args[0]), reg_num(args[1]), reg_num(args[2])
            word = (rs << 21) | (rt << 16) | (rd << 11) | fn
            fmt = "R"
            fields = f"000000 {rs:05b} {rt:05b} {rd:05b} 00000 {fn:06b}"
            op_sym = "<<" if mnemonic == "sllv" else (">>>" if mnemonic == "srlv" else ">>")
            desc = f"{MIPS_REG_NAMES[rd]} = {MIPS_REG_NAMES[rt]} {op_sym} {MIPS_REG_NAMES[rs]}"
            reg_tracker.pop(rd, None)

        elif mnemonic in (".word", "word"):
            try:
                word = int(args[0], 0) & 0xFFFFFFFF
            except Exception:
                word = 0
            fmt = "DATA"
            fields = f"{word:032b}"
            desc = f"Constant Data / String: 0x{word:08X} ({word})"

        elif mnemonic in ("mult", "multu", "div", "divu"):
            fn = {"mult": 0x18, "multu": 0x19, "div": 0x1A, "divu": 0x1B}[mnemonic]
            rs, rt = reg_num(args[0]), reg_num(args[1])
            word = (rs << 21) | (rt << 16) | fn
            fmt = "R"
            fields = f"000000 {rs:05b} {rt:05b} 00000 00000 {fn:06b}"
            desc = f"HI, LO = {MIPS_REG_NAMES[rs]} {mnemonic} {MIPS_REG_NAMES[rt]}"

        elif mnemonic in ("mfhi", "mflo"):
            fn = 0x10 if mnemonic == "mfhi" else 0x12
            rd = reg_num(args[0])
            word = (rd << 11) | fn
            fmt = "R"
            fields = f"000000 00000 00000 {rd:05b} 00000 {fn:06b}"
            src = "HI" if mnemonic == "mfhi" else "LO"
            desc = f"{MIPS_REG_NAMES[rd]} = {src}"
            reg_tracker.pop(rd, None)

        elif mnemonic in ("mthi", "mtlo"):
            fn = 0x11 if mnemonic == "mthi" else 0x13
            rs = reg_num(args[0])
            word = (rs << 21) | fn
            fmt = "R"
            fields = f"000000 {rs:05b} 00000 00000 00000 {fn:06b}"
            dst = "HI" if mnemonic == "mthi" else "LO"
            desc = f"{dst} = {MIPS_REG_NAMES[rs]}"

        elif mnemonic == "jr":
            rs = reg_num(args[0])
            op, fn = 0, 0x08
            word = (op << 26) | (rs << 21) | fn
            fmt = "R"
            fields = f"{op:06b} {rs:05b} 00000 00000 00000 {fn:06b}"
            desc = f"PC = {MIPS_REG_NAMES[rs]} (จบฟังก์ชัน/กระโดด)"

        elif mnemonic == "jalr":
            if len(args) == 1:
                rd, rs = 31, reg_num(args[0])
            else:
                rd, rs = reg_num(args[0]), reg_num(args[1])
            op, fn = 0, 0x09
            word = (op << 26) | (rs << 21) | (rd << 11) | fn
            fmt = "R"
            fields = f"{op:06b} {rs:05b} 00000 {rd:05b} 00000 {fn:06b}"
            desc = f"{MIPS_REG_NAMES[rd]} = PC + 4; PC = {MIPS_REG_NAMES[rs]}"
            reg_tracker.pop(rd, None)

        elif mnemonic in ("addi", "addiu", "ori", "andi", "xori", "slti", "sltiu"):
            op_map = {
                "addi": 0x08, "addiu": 0x09, "slti": 0x0A, "sltiu": 0x0B,
                "andi": 0x0C, "ori": 0x0D, "xori": 0x0E
            }
            op = op_map[mnemonic]
            rt, rs = reg_num(args[0]), reg_num(args[1])
            imm_val = int(args[2], 0)
            imm = mask(imm_val, 16)
            word = (op << 26) | (rs << 21) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} {rs:05b} {rt:05b} {imm:016b}"
            if rs == 0 and mnemonic in ("addi", "addiu", "ori"):
                reg_tracker[rt] = imm_val & 0xFFFFFFFF if mnemonic == "ori" else imm_val
                desc = f"{MIPS_REG_NAMES[rt]} = {reg_tracker[rt]}{fmt_ascii_hint(reg_tracker[rt])}"
            elif rs in reg_tracker and mnemonic in ("addi", "addiu", "ori"):
                if mnemonic == "ori":
                    val = (reg_tracker[rs] | (imm_val & 0xFFFF)) & 0xFFFFFFFF
                else:
                    val = (reg_tracker[rs] + imm_val) & 0xFFFFFFFF
                reg_tracker[rt] = val
                if val in MMIO_MAP:
                    io_name, io_th = MMIO_MAP[val]
                    desc = f"{MIPS_REG_NAMES[rt]} = 0x{val:08X} ({io_name}: {io_th})"
                else:
                    op_sym = "|" if mnemonic == "ori" else "+"
                    desc = f"{MIPS_REG_NAMES[rt]} = {MIPS_REG_NAMES[rs]} {op_sym} {imm_val} (0x{val:08X})"
            else:
                reg_tracker.pop(rt, None)
                op_sym = {"andi": "&", "ori": "|", "xori": "^", "slti": "<", "sltiu": "<u"}.get(mnemonic, "+")
                desc = f"{MIPS_REG_NAMES[rt]} = {MIPS_REG_NAMES[rs]} {op_sym} {imm_val}"

        elif mnemonic == "lui":
            op = 0x0F
            rt = reg_num(args[0])
            imm_raw = int(args[1], 0)
            if imm_raw > 0xFFFF:
                if imm_raw > 0xFFFFF:
                    imm_raw = (imm_raw >> 16) & 0xFFFF
                else:
                    imm_raw = (imm_raw >> 4) & 0xFFFF
            imm = mask(imm_raw, 16)
            word = (op << 26) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} 00000 {rt:05b} {imm:016b}"
            val = (imm << 16) & 0xFFFFFFFF
            reg_tracker[rt] = val
            if val == 0xF0000000:
                desc = f"{MIPS_REG_NAMES[rt]} = 0x{val:08X} (ตั้ง Base Address I/O)"
            elif val == 0x80010000 and rt == 29:
                desc = f"{MIPS_REG_NAMES[rt]} = 0x{val:08X} (ตั้งค่าเริ่มต้น Stack Pointer)"
            else:
                desc = f"{MIPS_REG_NAMES[rt]} = 0x{val:08X}"

        elif mnemonic in ("lw", "sw", "lb", "lbu", "lh", "lhu", "sb", "sh"):
            load_store_ops = {
                "lb": 0x20, "lh": 0x21, "lw": 0x23, "lbu": 0x24, "lhu": 0x25,
                "sb": 0x28, "sh": 0x29, "sw": 0x2B
            }
            op = load_store_ops[mnemonic]
            rt = reg_num(args[0])
            m = re.match(r"([-\dxXa-fA-F]+)\(([^)]+)\)", args[1])
            imm_val = int(m.group(1), 0) if m else 0
            imm = mask(imm_val, 16)
            rs = reg_num(m.group(2)) if m else 0
            word = (op << 26) | (rs << 21) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} {rs:05b} {rt:05b} {imm:016b}"
            base_val = reg_tracker.get(rs, None)
            if base_val is not None:
                eff_addr = (base_val + imm_val) & 0xFFFFFFFF
            elif rs in (28, 29, 30):
                eff_addr = (0x80010000 + imm_val) & 0xFFFFFFFF
            else:
                eff_addr = None

            if eff_addr is not None and eff_addr in MMIO_MAP:
                io_name, io_th = MMIO_MAP[eff_addr]
                if mnemonic in ("sw", "sb", "sh"):
                    v_hint = f" = {reg_tracker[rt]}{fmt_ascii_hint(reg_tracker[rt])}" if rt in reg_tracker else ""
                    desc = f"ส่งออก {io_name} (0x{eff_addr:08X}) <= {MIPS_REG_NAMES[rt]}{v_hint}"
                else:
                    desc = f"{MIPS_REG_NAMES[rt]} <= อ่าน {io_name} (0x{eff_addr:08X}: {io_th})"
            elif eff_addr is not None:
                if mnemonic in ("sw", "sb", "sh"):
                    v_hint = f" = {reg_tracker[rt]}" if rt in reg_tracker else ""
                    desc = f"MEM[0x{eff_addr:08X}] <= {MIPS_REG_NAMES[rt]}{v_hint}"
                else:
                    desc = f"{MIPS_REG_NAMES[rt]} <= MEM[0x{eff_addr:08X}]"
            else:
                if mnemonic in ("sw", "sb", "sh"):
                    desc = f"MEM[{MIPS_REG_NAMES[rs]} + {imm_val}] <= {MIPS_REG_NAMES[rt]}"
                else:
                    desc = f"{MIPS_REG_NAMES[rt]} <= MEM[{MIPS_REG_NAMES[rs]} + {imm_val}]"
            if mnemonic in ("lw", "lb", "lbu", "lh", "lhu"):
                reg_tracker.pop(rt, None)

        elif mnemonic in ("beq", "bne"):
            op = 0x04 if mnemonic == "beq" else 0x05
            rs, rt = reg_num(args[0]), reg_num(args[1])
            target = args[2].strip()
            if "<" in target:
                target = target.split("<")[0].strip()
            if target in labels:
                target_idx = labels[target]
            elif target == "main":
                target_idx = labels.get("main", 3)
            elif target in ("_halt", "halt"):
                target_idx = labels.get("_halt", 2)
            else:
                try:
                    target_idx = idx_pc + 1 + (int(target, 0) // 4)
                except Exception:
                    target_idx = idx_pc + 1
            offset = target_idx - idx_pc - 1
            imm = mask(offset, 16)
            word = (op << 26) | (rs << 21) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} {rs:05b} {rt:05b} {imm:016b}"
            sym = "==" if mnemonic == "beq" else "!="
            desc = f"if ({MIPS_REG_NAMES[rs]} {sym} {MIPS_REG_NAMES[rt]}) PC += {offset*4}"
            line = f"{mnemonic} {args[0]}, {args[1]}, {offset*4} <{target}>"

        elif mnemonic in ("blez", "bgtz"):
            op = 0x06 if mnemonic == "blez" else 0x07
            rs = reg_num(args[0])
            rt = 0
            target = args[1].strip()
            if "<" in target:
                target = target.split("<")[0].strip()
            if target in labels:
                target_idx = labels[target]
            else:
                try:
                    target_idx = idx_pc + 1 + (int(target, 0) // 4)
                except Exception:
                    target_idx = idx_pc + 1
            offset = target_idx - idx_pc - 1
            imm = mask(offset, 16)
            word = (op << 26) | (rs << 21) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} {rs:05b} 00000 {imm:016b}"
            sym = "<=" if mnemonic == "blez" else ">"
            desc = f"if ({MIPS_REG_NAMES[rs]} {sym} 0) PC += {offset*4}"
            line = f"{mnemonic} {args[0]}, {offset*4} <{target}>"

        elif mnemonic in ("bltz", "bgez"):
            op = 0x01
            rs = reg_num(args[0])
            rt = 0x00 if mnemonic == "bltz" else 0x01
            target = args[1].strip()
            if "<" in target:
                target = target.split("<")[0].strip()
            if target in labels:
                target_idx = labels[target]
            else:
                try:
                    target_idx = idx_pc + 1 + (int(target, 0) // 4)
                except Exception:
                    target_idx = idx_pc + 1
            offset = target_idx - idx_pc - 1
            imm = mask(offset, 16)
            word = (op << 26) | (rs << 21) | (rt << 16) | imm
            fmt = "I"
            fields = f"{op:06b} {rs:05b} {rt:05b} {imm:016b}"
            sym = "<" if mnemonic == "bltz" else ">="
            desc = f"if ({MIPS_REG_NAMES[rs]} {sym} 0) PC += {offset*4}"
            line = f"{mnemonic} {args[0]}, {offset*4} <{target}>"

        elif mnemonic in ("j", "jal"):
            op = 0x02 if mnemonic == "j" else 0x03
            target = args[-1].strip()
            m_anchor = re.search(r"<([^>]+)>", line)
            if m_anchor:
                anchor_val = m_anchor.group(1).strip()
                if ":" in anchor_val:
                    for part in anchor_val.split(":"):
                        if part in labels:
                            target = part
                            break
                        elif part.startswith("0x"):
                            target = part
                            break
                elif anchor_val in labels or anchor_val.startswith("0x"):
                    target = anchor_val

            if "<" in target:
                target = target.split("<")[0].strip()
            if target in labels:
                addr = labels[target]
            elif target in ("_halt", "halt"):
                addr = labels.get("_halt", 2)
            else:
                try:
                    raw_v = int(target, 0)
                    addr = (raw_v // 4) if raw_v >= 4 else raw_v
                except Exception:
                    addr = 0
            imm = mask(addr, 26)
            word = (op << 26) | imm
            fmt = "J"
            fields = f"{op:06b} {imm:026b}"
            if len(args) > 1:
                line = f"{mnemonic} {args[0]}, {target} <0x{addr*4:04X}>"
            else:
                line = f"{mnemonic} {target} <0x{addr*4:04X}>"
            byte_off = (addr - idx_pc) * 4
            desc = f"PC += {byte_off} (กระโดดไปยัง 0x{addr*4:04X} <{target}>)"

        elif mnemonic in ("syscall", "ecall"):
            word = 0x0000000C
            fmt = "R"
            fields = "000000 00000 00000 00000 00000 001100"
            desc = "System Call (MARS/OS Trap)"

        elif mnemonic in ("break", "ebreak"):
            try:
                code_val = int(args[0], 0) if args else 0
            except Exception:
                code_val = 0
            word = ((code_val & 0xFFFFF) << 6) | 0x0D
            fmt = "R"
            fields = f"000000 {code_val:020b} 001101"
            desc = "Breakpoint Trap"

        out.append({
            "pc": f"0x{idx_pc*4:04X}",
            "pc_int": idx_pc * 4,
            "asm": line,
            "hex": f"0x{word:08X}",
            "bin": f"{word:032b}",
            "fields": fields,
            "fmt": fmt,
            "desc": desc,
            "word": word,
        })
    return out

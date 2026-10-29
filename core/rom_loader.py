# -*- coding: utf-8 -*-
"""
Machine Code & ROM Loader
Supports parsing:
1. Xilinx COE (.coe) - memory_initialization_vector
2. Hex File (.hex, .mem) - Raw 32-bit words or Intel HEX
3. Raw Binary (.bin) - 32-bit machine code words
4. ELF / Output (.elf, .out)
"""

import os
import re
import struct
from core.disassembler import decode_mips_word, decode_rv32_word


def parse_coe_text(text):
    """Parse Xilinx .coe memory initialization vector."""
    words = []
    in_vector = False
    radix = 16
    for line in text.splitlines():
        line = line.split(";")[0].strip()
        if not line:
            continue
        if "memory_initialization_radix" in line.lower():
            m = re.search(r"=\s*(\d+)", line)
            if m:
                radix = int(m.group(1))
        elif "memory_initialization_vector" in line.lower():
            in_vector = True
            content = line.split("=", 1)[1].strip()
            if content:
                for tok in re.split(r"[\s,]+", content):
                    tok = tok.strip().rstrip(";")
                    if tok:
                        try:
                            words.append(int(tok, radix))
                        except Exception:
                            pass
        elif in_vector:
            for tok in re.split(r"[\s,]+", line):
                tok = tok.strip().rstrip(";")
                if tok:
                    try:
                        words.append(int(tok, radix))
                    except Exception:
                        pass
    return words


def parse_hex_text(text):
    """Parse raw hex lines or Intel Hex format."""
    words = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if any(l.startswith(":") for l in lines):
        raw_bytes = bytearray()
        for line in lines:
            if not line.startswith(":"):
                continue
            try:
                byte_count = int(line[1:3], 16)
                record_type = int(line[7:9], 16)
                if record_type == 0:  # Data record
                    data_hex = line[9:9 + byte_count * 2]
                    raw_bytes.extend(bytes.fromhex(data_hex))
            except Exception:
                pass
        for i in range(0, len(raw_bytes) - 3, 4):
            w = struct.unpack(">I", raw_bytes[i:i+4])[0]
            words.append(w)
        return words

    for line in lines:
        line = line.split("#")[0].split("//")[0].split(";")[0].strip()
        if not line:
            continue
        for tok in re.split(r"[\s,]+", line):
            tok = tok.strip()
            if not tok:
                continue
            if tok.startswith("0x") or tok.startswith("0X"):
                tok = tok[2:]
            try:
                words.append(int(tok, 16))
            except Exception:
                pass
    return words


def parse_binary_file(filepath, is_big_endian=False):
    """Read 32-bit words from raw .bin file."""
    words = []
    with open(filepath, "rb") as f:
        data = f.read()
    fmt = ">I" if is_big_endian else "<I"
    for i in range(0, len(data) - 3, 4):
        w = struct.unpack(fmt, data[i:i+4])[0]
        words.append(w)
    return words


def load_machine_code_file(filepath, arch="mips"):
    """
    Load .hex, .coe, .bin, or .elf and decode into simulator instruction dicts.
    Returns: (compiled_ins, summary_str)
    """
    ext = os.path.splitext(filepath)[1].lower()
    words = []
    is_mips = ("mips" in arch.lower())

    if ext == ".coe":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            words = parse_coe_text(f.read())
    elif ext == ".bin":
        words = parse_binary_file(filepath, is_big_endian=is_mips)
    elif ext in (".hex", ".mem", ".txt"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            words = parse_hex_text(f.read())
    elif ext in (".elf", ".out"):
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            if data.startswith(b"\x7fELF"):
                import subprocess
                from config.catalog import RISCV_BIN_DIR
                objdump = os.path.join(RISCV_BIN_DIR, "riscv-none-elf-objdump.exe") if RISCV_BIN_DIR else None
                if objdump and os.path.exists(objdump):
                    res = subprocess.run([objdump, "-d", filepath], capture_output=True, text=True)
                    if res.returncode == 0:
                        from core.transpiler import parse_objdump_to_ins
                        ins_list = parse_objdump_to_ins(res.stdout)
                        return ins_list, f"โหลดสำเร็จ {len(ins_list)} คำสั่งจาก ELF ({os.path.basename(filepath)})"
        except Exception:
            pass
        words = parse_binary_file(filepath, is_big_endian=is_mips)
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            words = parse_hex_text(f.read())

    if not words:
        raise ValueError(f"ไม่พบข้อมูล 32-bit Machine Code ในไฟล์ {os.path.basename(filepath)}")

    compiled_ins = []
    for idx, word in enumerate(words):
        pc = idx * 4
        word = word & 0xFFFFFFFF
        if is_mips:
            fmt, fields, canonical_asm, desc = decode_mips_word(word, pc=pc)
        else:
            fmt, fields, canonical_asm, desc = decode_rv32_word(word, pc=pc)

        compiled_ins.append({
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

    summary = f"โหลดสำเร็จ {len(compiled_ins)} คำสั่ง 32-bit จาก {os.path.basename(filepath)}"
    return compiled_ins, summary

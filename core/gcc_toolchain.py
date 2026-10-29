# -*- coding: utf-8 -*-
"""
Real xPack RISC-V GCC / G++ 15.2.0 Compiler Integration
"""

import os
import sys
import re
import glob
import tempfile
import subprocess
from config.catalog import ROOT_DIR
from core.disassembler import decode_rv32_word, decode_mips_word


def find_riscv_gcc_bin():
    candidates = [ROOT_DIR, os.path.dirname(sys.executable)]
    for base in candidates:
        if base:
            pattern = os.path.join(base, "toolchain", "*", "bin", "riscv-none-elf-gcc.exe")
            matches = glob.glob(pattern)
            if matches:
                return os.path.dirname(matches[0])
    return None


def find_mips_gcc_bin():
    candidates = [ROOT_DIR, os.path.dirname(sys.executable)]
    for base in candidates:
        if base:
            for pat in ("mips64-elf-gcc.exe", "mips-elf-gcc.exe", "mips-linux-gnu-gcc.exe"):
                pattern = os.path.join(base, "toolchain", "*", "bin", pat)
                matches = glob.glob(pattern)
                if matches:
                    return os.path.dirname(matches[0])
    return None


RISCV_BIN_DIR = find_riscv_gcc_bin()
MIPS_BIN_DIR = find_mips_gcc_bin()


def compile_with_real_riscv_gcc(c_code, opt_level="-O1", is_cpp=False):
    """
    Compile C or C++ source code with the real xPack riscv-none-elf-gcc / g++ toolchain:
      Target ISA : -march=rv32im
      Target ABI : -mabi=ilp32
      Optimization: -O1 (clean readable code generation)
    """
    if not RISCV_BIN_DIR:
        raise RuntimeError("ไม่พบ riscv-none-elf-gcc ในโฟลเดอร์ toolchain")

    compiler_name = "riscv-none-elf-g++.exe" if is_cpp else "riscv-none-elf-gcc.exe"
    gcc_exe = os.path.join(RISCV_BIN_DIR, compiler_name)
    objdump_exe = os.path.join(RISCV_BIN_DIR, "riscv-none-elf-objdump.exe")

    preamble = r"""
#include <stdint.h>

#define _FPGA_UART_TX (*(volatile int*)0xF0000010)

static inline int _fpga_printf(const char *s, ...) {
    while (*s) {
        _FPGA_UART_TX = (int)(*s++);
    }
    return 0;
}
"""

    def _expand_printf(m):
        s = m.group(1).replace("\\n", "\n").replace("\\t", "\t")
        stmts = [f"_FPGA_UART_TX = {ord(ch)};" for ch in s]
        return "{ " + " ".join(stmts) + " }"

    cleaned_code = re.sub(r"#\s*include\s*<stdio\.h>", "// <stdio.h> (Bare-Metal FPGA UART)", c_code)
    cleaned_code = re.sub(r"\bprintf\s*\(\s*\"([^\"]*)\"\s*\)\s*;", _expand_printf, cleaned_code)
    cleaned_code = re.sub(r"\bprintf\s*\(", "_fpga_printf(", cleaned_code)

    startup_asm = r"""
.section .text.init
.global _start
_start:
    lui sp, 0x80010
    jal ra, main
_halt:
    j _halt
"""
    linker_ld = r"""
ENTRY(_start)
SECTIONS {
    . = 0x00000000;
    .text : {
        *(.text.init)
        *(.text*)
    }
    . = 0x80000000;
    .data : ALIGN(4) {
        *(.rodata*)
        *(.srodata*)
        *(.data*)
        *(.sdata*)
    }
    .bss : ALIGN(4) {
        *(.bss*)
        *(.sbss*)
        *(COMMON)
    }
}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = os.path.join(tmpdir, "main.cpp" if is_cpp else "main.c")
        s_path = os.path.join(tmpdir, "start.S")
        ld_path = os.path.join(tmpdir, "link.ld")
        elf_path = os.path.join(tmpdir, "prog.elf")

        # Copy nexys_a7.h directly into temp compile dir so #include "nexys_a7.h" always succeeds
        h_candidates = [
            os.path.join(ROOT_DIR, "workspace", "nexys-a7-project", "nexys_a7.h"),
            os.path.join(ROOT_DIR, "workspace", "nexys_a7.h"),
            os.path.join(ROOT_DIR, "nexys_a7.h"),
        ]
        for hc in h_candidates:
            if os.path.exists(hc):
                try:
                    import shutil
                    shutil.copy2(hc, os.path.join(tmpdir, "nexys_a7.h"))
                    break
                except Exception:
                    pass

        with open(c_path, "w", encoding="utf-8") as f:
            f.write(preamble + '\n#line 1 "user_code"\n' + cleaned_code)
        with open(s_path, "w", encoding="utf-8") as f:
            f.write(startup_asm)
        with open(ld_path, "w", encoding="utf-8") as f:
            f.write(linker_ld)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        ws_dir = os.path.join(ROOT_DIR, "workspace", "nexys-a7-project")
        cmd_gcc = [
            gcc_exe,
            "-march=rv32im",
            "-mabi=ilp32",
            opt_level,
            "-nostdlib",
            "-fno-builtin",
            f"-I{ws_dir}",
        ]
        if is_cpp:
            cmd_gcc.extend(["-fno-exceptions", "-fno-rtti"])
        cmd_gcc.extend([
            "-T", ld_path,
            s_path, c_path,
            "-o", elf_path
        ])
        proc = subprocess.run(cmd_gcc, capture_output=True, text=True, startupinfo=startupinfo)
        if proc.returncode != 0:
            stderr_lines = proc.stderr.strip().splitlines() if proc.stderr else []
            err_msg = "GCC Compile Error"
            for sl in stderr_lines:
                m_err = re.search(r"user_code:(\d+):(?:\d+:)?\s*error:\s*(.+)", sl)
                if m_err:
                    err_msg = f"Line {m_err.group(1)}: {m_err.group(2)}"
                    break
                if "error:" in sl:
                    err_msg = sl.split("error:", 1)[-1].strip()
                    break
            else:
                if stderr_lines:
                    err_msg = stderr_lines[-1]
            raise RuntimeError(err_msg)

        cmd_dump = [objdump_exe, "-d", "-M", "no-aliases", elf_path]
        dump_proc = subprocess.run(cmd_dump, capture_output=True, text=True, startupinfo=startupinfo)

        # Extract initialized .data / .rodata (at 0x80000000) for Harvard Data RAM preloading
        init_dmem = {}
        objcopy_exe = os.path.join(RISCV_BIN_DIR, "riscv-none-elf-objcopy.exe")
        if os.path.exists(objcopy_exe):
            data_bin_path = os.path.join(tmpdir, "data.bin")
            subprocess.run(
                [objcopy_exe, "-O", "binary", "-j", ".data", elf_path, data_bin_path],
                capture_output=True,
                startupinfo=startupinfo,
            )
            if os.path.exists(data_bin_path):
                with open(data_bin_path, "rb") as bf:
                    raw_data = bf.read()
                if raw_data:
                    pad_len = (4 - (len(raw_data) % 4)) % 4
                    raw_data += b"\x00" * pad_len
                    for off in range(0, len(raw_data), 4):
                        w_val = int.from_bytes(raw_data[off:off + 4], "little")
                        if w_val != 0:
                            init_dmem[0x80000000 + off] = w_val

        sym_map = {}
        sym_re = re.compile(r"^([0-9a-fA-F]+)\s+<([^>]+)>:$")
        line_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+(.+)$")

        raw_words = []
        for line in dump_proc.stdout.splitlines():
            ms = sym_re.match(line.strip())
            if ms:
                sym_map[int(ms.group(1), 16)] = ms.group(2)
                continue
            ml = line_re.match(line)
            if ml:
                pc_int = int(ml.group(1), 16)
                word = int(ml.group(2), 16)
                raw_words.append((pc_int, word))

        instructions = []
        asm_lines = []
        reg_tracker = {}
        for pc_int, word in raw_words:
            fmt, fields, canonical_asm, desc = decode_rv32_word(word, pc=pc_int, sym_map=sym_map, reg_tracker=reg_tracker)
            asm_lines.append(canonical_asm)
            sym_name = sym_map.get(pc_int, "")
            instructions.append({
                "pc": f"0x{pc_int:04X}",
                "pc_int": pc_int,
                "asm": canonical_asm,
                "hex": f"0x{word:08X}",
                "bin": f"{word:032b}",
                "fields": fields,
                "fmt": fmt,
                "desc": desc,
                "word": word,
                "sym_name": sym_name,
            })
        if instructions and init_dmem:
            instructions[0]["init_dmem"] = init_dmem
        return asm_lines, instructions


def compile_with_real_mips_gcc(c_code, opt_level="-O1", is_cpp=False):
    """
    Compile C or C++ source code with the real MIPS GCC / G++ toolchain:
      Target ISA : -march=mips32
      Target ABI : -mabi=32
      Endianness : -EB (Big-Endian for OpenMIPS)
      Optimization: -O1 (clean readable code generation)
    """
    if not MIPS_BIN_DIR:
        raise RuntimeError("ไม่พบ mips-gcc ในโฟลเดอร์ toolchain")

    gcc_bin = "mips64-elf-gcc.exe"
    gpp_bin = "mips64-elf-g++.exe"
    objdump_bin = "mips64-elf-objdump.exe"
    objcopy_bin = "mips64-elf-objcopy.exe"
    for cand in os.listdir(MIPS_BIN_DIR):
        cand_l = cand.lower()
        if "gcc.exe" in cand_l and "ar" not in cand_l and "nm" not in cand_l:
            gcc_bin = cand
        if ("g++.exe" in cand_l or "c++.exe" in cand_l) and "filt" not in cand_l:
            gpp_bin = cand
        if "objdump.exe" in cand_l:
            objdump_bin = cand
        if "objcopy.exe" in cand_l:
            objcopy_bin = cand

    compiler_exe = os.path.join(MIPS_BIN_DIR, gpp_bin if is_cpp else gcc_bin)
    objdump_exe = os.path.join(MIPS_BIN_DIR, objdump_bin)
    objcopy_exe = os.path.join(MIPS_BIN_DIR, objcopy_bin)

    preamble = r"""
#include <stdint.h>

#define _FPGA_UART_TX (*(volatile int*)0xF0000010)

static inline int _fpga_printf(const char *s, ...) {
    while (*s) {
        _FPGA_UART_TX = (int)(*s++);
    }
    return 0;
}
"""

    def _expand_printf(m):
        s = m.group(1).replace("\\n", "\n").replace("\\t", "\t")
        stmts = [f"_FPGA_UART_TX = {ord(ch)};" for ch in s]
        return "{ " + " ".join(stmts) + " }"

    cleaned_code = re.sub(r"#\s*include\s*<stdio\.h>", "// <stdio.h> (Bare-Metal FPGA UART)", c_code)
    cleaned_code = re.sub(r"\bprintf\s*\(\s*\"([^\"]*)\"\s*\)\s*;", _expand_printf, cleaned_code)
    cleaned_code = re.sub(r"\bprintf\s*\(", "_fpga_printf(", cleaned_code)

    startup_asm = r"""
.section .text.init
.set noreorder
.global _start
_start:
    lui $sp, 0x8001
    jal main
    nop
_halt:
    j _halt
    nop
"""
    linker_ld = r"""
ENTRY(_start)
SECTIONS {
    . = 0x00000000;
    .text : {
        *(.text.init)
        *(.text*)
    }
    . = 0x80000000;
    .data : ALIGN(4) {
        *(.rodata*)
        *(.srodata*)
        *(.data*)
        *(.sdata*)
    }
    .bss : ALIGN(4) {
        *(.bss*)
        *(.sbss*)
        *(COMMON)
    }
}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = os.path.join(tmpdir, "main.cpp" if is_cpp else "main.c")
        s_path = os.path.join(tmpdir, "start.S")
        ld_path = os.path.join(tmpdir, "link.ld")
        elf_path = os.path.join(tmpdir, "prog.elf")

        h_candidates = [
            os.path.join(ROOT_DIR, "workspace", "nexys-a7-project", "nexys_a7.h"),
            os.path.join(ROOT_DIR, "workspace", "nexys_a7.h"),
            os.path.join(ROOT_DIR, "nexys_a7.h"),
        ]
        for hc in h_candidates:
            if os.path.exists(hc):
                try:
                    import shutil
                    shutil.copy2(hc, os.path.join(tmpdir, "nexys_a7.h"))
                    break
                except Exception:
                    pass

        with open(c_path, "w", encoding="utf-8") as f:
            f.write(preamble + '\n#line 1 "user_code"\n' + cleaned_code)
        with open(s_path, "w", encoding="utf-8") as f:
            f.write(startup_asm)
        with open(ld_path, "w", encoding="utf-8") as f:
            f.write(linker_ld)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        ws_dir = os.path.join(ROOT_DIR, "workspace", "nexys-a7-project")
        cmd_gcc = [
            compiler_exe,
            "-mabi=32",
            "-march=mips32",
            "-EB",
            opt_level,
            "-nostdlib",
            "-fno-builtin",
            f"-I{ws_dir}",
        ]
        if is_cpp:
            cmd_gcc.extend(["-fno-exceptions", "-fno-rtti"])
        cmd_gcc.extend([
            "-T", ld_path,
            s_path, c_path,
            "-o", elf_path
        ])
        proc = subprocess.run(cmd_gcc, capture_output=True, text=True, startupinfo=startupinfo)
        if proc.returncode != 0:
            stderr_lines = proc.stderr.strip().splitlines() if proc.stderr else []
            err_msg = "MIPS GCC Compile Error"
            for sl in stderr_lines:
                m_err = re.search(r"user_code:(\d+):(?:\d+:)?\s*error:\s*(.+)", sl)
                if m_err:
                    err_msg = f"Line {m_err.group(1)}: {m_err.group(2)}"
                    break
                if "error:" in sl:
                    err_msg = sl.split("error:", 1)[-1].strip()
                    break
            else:
                if stderr_lines:
                    err_msg = stderr_lines[-1]
            raise RuntimeError(err_msg)

        cmd_dump = [objdump_exe, "-d", "-M", "no-aliases", elf_path]
        dump_proc = subprocess.run(cmd_dump, capture_output=True, text=True, startupinfo=startupinfo)

        init_dmem = {}
        if os.path.exists(objcopy_exe):
            data_bin_path = os.path.join(tmpdir, "data.bin")
            subprocess.run(
                [objcopy_exe, "-O", "binary", "-j", ".data", elf_path, data_bin_path],
                capture_output=True,
                startupinfo=startupinfo,
            )
            if os.path.exists(data_bin_path):
                with open(data_bin_path, "rb") as bf:
                    raw_data = bf.read()
                if raw_data:
                    pad_len = (4 - (len(raw_data) % 4)) % 4
                    raw_data += b"\x00" * pad_len
                    for off in range(0, len(raw_data), 4):
                        w_val = int.from_bytes(raw_data[off:off + 4], "big")
                        if w_val != 0:
                            init_dmem[0x80000000 + off] = w_val

        sym_map = {}
        sym_re = re.compile(r"^([0-9a-fA-F]+)\s+<([^>]+)>:$")
        line_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+(.+)$")

        raw_words = []
        for line in dump_proc.stdout.splitlines():
            ms = sym_re.match(line.strip())
            if ms:
                sym_map[int(ms.group(1), 16)] = ms.group(2)
                continue
            ml = line_re.match(line)
            if ml:
                pc_int = int(ml.group(1), 16)
                word = int(ml.group(2), 16)
                raw_words.append((pc_int, word))

        instructions = []
        asm_lines = []
        reg_tracker = {}
        for pc_int, word in raw_words:
            fmt, fields, canonical_asm, desc = decode_mips_word(word, pc=pc_int, sym_map=sym_map, reg_tracker=reg_tracker)
            asm_lines.append(canonical_asm)
            sym_name = sym_map.get(pc_int, "")
            instructions.append({
                "pc": f"0x{pc_int:04X}",
                "pc_int": pc_int,
                "asm": canonical_asm,
                "hex": f"0x{word:08X}",
                "bin": f"{word:032b}",
                "fields": fields,
                "fmt": fmt,
                "desc": desc,
                "word": word,
                "sym_name": sym_name,
            })
        if instructions and init_dmem:
            instructions[0]["init_dmem"] = init_dmem
        return asm_lines, instructions


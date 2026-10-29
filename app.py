# -*- coding: utf-8 -*-
"""
FPGA Studio — Backward-Compatible Core API Facade
Re-exports core compiler, assembler, disassembler, and HDL routines.
"""

from config.catalog import ROOT_DIR
from core import (
    MMIO_BASE,
    MMIO_MAP,
    RV_REG_NAMES,
    MIPS_REG_NAMES,
    sign_extend,
    mask,
    fmt_ascii_hint,
    reg_num,
    decode_rv32_word,
    compile_with_real_riscv_gcc,
    find_riscv_gcc_bin,
    RISCV_BIN_DIR,
    assemble_riscv,
    assemble_mips,
    compile_c_to_asm,
    generate_vhdl_rom,
    generate_verilog_rom,
    generate_coe_content,
    transpile_python_to_c,
    transpile_rust_to_c,
    check_code_syntax,
    CPUSimulatorEngine,
)

__all__ = [
    "ROOT_DIR",
    "MMIO_BASE",
    "MMIO_MAP",
    "RV_REG_NAMES",
    "MIPS_REG_NAMES",
    "sign_extend",
    "mask",
    "fmt_ascii_hint",
    "reg_num",
    "decode_rv32_word",
    "compile_with_real_riscv_gcc",
    "find_riscv_gcc_bin",
    "RISCV_BIN_DIR",
    "assemble_riscv",
    "assemble_mips",
    "compile_c_to_asm",
    "generate_vhdl_rom",
    "generate_verilog_rom",
    "generate_coe_content",
    "transpile_python_to_c",
    "transpile_rust_to_c",
    "check_code_syntax",
    "CPUSimulatorEngine",
]

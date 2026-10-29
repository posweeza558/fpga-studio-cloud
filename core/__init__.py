# -*- coding: utf-8 -*-
"""
Core Backend Package for FPGA Studio
"""

from core.disassembler import (
    MMIO_BASE,
    MMIO_MAP,
    RV_REG_NAMES,
    MIPS_REG_NAMES,
    sign_extend,
    mask,
    fmt_ascii_hint,
    reg_num,
    decode_rv32_word,
)
from core.assembler import assemble_riscv, assemble_mips
from core.transpiler import (
    check_code_syntax,
    compile_c_to_asm,
    transpile_python_to_c,
    transpile_rust_to_c,
    translate_rv_ins_to_mips,
)
from core.gcc_toolchain import (
    find_riscv_gcc_bin,
    RISCV_BIN_DIR,
    compile_with_real_riscv_gcc,
    find_mips_gcc_bin,
    MIPS_BIN_DIR,
    compile_with_real_mips_gcc,
)
from core.hdl_generator import (
    generate_vhdl_rom,
    generate_verilog_rom,
    generate_coe_content,
    export_vivado_soc_package,
)
from core.simulator_engine import CPUSimulatorEngine
from core.rtl_cosim import (
    analyze_pipeline_hazards,
    detect_verilog_simulator,
    export_rtl_testbench,
    run_rtl_cosim,
)
from core.fpga_programmer import (
    detect_all_fpga_programmers,
    find_vivado_binary,
    find_djtgcfg_binary,
    find_openfpgaloader_binary,
    program_fpga_with_vivado,
    program_fpga_with_djtgcfg,
    program_fpga_with_openfpgaloader,
)

__all__ = [
    "MMIO_BASE",
    "MMIO_MAP",
    "RV_REG_NAMES",
    "MIPS_REG_NAMES",
    "sign_extend",
    "mask",
    "fmt_ascii_hint",
    "reg_num",
    "decode_rv32_word",
    "assemble_riscv",
    "assemble_mips",
    "check_code_syntax",
    "compile_c_to_asm",
    "transpile_python_to_c",
    "transpile_rust_to_c",
    "translate_rv_ins_to_mips",
    "find_riscv_gcc_bin",
    "RISCV_BIN_DIR",
    "compile_with_real_riscv_gcc",
    "find_mips_gcc_bin",
    "MIPS_BIN_DIR",
    "compile_with_real_mips_gcc",
    "generate_vhdl_rom",
    "generate_verilog_rom",
    "generate_coe_content",
    "export_vivado_soc_package",
    "CPUSimulatorEngine",
    "analyze_pipeline_hazards",
    "detect_verilog_simulator",
    "export_rtl_testbench",
    "run_rtl_cosim",
]

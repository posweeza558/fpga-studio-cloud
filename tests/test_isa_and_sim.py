# -*- coding: utf-8 -*-
"""
Automated ISA, Memory Alignment, GCC Integration & MIPS Delay Slot Test Suite
"""

import os
import sys
import time
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.gcc_toolchain import compile_with_real_riscv_gcc, RISCV_BIN_DIR
from core.transpiler import translate_rv_ins_to_mips
from core.assembler import assemble_riscv, assemble_mips
from core.simulator_engine import CPUSimulatorEngine


def _run_c_on_both_arches(c_code, max_cycles=50000, sw_val=0):
    assert RISCV_BIN_DIR, "Bundled riscv-none-elf-gcc toolchain must exist"
    _, rv_ins = compile_with_real_riscv_gcc(c_code, opt_level="-O1")
    mips_ins = translate_rv_ins_to_mips(rv_ins)

    # 1. Run on RISC-V RV32IM
    sim_rv = CPUSimulatorEngine()
    sim_rv.sw_value = sw_val
    sim_rv.load_program(rv_ins)
    res_rv = sim_rv.step_batch(rv_ins, batch_size=max_cycles, is_mips=False)
    assert sim_rv.last_error is None, f"RV32 error: {sim_rv.last_error}"
    assert res_rv and res_rv.get("is_halted"), "RV32 program did not reach _halt"

    # 2. Run on OpenMIPS (with Branch Delay Slots)
    sim_mips = CPUSimulatorEngine()
    sim_mips.sw_value = sw_val
    sim_mips.load_program(mips_ins)
    res_mips = sim_mips.step_batch(mips_ins, batch_size=max_cycles, is_mips=True)
    assert sim_mips.last_error is None, f"MIPS error: {sim_mips.last_error}"
    assert res_mips and res_mips.get("is_halted"), "MIPS program did not reach _halt"

    return sim_rv, sim_mips


def test_signed_comparisons_and_slti():
    c_code = r"""
    #define LED (*(volatile int*)0xF0000000)
    #define SEG7 (*(volatile int*)0xF0000008)
    int main() {
        volatile int a = -7;
        volatile int b = 5;
        int r1 = (a < 5) ? 1 : 0;          // slti signed: 1
        int r2 = (a < b) ? 1 : 0;          // slt / blt signed: 1
        unsigned int ua = (unsigned int)a; // 0xFFFFFFF9
        int r3 = (ua < 5u) ? 1 : 0;        // sltiu / bltu unsigned: 0
        int out = (r1 << 8) | (r2 << 4) | r3;
        LED = out;
        SEG7 = out;
        return out;
    }
    """
    sim_rv, sim_mips = _run_c_on_both_arches(c_code)
    assert sim_rv.led_value == 0x0110
    assert sim_mips.led_value == 0x0110
    assert sim_rv.seg7_value == 0x0110
    assert sim_mips.seg7_value == 0x0110


def test_byte_and_halfword_memory_alignment():
    c_code = r"""
    #define SEG7 (*(volatile int*)0xF0000008)
    int main() {
        volatile unsigned char bytes[4];
        bytes[0] = 0x01;
        bytes[1] = 0x02;
        bytes[2] = 0xFE;
        bytes[3] = 0x80;

        volatile unsigned short *u16 = (volatile unsigned short*)bytes;
        volatile short *s16 = (volatile short*)bytes;
        volatile signed char *s8 = (volatile signed char*)bytes;

        int check1 = (u16[0] == 0x0201) ? 1 : 0;
        int check2 = (s8[2] == -2) ? 1 : 0;
        int check3 = (s16[1] < 0) ? 1 : 0;

        u16[1] = 0xABCD;
        int check4 = (bytes[2] == 0xCD && bytes[3] == 0xAB) ? 1 : 0;

        int res = (check1 << 12) | (check2 << 8) | (check3 << 4) | check4;
        SEG7 = res;
        return res;
    }
    """
    sim_rv, sim_mips = _run_c_on_both_arches(c_code)
    assert sim_rv.seg7_value == 0x1111
    assert sim_mips.seg7_value == 0x1111


def test_arithmetic_right_shift_and_signed_div_rem():
    c_code = r"""
    #define SEG7 (*(volatile int*)0xF0000008)
    int main() {
        volatile int neg = -64;
        int s1 = neg >> 3;        // -8 (srai)
        volatile int sh = 2;
        int s2 = neg >> sh;       // -16 (sra / srav)
        volatile int d1 = -17;
        volatile int d2 = 5;
        int q = d1 / d2;          // -3
        int r = d1 % d2;          // -2 (dividend sign, NOT +3!)
        int ok = (s1 == -8) && (s2 == -16) && (q == -3) && (r == -2);
        SEG7 = ok ? 0xCAFE : 0xBAD0;
        return ok;
    }
    """
    sim_rv, sim_mips = _run_c_on_both_arches(c_code)
    assert sim_rv.seg7_value == 0xCAFE
    assert sim_mips.seg7_value == 0xCAFE


def test_recursion_and_delay_slot_calls():
    c_code = r"""
    #define SEG7 (*(volatile int*)0xF0000008)
    int fib(int n) {
        if (n <= 1) return n;
        return fib(n - 1) + fib(n - 2);
    }
    int main() {
        int ans = fib(10); // 55
        SEG7 = ans;
        return ans;
    }
    """
    sim_rv, sim_mips = _run_c_on_both_arches(c_code, max_cycles=100000)
    assert sim_rv.seg7_value == 55
    assert sim_mips.seg7_value == 55


def test_rodata_string_and_initialized_globals():
    c_code = r"""
    #include <stdio.h>
    const int LUT[5] = {10, 20, 30, 40, 50};
    int init_val = 7;
    #define SEG7 (*(volatile int*)0xF0000008)
    int main() {
        int sum = init_val;
        for (int i = 0; i < 5; i++) {
            sum += LUT[i];
        }
        printf("OK\n");
        SEG7 = sum; // 157
        return sum;
    }
    """
    sim_rv, sim_mips = _run_c_on_both_arches(c_code)
    assert sim_rv.seg7_value == 157
    assert sim_mips.seg7_value == 157
    assert "OK\n" in sim_rv.uart_buffer
    assert "OK\n" in sim_mips.uart_buffer

    # Verify reset restores initialized globals / rodata!
    sim_rv.reset()
    sim_rv.step_batch(compile_with_real_riscv_gcc(c_code)[1], batch_size=50000, is_mips=False)
    assert sim_rv.seg7_value == 157


def test_direct_assemblers_and_unsupported_error_reporting():
    rv_asm = """
        li t0, 0xF0000000
        auipc t1, 0x1
        li t2, -12
        srai t3, t2, 2
        slti t4, t3, 0
        sw t4, 0(t0)
    halt_here:
        j halt_here
    """
    rv_ins = assemble_riscv(rv_asm)
    sim = CPUSimulatorEngine()
    sim.load_program(rv_ins)
    sim.step_batch(rv_ins, batch_size=100, is_mips=False)
    assert sim.led_value == 1
    assert sim.last_error is None

    # Test explicit error reporting on invalid instruction
    bad_ins = [{"pc": "0x0000", "pc_int": 0, "asm": "bogus_op x1, x2, x3", "fmt": "R", "hex": "0xFFFFFFFF", "desc": "bad", "word": 0xFFFFFFFF}]
    sim2 = CPUSimulatorEngine()
    sim2.load_program(bad_ins)
    step_res = sim2.step(bad_ins, is_mips=False)
    assert sim2.last_error is not None
    assert "bogus_op" in sim2.last_error
    assert "[!]" in step_res["EX"]


def test_predecode_batch_performance():
    rv_asm = """
        addi t0, x0, 0
        addi t1, x0, 5000
    loop:
        addi t0, t0, 1
        bne t0, t1, loop
    done:
        j done
    """
    rv_ins = assemble_riscv(rv_asm)
    sim = CPUSimulatorEngine()
    sim.load_program(rv_ins)
    t_start = time.perf_counter()
    res = sim.step_batch(rv_ins, batch_size=15000, is_mips=False)
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    assert res["is_halted"]
    assert sim.regs[5] == 5000
    # 10,000+ cycles should complete well under 100ms in Python pre-decoded engine
    assert elapsed_ms < 250.0, f"Too slow: {elapsed_ms:.1f} ms"

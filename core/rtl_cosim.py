# -*- coding: utf-8 -*-
"""
FPGA Studio — 5-Stage Pipeline Hazard Analyzer & RTL Verilog Co-Simulation Engine
Provides:
  1. Cycle-accurate 5-Stage Pipeline timing & hazard analysis (IF/ID/EX/MEM/WB):
     - RAW Load-Use Stalls (1-cycle bubble + MEM->EX bypass)
     - EX->EX and MEM->EX Data Forwarding paths
     - Control Hazards (RISC-V branch flush vs. OpenMIPS 1-slot Branch Delay Slot)
     - Effective CPI & hardware runtime estimation @ 25 MHz / 100 MHz
  2. Self-contained Verilog RTL Testbench & VCD Waveform Generator (`tb_cpu_cosim.v`)
  3. Differential RTL vs. Golden ISA Co-Simulation (executes `iverilog`/`vvp` when installed,
     or transparently reports Golden Reference + exports ready-to-run Vivado/Icarus testbench).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

from core.simulator_engine import CPUSimulatorEngine
from core.hdl_analyzer import extract_cpu_ports


def _decode_pipeline_deps(word, is_mips):
    """
    Extract architectural register read/write dependencies & instruction class
    directly from a 32-bit machine word (`riscv` RV32IM or `mips` MIPS32).
    """
    word = int(word) & 0xFFFFFFFF
    if word == 0:
        return {"reads": [], "writes": 0, "kind": "nop"}

    reads = []
    writes = 0
    kind = "alu"

    if is_mips:
        op = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        funct = word & 0x3F

        if op == 0x00:  # SPECIAL
            if funct in (0x00, 0x02, 0x03):  # sll, srl, sra
                reads = [rt]
                writes = rd
                kind = "nop" if (rd == 0 and rt == 0 and word == 0) else "alu"
            elif funct == 0x08:  # jr
                reads = [rs]
                kind = "jump_reg"
            elif funct == 0x09:  # jalr
                reads = [rs]
                writes = rd if rd != 0 else 31
                kind = "jump_reg"
            elif funct in (0x18, 0x19, 0x1A, 0x1B):  # mult, multu, div, divu
                reads = [rs, rt]
                kind = "div" if funct in (0x1A, 0x1B) else "mdu"
            elif funct in (0x10, 0x12):  # mfhi, mflo
                writes = rd
                kind = "alu"
            elif funct in (0x11, 0x13):  # mthi, mtlo
                reads = [rs]
                kind = "alu"
            else:
                reads = [rs, rt]
                writes = rd
                kind = "alu"
        elif op == 0x1C:  # SPECIAL2 (mul, madd, clz, clo)
            if funct == 0x02:  # mul
                reads = [rs, rt]
                writes = rd
                kind = "mdu"
            elif funct in (0x20, 0x21):  # clz, clo
                reads = [rs]
                writes = rd
                kind = "alu"
            else:
                reads = [rs, rt]
                kind = "mdu"
        elif op == 0x01:  # REGIMM (bltz, bgez)
            reads = [rs]
            kind = "branch"
        elif op == 0x02:  # j
            kind = "jump"
        elif op == 0x03:  # jal
            writes = 31
            kind = "jump"
        elif op in (0x04, 0x05):  # beq, bne
            reads = [rs, rt]
            kind = "branch"
        elif op in (0x06, 0x07):  # blez, bgtz
            reads = [rs]
            kind = "branch"
        elif op == 0x0F:  # lui
            writes = rt
            kind = "alu"
        elif op in (0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E):
            reads = [rs]
            writes = rt
            kind = "alu"
        elif op in (0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26):  # loads
            reads = [rs]
            writes = rt
            kind = "load"
        elif op in (0x28, 0x29, 0x2A, 0x2B, 0x2E):  # stores
            reads = [rs, rt]
            kind = "store"
    else:
        # RISC-V RV32IM
        op = word & 0x7F
        rd = (word >> 7) & 0x1F
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        funct3 = (word >> 12) & 0x7
        funct7 = (word >> 25) & 0x7F

        if op == 0x33:
            reads = [rs1, rs2]
            writes = rd
            if funct7 == 0x01:
                kind = "div" if funct3 >= 4 else "mdu"
            else:
                kind = "alu"
        elif op == 0x13:
            reads = [rs1]
            writes = rd
            kind = "nop" if word == 0x00000013 else "alu"
        elif op == 0x03:
            reads = [rs1]
            writes = rd
            kind = "load"
        elif op == 0x23:
            reads = [rs1, rs2]
            kind = "store"
        elif op == 0x63:
            reads = [rs1, rs2]
            kind = "branch"
        elif op == 0x6F:  # jal
            writes = rd
            kind = "jump"
        elif op == 0x67:  # jalr
            reads = [rs1]
            writes = rd
            kind = "jump_reg"
        elif op in (0x37, 0x17):  # lui, auipc
            writes = rd
            kind = "alu"

    clean_reads = []
    for r in reads:
        if r != 0 and r not in clean_reads:
            clean_reads.append(r)
    clean_writes = writes if writes != 0 else 0
    return {"reads": clean_reads, "writes": clean_writes, "kind": kind}


def _fmt_reg(rnum, is_mips):
    if is_mips:
        names = [
            "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
            "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
            "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
            "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra",
        ]
        return names[rnum] if 0 <= rnum < 32 else f"${rnum}"
    rv_names = [
        "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
        "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
        "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
        "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
    ]
    return f"x{rnum}({rv_names[rnum]})" if 0 <= rnum < 32 else f"x{rnum}"


def analyze_pipeline_hazards(
    instructions,
    is_mips=True,
    max_retired=500,
    sw_init=0,
    btn_init=0,
    mmio_map=None,
):
    """
    Simulate dynamic program execution on a sandboxed CPUSimulatorEngine and run
    a cycle-accurate 5-Stage Pipeline Hazard & CPI model (`IF -> ID -> EX -> MEM -> WB`).
    """
    if not instructions:
        return {
            "retired_instructions": 0,
            "total_cycles": 0,
            "ideal_cycles": 0,
            "cpi": 0.0,
            "load_use_stalls": 0,
            "branch_flushes": 0,
            "delay_slots": 0,
            "ex_forwards": 0,
            "mem_forwards": 0,
            "runtime_25mhz_us": 0.0,
            "runtime_100mhz_us": 0.0,
            "hazard_events": [],
            "timeline": [],
            "final_regs": [0] * 32,
            "led_value": 0,
            "seg7_value": 0,
            "halted": True,
        }

    sim = CPUSimulatorEngine()
    if mmio_map:
        sim.set_mmio_map(mmio_map)
    raw_asm = "\n".join(i.get("asm", "") for i in instructions)
    sim.load_program(instructions, raw_asm_text=raw_asm)
    sim.sw_value = int(sw_init) & 0xFFFF
    sim.btn_value = int(btn_init) & 0x3F

    # 1. Collect dynamic retired trace
    retired = []
    halted = False
    for _ in range(max_retired):
        if sim.pc_index < 0 or sim.pc_index >= len(instructions):
            halted = True
            break
        cur_pc_idx = sim.pc_index
        was_in_delay = sim._mips_delay_target is not None
        ins = instructions[cur_pc_idx]
        word = ins.get("word", int(ins["hex"], 16))
        deps = _decode_pipeline_deps(word, is_mips=is_mips)

        res = sim.step(instructions, is_mips=is_mips, raw_asm_text=raw_asm)
        next_pc_idx = sim.pc_index

        # Detect whether a branch/jump redirected control flow
        if is_mips:
            branch_taken = (deps["kind"] in ("branch", "jump", "jump_reg")) and (sim._mips_delay_target is not None)
        else:
            branch_taken = (deps["kind"] in ("branch", "jump", "jump_reg")) and (next_pc_idx != cur_pc_idx + 1)

        retired.append({
            "seq": len(retired),
            "pc_idx": cur_pc_idx,
            "pc": ins.get("pc", f"0x{cur_pc_idx * 4:04X}"),
            "asm": ins.get("asm", "nop"),
            "hex": ins.get("hex", f"0x{word:08X}"),
            "reads": deps["reads"],
            "writes": deps["writes"],
            "kind": deps["kind"],
            "branch_taken": branch_taken,
            "in_delay_slot": was_in_delay,
        })

        if res and res.get("is_halted"):
            halted = True
            break

    # 2. Simulate 5-Stage Pipeline Timing & Hazards over the retired instruction stream
    load_use_stalls = 0
    branch_flushes = 0
    delay_slots = 0
    ex_forwards = 0
    mem_forwards = 0
    hazard_events = []
    timeline = []

    # Pipeline slots hold labels or None: [IF, ID, EX, MEM, WB]
    pipe = ["-", "-", "-", "-", "-"]
    cycle = 0

    def _record_cycle(note=""):
        if len(timeline) < 120:
            timeline.append({
                "cycle": cycle,
                "IF": pipe[0],
                "ID": pipe[1],
                "EX": pipe[2],
                "MEM": pipe[3],
                "WB": pipe[4],
                "note": note,
            })

    prev_1 = None  # Instruction currently in EX when `cur` is in ID
    prev_2 = None  # Instruction currently in MEM when `cur` is in ID

    # Cycle 1: First instruction enters 1. IF (Fetch) stage
    if retired:
        cycle = 1
        pipe = [f"{retired[0]['pc']}: {retired[0]['asm']}", "-", "-", "-", "-"]
        _record_cycle("Initial Fetch (1. IF)")

    for idx, cur in enumerate(retired):
        cur_lbl = f"{cur['pc']}: {cur['asm']}"
        next_lbl = f"{retired[idx + 1]['pc']}: {retired[idx + 1]['asm']}" if idx + 1 < len(retired) else "-"

        if cur["in_delay_slot"]:
            delay_slots += 1

        # Advance normal fetch/decode step so `cur` sits in ID, `prev_1` in EX, `prev_2` in MEM
        cycle += 1
        pipe = [next_lbl, cur_lbl, pipe[1], pipe[2], pipe[3]]
        notes = []

        # A. Check Load-Use RAW Hazard against instruction in EX (`prev_1`)
        stalled_on_load = False
        if prev_1 and prev_1["kind"] == "load" and prev_1["writes"] != 0:
            if prev_1["writes"] in cur["reads"]:
                stalled_on_load = True
                load_use_stalls += 1
                reg_str = _fmt_reg(prev_1["writes"], is_mips)
                notes.append(f"STALL (Load-Use {reg_str})")
                hazard_events.append({
                    "cycle": cycle,
                    "pc": cur["pc"],
                    "asm": cur["asm"],
                    "type": "RAW Load-Use Stall (+1 Cycle)",
                    "detail": f"รอข้อมูล {reg_str} จากคำสั่ง '{prev_1['asm']}' ในขั้น MEM ก่อนส่งต่อเข้า EX",
                })
                _record_cycle(" • ".join(notes))

                # Insert 1 hardware bubble into EX while IF & ID hold steady; MEM & WB advance
                cycle += 1
                pipe = [pipe[0], cur_lbl, "🫧 BUBBLE (STALL)", pipe[2], pipe[3]]
                # After the 1-cycle stall, prev_1 is now in MEM and forwards to cur!
                mem_forwards += 1
                notes = [f"FWD MEM→EX ({reg_str})"]
                prev_2 = prev_1
                prev_1 = None

        # B. Check EX->EX and MEM->EX Data Forwarding (zero-stall bypasses)
        if not stalled_on_load:
            for r in cur["reads"]:
                if prev_1 and prev_1["writes"] == r and prev_1["kind"] != "load":
                    ex_forwards += 1
                    reg_str = _fmt_reg(r, is_mips)
                    notes.append(f"FWD EX→EX ({reg_str})")
                    if len(hazard_events) < 200:
                        hazard_events.append({
                            "cycle": cycle,
                            "pc": cur["pc"],
                            "asm": cur["asm"],
                            "type": "EX→EX Forwarding (0 Stall)",
                            "detail": f"ส่งต่อค่า {reg_str} จากผลลัพธ์ ALU ของ '{prev_1['asm']}' โดยไม่ต้องหยุดรอ",
                        })
                elif prev_2 and prev_2["writes"] == r:
                    mem_forwards += 1
                    reg_str = _fmt_reg(r, is_mips)
                    notes.append(f"FWD MEM→EX ({reg_str})")
                    if len(hazard_events) < 200:
                        hazard_events.append({
                            "cycle": cycle,
                            "pc": cur["pc"],
                            "asm": cur["asm"],
                            "type": "MEM→EX Forwarding (0 Stall)",
                            "detail": f"ส่งต่อค่า {reg_str} จากขั้น MEM ของ '{prev_2['asm']}' โดยไม่ต้องหยุดรอ",
                        })

        if cur["in_delay_slot"]:
            notes.append("MIPS Delay Slot")

        _record_cycle(" • ".join(notes))

        # C. Check Control Hazard Flush (RISC-V has no delay slot -> flush wrong-path IF/ID on taken branch/jump)
        if not is_mips and cur["branch_taken"]:
            flush_penalty = 1 if cur["kind"] == "jump" else 2
            for f_i in range(flush_penalty):
                branch_flushes += 1
                cycle += 1
                pipe = [next_lbl if f_i == flush_penalty - 1 else "⚡ FLUSH", "⚡ FLUSH", pipe[1] if f_i == 0 else "⚡ FLUSH", pipe[2], pipe[3]]
                _record_cycle(f"FLUSH (Taken {cur['kind'].upper()})")
            if len(hazard_events) < 200:
                hazard_events.append({
                    "cycle": cycle,
                    "pc": cur["pc"],
                    "asm": cur["asm"],
                    "type": f"Branch Flush (+{flush_penalty} Cycle{'s' if flush_penalty > 1 else ''})",
                    "detail": f"ล้างคำสั่งที่ดึงล่วงหน้าผิดเส้นทางเมื่อกระโดดจาก '{cur['asm']}'",
                })
            prev_2 = cur
            prev_1 = None
        else:
            prev_2 = prev_1
            prev_1 = cur

    # Drain remaining 3 stages (EX -> MEM -> WB) of final instruction
    for _ in range(3):
        cycle += 1
        pipe = ["-", "-", pipe[1], pipe[2], pipe[3]]
        _record_cycle("Pipeline Drain")

    n_ret = len(retired)
    cpi = (cycle / n_ret) if n_ret > 0 else 0.0
    return {
        "retired_instructions": n_ret,
        "total_cycles": cycle,
        "ideal_cycles": n_ret,
        "cpi": round(cpi, 3),
        "load_use_stalls": load_use_stalls,
        "branch_flushes": branch_flushes,
        "delay_slots": delay_slots,
        "ex_forwards": ex_forwards,
        "mem_forwards": mem_forwards,
        "runtime_25mhz_us": round(cycle / 25.0, 2),
        "runtime_100mhz_us": round(cycle / 100.0, 2),
        "hazard_events": hazard_events,
        "timeline": timeline,
        "final_regs": list(sim.regs),
        "led_value": sim.led_value,
        "seg7_value": sim.seg7_value,
        "rgb_value": list(sim.rgb_value),
        "uart_output": sim.uart_buffer,
        "halted": halted,
    }


def find_gtkwave_bin():
    """Find GTKWave executable in project toolchain or system PATH."""
    roots = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.dirname(sys.executable),
    ]
    cands = []
    for r in roots:
        cands.append(os.path.join(r, "toolchain", "gtkwave", "bin", "gtkwave.exe"))
        cands.append(os.path.join(r, "toolchain", "iverilog", "bin", "gtkwave.exe"))
    cands.extend([
        shutil.which("gtkwave"),
        r"C:\iverilog\gtkwave\bin\gtkwave.exe",
    ])
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def detect_verilog_simulator():
    """
    Check if Icarus Verilog (`iverilog` + `vvp`) or Xilinx Vivado XSim (`xvlog` + `xelab` + `xsim`)
    is installed in FPGA Studio toolchain or on the host machine.
    """
    roots = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.dirname(sys.executable),
    ]
    iverilog_cands = []
    for r in roots:
        iverilog_cands.append(os.path.join(r, "toolchain", "iverilog", "bin", "iverilog.exe"))
    iverilog_cands.extend([
        shutil.which("iverilog"),
        r"C:\iverilog\bin\iverilog.exe",
        r"C:\Program Files\iverilog\bin\iverilog.exe",
    ])
    for iv in iverilog_cands:
        if iv and os.path.isfile(iv):
            vvp = os.path.join(os.path.dirname(iv), "vvp.exe" if os.name == "nt" else "vvp")
            if not os.path.isfile(vvp):
                vvp = shutil.which("vvp")
            if vvp:
                return {"kind": "iverilog", "iverilog": iv, "vvp": vvp}

    xvlog = shutil.which("xvlog")
    xelab = shutil.which("xelab")
    xsim = shutil.which("xsim")
    if xvlog and xelab and xsim:
        return {"kind": "xsim", "xvlog": xvlog, "xelab": xelab, "xsim": xsim}

    return None


def generate_gtkwave_savefile(out_dir, arch="mips", vcd_path=None):
    """
    Generate a GTKWave `.gtkw` configuration file (`waveform.gtkw`) that automatically
    populates Clock/Reset, Instruction ROM Bus, CPU Internal Pipeline (`u_dut`),
    Data Memory/MMIO Bus, and Nexys A7 Peripherals at an optimal zoom level.
    """
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    gtkw_path = os.path.join(out_dir, "waveform.gtkw")
    if not vcd_path:
        cand_vcd = os.path.join(out_dir, "waveform.vcd")
        if os.path.isfile(cand_vcd):
            vcd_path = cand_vcd

    # Discover internal u_dut signals from VCD header if available
    dut_signals = {}
    if vcd_path and os.path.isfile(vcd_path):
        scope_stack = []
        try:
            with open(vcd_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("$scope"):
                        parts = line.split()
                        if len(parts) >= 3:
                            scope_stack.append(parts[2])
                    elif line.startswith("$upscope"):
                        if scope_stack:
                            scope_stack.pop()
                    elif line.startswith("$var") and scope_stack == ["tb_cpu_cosim", "u_dut"]:
                        m = re.match(
                            r"^\$var\s+\S+\s+(\d+)\s+\S+\s+([a-zA-Z0-9_]+)(?:\s+(\[[0-9:]+\]))?\s+\$end",
                            line,
                        )
                        if m:
                            width = int(m.group(1))
                            name = m.group(2)
                            rng = m.group(3) or ""
                            dut_signals[name] = (width, f"tb_cpu_cosim.u_dut.{name}{rng}")
                    elif line.startswith("$enddefinitions"):
                        break
        except Exception:
            pass

    lines = [
        "[timestart] 0",
        "[size] 1360 780",
        "[pos] -1 -1",
        "*-16.200000 25000 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1",
        "[treeopen] tb_cpu_cosim.",
        "[treeopen] tb_cpu_cosim.u_dut.",
        "[sst_width] 220",
        "[signals_width] 230",
        "[sst_expanded] 1",
        "[sst_vpaned_height] 220",
        "@200",
        "-Clock & Reset",
        "@28",
        "tb_cpu_cosim.clk",
        "tb_cpu_cosim.rst",
        "@24",
        "tb_cpu_cosim.cyc_cnt[31:0]",
        "@200",
        "-Instruction Fetch (ROM Bus)",
        "@28",
        "tb_cpu_cosim.rom_ce",
        "@22",
        "tb_cpu_cosim.rom_addr[31:0]",
        "tb_cpu_cosim.rom_data[31:0]",
        "@200",
        "-CPU Core 5-Stage Pipeline (u_dut)",
    ]

    priority_names = [
        "pc", "if_id_pc", "if_id_inst", "id_ex_pc", "id_ex_inst",
        "ex_mem_pc", "ex_mem_alu_res", "mem_wb_pc", "wb_data",
        "load_use_stall", "branch_flush", "fwd_a", "fwd_b",
        "id_pc_i", "id_inst_i", "ex_reg1_i", "ex_reg2_i", "ex_wdata_o",
        "mem_wdata_o", "wb_wdata_i", "stall",
        "rs1", "rs2", "rd", "rdata1", "rdata2", "alu_res", "reg_we", "branch_taken",
        "rtl_cycle_cnt", "rtl_inst_retired", "rtl_load_stalls",
        "rtl_ex_fwds", "rtl_mem_fwds", "rtl_branch_flushes",
    ]
    added_dut = []
    if dut_signals:
        for pname in priority_names:
            if pname in dut_signals:
                added_dut.append(dut_signals[pname])
        if len(added_dut) < 4:
            for k, val in dut_signals.items():
                if k not in ("clk", "rst") and val not in added_dut:
                    added_dut.append(val)
                    if len(added_dut) >= 12:
                        break
    else:
        if arch == "mips":
            added_dut = [
                (32, "tb_cpu_cosim.u_dut.pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.id_pc_i[31:0]"),
                (32, "tb_cpu_cosim.u_dut.id_inst_i[31:0]"),
                (32, "tb_cpu_cosim.u_dut.ex_reg1_i[31:0]"),
                (32, "tb_cpu_cosim.u_dut.ex_reg2_i[31:0]"),
                (32, "tb_cpu_cosim.u_dut.ex_wdata_o[31:0]"),
                (32, "tb_cpu_cosim.u_dut.mem_wdata_o[31:0]"),
                (32, "tb_cpu_cosim.u_dut.wb_wdata_i[31:0]"),
                (6,  "tb_cpu_cosim.u_dut.stall[5:0]"),
            ]
        else:
            added_dut = [
                (32, "tb_cpu_cosim.u_dut.pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.if_id_pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.if_id_inst[31:0]"),
                (32, "tb_cpu_cosim.u_dut.id_ex_pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.ex_mem_pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.ex_mem_alu_res[31:0]"),
                (32, "tb_cpu_cosim.u_dut.mem_wb_pc[31:0]"),
                (32, "tb_cpu_cosim.u_dut.wb_data[31:0]"),
                (1,  "tb_cpu_cosim.u_dut.load_use_stall"),
                (1,  "tb_cpu_cosim.u_dut.branch_flush"),
                (2,  "tb_cpu_cosim.u_dut.fwd_a[1:0]"),
                (2,  "tb_cpu_cosim.u_dut.fwd_b[1:0]"),
                (1,  "tb_cpu_cosim.u_dut.reg_we"),
                (1,  "tb_cpu_cosim.u_dut.branch_taken"),
            ]

    for width, sig_path in added_dut:
        lines.append("@28" if width == 1 else "@22")
        lines.append(sig_path)

    lines.extend([
        "@200",
        "-Data Memory & MMIO Bus",
        "@28",
        "tb_cpu_cosim.ram_ce",
        "tb_cpu_cosim.ram_we",
        "tb_cpu_cosim.is_mmio",
        "@22",
        "tb_cpu_cosim.ram_addr[31:0]",
        "tb_cpu_cosim.ram_wdata[31:0]",
        "tb_cpu_cosim.ram_rdata[31:0]",
        "@200",
        "-Nexys A7 Board Peripherals",
        "@22",
        "tb_cpu_cosim.led_reg[15:0]",
        "tb_cpu_cosim.seg7_reg[31:0]",
        "tb_cpu_cosim.rgb_reg[23:0]",
        "tb_cpu_cosim.sw_i[15:0]",
        "tb_cpu_cosim.btn_i[5:0]",
    ])

    with open(gtkw_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return gtkw_path



_MMIO_DEVICES = ("led", "seg7", "rgb", "uart")
_P2_STEPS = 300
_STABILITY_STEPS = 300


def _golden_snapshot(sim):
    return (
        sim.led_value & 0xFFFF,
        sim.seg7_value & 0xFFFFFFFF,
        ((sim.rgb_value[0] & 0xFFF) << 12) | (sim.rgb_value[1] & 0xFFF),
    )


def _golden_run(sim, instructions, is_mips, raw_asm, n_steps, trace=None):
    """Step the golden ISA simulator up to `n_steps` instructions.
    Appends every MMIO output change (LED/SEG7/RGB value changes, UART chars) to `trace`.
    Returns (steps_executed, halted)."""
    steps = 0
    halted = False
    prev = _golden_snapshot(sim)
    prev_uart = len(sim.uart_buffer)
    for _ in range(int(n_steps)):
        if sim.pc_index < 0 or sim.pc_index >= len(instructions):
            halted = True
            break
        r = sim.step(instructions, is_mips=is_mips, raw_asm_text=raw_asm)
        steps += 1
        if trace is not None:
            cur = _golden_snapshot(sim)
            for i, dev in enumerate(("led", "seg7", "rgb")):
                if cur[i] != prev[i]:
                    trace[dev].append(cur[i])
            prev = cur
            ub = sim.uart_buffer
            if len(ub) > prev_uart:
                trace["uart"].extend(ord(c) for c in ub[prev_uart:])
            prev_uart = len(ub)
        if r and r.get("is_halted"):
            halted = True
            break
    if sim.pc_index < 0 or sim.pc_index >= len(instructions):
        halted = True
    return steps, halted


def _parse_rtl_mmio_trace(stdout, led_addr, seg7_addr, rgb_addr):
    """Rebuild the Phase-1 MMIO output-change trace from the RTL simulation log."""
    trace = {d: [] for d in _MMIO_DEVICES}
    cur = {"led": 0, "seg7": 0, "rgb": 0}
    for line in stdout.splitlines():
        if line.startswith("PHASE1_END"):
            break
        m = re.match(r"MMIO_WRITE cycle=\d+ addr=0x([0-9a-fA-F]+) data=0x([0-9a-fA-F]+)", line)
        if m:
            addr = int(m.group(1), 16)
            data = int(m.group(2), 16)
            dev, val = None, None
            if addr == led_addr:
                dev, val = "led", data & 0xFFFF
            elif addr == seg7_addr:
                dev, val = "seg7", data & 0xFFFFFFFF
            elif addr == rgb_addr:
                dev, val = "rgb", data & 0xFFFFFF
            if dev and val != cur[dev]:
                trace[dev].append(val)
                cur[dev] = val
            continue
        m = re.match(r"UART_CHAR char=(\d+)", line)
        if m:
            b = int(m.group(1)) & 0xFF
            if 32 <= b <= 126 or b in (10, 13):
                trace["uart"].append(b)
    return trace


def _compare_traces(golden, rtl, exact):
    """exact=True : RTL stopped after exactly N instructions -> traces must be identical.
    exact=False: RTL ran a cycle budget (>= N instructions) -> golden must be a prefix of RTL."""
    mism = []
    for dev in _MMIO_DEVICES:
        g, r = golden.get(dev, []), rtl.get(dev, [])
        ok = (g == r) if exact else (len(r) >= len(g) and r[:len(g)] == g)
        if not ok:
            idx = next((i for i in range(min(len(g), len(r))) if g[i] != r[i]), min(len(g), len(r)))
            g_v = f"0x{g[idx]:X}" if idx < len(g) else "(none)"
            r_v = f"0x{r[idx]:X}" if idx < len(r) else "(none)"
            mism.append(f"{dev.upper()} write#{idx + 1}: golden={g_v} rtl={r_v} (golden {len(g)} / rtl {len(r)} changes)")
    return (not mism), mism


def _cpu_has_perf_counters(cpu_hdl_path):
    if not cpu_hdl_path or not os.path.isfile(cpu_hdl_path):
        return False
    try:
        with open(cpu_hdl_path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        m_top = re.search(r"\bmodule\s+\w+.*?\bendmodule\b", txt, flags=re.DOTALL | re.IGNORECASE)
        top_txt = m_top.group(0) if m_top else txt
        return all(k in top_txt for k in ("rtl_mem_done", "rtl_inst_retired", "rtl_cycle_cnt"))
    except Exception:
        return False


def export_rtl_testbench(
    out_dir,
    instructions,
    arch="mips",
    cpu_hdl_path=None,
    sim_cycles=400,
    sw_init=0,
    btn_init=0,
    mmio_map=None,
):
    """
    Export a self-contained, self-checking Verilog RTL testbench package
    (`tb_cpu_cosim.v`, `program.hex`, `dmem_init.hex`, `rtl_cpu/`, runner scripts).

    `sim_cycles` is the maximum number N of instructions executed by the golden ISA
    simulator for Phase 1.  The testbench then:
      * cores with FPGA Studio perf counters: stops exactly when N instructions have
        completed MEM (exact MMIO-trace equality is required),
      * any other core: runs a generous cycle budget (4N+200) and the golden trace must
        be a prefix of the RTL trace.
    The CPU is connected via `resolve_cpu_port_binding`, so uploaded CPUs with other
    port names (or a cpu_manifest.json port_mapping) are supported.
    """
    from core.cpu_port_binding import resolve_cpu_port_binding, render_cpu_instance, describe_binding_th

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    rtl_cpu_dir = os.path.join(out_dir, "rtl_cpu")
    os.makedirs(rtl_cpu_dir, exist_ok=True)

    mmio = mmio_map or {}
    led_addr  = int(str(mmio.get("led",       "0xF0000000")), 16)
    sw_addr   = int(str(mmio.get("sw",        "0xF0000004")), 16)
    seg7_addr = int(str(mmio.get("seg7",      "0xF0000008")), 16)
    btn_addr  = int(str(mmio.get("btn",       "0xF000000C")), 16)
    uart_addr = int(str(mmio.get("uart_tx",   "0xF0000010")), 16)
    stat_addr = int(str(mmio.get("uart_stat", "0xF0000014")), 16)
    rgb_addr  = int(str(mmio.get("rgb",       "0xF0000018")), 16)

    binding = resolve_cpu_port_binding(cpu_hdl_path, arch=arch)
    if not binding["ok"]:
        raise ValueError("เชื่อมพอร์ต CPU เข้ากับ Testbench ไม่ได้ — " + describe_binding_th(binding))
    cpu_mod_name = binding["module"]

    copied_rtl = []
    if cpu_hdl_path and os.path.exists(cpu_hdl_path):
        src_dir = os.path.dirname(os.path.abspath(cpu_hdl_path))
        skip_sim_wrappers = {"top.v", "inst_rom.v", "data_ram.v", "openmips_min_sopc.v", "openmips_min_sopc_tb.v"}
        for fn in sorted(os.listdir(src_dir)):
            if fn.lower() in skip_sim_wrappers or fn.lower().startswith("tb_"):
                continue
            if fn.lower().endswith((".v", ".sv", ".vh")):
                shutil.copy2(os.path.join(src_dir, fn), os.path.join(rtl_cpu_dir, fn))
                copied_rtl.append(fn)

    # program.hex & dmem_init.hex (4096 words each)
    imem_words = [0] * 4096
    init_dmem = {}
    if instructions:
        init_dmem = instructions[0].get("init_dmem", {}) or {}
        for i, ins in enumerate(instructions[:4096]):
            imem_words[i] = ins.get("word", int(ins["hex"], 16)) & 0xFFFFFFFF
    prog_hex = os.path.join(out_dir, "program.hex")
    with open(prog_hex, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{w:08X}" for w in imem_words) + "\n")
    dmem_words = [0] * 4096
    for byte_addr, w_val in init_dmem.items():
        w_idx = ((int(byte_addr) & 0x00003FFF) >> 2)
        if 0 <= w_idx < 4096:
            dmem_words[w_idx] = int(w_val) & 0xFFFFFFFF
    dmem_hex = os.path.join(out_dir, "dmem_init.hex")
    with open(dmem_hex, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{w:08X}" for w in dmem_words) + "\n")

    # ---------------- Golden reference (ISA simulator) ----------------
    is_mips_tb = (arch == "mips")
    sw_p1 = int(sw_init) & 0xFFFF
    sw_p2 = 0x00A5 if sw_p1 != 0x00A5 else 0x005A
    has_cnt = _cpu_has_perf_counters(cpu_hdl_path)
    golden_trace = {d: [] for d in _MMIO_DEVICES}
    n_insts, halted = 0, True
    p1_vals = p2_vals = (0, 0, 0)
    stable1 = stable2 = True
    if instructions:
        gsim = CPUSimulatorEngine()
        if mmio_map:
            gsim.set_mmio_map(mmio_map)
        raw_asm_tb = "\n".join(i.get("asm", "") for i in instructions)
        gsim.load_program(instructions, raw_asm_text=raw_asm_tb)
        gsim.sw_value = sw_p1
        gsim.btn_value = int(btn_init) & 0x3F
        n_insts, halted = _golden_run(gsim, instructions, is_mips_tb, raw_asm_tb, max(int(sim_cycles), 1), golden_trace)
        p1_vals = _golden_snapshot(gsim)
        if not halted:
            _, h = _golden_run(gsim, instructions, is_mips_tb, raw_asm_tb, _STABILITY_STEPS)
            stable1 = h or (_golden_snapshot(gsim) == p1_vals)
        gsim.sw_value = sw_p2
        _, h2 = _golden_run(gsim, instructions, is_mips_tb, raw_asm_tb, _P2_STEPS)
        p2_vals = _golden_snapshot(gsim)
        if not h2:
            _, h3 = _golden_run(gsim, instructions, is_mips_tb, raw_asm_tb, _STABILITY_STEPS)
            stable2 = h3 or (_golden_snapshot(gsim) == p2_vals)

    n_insts = max(n_insts, 1)
    p1_budget = 4 * n_insts + 200
    p2_budget = 4 * _P2_STEPS + 100
    check_p1 = has_cnt or stable1
    check_p2 = stable2

    # ---------------- Testbench body ----------------
    sig = {
        "clk": "clk", "rst": "rst",
        "rom_addr": "rom_addr", "rom_data": "rom_data", "rom_ce": "rom_ce",
        "ram_addr": "ram_addr", "ram_wdata": "ram_wdata", "ram_rdata": "ram_rdata",
        "ram_we": "ram_we", "ram_ce": "ram_ce", "ram_sel": "ram_sel",
    }
    cpu_inst = render_cpu_instance(binding, "u_dut", sig)

    def _wait(cond_target, budget, start_var):
        if has_cnt:
            return (f"        while (u_dut.rtl_mem_done < {cond_target} && (cyc_cnt - {start_var}) < {budget}) begin\n"
                    f"            @(posedge clk); #1;\n        end\n")
        return (f"        while ((cyc_cnt - {start_var}) < {budget}) begin\n"
                f"            @(posedge clk); #1;\n        end\n")

    perf_block = ""
    if has_cnt:
        perf_block = (
            f"        guard = 0;\n"
            f"        while (u_dut.rtl_inst_retired < {n_insts} && guard < 16) begin\n"
            f"            @(posedge clk); #1; guard = guard + 1;\n"
            f"        end\n"
            '        $display("RTL_PERF cyc=%0d ret=%0d stall=%0d ex_fwd=%0d mem_fwd=%0d flush=%0d div_stall=%0d mem_done=%0d",\n'
            "                 u_dut.rtl_cycle_cnt, u_dut.rtl_inst_retired, u_dut.rtl_load_stalls, u_dut.rtl_ex_fwds,\n"
            "                 u_dut.rtl_mem_fwds, u_dut.rtl_branch_flushes, u_dut.rtl_div_stalls, u_dut.rtl_mem_done);\n"
        )

    e1l, e1s, e1r = p1_vals
    e2l, e2s, _ = p2_vals
    checks = "        ok = 1; checked = 0;\n"
    if check_p1:
        checks += (
            f"        checked = checked + 1;\n"
            f"        if (p1_led !== 16'h{e1l:04X} || p1_seg7 !== 32'h{e1s:08X} || p1_rgb !== 24'h{e1r:06X}) begin\n"
            f"            ok = 0;\n"
            f'            $display("FAIL_DETAIL Phase1 got LED=0x%04X SEG7=0x%08X RGB=0x%06X exp LED=0x{e1l:04X} SEG7=0x{e1s:08X} RGB=0x{e1r:06X}", p1_led, p1_seg7, p1_rgb);\n'
            f"        end\n"
        )
    else:
        checks += '        $display("INFO Phase1 output is time-varying on this core; verified by host MMIO-trace comparison");\n'
    if check_p2:
        checks += (
            f"        checked = checked + 1;\n"
            f"        if (led_reg !== 16'h{e2l:04X} || seg7_reg !== 32'h{e2s:08X}) begin\n"
            f"            ok = 0;\n"
            f'            $display("FAIL_DETAIL Phase2 got LED=0x%04X SEG7=0x%08X exp LED=0x{e2l:04X} SEG7=0x{e2s:08X}", led_reg, seg7_reg);\n'
            f"        end\n"
        )
    else:
        checks += '        $display("INFO Phase2 skipped: output keeps changing over time (not a switch-driven steady state)");\n'
    checks += (
        "        if (!ok) $display(\"FAIL: RTL outputs differ from golden ISA reference\");\n"
        "        else if (checked == 0) $display(\"INCONCLUSIVE: no steady-state output to self-check; see host MMIO-trace comparison\");\n"
        f"        else $display(\"PASS: Phase1(SW=0x{sw_p1:04X}->LED=0x%04X,SEG7=0x%08X) Phase2_DynamicSW(SW=0x{sw_p2:04X}->LED=0x%04X,SEG7=0x%08X)\", p1_led, p1_seg7, led_reg, seg7_reg);\n"
    )

    stop_desc = (f"stops after exactly {n_insts} instructions complete MEM (rtl_mem_done)"
                 if has_cnt else f"runs a {p1_budget}-cycle budget (core has no instruction counter)")

    tb_path = os.path.join(out_dir, "tb_cpu_cosim.v")
    tb_verilog = f"""`timescale 1ns / 1ps
// ==============================================================================
// FPGA Studio — Self-Checking RTL Co-Simulation & Waveform Testbench
// Target Core : {cpu_mod_name} ({arch.upper()})   reset: {'active-low' if binding['rst_active_low'] else 'active-high'}
// Phase 1     : SW=0x{sw_p1:04X}, {stop_desc}
// Phase 2     : SW changes to 0x{sw_p2:04X} while running (dynamic input test)
// Golden      : FPGA Studio ISA simulator, {n_insts} instructions{' (program halts)' if halted else ''}
// Output      : waveform.vcd, MMIO_WRITE trace, RTL_SUMMARY, PASS/FAIL/INCONCLUSIVE
// ==============================================================================
module tb_cpu_cosim;
    reg         clk = 1'b0;
    reg         rst = 1'b1;
    reg  [15:0] sw_i  = 16'h{sw_p1:04X};
    reg  [5:0]  btn_i = 6'h{int(btn_init) & 0x3F:02X};

    always #5 clk = ~clk; // 100 MHz simulation clock (10 ns period)

    reg [31:0] imem [0:4095];
    reg [31:0] dmem [0:4095];
    integer init_i, fd_dmem;

    initial begin
        for (init_i = 0; init_i < 4096; init_i = init_i + 1) begin
            imem[init_i] = 32'd0;
            dmem[init_i] = 32'd0;
        end
        $readmemh("program.hex", imem);
        fd_dmem = $fopen("dmem_init.hex", "r");
        if (fd_dmem != 0) begin
            $fclose(fd_dmem);
            $readmemh("dmem_init.hex", dmem);
        end
    end

    wire [31:0] rom_addr;
    wire        rom_ce;
    wire [31:0] rom_data = rom_ce ? imem[rom_addr[13:2]] : 32'd0;

    wire [31:0] ram_addr;
    wire [31:0] ram_wdata;
    reg  [31:0] ram_rdata;
    wire        ram_we;
    wire        ram_ce;
    wire [3:0]  ram_sel;

{cpu_inst}

    reg [15:0] led_reg  = 16'd0;
    reg [31:0] seg7_reg = 32'd0;
    reg [23:0] rgb_reg  = 24'd0;
    reg [15:0] p1_led   = 16'd0;
    reg [31:0] p1_seg7  = 32'd0;
    reg [23:0] p1_rgb   = 24'd0;
    integer    cyc_cnt  = 0;
    integer    p_start  = 0;
    integer    guard    = 0;
    integer    ok       = 1;
    integer    checked  = 0;

    wire is_mmio = (ram_addr[31:24] == 8'hF0) || (ram_addr[31:24] == 8'hFF);
    wire [11:0] dmem_idx = ram_addr[13:2];

    always @(posedge clk) begin
        if (!rst) begin
            cyc_cnt <= cyc_cnt + 1;
            if (ram_ce && ram_we) begin
                if (!is_mmio) begin
                    if (ram_sel[0]) dmem[dmem_idx][7:0]   <= ram_wdata[7:0];
                    if (ram_sel[1]) dmem[dmem_idx][15:8]  <= ram_wdata[15:8];
                    if (ram_sel[2]) dmem[dmem_idx][23:16] <= ram_wdata[23:16];
                    if (ram_sel[3]) dmem[dmem_idx][31:24] <= ram_wdata[31:24];
                end else begin
                    $display("MMIO_WRITE cycle=%0d addr=0x%08X data=0x%08X", cyc_cnt, ram_addr, ram_wdata);
                    case (ram_addr)
                        32'h{led_addr:08X}:  led_reg  <= ram_wdata[15:0];
                        32'h{seg7_addr:08X}: seg7_reg <= ram_wdata;
                        32'h{rgb_addr:08X}:  rgb_reg  <= ram_wdata[23:0];
                        32'h{uart_addr:08X}: $display("UART_CHAR char=%0d", ram_wdata[7:0]);
                    endcase
                end
            end
        end
    end

    always @(*) begin
        if (!ram_ce) begin
            ram_rdata = 32'd0;
        end else if (is_mmio) begin
            case (ram_addr)
                32'h{led_addr:08X}:  ram_rdata = {{16'd0, led_reg}};
                32'h{sw_addr:08X}:   ram_rdata = {{16'd0, sw_i}};
                32'h{seg7_addr:08X}: ram_rdata = seg7_reg;
                32'h{btn_addr:08X}:  ram_rdata = {{26'd0, btn_i}};
                32'h{stat_addr:08X}: ram_rdata = 32'h00000002; // TX ready
                32'h{rgb_addr:08X}:  ram_rdata = {{8'd0, rgb_reg}};
                default:             ram_rdata = 32'd0;
            endcase
        end else begin
            ram_rdata = dmem[dmem_idx];
        end
    end

    initial begin
        $dumpfile("waveform.vcd");
        $dumpvars(0, tb_cpu_cosim);
        #22 rst = 1'b0; // release reset between negedge(20ns) and posedge(25ns)

        // ---------------- Phase 1 ----------------
        p_start = 0;
{_wait(n_insts, p1_budget, "p_start")}        p1_led  = led_reg;
        p1_seg7 = seg7_reg;
        p1_rgb  = rgb_reg;
        $display("PHASE1_END cyc=%0d", cyc_cnt);
        $display("RTL_SUMMARY LED=0x%04X SEG7=0x%08X RGB=0x%06X", p1_led, p1_seg7, p1_rgb);
{perf_block}
        // ---------------- Phase 2: dynamic switch stimulus ----------------
        sw_i = 16'h{sw_p2:04X};
        p_start = cyc_cnt;
{_wait(n_insts + _P2_STEPS, p2_budget, "p_start")}        $display("RTL_DYN_SW SW=0x{sw_p2:04X} LED=0x%04X SEG7=0x%08X", led_reg, seg7_reg);

{checks}        $finish;
    end
endmodule
"""
    with open(tb_path, "w", encoding="utf-8") as f:
        f.write(tb_verilog)

    gtkw_path = generate_gtkwave_savefile(out_dir, arch=arch)

    iv_sim = detect_verilog_simulator()
    iv_cmd = f'"{iv_sim["iverilog"]}"' if iv_sim and iv_sim.get("kind") == "iverilog" else "iverilog"
    vvp_cmd = f'"{iv_sim["vvp"]}"' if iv_sim and iv_sim.get("kind") == "iverilog" else "vvp"
    gw_bin = find_gtkwave_bin()
    gw_cmd = f'"{gw_bin}"' if gw_bin else "gtkwave"

    bat_path = os.path.join(out_dir, "run_iverilog_gtkwave.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(
            "@echo off\n"
            "echo [FPGA Studio] Compiling RTL with Icarus Verilog...\n"
            f"{iv_cmd} -g2012 -I rtl_cpu -o sim_cosim.vvp tb_cpu_cosim.v rtl_cpu\\*.v\n"
            "if errorlevel 1 goto :err\n"
            "echo [FPGA Studio] Running simulation & generating waveform.vcd...\n"
            f"{vvp_cmd} sim_cosim.vvp\n"
            f"start \"\" {gw_cmd} waveform.vcd waveform.gtkw\n"
            "pause\n"
            "exit /b 0\n"
            ":err\n"
            "echo [Error] Icarus Verilog compilation failed.\n"
            "pause\n"
        )

    xsim_tcl = os.path.join(out_dir, "run_vivado_xsim.tcl")
    with open(xsim_tcl, "w", encoding="utf-8") as f:
        f.write(
            f"# Usage in Vivado Tcl Console:\n"
            f"#   cd {{{out_dir.replace(os.sep, '/')}}}\n"
            f"#   source run_vivado_xsim.tcl\n"
            f"create_project -force rtl_cosim_proj ./xsim_proj -part xc7a100tcsg324-1\n"
            f"add_files -fileset sim_1 -norecurse [glob -nocomplain ./rtl_cpu/*.v]\n"
            f"add_files -fileset sim_1 -norecurse ./tb_cpu_cosim.v ./program.hex ./dmem_init.hex\n"
            f"set_property include_dirs [list ./rtl_cpu] [get_filesets sim_1]\n"
            f"set_property top tb_cpu_cosim [get_filesets sim_1]\n"
            f"launch_simulation\n"
            f"run all\n"
        )

    return {
        "out_dir": out_dir,
        "tb_v": tb_path,
        "program_hex": prog_hex,
        "dmem_hex": dmem_hex,
        "gtkw_file": gtkw_path,
        "bat_script": bat_path,
        "xsim_tcl": xsim_tcl,
        "copied_rtl": copied_rtl,
        "binding": binding,
        "golden": {
            "n_insts": n_insts,
            "halted": halted,
            "trace": golden_trace,
            "exact": has_cnt,
            "p1": p1_vals,
            "p2": p2_vals,
            "sw_p2": sw_p2,
        },
        "mmio_addrs": (led_addr, seg7_addr, rgb_addr),
    }


# ------------------------------------------------------------------------------
# VCD -> real pipeline timeline / hazard events (for cores exposing FPGA Studio
# pipeline signal names, e.g. the bundled riscv_rv32i 5-stage core)
# ------------------------------------------------------------------------------
_VCD_PIPE_SIGNALS = (
    "pc", "fetch_valid", "if_id_pc", "if_id_valid", "id_ex_pc", "id_ex_valid",
    "ex_mem_pc", "ex_mem_valid", "mem_wb_pc", "mem_wb_valid", "load_use_stall",
    "ex_branch_taken", "id_jal_taken", "fwd_a", "fwd_b", "id_ex_rs1", "id_ex_rs2",
    "div_stall", "id_ex_rd",
)
_VCD_REQUIRED = ("pc", "if_id_pc", "if_id_valid", "id_ex_pc", "id_ex_valid", "ex_mem_pc",
                 "ex_mem_valid", "mem_wb_pc", "mem_wb_valid", "load_use_stall", "fwd_a", "fwd_b")


def _read_vcd_samples(vcd_path, sample_times_ns):
    """Return list of {signal: int|None} sampled at the given (sorted) times (in ns) for u_dut signals."""
    id_map = {}
    scope = []
    vals = {}
    samples = []
    s_idx = 0
    ns_mult = 1000  # default for `timescale 1ns / 1ps
    sample_times = [t * ns_mult for t in sample_times_ns]
    in_ts = False
    with open(vcd_path, "r", encoding="utf-8", errors="ignore") as f:
        in_header = True
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if in_header:
                if line.startswith("$timescale"):
                    in_ts = True
                if in_ts:
                    if "1ps" in line:
                        ns_mult = 1000
                    elif "10ps" in line:
                        ns_mult = 100
                    elif "100ps" in line:
                        ns_mult = 10
                    elif "1ns" in line:
                        ns_mult = 1
                    if "$end" in line:
                        in_ts = False
                        sample_times = [t * ns_mult for t in sample_times_ns]
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3:
                        scope.append(parts[2])
                elif line.startswith("$upscope"):
                    if scope:
                        scope.pop()
                elif line.startswith("$var") and scope == ["tb_cpu_cosim", "u_dut"]:
                    parts = line.split()
                    if len(parts) >= 5 and parts[4] in _VCD_PIPE_SIGNALS:
                        id_map.setdefault(parts[3], []).append(parts[4])
                elif line.startswith("$enddefinitions"):
                    in_header = False
                    if not all(any(s in v for v in id_map.values()) for s in _VCD_REQUIRED):
                        return None
                continue
            if line[0] == "#":
                t = int(line[1:])
                while s_idx < len(sample_times) and sample_times[s_idx] < t:
                    samples.append(dict(vals))
                    s_idx += 1
                if s_idx >= len(sample_times):
                    break
                continue
            if line[0] in "01xzXZ":
                code = line[1:]
                if code in id_map:
                    v = None if line[0] in "xzXZ" else int(line[0])
                    for n in id_map[code]:
                        vals[n] = v
            elif line[0] in "bB":
                bits, _, code = line[1:].partition(" ")
                if code in id_map:
                    v = None if any(c in bits for c in "xzXZ") else int(bits, 2)
                    for n in id_map[code]:
                        vals[n] = v
    while s_idx < len(sample_times):
        samples.append(dict(vals))
        s_idx += 1
    return samples


def extract_pipeline_from_vcd(vcd_path, instructions, n_cycles, is_mips=False, max_rows=120, max_events=200):
    """
    Build the 5-stage timeline and hazard-event list from REAL RTL waveform signals.
    Cycle n is sampled 1 ns before the n-th active clock edge (reset released at 22 ns,
    first active posedge at 25 ns), i.e. the stable state during that cycle.
    Returns None if the core does not expose the required pipeline signals.
    """
    if not vcd_path or not os.path.isfile(vcd_path):
        return None
    n = max(1, min(int(n_cycles), 5000))
    times = [24 + 10 * i for i in range(n)]
    samples = _read_vcd_samples(vcd_path, times)
    if not samples:
        return None

    def lbl(pc_val):
        if pc_val is None:
            return "?"
        idx = pc_val >> 2
        if 0 <= idx < len(instructions):
            ins = instructions[idx]
            return f"{ins.get('pc', f'0x{pc_val:04X}')}: {ins.get('asm', '')}"
        return f"0x{pc_val:08X}"

    timeline, events = [], []
    prev_div = False
    for c, s in enumerate(samples, start=1):
        g = lambda k, d=0: (s.get(k) if s.get(k) is not None else d)
        if_l = lbl(g("pc")) if g("fetch_valid", 1) else "-"
        id_l = lbl(g("if_id_pc")) if g("if_id_valid") else "🫧 bubble"
        ex_l = lbl(g("id_ex_pc")) if g("id_ex_valid") else "🫧 bubble"
        mem_l = lbl(g("ex_mem_pc")) if g("ex_mem_valid") else "🫧 bubble"
        wb_l = lbl(g("mem_wb_pc")) if g("mem_wb_valid") else "🫧 bubble"
        notes = []
        ex_pc = g("id_ex_pc")
        ex_asm = lbl(ex_pc).split(": ", 1)[-1]
        ex_pcs = lbl(ex_pc).split(": ", 1)[0]

        def add_ev(pc_s, asm, typ, detail):
            if len(events) < max_events:
                events.append({"cycle": c, "pc": pc_s, "asm": asm, "type": typ, "detail": detail})

        if g("load_use_stall"):
            rd = g("id_ex_rd")
            notes.append(f"STALL (Load-Use {_fmt_reg(rd, is_mips)})")
            id_parts = lbl(g("if_id_pc")).split(": ", 1)
            add_ev(id_parts[0], id_parts[-1], "RAW Load-Use Stall (+1 Cycle)",
                   f"load_use_stall=1: '{ex_asm}' ยังโหลด {_fmt_reg(rd, is_mips)} ไม่เสร็จ → แช่ PC/IF-ID และส่ง bubble เข้า EX")
        div_now = bool(g("div_stall"))
        if div_now and not prev_div:
            notes.append("STALL (Divider)")
            add_ev(ex_pcs, ex_asm, "Divider Stall (iterative 32-cycle)",
                   "div_stall=1: ตัวหารแบบวนรอบกำลังคำนวณ → แช่ IF/ID/EX และส่ง bubble ลง MEM")
        elif div_now:
            notes.append("STALL (Divider)")
        prev_div = div_now
        if g("id_ex_valid") and (not div_now or not prev_div or c == 1):
            fa, fb = g("fwd_a"), g("fwd_b")
            rs1, rs2 = g("id_ex_rs1"), g("id_ex_rs2")
            seen = set()
            for f_sel, reg in ((fa, rs1), (fb, rs2)):
                if f_sel in (1, 2) and (reg, f_sel) not in seen:
                    seen.add((reg, f_sel))
                    if f_sel == 2:
                        src = lbl(g("ex_mem_pc")).split(": ", 1)[-1]
                        notes.append(f"FWD EX→EX ({_fmt_reg(reg, is_mips)})")
                        add_ev(ex_pcs, ex_asm, "EX→EX Forwarding (0 Stall)",
                               f"fwd={f_sel:02b}: ค่า {_fmt_reg(reg, is_mips)} มาจาก EX/MEM ของ '{src}'")
                    else:
                        src = lbl(g("mem_wb_pc")).split(": ", 1)[-1]
                        notes.append(f"FWD MEM→EX ({_fmt_reg(reg, is_mips)})")
                        add_ev(ex_pcs, ex_asm, "MEM→EX Forwarding (0 Stall)",
                               f"fwd={f_sel:02b}: ค่า {_fmt_reg(reg, is_mips)} มาจาก MEM/WB ของ '{src}'")
        if g("ex_branch_taken"):
            notes.append("FLUSH (Branch/JALR in EX, 2 slots)")
            add_ev(ex_pcs, ex_asm, "Branch Flush (+2 Cycles)",
                   "ex_branch_taken=1: ล้าง IF/ID และ ID/EX ที่ดึงมาผิดเส้นทาง")
        elif g("id_jal_taken"):
            id_parts = lbl(g("if_id_pc")).split(": ", 1)
            notes.append("FLUSH (JAL in ID, 1 slot)")
            add_ev(id_parts[0], id_parts[-1], "Branch Flush (+1 Cycle)",
                   "id_jal_taken=1: คำนวณเป้าหมาย JAL ใน ID แล้วล้างคำสั่งใน IF")
        if len(timeline) < max_rows:
            timeline.append({"cycle": c, "IF": if_l, "ID": id_l, "EX": ex_l, "MEM": mem_l, "WB": wb_l,
                             "note": " • ".join(notes)})
    return {"timeline": timeline, "hazard_events": events}


def run_rtl_cosim(
    instructions,
    arch="mips",
    cpu_hdl_path=None,
    sim_cycles=400,
    sw_init=0,
    btn_init=0,
    mmio_map=None,
):
    """
    Differential verification: golden ISA simulator vs. real Verilog RTL (Icarus Verilog).

    Returned keys:
      projection : analytic 5-stage model (Python) — always present, always labelled as a model
      pipeline   : what the UI shows; `source` == "rtl" when the numbers/timeline come from the
                   RTL counters + waveform, otherwise "projection"
      passed     : True only if the MMIO output trace matches AND the testbench did not FAIL
    """
    is_mips = (arch == "mips")
    projection = analyze_pipeline_hazards(
        instructions,
        is_mips=is_mips,
        max_retired=max(sim_cycles, 100),
        sw_init=sw_init,
        btn_init=btn_init,
        mmio_map=mmio_map,
    )
    projection["source"] = "projection"
    pipe_view = dict(projection)

    def _result(**kw):
        base = {
            "ran_rtl": False, "simulator": None, "passed": None, "message": "",
            "golden_led": projection["led_value"] & 0xFFFF,
            "golden_seg7": projection["seg7_value"] & 0xFFFFFFFF,
            "pipeline": pipe_view, "projection": projection,
        }
        base.update(kw)
        return base

    sim_tool = detect_verilog_simulator()
    if not sim_tool or sim_tool["kind"] != "iverilog":
        return _result(message=(
            "ไม่พบ Icarus Verilog (`iverilog`) — ยังไม่ได้รัน RTL จริง ตัวเลขทั้งหมดเป็นค่าคาดการณ์จากโมเดล Python "
            "(ส่งออก Testbench ไปรันใน Vivado XSim / GTKWave ได้)"
        ))
    if cpu_hdl_path and os.path.splitext(cpu_hdl_path)[1].lower() in (".vhd", ".vhdl"):
        return _result(message="CPU เป็น VHDL — Icarus Verilog จำลอง VHDL ไม่ได้ ใช้ปุ่มส่งออกแล้วรันใน Vivado XSim แทน (ตัวเลขบนจอเป็นค่าคาดการณ์)")

    tmp_dir = tempfile.mkdtemp(prefix="fpga_studio_cosim_")
    try:
        try:
            pkg = export_rtl_testbench(
                tmp_dir, instructions, arch=arch, cpu_hdl_path=cpu_hdl_path,
                sim_cycles=max(projection["retired_instructions"], 1),
                sw_init=sw_init, btn_init=btn_init, mmio_map=mmio_map,
            )
        except ValueError as e:
            return _result(ran_rtl=False, passed=False, message=f"⚠️ {e}")

        rtl_files = [os.path.join(tmp_dir, "rtl_cpu", fn) for fn in pkg["copied_rtl"] if fn.lower().endswith((".v", ".sv"))]
        vvp_out = os.path.join(tmp_dir, "sim_cosim.vvp")
        cmd_compile = [sim_tool["iverilog"], "-g2012", "-I", os.path.join(tmp_dir, "rtl_cpu"), "-o", vvp_out, pkg["tb_v"]] + rtl_files
        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

        p_comp = subprocess.run(cmd_compile, cwd=tmp_dir, capture_output=True, text=True, timeout=30, creationflags=cflags)
        if p_comp.returncode != 0:
            return _result(ran_rtl=True, simulator="Icarus Verilog", passed=False,
                           message=f"คอมไพล์ Verilog RTL ไม่สำเร็จ: {(p_comp.stderr or p_comp.stdout).strip()[:600]}")

        p_run = subprocess.run([sim_tool["vvp"], vvp_out], cwd=tmp_dir, capture_output=True, text=True, timeout=60, creationflags=cflags)
        stdout = p_run.stdout or ""
        m = re.search(r"RTL_SUMMARY\s+LED=0x([0-9A-Fa-f]+)\s+SEG7=0x([0-9A-Fa-f]+)\s+RGB=0x([0-9A-Fa-f]+)", stdout)
        if not m:
            return _result(ran_rtl=True, simulator="Icarus Verilog", passed=False, rtl_log=stdout,
                           message="รัน RTL แล้วแต่ไม่พบบรรทัด RTL_SUMMARY (simulation อาจ error)")

        golden = pkg["golden"]
        led_a, seg_a, rgb_a = pkg["mmio_addrs"]
        rtl_trace = _parse_rtl_mmio_trace(stdout, led_a, seg_a, rgb_a)
        trace_ok, mism = _compare_traces(golden["trace"], rtl_trace, golden["exact"])
        tb_failed = "FAIL:" in stdout
        tb_pass = "PASS:" in stdout
        illegal = re.findall(r"RTL_ILLEGAL pc=0x([0-9A-Fa-f]+) inst=0x([0-9A-Fa-f]+)", stdout)

        # Real RTL counters (bundled core) -> replace the projected numbers
        rtl_perf = None
        m_perf = re.search(
            r"RTL_PERF\s+cyc=(\d+)\s+ret=(\d+)\s+stall=(\d+)\s+ex_fwd=(\d+)\s+mem_fwd=(\d+)\s+flush=(\d+)\s+div_stall=(\d+)\s+mem_done=(\d+)",
            stdout,
        )
        if m_perf:
            vals = [int(x) for x in m_perf.groups()]
            rtl_perf = dict(zip(("cycles", "retired", "load_use_stalls", "ex_forwards", "mem_forwards",
                                 "branch_flushes", "div_stalls", "mem_done"), vals))
            if rtl_perf["retired"] > 0:
                pipe_view.update({
                    "total_cycles": rtl_perf["cycles"],
                    "retired_instructions": rtl_perf["retired"],
                    "load_use_stalls": rtl_perf["load_use_stalls"],
                    "ex_forwards": rtl_perf["ex_forwards"],
                    "mem_forwards": rtl_perf["mem_forwards"],
                    "branch_flushes": rtl_perf["branch_flushes"],
                    "div_stalls": rtl_perf["div_stalls"],
                    "cpi": round(rtl_perf["cycles"] / rtl_perf["retired"], 3),
                    "runtime_25mhz_us": round(rtl_perf["cycles"] / 25.0, 2),
                    "runtime_100mhz_us": round(rtl_perf["cycles"] / 100.0, 2),
                    "source": "rtl",
                    "measured_from_rtl": True,
                })
        vcd_pipe = extract_pipeline_from_vcd(
            os.path.join(tmp_dir, "waveform.vcd"), instructions,
            n_cycles=(rtl_perf["cycles"] if rtl_perf else projection["total_cycles"]), is_mips=is_mips,
        )
        if vcd_pipe:
            pipe_view["timeline"] = vcd_pipe["timeline"]
            pipe_view["hazard_events"] = vcd_pipe["hazard_events"]
            pipe_view["timeline_source"] = "rtl"
        else:
            pipe_view["timeline_source"] = "projection"

        rtl_led = int(m.group(1), 16)
        rtl_seg7 = int(m.group(2), 16)
        passed = trace_ok and not tb_failed
        m_dyn = re.search(r"RTL_DYN_SW\s+SW=0x([0-9A-Fa-f]+)\s+LED=0x([0-9A-Fa-f]+)", stdout)
        if passed:
            msg = f"✅ RTL LED=0x{rtl_led:04X}, SEG7=0x{rtl_seg7:08X} == Golden ISA"
            if m_dyn and tb_pass:
                msg += f"   •   Dynamic SW=0x{int(m_dyn.group(1), 16):04X} → LED=0x{int(m_dyn.group(2), 16):04X} (PASS)"
        else:
            reasons = mism[:2] + (["testbench self-check รายงาน FAIL"] if tb_failed else [])
            msg = "❌ RTL ไม่ตรงกับ Golden ISA: " + " | ".join(reasons)
        if illegal:
            msg += f"   •   ⚠️ พบคำสั่งที่ core ไม่รองรับ {len(illegal)} ครั้ง (เช่น PC=0x{illegal[0][0]} inst=0x{illegal[0][1]})"

        return _result(
            ran_rtl=True,
            simulator="Icarus Verilog (iverilog + vvp)",
            passed=passed,
            rtl_led=rtl_led,
            rtl_seg7=rtl_seg7,
            rtl_log=stdout,
            rtl_perf=rtl_perf,
            trace_mismatches=mism,
            illegal_instructions=illegal,
            binding=pkg["binding"],
            message=msg,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

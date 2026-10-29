# -*- coding: utf-8 -*-
"""
Automated Tests for Stage 4 & Stage 5:
  - Synthesizable RV32IM Verilog Core (`riscv_rv32i.v`) & OpenMIPS Load-Use RTL Fix
  - Vivado Nexys A7-100T SoC Synthesis Package Export (`export_vivado_soc_package`)
  - 5-Stage Pipeline Hazard & CPI Analyzer (`analyze_pipeline_hazards`)
  - RTL Testbench & VCD Waveform Co-Simulator (`export_rtl_testbench` / `run_rtl_cosim`)
"""

import os
from core.assembler import assemble_riscv, assemble_mips
from core.hdl_analyzer import extract_cpu_ports, invalidate_hdl_cache
from core.hdl_generator import export_vivado_soc_package
from core.rtl_cosim import analyze_pipeline_hazards, export_rtl_testbench, run_rtl_cosim


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OPENMIPS_V = os.path.join(ROOT_DIR, "custom_cpus", "openmips", "openmips.v")
OPENMIPS_ID_V = os.path.join(ROOT_DIR, "custom_cpus", "openmips", "id.v")
RISCV_V = os.path.join(ROOT_DIR, "custom_cpus", "riscv", "riscv_rv32i.v")


def test_synthesizable_rv32im_rtl_ports_and_openmips_load_use():
    invalidate_hdl_cache(RISCV_V)
    pinfo = extract_cpu_ports(RISCV_V)
    assert pinfo["top_module"] == "riscv_rv32i"
    by_name = {p["name"]: p for p in pinfo["detailed_ports"]}

    assert by_name["rom_addr_o"]["dir"] == "output" and by_name["rom_addr_o"]["width"] == "31:0"
    assert by_name["rom_data_i"]["dir"] == "input" and by_name["rom_data_i"]["width"] == "31:0"
    assert by_name["ram_addr_o"]["dir"] == "output" and by_name["ram_addr_o"]["width"] == "31:0"
    assert by_name["ram_sel_o"]["dir"] == "output" and by_name["ram_sel_o"]["width"] == "3:0"

    with open(RISCV_V, "r", encoding="utf-8") as f:
        rv_rtl = f.read()
    # Confirm M-extension and full load/store/AUIPC support in synthesizable Verilog
    assert "7'b0000001" in rv_rtl  # RV32M
    assert "7'b0010111" in rv_rtl  # AUIPC

    with open(OPENMIPS_ID_V, "r", encoding="utf-8") as f:
        id_rtl = f.read()
    assert "stallreq_for_reg1_loadrelate" in id_rtl
    assert "pre_inst_is_load" in id_rtl


def test_export_vivado_soc_package_mips_and_riscv(tmp_path):
    rv_ins = assemble_riscv([
        "lui t0, 0xF0000",
        "lw t1, 4(t0)",
        "sw t1, 0(t0)",
    ])
    rv_out = str(tmp_path / "vivado_rv32")
    res_rv = export_vivado_soc_package(
        rv_out,
        rv_ins,
        arch="riscv",
        cpu_hdl_path=RISCV_V,
        mmio_map={"led": "0xF0000100", "sw": "0xF0000104"},
    )
    assert os.path.isfile(res_rv["top_v"])
    assert os.path.isfile(res_rv["loader_v"])
    assert os.path.isfile(res_rv["xdc"])
    assert os.path.isfile(res_rv["tcl"])
    assert "riscv_rv32i.v" in res_rv["copied_rtl"]

    with open(res_rv["top_v"], "r", encoding="utf-8") as f:
        top_txt = f.read()
    assert "riscv_rv32i u_cpu" in top_txt
    assert "32'hF0000100" in top_txt
    assert "32'hF0000104" in top_txt

    mips_ins = assemble_mips([
        "lui $t0, 0xF000",
        "lw $t1, 4($t0)",
        "sw $t1, 0($t0)",
    ])
    mips_out = str(tmp_path / "vivado_mips")
    res_mips = export_vivado_soc_package(mips_out, mips_ins, arch="mips", cpu_hdl_path=OPENMIPS_V)
    assert "openmips.v" in res_mips["copied_rtl"]
    assert "define.v" in res_mips["copied_rtl"]
    assert "top.v" not in res_mips["copied_rtl"]  # Simulation wrapper skipped


def test_pipeline_hazard_analyzer_stalls_forwarding_and_flushes():
    # 1. Load-Use Hazard on RV32: lw t1, 4(t0) immediately used by add t2, t1, t1
    rv_load_use = assemble_riscv([
        "lui t0, 0xF0000",
        "lw t1, 4(t0)",
        "add t2, t1, t1",
        "sw t2, 0(t0)",
    ])
    rep_lu = analyze_pipeline_hazards(rv_load_use, is_mips=False, sw_init=0x0015)
    assert rep_lu["retired_instructions"] == 4
    assert rep_lu["load_use_stalls"] == 1
    assert rep_lu["mem_forwards"] >= 1
    assert rep_lu["led_value"] == 0x002A
    assert rep_lu["cpi"] > 1.0

    # 2. Pure ALU->ALU EX->EX Forwarding (zero stalls)
    rv_fwd = assemble_riscv([
        "addi t0, zero, 10",
        "addi t1, t0, 20",
        "add t2, t1, t0",
    ])
    rep_fwd = analyze_pipeline_hazards(rv_fwd, is_mips=False)
    assert rep_fwd["load_use_stalls"] == 0
    assert rep_fwd["ex_forwards"] >= 2

    # 3. Taken Branch Flush (RV32) vs Branch Delay Slot (MIPS)
    rv_br = assemble_riscv([
        "addi t0, zero, 2",
        "loop:",
        "addi t0, t0, -1",
        "bne t0, zero, loop",
        "addi t1, zero, 99",
    ])
    rep_br = analyze_pipeline_hazards(rv_br, is_mips=False)
    assert rep_br["branch_flushes"] >= 2

    mips_br = assemble_mips([
        "addiu $t0, $zero, 1",
        "beq $t0, $t0, done",
        "addiu $t1, $zero, 77",
        "addiu $t1, $zero, 999",
        "done:",
        "addiu $t2, $t1, 1",
    ])
    rep_mips = analyze_pipeline_hazards(mips_br, is_mips=True)
    assert rep_mips["delay_slots"] == 1
    assert rep_mips["final_regs"][9] == 77   # $t1 set in delay slot
    assert rep_mips["final_regs"][10] == 78  # $t2 = 77 + 1


def test_rtl_testbench_export_and_cosim_runner(tmp_path):
    ins = assemble_mips([
        "lui $t0, 0xF000",
        "lw $t1, 4($t0)",
        "sw $t1, 0($t0)",
    ])
    tb_dir = str(tmp_path / "tb_out")
    pkg = export_rtl_testbench(tb_dir, ins, arch="mips", cpu_hdl_path=OPENMIPS_V, sw_init=0xABCD)
    assert os.path.isfile(pkg["tb_v"])
    assert os.path.isfile(pkg["program_hex"])
    assert os.path.isfile(pkg["bat_script"])
    assert os.path.isfile(pkg["xsim_tcl"])
    with open(pkg["tb_v"], "r", encoding="utf-8") as f:
        tb_txt = f.read()
    assert '$dumpfile("waveform.vcd")' in tb_txt
    assert "openmips u_dut" in tb_txt

    cosim = run_rtl_cosim(ins, arch="mips", cpu_hdl_path=OPENMIPS_V, sw_init=0x1234)
    assert cosim["golden_led"] == 0x1234
    assert "pipeline" in cosim


def test_mips_mmio_description_tracking_and_openmips_div_and_uart_dmem(tmp_path):
    ins = assemble_mips([
        "lui $sp, 0x8001",
        "lui $a2, 0xF000",
        "addi $a3, $a2, 4",
        "addi $t4, $a2, 8",
        "lw $t5, 0($a3)",
        "sw $t5, 0($t4)",
        "sw $t5, 0($a2)",
    ])
    assert "Stack Pointer" in ins[0]["desc"]
    assert "Base Address I/O" in ins[1]["desc"]
    assert "SWITCH (0xF0000004" in ins[4]["desc"]
    assert "SEG7 (0xF0000008" in ins[5]["desc"]
    assert "LED (0xF0000000" in ins[6]["desc"]

    # Verify OpenMIPS EXE_DIV / EXE_DIVU and latch-free HILO in ex.v
    ex_v = os.path.join(ROOT_DIR, "custom_cpus", "openmips", "ex.v")
    with open(ex_v, "r", encoding="utf-8") as f:
        ex_txt = f.read()
    assert "`EXE_DIV_OP" in ex_txt
    assert "`EXE_DIVU_OP" in ex_txt
    assert "{HI, LO} <= {hi_i, lo_i};" in ex_txt

    # Verify uart_prog_loader.v supports both "PROG" and "DMEM" live packets
    soc_out = str(tmp_path / "soc_dmem_check")
    pkg = export_vivado_soc_package(soc_out, ins, arch="mips", cpu_hdl_path=OPENMIPS_V)
    with open(pkg["loader_v"], "r", encoding="utf-8") as f:
        loader_txt = f.read()
    assert "prog_dmem_we_o" in loader_txt
    assert "is_dmem" in loader_txt


def test_real_iverilog_cosim_gtkwave_and_real_mips_gcc():
    from core.gcc_toolchain import compile_with_real_mips_gcc, find_mips_gcc_bin
    from core.rtl_cosim import detect_verilog_simulator, find_gtkwave_bin

    # 1. Real MIPS GCC compilation check
    assert find_mips_gcc_bin() is not None
    c_mips = r"""
    int main() {
        volatile int *led = (volatile int*)0xF0000000;
        *led = 0x55AA;
        return 0;
    }
    """
    asm_lines, ins = compile_with_real_mips_gcc(c_mips)
    assert len(ins) >= 5
    assert any("0xF000" in i["asm"] or "0xF0000000" in i["desc"] for i in ins)

    # 2. Real Icarus Verilog and GTKWave detection
    sim_tool = detect_verilog_simulator()
    assert sim_tool is not None
    assert sim_tool["kind"] == "iverilog"
    assert os.path.isfile(sim_tool["iverilog"])
    assert os.path.isfile(sim_tool["vvp"])

    gtkwave = find_gtkwave_bin()
    assert gtkwave is not None
    assert os.path.isfile(gtkwave)

    # 3. Real RTL execution with iverilog + vvp
    cosim = run_rtl_cosim(ins, arch="mips", cpu_hdl_path=OPENMIPS_V, sw_init=0x55AA)
    assert cosim["ran_rtl"] is True
    assert cosim["passed"] is True
    assert cosim["simulator"].startswith("Icarus Verilog")


def test_riscv_5stage_rtl_pipeline_sra_and_selfchecking_tb(tmp_path):
    """Verify 5-Stage Pipelined RISC-V RTL, SRA/SRAI sign-extension, honest RTL_PERF counters, VCD timeline, iterative divider, and custom CPU port binding."""
    from core.gcc_toolchain import compile_with_real_riscv_gcc
    from core.hdl_analyzer import inspect_cpu_hardware_ports

    # 1. Verify HDL analyzer detects 5-Stage Pipelined RTL for riscv_rv32i.v and ignores comments on single-cycle RTL
    caps = inspect_cpu_hardware_ports(RISCV_V)
    assert caps["is_pipelined"] is True
    assert caps["has_forwarding"] is True
    assert caps["has_stall_ctrl"] is True
    assert "5-Stage Pipelined RTL" in caps["rtl_topology"]

    sc_v = tmp_path / "single_cycle_comment_test.v"
    sc_v.write_text(
        "// Comment mentioning if_id, id_ex, ex_mem, mem_wb, stall, forward\n"
        "module sc_cpu(input wire clk, input wire rst, output wire [31:0] rom_addr_o, input wire [31:0] rom_data_i,\n"
        "              output wire [31:0] ram_addr_o, output wire [31:0] ram_data_o, input wire [31:0] ram_data_i, output wire ram_we_o);\n"
        "endmodule\n",
        encoding="utf-8",
    )
    sc_caps = inspect_cpu_hardware_ports(str(sc_v))
    assert sc_caps["is_pipelined"] is False

    # 2. Verify 1_switch_to_led.c runs on 5-Stage RTL and matches Golden ISA + Dynamic Switch Phase 2 + VCD timeline
    c_sw_led = """
    #define LED_ADDR  (*(volatile unsigned int *)0xF0000000)
    #define SW_ADDR   (*(volatile unsigned int *)0xF0000004)
    #define SEG7_ADDR (*(volatile unsigned int *)0xF0000008)
    void main() {
        while (1) {
            unsigned int sw = SW_ADDR;
            unsigned int out = sw + 1;
            LED_ADDR  = out;
            SEG7_ADDR = out;
        }
    }
    """
    _, ins_sw = compile_with_real_riscv_gcc(c_sw_led)
    cosim_sw = run_rtl_cosim(ins_sw, arch="riscv", cpu_hdl_path=RISCV_V, sim_cycles=500, sw_init=0x0000)
    assert cosim_sw["ran_rtl"] is True
    assert cosim_sw["passed"] is True
    assert cosim_sw["rtl_led"] == 0x0001
    assert cosim_sw["rtl_seg7"] == 0x00000001
    assert cosim_sw["pipeline"].get("measured_from_rtl") is True
    assert cosim_sw["pipeline"].get("source") == "rtl"
    assert cosim_sw["pipeline"].get("timeline_source") == "rtl"
    assert cosim_sw["pipeline"]["total_cycles"] == 702
    assert cosim_sw["pipeline"]["retired_instructions"] == 500
    assert cosim_sw["pipeline"]["load_use_stalls"] == 100
    assert cosim_sw["projection"]["total_cycles"] == 703
    assert "PASS:" in cosim_sw["rtl_log"]
    assert "Dynamic SW=0x00A5 → LED=0x00A6 (PASS)" in cosim_sw["message"]

    # 3. Verify SRA / SRAI arithmetic shift right AND iterative 32-cycle DIV/REM on negative values in real Verilog RTL
    c_sra_div = """
    #define LED_ADDR  (*(volatile unsigned int *)0xF0000000)
    #define SEG7_ADDR (*(volatile unsigned int *)0xF0000008)
    void main() {
        volatile int neg_val = -16;
        volatile int sh = 2;
        volatile int d = 3;
        int r_sra = neg_val >> sh;      // -4 (0xFFFFFFFC)
        int r_div = neg_val / d;        // -5
        int r_rem = neg_val % d;        // -1
        SEG7_ADDR = (unsigned int)r_sra;
        LED_ADDR  = (unsigned int)((r_div * 10 + r_rem) & 0xFFFF); // -51 = 0xFFCD
        while (1) {}
    }
    """
    _, ins_sra = compile_with_real_riscv_gcc(c_sra_div)
    cosim_sra = run_rtl_cosim(ins_sra, arch="riscv", cpu_hdl_path=RISCV_V, sw_init=0)
    assert cosim_sra["ran_rtl"] is True
    assert cosim_sra["passed"] is True
    assert cosim_sra["rtl_seg7"] == 0xFFFFFFFC
    assert cosim_sra["rtl_led"] == 0xFFCD
    assert cosim_sra["rtl_perf"]["div_stalls"] >= 60

    # 4. Verify custom user-uploaded CPU with non-standard port names & active-low reset works via cpu_port_binding
    custom_dir = tmp_path / "user_custom_cpu"
    custom_dir.mkdir()
    custom_v = custom_dir / "my_rv_core.v"
    with open(RISCV_V, "r", encoding="utf-8") as f:
        rv_src = f.read()
    custom_wrapper = (
        rv_src
        + "\nmodule my_rv_core(\n"
        + "    input  wire        i_clk,\n"
        + "    input  wire        i_rst_n,\n"
        + "    output wire [31:0] imem_addr,\n"
        + "    input  wire [31:0] imem_rdata,\n"
        + "    output wire [31:0] dmem_addr,\n"
        + "    output wire [31:0] dmem_wdata,\n"
        + "    input  wire [31:0] dmem_rdata,\n"
        + "    output wire        dmem_we\n"
        + ");\n"
        + "    riscv_rv32i u_inner(\n"
        + "        .clk(i_clk), .rst(~i_rst_n),\n"
        + "        .rom_addr_o(imem_addr), .rom_data_i(imem_rdata), .rom_ce_o(),\n"
        + "        .ram_addr_o(dmem_addr), .ram_data_o(dmem_wdata), .ram_data_i(dmem_rdata),\n"
        + "        .ram_we_o(dmem_we), .ram_ce_o(), .ram_sel_o()\n"
        + "    );\n"
        + "endmodule\n"
    )
    # Put my_rv_core first so extract_cpu_ports sees it as the top module
    custom_v.write_text(
        custom_wrapper.split("module my_rv_core")[1].join(["module my_rv_core", ""]) + "\n" + rv_src,
        encoding="utf-8",
    )
    cosim_cust = run_rtl_cosim(ins_sw, arch="riscv", cpu_hdl_path=str(custom_v), sim_cycles=120, sw_init=0x0010)
    assert cosim_cust["ran_rtl"] is True
    assert cosim_cust["passed"] is True
    assert cosim_cust["rtl_led"] == 0x0011
    assert cosim_cust["binding"]["module"] == "my_rv_core"
    assert cosim_cust["binding"]["rst_active_low"] is True





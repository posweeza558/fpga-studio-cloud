# -*- coding: utf-8 -*-
"""
Automated Tests for Stage 2 & Stage 3:
- HDL Macro Resolution (`define RegBus 31:0) & ANSI Port Direction/Width Accuracy
- HDL Analyzer Caching
- Unified MMIO Address Mapping (individual & legacy keys)
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.hdl_analyzer import extract_cpu_ports, inspect_cpu_hardware_ports, invalidate_hdl_cache
from core.simulator_engine import CPUSimulatorEngine


def test_openmips_macro_resolution_and_port_directions():
    invalidate_hdl_cache()
    openmips_v = os.path.join(ROOT, "custom_cpus", "openmips", "openmips.v")
    assert os.path.exists(openmips_v)

    info = extract_cpu_ports(openmips_v)
    by_name = {p["name"]: p for p in info["detailed_ports"]}

    # Previously failed: all ports got dir='input' and width='1' due to `RegBus and tight wire[`RegBus]
    assert by_name["clk"] == {"name": "clk", "dir": "input", "width": "1"}
    assert by_name["rst"] == {"name": "rst", "dir": "input", "width": "1"}
    assert by_name["rom_data_i"] == {"name": "rom_data_i", "dir": "input", "width": "31:0"}
    assert by_name["rom_addr_o"] == {"name": "rom_addr_o", "dir": "output", "width": "31:0"}
    assert by_name["ram_data_i"] == {"name": "ram_data_i", "dir": "input", "width": "31:0"}
    assert by_name["ram_addr_o"] == {"name": "ram_addr_o", "dir": "output", "width": "31:0"}
    assert by_name["ram_data_o"] == {"name": "ram_data_o", "dir": "output", "width": "31:0"}
    assert by_name["ram_we_o"] == {"name": "ram_we_o", "dir": "output", "width": "1"}
    assert by_name["ram_sel_o"] == {"name": "ram_sel_o", "dir": "output", "width": "3:0"}

    roles = info["detected_roles"]
    assert roles["mem_addr"] == "ram_addr_o"
    assert roles["mem_wdata"] == "ram_data_o"
    assert roles["mem_rdata"] == "ram_data_i"
    assert roles["mem_we"] == "ram_we_o"


def test_hdl_analyzer_caching():
    invalidate_hdl_cache()
    openmips_v = os.path.join(ROOT, "custom_cpus", "openmips", "openmips.v")
    first = inspect_cpu_hardware_ports(openmips_v)
    assert first["has_bus"] is True
    assert first["has_hilo"] is True

    t0 = time.perf_counter()
    for _ in range(200):
        res = inspect_cpu_hardware_ports(openmips_v)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert res["has_bus"] is True
    assert dt_ms < 80.0, f"Cached inspection too slow: {dt_ms:.2f} ms"


def test_unified_mmio_mapping_in_simulator():
    sim = CPUSimulatorEngine()
    sim.set_mmio_map({
        "led": "0xE0000000",
        "sw": "0xE0000004",
        "seg7": "0xE0000008",
        "btn": "0xE000000C",
        "uart_tx": "0xE0000010",
        "uart_stat": "0xE0000014",
        "rgb": "0xE0000018",
        "vga": "0xEE000000",
    })
    assert sim.mmio_led == 0xE0000000
    assert sim.mmio_sw == 0xE0000004
    assert sim.mmio_seg7 == 0xE0000008
    assert sim.mmio_btn == 0xE000000C
    assert sim.mmio_uart == 0xE0000010
    assert sim.mmio_uart_stat == 0xE0000014
    assert sim.mmio_rgb == 0xE0000018
    assert sim.mmio_vga == 0xEE000000

    sim.reset_mmio_map()
    assert sim.mmio_led == 0xF0000000
    assert sim.mmio_seg7 == 0xF0000008
    assert sim.mmio_vga == 0xFF000000

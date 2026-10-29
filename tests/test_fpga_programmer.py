# -*- coding: utf-8 -*-
"""
Tests for Direct In-App FPGA Hardware Bitstream Programmer (core/fpga_programmer.py)
"""

import os
import tempfile
import pytest

from core.fpga_programmer import (
    detect_all_fpga_programmers,
    generate_vivado_program_tcl,
    find_vivado_binary,
    find_djtgcfg_binary,
    find_openfpgaloader_binary,
)


def test_fpga_programmer_detection_and_tcl_generation():
    # 1. Detection scanner should run cleanly without exceptions
    tools = detect_all_fpga_programmers()
    assert isinstance(tools, dict)
    assert "vivado" in tools
    assert "djtgcfg" in tools
    assert "openfpgaloader" in tools

    # 2. Test Tcl generation for Vivado Hardware Manager
    fake_bit = r"C:\workspace\top_openmips.bit"
    tcl = generate_vivado_program_tcl(fake_bit, device_hint="xc7a100t")
    assert "open_hw_manager" in tcl
    assert "connect_hw_server" in tcl
    assert "set bitfile \"C:/workspace/top_openmips.bit\"" in tcl
    assert "program_hw_devices" in tcl
    assert "FPGA_STUDIO_FLASH_SUCCESS" in tcl


def test_openfpgaloader_detection_and_board_mapping():
    from core.fpga_programmer import map_board_to_openfpgaloader_target, find_openfpgaloader_binary

    # 1. Board mappings
    assert map_board_to_openfpgaloader_target("Digilent Nexys A7-100T (Artix-7)") == "nexys_a7_100"
    assert map_board_to_openfpgaloader_target("Digilent Nexys A7-50T (Artix-7)") == "nexys_a7_50"
    assert map_board_to_openfpgaloader_target("Digilent Basys 3 (Artix-7)") == "basys3"

    # 2. Bundled toolchain detection
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    toolchain_dir = os.path.join(app_root, "toolchain")
    loader_bin = find_openfpgaloader_binary(toolchain_dir)
    assert loader_bin is not None
    assert os.path.isfile(loader_bin)
    assert loader_bin.endswith("openFPGALoader.exe")

    # 3. Pre-bundled bitstreams exist and are non-empty
    mips_bit = os.path.join(app_root, "bitstreams", "nexys_a7_openmips.bit")
    riscv_bit = os.path.join(app_root, "bitstreams", "nexys_a7_riscv.bit")
    demo_bit = os.path.join(app_root, "bitstreams", "nexys_a7_factory_demo.bit")
    gpio_bit = os.path.join(app_root, "bitstreams", "nexys_a7_gpio_demo.bit")
    assert os.path.isfile(mips_bit)
    assert os.path.getsize(mips_bit) > 1000000
    assert os.path.isfile(riscv_bit)
    assert os.path.getsize(riscv_bit) > 1000000
    assert os.path.isfile(demo_bit)
    assert os.path.getsize(demo_bit) > 1000000
    assert os.path.isfile(gpio_bit)
    assert os.path.getsize(gpio_bit) > 1000000


def test_open_synthesizer_detection_and_soc_export():
    from core.open_synthesizer import detect_synthesis_engines, synthesize_soc_bitstream

    # 1. Detection scanner
    engines = detect_synthesis_engines()
    assert isinstance(engines, dict)
    assert "yosys" in engines
    assert "nextpnr" in engines
    assert "vivado" in engines

    # 2. Automated SoC wrapper generation (MIPS)
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok, msg, out_bit = synthesize_soc_bitstream(app_root, "test_cpu", "mips", None)
    assert ok is True
    out_dir = os.path.join(app_root, "build_soc_test_cpu")
    assert os.path.isdir(out_dir)
    assert os.path.isfile(os.path.join(out_dir, "nexys_a7_soc_top.v"))
    assert os.path.isfile(os.path.join(out_dir, "uart_prog_loader.v"))
    assert os.path.isfile(os.path.join(out_dir, "Nexys-A7-100T-Master.xdc"))
    assert os.path.isfile(os.path.join(out_dir, "build_vivado_project.tcl"))

    # 3. Test OSS CAD Suite installer function signature
    from core.open_synthesizer import install_oss_cad_suite
    assert callable(install_oss_cad_suite)

    # 4. Test Cloud Synthesis Module & Workflow template
    from core.cloud_synthesis import (
        prepare_cloud_synthesis_package,
        download_synthesized_bitstream_from_url,
        trigger_cloud_synthesis_workflow,
        export_cloud_bundle_zip,
    )
    assert callable(prepare_cloud_synthesis_package)
    assert callable(download_synthesized_bitstream_from_url)
    assert callable(trigger_cloud_synthesis_workflow)
    assert callable(export_cloud_bundle_zip)

    workflow_path = os.path.join(app_root, ".github", "workflows", "fpga_studio_synthesis.yml")
    assert os.path.isfile(workflow_path)

    # Test creating Cloud Bundle Zip
    z_ok, z_msg, z_path = export_cloud_bundle_zip(app_root, "test_cloud_cpu", "mips")
    assert z_ok is True
    assert z_path and os.path.isfile(z_path)
    if os.path.isfile(z_path):
        os.remove(z_path)

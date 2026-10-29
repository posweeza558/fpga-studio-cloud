# -*- coding: utf-8 -*-
"""
HDL Port & Hardware Interface Analyzer for FPGA Studio:
Inspects Verilog (.v, .sv) and VHDL (.vhd, .vhdl) CPU modules to determine
their actual physical hardware capabilities (Memory Bus, GPIO, UART, VGA, ALU-only).
Supports multi-dialect parsing (Verilog-95, Verilog-2001 ANSI, SystemVerilog, VHDL),
Verilog `define macro resolution (e.g., define.v), mtime caching, and cpu_manifest.json.
"""

import copy
import json
import os
import re


ROLE_PATTERNS = {
    "clock": r"^(clk|clock|sys_clk|clk_i|aclk|wb_clk_i|clk_100m|clk_50m)$",
    "reset": r"^(rst|reset|rst_n|reset_n|nrst|aresetn|reset_b|clr|rst_i|wb_rst_i)$",
    "mem_addr": r"(mem_addr|data_addr|d_addr|wb_adr|bus_addr|m_addr|addr_out|o_addr|address|dmem_addr|ram_addr|mar|m_axi_awaddr|m_axi_araddr|target_addr)",
    "mem_wdata": r"(mem_wdata|data_out|d_dout|wb_dat_o|bus_wdata|ram_data_o|m_axi_wdata|mdr|data_o|dout|dmem_wdata|wdata)",
    "mem_rdata": r"(mem_rdata|data_in|d_din|wb_dat_i|bus_rdata|ram_data_i|m_axi_rdata|data_i|din|dmem_rdata|rdata)",
    "mem_we": r"(mem_we|data_we|wb_we|d_we|memwrite|wr_en|write_en|we|we_o|m_axi_wvalid|dmem_we|ram_we|mem_write)",
    "direct_led": r"^(led|leds|direct_leds|o_led|led_out)",
    "direct_sw": r"^(sw|switch|switches|i_sw|sw_in)",
    "direct_btn": r"^(btn|button|buttons|btn_in)",
    "direct_seg": r"^(seg|seven_seg|seg7|sseg|anode|cathode|an)",
    "direct_uart": r"(uart_tx|uart_rx|txd|rxd|serial_tx|serial_rx|uart)",
    "direct_vga": r"(vga_r|vga_g|vga_b|hsync|vsync|vga)"
}

_PORT_CACHE = {}
_INSPECT_CACHE = {}


def invalidate_hdl_cache(file_path=None):
    """Clear cached HDL port/capability inspection results."""
    if file_path is None:
        _PORT_CACHE.clear()
        _INSPECT_CACHE.clear()
        return
    abs_p = os.path.abspath(file_path)
    _PORT_CACHE.pop(abs_p, None)
    _INSPECT_CACHE.pop(abs_p, None)


def _strip_hdl_comments(text, is_vhdl=False):
    if is_vhdl:
        return re.sub(r"--.*", "", text)
    out = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    out = re.sub(r"//.*", "", out)
    return out


def _collect_verilog_macros(file_path, clean_content):
    """Collect `define macros from included headers (e.g. define.v) and the target file."""
    macros = {}
    pkg_dir = os.path.dirname(os.path.abspath(file_path))
    header_files = []

    # 1. Explicit `include "..." directives
    for inc in re.findall(r'`include\s+"([^"]+)"', clean_content):
        cand = os.path.join(pkg_dir, os.path.basename(inc))
        if os.path.isfile(cand) and cand not in header_files:
            header_files.append(cand)

    # 2. Common macro definition files in same folder (define.v, defines.v, *.vh)
    if os.path.isdir(pkg_dir):
        for fn in sorted(os.listdir(pkg_dir)):
            low = fn.lower()
            if low in ("define.v", "defines.v", "params.v") or low.endswith((".vh", ".svh")):
                cand = os.path.join(pkg_dir, fn)
                if os.path.isfile(cand) and cand not in header_files:
                    header_files.append(cand)

    header_mtimes = []
    for hf in header_files:
        try:
            header_mtimes.append((hf, os.path.getmtime(hf)))
            with open(hf, "r", encoding="utf-8", errors="ignore") as f:
                htxt = _strip_hdl_comments(f.read(), is_vhdl=False)
            for m_name, m_val in re.findall(r"`define\s+(\w+)\s+([^\r\n]+)", htxt):
                macros[m_name] = m_val.strip()
        except Exception:
            pass

    for m_name, m_val in re.findall(r"`define\s+(\w+)\s+([^\r\n]+)", clean_content):
        macros[m_name] = m_val.strip()

    return macros, tuple(header_mtimes)


def _resolve_macro_expr(expr, macros):
    if not expr:
        return "1"
    resolved = expr.strip()
    for _ in range(4):
        if "`" not in resolved:
            break
        prev = resolved
        resolved = re.sub(r"`(\w+)", lambda m: macros.get(m.group(1), m.group(0)), resolved)
        if resolved == prev:
            break
    return resolved.strip()


def extract_cpu_ports(file_path):
    """
    Detailed Port Extractor:
    Scans a Verilog/VHDL file and extracts every top-level port with accurate
    direction, resolved bit-width (including `define macros), and architectural roles.
    """
    if not file_path or not os.path.exists(file_path):
        return {"ports": [], "detailed_ports": [], "detected_roles": {}}

    abs_path = os.path.abspath(file_path)
    try:
        file_mtime = os.path.getmtime(abs_path)
    except Exception:
        return {"ports": [], "detailed_ports": [], "detected_roles": {}}

    ext = os.path.splitext(abs_path)[1].lower()
    is_vhdl = ext in (".vhd", ".vhdl")

    cached = _PORT_CACHE.get(abs_path)
    if cached:
        c_mtime, c_inc_mtimes, c_result = cached
        if c_mtime == file_mtime:
            inc_ok = True
            for hf, hm in c_inc_mtimes:
                try:
                    if os.path.getmtime(hf) != hm:
                        inc_ok = False
                        break
                except Exception:
                    inc_ok = False
                    break
            if inc_ok:
                return copy.deepcopy(c_result)

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return {"ports": [], "detailed_ports": [], "detected_roles": {}}

    clean = _strip_hdl_comments(content, is_vhdl=is_vhdl)
    macros, inc_mtimes = ({}, ()) if is_vhdl else _collect_verilog_macros(abs_path, clean)

    detailed_ports = []
    seen = set()
    top_module = os.path.splitext(os.path.basename(abs_path))[0]

    if not is_vhdl:
        # Isolate the first module declaration (header + body) so submodules don't pollute top ports
        m_mod = re.search(
            r"\bmodule\s+(\w+)\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;(.*?)\bendmodule\b",
            clean,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m_mod:
            top_module = m_mod.group(1)
        header_text = m_mod.group(2) if m_mod else clean
        body_text = m_mod.group(3) if m_mod else clean

        # 1. Verilog-2001 / SystemVerilog ANSI port declarations in module header
        # Supports tight spacing like `input wire[`RegBus] rom_data_i`
        v2k_pat = re.compile(
            r"\b(input|output|inout)\b\s*"
            r"(?:(?:wire|reg|logic)\b\s*)?"
            r"(?:signed\b\s*)?"
            r"(?:\[\s*([^\]]+?)\s*\]\s*)?"
            r"([A-Za-z_]\w*)",
            re.IGNORECASE,
        )
        ansi_matches = v2k_pat.findall(header_text)
        if ansi_matches:
            # Handle multi-name ANSI declarations if any, while keeping exact per-port direction/width
            # Split header byport direction keywords
            segments = re.split(r"(?=\b(?:input|output|inout)\b)", header_text, flags=re.IGNORECASE)
            for seg in segments:
                seg_s = seg.strip().rstrip(",").strip()
                if not seg_s:
                    continue
                m_seg = re.match(
                    r"^(input|output|inout)\b\s*"
                    r"(?:(?:wire|reg|logic)\b\s*)?"
                    r"(?:signed\b\s*)?"
                    r"(?:\[\s*([^\]]+?)\s*\]\s*)?"
                    r"(.+)$",
                    seg_s,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if not m_seg:
                    continue
                pdir = m_seg.group(1).lower()
                pwidth = _resolve_macro_expr(m_seg.group(2), macros) if m_seg.group(2) else "1"
                names_part = m_seg.group(3)
                for item in names_part.split(","):
                    tok = re.sub(r"=\s*[^,]+", "", item)
                    tok = re.sub(r"\[[^\]]+\]", "", tok).strip()
                    if re.match(r"^[A-Za-z_]\w*$", tok):
                        pname_l = tok.lower()
                        if pname_l not in ("wire", "reg", "logic", "signed", "parameter", "input", "output", "inout") and pname_l not in seen:
                            seen.add(pname_l)
                            detailed_ports.append({
                                "name": pname_l,
                                "dir": pdir,
                                "width": pwidth,
                            })

        # 2. Verilog-95 style body port declarations (input a, b; output [31:0] c;)
        if not detailed_ports:
            v95 = re.findall(
                r"\b(input|output|inout)\b\s*"
                r"(?:(?:wire|reg|logic)\b\s*)?"
                r"(?:signed\b\s*)?"
                r"(?:\[\s*([^\]]+?)\s*\]\s*)?"
                r"([^;()]+);",
                body_text,
                re.IGNORECASE,
            )
            for pdir, pwidth_raw, pgroup in v95:
                pwidth = _resolve_macro_expr(pwidth_raw, macros) if pwidth_raw else "1"
                for item in pgroup.split(","):
                    clean_item = re.sub(r"\[[^\]]+\]", "", item).strip()
                    parts = clean_item.split()
                    if parts:
                        pname_l = parts[-1].lower()
                        if re.match(r"^[a-z_]\w*$", pname_l) and pname_l not in ("wire", "reg", "logic", "signed", "parameter") and pname_l not in seen:
                            seen.add(pname_l)
                            detailed_ports.append({
                                "name": pname_l,
                                "dir": pdir.lower(),
                                "width": pwidth,
                            })
    else:
        # 3. VHDL Entity Ports (isolated to first entity port(...) block if present)
        m_ent = re.search(
            r"\bentity\s+(\w+)\s+is\b(.*?)\bend\b",
            clean,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m_ent:
            top_module = m_ent.group(1)
        ent_text = m_ent.group(2) if m_ent else clean
        if re.search(r"\bport\s*\(", ent_text, flags=re.IGNORECASE):
            vhdl = re.findall(r"(\w+(?:\s*,\s*\w+)*)\s*:\s*(in|out|inout)\s+([^;]+)", ent_text, re.IGNORECASE)
            for pgroup, pdir, ptype in vhdl:
                w_str = ptype.strip().rstrip(")")
                for item in pgroup.split(","):
                    pname_l = item.strip().lower()
                    if pname_l and pname_l not in seen:
                        seen.add(pname_l)
                        detailed_ports.append({
                            "name": pname_l,
                            "dir": "input" if pdir.lower() == "in" else ("output" if pdir.lower() == "out" else "inout"),
                            "width": w_str,
                        })

    # Auto-detect architectural roles for each port with priority
    detected_roles = {}
    port_names = [p["name"] for p in detailed_ports]

    addr_candidates = [p for p in port_names if re.search(r"(ram_addr|data_addr|dmem_addr|d_addr|wb_adr)", p, re.I)]
    if not addr_candidates:
        addr_candidates = [p for p in port_names if re.search(r"(mem_addr|bus_addr|m_addr|addr_out|o_addr|address)", p, re.I) and not re.search(r"(rom|imem|instr|pc)", p, re.I)]
    if addr_candidates:
        detected_roles["mem_addr"] = addr_candidates[0]

    rdata_candidates = [p for p in port_names if re.search(r"(ram_data_i|ram_rdata|dmem_rdata|data_in|wb_dat_i|d_din)", p, re.I)]
    if not rdata_candidates:
        rdata_candidates = [p for p in port_names if re.search(r"(mem_rdata|bus_rdata|m_axi_rdata|data_i|din|rdata)", p, re.I) and not re.search(r"(rom|imem|instr)", p, re.I)]
    if rdata_candidates:
        detected_roles["mem_rdata"] = rdata_candidates[0]

    wdata_candidates = [p for p in port_names if re.search(r"(ram_data_o|ram_wdata|dmem_wdata|data_out|wb_dat_o|d_dout)", p, re.I)]
    if not wdata_candidates:
        wdata_candidates = [p for p in port_names if re.search(r"(mem_wdata|bus_wdata|m_axi_wdata|data_o|dout|wdata)", p, re.I)]
    if wdata_candidates:
        detected_roles["mem_wdata"] = wdata_candidates[0]

    for p in detailed_ports:
        name = p["name"]
        for role, pattern in ROLE_PATTERNS.items():
            if role not in detected_roles and re.search(pattern, name, re.IGNORECASE):
                detected_roles[role] = name

    result = {
        "top_module": top_module,
        "ports": [p["name"] for p in detailed_ports],
        "detailed_ports": detailed_ports,
        "detected_roles": detected_roles,
    }
    _PORT_CACHE[abs_path] = (file_mtime, inc_mtimes, copy.deepcopy(result))
    return result


def inspect_cpu_hardware_ports(file_path):
    """
    Real HDL Port & Bus Analyzer (with mtime caching):
    Scans the Verilog / VHDL top-level entity / module ports to determine
    actual physical hardware capabilities of the CPU core.
    """
    if not file_path or not os.path.exists(file_path):
        return {
            "has_bus": True,
            "has_gpio": True,
            "has_uart": True,
            "has_vga": True,
            "is_standalone_alu": False,
            "ports_found": [],
            "summary_th": "แกนประมวลผลมาตรฐาน (รองรับบอร์ดจำลองสมบูรณ์)",
            "details": []
        }

    abs_path = os.path.abspath(file_path)
    pkg_dir = os.path.dirname(abs_path)

    custom_manifest_path = os.path.join(pkg_dir, "cpu_manifest.json")
    if not os.path.exists(custom_manifest_path):
        custom_manifest_path = os.path.join(pkg_dir, "manifest.json")

    try:
        file_mtime = os.path.getmtime(abs_path)
        manifest_mtime = os.path.getmtime(custom_manifest_path) if os.path.exists(custom_manifest_path) else None
    except Exception:
        file_mtime, manifest_mtime = None, None

    cached = _INSPECT_CACHE.get(abs_path)
    if cached and file_mtime is not None:
        c_fmtime, c_mmtime, c_res = cached
        if c_fmtime == file_mtime and c_mmtime == manifest_mtime:
            return copy.deepcopy(c_res)

    custom_mapping = {}
    explicit_is_alu = None
    if os.path.exists(custom_manifest_path):
        try:
            with open(custom_manifest_path, "r", encoding="utf-8") as jf:
                manifest_data = json.load(jf)
                custom_mapping = manifest_data.get("port_mapping", {})
                if "is_standalone_alu" in manifest_data:
                    explicit_is_alu = bool(manifest_data["is_standalone_alu"])
                elif "is_standalone_alu" in custom_mapping:
                    explicit_is_alu = bool(custom_mapping["is_standalone_alu"])
        except Exception:
            pass

    port_info = extract_cpu_ports(abs_path)
    ports = port_info["ports"]
    roles = port_info["detected_roles"]

    if len(ports) == 0 and not custom_mapping:
        res = {
            "has_bus": False,
            "has_gpio": False,
            "has_uart": False,
            "has_vga": False,
            "is_standalone_alu": False,
            "is_closed_testbench": True,
            "ports_found": [],
            "detailed_ports": [],
            "detected_roles": {},
            "summary_th": "Closed Simulation Model / Testbench (วงจรจำลองปิดภายใน — ไม่มีพอร์ต I/O ภายนอก)",
            "details": [
                "[-] ไม่พบการประกาศพอร์ตภายนอกที่ Top Entity",
                "[-] ไม่สามารถต่อกับขาบอร์ด Nexys A7 หรือ MMIO ได้จนกว่าจะเจาะพอร์ต Entity ภายนอก",
                "[+] ตรวจพบโครงสร้าง Datapath ภายในโมเดล"
            ]
        }
        if file_mtime is not None:
            _INSPECT_CACHE[abs_path] = (file_mtime, manifest_mtime, copy.deepcopy(res))
        return res

    if "mem_addr" in custom_mapping and custom_mapping["mem_addr"]:
        has_bus = True
    else:
        has_bus = any(
            re.search(r"(mem_addr|data_addr|d_addr|wb_adr|bus_addr|m_addr|addr_out|o_addr|address|dmem_addr|ram_addr|mar|m_axi_awaddr|m_axi_araddr|mem_we|data_we|wb_we|d_we|memwrite|memread|dmem|ram_data|ram_we)", p)
            for p in ports
        )

    has_gpio = (
        has_bus or
        bool(custom_mapping.get("led") or custom_mapping.get("sw") or custom_mapping.get("btn")) or
        any(re.search(r"^(led|leds|sw|switch|switches|seg|seg7|btn|button|rgb)", p) for p in ports)
    )
    has_uart = (
        has_bus or
        bool(custom_mapping.get("uart_tx") or custom_mapping.get("uart_rx")) or
        any(re.search(r"(uart|uart_tx|uart_rx|txd|rxd|serial_tx|serial_rx)", p) for p in ports)
    )
    has_vga = (
        has_bus or
        bool(custom_mapping.get("vga_rgb")) or
        any(re.search(r"(vga|hsync|vsync|vga_r|vga_g|vga_b)", p) for p in ports)
    )

    if explicit_is_alu is not None:
        is_standalone_alu = explicit_is_alu
        if is_standalone_alu:
            has_bus = False
            has_gpio = False
            has_uart = False
            has_vga = False
    else:
        is_standalone_alu = (not has_bus and not has_gpio and not has_uart and not has_vga)

    has_hilo = False
    is_pipelined = False
    has_forwarding = False
    has_stall_ctrl = False
    if os.path.isdir(pkg_dir):
        sibling_names = [fn.lower() for fn in os.listdir(pkg_dir) if fn.lower().endswith((".v", ".sv", ".vhd", ".vhdl"))]
        if any("hilo" in fn for fn in sibling_names):
            has_hilo = True
        if any(st in " ".join(sibling_names) for st in ("if_id", "id_ex", "ex_mem", "mem_wb")):
            is_pipelined = True
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_txt = f.read()
            is_vhdl_file = os.path.splitext(abs_path)[1].lower() in (".vhd", ".vhdl")
            txt = _strip_hdl_comments(raw_txt, is_vhdl=is_vhdl_file).lower()
            if re.search(r"\b(hilo_reg|hi_o|ex_whilo)\b", txt):
                has_hilo = True
            stage_hits = sum(1 for k in ("if_id", "id_ex", "ex_mem", "mem_wb") if re.search(rf"\b{k}\w*\b", txt))
            if stage_hits >= 2:
                is_pipelined = True
            if re.search(r"\b(ex_wreg\w*|mem_wreg\w*|fwd_a|fwd_b|forward\w*|bypass\w*)\b", txt):
                has_forwarding = True
            if re.search(r"\b(stall\w*|load_use_stall|hazard\w*|branch_flush)\b", txt):
                has_stall_ctrl = True
        except Exception:
            pass
    if is_standalone_alu:
        has_hilo = False
        rtl_topology = "Standalone ALU RTL (ไม่มี Memory Bus)"
    elif is_pipelined:
        rtl_topology = "5-Stage Pipelined RTL"
    else:
        rtl_topology = "Single-Cycle RTL (จำลอง 5-Stage Projection)"

    details = []
    if is_standalone_alu:
        summary_th = "Standalone Pure ALU Core (วงจรคำนวณ ALU เดี่ยว — ไม่มี Memory Bus และไม่มี I/O บอร์ด)"
        details.append("[-] ไม่พบ Memory Bus (ไม่มีชุด Load/Store สำหรับอ่าน/เขียน RAM)")
        details.append("[-] ไม่พบพอร์ต GPIO (ไม่มีขาต่อ Switch, LED, 7-Segment)")
        details.append("[-] ไม่พบโมดูล UART Serial (ไม่สามารถส่งข้อมูลทาง Serial Monitor ได้)")
        details.append("[-] ไม่พบโมดูล VGA Controller (ไม่สามารถแสดงภาพบนจอ VGA ได้)")
        details.append("[+] มีเฉพาะพอร์ตคำนวณ ALU (alu_out) และ Register File ภายใน")
    else:
        features = []
        if has_bus:
            features.append("Memory Bus (เชื่อมต่อ Nexys A7 MMIO Bridge)")
        if has_gpio:
            features.append("Direct GPIO Pins")
        if has_uart:
            features.append("UART Serial Controller")
        if has_vga:
            features.append("VGA Controller")
        summary_th = f"Full System Core ({', '.join(features)})"
        if has_bus:
            details.append("[+] ตรวจพบ Memory Bus Interface (พร้อมต่อสะพาน MMIO ของ Nexys A7)")
        if has_uart or has_bus:
            details.append("[+] รองรับ UART Serial Monitor (ผ่าน MMIO 0xF0000010 หรือ Pin)")
        if has_vga or has_bus:
            details.append("[+] รองรับ VGA Graphic Monitor (ผ่าน MMIO 0xFF000000 หรือ Pin)")
        if has_gpio or has_bus:
            details.append("[+] รองรับ LEDs, Switches, 7-Segment (ผ่าน MMIO 0xF0000000 หรือ Pin)")

    res = {
        "has_bus": has_bus,
        "has_gpio": has_gpio or has_bus,
        "has_uart": has_uart or has_bus,
        "has_vga": has_vga or has_bus,
        "has_hilo": has_hilo,
        "is_pipelined": is_pipelined,
        "has_forwarding": has_forwarding,
        "has_stall_ctrl": has_stall_ctrl,
        "rtl_topology": rtl_topology,
        "is_standalone_alu": is_standalone_alu,
        "ports_found": ports[:20],
        "detailed_ports": port_info["detailed_ports"],
        "detected_roles": roles,
        "summary_th": summary_th,
        "details": details
    }
    if file_mtime is not None:
        _INSPECT_CACHE[abs_path] = (file_mtime, manifest_mtime, copy.deepcopy(res))
    return res

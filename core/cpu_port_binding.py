# -*- coding: utf-8 -*-
"""
CPU Port Binding for user-uploaded CPU cores.

Resolves which top-level port of an uploaded CPU plays which bus role
(clock, reset, instruction ROM bus, data RAM/MMIO bus) so that both the
RTL co-simulation testbench and the Nexys A7 SoC top can instantiate ANY
CPU that exposes a Harvard-style memory interface — not only cores whose
ports are literally named `rom_addr_o`, `ram_data_i`, ...

Resolution priority per role:
  1. `cpu_manifest.json` / `manifest.json` -> "port_mapping" (explicit, user-provided)
  2. Exact FPGA Studio standard port names
  3. Pattern matching on port names + port direction
"""

import json
import os
import re

from core.hdl_analyzer import extract_cpu_ports

# role -> (direction required, standard name, regex patterns, manifest keys)
_ROLE_SPEC = {
    "clk":       ("input",  "clk",        [r"^(clk|clock|sys_clk|clk_i|i_clk|aclk|wb_clk_i)$"], ["clk", "clock"]),
    "rst":       ("input",  "rst",        [r"^(rst|reset|rst_i|i_rst|wb_rst_i|rst_n|reset_n|nrst|aresetn|reset_b|rstn|i_rst_n)$"], ["rst", "reset"]),
    "rom_addr":  ("output", "rom_addr_o", [r"(rom_addr|imem_addr|inst_addr|instr_addr|iaddr|i_addr|pc_o|pc_out|fetch_addr)"], ["rom_addr", "imem_addr", "inst_addr"]),
    "rom_data":  ("input",  "rom_data_i", [r"(rom_data|imem_data|imem_rdata|inst_data|instr_data|inst_i|instr_i|idata|i_data|instruction)"], ["rom_data", "imem_data", "inst_data"]),
    "rom_ce":    ("output", "rom_ce_o",   [r"(rom_ce|imem_ce|imem_en|inst_ce|inst_en|instr_req|imem_req)"], ["rom_ce", "imem_ce"]),
    "ram_addr":  ("output", "ram_addr_o", [r"(ram_addr|dmem_addr|data_addr|d_addr|mem_addr|bus_addr|wb_adr|addr_o$|address)"], ["mem_addr", "ram_addr", "dmem_addr"]),
    "ram_wdata": ("output", "ram_data_o", [r"(ram_data_o|ram_wdata|dmem_wdata|mem_wdata|data_out|wb_dat_o|d_dout|bus_wdata|wdata)"], ["mem_wdata", "ram_wdata", "dmem_wdata"]),
    "ram_rdata": ("input",  "ram_data_i", [r"(ram_data_i|ram_rdata|dmem_rdata|mem_rdata|data_in|wb_dat_i|d_din|bus_rdata|rdata)"], ["mem_rdata", "ram_rdata", "dmem_rdata"]),
    "ram_we":    ("output", "ram_we_o",   [r"(ram_we|dmem_we|mem_we|data_we|wb_we|d_we|memwrite|mem_write|wr_en|write_en|we_o$|^we$)"], ["mem_we", "ram_we", "dmem_we"]),
    "ram_ce":    ("output", "ram_ce_o",   [r"(ram_ce|dmem_ce|dmem_en|mem_ce|mem_en|mem_req|data_req|wb_stb|wb_cyc)"], ["mem_ce", "ram_ce", "dmem_ce"]),
    "ram_sel":   ("output", "ram_sel_o",  [r"(ram_sel|dmem_sel|mem_sel|byte_en|be_o|wb_sel|mem_be|dmem_be|wstrb|mem_mask)"], ["mem_sel", "ram_sel", "byte_en"]),
}

REQUIRED_ROLES = ("clk", "rst", "rom_addr", "rom_data", "ram_addr", "ram_wdata", "ram_rdata", "ram_we")
_ACTIVE_LOW_RST = re.compile(r"(_n$|^n|_b$|resetn$|rstn$)", re.IGNORECASE)


def _parse_width(width_str):
    """Return integer bit width for 'MSB:LSB' strings, or None if unresolvable."""
    if not width_str or width_str.strip() == "1":
        return 1
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", str(width_str))
    if m:
        return abs(int(m.group(1)) - int(m.group(2))) + 1
    return None


def _load_manifest_mapping(cpu_hdl_path):
    pkg_dir = os.path.dirname(os.path.abspath(cpu_hdl_path))
    for fn in ("cpu_manifest.json", "manifest.json"):
        p = os.path.join(pkg_dir, fn)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mp = data.get("port_mapping", {}) or {}
                return {str(k).lower(): str(v).lower() for k, v in mp.items() if isinstance(v, str) and v}
            except Exception:
                return {}
    return {}


def resolve_cpu_port_binding(cpu_hdl_path, arch="riscv"):
    """
    Resolve the bus-role -> port-name binding of a CPU top module.
    Returns dict: module, roles{role: {name, width}}, rst_active_low, missing[], ok, source.
    """
    default_mod = "openmips" if arch == "mips" else "riscv_rv32i"
    if not cpu_hdl_path or not os.path.exists(cpu_hdl_path):
        roles = {r: {"name": spec[1], "width": None} for r, spec in _ROLE_SPEC.items()}
        return {"module": default_mod, "roles": roles, "rst_active_low": False, "missing": [], "ok": True, "source": "builtin"}

    pinfo = extract_cpu_ports(cpu_hdl_path)
    ports = {p["name"]: p for p in pinfo.get("detailed_ports", [])}
    manifest = _load_manifest_mapping(cpu_hdl_path)
    used = set()
    roles = {}

    for role, (pdir, std_name, patterns, mkeys) in _ROLE_SPEC.items():
        chosen = None
        # 1. Explicit manifest mapping
        for mk in mkeys:
            cand = manifest.get(mk)
            if cand and cand in ports:
                chosen = cand
                break
        # 2. Standard FPGA Studio name
        if not chosen and std_name in ports and ports[std_name]["dir"] == pdir and std_name not in used:
            chosen = std_name
        # 3. Pattern + direction match
        if not chosen:
            for pat in patterns:
                for pname, p in ports.items():
                    if pname in used or p["dir"] != pdir:
                        continue
                    if role.startswith("ram") and re.search(r"(rom|imem|inst|instr|pc)", pname):
                        continue
                    if role.startswith("rom") and re.search(r"(ram|dmem)", pname):
                        continue
                    if re.search(pat, pname, re.IGNORECASE):
                        chosen = pname
                        break
                if chosen:
                    break
        if chosen:
            used.add(chosen)
            roles[role] = {"name": chosen, "width": _parse_width(ports[chosen]["width"])}

    missing = [r for r in REQUIRED_ROLES if r not in roles]
    rst_low = bool(roles.get("rst") and _ACTIVE_LOW_RST.search(roles["rst"]["name"]))
    return {
        "module": pinfo.get("top_module") or default_mod,
        "roles": roles,
        "rst_active_low": rst_low,
        "missing": missing,
        "ok": not missing,
        "source": "manifest+ports" if manifest else "ports",
    }


def render_cpu_instance(binding, inst_name, sig):
    """
    Render Verilog for instantiating the bound CPU.
    `sig` maps role -> parent signal name (32-bit buses, 4-bit sel, 1-bit controls).
    Missing optional roles are tied off (rom_ce/ram_ce -> 1, ram_sel -> 4'b1111).
    Narrower CPU buses are zero-extended / truncated through adapter wires.
    """
    pre, conns, post = [], [], []
    roles = binding["roles"]
    full_w = {"rom_addr": 32, "rom_data": 32, "ram_addr": 32, "ram_wdata": 32, "ram_rdata": 32, "ram_sel": 4}

    for role in ("clk", "rst", "rom_addr", "rom_data", "rom_ce", "ram_addr", "ram_wdata", "ram_rdata", "ram_we", "ram_ce", "ram_sel"):
        parent = sig[role]
        if role not in roles:
            if role in ("rom_ce", "ram_ce"):
                post.append(f"    assign {parent} = 1'b1; // CPU has no {role} port -> always enabled")
            elif role == "ram_sel":
                post.append(f"    assign {parent} = 4'b1111; // CPU has no byte-enable port -> full-word writes")
            continue
        pname = roles[role]["name"]
        w = roles[role]["width"]
        if role == "rst":
            conns.append(f"        .{pname} ({'~' if binding['rst_active_low'] else ''}{parent})")
            continue
        fw = full_w.get(role)
        if fw is None or w is None or w == fw:
            conns.append(f"        .{pname} ({parent})")
            continue
        adapter = f"{inst_name}_{role}_w"
        if _ROLE_SPEC[role][0] == "output":
            pre.append(f"    wire [{w - 1}:0] {adapter};")
            conns.append(f"        .{pname} ({adapter})")
            if w < fw:
                post.append(f"    assign {parent} = {{{{{fw - w}{{1'b0}}}}, {adapter}}};")
            else:
                post.append(f"    assign {parent} = {adapter}[{fw - 1}:0];")
        else:
            if w < fw:
                conns.append(f"        .{pname} ({parent}[{w - 1}:0])")
            else:
                pre.append(f"    wire [{w - 1}:0] {adapter} = {{{{{w - fw}{{1'b0}}}}, {parent}}};")
                conns.append(f"        .{pname} ({adapter})")

    body = "\n".join(pre + [f"    {binding['module']} {inst_name} (", ",\n".join(conns), "    );"] + post)
    return body


def describe_binding_th(binding):
    """Short Thai description of the binding for UI messages."""
    if not binding["ok"]:
        return "ไม่พบพอร์ตที่จำเป็น: " + ", ".join(binding["missing"]) + " (กำหนดเองได้ใน cpu_manifest.json → port_mapping)"
    pairs = [f"{r}={v['name']}" for r, v in binding["roles"].items()]
    return f"โมดูล {binding['module']}: " + ", ".join(pairs)

# -*- coding: utf-8 -*-
"""
FPGA Studio — WSL (Windows Subsystem for Linux) Synthesis Engine
Enables local, 100% offline hardware synthesis for Digilent Nexys A7 (Artix-7)
using Linux tools (Yosys, nextpnr-xilinx, openXC7) directly on the user's PC without Vivado 50GB.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


def _decode_wsl_output(raw_bytes: bytes) -> str:
    """Decode WSL command output handling UTF-16LE or UTF-8."""
    if not raw_bytes:
        return ""
    try:
        return raw_bytes.decode("utf-16le").strip()
    except Exception:
        pass
    try:
        return raw_bytes.decode("utf-8", errors="ignore").strip()
    except Exception:
        return raw_bytes.decode("cp1252", errors="ignore").strip()


def check_wsl_status() -> Dict[str, Any]:
    """
    Check if WSL is installed on this Windows PC, and list available distributions.
    Returns:
        {
            "installed": bool,
            "distros": List[str],
            "default_distro": Optional[str],
            "has_tools": bool,
            "tools": Dict[str, bool],
            "message": str,
        }
    """
    wsl_exe = shutil.which("wsl.exe") or os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wsl.exe")
    if not os.path.isfile(wsl_exe):
        return {
            "installed": False,
            "distros": [],
            "default_distro": None,
            "has_tools": False,
            "tools": {},
            "message": "ไม่พบโปรแกรม wsl.exe ใน Windows (ระบบนี้ไม่รองรับ WSL)",
        }

    try:
        res = subprocess.run(["wsl.exe", "-l", "-v"], capture_output=True, timeout=8)
        out_text = _decode_wsl_output(res.stdout or res.stderr)
        
        # Check if WSL is not installed
        if "not installed" in out_text.lower() or res.returncode == 50:
            return {
                "installed": False,
                "distros": [],
                "default_distro": None,
                "has_tools": False,
                "tools": {},
                "message": "Windows Subsystem for Linux (WSL) ยังไม่ได้ติดตั้งบนเครื่องนี้",
            }

        # Query installed distros
        res_q = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, timeout=8)
        q_text = _decode_wsl_output(res_q.stdout)
        distros = [line.strip().replace("\x00", "") for line in q_text.splitlines() if line.strip().replace("\x00", "")]
        # Filter out invalid or docker-desktop distros if regular ones exist
        main_distros = [d for d in distros if not d.startswith("docker-desktop")]
        chosen_distros = main_distros if main_distros else distros

        default_distro = chosen_distros[0] if chosen_distros else None

        if not distros:
            return {
                "installed": True,
                "distros": [],
                "default_distro": None,
                "has_tools": False,
                "tools": {},
                "message": "WSL ติดตั้งแล้ว แต่ยังไม่มี Linux Distribution (เช่น Ubuntu)",
            }

        # Check for tools in the chosen distro
        tools = {"yosys": False, "nextpnr-xilinx": False, "docker": False, "python3": False}
        if default_distro:
            check_cmd = "(command -v yosys || test -x /usr/bin/yosys) && echo 'FOUND_YOSYS'; (command -v nextpnr-xilinx || test -x /opt/openxc7/bin/nextpnr-xilinx) && echo 'FOUND_NEXTPNR'; command -v docker; command -v python3"
            r_tools = subprocess.run(
                ["wsl.exe", "-d", default_distro, "--", "bash", "-c", check_cmd],
                capture_output=True,
                timeout=10,
            )
            t_out = r_tools.stdout.decode("utf-8", errors="ignore")
            tools["yosys"] = "FOUND_YOSYS" in t_out or "yosys" in t_out
            tools["nextpnr-xilinx"] = "FOUND_NEXTPNR" in t_out or "nextpnr" in t_out
            tools["docker"] = "docker" in t_out
            tools["python3"] = "python3" in t_out

        has_tools = (tools["yosys"] and tools["nextpnr-xilinx"]) or tools["docker"]

        return {
            "installed": True,
            "distros": chosen_distros,
            "default_distro": default_distro,
            "has_tools": has_tools,
            "tools": tools,
            "message": f"พบ WSL ({default_distro}) พร้อมใช้งานในเครื่อง",
        }
    except Exception as ex:
        return {
            "installed": False,
            "distros": [],
            "default_distro": None,
            "has_tools": False,
            "tools": {},
            "message": f"ตรวจสอบ WSL ผิดพลาด: {ex}",
        }


def launch_wsl_install():
    """Launch elevated command prompt to run 'wsl --install'."""
    cmd = 'Start-Process cmd -Verb runAs -ArgumentList "/k wsl --install"'
    subprocess.Popen(["powershell.exe", "-Command", cmd], shell=True)


def convert_win_to_wsl_path(win_path: str, distro: Optional[str] = None) -> str:
    """Convert Windows path (C:\\path\\...) to WSL path (/mnt/c/path/...)."""
    wsl_exe = "wsl.exe"
    cmd = ["wsl.exe"]
    if distro:
        cmd.extend(["-d", distro])
    cmd.extend(["--", "wslpath", "-u", win_path.replace("\\", "/")])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        path = res.stdout.strip()
        if path.startswith("/"):
            return path
    except Exception:
        pass
    
    # Fallback conversion
    abs_p = os.path.abspath(win_path)
    drive = abs_p[0].lower()
    rest = abs_p[2:].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def generate_wsl_build_script(
    pkg_dir: str,
    cpu_name: str,
    target_part: str = "xc7a100tcsg324-1",
) -> str:
    """
    Generate build_wsl.sh inside the SoC package directory.
    Uses native openXC7/Yosys inside WSL.
    """
    script_path = os.path.join(pkg_dir, "build_wsl.sh")

    sh_content = f"""#!/usr/bin/env bash
# FPGA Studio — Local WSL Synthesis Script for Digilent Nexys A7
set -e

DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

CPU="{cpu_name}"
DEVICE="{target_part}"

export PATH="/opt/openxc7/bin:/usr/bin:/bin:/usr/local/bin"

echo "================================================================="
echo "  FPGA Studio - Local WSL Synthesis Pipeline (Zero-Vivado)"
echo "  Target CPU: $CPU | Device: $DEVICE"
echo "================================================================="

# 1. Native toolchain check
if ! command -v yosys >/dev/null 2>&1; then
    echo "ERROR: Yosys not found in WSL. Install with: sudo apt update && sudo apt install -y yosys"
    exit 1
fi

echo "=== [1/3] Synthesizing SoC with Yosys (Native WSL) ==="
FILES="nexys_a7_soc_top.v uart_prog_loader.v"
for f in rtl_cpu/*.v; do
    [ -e "$f" ] || continue
    bn=$(basename "$f")
    if [ "$bn" != "top.v" ] && [ "$bn" != "inst_rom.v" ] && [ "$bn" != "data_ram.v" ] && [ "$bn" != "openmips_min_sopc.v" ]; then
        FILES="$FILES $f"
    fi
done

yosys -p "
    read_verilog -I rtl_cpu $FILES;
    hierarchy -top nexys_a7_soc_top;
    synth_xilinx -top nexys_a7_soc_top -family xc7 -json soc.json
"

CHIPDB="/opt/openxc7/chipdb/xc7a100tcsg324.bin"
if [ ! -f "$CHIPDB" ]; then
    CHIPDB=$(find /opt/openxc7 -name "*xc7a100t*.bin" 2>/dev/null | head -n 1)
fi

echo "=== [2/3] Place & Route with nextpnr-xilinx ==="
nextpnr-xilinx \\
    --chipdb "$CHIPDB" \\
    --xdc Nexys-A7-100T-Master.xdc \\
    --json soc.json \\
    --fasm soc.fasm \\
    --ignore-loops \\
    --timing-allow-fail \\
    --force || true

if [ -f soc.fasm ]; then
    echo "=== [3/3] Generating Artix-7 Bitstream ==="
    PRJXRAY_DB="/opt/openxc7/share/nextpnr/external/prjxray-db/artix7"
    if [ ! -d "$PRJXRAY_DB" ]; then
        PRJXRAY_DB=$(find /opt/openxc7 -type d -name "artix7" | grep "prjxray-db" | head -n 1)
    fi
    fasm2frames --part xc7a100tcsg324-1 --db-root "$PRJXRAY_DB" soc.fasm soc.frames
    PART_YAML="$PRJXRAY_DB/xc7a100tcsg324-1/part.yaml"
    xc7frames2bit --part_name xc7a100tcsg324-1 --part_file "$PART_YAML" --frm_file soc.frames --output_file "nexys_a7_{cpu_name}.bit"
    echo "SUCCESS: Generated nexys_a7_{cpu_name}.bit"
else
    echo "ERROR: Place & route did not generate soc.fasm"
    exit 1
fi
"""

    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sh_content)

    return script_path


def run_wsl_synthesis(
    project_dir: str,
    cpu_name: str,
    cpu_arch: str = "mips",
    cpu_hdl_path: Optional[str] = None,
    distro: Optional[str] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Execute complete synthesis inside WSL.
    Streams logs in real-time.
    """
    status = check_wsl_status()
    if not status["installed"]:
        return False, status["message"], None

    chosen_distro = distro or status["default_distro"]
    if not chosen_distro:
        return False, "ไม่พบ Linux Distribution ใน WSL (ต้องติดตั้ง Ubuntu ก่อน)", None

    if on_log:
        on_log(f"🐧 เริ่มระบบ Local WSL Synthesis บน Linux Distribution: '{chosen_distro}'...")

    from core.cloud_synthesis import prepare_cloud_synthesis_package

    pkg_dir = prepare_cloud_synthesis_package(project_dir, cpu_name, arch=cpu_arch, cpu_hdl_path=cpu_hdl_path)
    generate_wsl_build_script(pkg_dir, cpu_name)

    wsl_pkg_dir = convert_win_to_wsl_path(pkg_dir, chosen_distro)
    if on_log:
        on_log(f"📁 WSL Working Directory: {wsl_pkg_dir}")

    cmd = [
        "wsl.exe",
        "-d",
        chosen_distro,
        "--",
        "bash",
        "-c",
        f"cd '{wsl_pkg_dir}' && chmod +x build_wsl.sh && ./build_wsl.sh",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
        )

        for line in iter(proc.stdout.readline, ""):
            line_str = line.strip()
            if line_str and on_log:
                on_log(line_str)

        proc.stdout.close()
        rc = proc.wait()

        expected_bit = os.path.join(pkg_dir, f"nexys_a7_{cpu_name}.bit")
        target_bit = os.path.join(project_dir, "bitstreams", f"nexys_a7_{cpu_name}.bit")

        if os.path.isfile(expected_bit) and os.path.getsize(expected_bit) > 1000:
            os.makedirs(os.path.dirname(target_bit), exist_ok=True)
            shutil.copy2(expected_bit, target_bit)
            if on_log:
                on_log(f"\n🎉 สังเคราะห์ Bitstream สำเร็จสมบูรณ์: {target_bit}")
            return True, f"สังเคราะห์ Bitstream ({cpu_name}) ผ่าน WSL สำเร็จเรียบร้อย!", target_bit

        if rc == 0:
            return True, f"ประมวลผล WSL เสร็จสิ้น (Netlist soc.json พร้อมใช้งาน)", None
        else:
            return False, f"การประมวลผลใน WSL สิ้นสุดด้วยรหัสข้อผิดพลาด ({rc})", None

    except Exception as ex:
        err = f"เกิดข้อผิดพลาดในการรัน WSL: {ex}"
        if on_log:
            on_log(f"❌ {err}")
        return False, err, None

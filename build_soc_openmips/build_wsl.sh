#!/usr/bin/env bash
# FPGA Studio — Local WSL Synthesis Script for Digilent Nexys A7
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

CPU="openmips"
DEVICE="xc7a100tcsg324-1"

echo "================================================================="
echo "  FPGA Studio — Local WSL Synthesis Pipeline (Zero-Vivado)"
echo "  Target CPU: $CPU | Device: $DEVICE"
echo "================================================================="

# 1. Check if openXC7 Docker container is available in WSL
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "✓ ตรวจพบ Docker ใน WSL: ใช้คอนเทนเนอร์ regymm/openxc7:latest"
    docker run --rm -v "$DIR:/work" -w /work regymm/openxc7:latest bash -c '
        set -e
        echo "=== [1/3] Synthesizing SoC with Yosys ==="
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

        echo "=== [2/3] Place & Route with nextpnr-xilinx ==="
        CHIPDB="/work/chipdb/xc7a100t.bin"
        if [ ! -f "$CHIPDB" ]; then
            mkdir -p /work/chipdb
            EXISTING_DB=$(find / -name "*xc7a100t*.bin" 2>/dev/null | head -n 1)
            if [ -n "$EXISTING_DB" ]; then
                CHIPDB="$EXISTING_DB"
            else
                BBA_SCRIPT=$(find / -name "bbaexport.py" 2>/dev/null | head -n 1)
                if [ -n "$BBA_SCRIPT" ]; then
                    pypy3 "$BBA_SCRIPT" --device xc7a100tcsg324-1 --bba /work/chipdb/xc7a100t.bba || python3 "$BBA_SCRIPT" --device xc7a100tcsg324-1 --bba /work/chipdb/xc7a100t.bba
                    bbasm -l /work/chipdb/xc7a100t.bba "$CHIPDB"
                fi
            fi
        fi

        nextpnr-xilinx             --chipdb "$CHIPDB"             --xdc Nexys-A7-100T-Master.xdc             --json soc.json             --fasm soc.fasm             --ignore-loops             --timing-allow-fail             --force || true

        if [ -f soc.fasm ]; then
            echo "=== [3/3] Generating Artix-7 Bitstream ==="
            PRJXRAY_DB=$(find / -type d -name "artix7" | grep "prjxray-db" | head -n 1)
            fasm2frames --part xc7a100tcsg324-1 --db-root "$PRJXRAY_DB" soc.fasm soc.frames
            PART_YAML=$(find "$PRJXRAY_DB" -name "part.yaml" | grep "xc7a100t" | head -n 1)
            xc7frames2bit --part_file "$PART_YAML" --frm_file soc.frames --output_file "nexys_a7_openmips.bit"
            echo "SUCCESS: Generated nexys_a7_openmips.bit"
        else
            echo "ERROR: Place & route did not generate soc.fasm"
            exit 1
        fi
    '
    exit 0
fi

# 2. Native toolchain check
export PATH="/opt/openxc7/bin:/usr/bin:/bin:/usr/local/bin:$PATH"

if ! command -v yosys >/dev/null 2>&1; then
    echo "⚠️ ไม่พบ Yosys ใน WSL กรุณาติดตั้งด้วย: sudo apt update && sudo apt install -y yosys"
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
    CHIPDB=$(find / -name "*xc7a100t*.bin" 2>/dev/null | head -n 1)
fi

echo "=== [2/3] Place & Route with nextpnr-xilinx ==="
nextpnr-xilinx     --chipdb "$CHIPDB"     --xdc Nexys-A7-100T-Master.xdc     --json soc.json     --fasm soc.fasm     --ignore-loops     --timing-allow-fail     --force || true

if [ -f soc.fasm ]; then
    echo "=== [3/3] Generating Artix-7 Bitstream ==="
    PRJXRAY_DB="/opt/openxc7/share/nextpnr/external/prjxray-db/artix7"
    if [ ! -d "$PRJXRAY_DB" ]; then
        PRJXRAY_DB=$(find / -type d -name "artix7" | grep "prjxray-db" | head -n 1)
    fi
    fasm2frames --part xc7a100tcsg324-1 --db-root "$PRJXRAY_DB" soc.fasm soc.frames
    PART_YAML="$PRJXRAY_DB/xc7a100tcsg324-1/part.yaml"
    xc7frames2bit --part_file "$PART_YAML" --frm_file soc.frames --output_file "nexys_a7_openmips.bit"
    echo "SUCCESS: Generated nexys_a7_openmips.bit"
else
    echo "ERROR: Place & route did not generate soc.fasm"
    exit 1
fi

import sys
import os
import struct
import time
import serial
import subprocess
import tempfile
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import MIPS_BIN_DIR, ROOT_DIR

test_c = """
#define LED         (*(volatile int*)0xF0000000)
#define SEG7        (*(volatile int*)0xF0000008)
#define UART_TX     (*(volatile int*)0xF0000010)
#define UART_STATUS (*(volatile int*)0xF0000014)

void putc(char c) {
    while ((UART_STATUS & 2) == 0);
    UART_TX = c;
}

int main(void) {
    register int n = 10;
    register int k = 3;
    __asm__ __volatile__("" : "+r"(n), "+r"(k));

    register int ans = 1;
    for (register int i = 1; i <= k; i++) {
        ans = (ans * (n - i + 1)) / i;
    }

    LED = ans;

    int d2 = ans / 100;
    int rem = ans % 100;
    int d1 = rem / 10;
    int d0 = rem % 10;
    int bcd = (d2 << 8) | (d1 << 4) | d0;
    SEG7 = bcd;

    putc('R');
    putc('=');
    putc('0' + d2);
    putc('0' + d1);
    putc('0' + d0);
    putc('\\r');
    putc('\\n');

    while (1) {}
    return 0;
}
"""

def compile_no_delayed_branch(c_code):
    gcc_bin = "mips64-elf-gcc.exe"
    objdump_bin = "mips64-elf-objdump.exe"
    for cand in os.listdir(MIPS_BIN_DIR):
        if "gcc.exe" in cand.lower() and "ar" not in cand.lower():
            gcc_bin = cand
        if "objdump.exe" in cand.lower():
            objdump_bin = cand
    compiler_exe = os.path.join(MIPS_BIN_DIR, gcc_bin)
    objdump_exe = os.path.join(MIPS_BIN_DIR, objdump_bin)

    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = os.path.join(tmpdir, "main.c")
        s_path = os.path.join(tmpdir, "start.S")
        ld_path = os.path.join(tmpdir, "link.ld")
        elf_path = os.path.join(tmpdir, "prog.elf")

        with open(c_path, "w") as f: f.write(c_code)
        with open(s_path, "w") as f:
            f.write(".section .text.init\n.set noreorder\n.global _start\n_start:\n lui $sp, 0x8001\n jal main\n nop\n_halt:\n j _halt\n nop\n")
        with open(ld_path, "w") as f:
            f.write("ENTRY(_start)\nSECTIONS { . = 0x00000000; .text : { *(.text.init) *(.text*) } }\n")

        cmd = [
            compiler_exe, "-mabi=32", "-march=mips32", "-EB", "-O1",
            "-fno-delayed-branch", # <--- KEY FLAG
            "-nostdlib", "-fno-builtin", "-mno-check-zero-division",
            "-T", ld_path, s_path, c_path, "-o", elf_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0: raise RuntimeError(res.stderr)

        dump = subprocess.run([objdump_exe, "-d", elf_path], capture_output=True, text=True)
        line_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+(.+)$")
        words = []
        for line in dump.stdout.splitlines():
            ml = line_re.match(line)
            if ml:
                words.append(int(ml.group(2), 16))
        return words

def main():
    words = compile_no_delayed_branch(test_c)
    print(f"Compiled {len(words)} words with -fno-delayed-branch.")

    pad_target = max(len(words) + 256, 1024)
    while len(words) < pad_target: words.append(0x00000000)

    payload = bytearray(b"PROG")
    payload.extend(struct.pack("<I", len(words)))
    for w in words: payload.extend(struct.pack("<I", w))

    ser = serial.Serial('COM5', 115200, timeout=1.0)
    time.sleep(0.05)
    ser.reset_input_buffer()

    print("Uploading...")
    ser.write(payload)
    ser.flush()
    time.sleep(len(payload) / 11520.0 + 0.1)

    print("Reading output...")
    response = b""
    t0 = time.time()
    while time.time() - t0 < 1.5:
        if ser.in_waiting > 0:
            b = ser.read(ser.in_waiting)
            response += b
            if b"\n" in response: break
        time.sleep(0.02)
    ser.close()
    print("OUTPUT WITH -fno-delayed-branch:", repr(response.decode('latin1', errors='replace')))

if __name__ == '__main__':
    main()

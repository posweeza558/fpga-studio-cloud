import sys
import os
import struct
import time
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

def main():
    c_path = 'workspace/nexys-a7-project/nck_7seg_demo.c'
    with open(c_path, 'r', encoding='utf-8') as f:
        code = f.read()

    print("Compiling nck_7seg_demo.c with MIPS GCC...")
    asm_lines, instrs = compile_with_real_mips_gcc(code)
    print(f"Compiled {len(instrs)} instructions.")

    prog_words = []
    for ins in instrs:
        prog_words.append(ins.get("word", int(ins["hex"], 16)) & 0xFFFFFFFF)

    # Pad with NOPs up to 1024 words
    pad_target = max(len(prog_words) + 256, 1024)
    while len(prog_words) < pad_target:
        prog_words.append(0x00000000)

    payload = bytearray(b"PROG")
    payload.extend(struct.pack("<I", len(prog_words)))
    for w in prog_words:
        payload.extend(struct.pack("<I", w))

    print(f"Total payload size: {len(payload)} bytes")
    print("Opening COM5 @ 115200...")
    ser = serial.Serial('COM5', 115200, timeout=1.0)
    time.sleep(0.1)

    print("Sending payload...")
    ser.write(payload)
    ser.flush()

    time.sleep(len(payload) / 11520.0 + 0.2)
    ser.close()
    print("Upload completed successfully!")

if __name__ == '__main__':
    main()

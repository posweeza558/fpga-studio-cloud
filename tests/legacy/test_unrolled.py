import sys
import os
import struct
import time
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

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
    // 10C3 = (10 * 9 * 8) / (1 * 2 * 3) = 720 / 6 = 120
    // Direct computation without loop delay hazards:
    register int ans = 10;
    ans = (ans * 9) / 2; // 45
    ans = (ans * 8) / 3; // 120

    LED = ans;

    int d2 = ans / 100;
    int rem = ans % 100;
    int d1 = rem / 10;
    int d0 = rem % 10;
    int bcd = (d2 << 8) | (d1 << 4) | d0;
    SEG7 = bcd;

    putc('A');
    putc('N');
    putc('S');
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

def main():
    asm_lines, instrs = compile_with_real_mips_gcc(test_c)
    print(f"Compiled {len(instrs)} instructions.")
    for i in instrs:
        if "div" in i["asm"] or "mul" in i["asm"]:
            print(f"  {i['pc']}: {i['asm']}")

    prog_words = []
    for ins in instrs:
        prog_words.append(ins.get("word", int(ins["hex"], 16)) & 0xFFFFFFFF)

    pad_target = max(len(prog_words) + 256, 1024)
    while len(prog_words) < pad_target:
        prog_words.append(0x00000000)

    payload = bytearray(b"PROG")
    payload.extend(struct.pack("<I", len(prog_words)))
    for w in prog_words:
        payload.extend(struct.pack("<I", w))

    ser = serial.Serial('COM5', 115200, timeout=1.0)
    time.sleep(0.05)
    ser.reset_input_buffer()

    print("Uploading unrolled nCk...")
    ser.write(payload)
    ser.flush()

    time.sleep(len(payload) / 11520.0 + 0.1)

    print("Reading output from board...")
    response = b""
    t0 = time.time()
    while time.time() - t0 < 1.5:
        if ser.in_waiting > 0:
            b = ser.read(ser.in_waiting)
            response += b
            if b"\n" in response:
                break
        time.sleep(0.02)

    ser.close()
    print("RECEIVED FROM HARDWARE:", repr(response.decode('latin1', errors='replace')))

if __name__ == '__main__':
    main()

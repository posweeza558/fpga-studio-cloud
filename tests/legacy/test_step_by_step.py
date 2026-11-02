import sys
import os
import struct
import time
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

test_c = """
#define UART_TX     (*(volatile int*)0xF0000010)
#define UART_STATUS (*(volatile int*)0xF0000014)

void putc(char c) {
    while ((UART_STATUS & 2) == 0);
    UART_TX = c;
}

void print_hex(unsigned int v) {
    for (int i = 7; i >= 0; i--) {
        int nib = (v >> (i * 4)) & 0xF;
        if (nib < 10) putc('0' + nib);
        else putc('A' + nib - 10);
    }
}

int main(void) {
    register int n = 10;
    register int k = 3;
    __asm__ __volatile__("" : "+r"(n), "+r"(k));

    register int ans = 1;
    for (register int i = 1; i <= k; i++) {
        putc('i'); putc('='); putc('0' + i);
        putc(' ');

        int factor = n - i + 1;
        putc('f'); putc('='); putc('0' + factor);
        putc(' ');

        int prod = ans * factor;
        putc('p'); putc('='); print_hex(prod);
        putc(' ');

        ans = prod / i;
        putc('a'); putc('='); print_hex(ans);
        putc('\\r'); putc('\\n');
    }

    while (1) {}
    return 0;
}
"""

def main():
    asm_lines, instrs = compile_with_real_mips_gcc(test_c)
    prog_words = [ins.get("word", int(ins["hex"], 16)) & 0xFFFFFFFF for ins in instrs]
    pad_target = max(len(prog_words) + 256, 1024)
    while len(prog_words) < pad_target: prog_words.append(0x00000000)

    payload = bytearray(b"PROG")
    payload.extend(struct.pack("<I", len(prog_words)))
    for w in prog_words: payload.extend(struct.pack("<I", w))

    ser = serial.Serial('COM5', 115200, timeout=1.0)
    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()
    time.sleep(len(payload) / 11520.0 + 0.1)

    response = b""
    t0 = time.time()
    while time.time() - t0 < 2.0:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting)
            if response.count(b"\n") >= 3: break
        time.sleep(0.02)
    ser.close()
    print("OUTPUT FROM BOARD:\n" + response.decode('latin1', errors='replace'))

if __name__ == '__main__':
    main()

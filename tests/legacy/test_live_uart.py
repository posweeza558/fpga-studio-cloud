import sys
import os
import struct
import time
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

test_c = """
#define LED     (*(volatile int*)0xF0000000)
#define SEG7    (*(volatile int*)0xF0000008)
#define UART_TX (*(volatile int*)0xF0000010)

void putc(char c) {
    // Wait until tx ready (or small delay)
    for (volatile int i = 0; i < 3000; i++);
    UART_TX = c;
}

void puts(const char *s) {
    while (*s) {
        putc(*s++);
    }
}

int main(void) {
    register int n = 10;
    register int k = 3;
    __asm__ __volatile__("" : "+r"(n), "+r"(k));

    register int ans = 1;
    for (register int i = 1; i <= k; i++) {
        ans = (ans * (n - i + 1)) / i;
    }

    LED = ans; // 120

    int d2 = ans / 100;
    int rem = ans % 100;
    int d1 = rem / 10;
    int d0 = rem % 10;
    int bcd = (d2 << 8) | (d1 << 4) | d0;
    SEG7 = bcd;

    puts("NCK_RESULT_OK=");
    putc('0' + d2);
    putc('0' + d1);
    putc('0' + d0);
    puts("\\r\\n");

    while (1) {}
    return 0;
}
"""

def main():
    asm_lines, instrs = compile_with_real_mips_gcc(test_c)
    print(f"Compiled {len(instrs)} instructions.")

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

    print("Opening COM5...")
    ser = serial.Serial('COM5', 115200, timeout=1.5)
    time.sleep(0.1)
    ser.reset_input_buffer()

    print("Uploading...")
    ser.write(payload)
    ser.flush()

    time.sleep(len(payload) / 11520.0 + 0.1)

    print("Listening for UART output from board...")
    response = b""
    t0 = time.time()
    while time.time() - t0 < 2.0:
        if ser.in_waiting > 0:
            b = ser.read(ser.in_waiting)
            response += b
            if b"\n" in response:
                break
        time.sleep(0.05)

    ser.close()
    print("Received from board:", repr(response))

if __name__ == '__main__':
    main()

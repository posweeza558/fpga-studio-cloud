#ifndef NEXYS_A7_H
#define NEXYS_A7_H

#include <stdint.h>

/**
 * ==============================================================================
 * Digilent Nexys A7 FPGA (Artix-7 XC7A100T) — Memory Mapped I/O Definitions
 * ==============================================================================
 */

// 1. LED 16 ดวง (Physical Pins: H17, K15, J13, N14, R18, V17, U17, U16, V16, T15, U14, T16, V15, V14, V12, V11)
#define LED             (*(volatile uint32_t*)0xF0000000)

// 2. สวิตช์ 16 ตัว (Physical Pins: J15, L16, M13, R15, R17, T18, U18, R13, T8, U8, R16, T13, H6, U12, U11, V10)
#define SWITCH          (*(volatile uint32_t*)0xF0000004)

// 3. 7-Segment Display 8 หลัก (Physical Pins: Cathodes CA-CG, DP / Anodes AN0-AN7)
#define SEG7            (*(volatile uint32_t*)0xF0000008)

// 4. ปุ่มกด 5 ทิศทาง + RESET (Physical Pins: BTNC=N17, BTNU=M18, BTNL=P17, BTNR=M17, BTND=P18, RESET=C12)
#define BTN             (*(volatile uint32_t*)0xF000000C)
#define BUTTON          (*(volatile uint32_t*)0xF000000C)

#define BTN_CENTER      (1 << 0) // ปุ่มกลาง (BTNC - N17)
#define BTN_UP          (1 << 1) // ปุ่มบน   (BTNU - M18)
#define BTN_LEFT        (1 << 2) // ปุ่มซ้าย (BTNL - P17)
#define BTN_RIGHT       (1 << 3) // ปุ่มขวา (BTNR - M17)
#define BTN_DOWN        (1 << 4) // ปุ่มล่าง (BTND - P18)
#define BTN_RESET       (1 << 5) // ปุ่มแดง CPU RESET (C12)

// 5. UART TX / RX Serial Communication (Physical Pins: TX=D4, RX=C4)
#define UART_TX         (*(volatile uint32_t*)0xF0000010)
#define UART_RX         (*(volatile uint32_t*)0xF0000010)
#define UART_STATUS     (*(volatile uint32_t*)0xF0000014) // Bit 0: RX Data Ready, Bit 1: TX Buffer Ready

// 6. ไฟ RGB LEDs 2 ดวง (Physical Pins: LD16=R12/M16/N15, LD17=G14/R11/N16)
#define RGB_LED         (*(volatile uint32_t*)0xF0000018)

// 7. จอภาพ VGA Framebuffer (640x480 @ 60Hz 12-bit RGB)
#define VGA_VRAM        ((volatile uint32_t*)0xFF000000)

// Helper function to send character to UART console
static inline void uart_putchar(char c) {
    UART_TX = (uint32_t)c;
}

// Helper function to print string
static inline void uart_print(const char *str) {
    while (*str) {
        uart_putchar(*str++);
    }
}

// Helper function to check if a specific button is pressed
static inline int is_button_pressed(uint32_t btn_mask) {
    return (BTN & btn_mask) != 0;
}

#endif // NEXYS_A7_H

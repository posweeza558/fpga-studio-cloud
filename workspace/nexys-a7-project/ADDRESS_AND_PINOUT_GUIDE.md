# คู่มือการจับคู่ Address (MMIO) กับ ขาพินบนบอร์ด Nexys A7 FPGA
> **บอร์ดเป้าหมาย:** Digilent Nexys A7 (ชิป Xilinx Artix-7 XC7A100T-1CSG324C หรือ XC7A50T)

---

## 1. ตาราง Memory-Mapped I/O (MMIO Address Map)

ในระบบ CPU (MIPS / RISC-V) ของ FPGA Studio อุปกรณ์ทุกชิ้นจะถูกกำหนดเป็น "เลขที่อยู่หน่วยความจำ (Address)" ดังนี้:

| อุปกรณ์ I/O | Memory Address | โหมด | ขนาดบิต | คำอธิบาย |
|---|---|---|---|---|
| **LED 16 ดวง** | `0xF0000000` | Read/Write | 16-bit (`[15:0]`) | ควบคุมไฟ LED 16 ดวง (1 = ติด, 0 = ดับ) |
| **Switch 16 ตัว** | `0xF0000004` | Read Only | 16-bit (`[15:0]`) | อ่านสถานะสวิตช์ 16 ตัว (1 = ดันขึ้น, 0 = ดันลง) |
| **7-Segment Display** | `0xF0000008` | Read/Write | 32-bit (`[31:0]`) | แสดงเลขฐานสิบหก 8 หลัก (แต่ละหลักใช้ 4 บิต) |
| **ปุ่มกด (Push Buttons)** | `0xF000000C` | Read Only | 6-bit (`[5:0]`) | อ่านสถานะปุ่มกด 5 ทิศทาง + RESET (1 = กด, 0 = ปล่อย) |
| **UART TX / RX (Console)** | `0xF0000010` | Read/Write | 8-bit (`[7:0]`) | ส่งตัวอักษร TX (Write) / รับตัวอักษร RX (Read) |
| **UART Status** | `0xF0000014` | Read Only | 2-bit (`[1:0]`) | Bit 0: RX Data Ready, Bit 1: TX Buffer Ready |
| **ไฟ RGB LEDs 2 ดวง** | `0xF0000018` | Read/Write | 24-bit (`[23:0]`) | ควบคุมสี RGB: Bits [23:12] = LD16, Bits [11:0] = LD17 |
| **VGA Framebuffer** | `0xFF000000` | Read/Write | 12-bit RGB | จอภาพ VGA 640×480 (แอดเดรส 0xFF000000 ถึง 0xFF00FFFF) |

---

## 2. ตารางจับคู่ Address กับ ขาพินจริงบนบอร์ด (Physical FPGA Pins)

### 2.1 สวิตช์เลื่อน (Slide Switches: SW0 – SW15) ➜ Address: `0xF0000004`
| บิตในโปรแกรม | ชื่ออุปกรณ์ | ขาพินชิป FPGA (Nexys A7) | I/O Standard |
|---|---|---|---|
| Bit 0 | `SW[0]` | **J15** | LVCMOS33 |
| Bit 1 | `SW[1]` | **L16** | LVCMOS33 |
| Bit 2 | `SW[2]` | **M13** | LVCMOS33 |
| Bit 3 | `SW[3]` | **R15** | LVCMOS33 |
| Bit 4 | `SW[4]` | **R17** | LVCMOS33 |
| Bit 5 | `SW[5]` | **T18** | LVCMOS33 |
| Bit 6 | `SW[6]` | **U18** | LVCMOS33 |
| Bit 7 | `SW[7]` | **R13** | LVCMOS33 |
| Bit 8 | `SW[8]` | **T8** | LVCMOS33 |
| Bit 9 | `SW[9]` | **U8** | LVCMOS33 |
| Bit 10 | `SW[10]` | **R16** | LVCMOS33 |
| Bit 11 | `SW[11]` | **T13** | LVCMOS33 |
| Bit 12 | `SW[12]` | **H6** | LVCMOS33 |
| Bit 13 | `SW[13]` | **U12** | LVCMOS33 |
| Bit 14 | `SW[14]` | **U11** | LVCMOS33 |
| Bit 15 | `SW[15]` | **V10** | LVCMOS33 |

---

### 2.2 หลอดไฟ (LEDs: LED0 – LED15) ➜ Address: `0xF0000000`
| บิตในโปรแกรม | ชื่ออุปกรณ์ | ขาพินชิป FPGA (Nexys A7) | I/O Standard |
|---|---|---|---|
| Bit 0 | `LED[0]` | **H17** | LVCMOS33 |
| Bit 1 | `LED[1]` | **K15** | LVCMOS33 |
| Bit 2 | `LED[2]` | **J13** | LVCMOS33 |
| Bit 3 | `LED[3]` | **N14** | LVCMOS33 |
| Bit 4 | `LED[4]` | **R18** | LVCMOS33 |
| Bit 5 | `LED[5]` | **V17** | LVCMOS33 |
| Bit 6 | `LED[6]` | **U17** | LVCMOS33 |
| Bit 7 | `LED[7]` | **U16** | LVCMOS33 |
| Bit 8 | `LED[8]` | **V16** | LVCMOS33 |
| Bit 9 | `LED[9]` | **T15** | LVCMOS33 |
| Bit 10 | `LED[10]` | **U14** | LVCMOS33 |
| Bit 11 | `LED[11]` | **T16** | LVCMOS33 |
| Bit 12 | `LED[12]` | **V15** | LVCMOS33 |
| Bit 13 | `LED[13]` | **V14** | LVCMOS33 |
| Bit 14 | `LED[14]` | **V12** | LVCMOS33 |
| Bit 15 | `LED[15]` | **V11** | LVCMOS33 |

---

### 2.3 ตัวเลข 7-Segment (8 Digits) ➜ Address: `0xF0000008`
บอร์ด Nexys A7 ขับ 7-Segment แบบ Multiplexing (Active Low):

**ขาสัญญาณเซกเมนต์ (Cathodes a, b, c, d, e, f, g, dp):**
| เส้นสัญญาณ | ขาพินชิป FPGA | หน้าที่ |
|---|---|---|
| `CA` | **T10** | Segment a (แถวบนสุด) |
| `CB` | **R10** | Segment b (ขวาบน) |
| `CC` | **K16** | Segment c (ขวาล่าง) |
| `CD` | **K13** | Segment d (แถวล่างสุด) |
| `CE` | **P15** | Segment e (ซ้ายล่าง) |
| `CF` | **T11** | Segment f (ซ้ายบน) |
| `CG` | **L18** | Segment g (แถวกลาง) |
| `DP` | **H15** | จุดทศนิยม (Decimal Point) |

**ขาสัญญาณเลือกหลัก (Anodes 8 หลัก: AN0 – AN7):**
| เส้นสัญญาณ | ขาพินชิป FPGA | ตำแหน่งหลัก |
|---|---|---|
| `AN[0]` | **J17** | หลักที่ 0 (ขวาสุด) |
| `AN[1]` | **J18** | หลักที่ 1 |
| `AN[2]` | **T9** | หลักที่ 2 |
| `AN[3]` | **J14** | หลักที่ 3 |
| `AN[4]` | **P14** | หลักที่ 4 |
| `AN[5]` | **T14** | หลักที่ 5 |
| `AN[6]` | **K2** | หลักที่ 6 |
| `AN[7]` | **U13** | หลักที่ 7 (ซ้ายสุด) |

---

### 2.4 สัญญาณนาฬิกา และ UART (Serial)
| สัญญาณ | Address / หน้าที่ | ขาพินชิป FPGA |
|---|---|---|
| `CLK100MHZ` | System Clock (100 MHz) | **E3** |
| `CPU_RESETN` | ปุ่ม Reset หลัก (Active Low) | **C12** |
| `UART_TXD` | `0xF0000010` (ส่งจาก FPGA ไป PC) | **D4** |
| `UART_RXD` | รับข้อมูลจาก PC เข้า FPGA | **C4** |

---

## 3. ตัวอย่างการเชื่อมต่อในภาษา Verilog (SoC Decoder)

```verilog
// ภายนอก CPU ในโมดูล Top Level
always @(posedge clk) begin
    if (mem_write) begin
        case (mem_address)
            32'hF0000000: led_reg      <= mem_writedata[15:0];  // ส่งไปขา H17..V11
            32'hF0000008: seg7_reg     <= mem_writedata;        // ส่งไปวงจร 7-Segment
            32'hF0000010: uart_tx_data <= mem_writedata[7:0];   // ส่งไปขา D4
        endcase
    end
end

// ตอน CPU สั่งอ่าน (lw)
always @(*) begin
    if (mem_address == 32'hF0000004)
        mem_readdata = {16'b0, sw_pins}; // อ่านจากขา J15..V10
    else
        mem_readdata = ram_readdata;
end
```

---

## 4. ตัวอย่างการใช้งานในภาษา C ผ่าน `nexys_a7.h`

```c
#include "nexys_a7.h"

int main() {
    while (1) {
        // อ่านค่าจากสวิตช์ขา J15..V10
        int value = SWITCH;
        
        // ส่งผลลัพธ์ออกไฟ LED ขา H17..V11
        LED = value;
        
        // ส่งผลลัพธ์ออก 7-Segment
        SEG7 = value;
    }
}
```

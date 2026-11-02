# คู่มือสถาปัตยกรรมระบบและการทำงานจริงฉบับสมบูรณ์ (FPGA Studio Developer & Architecture Manual v4.2)

> **สถานะเอกสาร**: เอกสารฉบับสมบูรณ์ (Exhaustive Technical & Developer Specification)  
> **เวอร์ชันโปรแกรม**: FPGA Studio v4.2 (Spotify Dark Edition)  
> **เป้าหมายฮาร์ดแวร์**: Digilent Nexys A7-100T (Xilinx Artix-7 XC7A100T-1CSG324C FPGA)  
> **สถาปัตยกรรมหลัก**: OpenMIPS (MIPS32 Release 1 Big-Endian) และ RISC-V (RV32IM Little-Endian)  
> **วัตถุประสงค์**: เพื่อให้วิศวกรและนักพัฒนาสามารถอ่านทำความเข้าใจระบบทั้งหมดในเอกสารชุดเดียว และสามารถนำซอร์สโค้ดไปบำรุงรักษาหรือพัฒนาต่อยอดได้ทันที

---

## สารบัญหัวข้อ (Table of Contents)
1. [ภาพรวมของระบบและปรัชญาการออกแบบ (System Overview & Design Philosophy)](#1-ภาพรวมของระบบและปรัชญาการออกแบบ)
2. [สถาปัตยกรรม 5-Stage Pipeline เจาะลึก (RTL Hardware & Simulation Engine)](#2-สถาปัตยกรรม-5-stage-pipeline-เจาะลึก)
   - 2.1 [โครงสร้างฮาร์ดแวร์ Verilog (OpenMIPS & RISC-V RTL)](#21-โครงสร้างฮาร์ดแวร์-verilog)
   - 2.2 [การจัดการ Pipeline Hazards: Forwarding, Stall และ Flush](#22-การจัดการ-pipeline-hazards)
   - 2.3 [กลไก Branch Delay Slot (MIPS) เทียบกับ Branch Flush (RISC-V)](#23-กลไก-branch-delay-slot-เทียบกับ-branch-flush)
   - 2.4 [ซอฟต์แวร์จำลอง Cycle-Accurate Simulator (`simulator_engine.py`)](#24-ซอฟต์แวร์จำลอง-cycle-accurate-simulator)
   - 2.5 [Rust Native Simulation Acceleration (`fpga_engine_rust.dll`)](#25-rust-native-simulation-acceleration)
3. [ระบบคอมไพเลอร์จริงและท่อส่งภาษา (Dual Real GCC Toolchains & Language Pipelines)](#3-ระบบคอมไพเลอร์จริงและท่อส่งภาษา)
   - 3.1 [คอมไพเลอร์ MIPS64 GCC 12.2 และการตั้งค่า Flag](#31-คอมไพเลอร์-mips64-gcc-122)
   - 3.2 [คอมไพเลอร์ xPack RISC-V GCC 15.2 และการตั้งค่า Flag](#32-คอมไพเลอร์-xpack-riscv-gcc-152)
   - 3.3 [Bare-Metal Startup Routine (`start.S`) และ Linker Script (`link.ld`)](#33-bare-metal-startup-routine-และ-linker-script)
   - 3.4 [การดึงข้อมูลส่วน Data (`.data`) และการทำ Word-Aligned BRAM Initialization](#34-การดึงข้อมูลส่วน-data)
   - 3.5 [ระบบ In-Memory LRU Compile Cache (0ms Latency)](#35-ระบบ-in-memory-lru-compile-cache)
   - 3.6 [Direct 32-Bit Assembler & Disassembler (Bit-Field Encoding/Decoding)](#36-direct-32-bit-assembler--disassembler)
   - 3.7 [Syntax Transpiler สำหรับภาษา Python และ Rust (`transpiler.py`)](#37-syntax-transpiler-สำหรับภาษา-python-และ-rust)
4. [ระบบการนำเข้าและวิเคราะห์ Custom CPU ของผู้ใช้ (Custom CPU Import & AST Analysis)](#4-ระบบการนำเข้าและวิเคราะห์-custom-cpu-ของผู้ใช้)
   - 4.1 [กลไก HDL Lexer/Parser ใน `hdl_analyzer.py`](#41-กลไก-hdl-lexerparser-ใน-hdl_analyzerpy)
   - 4.2 [การจำแนกประเภทวงจร: Standalone ALU vs Full SoC CPU vs Testbench](#42-การจำแนกประเภทวงจร)
   - 4.3 [การตรวจจับพอร์ตด้วย Regular Expression Role Patterns](#43-การตรวจจับพอร์ตด้วย-role-patterns)
   - 4.4 [โครงสร้างไฟล์ Manifest (`cpu_manifest.json`) และการ Binding ขาบอร์ด](#44-โครงสร้างไฟล์-manifest-และการ-binding-ขาบอร์ด)
5. [ระบบสร้างโค้ดฮาร์ดแวร์และแพ็กเกจ Vivado SoC (HDL & SoC Package Generator)](#5-ระบบสร้างโค้ดฮาร์ดแวร์และแพ็กเกจ-vivado-soc)
   - 5.1 [การสร้าง ROM สำหรับ VHDL, Verilog และ Vivado COE](#51-การสร้าง-rom-สำหรับ-vhdl-verilog-และ-vivado-coe)
   - 5.2 [โมดูล `nexys_a7_soc_top.v` และการเชื่อมต่อ MMIO Interconnect](#52-โมดูล-nexys_a7_soc_topv)
   - 5.3 [วงจร Live Hardware RAM Bootloader (`uart_prog_loader.v`)](#53-วงจร-live-hardware-ram-bootloader)
   - 5.4 [ไฟล์ Physical Constraints (`Nexys-A7-100T-Master.xdc`) และ Tcl Automation](#54-ไฟล์-physical-constraints-และ-tcl-automation)
6. [ระบบสังเคราะห์ Bitstream: ทั้งแบบ Vivado และ WSL Linux (Synthesis Pipelines)](#6-ระบบสังเคราะห์-bitstream)
   - 6.1 [WSL Local Synthesis ผ่าน openXC7 (Yosys + nextpnr-xilinx + prjxray)](#61-wsl-local-synthesis-ผ่าน-openxc7)
   - 6.2 [การแปลง Path ระหว่าง Windows และ Linux (`win_path_to_wsl_path`)](#62-การแปลง-path-ระหว่าง-windows-และ-linux)
   - 6.3 [สคริปต์การสังเคราะห์ภายใน WSL (`build_wsl.sh`)](#63-สคริปต์การสังเคราะห์ภายใน-wsl)
   - 6.4 [Xilinx Vivado CLI Batch Mode Synthesis](#64-xilinx-vivado-cli-batch-mode-synthesis)
   - 6.5 [Cloud Synthesis Pipeline ผ่าน GitHub Actions](#65-cloud-synthesis-pipeline)
7. [ระบบโปรแกรมฮาร์ดแวร์จริงและตัวจัดการไดรเวอร์ USB (Hardware Flashing & Port Drivers)](#7-ระบบโปรแกรมฮาร์ดแวร์จริงและตัวจัดการไดรเวอร์-usb)
   - 7.1 [ปัญหาไดรเวอร์ FTDI บน Windows และการแก้ปัญหาด้วย Zadig](#71-ปัญหาไดรเวอร์-ftdi-บน-windows-และการแก้ปัญหาด้วย-zadig)
   - 7.2 [การทำงานของ `openFPGALoader` (Direct JTAG Flash ลง SRAM และ SPI Flash)](#72-การทำงานของ-openfpgaloader)
   - 7.3 [การสั่งงาน Digilent Adept CLI (`djtgcfg`)](#73-การสั่งงาน-digilent-adept-cli)
   - 7.4 [การส่งโปรแกรมความเร็วสูงผ่าน USB-UART Bootloader (Python `serial`)](#74-การส่งโปรแกรมความเร็วสูงผ่าน-usb-uart-bootloader)
   - 7.5 [คลังบิตสตรีมสำเร็จรูป (Pre-bundled Bitstreams)](#75-คลังบิตสตรีมสำเร็จรูป)
8. [ระบบฮาร์ดแวร์จำลองและ Memory-Mapped I/O (Virtual Board & MMIO)](#8-ระบบฮาร์ดแวร์จำลองและ-memory-mapped-io)
   - 8.1 [ตารางแผนที่หน่วยความจำฉบับเต็ม (Complete MMIO Address Map)](#81-ตารางแผนที่หน่วยความจำฉบับเต็ม)
   - 8.2 [การทำงานของวิดเจ็ต Interactive Board (Switches, LEDs, Buttons)](#82-การทำงานของวิดเจ็ต-interactive-board)
   - 8.3 [วงจรถอดรหัส 8-Digit Multiplexed 7-Segment Display](#83-วงจรถอดรหัส-8-digit-multiplexed-7-segment-display)
   - 8.4 [ระบบ UART Terminal Console (115200 8N1)](#84-ระบบ-uart-terminal-console)
   - 8.5 [ระบบจำลองสัญญาณภาพ VGA 640x480 Virtual Framebuffer](#85-ระบบจำลองสัญญาณภาพ-vga-640x480-virtual-framebuffer)
9. [ระบบ Co-Simulation และการวิเคราะห์รูปคลื่นสัญญาณ (iverilog, VVP, GTKWave)](#9-ระบบ-co-simulation-และการวิเคราะห์รูปคลื่นสัญญาณ)
   - 9.1 [RTL Verification ด้วย Icarus Verilog (`iverilog`)](#91-rtl-verification-ด้วย-icarus-verilog)
   - 9.2 [การสร้างสัญญาณและเปิดดู Waveform ด้วย GTKWave](#92-การสร้างสัญญาณและเปิดดู-waveform-ด้วย-gtkwave)
10. [ระบบการติดตั้งและการพัฒนาต่อยอด (Packaging, Extensibility & Developer Guide)](#10-ระบบการติดตั้งและการพัฒนาต่อยอด)
    - 10.1 [การแพ็กเกจด้วย PyInstaller และ Inno Setup 6](#101-การแพ็กเกจด้วย-pyinstaller-และ-inno-setup-6)
    - 10.2 [คู่มือการเพิ่มสถาปัตยกรรม CPU ใหม่เข้าสู่ระบบ](#102-คู่มือการเพิ่มสถาปัตยกรรม-cpu-ใหม่เข้าสู่ระบบ)
    - 10.3 [คู่มือการเพิ่มอุปกรณ์ MMIO Peripheral ใหม่](#103-คู่มือการเพิ่มอุปกรณ์-mmio-peripheral-ใหม่)

---

## 1. ภาพรวมของระบบและปรัชญาการออกแบบ

**FPGA Studio** ได้รับการพัฒนาขึ้นภายใต้แนวคิด **"Zero-Vivado Barrier, 100% Real Hardware Flow"** เพื่อขจัดปัญหาคอขวดที่ใหญ่ที่สุดของการศึกษาและพัฒนาระบบฝังตัว (Embedded System/CPU Design) บน FPGA คือ:
1. โปรแกรมอย่าง Vivado มีขนาดใหญ่มาก (60–80GB) กินทรัพยากรเครื่องสูง และเปิดใช้งานช้า
2. คอมไพเลอร์ในโปรแกรมจำลองส่วนใหญ่เป็นตัวจำลองเทียม (Fake Assembler) ที่ไม่รองรับมาตรฐานภาษา C/C++ สากล และไม่มี Linker ที่แท้จริง
3. ขาดการเชื่อมโยงอย่างต่อเนื่อง (Continuous Feedback Loop) ระหว่างการเขียนโค้ดซอฟต์แวร์ การดูสถานะรีจิสเตอร์ของ CPU และการเห็นไฟติดบนบอร์ด FPGA จริง

FPGA Studio รวมเอาเครื่องมือคอมไพเลอร์ระดับอุตสาหกรรม (Real GCC Toolchains), ซิมูเลเตอร์ท่อส่งคำสั่งระดับไซเคิล (Cycle-Accurate 5-Stage Pipeline Simulator), เอนจินเร่งความเร็วภาษา Rust, วงจรจำลองบอร์ดเสมือนแบบครบชุด (Interactive Digilent Nexys A7-100T Virtual Board), ระบบสังเคราะห์บิตสตรีมแบบโอเพนซอร์สบน Linux/WSL, และตัวแฟลชฮาร์ดแวร์ผ่าน USB-JTAG มาบรรจุรวมกันเป็นโปรแกรมเดียวที่มีขนาดติดตั้งเพียง 1.76 GB พร้อมใช้งานแบบออฟไลน์ 100%

---

## 2. สถาปัตยกรรม 5-Stage Pipeline เจาะลึก

โปรแกรมรองรับและจำลองสถาปัตยกรรมท่อส่งคำสั่ง **5-Stage Pipeline** ตามแบบฉบับสถาปัตยกรรม RISC คลาสสิก:

```
[ IF: Instruction Fetch ]  --->  [ ID: Instruction Decode ]  --->  [ EX: Execution / ALU ]  --->  [ MEM: Memory Access ]  --->  [ WB: Write Back ]
        │                                  │                                   │                                  │                                 │
     (PC Reg)                      (Regfile Read)                      (ALU / Mul / Div)                    (BRAM Load/Store)               (Regfile Write)
        ▲                                  ▲                                   │                                  │                                 │
        │                                  └────── Forwarding Path 1 ──────────┴────── Forwarding Path 2 ─────────┘                                 │
        └────────────────────────────────────────────── Stall & Hazard Control Unit ◄───────────────────────────────────────────────────────────────┘
```

### 2.1 โครงสร้างฮาร์ดแวร์ Verilog

ในโฟลเดอร์ [`custom_cpus/openmips/`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/custom_cpus/openmips/) มีโครงสร้างโมดูลฮาร์ดแวร์ที่สอดคล้องกับแต่ละ Stage อย่างชัดเจน:

1. **PC Generator (`pc_reg.v`)**:
   * รีจิสเตอร์นับที่อยู่คำสั่ง (Program Counter ขนาด 32 บิต)
   * รองรับสัญญาณ `stall[0]`: ถ้า `stall[0] == 1` ค่า PC จะคงที่ (Stall) ไม่อัปเดตที่อยู่
   * รองรับการ Branch/Jump ผ่านสัญญาณ `branch_flag_i` และ `branch_target_address_i` จาก ID Stage
2. **IF/ID Register (`if_id.v`)**:
   * คั่นระหว่าง Stage Fetch และ Decode ทำงานที่สัญญาณนาฬิกาขาขึ้น (`posedge clk`)
   * ถ้า `stall[1] == 1 && stall[2] == 0`: ส่งสัญญาณ NOP (`32'h00000000`) ไปยัง ID Stage (ใส่ Bubble)
   * ถ้า `stall[1] == 0`: ส่งผ่านค่า `id_pc` และ `id_inst` ไปตามปกติ
3. **Instruction Decoder (`id.v`)**:
   * ถอดรหัส Opcode และ Function Code ของคำสั่ง
   * กำหนดสัญญาณควบคุม: `aluop_o`, `alusel_o`, ที่อยู่รีจิสเตอร์เป้าหมาย `wd_o`, สัญญาณอนุญาตเขียน `wreg_o`
   * ตรวจสอบเงื่อนไขการกระโดด (Branch condition) ทันทีใน Stage นี้ (เช่น `BEQ`, `BNE`, `BGTZ`, `BLEZ`) เพื่อลด Branch Penalty เหลือ 1 ไซเคิล
4. **ID/EX Register (`id_ex.v`)**:
   * คั่นระหว่าง Stage Decode และ Execute
   * บันทึกค่า Operand 1 (`rdata1`), Operand 2 (`rdata2`), `imm`, `wd`, `wreg`, `aluop`, `alusel`
   * มีกลไกเคลียร์ค่าเป็น 0 (Flush/Bubble) เมื่อได้รับคำสั่ง Stall จากคอนโทรลเลอร์
5. **Execution Unit (`ex.v`)**:
   * วงจร ALU 32-bit คำนวณ Arithmetic (`ADD`, `SUB`, `SLT`), Logic (`AND`, `OR`, `XOR`, `NOR`), Shift (`SLL`, `SRL`, `SRA`)
   * **วงจรคูณฮาร์ดแวร์ 32-bit (`ex.v`)**: ใช้วงจรคูณแบบ Signed และ Unsigned คำนวณผลลัพธ์ขนาด 64 บิต ส่งเข้าเก็บในรีจิสเตอร์พิเศษ `HI` และ `LO`
   * **วงจรหารหลายไซเคิล (`div.v`)**: ใช้วงจร Trial Subtraction 32 ไซเคิล ในระหว่างการหารจะส่งสัญญาณ `stallreq_from_ex = 1` เพื่อหยุด Pipeline ชั่วคราว
6. **EX/MEM Register (`ex_mem.v`)**:
   * คั่นระหว่าง Stage Execute และ Memory
   * ส่งผ่านผลลัพธ์ ALU, ข้อมูลที่จะเขียนลงหน่วยความจำ (`mem_data`), ที่อยู่หน่วยความจำ (`mem_addr`), และสถานะการเขียน HI/LO
7. **Memory Access Unit (`mem.v`)**:
   * จัดการคำสั่ง Load/Store: `LW`, `SW`, `LH`, `LHU`, `SH`, `LB`, `LBU`, `SB`
   * มีวงจร Mask และ Byte-Enable จัดการการเข้าถึงข้อมูลแบบ Unaligned (เช่น `LWL`, `LWR`, `SWL`, `SWR`)
   * เชื่อมต่อเข้ากับ Data Memory Bus เพื่อเข้าถึง RAM หรือ MMIO Peripherals
8. **MEM/WB Register (`mem_wb.v`)**:
   * คั่นระหว่าง Stage Memory และ Write Back
   * ส่งผ่านค่าสุดท้ายที่ต้องเขียนลง Register File (`wdata`, `wd`, `wreg`)
9. **Register File (`regfile.v`)**:
   * แถวลำดับรีจิสเตอร์ 32 ตัว ขนาด 32 บิต ($r0 ถึง $r31)
   * มีพอร์ตอ่าน 2 พอร์ต (Read Port 1 & 2) และพอร์ตเขียน 1 พอร์ต (Write Port)
   * $r0 ต่อลงกราวด์ฮาร์ดแวร์ถาวร (Hardwired to Zero) เขียนค่าไม่เข้า อ่านได้ 0 เสมอ
10. **Pipeline Controller (`ctrl.v`)**:
    * รับสัญญาณ `stallreq_from_id` (เกิดจาก Load-Use Hazard)
    * รับสัญญาณ `stallreq_from_ex` (เกิดจาก Multicycle Division)
    * รับสัญญาณ `stallreq_from_dbg` (เกิดจากการกด Pause/Step ในโปรแกรม)
    * ส่งสัญญาณบัสควบคุม `stall[5:0]` ไปสั่งหยุดแต่ละ Stage อย่างเป็นเอกเทศ

---

### 2.2 การจัดการ Pipeline Hazards

#### ก. Data Forwarding (Bypassing)
เกิดขึ้นเมื่อคำสั่งปัจจุบันใน ID Stage จำเป็นต้องอ่านค่าจากรีจิสเตอร์ที่คำสั่งก่อนหน้ากำลังประมวลผลอยู่ (RAW: Read-After-Write Hazard) หากไม่มี Forwarding จะต้องรอจนกว่าคำสั่งก่อนหน้าจะผ่าน WB Stage (เสียเวลา 2–3 ไซเคิล)

ใน [`custom_cpus/openmips/id.v`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/custom_cpus/openmips/id.v) บรรทัดที่ 810–860 ได้ออกแบบวงจร Forwarding แบบขนาน:
1. **EX to ID Forwarding**:
   ```verilog
   if ((ex_wreg_i == 1'b1) && (ex_wd_i == reg1_addr_o) && (reg1_read_o == 1'b1)) begin
       reg1_o <= ex_wdata_i; // ดึงผลลัพธ์จาก EX stage มาใช้ทันที
   end
   ```
2. **MEM to ID Forwarding**:
   ```verilog
   else if ((mem_wreg_i == 1'b1) && (mem_wd_i == reg1_addr_o) && (reg1_read_o == 1'b1)) begin
       reg1_o <= mem_wdata_i; // ดึงผลลัพธ์จาก MEM stage มาใช้ทันที
   end
   ```

#### ข. Load-Use Data Hazard & Stall
ในกรณีที่คำสั่งก่อนหน้าเป็นคำสั่ง `LW` (Load Word) ข้อมูลจะยังไม่พร้อมจนกว่าจะจบ MEM Stage ทำให้ไม่สามารถ Forward มายัง EX Stage ทันทีได้  
โมดูล `id.v` จะตรวจสอบ:
```verilog
assign pre_inst_is_load = (ex_aluop_i == `EXE_LW_OP || ...);
if (pre_inst_is_load && ((ex_wd_i == reg1_addr_o) || (ex_wd_i == reg2_addr_o))) begin
    stallreq_for_reg_loadrelate <= 1'b1; // สั่ง Stall
end
```
เมื่อเกิด Stall สัญญาณ `stall[5:0]` จาก `ctrl.v` จะกลายเป็น `6'b000111` ซึ่งหมายถึง:
* **PC**: หยุดนับค้างไว้ 1 ไซเคิล
* **IF/ID**: ค้างคำสั่งเดิมไว้ 1 ไซเคิล
* **ID/EX**: ส่งสัญญาณ NOP (ใส่ Bubble) เข้าสู่ EX Stage แทน

---

### 2.3 กลไก Branch Delay Slot เทียบกับ Branch Flush

มีความแตกต่างทางสถาปัตยกรรมอย่างมีนัยสำคัญระหว่าง **OpenMIPS** และ **RISC-V**:

| คุณลักษณะ | OpenMIPS (MIPS32) | RISC-V (RV32IM) |
|---|---|---|
| **Branch Penalty** | 0 Cycle (ใช้ประโยชน์จาก Delay Slot) | 1–2 Cycles (เมื่อทายผิด ต้อง Flush) |
| **Delay Slot Execution** | คำสั่งที่อยู่ถัดจาก Branch ในเมมโมรี **จะถูก Execute เสมอ** | **ไม่มี Delay Slot** คำสั่งถัดไปจะไม่ถูก Execute หากเงื่อนไขกระโดดเป็นจริง |
| **Compiler Handling** | คอมไพเลอร์จัดหาคำสั่งที่เป็นอิสระมาใส่หลัง Branch หรือใส่ `nop` | คอมไพเลอร์วางโค้ดตรงไปตรงมา ไม่ต้องใส่ NOP หลัง Branch |
| **ฮาร์ดแวร์ Pipeline** | มีสัญญาณ `is_in_delayslot` ส่งตามท่อส่งคำสั่งเพื่อจัดการข้อยกเว้นและ PC Link | มีสัญญาณ `branch_taken` ส่งสัญญาณ Clear ไปยัง IF/ID register (Flush) |

ในซิมูเลเตอร์ [`core/simulator_engine.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/simulator_engine.py) ตัวแปร `self._mips_delay_target` จะถูกตั้งค่าเมื่อเจอคำสั่ง Jump/Branch บน MIPS เพื่อสั่งให้ซิมูเลเตอร์ประมวลผลคำสั่งใน Delay Slot ก่อน 1 คำสั่ง แล้วจึงกระโดดไปยัง `self.pc_index` ที่แท้จริง

---

### 2.4 ซอฟต์แวร์จำลอง Cycle-Accurate Simulator

ไฟล์แกนหลัก: [`core/simulator_engine.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/simulator_engine.py)

1. **State Retention**:
   * รีจิสเตอร์ 32 บิต: `self.regs = [0] * 32`
   * รีจิสเตอร์พิเศษ MIPS: `self.hi = 0`, `self.lo = 0`
   * หน่วยความจำข้อมูล: `self.dmem = {}` (เก็บเป็น Dictionary โดยคีย์คือ Address 32-bit แบบ Word-aligned `addr & ~3`)
   * ตัวแปรฮาร์ดแวร์บอร์ด: `self.sw_value`, `self.led_value`, `self.seg7_value`, `self.btn_value`, `self.uart_buffer`
2. **Pre-Decoded Operation Cache**:
   * เพื่อความเร็วสูงสุด ซิมูเลเตอร์ไม่ได้ Parse สตริง Assembly ในทุกๆ ไซเคิล แต่จะทำการ Pre-decode รายการคำสั่งทั้งหมดไว้ล่วงหน้า (`self._decoded_ops`) เป็น Tuple ข้อมูล `(op, rd, rs, rt, imm, shamt)`
   * ทำให้การรันแต่ละคำสั่งเป็นเพียงการเรียก Switch-Case ผ่าน Dictionary Lookup ในหน่วยความจำ
3. **การเข้าถึง MMIO แบบ Real-Time**:
   * ทุกครั้งที่มีคำสั่ง `SW` หรือ `SB` ตัวซิมูเลเตอร์จะตรวจสอบว่า Address นั้นตรงกับช่วง MMIO หรือไม่:
     * ถ้าเท่ากับ `0xF0000000`: อัปเดต `self.led_value` ทันที
     * ถ้าเท่ากับ `0xF0000008`: อัปเดต `self.seg7_value` ทันที
     * ถ้าเท่ากับ `0xF0000010`: นำอักขระ ASCII ต่อเข้า `self.uart_buffer` ทันที
     * ถ้าไม่ใช่: เขียนลง `self.dmem` ตามปกติ

---

### 2.5 Rust Native Simulation Acceleration (`fpga_engine_rust.dll`)

ไฟล์แกนหลัก: [`core/rust_accel.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/rust_accel.py)

* เขียนด้วยภาษา Rust เพื่อให้ได้ความเร็วระดับเนทีฟ (Native C-Speed) โดยปราศจากปัญหา Python GIL (Global Interpreter Lock)
* ทำงานผ่าน C-ABI Shared Library (`fpga_engine_rust.dll`) โดยใช้โมดูล `ctypes`:
  ```python
  lib.rust_sim_step_batch(sim_handle, ctypes.c_uint32(cycles))
  ```
* ภายในตัว Rust Engine จำลองหน่วยความจำด้วย Flat Array ขนาดใหญ่ `Vec<u32>` และประมวลผลคำสั่งด้วยฟังก์ชัน `match opcode` ที่ถูก Optimize ด้วย LLVM Vectorization
* ทำให้โปรแกรมสามารถรันซิมูเลชันด้วยความเร็วมากกว่า **50,000,000 ไซเคิลต่อวินาที** สามารถเรนเดอร์ภาพ VGA หรือรันอัลกอริทึมซับซ้อนได้อย่างลื่นไหลแบบ Real-time

---

## 3. ระบบคอมไพเลอร์จริงและท่อส่งภาษา

### 3.1 คอมไพเลอร์ MIPS64 GCC 12.2

โปรแกรมบันเดิลคอมไพเลอร์ `mips64-elf-gcc.exe` ในโฟลเดอร์ `toolchain/mips-gcc/bin/`:

* **คำสั่งและพารามิเตอร์ที่เรียกใช้จริง**:
  ```bash
  mips64-elf-gcc.exe \
      -mabi=32 \
      -march=mips32 \
      -EB \
      -O1 \
      -g \
      -nostdlib \
      -fno-builtin \
      -mno-check-zero-division \
      -mno-branch-likely \
      -I<workspace_dir> \
      -T link.ld \
      start.S main.c \
      -o prog.elf
  ```
* **ความหมายของแต่ละ Flag**:
  * `-mabi=32`: สั่งให้สร้างโค้ดตามมาตรฐาน MIPS O32 ABI (รีจิสเตอร์ขนาด 32 บิต, การส่งอาร์กิวเมนต์ผ่าน `$a0-$a3`)
  * `-march=mips32`: จำกัดชุดคำสั่งให้อยู่ในมาตรฐาน MIPS32 Release 1 (ไม่มีคำสั่ง 64 บิตที่ OpenMIPS ไม่รองรับ)
  * `-EB`: กำหนด Endianness เป็น **Big-Endian** (ไบต์ที่มีค่าสูงสุดอยู่ตำแหน่งที่อยู่ต่ำสุด) ซึ่งตรงกับฮาร์ดแวร์ OpenMIPS
  * `-nostdlib -fno-builtin`: ไม่ลิงก์ C Standard Library ปกติ (เช่น `glibc`) เนื่องจากเป็นการรันบน Bare-Metal ไม่มี OS รองรับ
  * `-mno-check-zero-division`: **สำคัญมาก!** ห้าม GCC สร้างคำสั่งดักการหารด้วยศูนย์ (`teq $reg, $zero, 7`) เพราะคำสั่ง `TEQ` (Trap if Equal) ไม่มีในสเปกของ OpenMIPS ทำให้คอร์แฮงก์
  * `-mno-branch-likely`: ป้องกันไม่ให้ GCC สร้างคำสั่ง Branch Likely (`beql`, `bnel`) ที่จะยกเลิกคำสั่งใน Delay Slot เมื่อเงื่อนไขเป็นเท็จ

---

### 3.2 คอมไพเลอร์ xPack RISC-V GCC 15.2

โปรแกรมบันเดิลคอมไพเลอร์ `riscv-none-elf-gcc.exe` ในโฟลเดอร์ `toolchain/xpack-riscv-none-elf-gcc-15.2.0-1/bin/`:

* **คำสั่งและพารามิเตอร์ที่เรียกใช้จริง**:
  ```bash
  riscv-none-elf-gcc.exe \
      -march=rv32im \
      -mabi=ilp32 \
      -O1 \
      -g \
      -nostdlib \
      -fno-builtin \
      -I<workspace_dir> \
      -T link.ld \
      start.S main.c \
      -o prog.elf
  ```
* **ความหมายของแต่ละ Flag**:
  * `-march=rv32im`: ระบุชุดคำสั่ง Base Integer (I) + Integer Multiplication & Division (M) ขนาด 32 บิต
  * `-mabi=ilp32`: กำหนด Data Model เป็น `int`, `long`, `pointer` ขนาด 32 บิต ส่งอาร์กิวเมนต์ผ่านรีจิสเตอร์ `a0-a7`
  * `-O1`: คอมไพล์แบบ Optimize ระดับ 1 เพื่อตัดโค้ดส่วนเกินออก แต่ยังคงรักษาโครงสร้างคำสั่งให้อ่านและดีบักได้ง่าย

---

### 3.3 Bare-Metal Startup Routine และ Linker Script

เพื่อให้โค้ดภาษา C สามารถรันได้โดยตรงบน CPU ทันทีที่จ่ายไฟเข้าบอร์ด จำเป็นต้องมีกระบวนการเริ่มต้นระบบ (Bootstrapping):

#### โค้ด Assembly เริ่มต้นระบบ (`start.S`) สำหรับ MIPS:
```assembly
.section .text.init
.set noreorder
.global _start
_start:
    lui $sp, 0x8001      # กำหนด Stack Pointer ชี้ไปที่จุดสูงสุดของ RAM (0x80010000)
    jal main             # กระโดดเรียกฟังก์ชัน main() ของภาษา C
    nop                  # Branch Delay Slot
_halt:
    j _halt              # หาก main() สิ้นสุด ให้วนลูปอยู่ที่นี่ ป้องกัน CPU เตลิด
    nop
```

#### โค้ด Assembly เริ่มต้นระบบ (`start.S`) สำหรับ RISC-V:
```assembly
.section .text.init
.global _start
_start:
    lui sp, 0x80010      # sp = 0x80010000
    call main            # เรียก main()
_halt:
    j _halt              # ลูปหยุดการทำงาน
```

#### สคริปต์การจัดสรรหน่วยความจำ (`link.ld`):
```ld
ENTRY(_start)
SECTIONS {
    . = 0x00000000;      /* ตำแหน่งเริ่มต้นของ Instruction ROM */
    .text : {
        *(.text.init)    /* วางโค้ด _start เป็นคำสั่งแรกสุดที่ 0x00000000 */
        *(.text*)
    }
    . = 0x80000000;      /* ตำแหน่งเริ่มต้นของ Data RAM (BRAM) */
    .data : ALIGN(4) {
        *(.rodata*)      /* ตัวแปรคงที่ (Constants) และข้อความสตริง */
        *(.srodata*)
        *(.data*)        /* ตัวแปร Global / Static ที่มีค่าเริ่มต้น */
        *(.sdata*)
    }
    .bss : ALIGN(4) {
        *(.bss*)         /* ตัวแปร Global / Static ที่ไม่มีค่าเริ่มต้น (เป็น 0) */
        *(.sbss*)
        *(COMMON)
    }
}
```

---

### 3.4 การดึงข้อมูลส่วน Data (`.data`) และ BRAM Initialization

ในโปรแกรมภาษา C บ่อยครั้งที่มีการประกาศข้อมูลเริ่มต้น เช่น:
```c
static const int font_table[] = { 0x3F, 0x06, 0x5B, 0x4F };
```
ข้อมูลเหล่านี้ไม่ได้อยู่ในคำสั่ง CPU แต่อยู่ใน Section `.data` หรือ `.rodata` ซึ่ง GCC จะจัดวางไว้ที่ตำแหน่ง `0x80000000` ตาม Linker Script

ใน [`core/gcc_toolchain.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/gcc_toolchain.py) บรรทัดที่ 444–461 โปรแกรมใช้ `objcopy` สกัดข้อมูลออกมา:
```python
objcopy_exe -O binary -j .data prog.elf data.bin
```
จากนั้นอ่านข้อมูลเป็นไบต์ และจัดให้อยู่ในรูปเวิร์ด 32 บิต (`Big-Endian` สำหรับ MIPS และ `Little-Endian` สำหรับ RISC-V) เก็บไว้ในตัวแปร Dictionary `init_dmem`:
```python
init_dmem[0x80000000 + off] = w_val
```
เมื่อโหลดซอฟต์แวร์เข้าสู่บอร์ดเสมือน ค่าเหล่านี้จะถูกเขียนลงใน RAM ที่ตำแหน่ง `0x80000000` อัตโนมัติ ทำให้โปรแกรมสามารถเข้าถึงตัวแปร Static/Global ได้ถูกต้องสมบูรณ์

---

### 3.5 ระบบ In-Memory LRU Compile Cache

ไฟล์แกนหลัก: [`core/gcc_toolchain.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/gcc_toolchain.py) บรรทัดที่ 42–65

* ทุกครั้งที่ผู้ใช้พิมพ์โค้ด หากต้องรัน Subprocess ของ GCC บ่อยๆ จะทำให้เกิดความหน่วง (I/O Disk Latency ประมาณ 200–500ms ต่อครั้ง)
* โปรแกรมได้สร้างระบบแคชแบบ **Least Recently Used (LRU)**:
  ```python
  cache_key = (hash(c_code), opt_level, is_cpp)
  if cache_key in _COMPILER_CACHE_MIPS:
      return _COMPILER_CACHE_MIPS[cache_key]
  ```
* หากคีย์ตรงกับข้อมูลที่มีในแคช โปรแกรมจะส่งผลลัพธ์ Opcode กลับไปอัปเดตหน้าจอทันทีภายในเวลา **0 มิลลิวินาที** โดยไม่มีการเรียกดิสก์หรือรันโปรเซสใหม่

---

### 3.6 Direct 32-Bit Assembler & Disassembler

ไฟล์แกนหลัก: [`core/assembler.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/assembler.py), [`core/disassembler.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/disassembler.py)

รองรับการแปลงและถอดรหัสรูปแบบคำสั่งตามบิตฟิลด์อย่างแม่นยำ:

#### รูปแบบคำสั่ง MIPS32:
* **R-Type**: `opcode[31:26] | rs[25:21] | rt[20:16] | rd[15:11] | shamt[10:6] | funct[5:0]`
* **I-Type**: `opcode[31:26] | rs[25:21] | rt[20:16] | immediate[15:0]`
* **J-Type**: `opcode[31:26] | target_address[25:0]`

#### รูปแบบคำสั่ง RISC-V RV32I:
* **R-Type**: `funct7[31:25] | rs2[24:20] | rs1[19:15] | funct3[14:12] | rd[11:7] | opcode[6:0]`
* **I-Type**: `imm[31:20] | rs1[19:15] | funct3[14:12] | rd[11:7] | opcode[6:0]`
* **S-Type**: `imm[31:25] | rs2[24:20] | rs1[19:15] | funct3[14:12] | imm[4:0] | opcode[6:0]`
* **B-Type**: `imm[12|10:5] | rs2[24:20] | rs1[19:15] | funct3[14:12] | imm[4:1|11] | opcode[6:0]`
* **U-Type**: `imm[31:12] | rd[11:7] | opcode[6:0]`
* **J-Type**: `imm[20|10:1|11|19:12] | rd[11:7] | opcode[6:0]`

---

### 3.7 Syntax Transpiler สำหรับภาษา Python และ Rust

ไฟล์แกนหลัก: [`core/transpiler.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/transpiler.py)

ช่วยให้นักเรียนหรือผู้เริ่มต้นสามารถเขียนโค้ดภาษาชั้นสูง (High-Level Language) ควบคุมฮาร์ดแวร์ FPGA ได้โดยไม่ต้องมีความรู้ภาษา C หรือ Assembly:

1. **Python Transpiler (`transpile_python_to_c`)**:
   * ใช้ไลบรารี `ast` ของ Python ในการแยกโครงสร้างคำสั่ง (Abstract Syntax Tree)
   * แปลงลูป `while True:` หรือ `for i in range(10):` ให้กลายเป็น `while(1)` หรือ `for(int i=0; i<10; i++)`
   * แปลงคำสั่ง `print("...")` เป็นการเขียนข้อมูลอักขระเรียงไบต์ลงรีจิสเตอร์ `UART_TX` (`0xF0000010`)
   * แปลงตัวแปรฮาร์ดแวร์ เช่น `LED = 0xFF` เป็น `(*(volatile int*)0xF0000000) = 0xFF;`
2. **Rust Transpiler (`transpile_rust_to_c`)**:
   * แปลงรูปแบบภาษา Rust ยอดนิยม เช่น `let mut x: u32 = 10;`, `loop { ... }`, `match` ให้กลายเป็นโค้ดภาษา C แบบ Bare-Metal

---

## 4. ระบบการนำเข้าและวิเคราะห์ Custom CPU ของผู้ใช้

ไฟล์แกนหลัก: [`core/hdl_analyzer.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/hdl_analyzer.py), [`ui/pin_assignment_dialog.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/ui/pin_assignment_dialog.py)

ผู้ใช้สามารถนำโมดูล CPU ที่ตนเองออกแบบเองในวิชา Computer Architecture (ไม่ว่าจะเป็น Verilog หรือ VHDL) เข้ามาทดสอบใน FPGA Studio ได้ทันทีผ่านขั้นตอนอัจฉริยะดังนี้:

### 4.1 กลไก HDL Lexer/Parser ใน `hdl_analyzer.py`

1. **การลบความคิดเห็น (Comment Stripping)**:
   * ใช้ Regex ลบทั้ง Block Comments (`/* ... */`) และ Line Comments (`// ...` หรือ `-- ...`)
2. **การรวบรวมและคลี่มาโคร (Macro Resolution)**:
   * ค้นหาคำสั่ง `` `include "define.v" `` หรือค้นหาไฟล์นิยามมาโคร เช่น `define.v`, `params.v`, `*.vh` ในโฟลเดอร์เดียวกัน
   * สร้างตารางสัญลักษณ์มาโคร (Macro Symbol Table) แล้วคลี่นิยามในโค้ดทั้งหมด (เช่น `` `RegBus `` $\rightarrow$ `[31:0]`)
3. **การสกัด Entity / Module Port**:
   * รองรับทั้งไวยากรณ์ **Verilog-95** (ประกาศพอร์ตในวงเล็บ แล้วระบุทิศทางแยกด้านล่าง)
   * รองรับไวยากรณ์ **Verilog-2001 ANSI** (ระบุ `input wire [31:0] name` ในพารามิเตอร์)
   * รองรับไวยากรณ์ **VHDL** (`port ( clk : in std_logic; ... );`)

---

### 4.2 การจำแนกประเภทวงจร

ระบบจะจัดกลุ่มวงจรที่ผู้ใช้นำเข้าเป็น 3 รูปแบบอัตโนมัติ:

1. **Closed Simulation Model / Testbench**:
   * วงจรที่ไม่มีพอร์ตอินพุตหรือเอาต์พุตภายนอกเลย (Entity ว่าง)
   * แจ้งเตือนผู้ใช้ว่าเป็นโมเดลจำลองภายใน ไม่สามารถต่อขาบอร์ด Nexys A7 ได้
2. **Standalone Pure ALU Core**:
   * วงจรที่มีเฉพาะพอร์ตคำนวณ เช่น `alu_op`, `data_a`, `data_b`, `alu_out` โดยไม่มีพอร์ตบัสหน่วยความจำ (`mem_addr`, `mem_wdata`, `mem_we`)
   * ซิมูเลเตอร์จะตัดการเชื่อมต่อกับอุปกรณ์ MMIO (ไม่มีปุ่ม, สวิตช์, หลอดไฟ) และเปิดให้ทดสอบเฉพาะฟังก์ชันทางคณิตศาสตร์ใน Register File
3. **Full SoC CPU (Bus-Connected)**:
   * วงจรที่มีพอร์ตบัสหน่วยความจำสมบูรณ์
   * ซิมูเลเตอร์จะเชื่อมต่อเข้ากับ Nexys A7 Virtual Board เต็มรูปแบบ (ควบคุมไฟ LED, สวิตช์, 7-Segment, UART ได้ครบวงจร)

---

### 4.3 การตรวจจับพอร์ตด้วย Role Patterns

ระบบใช้ Regular Expression ตรวจจับบทบาทของขาพอร์ตอัตโนมัติ:

```python
ROLE_PATTERNS = {
    "clock":     r"^(clk|clock|sys_clk|clk_i|aclk|wb_clk_i|clk_100m)$",
    "reset":     r"^(rst|reset|rst_n|reset_n|nrst|aresetn|clr|rst_i)$",
    "mem_addr":  r"(mem_addr|data_addr|d_addr|wb_adr|bus_addr|m_addr|addr_out|ram_addr|mar)",
    "mem_wdata": r"(mem_wdata|data_out|d_dout|wb_dat_o|bus_wdata|ram_data_o|dout|wdata)",
    "mem_rdata": r"(mem_rdata|data_in|d_din|wb_dat_i|bus_rdata|ram_data_i|din|rdata)",
    "mem_we":    r"(mem_we|data_we|wb_we|d_we|memwrite|wr_en|write_en|we|we_o)",
    "direct_led": r"^(led|leds|direct_leds|o_led|led_out)",
    "direct_sw":  r"^(sw|switch|switches|i_sw|sw_in)",
    "direct_btn": r"^(btn|button|buttons|btn_in)",
    "direct_seg": r"^(seg|seven_seg|seg7|sseg|anode|cathode|an)",
    "direct_uart": r"(uart_tx|uart_rx|txd|rxd|serial_tx|serial_rx)",
    "direct_vga":  r"(vga_r|vga_g|vga_b|hsync|vsync|vga)"
}
```

---

### 4.4 โครงสร้างไฟล์ Manifest (`cpu_manifest.json`) และการ Binding ขาบอร์ด

เมื่อผู้ใช้เปิดหน้าต่าง **Hardware Pin & MMIO Planner** (`PinAssignmentDialog`) ผู้ใช้สามารถปรับเปลี่ยนการจับคู่ระหว่างขาฮาร์ดแวร์กับสัญญาณใน CPU ได้ ข้อมูลจะถูกบันทึกเป็นไฟล์ `cpu_manifest.json` อยู่ในโฟลเดอร์ของ CPU นั้นๆ:

```json
{
  "cpu_name": "My_Custom_RISCV",
  "arch": "riscv",
  "is_standalone_alu": false,
  "top_module": "riscv_rv32i",
  "port_mapping": {
    "clock": "clk",
    "reset": "rst",
    "mem_addr": "wb_adr_o",
    "mem_wdata": "wb_dat_o",
    "mem_rdata": "wb_dat_i",
    "mem_we": "wb_we_o"
  },
  "mmio_addresses": {
    "led": "0xF0000000",
    "sw": "0xF0000004",
    "seg7": "0xF0000008",
    "btn": "0xF000000C",
    "uart_tx": "0xF0000010"
  }
}
```
เมื่อโหลด CPU นี้เข้ามาในบอร์ดเสมือน ซิมูเลเตอร์จะอ่านค่า `port_mapping` และ `mmio_addresses` จากไฟล์นี้ไปตั้งค่า Router ของบัสทันที ทำให้ CPU แปลกใหม่ที่มีรูปแบบพอร์ตไม่เหมือนใครก็สามารถควบคุมบอร์ด Nexys A7 เสมือนได้ทันที

---

## 5. ระบบสร้างโค้ดฮาร์ดแวร์และแพ็กเกจ Vivado SoC

ไฟล์แกนหลัก: [`core/hdl_generator.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/hdl_generator.py)

เมื่อผู้ใช้เขียนโปรแกรมและทดสอบบนบอร์ดเสมือนจนพอใจแล้ว โปรแกรมสามารถสร้างแพ็กเกจฮาร์ดแวร์ที่พร้อมนำไปเปิดใน Xilinx Vivado หรือสังเคราะห์ลงชิปจริงได้ทันที

### 5.1 การสร้าง ROM สำหรับ VHDL, Verilog และ Vivado COE

โปรแกรมจะแปลงค่า Machine Code ในตารางออกมาเป็นไฟล์เมมโมรี:
* **VHDL ROM (`instruction_memory.vhd`)**: สร้างโมดูลภาษา VHDL ใช้คำสั่ง `case address is when 0 => instruction <= "001000...";`
* **Verilog ROM (`instruction_memory.v`)**: สร้างโมดูลภาษา Verilog ใช้บล็อก `always @(*) case(address)`
* **Vivado COE (`program.coe`)**: สร้างไฟล์สัมประสิทธิ์สำหรับ Block RAM Generator IP Core:
  ```
  memory_initialization_radix=16;
  memory_initialization_vector=
  20020005,
  2003000a,
  00431020;
  ```

---

### 5.2 โมดูล `nexys_a7_soc_top.v` และการเชื่อมต่อ MMIO Interconnect

สร้างไฟล์ Top-Level Verilog ที่เชื่อมโยงส่วนประกอบทั้งหมดบนชิป Artix-7 เข้าด้วยกัน:
1. **Clock Divider**: แปลงสัญญาณนาฬิกาหลัก 100MHz จากพิน `E3` บนบอร์ด Nexys A7 ลงมาเป็นสัญญาณนาฬิการะบบ 25MHz หรือ 50MHz สำหรับ CPU
2. **Address Decoder (MMIO Bridge)**:
   * ถ้า Address อยู่ในช่วง `0x00000000 - 0x00007FFF`: ต่อเข้า Block RAM Instruction ROM
   * ถ้า Address อยู่ในช่วง `0x80000000 - 0x8000FFFF`: ต่อเข้า Block RAM Data RAM
   * ถ้า Address เท่ากับ `0xF0000000`: ต่อเข้า Register ควบคุม 16 User LEDs (`LED[15:0]`)
   * ถ้า Address เท่ากับ `0xF0000004`: อ่านสถานะสวิตช์เลื่อน 16 ตัว (`SW[15:0]`)
   * ถ้า Address เท่ากับ `0xF0000008`: ต่อเข้าโมดูล Multiplexed 7-Segment Controller
   * ถ้า Address เท่ากับ `0xF0000010`: ต่อเข้าโมดูลฮาร์ดแวร์ UART Transmitter (115200 baud)

---

### 5.3 วงจร Live Hardware RAM Bootloader (`uart_prog_loader.v`)

นี่คือหนึ่งในฟีเจอร์ที่ทรงพลังที่สุดของ FPGA Studio:
* **ปัญหาเดิม**: ทุกครั้งที่แก้โค้ด C แม้เพียงบรรทัดเดียว วิศวกรจะต้องกดรัน Synthesis, Place & Route ใน Vivado ใหม่ ซึ่งกินเวลา 5–15 นาทีต่อครั้ง
* **ทางแก้ของ FPGA Studio**: ในไฟล์ `nexys_a7_soc_top.v` จะมีโมดูลฮาร์ดแวร์ขนาดเล็กชื่อ `uart_prog_loader.v` ฝังอยู่ร่วมกับ CPU
* **การทำงาน**:
  1. เมื่อผู้ใช้กดปุ่ม `PROG` หรือส่งสัญญาณพิเศษผ่านพอร์ต USB-UART วงจร Bootloader จะส่งสัญญาณ Reset ค้างไว้ที่ CPU ชั่วคราว
  2. วงจร Bootloader จะสลับบัสหน่วยความจำของ Block RAM มาเป็นของตนเอง
  3. รับข้อมูลไบนารีของโปรแกรมใหม่ที่ส่งมาจาก FPGA Studio ด้วยความเร็ว 115200 baud แล้วเขียนทับลงใน Block RAM ภายในเวลาเพียง **1–2 วินาที**
  4. ปล่อยสัญญาณ Reset ให้ CPU เริ่มต้นรันโปรแกรมใหม่ทันที  
  **ทำให้สามารถทดสอบโค้ดบนบอร์ดจริงได้รวดเร็วเหมือนกับรันบนซิมูเลเตอร์!**

---

### 5.4 ไฟล์ Physical Constraints (`Nexys-A7-100T-Master.xdc`)

สร้างไฟล์กำหนดขา FPGA มาตรฐานตรงตามคู่มือของ Digilent Nexys A7:
* Clock 100MHz: Pin `E3` (IOSTANDARD LVCMOS33)
* 16 LEDs: Pins `H17`, `K15`, `J13`, `N14`, `R18`, `V17`, `U17`, `U16`, `V16`, `T15`, `U14`, `T16`, `V15`, `V14`, `V12`, `P14`
* 16 Switches: Pins `J15`, `L16`, `M13`, `R15`, `R17`, `T18`, `U18`, `R13`, `T8`, `U8`, `R16`, `T13`, `H6`, `U12`, `U11`, `V10`
* 7-Segment Anodes (AN0–AN7): Pins `J17`, `J18`, `T9`, `J14`, `P14`, `T14`, `K2`, `U13`
* 7-Segment Cathodes (CA–CG, DP): Pins `T10`, `R10`, `K16`, `K13`, `P15`, `T11`, `L18`, `H15`
* UART TX & RX: Pin `D4` (TX) และ Pin `C4` (RX)
* CPU Reset: Pin `C12` (Active-Low)

---

## 6. ระบบสังเคราะห์ Bitstream

### 6.1 WSL Local Synthesis ผ่าน openXC7

ไฟล์แกนหลัก: [`core/wsl_synthesis.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/wsl_synthesis.py)

FPGA Studio มีระบบสังเคราะห์วงจรเป็นไฟล์ Bitstream (`.bit`) โดยสมบูรณ์ในเครื่องตนเองโดยไม่ต้องติดตั้ง Vivado ผ่านเครื่องมือ Open-Source EDA ที่รันบน **Windows Subsystem for Linux (WSL)**:

```
[ Verilog Source Files ]  ───►  [ Yosys Synthesis ]  ───►  [ soc.json Netlist ]
                                                                 │
[ Nexys-A7-Master.xdc ]   ───►  [ nextpnr-xilinx ]   ◄───────────┘
                                       │
                                [ soc.fasm Floorplan ]
                                       │
                                [ fasm2frames & xc7frames2bit ]
                                       │
                                       ▼
                          [ nexys_a7_<cpu>.bit (Final Bitstream) ]
```

---

### 6.2 การแปลง Path ระหว่าง Windows และ Linux

เนื่องจากโปรแกรมรันบน Windows แต่เอนจินการสังเคราะห์รันอยู่ภายใน Linux Container ของ WSL ฟังก์ชัน `win_path_to_wsl_path` ใน `wsl_synthesis.py` จะทำหน้าที่แปลงไดเรกทอรีอัตโนมัติ:
```python
def win_path_to_wsl_path(win_path: str) -> str:
    abs_p = os.path.abspath(win_path)
    drive = abs_p[0].lower() # e.g. "c"
    rest = abs_p[2:].replace("\\", "/") # e.g. "/Users/poswe/..."
    return f"/mnt/{drive}{rest}"
```
ทำให้การส่งคำสั่งและอ่านไฟล์ล็อกทำงานประสานกันอย่างไร้รอยต่อ

---

### 6.3 สคริปต์การสังเคราะห์ภายใน WSL (`build_wsl.sh`)

ขั้นตอนการทำงานที่ถูกรันภายใน WSL โดยอัตโนมัติ:
1. **Yosys Synthesis**:
   ```bash
   yosys -p "
       read_verilog -I rtl_cpu nexys_a7_soc_top.v uart_prog_loader.v rtl_cpu/*.v;
       hierarchy -top nexys_a7_soc_top;
       synth_xilinx -top nexys_a7_soc_top -family xc7 -json soc.json
   "
   ```
2. **nextpnr-xilinx Place & Route**:
   ```bash
   nextpnr-xilinx \
       --chipdb /opt/openxc7/chipdb/xc7a100tcsg324.bin \
       --xdc Nexys-A7-100T-Master.xdc \
       --json soc.json \
       --fasm soc.fasm \
       --ignore-loops \
       --timing-allow-fail \
       --force
   ```
3. **Bitstream Assembly**:
   ```bash
   fasm2frames --part xc7a100tcsg324-1 --db-root /opt/openxc7/share/nextpnr/prjxray-db/artix7 soc.fasm soc.frames
   xc7frames2bit --part_name xc7a100tcsg324-1 --part_file /opt/openxc7/part.yaml --frm_file soc.frames --output_file nexys_a7_cpu.bit
   ```

---

### 6.4 Xilinx Vivado CLI Batch Mode Synthesis

หากเครื่องของผู้ใช้มีการติดตั้ง Xilinx Vivado อยู่แล้ว ตัวโปรแกรมจะตรวจจับพาธของ `vivado.bat` อัตโนมัติ และสามารถสั่งรันในโหมด Batch เบื้องหลังโดยไม่ต้องเปิด GUI ของ Vivado ให้หนักเครื่อง:
```bash
vivado.bat -mode batch -nojournal -nolog -source build_vivado_project.tcl
```

---

### 6.5 Cloud Synthesis Pipeline ผ่าน GitHub Actions

ไฟล์แกนหลัก: [`core/cloud_synthesis.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/cloud_synthesis.py)

สำหรับผู้ใช้ที่มีเครื่องคอมพิวเตอร์สเปกต่ำ ไม่สามารถลงทั้ง Vivado หรือ WSL ได้ โปรแกรมมีระบบแพ็กไฟล์โปรเจกต์เป็น ZIP แล้วส่งคำสั่งผ่าน GitHub Actions API เพื่อให้เซิร์ฟเวอร์คลาวด์บนอินเทอร์เน็ตรัน Vivado สังเคราะห์ Bitstream ให้ แล้วดาวน์โหลดไฟล์ `.bit` ที่เสร็จสมบูรณ์กลับลงมายังเครื่องของผู้ใช้โดยอัตโนมัติ

---

## 7. ระบบโปรแกรมฮาร์ดแวร์จริงและตัวจัดการไดรเวอร์ USB

ไฟล์แกนหลัก: [`core/fpga_programmer.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/fpga_programmer.py)

### 7.1 ปัญหาไดรเวอร์ FTDI บน Windows และการแก้ปัญหาด้วย Zadig

บนบอร์ด Digilent Nexys A7-100T จะมีชิปสะพานต่อพ่วง USB ของบริษัท FTDI คือรุ่น **FT2232H** (Dual USB UART/FIFO IC, Vendor ID: `0x0403`, Product ID: `0x6010`):
* **Channel A (Interface 0)**: เชื่อมต่อเข้ากับพอร์ต JTAG ของชิป FPGA Artix-7 (ใช้สำหรับดาวน์โหลดบิตสตรีม)
* **Channel B (Interface 1)**: เชื่อมต่อเข้ากับขา UART TX/RX ของชิป FPGA (ใช้สำหรับ Serial Terminal)

#### ปัญหาไดรเวอร์บน Windows:
โดยค่าเริ่มต้น Windows จะติดตั้งไดรเวอร์ FTDI Virtual COM Port (VCP) หรือ D2XX ซึ่งเครื่องมือดาวน์โหลดโอเพนซอร์สมาตรฐานอย่าง **`openFPGALoader`** (ที่พัฒนาบนไลบรารี `libusb` / `libftdi`) จะไม่สามารถเข้าถึง Channel A ผ่าน API มาตรฐานได้

#### วิธีแก้ปัญหาด้วย Zadig:
โปรแกรมได้บันเดิลยูทิลิตี้ [`toolchain/zadig.exe`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/toolchain/zadig.exe) ไว้ในตัวติดตั้ง พร้อมคู่มือแนะนำ:
1. เปิด Zadig เลือกเมนู **Options $\rightarrow$ List All Devices**
2. เลือกอุปกรณ์ **"Digilent USB Device (Interface 0)"**
3. เปลี่ยนไดรเวอร์เป็น **WinUSB (v6.1.7600.16385)** หรือ **libusbK** แล้วกดปุ่ม **Replace Driver**
4. **ข้อควรระวัง**: ห้ามเปลี่ยนไดรเวอร์ของ Interface 1 เพราะต้องคงไว้เป็นพอร์ตเสมือน (COM Port) สำหรับการรับส่งข้อมูล UART!

---

### 7.2 การทำงานของ `openFPGALoader`

เมื่อผู้ใช้กดปุ่ม **แฟลชลงบอร์ด FPGA** ในหน้าต่าง Programmer โปรแกรมจะดำเนินการดังนี้:
1. **สแกนค้นหาอุปกรณ์ USB (`--scan-usb`)**:
   ```bash
   openFPGALoader.exe --scan-usb
   ```
   อ่านรหัสประจำตัวของบอร์ด Digilent และดึง Serial Number ของชิป FTDI ออกมา เพื่อให้เจาะจงบอร์ดได้ถูกต้องแม้เครื่องจะต่อพอร์ต USB หลายเส้น
2. **แฟลชลงหน่วยความจำ SRAM ของ FPGA (`-m`)**:
   ```bash
   openFPGALoader.exe -c digilent --usb-serial-num <SERIAL> -m nexys_a7_openmips.bit
   ```
   ใช้เวลาแฟลชเพียง **2–4 วินาที** ไฟสถานะ **DONE LED** (สีเขียว) บนบอร์ด Nexys A7 จะติดสว่างทันที บอร์ดจะเริ่มทำงานทันที
3. **การแฟลชถาวรลงหน่วยความจำ SPI Flash (`-f`)**:
   หากต้องการให้โปรแกรมยังคงอยู่แม้ปิดสวิตช์ไฟของบอร์ด โปรแกรมรองรับคำสั่งแฟลชลงชิป Quad-SPI Flash (Spansion S25FL128S ขนาด 16MB) บนบอร์ด Nexys A7

---

### 7.3 การสั่งงาน Digilent Adept CLI (`djtgcfg`)

หากเครื่องของผู้ใช้ได้ติดตั้งโปรแกรม Digilent Adept Runtime ไว้ โปรแกรม FPGA Studio จะตรวจพบ `djtgcfg.exe` อัตโนมัติ และสามารถสั่งแฟลชผ่านไดรเวอร์เนทีฟของ Digilent ได้โดยไม่ต้องสลับไดรเวอร์ผ่าน Zadig:
```bash
djtgcfg.exe prog -d NexysA7 -i 0 -f nexys_a7_openmips.bit
```

---

### 7.4 การส่งโปรแกรมความเร็วสูงผ่าน USB-UART Bootloader

เมื่อบอร์ด Nexys A7 ถูกแฟลชด้วย SoC Bitstream ของ FPGA Studio เรียบร้อยแล้ว ในการเปลี่ยนโค้ด C ครั้งต่อไป ผู้ใช้ไม่จำเป็นต้องแตะต้อง JTAG เลย:
* โปรแกรมจะใช้โมดูล Python `serial` เชื่อมต่อไปยังพอร์ต COM ของบอร์ด (เช่น `COM3`) ที่ Baud rate `115200`
* ส่งคำสั่ง Handshake และส่งไบนารีขนาด 1KB–16KB เข้าไปเก็บใน Block RAM ของบอร์ดโดยตรงผ่านวงจร `uart_prog_loader.v` ภายในเวลาเสี้ยววินาที

---

### 7.5 คลังบิตสตรีมสำเร็จรูป (Pre-bundled Bitstreams)

ในโฟลเดอร์ [`bitstreams/`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/bitstreams/) มีไฟล์บิตสตรีมที่คอมไพล์สำเร็จแล้วพร้อมใช้งาน:
* `nexys_a7_openmips.bit`: SoC เต็มรูปแบบสำหรับ OpenMIPS (พร้อม MMIO, 7-Segment, UART, BRAM)
* `nexys_a7_riscv.bit`: SoC เต็มรูปแบบสำหรับ RISC-V RV32IM
* `nexys_a7_gpio_demo.bit`: วงจรทดสอบสวิตช์และไฟ LED
* `nexys_a7_factory_demo.bit`: โปรแกรมทดสอบโรงงานของ Digilent Nexys A7

---

## 8. ระบบฮาร์ดแวร์จำลองและ Memory-Mapped I/O

ไฟล์แกนหลัก: [`ui/board_panels.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/ui/board_panels.py)

### 8.1 ตารางแผนที่หน่วยความจำฉบับเต็ม

| ช่วงตำแหน่ง (Address Range) | ขนาด (Size) | อุปกรณ์ฮาร์ดแวร์ / หน้าที่การทำงาน | การเข้าถึง (R/W) |
|---|---|---|---|
| `0x0000_0000` – `0x0000_7FFF` | 32 KB | **Instruction ROM (Block RAM)**: เก็บโค้ดคำสั่งที่โปรแกรมจะดึงไปรัน | Read Only |
| `0x8000_0000` – `0x8000_FFFF` | 64 KB | **Data RAM (Block RAM)**: พื้นที่เก็บตัวแปร `.data`, `.bss`, Heap และ Stack | Read / Write |
| `0xF000_0000` | 4 Bytes | **16 User LEDs (`LED[15:0]`)**: เขียนค่าเพื่อสั่งเปิด/ปิดไฟ LED สีเขียว 16 ดวง | Read / Write |
| `0xF000_0004` | 4 Bytes | **16 Slide Switches (`SW[15:0]`)**: อ่านค่าตำแหน่งของสวิตช์เลื่อน 16 ตัว | Read Only |
| `0xF000_0008` | 4 Bytes | **8-Digit 7-Segment Display**: ส่งรหัสตัวเลขหรือ Segment บิตเพื่อแสดงผล | Read / Write |
| `0xF000_000C` | 4 Bytes | **5 Pushbuttons & Reset**: อ่านสถานะปุ่ม (Bit 0: BTNC, 1: BTNU, 2: BTNL, 3: BTNR, 4: BTND) | Read Only |
| `0xF000_0010` | 4 Bytes | **UART Serial Data**: เขียนตัวอักษรเพื่อส่งออกพอร์ต TX / อ่านเพื่อรับข้อมูล RX | Read / Write |
| `0xF000_0014` | 4 Bytes | **UART Status Register**: บิต 0 = RX Ready (มีข้อมูลเข้า), บิต 1 = TX Ready (พอร์ตว่าง) | Read Only |
| `0xF000_0018` | 4 Bytes | **2 RGB LEDs**: ควบคุมค่าสี PWM ของหลอด LD16 และ LD17 | Read / Write |
| `0xFF00_0000` – `0xFF04_AFFF` | ~300 KB | **VGA Video Framebuffer**: ข้อมูลสีของหน้าจอภาพ 640x480 พิกเซล | Read / Write |

---

### 8.2 การทำงานของวิดเจ็ต Interactive Board

* **16 DIP Switches**: ผู้ใช้สามารถใช้เมาส์คลิกเพื่อสลับตำแหน่งของแต่ละสวิตช์ได้แบบอิสระ ค่าบิต `0` หรือ `1` จะถูกอัปเดตลงในหน่วยความจำตำแหน่ง `0xF0000004` ทันที เมื่อโปรแกรม C สั่ง `int val = SWITCH;` จะได้ค่าสถานะตามจริง
* **16 User LEDs**: ออกแบบ Canvas ให้มีแสงเรือง (Glow Effect) สีเขียวสดใส (`#1DB954`) เมื่อบิตนั้นๆ เป็น 1
* **ปุ่มกด 5 ทิศทาง (Pushbuttons)**: มีปุ่มเสมือนจัดวางเป็นรูปกากบาทตรงตามตำแหน่งบนบอร์ด Nexys A7 รองรับทั้งการคลิกธรรมดา และการคลิกค้าง (Latch Mode) เพื่อทดสอบสัญญาณ Interrupt

---

### 8.3 วงจรถอดรหัส 8-Digit Multiplexed 7-Segment Display

บอร์ด Digilent Nexys A7 มีหลอด 7-Segment ทั้งหมด 8 หลัก โดยใช้สัญญาณควบคุมร่วมกัน (Multiplexed):
* ในระดับฮาร์ดแวร์: มีสัญญาณ Cathodes 8 ขา (`CA-CG, DP`) และ Anodes 8 ขา (`AN0-AN7`)
* ในซิมูเลเตอร์: รองรับ 2 โหมด:
  1. **Dynamic BCD / Value Mode**: เมื่อโปรแกรมเขียนตัวเลข เช่น `120` หรือ `0x00000078` ลงที่ `0xF0000008` ซิมูเลเตอร์จะทำการแปลงเป็นเลขฐานสิบและกระจายแสดงผลบนหน้าจอ 8 หลักให้โดยอัตโนมัติ
  2. **Raw Cathode/Anode Mode**: ผู้ใช้สามารถเขียนรูปแบบบิตควบคุมขีด Segment ทีละเส้นได้ตามต้องการ

---

### 8.4 ระบบ UART Terminal Console

* มีวิดเจ็ตหน้าต่างดำแบบ Real-time ติดตั้งอยู่ใต้แผงควบคุมบอร์ด
* เมื่อซอฟต์แวร์บน CPU ทำการรันคำสั่ง `printf("Hello World\n");` ตัวคอมไพเลอร์จะแปลงคำสั่งให้วนลูปเขียนค่า ASCII ทีละตัวอักษรลงในตำแหน่ง `0xF0000010`
* ตัวซิมูเลเตอร์จะดึงตัวอักษรออกมาแสดงผลในคอนโซลแบบสดๆ ทันที พร้อมแสดงเวลาประทับ (Timestamp)

---

### 8.5 ระบบจำลองสัญญาณภาพ VGA 640x480 Virtual Framebuffer

* รองรับการเปิดหน้าต่างจำลองจอภาพ VGA ภายนอกขนาด 640x480 พิกเซล
* หน่วยความจำ Framebuffer เริ่มต้นที่ตำแหน่ง `0xFF000000`
* ซิมูเลเตอร์เรนเดอร์พิกเซลด้วยความเร็วสูงผ่าน Tkinter PhotoImage หรือ Rust Native Engine ทำให้สามารถเขียนเกมหรือแสดงผลกราฟิกได้เสมือนต่อจอ Monitor ผ่านพอร์ต VGA จริงของบอร์ด

---

## 9. ระบบ Co-Simulation และการวิเคราะห์รูปคลื่นสัญญาณ

ไฟล์แกนหลัก: [`core/rtl_cosim.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/rtl_cosim.py), [`ui/rtl_verify_dialog.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/ui/rtl_verify_dialog.py)

### 9.1 RTL Verification ด้วย Icarus Verilog

FPGA Studio บันทึกคอมไพเลอร์ฮาร์ดแวร์ **Icarus Verilog (`iverilog.exe`)** และรันไทม์ **`vvp.exe`** ไว้ในตัวติดตั้ง:
1. เมื่อผู้ใช้คลิกเมนู **"ตรวจสอบความถูกต้อง RTL (Co-Simulation)"** โปรแกรมจะนำซอร์สโค้ด Verilog ทั้งหมดของ CPU มารวมกับ Testbench อัตโนมัติ
2. ใส่โค้ด Machine Code ที่คอมไพล์ได้จากโปรแกรม C ของผู้ใช้ลงใน Testbench Memory
3. สั่งคอมไพล์วงจรระดับฮาร์ดแวร์:
   ```bash
   iverilog.exe -o sim.vvp -I custom_cpus/openmips custom_cpus/openmips/*.v tb.v
   vvp.exe sim.vvp
   ```

---

### 9.2 การสร้างสัญญาณและเปิดดู Waveform ด้วย GTKWave

1. ในระหว่างที่ `vvp` ทำงาน คำสั่งระบบ `$dumpfile("waveform.vcd");` และ `$dumpvars;` จะทำการบันทึกสถานะของสายไฟและรีจิสเตอร์ทุกเส้นใน CPU ทุกๆ พิโกวินาที (picosecond) ลงในไฟล์ **VCD (Value Change Dump)**
2. เมื่อซิมูเลชันเสร็จสิ้น FPGA Studio จะสั่งเปิดโปรแกรม **GTKWave (`gtkwave.exe`)** ที่บันเดิลมาในโฟลเดอร์ `toolchain/gtkwave/bin/` ขึ้นมาแสดงผลโดยอัตโนมัติ
3. ผู้ใช้สามารถกางดูสัญญาณ Clock, Reset, PC, ALU Result, ค่าใน Register File $r1–$r31, และไฟแสดงสถานะของแต่ละ Pipeline Stage ได้อย่างละเอียดลึกซึ้ง

---

## 10. ระบบการติดตั้งและการพัฒนาต่อยอด

### 10.1 การแพ็กเกจด้วย PyInstaller และ Inno Setup 6

* **PyInstaller (`FPGA Studio.spec`)**:
  * รวมสคริปต์ภาษา Python ทั้งหมดให้เป็นไบนารี `FPGA Studio.exe`
  * บรรจุ DLL พิเศษ `core/fpga_engine_rust.dll`
  * กำหนด `datas` ดึงโฟลเดอร์ `toolchain`, `custom_cpus`, `bitstreams`, `fonts` เข้าสู่โฟลเดอร์แอปพลิเคชัน
* **Inno Setup 6 (`installer.iss`)**:
  * สร้างตัวติดตั้งระดับมืออาชีพ `FPGA_Studio_Setup_v4.2.exe` ขนาด 1.76 GB
  * ใช้อัลกอริทึมบีบอัดข้อมูลแบบ **Solid LZMA2**
  * สิทธิ์การติดตั้ง: `PrivilegesRequired=lowest` ทำให้ผู้ใช้สามารถติดตั้งได้ทันทีโดยไม่ต้องใช้สิทธิ์ Administrator ของ Windows

---

### 10.2 คู่มือการเพิ่มสถาปัตยกรรม CPU ใหม่เข้าสู่ระบบ

หากนักพัฒนาต้องการเพิ่มสถาปัตยกรรม CPU ตัวใหม่ (เช่น ARM Cortex-M0 หรือ 6502):
1. **เพิ่มโฟลเดอร์ฮาร์ดแวร์**: สร้างโฟลเดอร์ใน `custom_cpus/<cpu_name>/` วางไฟล์ Verilog/VHDL ทั้งหมด
2. **สร้าง Manifest**: สร้างไฟล์ `cpu_manifest.json` ระบุพอร์ต Clock, Reset, Memory Bus ตามแบบฟอร์มในบทที่ 4.4
3. **เพิ่มตรรกะใน Disassembler**: เพิ่มฟังก์ชันถอดรหัสบิตคำสั่งใน [`core/disassembler.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/disassembler.py)
4. **เพิ่มโหมดใน UI**: เพิ่มตัวเลือกในเมนู CPU ของ [`ui/studio_window.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/ui/studio_window.py)

---

### 10.3 คู่มือการเพิ่มอุปกรณ์ MMIO Peripheral ใหม่

หากต้องการเพิ่มอุปกรณ์ใหม่ (เช่น พอร์ต I2C, SPI, หรือ Audio PWM Buzzer):
1. **กำหนด Address**: ระบุตำแหน่งที่อยู่ใน [`config/catalog.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/config/catalog.py) เช่น `#define BUZZER (*(volatile int*)0xF0000020)`
2. **อัปเดตซิมูเลเตอร์**: ใน [`core/simulator_engine.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/simulator_engine.py) ในฟังก์ชัน `_exec_instruction()` ดักจับ Address `0xF0000020` เมื่อมีคำสั่ง `SW`
3. **สร้างวิดเจ็ตแสดงผล**: ใน [`ui/board_panels.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/ui/board_panels.py) สร้าง Canvas หรือ Label วาดภาพอุปกรณ์ใหม่ และสั่งให้กระพริบหรือส่งเสียงตามค่าที่ส่งมาจาก CPU
4. **อัปเดตไฟล์ Top-Level RTL**: ใน [`core/hdl_generator.py`](file:///C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/core/hdl_generator.py) เพิ่มเงื่อนไขในโมดูล `nexys_a7_soc_top.v` เพื่อส่งสัญญาณออกพินภายนอกของ FPGA ตามที่ต้องการ

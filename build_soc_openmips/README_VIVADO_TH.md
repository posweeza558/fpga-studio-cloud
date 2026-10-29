# ชุดสังเคราะห์ฮาร์ดแวร์ FPGA Studio สำหรับบอร์ด Digilent Nexys A7-100T

แกนประมวลผลที่ส่งออก: **`openmips`** (MIPS)  
จำนวนคำสั่งเริ่มต้นใน ROM: **0 คำสั่ง (32-bit)**

## ไฟล์ในแพ็กเกจนี้
1. `nexys_a7_soc_top.v` — วงจรระดับบนสุด (SoC Top) เชื่อมต่อ CPU, หน่วยความจำ 16KB, สะพาน MMIO, 7-Segment 8 หลัก และ UART 115200
2. `uart_prog_loader.v` — วงจร Bootloader รับโปรแกรมใหม่ผ่านสาย USB-UART (`PROG` protocol) โดยไม่ต้องสังเคราะห์ Bitstream ซ้ำ!
3. `Nexys-A7-100T-Master.xdc` — ไฟล์กำหนดขาพินมาตรฐานของบอร์ด Nexys A7-100T (`xc7a100tcsg324-1`)
4. `rtl_cpu/` — ซอร์สโค้ด Verilog ของ CPU (0 ไฟล์)
5. `program.hex` / `dmem_init.hex` / `program.coe` — ข้อมูลโปรแกรมเริ่มต้นสำหรับ Block/Distributed RAM
6. `build_vivado_project.tcl` — สคริปต์สร้างโปรเจกต์ Vivado อัตโนมัติ

## วิธีนำไปใช้งานบนบอร์ดจริง
1. เปิดโปรแกรม **Xilinx Vivado** แล้วเปิดแถบ **Tcl Console** ด้านล่าง
2. พิมพ์คำสั่ง:
   ```tcl
   cd {C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/build_soc_openmips}
   source build_vivado_project.tcl
   ```
3. กด **Generate Bitstream** แล้ว **Program Device** ลงบอร์ด Nexys A7-100T เพียงครั้งเดียว
4. หลังจากโปรแกรม Bitstream นี้ลงบอร์ดแล้ว คุณสามารถแก้ไขโค้ด C / Assembly ใน **FPGA Studio** แล้วกดปุ่ม **"อัปโหลด USB"** เพื่อส่งคำสั่งชุดใหม่เข้าสู่บอร์ดผ่านสาย USB-UART (115200 baud) ได้ทันทีโดยไม่ต้องรอ Synthesis ใหม่!

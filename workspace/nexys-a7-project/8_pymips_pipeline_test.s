# [โหมด PyMIPS] ทดสอบ Data Hazard (RAW) & Forwarding ตามโมเดลอาจารย์
# คำนวณใน 5-Stage Pipeline (IF, ID, EX, MEM, WB)
add $r1, $r2, $r3    # r1 = r2 + r3
sub $r5, $r1, $r4    # r5 = r1 - r4 (Forwarding ดึงค่า r1 จาก Stage EX มาทันที)
sw $r5, 4($r0)       # เขียนผลลัพธ์ r5 ลง Data Memory ช่องที่ 4
lw $r6, 4($r0)       # อ่านผลลัพธ์กลับมาใส่ r6

import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

with open('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/workspace/nexys-a7-project/nck_7seg_demo.c', 'r', encoding='utf-8') as f:
    c_code = f.read()

lines = c_code.splitlines()

asm, ins = compile_with_real_mips_gcc(c_code, opt_level="-O1")
for i, x in enumerate(ins):
    s = x.get('src_line')
    txt = lines[s - 1].strip() if s and 0 < s <= len(lines) else ""
    print(f"[{i:02d}] PC: {x['pc']} | src: {str(s):4} | code: {txt:40} | ASM: {x['asm']}")

import sys
sys.path.append('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio')
from core.gcc_toolchain import compile_with_real_mips_gcc

with open('C:/Users/poswe/.gemini/antigravity/scratch/mips-fpga-plan/fpga_studio/workspace/nexys-a7-project/nck_7seg_demo.c', 'r', encoding='utf-8') as f:
    code = f.read()

lines = code.splitlines()

asm, ins = compile_with_real_mips_gcc(code, opt_level="-O1")
print(f"Total instructions: {len(ins)}")
for i, x in enumerate(ins):
    s_line = x.get("src_line")
    c_text = lines[s_line - 1].strip() if s_line and 0 < s_line <= len(lines) else ""
    s_str = str(s_line) if s_line is not None else "None"
    print(f"[{i:02d}] PC: {x['pc']} (byte: {x['pc_int']:04x}) | src_line: {s_str:4} | code: {c_text:30} | ASM: {x['asm']}")

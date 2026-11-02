import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

def main():
    with open('workspace/nexys-a7-project/4_fibonacci.c', 'r', encoding='utf-8') as f:
        code = f.read()
    # Change delay to 5 cycles so simulation doesn't take forever
    code = code.replace("6000000", "5")
    asm, instrs = compile_with_real_mips_gcc(code)
    with open('tb_imem.hex', 'w') as f:
        for i in instrs:
            f.write(f"{i['word']:08x}\n")
    print(f"Generated tb_imem.hex for Fibonacci with {len(instrs)} words")

if __name__ == '__main__':
    main()

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gcc_toolchain import compile_with_real_mips_gcc

def main():
    with open('workspace/nexys-a7-project/4_fibonacci.c', 'r', encoding='utf-8') as f:
        code = f.read()
    asm, instrs = compile_with_real_mips_gcc(code)
    for i in instrs:
        print(f"{i['pc']}: {i['hex']}  {i['asm']}")

if __name__ == '__main__':
    main()

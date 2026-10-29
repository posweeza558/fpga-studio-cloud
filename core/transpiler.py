# -*- coding: utf-8 -*-
"""
Language Transpilers (C Subset -> Assembly, Python -> C, Rust -> C) & Real-Time Syntax Checker
"""

import re
import ast


def check_code_syntax(raw_code, ext):
    """
    Validate syntax of Assembly (.s/.asm), Python (.py), C (.c), C++ (.cpp), or Rust (.rs).
    Returns (error_line_number, error_message) or (None, "").
    """
    if not raw_code.strip():
        return None, ""
    lines = raw_code.splitlines()

    if ext in (".s", ".asm"):
        valid_ops = {
            "lui", "auipc", "addi", "addiu", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai",
            "add", "addu", "sub", "subu", "sll", "sllv", "slt", "sltu", "xor", "srl", "srlv", "sra", "srav",
            "or", "and", "nor", "mul", "mulh", "mulhsu", "mulhu", "mult", "multu", "div", "divu", "rem", "remu",
            "mflo", "mfhi", "mthi", "mtlo", "blez", "bgtz", "bltz", "bgez",
            "lw", "sw", "lb", "lbu", "lh", "lhu", "sb", "sh",
            "beq", "bne", "blt", "bge", "bltu", "bgeu", "beqz", "bnez", "ble", "bgt", "bleu", "bgtu",
            "jal", "jalr", "j", "jr", "call", "nop", "li", "mv", "move", "ret",
            "seqz", "snez", "sltz", "sgtz", "neg", "negu", "not",
            "syscall", "ecall", "break", "ebreak", "scall", "sbreak",
        }
        for idx, ln in enumerate(lines, 1):
            clean = ln.split("#")[0].split("//")[0].strip()
            if not clean or clean.endswith(":") or clean.startswith("."):
                continue
            if ":" in clean:
                clean = clean.split(":", 1)[1].strip()
            if not clean:
                continue
            op = clean.replace(",", " ").split()[0].lower()
            if op not in valid_ops:
                return idx, f"Line {idx}: Unknown Assembly instruction '{op}'"
        return None, ""

    if ext == ".py":
        try:
            ast.parse(raw_code)
        except SyntaxError as e:
            ln_no = e.lineno or 1
            return ln_no, f"Line {ln_no}: Python SyntaxError: {e.msg}"
        return None, ""

    if ext in (".c", ".cpp", ".rs"):
        brace_balance = 0
        last_open_line = 1
        paren_balance = 0
        last_paren_line = 1
        for idx, ln in enumerate(lines, 1):
            clean = re.sub(r"//.*", "", ln)
            for ch in clean:
                if ch == "{":
                    brace_balance += 1
                    last_open_line = idx
                elif ch == "}":
                    brace_balance -= 1
                    if brace_balance < 0:
                        return idx, f"Line {idx}: Unexpected closing brace '}}'"
                elif ch == "(":
                    paren_balance += 1
                    last_paren_line = idx
                elif ch == ")":
                    paren_balance -= 1
                    if paren_balance < 0:
                        return idx, f"Line {idx}: Unexpected closing parenthesis ')'"
        if brace_balance > 0:
            return last_open_line, f"Line {last_open_line}: Unclosed brace '{{' (missing '}}')"
        if paren_balance > 0:
            return last_paren_line, f"Line {last_paren_line}: Unclosed parenthesis '(' (missing ')')"

        if ext == ".rs":
            for idx, ln in enumerate(lines, 1):
                s = re.sub(r"//.*", "", ln).strip()
                if not s or s.startswith("#") or s.endswith("{") or s.endswith("}"):
                    continue
                if not s.endswith(";"):
                    return idx, f"Line {idx}: Rust statement missing semicolon ';'"

    return None, ""


def compile_c_to_asm(c_code, arch="riscv"):
    """
    Built-in Fast C-Subset Transpiler:
    Translates embedded C (MMIO, arithmetic, while/if, printf, return) into
    complete, clean RISC-V or MIPS assembly including return value & halt loop.
    """
    is_rv = (arch == "riscv")
    r_base = "a5" if is_rv else "$t7"
    r_tmp1 = "a4" if is_rv else "$t6"
    r_tmp2 = "a3" if is_rv else "$t5"
    r_ret  = "a0" if is_rv else "$v0"
    r_zero = "x0" if is_rv else "$zero"

    var_pool = ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t0", "t1", "t2"] if is_rv else \
               ["$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7", "$t0", "$t1", "$t2"]
    var_map = {}

    def get_var_reg(vname):
        if vname not in var_map:
            var_map[vname] = var_pool[len(var_map) % len(var_pool)]
        return var_map[vname]

    mmio_offsets = {
        "LED": 0, "LED_ADDR": 0,
        "SWITCH": 4, "SW": 4, "SWITCH_ADDR": 4,
        "SEG7": 8, "SEG7_ADDR": 8,
        "BTN": 12, "BUTTON": 12,
        "UART_TX": 16, "UART_RX": 20,
    }

    for m in re.finditer(r"#define\s+(\w+)\s+.*?(0x[0-9a-fA-F]+|\d+)", c_code):
        name, val_s = m.group(1), m.group(2)
        val = int(val_s, 0)
        if val >= 0xF0000000:
            mmio_offsets[name] = val - 0xF0000000

    code = re.sub(r"//.*", "", c_code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"#.*", "", code)
    m_main = re.search(r"main\s*\([^)]*\)\s*\{(.*)\}", code, flags=re.S)
    body = m_main.group(1) if m_main else code

    # Only initialize MMIO base register if the code actually uses hardware MMIO devices
    uses_mmio = any(re.search(rf"\b{re.escape(k)}\b", body) for k in mmio_offsets) or bool(re.search(r"\b(?:printf|puts|print)\b", body))

    asm = ["main:"]
    if uses_mmio:
        if is_rv:
            asm.append("lui a5, 0xF0000")
        else:
            asm.append("lui $t7, 0xF000")

    lbl_counter = [0]
    block_stack = []
    has_infinite_loop = False
    has_return = False

    def new_lbl(prefix="L"):
        lbl_counter[0] += 1
        return f"{prefix}_{lbl_counter[0]}"

    def load_operand(tok, target_reg):
        tok = tok.strip()
        if tok in mmio_offsets:
            off = mmio_offsets[tok]
            asm.append(f"lw {target_reg}, {off}({r_base})")
            return target_reg
        if re.match(r"^-?(0x[0-9a-fA-F]+|\d+)$", tok):
            val = int(tok, 0)
            asm.append(f"addi {target_reg}, {r_zero}, {val}")
            return target_reg
        return get_var_reg(tok)

    tokens = re.findall(r"(?:while|if|else)\s*(?:\([^)]*\))?\s*\{?|\}|[^;{}]+;", body)

    for raw_t in tokens:
        t = raw_t.strip()
        if not t:
            continue

        m_w = re.match(r"while\s*\(([^)]+)\)\s*(?:\{|;)?", t)
        if m_w:
            cond = m_w.group(1).strip()
            l_start = new_lbl("loop")
            l_end = new_lbl("endloop")
            asm.append(f"{l_start}:")
            if cond in ("1", "true"):
                has_infinite_loop = True
                if t.endswith(";"):
                    asm.append(f"j {l_start}")
                    continue
                block_stack.append(("while_inf", l_start, None))
            else:
                m_c = re.match(r"(\w+)\s*(==|!=|<|>=|>|<=)\s*(\w+)", cond)
                if m_c:
                    lhs, op, rhs = m_c.groups()
                    r1 = load_operand(lhs, r_tmp1)
                    r2 = load_operand(rhs, r_tmp2)
                    if is_rv:
                        inv = {"==": "bne", "!=": "beq", "<": "bge", ">=": "blt"}.get(op, "beq")
                        asm.append(f"{inv} {r1}, {r2}, {l_end}")
                    else:
                        asm.append(f"beq {r1}, {r2}, {l_end}")
                if t.endswith(";"):
                    asm.append(f"j {l_start}")
                    asm.append(f"{l_end}:")
                    continue
                block_stack.append(("while_cond", l_start, l_end))
            continue

        m_if = re.match(r"if\s*\(([^)]+)\)\s*\{?", t)
        if m_if:
            cond = m_if.group(1).strip()
            l_skip = new_lbl("skip_if")
            m_c = re.match(r"(\w+)\s*(==|!=|<|>=)\s*([-\w]+)", cond)
            if m_c:
                lhs, op, rhs = m_c.groups()
                r1 = load_operand(lhs, r_tmp1)
                r2 = load_operand(rhs, r_tmp2)
                if is_rv:
                    inv = {"==": "bne", "!=": "beq", "<": "bge", ">=": "blt"}.get(op, "bne")
                    asm.append(f"{inv} {r1}, {r2}, {l_skip}")
                else:
                    inv = "bne" if op == "==" else "beq"
                    asm.append(f"{inv} {r1}, {r2}, {l_skip}")
            else:
                r1 = load_operand(cond, r_tmp1)
                asm.append(f"beq {r1}, {r_zero}, {l_skip}")
            block_stack.append(("if", l_skip, None))
            continue

        if t == "}":
            if block_stack:
                btype, l1, l2 = block_stack.pop()
                if btype == "while_inf":
                    asm.append(f"j {l1}")
                elif btype == "while_cond":
                    asm.append(f"j {l1}")
                    asm.append(f"{l2}:")
                elif btype == "if":
                    asm.append(f"{l1}:")
            continue

        stmt = t.rstrip(";").strip()
        if not stmt:
            continue

        m_ret = re.match(r"^return(?:\s+(.+))?$", stmt)
        if m_ret:
            ret_expr = (m_ret.group(1) or "0").strip()
            # If return expression has a binary operator (e.g. return 4 + 5), treat as assignment to r_ret
            m_ret_bin = re.match(r"^([-\w]+)\s*(\+|-|\^|\||&|<<|>>|\*|<)\s*([-\w]+)$", ret_expr)
            if m_ret_bin:
                stmt = f"{r_ret} = {ret_expr}"
                has_return = True
            elif re.match(r"^-?(0x[0-9a-fA-F]+|\d+)$", ret_expr):
                has_return = True
                asm.append(f"addi {r_ret}, {r_zero}, {int(ret_expr, 0)}")
                asm.append("_halt:")
                asm.append("j _halt")
                continue
            else:
                has_return = True
                rv = get_var_reg(ret_expr)
                asm.append(f"addi {r_ret}, {rv}, 0")
                asm.append("_halt:")
                asm.append("j _halt")
                continue

        m_pr = re.match(r"^(?:printf|puts|print)\s*\(\s*\"([^\"]*)\"", stmt)
        if m_pr:
            raw_str = m_pr.group(1).replace("\\n", "\n").replace("\\t", "\t")
            for ch in raw_str:
                ascii_code = ord(ch)
                asm.append(f"addi {r_tmp1}, {r_zero}, {ascii_code}")
                asm.append(f"sw {r_tmp1}, 16({r_base})")
            continue

        m_inc = re.match(r"^(\w+)(\+\+|--)$", stmt)
        if m_inc:
            v, op = m_inc.groups()
            delta = 1 if op == "++" else -1
            if v in mmio_offsets:
                off = mmio_offsets[v]
                asm.append(f"lw {r_tmp1}, {off}({r_base})")
                asm.append(f"addi {r_tmp1}, {r_tmp1}, {delta}")
                asm.append(f"sw {r_tmp1}, {off}({r_base})")
            else:
                rv = get_var_reg(v)
                asm.append(f"addi {rv}, {rv}, {delta}")
            continue

        m_comp = re.match(r"^(\w+)\s*(\+=|-=)\s*(.+)$", stmt)
        if m_comp:
            v, cop, rhs = m_comp.groups()
            op_ch = "+" if cop == "+=" else "-"
            stmt = f"{v} = {v} {op_ch} {rhs}"

        # Support bare arithmetic expression without assignment (e.g. "4 + 5" or "a + b")
        m_bare_bin = re.match(r"^([-\w]+)\s*(\+|-|\^|\||&|<<|>>|\*|<)\s*([-\w]+)$", stmt)
        if m_bare_bin and not stmt.startswith(f"{r_ret} ="):
            stmt = f"{r_ret} = {stmt}"

        m_asgn = re.match(r"^(?:(?:unsigned|signed|volatile|int|uint32_t|char|short|long)\s+)*(\$?\w+)\s*=\s*(.+)$", stmt)
        if m_asgn:
            lhs, rhs = m_asgn.group(1).strip(), m_asgn.group(2).strip()
            is_mmio_dst = lhs in mmio_offsets
            if is_mmio_dst:
                dst_reg = r_tmp1
            elif lhs == r_ret or lhs.startswith("$"):
                dst_reg = lhs
            else:
                dst_reg = get_var_reg(lhs)

            m_bin = re.match(r"^([-\w]+)\s*(\+|-|\^|\||&|<<|>>|\*|<)\s*([-\w]+)$", rhs)
            if m_bin:
                a, op, b = m_bin.groups()
                ra = load_operand(a, r_tmp1)
                if re.match(r"^-?(0x[0-9a-fA-F]+|\d+)$", b) and op in ("+", "-", "&", "|", "^", "<<", ">>"):
                    imm = int(b, 0)
                    if op == "-":
                        imm = -imm
                        op = "+"
                    ins_map = {
                        "+": "addi", "&": "andi", "|": "ori",
                        "^": "xori" if is_rv else "xori",
                        "<<": "slli" if is_rv else "sll",
                        ">>": "srli" if is_rv else "srl"
                    }
                    asm.append(f"{ins_map[op]} {dst_reg}, {ra}, {imm}")
                else:
                    rb = load_operand(b, r_tmp2)
                    if op == "*":
                        if is_rv:
                            asm.append(f"mul {dst_reg}, {ra}, {rb}")
                        else:
                            asm.append(f"mult {ra}, {rb}")
                            asm.append(f"mflo {dst_reg}")
                    elif op == "/":
                        if is_rv:
                            asm.append(f"div {dst_reg}, {ra}, {rb}")
                        else:
                            asm.append(f"div {ra}, {rb}")
                            asm.append(f"mflo {dst_reg}")
                    elif op == "%":
                        if is_rv:
                            asm.append(f"rem {dst_reg}, {ra}, {rb}")
                        else:
                            asm.append(f"div {ra}, {rb}")
                            asm.append(f"mfhi {dst_reg}")
                    else:
                        ins_map = {
                            "+": "add", "-": "sub", "&": "and", "|": "or",
                            "^": "xor",
                            "<<": "sll" if is_rv else "sllv",
                            ">>": "srl" if is_rv else "srlv",
                            "<": "slt"
                        }
                        asm.append(f"{ins_map[op]} {dst_reg}, {ra}, {rb}")
            else:
                if rhs in mmio_offsets:
                    off = mmio_offsets[rhs]
                    asm.append(f"lw {dst_reg}, {off}({r_base})")
                elif re.match(r"^-?(0x[0-9a-fA-F]+|\d+)$", rhs):
                    val = int(rhs, 0)
                    asm.append(f"addi {dst_reg}, {r_zero}, {val}")
                else:
                    rs = get_var_reg(rhs)
                    asm.append(f"addi {dst_reg}, {rs}, 0")

            if is_mmio_dst:
                off = mmio_offsets[lhs]
                asm.append(f"sw {dst_reg}, {off}({r_base})")

    while block_stack:
        btype, l1, l2 = block_stack.pop()
        if btype == "while_inf":
            asm.append(f"j {l1}")
        elif btype == "while_cond":
            asm.append(f"j {l1}")
            asm.append(f"{l2}:")
        elif btype == "if":
            asm.append(f"{l1}:")

    if not has_infinite_loop:
        if not asm or not asm[-1].endswith("_halt"):
            asm.append("_halt:")
            asm.append("j _halt")

    return asm


def transpile_python_to_c(py_code):
    """Transpile MicroPython / Python Hardware Subset (.py) into Bare-Metal C."""
    c_lines = [
        "#define LED     (*(volatile int*)0xF0000000)",
        "#define SWITCH  (*(volatile int*)0xF0000004)",
        "#define SEG7    (*(volatile int*)0xF0000008)",
        "#define BTN     (*(volatile int*)0xF000000C)",
        "int main() {",
    ]
    declared_vars = {"LED", "SWITCH", "SEG7", "BTN"}
    indent_stack = [0]

    for raw in py_code.splitlines():
        line = raw.split("#")[0].rstrip()
        if not line.strip():
            continue
        stripped = line.lstrip()
        if stripped.startswith(("import ", "from ")):
            continue
        indent = len(line) - len(stripped)

        while len(indent_stack) > 1 and indent < indent_stack[-1]:
            indent_stack.pop()
            c_lines.append("    " * len(indent_stack) + "}")

        pad = "    " * len(indent_stack)
        if stripped in ("while True:", "while 1:"):
            c_lines.append(f"{pad}while (1) {{")
            indent_stack.append(indent + 4)
        elif stripped.startswith("while ") and stripped.endswith(":"):
            cond = stripped[6:-1].strip()
            c_lines.append(f"{pad}while ({cond}) {{")
            indent_stack.append(indent + 4)
        elif stripped.startswith("if ") and stripped.endswith(":"):
            cond = stripped[3:-1].strip()
            c_lines.append(f"{pad}if ({cond}) {{")
            indent_stack.append(indent + 4)
        elif stripped.startswith("print(") and stripped.endswith(")"):
            inner = stripped[6:-1].strip()
            if inner.startswith("'") and inner.endswith("'"):
                inner = '"' + inner[1:-1] + '\\n"'
            elif inner.startswith('"') and inner.endswith('"') and not inner.endswith('\\n"'):
                inner = inner[:-1] + '\\n"'
            c_lines.append(f"{pad}printf({inner});")
        elif "=" in stripped and not stripped.startswith(("==", "!=", "<=", ">=")):
            m = re.match(r"^(\w+)\s*([+\-]?=)\s*(.+)$", stripped)
            if m:
                var, op, expr = m.groups()
                if var not in declared_vars and op == "=":
                    declared_vars.add(var)
                    c_lines.append(f"{pad}int {var} = {expr};")
                else:
                    c_lines.append(f"{pad}{var} {op} {expr};")
        else:
            c_lines.append(f"{pad}{stripped};")

    while len(indent_stack) > 1:
        indent_stack.pop()
        c_lines.append("    " * len(indent_stack) + "}")

    c_lines.append("    return 0;")
    c_lines.append("}")
    return "\n".join(c_lines)


def transpile_rust_to_c(rs_code):
    """Transpile Bare-Metal Rust Subset (.rs) into Bare-Metal C."""
    body = rs_code
    body = re.sub(r"#!\[[^\]]*\]", "", body)
    body = re.sub(r"\bfn\s+main\s*\(\s*\)", "int main()", body)
    body = re.sub(r"\bloop\s*\{", "while (1) {", body)
    body = re.sub(r"\blet\s+mut\s+(\w+)\s*(?::\s*\w+)?\s*=", r"int \1 =", body)
    body = re.sub(r"\blet\s+(\w+)\s*(?::\s*\w+)?\s*=", r"int \1 =", body)
    body = re.sub(r"\bprintln!\s*\(", "printf(", body)
    header = (
        "#define LED     (*(volatile int*)0xF0000000)\n"
        "#define SWITCH  (*(volatile int*)0xF0000004)\n"
        "#define SEG7    (*(volatile int*)0xF0000008)\n"
        "#define BTN     (*(volatile int*)0xF000000C)\n"
    )
    return header + "\n" + body


RV_TO_MIPS_ABI = {
    "zero": "$zero",
    "ra": "$ra",
    "sp": "$sp",
    "gp": "$gp",
    "tp": "$k0",
    "t0": "$t0", "t1": "$t1", "t2": "$t2",
    "s0": "$s0", "s1": "$s1",
    "a0": "$a0", "a1": "$a1", "a2": "$a2", "a3": "$a3",
    "a4": "$t4", "a5": "$t5", "a6": "$t6", "a7": "$t7",
    "s2": "$s2", "s3": "$s3", "s4": "$s4", "s5": "$s5",
    "s6": "$s6", "s7": "$s7", "s8": "$s8", "s9": "$fp",
    "s10": "$v0", "s11": "$v1",
    "t3": "$t3", "t4": "$t8", "t5": "$t9", "t6": "$at",
}


def translate_rv_ins_to_mips(ins_list):
    """
    Translate compiled RV32 machine instructions from Real GCC into authentic MIPS-I instructions
    with MIPS ABI registers ($zero, $ra, $sp, $s0, $t0, etc.) and true MIPS 32-bit machine code.
    Expands multiply/divide into hardware mult/div + mflo/mfhi, recalculates all branch offsets,
    fuses 32-bit constants into lui+ori (16-bit), and resolves J/JAL targets.
    """
    from core.assembler import assemble_mips

    # Step 1: Scan all branch/jump target addresses and function symbols to place anchor labels
    target_pcs = set()
    sym_to_pc = {}
    for ins in ins_list:
        pc_int = ins.get("pc_int", 0)
        sym = ins.get("sym_name", "")
        if sym:
            sym_to_pc[sym] = pc_int
            target_pcs.add(pc_int)

        m_hex = re.search(r"<(0x[0-9a-fA-F]+)>", ins.get("asm", ""))
        if m_hex:
            target_pcs.add(int(m_hex.group(1), 16))
        m_j = re.search(r"\b(?:j|jal)\s+(?:[a-z0-9]+,\s*)?(0x[0-9a-fA-F]+)", ins.get("asm", ""))
        if m_j:
            target_pcs.add(int(m_j.group(1), 16))

    mips_asm_lines = []
    skip_indices = set()

    for i, ins in enumerate(ins_list):
        if i in skip_indices:
            continue

        pc_int = ins.get("pc_int", 0)
        sym = ins.get("sym_name", "")
        if sym:
            mips_asm_lines.append(f"{sym}:")
        if pc_int in target_pcs:
            mips_asm_lines.append(f"_L_{pc_int:04X}:")
        if pc_int == 0x0000 and not sym:
            mips_asm_lines.append("_start:")
        elif pc_int == 0x0008 and not sym:
            mips_asm_lines.append("_halt:")

        asm = ins.get("asm", "")
        def repl_reg(m):
            r = m.group(1).lower()
            return RV_TO_MIPS_ABI.get(r, f"${r}")
        m_asm = re.sub(r"\b(zero|ra|sp|gp|tp|t[0-6]|s[0-9]|s1[0-1]|a[0-7]|x[0-9]|x[1-2][0-9]|x3[0-1]|fp)\b", repl_reg, asm)

        # 1. 32-bit Constant Loading & lui / auipc translation for MIPS-I 16-bit architecture
        m_u = re.match(r"^\s*(lui|auipc)\s+([$a-z0-9]+),\s*(0x[0-9a-fA-F]+|\d+)", m_asm)
        if m_u:
            u_op = m_u.group(1).lower()
            dst_reg = m_u.group(2)
            raw_imm = int(m_u.group(3), 0)
            val_high = ((pc_int + (raw_imm << 12)) & 0xFFFFFFFF) if u_op == "auipc" else ((raw_imm << 12) & 0xFFFFFFFF)
            # Check if next instruction in ins_list is addi dst_reg, dst_reg, simm
            fused = False
            if i + 1 < len(ins_list) and ins_list[i+1].get("pc_int") not in target_pcs:
                next_asm = ins_list[i+1].get("asm", "")
                next_m = re.sub(r"\b(zero|ra|sp|gp|tp|t[0-6]|s[0-9]|s1[0-1]|a[0-7]|x[0-9]|x[1-2][0-9]|x3[0-1]|fp)\b", repl_reg, next_asm)
                m_addi = re.match(r"^\s*addi\s+([$a-z0-9]+),\s*([$a-z0-9]+),\s*(-?0x[0-9a-fA-F]+|-?\d+)", next_m)
                if m_addi and m_addi.group(1) == dst_reg and m_addi.group(2) == dst_reg:
                    simm12 = int(m_addi.group(3), 0)
                    val32 = (val_high + simm12) & 0xFFFFFFFF
                    u16 = (val32 >> 16) & 0xFFFF
                    l16 = val32 & 0xFFFF
                    mips_asm_lines.append(f"lui {dst_reg}, 0x{u16:04X}")
                    if l16 != 0:
                        mips_asm_lines.append(f"ori {dst_reg}, {dst_reg}, 0x{l16:04X}")
                    skip_indices.add(i + 1)
                    fused = True
            if not fused:
                u16 = (val_high >> 16) & 0xFFFF
                l16 = val_high & 0xFFFF
                mips_asm_lines.append(f"lui {dst_reg}, 0x{u16:04X}")
                if l16 != 0:
                    mips_asm_lines.append(f"ori {dst_reg}, {dst_reg}, 0x{l16:04X}")
            continue

        # Handle jalr with optional non-zero offset before generic regex rewrites
        m_jalr_full = re.match(r"^\s*jalr\s+([$a-z0-9]+),\s*(-?0x[0-9a-fA-F]+|-?\d+)\(([$a-z0-9]+)\)", m_asm)
        if m_jalr_full:
            j_rd, j_off_s, j_rs = m_jalr_full.group(1), m_jalr_full.group(2), m_jalr_full.group(3)
            j_off = int(j_off_s, 0)
            target_r = j_rs
            if j_off != 0:
                mips_asm_lines.append(f"addiu $at, {j_rs}, {j_off}")
                target_r = "$at"
            if j_rd == "$zero":
                mips_asm_lines.append(f"jr {target_r}")
            elif j_rd == "$ra":
                mips_asm_lines.append(f"jalr {target_r}")
            else:
                mips_asm_lines.append(f"jalr {j_rd}, {target_r}")
            mips_asm_lines.append("nop")
            continue

        m_asm = re.sub(r"\bslli\b", "sll", m_asm)
        m_asm = re.sub(r"\bsrli\b", "srl", m_asm)
        m_asm = re.sub(r"\bsrai\b", "sra", m_asm)
        m_asm = re.sub(r"\bmv\s+([^,]+),\s*([^,]+)", r"addu \1, \2, $zero", m_asm)
        m_asm = re.sub(r"\bli\s+([^,]+),\s*([-\w]+)", r"addiu \1, $zero, \2", m_asm)
        m_asm = re.sub(r"\bneg\s+([^,]+),\s*([^,]+)", r"subu \1, $zero, \2", m_asm)
        m_asm = re.sub(r"\bnot\s+([^,]+),\s*([^,]+)", r"nor \1, \2, $zero", m_asm)
        m_asm = re.sub(r"\bret\b", "jr $ra", m_asm)
        m_asm = re.sub(r"\bjalr\s+\$zero,\s*0\(\$ra\)", "jr $ra", m_asm)
        m_asm = re.sub(r"\bjalr\s+\$zero,\s*0\(([^)]+)\)", r"jr \1", m_asm)
        m_asm = re.sub(r"\bjalr\s+\$ra,\s*0\(([^)]+)\)", r"jalr \1", m_asm)

        tgt_lbl = None
        m_tgt = re.search(r"<(0x[0-9a-fA-F]+)>", m_asm)
        if m_tgt:
            t_addr = int(m_tgt.group(1), 16)
            tgt_lbl = f"_L_{t_addr:04X}"
        else:
            for sname, spc in sym_to_pc.items():
                if f"<{sname}>" in m_asm or m_asm.endswith(f" {sname}") or f" {sname} " in m_asm:
                    tgt_lbl = f"_L_{spc:04X}"
                    break

        m_clean = re.sub(r"\s*<[^>]+>", "", m_asm).strip()
        parts = re.split(r"[\s,]+", m_clean, maxsplit=1)
        mnem = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

        if not tgt_lbl and mnem in ("j", "jal") and args:
            m_hex_arg = re.match(r"^0x[0-9a-fA-F]+$", args[-1])
            if m_hex_arg:
                t_addr = int(args[-1], 16)
                tgt_lbl = f"_L_{t_addr:04X}"
            elif args[-1] in sym_to_pc:
                tgt_lbl = f"_L_{sym_to_pc[args[-1]]:04X}"

        if mnem in (".word", "word") and args:
            mips_asm_lines.append(f".word {args[0]}")
            continue

        if mnem in ("sll", "srl", "sra") and len(args) == 3:
            a2 = args[2].strip()
            if a2.startswith("$") or a2 in RV_TO_MIPS_ABI:
                var_op = {"sll": "sllv", "srl": "srlv", "sra": "srav"}[mnem]
                mips_asm_lines.append(f"{var_op} {args[0]}, {args[1]}, {args[2]}")
                continue

        if mnem == "seqz" and len(args) == 2:
            mips_asm_lines.append(f"sltiu {args[0]}, {args[1]}, 1")
            continue
        elif mnem == "snez" and len(args) == 2:
            mips_asm_lines.append(f"sltu {args[0]}, $zero, {args[1]}")
            continue
        elif mnem == "sltz" and len(args) == 2:
            mips_asm_lines.append(f"slt {args[0]}, {args[1]}, $zero")
            continue
        elif mnem == "sgtz" and len(args) == 2:
            mips_asm_lines.append(f"slt {args[0]}, $zero, {args[1]}")
            continue

        # Standard MIPS-I Hardware Multiply & Divide Expansion
        if mnem == "mul" and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            mips_asm_lines.append(f"mult {rs1}, {rs2}")
            mips_asm_lines.append(f"mflo {rd}")
            continue
        elif mnem in ("div", "divu") and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            mips_asm_lines.append(f"{mnem} {rs1}, {rs2}")
            mips_asm_lines.append(f"mflo {rd}")
            continue
        elif mnem in ("rem", "remu") and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            div_op = "div" if mnem == "rem" else "divu"
            mips_asm_lines.append(f"{div_op} {rs1}, {rs2}")
            mips_asm_lines.append(f"mfhi {rd}")
            continue
        elif mnem == "mulh" and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            mips_asm_lines.append(f"mult {rs1}, {rs2}")
            mips_asm_lines.append(f"mfhi {rd}")
            continue
        elif mnem == "mulhu" and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            mips_asm_lines.append(f"multu {rs1}, {rs2}")
            mips_asm_lines.append(f"mfhi {rd}")
            continue
        elif mnem == "mulhsu" and len(args) == 3:
            rd, rs1, rs2 = args[0], args[1], args[2]
            mips_asm_lines.append(f"multu {rs1}, {rs2}")
            mips_asm_lines.append(f"mfhi {rd}")
            mips_asm_lines.append(f"sra $at, {rs1}, 31")
            mips_asm_lines.append(f"and $at, $at, {rs2}")
            mips_asm_lines.append(f"subu {rd}, {rd}, $at")
            continue

        # Branches & Jumps with resolved target labels + OpenMIPS Branch Delay Slot (nop)
        if tgt_lbl:
            if mnem == "beq" and len(args) >= 2:
                mips_asm_lines.append(f"beq {args[0]}, {args[1]}, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "bne" and len(args) >= 2:
                mips_asm_lines.append(f"bne {args[0]}, {args[1]}, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "blt" and len(args) >= 2:
                mips_asm_lines.append(f"slt $at, {args[0]}, {args[1]}")
                mips_asm_lines.append(f"bne $at, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "bge" and len(args) >= 2:
                mips_asm_lines.append(f"slt $at, {args[0]}, {args[1]}")
                mips_asm_lines.append(f"beq $at, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "bltu" and len(args) >= 2:
                mips_asm_lines.append(f"sltu $at, {args[0]}, {args[1]}")
                mips_asm_lines.append(f"bne $at, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "bgeu" and len(args) >= 2:
                mips_asm_lines.append(f"sltu $at, {args[0]}, {args[1]}")
                mips_asm_lines.append(f"beq $at, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "bnez" and len(args) >= 1:
                mips_asm_lines.append(f"bne {args[0]}, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "beqz" and len(args) >= 1:
                mips_asm_lines.append(f"beq {args[0]}, $zero, {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "j":
                mips_asm_lines.append(f"j {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue
            elif mnem == "jal":
                mips_asm_lines.append(f"jal {tgt_lbl}")
                mips_asm_lines.append("nop")
                continue

        mips_asm_lines.append(m_clean)
        if mnem in ("jr", "jalr", "j", "jal", "beq", "bne", "blez", "bgtz", "bltz", "bgez"):
            mips_asm_lines.append("nop")

    mips_out = assemble_mips(mips_asm_lines)
    if mips_out and ins_list and "init_dmem" in ins_list[0]:
        mips_out[0]["init_dmem"] = dict(ins_list[0]["init_dmem"])
    return mips_out


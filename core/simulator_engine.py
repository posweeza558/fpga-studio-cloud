# -*- coding: utf-8 -*-
"""
Pre-Decoded RV32IM / OpenMIPS-32 CPU & Nexys A7 Board Simulator Engine
"""

import re
from core.disassembler import reg_num, MIPS_REG_NAMES

_MEM_OPERAND_RE = re.compile(r"^\s*(-?0x[0-9a-fA-F]+|-?\d+)\(([^)]+)\)\s*$")


class CPUSimulatorEngine:
    """Manages CPU registers, word-aligned Data Memory, MMIO state, and pre-decoded execution."""

    def __init__(self):
        self.pc_index = 0
        self.cycles = 0
        self.regs = [0] * 32
        self.hi = 0
        self.lo = 0
        self.last_alu_out = 0
        self.dmem = {}
        self._init_dmem = {}
        self.sw_value = 0
        self.led_value = 0
        self.seg7_value = 0
        self.btn_value = 0       # Bit 0: BTNC, 1: BTNU, 2: BTNL, 3: BTNR, 4: BTND, 5: RESET
        self.rgb_value = [0, 0]  # LD16, LD17
        self.uart_buffer = ""
        self.uart_rx_queue = []
        self.vga_mode = "colorbars"
        self.vga_buffer = {}
        self.last_error = None
        self._mips_delay_target = None

        # Configurable MMIO Addresses (Default Nexys A7 SoC Map)
        self.mmio_led = 0xF0000000
        self.mmio_sw = 0xF0000004
        self.mmio_seg7 = 0xF0000008
        self.mmio_btn = 0xF000000C
        self.mmio_uart = 0xF0000010
        self.mmio_uart_stat = 0xF0000014
        self.mmio_rgb = 0xF0000018
        self.mmio_vga = 0xFF000000

        # Pre-decoded instruction cache
        self._decoded_ops = []
        self._decoded_source_id = None
        self._decoded_source_len = 0
        self._loaded_code_id = None

    @staticmethod
    def _parse_addr_val(val):
        if isinstance(val, str):
            s = val.strip()
            return int(s, 16) if s.lower().startswith("0x") else int(s, 0)
        return int(val)

    def reset_mmio_map(self):
        self.mmio_led = 0xF0000000
        self.mmio_sw = 0xF0000004
        self.mmio_seg7 = 0xF0000008
        self.mmio_btn = 0xF000000C
        self.mmio_uart = 0xF0000010
        self.mmio_uart_stat = 0xF0000014
        self.mmio_rgb = 0xF0000018
        self.mmio_vga = 0xFF000000

    def set_mmio_map(self, mmio_dict):
        if not mmio_dict:
            return
        try:
            if "led" in mmio_dict:
                self.mmio_led = self._parse_addr_val(mmio_dict["led"])
            elif "led_seg" in mmio_dict:
                self.mmio_led = self._parse_addr_val(mmio_dict["led_seg"])

            if "sw" in mmio_dict:
                self.mmio_sw = self._parse_addr_val(mmio_dict["sw"])

            if "seg7" in mmio_dict:
                self.mmio_seg7 = self._parse_addr_val(mmio_dict["seg7"])
            elif "led_seg" in mmio_dict and "led" not in mmio_dict:
                self.mmio_seg7 = (self.mmio_led + 8) & 0xFFFFFFFF

            if "btn" in mmio_dict:
                self.mmio_btn = self._parse_addr_val(mmio_dict["btn"])
            elif "btn_rgb" in mmio_dict:
                self.mmio_btn = self._parse_addr_val(mmio_dict["btn_rgb"])

            if "uart_tx" in mmio_dict:
                self.mmio_uart = self._parse_addr_val(mmio_dict["uart_tx"])
                if "uart_stat" not in mmio_dict:
                    self.mmio_uart_stat = (self.mmio_uart + 4) & 0xFFFFFFFF

            if "uart_stat" in mmio_dict:
                self.mmio_uart_stat = self._parse_addr_val(mmio_dict["uart_stat"])

            if "rgb" in mmio_dict:
                self.mmio_rgb = self._parse_addr_val(mmio_dict["rgb"])
            elif "btn_rgb" in mmio_dict and "btn" not in mmio_dict:
                self.mmio_rgb = (self.mmio_btn + 12) & 0xFFFFFFFF

            if "vga" in mmio_dict:
                self.mmio_vga = self._parse_addr_val(mmio_dict["vga"])
        except Exception:
            pass

    def reset(self):
        self.pc_index = 0
        self.cycles = 0
        self.regs = [0] * 32
        self.hi = 0
        self.lo = 0
        self.last_alu_out = 0
        self.dmem = dict(self._init_dmem)
        self.led_value = 0
        self.seg7_value = 0
        self.btn_value = 0
        self.rgb_value = [0, 0]
        self.uart_buffer = ""
        self.uart_rx_queue.clear()
        self.vga_buffer.clear()
        self.last_error = None
        self._mips_delay_target = None

    def reset_registers(self):
        self.regs = [0] * 32
        self.hi = 0
        self.lo = 0
        self.pc_index = 0
        self.cycles = 0
        self.last_error = None
        self._mips_delay_target = None

    def toggle_switch_bit(self, bit):
        self.sw_value ^= (1 << bit)

    def set_button(self, bit, pressed=True):
        if pressed:
            self.btn_value |= (1 << bit)
        else:
            self.btn_value &= ~(1 << bit)

    def toggle_button(self, bit):
        self.btn_value ^= (1 << bit)

    def send_uart_input(self, text):
        for ch in text:
            self.uart_rx_queue.append(ord(ch))

    @staticmethod
    def _parse_imm(tok):
        tok = tok.strip()
        if "<" in tok:
            tok = tok.split("<")[0].strip()
        try:
            return int(tok, 16) if tok.lower().startswith(("0x", "-0x")) else int(tok)
        except Exception:
            return 0

    @staticmethod
    def _to_signed(val):
        val = val & 0xFFFFFFFF
        return val - 0x100000000 if (val & 0x80000000) else val

    @classmethod
    def _predecode_instruction(cls, idx, ins):
        """Pre-decode an instruction dictionary once into fast integer fields."""
        asm = ins.get("asm", "").strip()
        word = ins.get("word", 0) & 0xFFFFFFFF
        pc_int = ins.get("pc_int", idx * 4)

        raw_parts = [p.strip() for p in asm.replace(",", " ").split() if p.strip()]
        has_halt_tag = bool(raw_parts and ("_halt" in raw_parts[-1]))
        parts = list(raw_parts)
        if parts and parts[-1].startswith("<") and parts[-1].endswith(">"):
            parts = parts[:-1]

        op = parts[0].lower() if parts else "nop"
        rd = rs1 = rs2 = imm = 0
        use_imm = False
        rv_target = mips_target = None
        rd_label = parts[1] if len(parts) > 1 else "x0"

        if op in ("nop", "fence", "sync", "pref") or (op in (".word", "word") and word == 0):
            return ("nop", op, 0, 0, 0, 0, False, None, None, False, "")

        if op in ("ebreak", "ecall", "syscall", "break"):
            return ("halt", op, 0, 0, 0, 0, False, idx, idx, True, "")

        if op in ("lui", "auipc") and len(parts) >= 3:
            rd = reg_num(parts[1])
            imm = cls._parse_imm(parts[2])
            return ("u", op, rd, pc_int, 0, imm, True, None, None, False, parts[1])

        if op in ("addi", "addiu", "slti", "sltiu", "andi", "ori", "xori", "slli", "srli", "srai") and len(parts) >= 4:
            rd = reg_num(parts[1])
            rs1 = reg_num(parts[2])
            imm = cls._parse_imm(parts[3])
            return ("alu_i", op, rd, rs1, 0, imm, True, None, None, False, parts[1])

        if op in (
            "add", "addu", "sub", "subu", "and", "or", "xor", "nor",
            "slt", "sltu", "mul", "mulh", "mulhu", "mulhsu", "rem", "remu",
            "sll", "srl", "sra", "sllv", "srlv", "srav", "movz", "movn",
        ) and len(parts) >= 4:
            rd = reg_num(parts[1])
            rs1 = reg_num(parts[2])
            p3 = parts[3].strip()
            if op in ("sll", "srl", "sra") and (p3.isdigit() or p3.startswith(("-", "0x", "-0x"))):
                imm = cls._parse_imm(p3) & 0x1F
                use_imm = True
            else:
                rs2 = reg_num(p3)
            return ("alu_r", op, rd, rs1, rs2, imm, use_imm, None, None, False, parts[1])

        if op in ("clz", "clo") and len(parts) >= 3:
            rd = reg_num(parts[1])
            rs1 = reg_num(parts[2])
            return ("alu_r", op, rd, rs1, 0, 0, False, None, None, False, parts[1])

        if op in ("mult", "multu", "madd", "maddu", "msub", "msubu") and len(parts) >= 3:
            rs1 = reg_num(parts[1])
            rs2 = reg_num(parts[2])
            return ("hilo_mul", op, 0, rs1, rs2, 0, False, None, None, False, "")

        if op in ("div", "divu") and len(parts) >= 3:
            if len(parts) >= 4:
                rd = reg_num(parts[1])
                rs1 = reg_num(parts[2])
                rs2 = reg_num(parts[3])
                return ("div3", op, rd, rs1, rs2, 0, False, None, None, False, parts[1])
            rs1 = reg_num(parts[1])
            rs2 = reg_num(parts[2])
            return ("div2", op, 0, rs1, rs2, 0, False, None, None, False, "")

        if op in ("mfhi", "mflo", "mthi", "mtlo") and len(parts) >= 2:
            r = reg_num(parts[1])
            return ("hilo_mv", op, r, r, 0, 0, False, None, None, False, parts[1])

        if op in ("lw", "lh", "lhu", "lb", "lbu") and len(parts) >= 3:
            rd = reg_num(parts[1])
            m = _MEM_OPERAND_RE.match(parts[2])
            if m:
                imm = cls._parse_imm(m.group(1))
                rs1 = reg_num(m.group(2))
                return ("load", op, rd, rs1, 0, imm, True, None, None, False, parts[1])

        if op in ("sw", "sh", "sb") and len(parts) >= 3:
            rs2 = reg_num(parts[1])
            m = _MEM_OPERAND_RE.match(parts[2])
            if m:
                imm = cls._parse_imm(m.group(1))
                rs1 = reg_num(m.group(2))
                return ("store", op, 0, rs1, rs2, imm, True, None, None, False, parts[1])

        if op in ("blez", "bgtz", "bltz", "bgez") and len(parts) >= 3:
            rs1 = reg_num(parts[1])
            if word:
                imm16 = word & 0xFFFF
                if imm16 & 0x8000:
                    imm16 -= 0x10000
                mips_target = idx + 1 + imm16
            else:
                off = cls._parse_imm(parts[2])
                step_idx = (off // 4) if (abs(off) >= 4 and off % 4 == 0) else off
                mips_target = idx + 1 + step_idx
            rv_target = mips_target
            return ("bz", op, 0, rs1, 0, 0, False, rv_target, mips_target, has_halt_tag, "")

        if op in ("beq", "bne", "blt", "bge", "bltu", "bgeu") and len(parts) >= 4:
            rs1 = reg_num(parts[1])
            rs2 = reg_num(parts[2])
            if word:
                b12 = (word >> 31) & 1
                b10_5 = (word >> 25) & 0x3F
                b4_1 = (word >> 8) & 0xF
                b11 = (word >> 7) & 1
                imm13 = (b12 << 12) | (b11 << 11) | (b10_5 << 5) | (b4_1 << 1)
                if imm13 & (1 << 12):
                    imm13 -= (1 << 13)
                rv_target = idx + (imm13 // 4)

                imm16 = word & 0xFFFF
                if imm16 & 0x8000:
                    imm16 -= 0x10000
                mips_target = idx + 1 + imm16
            else:
                off = cls._parse_imm(parts[3])
                step_idx = (off // 4) if (abs(off) >= 4 and off % 4 == 0) else off
                rv_target = idx + step_idx
                mips_target = idx + 1 + step_idx
            return ("branch", op, 0, rs1, rs2, 0, False, rv_target, mips_target, has_halt_tag, "")

        if op == "jal" and len(parts) >= 2:
            rd_rv = reg_num(parts[1]) if len(parts) >= 3 else 1
            if word:
                b20 = (word >> 31) & 1
                b10_1 = (word >> 21) & 0x3FF
                b11 = (word >> 20) & 1
                b19_12 = (word >> 12) & 0xFF
                imm21 = (b20 << 20) | (b19_12 << 12) | (b11 << 11) | (b10_1 << 1)
                if imm21 & (1 << 20):
                    imm21 -= (1 << 21)
                rv_target = idx + (imm21 // 4)
                mips_target = word & 0x03FFFFFF
            else:
                target_arg = parts[2] if len(parts) >= 3 else parts[1]
                off = cls._parse_imm(target_arg)
                step_idx = (off // 4) if (off % 4 == 0) else off
                rv_target = idx + step_idx
                mips_target = (off // 4) if (off >= 4 and off % 4 == 0) else off
            return ("jal", op, rd_rv, 0, 0, 0, False, rv_target, mips_target, has_halt_tag, parts[1])

        if op == "j" and len(parts) >= 2:
            if word:
                b20 = (word >> 31) & 1
                b10_1 = (word >> 21) & 0x3FF
                b11 = (word >> 20) & 1
                b19_12 = (word >> 12) & 0xFF
                imm21 = (b20 << 20) | (b19_12 << 12) | (b11 << 11) | (b10_1 << 1)
                if imm21 & (1 << 20):
                    imm21 -= (1 << 21)
                rv_target = idx + (imm21 // 4)
                mips_target = word & 0x03FFFFFF
            else:
                off = cls._parse_imm(parts[1])
                rv_target = idx + (off // 4 if off % 4 == 0 else off)
                mips_target = (off // 4) if (off >= 4 and off % 4 == 0) else off
            return ("j", op, 0, 0, 0, 0, False, rv_target, mips_target, has_halt_tag, "")

        if op == "jr" and len(parts) >= 2:
            rs1 = reg_num(parts[1])
            return ("jr", op, 0, rs1, 0, 0, False, None, None, False, parts[1])

        if op == "jalr" and len(parts) >= 2:
            if len(parts) >= 3:
                rd = reg_num(parts[1])
                m = _MEM_OPERAND_RE.match(parts[2])
                if m:
                    imm = cls._parse_imm(m.group(1))
                    rs1 = reg_num(m.group(2))
                else:
                    rs1 = reg_num(parts[2])
                    imm = 0
            else:
                rd = 31
                rs1 = reg_num(parts[1])
                imm = 0
            return ("jalr", op, rd, rs1, 0, imm, True, None, None, False, parts[1])

        return ("unknown", op, 0, 0, 0, 0, False, None, None, False, rd_label)

    def _ensure_predecoded(self, compiled_ins):
        src_id = id(compiled_ins)
        src_len = len(compiled_ins)
        if self._decoded_source_id != src_id or self._decoded_source_len != src_len:
            self._decoded_ops = [self._predecode_instruction(i, ins) for i, ins in enumerate(compiled_ins)]
            self._decoded_source_id = src_id
            self._decoded_source_len = src_len

    def load_program(self, compiled_ins, raw_asm_text=None):
        self._init_dmem = {}
        if compiled_ins:
            first_init = compiled_ins[0].get("init_dmem")
            if isinstance(first_init, dict):
                for k, v in first_init.items():
                    self._init_dmem[int(k) & ~3] = int(v) & 0xFFFFFFFF
            self._ensure_predecoded(compiled_ins)
        else:
            self._decoded_ops = []
            self._decoded_source_id = None
            self._decoded_source_len = 0

        for addr_w, val_w in self._init_dmem.items():
            self.dmem[addr_w] = val_w

        self.last_error = None
        self._mips_delay_target = None
        self._loaded_code_id = id(compiled_ins) if compiled_ins else None

    def _read_dmem(self, addr, op):
        word_addr = addr & ~3
        byte_off = addr & 3
        w0 = self.dmem.get(word_addr, 0)
        if op == "lw":
            if byte_off == 0:
                return w0
            w1 = self.dmem.get((word_addr + 4) & 0xFFFFFFFF, 0)
            sh = byte_off * 8
            return ((w0 >> sh) | (w1 << (32 - sh))) & 0xFFFFFFFF
        if op in ("lh", "lhu"):
            if byte_off <= 2:
                half = (w0 >> (byte_off * 8)) & 0xFFFF
            else:
                w1 = self.dmem.get((word_addr + 4) & 0xFFFFFFFF, 0)
                half = ((w0 >> 24) | ((w1 & 0xFF) << 8)) & 0xFFFF
            if op == "lh" and (half & 0x8000):
                return (half | 0xFFFF0000) & 0xFFFFFFFF
            return half
        # lb / lbu
        b = (w0 >> (byte_off * 8)) & 0xFF
        if op == "lb" and (b & 0x80):
            return (b | 0xFFFFFF00) & 0xFFFFFFFF
        return b

    def _write_dmem(self, addr, val, op):
        word_addr = addr & ~3
        byte_off = addr & 3
        if op == "sw":
            if byte_off == 0:
                self.dmem[word_addr] = val & 0xFFFFFFFF
            else:
                sh = byte_off * 8
                w0 = self.dmem.get(word_addr, 0)
                w1 = self.dmem.get((word_addr + 4) & 0xFFFFFFFF, 0)
                m0 = (1 << sh) - 1
                self.dmem[word_addr] = (w0 & m0) | ((val << sh) & 0xFFFFFFFF)
                self.dmem[(word_addr + 4) & 0xFFFFFFFF] = (w1 & (~((1 << sh) - 1) & 0xFFFFFFFF)) | ((val >> (32 - sh)) & m0)
        elif op == "sh":
            half = val & 0xFFFF
            if byte_off <= 2:
                sh = byte_off * 8
                cur = self.dmem.get(word_addr, 0)
                clr = ~(0xFFFF << sh) & 0xFFFFFFFF
                self.dmem[word_addr] = (cur & clr) | (half << sh)
            else:
                # Cross-word halfword write
                self._write_dmem(addr, half & 0xFF, "sb")
                self._write_dmem((addr + 1) & 0xFFFFFFFF, (half >> 8) & 0xFF, "sb")
        else:  # sb
            sh = byte_off * 8
            cur = self.dmem.get(word_addr, 0)
            clr = ~(0xFF << sh) & 0xFFFFFFFF
            self.dmem[word_addr] = (cur & clr) | ((val & 0xFF) << sh)

    def _exec_one(self, compiled_ins, is_mips=False, detail=True):
        """Core single-cycle pre-decoded executor. Formats UI strings only when detail=True."""
        n_ins = len(compiled_ins)
        if self.pc_index < 0 or self.pc_index >= n_ins:
            self.pc_index = 0

        cur_pc = self.pc_index
        ins = compiled_ins[cur_pc]
        dec = self._decoded_ops[cur_pc]
        kind, op, rd, rs1, rs2, imm, use_imm, rv_target, mips_target, has_halt_tag, rlabel = dec

        # Check if THIS instruction is executing in a MIPS Branch Delay Slot
        in_delay_slot = False
        delayed_jump_pc = None
        if is_mips and self._mips_delay_target is not None:
            in_delay_slot = True
            delayed_jump_pc = self._mips_delay_target
            self._mips_delay_target = None

        next_pc = cur_pc + 1
        scheduled_delay_target = None
        uart_updated = False
        is_halted = False
        wb_msg = "No Register Write" if detail else ""
        mem_msg = "Idle" if detail else ""
        ex_msg = ins.get("desc", "") if detail else ""
        regs = self.regs

        try:
            if kind == "nop":
                pass

            elif kind == "halt":
                if op in ("syscall", "ecall"):
                    if is_mips:
                        v0 = self.regs[2]  # $v0
                        if v0 == 1:
                            val = self.regs[4]
                            self.uart_buffer += f"{val}\n"
                            uart_updated = True
                            is_halted = False
                            next_pc = cur_pc + 1
                            if detail:
                                ex_msg = f"syscall 1: print_int({val})"
                        elif v0 == 11:
                            ch = chr(self.regs[4] & 0xFF)
                            self.uart_buffer += ch
                            uart_updated = True
                            is_halted = False
                            next_pc = cur_pc + 1
                            if detail:
                                ex_msg = f"syscall 11: print_char({repr(ch)})"
                        elif v0 == 10:
                            is_halted = True
                            next_pc = cur_pc
                            if detail:
                                ex_msg = "syscall 10: exit()"
                        else:
                            is_halted = True
                            next_pc = cur_pc
                            if detail:
                                ex_msg = f"syscall {v0}: halt"
                    else:
                        # RISC-V ecall: a7 (x17) holds service number, a0 (x10) holds arg
                        a7 = self.regs[17] if len(self.regs) > 17 else 10
                        if a7 == 1:
                            val = self.regs[10]
                            self.uart_buffer += f"{val}\n"
                            uart_updated = True
                            is_halted = False
                            next_pc = cur_pc + 1
                            if detail:
                                ex_msg = f"ecall 1: print_int({val})"
                        elif a7 == 11:
                            ch = chr(self.regs[10] & 0xFF)
                            self.uart_buffer += ch
                            uart_updated = True
                            is_halted = False
                            next_pc = cur_pc + 1
                            if detail:
                                ex_msg = f"ecall 11: print_char({repr(ch)})"
                        elif a7 in (10, 93):
                            is_halted = True
                            next_pc = cur_pc
                            if detail:
                                ex_msg = f"ecall {a7}: exit()"
                        else:
                            is_halted = True
                            next_pc = cur_pc
                            if detail:
                                ex_msg = f"ecall {a7}: halt"
                else:
                    next_pc = cur_pc
                    is_halted = True
                    if detail:
                        ex_msg = f"Breakpoint / System Halt ({op})"

            elif kind == "u":
                if op == "lui":
                    imm_eff = imm
                    if is_mips and imm_eff > 0xFFFF:
                        imm_eff = (imm_eff >> 16) & 0xFFFF if imm_eff > 0xFFFFF else (imm_eff >> 4) & 0xFFFF
                    val = ((imm_eff << 16) if is_mips else (imm_eff << 12)) & 0xFFFFFFFF
                else:  # auipc (rs1 holds pc_int)
                    val = (rs1 + (imm << 12)) & 0xFFFFFFFF
                if rd != 0:
                    regs[rd] = val
                    self.last_alu_out = val
                    if detail:
                        wb_msg = f"{rlabel} <= 0x{val:08X}"

            elif kind == "alu_i":
                v1 = regs[rs1]
                if op in ("addi", "addiu"):
                    res = (v1 + imm) & 0xFFFFFFFF
                elif op == "slti":
                    res = 1 if (self._to_signed(v1) < imm) else 0
                elif op == "sltiu":
                    # Both RV32I and MIPS sign-extend immediate before unsigned comparison
                    u_imm = imm & 0xFFFFFFFF
                    res = 1 if ((v1 & 0xFFFFFFFF) < u_imm) else 0
                elif op == "slli":
                    res = (v1 << (imm & 0x1F)) & 0xFFFFFFFF
                elif op == "srli":
                    res = (v1 & 0xFFFFFFFF) >> (imm & 0x1F)
                elif op == "srai":
                    res = (self._to_signed(v1) >> (imm & 0x1F)) & 0xFFFFFFFF
                elif op == "andi":
                    m_imm = (imm & 0xFFFF) if is_mips else (imm & 0xFFFFFFFF)
                    res = v1 & m_imm
                elif op == "ori":
                    m_imm = (imm & 0xFFFF) if is_mips else (imm & 0xFFFFFFFF)
                    res = v1 | m_imm
                else:  # xori
                    m_imm = (imm & 0xFFFF) if is_mips else (imm & 0xFFFFFFFF)
                    res = v1 ^ m_imm
                if rd != 0:
                    regs[rd] = res & 0xFFFFFFFF
                    self.last_alu_out = regs[rd]
                    if detail:
                        wb_msg = f"{rlabel} <= {regs[rd]}"

            elif kind == "alu_r":
                v1 = regs[rs1]
                v2 = imm if use_imm else regs[rs2]
                write_rd = True
                res = 0
                if op in ("add", "addu"):
                    res = v1 + v2
                elif op in ("sub", "subu"):
                    res = v1 - v2
                elif op == "and":
                    res = v1 & v2
                elif op == "or":
                    res = v1 | v2
                elif op == "xor":
                    res = v1 ^ v2
                elif op == "nor":
                    res = ~(v1 | v2)
                elif op in ("sll", "sllv"):
                    res = v1 << (v2 & 0x1F)
                elif op in ("srl", "srlv"):
                    res = (v1 & 0xFFFFFFFF) >> (v2 & 0x1F)
                elif op in ("sra", "srav"):
                    res = self._to_signed(v1) >> (v2 & 0x1F)
                elif op == "slt":
                    res = 1 if (self._to_signed(v1) < self._to_signed(v2)) else 0
                elif op == "sltu":
                    res = 1 if ((v1 & 0xFFFFFFFF) < (v2 & 0xFFFFFFFF)) else 0
                elif op == "mul":
                    res = (self._to_signed(v1) * self._to_signed(v2)) & 0xFFFFFFFF
                elif op == "mulh":
                    res = ((self._to_signed(v1) * self._to_signed(v2)) >> 32) & 0xFFFFFFFF
                elif op == "mulhu":
                    res = (((v1 & 0xFFFFFFFF) * (v2 & 0xFFFFFFFF)) >> 32) & 0xFFFFFFFF
                elif op == "mulhsu":
                    res = ((self._to_signed(v1) * (v2 & 0xFFFFFFFF)) >> 32) & 0xFFFFFFFF
                elif op == "rem":
                    sv1, sv2 = self._to_signed(v1), self._to_signed(v2)
                    if sv2 == 0:
                        res = sv1
                    elif sv1 == -0x80000000 and sv2 == -1:
                        res = 0
                    else:
                        res = sv1 - int(sv1 / sv2) * sv2
                elif op == "remu":
                    uv1, uv2 = v1 & 0xFFFFFFFF, v2 & 0xFFFFFFFF
                    res = (uv1 % uv2) if uv2 != 0 else uv1
                elif op == "movz":
                    if (v2 & 0xFFFFFFFF) == 0:
                        res = v1
                    else:
                        write_rd = False
                elif op == "movn":
                    if (v2 & 0xFFFFFFFF) != 0:
                        res = v1
                    else:
                        write_rd = False
                elif op == "clz":
                    uv1 = v1 & 0xFFFFFFFF
                    res = 32 if uv1 == 0 else (32 - uv1.bit_length())
                elif op == "clo":
                    inv = (~v1) & 0xFFFFFFFF
                    res = 32 if inv == 0 else (32 - inv.bit_length())

                if write_rd and rd != 0:
                    regs[rd] = res & 0xFFFFFFFF
                    self.last_alu_out = regs[rd]
                    if detail:
                        wb_msg = f"{rlabel} <= {regs[rd]}"

            elif kind == "hilo_mul":
                if op in ("mult", "madd", "msub"):
                    v1, v2 = self._to_signed(regs[rs1]), self._to_signed(regs[rs2])
                else:
                    v1, v2 = regs[rs1] & 0xFFFFFFFF, regs[rs2] & 0xFFFFFFFF
                prod = v1 * v2
                if op in ("madd", "maddu"):
                    cur64 = ((self.hi & 0xFFFFFFFF) << 32) | (self.lo & 0xFFFFFFFF)
                    if op == "madd" and (cur64 & (1 << 63)):
                        cur64 -= (1 << 64)
                    prod = cur64 + prod
                elif op in ("msub", "msubu"):
                    cur64 = ((self.hi & 0xFFFFFFFF) << 32) | (self.lo & 0xFFFFFFFF)
                    if op == "msub" and (cur64 & (1 << 63)):
                        cur64 -= (1 << 64)
                    prod = cur64 - prod
                self.lo = prod & 0xFFFFFFFF
                self.hi = (prod >> 32) & 0xFFFFFFFF
                if detail:
                    ex_msg = f"HI:LO <= {v1} * {v2}"
                    wb_msg = f"LO <= 0x{self.lo:08X}, HI <= 0x{self.hi:08X}"

            elif kind == "div3":
                if op == "div":
                    sv1, sv2 = self._to_signed(regs[rs1]), self._to_signed(regs[rs2])
                    if sv2 == 0:
                        res = -1
                    elif sv1 == -0x80000000 and sv2 == -1:
                        res = -0x80000000
                    else:
                        res = int(sv1 / sv2)
                else:
                    uv1, uv2 = regs[rs1] & 0xFFFFFFFF, regs[rs2] & 0xFFFFFFFF
                    res = (uv1 // uv2) if uv2 != 0 else 0xFFFFFFFF
                if rd != 0:
                    regs[rd] = res & 0xFFFFFFFF
                    self.last_alu_out = regs[rd]
                    if detail:
                        wb_msg = f"{rlabel} <= {regs[rd]}"

            elif kind == "div2":
                if op == "div":
                    sv1, sv2 = self._to_signed(regs[rs1]), self._to_signed(regs[rs2])
                    if sv2 == 0:
                        self.lo = 0xFFFFFFFF
                        self.hi = sv1 & 0xFFFFFFFF
                    elif sv1 == -0x80000000 and sv2 == -1:
                        self.lo = 0x80000000
                        self.hi = 0
                    else:
                        q = int(sv1 / sv2)
                        r = sv1 - q * sv2
                        self.lo = q & 0xFFFFFFFF
                        self.hi = r & 0xFFFFFFFF
                else:
                    uv1, uv2 = regs[rs1] & 0xFFFFFFFF, regs[rs2] & 0xFFFFFFFF
                    if uv2 == 0:
                        self.lo = 0xFFFFFFFF
                        self.hi = uv1
                    else:
                        self.lo = (uv1 // uv2) & 0xFFFFFFFF
                        self.hi = (uv1 % uv2) & 0xFFFFFFFF
                if detail:
                    wb_msg = f"LO <= 0x{self.lo:08X}, HI <= 0x{self.hi:08X}"

            elif kind == "hilo_mv":
                if op == "mflo":
                    if rd != 0:
                        regs[rd] = self.lo & 0xFFFFFFFF
                        if detail:
                            wb_msg = f"{rlabel} <= LO ({self.lo})"
                elif op == "mfhi":
                    if rd != 0:
                        regs[rd] = self.hi & 0xFFFFFFFF
                        if detail:
                            wb_msg = f"{rlabel} <= HI ({self.hi})"
                elif op == "mthi":
                    self.hi = regs[rs1] & 0xFFFFFFFF
                    if detail:
                        wb_msg = f"HI <= {self.hi}"
                elif op == "mtlo":
                    self.lo = regs[rs1] & 0xFFFFFFFF
                    if detail:
                        wb_msg = f"LO <= {self.lo}"

            elif kind == "load":
                addr = (regs[rs1] + imm) & 0xFFFFFFFF
                if addr == self.mmio_sw:
                    val = self.sw_value
                    if detail:
                        mem_msg = f"Read SWITCH = {val}"
                elif addr == self.mmio_led:
                    val = self.led_value
                elif addr == self.mmio_seg7:
                    val = self.seg7_value
                elif addr == self.mmio_btn:
                    val = self.btn_value
                    if detail:
                        mem_msg = f"Read BUTTON = 0x{val:02X}"
                elif addr == self.mmio_uart:
                    val = self.uart_rx_queue.pop(0) if self.uart_rx_queue else 0
                    if detail:
                        mem_msg = f"Read UART_RX = '{chr(val) if 32 <= val <= 126 else val}'"
                elif addr == self.mmio_uart_stat:
                    val = (1 if self.uart_rx_queue else 0) | 2
                elif addr == self.mmio_rgb:
                    val = (self.rgb_value[0] << 12) | (self.rgb_value[1] & 0xFFF)
                elif self.mmio_vga <= addr <= (self.mmio_vga + 0x000FFFFF):
                    val = self.vga_buffer.get(addr & ~3, 0)
                else:
                    val = self._read_dmem(addr, op)
                    if detail:
                        mem_msg = f"Read MEM[0x{addr:08X}] = {val}"
                if rd != 0:
                    regs[rd] = val & 0xFFFFFFFF
                    if detail:
                        rname = MIPS_REG_NAMES[rd] if is_mips else f"x{rd}"
                        wb_msg = f"{rname} <= {regs[rd]}"

            elif kind == "store":
                addr = (regs[rs1] + imm) & 0xFFFFFFFF
                val = regs[rs2] & 0xFFFFFFFF
                if addr == self.mmio_led:
                    self.led_value = val & 0xFFFF
                    if detail:
                        mem_msg = f"Write LED <= {self.led_value}"
                elif addr == self.mmio_seg7:
                    self.seg7_value = val
                    if detail:
                        mem_msg = f"Write SEG7 <= {self.seg7_value}"
                elif addr == self.mmio_btn:
                    self.btn_value = val & 0x3F
                    if detail:
                        mem_msg = f"Write BTN <= 0x{val:02X}"
                elif addr == self.mmio_uart:
                    b = val & 0xFF
                    ch = chr(b) if (32 <= b <= 126 or b in (10, 13)) else ""
                    if ch:
                        self.uart_buffer += ch
                        if len(self.uart_buffer) > 4000:
                            self.uart_buffer = self.uart_buffer[-3000:]
                    uart_updated = True
                    if detail:
                        mem_msg = f"UART_TX <= '{ch if ch != chr(10) else '\\n'}'"
                elif addr == self.mmio_rgb:
                    self.rgb_value[0] = (val >> 12) & 0xFFF
                    self.rgb_value[1] = val & 0xFFF
                    if detail:
                        mem_msg = f"Write RGB <= 0x{val:06X}"
                elif self.mmio_vga <= addr <= (self.mmio_vga + 0x000FFFFF):
                    self.vga_buffer[addr & ~3] = val
                    if detail:
                        mem_msg = f"VGA_VRAM[0x{addr:08X}] <= 0x{val:08X}"
                else:
                    self._write_dmem(addr, val, op)
                    if detail:
                        mem_msg = f"Write MEM[0x{addr:08X}] <= {val}"

            elif kind == "bz":
                sv1 = self._to_signed(regs[rs1])
                take = (
                    (op == "blez" and sv1 <= 0) or
                    (op == "bgtz" and sv1 > 0) or
                    (op == "bltz" and sv1 < 0) or
                    (op == "bgez" and sv1 >= 0)
                )
                if take:
                    tgt = mips_target if is_mips else rv_target
                    if is_mips and tgt != cur_pc and (cur_pc + 1) < n_ins:
                        scheduled_delay_target = tgt
                    else:
                        next_pc = tgt

            elif kind == "branch":
                v1, v2 = regs[rs1], regs[rs2]
                take = (
                    (op == "beq" and v1 == v2) or
                    (op == "bne" and v1 != v2) or
                    (op == "blt" and (self._to_signed(v1) < self._to_signed(v2))) or
                    (op == "bge" and (self._to_signed(v1) >= self._to_signed(v2))) or
                    (op == "bltu" and ((v1 & 0xFFFFFFFF) < (v2 & 0xFFFFFFFF))) or
                    (op == "bgeu" and ((v1 & 0xFFFFFFFF) >= (v2 & 0xFFFFFFFF)))
                )
                if take:
                    tgt = mips_target if is_mips else rv_target
                    if is_mips and tgt != cur_pc and (cur_pc + 1) < n_ins:
                        scheduled_delay_target = tgt
                    else:
                        next_pc = tgt

            elif kind == "jal":
                actual_rd = 31 if is_mips else rd
                tgt = mips_target if is_mips else rv_target
                if is_mips:
                    # OpenMIPS link_addr_o = pc_plus_8 when delay slot exists
                    has_ds = (cur_pc + 1) < n_ins
                    if actual_rd != 0:
                        regs[actual_rd] = ((cur_pc + 2) * 4) if has_ds else ((cur_pc + 1) * 4)
                    if tgt != cur_pc and has_ds:
                        scheduled_delay_target = tgt
                    else:
                        next_pc = tgt
                else:
                    if actual_rd != 0:
                        regs[actual_rd] = (cur_pc + 1) * 4
                    next_pc = tgt

            elif kind == "j":
                tgt = mips_target if is_mips else rv_target
                if tgt == cur_pc or has_halt_tag:
                    next_pc = cur_pc
                    is_halted = True
                elif is_mips and (cur_pc + 1) < n_ins:
                    scheduled_delay_target = tgt
                else:
                    next_pc = tgt

            elif kind == "jr":
                target_byte = regs[rs1] & 0xFFFFFFFF
                tgt = target_byte // 4
                if is_mips and tgt != cur_pc and (cur_pc + 1) < n_ins:
                    scheduled_delay_target = tgt
                else:
                    next_pc = tgt
                if detail:
                    ex_msg = f"PC <= {rlabel} (0x{target_byte:08X})"

            elif kind == "jalr":
                target_byte = (regs[rs1] + imm) & ~1 & 0xFFFFFFFF
                tgt = target_byte // 4
                if is_mips:
                    has_ds = (cur_pc + 1) < n_ins
                    if rd != 0:
                        regs[rd] = ((cur_pc + 2) * 4) if has_ds else ((cur_pc + 1) * 4)
                    if tgt != cur_pc and has_ds:
                        scheduled_delay_target = tgt
                    else:
                        next_pc = tgt
                else:
                    if rd != 0:
                        regs[rd] = (cur_pc + 1) * 4
                    next_pc = tgt

            else:
                self.last_error = f"คำสั่งที่ไม่รองรับที่ PC={ins.get('pc', hex(cur_pc*4))}: {ins.get('asm', op)}"
                if detail:
                    ex_msg = f"[!] {self.last_error}"

        except Exception as exc:
            self.last_error = f"Runtime Error ที่ PC={ins.get('pc', hex(cur_pc*4))}: {exc}"
            if detail:
                ex_msg = f"[!] {self.last_error}"

        # Finalize next PC with MIPS branch delay slot semantics
        if in_delay_slot and delayed_jump_pc is not None:
            next_pc = delayed_jump_pc
            if detail:
                ex_msg = f"[Delay Slot] {ex_msg}"
        elif scheduled_delay_target is not None:
            self._mips_delay_target = scheduled_delay_target
            next_pc = cur_pc + 1

        if not is_halted:
            is_halted = bool(next_pc == cur_pc or (kind == "j" and has_halt_tag))

        regs[0] = 0
        self.cycles += 1
        self.pc_index = next_pc

        if not detail:
            return is_halted, uart_updated

        return {
            "IF": f"PC={ins['pc']} : {ins['asm']}",
            "ID": f"Type={ins['fmt']} | Hex={ins['hex']}",
            "EX": ex_msg,
            "MEM": mem_msg,
            "WB": wb_msg,
            "uart_updated": uart_updated,
            "is_halted": is_halted,
            "error": self.last_error,
        }

    def step(self, compiled_ins, is_mips=False, raw_asm_text=None):
        """Execute one instruction at self.pc_index and return pipeline stage summary dict."""
        if not compiled_ins:
            return None
        self._ensure_predecoded(compiled_ins)
        return self._exec_one(compiled_ins, is_mips=is_mips, detail=True)

    def step_batch(self, compiled_ins, batch_size=2000, is_mips=False, raw_asm_text=None):
        """Batch-execute pre-decoded cycles at high speed, formatting UI stage strings on final cycle."""
        if not compiled_ins or batch_size <= 0:
            return None
        self._ensure_predecoded(compiled_ins)

        any_uart = False
        fast_steps = max(0, batch_size - 1)
        for _ in range(fast_steps):
            halted, u_upd = self._exec_one(compiled_ins, is_mips=is_mips, detail=False)
            if u_upd:
                any_uart = True
            if halted:
                # Re-describe final halted state cleanly for UI
                ins = compiled_ins[self.pc_index] if 0 <= self.pc_index < len(compiled_ins) else compiled_ins[0]
                return {
                    "IF": f"PC={ins['pc']} : {ins['asm']}",
                    "ID": f"Type={ins['fmt']} | Hex={ins['hex']}",
                    "EX": ins.get("desc", "Halted"),
                    "MEM": "Idle",
                    "WB": "No Register Write",
                    "uart_updated": any_uart,
                    "is_halted": True,
                    "error": self.last_error,
                }

        res = self._exec_one(compiled_ins, is_mips=is_mips, detail=True)
        if res and any_uart:
            res["uart_updated"] = True
        return res

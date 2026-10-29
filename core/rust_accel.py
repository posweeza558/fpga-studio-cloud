# -*- coding: utf-8 -*-
"""
High-Speed Rust Native Simulation Accelerator (C-ABI Bridge via ctypes)
Enables 50x-100x speedup for CPU cycle execution and VGA rendering
while maintaining 100% identical VS Code/Spotify UI and layout.
"""

import os
import sys
import ctypes

_rust_lib = None
_load_attempted = False


def get_rust_dll_path():
    candidates = []
    # 1. Next to executable (if frozen by PyInstaller)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "fpga_engine_rust.dll"))
        candidates.append(os.path.join(exe_dir, "core", "fpga_engine_rust.dll"))
        candidates.append(os.path.join(exe_dir, "_internal", "fpga_engine_rust.dll"))
        candidates.append(os.path.join(exe_dir, "_internal", "core", "fpga_engine_rust.dll"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "fpga_engine_rust.dll"))
            candidates.append(os.path.join(sys._MEIPASS, "core", "fpga_engine_rust.dll"))

    # 2. In project core directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "fpga_engine_rust.dll"))

    # 3. In sibling rust target directory
    sibling_target = os.path.join(os.path.dirname(base_dir), "..", "fpga_studio_rust", "target", "release", "fpga_engine_rust.dll")
    candidates.append(os.path.abspath(sibling_target))

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def init_rust_library():
    global _rust_lib, _load_attempted
    if _load_attempted:
        return _rust_lib
    _load_attempted = True

    dll_path = get_rust_dll_path()
    if not dll_path:
        return None

    try:
        lib = ctypes.CDLL(dll_path)
        # Signatures
        lib.rust_sim_create.restype = ctypes.c_void_p
        lib.rust_sim_destroy.argtypes = [ctypes.c_void_p]

        lib.rust_sim_reset.argtypes = [ctypes.c_void_p]
        lib.rust_sim_reset_registers.argtypes = [ctypes.c_void_p]

        lib.rust_sim_load_asm.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.rust_sim_load_asm.restype = ctypes.c_uint32

        lib.rust_sim_step_batch.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_bool]
        lib.rust_sim_step_batch.restype = ctypes.c_uint32

        lib.rust_sim_get_registers.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.POINTER(ctypes.c_uint32)]
        lib.rust_sim_get_pc.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        lib.rust_sim_get_pc.restype = ctypes.c_uint32

        lib.rust_sim_get_cycles.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        lib.rust_sim_get_cycles.restype = ctypes.c_uint64

        lib.rust_sim_get_board_state.argtypes = [
            ctypes.c_void_p, ctypes.c_bool,
            ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint16)
        ]

        lib.rust_sim_set_switches.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
        lib.rust_sim_set_buttons.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.rust_sim_toggle_button.argtypes = [ctypes.c_void_p, ctypes.c_uint8]

        lib.rust_sim_get_vram.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
        lib.rust_sim_get_vram.restype = ctypes.c_size_t

        lib.rust_sim_get_uart.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.POINTER(ctypes.c_char), ctypes.c_size_t]
        lib.rust_sim_get_uart.restype = ctypes.c_size_t

        lib.rust_sim_send_uart_rx.argtypes = [ctypes.c_void_p, ctypes.c_uint8]

        _rust_lib = lib
        return _rust_lib
    except Exception as e:
        print("[Rust Acceleration] Failed to load DLL:", e)
        return None


class RustSimulatorClient:
    """High-speed native wrapper driving CPU cycle simulation in Rust."""

    def __init__(self):
        self.lib = init_rust_library()
        self.ptr = self.lib.rust_sim_create() if self.lib else None
        self._regs_buf = (ctypes.c_uint32 * 32)()
        self._vram_buf = (ctypes.c_uint32 * 4800)()
        self._uart_buf = (ctypes.c_char * 8192)()
        self._led = ctypes.c_uint16()
        self._sw = ctypes.c_uint16()
        self._seg7 = ctypes.c_uint32()
        self._btn = ctypes.c_uint8()
        self._rgb0 = ctypes.c_uint16()
        self._rgb1 = ctypes.c_uint16()

    def is_available(self):
        return bool(self.ptr)

    def load_instructions(self, compiled_ins, raw_asm_text=None):
        if not self.ptr:
            return 0
        if raw_asm_text:
            full_text = raw_asm_text
        elif compiled_ins:
            asm_lines = [ins["asm"] for ins in compiled_ins]
            full_text = "\n".join(asm_lines)
        else:
            return 0
        return self.lib.rust_sim_load_asm(self.ptr, full_text.encode("utf-8"))

    def step_batch(self, cycles=1000, is_mips=True):
        if not self.ptr:
            return 0
        return self.lib.rust_sim_step_batch(self.ptr, int(cycles), bool(is_mips))

    def get_pc_index(self, is_mips=True):
        if not self.ptr:
            return 0
        return self.lib.rust_sim_get_pc(self.ptr, bool(is_mips)) // 4

    def get_cycles(self, is_mips=True):
        if not self.ptr:
            return 0
        return self.lib.rust_sim_get_cycles(self.ptr, bool(is_mips))

    def sync_registers(self, target_regs_list, is_mips=True):
        if not self.ptr:
            return
        self.lib.rust_sim_get_registers(self.ptr, bool(is_mips), self._regs_buf)
        for i in range(32):
            target_regs_list[i] = int(self._regs_buf[i])

    def sync_board_state(self, is_mips=True):
        if not self.ptr:
            return None
        self.lib.rust_sim_get_board_state(
            self.ptr, bool(is_mips),
            ctypes.byref(self._led), ctypes.byref(self._sw),
            ctypes.byref(self._seg7), ctypes.byref(self._btn),
            ctypes.byref(self._rgb0), ctypes.byref(self._rgb1)
        )
        return {
            "led": int(self._led.value),
            "sw": int(self._sw.value),
            "seg7": int(self._seg7.value),
            "btn": int(self._btn.value),
            "rgb": [int(self._rgb0.value), int(self._rgb1.value)]
        }

    def sync_vram(self, target_vga_buffer, is_mips=True):
        if not self.ptr:
            return
        count = self.lib.rust_sim_get_vram(self.ptr, bool(is_mips), self._vram_buf, 4800)
        base = 0xFF000000
        for i in range(count):
            c = int(self._vram_buf[i])
            addr = base + i * 4
            if c != 0:
                target_vga_buffer[addr] = c
            elif addr in target_vga_buffer:
                del target_vga_buffer[addr]

    def set_buttons(self, btn_val):
        if self.ptr:
            self.lib.rust_sim_set_buttons(self.ptr, int(btn_val))

    def set_switches(self, sw_val):
        if self.ptr:
            self.lib.rust_sim_set_switches(self.ptr, int(sw_val))

    def reset(self):
        if self.ptr:
            self.lib.rust_sim_reset(self.ptr)

    def reset_registers(self):
        if self.ptr:
            self.lib.rust_sim_reset_registers(self.ptr)

    def close(self):
        if self.ptr and self.lib:
            self.lib.rust_sim_destroy(self.ptr)
            self.ptr = None

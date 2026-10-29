# -*- coding: utf-8 -*-
"""
FPGA Studio — Direct In-App FPGA Hardware Programmer & Bitstream Flasher Dialog
Frameless Spotify Dark Modal Window allowing 1-click flashing of synthesizable CPU bitstreams
(.bit) directly onto the connected FPGA board (Digilent Nexys A7-100T, Virtex-6, Basys 3, etc.)
without opening external Vivado windows.

Supports:
  - Built-in OpenMIPS 32-bit CPU
  - Built-in RISC-V RV32I 32-bit CPU
  - All User Custom CPUs (imported Verilog / VHDL modules)
  - 1-Click SoC Vivado synthesis wrapper generation
"""

import glob
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from config.theme import (
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_RED,
    BG_ACTIVITY,
    BG_BLACK,
    BG_EDITOR,
    BG_ELEVATED,
    BG_HOVER,
    BG_PANEL,
    BG_PILL_ACT,
    BG_PILL_INACT,
    BG_SIDEBAR,
    BORDER_COLOR,
    BORDER_HOVER,
    FONT_CODE,
    FONT_UI,
    TXT_BRIGHT,
    TXT_DIM,
    TXT_MUTED,
    TXT_PRIMARY,
)
from core.fpga_programmer import (
    detect_all_fpga_programmers,
    find_djtgcfg_binary,
    find_openfpgaloader_binary,
    find_vivado_binary,
    program_fpga_with_djtgcfg,
    program_fpga_with_openfpgaloader,
    program_fpga_with_vivado,
)
from ui.installer_wizard import BaseFramelessWizardDialog
from ui.widgets import SpotifyAutoScrollbar, SpotifyPillButton

ACCENT_CYAN = "#38BDF8"  # Sky blue accent for Open-Source Toolchain


class FPGAProgrammerDialog(BaseFramelessWizardDialog):
    """Direct In-App FPGA Hardware Flasher & JTAG Bitstream Loader Dialog."""

    def __init__(
        self,
        parent,
        current_arch: str = "openmips",
        active_arch_val: str = "",
        custom_cpus: Optional[List[dict]] = None,
        project_dir: Optional[str] = None,
        compiled_ins: Optional[list] = None,
        on_success_callback=None,
    ):
        self.current_arch = current_arch or "openmips"
        self.active_arch_val = active_arch_val or ""
        self.custom_cpus = custom_cpus or []
        self.project_dir = project_dir or os.getcwd()
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.compiled_ins = compiled_ins or []
        self.on_success_callback = on_success_callback
        self.is_flashing = False

        # Scan for available programmer backends (check app toolchain dir first)
        toolchain_path = os.path.join(self.app_dir, "toolchain")
        if not os.path.exists(toolchain_path):
            toolchain_path = os.path.join(self.project_dir, "toolchain")
        self.programmers = detect_all_fpga_programmers(toolchain_dir=toolchain_path)

        super().__init__(
            parent,
            "FPGA Studio — แฟลชฮาร์ดแวร์ CPU ลงบอร์ด FPGA (In-App JTAG Flasher)",
            900,
            660,
        )
        self._build_ui()
        self._on_cpu_selection_changed()

    def _build_ui(self):
        body = tk.Frame(self.container, bg=BG_BLACK, padx=20, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        # Header description
        lbl_info = tk.Label(
            body,
            text="⚡ แฟลชวงจรฮาร์ดแวร์ CPU เข้าสู่ชิป FPGA ผ่านสาย USB โดยตรง (In-App JTAG Flasher)\n"
                 "✓ มีระบบแฟลชในตัว (openFPGALoader) พร้อม Bitstream สำเร็จรูป — ไม่ต้องติดตั้ง Vivado 50GB!\n"
                 "รองรับ OpenMIPS, RISC-V, บอร์ด Demo และ CPU ที่ผู้ใช้เพิ่มเอง (*.v / *.vhd)",
            bg=BG_BLACK,
            fg=TXT_MUTED,
            font=(FONT_UI, 9),
            justify=tk.LEFT,
        )
        lbl_info.pack(anchor="w", pady=(0, 10))

        # Config Card
        card_cfg = tk.Frame(body, bg=BG_ELEVATED, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card_cfg.pack(fill=tk.X, pady=(0, 10))

        # Row 1: Target Board
        r1 = tk.Frame(card_cfg, bg=BG_ELEVATED)
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="บอร์ด FPGA เป้าหมาย:", bg=BG_ELEVATED, fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), width=18, anchor="w").pack(side=tk.LEFT)
        self.board_var = tk.StringVar(value="Digilent Nexys A7-100T (Artix-7)")
        cb_board = ttk.Combobox(
            r1,
            textvariable=self.board_var,
            values=[
                "Digilent Nexys A7-100T (Artix-7)",
                "Digilent Nexys A7-50T (Artix-7)",
                "Digilent Basys 3 (Artix-7)",
                "AMD Virtex-6 Connectivity Kit (XC6VLX240T)",
                "บอร์ด FPGA ทั่วไป (Generic JTAG)",
            ],
            state="readonly",
            width=42,
            font=(FONT_UI, 9),
        )
        cb_board.pack(side=tk.LEFT, padx=6)

        # Row 2: CPU Architecture (Built-in + Custom CPUs)
        r2 = tk.Frame(card_cfg, bg=BG_ELEVATED)
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="สถาปัตยกรรม CPU:", bg=BG_ELEVATED, fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), width=18, anchor="w").pack(side=tk.LEFT)

        self.cpu_map = {}
        mips_label = "⚡ OpenMIPS 32-bit (พร้อมวงจรคูณ MDU & 7-Segment)"
        self.cpu_map[mips_label] = {"kind": "builtin", "arch": "mips", "name": "openmips", "path": None}

        riscv_label = "⚡ RISC-V RV32I 32-bit (พร้อมวงจรคูณ MDU & 7-Segment)"
        self.cpu_map[riscv_label] = {"kind": "builtin", "arch": "riscv", "name": "riscv", "path": None}

        demo_label = "⚡ Digilent Nexys A7 Factory Demo (ทดสอบฮาร์ดแวร์บอร์ด/งูเลื้อย)"
        self.cpu_map[demo_label] = {"kind": "demo", "arch": "demo", "name": "factory_demo", "path": None}

        gpio_label = "⚡ Digilent Nexys A7 Switch-to-LED (สวิตช์ 16 ตัว ➔ LED 16 ดวง + 7-Seg)"
        self.cpu_map[gpio_label] = {"kind": "demo", "arch": "demo", "name": "gpio_demo", "path": None}

        for c in self.custom_cpus:
            c_name = c.get("name", "Custom CPU")
            c_arch = c.get("arch", "Generic")
            lbl = f"⚡ [Custom CPU] {c_name} ({c_arch})"
            self.cpu_map[lbl] = {"kind": "custom", "arch": c_arch, "name": c_name, "path": c.get("path")}

        default_lbl = mips_label
        if self.active_arch_val.startswith("custom:"):
            c_path = self.active_arch_val.split("custom:", 1)[1]
            for lbl, info in self.cpu_map.items():
                if info.get("path") == c_path or info.get("name") == os.path.basename(c_path):
                    default_lbl = lbl
                    break
        elif "riscv" in self.current_arch.lower():
            default_lbl = riscv_label

        self.cpu_core_var = tk.StringVar(value=default_lbl)
        cb_cpu = ttk.Combobox(
            r2,
            textvariable=self.cpu_core_var,
            values=list(self.cpu_map.keys()),
            state="readonly",
            width=42,
            font=(FONT_UI, 9),
        )
        cb_cpu.pack(side=tk.LEFT, padx=6)
        cb_cpu.bind("<<ComboboxSelected>>", lambda e: self._on_cpu_selection_changed())

        btn_install_oss = tk.Button(
            r2,
            text="📥 ติดตั้ง OSS Toolchain",
            bg=BG_PILL_INACT,
            fg=ACCENT_CYAN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_CYAN,
            padx=8,
            pady=1,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=lambda: self._start_install_oss_cad_suite(auto_synthesize_after=False),
        )
        btn_install_oss.pack(side=tk.RIGHT, padx=(4, 0))

        btn_cloud_synth = tk.Button(
            r2,
            text="☁️ สังเคราะห์ Cloud (GitHub)",
            bg=BG_PILL_INACT,
            fg="#A78BFA",
            bd=0,
            highlightthickness=1,
            highlightbackground="#A78BFA",
            padx=8,
            pady=1,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=self._open_cloud_synthesis_dialog,
        )
        btn_cloud_synth.pack(side=tk.RIGHT, padx=(4, 0))

        btn_export_soc = tk.Button(
            r2,
            text="⚡ สังเคราะห์ SoC Bitstream",
            bg=BG_PILL_INACT,
            fg=ACCENT_GREEN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_GREEN,
            padx=8,
            pady=1,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=self._start_synthesis_thread,
        )
        btn_export_soc.pack(side=tk.RIGHT)

        # Row 3: Bitstream File (.bit)
        r3 = tk.Frame(card_cfg, bg=BG_ELEVATED)
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="ไฟล์ Bitstream (.bit):", bg=BG_ELEVATED, fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), width=18, anchor="w").pack(side=tk.LEFT)
        self.bit_path_var = tk.StringVar(value="")
        e_bit = tk.Entry(r3, textvariable=self.bit_path_var, bg=BG_EDITOR, fg=TXT_BRIGHT, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, font=(FONT_CODE, 9))
        e_bit.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, ipady=3)

        btn_browse_bit = tk.Button(
            r3,
            text="เลือกไฟล์ .bit...",
            bg=BG_PILL_INACT,
            fg=TXT_BRIGHT,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=10,
            pady=2,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=self._browse_bitstream,
        )
        btn_browse_bit.pack(side=tk.RIGHT)

        # Row 4: Programmer Engine detected
        r4 = tk.Frame(card_cfg, bg=BG_ELEVATED)
        r4.pack(fill=tk.X, pady=(6, 2))
        tk.Label(r4, text="เครื่องมือแฟลช (Engine):", bg=BG_ELEVATED, fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), width=18, anchor="w").pack(side=tk.LEFT)

        eng_text, eng_color = self._get_engine_status_summary()
        self.lbl_eng_status = tk.Label(r4, text=eng_text, bg=BG_ELEVATED, fg=eng_color, font=(FONT_UI, 9, "bold"))
        self.lbl_eng_status.pack(side=tk.LEFT, padx=6)

        btn_browse_eng = tk.Button(
            r4,
            text="ระบุตำแหน่ง Vivado...",
            bg=BG_PILL_INACT,
            fg=TXT_MUTED,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=8,
            pady=1,
            cursor="hand2",
            font=(FONT_UI, 8),
            command=self._browse_vivado,
        )
        btn_browse_eng.pack(side=tk.RIGHT)

        btn_zadig = tk.Button(
            r4,
            text="🔧 ติดตั้งไดรเวอร์ USB JTAG (Zadig)",
            bg=BG_PILL_INACT,
            fg=ACCENT_GREEN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_GREEN,
            padx=8,
            pady=1,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=self._open_zadig,
        )
        btn_zadig.pack(side=tk.RIGHT, padx=(0, 6))

        # Bottom Action Bar (packed at bottom first so it is never pushed off-screen)
        act_bar = tk.Frame(body, bg=BG_BLACK)
        act_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        self.btn_flash = tk.Button(
            act_bar,
            text="⚡ เริ่มแฟลช CPU ลงบอร์ดทันที (Burn Bitstream)",
            bg=ACCENT_GREEN,
            fg=BG_BLACK,
            activebackground="#1ED760",
            activeforeground=BG_BLACK,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            font=(FONT_UI, 10, "bold"),
            command=self._start_flashing_thread,
        )
        self.btn_flash.pack(side=tk.LEFT, padx=(0, 10))

        btn_uart = tk.Button(
            act_bar,
            text="⬆ อัปโหลดโค้ด MIPS / C (USB UART)",
            bg=BG_PILL_INACT,
            fg=TXT_BRIGHT,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=12,
            pady=8,
            cursor="hand2",
            font=(FONT_UI, 9, "bold"),
            command=self._call_parent_uart_upload,
        )
        btn_uart.pack(side=tk.LEFT)

        btn_close = tk.Button(
            act_bar,
            text="ปิดหน้าต่าง",
            bg=BG_PILL_INACT,
            fg=TXT_MUTED,
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            font=(FONT_UI, 9),
            command=self.destroy,
        )
        btn_close.pack(side=tk.RIGHT)

        # Terminal / Log Box (expands in middle)
        card_log = tk.Frame(body, bg=BG_EDITOR, padx=8, pady=8, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card_log.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 6))

        log_hdr = tk.Frame(card_log, bg=BG_EDITOR)
        log_hdr.pack(fill=tk.X, pady=(0, 4))
        tk.Label(log_hdr, text="🖥️ คอนโซลการแฟลชฮาร์ดแวร์ (Live Hardware Flasher Log):", bg=BG_EDITOR, fg=TXT_MUTED, font=(FONT_UI, 8, "bold")).pack(side=tk.LEFT)

        self.log_text = tk.Text(
            card_log,
            bg="#121212",
            fg=TXT_BRIGHT,
            bd=0,
            highlightthickness=0,
            font=(FONT_CODE, 9),
            wrap=tk.WORD,
            spacing1=2,
            spacing3=2,
        )
        log_scroll = SpotifyAutoScrollbar(card_log, command=self.log_text.yview, bg_track="#121212")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._log("พร้อมทำงาน: เลือกรุ่น CPU และตรวจสอบสาย USB ของบอร์ด FPGA จากนั้นกด 'เริ่มแฟลช CPU'")

    def _on_cpu_selection_changed(self):
        sel = self.cpu_core_var.get()
        info = self.cpu_map.get(sel, {})
        core_name = info.get("name", "openmips")
        c_path = info.get("path")

        # Auto-detect bitstream with priority to pre-bundled bitstreams
        cands = [
            os.path.join(self.app_dir, "bitstreams", f"nexys_a7_{core_name}.bit"),
            os.path.join(self.project_dir, "bitstreams", f"nexys_a7_{core_name}.bit"),
            os.path.join(self.project_dir, f"vivado_nexys_a7_{core_name}", "vivado_proj", "fpga_studio_nexys_a7.runs", "impl_1", "nexys_a7_soc_top.bit"),
            os.path.join(self.project_dir, f"top_{core_name}.bit"),
            os.path.join(self.project_dir, f"{core_name}.bit"),
            os.path.join(self.project_dir, "top.bit"),
        ]
        if c_path and os.path.exists(c_path):
            c_dir = os.path.dirname(c_path)
            cands.extend(glob.glob(os.path.join(c_dir, "*.bit")))
            cands.extend(glob.glob(os.path.join(c_dir, "**", "*.bit"), recursive=True))

        found = None
        for c in cands:
            if os.path.isfile(c):
                found = c
                break

        if found:
            self.bit_path_var.set(found)
            self._log(f"✓ โหลด Bitstream สำเร็จรูปสำหรับ '{core_name}': {os.path.basename(found)}")
        else:
            self.bit_path_var.set("")
            if info.get("kind") == "custom":
                self._log(f"ℹ️ CPU ที่ผู้ใช้เพิ่มเอง '{core_name}': เลือกไฟล์ .bit หรือกด 'สร้างแพ็กเกจ Vivado สำหรับ CPU นี้'")
            else:
                self._log(f"ℹ️ ยังไม่พบไฟล์ .bit สำหรับ '{core_name}' — สามารถกดเลือกไฟล์ .bit หรือสร้างแพ็กเกจ Vivado")

    def _open_cloud_synthesis_dialog(self):
        """Open Cloud Synthesis modal dialog (GitHub Actions)."""
        sel = self.cpu_core_var.get()
        info = self.cpu_map.get(sel, {})
        core_name = info.get("name", "openmips")
        core_arch = "mips" if "mips" in info.get("arch", "").lower() or "openmips" in core_name.lower() else "riscv"
        c_path = info.get("path")

        from ui.cloud_synthesis_dialog import CloudSynthesisDialog

        def on_ready(bit_path):
            self.bit_path_var.set(bit_path)
            self._log(f"✅ เลือกไฟล์ Bitstream จาก Cloud อัตโนมัติ: {os.path.basename(bit_path)}")

        CloudSynthesisDialog(
            parent=self,
            cpu_name=core_name,
            cpu_arch=core_arch,
            cpu_hdl_path=c_path,
            board_name=self.board_var.get(),
            project_dir=self.project_dir,
            on_bitstream_ready=on_ready,
        )

    def _start_synthesis_thread(self):
        """Run In-App Synthesis Pipeline in background thread."""
        sel = self.cpu_core_var.get()
        info = self.cpu_map.get(sel, {})
        core_name = info.get("name", "openmips")
        core_arch = "mips" if "mips" in info.get("arch", "").lower() or "openmips" in core_name.lower() else "riscv"
        c_path = info.get("path")

        from core.open_synthesizer import synthesize_soc_bitstream

        def worker():
            ok, msg, out_bit = synthesize_soc_bitstream(
                project_dir=self.project_dir,
                cpu_name=core_name,
                cpu_arch=core_arch,
                cpu_hdl_path=c_path,
                board_name=self.board_var.get(),
                on_log=self._log,
            )

            def done():
                if ok and out_bit and os.path.isfile(out_bit):
                    self.bit_path_var.set(out_bit)
                    self._log(f"\n✅ {msg}")
                    ans = messagebox.askyesno(
                        "สังเคราะห์สำเร็จ",
                        f"สังเคราะห์ Bitstream สำหรับ '{core_name}' สำเร็จเรียบร้อย!\n\n"
                        f"ไฟล์: {os.path.basename(out_bit)}\n\n"
                        "คุณต้องการเริ่มแฟลชลงบอร์ด FPGA ผ่านสาย USB ทันทีเลยหรือไม่?",
                        parent=self,
                    )
                    if ans:
                        self._start_flashing_thread()
                elif ok:
                    self._log(f"\n📁 {msg}")
                    ans = messagebox.askyesno(
                        "สร้างแพ็กเกจ SoC สำเร็จ (ต้องการติดตั้ง OSS Toolchain?)",
                        f"ระบบสร้างแพ็กเกจ SoC Auto-Wrapper สำหรับ '{core_name}' เสร็จสมบูรณ์แล้ว!\n\n"
                        f"สถานะ: {msg}\n\n"
                        "แต่ในเครื่องของคุณยังไม่มีตัวสังเคราะห์เพื่อแปลงเป็นไฟล์ Bitstream (.bit)\n\n"
                        "คุณต้องการให้ FPGA Studio ดาวน์โหลดและติดตั้ง Open-Source Toolchain (OSS CAD Suite ~600MB)\n"
                        "ลงในตัวแอปอัตโนมัติหรือไม่?\n\n"
                        "✓ ฟรี 100% ไม่ต้องติดตั้ง Vivado (50-80GB) ให้หนักเครื่อง\n"
                        "✓ รองรับการสังเคราะห์เป็น .bit ในโปรแกรมโดยตรง",
                        parent=self,
                    )
                    if ans:
                        self._start_install_oss_cad_suite(auto_synthesize_after=True)
                else:
                    self._log(f"\n❌ ข้อผิดพลาด: {msg}")
                    messagebox.showerror("การสังเคราะห์ล้มเหลว", msg, parent=self)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _start_install_oss_cad_suite(self, auto_synthesize_after: bool = False):
        """Download and install OSS CAD Suite in background thread."""
        from core.open_synthesizer import install_oss_cad_suite

        def worker():
            self._log("\n" + "=" * 65)
            self._log("🚀 เริ่มกระบวนการดาวน์โหลดและติดตั้ง OSS CAD Suite (Yosys + NextPNR)...")
            self._log("=" * 65)
            ok, msg = install_oss_cad_suite(on_log=self._log)

            def done():
                if ok:
                    self._log(f"\n✅ {msg}")
                    messagebox.showinfo("ติดตั้งสำเร็จ", msg, parent=self)
                    if auto_synthesize_after:
                        self._start_synthesis_thread()
                else:
                    self._log(f"\n❌ {msg}")
                    messagebox.showerror("การติดตั้งล้มเหลว", msg, parent=self)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _generate_soc_package_for_selected_cpu(self):
        """Generate ready-to-synthesize Vivado package for the selected CPU."""
        self._start_synthesis_thread()

    def _get_engine_status_summary(self):
        if self.programmers.get("openfpgaloader"):
            return "✓ เครื่องมือแฟลชในตัว: openFPGALoader (แฟลชตรงผ่าน USB ไม่ต้องลง Vivado 50GB!)", ACCENT_GREEN
        if self.programmers.get("vivado"):
            p = self.programmers["vivado"]
            base = os.path.basename(os.path.dirname(os.path.dirname(p)))
            return f"✓ พบ Xilinx Vivado CLI ({base})", ACCENT_GREEN
        if self.programmers.get("djtgcfg"):
            return "✓ พบ Digilent Adept CLI (djtgcfg)", ACCENT_GREEN
        return "⚠️ ไม่พบเครื่องมือแฟลช JTAG ในระบบ", ACCENT_AMBER

    def _browse_bitstream(self):
        f = filedialog.askopenfilename(
            parent=self,
            title="เลือกไฟล์ FPGA Bitstream (.bit)",
            filetypes=[("FPGA Bitstream", "*.bit"), ("All files", "*.*")],
            initialdir=os.path.join(self.app_dir, "bitstreams"),
        )
        if f:
            self.bit_path_var.set(f)
            self._log(f"เลือกไฟล์ Bitstream: {f}")

    def _open_zadig(self):
        """Launch bundled Zadig tool to switch Interface 0 to WinUSB."""
        cands = [
            os.path.join(self.app_dir, "toolchain", "zadig.exe"),
            os.path.join(self.project_dir, "toolchain", "zadig.exe"),
            os.path.join(self.app_dir, "_internal", "toolchain", "zadig.exe"),
        ]
        found = None
        for c in cands:
            if os.path.isfile(c):
                found = c
                break
        if found:
            self._log("🔧 กำลังเปิดโปรแกรม Zadig ด้วยสิทธิ์ Administrator (UAC)...")
            try:
                if os.name == "nt":
                    import ctypes
                    # ShellExecuteW with 'runas' prompts Windows UAC cleanly without WinError 740
                    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", found, None, None, 1)
                    if ret <= 32:
                        os.startfile(found)
                else:
                    import subprocess
                    subprocess.Popen([found])
                self._log("✓ ส่งคำขอเปิด Zadig เรียบร้อย (โปรดกดยืนยัน 'Yes' ในหน้าต่าง UAC):")
                self._log("   1. ใน Zadig คลิกเมนู 'Options' -> ติ๊ก 'List All Devices'")
                self._log("   2. ช่องบนเลือก 'USB Serial Converter A' หรือ 'Digilent USB Device (Interface 0)'")
                self._log("   3. ช่องขวาเลือก 'WinUSB' แล้วกดปุ่ม 'Replace Driver'")
            except Exception as e:
                self._log(f"❌ ไม่สามารถเปิด Zadig อัตโนมัติ: {e}")
                self._log(f"💡 สามารถคลิกขวาที่ไฟล์นี้แล้วกด 'Run as administrator' ได้โดยตรง:")
                self._log(f"   {found}")
        else:
            import webbrowser
            self._log("🌐 กำลังเปิดหน้าดาวน์โหลด Zadig (https://zadig.akeo.ie/)...")
            webbrowser.open("https://zadig.akeo.ie/")

    def _browse_vivado(self):
        f = filedialog.askopenfilename(
            parent=self,
            title="ระบุตำแหน่งไฟล์ vivado.bat หรือ vivado_lab.bat",
            filetypes=[("Vivado Executable", "*.bat;*.exe"), ("All files", "*.*")],
            initialdir=r"C:\Xilinx",
        )
        if f and os.path.isfile(f):
            self.programmers["vivado"] = f
            txt, col = self._get_engine_status_summary()
            self.lbl_eng_status.config(text=txt, fg=col)
            self._log(f"ตั้งค่าเส้นทาง Vivado สำเร็จ: {f}")

    def _log(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.update_idletasks()

    def _call_parent_uart_upload(self):
        if hasattr(self.master, "upload_to_board"):
            self.destroy()
            self.master.upload_to_board()

    def _start_flashing_thread(self):
        if self.is_flashing:
            return

        bit_path = self.bit_path_var.get().strip()
        if not bit_path or not os.path.isfile(bit_path):
            messagebox.showwarning(
                "ไม่พบไฟล์ Bitstream",
                "กรุณาระบุไฟล์ .bit ของ CPU ก่อนเริ่มแฟลช\n\n"
                "คุณสามารถกดปุ่ม 'เลือกไฟล์ .bit...' เพื่อเลือก Bitstream สำเร็จรูป\n"
                "หรือกด '⬆ อัปโหลดโค้ด MIPS / C (USB UART)' เพื่อรันโค้ดบนบอร์ดทันที",
                parent=self,
            )
            return

        prog_type = None
        prog_bin = None
        # Prioritize bundled lightweight openFPGALoader so users never need 50GB Vivado!
        if self.programmers.get("openfpgaloader"):
            prog_type = "openfpgaloader"
            prog_bin = self.programmers["openfpgaloader"]
        elif self.programmers.get("vivado"):
            prog_type = "vivado"
            prog_bin = self.programmers["vivado"]
        elif self.programmers.get("djtgcfg"):
            prog_type = "djtgcfg"
            prog_bin = self.programmers["djtgcfg"]

        if not prog_bin:
            messagebox.showinfo(
                "ต้องการเครื่องมือแฟลช JTAG",
                "ไม่พบเครื่องมือแฟลชบอร์ด FPGA ในระบบ\n\n"
                "โปรดตรวจสอบว่าโฟลเดอร์ toolchain/openFPGALoader อยู่ในโปรแกรม\n"
                "หรือกดปุ่ม 'ระบุตำแหน่ง Vivado...' เพื่อเลือกไฟล์ vivado.bat\n"
                "หรือหากบอร์ดได้แฟลช CPU ไว้อยู่แล้ว ให้ใช้ปุ่ม 'อัปโหลดโค้ด MIPS / C (USB UART)'",
                parent=self,
            )
            return

        self.is_flashing = True
        self.btn_flash.config(text="⏳ กำลังแฟลช CPU ลงบอร์ด...", bg=ACCENT_AMBER, state=tk.DISABLED)
        sel_cpu = self.cpu_core_var.get()
        self._log("\n" + "=" * 65)
        self._log(f"🚀 เริ่มกระบวนการแฟลช CPU: {sel_cpu}")
        self._log(f"เป้าหมาย: บอร์ด {self.board_var.get()}")
        self._log(f"ไฟล์ Bitstream: {bit_path}")
        self._log(f"เครื่องมือแฟลช: {prog_type} ({os.path.basename(prog_bin)})")
        self._log("=" * 65)

        def worker():
            ok = False
            msg = ""
            device_hint = "xc7a100t"
            if "50t" in self.board_var.get().lower():
                device_hint = "xc7a50t"
            elif "basys" in self.board_var.get().lower():
                device_hint = "xc7a35t"
            elif "virtex" in self.board_var.get().lower():
                device_hint = "xc6v"

            try:
                if prog_type == "openfpgaloader":
                    ok, msg = program_fpga_with_openfpgaloader(prog_bin, bit_path, board=self.board_var.get(), on_log=self._log)
                elif prog_type == "vivado":
                    ok, msg = program_fpga_with_vivado(prog_bin, bit_path, device_hint=device_hint, on_log=self._log)
                elif prog_type == "djtgcfg":
                    ok, msg = program_fpga_with_djtgcfg(prog_bin, bit_path, on_log=self._log)
            except Exception as ex:
                ok = False
                msg = str(ex)

            def done():
                self.is_flashing = False
                self.btn_flash.config(text="⚡ เริ่มแฟลช CPU ลงบอร์ดทันที (Burn Bitstream)", bg=ACCENT_GREEN, state=tk.NORMAL)
                if ok:
                    self._log(f"\n✅ {msg}")
                    messagebox.showinfo("แฟลชสำเร็จ", msg, parent=self)
                    if self.on_success_callback:
                        self.on_success_callback()
                else:
                    self._log(f"\n❌ ข้อผิดพลาด: {msg}")
                    if "unable to open ftdi" in msg.lower() or "usb_open" in msg.lower():
                        self._log("\n" + "=" * 65)
                        self._log("💡 ตรวจพบว่าบอร์ดต่ออยู่ แต่ Windows ยังไม่เปิดสิทธิ์ WinUSB:")
                        self._log("1. ในหน้าต่าง Zadig ที่กำลังเปิด ให้ไปที่ Options -> ติ๊ก 'List All Devices'")
                        self._log("2. ช่อง Dropdown เลือก 'USB Serial Converter A' หรือ 'Digilent USB Device (Interface 0)'")
                        self._log("3. ฝั่งขวา (Target Driver) เลือกเป็น 'WinUSB' แล้วกดปุ่ม 'Replace Driver'")
                        self._log("4. รอ 5 วินาที แล้วกลับมากดปุ่ม '⚡ เริ่มแฟลช CPU ลงบอร์ดทันที' อีกครั้งได้เลย!")
                        self._log("=" * 65)
                        ans = messagebox.askyesno(
                            "ต้องเปิดสิทธิ์ไดรเวอร์ JTAG (ทำครั้งเดียว)",
                            "ตรวจพบบอร์ด FPGA เสียบสาย USB อยู่แล้ว แต่ระบบ Windows กำหนดไดรเวอร์เดิม (FTDIBUS) ล็อกพอร์ต JTAG ไว้\n\n"
                            "วิธีแก้ไขง่ายมากใน 1 นาที (ทำครั้งเดียวตลอดชีพ ไม่ต้องลง Vivado):\n"
                            "1. เปิด Zadig (กด 'Yes' ด้านล่างเพื่อเปิดทันที)\n"
                            "2. ไปที่เมนู Options -> ติ๊ก 'List All Devices'\n"
                            "3. ในช่อง Dropdown เลือก 'USB Serial Converter A' (หรือ Interface 0)\n"
                            "4. ทางขวาเลือก 'WinUSB' แล้วกดปุ่ม 'Replace Driver'\n\n"
                            "คุณต้องการเปิดโปรแกรม Zadig เพื่อสลับไดรเวอร์ตอนนี้หรือไม่?",
                            parent=self,
                        )
                        if ans:
                            self._open_zadig()
                    else:
                        messagebox.showerror("การแฟลชล้มเหลว", msg, parent=self)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

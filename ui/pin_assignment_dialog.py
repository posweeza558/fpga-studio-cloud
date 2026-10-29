# -*- coding: utf-8 -*-
"""
FPGA Studio — Hardware Pin & Address Configuration Dialog (Pin & MMIO Planner):
Frameless Spotify/NVIDIA Dark Modal Dialog styled identically to the Import Wizard.
Allows users to visually inspect and customize:
  1. Hardware HDL port pin bindings (Clock, Reset, Address Bus, Data In/Out, WE).
  2. MMIO Base Addresses for peripherals (LEDs, Switches, 7-Segment, UART, VGA Framebuffer).
Saves configuration to cpu_manifest.json and updates the Nexys A7 simulator in real time.
"""

import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox

from config.theme import (
    BG_BLACK,
    BG_TITLEBAR,
    BG_ACTIVITY,
    BG_SIDEBAR,
    BG_EDITOR,
    BG_POPUP,
    BG_ELEVATED,
    BORDER_COLOR,
    ACCENT_GREEN,
    ACCENT_AMBER,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    FONT_UI,
    FONT_CODE,
    FONT_ICON,
)
from core.hdl_analyzer import extract_cpu_ports, inspect_cpu_hardware_ports, invalidate_hdl_cache
from ui.installer_wizard import BaseFramelessWizardDialog
from ui.widgets import SpotifyPillButton


class PinAssignmentDialog(BaseFramelessWizardDialog):
    """
    Hardware Pin & MMIO Address Configuration Dialog.
    Styled identically to the Setup & Import Wizard (Frameless, DWM rounded, Spotify/NVIDIA dark theme).
    """

    def __init__(self, parent, target_file_path=None, cpu_info=None, on_save=None):
        self.cpu_info = cpu_info or {}
        if target_file_path:
            self.target_file_path = os.path.abspath(target_file_path)
        else:
            self.target_file_path = self.cpu_info.get("path", "")

        self.on_save = on_save
        self.pkg_dir = os.path.dirname(self.target_file_path) if self.target_file_path else os.getcwd()
        self.cpu_name = self.cpu_info.get("name") or (os.path.splitext(os.path.basename(self.target_file_path))[0] if self.target_file_path else "Standard CPU")

        # 1. Extract physical ports from HDL file (if file exists)
        if self.target_file_path and os.path.exists(self.target_file_path):
            self.port_data = extract_cpu_ports(self.target_file_path)
            self.all_ports = self.port_data.get("ports", [])
            self.detailed = self.port_data.get("detailed_ports", [])
            self.roles = self.port_data.get("detected_roles", {})
        else:
            self.port_data = {"ports": [], "detailed_ports": [], "detected_roles": {}}
            self.all_ports = ["clk", "rst", "ram_addr_o", "ram_data_o", "ram_data_i", "ram_we_o"]
            self.detailed = []
            self.roles = {
                "clock": "clk", "reset": "rst",
                "mem_addr": "ram_addr_o", "mem_wdata": "ram_data_o",
                "mem_rdata": "ram_data_i", "mem_we": "ram_we_o"
            }

        # 2. Load existing manifest mapping if present
        self.manifest_path = os.path.join(self.pkg_dir, "cpu_manifest.json")
        self.existing_manifest_raw = {}
        self.existing_mapping = {}
        self.existing_mmio = {}
        self.existing_is_alu = False

        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as jf:
                    mdata = json.load(jf)
                    self.existing_manifest_raw = dict(mdata)
                    self.existing_mapping = mdata.get("port_mapping", {})
                    self.existing_mmio = mdata.get("mmio_mapping", {})
                    self.existing_is_alu = mdata.get("is_standalone_alu", False)
            except Exception:
                pass

        # 3. Form Variables — Pin Mapping
        self.clk_var = tk.StringVar(value=self.existing_mapping.get("clk") or self.roles.get("clock") or "")
        self.rst_var = tk.StringVar(value=self.existing_mapping.get("rst") or self.roles.get("reset") or "")
        self.addr_var = tk.StringVar(value=self.existing_mapping.get("mem_addr") or self.roles.get("mem_addr") or "")
        self.wdata_var = tk.StringVar(value=self.existing_mapping.get("mem_wdata") or self.roles.get("mem_wdata") or "")
        self.rdata_var = tk.StringVar(value=self.existing_mapping.get("mem_rdata") or self.roles.get("mem_rdata") or "")
        self.we_var = tk.StringVar(value=self.existing_mapping.get("mem_we") or self.roles.get("mem_we") or "")

        # Has Memory Bus capability
        has_bus_detect = bool(self.addr_var.get() or self.roles.get("mem_addr"))

        # Default GPIO & UART (Clear, compact labels that fit neatly in dropdowns)
        default_gpio = self.existing_mapping.get("led")
        if not default_gpio or "Memory Bus" in default_gpio or default_gpio.startswith("("):
            default_gpio = "MMIO 0xF0000000 (Nexys A7 Bus)" if has_bus_detect else "(ไม่ระบุ / Unmapped)"
        self.gpio_var = tk.StringVar(value=default_gpio)

        default_uart = self.existing_mapping.get("uart_tx")
        if not default_uart or "Memory Bus" in default_uart or default_uart.startswith("("):
            default_uart = "MMIO 0xF0000010 (Nexys A7 Bus)" if has_bus_detect else "(ไม่ระบุ / Unmapped)"
        self.uart_var = tk.StringVar(value=default_uart)

        # Standalone ALU flag
        init_alu = self.existing_is_alu or ("alu_only" in self.cpu_name.lower()) or (not has_bus_detect and len(self.all_ports) > 0)
        self.is_alu_var = tk.BooleanVar(value=init_alu)

        # 4. Form Variables — Unified MMIO Addresses (supports both individual and legacy keys)
        self.mmio_led_var = tk.StringVar(value=self.existing_mmio.get("led") or self.existing_mmio.get("led_seg") or "0xF0000000")
        self.mmio_sw_var = tk.StringVar(value=self.existing_mmio.get("sw") or "0xF0000004")
        self.mmio_seg7_var = tk.StringVar(value=self.existing_mmio.get("seg7") or "0xF0000008")
        self.mmio_btn_var = tk.StringVar(value=self.existing_mmio.get("btn") or self.existing_mmio.get("btn_rgb") or "0xF000000C")
        self.mmio_uart_var = tk.StringVar(value=self.existing_mmio.get("uart_tx") or "0xF0000010")
        self.mmio_rgb_var = tk.StringVar(value=self.existing_mmio.get("rgb") or "0xF0000018")
        self.mmio_vga_var = tk.StringVar(value=self.existing_mmio.get("vga") or "0xFF000000")

        # Active tab state: 'pins' | 'addresses'
        self.active_tab = "pins"

        super().__init__(parent, "FPGA Studio — การกำหนดขาพอร์ตและแอดเดรสฮาร์ดแวร์ (Pin & Address Configuration)", 820, 720)
        self._build_ui()

    def _build_ui(self):
        for w in self.container.winfo_children():
            w.destroy()

        # 1. Top Banner Header (Frameless Import-Wizard style)
        header = tk.Frame(self.container, bg=BG_ACTIVITY, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_inner = tk.Frame(header, bg=BG_ACTIVITY)
        h_inner.pack(fill="both", expand=True, padx=20, pady=8)

        tk.Label(h_inner, text="📐", font=(FONT_ICON, 18), bg=BG_ACTIVITY, fg=ACCENT_GREEN).pack(side="left", padx=(0, 12))
        tb = tk.Frame(h_inner, bg=BG_ACTIVITY)
        tb.pack(side="left", fill="y")
        tk.Label(tb, text="กำหนดขาพอร์ตและแอดเดรสฮาร์ดแวร์ (Pin & Address Configuration)",
                 font=(FONT_UI, 11, "bold"), bg=BG_ACTIVITY, fg=TXT_BRIGHT).pack(anchor="w")
        tk.Label(tb, text="ตรวจสอบและปรับเปลี่ยนการจับคู่พอร์ต HDL กับช่วงแอดเดรสหน่วยความจำ (MMIO)",
                 font=(FONT_UI, 8), bg=BG_ACTIVITY, fg=TXT_MUTED).pack(anchor="w")

        # 2. Target CPU Overview Card (Elevated Dark Box)
        card = tk.Frame(self.container, bg=BG_ELEVATED, padx=14, pady=8)
        card.pack(fill="x", padx=20, pady=(8, 6))

        top_info = tk.Frame(card, bg=BG_ELEVATED)
        top_info.pack(fill="x")

        fname = os.path.basename(self.target_file_path) if self.target_file_path else "Built-in Core"
        tk.Label(top_info, text=f"โมดูล CPU: {self.cpu_name.upper()} ({fname})",
                 font=(FONT_UI, 9, "bold"), bg=BG_ELEVATED, fg=TXT_BRIGHT).pack(side="left")

        # Status badge
        if self.is_alu_var.get():
            badge_txt = "STANDALONE ALU (UNMAPPED)"
            badge_fg = ACCENT_AMBER
        elif len(self.all_ports) == 0:
            badge_txt = "CLOSED TESTBENCH"
            badge_fg = TXT_MUTED
        else:
            badge_txt = "BUS CONNECTED (MMIO SOC)"
            badge_fg = ACCENT_GREEN

        tk.Label(top_info, text=f"[{badge_txt}]", font=(FONT_CODE, 8, "bold"), bg=BG_ELEVATED, fg=badge_fg).pack(side="right")

        if self.detailed:
            sample_p = [f"{p['name']}({'in' if p['dir']=='input' else 'out'}:{p['width']})" for p in self.detailed[:8]]
            ports_desc = f"พอร์ตที่ตรวจพบในไฟล์: {len(self.all_ports)} ขาพอร์ต ({', '.join(sample_p)}{'...' if len(self.detailed)>8 else ''})"
        elif self.all_ports:
            ports_desc = f"พอร์ตที่ตรวจพบในไฟล์: {len(self.all_ports)} ขาพอร์ต ({', '.join(self.all_ports[:10])}{'...' if len(self.all_ports)>10 else ''})"
        else:
            ports_desc = "วงจรจำลองแบบปิด (0 พอร์ตภายนอก / Self-Contained Model)"
        tk.Label(card, text=ports_desc, font=(FONT_CODE, 8), bg=BG_ELEVATED, fg=TXT_MUTED, wraplength=720, justify="left").pack(anchor="w", pady=(2, 0))

        # 3. Tab Buttons Header (Capsule Switches)
        tab_bar = tk.Frame(self.container, bg=BG_BLACK, height=36)
        tab_bar.pack(fill="x", padx=20, pady=(4, 6))

        self.btn_tab_pins = tk.Button(
            tab_bar, text="🔌  1. การจับคู่ขาพอร์ตฮาร์ดแวร์ (Pin Mapping)",
            command=lambda: self._switch_tab("pins"),
            font=(FONT_UI, 8, "bold"), bg=BG_ELEVATED if self.active_tab == "pins" else BG_POPUP,
            fg=TXT_BRIGHT if self.active_tab == "pins" else TXT_MUTED,
            bd=0, highlightthickness=1,
            highlightbackground=ACCENT_GREEN if self.active_tab == "pins" else BORDER_COLOR,
            padx=14, pady=4, cursor="hand2"
        )
        self.btn_tab_pins.pack(side="left", padx=(0, 6))

        self.btn_tab_mmio = tk.Button(
            tab_bar, text="🗺️  2. ช่วงแอดเดรสหน่วยความจำ (MMIO Address Space)",
            command=lambda: self._switch_tab("addresses"),
            font=(FONT_UI, 8, "bold"), bg=BG_ELEVATED if self.active_tab == "addresses" else BG_POPUP,
            fg=TXT_BRIGHT if self.active_tab == "addresses" else TXT_MUTED,
            bd=0, highlightthickness=1,
            highlightbackground=ACCENT_GREEN if self.active_tab == "addresses" else BORDER_COLOR,
            padx=14, pady=4, cursor="hand2"
        )
        self.btn_tab_mmio.pack(side="left")

        # 4. Bottom Action Bar (Packed FIRST with side="bottom" to guarantee it is NEVER pushed out or clipped)
        bbar = tk.Frame(self.container, bg=BG_BLACK, height=52)
        bbar.pack(fill="x", side="bottom", padx=20, pady=(10, 16))

        SpotifyPillButton(bbar, text="ยกเลิก (Cancel)", command=self.destroy,
                          bg_parent=BG_BLACK, fill_col=BG_POPUP, fg_col=TXT_MUTED,
                          height=34, pad_x=18).pack(side="left")

        SpotifyPillButton(bbar, text="💾  บันทึกการกำหนดค่า (Save & Apply Changes)", command=self._save_all,
                          bg_parent=BG_BLACK, fill_col=ACCENT_GREEN, fg_col="#000000",
                          height=34, pad_x=24).pack(side="right")

        # 5. Content Area (Fills remaining middle space)
        self.content_frame = tk.Frame(self.container, bg=BG_BLACK)
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        if self.active_tab == "pins":
            self._render_pins_tab()
        else:
            self._render_mmio_tab()

    def _switch_tab(self, tab):
        self.active_tab = tab
        self._build_ui()

    def _render_pins_tab(self):
        """Renders Pin Mapping view with comfortable line spacing (no overlapping text)."""
        # Standalone ALU toggle
        alu_box = tk.Frame(self.content_frame, bg=BG_SIDEBAR, padx=12, pady=6, bd=1, relief="solid")
        alu_box.pack(fill="x", pady=(0, 6))
        tk.Checkbutton(alu_box, text="⚙️ กำหนดให้เป็น Standalone Pure ALU Core (วงจรคำนวณเดี่ยว — ไม่มี Memory Bus และตัดการเชื่อมต่อ I/O บอร์ด)",
                       variable=self.is_alu_var, command=self._on_alu_toggle,
                       font=(FONT_UI, 8, "bold"), bg=BG_SIDEBAR, fg=ACCENT_AMBER,
                       selectcolor=BG_POPUP, activebackground=BG_SIDEBAR).pack(anchor="w")

        port_options = ["(ไม่ระบุ / Unmapped)"] + self.all_ports

        gpio_options = ["MMIO 0xF0000000 (Nexys A7 Bus)", "(ไม่ระบุ / Unmapped)"] + self.all_ports
        uart_options = ["MMIO 0xF0000010 (Nexys A7 Bus)", "(ไม่ระบุ / Unmapped)"] + self.all_ports

        rows = [
            ("ขาสัญญาณ Address Bus (Memory Address Out):", self.addr_var, port_options, "สายส่ง Data Address จาก CPU ไปยัง RAM / MMIO (32-bit เช่น ram_addr_o)"),
            ("ขาสัญญาณ Write Enable (Memory Write Strobe):", self.we_var, port_options, "สายควบคุมการเขียนข้อมูล (WE / Write Enable เช่น ram_we_o)"),
            ("ขาสัญญาณ Write Data (Memory Data Out):", self.wdata_var, port_options, "สายส่งข้อมูลจาก CPU ไปยัง RAM หรืออุปกรณ์ (32-bit เช่น ram_data_o)"),
            ("ขาสัญญาณ Read Data (Memory Data In):", self.rdata_var, port_options, "สายรับข้อมูลจาก RAM หรืออุปกรณ์กลับเข้า CPU (32-bit เช่น ram_data_i)"),
            ("ขาสัญญาณนาฬิกา (System Clock):", self.clk_var, port_options, "ขาสัญญาณ Clock สำหรับซิงโครไนซ์วงจร เช่น clk"),
            ("ขาสัญญาณรีเซ็ต (System Reset):", self.rst_var, port_options, "ขาสัญญาณ Reset (Active High หรือ Low เช่น rst, rst_n)"),
            ("ขาต่อตรง GPIO LEDs/Switches (ตัวเลือก):", self.gpio_var, gpio_options, "ค่าเริ่มต้น: เชื่อมต่อผ่าน MMIO 0xF0000000 (เลือกเฉพาะกรณี CPU ต่อขาตรง)"),
            ("ขาต่อตรง UART TX (ตัวเลือก):", self.uart_var, uart_options, "ค่าเริ่มต้น: เชื่อมต่อผ่าน MMIO 0xF0000010 (เลือกเฉพาะกรณี CPU ต่อขาตรง)"),
        ]

        self.combos = []
        for label_text, var, options, tip in rows:
            # Row container with comfortable line spacing
            r = tk.Frame(self.content_frame, bg=BG_BLACK)
            r.pack(fill="x", pady=3)

            # Label box with fixed width and natural height to prevent text submerging/overlap
            lbl_box = tk.Frame(r, bg=BG_BLACK, width=340)
            lbl_box.pack(side="left", padx=(0, 8))

            tk.Label(lbl_box, text=label_text, font=(FONT_UI, 8, "bold"),
                     bg=BG_BLACK, fg=TXT_PRIMARY, anchor="w").pack(fill="x", anchor="w")
            tk.Label(lbl_box, text=tip, font=(FONT_UI, 8),
                     bg=BG_BLACK, fg=TXT_MUTED, anchor="w").pack(fill="x", anchor="w", pady=(1, 0))

            combo = ttk.Combobox(r, textvariable=var, values=options, state="readonly", width=33, font=(FONT_CODE, 8))
            combo.pack(side="left", padx=(0, 8), pady=2)
            self.combos.append(combo)

            cur_val = var.get()
            if "MMIO" in cur_val:
                tk.Label(r, text="✓ MMIO Active", font=(FONT_CODE, 8, "bold"), bg=BG_BLACK, fg=ACCENT_GREEN).pack(side="left")
            elif cur_val and not cur_val.startswith("(") and cur_val != "(ไม่ระบุ / Unmapped)":
                tk.Label(r, text="✓ Pin Mapped", font=(FONT_CODE, 8, "bold"), bg=BG_BLACK, fg=ACCENT_GREEN).pack(side="left")

        self._on_alu_toggle()

    def _render_mmio_tab(self):
        """Renders MMIO Address Space Mapping view (Editable Hex addresses)."""
        card_desc = tk.Frame(self.content_frame, bg=BG_SIDEBAR, padx=12, pady=8)
        card_desc.pack(fill="x", pady=(0, 8))
        tk.Label(card_desc, text="กำหนดช่วงแอดเดรสสำหรับอุปกรณ์ต่อพ่วงบนบอร์ดเสมือน Nexys A7 (MMIO Base Addresses):",
                 font=(FONT_UI, 8, "bold"), bg=BG_SIDEBAR, fg=TXT_BRIGHT).pack(anchor="w")
        tk.Label(card_desc, text="สำหรับ CPU ที่มี Memory Bus (เช่น OpenMIPS): เมื่อ CPU เขียน/อ่านแอดเดรสเหล่านี้ จะเชื่อมต่อกับอุปกรณ์โดยอัตโนมัติ",
                 font=(FONT_UI, 8), bg=BG_SIDEBAR, fg=TXT_MUTED).pack(anchor="w", pady=(2, 0))

        mmio_items = [
            ("16-bit Discrete LEDs (LD0..LD15)", self.mmio_led_var, "0xF0000000", "เขียน 16-bit: แสดงผลออกไฟ LED 16 ดวงบนบอร์ด"),
            ("16-bit Slide Switches (SW0..SW15)", self.mmio_sw_var, "0xF0000004", "อ่าน 16-bit: สถานะสวิตช์เลื่อน 16 ตัวบนบอร์ด"),
            ("8-Digit 7-Segment Display", self.mmio_seg7_var, "0xF0000008", "เขียน 32-bit: แสดงตัวเลขฐาน 16 บนจอ 7-Segment 8 หลัก"),
            ("Push Buttons (BTNC/U/L/R/D)", self.mmio_btn_var, "0xF000000C", "อ่าน 6-bit: ปุ่มกด 5 ทิศทางและปุ่มรีเซ็ต"),
            ("USB-UART Serial (TX/RX + Status +4)", self.mmio_uart_var, "0xF0000010", "ส่ง/รับอักขระ Serial Monitor 115200 8-N-1 (Status = Base + 4)"),
            ("Dual RGB LEDs (LD16, LD17)", self.mmio_rgb_var, "0xF0000018", "เขียน 24-bit: ควบคุมไฟสี RGB ทั้ง 2 ดวง ([23:12]=LD16, [11:0]=LD17)"),
            ("VGA Graphic Framebuffer", self.mmio_vga_var, "0xFF000000", "พื้นที่หน่วยความจำแสดงภาพ VGA (640x480 @ 60Hz)"),
        ]

        for title, var, default_hex, desc in mmio_items:
            r = tk.Frame(self.content_frame, bg=BG_ELEVATED, padx=12, pady=5)
            r.pack(fill="x", pady=2)

            # 1. Right-side controls (packed to the right first so they never get squished)
            def _make_reset(v, d):
                return lambda: v.set(d)
            b_reset = tk.Button(r, text="ค่าเริ่มต้น", font=(FONT_UI, 7), bg=BG_POPUP, fg=TXT_MUTED,
                                bd=0, highlightthickness=0, padx=8, pady=3, cursor="hand2",
                                command=_make_reset(var, default_hex))
            b_reset.pack(side="right", padx=(8, 0))

            e = tk.Entry(r, textvariable=var, font=(FONT_CODE, 9, "bold"), bg=BG_POPUP, fg=ACCENT_GREEN,
                         insertbackground=TXT_BRIGHT, relief="flat", bd=2, width=13)
            e.pack(side="right", padx=(4, 0))

            tk.Label(r, text="Address:", font=(FONT_CODE, 8), bg=BG_ELEVATED, fg=TXT_PRIMARY).pack(side="right", padx=(8, 4))

            # 2. Left-side info labels (natural expansion, generous height, no submerged text)
            info_box = tk.Frame(r, bg=BG_ELEVATED)
            info_box.pack(side="left", fill="both", expand=True)

            tk.Label(info_box, text=title, font=(FONT_UI, 8, "bold"), bg=BG_ELEVATED, fg=TXT_BRIGHT, anchor="w").pack(fill="x", anchor="w")
            tk.Label(info_box, text=desc, font=(FONT_UI, 8), bg=BG_ELEVATED, fg=TXT_MUTED, anchor="w").pack(fill="x", anchor="w", pady=(2, 0))

    def _on_alu_toggle(self):
        if not hasattr(self, "combos") or not self.combos:
            return
        is_alu = self.is_alu_var.get()
        if is_alu:
            for c in self.combos[:4]:
                c.config(state="disabled")
        else:
            for c in self.combos[:4]:
                c.config(state="readonly")

    def _save_all(self):
        is_alu = self.is_alu_var.get()

        def clean_val(v):
            val = v.get().strip()
            if "MMIO" in val or "Unmapped" in val or val.startswith("("):
                return ""
            return val

        def clean_hex(v, fallback):
            val = v.get().strip().upper()
            if not val.startswith("0X"):
                val = "0X" + val
            if re.match(r"^0X[0-9A-F]{1,8}$", val):
                return "0x" + val[2:]
            return fallback

        port_mapping = {
            "clk": clean_val(self.clk_var),
            "rst": clean_val(self.rst_var),
            "mem_addr": "" if is_alu else clean_val(self.addr_var),
            "mem_we": "" if is_alu else clean_val(self.we_var),
            "mem_wdata": "" if is_alu else clean_val(self.wdata_var),
            "mem_rdata": "" if is_alu else clean_val(self.rdata_var),
            "led": "" if is_alu else clean_val(self.gpio_var),
            "uart_tx": "" if is_alu else clean_val(self.uart_var),
        }

        led_hex = clean_hex(self.mmio_led_var, "0xF0000000")
        sw_hex = clean_hex(self.mmio_sw_var, "0xF0000004")
        seg7_hex = clean_hex(self.mmio_seg7_var, "0xF0000008")
        btn_hex = clean_hex(self.mmio_btn_var, "0xF000000C")
        uart_hex = clean_hex(self.mmio_uart_var, "0xF0000010")
        uart_stat_int = (int(uart_hex, 16) + 4) & 0xFFFFFFFF
        rgb_hex = clean_hex(self.mmio_rgb_var, "0xF0000018")
        vga_hex = clean_hex(self.mmio_vga_var, "0xFF000000")

        mmio_mapping = {
            "led": led_hex,
            "sw": sw_hex,
            "seg7": seg7_hex,
            "btn": btn_hex,
            "uart_tx": uart_hex,
            "uart_rx": uart_hex,
            "uart_stat": f"0x{uart_stat_int:08X}",
            "rgb": rgb_hex,
            "vga": vga_hex,
        }

        manifest_data = dict(self.existing_manifest_raw)
        manifest_data.update({
            "cpu_name": self.cpu_name,
            "target_file": os.path.basename(self.target_file_path) if self.target_file_path else "",
            "is_standalone_alu": is_alu,
            "port_mapping": port_mapping,
            "mmio_mapping": mmio_mapping,
        })

        # Save to cpu_manifest.json if directory exists
        if self.pkg_dir and os.path.isdir(self.pkg_dir):
            try:
                with open(self.manifest_path, "w", encoding="utf-8") as jf:
                    json.dump(manifest_data, jf, indent=2, ensure_ascii=False)
                invalidate_hdl_cache(self.target_file_path)
            except Exception as e:
                messagebox.showerror("Error", f"ไม่สามารถบันทึก cpu_manifest.json ได้: {e}", parent=self)
                return

        if self.on_save:
            self.on_save(manifest_data)

        messagebox.showinfo("บันทึกสำเร็จ",
                            "บันทึกการกำหนดขาพอร์ตและแอดเดรสฮาร์ดแวร์เรียบร้อยแล้ว!\nระบบได้ปรับปรุงสถานะการเชื่อมต่อกับบอร์ดเสมือน Nexys A7 ทันที",
                            parent=self)
        self.destroy()

# -*- coding: utf-8 -*-
"""
FPGA Studio — 5-Stage Pipeline Hazard Analyzer & RTL Testbench Co-Simulation Dialog
Frameless Spotify Dark modal window providing:
  - Cycle-accurate CPI, RAW Load-Use Stall, Forwarding (EX->EX, MEM->EX), and Branch Flush/Delay metrics
  - Cycle-by-cycle 5-Stage Pipeline Waterfall (IF / ID / EX / MEM / WB)
  - Differential RTL Verification status & 1-click export of Verilog Testbench + VCD Waveform scripts
"""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from config.theme import (
    BG_BLACK,
    BG_ACTIVITY,
    BG_EDITOR,
    BG_ELEVATED,
    BG_PILL_INACT,
    BG_PILL_ACT,
    BORDER_COLOR,
    ACCENT_GREEN,
    ACCENT_AMBER,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    TXT_ON_WHITE,
    FONT_UI,
    FONT_CODE,
    FONT_ICON,
)
from core.rtl_cosim import (
    run_rtl_cosim,
    export_rtl_testbench,
    generate_gtkwave_savefile,
    find_gtkwave_bin,
    detect_verilog_simulator,
)
from ui.installer_wizard import BaseFramelessWizardDialog
from ui.widgets import SpotifyPillButton, SpotifyAutoScrollbar


class RTLVerifyDialog(BaseFramelessWizardDialog):
    """5-Stage Pipeline Hazard Analyzer & RTL Testbench Co-Simulation Dialog."""

    def __init__(self, parent, instructions, arch="mips", cpu_name="OpenMIPS 32-bit",
                 cpu_hdl_path=None, sw_init=0, btn_init=0, mmio_map=None, project_dir=None,
                 on_exported=None):
        self.instructions = instructions or []
        self.arch = arch
        self.cpu_name = cpu_name
        self.cpu_hdl_path = cpu_hdl_path
        self.sw_init = sw_init
        self.btn_init = btn_init
        self.mmio_map = mmio_map or {}
        self.project_dir = project_dir or os.getcwd()
        self.on_exported = on_exported
        self.active_tab = "hazards"
        self.cosim_res = None

        super().__init__(
            parent,
            "FPGA Studio — วิเคราะห์ 5-Stage Pipeline & ทดสอบ RTL Testbench",
            940,
            680,
        )
        self._run_analysis()
        self._build_ui()

    def _run_analysis(self):
        self.cosim_res = run_rtl_cosim(
            self.instructions,
            arch=self.arch,
            cpu_hdl_path=self.cpu_hdl_path,
            sim_cycles=500,
            sw_init=self.sw_init,
            btn_init=self.btn_init,
            mmio_map=self.mmio_map,
        )

    def _build_ui(self):
        for w in self.container.winfo_children():
            w.destroy()

        pipe = self.cosim_res["pipeline"]

        # 1. Top Header Banner
        header = tk.Frame(self.container, bg=BG_ACTIVITY, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_in = tk.Frame(header, bg=BG_ACTIVITY)
        h_in.pack(fill="both", expand=True, padx=20, pady=8)

        tk.Label(h_in, text="🔬", font=(FONT_ICON, 18), bg=BG_ACTIVITY, fg=ACCENT_GREEN).pack(side="left", padx=(0, 12))
        tb = tk.Frame(h_in, bg=BG_ACTIVITY)
        tb.pack(side="left", fill="y")
        tk.Label(
            tb,
            text=f"วิเคราะห์ 5-Stage Pipeline & RTL Verification  •  {self.cpu_name}",
            font=(FONT_UI, 11, "bold"),
            bg=BG_ACTIVITY,
            fg=TXT_BRIGHT,
        ).pack(anchor="w")
        from core.hdl_analyzer import inspect_cpu_hardware_ports
        caps = inspect_cpu_hardware_ports(self.cpu_hdl_path) if self.cpu_hdl_path else {}
        rtl_topo = caps.get("rtl_topology") or "5-Stage Pipelined RTL"
        tk.Label(
            tb,
            text=(
                f"สถาปัตยกรรม: {self.arch.upper()} ({rtl_topo})   •   ขนาดโปรแกรม ROM: {len(self.instructions)} คำสั่ง   •   "
                f"อินพุต SW=0x{self.sw_init:04X}, BTN=0x{self.btn_init:02X}"
            ),
            font=(FONT_UI, 8),
            bg=BG_ACTIVITY,
            fg=TXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # 2. Six Hardware Performance Metric Cards
        cards_row = tk.Frame(self.container, bg=BG_BLACK, padx=18, pady=10)
        cards_row.pack(fill="x")

        total_fwds = pipe["ex_forwards"] + pipe["mem_forwards"]
        ctrl_val = pipe["delay_slots"] if self.arch == "mips" else pipe["branch_flushes"]
        ctrl_lbl = "Delay Slots (MIPS)" if self.arch == "mips" else "Branch Flushes"
        cpi_col = ACCENT_GREEN if pipe["cpi"] <= 1.35 else ACCENT_AMBER

        metrics = [
            ("คำสั่งที่รันจริง (Insts)", f"{pipe['retired_instructions']}", TXT_BRIGHT),
            ("รอบนาฬิกาจริง (Cycles)", f"{pipe['total_cycles']}", ACCENT_GREEN),
            ("ค่าเฉลี่ย CPI", f"{pipe['cpi']:.2f}", cpi_col),
            ("Load-Use Stalls", f"{pipe['load_use_stalls']}", ACCENT_AMBER if pipe["load_use_stalls"] else TXT_BRIGHT),
            ("Data Forwarding", f"{total_fwds}", ACCENT_GREEN),
            (ctrl_lbl, f"{ctrl_val}  ({pipe['runtime_25mhz_us']:.1f} µs)", TXT_BRIGHT),
        ]

        for idx, (m_title, m_val, m_col) in enumerate(metrics):
            c = tk.Frame(
                cards_row,
                bg="#161616",
                padx=10,
                pady=8,
                highlightthickness=1,
                highlightbackground="#282828",
            )
            c.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 6, 0))
            tk.Label(c, text=m_title, font=(FONT_UI, 8), bg="#161616", fg=TXT_MUTED).pack(anchor="w")
            tk.Label(c, text=m_val, font=(FONT_CODE, 11, "bold"), bg="#161616", fg=m_col).pack(anchor="w", pady=(3, 0))

        # 3. Clean Hardware & Pipeline Summary Bar (Single-line layout, no word-wrap splitting Thai text)
        rgb_vals = pipe.get("rgb_value", [0, 0])
        rgb_hex = ((rgb_vals[0] & 0xFFF) << 12) | (rgb_vals[1] & 0xFFF) if len(rgb_vals) >= 2 else 0

        banner = tk.Frame(
            self.container,
            bg="#151917",
            padx=14,
            pady=8,
            highlightthickness=1,
            highlightbackground="#28352D",
        )
        banner.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            banner,
            text=(
                f"●  สถานะพอร์ตเอาต์พุต (MMIO Output)   •   "
                f"LED = 0x{pipe['led_value'] & 0xFFFF:04X}   •   "
                f"7-SEG = 0x{pipe['seg7_value'] & 0xFFFFFFFF:08X}   •   "
                f"RGB = 0x{rgb_hex:06X}"
            ),
            font=(FONT_CODE, 9, "bold"),
            bg="#151917",
            fg=ACCENT_GREEN,
            anchor="w",
        ).pack(fill="x")

        div_stalls = pipe.get("div_stalls", 0)
        div_txt = f"   •   Divider Stalls = {div_stalls} รอบ" if div_stalls else ""
        tk.Label(
            banner,
            text=(
                f"EX→EX Forwarding = {pipe['ex_forwards']} ครั้ง   •   "
                f"MEM→EX Forwarding = {pipe['mem_forwards']} ครั้ง{div_txt}"
            ),
            font=(FONT_UI, 8),
            bg="#151917",
            fg=TXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        if self.cosim_res.get("ran_rtl"):
            rtl_msg = self.cosim_res.get("message", "")
            msg_col = ACCENT_GREEN if self.cosim_res.get("passed") else ACCENT_AMBER
            tk.Label(
                banner,
                text=f"🔬 {rtl_msg}",
                font=(FONT_UI, 8, "bold"),
                bg="#151917",
                fg=msg_col,
                anchor="w",
            ).pack(fill="x", pady=(3, 0))

        # 4. Tab Bar for Hazard Events vs. 5-Stage Waterfall Timeline + Quick Actions
        tab_strip = tk.Frame(self.container, bg=BG_BLACK, padx=18, pady=4)
        tab_strip.pack(fill="x")

        self.btn_tab_haz = SpotifyPillButton(
            tab_strip,
            text=f"⚡ รายการ Hazards & Forwarding ({len(pipe['hazard_events'])})",
            bg_parent=BG_BLACK,
            fill_col=BG_PILL_ACT if self.active_tab == "hazards" else BG_PILL_INACT,
            fg_col=TXT_ON_WHITE if self.active_tab == "hazards" else TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"),
            pad_x=14,
            height=30,
            command=lambda: self._switch_tab("hazards"),
        )
        self.btn_tab_haz.pack(side="left", padx=(0, 8))

        self.btn_tab_time = SpotifyPillButton(
            tab_strip,
            text=f"⏱️ ไทม์ไลน์ 5-Stage Waterfall ({len(pipe['timeline'])} Cycles)",
            bg_parent=BG_BLACK,
            fill_col=BG_PILL_ACT if self.active_tab == "timeline" else BG_PILL_INACT,
            fg_col=TXT_ON_WHITE if self.active_tab == "timeline" else TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"),
            pad_x=14,
            height=30,
            command=lambda: self._switch_tab("timeline"),
        )
        self.btn_tab_time.pack(side="left")

        # Quick-access GTKWave & Export buttons in the tab bar (Always visible even on low-resolution/high-DPI screens)
        btn_tab_gtkwave = SpotifyPillButton(
            tab_strip,
            text="📈 ดูกราฟสัญญาณ (GTKWave)...",
            bg_parent=BG_BLACK,
            fill_col="#1E3A8A",
            fg_col=TXT_ON_WHITE,
            hover_fill="#2563EB",
            font_spec=(FONT_UI, 9, "bold"),
            pad_x=14,
            height=30,
            command=self._on_open_gtkwave,
        )
        btn_tab_gtkwave.pack(side="right")

        btn_tab_export = SpotifyPillButton(
            tab_strip,
            text="📦 ส่งออก RTL Testbench...",
            bg_parent=BG_BLACK,
            fill_col=BG_ELEVATED,
            fg_col=TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"),
            pad_x=12,
            height=30,
            command=self._on_export_testbench,
        )
        btn_tab_export.pack(side="right", padx=(0, 8))

        # 5. Footer Action Bar (PACK BEFORE body_frame so expand=True does not hide it!)
        footer = tk.Frame(self.container, bg=BG_ACTIVITY, height=52, padx=18)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        btn_rerun = SpotifyPillButton(
            footer,
            text="🔄 วิเคราะห์ใหม่",
            bg_parent=BG_ACTIVITY,
            fill_col=BG_ELEVATED,
            fg_col=TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"),
            pad_x=14,
            height=30,
            command=self._rerun_and_refresh,
        )
        btn_rerun.pack(side="right", pady=11)

        # 6. Table Body Area (PACK AFTER footer so it expands only within the middle space)
        self.body_frame = tk.Frame(
            self.container,
            bg=BG_EDITOR,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.body_frame.pack(fill="both", expand=True, padx=18, pady=(6, 10))
        self._populate_active_table()

    def _switch_tab(self, tab_name):
        self.active_tab = tab_name
        self.btn_tab_haz.set_style(
            fill_col=BG_PILL_ACT if tab_name == "hazards" else BG_PILL_INACT,
            fg_col=TXT_ON_WHITE if tab_name == "hazards" else TXT_BRIGHT,
        )
        self.btn_tab_time.set_style(
            fill_col=BG_PILL_ACT if tab_name == "timeline" else BG_PILL_INACT,
            fg_col=TXT_ON_WHITE if tab_name == "timeline" else TXT_BRIGHT,
        )
        self._populate_active_table()

    def _populate_active_table(self):
        for w in self.body_frame.winfo_children():
            w.destroy()

        pipe = self.cosim_res["pipeline"]
        scroll = SpotifyAutoScrollbar(self.body_frame, bg_track=BG_EDITOR)

        if self.active_tab == "hazards":
            cols = ("cycle", "pc", "asm", "type", "detail")
            tree = ttk.Treeview(self.body_frame, columns=cols, show="headings", yscrollcommand=scroll.set)
            scroll.command = tree.yview

            tree.heading("cycle", text="Cycle")
            tree.heading("pc", text="PC")
            tree.heading("asm", text="Assembly")
            tree.heading("type", text="Hazard / Bypass Event")
            tree.heading("detail", text="คำอธิบายการทำงานของฮาร์ดแวร์")

            tree.column("cycle", width=62, anchor="center")
            tree.column("pc", width=72, anchor="center")
            tree.column("asm", width=165, anchor="w")
            tree.column("type", width=205, anchor="w")
            tree.column("detail", width=375, anchor="w")

            tree.tag_configure("stall", background="#2B1E0D", foreground=ACCENT_AMBER)
            tree.tag_configure("flush", background="#2D1418", foreground=ACCENT_RED)
            tree.tag_configure("fwd", background=BG_EDITOR, foreground=ACCENT_GREEN)
            tree.tag_configure("empty", background=BG_EDITOR, foreground=TXT_MUTED)

            events = pipe["hazard_events"]
            if not events:
                tree.insert(
                    "",
                    tk.END,
                    values=("-", "-", "-", "No Hazards Detected", "ไม่พบ Stall หรือ Data Hazard ในช่วงคำสั่งที่รัน"),
                    tags=("empty",),
                )
            else:
                for ev in events:
                    tp = ev["type"]
                    tag = "stall" if "Load-Use" in tp else ("flush" if "Flush" in tp else "fwd")
                    tree.insert("", tk.END, values=(ev["cycle"], ev["pc"], ev["asm"], tp, ev["detail"]), tags=(tag,))
            tree.pack(side="left", fill="both", expand=True)
        else:
            cols = ("cycle", "if", "id", "ex", "mem", "wb", "note")
            tree = ttk.Treeview(self.body_frame, columns=cols, show="headings", yscrollcommand=scroll.set)
            scroll.command = tree.yview

            tree.heading("cycle", text="Clk")
            tree.heading("if", text="1. IF")
            tree.heading("id", text="2. ID")
            tree.heading("ex", text="3. EX")
            tree.heading("mem", text="4. MEM")
            tree.heading("wb", text="5. WB")
            tree.heading("note", text="Pipeline Signal")

            tree.column("cycle", width=50, anchor="center")
            tree.column("if", width=130, anchor="w")
            tree.column("id", width=130, anchor="w")
            tree.column("ex", width=135, anchor="w")
            tree.column("mem", width=130, anchor="w")
            tree.column("wb", width=130, anchor="w")
            tree.column("note", width=170, anchor="w")

            tree.tag_configure("stall", background="#2B1E0D", foreground=ACCENT_AMBER)
            tree.tag_configure("flush", background="#2D1418", foreground=ACCENT_RED)
            tree.tag_configure("even", background=BG_EDITOR, foreground=TXT_PRIMARY)
            tree.tag_configure("odd", background="#181818", foreground=TXT_PRIMARY)

            for idx, row in enumerate(pipe["timeline"]):
                note = row["note"]
                tag = "stall" if "STALL" in note else ("flush" if "FLUSH" in note else ("even" if idx % 2 == 0 else "odd"))
                tree.insert(
                    "",
                    tk.END,
                    values=(row["cycle"], row["IF"], row["ID"], row["EX"], row["MEM"], row["WB"], note),
                    tags=(tag,),
                )
            tree.pack(side="left", fill="both", expand=True)

    def _rerun_and_refresh(self):
        self._run_analysis()
        self._build_ui()

    def _on_export_testbench(self):
        chosen = filedialog.askdirectory(
            parent=self,
            initialdir=self.project_dir,
            title="เลือกโฟลเดอร์สำหรับส่งออกชุด RTL Testbench (.v + .hex + VCD Waveform)",
        )
        if not chosen:
            return
        if os.path.abspath(chosen).lower() == os.path.abspath(self.project_dir).lower():
            out_dir = os.path.join(chosen, f"rtl_testbench_{self.arch}")
        else:
            out_dir = chosen

        pkg = export_rtl_testbench(
            out_dir,
            self.instructions,
            arch=self.arch,
            cpu_hdl_path=self.cpu_hdl_path,
            sim_cycles=max(1, self.cosim_res["pipeline"]["retired_instructions"]),
            sw_init=self.sw_init,
            btn_init=self.btn_init,
            mmio_map=self.mmio_map,
        )
        if self.on_exported:
            self.on_exported(pkg)
        messagebox.showinfo(
            "ส่งออกชุด RTL Testbench สำเร็จ",
            f"ส่งออกไฟล์ Testbench และโปรแกรมเสร็จสมบูรณ์ที่:\n{pkg['out_dir']}\n\n"
            f"• tb_cpu_cosim.v (พร้อม $dumpfile waveform.vcd)\n"
            f"• program.hex & dmem_init.hex\n"
            f"• rtl_cpu/ ({len(pkg['copied_rtl'])} ไฟล์ RTL)\n"
            f"• run_iverilog_gtkwave.bat & run_vivado_xsim.tcl",
            parent=self,
        )

    def _on_open_gtkwave(self):
        gtkwave_exe = find_gtkwave_bin()
        if not gtkwave_exe:
            messagebox.showwarning("ไม่พบ GTKWave", "ไม่พบโปรแกรม GTKWave ในโฟลเดอร์ toolchain/gtkwave", parent=self)
            return

        out_dir = os.path.join(self.project_dir, f"rtl_testbench_{self.arch}")
        vcd_path = os.path.join(out_dir, "waveform.vcd")

        pkg = export_rtl_testbench(
            out_dir,
            self.instructions,
            arch=self.arch,
            cpu_hdl_path=self.cpu_hdl_path,
            sim_cycles=max(1, self.cosim_res["pipeline"]["retired_instructions"]),
            sw_init=self.sw_init,
            btn_init=self.btn_init,
            mmio_map=self.mmio_map,
        )
        sim_tool = detect_verilog_simulator()
        if sim_tool and sim_tool.get("kind") == "iverilog":
            rtl_files = [
                os.path.join(out_dir, "rtl_cpu", fn)
                for fn in pkg["copied_rtl"]
                if fn.lower().endswith((".v", ".sv"))
            ]
            vvp_out = os.path.join(out_dir, "sim_cosim.vvp")
            subprocess.run(
                [sim_tool["iverilog"], "-g2012", "-I", os.path.join(out_dir, "rtl_cpu"), "-o", vvp_out, pkg["tb_v"]] + rtl_files,
                cwd=out_dir,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            subprocess.run(
                [sim_tool["vvp"], vvp_out],
                cwd=out_dir,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )

        gtkw_path = generate_gtkwave_savefile(out_dir, arch=self.arch, vcd_path=vcd_path)
        if os.path.exists(vcd_path):
            subprocess.Popen([gtkwave_exe, vcd_path, gtkw_path], cwd=out_dir)
        else:
            subprocess.Popen([gtkwave_exe], cwd=os.path.dirname(gtkwave_exe))

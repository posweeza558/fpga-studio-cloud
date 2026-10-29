# -*- coding: utf-8 -*-
"""
FPGA Studio — WSL Local Hardware Synthesis Dialog
Enables running open-source hardware synthesis (openXC7, Yosys, nextpnr)
directly on the user's PC via Windows Subsystem for Linux (WSL).
"""

import os
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from config.theme import (
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_PURPLE,
    ACCENT_WARN,
    BG_CARD,
    BG_DARK,
    BG_EDITOR,
    BG_ELEVATED,
    BG_PILL_ACT,
    BG_PILL_INACT,
    BORDER_COLOR,
    FONT_CODE,
    FONT_UI,
    TXT_BRIGHT,
    TXT_DIM,
    TXT_MUTED,
)
from core.wsl_synthesis import (
    check_wsl_status,
    launch_wsl_install,
    run_wsl_synthesis,
)
from ui.installer_wizard import BaseFramelessWizardDialog
from ui.widgets import SpotifyAutoScrollbar


class WSLSynthesisDialog(BaseFramelessWizardDialog):
    """
    WSL Local Synthesis Wizard Dialog.
    Detects WSL status, offers 1-click install if missing, and runs local synthesis.
    """

    def __init__(
        self,
        parent,
        cpu_name: str = "openmips",
        cpu_arch: str = "mips",
        cpu_hdl_path: Optional[str] = None,
        board_name: str = "Digilent Nexys A7-100T (Artix-7)",
        project_dir: Optional[str] = None,
        on_bitstream_ready: Optional[Callable[[str], None]] = None,
    ):
        self.cpu_name = cpu_name
        self.cpu_arch = cpu_arch
        self.cpu_hdl_path = cpu_hdl_path
        self.board_name = board_name
        self.project_dir = project_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.on_bitstream_ready = on_bitstream_ready
        self.is_running = False

        super().__init__(
            parent,
            title=f"🐧 สังเคราะห์ Bitstream ในเครื่องผ่าน WSL (Linux Local Engine) — {cpu_name}",
            width=840,
            height=660,
        )

        self._build_ui()
        self._refresh_wsl_status()

    def _build_ui(self):
        body = tk.Frame(self.container, bg=BG_DARK)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # Header description
        hdr = tk.Frame(body, bg=BG_DARK)
        hdr.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            hdr,
            text="🐧 WSL Local Synthesis — สังเคราะห์และแปลงฮาร์ดแวร์ CPU ในเครื่องคอมพิวเตอร์ของคุณ",
            bg=BG_DARK,
            fg=ACCENT_CYAN,
            font=(FONT_UI, 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X)

        sub_txt = (
            "✓ ทำงานออฟไลน์ 100% ในเครื่อง ไม่ต้องเชื่อมต่อคลาวด์ ไม่ต้องมีบัญชี GitHub\n"
            "✓ ใช้เครื่องมือสังเคราะห์ Linux (openXC7 / Yosys) ผ่าน WSL ไม่ต้องติดตั้ง Vivado 50-80GB"
        )
        tk.Label(
            hdr,
            text=sub_txt,
            bg=BG_DARK,
            fg=TXT_MUTED,
            font=(FONT_UI, 9),
            justify="left",
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Status & Control Card
        self.card_status = tk.Frame(body, bg=BG_CARD, bd=1, relief="solid", highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.card_status.pack(fill=tk.X, pady=(0, 10), ipady=8, ipadx=12)

        self.lbl_status_icon = tk.Label(self.card_status, text="🔍", bg=BG_CARD, font=(FONT_UI, 16))
        self.lbl_status_icon.pack(side=tk.LEFT, padx=(10, 12))

        stat_info = tk.Frame(self.card_status, bg=BG_CARD)
        stat_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_status_title = tk.Label(stat_info, text="กำลังตรวจสอบสถานะ WSL ในเครื่อง...", bg=BG_CARD, fg=TXT_BRIGHT, font=(FONT_UI, 10, "bold"), anchor="w")
        self.lbl_status_title.pack(fill=tk.X)

        self.lbl_status_desc = tk.Label(stat_info, text="รอสักครู่...", bg=BG_CARD, fg=TXT_DIM, font=(FONT_UI, 8), anchor="w")
        self.lbl_status_desc.pack(fill=tk.X)

        # Actions on status card
        act_box = tk.Frame(self.card_status, bg=BG_CARD)
        act_box.pack(side=tk.RIGHT, padx=10)

        self.btn_install_wsl = tk.Button(
            act_box,
            text="⚡ ติดตั้ง WSL (Ubuntu) อัตโนมัติ",
            bg=BG_PILL_INACT,
            fg=ACCENT_WARN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_WARN,
            padx=10,
            pady=4,
            cursor="hand2",
            font=(FONT_UI, 9, "bold"),
            command=self._install_wsl_clicked,
        )

        self.btn_refresh = tk.Button(
            act_box,
            text="🔄 ตรวจสอบใหม่",
            bg=BG_PILL_INACT,
            fg=TXT_BRIGHT,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=8,
            pady=4,
            cursor="hand2",
            font=(FONT_UI, 9),
            command=self._refresh_wsl_status,
        )
        self.btn_refresh.pack(side=tk.RIGHT, padx=(4, 0))

        # Target Config Row
        cfg_frame = tk.Frame(body, bg=BG_DARK)
        cfg_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(cfg_frame, text=f"สถาปัตยกรรม CPU: ", bg=BG_DARK, fg=TXT_DIM, font=(FONT_UI, 9)).pack(side=tk.LEFT)
        tk.Label(cfg_frame, text=f"{self.cpu_name} ({self.cpu_arch.upper()})", bg=BG_DARK, fg=ACCENT_CYAN, font=(FONT_UI, 9, "bold")).pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(cfg_frame, text="บอร์ดเป้าหมาย: ", bg=BG_DARK, fg=TXT_DIM, font=(FONT_UI, 9)).pack(side=tk.LEFT)
        tk.Label(cfg_frame, text=self.board_name, bg=BG_DARK, fg=ACCENT_GREEN, font=(FONT_UI, 9, "bold")).pack(side=tk.LEFT)

        # Run Button
        btn_bar = tk.Frame(body, bg=BG_DARK)
        btn_bar.pack(fill=tk.X, pady=(0, 10))

        self.btn_start = tk.Button(
            btn_bar,
            text="🚀 เริ่มสังเคราะห์ Bitstream ในเครื่อง (Start WSL Synthesis)",
            bg=ACCENT_GREEN,
            fg="#000000",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            font=(FONT_UI, 10, "bold"),
            command=self._start_wsl_synthesis_thread,
        )
        self.btn_start.pack(side=tk.LEFT)

        # Log Console
        lbl_console = tk.Label(body, text="บันทึกการทำงานในเครื่อง (WSL Live Log):", bg=BG_DARK, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), anchor="w")
        lbl_console.pack(fill=tk.X, pady=(4, 2))

        con_frame = tk.Frame(body, bg=BG_EDITOR, bd=1, relief="solid", highlightthickness=1, highlightbackground=BORDER_COLOR)
        con_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(con_frame, bg=BG_EDITOR, fg=TXT_BRIGHT, font=(FONT_CODE, 8), wrap="char", bd=0, padx=8, pady=6)
        sb = SpotifyAutoScrollbar(con_frame, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._log("🐧 ระบบ WSL Local Synthesis พร้อมทำงาน")
        self._log(f"   เป้าหมาย: CPU '{self.cpu_name}' | บอร์ด '{self.board_name}'")

    def _log(self, text: str):
        def _append():
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)

        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)

    def _refresh_wsl_status(self):
        self.lbl_status_title.config(text="กำลังตรวจสอบสถานะ WSL ในเครื่อง...", fg=TXT_BRIGHT)
        self.lbl_status_desc.config(text="รอสักครู่...")
        self.btn_install_wsl.pack_forget()

        def worker():
            status = check_wsl_status()

            def update():
                if status["installed"]:
                    distro = status.get("default_distro") or "Linux"
                    self.lbl_status_icon.config(text="🐧")
                    self.lbl_status_title.config(text=f"ตรวจพบ WSL ({distro}) พร้อมใช้งาน", fg=ACCENT_GREEN)
                    tool_desc = []
                    if status["tools"].get("yosys"):
                        tool_desc.append("Yosys ✓")
                    if status["tools"].get("docker"):
                        tool_desc.append("Docker ✓")
                    desc = f"Linux Distro: {distro} | เครื่องมือที่พบ: {', '.join(tool_desc) if tool_desc else 'พร้อมติดตั้ง/รันสคริปต์'}"
                    self.lbl_status_desc.config(text=desc)
                    self.btn_start.config(state=tk.NORMAL)
                    self._log(f"✓ ตรวจพบ WSL: {distro}")
                else:
                    self.lbl_status_icon.config(text="⚠️")
                    self.lbl_status_title.config(text="เครื่องนี้ยังไม่ได้ติดตั้ง WSL (Linux)", fg=ACCENT_WARN)
                    self.lbl_status_desc.config(text="กดปุ่ม 'ติดตั้ง WSL (Ubuntu) อัตโนมัติ' ด้านขวา เพื่อเปิดใช้งาน Linux ในเครื่อง")
                    self.btn_install_wsl.pack(side=tk.RIGHT, padx=(0, 4))
                    self.btn_start.config(state=tk.DISABLED)
                    self._log("⚠️ เครื่องนี้ยังไม่ได้ติดตั้ง WSL — สามารถคลิกปุ่มสีส้มเพื่อติดตั้งได้ทันที")

            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _install_wsl_clicked(self):
        ans = messagebox.askyesno(
            "ติดตั้ง WSL (Windows Subsystem for Linux)",
            "ระบบจะเปิดหน้าต่าง Command Prompt (สิทธิ์ Administrator) เพื่อรันคำสั่ง:\n\n"
            "wsl --install\n\n"
            "• เป็นฟังก์ชันมาตรฐานของ Windows ฟรี 100%\n"
            "• จะติดตั้ง Linux (Ubuntu) ลงในเครื่องโดยอัตโนมัติ\n"
            "• หลังจากติดตั้งเสร็จ อาจต้อง Restart เครื่อง 1 ครั้ง\n\n"
            "ต้องการเริ่มติดตั้งทันทีหรือไม่?",
            parent=self,
        )
        if ans:
            self._log("⚡ กำลังเรียกตัวติดตั้ง 'wsl --install' ผ่าน Administrator Shell...")
            launch_wsl_install()
            messagebox.showinfo(
                "กำลังติดตั้ง WSL",
                "เปิดหน้าต่างติดตั้ง WSL เรียบร้อยแล้ว!\n\nกรุณากด 'Yes' ที่หน้าต่าง UAC ของ Windows และรอการดาวน์โหลดเสร็จสิ้นในหน้าต่างสีดำครับ",
                parent=self,
            )

    def _start_wsl_synthesis_thread(self):
        if self.is_running:
            return

        self.is_running = True
        self.btn_start.config(state=tk.DISABLED, text="⏳ กำลังสังเคราะห์ในเครื่อง (WSL Running)...")

        def worker():
            self._log("\n" + "=" * 60)
            self._log(f"🚀 เริ่มต้นการสังเคราะห์วงจร CPU '{self.cpu_name}' ผ่าน WSL...")
            
            ok, msg, out_bit = run_wsl_synthesis(
                project_dir=self.project_dir,
                cpu_name=self.cpu_name,
                cpu_arch=self.cpu_arch,
                cpu_hdl_path=self.cpu_hdl_path,
                on_log=self._log,
            )

            def done():
                self.is_running = False
                self.btn_start.config(state=tk.NORMAL, text="🚀 เริ่มสังเคราะห์ Bitstream ในเครื่อง (Start WSL Synthesis)")
                if ok and out_bit and os.path.isfile(out_bit):
                    self._log(f"\n✅ {msg}")
                    if self.on_bitstream_ready:
                        self.on_bitstream_ready(out_bit)
                    messagebox.showinfo(
                        "สังเคราะห์สำเร็จ!",
                        f"สร้าง Bitstream สำเร็จเรียบร้อยแล้วผ่าน WSL!\n\nไฟล์: {os.path.basename(out_bit)}\n\nพร้อมสำหรับการแฟลชลงบอร์ด FPGA ผ่านสาย USB ทันที!",
                        parent=self,
                    )
                    self.destroy()
                elif ok:
                    self._log(f"\n📁 {msg}")
                    messagebox.showinfo("การสังเคราะห์ใน WSL", msg, parent=self)
                else:
                    self._log(f"\n❌ ข้อผิดพลาด: {msg}")
                    messagebox.showerror("การสังเคราะห์ใน WSL ไม่สำเร็จ", msg, parent=self)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

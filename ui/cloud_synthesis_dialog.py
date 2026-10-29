# -*- coding: utf-8 -*-
"""
FPGA Studio — Cloud Synthesis Dialog (GitHub Actions CI/CD)
Provides an intuitive GUI for 1-Click Zero-Vivado Bitstream Generation.
"""

import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from config.theme import (
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_WARN,
    BG_CARD,
    BG_DARK,
    BG_EDITOR,
    BG_ELEVATED,
    BG_PILL_INACT,
    BORDER_COLOR,
    FONT_CODE,
    FONT_UI,
    TXT_BRIGHT,
    TXT_DIM,
    TXT_MUTED,
    TXT_PRIMARY,
)
from core.cloud_synthesis import (
    check_github_repo_workflow,
    download_synthesized_bitstream_from_url,
    export_cloud_bundle_zip,
    get_latest_workflow_run,
    get_run_artifacts,
    trigger_cloud_synthesis_workflow,
)
from ui.installer_wizard import BaseFramelessWizardDialog
from ui.widgets import SpotifyAutoScrollbar, SpotifyPillButton

ACCENT_PURPLE = "#A78BFA"


class CloudSynthesisDialog(BaseFramelessWizardDialog):
    """Dialog for automated Cloud Bitstream Synthesis via GitHub Actions."""

    def __init__(
        self,
        parent,
        cpu_name: str = "openmips",
        cpu_arch: str = "mips",
        cpu_hdl_path: Optional[str] = None,
        board_name: str = "nexys_a7_100",
        project_dir: Optional[str] = None,
        on_bitstream_ready: Optional[Callable[[str], None]] = None,
    ):
        self.cpu_name = cpu_name
        self.cpu_arch = cpu_arch
        self.cpu_hdl_path = cpu_hdl_path
        self.board_name = board_name
        self.project_dir = project_dir or os.getcwd()
        self.on_bitstream_ready = on_bitstream_ready
        self.is_running = False

        super().__init__(
            parent,
            "FPGA Studio — สังเคราะห์ Bitstream ผ่าน Cloud (GitHub Actions ฟรี)",
            820,
            620,
        )

        self._build_ui()

    def _build_ui(self):
        body = tk.Frame(self.main_frame, bg=BG_DARK)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # Header description
        lbl_info = tk.Label(
            body,
            text=(
                "☁️ Cloud Synthesis — สังเคราะห์และแปลงฮาร์ดแวร์ CPU เป็น Bitstream (.bit) บน Cloud ฟรี 100%\n"
                "✓ ไม่ต้องติดตั้ง Vivado (50-80GB) ในเครื่องคอมพิวเตอร์ของคุณ\n"
                "✓ ใช้ระบบ Linux Container (openXC7) ของ GitHub Actions ในการทำ Place & Route อัตโนมัติ"
            ),
            bg=BG_DARK,
            fg=TXT_PRIMARY,
            font=(FONT_UI, 9),
            justify="left",
            anchor="w",
        )
        lbl_info.pack(fill=tk.X, pady=(0, 10))

        # Card 1: Cloud Dispatch Configuration
        card_cfg = tk.Frame(body, bg=BG_CARD, bd=1, relief="solid", highlightthickness=1, highlightbackground=BORDER_COLOR)
        card_cfg.pack(fill=tk.X, pady=(0, 10), ipady=6, padx=2)

        # Row 1: Target CPU & Board
        r1 = tk.Frame(card_cfg, bg=BG_CARD)
        r1.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(r1, text="สถาปัตยกรรม CPU:", bg=BG_CARD, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), width=16, anchor="w").pack(side=tk.LEFT)
        tk.Label(r1, text=f"{self.cpu_name} ({self.cpu_arch.upper()})", bg=BG_CARD, fg=ACCENT_CYAN, font=(FONT_CODE, 9, "bold")).pack(side=tk.LEFT, padx=6)

        tk.Label(r1, text="เป้าหมายบอร์ด:", bg=BG_CARD, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), width=14, anchor="w").pack(side=tk.LEFT, padx=(20, 0))
        tk.Label(r1, text=f"{self.board_name} (Artix-7 100T)", bg=BG_CARD, fg=TXT_BRIGHT, font=(FONT_CODE, 9)).pack(side=tk.LEFT, padx=6)

        # Row 2: GitHub Repository Slug
        r2 = tk.Frame(card_cfg, bg=BG_CARD)
        r2.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(r2, text="คลัง GitHub (Repo):", bg=BG_CARD, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), width=16, anchor="w").pack(side=tk.LEFT)
        self.repo_var = tk.StringVar(value="your-username/fpga-studio-cloud")
        e_repo = tk.Entry(r2, textvariable=self.repo_var, bg=BG_EDITOR, fg=TXT_BRIGHT, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, font=(FONT_CODE, 9))
        e_repo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, ipady=3)

        # Row 3: GitHub Token (PAT)
        r3 = tk.Frame(card_cfg, bg=BG_CARD)
        r3.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(r3, text="GitHub Token (PAT):", bg=BG_CARD, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), width=16, anchor="w").pack(side=tk.LEFT)
        self.token_var = tk.StringVar(value="")
        e_token = tk.Entry(r3, textvariable=self.token_var, show="*", bg=BG_EDITOR, fg=TXT_BRIGHT, bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, font=(FONT_CODE, 9))
        e_token.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, ipady=3)

        btn_test_repo = tk.Button(
            r3,
            text="ตรวจสอบคลัง",
            bg=BG_PILL_INACT,
            fg=ACCENT_CYAN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_CYAN,
            padx=8,
            pady=2,
            cursor="hand2",
            font=(FONT_UI, 8, "bold"),
            command=self._test_repo_connection,
        )
        btn_test_repo.pack(side=tk.RIGHT)

        # Card 2: Action Buttons
        act_frame = tk.Frame(body, bg=BG_DARK)
        act_frame.pack(fill=tk.X, pady=(0, 8))

        self.btn_dispatch = tk.Button(
            act_frame,
            text="🚀 เริ่มสังเคราะห์บน Cloud (GitHub Dispatch)",
            bg=BG_PILL_INACT,
            fg=ACCENT_PURPLE,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_PURPLE,
            padx=12,
            pady=4,
            cursor="hand2",
            font=(FONT_UI, 9, "bold"),
            command=self._start_cloud_synthesis_thread,
        )
        self.btn_dispatch.pack(side=tk.LEFT, padx=(0, 8))

        btn_bundle = tk.Button(
            act_frame,
            text="📦 รวมไฟล์แพ็กเกจ .ZIP เพื่อ Push เอง",
            bg=BG_PILL_INACT,
            fg=ACCENT_GREEN,
            bd=0,
            highlightthickness=1,
            highlightbackground=ACCENT_GREEN,
            padx=12,
            pady=4,
            cursor="hand2",
            font=(FONT_UI, 9, "bold"),
            command=self._export_bundle_zip,
        )
        btn_bundle.pack(side=tk.LEFT, padx=(0, 8))

        # Status & Log Console
        lbl_console = tk.Label(body, text="บันทึกการทำงานและสถานะ Cloud (Log Console):", bg=BG_DARK, fg=TXT_DIM, font=(FONT_UI, 9, "bold"), anchor="w")
        lbl_console.pack(fill=tk.X, pady=(4, 2))

        con_frame = tk.Frame(body, bg=BG_EDITOR, bd=1, relief="solid", highlightthickness=1, highlightbackground=BORDER_COLOR)
        con_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(con_frame, bg=BG_EDITOR, fg=TXT_BRIGHT, font=(FONT_CODE, 8), wrap="char", bd=0, padx=8, pady=6)
        sb = SpotifyAutoScrollbar(con_frame, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._log("☁️ ระบบ Cloud Synthesis พร้อมใช้งาน")
        self._log(f"   เป้าหมาย: CPU '{self.cpu_name}' | บอร์ด '{self.board_name}'")
        self._log("   แนะนำ: ระบุ GitHub Repo และ Token เพื่อสั่งการสังเคราะห์ Place & Route อัตโนมัติ")

    def _log(self, text: str):
        def _append():
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)

        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)

    def _test_repo_connection(self):
        repo = self.repo_var.get().strip()
        token = self.token_var.get().strip() or None
        if not repo or "/" not in repo:
            messagebox.showwarning("รูปแบบคลังไม่ถูกต้อง", "กรุณาระบุคลังในรูปแบบ 'owner/repository'", parent=self)
            return

        self._log(f"\n🔍 กำลังตรวจสอบการเชื่อมต่อไปยังคลัง: {repo}...")
        ok, msg = check_github_repo_workflow(repo, token)
        if ok:
            self._log(f"✅ {msg}")
            messagebox.showinfo("เชื่อมต่อสำเร็จ", msg, parent=self)
        else:
            self._log(f"❌ {msg}")
            messagebox.showerror("เชื่อมต่อไม่สำเร็จ", msg, parent=self)

    def _export_bundle_zip(self):
        ok, msg, z_path = export_cloud_bundle_zip(
            project_dir=self.project_dir,
            cpu_name=self.cpu_name,
            cpu_arch=self.cpu_arch,
            cpu_hdl_path=self.cpu_hdl_path,
            on_log=self._log,
        )
        if ok and z_path:
            messagebox.showinfo(
                "สร้างแพ็กเกจสำเร็จ",
                f"สร้างแพ็กเกจ Cloud ZIP เรียบร้อยแล้วที่:\n\n{z_path}\n\nคุณสามารถนำไฟล์นี้ไปแตกและ Push ขึ้น GitHub เพื่อรัน Cloud Actions ได้ทันที!",
                parent=self,
            )

    def _start_cloud_synthesis_thread(self):
        if self.is_running:
            return

        repo = self.repo_var.get().strip()
        token = self.token_var.get().strip()
        if not repo or "/" not in repo:
            messagebox.showwarning("กรุณาระบุคลัง", "กรุณาระบุชื่อ GitHub Repo ให้ถูกต้อง เช่น 'username/project'", parent=self)
            return
        if not token:
            messagebox.showwarning("ต้องใช้ GitHub Token", "การสั่งรัน GitHub Actions ผ่านโปรแกรมจำเป็นต้องใช้ Personal Access Token (PAT)\n\nหรือหากไม่มี Token สามารถใช้ปุ่ม 'รวมไฟล์แพ็กเกจ .ZIP เพื่อ Push เอง' ได้ครับ", parent=self)
            return

        self.is_running = True
        self.btn_dispatch.config(state=tk.DISABLED, text="⏳ กำลังสั่งการบน Cloud...")

        def worker():
            self._log("\n" + "=" * 60)
            self._log(f"📦 [1/2] เตรียมแพ็กเกจ SoC Auto-Wrapper สำหรับ '{self.cpu_name}'...")
            try:
                from core.cloud_synthesis import prepare_cloud_synthesis_package
                prepare_cloud_synthesis_package(self.project_dir, self.cpu_name, arch=self.cpu_arch, cpu_hdl_path=self.cpu_hdl_path)
                self._log("✓ สร้างโค้ด SoC Top และ Constraints เรียบร้อย")
            except Exception as e:
                self._log(f"⚠️ เตรียมแพ็กเกจล้มเหลว: {e}")

            self._log(f"🚀 [2/2] เริ่มส่งคำสั่ง Cloud Synthesis ไปยัง GitHub Actions ({repo})...")

            ok, msg = trigger_cloud_synthesis_workflow(
                repo_slug=repo,
                github_token=token,
                cpu_name=self.cpu_name,
                board_target=self.board_name,
            )
            if not ok:
                self._log(f"❌ {msg}")
                self.after(0, lambda: self._on_finish(False, msg))
                return

            self._log(f"✅ {msg}")
            self._log("⏳ กำลังรอเวิร์กโฟลว์เริ่มทำงานบน GitHub Runners (ตรวจสอบทุก 6 วินาที)...")

            # Polling loop
            start_time = time.time()
            active_run_id = None
            max_wait_seconds = 1800  # 30 mins

            while time.time() - start_time < max_wait_seconds:
                time.sleep(6)
                s_ok, run_data, r_msg = get_latest_workflow_run(repo, token)
                if not s_ok or not run_data:
                    continue

                active_run_id = run_data.get("id")
                status = run_data.get("status")
                conclusion = run_data.get("conclusion")
                html_url = run_data.get("html_url", "")

                self._log(f"   [Cloud Status] Run #{active_run_id}: {status} (ข้อสรุป: {conclusion or 'กำลังรัน...'})")

                if status == "completed":
                    if conclusion == "success":
                        self._log("🎉 เวิร์กโฟลว์สังเคราะห์ Bitstream บน Cloud สำเร็จสมบูรณ์!")
                        # Download artifact
                        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        dest_bit = os.path.join(app_root, "bitstreams", f"nexys_a7_{self.cpu_name}.bit")

                        a_ok, artifacts, a_msg = get_run_artifacts(repo, active_run_id, token)
                        if a_ok and artifacts:
                            down_url = artifacts[0].get("archive_download_url")
                            d_ok, d_msg = download_synthesized_bitstream_from_url(down_url, dest_bit, token, on_log=self._log)
                            if d_ok:
                                self.after(0, lambda: self._on_bitstream_downloaded(dest_bit))
                                return
                        self.after(0, lambda: self._on_finish(True, f"สังเคราะห์สำเร็จแต่ไม่พบ Artifacts สำหรับดาวน์โหลดอัตโนมัติ ({html_url})"))
                        return
                    else:
                        err_str = f"การสังเคราะห์บน Cloud ล้มเหลว (ผลลัพธ์: {conclusion})\nดูรายละเอียดได้ที่: {html_url}"
                        self._log(f"❌ {err_str}")
                        self.after(0, lambda: self._on_finish(False, err_str))
                        return

            self.after(0, lambda: self._on_finish(False, "หมดเวลารอคอยผลลัพธ์จาก Cloud (Timeout)"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_bitstream_downloaded(self, bit_path: str):
        self.is_running = False
        self.btn_dispatch.config(state=tk.NORMAL, text="🚀 เริ่มสังเคราะห์บน Cloud (GitHub Dispatch)")
        self._log(f"\n✅ ได้รับไฟล์ Bitstream สำเร็จรูป: {bit_path}")
        if self.on_bitstream_ready:
            self.on_bitstream_ready(bit_path)
        messagebox.showinfo(
            "Cloud Synthesis สำเร็จ!",
            f"ดาวน์โหลดไฟล์ Bitstream เรียบร้อยแล้ว!\n\nไฟล์: {os.path.basename(bit_path)}\n\nพร้อมสำหรับการแฟลชลงบอร์ด FPGA ผ่านสาย USB ทันที!",
            parent=self,
        )
        self.destroy()

    def _on_finish(self, ok: bool, msg: str):
        self.is_running = False
        self.btn_dispatch.config(state=tk.NORMAL, text="🚀 เริ่มสังเคราะห์บน Cloud (GitHub Dispatch)")
        if not ok:
            messagebox.showerror("Cloud Synthesis ไม่สำเร็จ", msg, parent=self)

# -*- coding: utf-8 -*-
"""
Interactive Peripheral Simulation Windows for Nexys A7:
1. VGADisplayWindow: Frameless 640x480 @ 60Hz 12-bit RGB VGA Monitor screen.
   Connects directly to FPGA video output (VRAM 0xFF000000) with custom dark titlebar,
   matching the main program window architecture (single seamless frame, no nested double borders).
2. UARTTerminalWindow: Frameless USB-UART Serial Terminal (115200 8-N-1) with live RX log,
   TX interactive sending, custom dark titlebar, and unified frameless window style.
"""

import ctypes
import tkinter as tk
from tkinter import ttk
from config.theme import (
    BG_BLACK,
    BG_PANEL,
    BG_ELEVATED,
    BG_HOVER,
    BG_PILL_INACT,
    BG_PILL_ACT,
    BORDER_COLOR,
    BORDER_HOVER,
    ACCENT_GREEN,
    ACCENT_AMBER,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    TXT_DIM,
    TXT_ON_WHITE,
    FONT_UI,
    FONT_CODE,
)
from ui.widgets import SpotifyAutoScrollbar


def apply_main_window_style(win):
    """
    Enables frameless mode with Windows 11 DWM native rounded corners and taskbar integration,
    matching the main application window architecture exactly (no nested double borders).
    """
    win.overrideredirect(True)
    win._click_to_raise = True
    try:
        win.update()
        hwnd = win.winfo_id()
        p_hwnd = ctypes.windll.user32.GetParent(hwnd) or hwnd
        for h in (hwnd, p_hwnd):
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            ex_style = ctypes.windll.user32.GetWindowLongW(h, GWL_EXSTYLE)
            ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(h, GWL_EXSTYLE, ex_style)

            # Apply Windows 11 native DWM smooth rounded corners (DWMWCP_ROUND = 2)
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(h, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def center_on_parent(win, parent, w, h):
    """Center child window within parent window bounds."""
    try:
        parent.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        x = max(px + (pw - w) // 2, 40)
        y = max(py + (ph - h) // 2, 40)
    except Exception:
        x, y = 200, 120
    win.geometry(f"{w}x{h}+{x}+{y}")


def attach_window_drag(win, handle_widgets):
    """Attach mouse drag-to-move handlers to specified handle widgets."""
    def _start_drag(e):
        try:
            if getattr(win, "master", None) is not None:
                win.master.winfo_toplevel()._active_raised_window = win
            win.lift()
        except Exception:
            pass
        win._drag_start_x = e.x_root
        win._drag_start_y = e.y_root
        win._win_x = win.winfo_x()
        win._win_y = win.winfo_y()

    def _on_drag(e):
        dx = e.x_root - win._drag_start_x
        dy = e.y_root - win._drag_start_y
        win.geometry(f"+{win._win_x + dx}+{win._win_y + dy}")

    for w in handle_widgets:
        w.bind("<Button-1>", _start_drag)
        w.bind("<B1-Motion>", _on_drag)


class VGADisplayWindow(tk.Toplevel):
    """Frameless 640x480 @ 60Hz VGA Monitor Simulation Window matching Main Application styling."""

    def __init__(self, parent, sim_engine):
        super().__init__(parent)
        self.sim_engine = sim_engine
        center_on_parent(self, parent, 670, 560)
        self.minsize(640, 500)
        self.configure(bg="#121212")
        apply_main_window_style(self)

        self._build_ui()
        self.redraw()
        self.deiconify()
        try:
            if parent is not None:
                parent.winfo_toplevel()._active_raised_window = self
        except Exception:
            pass
        self.lift()
        self.focus_force()

    def _build_ui(self):
        # 1. Custom Dark Title Bar (Seamless, directly in root window - no nested borders)
        tb = tk.Frame(self, bg="#181818", height=38, padx=12)
        tb.pack(side=tk.TOP, fill=tk.X)
        tb.pack_propagate(False)

        title_lbl = tk.Label(
            tb, text="🖥️  จอภาพ VGA เสมือน (DIGILENT NEXYS A7  •  ARTIX-7)",
            bg="#181818", fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold")
        )
        title_lbl.pack(side=tk.LEFT)

        btn_close = tk.Button(
            tb, text="✕", bg="#181818", fg=TXT_MUTED,
            activebackground=ACCENT_RED, activeforeground=TXT_ON_WHITE,
            bd=0, highlightthickness=0, width=4, pady=6, cursor="hand2",
            font=(FONT_UI, 9, "bold"), command=self.destroy
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=ACCENT_RED, fg=TXT_ON_WHITE))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg="#181818", fg=TXT_MUTED))

        res_lbl = tk.Label(
            tb, text="640 × 480 @ 60Hz (12-bit RGB 4:4:4)",
            bg="#181818", fg=ACCENT_GREEN, font=(FONT_CODE, 8, "bold"), padx=10
        )
        res_lbl.pack(side=tk.RIGHT)

        attach_window_drag(self, [tb, title_lbl, res_lbl])

        # 2. Bottom Hardware Sync Status Bar (Packed at bottom before canvas)
        sb = tk.Frame(self, bg="#121212", height=32, padx=12)
        sb.pack(side=tk.BOTTOM, fill=tk.X)
        sb.pack_propagate(False)

        tk.Label(
            sb, text="● SIGNAL: CONNECTED", bg="#121212", fg=ACCENT_GREEN,
            font=(FONT_UI, 8, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.sync_lbl = tk.Label(
            sb,
            text="HSync: 31.5 kHz   •   VSync: 60.0 Hz   •   Clock: 25.175 MHz",
            bg="#121212", fg=TXT_MUTED, font=(FONT_CODE, 8)
        )
        self.sync_lbl.pack(side=tk.LEFT)

        tk.Label(
            sb,
            text="VRAM Framebuffer: 0xFF000000",
            bg="#121212", fg=TXT_DIM, font=(FONT_CODE, 8)
        ).pack(side=tk.RIGHT)

        # 3. VGA Screen Canvas (Directly packed in window - No nested bezel/border frames!)
        self.canvas = tk.Canvas(self, bg="#0A0E0C", bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Redraw automatically on any size/configure change so display is always full & seamless
        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        w = max(self.canvas.winfo_width(), 640)
        h = max(self.canvas.winfo_height(), 440)
        self.canvas.delete("all")

        # If CPU/FPGA has written pixel data to VRAM framebuffer, render it directly!
        if self.sim_engine.vga_buffer:
            self.canvas.create_rectangle(0, 0, w, h, fill="#0A0E0C", outline="")
            cw = w / 80.0
            ch = h / 60.0
            for addr, color_val in list(self.sim_engine.vga_buffer.items())[:4800]:
                offset = (addr - 0xFF000000) // 4
                gx = offset % 80
                gy = offset // 80
                if 0 <= gx < 80 and 0 <= gy < 60:
                    px0 = int(gx * cw)
                    py0 = int(gy * ch)
                    px1 = int((gx + 1) * cw) + 1
                    py1 = int((gy + 1) * ch) + 1
                    hex_col = f"#{color_val & 0xFFFFFF:06X}"
                    self.canvas.create_rectangle(px0, py0, px1, py1, fill=hex_col, outline="")
        else:
            # Full-Viewport Authentic Broadcast / FPGA Video Test Pattern Screen (ZERO black dead space!)
            # 1. Base dark grid background
            self.canvas.create_rectangle(0, 0, w, h, fill="#0A0E0C", outline="")
            for gx in range(0, w, 40):
                self.canvas.create_line(gx, 0, gx, h, fill="#121815", width=1)
            for gy in range(0, h, 40):
                self.canvas.create_line(0, gy, w, gy, fill="#121815", width=1)

            # 2. SMPTE 8-Color Bars across top (Seamless edge-to-edge)
            bar_h = 68
            bars = [
                ("#EAEAEA", "WHITE"),
                ("#DADA00", "YELLOW"),
                ("#00DADA", "CYAN"),
                ("#00DA00", "GREEN"),
                ("#DA00DA", "MAGENTA"),
                ("#DA0000", "RED"),
                ("#0000DA", "BLUE"),
                ("#141414", "BLACK"),
            ]
            bar_w = w / len(bars)
            for i, (col, b_name) in enumerate(bars):
                bx0 = int(i * bar_w)
                bx1 = int((i + 1) * bar_w) if i < len(bars) - 1 else w
                self.canvas.create_rectangle(bx0, 0, bx1, bar_h, fill=col, outline="")

            # 3. Grayscale test ramp across bottom (Seamless edge-to-edge right to bottom edge)
            ramp_h = 34
            steps = 16
            ramp_w = w / steps
            for s in range(steps):
                gray = int(s * (255 / (steps - 1)))
                g_col = f"#{gray:02X}{gray:02X}{gray:02X}"
                rx0 = int(s * ramp_w)
                rx1 = int((s + 1) * ramp_w) if s < steps - 1 else w
                self.canvas.create_rectangle(rx0, h - ramp_h, rx1, h, fill=g_col, outline="")

            # 4. Center High-Tech Monitor OSD Bezel Card (Fills middle area seamlessly)
            card_margin_x = 18
            cy0 = bar_h + 12
            cy1 = h - ramp_h - 12
            self.canvas.create_rectangle(
                card_margin_x, cy0, w - card_margin_x, cy1,
                fill="#0E1410", outline="#1ED760", width=1
            )

            # Center Card Content
            self.canvas.create_text(
                w // 2, cy0 + 26,
                text="DIGILENT NEXYS A7  •  VGA VIDEO MONITOR (ACTIVE)",
                fill=ACCENT_GREEN, font=(FONT_UI, 11, "bold")
            )
            self.canvas.create_text(
                w // 2, cy0 + 58,
                text="พร้อมรับสัญญาณภาพ 640 × 480 @ 60Hz",
                fill=TXT_BRIGHT, font=(FONT_UI, 14, "bold")
            )
            self.canvas.create_text(
                w // 2, cy0 + 96,
                text="พอร์ต VGA ต่ออยู่กับบอร์ดแล้ว — เมื่อรันโค้ดและมีการเขียนข้อมูลภาพลง VRAM\n(แอดเดรส 0xFF000000) ภาพกราฟิกจะปรากฏบนหน้านี้โดยตรงทันทีแบบ Real-Time",
                fill=TXT_MUTED, font=(FONT_UI, 9), justify="center"
            )
            self.canvas.create_text(
                w // 2, cy1 - 20,
                text="Pixel Clock: 25.175 MHz  |  Horiz: 31.47 kHz  |  Vert: 60.0 Hz  |  Color: 12-bit RGB 4:4:4",
                fill=TXT_DIM, font=(FONT_CODE, 8)
            )


class UARTTerminalWindow(tk.Toplevel):
    """Frameless USB-UART Serial Terminal Window (COM Port Simulation) matching Main Application styling."""

    def __init__(self, parent, sim_engine, on_send_callback=None):
        super().__init__(parent)
        self.sim_engine = sim_engine
        self.on_send_callback = on_send_callback
        center_on_parent(self, parent, 670, 520)
        self.minsize(600, 420)
        self.configure(bg="#121212")
        apply_main_window_style(self)

        self._build_ui()
        self._refresh_content()
        self.deiconify()
        try:
            if parent is not None:
                parent.winfo_toplevel()._active_raised_window = self
        except Exception:
            pass
        self.lift()
        self.focus_force()

    def _build_ui(self):
        # 1. Custom Dark Title Bar (Seamless, directly in root window - no nested borders)
        tb = tk.Frame(self, bg="#181818", height=38, padx=12)
        tb.pack(side=tk.TOP, fill=tk.X)
        tb.pack_propagate(False)

        title_lbl = tk.Label(
            tb, text="💬  USB-UART Serial Terminal (NEXYS A7  •  FT2232HQ)",
            bg="#181818", fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold")
        )
        title_lbl.pack(side=tk.LEFT)

        btn_close = tk.Button(
            tb, text="✕", bg="#181818", fg=TXT_MUTED,
            activebackground=ACCENT_RED, activeforeground=TXT_ON_WHITE,
            bd=0, highlightthickness=0, width=4, pady=6, cursor="hand2",
            font=(FONT_UI, 9, "bold"), command=self.destroy
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=ACCENT_RED, fg=TXT_ON_WHITE))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg="#181818", fg=TXT_MUTED))

        baud_lbl = tk.Label(
            tb, text="115200 8-N-1 (COM Port)",
            bg="#181818", fg=ACCENT_GREEN, font=(FONT_CODE, 8, "bold"), padx=10
        )
        baud_lbl.pack(side=tk.RIGHT)

        attach_window_drag(self, [tb, title_lbl, baud_lbl])

        # 2. Bottom Status Bar (Packed at bottom before text area)
        sb = tk.Frame(self, bg="#121212", height=32, padx=12)
        sb.pack(side=tk.BOTTOM, fill=tk.X)
        sb.pack_propagate(False)

        tk.Label(
            sb, text="● UART PORT: ACTIVE (Port 0xF0000010)",
            bg="#121212", fg=ACCENT_GREEN, font=(FONT_UI, 8, "bold")
        ).pack(side=tk.LEFT)

        tk.Label(
            sb, text="Baud: 115200bps   •   Data: 8-bit   •   Parity: None   •   Stop: 1",
            bg="#121212", fg=TXT_MUTED, font=(FONT_CODE, 8)
        ).pack(side=tk.RIGHT)

        # 3. Transmission / Input Bar (Packed above status bar)
        send_bar = tk.Frame(self, bg=BG_PANEL, padx=12, pady=8)
        send_bar.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(
            send_bar, text="TX ส่งข้อมูลเข้า CPU:", bg=BG_PANEL, fg=TXT_MUTED,
            font=(FONT_UI, 8, "bold")
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(
            send_bar, textvariable=self.input_var, bg=BG_ELEVATED, fg=TXT_BRIGHT,
            insertbackground=ACCENT_GREEN, bd=0, highlightthickness=1,
            highlightbackground="#383838", font=(FONT_CODE, 9)
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)
        self.input_entry.bind("<Return>", lambda e: self.send_text())

        btn_send = tk.Button(
            send_bar, text="ส่ง (Send)", bg=ACCENT_GREEN, fg=TXT_ON_WHITE,
            activebackground="#1FDF64", activeforeground=TXT_ON_WHITE,
            bd=0, padx=12, pady=2, cursor="hand2", font=(FONT_UI, 8, "bold"),
            command=self.send_text
        )
        btn_send.pack(side=tk.RIGHT)

        btn_clear = tk.Button(
            send_bar, text="ล้างหน้าจอ", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground="#333333",
            padx=10, pady=2, cursor="hand2", font=(FONT_UI, 8, "bold"),
            command=self.clear_log
        )
        btn_clear.pack(side=tk.RIGHT, padx=6)

        # 4. Terminal Screen (Scrollable Text Area directly in window)
        term_frame = tk.Frame(self, bg="#0A0E0A")
        term_frame.pack(fill=tk.BOTH, expand=True)

        self.scroll = SpotifyAutoScrollbar(term_frame, bg_track="#0A0E0A")
        self.text_area = tk.Text(
            term_frame, bg="#0A0E0A", fg=ACCENT_GREEN, insertbackground=ACCENT_GREEN,
            selectbackground="#1B4D27", font=(FONT_CODE, 10), wrap=tk.WORD,
            bd=0, highlightthickness=0, yscrollcommand=self.scroll.set, padx=8, pady=8
        )
        self.scroll.command = self.text_area.yview
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _refresh_content(self):
        self.text_area.delete("1.0", tk.END)
        buf = self.sim_engine.uart_buffer
        if not buf:
            self.text_area.insert(
                tk.END,
                "=== Nexys A7 USB-UART Serial Terminal Ready (115200 8-N-1) ===\n"
                "กำลังรอรับข้อมูลจาก CPU ที่แอดเดรส 0xF0000010...\n"
                "-----------------------------------------------------------------\n"
            )
        else:
            self.text_area.insert(tk.END, buf)
        self.text_area.see(tk.END)

    def append_text(self, text):
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)

    def send_text(self):
        val = self.input_var.get()
        if not val:
            return
        self.send_raw(val + "\n")
        self.input_var.set("")

    def send_raw(self, text):
        self.sim_engine.send_uart_input(text)
        self.append_text(f"[RX-IN] {text}")
        if self.on_send_callback:
            self.on_send_callback()

    def clear_log(self):
        self.sim_engine.uart_buffer = ""
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, "=== เคลียร์หน้าจอแล้ว ===\n")

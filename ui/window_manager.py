# -*- coding: utf-8 -*-
"""
Frameless Windows 11 DWM Rounded Window & 8-Direction Edge/Corner Resizing Mixin
"""

import ctypes
import tkinter as tk
from config.theme import BG_BLACK


class FramelessWindowMixin:
    """
    Provides native Windows 11 DWM rounded outer corners, taskbar integration,
    titlebar drag, minimize/maximize/restore, and 8-direction edge/corner resizing.
    """

    def _enable_frameless_rounded_resizable_window(self):
        self.overrideredirect(True)
        self.update()  # Ensure window is mapped with full dimensions before applying DWM attributes
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            # Apply Windows 11 native DWM smooth rounded corners (DWMWCP_ROUND = 2)
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            self._hwnd = hwnd
        except Exception:
            self._hwnd = None

        self._click_to_raise = True
        self._active_raised_window = self
        self.bind_all("<ButtonPress-1>", self._on_any_window_click_raise, add="+")
        self._build_window_resize_grips()

    def _on_any_window_click_raise(self, event):
        try:
            w = getattr(event, "widget", None)
            if w is None or isinstance(w, str):
                return
            top = w.winfo_toplevel()
            if getattr(top, "_click_to_raise", False) and top is not getattr(self, "_active_raised_window", None):
                self._active_raised_window = top
                top.lift()
        except Exception:
            pass

    def _build_window_resize_grips(self):
        grip_thickness = 5
        corner_size = 12
        specs = [
            ("n",  0.0, 0.0, 1.0, 0.0, "sb_v_double_arrow", "n"),
            ("s",  0.0, 1.0, 1.0, 0.0, "sb_v_double_arrow", "s"),
            ("w",  0.0, 0.0, 0.0, 1.0, "sb_h_double_arrow", "w"),
            ("e",  1.0, 0.0, 0.0, 1.0, "sb_h_double_arrow", "e"),
            ("nw", 0.0, 0.0, 0.0, 0.0, "size_nw_se",        "nw"),
            ("ne", 1.0, 0.0, 0.0, 0.0, "size_ne_sw",        "ne"),
            ("sw", 0.0, 1.0, 0.0, 0.0, "size_ne_sw",        "sw"),
            ("se", 1.0, 1.0, 0.0, 0.0, "size_nw_se",        "se"),
        ]
        self._resize_grips = []
        for mode, rx, ry, rw, rh, cur_name, anchor in specs:
            f = tk.Frame(self, bg=BG_BLACK, bd=0, highlightthickness=0, cursor=cur_name)
            if len(mode) == 1:
                if mode in ("n", "s"):
                    f.place(relx=rx, rely=ry, relwidth=rw, height=grip_thickness, anchor=anchor)
                else:
                    f.place(relx=rx, rely=ry, width=grip_thickness, relheight=rh, anchor=anchor)
            else:
                f.place(relx=rx, rely=ry, width=corner_size, height=corner_size, anchor=anchor)

            f.bind("<ButtonPress-1>", lambda e, m=mode: self._start_edge_resize(e, m))
            f.bind("<B1-Motion>", lambda e, m=mode: self._do_edge_resize(e, m))
            self._resize_grips.append(f)

    def _start_edge_resize(self, event, mode):
        if self._is_maximized:
            return
        self._rsz_start_x = event.x_root
        self._rsz_start_y = event.y_root
        self._rsz_win_x = self.winfo_x()
        self._rsz_win_y = self.winfo_y()
        self._rsz_win_w = self.winfo_width()
        self._rsz_win_h = self.winfo_height()

    def _do_edge_resize(self, event, mode):
        if self._is_maximized:
            return
        dx = event.x_root - self._rsz_start_x
        dy = event.y_root - self._rsz_start_y
        min_w, min_h = 1100, 650

        nx, ny = self._rsz_win_x, self._rsz_win_y
        nw, nh = self._rsz_win_w, self._rsz_win_h

        if "e" in mode:
            nw = max(min_w, self._rsz_win_w + dx)
        if "s" in mode:
            nh = max(min_h, self._rsz_win_h + dy)
        if "w" in mode:
            cand_w = self._rsz_win_w - dx
            if cand_w >= min_w:
                nw = cand_w
                nx = self._rsz_win_x + dx
        if "n" in mode:
            cand_h = self._rsz_win_h - dy
            if cand_h >= min_h:
                nh = cand_h
                ny = self._rsz_win_y + dy

        self.geometry(f"{nw}x{nh}+{nx}+{ny}")

    def _start_window_drag(self, event):
        try:
            self._active_raised_window = self
            self.lift()
        except Exception:
            pass
        if self._is_maximized:
            return
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _do_window_drag(self, event):
        if self._is_maximized:
            return
        nx = event.x_root - self._drag_offset_x
        ny = event.y_root - self._drag_offset_y
        self.geometry(f"+{nx}+{ny}")

    def minimize_window(self):
        try:
            hwnd = getattr(self, "_hwnd", None) or ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            pass

    def toggle_maximize_window(self):
        if not self._is_maximized:
            self._normal_geom = self.geometry()
            try:
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)
                    ]
                rect = RECT()
                ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                self.geometry(f"{w}x{h}+{rect.left}+{rect.top}")
            except Exception:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight() - 48
                self.geometry(f"{sw}x{sh}+0+0")
            self._is_maximized = True
            self.btn_max_win.config(text="\uE923")
            try:
                if getattr(self, "_hwnd", None):
                    pref = ctypes.c_int(1)  # DWMWCP_DONOTROUND when maximized
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(self._hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass
        else:
            self.geometry(self._normal_geom)
            self._is_maximized = False
            self.btn_max_win.config(text="\uE922")
            try:
                if getattr(self, "_hwnd", None):
                    pref = ctypes.c_int(2)  # DWMWCP_ROUND when restored
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(self._hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass
        self.update_idletasks()

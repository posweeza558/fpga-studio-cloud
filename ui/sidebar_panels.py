# -*- coding: utf-8 -*-
"""
Left Sidebar Panels Mixin:
- Explorer View (Multi-folder collapsible tree, inline file/folder creation & rename)
- Search View (Project-wide code & 32-bit opcode search + Quick ISA Reference)
- Extensions View (Marketplace cards for C++, Python, Rust, Verilog HDL)
"""

import os
import re
import json
import shutil
import tkinter as tk
from tkinter import filedialog
from config.theme import (
    BG_SIDEBAR,
    BG_ELEVATED,
    BG_PILL_INACT,
    BG_HOVER,
    BORDER_COLOR,
    BORDER_HOVER,
    ACCENT_GREEN,
    ACCENT_YELLOW,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    TXT_DIM,
    TXT_ON_WHITE,
    FONT_UI,
    FONT_CODE,
)
from config.catalog import (
    DEFAULT_PROJECT_DIR,
    EXTENSIONS_STATE_FILE,
    DEFAULT_FILES,
    BADGE_STYLES,
    EXTENSIONS_CATALOG,
    EXT_TO_CATALOG,
    ISA_REFERENCE,
)
from ui.graphics import truncate_to_pixel_width, add_hover_border
from ui.widgets import SpotifyPillButton, SpotifyPopupMenu, SpotifyAutoScrollbar


class SidebarPanelsMixin:
    """Provides Explorer, Search, and Extensions Marketplace sidebar views and workspace file operations."""

    # ==========================================================================
    # REAL DISK WORKSPACE & EXTENSIONS PERSISTENCE
    # ==========================================================================
    def _init_workspace_on_disk(self):
        os.makedirs(DEFAULT_PROJECT_DIR, exist_ok=True)
        existing = [
            f for f in os.listdir(DEFAULT_PROJECT_DIR)
            if os.path.isfile(os.path.join(DEFAULT_PROJECT_DIR, f))
        ]
        if not existing:
            for fname, content in DEFAULT_FILES.items():
                fpath = os.path.join(DEFAULT_PROJECT_DIR, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

    def _load_extensions_state(self):
        # All extensions (C++, Python, Rust, Verilog) are enabled 100% out-of-the-box
        return {item["id"] for item in EXTENSIONS_CATALOG}

    def _save_extensions_state(self):
        pass

    def _is_file_missing_extension(self, filepath):
        # All extensions are built-in and active by default; never prompt
        return None

    def _list_workspace_folders(self):
        if not os.path.isdir(self.workspace_root):
            return []
        folders = []
        for entry in sorted(os.listdir(self.workspace_root)):
            full = os.path.join(self.workspace_root, entry)
            if os.path.isdir(full) and not entry.startswith("."):
                folders.append(full)
        if not folders and os.path.isdir(self.project_dir):
            folders.append(self.project_dir)
        return folders

    def _list_files_in_dir(self, folder_path):
        if not os.path.isdir(folder_path):
            return []
        items = []
        for fn in sorted(os.listdir(folder_path)):
            full = os.path.join(folder_path, fn)
            if os.path.isfile(full) and not fn.startswith("."):
                items.append(fn)
        return items

    # ==========================================================================
    # VIEW 1: MULTI-FOLDER COLLAPSIBLE EXPLORER
    # ==========================================================================
    def _build_explorer_view(self):
        hdr = tk.Frame(self.view_explorer, bg=BG_SIDEBAR, padx=14, pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="EXPLORER", bg=BG_SIDEBAR, fg=TXT_BRIGHT,
                 font=(FONT_UI, 10, "bold")).pack(side=tk.LEFT)

        act_row = tk.Frame(self.view_explorer, bg=BG_SIDEBAR, padx=10, pady=2)
        act_row.pack(fill=tk.X)

        for btn_txt, btn_cmd in [
            ("+ ไฟล์ใหม่",     self.start_inline_new_file),
            ("+ โฟลเดอร์ใหม่", self.start_inline_new_project),
            ("เปิดโฟลเดอร์",    self.open_folder_dialog),
        ]:
            b = tk.Button(
                act_row, text=btn_txt, bd=0,
                highlightthickness=1, highlightbackground=BG_PILL_INACT,
                padx=6, pady=4,
                bg=BG_PILL_INACT, fg=TXT_BRIGHT, activebackground=BG_HOVER, activeforeground=ACCENT_GREEN,
                cursor="hand2", font=(FONT_UI, 8, "bold"), command=btn_cmd
            )
            b.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
            add_hover_border(b, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        tree_area = tk.Frame(self.view_explorer, bg=BG_SIDEBAR)
        tree_area.pack(fill=tk.BOTH, expand=True, pady=(6, 2))

        self.exp_scroll = SpotifyAutoScrollbar(tree_area, bg_track=BG_SIDEBAR)
        self.exp_canvas = tk.Canvas(
            tree_area, bg=BG_SIDEBAR, bd=0, highlightthickness=0,
            yscrollcommand=self.exp_scroll.set
        )
        self.exp_scroll.command = self.exp_canvas.yview
        self.exp_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.file_list_frame = tk.Frame(self.exp_canvas, bg=BG_SIDEBAR)
        self._exp_canvas_win = self.exp_canvas.create_window((0, 0), window=self.file_list_frame, anchor="nw")

        self.file_list_frame.bind(
            "<Configure>",
            lambda e: self.exp_canvas.configure(scrollregion=self.exp_canvas.bbox("all"))
        )
        self.exp_canvas.bind(
            "<Configure>",
            lambda e: self.exp_canvas.itemconfig(self._exp_canvas_win, width=e.width)
        )

        def _on_exp_wheel(event):
            first, last = self.exp_canvas.yview()
            if first <= 0.0 and last >= 1.0:
                return
            self.exp_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.exp_canvas.bind("<Enter>", lambda e: self.exp_canvas.bind_all("<MouseWheel>", _on_exp_wheel))
        self.exp_canvas.bind("<Leave>", lambda e: self.exp_canvas.unbind_all("<MouseWheel>"))

        self.file_buttons = {}
        self.folder_frames = {}

        tk.Frame(self.view_explorer, bg=BORDER_COLOR, height=1).pack(fill=tk.X, padx=14, pady=6)

        exp_hdr = tk.Frame(self.view_explorer, bg=BG_SIDEBAR, padx=14, pady=2)
        exp_hdr.pack(fill=tk.X)
        tk.Label(exp_hdr, text="ส่งออกไฟล์ลงบอร์ด VIVADO", bg=BG_SIDEBAR, fg=TXT_MUTED,
                 font=(FONT_UI, 9, "bold")).pack(side=tk.LEFT)

        for exp_txt, exp_kind in [
            ("บันทึก instruction_memory.vhd", "vhdl"),
            ("บันทึก program.coe",            "coe"),
            ("บันทึก machine_code_32bit.txt", "bin"),
        ]:
            eb = tk.Button(
                self.view_explorer, text=exp_txt, anchor="w",
                bg=BG_SIDEBAR, fg=TXT_MUTED, activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
                bd=0, highlightthickness=1, highlightbackground=BG_SIDEBAR,
                padx=12, pady=4, cursor="hand2",
                font=(FONT_UI, 8, "bold"),
                command=lambda k=exp_kind: self.export_file(k)
            )
            eb.pack(fill=tk.X, padx=8, pady=1)
            add_hover_border(eb, BG_SIDEBAR, "#1D1D1D", BG_SIDEBAR, BORDER_HOVER)

    def _clear_inline_entry(self):
        if self._inline_entry_row and self._inline_entry_row.winfo_exists():
            self._inline_entry_row.destroy()
        self._inline_entry_row = None

    def toggle_folder_expand(self, folder_path):
        abs_p = os.path.abspath(folder_path)
        self.project_dir = abs_p
        if abs_p in self.expanded_folders:
            self.expanded_folders.remove(abs_p)
        else:
            self.expanded_folders.add(abs_p)
        self.refresh_project_explorer()

    def refresh_project_explorer(self):
        self._clear_inline_entry()
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        self.file_buttons.clear()
        self.folder_frames.clear()

        folders = self._list_workspace_folders()
        for folder_path in folders:
            abs_f = os.path.abspath(folder_path)
            fname_dir = os.path.basename(abs_f) or abs_f
            is_expanded = abs_f in self.expanded_folders
            is_active_proj = (abs_f == os.path.abspath(self.project_dir))

            hdr_bg = "#1C1C1C" if is_active_proj else "#161616"
            f_hdr = tk.Frame(
                self.file_list_frame, bg=hdr_bg, padx=8, pady=4,
                highlightthickness=1, highlightbackground="#252525" if is_active_proj else "#161616"
            )
            f_hdr.pack(fill=tk.X, padx=6, pady=(4, 1))

            arrow = "▾" if is_expanded else "▸"
            f_disp = truncate_to_pixel_width(fname_dir, (FONT_UI, 9, "bold"), max_px=220)
            f_btn = tk.Button(
                f_hdr, text=f"{arrow}  {f_disp}", anchor="w",
                bg=hdr_bg,
                fg=ACCENT_GREEN if is_active_proj else TXT_BRIGHT,
                activebackground=BG_HOVER, activeforeground=ACCENT_GREEN,
                bd=0, highlightthickness=0, cursor="hand2",
                font=(FONT_UI, 9, "bold"),
                command=lambda p=abs_f: self.toggle_folder_expand(p)
            )
            f_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
            add_hover_border(f_hdr, hdr_bg, "#242424", "#252525" if is_active_proj else "#161616", BORDER_HOVER, sync_children=True)

            def _show_folder_ctx(event, p=abs_f, fn=fname_dir):
                m = SpotifyPopupMenu(self)
                m.add_command("สร้างไฟล์ใหม่ในโฟลเดอร์นี้", command=lambda: self.start_inline_new_file(target_dir=p))
                m.add_command("เปิดโฟลเดอร์ใน Windows Explorer", command=lambda: os.startfile(p))
                m.add_separator()
                m.add_command(f"ลบโฟลเดอร์ ({fn})", command=lambda: self.delete_folder_direct(p))
                m.show(event.x_root, event.y_root)

            f_btn.bind("<Button-3>", _show_folder_ctx)

            files_box = tk.Frame(self.file_list_frame, bg=BG_SIDEBAR)
            self.folder_frames[abs_f] = files_box
            if is_expanded:
                files_box.pack(fill=tk.X)

                for fname in self._list_files_in_dir(abs_f):
                    full_p = os.path.abspath(os.path.join(abs_f, fname))
                    ext = os.path.splitext(fname)[1].lower()
                    badge, badge_col = BADGE_STYLES.get(ext, ("TEXT", TXT_MUTED))

                    display_name = truncate_to_pixel_width(fname, (FONT_UI, 9, "bold"), max_px=190)

                    missing_ext = self._is_file_missing_extension(full_p) is not None
                    has_err = (full_p in self.file_errors) and not missing_ext

                    row = tk.Frame(
                        files_box, bg=BG_SIDEBAR, padx=6, pady=1,
                        highlightthickness=1, highlightbackground=BG_SIDEBAR
                    )
                    row.pack(fill=tk.X, padx=(14, 6), pady=1)

                    lbl_ic = tk.Label(row, text=badge, bg=BG_ELEVATED, fg=badge_col,
                                      font=(FONT_CODE, 7, "bold"), width=4, pady=3)
                    lbl_ic.pack(side=tk.LEFT, padx=(2, 6))

                    dot_txt = "●" if (has_err or missing_ext) else ""
                    dot_col = ACCENT_YELLOW if missing_ext else ACCENT_RED
                    err_dot = tk.Label(
                        row, text=dot_txt,
                        bg=BG_SIDEBAR, fg=dot_col, font=(FONT_UI, 9, "bold"), width=2
                    )
                    err_dot.pack(side=tk.RIGHT, padx=(2, 2))

                    txt_col = ACCENT_YELLOW if missing_ext else (ACCENT_RED if has_err else TXT_PRIMARY)
                    b = tk.Button(
                        row, text=display_name, anchor="w",
                        bg=BG_SIDEBAR, fg=txt_col,
                        activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
                        bd=0, highlightthickness=0, padx=4, pady=3, cursor="hand2",
                        font=(FONT_UI, 9, "bold"),
                        command=lambda fp=full_p: self.load_file_path(fp)
                    )
                    b.pack(side=tk.LEFT, fill=tk.X, expand=True)

                    def _row_enter(e, r=row, bt=b, dt=err_dot, fp=full_p):
                        r.config(bg="#222222", highlightbackground=BORDER_HOVER)
                        bt.config(bg="#222222")
                        dt.config(bg="#222222")

                    def _row_leave(e, r=row, bt=b, dt=err_dot, fp=full_p):
                        is_act = (fp == os.path.abspath(self.current_file_path)) if self.current_file_path else False
                        bg_c = "#232323" if is_act else BG_SIDEBAR
                        r.config(bg=bg_c, highlightbackground="#383838" if is_act else BG_SIDEBAR)
                        bt.config(bg=bg_c)
                        dt.config(bg=bg_c)

                    for w_el in (row, b, lbl_ic, err_dot):
                        w_el.bind("<Enter>", _row_enter)
                        w_el.bind("<Leave>", _row_leave)

                    def _show_file_ctx(event, fp=full_p, fn=fname, r=row, p=abs_f):
                        m = SpotifyPopupMenu(self)
                        m.add_command(f"เปลี่ยนชื่อไฟล์ ({fn})", command=lambda: self.start_inline_rename_file(fp, r))
                        m.add_command(f"ลบไฟล์ ({fn})", command=lambda: self.delete_file_direct(fp))
                        m.add_separator()
                        m.add_command("เปิดโฟลเดอร์จริงใน Windows Explorer", command=lambda: os.startfile(p))
                        m.show(event.x_root, event.y_root)

                    b.bind("<Button-3>", _show_file_ctx)
                    self.file_buttons[full_p] = (row, lbl_ic, b, err_dot)

        self._highlight_active_file_in_explorer()
        self.file_list_frame.update_idletasks()
        self.exp_canvas.configure(scrollregion=self.exp_canvas.bbox("all"))

    def _highlight_active_file_in_explorer(self):
        cur_abs = os.path.abspath(self.current_file_path) if self.current_file_path else ""
        for full_p, (row, lbl_ic, btn, err_dot) in self.file_buttons.items():
            active = (full_p == cur_abs)
            missing_ext = self._is_file_missing_extension(full_p) is not None
            has_err = (full_p in self.file_errors) and not missing_ext
            bg = "#232323" if active else BG_SIDEBAR
            row.config(bg=bg, highlightbackground="#383838" if active else BG_SIDEBAR)
            err_dot.config(
                bg=bg,
                text="●" if (has_err or missing_ext) else "",
                fg=ACCENT_YELLOW if missing_ext else ACCENT_RED
            )
            if missing_ext:
                btn.config(bg=bg, fg=ACCENT_YELLOW)
            elif has_err:
                btn.config(bg=bg, fg=ACCENT_RED)
            else:
                btn.config(bg=bg, fg=ACCENT_GREEN if active else TXT_PRIMARY)

    # ==========================================================================
    # INLINE FILE & FOLDER CREATION / RENAME / DELETE
    # ==========================================================================
    def start_inline_new_file(self, target_dir=None):
        if self.left_sidebar_mode != "explorer":
            self.switch_left_sidebar("explorer", toggle=False)
        if target_dir:
            self.project_dir = os.path.abspath(target_dir)
        abs_proj = os.path.abspath(self.project_dir)
        if abs_proj not in self.expanded_folders:
            self.expanded_folders.add(abs_proj)
            self.refresh_project_explorer()
        else:
            self._clear_inline_entry()

        parent_box = self.folder_frames.get(abs_proj, self.file_list_frame)
        row = tk.Frame(parent_box, bg="#1F1F1F", highlightbackground=ACCENT_GREEN, highlightthickness=1, padx=6, pady=3)
        row.pack(fill=tk.X, padx=(14, 6), pady=3)
        self._inline_entry_row = row

        tk.Label(row, text="+", bg="#1F1F1F", fg=ACCENT_GREEN, font=(FONT_CODE, 9, "bold"), width=2).pack(side=tk.LEFT)

        ent = tk.Entry(
            row, bg="#1F1F1F", fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            bd=0, relief="flat", font=(FONT_CODE, 9)
        )
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ent.focus_set()

        done = [False]

        def commit_new_file(event=None):
            if done[0]:
                return
            fname = ent.get().strip()
            if not fname:
                cancel_new_file()
                return
            done[0] = True
            self._clear_inline_entry()

            fpath = os.path.join(self.project_dir, fname)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("")
            self.refresh_project_explorer()
            self.load_file_path(fpath)
            ext = os.path.splitext(fname)[1]
            mode_note = " (โหมด TEXT)" if not ext else ""
            self.status_lbl.config(text=f"สร้างไฟล์ว่าง {fname}{mode_note} เรียบร้อย")

        def cancel_new_file(event=None):
            if done[0]:
                return
            done[0] = True
            self._clear_inline_entry()

        def on_focus_out(event=None):
            if ent.get().strip() == "":
                cancel_new_file()

        ent.bind("<Return>", commit_new_file)
        ent.bind("<Escape>", cancel_new_file)
        ent.bind("<FocusOut>", on_focus_out)

    def start_inline_new_project(self):
        if self.left_sidebar_mode != "explorer":
            self.switch_left_sidebar("explorer", toggle=False)
        self._clear_inline_entry()

        row = tk.Frame(self.file_list_frame, bg="#1F1F1F", highlightbackground=ACCENT_GREEN, highlightthickness=1, padx=6, pady=3)
        row.pack(fill=tk.X, padx=6, pady=3)
        self._inline_entry_row = row

        tk.Label(row, text="▸", bg="#1F1F1F", fg=ACCENT_GREEN, font=(FONT_CODE, 9, "bold"), width=2).pack(side=tk.LEFT)

        ent = tk.Entry(
            row, bg="#1F1F1F", fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            bd=0, relief="flat", font=(FONT_CODE, 9)
        )
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ent.focus_set()

        done = [False]

        def commit_new_folder(event=None):
            if done[0]:
                return
            proj_name = ent.get().strip()
            if not proj_name:
                cancel_new_folder()
                return
            done[0] = True
            self._clear_inline_entry()

            new_dir = os.path.abspath(os.path.join(self.workspace_root, proj_name))
            os.makedirs(new_dir, exist_ok=True)
            self.project_dir = new_dir
            self.expanded_folders.add(new_dir)
            self.refresh_project_explorer()
            self.status_lbl.config(text=f"สร้างโฟลเดอร์ว่าง '{proj_name}' เรียบร้อย")

        def cancel_new_folder(event=None):
            if done[0]:
                return
            done[0] = True
            self._clear_inline_entry()

        def on_focus_out(event=None):
            if ent.get().strip() == "":
                cancel_new_folder()

        ent.bind("<Return>", commit_new_folder)
        ent.bind("<Escape>", cancel_new_folder)
        ent.bind("<FocusOut>", on_focus_out)

    def start_inline_rename_file(self, old_full_path, row_widget):
        self._clear_inline_entry()
        old_name = os.path.basename(old_full_path)
        folder_dir = os.path.dirname(old_full_path)
        parent_box = self.folder_frames.get(os.path.abspath(folder_dir), self.file_list_frame)

        row = tk.Frame(parent_box, bg="#1F1F1F", highlightbackground=ACCENT_GREEN, highlightthickness=1, padx=6, pady=3)
        row.pack(fill=tk.X, padx=(14, 6), pady=2, before=row_widget)
        self._inline_entry_row = row

        ent = tk.Entry(
            row, bg="#1F1F1F", fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            bd=0, relief="flat", font=(FONT_CODE, 9)
        )
        ent.insert(0, old_name)
        ent.select_range(0, tk.END)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ent.focus_set()

        done = [False]

        def commit_rename(event=None):
            if done[0]:
                return
            new_name = ent.get().strip()
            if not new_name or new_name == old_name:
                cancel_rename()
                return
            done[0] = True
            self._clear_inline_entry()

            old_abs = os.path.abspath(old_full_path)
            new_p = os.path.abspath(os.path.join(folder_dir, new_name))
            try:
                os.rename(old_abs, new_p)
                if old_abs in self.file_errors:
                    self.file_errors[new_p] = self.file_errors.pop(old_abs)
                if old_abs in self.open_tabs:
                    self.open_tabs[self.open_tabs.index(old_abs)] = new_p
                self.refresh_project_explorer()
                if os.path.abspath(self.current_file_path) == old_abs:
                    self.load_file_path(new_p)
                else:
                    self._refresh_editor_tabs()
                self.status_lbl.config(text=f"เปลี่ยนชื่อไฟล์เป็น {new_name} เรียบร้อย")
            except Exception as e:
                self.status_lbl.config(text=f"เปลี่ยนชื่อไม่สำเร็จ: {e}")

        def cancel_rename(event=None):
            if done[0]:
                return
            done[0] = True
            self._clear_inline_entry()

        def on_focus_out(event=None):
            if ent.get().strip() == "":
                cancel_rename()

        ent.bind("<Return>", commit_rename)
        ent.bind("<Escape>", cancel_rename)
        ent.bind("<FocusOut>", on_focus_out)

    def open_folder_dialog(self):
        chosen = filedialog.askdirectory(
            title="เลือกโฟลเดอร์โปรเจกต์ (คลิกขวาสร้างโฟลเดอร์/ไฟล์ในหน้าต่างนี้ได้เลย)",
            initialdir=self.workspace_root,
            mustexist=False
        )
        if not chosen:
            return
        chosen_abs = os.path.abspath(chosen)
        os.makedirs(chosen_abs, exist_ok=True)
        parent_dir = os.path.dirname(chosen_abs)
        if os.path.isdir(parent_dir) and parent_dir != chosen_abs:
            self.workspace_root = parent_dir
        else:
            self.workspace_root = chosen_abs
        self.project_dir = chosen_abs
        self.expanded_folders.add(chosen_abs)
        self.refresh_project_explorer()
        files = self._list_files_in_dir(chosen_abs)
        if files:
            self.load_file_path(os.path.join(chosen_abs, files[0]))
        self.status_lbl.config(text=f"เปิดโฟลเดอร์: {os.path.basename(chosen_abs)}")

    def delete_file_direct(self, full_path):
        try:
            abs_p = os.path.abspath(full_path)
            fname = os.path.basename(abs_p)
            os.remove(abs_p)
            self.file_errors.pop(abs_p, None)
            if abs_p in self.open_tabs:
                self.open_tabs.remove(abs_p)
            self.refresh_project_explorer()
            if os.path.abspath(self.current_file_path) == abs_p:
                if self.open_tabs:
                    self.load_file_path(self.open_tabs[-1])
                else:
                    files = self._list_files_in_dir(self.project_dir)
                    if files:
                        self.load_file_path(os.path.join(self.project_dir, files[0]))
                    else:
                        self.current_file = ""
                        self.current_file_path = ""
                        self.code_text.delete("1.0", tk.END)
                        self._refresh_editor_tabs()
            else:
                self._refresh_editor_tabs()
            self.status_lbl.config(text=f"ลบไฟล์ {fname} เรียบร้อย")
        except Exception as e:
            self.status_lbl.config(text=f"ลบไฟล์ไม่สำเร็จ: {e}")

    def delete_folder_direct(self, folder_path):
        try:
            shutil.rmtree(folder_path)
            self.expanded_folders.discard(os.path.abspath(folder_path))
            folders = self._list_workspace_folders()
            if folders:
                self.project_dir = folders[0]
            self.refresh_project_explorer()
            self._refresh_editor_tabs()
        except Exception as e:
            self.status_lbl.config(text=f"ลบโฟลเดอร์ไม่สำเร็จ: {e}")

    # ==========================================================================
    # VIEW 2: SEARCH & INSTRUCTION FINDER SIDEBAR
    # ==========================================================================
    def _build_search_view(self):
        hdr = tk.Frame(self.view_search, bg=BG_SIDEBAR, padx=14, pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="SEARCH", bg=BG_SIDEBAR, fg=TXT_BRIGHT,
                 font=(FONT_UI, 10, "bold")).pack(side=tk.LEFT)

        search_box = tk.Frame(
            self.view_search, bg=BG_ELEVATED, padx=10, pady=6,
            highlightthickness=1, highlightbackground="#2E2E2E"
        )
        search_box.pack(fill=tk.X, padx=12, pady=(0, 8))
        add_hover_border(search_box, BG_ELEVATED, "#262626", "#2E2E2E", ACCENT_GREEN)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_box, textvariable=self.search_var,
            bg=BG_ELEVATED, fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            bd=0, relief="flat", font=(FONT_UI, 9)
        )
        self.search_entry.pack(fill=tk.X)
        self.search_entry.bind("<KeyRelease>", self._run_project_search)

        tk.Label(self.view_search, text="พิมพ์คำค้นหา เช่น SWITCH, lw, jal, 0x0018, 0xF0000000",
                 bg=BG_SIDEBAR, fg=TXT_DIM, font=(FONT_UI, 8), anchor="w", padx=14).pack(fill=tk.X)

        self.search_summary_lbl = tk.Label(
            self.view_search, text="ผลลัพธ์การค้นหา (คลิกเพื่อกระโดดไปยังจุดนั้น)",
            bg=BG_SIDEBAR, fg=ACCENT_GREEN, font=(FONT_UI, 9, "bold"), anchor="w", padx=14, pady=6
        )
        self.search_summary_lbl.pack(fill=tk.X)

        list_wrap = tk.Frame(self.view_search, bg="#181818", highlightthickness=1, highlightbackground="#242424")
        list_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.search_scroll = SpotifyAutoScrollbar(list_wrap, bg_track="#181818")
        self.search_results_list = tk.Listbox(
            list_wrap, bg="#181818", fg=TXT_PRIMARY,
            selectbackground="#282828", selectforeground=ACCENT_GREEN,
            bd=0, highlightthickness=0, font=(FONT_CODE, 8), activestyle="none",
            yscrollcommand=self.search_scroll.set
        )
        self.search_scroll.command = self.search_results_list.yview
        self.search_results_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.search_results_list.bind("<<ListboxSelect>>", self._on_search_result_clicked)
        self._search_targets = []

        isa_box = tk.Frame(self.view_search, bg="#181818", padx=12, pady=10, highlightthickness=1, highlightbackground="#242424")
        isa_box.pack(fill=tk.X, padx=12, pady=10)
        tk.Label(isa_box, text="คู่มือคำสั่ง RISC-V / MIPS ด่วน", bg="#181818", fg=TXT_BRIGHT,
                 font=(FONT_UI, 9, "bold"), anchor="w").pack(fill=tk.X, pady=(0, 4))
        self.isa_hint_lbl = tk.Label(
            isa_box, text="พิมพ์ชื่อคำสั่ง (เช่น lui, addi, lw, sw, beq, jal) ในช่องค้นหาด้านบนเพื่อดูรูปแบบคำสั่ง",
            bg="#181818", fg=TXT_MUTED, font=(FONT_UI, 8), justify="left", wraplength=235, anchor="w"
        )
        self.isa_hint_lbl.pack(fill=tk.X)

    def _run_project_search(self, event=None):
        q = self.search_var.get().strip()
        self.search_results_list.delete(0, tk.END)
        self._search_targets.clear()
        self.code_text.tag_remove("search_hit", "1.0", tk.END)

        if not q:
            self.search_summary_lbl.config(text="ผลลัพธ์การค้นหา (คลิกเพื่อกระโดดไปยังจุดนั้น)")
            self.isa_hint_lbl.config(text="พิมพ์ชื่อคำสั่ง (เช่น lui, addi, lw, sw, beq, jal) ในช่องค้นหาด้านบนเพื่อดูรูปแบบคำสั่ง")
            return

        ql = q.lower()
        if ql in ISA_REFERENCE:
            self.isa_hint_lbl.config(text=ISA_REFERENCE[ql], fg=ACCENT_GREEN)
        else:
            self.isa_hint_lbl.config(text="ค้นหาทั้งในไฟล์โค้ดของโปรเจกต์ และในตาราง 32-bit Machine Code", fg=TXT_MUTED)

        for idx, ins in enumerate(self.compiled_ins):
            row_str = f"{ins['pc']} {ins['asm']} {ins['hex']} {ins['desc']}"
            if ql in row_str.lower():
                self.search_results_list.insert(tk.END, f"[32-bit {ins['pc']}] {ins['asm']} ({ins['hex']})")
                self._search_targets.append(("opcode", idx, None))

        for folder_p in self._list_workspace_folders():
            for fname in self._list_files_in_dir(folder_p):
                fpath = os.path.join(folder_p, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for ln_no, line in enumerate(f, 1):
                            if ql in line.lower():
                                preview = line.strip()[:34]
                                self.search_results_list.insert(tk.END, f"[{fname}:{ln_no}] {preview}")
                                self._search_targets.append(("file", fpath, ln_no))
                except Exception:
                    pass

        code = self.code_text.get("1.0", tk.END)
        for m in re.finditer(re.escape(q), code, re.IGNORECASE):
            self.code_text.tag_add("search_hit", f"1.0+{m.start()}c", f"1.0+{m.end()}c")

        self.search_summary_lbl.config(text=f"พบทั้งหมด {len(self._search_targets)} รายการ")

    def _on_search_result_clicked(self, event=None):
        sel = self.search_results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._search_targets):
            return
        kind, a, b = self._search_targets[idx]
        if kind == "opcode":
            if not self.show_machine_panel_var.get():
                self.toggle_machine_panel()
            self.switch_right_view("opcode")
            iid = str(a)
            if self.op_tree.exists(iid):
                self.op_tree.selection_set(iid)
                self.op_tree.see(iid)
        elif kind == "file":
            if os.path.abspath(self.current_file_path) != os.path.abspath(a):
                self.load_file_path(a)
            self.code_text.mark_set(tk.INSERT, f"{b}.0")
            self.code_text.see(f"{b}.0")
            self._run_project_search()

    # ==========================================================================
    # VIEW 3: EXTENSIONS MARKETPLACE SIDEBAR
    # ==========================================================================
    def _build_extensions_view(self):
        hdr = tk.Frame(self.view_extensions, bg=BG_SIDEBAR, padx=14, pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="EXTENSIONS", bg=BG_SIDEBAR, fg=TXT_BRIGHT,
                 font=(FONT_UI, 10, "bold")).pack(side=tk.LEFT)

        tk.Label(
            self.view_extensions,
            text="ติดตั้งส่วนเสริมภาษาเพื่อเขียน C++, Python, Rust หรือส่งออก Verilog HDL ลงบอร์ด FPGA",
            bg=BG_SIDEBAR, fg=TXT_MUTED, font=(FONT_UI, 8), justify="left", wraplength=250, anchor="w", padx=14
        ).pack(fill=tk.X, pady=(0, 8))

        self.ext_cards_frame = tk.Frame(self.view_extensions, bg=BG_SIDEBAR)
        self.ext_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        self._refresh_extension_cards()

    def _refresh_extension_cards(self):
        for w in self.ext_cards_frame.winfo_children():
            w.destroy()

        for ext_info in EXTENSIONS_CATALOG:
            ext_id = ext_info["id"]
            is_inst = ext_id in self.installed_extensions

            card = tk.Frame(
                self.ext_cards_frame, bg="#181818", padx=10, pady=8,
                highlightthickness=1, highlightbackground="#252525"
            )
            card.pack(fill=tk.X, pady=4)
            add_hover_border(card, "#181818", "#202020", "#252525", BORDER_HOVER, sync_children=True)

            top = tk.Frame(card, bg="#181818")
            top.pack(fill=tk.X)

            badge = tk.Label(top, text=ext_info["badge"], bg=BG_ELEVATED, fg=ext_info["badge_color"],
                             font=(FONT_CODE, 9, "bold"), width=4, pady=3)
            badge.pack(side=tk.LEFT, padx=(0, 8))

            title_col = tk.Frame(top, bg="#181818")
            title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(title_col, text=ext_info["name"], bg="#181818", fg=TXT_BRIGHT,
                     font=(FONT_UI, 9, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(title_col, text=ext_info["publisher"], bg="#181818", fg=TXT_DIM,
                     font=(FONT_UI, 8), anchor="w").pack(fill=tk.X)

            tk.Label(card, text=ext_info["desc"], bg="#181818", fg=TXT_MUTED,
                     font=(FONT_UI, 8), justify="left", wraplength=235, anchor="w").pack(fill=tk.X, pady=(6, 6))

            btn_row = tk.Frame(card, bg="#181818")
            btn_row.pack(fill=tk.X)

            if is_inst:
                b_uninst = SpotifyPillButton(
                    btn_row, text="✓ ติดตั้งแล้ว (ถอน)", bg_parent="#181818",
                    fill_col=BG_PILL_INACT, fg_col=ACCENT_GREEN, hover_fill="#2E2E2E",
                    font_spec=(FONT_UI, 8, "bold"), pad_x=10, height=26,
                    icon_font_name=self.icon_font_name,
                    command=lambda eid=ext_id: self.toggle_install_extension(eid)
                )
                b_uninst.pack(side=tk.LEFT)

                if ext_info["sample_file"]:
                    b_sample = SpotifyPillButton(
                        btn_row, text="+ ลองไฟล์ตัวอย่าง", bg_parent="#181818",
                        fill_col=ACCENT_GREEN, fg_col=TXT_ON_WHITE, hover_fill="#1FDF64",
                        font_spec=(FONT_UI, 8, "bold"), pad_x=10, height=26,
                        icon_font_name=self.icon_font_name,
                        command=lambda info=ext_info: self.create_extension_sample_file(info)
                    )
                    b_sample.pack(side=tk.RIGHT)
            else:
                b_inst = SpotifyPillButton(
                    btn_row, text="ดาวน์โหลด & ติดตั้ง (Install)", bg_parent="#181818",
                    fill_col=ACCENT_GREEN, fg_col=TXT_ON_WHITE, hover_fill="#1FDF64",
                    font_spec=(FONT_UI, 8, "bold"), pad_x=12, height=26,
                    icon_glyph="\uE896", icon_font_name=self.icon_font_name,
                    command=lambda eid=ext_id: self.toggle_install_extension(eid)
                )
                b_inst.pack(side=tk.LEFT)

    def toggle_install_extension(self, ext_id):
        ext_info = next((x for x in EXTENSIONS_CATALOG if x["id"] == ext_id), None)
        if not ext_info:
            return

        if ext_id in self.installed_extensions:
            self.installed_extensions.remove(ext_id)
            if ext_id == "verilog_exporter":
                self.tab_btn_verilog.pack_forget()
                if self.right_view_mode == "verilog":
                    self.switch_right_view("opcode")
            self.status_lbl.config(text=f"ถอนการติดตั้งส่วนเสริม {ext_info['name']} แล้ว")
        else:
            self.installed_extensions.add(ext_id)
            if ext_id == "verilog_exporter":
                self.tab_btn_verilog.pack(side=tk.LEFT, padx=(0, 6), before=self.tab_btn_coe)
            self._hide_extension_recommend_popup()
            self.status_lbl.config(text=f"ติดตั้งส่วนเสริม {ext_info['name']} สำเร็จ")

        self._save_extensions_state()
        self._refresh_extension_cards()
        self.refresh_project_explorer()
        self.compile_now()

    def create_extension_sample_file(self, ext_info):
        fname = ext_info["sample_file"]
        fpath = os.path.join(self.project_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(ext_info["sample_code"])
        self.expanded_folders.add(os.path.abspath(self.project_dir))
        self.refresh_project_explorer()
        self.load_file_path(fpath)
        self.switch_left_sidebar("explorer", toggle=False)

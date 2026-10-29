# -*- coding: utf-8 -*-
"""
FPGA Studio — Spotify Dark Edition (Entry Point)

Project layout:
    config/   theme.py (colors & fonts), catalog.py (paths, starter files, extensions, ISA reference)
    core/     disassembler, assembler, transpiler, gcc_toolchain, hdl_generator, simulator_engine
    ui/       graphics, widgets, window_manager, sidebar_panels, board_panels, studio_window
"""

import ctypes


def _enable_high_dpi():
    """Enable Windows High-DPI awareness & set AppUserModelID for taskbar icon."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("fpga.studio.desktop.ide")
    except Exception:
        pass

    for fn in (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(1),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            fn()
            return
        except Exception:
            continue


def main():
    try:
        _enable_high_dpi()
        from ui import VSCodeFPGAStudio
        app = VSCodeFPGAStudio()
        app.mainloop()
    except Exception:
        import traceback
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    main()

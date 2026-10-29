# -*- coding: utf-8 -*-
"""
4x Supersampled Anti-Aliased Graphics & Pixel-Accurate Text Measurement Utilities
"""

import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageTk
from config.theme import BG_BLACK, BG_EDITOR, BORDER_HOVER, FONT_UI

_PILL_IMAGE_CACHE = {}
_CORNER_IMAGE_CACHE = {}


def truncate_to_pixel_width(text, font_spec=(FONT_UI, 9, "bold"), max_px=185):
    """Only truncate with '...' if the rendered pixel width actually exceeds max_px."""
    try:
        f = tkfont.Font(font=font_spec)
        if f.measure(text) <= max_px:
            return text
        ellipsis_w = f.measure("...")
        target_w = max_px - ellipsis_w
        lo, hi = 1, len(text)
        best = text[:1]
        while lo <= hi:
            mid = (lo + hi) // 2
            if f.measure(text[:mid]) <= target_w:
                best = text[:mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best + "..."
    except Exception:
        return text if len(text) <= 26 else text[:23] + "..."


def get_antialiased_pill_photo(w, h, bg_hex, fill_hex, outline_hex=None, radius=None):
    """Render a 100% smooth 4x-supersampled anti-aliased capsule PhotoImage using Pillow LANCZOS."""
    w = max(24, int(w))
    h = max(16, int(h))
    if radius is None:
        radius = (h - 2) // 2
    outline_hex = outline_hex or fill_hex
    key = (w, h, bg_hex, fill_hex, outline_hex, radius)
    if key in _PILL_IMAGE_CACHE:
        return _PILL_IMAGE_CACHE[key]

    scale = 4
    W, H = w * scale, h * scale
    R = radius * scale
    img = Image.new("RGBA", (W, H), bg_hex)
    draw = ImageDraw.Draw(img)
    pad = scale
    draw.rounded_rectangle(
        [pad, pad, W - pad - 1, H - pad - 1],
        radius=R,
        fill=fill_hex,
        outline=outline_hex,
        width=scale if outline_hex != fill_hex else 0,
    )
    smooth = img.resize((w, h), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(smooth)
    _PILL_IMAGE_CACHE[key] = photo
    return photo


def get_antialiased_corner_photos(radius, card_bg, outer_bg):
    """Return 4 silky-smooth 4x-supersampled corner mask PhotoImages (nw, ne, sw, se)."""
    key = (radius, card_bg, outer_bg)
    if key in _CORNER_IMAGE_CACHE:
        return _CORNER_IMAGE_CACHE[key]

    scale = 4
    S = radius * 2 * scale
    img = Image.new("RGBA", (S, S), outer_bg)
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, S - 1, S - 1], fill=card_bg)
    smooth_full = img.resize((radius * 2, radius * 2), Image.Resampling.LANCZOS)

    r = radius
    nw = ImageTk.PhotoImage(smooth_full.crop((0, 0, r, r)))
    ne = ImageTk.PhotoImage(smooth_full.crop((r, 0, r * 2, r)))
    sw = ImageTk.PhotoImage(smooth_full.crop((0, r, r, r * 2)))
    se = ImageTk.PhotoImage(smooth_full.crop((r, r, r * 2, r * 2)))
    res = {"nw": nw, "ne": ne, "sw": sw, "se": se}
    _CORNER_IMAGE_CACHE[key] = res
    return res


def add_card_rounded_corners(card_frame, card_bg=BG_EDITOR, outer_bg=BG_BLACK, radius=10):
    """Place 4 anti-aliased corner caps on a Frame so the panel card has smooth rounded corners."""
    photos = get_antialiased_corner_photos(radius, card_bg, outer_bg)
    for anchor, rx, ry in [("nw", 0.0, 0.0), ("ne", 1.0, 0.0), ("sw", 0.0, 1.0), ("se", 1.0, 1.0)]:
        lbl = tk.Label(card_frame, image=photos[anchor], bd=0, highlightthickness=0, bg=outer_bg)
        lbl._corner_img = photos[anchor]
        lbl.place(relx=rx, rely=ry, anchor=anchor, width=radius, height=radius)


def add_hover_border(widget, normal_bg, hover_bg, normal_border=None, hover_border=BORDER_HOVER, sync_children=False):
    """Add a steady subtle selection border & background highlight on hover."""
    if normal_border is not None:
        try:
            widget.configure(highlightthickness=1, highlightbackground=normal_border, highlightcolor=hover_border)
        except Exception:
            pass

    def _on_enter(e):
        try:
            widget.configure(bg=hover_bg)
            if normal_border is not None:
                widget.configure(highlightbackground=hover_border)
            if sync_children:
                for ch in widget.winfo_children():
                    if isinstance(ch, (tk.Label, tk.Frame)) and not hasattr(ch, "_corner_img"):
                        try:
                            ch.configure(bg=hover_bg)
                        except Exception:
                            pass
        except Exception:
            pass

    def _on_leave(e):
        try:
            widget.configure(bg=normal_bg)
            if normal_border is not None:
                widget.configure(highlightbackground=normal_border)
            if sync_children:
                for ch in widget.winfo_children():
                    if isinstance(ch, (tk.Label, tk.Frame)) and not hasattr(ch, "_corner_img"):
                        try:
                            ch.configure(bg=normal_bg)
                        except Exception:
                            pass
        except Exception:
            pass

    widget.bind("<Enter>", _on_enter, add="+")
    widget.bind("<Leave>", _on_leave, add="+")

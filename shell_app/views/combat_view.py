"""
combat_view.py — Player-facing combat screen rendered on the Tkinter window.

Replaces the image during an active combat encounter.
The DM calls render(snapshot, page) whenever state changes; this redraws the canvas.
"""

import tkinter as tk
import math

from .styling import *
from ..combat import Combatant, Type
from .combatant_view import CombatantView

def _page_count(total: int) -> int:
    return max(1, math.ceil(total / PAGE_SIZE))


class CombatView(tk.Frame):
    """Draws the combat tracker directly onto the Tk Frame which will be shown in the full root.
    The view starts hidden. Call show() to make it render.
    """

    def __init__(self, root: tk.Tk):
        super().__init__(root, bg=PALETTE["bg"])
        self._snapshot: dict | None = None
        self._page: int = 0          # 0-based current page index
        # Cache: (filename, row_h) -> ImageTk.PhotoImage with fade applied
        self._image_cache: dict = {}
        self.bind("<Configure>", lambda e: self._redraw())

    # ── Public API ────────────────────────────────────────────────────────────

    def render(self, snapshot: dict, page: int | None = None):
        """Update snapshot and optionally force a specific page, then redraw."""
        self._snapshot = snapshot
        if page is not None:
            self._page = page
        self._image_cache.clear()   # row_h may have changed
        self._clamp_page()
        self._redraw()

    def set_page(self, page: int):
        """Jump to a specific 0-based page and redraw."""
        self._page = page
        self._clamp_page()
        self._redraw()

    def page_next(self):
        total = len(self._ordered_entries()) if self._snapshot else 0
        pages = _page_count(total)
        self._page = (self._page + 1) % pages
        self._redraw()

    def page_prev(self):
        total = len(self._ordered_entries()) if self._snapshot else 0
        pages = _page_count(total)
        self._page = (self._page - 1) % pages
        self._redraw()

    def current_page(self) -> int:
        return self._page

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clamp_page(self):
        if self._snapshot is None:
            self._page = 0
            return
        total = len(self._ordered_entries())
        pages = _page_count(total)
        self._page = max(0, min(self._page, pages - 1))

    def _ordered_entries(self) -> list:
        """All combatants in initiative order, with pending/left_combat/unacted monsters at bottom."""
        combatants = self._snapshot["combatants"] if self._snapshot is not None else []
        def _goes_to_bottom(e: Combatant):
            return e.pending or e.left_combat or (e.type is Type.MONSTER and not e.has_acted)
        in_order = [e for e in combatants if not _goes_to_bottom(e)]
        bottom   = [e for e in combatants if _goes_to_bottom(e)]
        return in_order + bottom

    def _page_entries(self) -> list:
        entries = self._ordered_entries()
        start   = self._page * PAGE_SIZE
        return entries[start : start + PAGE_SIZE]

    # ── Redraw ────────────────────────────────────────────────────────────────

    def _redraw(self):
        if self._snapshot is None:
            return
        for item in self.winfo_children():
            if isinstance(item, tk.Widget):
              item.pack_forget()
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10:
            return
        self._draw(self._snapshot, W, H)

    def _draw(self, snap: dict, W: int, H: int):
        # c        = self.canvas
        all_entries = self._ordered_entries()
        total    = len(all_entries)
        pages    = _page_count(total)
        entries  = self._page_entries()

        if total == 0:
            # c.create_text(W // 2, H // 2,
            #     text="No combatants yet.\nUse  combat add  in the shell.",
            #     fill=PALETTE["text_muted"], font=(FONT_FAMILY, 14), justify="center")
            return

        scale    = min(W / 900, H / 600, 1.5)
        pad      = int(PADDING * scale)
        header_h = int(60 * scale)

        # Fixed row height: always the tall version (with conditions space)
        # avail_h  = H - header_h - pad * 2
        # row_h    = max(30, min(int((ROW_HEIGHT_BASE + COND_EXTRA) * scale),
        #                        avail_h // PAGE_SIZE))

        self._draw_header(snap, W, header_h, pad, scale, self._page + 1, pages)

        # y = header_h + pad
        gap = int(6 * scale)
        combatant: Combatant
        for index, combatant in enumerate(entries):
            combatant_view = CombatantView(self, combatant, self._image_cache)
            if combatant_view.is_unrevealed():
                combatant_view.draw_unrevealed_row()
            else:
                combatant_view.draw_row(snap["current_index"] == index, scale)
            combatant_view.pack(fill="x", expand=False, pady=gap)
            # y += row_h + gap

    # ── Header ────────────────────────────────────────────────────────────────

    def _draw_header(self, snap, W, header_h, pad, scale, page, pages):
        c = tk.Canvas(self, bg=PALETTE["surface"], bd=0, highlightthickness=0, width=W, height=header_h)
        c.pack()
        c.create_line(0, header_h, W, header_h, fill=PALETTE["border"], width=1)

        active    = snap["active"]
        round_num = snap["round"]
        title     = f"Round {round_num}" if active else "Combat — not started"
        c.create_text(pad, header_h // 2,
            text=title,
            fill=PALETTE["gold"],
            font=(FONT_FAMILY, scaled_font(ROUND_FONT_SIZE, scale), "bold"),
            anchor="w")

        page_text = f"Page {page} / {pages}"
        c.create_text(W - pad, header_h // 2,
            text=page_text,
            fill=PALETTE["text_muted"],
            font=(FONT_FAMILY, scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="e")

    # ── Pack helpers ──────────────────────────────────────────────────────────

    def hide(self):
        self.pack_forget()

    def show(self):
        self.pack(fill="both", expand=True)
        self._redraw()

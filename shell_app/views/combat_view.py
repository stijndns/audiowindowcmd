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
        self.view_cache: list[CombatantView] = []
        self.header = None

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
        pages = self._page_count()
        self._page = (self._page + 1) % pages
        self._redraw()

    def page_prev(self):
        pages = self._page_count()
        self._page = (self._page - 1) % pages
        self._redraw()

    def current_page(self) -> int:
        return self._page

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _page_count(self) -> int:
      return max(1, math.ceil(len(self._ordered_entries()) / MIN_PAGE_SIZE))

    def _clamp_page(self):
        if self._snapshot is None:
            self._page = 0
            return
        pages = self._page_count()
        self._page = max(0, min(self._page, pages - 1))

    def _ordered_entries(self) -> list:
        """All combatants in initiative order, with pending/left_combat/unacted monsters at bottom."""
        def _goes_to_bottom(e: Combatant):
            return e.pending or e.left_combat or (e.type is Type.MONSTER and not e.has_acted)

        combatants = self._snapshot["combatants"] if self._snapshot is not None else []
        in_order = [e for e in combatants if not _goes_to_bottom(e)]
        bottom   = [e for e in combatants if _goes_to_bottom(e)]
        return in_order + bottom

    def _page_entries(self) -> list:
        entries = self._ordered_entries()
        start   = self._page * MIN_PAGE_SIZE
        return entries[start : start + MIN_PAGE_SIZE]

    # ── Redraw ────────────────────────────────────────────────────────────────

    def _redraw(self):
        if self._snapshot is None:
            return
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10:
            return
        self._draw(self._snapshot, W, H)

    def _draw(self, snap: dict, W: int, H: int):
        all_entries = self._ordered_entries()
        total    = len(all_entries)
        pages    = self._page_count()
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
        #                        avail_h // MIN_PAGE_SIZE))

        self._draw_header(snap, W, header_h, pad, scale, self._page + 1, pages)

        gap = int(6 * scale)
        combatant: Combatant
        for index, combatant in enumerate(entries, 0):
            if len(self.view_cache) <= index:
                combatant_view = CombatantView(self, combatant, self._image_cache)
                self.view_cache.append(combatant_view)
                combatant_view.pack(fill="x", expand=False, pady= ((gap * 2 if index == 0 else gap), 2), padx=combatant_view.padding)
            else:
                combatant_view = self.view_cache[index]
                if not combatant_view.winfo_ismapped():
                    combatant_view.pack(fill="x", expand=False, pady=((gap * 2 if index == 0 else gap), 2), padx=combatant_view.padding)
                combatant_view.delete('all')
                combatant_view.combatant = combatant

            if combatant_view.is_unrevealed():
                combatant_view.draw_unrevealed_row()
            else:
                combatant_view.draw_row(snap["current_index"] % MIN_PAGE_SIZE== index)
        for index in range(len(entries), len(self.view_cache)):
            self.view_cache[index].pack_forget()


    # ── Header ────────────────────────────────────────────────────────────────

    def _draw_header(self, snap, W, header_h, pad, scale, page, pages):
        c: tk.Canvas
        if self.header is None:
            c = tk.Canvas(self, bg=PALETTE["surface"], bd=0, highlightthickness=0, height=header_h)
            self.header = c
            c.pack(fill="x", expand=False)
        else:
            c = self.header
            c.delete('all')
            c.config(height=header_h)
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

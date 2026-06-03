"""
combat_view.py — Player-facing combat screen rendered on the Tkinter window.

Replaces the image during an active combat encounter.
The DM calls render(snapshot, page) whenever state changes; this redraws the canvas.
"""

import tkinter as tk
import math
import os
from PIL import Image, ImageTk

# ── Colour palette ────────────────────────────────────────────────────────────
PALETTE = {
    "bg":            "#0d1117",
    "surface":       "#161b22",
    "surface2":      "#21262d",
    "border":        "#30363d",
    "text_primary":  "#e6edf3",
    "text_muted":    "#8b949e",
    "text_dim":      "#484f58",
    "gold":          "#d4a843",
    "current_glow":  "#f0c040",
    "pc_accent":     "#4493f8",
    "npc_accent":    "#bc8cff",
    "monster_accent":"#ff7b72",
    "bar_green":     "#3fb950",
    "bar_yellow":    "#d29922",
    "bar_orange":    "#e3652b",
    "bar_red":       "#f85149",
    "bar_dead":      "#30363d",
    "bar_track":     "#21262d",
    "active_bg":     "#1c2128",
    "active_border": "#d4a843",
}

BAR_COLORS = {
    "green":  PALETTE["bar_green"],
    "yellow": PALETTE["bar_yellow"],
    "orange": PALETTE["bar_orange"],
    "red":    PALETTE["bar_red"],
    "dead":   PALETTE["bar_dead"],
}

TYPE_ACCENT = {
    "pc":      PALETTE["pc_accent"],
    "npc":     PALETTE["npc_accent"],
    "monster": PALETTE["monster_accent"],
}

STATE_LABELS = {
    "green":  "Healthy",
    "yellow": "Bloodied",
    "orange": "Wounded",
    "red":    "Near Death",
    "dead":   "Defeated",
}

# ── Layout constants ──────────────────────────────────────────────────────────
FONT_FAMILY     = "Consolas"
PADDING         = 24
PAGE_SIZE       = 6             # combatants per page
INITIATIVE_W    = 52
ROUND_FONT_SIZE = 22
NAME_FONT_SIZE  = 15
STAT_FONT_SIZE  = 12
MUTED_FONT_SIZE = 11
COND_EXTRA      = 18            # extra px (pre-scale) reserved for conditions line


def _scaled_font(base: int, scale: float) -> int:
    return max(9, int(base * scale))


def _page_count(total: int) -> int:
    return max(1, math.ceil(total / PAGE_SIZE))


class CombatView(tk.Frame):
    """Draws the combat tracker directly onto the existing Tk root."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.canvas = tk.Canvas(self, bg=PALETTE["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._snapshot: dict | None = None
        self._page: int = 0          # 0-based current page index
        # Cache: (filename, row_h) -> ImageTk.PhotoImage with fade applied
        self._image_cache: dict = {}
        root.bind("<Configure>", lambda e: self._redraw(), add='+')

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
        combatants = self._snapshot["combatants"]
        def _goes_to_bottom(e):
            return (e.get("pending", False)
                    or e.get("left_combat", False)
                    or (e["type"] == "monster" and not e.get("has_acted", True)))
        in_order = [e for e in combatants if not _goes_to_bottom(e)]
        bottom   = [e for e in combatants if _goes_to_bottom(e)]
        return in_order + bottom

    @staticmethod
    def _is_greyed(e) -> bool:
        """Return True if this entry should be rendered via _draw_unrevealed_row."""
        return (e.get("pending", False)
                or e.get("left_combat", False)
                or e.get("status", "active") in ("dead", "incapacitated")
                or (e["type"] == "monster" and not e.get("has_acted", True)))

    def _page_entries(self) -> list:
        entries = self._ordered_entries()
        start   = self._page * PAGE_SIZE
        return entries[start : start + PAGE_SIZE]

    # ── Redraw ────────────────────────────────────────────────────────────────

    def _redraw(self):
        if self._snapshot is None:
            return
        self.canvas.delete("all")
        self._live_images = []   # release previous frame's image refs
        W = self.canvas.winfo_width()
        H = self.canvas.winfo_height()
        if W < 10 or H < 10:
            return
        self._draw(self._snapshot, W, H)

    def _draw(self, snap: dict, W: int, H: int):
        c        = self.canvas
        all_entries = self._ordered_entries()
        total    = len(all_entries)
        pages    = _page_count(total)
        entries  = self._page_entries()

        if total == 0:
            c.create_text(W // 2, H // 2,
                text="No combatants yet.\nUse  combat add  in the shell.",
                fill=PALETTE["text_muted"], font=(FONT_FAMILY, 14), justify="center")
            return

        scale    = min(W / 900, H / 600, 1.5)
        pad      = int(PADDING * scale)
        header_h = int(60 * scale)

        # Fixed row height: always the tall version (with conditions space)
        avail_h  = H - header_h - pad * 2
        row_h    = max(30, min(int((ROW_HEIGHT_BASE + COND_EXTRA) * scale),
                               avail_h // PAGE_SIZE))

        self._draw_header(c, snap, W, header_h, pad, scale, self._page + 1, pages)

        y = header_h + pad
        gap = int(6 * scale)
        for entry in entries:
            if self._is_greyed(entry):
                self._draw_unrevealed_row(c, entry, pad, y, W, row_h, scale)
            else:
                self._draw_row(c, entry, pad, y, W, row_h, scale)
            y += row_h + gap

    # ── Header ────────────────────────────────────────────────────────────────

    def _draw_header(self, c, snap, W, header_h, pad, scale, page, pages):
        c.create_rectangle(0, 0, W, header_h, fill=PALETTE["surface"], outline="")
        c.create_line(0, header_h, W, header_h, fill=PALETTE["border"], width=1)

        active    = snap["active"]
        round_num = snap["round"]
        title     = f"Round {round_num}" if active else "Combat — not started"
        c.create_text(pad, header_h // 2,
            text=title,
            fill=PALETTE["gold"],
            font=(FONT_FAMILY, _scaled_font(ROUND_FONT_SIZE, scale), "bold"),
            anchor="w")

        page_text = f"Page {page} / {pages}"
        c.create_text(W - pad, header_h // 2,
            text=page_text,
            fill=PALETTE["text_muted"],
            font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="e")

    # ── Image loading ─────────────────────────────────────────────────────────

    def _prepare_combatant_image(self, filename: str, row_h: int) -> ImageTk.PhotoImage | None:
        """Load, resize, fade and cache a combatant image. Returns None on failure."""
        cache_key = (filename, row_h)
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        path = os.path.join("assets", "images", "combatants", filename)
        if not os.path.exists(path):
            return None

        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None

        # Scale to row height, preserving aspect ratio
        orig_w, orig_h = img.size
        new_w = max(1, int(orig_w * row_h / orig_h))
        img = img.resize((new_w, row_h), Image.LANCZOS)

        # Apply horizontal fade: right=opaque (200/255), left=transparent
        # Use a 1-pixel-tall gradient then scale up — fast and avoids pixel loops
        r, g, b, a = img.split()
        # Build gradient as raw bytes: left=0, right=200
        gradient_row = bytes(int(200 * x / new_w) for x in range(new_w))
        gradient_data = gradient_row * row_h
        fade = Image.frombytes("L", (new_w, row_h), gradient_data)
        # Multiply existing alpha channel with fade mask using Pillow multiply
        from PIL import ImageChops
        combined = ImageChops.multiply(a, fade)
        img.putalpha(combined)

        tk_img = ImageTk.PhotoImage(img)
        self._image_cache[cache_key] = tk_img
        return tk_img

    # ── Revealed row ──────────────────────────────────────────────────────────

    def _draw_row(self, c, entry, pad, y, W, row_h, scale):
        is_current = entry["is_current_turn"]
        status     = entry.get("status", "active")
        is_dead    = status in ("dead", "incapacitated")
        is_dying   = status == "dying"
        is_dimmed  = is_dead or is_dying   # greyed colours but may still show turn indicator
        ctype      = entry["type"]
        accent     = TYPE_ACCENT.get(ctype, PALETTE["text_muted"])

        init_col_w = int(INITIATIVE_W * scale)
        x_left     = pad + init_col_w
        x_right    = W - pad
        inner_pad  = int(12 * scale)
        text_x     = x_left + inner_pad + 6

        # Initiative column
        init_color = (PALETTE["current_glow"] if is_current else
                      PALETTE["text_dim"] if is_dimmed else PALETTE["text_primary"])
        c.create_text(pad + init_col_w // 2, y + row_h // 2,
            text=str(entry["initiative"]),
            fill=init_color,
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center")

        # Row background
        bg_col     = PALETTE["active_bg"] if is_current else PALETTE["bg"]
        border_col = PALETTE["active_border"] if is_current else PALETTE["border"]
        border_w   = 2 if is_current else 1
        c.create_rectangle(x_left, y, x_right, y + row_h,
            fill=bg_col, outline=border_col, width=border_w)

        # Combatant image (anchored top-right of row box, drawn before text)
        img_filename = entry.get("image")
        if img_filename:
            tk_img = self._prepare_combatant_image(img_filename, row_h)
            if tk_img:
                c.create_image(x_right, y, image=tk_img, anchor="ne")
                # Keep reference to prevent garbage collection
                if not hasattr(self, "_live_images"):
                    self._live_images = []
                self._live_images.append(tk_img)

        # Accent bar
        c.create_rectangle(x_left, y, x_left + 4, y + row_h,
            fill=accent if not is_dimmed else PALETTE["bar_dead"], outline="")

        # Layout: divide row into 4 vertical zones
        # name_y: name line (shifted up)
        # badge_y: type badge
        # res_y: resources line
        # cond_y: conditions line (bottom)
        quarter = row_h // 4
        name_y  = y + quarter - int(4 * scale)
        badge_y = y + quarter * 2 - int(2 * scale)
        res_y   = y + quarter * 3 - int(2 * scale)
        cond_y  = y + row_h - int(10 * scale)

        # Name
        name_color = (PALETTE["text_dim"] if is_dimmed and not is_current else
                      PALETTE["current_glow"] if is_current else PALETTE["text_primary"])
        if is_dying:
            status_suffix = "  [DYING]"
        else:
            status_suffix = ""
        c.create_text(text_x, name_y,
            text=entry["name"].replace("_", " ") + status_suffix,
            fill=name_color,
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="w")

        # Type badge
        c.create_text(text_x, badge_y,
            text=ctype.upper(),
            fill=accent if not is_dimmed else PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w")

        # HP / status (aligned to name_y on right side)
        if ctype == "pc":
            hp_str   = f"{entry['hp_current']}/{entry['hp_max']} HP"
            hp_color = PALETTE["text_primary"] if not is_dimmed else PALETTE["text_dim"]
            c.create_text(x_right - inner_pad, name_y,
                text=hp_str, fill=hp_color,
                font=(FONT_FAMILY, _scaled_font(STAT_FONT_SIZE, scale), "bold"),
                anchor="e")
        else:
            state_text  = STATE_LABELS.get(entry["hp_bar"], "")
            fill_color  = BAR_COLORS.get(entry["hp_bar"], PALETTE["bar_dead"])
            label_color = fill_color if not is_dimmed else PALETTE["text_dim"]
            c.create_text(x_right - inner_pad, name_y,
                text=state_text, fill=label_color,
                font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
                anchor="e")

        # Resources line: reaction and legendary actions
        res_parts = []
        reaction = entry.get("reaction")
        if reaction is not None:
            res_parts.append(f"Reaction {reaction['current']}/{reaction['maximum']}")
        leg = entry.get("legendary_actions")
        if leg is not None:
            res_parts.append(f"Legendary Actions {leg['current']}/{leg['maximum']}")
        # Note: "legendary_actions" key → display as "Legendary Actions" (underscore → space, title case)
        if res_parts:
            res_color = PALETTE["text_dim"] if is_dimmed else PALETTE["text_muted"]
            c.create_text(text_x, res_y,
                text="  ·  ".join(res_parts),
                fill=res_color,
                font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
                anchor="w")

        # Conditions line (always reserved at bottom of row)
        conditions = entry.get("conditions", [])
        if conditions:
            c.create_text(text_x, cond_y,
                text="  ·  ".join(conditions), fill=PALETTE["gold"],
                font=(FONT_FAMILY, _scaled_font(10, scale)),
                anchor="w")

    # ── Unrevealed / pending row ──────────────────────────────────────────────

    def _draw_unrevealed_row(self, c, entry, pad, y, W, row_h, scale):
        init_col_w = int(INITIATIVE_W * scale)
        x_left     = pad + init_col_w
        x_right    = W - pad
        inner_pad  = int(12 * scale)
        text_x     = x_left + inner_pad + 6

        # Initiative: ? for unacted monsters, real value for pending/left_combat
        non_mystery = (entry.get("left_combat", False)
                       or entry.get("status", "active") != "active")
        init_text = "?" if (not entry.get("has_acted", True) and not non_mystery) else str(entry["initiative"])
        c.create_text(pad + init_col_w // 2, y + row_h // 2,
            text=init_text, fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center")

        # Row background
        c.create_rectangle(x_left, y, x_right, y + row_h,
            fill=PALETTE["bg"], outline=PALETTE["border"], width=1)

        # Greyed accent bar
        c.create_rectangle(x_left, y, x_left + 4, y + row_h,
            fill=PALETTE["bar_dead"], outline="")

        # Name + status tag
        display_name = entry["name"].replace("_", " ")
        entry_status = entry.get("status", "active")
        if entry_status == "dead":
            display_name += "  [DEAD]"
        elif entry_status == "dying":
            display_name += "  [DYING]"
        elif entry_status == "incapacitated":
            display_name += "  [INCAPACITATED]"
        elif entry.get("left_combat", False):
            display_name += "  [LEFT COMBAT]"
        elif entry.get("pending", False):
            display_name += "  [PENDING]"
        c.create_text(text_x, y + row_h // 2 - int(9 * scale),
            text=display_name, fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="w")

        # Type badge
        c.create_text(text_x, y + row_h // 2 + int(8 * scale),
            text=entry["type"].upper(),
            fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w")

    # ── Pack helpers ──────────────────────────────────────────────────────────

    def hide(self):
        self.pack_forget()

    def show(self):
        self.pack(fill="both", expand=True)
        self._redraw()


# Row height base (without conditions) — used in _draw
ROW_HEIGHT_BASE = 64
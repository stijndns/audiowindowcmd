"""
combat_view.py — Player-facing combat screen rendered on the Tkinter window.

Replaces the image during an active combat encounter.
The DM calls render(snapshot) whenever state changes; this redraws the canvas.
"""

import tkinter as tk


# ── Colour palette ────────────────────────────────────────────────────────────
PALETTE = {
    "bg":           "#0d1117",   # near-black parchment
    "surface":      "#161b22",
    "surface2":     "#21262d",
    "border":       "#30363d",
    "text_primary": "#e6edf3",
    "text_muted":   "#8b949e",
    "text_dim":     "#484f58",
    "gold":         "#d4a843",   # initiative / headings
    "current_glow": "#f0c040",
    "pc_accent":    "#4493f8",   # blue for player characters
    "npc_accent":   "#bc8cff",   # purple for NPCs
    "monster_accent":"#ff7b72",  # red-orange for monsters
    # HP bar states
    "bar_green":    "#3fb950",
    "bar_yellow":   "#d29922",
    "bar_orange":   "#e3652b",
    "bar_red":      "#f85149",
    "bar_dead":     "#30363d",
    "bar_track":    "#21262d",
    # Active turn highlight
    "active_bg":    "#1c2128",
    "active_border":"#d4a843",
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

# ── Layout constants (will be scaled to window size) ─────────────────────────
FONT_FAMILY  = "Consolas"   # monospaced fantasy feel; fallback handled by Tk
PADDING      = 24
ROW_HEIGHT   = 64           # base row height; shrinks when many combatants
MIN_ROW_H    = 38
BAR_H        = 10
INITIATIVE_W = 52
HP_COL_W     = 80           # width reserved for HP text on right
ROUND_FONT_SIZE = 22
NAME_FONT_SIZE  = 15
STAT_FONT_SIZE  = 12
MUTED_FONT_SIZE = 11


def _scaled_font(base: int, scale: float) -> int:
    return max(9, int(base * scale))


class CombatView:
    """Draws the combat tracker directly onto the existing Tk root."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.canvas = tk.Canvas(
            root,
            bg=PALETTE["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self._snapshot: dict | None = None

        self.root.bind("<Configure>", lambda e: self._redraw())

    def render(self, snapshot: dict):
        """Called by the main thread (via after()) when combat state changes."""
        self._snapshot = snapshot
        self._redraw()

    def _redraw(self):
        if self._snapshot is None:
            return
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        self._draw(self._snapshot, w, h)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, snap: dict, W: int, H: int):
        c = self.canvas
        combatants = snap["combatants"]
        n = len(combatants)
        if n == 0:
            c.create_text(
                W // 2, H // 2,
                text="No combatants yet.\nUse  combat add  in the shell.",
                fill=PALETTE["text_muted"],
                font=(FONT_FAMILY, 14),
                justify="center",
            )
            return

        # Scale factor for very large or very small windows
        scale = min(W / 900, H / 600, 1.5)

        pad = int(PADDING * scale)
        header_h = int(60 * scale)

        # Available height for the roster
        avail_h = H - header_h - pad * 2
        row_h = max(MIN_ROW_H, min(int(ROW_HEIGHT * scale), avail_h // n))

        # ── Header ────────────────────────────────────────────────────────────
        self._draw_header(c, snap, W, header_h, pad, scale)

        # ── Combatant rows ────────────────────────────────────────────────────
        COND_EXTRA = int(18 * scale)   # extra height reserved for conditions line
        y = header_h + pad

        revealed   = [e for e in combatants if e["type"] != "monster" or e.get("has_acted", True)]
        unrevealed = [e for e in combatants if e["type"] == "monster" and not e.get("has_acted", True)]

        for entry in revealed:
            has_conditions = bool(entry.get("conditions"))
            effective_row_h = row_h + (COND_EXTRA if has_conditions else 0)
            self._draw_row(c, entry, pad, y, W, effective_row_h, scale)
            y += effective_row_h + int(6 * scale)

        for entry in unrevealed:
            self._draw_unrevealed_row(c, entry, pad, y, W, row_h, scale)
            y += row_h + int(6 * scale)

    def _draw_header(self, c, snap, W, header_h, pad, scale):
        """Draws the round counter and column labels."""
        round_num = snap["round"]
        active    = snap["active"]

        # Background strip
        c.create_rectangle(0, 0, W, header_h, fill=PALETTE["surface"], outline="")
        c.create_line(0, header_h, W, header_h, fill=PALETTE["border"], width=1)

        # Round text
        title = f"Round {round_num}" if active else "Combat — not started"
        c.create_text(
            pad, header_h // 2,
            text=title,
            fill=PALETTE["gold"],
            font=(FONT_FAMILY, _scaled_font(ROUND_FONT_SIZE, scale), "bold"),
            anchor="w",
        )



    def _draw_row(self, c, entry: dict, pad: int, y: int, W: int, row_h: int, scale: float):
        """Draws a single combatant row."""
        is_current = entry["is_current_turn"]
        is_dead    = not entry["is_active"]
        ctype      = entry["type"]
        accent     = TYPE_ACCENT.get(ctype, PALETTE["text_muted"])

        # ── Initiative column (outside row box, left of accent bar) ──────────
        init_col_w = int(INITIATIVE_W * scale)
        x_left  = pad + init_col_w
        x_right = W - pad

        init_color = PALETTE["current_glow"] if is_current else (
            PALETTE["text_dim"] if is_dead else PALETTE["text_primary"]
        )
        c.create_text(
            pad + init_col_w // 2, y + row_h // 2,
            text=str(entry["initiative"]),
            fill=init_color,
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center",
        )

        # ── Row background ────────────────────────────────────────────────────
        bg_col     = PALETTE["active_bg"] if is_current else PALETTE["bg"]
        border_col = PALETTE["active_border"] if is_current else PALETTE["border"]
        border_w   = 2 if is_current else 1

        c.create_rectangle(
            x_left, y,
            x_right, y + row_h,
            fill=bg_col,
            outline=border_col,
            width=border_w,
        )

        # ── Accent bar on left edge of row box ────────────────────────────────
        c.create_rectangle(
            x_left, y,
            x_left + 4, y + row_h,
            fill=accent if not is_dead else PALETTE["bar_dead"],
            outline="",
        )

        inner_pad = int(12 * scale)
        text_x = x_left + inner_pad + 6

        # ── Name ──────────────────────────────────────────────────────────────
        name_color = PALETTE["text_muted"] if is_dead else (
            PALETTE["current_glow"] if is_current else PALETTE["text_primary"]
        )
        name_font_size = _scaled_font(NAME_FONT_SIZE, scale)
        dead_suffix = "  [DEAD]" if is_dead else ""

        c.create_text(
            text_x, y + row_h // 2 - int(9 * scale),
            text=entry["name"].replace("_", " ") + dead_suffix,
            fill=name_color,
            font=(FONT_FAMILY, name_font_size, "bold"),
            anchor="w",
        )

        # ── Type badge ────────────────────────────────────────────────────────
        badge_text = ctype.upper()
        c.create_text(
            text_x, y + row_h // 2 + int(8 * scale),
            text=badge_text,
            fill=accent if not is_dead else PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w",
        )

        # ── HP bar (NPC / monster) or HP numbers (PC) ───────────────────────
        if ctype == "pc":
            # Show exact HP for player characters
            hp_str = f"{entry['hp_current']}/{entry['hp_max']} HP"
            hp_color = PALETTE["text_primary"] if not is_dead else PALETTE["text_dim"]

            c.create_text(
                x_right - inner_pad, y + row_h // 2 - int(9 * scale),
                text=hp_str,
                fill=hp_color,
                font=(FONT_FAMILY, _scaled_font(STAT_FONT_SIZE, scale), "bold"),
                anchor="e",
            )
        else:
            # Draw HP bar for monsters/NPCs
            bar_w      = int(min(200 * scale, (W - 2 * pad) * 0.28))
            bar_right  = x_right - inner_pad
            bar_left   = bar_right - bar_w
            bar_top    = y + row_h // 2 - int(BAR_H * scale * 0.5) - int(6 * scale)
            bar_bottom = bar_top + int(BAR_H * scale)

            # Track
            c.create_rectangle(
                bar_left, bar_top, bar_right, bar_bottom,
                fill=PALETTE["bar_track"], outline=PALETTE["border"], width=1,
            )
            # Fill
            fill_color = BAR_COLORS.get(entry["hp_bar"], PALETTE["bar_dead"])
            fill_w = int(bar_w * entry["hp_fraction"])
            if fill_w > 0:
                c.create_rectangle(
                    bar_left, bar_top,
                    bar_left + fill_w, bar_bottom,
                    fill=fill_color, outline="",
                )

            # State label below bar
            state_labels = {
                "green":  "Healthy",
                "yellow": "Bloodied",
                "orange": "Critical",
                "red":    "Near Death",
                "dead":   "Defeated",
            }
            state_text = state_labels.get(entry["hp_bar"], "")
            c.create_text(
                (bar_left + bar_right) // 2,
                bar_top + int(BAR_H * scale) + int(5 * scale),
                text=state_text,
                fill=fill_color if not is_dead else PALETTE["text_dim"],
                font=(FONT_FAMILY, _scaled_font(10, scale)),
                anchor="n",
            )



        # ── Conditions line ───────────────────────────────────────────────────
        conditions = entry.get("conditions", [])
        if conditions:
            cond_text = "  ·  ".join(conditions)
            cond_y = y + row_h - int(10 * scale)
            c.create_text(
                text_x, cond_y,
                text=cond_text,
                fill=PALETTE["gold"],
                font=(FONT_FAMILY, _scaled_font(10, scale)),
                anchor="w",
            )

    def _draw_unrevealed_row(self, c, entry: dict, pad: int, y: int, W: int, row_h: int, scale: float):
        """Draws a greyed-out placeholder row for a monster that hasn't acted yet."""
        init_col_w = int(INITIATIVE_W * scale)
        x_left  = pad + init_col_w
        x_right = W - pad
        inner_pad = int(12 * scale)

        # Question mark in initiative column
        c.create_text(
            pad + init_col_w // 2, y + row_h // 2,
            text="?",
            fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center",
        )

        # Row background
        c.create_rectangle(
            x_left, y, x_right, y + row_h,
            fill=PALETTE["bg"],
            outline=PALETTE["border"],
            width=1,
        )

        # Greyed-out accent bar
        c.create_rectangle(
            x_left, y, x_left + 4, y + row_h,
            fill=PALETTE["bar_dead"],
            outline="",
        )

        text_x = x_left + inner_pad + 6

        # Greyed-out name
        c.create_text(
            text_x, y + row_h // 2 - int(9 * scale),
            text=entry["name"].replace("_", " "),
            fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="w",
        )

        # Greyed-out type badge
        c.create_text(
            text_x, y + row_h // 2 + int(8 * scale),
            text="MONSTER",
            fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, _scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w",
        )

    def hide(self):
        """Called when leaving combat mode."""
        self.canvas.pack_forget()

    def show(self):
        """Called when entering combat mode."""
        self.canvas.pack(fill="both", expand=True)
        self._redraw()
import os
import tkinter as tk

from PIL import ImageTk, Image

from .combat_view import ROW_HEIGHT_BASE
from .styling import *
from ..combat import Type, Combatant, Status

INITIATIVE_W    = 52
class CombatantView(tk.Canvas):
    def __init__(self, parent, combatant: Combatant, img_cache: dict):
        super().__init__(parent, bg=PALETTE["bg"], highlightthickness=0, bd=0)
        #TODO: fix all sizing/rendering
        self.combatant = combatant
        self._image_cache = img_cache

    def is_unrevealed(self) -> bool:
        """Return True if this self.combatant should be rendered via _draw_unrevealed_row."""
        return (self.combatant.pending
                or self.combatant.left_combat
                or self.combatant.status in ("dead", "incapacitated")
                or (self.combatant.type is Type.MONSTER and not self.combatant.has_acted))

    # ── Revealed row ──────────────────────────────────────────────────────────

    def draw_row(self, is_current: bool, scale):
        # is_current = self.combatant.is_current_turn
        status     = self.combatant.status
        is_dead    = status in (Status.DEAD, Status.INCAPACITATED)
        is_dying   = status == Status.DYING
        is_dimmed  = is_dead or is_dying   # greyed colours but may still show turn indicator
        accent     = TYPE_ACCENT.get(self.combatant.type, PALETTE["text_muted"])

        pad = PADDING
        W = self.master.winfo_width()
        # scale=1
        row_h = ROW_HEIGHT_BASE
        y = 0

        init_col_w = int(INITIATIVE_W * scale)
        x_left     = pad + init_col_w
        x_right    = W - pad
        inner_pad  = int(12 * scale)
        text_x     = x_left + inner_pad + 6

        # Initiative column
        init_color = (PALETTE["current_glow"] if is_current else
                      PALETTE["text_dim"] if is_dimmed else PALETTE["text_primary"])
        self.create_text(pad + init_col_w // 2, y + row_h // 2,
            text=str(self.combatant.initiative),
            fill=init_color,
            font=(FONT_FAMILY, scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center")

        # Row background
        bg_col     = PALETTE["active_bg"] if is_current else PALETTE["bg"]
        border_col = PALETTE["active_border"] if is_current else PALETTE["border"]
        border_w   = 2 if is_current else 1
        self.create_rectangle(x_left, y, x_right, y + row_h,
            fill=bg_col, outline=border_col, width=border_w)

        # Combatant image (anchored top-right of row box, drawn before text)
        img_filename = self.combatant.image
        if img_filename:
            tk_img = self._prepare_combatant_image(img_filename, row_h)
            if tk_img:
                self.create_image(x_right, y, image=tk_img, anchor="ne")

        # Accent bar
        self.create_rectangle(x_left, y, x_left + 4, y + row_h,
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
        self.create_text(text_x, name_y,
            text=self.combatant.name.replace("_", " ") + status_suffix,
            fill=name_color,
            font=(FONT_FAMILY, scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="w")

        # Type badge
        self.create_text(text_x, badge_y,
            text=self.combatant.type.value.upper(),
            fill=accent if not is_dimmed else PALETTE["text_dim"],
            font=(FONT_FAMILY, scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w")

        # HP / status (aligned to name_y on right side)
        if self.combatant.type is Type.PC:
            hp_str   = f"{self.combatant.hp_current}/{self.combatant.hp_max} HP"
            hp_color = PALETTE["text_primary"] if not is_dimmed else PALETTE["text_dim"]
            self.create_text(x_right - inner_pad, name_y,
                text=hp_str, fill=hp_color,
                font=(FONT_FAMILY, scaled_font(STAT_FONT_SIZE, scale), "bold"),
                anchor="e")
        else:
            state_text  = STATE_LABELS.get(self.combatant.hp_bar_state, "")
            fill_color  = BAR_COLORS.get(self.combatant.hp_bar_state, PALETTE["bar_dead"])
            label_color = fill_color if not is_dimmed else PALETTE["text_dim"]
            self.create_text(x_right - inner_pad, name_y,
                text=state_text, fill=label_color,
                font=(FONT_FAMILY, scaled_font(NAME_FONT_SIZE, scale), "bold"),
                anchor="e")

        # Resources line: reaction and legendary actions
        res_parts = []
        reaction = self.combatant.resources.get("reaction", None)
        if reaction is not None:
            res_parts.append(f"Reaction {reaction.current}/{reaction.maximum}")
        leg = self.combatant.resources.get("legendary_actions", None)
        if leg is not None:
            res_parts.append(f"Legendary Actions {leg.current}/{leg.maximum}")
        # Note: "legendary_actions" key → display as "Legendary Actions" (underscore → space, title case)
        if res_parts:
            res_color = PALETTE["text_dim"] if is_dimmed else PALETTE["text_muted"]
            self.create_text(text_x, res_y,
                text="  ·  ".join(res_parts),
                fill=res_color,
                font=(FONT_FAMILY, scaled_font(MUTED_FONT_SIZE, scale)),
                anchor="w")

        # Conditions line (always reserved at bottom of row)
        conditions = self.combatant.conditions
        if conditions:
            self.create_text(text_x, cond_y,
                text="  ·  ".join(conditions), fill=PALETTE["gold"],
                font=(FONT_FAMILY, scaled_font(10, scale)),
                anchor="w")

    # ── Unrevealed / pending row ──────────────────────────────────────────────

    def draw_unrevealed_row(self):
        pad = PADDING * 2
        W = self.master.winfo_width()
        scale=2
        row_h = ROW_HEIGHT_BASE * 2
        y = pad

        init_col_w = int(INITIATIVE_W * scale) # round, ceil or floor?
        x_left     = pad + init_col_w
        x_right    = W - pad
        inner_pad  = int(12 * scale)
        text_x     = x_left + inner_pad + 6

        # Initiative: ? for unacted monsters, real value for pending/left_combat
        non_mystery = (self.combatant.left_combat
                       or self.combatant.status is not Combatant.Status.ACTIVE)
        init_text = "?" if (not self.combatant.has_acted and not non_mystery) else str(self.combatant.initiative)
        self.create_text(pad + init_col_w // 2, y + row_h // 2,
            text=init_text, fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="center")

        # Row background
        self.create_rectangle(x_left, y, x_right, y + row_h,
            fill=PALETTE["bg"], outline=PALETTE["border"], width=1)

        # Greyed accent bar
        self.create_rectangle(x_left, y, x_left + 4, y + row_h,
            fill=PALETTE["bar_dead"], outline="")

        # Name + status tag
        display_name = self.combatant.name.replace("_", " ")
        if self.combatant.status is Status.DEAD:
            display_name += "  [DEAD]"
        elif self.combatant.status is Status.DYING:
            display_name += "  [DYING]"
        elif self.combatant.status is Status.INCAPACITATED:
            display_name += "  [INCAPACITATED]"
        elif self.combatant.left_combat:
            display_name += "  [LEFT COMBAT]"
        elif self.combatant.pending:
            display_name += "  [PENDING]"
        self.create_text(text_x, y + row_h // 2 - int(9 * scale),
            text=display_name, fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, scaled_font(NAME_FONT_SIZE, scale), "bold"),
            anchor="w")

        # Type badge
        self.create_text(text_x, y + row_h // 2 + int(8 * scale),
            text=self.combatant.type.value.upper(),
            fill=PALETTE["text_dim"],
            font=(FONT_FAMILY, scaled_font(MUTED_FONT_SIZE, scale)),
            anchor="w")
        
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
"""
battlemap_view.py — The battlemap display.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from PIL import Image, ImageTk

from ....core.paths import IMAGES_DIR

class BattleMapView:
    """Displays one image, scaled to fit its frame while preserving aspect."""

    def __init__(self, parent: tk.Widget):
        self.label = tk.Label(parent, bg="black")
        self.label.pack(fill="both", expand=True)

        self._original: Optional[Image.Image] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._filename: Optional[str] = None

        # Re-render when the frame itself changes size (the window was
        # resized), not only when a new image is shown.
        self.label.bind("<Configure>", lambda e: self.rescale())

    # ── Loading ───────────────────────────────────────────────────────────

    def load(self, filename: str) -> bool:
        """Load an image by name, relative to assets/images."""
        if not filename:
            self._original = None
            self._photo = None
            self._filename = None
            return True

        path = IMAGES_DIR / filename
        if not path.exists():
            print(f"[!] File not found: {path}")
            return False
        try:
            self._original = Image.open(path)
            self._filename = filename
            print(f"[+] Loaded image: {filename}")
            return True
        except Exception as exc:
            print(f"[!] Error loading image: {exc}")
            return False

    # ── Rendering ─────────────────────────────────────────────────────────

    def render(self, snapshot: dict) -> None:
        """Render from a feature snapshot. Loads the image if it changed."""
        filename = snapshot.get("bgimage")
        if filename != self._filename:
            if not self.load(filename):
                return
        self.rescale()

    def rescale(self) -> None:
        """Redraw the current image letterboxed into the frame."""
        if self._original is None:
            self.label.config(image=None)
            return

        width = self.label.winfo_width()
        height = self.label.winfo_height()
        # During construction the widget reports 1x1; nothing useful to draw.
        if width <= 1 or height <= 1:
            return

        img = self._original.copy()
        img_w, img_h = img.size
        scale = min(width / img_w, height / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        img = img.resize((new_w, new_h), Image.LANCZOS)  # type: ignore[attr-defined]
        # Keep a reference: Tk does not own PhotoImage data, so dropping the
        # last Python reference would blank the label.
        self._photo = ImageTk.PhotoImage(img)
        self.label.config(image=self._photo)

    def clear(self) -> None:
        self._original = None
        self._photo = None
        self._filename = None
        self.label.config(image="")

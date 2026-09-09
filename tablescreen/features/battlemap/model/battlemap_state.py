"""
battlemapstate.py — Battlemap state model for Tablescreen.
"""

from typing import Optional
from copy import deepcopy

class BattleMapState:
    """Manages the full battlemap."""

    def __init__(self):
        self.bgimage: str = None

    def snapshot(self) -> dict:
        """Return a dict for the battlemap state."""
        return {"bgimage": self.bgimage}

    def load_map_image(self, filename: str) -> None:
        self.bgimage = filename

    def clear_map_image(self) -> None:
        self.bgimage = None

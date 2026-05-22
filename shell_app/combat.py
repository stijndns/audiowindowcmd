"""
combat.py — Combat state model for AudioWindowCMD.

Tracks combatants, turn order, HP, and arbitrary named resources.
No rule-checking; purely a bookkeeping layer.
"""

from dataclasses import dataclass, field
from typing import Optional
import math


# ── HP bar thresholds (fraction of max HP) ──────────────────────────────────
BAR_GREEN  = 0.75   # > 75 %  → green
BAR_YELLOW = 0.50   # 50–75 % → yellow
BAR_ORANGE = 0.25   # 25–50 % → orange
BAR_RED    = 0.01   # 1–24 %  → red
# ≤ 0 %             → dead / empty


def hp_bar_state(current: int, maximum: int) -> str:
    """Return one of: 'green', 'yellow', 'orange', 'red', 'dead'."""
    if maximum <= 0:
        return "dead"
    ratio = current / maximum
    if ratio > BAR_GREEN:
        return "green"
    if ratio > BAR_YELLOW:
        return "yellow"
    if ratio > BAR_ORANGE:
        return "orange"
    if ratio > 0:
        return "red"
    return "dead"


@dataclass
class Resource:
    """A named, finite resource (spell slots, reactions, legendary actions, …)."""
    name: str
    current: int
    maximum: int

    def adjust(self, delta: int) -> str:
        """Apply delta, clamped to [0, maximum]. Returns a description string."""
        before = self.current
        self.current = max(0, min(self.maximum, self.current + delta))
        return f"{self.name}: {before} → {self.current}/{self.maximum}"

    def reset(self):
        self.current = self.maximum

    def __str__(self):
        return f"{self.name} {self.current}/{self.maximum}"


@dataclass
class Combatant:
    """One participant in combat (PC, NPC, or monster)."""
    name: str
    combatant_type: str          # 'pc', 'npc', or 'monster'
    initiative: int
    hp_current: int
    hp_max: int
    resources: dict = field(default_factory=dict)   # name → Resource
    conditions: list = field(default_factory=list)  # free-form condition strings
    is_active: bool = True       # False when dead / removed

    # Default resources injected at creation time (reaction, etc.) are done
    # externally so the shell can control them.

    # ── HP helpers ──────────────────────────────────────────────────────────

    def adjust_hp(self, delta: int) -> str:
        before = self.hp_current
        self.hp_current = max(0, min(self.hp_max, self.hp_current + delta))
        if self.hp_current == 0:
            self.is_active = False
        else:
            self.is_active = True
        return f"{self.name} HP: {before} → {self.hp_current}/{self.hp_max}"

    def set_hp(self, value: int) -> str:
        return self.adjust_hp(value - self.hp_current)

    @property
    def hp_bar_state(self) -> str:
        return hp_bar_state(self.hp_current, self.hp_max)

    @property
    def hp_fraction(self) -> float:
        if self.hp_max <= 0:
            return 0.0
        return max(0.0, min(1.0, self.hp_current / self.hp_max))

    # ── Resource helpers ─────────────────────────────────────────────────────

    def add_resource(self, name: str, maximum: int, current: Optional[int] = None) -> str:
        key = name.lower()
        c = maximum if current is None else current
        self.resources[key] = Resource(name=name, current=c, maximum=maximum)
        return f"Added resource '{name}' ({c}/{maximum}) to {self.name}"

    def adjust_resource(self, name: str, delta: int) -> str:
        key = name.lower()
        if key not in self.resources:
            return f"[!] {self.name} has no resource '{name}'"
        return self.resources[key].adjust(delta)

    def reset_resources(self):
        for r in self.resources.values():
            r.reset()

    # ── Condition helpers ────────────────────────────────────────────────────

    def add_condition(self, condition: str) -> str:
        if condition.lower() in (c.lower() for c in self.conditions):
            return f"[!] {self.name} already has condition '{condition}'"
        self.conditions.append(condition)
        return f"Added condition '{condition}' to {self.name}"

    def remove_condition(self, condition: str) -> str:
        for i, c in enumerate(self.conditions):
            if c.lower() == condition.lower():
                self.conditions.pop(i)
                return f"Removed condition '{condition}' from {self.name}"
        return f"[!] {self.name} does not have condition '{condition}'"

    # ── Display helpers ──────────────────────────────────────────────────────

    def summary(self) -> str:
        """Single-line DM summary."""
        res_str = "  ".join(str(r) for r in self.resources.values())
        cond_str = ", ".join(self.conditions)
        status = "" if self.is_active else " [DEAD]"
        return (
            f"[{self.combatant_type.upper():7s}] "
            f"{self.name:<20s} "
            f"Init:{self.initiative:>3}  "
            f"HP:{self.hp_current:>4}/{self.hp_max:<4}"
            + (f"  {res_str}" if res_str else "")
            + (f"  [{cond_str}]" if cond_str else "")
            + status
        )


class Combat:
    """Manages the full combat encounter."""

    def __init__(self):
        self.combatants: list[Combatant] = []
        self.round: int = 0
        self.turn_index: int = 0        # index into sorted active list
        self.active: bool = False

    # ── Building the encounter ───────────────────────────────────────────────

    def add_combatant(
        self,
        name: str,
        combatant_type: str,
        initiative: int,
        hp_max: int,
        hp_current: Optional[int] = None,
        add_reaction: bool = True,
    ) -> Combatant | None:
        if self.get(name) is not None:
            return None
        c = Combatant(
            name=name,
            combatant_type=combatant_type.lower(),
            initiative=initiative,
            hp_current=hp_current if hp_current is not None else hp_max,
            hp_max=hp_max,
        )
        if add_reaction:
            c.add_resource("Reaction", 1)
        self.combatants.append(c)
        return c

    def remove_combatant(self, name: str) -> bool:
        for i, c in enumerate(self.combatants):
            if c.name.lower() == name.lower():
                self.combatants.pop(i)
                # Clamp turn index
                self.turn_index = min(self.turn_index, max(0, len(self._order()) - 1))
                return True
        return False

    def get(self, name: str) -> Optional[Combatant]:
        for c in self.combatants:
            if c.name.lower() == name.lower():
                return c
        return None

    # ── Turn flow ────────────────────────────────────────────────────────────

    def _order(self) -> list[Combatant]:
        """Return combatants sorted by initiative descending (ties: insertion order)."""
        return sorted(self.combatants, key=lambda c: -c.initiative)

    def start(self) -> str:
        if not self.combatants:
            return "[!] No combatants added yet."
        self.active = True
        self.round = 1
        self.turn_index = 0
        return f"Combat started! Round 1. First up: {self._order()[0].name}"

    def current_combatant(self) -> Optional[Combatant]:
        order = self._order()
        if not order:
            return None
        return order[self.turn_index % len(order)]

    def next_turn(self) -> str:
        if not self.active:
            return "[!] Combat is not active. Use 'combat start'."
        order = self._order()
        if not order:
            return "[!] No combatants."

        # Reset reaction for the combatant who just finished their turn
        current = order[self.turn_index % len(order)]
        if "reaction" in current.resources:
            current.resources["reaction"].reset()

        self.turn_index += 1
        if self.turn_index >= len(order):
            self.turn_index = 0
            self.round += 1
            new_round_msg = f"\n  *** Round {self.round} begins! ***"
        else:
            new_round_msg = ""

        next_c = order[self.turn_index]
        return f"Next turn: {next_c.name} (Initiative {next_c.initiative}){new_round_msg}"

    def end(self) -> str:
        self.active = False
        self.combatants = []
        self.round = 0
        self.turn_index = 0
        return "Combat ended. All combatants cleared."

    def reset_all_resources(self) -> str:
        for c in self.combatants:
            c.reset_resources()
        return "All resources reset."

    # ── Display ──────────────────────────────────────────────────────────────

    def status(self) -> str:
        """Full DM status printout."""
        if not self.combatants:
            return "[i] No active combat."
        order = self._order()
        lines = [
            f"══ Round {self.round} {'(active)' if self.active else '(not started)'} ══",
        ]
        current = self.current_combatant() if self.active else None
        for i, c in enumerate(order):
            arrow = "▶ " if c is current else "  "
            lines.append(f"{arrow}{c.summary()}")
        return "\n".join(lines)

    def snapshot(self) -> dict:
        """Return a JSON-serialisable dict for the player screen renderer."""
        order = self._order()
        current = self.current_combatant() if self.active else None
        return {
            "active": self.active,
            "round": self.round,
            "combatants": [
                {
                    "name": c.name,
                    "type": c.combatant_type,
                    "initiative": c.initiative,
                    "hp_current": c.hp_current,
                    "hp_max": c.hp_max,
                    "hp_bar": c.hp_bar_state,
                    "hp_fraction": round(c.hp_fraction, 4),
                    "is_active": c.is_active,
                    "is_current_turn": c is current,
                    "conditions": list(c.conditions),
                    "resources": {
                        k: {"current": r.current, "maximum": r.maximum}
                        for k, r in c.resources.items()
                    },
                }
                for c in order
            ],
        }
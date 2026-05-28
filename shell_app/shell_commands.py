import cmd
import threading
import os
import glob
from PIL import Image, ImageTk

from shell_app.utils import tab_completion
from shell_app.combat import Combat

import platform

current_os = platform.system()

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame


class ImageShell(cmd.Cmd):
    intro = "AudioWindowCMD Shell. Type help or ? to list commands.\nType 'combat help' for combat tracker commands."
    prompt = "> "

    def __init__(self, command_queue):
        super().__init__()
        self.commands_list = [
            "show", "fullscreen", "restore", "minimize",
            "play", "stop", "volume",
            "combat", "next", "hp", "resource", "condition", "page",
            "exit",
        ]
        self.command_queue = command_queue
        self.vol_user = None
        self._combat = Combat()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _push_combat(self, page: int | None = None):
        """Send the latest combat snapshot to the player window."""
        self.command_queue.put(("combat_update", (self._combat.snapshot(), page)))

    def _start_combat_view(self):
        self.command_queue.put(("combat_enter", (self._combat.snapshot(), 0)))

    def _stop_combat_view(self):
        self.command_queue.put(("combat_exit", None))

    def _resolve_ties_for(self, init_val: int, tied: list):
        """Prompt the user to order a single group of tied combatants."""
        names = [c.name for c in tied]
        print(f"\n[!] Initiative tie at {init_val}:")
        for i, name in enumerate(names, 1):
            print(f"    {i}. {name}")
        print(f"    Enter desired turn order as space-separated numbers (1-{len(names)}),")
        print(f"    e.g. '2 1 3' means combatant 2 goes first, 1 second, 3 third.")
        while True:
            try:
                raw = input("    > ").strip().split()
                if len(raw) != len(names):
                    raise ValueError
                positions = [int(x) for x in raw]
                if sorted(positions) != list(range(1, len(names) + 1)):
                    raise ValueError
                msg = self._combat.apply_tiebreaker_order(init_val, names, positions)
                print(f"    [+] {msg}")
                break
            except (ValueError, IndexError):
                print(f"    [!] Invalid input. Enter {len(names)} unique numbers between 1 and {len(names)}.")

    def _resolve_ties(self):
        """Resolve all tied initiative groups — used on combat start."""
        for init_val, tied in self._combat.tied_initiatives().items():
            self._resolve_ties_for(init_val, tied)

    # ── Image / window commands ───────────────────────────────────────────────

    def do_show(self, arg):
        """Display an image in the window.\nUsage: show <path/to/file>"""
        self.command_queue.put(("show", arg))

    def do_fullscreen(self, arg):
        """Switch to fullscreen mode."""
        self.command_queue.put(("fullscreen", None))

    def do_restore(self, arg):
        """Restore window to default size (800×600)."""
        self.command_queue.put(("restore", None))

    def do_minimize(self, arg):
        """Minimize the window."""
        self.command_queue.put(("minimize", None))

    # ── Audio commands ────────────────────────────────────────────────────────

    def do_play(self, arg):
        """Play a music file (mp3, wav, ogg).\nUsage: play <path/to/file>"""
        if not arg:
            print("Usage: play <path/to/file>")
            return

        def play_thread(path):
            path = 'assets/audio/' + path
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"[!] Could not play {path}: {e}")

        threading.Thread(target=play_thread, args=(arg,), daemon=True).start()

    def do_volume(self, arg):
        """Get or set music volume (0-100).\nUsage: volume  |  volume <0-100>"""
        try:
            if not pygame.mixer.get_init():
                print("[!] Mixer not initialised. Play something first.")
                return
            if not arg.strip():
                vol = pygame.mixer.music.get_volume()
                if self.vol_user is not None:
                    print(f"Volume set to {self.vol_user}% (internal: {vol:.3f})")
                else:
                    print(f"Volume not manually set. Internal value: {vol:.3f}")
            else:
                val = float(arg)
                if not 0 <= val <= 100:
                    print("[!] Volume must be between 0 and 100")
                    return
                pygame.mixer.music.set_volume(val / 100.0)
                self.vol_user = val
                print(f"Volume set to {val}%")
        except Exception as e:
            print(f"[!] Could not adjust volume: {e}")

    def do_stop(self, arg):
        """Stop audio playback."""
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            print(f"[!] Could not stop playback: {e}")

    # ── Combat commands ───────────────────────────────────────────────────────
    #
    # All combat functionality lives under a single `combat` dispatcher so that
    # tab-completion for the top-level prompt stays clean.

    _COMBAT_HELP = """\
Combat tracker commands:
  combat new                                  — clear all combatants, start fresh
  combat add <name> <init> <type> <hp>        — add combatant
                                                type: pc | npc | monster
                                                e.g.  combat add Aria 18 pc 120
  combat add <name> <init> <type> <hp> <cur>  — add with current HP ≠ max
  combat start                                — begin combat (sort by initiative)
  combat status                               — print full DM status table
  combat end                                  — end combat, clear roster
  combat noreaction                           — add next combatant WITHOUT a reaction slot
                                                (use before the next 'combat add')
  combat legendary <name> <max>               — add legendary actions to a monster or NPC
  combat reset resources                      — reset all resources for all combatants
  combat action <actor> damage <target> <amount> [type]  — deal damage
  combat action <actor> heal <target> <amount>           — heal
  combat action <actor> condition <target> <condition>   — apply condition
  combat action <actor> remove_condition <target> <cond> — remove condition
  combat show                                 — restore combat view after showing an image

Shorthand commands (usable outside 'combat ...'):
  next                        — advance to next turn (resets current combatant's reaction)
  hp <name> <±amount>         — adjust HP:  hp Aria -15   hp Goblin-A +5
  hp <name> = <amount>        — set HP to exact value:  hp Aria = 80

  resource add <name> <res> <max>    — add/replace a resource slot
                                       e.g.  resource add Aria "Spell Slots 9th" 1
  resource <name> <res> <±amount>    — adjust a resource
                                       e.g.  resource Aria reaction -1
  resource reset <name>              — reset all resources for one combatant
  resource list <name>               — list a combatant's resources
"""

    def do_combat(self, arg):
        """Combat tracker. Type 'combat help' for full usage."""
        import shlex
        try:
            parts = shlex.split(arg.strip())
        except ValueError:
            parts = arg.strip().split()
        if not parts or parts[0] in ("help", "?"):
            print(self._COMBAT_HELP)
            return

        sub = parts[0].lower()

        if sub == "new":
            self._combat.end()
            print("[+] Combat roster cleared. Ready for new encounter.")
            self._push_combat()

        elif sub == "add":
            self._cmd_combat_add(parts[1:])

        elif sub == "start":
            self._resolve_ties()
            msg = self._combat.start()
            print(f"[+] {msg}")
            self._start_combat_view()

        elif sub == "status":
            print(self._combat.status())

        elif sub == "end":
            msg = self._combat.end()
            print(f"[+] {msg}")
            self._stop_combat_view()

        elif sub == "legendary":
            self._cmd_combat_legendary(parts[1:])

        elif sub == "action":
            self._cmd_combat_action(parts[1:])

        elif sub in ("show", "screen"):
            if not self._combat.combatants:
                print("[!] No combatants added yet.")
            else:
                self._start_combat_view()
                print("[+] Combat view restored.")

        elif sub == "noreaction":
            self._next_no_reaction = True
            print("[i] Next 'combat add' will not get a Reaction slot.")

        elif sub == "reset" and len(parts) > 1 and parts[1].lower() == "resources":
            msg = self._combat.reset_all_resources()
            print(f"[+] {msg}")
            self._push_combat()

        else:
            print(f"[!] Unknown combat sub-command '{sub}'. Type 'combat help'.")

    def _prompt_resource_spend(self, actor) -> str:
        """Prompt DM to choose which resource the actor spends for an out-of-turn action.
        Returns 'reaction', 'legendary_actions', or 'special'."""
        options = []
        current = self._combat.current_combatant()
        is_current_turn = current is not None and current.name == actor.name

        if is_current_turn:
            return "none"   # no prompt needed

        # Build options list
        if "reaction" in actor.resources:
            r = actor.resources["reaction"]
            warn = " [EMPTY]" if r.current == 0 else ""
            options.append(("reaction", f"Reaction ({r.current}/{r.maximum}){warn}"))
        if "legendary_actions" in actor.resources:
            r = actor.resources["legendary_actions"]
            warn = " [EMPTY]" if r.current == 0 else ""
            options.append(("legendary_actions", f"Legendary Actions ({r.current}/{r.maximum}){warn}"))
        options.append(("special", "Special case (no resource spent)"))

        print(f"[?] {actor.name} is acting outside their turn. Resource spent?")
        for i, (_, label) in enumerate(options, 1):
            print(f"    {i}. {label}")
        while True:
            try:
                raw = input("    > ").strip()
                idx = int(raw) - 1
                if not 0 <= idx < len(options):
                    raise ValueError
                key, label = options[idx]
                return key
            except (ValueError, IndexError):
                print(f"    [!] Enter a number between 1 and {len(options)}.")

    def _apply_resource_spend(self, actor, resource_key: str):
        """Apply the chosen resource spend and print the result."""
        if resource_key in ("none", "special"):
            if resource_key == "special":
                print(f"    [i] Special case — no resource spent for {actor.name}.")
            return
        msg = actor.adjust_resource(resource_key, -1)
        display = resource_key.replace("_", " ").title()
        print(f"    [+] {actor.name} spent a {display}. ({msg})")

    def _cmd_combat_action(self, parts: list[str]):
        """Handle 'combat action <actor> <type> <target> [args...]'."""
        ACTION_TYPES = ["damage", "heal", "condition", "remove_condition"]

        if len(parts) < 3:
            print("Usage: combat action <actor> damage|heal|condition|remove_condition <target> [args]")
            return

        actor_name  = parts[0]
        action_type = parts[1].lower()
        target_name = parts[2]
        rest        = parts[3:]

        if action_type not in ACTION_TYPES:
            print(f"[!] Unknown action type '{action_type}'. Choose: {', '.join(ACTION_TYPES)}")
            return

        actor = self._combat.get(actor_name)
        if actor is None:
            print(f"[!] Actor '{actor_name}' not found.")
            return

        target = self._combat.get(target_name)
        if target is None:
            print(f"[!] Target '{target_name}' not found.")
            return

        # Prompt resource spend if actor is not the current combatant
        resource_key = self._prompt_resource_spend(actor)

        # Execute the action
        if action_type == "damage":
            if not rest:
                print("[!] Usage: combat action <actor> damage <target> <amount> [type]")
                return
            try:
                amount = int(rest[0])
            except ValueError:
                print("[!] Amount must be an integer.")
                return
            dmg_type = rest[1] if len(rest) > 1 else None
            before = target.hp_current
            msg = target.adjust_hp(-amount)
            type_str = f" {dmg_type}" if dmg_type else ""
            print(f"[+] {actor_name} → damage → {target_name}: {amount}{type_str}  ({msg})")
            if not target.is_active:
                print(f"    {target.name} has dropped to 0 HP!")

        elif action_type == "heal":
            if not rest:
                print("[!] Usage: combat action <actor> heal <target> <amount>")
                return
            try:
                amount = int(rest[0])
            except ValueError:
                print("[!] Amount must be an integer.")
                return
            msg = target.adjust_hp(amount)
            print(f"[+] {actor_name} → heal → {target_name}: {amount}  ({msg})")

        elif action_type == "condition":
            if not rest:
                print("[!] Usage: combat action <actor> condition <target> <condition>")
                return
            condition = rest[0]
            msg = target.add_condition(condition)
            if msg.startswith("[!]"):
                print(f"    [!] Warning: {msg}")
            else:
                print(f"[+] {actor_name} → condition → {target_name}: {condition}")

        elif action_type == "remove_condition":
            if not rest:
                print("[!] Usage: combat action <actor> remove_condition <target> <condition>")
                return
            condition = rest[0]
            msg = target.remove_condition(condition)
            if msg.startswith("[!]"):
                print(f"    {msg}")
            else:
                print(f"[+] {actor_name} → remove_condition → {target_name}: {condition}")

        # Apply resource spend after action succeeds
        self._apply_resource_spend(actor, resource_key)
        self._push_combat()

    def _cmd_combat_legendary(self, parts: list[str]):
        """Handle 'combat legendary <name> <max>' command."""
        if len(parts) < 2:
            print("Usage: combat legendary <name> <max>")
            return
        import shlex
        name = parts[0]
        try:
            maximum = int(parts[1])
        except ValueError:
            print("[!] max must be an integer.")
            return
        c = self._combat.get(name)
        if c is None:
            print(f"[!] Combatant '{name}' not found.")
            return
        if c.combatant_type not in ("npc", "monster"):
            print(f"[!] Legendary actions can only be assigned to NPCs and monsters.")
            return
        msg = c.add_resource("legendary_actions", maximum)
        print(f"[+] {msg}")
        self._push_combat()

    def _cmd_combat_add(self, parts: list[str]):
        """Parse and execute 'combat add <name> <init> <type> <hp_max> [hp_cur]'."""
        if len(parts) < 4:
            print("Usage: combat add <name> <initiative> <type> <hp_max> [hp_current]")
            return
        name  = parts[0]
        try:
            init   = int(parts[1])
            ctype  = parts[2].lower()
            hp_max = int(parts[3])
            hp_cur = int(parts[4]) if len(parts) >= 5 else None
        except ValueError:
            print("[!] initiative, hp_max, and hp_current must be integers.")
            return

        if ctype not in ("pc", "npc", "monster"):
            print("[!] type must be one of: pc  npc  monster")
            return

        add_reaction = not getattr(self, "_next_no_reaction", False)
        self._next_no_reaction = False

        c = self._combat.add_combatant(
            name=name,
            combatant_type=ctype,
            initiative=init,
            hp_max=hp_max,
            hp_current=hp_cur,
            add_reaction=add_reaction,
        )
        if c is None:
            print(f"[!] A combatant named '{name}' already exists. Use a unique name, e.g. '{name} (Red)'.")
            return
        print(f"[+] Added: {c.summary()}")

        # If combat is already active, resolve ties only for this initiative value if needed
        if self._combat.active:
            ties = self._combat.tied_initiatives()
            if init in ties:
                self._resolve_ties_for(init, ties[init])
            self._push_combat()

    # ── next ──────────────────────────────────────────────────────────────────

    def do_next(self, arg):
        """Advance to the next combatant's turn.\nUsage: next"""
        msg = self._combat.next_turn()
        print(f"[+] {msg}")
        if self._combat.active:
            self._push_combat(page=self._page_of_current())

    def _page_of_current(self) -> int | None:
        """Return the 0-based page index of the current combatant, or None if unknown."""
        from shell_app.combat_view import PAGE_SIZE
        current = self._combat.current_combatant()
        if current is None:
            return None
        snap = self._combat.snapshot()
        combatants = snap["combatants"]
        revealed   = [e for e in combatants
                      if not e.get("pending", False)
                      and (e["type"] != "monster" or e.get("has_acted", True))]
        unrevealed = [e for e in combatants
                      if e.get("pending", False)
                      or (e["type"] == "monster" and not e.get("has_acted", True))]
        ordered = revealed + unrevealed
        for i, e in enumerate(ordered):
            if e["name"] == current.name:
                return i // PAGE_SIZE
        return None

    # ── hp ────────────────────────────────────────────────────────────────────

    def do_hp(self, arg):
        """Adjust or set a combatant's HP.
Usage:
  hp <name> <±amount>    e.g.  hp Aria -15   hp Goblin +5
  hp <name> = <amount>   e.g.  hp Aria = 80  (set to exact value)
"""
        import shlex
        try:
            parts = shlex.split(arg.strip())
        except ValueError:
            parts = arg.strip().split()
        if len(parts) < 2:
            print("Usage: hp <name> <±amount>  |  hp <name> = <amount>")
            return

        name = parts[0]
        c = self._combat.get(name)
        if c is None:
            print(f"[!] Combatant '{name}' not found.")
            return

        try:
            if parts[1] == "=" and len(parts) >= 3:
                value = int(parts[2])
                msg = c.set_hp(value)
            else:
                delta = int(parts[1])
                msg = c.adjust_hp(delta)
        except ValueError:
            print("[!] Amount must be an integer (e.g. -15, +8, 42).")
            return

        print(f"[+] {msg}")
        if not c.is_active:
            print(f"    {c.name} has dropped to 0 HP!")
        self._push_combat()

    # ── resource ──────────────────────────────────────────────────────────────

    def do_resource(self, arg):
        """Manage combatant resources (spell slots, legendary actions, …).
Usage:
  resource add <name> <resource_name> <max>       — define / replace a resource
  resource <name> <resource_name> <±amount>       — adjust current value
  resource reset <name>                           — reset all resources to max
  resource list <name>                            — list all resources
Examples:
  resource add Aria "Spell Slots 5th" 3
  resource Aria "Spell Slots 5th" -1
  resource add Vecna "Legendary Actions" 3
  resource Vecna "Legendary Actions" -1
  resource reset Vecna
"""
        # Tokenise, respecting quoted strings
        import shlex
        try:
            parts = shlex.split(arg.strip())
        except ValueError:
            parts = arg.strip().split()

        if not parts:
            print("Usage: resource add|reset|list|<name> …  Type 'help resource'.")
            return

        sub = parts[0].lower()

        if sub == "add":
            if len(parts) < 4:
                print("Usage: resource add <combatant_name> <resource_name> <max>")
                return
            c_name = parts[1]
            res_name = parts[2]
            try:
                maximum = int(parts[3])
            except ValueError:
                print("[!] max must be an integer.")
                return
            c = self._combat.get(c_name)
            if c is None:
                print(f"[!] Combatant '{c_name}' not found.")
                return
            msg = c.add_resource(res_name, maximum)
            print(f"[+] {msg}")
            self._push_combat()

        elif sub == "reset":
            if len(parts) < 2:
                print("Usage: resource reset <combatant_name>")
                return
            c = self._combat.get(parts[1])
            if c is None:
                print(f"[!] Combatant '{parts[1]}' not found.")
                return
            c.reset_resources()
            print(f"[+] Resources reset for {c.name}.")
            self._push_combat()

        elif sub == "list":
            if len(parts) < 2:
                print("Usage: resource list <combatant_name>")
                return
            c = self._combat.get(parts[1])
            if c is None:
                print(f"[!] Combatant '{parts[1]}' not found.")
                return
            if not c.resources:
                print(f"  {c.name} has no tracked resources.")
            else:
                for r in c.resources.values():
                    display_name = r.name.replace("_", " ").title()
                    bar = "█" * r.current + "░" * (r.maximum - r.current)
                    print(f"  {display_name:<30s} {r.current}/{r.maximum}  [{bar}]")

        else:
            # Interpret as: resource <name> <resource_name> <±amount>
            if len(parts) < 3:
                print("Usage: resource <combatant_name> <resource_name> <±amount>")
                return
            c_name = parts[0]
            res_name = parts[1]
            try:
                delta = int(parts[2])
            except ValueError:
                print("[!] amount must be an integer.")
                return
            c = self._combat.get(c_name)
            if c is None:
                print(f"[!] Combatant '{c_name}' not found.")
                return
            msg = c.adjust_resource(res_name, delta)
            print(f"[+] {msg}")
            self._push_combat()

    # ── condition ─────────────────────────────────────────────────────────────

    def do_condition(self, arg):
        """Add or remove a condition on a combatant.
Usage:
  condition add <name> <condition>     — add a condition
  condition remove <name> <condition>  — remove a condition
  condition list <name>                — list all conditions
Examples:
  condition add Aria Poisoned
  condition add "Dark Knight" "Magically Silenced"
  condition remove Aria Poisoned
"""
        import shlex
        try:
            parts = shlex.split(arg.strip())
        except ValueError:
            parts = arg.strip().split()

        if len(parts) < 2:
            print("Usage: condition add|remove|list <name> [condition]")
            return

        sub    = parts[0].lower()
        c_name = parts[1]
        c      = self._combat.get(c_name)
        if c is None:
            print(f"[!] Combatant '{c_name}' not found.")
            return

        if sub == "list":
            if not c.conditions:
                print(f"  {c.name} has no conditions.")
            else:
                for i, cond in enumerate(c.conditions, 1):
                    print(f"  {i}. {cond}")
            return

        if len(parts) < 3:
            print(f"Usage: condition {sub} <name> <condition>")
            return

        condition = parts[2]

        if sub == "add":
            msg = c.add_condition(condition)
            print(f"[+] {msg}")
            self._push_combat()
        elif sub == "remove":
            msg = c.remove_condition(condition)
            print(f"[+] {msg}")
            self._push_combat()
        else:
            print(f"[!] Unknown sub-command '{sub}'. Use add, remove, or list.")

    def complete_condition(self, text, line, begidx, endidx):
        import shlex
        try:
            parts = shlex.split(line[:begidx])
        except ValueError:
            parts = line[:begidx].split()

        # Position 1: sub-command
        if len(parts) == 1:
            subs = ["add", "remove", "list"]
            return [s for s in subs if s.startswith(text)]

        # Position 2: combatant name
        if len(parts) == 2:
            names = [c.name for c in self._combat.combatants]
            return [n for n in names if n.lower().startswith(text.lower())]

        # Position 3 for remove: existing condition name
        if len(parts) == 3 and parts[1].lower() == "remove":
            c_name = parts[2]
            c = self._combat.get(c_name)
            if c:
                return [cond for cond in c.conditions if cond.lower().startswith(text.lower())]

        return []

    # ── page ──────────────────────────────────────────────────────────────────

    def do_page(self, arg):
        """Navigate the combat view pages.
Usage:
  page next       — go to next page (wraps around)
  page prev       — go to previous page (wraps around)
  page <number>   — jump to specific page (1-based)
"""
        arg = arg.strip().lower()
        if arg == "next":
            self.command_queue.put(("page_next", None))
        elif arg == "prev":
            self.command_queue.put(("page_prev", None))
        else:
            try:
                n = int(arg)
                self.command_queue.put(("page_set", n - 1))  # convert to 0-based
            except ValueError:
                print("Usage: page next | page prev | page <number>")

    def complete_page(self, text, line, begidx, endidx):
        options = ["next", "prev"]
        return [o for o in options if o.startswith(text)]

    # ── Exit ──────────────────────────────────────────────────────────────────────

    def do_exit(self, arg):
        """Close the application."""
        self.command_queue.put(("exit", None))
        print("Exiting shell.")
        return True

    # ── Tab completion ────────────────────────────────────────────────────────

    def complete_show(self, text, line, begidx, endidx):
        if current_os == "Linux" and len(line.split()) > 1:
            clean_text = line.split()[1]
        else:
            clean_text = text
        return tab_completion(clean_text, list(Image.registered_extensions()), current_os, 'image')

    def complete_play(self, text, line, begidx, endidx):
        if current_os == "Linux" and len(line.split()) > 1:
            clean_text = line.split()[1]
        else:
            clean_text = text
        return tab_completion(clean_text, [".mp3", ".wav", ".ogg"], current_os, 'audio')

    def complete_combat(self, text, line, begidx, endidx):
        import shlex
        try:
            parts = shlex.split(line[:begidx])
        except ValueError:
            parts = line[:begidx].split()

        top_subs = ["new", "add", "start", "status", "end", "show", "screen",
                    "noreaction", "reset", "legendary", "action"]

        # Position 1: top-level subcommand
        if len(parts) == 1:
            return [s for s in top_subs if s.startswith(text)]

        if parts[1].lower() != "action":
            return [s for s in top_subs if s.startswith(text)]

        action_types = ["damage", "heal", "condition", "remove_condition"]
        names = [c.name for c in self._combat.combatants]

        # Position 2 (action): actor name
        if len(parts) == 2:
            return [n for n in names if n.lower().startswith(text.lower())]

        # Position 3 (action): action type
        if len(parts) == 3:
            return [a for a in action_types if a.startswith(text)]

        # Position 4 (action): target name
        if len(parts) == 4:
            return [n for n in names if n.lower().startswith(text.lower())]

        # Position 5 (action): condition name for remove_condition
        if len(parts) == 5 and parts[3].lower() == "remove_condition":
            target = self._combat.get(parts[4])
            if target:
                return [cond for cond in target.conditions if cond.lower().startswith(text.lower())]

        return []

    def complete_hp(self, text, line, begidx, endidx):
        names = [c.name for c in self._combat.combatants]
        return [n for n in names if n.lower().startswith(text.lower())]

    def complete_resource(self, text, line, begidx, endidx):
        import shlex
        try:
            parts = shlex.split(line[:begidx])
        except ValueError:
            parts = line[:begidx].split()

        # Position 1: sub-command or combatant name
        if len(parts) == 1:
            subs = ["add", "reset", "list"] + [c.name for c in self._combat.combatants]
            return [s for s in subs if s.lower().startswith(text.lower())]

        # Position 2: combatant name (when sub is add/reset/list) or resource name
        if len(parts) == 2:
            sub = parts[1].lower()
            if sub in ("add", "reset", "list"):
                names = [c.name for c in self._combat.combatants]
                return [n for n in names if n.lower().startswith(text.lower())]
            else:
                # Interpret as combatant name, complete resource names
                c = self._combat.get(parts[1])
                if c:
                    return [k for k in c.resources if k.startswith(text.lower())]

        # Position 3: resource name when sub is add/reset/list + combatant name
        if len(parts) == 3 and parts[1].lower() not in ("add",):
            c = self._combat.get(parts[2])
            if c:
                return [k for k in c.resources if k.startswith(text.lower())]

        return []

    def complete_next(self, text, line, begidx, endidx):
        return []

    def completenames(self, text, *ignored):
        return [cmd for cmd in self.commands_list if cmd.startswith(text)]
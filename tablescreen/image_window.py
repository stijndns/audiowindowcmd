import tkinter as tk
from PIL import Image, ImageTk
from screeninfo import get_monitors
import os
import platform

from tablescreen.features.combat.views.combat_view import CombatView

current_os = platform.system()

class ImageWindow(tk.Frame):
    def __init__(self, root, command_queue):
        super().__init__(root, bg="black")
        root.title("AudioWindowCMD")
        root.geometry("800x600")

        self.label = tk.Label(self, bg="black")
        self.label.pack(fill="both", expand=True)

        self.original_image = None
        self.image = None

        self.command_queue = command_queue
        self.pack(fill="both", expand=True)

        # Combat view overlay
        self._combat_mode = False
        self.combat_view = CombatView(root)
        self.combat_view.hide()   # hidden until combat starts

        # Bind window resize event to re-render the image
        self.bind("<Configure>", lambda e: self.render_image())

        # Start checking queue for commands
        self.bind("<<QueueMsg>>", self.check_commands)

    # ── Image display ─────────────────────────────────────────────────────────

    def load_image(self, path):
        path = 'assets/images/' + path
        if not os.path.exists(path):
            print(f"[!] File not found: {path}")
            return
        try:
            self.original_image = Image.open(path)
            print(f"[+] Loaded image: {path}")
        except Exception as e:
            print(f"[!] Error loading image: {e}")

    def render_image(self):
        if self._combat_mode:
            return
        if self.original_image is None:
            return

        img = self.original_image.copy()

        win_w = self.winfo_width()
        win_h = self.winfo_height()

        if win_w <= 1 or win_h <= 1:
            return

        img_w, img_h = img.size
        scale = min(win_w / img_w, win_h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        img = img.resize((new_w, new_h), Image.LANCZOS) # type: ignore
        self.image = ImageTk.PhotoImage(img)
        self.label.config(image=self.image)

    # ── Window controls ───────────────────────────────────────────────────────

    def fullscreen(self):
        self.restore()

        x = self.winfo_toplevel().winfo_x()
        y = self.winfo_toplevel().winfo_y()

        for m in get_monitors():
            if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
                if current_os == "Windows":
                    self.winfo_toplevel().geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
                    self.winfo_toplevel().overrideredirect(True)
                if current_os == "Linux":
                    self.winfo_toplevel().attributes("-fullscreen", True)
                self.render_image()
                return m
        return None

    def restore(self):
        self.winfo_toplevel().overrideredirect(False)
        self.winfo_toplevel().attributes("-fullscreen", False)
        self.winfo_toplevel().deiconify()
        self.winfo_toplevel().geometry("800x600")
        self.render_image()

    def minimize(self):
        if self.winfo_toplevel().overrideredirect():
            self.restore()
        self.winfo_toplevel().iconify()

    # ── Combat mode ───────────────────────────────────────────────────────────

    def enter_combat_mode(self, snapshot):
        """Hide image label, show combat canvas."""
        self._combat_mode = True
        self.pack_forget()
        self.combat_view._snapshot = snapshot
        self.combat_view._page = 0
        self.combat_view.show()

    def exit_combat_mode(self):
        """Hide combat canvas, restore image label."""
        self._combat_mode = False
        self.combat_view.hide()
        self.pack(fill="both", expand=True)
        self.render_image()

    # ── Command queue polling ─────────────────────────────────────────────────

    def check_commands(self, event):
        assert not self.command_queue.empty()
        cmd, arg = self.command_queue.get()
        if cmd == "show":
            if self._combat_mode:
                self.exit_combat_mode()
            self.load_image(arg)
            self.render_image()

        elif cmd == "fullscreen":
            m = self.fullscreen()
            print(f"[+] Fullscreen on monitor {m}")

        elif cmd == "restore":
            self.restore()
            print("[+] Restored window")

        elif cmd == "minimize":
            self.minimize()
            print("[+] Minimized window")

        elif cmd == "combat_enter":
            self.enter_combat_mode(arg)

        elif cmd == "combat_exit":
            self.exit_combat_mode()

        elif cmd == "combat_update":
            snapshot, page = arg
            self.combat_view.render(snapshot, page)

        elif cmd == "page_next":
            self.combat_view.page_next()

        elif cmd == "page_prev":
            self.combat_view.page_prev()

        elif cmd == "page_set":
            self.combat_view.set_page(arg)

        elif cmd == "exit":
            print("[+] Exiting...")
            self.master.destroy()
            return
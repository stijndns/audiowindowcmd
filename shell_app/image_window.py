import tkinter as tk
from PIL import Image, ImageTk
from screeninfo import get_monitors
import os
import platform

current_os = platform.system()

class ImageWindow:
    def __init__(self, root, command_queue):
        self.root = root
        self.root.title("AudioWindowCMD")
        self.root.geometry("800x600")

        self.label = tk.Label(root, bg="black")
        self.label.pack(fill="both", expand=True)

        self.original_image = None
        self.image = None

        self.command_queue = command_queue

        # Bind window resize event to re-render the image
        self.root.bind("<Configure>", lambda e: self.render_image())

        # Start checking queue for commands
        self.root.after(200, self.check_commands)

    def load_image(self, path):
        if not os.path.exists(path):
            print(f"[!] File not found: {path}")
            return
        try:
            self.original_image = Image.open(path)
            print(f"[+] Loaded image: {path}")
        except Exception as e:
            print(f"[!] Error loading image: {e}")

    def render_image(self):
        if self.original_image is None:
            return

        img = self.original_image.copy()

        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()

        if win_w <= 1 or win_h <= 1:
            return

        img_w, img_h = img.size

        # Compute scale factor to fit image inside window while preserving aspect ratio
        scale = min(win_w / img_w, win_h / img_h)

        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        img = img.resize((new_w, new_h), Image.LANCZOS)
        self.image = ImageTk.PhotoImage(img)
        self.label.config(image=self.image)

    def fullscreen(self):
        self.restore()

        x = self.root.winfo_x()
        y = self.root.winfo_y()

        # Ensure fullscreen occurs on monitor containing window origin
        for m in get_monitors():
            if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
                if current_os == "Windows":
                    self.root.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
                    self.root.overrideredirect(True)
                if current_os == "Linux":
                    self.root.attributes("-fullscreen", True)
                self.render_image()
                return m

    def restore(self):
        self.root.overrideredirect(False)
        self.root.attributes("-fullscreen", False)
        self.root.deiconify()
        self.root.geometry("800x600")
        self.render_image()

    def minimize(self):
        if self.root.overrideredirect():
            self.restore()
        self.root.iconify()

    def check_commands(self):
        while not self.command_queue.empty():
            cmd, arg = self.command_queue.get()
            if cmd == "show":
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
            elif cmd == "exit":
                print("[+] Exiting...")
                self.root.destroy()
                return
        # Poll queue for commands every 200 ms
        self.root.after(200, self.check_commands)
import tkinter as tk
import threading
import queue

from shell_app.image_window import ImageWindow
from shell_app.shell_commands import ImageShell

def shell_thread():
    shell = ImageShell(command_queue)
    shell.cmdloop()

if __name__ == "__main__":

    command_queue = queue.Queue()
    root = tk.Tk()
    win = ImageWindow(root, command_queue)
    
    # Separate thread for shell, communication occurs via queue
    threading.Thread(target=shell_thread, daemon=True).start()

    root.mainloop()
import cmd
import threading
import os
import glob
from PIL import Image, ImageTk

from shell_app.utils import tab_completion

# Hide pygame import message 
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

class ImageShell(cmd.Cmd):
    intro = "AudioWindowCMD Shell. Type help or ? to list commands."
    prompt = "> "

    def __init__(self, command_queue):
        super().__init__()
        self.commands_list = ["show", "fullscreen", "restore", "minimize", "play", "stop", "exit"]
        self.command_queue = command_queue
        # Variable to track exact input volume given by user, necessary because pygame.mixer.music.get_volume() might not return exact same value due to mixer quantization
        self.vol_user = None

    # --- Commands ---
    def do_show(self, arg):
        """
        Display an image in the window. It is automatically scaled to the window size.
        Usage:
          show <path/to/file>
        """
        self.command_queue.put(("show", arg))

    def do_fullscreen(self, arg):
        """
        Switch to fullscreen mode on the monitor which currently contains the window origin.
        """
        self.command_queue.put(("fullscreen", None))

    def do_restore(self, arg):
        """
        Restore window from fullscreen to the default size (800x600).
        """
        self.command_queue.put(("restore", None))

    def do_minimize(self, arg):
        """
        Minimize the window.
        """
        self.command_queue.put(("minimize", None))
    
    def do_play(self, arg):
        """
        Play a music file (mp3, wav or ogg).
        """
        if not arg:
            print("Usage: play <path/to/file>")
            return

        # Run playback in a background thread so shell doesn’t block
        def play_thread(path):
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"[!] Could not play {path}: {e}")

        threading.Thread(target=play_thread, args=(arg,), daemon=True).start()

    def do_volume(self, arg):
        """
        Get or set music volume.
        Usage:
          volume         -> shows current volume
          volume <0-100> -> sets volume (percentage)
        """
        try:
            if not pygame.mixer.get_init():
                print("[!] Mixer is not initialized. Play something first.")
                return

            if not arg.strip():
                vol = pygame.mixer.music.get_volume()
                if self.vol_user:
                    print(f"Volume was set to {self.vol_user}%, the actual internal value is {vol}.")
                else:
                    print(f"Volume was not manually set by user, the actual internal value is {vol}.")
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
        """
        Stop playback.
        """
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            print(f"[!] Could not stop playback: {e}")

    def do_exit(self, arg):
        """
        Close the application.
        """
        self.command_queue.put(("exit", None))
        print("Exiting shell.")
        return True

    # --- Tab completion ---
    def complete_show(self, text, line, begidx, endidx):
        """
        Tab completion for image file paths.
        """
        if not text:
            text = ""
        results = tab_completion(text, list(Image.registered_extensions()))
        return results

    def complete_play(self, text, line, begidx, endidx):
        """
        Tab completion for audio file paths.
        """
        if not text:
            text = ""
        results = tab_completion(text, [".mp3", ".wav", ".ogg"])
        return results

    def completenames(self, text, *ignored):
        return [cmd for cmd in self.commands_list if cmd.startswith(text)]
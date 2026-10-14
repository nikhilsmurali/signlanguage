# phase2/sign_player.py

"""
Sign Player Module
------------------
Text-to-sign translator UI for Phase 2.

Converts text into a live 2D hand animation using the real MediaPipe
landmarks captured in Phase 1 (see phase2/hand_animator.py).
"""

import tkinter as tk
from tkinter import ttk

# Import the real hand animator
try:
    from hand_animator import HandAnimatorCanvas, build_sign_sequence
except ModuleNotFoundError:
    from phase2.hand_animator import HandAnimatorCanvas, build_sign_sequence


class SignPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sign Language Translator")
        self.root.geometry("980x880")
        self.root.minsize(760, 700)
        self.root.resizable(True, True)
        self._configure_styles()

        self._build_ui()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(background="#101820")
        style.configure("App.TFrame", background="#101820")
        style.configure("Panel.TFrame", background="#17232d")
        style.configure("Title.TLabel", background="#101820", foreground="#f4f7fa", font=("Arial", 21, "bold"))
        style.configure("Subtitle.TLabel", background="#101820", foreground="#9eacb8", font=("Arial", 10))
        style.configure("Section.TLabel", background="#17232d", foreground="#e7edf2", font=("Arial", 10, "bold"))
        style.configure("Muted.TLabel", background="#17232d", foreground="#91a0ad", font=("Arial", 9))
        style.configure("Sign.TLabel", background="#17232d", foreground="#5fd4c1", font=("Arial", 18, "bold"))
        style.configure("Status.TLabel", background="#101820", foreground="#5fd4c1", font=("Arial", 9, "bold"))
        style.configure("Warning.TLabel", background="#17232d", foreground="#ff9b8e", font=("Arial", 9))
        style.configure("TButton", font=("Arial", 10, "bold"), padding=(12, 8))
        style.configure("Primary.TButton", background="#36a995", foreground="#ffffff")
        style.map(
            "Primary.TButton",
            background=[("active", "#2c927f"), ("disabled", "#36434d")],
            foreground=[("disabled", "#87939d")],
        )
        style.configure("TEntry", padding=10, fieldbackground="#f4f7fa", foreground="#17232d")
        style.configure("Horizontal.TScale", background="#17232d", troughcolor="#34444f")

    def _build_ui(self):
        header_frame = ttk.Frame(self.root, style="App.TFrame", padding=(28, 22, 28, 18))
        header_frame.pack(fill=tk.X)
        ttk.Label(
            header_frame, text="SIGN LANGUAGE TRANSLATOR", style="Title.TLabel"
        ).pack(anchor=tk.W)
        ttk.Label(
            header_frame,
            text="SIGN STUDIO     /     Turn text into expressive hand animation",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(5, 0))

        input_frame = ttk.Frame(self.root, style="Panel.TFrame", padding=(18, 16))
        input_frame.pack(fill=tk.X, padx=28, pady=(0, 14))
        ttk.Label(input_frame, text="TEXT TO SIGN", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 9))
        input_row = ttk.Frame(input_frame, style="Panel.TFrame")
        input_row.pack(fill=tk.X)
        self.entry_var = tk.StringVar(value="I NEED WATER")
        self.entry_box = ttk.Entry(input_row, textvariable=self.entry_var, font=("Arial", 11))
        self.entry_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.entry_box.bind("<Return>", lambda event: self.process_input())
        convert_btn = ttk.Button(
            input_row, text="Generate signs", style="Primary.TButton", command=self.process_input
        )
        convert_btn.pack(side=tk.RIGHT)

        output_frame = ttk.Frame(self.root, style="Panel.TFrame", padding=16)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 14))
        output_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)

        output_header = ttk.Frame(output_frame, style="Panel.TFrame")
        output_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(output_header, text="SIGN OUTPUT", style="Section.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(output_header, text="READY", style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)

        self.anim_canvas = HandAnimatorCanvas(
            output_frame, width=760, height=340, bg="#111b23"
        )
        self.anim_canvas.grid(row=1, column=0, sticky="nsew")
        self.anim_canvas.on_label_change = self._on_anim_label_change
        self.anim_canvas.on_finished = self._on_anim_finished

        caption_frame = ttk.Frame(output_frame, style="Panel.TFrame", padding=(0, 14, 0, 0))
        caption_frame.grid(row=2, column=0, sticky="ew")
        caption_frame.columnconfigure(0, weight=1)
        self.anim_label = ttk.Label(caption_frame, text="Ready to sign", style="Sign.TLabel")
        self.anim_label.grid(row=0, column=0, sticky=tk.W)
        ttk.Label(
            caption_frame,
            text="REAL CAPTURED HAND POSES",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky=tk.E)

        self.anim_unsupported_label = ttk.Label(
            output_frame, text="", style="Warning.TLabel", wraplength=820,
        )
        self.anim_unsupported_label.grid(row=3, column=0, sticky=tk.W, pady=(8, 0))

        controls_frame = ttk.Frame(output_frame, style="Panel.TFrame", padding=(0, 14, 0, 0))
        controls_frame.grid(row=4, column=0, sticky="ew")
        self.anim_play_btn = ttk.Button(
            controls_frame, text="Play", command=self.anim_play, state=tk.DISABLED
        )
        self.anim_play_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.anim_pause_btn = ttk.Button(
            controls_frame, text="Pause", command=self.anim_pause, state=tk.DISABLED
        )
        self.anim_pause_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.anim_restart_btn = ttk.Button(
            controls_frame, text="Restart", command=self.anim_restart, state=tk.DISABLED
        )
        self.anim_restart_btn.pack(side=tk.LEFT)
        ttk.Label(controls_frame, text="PLAYBACK SPEED", style="Subtitle.TLabel").pack(
            side=tk.LEFT, padx=(28, 10)
        )
        self.anim_speed = tk.IntVar(value=12)
        ttk.Label(controls_frame, text="SLOW", style="Subtitle.TLabel").pack(side=tk.LEFT)
        speed_slider = ttk.Scale(
            controls_frame, from_=4, to=24, orient=tk.HORIZONTAL,
            variable=self.anim_speed, command=self._on_speed_change, length=170
        )
        speed_slider.pack(side=tk.LEFT, padx=8)
        ttk.Label(controls_frame, text="FAST", style="Subtitle.TLabel").pack(side=tk.LEFT)

    # ---------------- Input processing ----------------

    def process_input(self):
        text = self.entry_var.get().strip()
        if not text:
            self.anim_canvas.load_sequence([])
            self.anim_play_btn.config(state=tk.DISABLED, text="Play")
            self.anim_pause_btn.config(state=tk.DISABLED)
            self.anim_restart_btn.config(state=tk.DISABLED)
            self.anim_label.config(text="Enter text to begin")
            self.anim_unsupported_label.config(text="")
            self.status_label.config(text="ENTER TEXT")
            return

        sequence, anim_unsupported = build_sign_sequence(text)
        self.anim_canvas.load_sequence(sequence)

        if sequence:
            self.anim_play_btn.config(state=tk.NORMAL)
            self.anim_pause_btn.config(state=tk.NORMAL)
            self.anim_restart_btn.config(state=tk.NORMAL)
            self.status_label.config(text="PLAYING")
            self.anim_canvas.play()
        else:
            self.anim_play_btn.config(state=tk.DISABLED)
            self.anim_pause_btn.config(state=tk.DISABLED)
            self.anim_restart_btn.config(state=tk.DISABLED)
            self.status_label.config(text="NO CAPTURED SIGNS")
            self.anim_label.config(text="No supported signs found")

        if anim_unsupported:
            self.anim_unsupported_label.config(
                text=f"No captured pose for: {', '.join(anim_unsupported)}"
            )
        else:
            self.anim_unsupported_label.config(text="")

    # ---------------- Real hand animation controls ----------------

    def _on_anim_label_change(self, label):
        self.anim_label.config(text=label)

    def _on_anim_finished(self):
        self.status_label.config(text="COMPLETE")

    def anim_play(self):
        self.anim_canvas.play()
        if self.anim_canvas.playing:
            self.status_label.config(text="PLAYING")

    def anim_pause(self):
        self.anim_canvas.pause()
        self.status_label.config(text="PAUSED")

    def anim_restart(self):
        self.anim_canvas.restart()
        self.anim_canvas.play()
        self.status_label.config(text="PLAYING" if self.anim_canvas.playing else "READY")

    def _on_speed_change(self, _value):
        frames = 28 - int(self.anim_speed.get())
        self.anim_canvas.set_speed(frames_per_sign=frames, hold_frames=max(4, frames - 4))


def main():
    root = tk.Tk()
    app = SignPlayerApp(root)
    app.process_input()
    root.mainloop()


if __name__ == "__main__":
    main()
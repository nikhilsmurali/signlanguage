"""
SignConnect Live - Master Application Portal
============================================
Unified dashboard connecting Phase 1 (Sign -> Text Recognition)
and Phase 2 (Text -> Sign Animation) with an elegant, modern UI.
"""

import sys
import os
import subprocess
import threading
import time
import re
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw

# Set high-DPI awareness on Windows if available
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Setup paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE1_DIR = os.path.join(ROOT_DIR, "phase1")
PHASE1_SCRIPT = os.path.join(PHASE1_DIR, "phase1", "camera_test.py")
PHASE2_DIR = os.path.join(ROOT_DIR, "phase2")

# Add phase2 to sys.path for direct imports
if PHASE2_DIR not in sys.path:
    sys.path.insert(0, PHASE2_DIR)

# Attempt importing Phase 2 modules
try:
    from sign_player import SignPlayerApp
    from hand_animator import build_sign_sequence, HAND_CONNECTIONS, FINGERTIPS, interpolate, POSE_BANK
    PHASE2_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import Phase 2 modules: {e}")
    PHASE2_AVAILABLE = False


# ---------------------------------------------------------
# Icon Generation Helpers (PIL Vector Rendering)
# ---------------------------------------------------------

def create_hand_icon(size=(32, 32), color="#3B82F6", stroke_width=2):
    """Draws a crisp anti-aliased hand icon outline."""
    w, h = size
    scale = 4
    sw, sh = w * scale, h * scale
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    norm_pts = [
        (35, 92), (25, 84), (16, 70), (12, 56), (15, 46), (22, 46), (29, 58),
        (32, 34), (36, 18), (43, 18), (45, 38),
        (46, 26), (51, 12), (58, 12), (59, 38),
        (60, 28), (65, 18), (72, 18), (73, 42),
        (74, 42), (79, 36), (85, 36), (86, 54),
        (76, 76), (62, 92)
    ]
    scaled_pts = [(x * sw / 100, y * sh / 100) for x, y in norm_pts]

    for i in range(len(scaled_pts) - 1):
        d.line([scaled_pts[i], scaled_pts[i + 1]], fill=color, width=stroke_width * scale)
    d.line([scaled_pts[-1], scaled_pts[0]], fill=color, width=stroke_width * scale)

    return img.resize((w, h), Image.Resampling.LANCZOS)


def create_t_icon(size=(32, 32), color="#8B5CF6", stroke_width=2):
    """Draws a crisp anti-aliased styled 'T' icon."""
    w, h = size
    scale = 4
    sw, sh = w * scale, h * scale
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    x1, y1 = 0.20 * sw, 0.22 * sh
    x2, y2 = 0.80 * sw, 0.22 * sh
    d.line([(x1, y1), (x2, y2)], fill=color, width=stroke_width * scale + 2)
    d.line([(x1, y1), (x1, y1 + 0.12 * sh)], fill=color, width=stroke_width * scale)
    d.line([(x2, y2), (x2, y2 + 0.12 * sh)], fill=color, width=stroke_width * scale)

    cx = 0.50 * sw
    sy1 = y1
    sy2 = 0.82 * sh
    d.line([(cx, sy1), (cx, sy2)], fill=color, width=stroke_width * scale + 2)

    bx1, bx2 = 0.35 * sw, 0.65 * sw
    d.line([(bx1, sy2), (bx2, sy2)], fill=color, width=stroke_width * scale)

    return img.resize((w, h), Image.Resampling.LANCZOS)


def create_camera_icon(size=(64, 64), color="#94A3B8", stroke_width=3):
    """Draws a modern line-art camera icon."""
    w, h = size
    scale = 4
    sw, sh = w * scale, h * scale
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    bx1, by1 = 0.14 * sw, 0.32 * sh
    bx2, by2 = 0.86 * sw, 0.82 * sh
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=int(0.10 * sw), outline=color, width=stroke_width * scale)

    tx1, ty1 = 0.35 * sw, 0.32 * sh
    tx2, ty2 = 0.65 * sw, 0.22 * sh
    d.polygon([(tx1, ty1), (tx1 + 0.05 * sw, ty2), (tx2 - 0.05 * sw, ty2), (tx2, ty1)], outline=color, width=stroke_width * scale)

    lx1, ly1 = 0.36 * sw, 0.43 * sh
    lx2, ly2 = 0.64 * sw, 0.71 * sh
    d.ellipse([lx1, ly1, lx2, ly2], outline=color, width=stroke_width * scale)

    fx, fy = 0.74 * sw, 0.40 * sh
    fr = 0.03 * sw
    d.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], fill=color)

    return img.resize((w, h), Image.Resampling.LANCZOS)


# ---------------------------------------------------------
# Main UI Application
# ---------------------------------------------------------

class SignConnectApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SignConnect Live")
        self.root.geometry("1080x760")
        self.root.minsize(980, 680)
        self.root.configure(bg="#F8FAFC")

        # Process management for Phase 1
        self.phase1_process = None
        self.phase1_monitor_thread = None
        self.phase1_user_stopped = False

        # Phase 2 animation state inside the dashboard
        self.anim_sequence = []
        self.anim_index = 0
        self.anim_frame = 0
        self.anim_frames_per_sign = 14
        self.anim_hold_frames = 8
        self.anim_hold_counter = 0
        self.anim_playing = False
        self.anim_after_id = None

        # Cache PIL images
        self._cache_icons()

        # Build UI layout
        self._build_header()
        self._build_cards_container()
        self._build_footer()

        # Handle clean window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _cache_icons(self):
        """Pre-renders vector icons to prevent garbage collection."""
        self.blue_hand_icon = ImageTk.PhotoImage(create_hand_icon(size=(30, 30), color="#3B82F6", stroke_width=2))
        self.purple_t_icon = ImageTk.PhotoImage(create_t_icon(size=(30, 30), color="#8B5CF6", stroke_width=2))
        self.camera_placeholder_icon = ImageTk.PhotoImage(create_camera_icon(size=(58, 58), color="#94A3B8", stroke_width=3))
        self.purple_hand_placeholder_icon = ImageTk.PhotoImage(create_hand_icon(size=(58, 58), color="#8B5CF6", stroke_width=2))

    # ---------------- UI Structure ----------------

    def _build_header(self):
        """Builds the top header banner: SignConnect Live + Subtitle."""
        header_frame = tk.Frame(self.root, bg="#F8FAFC")
        header_frame.pack(fill=tk.X, pady=(32, 18))

        # Title container
        title_box = tk.Frame(header_frame, bg="#F8FAFC")
        title_box.pack(anchor=tk.CENTER)

        tk.Label(
            title_box,
            text="SignConnect ",
            font=("Segoe UI", 26, "bold"),
            fg="#0F172A",
            bg="#F8FAFC"
        ).pack(side=tk.LEFT)

        tk.Label(
            title_box,
            text="Live",
            font=("Segoe UI", 26, "bold"),
            fg="#6366F1",
            bg="#F8FAFC"
        ).pack(side=tk.LEFT)

        # Subtitle
        tk.Label(
            header_frame,
            text="Hands speak. Words connect.",
            font=("Segoe UI", 12),
            fg="#64748B",
            bg="#F8FAFC"
        ).pack(anchor=tk.CENTER, pady=(4, 0))

    def _build_cards_container(self):
        """Builds the dual-card dashboard: Left (Sign->Text) & Right (Text->Sign)."""
        main_cards_frame = tk.Frame(self.root, bg="#F8FAFC")
        main_cards_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 15))

        main_cards_frame.columnconfigure(0, weight=1, uniform="card")
        main_cards_frame.columnconfigure(1, weight=1, uniform="card")
        main_cards_frame.rowconfigure(0, weight=1)

        # Build Left Card: Sign -> Text (Phase 1)
        self._build_phase1_card(main_cards_frame)

        # Build Right Card: Text -> Sign (Phase 2)
        self._build_phase2_card(main_cards_frame)

    # ---------------- Left Card: Phase 1 (Sign -> Text) ----------------

    def _build_phase1_card(self, parent):
        card_outer = tk.Frame(parent, bg="#E2E8F0", bd=1, relief=tk.SOLID, cursor="hand2")
        card_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=6)
        card_outer.bind("<Button-1>", lambda e: self.toggle_phase1())

        card_inner = tk.Frame(card_outer, bg="#FFFFFF", padx=22, pady=20, cursor="hand2")
        card_inner.pack(fill=tk.BOTH, expand=True)
        card_inner.bind("<Button-1>", lambda e: self.toggle_phase1())

        # 1. Header (Icon + Title + Subtitle)
        hdr_frame = tk.Frame(card_inner, bg="#FFFFFF", cursor="hand2")
        hdr_frame.pack(fill=tk.X, pady=(0, 14))
        hdr_frame.bind("<Button-1>", lambda e: self.toggle_phase1())

        icon_lbl = tk.Label(hdr_frame, image=self.blue_hand_icon, bg="#FFFFFF", cursor="hand2")
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 12))
        icon_lbl.bind("<Button-1>", lambda e: self.toggle_phase1())

        text_hdr = tk.Frame(hdr_frame, bg="#FFFFFF", cursor="hand2")
        text_hdr.pack(side=tk.LEFT, fill=tk.X)
        text_hdr.bind("<Button-1>", lambda e: self.toggle_phase1())

        title_lbl = tk.Label(text_hdr, text="Sign → Text", font=("Segoe UI", 16, "bold"), fg="#0F172A", bg="#FFFFFF", cursor="hand2")
        title_lbl.pack(anchor=tk.W)
        title_lbl.bind("<Button-1>", lambda e: self.toggle_phase1())

        sub_lbl = tk.Label(text_hdr, text="Show a hand gesture to see the text.", font=("Segoe UI", 10), fg="#64748B", bg="#FFFFFF", cursor="hand2")
        sub_lbl.pack(anchor=tk.W, pady=(2, 0))
        sub_lbl.bind("<Button-1>", lambda e: self.toggle_phase1())

        # 2. Camera Box / Preview Area (Clickable to launch Phase 1)
        self.camera_box = tk.Canvas(
            card_inner,
            bg="#F1F5F9",
            highlightthickness=1,
            highlightbackground="#E2E8F0",
            cursor="hand2"
        )
        self.camera_box.pack(fill=tk.BOTH, expand=True, pady=(0, 14))
        self.camera_box.bind("<Button-1>", lambda e: self.toggle_phase1())
        self.camera_box.bind("<Enter>", self._on_camera_box_enter)
        self.camera_box.bind("<Leave>", self._on_camera_box_leave)
        self.camera_box.bind("<Configure>", self._draw_camera_box_content)

        # 3. Bottom Text Box ("Detected text will appear here...")
        det_outer = tk.Frame(card_inner, bg="#E2E8F0", bd=1, relief=tk.SOLID)
        det_outer.pack(fill=tk.X)

        self.det_inner = tk.Frame(det_outer, bg="#F8FAFC", padx=14, pady=12)
        self.det_inner.pack(fill=tk.X)

        self.detected_text_lbl = tk.Label(
            self.det_inner,
            text="Detected text will appear here...",
            font=("Segoe UI", 11),
            fg="#94A3B8",
            bg="#F8FAFC",
            anchor=tk.W
        )
        self.detected_text_lbl.pack(fill=tk.X)

    def _on_camera_box_enter(self, event=None):
        if self.phase1_process is None:
            self.camera_box.config(highlightbackground="#3B82F6", bg="#EFF6FF")
            self._draw_camera_box_content()

    def _on_camera_box_leave(self, event=None):
        if self.phase1_process is None:
            self.camera_box.config(highlightbackground="#E2E8F0", bg="#F1F5F9")
            self._draw_camera_box_content()

    def _draw_camera_box_content(self, event=None):
        """Renders the idle or active state inside the Phase 1 camera box."""
        self.camera_box.delete("all")
        w = self.camera_box.winfo_width()
        h = self.camera_box.winfo_height()
        if w < 10 or h < 10:
            return

        cx, cy = w // 2, h // 2

        if self.phase1_process is None:
            # Idle placeholder state
            self.camera_box.create_image(cx, cy - 22, image=self.camera_placeholder_icon)
            self.camera_box.create_text(
                cx, cy + 30,
                text="Camera will start here",
                font=("Segoe UI", 12),
                fill="#64748B"
            )
            self.camera_box.create_text(
                cx, cy + 54,
                text="(Click box to open Phase 1 ISL Recognition)",
                font=("Segoe UI", 9),
                fill="#94A3B8"
            )
        else:
            # Active camera running state
            self.camera_box.create_oval(cx - 50, cy - 50, cx + 50, cy + 50, fill="#DCFCE7", outline="#86EFAC", width=2)
            self.camera_box.create_oval(cx - 20, cy - 20, cx + 20, cy + 20, fill="#22C55E", outline="#16A34A", width=2)

            self.camera_box.create_text(
                cx, cy + 28,
                text="Phase 1 ISL Window Running",
                font=("Segoe UI", 13, "bold"),
                fill="#15803D"
            )
            self.camera_box.create_text(
                cx, cy + 52,
                text="Recognizing gestures from live camera...",
                font=("Segoe UI", 10),
                fill="#166534"
            )
            self.camera_box.create_text(
                cx, cy + 76,
                text="Click here or press 'Q' in camera window to stop",
                font=("Segoe UI", 9, "italic"),
                fill="#64748B"
            )

    # ---------------- Right Card: Phase 2 (Text -> Sign) ----------------

    def _build_phase2_card(self, parent):
        card_outer = tk.Frame(parent, bg="#E2E8F0", bd=1, relief=tk.SOLID)
        card_outer.grid(row=0, column=1, sticky="nsew", padx=(16, 0), pady=6)

        card_inner = tk.Frame(card_outer, bg="#FFFFFF", padx=22, pady=20)
        card_inner.pack(fill=tk.BOTH, expand=True)

        # 1. Header (Icon + Title + Subtitle)
        hdr_frame = tk.Frame(card_inner, bg="#FFFFFF", cursor="hand2")
        hdr_frame.pack(fill=tk.X, pady=(0, 14))
        hdr_frame.bind("<Button-1>", lambda e: self.open_phase2())

        icon_lbl = tk.Label(hdr_frame, image=self.purple_t_icon, bg="#FFFFFF", cursor="hand2")
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 12))
        icon_lbl.bind("<Button-1>", lambda e: self.open_phase2())

        text_hdr = tk.Frame(hdr_frame, bg="#FFFFFF", cursor="hand2")
        text_hdr.pack(side=tk.LEFT, fill=tk.X)
        text_hdr.bind("<Button-1>", lambda e: self.open_phase2())

        title_lbl = tk.Label(text_hdr, text="Text → Sign", font=("Segoe UI", 16, "bold"), fg="#0F172A", bg="#FFFFFF", cursor="hand2")
        title_lbl.pack(anchor=tk.W)
        title_lbl.bind("<Button-1>", lambda e: self.open_phase2())

        sub_lbl = tk.Label(text_hdr, text="Type a word to see the sign gesture.", font=("Segoe UI", 10), fg="#64748B", bg="#FFFFFF", cursor="hand2")
        sub_lbl.pack(anchor=tk.W, pady=(2, 0))
        sub_lbl.bind("<Button-1>", lambda e: self.open_phase2())

        # 2. Input Box ("Enter text...")
        input_outer = tk.Frame(card_inner, bg="#E2E8F0", bd=1, relief=tk.SOLID)
        input_outer.pack(fill=tk.X, pady=(0, 14))

        input_inner = tk.Frame(input_outer, bg="#FFFFFF", padx=12, pady=8)
        input_inner.pack(fill=tk.X)

        self.input_var = tk.StringVar()
        self.entry_box = tk.Entry(
            input_inner,
            textvariable=self.input_var,
            font=("Segoe UI", 11),
            fg="#0F172A",
            bg="#FFFFFF",
            relief=tk.FLAT,
            bd=0
        )
        self.entry_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Placeholder management
        self.placeholder_text = "Enter text..."
        self._set_placeholder()
        self.entry_box.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_box.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_box.bind("<Return>", lambda e: self.on_text_submit())

        # 3. Sign Animation Box / Preview Area (Clickable to open Phase 2)
        self.anim_box = tk.Canvas(
            card_inner,
            bg="#F1F5F9",
            highlightthickness=1,
            highlightbackground="#E2E8F0",
            cursor="hand2"
        )
        self.anim_box.pack(fill=tk.BOTH, expand=True)
        self.anim_box.bind("<Button-1>", lambda e: self.open_phase2())
        self.anim_box.bind("<Enter>", self._on_anim_box_enter)
        self.anim_box.bind("<Leave>", self._on_anim_box_leave)
        self.anim_box.bind("<Configure>", self._on_anim_box_configure)

    def _set_placeholder(self):
        if not self.input_var.get().strip():
            self.entry_box.config(fg="#94A3B8")
            self.input_var.set(self.placeholder_text)

    def _on_entry_focus_in(self, event):
        if self.input_var.get() == self.placeholder_text:
            self.input_var.set("")
            self.entry_box.config(fg="#0F172A")

    def _on_entry_focus_out(self, event):
        if not self.input_var.get().strip():
            self._set_placeholder()

    def _on_anim_box_enter(self, event=None):
        if not self.anim_playing:
            self.anim_box.config(highlightbackground="#8B5CF6", bg="#FAF5FF")
            self._draw_anim_placeholder()

    def _on_anim_box_leave(self, event=None):
        if not self.anim_playing:
            self.anim_box.config(highlightbackground="#E2E8F0", bg="#F1F5F9")
            self._draw_anim_placeholder()

    def _on_anim_box_configure(self, event=None):
        if not self.anim_playing:
            self._draw_anim_placeholder()

    def _draw_anim_placeholder(self):
        self.anim_box.delete("all")
        w = self.anim_box.winfo_width()
        h = self.anim_box.winfo_height()
        if w < 10 or h < 10:
            return
        cx, cy = w // 2, h // 2
        self.anim_box.create_image(cx, cy - 22, image=self.purple_hand_placeholder_icon)
        self.anim_box.create_text(
            cx, cy + 30,
            text="Sign animation will appear here",
            font=("Segoe UI", 12),
            fill="#64748B"
        )
        self.anim_box.create_text(
            cx, cy + 54,
            text="(Click box to open Phase 2 Sign Player)",
            font=("Segoe UI", 9),
            fill="#94A3B8"
        )

    # ---------------- Bottom Footer ----------------

    def _build_footer(self):
        footer_frame = tk.Frame(self.root, bg="#F8FAFC")
        footer_frame.pack(fill=tk.X, pady=(0, 22))

        tk.Label(
            footer_frame,
            text="SignConnect Live   •   Hand Gesture Recognition   •   Text to Sign Language",
            font=("Segoe UI", 10),
            fg="#94A3B8",
            bg="#F8FAFC"
        ).pack(anchor=tk.CENTER)

    # ---------------- Phase 1 Actions ----------------

    def toggle_phase1(self):
        """Starts or stops the Phase 1 ISL Camera Window."""
        if self.phase1_process is not None:
            self.stop_phase1()
        else:
            self.start_phase1()

    def start_phase1(self):
        """Launches camera_test.py as an independent process with stdout monitoring."""
        if not os.path.exists(PHASE1_SCRIPT):
            messagebox.showerror(
                "Phase 1 Not Found",
                f"Could not locate Phase 1 camera script at:\n{PHASE1_SCRIPT}"
            )
            return

        try:
            env = os.environ.copy()
            # Ensure proper python imports inside phase1
            env["PYTHONPATH"] = (
                ROOT_DIR
                + os.pathsep
                + PHASE1_DIR
                + os.pathsep
                + os.path.join(PHASE1_DIR, "phase1")
                + os.pathsep
                + env.get("PYTHONPATH", "")
            )

            self.phase1_user_stopped = False
            self.phase1_process = subprocess.Popen(
                [sys.executable, PHASE1_SCRIPT],
                cwd=PHASE1_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Update UI state to active
            self.camera_box.config(highlightbackground="#22C55E", bg="#F0FDF4")
            self._draw_camera_box_content()

            self.det_inner.config(bg="#FFFFFF")
            self.detected_text_lbl.config(
                text="Live ISL Recognition Active (Listening for signs...)",
                fg="#16A34A",
                font=("Segoe UI", 11, "bold")
            )

            # Start background reader thread
            self.phase1_monitor_thread = threading.Thread(
                target=self._monitor_phase1_process,
                daemon=True
            )
            self.phase1_monitor_thread.start()

        except Exception as e:
            self.phase1_process = None
            messagebox.showerror("Error Launching Phase 1", f"Failed to start Phase 1:\n{e}")
            self._draw_camera_box_content()

    def _monitor_phase1_process(self):
        """Monitors Phase 1 process stdout and handles termination."""
        proc = self.phase1_process
        if proc is None:
            return

        captured_lines = []
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                clean_line = line.strip()
                if clean_line:
                    captured_lines.append(clean_line)

                # If prediction output is detected
                if "PREDICTED:" in clean_line:
                    pred_text = clean_line.split("PREDICTED:", 1)[1].strip()
                    self.root.after(0, lambda t=pred_text: self._update_detected_text(t))
                elif "LOW CONFIDENCE" in clean_line:
                    self.root.after(0, lambda: self._update_detected_text("Detecting... (Low confidence)"))
                elif "Status: Hand Detected" in clean_line:
                    self.root.after(0, lambda: self._update_detected_text("Hand Detected - Analyzing..."))
                elif "Error: Could not open webcam" in clean_line:
                    self.root.after(0, lambda: self._update_detected_text("Camera Warning: No webcam found"))

        except Exception:
            pass
        finally:
            proc.stdout.close()
            return_code = proc.wait()
            was_stopped = getattr(self, "phase1_user_stopped", False)
            self.phase1_user_stopped = False

            if return_code != 0 and not was_stopped:
                err_summary = "\n".join(captured_lines[-6:]) if captured_lines else f"Exited with code {return_code}"
                self.root.after(0, lambda m=err_summary: messagebox.showerror(
                    "Phase 1 Camera Error",
                    f"Phase 1 stopped unexpectedly:\n\n{m}"
                ))

            self.root.after(0, self._on_phase1_exit)

    def _update_detected_text(self, text):
        self.detected_text_lbl.config(
            text=f"Detected: {text}",
            fg="#0F172A",
            font=("Segoe UI", 11, "bold")
        )

    def _on_phase1_exit(self):
        """Called when Phase 1 process finishes or is closed."""
        self.phase1_process = None
        self.camera_box.config(highlightbackground="#E2E8F0", bg="#F1F5F9")
        self._draw_camera_box_content()

        self.det_inner.config(bg="#F8FAFC")
        self.detected_text_lbl.config(
            text="Detected text will appear here...",
            fg="#94A3B8",
            font=("Segoe UI", 11)
        )

    def stop_phase1(self):
        """Stops the running Phase 1 process cleanly."""
        if self.phase1_process is not None:
            self.phase1_user_stopped = True
            try:
                self.phase1_process.terminate()
            except Exception:
                pass
            self.phase1_process = None
            self._on_phase1_exit()

    # ---------------- Phase 2 Actions ----------------

    def open_phase2(self):
        """Opens the full Phase 2 Sign Player window."""
        text = self.input_var.get().strip()
        if not text or text == self.placeholder_text:
            text = "I NEED WATER"

        # Also animate in dashboard
        self.play_embedded_animation(text)

        # Open dedicated Phase 2 window
        if PHASE2_AVAILABLE:
            top = tk.Toplevel(self.root)
            app = SignPlayerApp(top)
            app.entry_var.set(text)
            app.process_input()
        else:
            messagebox.showinfo(
                "Phase 2",
                f"Playing sign animation for '{text}'. Phase 2 module loaded in dashboard."
            )

    def on_text_submit(self):
        """Triggered when pressing Return in the input box."""
        text = self.input_var.get().strip()
        if not text or text == self.placeholder_text:
            return
        self.open_phase2()

    # ---------------- Embedded Dashboard Sign Animator ----------------

    def play_embedded_animation(self, text):
        """Plays real 21-landmark MediaPipe animation inside the right preview box."""
        if not PHASE2_AVAILABLE:
            return

        sequence, unsupported = build_sign_sequence(text)
        if not sequence:
            self._draw_anim_placeholder()
            return

        self.anim_sequence = sequence
        self.anim_index = 0
        self.anim_frame = 0
        self.anim_hold_counter = 0
        self.anim_playing = True

        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
            self.anim_after_id = None

        self._tick_embedded_anim()

    def _tick_embedded_anim(self):
        if not self.anim_playing or not self.anim_sequence:
            return

        curr_label, curr_pose = self.anim_sequence[self.anim_index]
        has_next = self.anim_index < len(self.anim_sequence) - 1

        if has_next:
            next_label, next_pose = self.anim_sequence[self.anim_index + 1]
            if self.anim_frame < self.anim_frames_per_sign:
                t = self.anim_frame / float(self.anim_frames_per_sign)
                pose_to_draw = interpolate(curr_pose, next_pose, t)
                display_label = curr_label
                self.anim_frame += 1
            else:
                pose_to_draw = next_pose
                display_label = next_label
                self.anim_hold_counter += 1
                if self.anim_hold_counter >= self.anim_hold_frames:
                    self.anim_index += 1
                    self.anim_frame = 0
                    self.anim_hold_counter = 0
        else:
            pose_to_draw = curr_pose
            display_label = curr_label
            self.anim_hold_counter += 1
            if self.anim_hold_counter >= self.anim_hold_frames * 2:
                self.anim_index = 0
                self.anim_frame = 0
                self.anim_hold_counter = 0

        self._draw_hand_pose(pose_to_draw, display_label)
        self.anim_after_id = self.root.after(35, self._tick_embedded_anim)

    def _draw_hand_pose(self, pose_21x2, label):
        """Draws the 21 MediaPipe hand landmarks and bone connections."""
        self.anim_box.delete("all")
        w = self.anim_box.winfo_width()
        h = self.anim_box.winfo_height()
        if w < 20 or h < 20:
            return

        xs = [pt[0] for pt in pose_21x2]
        ys = [pt[1] for pt in pose_21x2]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        box_w = max(1e-4, max_x - min_x)
        box_h = max(1e-4, max_y - min_y)

        pad = 42
        avail_w = max(10, w - pad * 2)
        avail_h = max(10, h - pad * 2 - 30)

        scale = min(avail_w / box_w, avail_h / box_h)
        off_x = (w - box_w * scale) / 2.0 - min_x * scale
        off_y = ((h - 20) - box_h * scale) / 2.0 - min_y * scale

        coords = []
        for x, y in pose_21x2:
            coords.append((x * scale + off_x, y * scale + off_y))

        # 1. Draw Bones
        for i, j in HAND_CONNECTIONS:
            x1, y1 = coords[i]
            x2, y2 = coords[j]
            self.anim_box.create_line(x1, y1, x2, y2, fill="#8B5CF6", width=3, capstyle=tk.ROUND)

        # 2. Draw Joints
        for idx, (x, y) in enumerate(coords):
            if idx in FINGERTIPS:
                r = 4.5
                color = "#EC4899"
            elif idx == 0:
                r = 5.0
                color = "#4F46E5"
            else:
                r = 3.5
                color = "#6366F1"
            self.anim_box.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#FFFFFF", width=1)

        # 3. Label overlay at bottom
        self.anim_box.create_rectangle(0, h - 34, w, h, fill="#EDE9FE", outline="")
        self.anim_box.create_text(
            w // 2, h - 17,
            text=f"Signing: {label}",
            font=("Segoe UI", 11, "bold"),
            fill="#5B21B6"
        )

    # ---------------- Application Lifecycle ----------------

    def on_close(self):
        """Clean shutdown of background processes and timers."""
        if self.anim_after_id:
            try:
                self.root.after_cancel(self.anim_after_id)
            except Exception:
                pass
        self.stop_phase1()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SignConnectApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

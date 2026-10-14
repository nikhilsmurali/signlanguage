# phase2/hand_animator.py

"""
Real Hand Animation Module
---------------------------
Animates a 2D hand skeleton using REAL MediaPipe landmark data captured and
labeled in Phase 1 (see phase1/data/raw/*.csv and
phase2/scripts/build_hand_pose_bank.py) - not a video file, and not a
synthetic/guessed hand shape.

For every class Phase 1 was trained on (digits 1-5, letters A-Z, and the
word gesture HELLO), phase2/data/hand_poses.json holds one representative
21-point hand pose, averaged from the actual captured webcam samples for
that class.

Any input text is converted into a sequence of these real poses:
  1. A whole word/phrase that matches a trained class (e.g. "HELLO") uses
     the real captured pose for that gesture directly.
  2. Anything else is fingerspelled letter-by-letter / digit-by-digit using
     the real captured pose for each character (A-Z and 1-5 are covered).
  3. Characters with no captured pose (0, 6-9, punctuation, etc.) are
     skipped and reported so the UI can flag them as unsupported.

The animator then linearly interpolates between consecutive real poses so
the hand moves smoothly from sign to sign, and renders bones + joints on a
Tkinter Canvas using the same 21-point MediaPipe hand skeleton Phase 1
tracks from the webcam.
"""

import json
import os
import re
import tkinter as tk

# --- Load the real pose bank -------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_POSE_BANK_PATH = os.path.join(_BASE_DIR, "data", "hand_poses.json")


def _load_pose_bank():
    if not os.path.exists(_POSE_BANK_PATH):
        raise FileNotFoundError(
            f"Real hand pose bank not found at {_POSE_BANK_PATH}.\n"
            "Run: python phase2/scripts/build_hand_pose_bank.py"
        )
    with open(_POSE_BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


POSE_BANK = _load_pose_bank()  # {"A": [[x,y], ...21 pts...], "HELLO": [...], ...}

# Standard MediaPipe Hands 21-point skeleton connections (same bones Phase 1
# draws live on the webcam feed via mp_hands.HAND_CONNECTIONS).
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (0, 17),                                 # palm base
]
FINGERTIPS = {4, 8, 12, 16, 20}


# --- Text -> real pose sequence ----------------------------------------------

def build_sign_sequence(text):
    """
    Converts input text into an ordered list of (label, pose) using REAL
    captured Phase 1 landmark data.

    Returns:
        (sequence, unsupported)
        sequence: list of (display_label, pose_21x2) in signing order
        unsupported: list of characters that have no captured pose
    """
    cleaned = re.sub(r"[^A-Za-z0-9 ]", "", text.upper())
    words = [w for w in cleaned.split() if w]

    sequence = []
    unsupported = []

    for word in words:
        if word in POSE_BANK:
            sequence.append((word, POSE_BANK[word]))
            continue
        # Fall back to fingerspelling / digit-spelling this word
        for ch in word:
            if ch in POSE_BANK:
                sequence.append((ch, POSE_BANK[ch]))
            else:
                unsupported.append(ch)

    return sequence, unsupported


def interpolate(pose_a, pose_b, t):
    """Linear interpolation between two 21-point real poses at t in [0, 1]."""
    return [
        (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        for a, b in zip(pose_a, pose_b)
    ]


# --- Tkinter renderer ---------------------------------------------------------

class HandAnimatorCanvas(tk.Canvas):
    """
    A Tkinter Canvas that draws and animates a real, landmark-driven 2D hand
    skeleton through a sequence of Phase-1-derived poses.
    """

    def __init__(self, parent, width=440, height=340, bg="#10181a", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg,
                          highlightthickness=0, **kwargs)
        # Update these lines:
        self.canvas_width = width
        self.canvas_height = height

        self.sequence = []
        self._current_pose = None
        self.index = 0
        self.frame = 0
        self.frames_per_sign = 12   # interpolation steps between two signs
        self.hold_frames = 10       # frames to hold each sign before moving on
        self._hold_counter = 0
        self.playing = False
        self._after_id = None

        self.on_label_change = None  # optional callback(label)
        self.on_finished = None      # optional callback()

        self.bone_color = "#5FD4C1"
        self.joint_color = "#F2B84B"
        self.tip_color = "#FF8A65"
        self.bind("<Configure>", self._on_canvas_resize)

    # -- public controls --

    def load_sequence(self, sequence):
        self.pause()
        self.sequence = sequence
        self.index = 0
        self.frame = 0
        self._hold_counter = 0
        if self.sequence:
            self._draw_pose(self.sequence[0][1])
            if self.on_label_change:
                self.on_label_change(self.sequence[0][0])
        else:
            self._current_pose = None
            self.delete("all")

    def set_speed(self, frames_per_sign, hold_frames):
        self.frames_per_sign = max(1, int(frames_per_sign))
        self.hold_frames = max(1, int(hold_frames))

    def play(self):
        if not self.sequence or self.playing:
            return
        if self.index >= len(self.sequence) - 1 and self._hold_counter >= self.hold_frames:
            self.restart()
        self.playing = True
        self._tick()

    def pause(self):
        self.playing = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def restart(self):
        self.pause()
        self.index = 0
        self.frame = 0
        self._hold_counter = 0
        if self.sequence:
            self._draw_pose(self.sequence[0][1])
            if self.on_label_change:
                self.on_label_change(self.sequence[0][0])

    # -- internal animation loop --

    def _tick(self):
        if not self.playing or not self.sequence:
            return

        cur_label, cur_pose = self.sequence[self.index]
        is_last = self.index == len(self.sequence) - 1

        if self._hold_counter < self.hold_frames:
            if self._hold_counter == 0:
                self._draw_pose(cur_pose)
                if self.on_label_change:
                    self.on_label_change(cur_label)
            self._hold_counter += 1
            self._after_id = self.after(30, self._tick)
            return

        if is_last:
            self.playing = False
            if self.on_finished:
                self.on_finished()
            return

        next_label, next_pose = self.sequence[self.index + 1]
        t = self.frame / self.frames_per_sign
        self._draw_pose(interpolate(cur_pose, next_pose, t))
        self.frame += 1

        if self.frame > self.frames_per_sign:
            self.frame = 0
            self._hold_counter = 0
            self.index += 1

        self._after_id = self.after(30, self._tick)

    # -- drawing --

    def _on_canvas_resize(self, event):
        if event.widget is not self:
            return
        if event.width == self.canvas_width and event.height == self.canvas_height:
            return

        self.canvas_width = event.width
        self.canvas_height = event.height
        if self._current_pose is not None:
            self._draw_pose(self._current_pose)

    def _to_canvas(self, pose):
        xs = [p[0] for p in pose]
        ys = [p[1] for p in pose]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span = max(max_x - min_x, max_y - min_y, 1e-6)
        # Update these lines:
        scale = min(self.canvas_width, self.canvas_height) * 0.68 / span
        cx, cy = self.canvas_width / 2, self.canvas_height * 0.56
        return [
            (cx + (x - (min_x + max_x) / 2) * scale,
             cy + (y - (min_y + max_y) / 2) * scale)
            for x, y in pose
        ]

    def _draw_pose(self, pose):
        self._current_pose = pose
        self.delete("all")
        pts = self._to_canvas(pose)
        for a, b in HAND_CONNECTIONS:
            self.create_line(*pts[a], *pts[b], fill=self.bone_color,
                              width=5, capstyle=tk.ROUND)
        for i, (x, y) in enumerate(pts):
            is_tip = i in FINGERTIPS
            r = 7 if is_tip else 5
            color = self.tip_color if is_tip else self.joint_color
            self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
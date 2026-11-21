"""Common machinery for the turn-based games.

Every message on the air looks like   <P><nnn> <body>
  P    one letter that identifies the game (C = chess, F = four in a row ...)
  nnn  the number of this message in the game (1, 2, 3 ...), so repeats and
       our own Moon echoes can be ignored and missed moves noticed
  body the move itself, at most 8 characters (Q65 free text is 13 max)

A game is stored as the list of message bodies sent by both sides and is
rebuilt by replaying them, so every game gets save / resume for free.
"""
import json
import re
import tkinter as tk
from tkinter import messagebox

MAX_TEXT = 13            # Q65 / JT65 / FT8 free-text limit
FREE_TEXT_OK = re.compile(r"^[0-9A-Z +\-./?]*$")


class TurnGame:
    key = "game"                 # internal name
    title = "Game"               # shown to the user
    prefix = "G"                 # first letter of every message
    blurb = ""                   # one-line description in the chooser
    help_text = ""
    sides = ("First", "Second")  # names of the first and second player
    save_name = "eme_game.json"

    def __init__(self, shell):
        self.shell = shell
        self.root = shell.root
        self.my_first = True
        self.reset()

    # ------------------------------------------------------------------
    # things a game fills in
    # ------------------------------------------------------------------
    def reset_position(self):
        """Set up the starting position (called before replaying moves)."""

    def setup_new(self):
        """Extra questions / random set-up for a new game. Return False to
        abort the new game."""
        return True

    def parse(self, rest):
        """Turn the text after 'Pnnn ' into a canonical body, or None."""
        raise NotImplementedError

    def check(self, body, mine):
        """Return an error text if this move is not allowed now, else None."""
        return None

    def apply(self, body, mine):
        """Play a move on the board. Return a short description for the log."""
        raise NotImplementedError

    def pending_body(self):
        """Body of the move the user has prepared (self.pending)."""
        raise NotImplementedError

    def describe_pending(self):
        return self.pending_body()

    def result(self):
        """Text describing the end of the game, or None if still running."""
        return None

    def your_move_hint(self):
        return ""

    def waiting_hint(self):
        return ""

    def extra_save(self):
        return {}

    def extra_load(self, data):
        pass

    def after_receive(self):
        """Called after an opponent's move was played (e.g. automatic replies)."""

    # drawing
    def build(self, frame):
        raise NotImplementedError

    def build_buttons(self, frame):
        pass

    def update_buttons(self):
        pass

    def draw(self):
        pass

    # ------------------------------------------------------------------
    # shared logic
    # ------------------------------------------------------------------
    def reset(self):
        self.history = []        # [["M" or "O", body], ...]
        self.ply = 0
        self.last_text = ""
        self.ended = None
        self.pending = None
        self.reset_position()

    @property
    def my_side(self):
        return self.sides[0] if self.my_first else self.sides[1]

    def side_of(self, mine):
        """Index (0 = first player, 1 = second) of the player who moves."""
        return 0 if mine == self.my_first else 1

    def log(self, text):
        self.shell.log(text)

    def refresh(self):
        self.shell.refresh()

    def over_text(self):
        return self.ended or self.result()

    def my_turn(self):
        return (not self.over_text()) and (self.ply % 2 == 0) == self.my_first

    def can_resign(self):
        return self.my_turn()

    def status_text(self):
        over = self.over_text()
        if over:
            return over
        if self.pending is not None:
            return f"Pending move {self.describe_pending()} - confirm to send"
        if self.my_turn():
            hint = self.your_move_hint()
            return f"You are {self.my_side}. YOUR MOVE." + (f"\n{hint}" if hint else "")
        hint = self.waiting_hint()
        return (f"You are {self.my_side}. Waiting for opponent's move..."
                + (f"\n{hint}" if hint else ""))

    def new_game(self, first_time=False):
        first = messagebox.askyesno(
            "Choose side", f"{self.title}: will YOU move first?\n\n"
            f"(Yes = {self.sides[0]}, moves first. No = {self.sides[1]}.)",
            parent=self.root)
        self.my_first = bool(first)
        self.reset()
        if not self.setup_new():
            return
        if not first_time:
            self.shell.ask_callsigns()
        self.save()
        self.log(f"New {self.title} game started. You are {self.my_side}.")
        self.refresh()

    def cancel(self):
        self.pending = None
        self.refresh()

    def confirm(self):
        if self.pending is None or not self.my_turn():
            return
        body = self.pending_body()
        err = self.check(body, True)
        if err:
            self.log(err)
            return
        self.pending = None
        self.send_body(body)

    def send_body(self, body):
        text = f"{self.prefix}{self.ply + 1:03d} {body}"
        assert len(text) <= MAX_TEXT and FREE_TEXT_OK.match(text), text
        desc = self.apply(body, True)
        self.history.append(["M", body])
        self.ply += 1
        self.last_text = text
        self.save()
        self.log(f"You played {desc}")
        self.shell.transmit()
        over = self.over_text()
        if over:
            self.log(over)
        self.refresh()

    def resign(self):
        if not self.my_turn():
            return
        if not messagebox.askyesno("Resign", "Really resign this game?",
                                   parent=self.root):
            return
        self.pending = None
        self.last_text = f"{self.prefix}{self.ply + 1:03d} RESIGN"
        self.ended = "You resigned - your opponent wins."
        self.save()
        self.log(self.ended)
        self.shell.transmit()
        self.refresh()

    def handle_message(self, clean, snr):
        """Return True if the text was a message for this game."""
        m = re.search(rf"\b{self.prefix}(\d{{3}}) (.+)$", clean)
        if not m:
            return False
        seq, rest = int(m.group(1)), m.group(2)
        resign = rest.startswith("RESIGN")
        body = None if resign else self.parse(rest)
        if body is None and not resign:
            return False
        if self.over_text():
            self.shell.dbg(f"Heard '{clean}' but the game is over - ignored.")
            return True
        if self.my_turn():
            self.shell.dbg(f"Heard '{clean}' but ignored it (it is your turn).")
            return True
        if seq <= self.ply:
            self.shell.dbg(f"Heard '{clean}' - already played / our own echo, ignored.")
            return True
        if seq != self.ply + 1:
            self.log(f"OUT OF SYNC: got move #{seq}, expected #{self.ply + 1}. "
                     "Ask opponent to re-send.")
            return True
        if resign:
            self.log(f"RECEIVED '{clean}' (SNR {snr} dB)")
            self.ended = "Opponent resigned - you win!"
            self.pending = None
            self.save()
            self.log(self.ended)
            self.refresh()
            return True
        err = self.check(body, False)
        if err:
            self.log(f"Received '{clean}' but {err} - ignored.")
            return True
        desc = self.apply(body, False)
        self.history.append(["O", body])
        self.ply += 1
        self.pending = None
        self.log(f"RECEIVED {desc}  ({clean}, SNR {snr} dB)")
        self.save()
        over = self.over_text()
        if over:
            self.log(over)
        self.refresh()
        self.after_receive()
        return True

    # ------------------------------------------------------------------
    # save / load
    # ------------------------------------------------------------------
    def save(self):
        data = {"game": self.key, "my_first": self.my_first,
                "history": self.history, "last_text": self.last_text,
                "ended": self.ended, "extra": self.extra_save()}
        try:
            with open(self.shell.save_path(self.save_name), "w") as fh:
                json.dump(data, fh)
        except OSError as err:
            self.log(f"Could not save the game: {err}")

    def load(self):
        try:
            with open(self.shell.save_path(self.save_name)) as fh:
                data = json.load(fh)
            self.my_first = data["my_first"]
            self.reset()
            self.extra_load(data.get("extra", {}))
            for who, body in data["history"]:
                self.apply(body, who == "M")
                self.history.append([who, body])
                self.ply += 1
            self.last_text = data.get("last_text", "")
            self.ended = data.get("ended")
            self.log(f"Resumed saved {self.title} game ({self.ply} moves played).")
        except Exception as err:
            self.log(f"Could not load saved game: {err!r}")
            self.reset()
        self.refresh()
        if self.my_turn():
            self.after_receive()    # an automatic reply that was not sent yet


def make_canvas(frame, width, height, on_click=None, on_right=None):
    canvas = tk.Canvas(frame, width=width, height=height, highlightthickness=0,
                       bg="#1e1f22")
    canvas.pack()
    if on_click:
        canvas.bind("<Button-1>", on_click)
    if on_right:
        canvas.bind("<Button-3>", on_right)
        canvas.bind("<Button-2>", on_right)     # macOS right button
    return canvas

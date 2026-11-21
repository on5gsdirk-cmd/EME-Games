"""Code Breaker - both players hide a 4-colour code and try to crack the
other's code in fewer guesses.

Every message carries your next guess AND the score of the opponent's last
guess, which this program works out from your secret code automatically:
    K001 1234       first guess (colours 1-6)
    K002 5566 12    guess 5566; your guess 1234 scored 1 black, 2 white
    K011 ---- 40    no more guesses: your last guess scored 4 black
The first player always sends the closing "----" message, so both players
get exactly the same number of guesses.
"""
import random
import re
from tkinter import messagebox, simpledialog

from .base import TurnGame, make_canvas

COLOURS = ["#e04848", "#3fbf5f", "#3f7fe0", "#f2d04c", "#b05fe0", "#f08a3c"]
NAMES = ["red", "green", "blue", "yellow", "purple", "orange"]
LEN = 4
MAX_GUESSES = 10


def score(secret, guess):
    black = sum(a == b for a, b in zip(secret, guess))
    common = sum(min(secret.count(d), guess.count(d)) for d in set(guess))
    return black, common - black


class CodeBreaker(TurnGame):
    key = "codebreaker"
    title = "Code Breaker"
    prefix = "K"
    blurb = "Crack your opponent's secret colour code in fewer guesses. (Mastermind-style)"
    sides = ("First guesser", "Second guesser")
    save_name = "eme_code_breaker.json"
    help_text = r"""## Code Breaker
Each player hides a secret code of 4 colours, chosen from 6 (colours may repeat). Players take turns guessing the other's code. Each guess is scored: a black peg for every colour in exactly the right place, a white peg for every right colour in the wrong place. Your program scores your opponent's guesses against your code automatically and sends the score along with your next guess, so nobody can make a scoring mistake.
Whoever cracks the code in fewer guesses wins. Both players always get the same number of guesses: if the first player cracks the code, the second player still gets one last guess to equal it. After 10 guesses each without a winner the game is a draw.
At a new game you can type your own secret code (digits 1-6) or let the program pick one. Click the coloured pegs at the bottom to build your guess (click a peg in your guess row to remove it), then press "Confirm & Send".

## What goes over the air (code breaker)
    K001 1234       first guess: colours 1,2,3,4 (1 red, 2 green, 3 blue, 4 yellow,
                    5 purple, 6 orange)
    K002 5566 12    guess 5566, and your last guess scored 1 black and 2 white
    K011 ---- 40    no more guesses; your last guess scored 4 black (cracked!)
    K006 RESIGN     resign
"""
    secret = None

    def reset_position(self):
        self.my_guesses = []     # [guess, (black, white) or None]
        self.opp_guesses = []    # guesses at my code
        self.closed = False      # the closing "----" message was played
        self.building = ""

    def setup_new(self):
        text = simpledialog.askstring(
            "Your secret code", "Type your secret code: 4 digits 1-6\n"
            "(1 red, 2 green, 3 blue, 4 yellow, 5 purple, 6 orange)\n\n"
            "Leave empty or Cancel for a random code.", parent=self.root)
        text = "".join(ch for ch in (text or "") if ch in "123456")
        if len(text) != LEN:
            text = "".join(random.choice("123456") for _ in range(LEN))
            messagebox.showinfo("Secret code", "A random secret code was chosen "
                                "for you; it is shown at the top right.",
                                parent=self.root)
        self.secret = text
        return True

    def extra_save(self):
        return {"secret": self.secret}

    def extra_load(self, data):
        self.secret = data.get("secret") or self.secret

    # ---------------- protocol ----------------
    def parse(self, rest):
        m = re.match(r"([1-6]{4}|----)(?: ([0-4])([0-4]))?(?![0-9A-Z])", rest)
        if not m:
            return None
        return m.group(1) + (f" {m.group(2)}{m.group(3)}" if m.group(2) else "")

    def check(self, body, mine):
        if not mine and self.ply > 0 and " " not in body:
            return "the message lacks the score of your last guess"
        return None

    def apply(self, body, mine):
        parts = body.split()
        guess = parts[0]
        desc = []
        if len(parts) > 1 and not mine and self.my_guesses:
            b, w = int(parts[1][0]), int(parts[1][1])
            self.my_guesses[-1][1] = (b, w)
            desc.append(f"your guess {self.my_guesses[-1][0]} scored "
                        f"{b} black, {w} white" + (" - CRACKED!" if b == LEN else ""))
        if guess == "----":
            self.closed = True
            desc.append("no more guesses")
        elif mine:
            self.my_guesses.append([guess, None])
            desc.append(f"guess {guess}")
        else:
            self.opp_guesses.append(guess)
            b, w = score(self.secret, guess)
            desc.append(f"their guess {guess} ({b} black, {w} white)")
        return "; ".join(desc)

    def owed_score(self):
        if self.history and self.history[-1][0] == "O" and self.opp_guesses:
            b, w = score(self.secret, self.opp_guesses[-1])
            return f"{b}{w}"
        return None

    def pending_body(self):
        s = self.owed_score()
        return self.pending + (f" {s}" if s else "")

    def solved_at(self, guesses):
        """1-based number of the guess that cracked the code, or None."""
        for i, g in enumerate(guesses):
            if g == self.secret if isinstance(g, str) else (g[1] and g[1][0] == LEN):
                return i + 1
        return None

    def must_close(self):
        """First player only: both have had the same number of guesses
        and someone has cracked the code (or the guesses are used up)."""
        if not self.my_first or self.closed or not self.my_turn():
            return False
        n = len(self.my_guesses)
        if n == 0 or len(self.opp_guesses) != n:
            return False
        return (self.solved_at(self.my_guesses) is not None
                or self.solved_at(self.opp_guesses) is not None
                or n >= MAX_GUESSES)

    def after_receive(self):
        if self.must_close():
            self.log("Both sides have had the same number of guesses - "
                     "sending the closing message.")
            self.send_body("---- " + self.owed_score())

    def result(self):
        if not self.closed:
            return None
        me = self.solved_at(self.my_guesses)
        them = self.solved_at(self.opp_guesses)
        if me and (not them or me < them):
            return f"You cracked the code in {me} guesses - YOU WIN!"
        if them and (not me or them < me):
            return f"Your opponent cracked your code in {them} guesses - you lose."
        if me:
            return f"Both cracked the code in {me} guesses - it's a draw."
        return "Nobody cracked the code - it's a draw."

    def can_resign(self):
        return self.my_turn() and not self.must_close()

    def your_move_hint(self):
        if not self.my_first and self.solved_at(self.opp_guesses):
            return "Your opponent CRACKED your code! This is your last guess to tie."
        return f"Guess {len(self.my_guesses) + 1} of {MAX_GUESSES}."

    # ---------------- widgets ----------------
    PEG, ROW = 26, 34

    def build(self, frame):
        self.canvas = make_canvas(frame, 640, 60 + MAX_GUESSES * self.ROW + 110,
                                  self.on_click)

    def peg(self, x, y, digit, r=None, outline="#111"):
        r = r or self.PEG // 2
        cv = self.canvas
        if digit:
            cv.create_oval(x - r, y - r, x + r, y + r,
                           fill=COLOURS[int(digit) - 1], outline=outline, width=2)
            cv.create_text(x, y, text=digit, fill="#111",
                           font=("Segoe UI", 9, "bold"))
        else:
            cv.create_oval(x - r, y - r, x + r, y + r, fill="#2b2d31",
                           outline="#3a3c42")

    def score_pegs(self, x, y, sc):
        if not sc:
            self.canvas.create_text(x + 18, y, text="?", fill="#ffb454",
                                    font=("Segoe UI", 11, "bold"))
            return
        b, w = sc
        cols = ["#111111"] * b + ["#f4f4f4"] * w + [None] * (LEN - b - w)
        for i, col in enumerate(cols):
            px, py = x + (i % 2) * 14, y - 7 + (i // 2) * 14
            self.canvas.create_oval(px - 5, py - 5, px + 5, py + 5,
                                    fill=col or "#2b2d31",
                                    outline="#8a8d93" if col else "#3a3c42")

    def board_rows(self, x0, guesses, scores, title):
        cv = self.canvas
        cv.create_text(x0 + 90, 20, text=title, fill="#4ea1ff",
                       font=("Segoe UI", 12, "bold"))
        for i in range(MAX_GUESSES):
            y = 60 + i * self.ROW
            cv.create_text(x0, y, text=str(i + 1), fill="#8a8d93",
                           font=("Segoe UI", 9))
            g = guesses[i] if i < len(guesses) else None
            for j in range(LEN):
                self.peg(x0 + 24 + j * 32, y, g[j] if g else None)
            if g:
                self.score_pegs(x0 + 24 + LEN * 32, y, scores[i])

    def draw(self):
        cv = self.canvas
        cv.delete("all")
        self.board_rows(20, [g for g, _ in self.my_guesses],
                        [s for _, s in self.my_guesses], "Your guesses")
        self.board_rows(340, self.opp_guesses,
                        [score(self.secret, g) for g in self.opp_guesses],
                        "Their guesses at your code")
        cv.create_line(318, 10, 318, 60 + MAX_GUESSES * self.ROW,
                       fill="#3a3c42")
        y = 60 + MAX_GUESSES * self.ROW + 10
        cv.create_text(340, y + 4, text="Your code:", anchor="w", fill="#8a8d93",
                       font=("Segoe UI", 10))
        for j, d in enumerate(self.secret or ""):
            self.peg(440 + j * 32, y + 4, d)
        # guess being built + palette
        cur = self.pending or self.building
        y = 60 + MAX_GUESSES * self.ROW + 10
        cv.create_text(20, y + 4, text="Next guess:", anchor="w", fill="#8a8d93",
                       font=("Segoe UI", 10))
        for j in range(LEN):
            self.peg(120 + j * 32, y + 4, cur[j] if j < len(cur) else None,
                     outline="#7fd67f" if self.pending else "#111")
        y += 50
        for k in range(6):
            self.peg(32 + k * 44, y, str(k + 1), r=17)

    def on_click(self, event):
        if not self.my_turn() or self.must_close():
            return
        top = 60 + MAX_GUESSES * self.ROW + 10
        # palette
        if abs(event.y - (top + 50)) <= 18:
            k = (event.x - 32 + 22) // 44
            if 0 <= k < 6 and len(self.building) < LEN and self.pending is None:
                self.building += str(k + 1)
        # remove a peg from the guess being built
        elif abs(event.y - (top + 4)) <= 14 and 104 <= event.x <= 104 + LEN * 32:
            j = (event.x - 104) // 32
            cur = self.pending or self.building
            if j < len(cur):
                self.building = cur[:j] + cur[j + 1:]
                self.pending = None
        else:
            return
        if len(self.building) == LEN:
            self.pending = self.building
        self.refresh()

    def cancel(self):
        self.pending = None
        self.building = ""
        self.refresh()

    def send_body(self, body):
        self.building = ""
        super().send_body(body)

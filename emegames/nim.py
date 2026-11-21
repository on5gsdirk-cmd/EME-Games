"""Nim - take sticks from one pile; who takes the last one wins (or loses)."""
import re
from tkinter import messagebox, simpledialog

from .base import TurnGame, make_canvas

PILES = "ABCD"


class Nim(TurnGame):
    key = "nim"
    title = "Nim"
    prefix = "N"
    blurb = "Take sticks from one pile per turn. The first player picks the piles and rule."
    sides = ("Starter", "Second")
    save_name = "eme_nim.json"
    help_text = r"""## Nim
There are 2 to 4 piles (A-D) of 1 to 9 sticks. On your turn take one or more sticks from ONE pile. In the normal game whoever takes the last stick WINS; in the "misere" variant whoever takes the last stick LOSES.
The player who moves first chooses the piles and the rule when starting a new game; they travel with the first move, so the second player does not need to set anything up.
Click a stick: it and every stick to its right in that pile will be taken. Then press "Confirm & Send".

## What goes over the air (nim)
    N001 B3 1357L   first move: take 3 from pile B; the game has piles 1,3,5,7 and
                    the rule L (last stick loses) or W (last stick wins)
    N002 D2         take 2 from pile D
    N009 RESIGN     resign
"""
    STICK_W, ROW_H = 40, 80
    setup = None

    def reset_position(self):
        self.piles = None
        self.start_piles = None
        self.rule = None
        self.last = None

    def setup_new(self):
        self.setup = None
        if not self.my_first:
            return True
        text = simpledialog.askstring(
            "Nim set-up", "Pile sizes (2-4 piles of 1-9 sticks), e.g. 1 3 5 7:",
            initialvalue="3 4 5", parent=self.root)
        if text is None:
            text = "3 4 5"
        sizes = [int(ch) for ch in text if ch.isdigit() and ch != "0"]
        if not 2 <= len(sizes) <= 4:
            messagebox.showinfo("Nim", "Using piles 3 4 5.", parent=self.root)
            sizes = [3, 4, 5]
        lose = messagebox.askyesno(
            "Nim rule", "Misere rule: whoever takes the LAST stick LOSES?\n\n"
            "Yes = last stick loses (classic misere)\nNo = last stick wins",
            parent=self.root)
        self.setup = ("".join(map(str, sizes)), "L" if lose else "W")
        self.start(*self.setup)
        return True

    def start(self, sizes, rule):
        self.start_piles = sizes
        self.piles = [int(ch) for ch in sizes]
        self.rule = rule

    def extra_save(self):
        return {"setup": self.setup}

    def extra_load(self, data):
        self.setup = data.get("setup")
        if self.setup:
            self.start(*self.setup)

    def parse(self, rest):
        m = re.match(r"([A-D])([1-9])(?: ([1-9]{2,4})([LW]))?(?![0-9A-Z])", rest)
        if not m:
            return None
        body = m.group(1) + m.group(2)
        if m.group(3):
            body += f" {m.group(3)}{m.group(4)}"
        return body

    def check(self, body, mine):
        if self.ply == 0 and not mine and " " not in body:
            return "the first move does not carry the pile set-up"
        piles = self.piles
        if " " in body and self.ply == 0:
            piles = [int(ch) for ch in body.split()[1][:-1]]
        if piles is None:
            return "the piles are not set up"
        i, n = PILES.index(body[0]), int(body[1])
        if i >= len(piles) or n > piles[i]:
            return f"pile {body[0]} does not have {n} sticks"
        return None

    def apply(self, body, mine):
        if " " in body and self.ply == 0:
            spec = body.split()[1]
            self.start(spec[:-1], spec[-1])
            if not mine:
                self.setup = (spec[:-1], spec[-1])
                self.log(f"Piles {' '.join(spec[:-1])}, rule: last stick "
                         f"{'LOSES' if spec[-1] == 'L' else 'WINS'}.")
        i, n = PILES.index(body[0]), int(body[1])
        self.piles[i] -= n
        self.last = (i, n)
        return f"{n} from pile {body[0]}"

    def pending_body(self):
        i, n = self.pending
        body = f"{PILES[i]}{n}"
        if self.ply == 0 and self.setup:
            body += f" {self.setup[0]}{self.setup[1]}"
        return body

    def describe_pending(self):
        i, n = self.pending
        return f"take {n} from pile {PILES[i]}"

    def result(self):
        if not self.piles or any(self.piles):
            return None
        i_took_last = self.history[-1][0] == "M" if self.history else False
        win = i_took_last == (self.rule == "W")
        who = "You" if i_took_last else "Your opponent"
        return f"{who} took the last stick - " + ("YOU WIN!" if win else "you lose.")

    def rule_text(self):
        if not self.rule:
            return ""
        return "Rule: last stick " + ("LOSES" if self.rule == "L" else "WINS")

    def your_move_hint(self):
        return self.rule_text()

    def waiting_hint(self):
        if self.piles is None:
            return "The piles and rule arrive with your opponent's first move."
        return self.rule_text()

    def build(self, frame):
        self.canvas = make_canvas(frame, 60 + 9 * self.STICK_W + 20,
                                  4 * self.ROW_H + 20, self.on_click)

    def on_click(self, event):
        if not self.my_turn() or not self.piles:
            return
        i = (event.y - 10) // self.ROW_H
        j = (event.x - 60) // self.STICK_W
        if 0 <= i < len(self.piles) and 0 <= j < self.piles[i]:
            self.pending = (i, self.piles[i] - j)
            self.refresh()

    def draw(self):
        cv = self.canvas
        cv.delete("all")
        if not self.piles:
            cv.create_text(250, 150, text="Waiting for the first move\n"
                           "(it brings the piles)", fill="#8a8d93",
                           font=("Segoe UI", 14), justify="center")
            return
        for i, n in enumerate(self.piles):
            y0 = 10 + i * self.ROW_H
            cv.create_text(30, y0 + self.ROW_H // 2, text=PILES[i],
                           fill="#4ea1ff", font=("Segoe UI", 18, "bold"))
            cv.create_text(30, y0 + self.ROW_H // 2 + 24, text=str(n),
                           fill="#8a8d93", font=("Segoe UI", 9))
            total = int(self.start_piles[i])
            for j in range(total):
                x0 = 60 + j * self.STICK_W + 12
                if j < n:
                    take = (self.pending and self.pending[0] == i
                            and j >= n - self.pending[1])
                    fill = "#7fd67f" if take else "#d9a35b"
                    cv.create_rectangle(x0, y0 + 10, x0 + 14, y0 + self.ROW_H - 10,
                                        fill=fill, outline="")
                else:
                    cv.create_rectangle(x0, y0 + 10, x0 + 14, y0 + self.ROW_H - 10,
                                        fill="", outline="#3a3c42", dash=(2, 3))

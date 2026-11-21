"""Simple open-information board games: Four in a Row, Tic-Tac-Toe, Reversi."""
import re
import tkinter as tk

from .base import TurnGame, make_canvas

MINE_COL = "#e04848"      # first player's pieces (red / black)
THEIR_COL = "#f2c94c"     # second player's pieces (yellow / white)


# ======================================================================
# Four in a Row
# ======================================================================
class FourInARow(TurnGame):
    key = "four"
    title = "Four in a Row"
    prefix = "F"
    blurb = "Drop discs in a 7 x 6 grid; four in a line wins. (Vier op een rij)"
    sides = ("Red", "Yellow")
    save_name = "eme_four_in_a_row.json"
    COLS, ROWS, CELL = 7, 6, 72
    help_text = r"""## Four in a Row
Players take turns dropping a disc into one of the 7 columns; it falls to the lowest free spot. The first to get four of their own discs in a row - horizontally, vertically or diagonally - wins. A full board is a draw. Red moves first.
Click a column to choose it, then press "Confirm & Send".

## What goes over the air (four in a row)
    F007 4          move number 7: a disc in column 4 (columns 1-7, left to right)
    F008 RESIGN     resign
"""

    def reset_position(self):
        self.grid = [[] for _ in range(self.COLS)]   # bottom-up list of side
        self.last = None

    def parse(self, rest):
        m = re.match(r"([1-7])\b", rest)
        return m.group(1) if m else None

    def check(self, body, mine):
        if len(self.grid[int(body) - 1]) >= self.ROWS:
            return f"column {body} is full"
        return None

    def apply(self, body, mine):
        c = int(body) - 1
        self.grid[c].append(self.side_of(mine))
        self.last = (c, len(self.grid[c]) - 1)
        return f"column {body}"

    def pending_body(self):
        return str(self.pending + 1)

    def describe_pending(self):
        return f"column {self.pending + 1}"

    def cell(self, c, r):
        if not (0 <= c < self.COLS and 0 <= r < len(self.grid[c])):
            return None
        return self.grid[c][r]

    def winner_line(self):
        for c in range(self.COLS):
            for r in range(len(self.grid[c])):
                s = self.grid[c][r]
                for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    line = [(c + i * dc, r + i * dr) for i in range(4)]
                    if all(self.cell(x, y) == s for x, y in line):
                        return s, line
        return None, None

    def result(self):
        side, _ = self.winner_line()
        if side is not None:
            mine = side == (0 if self.my_first else 1)
            return ("Four in a row - YOU WIN!" if mine
                    else "Four in a row for your opponent - you lose.")
        if all(len(col) >= self.ROWS for col in self.grid):
            return "The board is full - it's a draw."
        return None

    def build(self, frame):
        self.canvas = make_canvas(frame, self.COLS * self.CELL,
                                  self.ROWS * self.CELL + 28, self.on_click)

    def on_click(self, event):
        if not self.my_turn():
            return
        c = event.x // self.CELL
        if 0 <= c < self.COLS and len(self.grid[c]) < self.ROWS:
            self.pending = c
            self.refresh()

    def draw(self):
        cv, S = self.canvas, self.CELL
        cv.delete("all")
        cv.create_rectangle(0, 0, self.COLS * S, self.ROWS * S,
                            fill="#2456c4", outline="")
        _, line = self.winner_line()
        line = line or []
        colours = (MINE_COL, THEIR_COL)
        for c in range(self.COLS):
            for r in range(self.ROWS):
                x0, y0 = c * S + 6, (self.ROWS - 1 - r) * S + 6
                s = self.cell(c, r)
                fill = colours[s] if s is not None else "#1e1f22"
                outline = ""
                width = 1
                if (c, r) in line:
                    outline, width = "white", 4
                elif (c, r) == self.last:
                    outline, width = "#9fe39f", 3
                cv.create_oval(x0, y0, x0 + S - 12, y0 + S - 12, fill=fill,
                               outline=outline, width=width)
            cv.create_text(c * S + S // 2, self.ROWS * S + 14, text=str(c + 1),
                           fill="#8a8d93", font=("Segoe UI", 11, "bold"))
        if self.pending is not None:
            c, r = self.pending, len(self.grid[self.pending])
            x0, y0 = c * S + 6, (self.ROWS - 1 - r) * S + 6
            cv.create_oval(x0, y0, x0 + S - 12, y0 + S - 12,
                           fill=colours[0 if self.my_first else 1],
                           stipple="gray50", outline="#7fd67f", width=3)


# ======================================================================
# Tic-Tac-Toe
# ======================================================================
class TicTacToe(TurnGame):
    key = "tictactoe"
    title = "Tic-Tac-Toe"
    prefix = "T"
    blurb = "Three in a row on a 3 x 3 grid. Quick test game. (Boter-kaas-en-eieren)"
    sides = ("X", "O")
    save_name = "eme_tictactoe.json"
    CELL = 140
    help_text = r"""## Tic-Tac-Toe
Players take turns placing their mark (X moves first) on a 3 x 3 grid. Three in a row - horizontally, vertically or diagonally - wins. A short game that is handy for testing your set-up before a long chess match.

## What goes over the air (tic-tac-toe)
    T003 B2         move number 3: centre square (columns A-C, rows 1-3 from the top)
    T004 RESIGN     resign
"""
    def reset_position(self):
        self.board = {}

    def parse(self, rest):
        m = re.match(r"([A-C][1-3])\b", rest)
        return m.group(1) if m else None

    @staticmethod
    def pos(body):
        return "ABC".index(body[0]), int(body[1]) - 1

    def check(self, body, mine):
        return f"{body} is already taken" if self.pos(body) in self.board else None

    def apply(self, body, mine):
        self.board[self.pos(body)] = self.side_of(mine)
        return body

    def pending_body(self):
        c, r = self.pending
        return f"{'ABC'[c]}{r + 1}"

    def winner_line(self):
        lines = [[(c, r) for c in range(3)] for r in range(3)]
        lines += [[(c, r) for r in range(3)] for c in range(3)]
        lines += [[(i, i) for i in range(3)], [(i, 2 - i) for i in range(3)]]
        for line in lines:
            vals = [self.board.get(p) for p in line]
            if vals[0] is not None and vals.count(vals[0]) == 3:
                return vals[0], line
        return None, None

    def result(self):
        side, _ = self.winner_line()
        if side is not None:
            return ("Three in a row - YOU WIN!" if side == (0 if self.my_first else 1)
                    else "Three in a row for your opponent - you lose.")
        if len(self.board) == 9:
            return "Board full - it's a draw."
        return None

    def build(self, frame):
        self.canvas = make_canvas(frame, 3 * self.CELL + 30, 3 * self.CELL + 30,
                                  self.on_click)

    def on_click(self, event):
        if not self.my_turn():
            return
        c, r = (event.x - 30) // self.CELL, (event.y - 30) // self.CELL
        if 0 <= c < 3 and 0 <= r < 3 and (c, r) not in self.board:
            self.pending = (c, r)
            self.refresh()

    def draw(self):
        cv, S, o = self.canvas, self.CELL, 30
        cv.delete("all")
        _, line = self.winner_line()
        line = line or []
        for i in range(3):
            cv.create_text(o + i * S + S // 2, 15, text="ABC"[i], fill="#8a8d93",
                           font=("Segoe UI", 11, "bold"))
            cv.create_text(15, o + i * S + S // 2, text=str(i + 1), fill="#8a8d93",
                           font=("Segoe UI", 11, "bold"))
        for c in range(3):
            for r in range(3):
                x0, y0 = o + c * S, o + r * S
                fill = "#2b2d31"
                if (c, r) == self.pending:
                    fill = "#2f4f2f"
                elif (c, r) in line:
                    fill = "#3d4a63"
                cv.create_rectangle(x0 + 3, y0 + 3, x0 + S - 3, y0 + S - 3,
                                    fill=fill, outline="")
                side = self.board.get((c, r))
                if (c, r) == self.pending:
                    side = 0 if self.my_first else 1
                if side is None:
                    continue
                pad = 30
                if side == 0:
                    for a, b in (((x0 + pad, y0 + pad), (x0 + S - pad, y0 + S - pad)),
                                 ((x0 + S - pad, y0 + pad), (x0 + pad, y0 + S - pad))):
                        cv.create_line(*a, *b, fill=MINE_COL, width=10,
                                       capstyle="round")
                else:
                    cv.create_oval(x0 + pad, y0 + pad, x0 + S - pad, y0 + S - pad,
                                   outline=THEIR_COL, width=10)


# ======================================================================
# Reversi
# ======================================================================
DIRS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


class Reversi(TurnGame):
    key = "reversi"
    title = "Reversi"
    prefix = "R"
    blurb = "Outflank and flip your opponent's discs on an 8 x 8 board."
    sides = ("Black", "White")
    save_name = "eme_reversi.json"
    SQ = 64
    help_text = r"""## Reversi
Black moves first. Place a disc so that one or more straight lines (horizontal, vertical or diagonal) of your opponent's discs are enclosed between the new disc and another of your own; those discs are flipped to your colour. Legal moves are marked with a small dot. If you have no legal move you must pass (the "Pass" button becomes available). The game ends when neither side can move; the player with the most discs wins.

## What goes over the air (reversi)
    R005 D3         move number 5: a disc on D3 (columns A-H, rows 1-8 from the top)
    R018 PASS       no legal move, pass
    R019 RESIGN     resign
"""

    def reset_position(self):
        self.board = {(3, 3): 1, (4, 4): 1, (3, 4): 0, (4, 3): 0}
        self.last = None

    def parse(self, rest):
        m = re.match(r"(PASS|[A-H][1-8])\b", rest)
        return m.group(1) if m else None

    def flips(self, pos, side):
        if pos in self.board:
            return []
        out = []
        for dx, dy in DIRS:
            run = []
            x, y = pos[0] + dx, pos[1] + dy
            while self.board.get((x, y)) == 1 - side:
                run.append((x, y))
                x, y = x + dx, y + dy
            if run and self.board.get((x, y)) == side:
                out += run
        return out

    def legal(self, side):
        return [(x, y) for x in range(8) for y in range(8)
                if self.flips((x, y), side)]

    @staticmethod
    def pos(body):
        return "ABCDEFGH".index(body[0]), int(body[1]) - 1

    def to_move(self):
        return self.ply % 2      # 0 = black (first player)

    def check(self, body, mine):
        side = self.to_move()
        if body == "PASS":
            return "a pass is only allowed without legal moves" if self.legal(side) else None
        return None if self.flips(self.pos(body), side) else f"{body} is not a legal move"

    def apply(self, body, mine):
        side = self.side_of(mine)
        if body == "PASS":
            self.last = None
            return "PASS"
        p = self.pos(body)
        flipped = self.flips(p, side)
        for q in flipped + [p]:
            self.board[q] = side
        self.last = p
        return f"{body} ({len(flipped)} flipped)"

    def pending_body(self):
        if self.pending == "PASS":
            return "PASS"
        x, y = self.pending
        return f"{'ABCDEFGH'[x]}{y + 1}"

    def counts(self):
        vals = list(self.board.values())
        return vals.count(0), vals.count(1)

    def result(self):
        if self.legal(0) or self.legal(1):
            return None
        b, w = self.counts()
        mine, theirs = (b, w) if self.my_first else (w, b)
        score = f"{mine}-{theirs}"
        if mine > theirs:
            return f"Game over - YOU WIN {score}!"
        if mine < theirs:
            return f"Game over - you lose {score}."
        return f"Game over - draw {score}."

    def your_move_hint(self):
        if not self.legal(self.to_move()):
            return "You have no legal move: press Pass."
        return ""

    def status_text(self):
        b, w = self.counts()
        return super().status_text() + f"\nDiscs: Black {b} - White {w}"

    def build(self, frame):
        self.canvas = make_canvas(frame, 8 * self.SQ + 24, 8 * self.SQ + 24,
                                  self.on_click)

    def build_buttons(self, frame):
        self.pass_btn = tk.Button(frame, text="Pass (no legal move)",
                                  command=self.do_pass, state="disabled")
        self.pass_btn.pack(fill="x", pady=2)

    def update_buttons(self):
        ok = self.my_turn() and not self.legal(self.to_move())
        self.pass_btn.config(state="normal" if ok else "disabled")

    def do_pass(self):
        self.pending = "PASS"
        self.refresh()

    def on_click(self, event):
        if not self.my_turn():
            return
        x, y = (event.x - 24) // self.SQ, (event.y - 24) // self.SQ
        if 0 <= x < 8 and 0 <= y < 8 and self.flips((x, y), self.to_move()):
            self.pending = (x, y)
            self.refresh()

    def draw(self):
        cv, S, o = self.canvas, self.SQ, 24
        cv.delete("all")
        colours = ("#111111", "#f4f4f4")
        hints = self.legal(self.to_move()) if self.my_turn() else []
        pend = self.pending if isinstance(self.pending, tuple) else None
        preview = self.flips(pend, self.to_move()) if pend else []
        for i in range(8):
            cv.create_text(o + i * S + S // 2, 12, text="ABCDEFGH"[i],
                           fill="#8a8d93", font=("Segoe UI", 10, "bold"))
            cv.create_text(12, o + i * S + S // 2, text=str(i + 1),
                           fill="#8a8d93", font=("Segoe UI", 10, "bold"))
        for x in range(8):
            for y in range(8):
                x0, y0 = o + x * S, o + y * S
                fill = "#2f7d4a" if (x, y) != pend else "#4fa36a"
                cv.create_rectangle(x0, y0, x0 + S, y0 + S, fill=fill,
                                    outline="#1d5631")
                side = self.board.get((x, y))
                if (x, y) == pend:
                    side = self.to_move()
                if side is not None:
                    if (x, y) in preview:
                        side = self.to_move()
                    outline = "#f6f669" if (x, y) == self.last else "#333"
                    cv.create_oval(x0 + 6, y0 + 6, x0 + S - 6, y0 + S - 6,
                                   fill=colours[side], outline=outline,
                                   width=3 if (x, y) == self.last else 1)
                    if (x, y) in preview:
                        cv.create_oval(x0 + S // 2 - 4, y0 + S // 2 - 4,
                                       x0 + S // 2 + 4, y0 + S // 2 + 4,
                                       fill="#7fd67f", outline="")
                elif (x, y) in hints and not pend:
                    cv.create_oval(x0 + S // 2 - 5, y0 + S // 2 - 5,
                                   x0 + S // 2 + 5, y0 + S // 2 + 5,
                                   fill="#1d5631", outline="")

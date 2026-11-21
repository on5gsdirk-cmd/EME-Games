"""Chess - the original EME Chess by W4ATC, unchanged on the air.

Messages are identical to eme_chess.py, so a player using this program can
play against a player still using the original script."""
import json
import re
import tkinter as tk
from tkinter import messagebox, simpledialog

import chess

SQ = 72                     # size of one board square in pixels
LIGHT = "#f0d9b5"
DARK = "#b58863"
SELECT = "#f6f669"
PENDING = "#7fd67f"
LASTMOVE = "#cdd26a"

GLYPH = {"p": "♟", "n": "♞", "b": "♝",
         "r": "♜", "q": "♛", "k": "♚"}

# Message formats on the air (13 characters max in Q65 free text):
#   C007 E2E4       a move (ply number 007)
#   C008 XE7E5      a move that also DECLINES a draw offer
#   C007 E2E4 D?    a move with a draw offer attached
#   C008 DRAW.      accept a draw offer (sent instead of a move)
#   C008 RESIGN     resign (sent instead of a move)
MOVE_RE = re.compile(r"\bC(\d{3}) (X?)([A-H][1-8][A-H][1-8][QRBN]?)( D\?)?")
CMD_RE = re.compile(r"\bC(\d{3}) (RESIGN|DRAW\.)")

HELP = r"""## Chess
Click one of your pieces, then click its destination. Illegal moves are refused. Castling: move the king two squares. Promotion: you will be asked which piece you want. White moves first.

## Draws and resigning
- "Offer draw" is available while you are waiting for your opponent. It re-sends your last move with a draw offer attached.
- If your opponent offers a draw, "Accept draw offer" becomes available. To decline, simply play a move; the program marks it with an X so your opponent knows.
- "Resign" is available on your turn and is sent in place of a move.

## What goes over the air (chess)
    C007 E2E4       move number 7: e2 to e4
    C012 E7E8Q      a pawn promoting to a queen
    C007 E2E4 D?    a move with a draw offer
    C008 XE7E5      a move that declines a draw offer
    C008 DRAW.      accept a draw
    C008 RESIGN     resign
These are exactly the same as in the original eme_chess.py, so you can play against someone who still uses that script.
"""


class ChessGame:
    key = "chess"
    title = "Chess"
    prefix = "C"
    blurb = "The original EME Chess (W4ATC). Compatible with eme_chess.py."
    help_text = HELP
    save_name = "eme_chess_game.json"

    def __init__(self, shell):
        self.shell = shell
        self.root = shell.root
        self.board = chess.Board()
        self.my_color = chess.WHITE
        self.selected = None
        self.pending = None
        self.last_text = ""
        self.offer_in = False       # opponent has offered us a draw
        self.offer_out = False      # we have offered the opponent a draw
        self.ended = None           # text describing how the game ended

    def log(self, text):
        self.shell.log(text)

    def refresh(self):
        self.shell.refresh()

    # ---------------- widgets ----------------
    def build(self, frame):
        self.canvas = tk.Canvas(frame, width=8 * SQ, height=8 * SQ,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

    def build_buttons(self, frame):
        self.offer_btn = tk.Button(frame, text="Offer draw",
                                   command=self.offer_draw, state="disabled")
        self.offer_btn.pack(fill="x", pady=2)
        self.accept_btn = tk.Button(frame, text="Accept draw offer",
                                    command=self.accept_draw, state="disabled")
        self.accept_btn.pack(fill="x", pady=2)

    def over_text(self):
        if self.ended:
            return self.ended
        b = self.board
        if b.is_checkmate():
            return "Checkmate! Result " + b.result()
        if b.is_game_over():
            return "Game over (draw). Result " + b.result()
        return None

    def can_resign(self):
        return (not self.over_text()) and self.board.turn == self.my_color

    def status_text(self):
        over = self.over_text()
        side = "White" if self.my_color == chess.WHITE else "Black"
        if over:
            text = over
        elif self.pending:
            text = f"Pending move {self.pending.uci().upper()} - confirm to send"
        elif self.board.turn == self.my_color:
            text = f"You are {side}. YOUR MOVE."
            if self.offer_in:
                text += ("\nOpponent has OFFERED A DRAW. Accept it, "
                         "or just play a move to decline.")
        else:
            text = f"You are {side}. Waiting for opponent's move..."
            if self.offer_out:
                text += "\nDraw offer sent."
        return text

    def update_buttons(self):
        over = self.over_text()
        my_turn = (not over) and self.board.turn == self.my_color
        waiting = (not over) and self.board.turn != self.my_color
        self.accept_btn.config(state="normal" if (
            my_turn and self.offer_in and not self.pending) else "disabled")
        self.offer_btn.config(state="normal" if (
            waiting and self.board.move_stack and not self.offer_out) else "disabled")

    # ---------------- drawing ----------------
    def draw(self):
        c = self.canvas
        c.delete("all")
        flip = self.my_color == chess.BLACK
        last = self.board.peek() if self.board.move_stack else None
        font = ("Segoe UI Symbol", int(SQ * 0.68))
        small = ("Segoe UI", 8)
        for sq in chess.SQUARES:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            x = 7 - f if flip else f
            y = r if flip else 7 - r
            x0, y0 = x * SQ, y * SQ
            colour = LIGHT if (f + r) % 2 else DARK
            if sq == self.selected:
                colour = SELECT
            elif self.pending and sq in (self.pending.from_square,
                                         self.pending.to_square):
                colour = PENDING
            elif last and sq in (last.from_square, last.to_square):
                colour = LASTMOVE
            c.create_rectangle(x0, y0, x0 + SQ, y0 + SQ, fill=colour, outline="")
            if y == 7:
                c.create_text(x0 + SQ - 8, y0 + SQ - 8, text="abcdefgh"[f],
                              font=small, fill="#555")
            if x == 0:
                c.create_text(x0 + 8, y0 + 8, text=str(r + 1),
                              font=small, fill="#555")
            piece = self.board.piece_at(sq)
            if piece:
                cx, cy = x0 + SQ // 2, y0 + SQ // 2
                glyph = GLYPH[piece.symbol().lower()]
                if piece.color == chess.WHITE:
                    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1),
                                   (0, 2), (0, -2), (2, 0), (-2, 0)):
                        c.create_text(cx + dx, cy + dy, text=glyph,
                                      font=font, fill="black")
                    c.create_text(cx, cy, text=glyph, font=font, fill="white")
                else:
                    c.create_text(cx, cy, text=glyph, font=font, fill="black")

    # ---------------- user moves ----------------
    def on_click(self, event):
        if self.pending or self.board.turn != self.my_color:
            return
        if self.over_text():
            return
        x, y = event.x // SQ, event.y // SQ
        if not (0 <= x < 8 and 0 <= y < 8):
            return
        flip = self.my_color == chess.BLACK
        f = 7 - x if flip else x
        r = y if flip else 7 - y
        sq = chess.square(f, r)
        piece = self.board.piece_at(sq)

        if self.selected is None or (piece and piece.color == self.my_color):
            self.selected = sq if (piece and piece.color == self.my_color) else None
        else:
            move = chess.Move(self.selected, sq)
            mover = self.board.piece_at(self.selected)
            if mover.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                if chess.Move(self.selected, sq, chess.QUEEN) in self.board.legal_moves:
                    ans = (simpledialog.askstring(
                        "Promotion", "Promote to (Q, R, B, N):",
                        initialvalue="Q", parent=self.root) or "Q").upper()
                    promo = {"Q": chess.QUEEN, "R": chess.ROOK,
                             "B": chess.BISHOP, "N": chess.KNIGHT}.get(ans[:1], chess.QUEEN)
                    move = chess.Move(self.selected, sq, promo)
            if move in self.board.legal_moves:
                self.pending = move
            else:
                self.log("That move is not legal.")
            self.selected = None
        self.refresh()

    def cancel(self):
        self.pending = None
        self.selected = None
        self.refresh()

    def confirm(self):
        move = self.pending
        if not move:
            return
        decline = False
        if self.offer_in:
            if not messagebox.askyesno(
                    "Draw offer", "Your opponent has offered a draw.\n\n"
                    "Playing this move DECLINES the offer. Continue?"):
                return
            decline = True
        seq = len(self.board.move_stack) + 1
        san = self.board.san(move)
        self.board.push(move)
        self.pending = None
        self.selected = None
        self.offer_in = False
        self.last_text = f"C{seq:03d} {'X' if decline else ''}{move.uci().upper()}"
        if decline:
            self.log("You declined the draw offer.")
        self.save()
        self.log(f"You played {san}")
        self.shell.transmit()
        over = self.over_text()
        if over:
            self.log(over)
        self.refresh()

    # ---------------- draw / resign ----------------
    def end_game(self, text):
        self.ended = text
        self.pending = None
        self.selected = None
        self.offer_in = False
        self.offer_out = False
        self.save()
        self.log(text)
        self.refresh()

    def offer_draw(self):
        text = self.last_text + " D?"
        if len(text) > 13:
            messagebox.showinfo("Cannot fit",
                                "That message is too long to carry a draw offer "
                                "(Q65 free text is limited to 13 characters).\n"
                                "Offer the draw after your next move instead.")
            return
        if not messagebox.askyesno("Offer draw",
                                   "Offer your opponent a draw?\n\n"
                                   f"Will transmit: {text}"):
            return
        self.offer_out = True
        self.last_text = text
        self.save()
        self.log("Draw offered.")
        self.shell.transmit()
        self.refresh()

    def accept_draw(self):
        if not messagebox.askyesno("Accept draw", "Accept the draw offer?"):
            return
        seq = len(self.board.move_stack) + 1
        self.last_text = f"C{seq:03d} DRAW."
        self.end_game("Draw agreed. Result 1/2-1/2")
        self.shell.transmit()

    def resign(self):
        if not messagebox.askyesno("Resign", "Really resign this game?"):
            return
        seq = len(self.board.move_stack) + 1
        self.last_text = f"C{seq:03d} RESIGN"
        result = "0-1" if self.my_color == chess.WHITE else "1-0"
        self.end_game(f"You resigned. Result {result}")
        self.shell.transmit()

    # ---------------- receiving ----------------
    def handle_message(self, clean, snr):
        """Return True if the text was a chess message."""
        c = CMD_RE.search(clean)
        m = None if c else MOVE_RE.search(clean)
        if not (c or m):
            return False                            # not a chess message
        if self.ended:
            return True
        ply = len(self.board.move_stack)
        opp_turn = self.board.turn != self.my_color     # we are waiting on them

        # --- resign / accept draw (take the place of the opponent's move) ---
        if c:
            seq, word = int(c.group(1)), c.group(2)
            if not opp_turn or seq <= ply:
                self.shell.dbg(f"Heard '{clean}' but ignored it (not expected now).")
                return True
            if seq != ply + 1:
                self.log(f"OUT OF SYNC: got #{seq}, expected #{ply + 1}.")
                return True
            if word == "RESIGN":
                result = "1-0" if self.my_color == chess.WHITE else "0-1"
                self.log(f"RECEIVED '{clean}' (SNR {snr} dB)")
                self.end_game(f"Opponent resigned - you win! Result {result}")
            elif self.offer_out:
                self.log(f"RECEIVED '{clean}' (SNR {snr} dB)")
                self.end_game("Draw agreed. Result 1/2-1/2")
            else:
                self.log("Received DRAW. but no offer was made - ignored.")
            return True

        # --- ordinary move ---
        seq, declined = int(m.group(1)), bool(m.group(2))
        uci, offer = m.group(3).lower(), bool(m.group(4))

        if not opp_turn:
            # We are already up to date. This may be a repeat of the opponent's
            # last move that now carries a draw offer.
            if (seq == ply and offer and not self.offer_in and ply > 0
                    and self.board.peek().uci() == uci):
                self.offer_in = True
                self.log("Opponent OFFERS A DRAW.")
                self.save()
                self.refresh()
            self.shell.dbg(f"Heard '{clean}' but ignored it (it is your turn).")
            return True
        if seq <= ply:
            self.shell.dbg(f"Heard '{clean}' - already played / our own echo, ignored.")
            return True
        if seq != ply + 1:
            self.log(f"OUT OF SYNC: got move #{seq}, expected #{ply + 1}. "
                     "Ask opponent to re-send.")
            return True
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return True
        if move not in self.board.legal_moves:
            self.log(f"Received '{clean}' but it is not legal here - ignored.")
            return True
        san = self.board.san(move)
        self.board.push(move)
        self.log(f"RECEIVED {san}  ({clean}, SNR {snr} dB)")
        if self.offer_out:
            self.offer_out = False
            self.log("Opponent DECLINED your draw offer." if declined
                     else "Opponent moved on - draw offer considered declined.")
        if offer:
            self.offer_in = True
            self.log("Opponent OFFERS A DRAW.")
        self.save()
        over = self.over_text()
        if over:
            self.log(over)
        self.refresh()
        return True

    # ---------------- game management ----------------
    def new_game(self, first_time=False):
        white = messagebox.askyesno("Choose side",
                                    "Will YOU play White?\n\n"
                                    "(Yes = White, moves first. No = Black.)")
        self.board = chess.Board()
        self.my_color = chess.WHITE if white else chess.BLACK
        self.pending = None
        self.selected = None
        self.last_text = ""
        self.offer_in = self.offer_out = False
        self.ended = None
        if not first_time:
            self.shell.ask_callsigns()
        self.save()
        self.log("New game started. You are " + ("White." if white else "Black."))
        self.refresh()

    def save(self):
        # same file format as the original eme_chess.py
        data = {"my_color": "white" if self.my_color == chess.WHITE else "black",
                "moves": [m.uci() for m in self.board.move_stack],
                "last_text": self.last_text,
                "offer_in": self.offer_in, "offer_out": self.offer_out,
                "ended": self.ended,
                "my_call": self.shell.my_call, "opp_call": self.shell.opp_call}
        try:
            with open(self.shell.save_path(self.save_name), "w") as fh:
                json.dump(data, fh)
        except OSError as err:
            self.log(f"Could not save the game: {err}")

    def load(self):
        try:
            with open(self.shell.save_path(self.save_name)) as fh:
                data = json.load(fh)
            self.my_color = chess.WHITE if data["my_color"] == "white" else chess.BLACK
            self.board = chess.Board()
            for uci in data["moves"]:
                self.board.push_uci(uci)
            self.last_text = data.get("last_text", "")
            self.offer_in = data.get("offer_in", False)
            self.offer_out = data.get("offer_out", False)
            self.ended = data.get("ended")
            # a game saved by the original script carries the callsigns
            if not self.shell.my_call:
                self.shell.my_call = data.get("my_call", "")
            if not self.shell.opp_call:
                self.shell.opp_call = data.get("opp_call", "")
            self.log(f"Resumed saved game ({len(self.board.move_stack)} moves played).")
        except Exception as err:
            self.log(f"Could not load saved game: {err}")
        self.refresh()

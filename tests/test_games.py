"""Play many random games between two program instances connected by a
simulated radio path (with Moon echoes and repeats). Needs a display
(use xvfb-run on Linux)."""
import os
import random
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tkinter import messagebox, simpledialog  # noqa: E402

import emegames.shell as shell_mod  # noqa: E402
from eme_games import GAMES  # noqa: E402

ANSWERS = {}            # dialog answers for the next new game
messagebox.askyesno = lambda *a, **k: ANSWERS.get("yes", True)
messagebox.askyesnocancel = lambda *a, **k: False
messagebox.showinfo = lambda *a, **k: None
simpledialog.askstring = lambda title, prompt, **k: ANSWERS.get(title, "")


class FakeLink:
    connected = True
    n_packets = n_decodes = 0
    last_decode = None

    def __init__(self):
        self.sent = []

    def send_free_text(self, text):
        self.sent.append(text)
        return True

    def halt_tx(self):
        return True


def make_shell(root, tmp, name):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    shell_mod.SETTINGS_FILE = os.path.join(d, "settings.json")
    s = shell_mod.Shell(tk.Toplevel(root), FakeLink(), None, GAMES)
    s.save_path = lambda n, d=d: os.path.join(d, n)
    s.my_call, s.opp_call = name.upper(), "OPP"
    s.log_lines = []
    orig = s.log
    s.log = lambda t, o=orig: (s.log_lines.append(t), o(t))
    return s


def radio(src, dst):
    """Deliver src's last message to dst (several times) and echo it back."""
    text = src.link.sent[-1]
    for _ in range(random.randint(1, 3)):
        dst.handle_message(text + random.choice(["", " q3", "?"]), -20)
        src.handle_message(text, -24)          # own Moon echo


def is_my_turn(g):
    if g.over_text():
        return False
    if g.key == "chess":
        return g.board.turn == g.my_color
    return g.my_turn()


def random_move(g):
    """Prepare a random legal move in game g (sets g.pending)."""
    k = g.key
    if k == "chess":
        g.pending = random.choice(list(g.board.legal_moves))
    elif k == "four":
        g.pending = random.choice([c for c in range(7) if len(g.grid[c]) < 6])
    elif k == "tictactoe":
        g.pending = random.choice([(c, r) for c in range(3) for r in range(3)
                                   if (c, r) not in g.board])
    elif k == "reversi":
        legal = g.legal(g.to_move())
        g.pending = random.choice(legal) if legal else "PASS"
    elif k == "nim":
        i = random.choice([i for i, n in enumerate(g.piles) if n])
        g.pending = (i, random.randint(1, g.piles[i]))
    elif k == "seabattle":
        g.pending = random.choice([(x, y) for x in range(10) for y in range(10)
                                   if (x, y) not in g.my_shots])
    elif k == "codebreaker":
        # sometimes the right answer, so games end at different points
        opp = g._opp_secret
        g.pending = opp if random.random() < 0.12 else "".join(
            random.choice("123456") for _ in range(4))


OPPOSITE = [("YOU WIN", "you lose"), ("you lose", "YOU WIN"), ("draw", "draw"),
            ("Opponent resigned", "You resigned"), ("You resigned", "Opponent resigned"),
            ("Checkmate", "Checkmate"), ("Game over (draw)", "Game over (draw)")]


def play(root, tmp, key, n):
    stats = {}
    for i in range(n):
        a = make_shell(root, tmp, f"a{i}")
        b = make_shell(root, tmp, f"b{i}")
        for s, first in ((a, True), (b, False)):
            ANSWERS.clear()
            ANSWERS.update({"yes": first, "Nim set-up": random.choice(["1357", "3 4 5", "22"]),
                            "Your secret code": "".join(random.choice("123456") for _ in range(4))})
            s.open_game(key)
            s.game.new_game(first_time=True)
        if key == "codebreaker":
            a.game._opp_secret, b.game._opp_secret = b.game.secret, a.game.secret
        players = (a, b)
        delivered = {id(a): 0, id(b): 0}

        def flush():
            moved = True
            while moved:
                moved = False
                for src, dst in ((a, b), (b, a)):
                    if len(src.link.sent) > delivered[id(src)]:
                        delivered[id(src)] = len(src.link.sent)
                        radio(src, dst)
                        moved = True

        for step in range(2000):
            if a.game.over_text() and b.game.over_text():
                break
            movers = [s for s in players if is_my_turn(s.game)]
            assert len(movers) == 1, (key, step, a.link.sent[-2:], b.link.sent[-2:])
            g = movers[0].game
            if random.random() < 0.01 and g.can_resign():
                ANSWERS["yes"] = True
                g.resign()
            else:
                random_move(g)
                g.confirm()
            flush()
            if step == 7:          # save / reload half way through
                for s in players:
                    s.game.save()
                    old = getattr(s.game, "history", None)
                    s.game.load()
                    if old is not None:
                        assert s.game.history == old
                flush()
        ta, tb = a.game.over_text(), b.game.over_text()
        assert ta and tb, (key, ta, tb, a.link.sent[-3:], b.link.sent[-3:])
        assert any(x in ta and y in tb for x, y in OPPOSITE), (key, ta, tb)
        # both agree on the number of moves
        if key == "chess":
            assert a.game.board.fen() == b.game.board.fen()
        else:
            assert a.game.history == [["O" if w == "M" else "M", body]
                                      for w, body in b.game.history], key
            for t in a.link.sent + b.link.sent:
                assert len(t) <= 13, t
        stats[ta.split(" - ")[-1][:20]] = stats.get(ta.split(" - ")[-1][:20], 0) + 1
        for s in players:
            s.root.destroy()
    return stats


def main():
    random.seed(int(os.environ.get("SEED", "1")))
    root = tk.Tk()
    root.withdraw()
    with tempfile.TemporaryDirectory() as tmp:
        for key in GAMES:
            n = 30 if key == "chess" else 150
            print(f"{key:12s} {n} games OK  {play(root, tmp, key, n)}")
    root.destroy()


if __name__ == "__main__":
    main()

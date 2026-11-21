"""The new program must play chess against the ORIGINAL eme_chess.py."""
import os
import random
import sys
import tempfile
import tkinter as tk

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))
import test_games as T  # noqa: E402  (patches the dialogs)
import eme_chess as orig  # noqa: E402


def main():
    random.seed(3)
    root = tk.Tk()
    root.withdraw()
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(20):
            os.chdir(tmp)
            orig.SAVE_FILE = os.path.join(tmp, f"orig{n}.json")
            new = T.make_shell(root, tmp, f"new{n}")
            T.ANSWERS.update(yes=(n % 2 == 0))
            new.open_game("chess")
            new.game.new_game(first_time=True)
            T.ANSWERS.update(yes=(n % 2 == 1))
            o = orig.ChessApp(tk.Toplevel(root), T.FakeLink(), None)
            sent = {id(new): 0, id(o): 0}
            for step in range(3000):
                if new.game.over_text() and o.game_over_text():
                    break
                if o.board.turn == o.my_color and not o.game_over_text():
                    o.pending = random.choice(list(o.board.legal_moves))
                    o.confirm()
                else:
                    g = new.game
                    g.pending = random.choice(list(g.board.legal_moves))
                    g.confirm()
                for src, dst in ((new, o), (o, new)):
                    if len(src.link.sent) > sent[id(src)]:
                        sent[id(src)] = len(src.link.sent)
                        dst.handle_message(src.link.sent[-1] + " q3", -21)
                        src.handle_message(src.link.sent[-1], -25)
            assert new.game.board.fen() == o.board.fen()
            assert new.game.over_text() and o.game_over_text()
            new.root.destroy()
            o.root.destroy()
    print("20 games new-vs-original chess: OK")


if __name__ == "__main__":
    main()

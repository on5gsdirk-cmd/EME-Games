"""
EME Games - chess and other turn-based games over the Moon using WSJT-X.

Based on EME Chess by W4ATC / KQ4LNE. Start this file with Python, or use
the stand-alone EMEGames.exe (no Python needed).

REQUIREMENTS (only when running from source)
  * Python 3 (tkinter comes with it)
  * pip install chess
  * WSJT-X: File > Settings > Reporting > UDP Server
        address 127.0.0.1, port 2237, and tick "Accept UDP requests"
"""
import queue
import tkinter as tk
from tkinter import messagebox

from emegames.board_games import FourInARow, Reversi, TicTacToe
from emegames.chess_game import ChessGame
from emegames.code_breaker import CodeBreaker
from emegames.nim import Nim
from emegames.sea_battle import SeaBattle
from emegames.shell import Shell
from emegames.wsjtx import UDP_IP, UDP_PORT, WsjtxLink

GAMES = {cls.key: cls for cls in (ChessGame, FourInARow, SeaBattle, CodeBreaker,
                                  Reversi, Nim, TicTacToe)}


def main():
    root = tk.Tk()
    inbox = queue.Queue()
    try:
        link = WsjtxLink(inbox)
    except OSError as err:
        messagebox.showerror(
            "Cannot open UDP port",
            f"Could not listen on {UDP_IP}:{UDP_PORT}\n\n{err}\n\n"
            "Another program (JTAlert, GridTracker, ...) may be using it.")
        return
    shell = Shell(root, link, inbox, GAMES)
    root.after(50, shell.start)
    root.mainloop()


if __name__ == "__main__":
    main()

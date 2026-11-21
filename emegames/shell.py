"""The main window shared by every game.

Everything that is not game specific lives here: the WSJT-X connection
status, the station-ID timer (FCC 97.119), the log, re-send / HALT / resign
buttons and the game chooser. The game itself draws in the left half of the
window and adds its own buttons to the panel.
"""
import json
import os
import queue
import re
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from . import VERSION
from .theme import (ACCENT, BAD, BG, BTN, BTN_HOVER, FG, GOOD, INPUT_BG,
                    MUTED, WARN)

# Send a station ID after this many seconds of unidentified transmitting.
# The FCC limit is 10 minutes; 8 leaves room for the wait until the next gap.
ID_INTERVAL = 8 * 60


def app_dir():
    """Folder for save files: next to the .exe / script, or the user's home
    folder if that one is not writable (e.g. under Program Files)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        test = os.path.join(base, ".eme_write_test")
        with open(test, "w") as fh:
            fh.write("x")
        os.remove(test)
        return base
    except OSError:
        alt = os.path.join(os.path.expanduser("~"), "EME Games")
        os.makedirs(alt, exist_ok=True)
        return alt


APP_DIR = app_dir()
SETTINGS_FILE = os.path.join(APP_DIR, "eme_settings.json")

GENERAL_HELP = r"""## What this program does
EME Games lets two stations play turn-based games by bouncing each move off the Moon (or over any other path WSJT-X can work). You make a move on the board and confirm it, and the program hands it to WSJT-X as a short free-text message. When WSJT-X decodes your opponent's message, their move appears on your board automatically.
Use "Switch game..." to pick a game. Each game is saved separately, after every move, so you can close the program between EME sessions and pick up where you left off. Both stations must have the same game open.

## One-time WSJT-X setup
1. In WSJT-X choose File > Settings > Reporting.
2. In the "UDP Server" section set:
    UDP Server:              127.0.0.1
    UDP Server port number:  2237
   and tick "Accept UDP requests". Click OK.
3. Choose Mode > Q65 and set the sub-mode and period you and your opponent have agreed on (for example 30B: 30-second period, sub-mode B).
4. Agree with your opponent on frequencies and on who transmits in the first period and who in the second (the "Tx even/1st" checkbox).
5. Untick "Auto Seq" on the main WSJT-X window, so it does not answer station-ID messages by itself.
6. Leave WSJT-X running. Within about 15 seconds the top of this window should change to a green "WSJT-X: connected".

## Playing (all games)
- Agree beforehand who moves first.
- Make your move on the board and press "Confirm & Send". The move is loaded into WSJT-X's free-text message. You must then press Enable Tx in WSJT-X to actually transmit; this program never keys your transmitter by itself.
- WSJT-X repeats the message each transmit period until you disable Tx. That gives your opponent several chances to decode it, and duplicates are ignored automatically.
- When your opponent's move is decoded it is played on your board and shown in the log with its signal report.
- "Re-send last message" loads your last message into WSJT-X again.
- "HALT TX" tells WSJT-X to stop transmitting immediately.
- "Resign" is available on your turn and is sent in place of a move.
Every message starts with a letter for the game and the move number, for example C007 (chess, move 7) or F012 (four in a row, move 12). The number lets the program ignore repeats and your own Moon echoes, and notice missed moves.

## Station identification (call sign)
FCC rules (Part 97.119) require your station to transmit its call sign at the end of each communication and at least every 10 minutes during one; most other countries have similar rules. Game moves do not carry a call sign, so this program does it for you.
- Enter both call signs with the "Callsigns..." button. Your own is picked up from WSJT-X automatically when it can.
- While you are transmitting, the program keeps a countdown. After 8 minutes without an ID, it swaps in a normal Q65 message for one transmission, then puts your move message back. There is nothing for you to do:
    N4XYZ W4ATC
- "Send ID now" does the same thing on demand.
- "Final ID (73)" sends the closing ID and then stops WSJT-X's transmitter:
    N4XYZ W4ATC 73
  Press it when you have finished for the session or when the game is over, instead of just switching Tx off. The program also asks when you close it.
- Your opponent is responsible for identifying their own station under their own country's rules.

## Troubleshooting
- Opponent's moves do not appear on the board: leave "Show every decode from WSJT-X in the log" ticked and watch the log. A line starting "RX" appears for every message WSJT-X decodes. The "UDP from WSJT-X" counter under the status shows whether decodes are reaching this program at all. If the counter rises but no move appears, the log line shows exactly what text arrived.
- "Heard a message for another game": your opponent has a different game open. Both must use the same game.
- Still "not connected": WSJT-X must be running, and the three Reporting settings above must match exactly (127.0.0.1, 2237, Accept UDP requests).
- Error box about the UDP port: another program (JTAlert, GridTracker and similar) is already using port 2237. Close it while playing.
- Nothing is transmitted: press Enable Tx in WSJT-X, and check the mode, frequency and Tx even/1st settings.
- "OUT OF SYNC": a move was missed. Ask your opponent to press "Re-send last message".
- Try it without a radio: type a message into the "Test receive" box and press Go.
- Windows SmartScreen may warn the first time you start EMEGames.exe because it is not signed: click "More info" and "Run anyway".
- Both players should use the same version of this program.
"""

ANY_GAME_RE = re.compile(r"\b([A-Z])(\d{3}) ")


class Shell:
    def __init__(self, root, link, inbox, games):
        self.root = root
        self.link = link
        self.inbox = inbox
        self.games = games              # key -> Game class
        self.game = None
        self.settings = self.load_settings()
        self.my_call = self.settings.get("my_call", "")
        self.opp_call = self.settings.get("opp_call", "")
        self.transmitting = False   # WSJT-X is on the air right now
        self.tx_enabled = False
        self.unid_since = None      # when unidentified transmitting began
        self.last_id = None
        self.id_stage = None        # None / "loaded" / "sending"
        self.id_kind = "id"
        self.id_text = ""
        self.id_request = None      # "id" / "final" waiting for a gap
        self.id_warned = False
        self.help_win = None

        root.configure(bg=BG)
        root.option_add("*Background", BG)
        root.option_add("*Foreground", FG)
        root.option_add("*Button.Background", BTN)
        root.option_add("*Button.Foreground", FG)
        root.option_add("*Button.activeBackground", BTN_HOVER)
        root.option_add("*Button.activeForeground", "white")
        root.option_add("*Button.disabledForeground", MUTED)
        root.option_add("*Button.relief", "flat")
        root.option_add("*Button.borderWidth", 0)
        root.option_add("*Button.padY", 4)
        root.title("EME Games")

        self.board_frame = tk.Frame(root)
        self.board_frame.grid(row=0, column=0, padx=8, pady=8, sticky="n")

        panel = tk.Frame(root)
        panel.grid(row=0, column=1, sticky="ns", padx=8, pady=8)

        top = tk.Frame(panel)
        top.pack(fill="x")
        tk.Button(top, text="?  Help", command=self.show_help,
                  width=9).pack(side="right")
        self.conn_label = tk.Label(top, text="WSJT-X: not connected (yet)",
                                   fg=BAD, anchor="w")
        self.conn_label.pack(side="left", fill="x", expand=True)
        self.game_label = tk.Label(panel, text="", font=("Segoe UI", 14, "bold"),
                                   fg=ACCENT, anchor="w")
        self.game_label.pack(fill="x", pady=(6, 0))
        self.status_label = tk.Label(panel, text="", font=("Segoe UI", 12, "bold"),
                                     anchor="w", wraplength=330, justify="left")
        self.status_label.pack(fill="x", pady=6)
        self.id_label = tk.Label(panel, text="", font=("Segoe UI", 9), anchor="w")
        self.id_label.pack(fill="x", pady=(0, 2))
        self.udp_label = tk.Label(panel, text="UDP from WSJT-X: waiting...",
                                  font=("Segoe UI", 8), fg=MUTED, anchor="w")
        self.udp_label.pack(fill="x", pady=(0, 6))

        self.confirm_btn = tk.Button(panel, text="Confirm & Send",
                                     command=self.confirm, state="disabled",
                                     height=2)
        self.confirm_btn.pack(fill="x", pady=2)
        self.cancel_btn = tk.Button(panel, text="Cancel move",
                                    command=self.cancel, state="disabled")
        self.cancel_btn.pack(fill="x", pady=2)
        self.game_buttons = tk.Frame(panel)       # filled by the game
        self.game_buttons.pack(fill="x")
        tk.Button(panel, text="Re-send last message",
                  command=self.resend).pack(fill="x", pady=2)
        self.resign_btn = tk.Button(panel, text="Resign",
                                    command=self.resign, state="disabled")
        self.resign_btn.pack(fill="x", pady=2)
        tk.Button(panel, text="HALT TX", fg="white", bg="#8b2323",
                  activebackground="#b03030",
                  command=self.halt).pack(fill="x", pady=2)
        row = tk.Frame(panel)
        row.pack(fill="x", pady=2)
        tk.Button(row, text="New game...", command=self.new_game).pack(
            side="left", expand=True, fill="x", padx=(0, 1))
        tk.Button(row, text="Switch game...", command=self.choose_game).pack(
            side="left", expand=True, fill="x", padx=(1, 0))
        row = tk.Frame(panel)
        row.pack(fill="x", pady=2)
        for label, cmd in (("Send ID now", self.id_now),
                           ("Final ID (73)", self.id_final),
                           ("Callsigns...", self.ask_callsigns)):
            tk.Button(row, text=label, command=cmd).pack(
                side="left", expand=True, fill="x", padx=1)

        self.log_box = tk.Text(panel, width=44, height=10, state="disabled",
                               wrap="word", bg=INPUT_BG, fg=FG, relief="flat",
                               highlightthickness=0, padx=6, pady=6,
                               font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, pady=6)

        test = tk.Frame(panel)
        test.pack(fill="x")
        tk.Label(test, text="Test receive:").pack(side="left")
        self.test_entry = tk.Entry(test, width=16, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief="flat")
        self.test_entry.pack(side="left", padx=4)
        self.test_entry.bind("<Return>", lambda _e: self.test_receive())
        tk.Button(test, text="Go", command=self.test_receive).pack(side="left")
        self.show_all = tk.BooleanVar(value=True)
        tk.Checkbutton(panel, text="Show every decode from WSJT-X in the log",
                       variable=self.show_all, selectcolor=INPUT_BG,
                       activebackground=BG, activeforeground=FG,
                       anchor="w").pack(fill="x", pady=(4, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.poll)
        self.root.after(1000, self.id_tick)

    def start(self):
        """Open the last game played, or ask which game to play."""
        key = self.settings.get("game")
        if key in self.games:
            self.open_game(key)
        else:
            self.choose_game(first_time=True)

    # ---------------- settings ----------------
    def load_settings(self):
        try:
            with open(SETTINGS_FILE) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        self.settings.update(my_call=self.my_call, opp_call=self.opp_call,
                             game=self.game.key if self.game else None)
        try:
            with open(SETTINGS_FILE, "w") as fh:
                json.dump(self.settings, fh, indent=1)
        except OSError as err:
            self.log(f"Could not save settings: {err}")

    # ---------------- helpers ----------------
    def log(self, text):
        stamp = time.strftime("%H:%M:%S")
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"{stamp}  {text}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def dbg(self, text):
        if self.show_all.get():
            self.log(text)

    def refresh(self):
        if not self.game:
            return
        self.game.draw()
        self.update_status()

    def update_status(self):
        g = self.game
        self.status_label.config(text=g.status_text())
        state = "normal" if g.pending is not None else "disabled"
        self.confirm_btn.config(state=state)
        self.cancel_btn.config(state=state)
        self.resign_btn.config(state="normal" if g.can_resign() else "disabled")
        g.update_buttons()

    def save_path(self, name):
        return os.path.join(APP_DIR, name)

    # ---------------- choosing a game ----------------
    def choose_game(self, first_time=False):
        win = tk.Toplevel(self.root)
        win.title("Choose a game")
        win.configure(bg=BG)
        win.transient(self.root)
        tk.Label(win, text="Which game do you want to play?",
                 font=("Segoe UI", 13, "bold"), fg=ACCENT).pack(
            padx=16, pady=(14, 4), anchor="w")
        tk.Label(win, text="Your opponent must open the same game.",
                 fg=MUTED).pack(padx=16, pady=(0, 8), anchor="w")
        for key, cls in self.games.items():
            row = tk.Frame(win)
            row.pack(fill="x", padx=16, pady=3)
            mark = "  (current)" if self.game and self.game.key == key else ""
            tk.Button(row, text=cls.title + mark, width=22, anchor="w", padx=8,
                      command=lambda k=key: (win.destroy(), self.open_game(k))
                      ).pack(side="left")
            tk.Label(row, text=cls.blurb, fg=MUTED, anchor="w", justify="left",
                     wraplength=380).pack(side="left", padx=10, fill="x")
        tk.Frame(win, height=10).pack()
        win.grab_set()
        if first_time:
            # nothing open yet: closing the chooser opens chess
            win.protocol("WM_DELETE_WINDOW",
                         lambda: (win.destroy(), self.open_game("chess")))

    def open_game(self, key):
        if self.game:
            if self.game.key == key:
                return
            self.game.save()
        for frame in (self.board_frame, self.game_buttons):
            for child in frame.winfo_children():
                child.destroy()
        self.game = self.games[key](self)
        self.game.build(self.board_frame)
        self.game.build_buttons(self.game_buttons)
        self.game_label.config(text=self.game.title)
        self.root.title(f"EME Games {VERSION} - {self.game.title}")
        first_run = not self.settings
        if os.path.exists(self.save_path(self.game.save_name)):
            self.game.load()
        else:
            self.refresh()
            self.game.new_game(first_time=True)
        if not (self.my_call and self.opp_call):
            self.ask_callsigns()
        self.save_settings()
        self.refresh()
        if first_run:
            self.show_help()

    def new_game(self):
        if not messagebox.askyesno(
                "New game", f"Discard the current {self.game.title} game "
                "and start a new one?"):
            return
        self.game.new_game()
        self.refresh()

    # ---------------- moves ----------------
    def confirm(self):
        self.game.confirm()

    def cancel(self):
        self.game.cancel()

    def resign(self):
        self.game.resign()

    def transmit(self):
        text = self.game.last_text
        if not text:
            self.log("Nothing to send yet.")
            return
        if self.id_stage:
            self.log("A station ID is queued - your move goes out right after it.")
            return
        if self.link.send_free_text(text):
            self.log(f"Loaded '{text}' into WSJT-X. "
                     "Press Enable Tx there to transmit.")
        else:
            self.log("WSJT-X not connected - move saved but NOT loaded. "
                     "Use 'Re-send last message' once WSJT-X is talking to us.")

    def resend(self):
        self.transmit()

    def halt(self):
        if self.link.halt_tx():
            self.log("Sent HALT TX to WSJT-X.")
        else:
            self.log("WSJT-X not connected.")

    # ---------------- receiving ----------------
    def poll(self):
        try:
            while True:
                try:
                    item = self.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    self.dispatch(item)
                except Exception as err:
                    self.log(f"Internal error handling '{item[0]}': {err!r}")
        finally:
            self.root.after(200, self.poll)

    def dispatch(self, item):
        kind = item[0]
        if kind == "connected":
            self.conn_label.config(text=f"WSJT-X: connected ({item[1]})", fg=GOOD)
        elif kind == "decode":
            snr, text = item[1], item[2]
            if self.show_all.get():
                self.log(f"RX {snr:+d} dB: {text!r}")
            self.handle_message(text, snr)
        elif kind == "status":
            self.on_status(*item[1:])
        elif kind == "error":
            self.log(item[1])

    def test_receive(self):
        self.handle_message(self.test_entry.get(), 0)

    def handle_message(self, text, snr):
        if not self.game:
            return
        clean = " ".join(text.strip().upper().split())
        if self.game.handle_message(clean, snr):
            return
        # not for the open game - is it for another one?
        m = ANY_GAME_RE.search(clean)
        if m and m.group(1) != self.game.prefix:
            for cls in self.games.values():
                if cls.prefix == m.group(1):
                    self.log(f"Heard '{clean}' - that is a {cls.title} message, "
                             f"but you have {self.game.title} open.")
                    break

    # ---------------- station identification ----------------
    def ask_callsigns(self):
        me = simpledialog.askstring("Callsigns", "YOUR callsign:",
                                    initialvalue=self.my_call, parent=self.root)
        if me and me.strip():
            self.my_call = me.strip().upper()
        opp = simpledialog.askstring("Callsigns", "OPPONENT's callsign:",
                                     initialvalue=self.opp_call, parent=self.root)
        if opp and opp.strip():
            self.opp_call = opp.strip().upper()
        for call in (self.my_call, self.opp_call):
            if "/" in call:
                self.log(f"Note: '{call}' has a slash; ID messages work best "
                         "with plain callsigns.")
        self.save_settings()
        if self.game:
            self.game.save()

    def ensure_calls(self):
        if not (self.my_call and self.opp_call):
            self.ask_callsigns()
        return bool(self.my_call and self.opp_call)

    def id_now(self):
        if not self.ensure_calls():
            return
        if not self.link.connected:
            self.log("WSJT-X not connected - cannot load an ID.")
            return
        self.id_request = "id"
        self.log("ID requested - it goes out at the next gap between transmissions.")
        self.maybe_queue_id()

    def id_final(self):
        if not self.ensure_calls():
            return
        if not self.link.connected:
            self.log("WSJT-X not connected - cannot load an ID.")
            return
        self.id_request = "final"
        self.log("Final ID (73) requested - it goes out at the next gap between "
                 "transmissions. Make sure Enable Tx is on.")
        self.maybe_queue_id()

    def maybe_queue_id(self):
        """Load an ID into WSJT-X if one is due or requested, but only in the
        gap between transmissions so we never change a message mid-period."""
        if self.id_stage or self.transmitting:
            return
        due = (self.unid_since is not None
               and time.time() - self.unid_since >= ID_INTERVAL)
        if not (self.id_request or due):
            return
        if not (self.my_call and self.opp_call):
            if not self.id_warned:
                self.id_warned = True
                self.log("A station ID is due but the callsigns are not set - "
                         "press 'Callsigns...'.")
            return
        if not self.link.connected:
            return
        kind = self.id_request or "id"
        self.id_request = None
        text = f"{self.opp_call} {self.my_call}" + (" 73" if kind == "final" else "")
        if self.link.send_free_text(text):
            self.id_stage = "loaded"
            self.id_kind = kind
            self.id_text = text
            self.log(f"Station ID '{text}' loaded into WSJT-X.")

    def finish_id(self, now):
        kind = self.id_kind
        self.id_stage = None
        self.unid_since = None
        self.last_id = now
        self.id_warned = False
        if kind == "final":
            self.link.halt_tx()
            self.log("Final ID sent - Tx halted. 73!")
            return
        self.log("Station ID sent.")
        last_text = self.game.last_text if self.game else ""
        if last_text:
            self.link.send_free_text(last_text)
            self.log(f"Move message '{last_text}' put back in WSJT-X.")
        else:
            self.link.halt_tx()
        self.maybe_queue_id()

    def on_status(self, tx_enabled, transmitting, de_call, dx_call, tx_message):
        now = time.time()
        if de_call and not self.my_call:
            self.my_call = de_call.strip().upper()
            self.log(f"Your callsign ({self.my_call}) was taken from WSJT-X.")
            self.save_settings()
        was_tx, was_en = self.transmitting, self.tx_enabled
        self.transmitting, self.tx_enabled = transmitting, tx_enabled

        if tx_enabled and not was_en and self.unid_since is None and not self.id_stage:
            self.unid_since = now               # the ID clock starts

        if transmitting and not was_tx:         # a transmission just began
            sending_id = False
            if self.id_stage:
                if tx_message:
                    sending_id = tx_message.strip().upper() == self.id_text
                else:
                    sending_id = True
            if sending_id:
                self.id_stage = "sending"
            elif self.unid_since is None:
                self.unid_since = now
        elif was_tx and not transmitting:       # a transmission just ended
            if self.id_stage == "sending":
                self.finish_id(now)
            else:
                self.maybe_queue_id()

        if (was_en and not tx_enabled and self.unid_since is not None
                and not self.id_stage):
            self.log("Tx was switched off but you have transmitted since your "
                     "last ID. When you are finished, press 'Final ID (73)'.")

    def update_udp_label(self):
        link = self.link
        last = (time.strftime("%H:%M:%S", time.localtime(link.last_decode))
                if link.last_decode else "never")
        self.udp_label.config(text=f"UDP from WSJT-X: {link.n_packets} packets, "
                                   f"{link.n_decodes} decodes (last {last})")

    def id_tick(self):
        try:
            self._id_tick()
        except Exception as err:
            self.log(f"Internal error in ID timer: {err!r}")
            self.root.after(1000, self.id_tick)

    def _id_tick(self):
        self.update_udp_label()
        self.maybe_queue_id()
        now = time.time()
        colour = FG
        if self.id_stage == "loaded":
            text, colour = "Station ID queued - goes out on the next transmission", WARN
        elif self.id_stage == "sending":
            text, colour = "Transmitting station ID...", WARN
        elif self.unid_since is None:
            last = (time.strftime("%H:%M", time.localtime(self.last_id))
                    if self.last_id else "none yet")
            text, colour = f"Station ID: all clear (last ID {last})", GOOD
        elif self.game and self.game.over_text():
            text, colour = "Game over - press Final ID (73) when you are done", WARN
        else:
            left = int(ID_INTERVAL - (now - self.unid_since))
            if left > 0:
                text = f"Next station ID in {left // 60}:{left % 60:02d}"
                colour = FG if left > 120 else WARN
            else:
                text, colour = "Station ID due now", BAD
        self.id_label.config(text=text, fg=colour)
        self.root.after(1000, self.id_tick)

    def on_close(self):
        if self.id_stage:
            if not messagebox.askyesno("Station ID",
                                       "A station ID is queued or being sent.\n\n"
                                       "Close anyway?"):
                return
        elif self.unid_since is not None:
            ans = messagebox.askyesnocancel(
                "Station ID",
                "You have transmitted since your last station ID.\n\n"
                "Yes = queue a final ID (73) and keep the program open\n"
                "No = close anyway\nCancel = go back")
            if ans is None:
                return
            if ans:
                self.id_final()
                return
        if self.game:
            self.game.save()
        self.root.destroy()

    # ---------------- help ----------------
    def show_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.destroy()
        win = tk.Toplevel(self.root)
        self.help_win = win
        title = self.game.title if self.game else ""
        win.title(f"EME Games - Help ({title})")
        win.geometry("700x660")
        win.configure(bg=BG)
        bar = tk.Scrollbar(win)
        bar.pack(side="right", fill="y")
        box = tk.Text(win, wrap="word", bg=INPUT_BG, fg=FG, relief="flat",
                      highlightthickness=0, padx=16, pady=12,
                      font=("Segoe UI", 10), yscrollcommand=bar.set,
                      spacing1=2, spacing3=2)
        box.pack(side="left", fill="both", expand=True)
        bar.config(command=box.yview)
        box.tag_configure("h", font=("Segoe UI", 13, "bold"), foreground=ACCENT,
                          spacing1=14, spacing3=4)
        box.tag_configure("mono", font=("Consolas", 10), lmargin1=24, lmargin2=24,
                          foreground="#b8d8ff")
        text = (self.game.help_text.strip() + "\n\n" if self.game else "") + GENERAL_HELP
        for line in text.splitlines():
            if line.startswith("## "):
                box.insert("end", line[3:] + "\n", "h")
            elif line.startswith("    "):
                box.insert("end", line[4:] + "\n", "mono")
            else:
                box.insert("end", line + "\n")
        box.config(state="disabled")

"""Sea Battle - hidden fleets on a 10 x 10 grid. (Zeeslag)

Each message carries your shot AND the result of the opponent's previous
shot, which this program works out from your fleet automatically:
    S001 B5         first shot
    S002 J10 H      shot at J10; your shot at B5 was a Hit
    S003 C5 S3      shot at C5; that last shot Sank a ship of length 3
    S004 E7 M       shot at E7; Miss
    S017 W          your last shot sank my whole fleet - you Win
"""
import random
import re
import tkinter as tk

from .base import TurnGame, make_canvas

FLEET = [5, 4, 3, 3, 2]
COLS = "ABCDEFGHIJ"
N = 10


def cell_name(c):
    return f"{COLS[c[0]]}{c[1] + 1}"


def parse_cell(text):
    return COLS.index(text[0]), int(text[1:]) - 1


def ship_cells(x, y, size, horizontal):
    return [(x + i, y) if horizontal else (x, y + i) for i in range(size)]


class SeaBattle(TurnGame):
    key = "seabattle"
    title = "Sea Battle"
    prefix = "S"
    blurb = "Hidden fleets on a 10 x 10 grid; sink them all. (Zeeslag)"
    sides = ("First to fire", "Second to fire")
    save_name = "eme_sea_battle.json"
    CELL = 30
    help_text = r"""## Sea Battle
Each player has a secret fleet of 5 ships (lengths 5, 4, 3, 3 and 2) on a 10 x 10 grid; ships may not touch each other, not even diagonally. Players take turns firing one shot. Your program checks the opponent's shots against your fleet and reports Miss, Hit or Sunk automatically with your next shot, so nobody can make a mistake. Whoever sinks the whole enemy fleet first wins.
Before the first shot is fired or received you can change your fleet: "Shuffle fleet" places it at random, or click one of your ships to pick it up and click where its first square should go; right-click a ship to turn it. Once the battle starts the fleet is locked.
On your turn click a square on the right-hand grid ("Enemy waters"), then press "Confirm & Send".

## What goes over the air (sea battle)
    S001 B5         shot number 1 at B5 (columns A-J, rows 1-10)
    S002 J10 H      shot at J10, and your shot at B5 was a Hit
    S003 C5 S3      shot at C5, and your last shot Sank a ship of length 3
    S004 E7 M       shot at E7, and your last shot was a Miss
    S017 W          your last shot sank my last ship - you Win
    S018 RESIGN     resign
"""

    def reset_position(self):
        self.fleet = getattr(self, "fleet", None) or self.random_fleet()
        self.incoming = []      # cells the opponent fired at, in order
        self.my_shots = {}      # cell -> "?", "M", "H" or "S"
        self.my_order = []      # my shots in order
        self.sunk_sizes = []    # enemy ships I sank
        self.lost = False       # I reported W
        self.won = False        # opponent reported W
        self.selected_ship = None

    def setup_new(self):
        self.fleet = self.random_fleet()
        self.reset_position()
        return True

    # ---------------- fleet ----------------
    @staticmethod
    def valid(fleet):
        taken = set()
        for cells in fleet:
            for x, y in cells:
                if not (0 <= x < N and 0 <= y < N):
                    return False
            for x, y in cells:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if (x + dx, y + dy) in taken:
                            return False
            taken.update(cells)
        return True

    @classmethod
    def random_fleet(cls):
        while True:
            fleet = []
            for size in FLEET:
                for _ in range(200):
                    h = random.random() < 0.5
                    x = random.randrange(N - (size - 1 if h else 0))
                    y = random.randrange(N - (0 if h else size - 1))
                    cand = fleet + [ship_cells(x, y, size, h)]
                    if cls.valid(cand):
                        fleet = cand
                        break
            if len(fleet) == len(FLEET):
                return fleet

    @property
    def locked(self):
        return bool(self.history)

    def ship_at(self, cell):
        for i, cells in enumerate(self.fleet):
            if cell in cells:
                return i
        return None

    def report_for(self, cell):
        """What happened to the opponent's shot at cell (my fleet)."""
        i = self.ship_at(cell)
        if i is None:
            return "M"
        hit = set(self.incoming)
        if all(c in hit for c in self.fleet[i]):
            if all(all(c in hit for c in ship) for ship in self.fleet):
                return "W"
            return f"S{len(self.fleet[i])}"
        return "H"

    def owed_report(self):
        """Report I still have to give on the opponent's last shot."""
        if self.history and self.history[-1][0] == "O" and self.incoming:
            return self.report_for(self.incoming[-1])
        return None

    # ---------------- protocol ----------------
    def parse(self, rest):
        m = re.match(r"(?:(W)|([A-J](?:10|[1-9]))(?: (M|H|S[2-5]))?)(?![0-9A-Z])", rest)
        if not m:
            return None
        if m.group(1):
            return "W"
        return m.group(2) + (f" {m.group(3)}" if m.group(3) else "")

    def check(self, body, mine):
        if body == "W":
            return None if not mine or self.owed_report() == "W" else "not lost"
        cell = parse_cell(body.split()[0])
        if mine and cell in self.my_shots:
            return f"you already fired at {cell_name(cell)}"
        if not mine and self.ply > 0 and " " not in body:
            return "the message lacks the report on your last shot"
        return None

    def apply(self, body, mine):
        if body == "W":
            if mine:
                self.lost = True
                return "W - your fleet is sunk"
            self.won = True
            if self.my_order:
                self.my_shots[self.my_order[-1]] = "S"
            return "W - the enemy fleet is sunk!"
        parts = body.split()
        cell = parse_cell(parts[0])
        report = parts[1] if len(parts) > 1 else None
        desc = ""
        if not mine and report and self.my_order:
            last = self.my_order[-1]
            self.my_shots[last] = report[0]
            word = {"M": "miss", "H": "HIT", "S": "SUNK"}[report[0]]
            desc = f"your shot at {cell_name(last)}: {word}"
            if report[0] == "S":
                self.sunk_sizes.append(int(report[1]))
                desc += f" (a ship of length {report[1]})"
            desc += "; "
        if mine:
            self.my_shots[cell] = "?"
            self.my_order.append(cell)
            return f"a shot at {cell_name(cell)}"
        self.incoming.append(cell)
        hit = self.ship_at(cell) is not None
        return desc + f"they fire at {cell_name(cell)} ({'hit' if hit else 'miss'})"

    def pending_body(self):
        body = cell_name(self.pending)
        report = self.owed_report()
        return body + (f" {report}" if report else "")

    def describe_pending(self):
        return f"fire at {cell_name(self.pending)}"

    def after_receive(self):
        if self.owed_report() == "W" and not self.over_text():
            self.log("Your last ship is sunk. Reporting it to your opponent.")
            self.send_body("W")

    def can_resign(self):
        return self.my_turn() and self.owed_report() != "W"

    def result(self):
        if self.won:
            return "You sank the whole enemy fleet - YOU WIN!"
        if self.lost:
            return "Your fleet is sunk - you lose."
        return None

    def your_move_hint(self):
        if not self.locked:
            return "Arrange your fleet if you like, then pick a target."
        return f"Enemy ships sunk: {len(self.sunk_sizes)} of {len(FLEET)}"

    def waiting_hint(self):
        if not self.locked:
            return "You may still rearrange your fleet."
        return f"Enemy ships sunk: {len(self.sunk_sizes)} of {len(FLEET)}"

    def extra_save(self):
        return {"fleet": self.fleet}

    def extra_load(self, data):
        if data.get("fleet"):
            self.fleet = [[tuple(c) for c in ship] for ship in data["fleet"]]
            self.reset_position()

    # ---------------- widgets ----------------
    def build(self, frame):
        S = self.CELL
        self.ox = (30, 30 + 11 * S + 30)      # left edge of each grid
        self.oy = 50
        self.canvas = make_canvas(frame, self.ox[1] + 11 * S, self.oy + 11 * S + 30,
                                  self.on_click, self.on_right)

    def build_buttons(self, frame):
        self.shuffle_btn = tk.Button(frame, text="Shuffle fleet",
                                     command=self.shuffle)
        self.shuffle_btn.pack(fill="x", pady=2)

    def update_buttons(self):
        self.shuffle_btn.config(state="disabled" if self.locked else "normal")

    def shuffle(self):
        if self.locked:
            return
        self.fleet = self.random_fleet()
        self.selected_ship = None
        self.save()
        self.refresh()

    def grid_cell(self, event, which):
        S = self.CELL
        x = (event.x - self.ox[which] - S) // S
        y = (event.y - self.oy - S) // S
        return (x, y) if 0 <= x < N and 0 <= y < N else None

    def on_click(self, event):
        mine = self.grid_cell(event, 0)
        if mine is not None and not self.locked:
            self.place_click(mine)
            return
        target = self.grid_cell(event, 1)
        if target is not None and self.my_turn() and target not in self.my_shots:
            self.pending = target
            self.refresh()

    def place_click(self, cell):
        i = self.ship_at(cell)
        if self.selected_ship is None or i is not None:
            self.selected_ship = i
        else:
            ship = self.fleet[self.selected_ship]
            h = len(ship) > 1 and ship[0][1] == ship[1][1]
            moved = ship_cells(cell[0], cell[1], len(ship), h)
            fleet = [s for k, s in enumerate(self.fleet) if k != self.selected_ship]
            if self.valid(fleet + [moved]):
                self.fleet[self.selected_ship] = moved
                self.selected_ship = None
                self.save()
            else:
                self.log("The ship does not fit there (ships may not touch).")
        self.refresh()

    def on_right(self, event):
        cell = self.grid_cell(event, 0)
        if cell is None or self.locked:
            return
        i = self.ship_at(cell)
        if i is None:
            return
        ship = self.fleet[i]
        h = len(ship) > 1 and ship[0][1] == ship[1][1]
        turned = ship_cells(ship[0][0], ship[0][1], len(ship), not h)
        fleet = [s for k, s in enumerate(self.fleet) if k != i]
        if self.valid(fleet + [turned]):
            self.fleet[i] = turned
            self.save()
        else:
            self.log("No room to turn that ship.")
        self.refresh()

    def draw(self):
        cv, S = self.canvas, self.CELL
        cv.delete("all")
        hits_on_me = set(self.incoming)
        for which, title in ((0, "Your fleet"), (1, "Enemy waters")):
            ox, oy = self.ox[which], self.oy
            cv.create_text(ox + S + 5 * S, 20, text=title, fill="#4ea1ff",
                           font=("Segoe UI", 12, "bold"))
            for i in range(N):
                cv.create_text(ox + S + i * S + S // 2, oy + S // 2, text=COLS[i],
                               fill="#8a8d93", font=("Segoe UI", 9))
                cv.create_text(ox + S // 2, oy + S + i * S + S // 2, text=str(i + 1),
                               fill="#8a8d93", font=("Segoe UI", 9))
            for x in range(N):
                for y in range(N):
                    x0, y0 = ox + S + x * S, oy + S + y * S
                    fill = "#1b3b5a"
                    if which == 0:
                        i = self.ship_at((x, y))
                        if i is not None:
                            fill = "#f6f669" if i == self.selected_ship else "#8d96a0"
                    elif (x, y) == self.pending:
                        fill = "#2f6f3f"
                    cv.create_rectangle(x0, y0, x0 + S, y0 + S, fill=fill,
                                        outline="#2c5478")
                    mark = None
                    if which == 0 and (x, y) in hits_on_me:
                        mark = "H" if self.ship_at((x, y)) is not None else "M"
                    elif which == 1 and (x, y) in self.my_shots:
                        mark = self.my_shots[(x, y)]
                    cx, cy = x0 + S // 2, y0 + S // 2
                    if mark == "M":
                        cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                       fill="#cfd8e3", outline="")
                    elif mark in ("H", "S"):
                        col = "#ff4040" if mark == "H" else "#a01010"
                        cv.create_line(x0 + 6, y0 + 6, x0 + S - 6, y0 + S - 6,
                                       fill=col, width=4)
                        cv.create_line(x0 + S - 6, y0 + 6, x0 + 6, y0 + S - 6,
                                       fill=col, width=4)
                    elif mark == "?":
                        cv.create_text(cx, cy, text="?", fill="#ffb454",
                                       font=("Segoe UI", 11, "bold"))
            if which == 0 and self.incoming:
                x, y = self.incoming[-1]
                x0, y0 = ox + S + x * S, oy + S + y * S
                cv.create_rectangle(x0 + 1, y0 + 1, x0 + S - 1, y0 + S - 1,
                                    outline="#ffb454", width=2)
        cv.create_text(self.ox[1] + S + 5 * S, self.oy + 11 * S + 14,
                       text="o miss    X hit    dark X sunk    ? waiting for report",
                       fill="#8a8d93", font=("Segoe UI", 9))
        if not self.locked:
            cv.create_text(self.ox[0] + S + 5 * S, self.oy + 11 * S + 14,
                           text="click a ship, then where it goes; right-click turns",
                           fill="#8a8d93", font=("Segoe UI", 9))

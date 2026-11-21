# EME Games (formerly EME-Chess)
Chess and other turn-based games over the Moon (or any path WSJT-X can work), using WSJT-X Q65 free-text messages. The program turns your move into a short message (max 13 characters), hands it to WSJT-X over UDP, and plays your opponent's decoded moves on your board automatically. It never keys your transmitter by itself: you still press Enable Tx in WSJT-X. Station IDs are sent automatically every 8 minutes.

## Games
| Game | Prefix | Example message | Notes |
|---|---|---|---|
| Chess | `C` | `C007 E2E4` | Identical to the original `eme_chess.py` - you can play against someone still using it |
| Four in a Row | `F` | `F007 4` | Drop a disc in column 1-7 |
| Sea Battle | `S` | `S002 J10 H` | Hidden fleets; the result of the opponent's shot (M/H/S3/W) is added automatically |
| Code Breaker | `K` | `K002 5566 12` | Mastermind-style; both hide a code, the score is added automatically |
| Reversi | `R` | `R005 D3` | `R018 PASS` when you cannot move |
| Nim | `N` | `N001 B3 1357L` | First move carries the piles and the rule (L = last stick loses, W = wins) |
| Tic-Tac-Toe | `T` | `T003 B2` | Quick game to test your set-up |

Every game: `<letter><move number> RESIGN` to resign. Both stations must have the same game open (use "Switch game..."). Each game is saved separately after every move. The Help button explains each game.

## Windows: no Python needed
Download `EMEGames.exe` (see Releases, or the Actions tab > latest "Build Windows exe" run > Artifacts), put it in a folder of its own such as `C:\EMEGames`, and double-click it. Save files are written next to the .exe. Windows SmartScreen may warn the first time because the file is not signed: click "More info" > "Run anyway".

To build the .exe yourself on any Windows PC that has Python: double-click `build_exe.bat`; the result is `dist\EMEGames.exe`, which you can give to anyone. Maintainers: pushing a tag such as `v2.0` makes GitHub build the .exe and attach it to a Release automatically (`.github/workflows/build-windows.yml`).

## Running from source
Python 3 and `pip install chess`, then `python eme_games.py` (or double-click `EME Games.bat`, which installs `chess` if needed). Tests: `python tests/test_games.py` plays hundreds of random games between two simulated stations; `python tests/test_chess_compat.py` plays the new program against the original `eme_chess.py`.

## WSJT-X setup
File > Settings > Reporting > UDP Server: address `127.0.0.1`, port `2237`, tick "Accept UDP requests". Untick "Auto Seq". See the Help button in the program for the full guide.

---

# Original EME-Chess instructions (eme_chess.py)
A simple python script that interfaces with WSJT-X to coordinate and provide a GUI for over-the-air chess games via earth-moon-earth amateur radio communication.
Works directly with WSJT-X.
Download eme-chess.py and put it in a folder on your drive called "C:\EMEChess"
Ensure that you have Python 3 or newer installed on your machine. 
During installation ensure that you check "Add Python to PATH" so that pip and python commands are useable in Command Prompt. 
Open Command Prompt and type "pip install chess". If that doesnt work, try "python -m pip install chess" or "py -m pip install chess"

Now you should be good to go ahead and open the program. In Command Prompt, navigate to the folder where you saved the program. i.e. "cd C:\EMEChess" once there, enter the command "python eme_chess.py" to start the program.

Now that you have the program installed, it needs to be set up to interface with WSJT-X. Open WSJT-X and simply navigate to File->Settings->Reporting->UDP Server, then set the address to 127.0.0.1 and port to 2237, and activate "Accept UDP requests"
Close out WSJT-X and restart the program. 

Now you should be able to start a new game. Agree on who will play white before starting the game. Moves are encoded as follows: "Cnnn XkXk" where n is the number of moves since the start of the game, X is a column letter and k is a row number. For instance, the opening 1.e4e5 2.Nf3Nc6 in standard algebraic chess notation would be encoded as the following in EME chess, assuming station1 is white and station2 is black:
station1: "C001 E2E4"
station2: "C002 E7E5"
station1: "C003 G1F3"
station2: "C004 B8C6"

Note that in order to adhere to the 10-minute ID limit, the program will automatically send your callsign to WSJT-X once every 8 minutes, delaying the game by a turn. You may manually ID by clicking the "send ID now" button. Also, you can offer/accept a draw or resign, just like on other correspondence chess platforms. 

Now you are all set up to start playing chess on the moon!

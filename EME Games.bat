@echo off
REM Starts EME Games from the Python source (for people who have Python).
REM No Python? Use EMEGames.exe instead.
cd /d "%~dp0"
python -c "import chess" 2>nul || python -m pip install --user chess
python eme_games.py
if errorlevel 1 pause

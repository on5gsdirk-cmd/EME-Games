@echo off
REM Builds a stand-alone EMEGames.exe (needs Python only on THIS computer).
REM Hand dist\EMEGames.exe to other hams: they do not need Python at all.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller chess || goto :error
python -m PyInstaller --noconfirm --onefile --windowed --name EMEGames eme_games.py || goto :error
echo.
echo Done: %~dp0dist\EMEGames.exe
pause
exit /b 0
:error
echo.
echo Build failed. Is Python 3 installed with "Add Python to PATH" ticked?
pause
exit /b 1

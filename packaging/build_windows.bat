@echo off
REM Double-click to build iMHEA-Data-Processor.exe on Windows.
REM Requires Python 3.10+ from https://www.python.org/downloads/
REM (tick "Add python.exe to PATH" during installation).
cd /d "%~dp0.."
echo == iMHEA Data Processor - Windows build ==

python --version || (echo Python not found. Install it and retry. & pause & exit /b 1)

echo -- creating build environment...
python -m venv .venv-build
call .venv-build\Scripts\activate.bat
pip install --quiet --upgrade pip
echo -- installing imhea + build dependencies (first run takes a few minutes)...
pip install --quiet -e ".[build]"

echo -- building the app...
pyinstaller packaging\imhea_gui.spec --noconfirm

if exist "dist\iMHEA-Data-Processor\iMHEA-Data-Processor.exe" (
  echo.
  echo SUCCESS: dist\iMHEA-Data-Processor\iMHEA-Data-Processor.exe
  echo Zip the dist\iMHEA-Data-Processor folder to share it.
  start "" dist
) else (
  echo Build finished but the exe was not found - check messages above.
)
pause

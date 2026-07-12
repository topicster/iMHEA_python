#!/bin/bash
# Double-click this file in Finder to build "iMHEA Data Processor.app".
# Requires Python 3.10+ (https://www.python.org/downloads/ or `brew install python`).
set -e
cd "$(dirname "$0")/.."
echo "== iMHEA Data Processor — macOS build =="

PY=python3
$PY --version || { echo "Python 3 not found. Install it from python.org and retry."; read -p "Press Enter to close."; exit 1; }

echo "-- creating build environment (.venv-build)..."
$PY -m venv .venv-build
source .venv-build/bin/activate
pip install --quiet --upgrade pip
echo "-- installing imhea + build dependencies (first run takes a few minutes)..."
pip install --quiet -e ".[build]"

echo "-- building the app..."
pyinstaller packaging/imhea_gui.spec --noconfirm

APP="dist/iMHEA Data Processor.app"
if [ -d "$APP" ]; then
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
  echo
  echo "SUCCESS: $PWD/$APP"
  echo "Drag it to /Applications, or zip it to share."
  open dist
else
  echo "Build finished but the .app was not found — check messages above."
fi
read -p "Press Enter to close."

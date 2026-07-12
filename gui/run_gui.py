#!/usr/bin/env python3
"""Launcher: python gui/run_gui.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from imhea_gui.app import main

if __name__ == "__main__":
    main()

# iMHEA Data Processor — desktop app

PySide6 GUI on top of the `imhea` library.

## Run from source
```bash
pip install -e ".[gui]"
python gui/run_gui.py
```

## Structure
- `imhea_gui/app.py` — main window, start screen, sidebar, run/export
- `imhea_gui/project.py` — `.imhea` project files (JSON), data loading
- `imhea_gui/runner.py` — background pipeline thread with log capture
- `imhea_gui/tabs.py` — Setup / Results / Indices / Log tabs
- `imhea_gui/dialogs.py` — rating-curve editor, gap-filling report
- `imhea_gui/i18n.py` — EN/ES strings

Start screen: "Process my data" (empty project), "Explore the iMHEA
network" (loads the built-in 2018 registry after choosing the folder that
contains `iMHEA_raw/`), or open a saved `.imhea` project.

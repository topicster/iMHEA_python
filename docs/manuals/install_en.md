---
title: "iMHEA Data Processor — Installation Manual"
subtitle: "Version 1.0 · July 2026"
lang: en
---

# About this software

The **iMHEA Data Processor** processes rainfall and streamflow data from
hydrological monitoring catchments following the methodology of the Regional
Initiative for Hydrological Monitoring of Andean Ecosystems (iMHEA),
published in Ochoa-Tocachi et al. (2018), *Scientific Data* 5:180080.

It is distributed in three forms — install whichever suits you:

| Component | For | Requires |
|---|---|---|
| **Desktop application** | Field teams and analysts; no programming | Nothing (standalone) |
| **Command-line tool** (`imhea`) | Batch processing, automation | Python 3.10+ |
| **Python library** (`import imhea`) | Researchers, custom analyses | Python 3.10+ |

# Option A — Desktop application (recommended)

## A.1 From a release package

If you received (or downloaded from the project's GitHub Releases page) a
ZIP file for your operating system:

**Windows**

1. Unzip `iMHEA-Data-Processor-windows.zip` anywhere (e.g. `Documents`).
2. Open the folder and double-click `iMHEA-Data-Processor.exe`.
3. First launch only: Windows SmartScreen may warn about an unrecognised
   app. Click **More info → Run anyway**. This happens because the
   executable is not code-signed; it does not indicate a problem.

**macOS**

1. Unzip and drag `iMHEA Data Processor.app` to `Applications` (optional).
2. First launch only: **right-click the app → Open → Open**. macOS
   Gatekeeper blocks double-clicking unsigned apps the first time.
   If it still refuses, run in Terminal:
   `xattr -dr com.apple.quarantine "/Applications/iMHEA Data Processor.app"`

**Linux**

1. Unzip, then run `./iMHEA-Data-Processor/iMHEA-Data-Processor`.
2. If it reports a missing Qt platform plugin, install the system
   libraries: `sudo apt install libegl1 libxkbcommon0`.

## A.2 Building the application yourself

If no release package is available for your platform, build it with one
double-click. You need **Python 3.10 or newer** installed first
(<https://www.python.org/downloads/> — on Windows, tick *"Add python.exe
to PATH"* during installation).

1. Obtain the `imhea-python` folder (from the repository or from a
   colleague).
2. Open the `packaging` subfolder.
3. **macOS:** double-click `build_mac.command` (first time: right-click →
   Open). **Windows:** double-click `build_windows.bat`.
4. Wait a few minutes. The finished app appears in `imhea-python/dist/`
   and the folder opens automatically. The app is self-contained — copy or
   zip it to share with colleagues, who do **not** need Python.

## A.3 Automated builds with GitHub Actions

If the repository is hosted on GitHub, every tagged release (e.g.
`v1.0.0`) automatically builds and publishes packages for Windows, macOS
(Intel and Apple Silicon) and Linux. Maintainers can also trigger a build
manually from the **Actions** tab (*Build desktop apps* workflow); the
packages appear as downloadable artifacts on the workflow run page.

# Option B — Python package (CLI + library)

For users comfortable with a terminal:

```
pip install imhea            # from PyPI, when published
# or, from a repository checkout:
pip install -e ".[gui]"      # library + CLI + desktop app
```

This installs two commands:

- `imhea` — the command-line interface (see the User Manual, section 9).
- `imhea-gui` — launches the desktop application.

To run the GUI from a source checkout without installing:
`python gui/run_gui.py`.

# System requirements

| | Minimum |
|---|---|
| Operating system | Windows 10+, macOS 12+, or Linux (glibc 2.31+) |
| Memory | 4 GB (8 GB recommended for multi-year 5-min records) |
| Disk | 500 MB for the application; data storage as needed |
| Python (options B / A.2 only) | 3.10 or newer |

# Updating

- **Desktop app:** download or build the new version and replace the old
  folder/app. Project files (`.imhea`) are forward-compatible.
- **Python package:** `pip install -U imhea`.

# Troubleshooting

**"Python not found" when building.** Install Python from python.org and,
on Windows, re-run the installer choosing *Modify* if you forgot to tick
"Add python.exe to PATH".

**The build script closes immediately (Windows).** Right-click →
*Run as administrator* is not needed; instead open a Command Prompt in the
`packaging` folder and run `build_windows.bat` to see the error message.

**macOS: "app is damaged or incomplete".** The quarantine flag survives
some transfers. Run:
`xattr -dr com.apple.quarantine "iMHEA Data Processor.app"`.

**The app starts but figures are blank (Linux).** Set the environment
variable `QT_QPA_PLATFORM=xcb` (Wayland systems) or install `libegl1`.

**Cloud-synced folders.** Building inside OneDrive/Dropbox/Drive folders
works but syncs hundreds of megabytes; prefer building in a local folder,
or pause syncing during the build.

# Getting help

Report problems on the project's GitHub *Issues* page, attaching the
message shown in the app's **Log** tab or the terminal output. Include
your operating system and the software version (shown by `imhea
--version` or in the app title bar).

# Building the standalone apps

The desktop app bundles Python, the `imhea` library, Qt and matplotlib into
a folder users can run without installing anything.

## One-command local build (any platform)

```bash
pip install -e ".[build]"
pyinstaller packaging/imhea_gui.spec --noconfirm
```

Output:
- **Windows:** `dist/iMHEA-Data-Processor/iMHEA-Data-Processor.exe`
- **macOS:** `dist/iMHEA Data Processor.app` (double-clickable)
- **Linux:** `dist/iMHEA-Data-Processor/iMHEA-Data-Processor`

Zip the output folder/app to share it. Each platform must be built ON that
platform (PyInstaller does not cross-compile).

## Automated builds (recommended)

Push the repository to GitHub and either:
- push a tag like `v1.0.0` — `.github/workflows/build.yml` runs the test
  suite, builds Windows + macOS (Intel and Apple Silicon) + Linux bundles,
  and attaches the zips to a GitHub Release; or
- run the "Build desktop apps" workflow manually from the Actions tab
  (artifacts appear on the workflow run page).

## Notes

- **macOS Gatekeeper:** unsigned apps need right-click → Open the first
  time (or `xattr -dr com.apple.quarantine "iMHEA Data Processor.app"`).
  Proper signing/notarization needs an Apple Developer ID — can be added
  to the workflow later.
- **Windows SmartScreen:** "More info → Run anyway" on first launch, until
  the binaries build reputation or are code-signed.
- **Size:** ~250-350 MB per bundle (Qt + NumPy/SciPy/matplotlib); the spec
  already excludes QtWebEngine/QML/Multimedia to keep it down.
- An app icon can be added as `packaging/imhea.ico` (Windows/Linux) and
  `.icns` (macOS) — the spec picks it up automatically if present.
- The CLI (`imhea process/pair/network`) is available in any environment
  with `pip install imhea` — no bundling needed.

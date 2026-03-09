# Card Optimiser

Optimises bulk purchases from mtgsingles.co.nz, letting you compare stores and minimise total order cost.

## Usage (CLI)

1. Configure cards and vendors in `config.yaml`.
2. Run `python run_optimiser.py`.
3. Check output in `results.txt`.

## Usage (Web UI, local)

1. Install dependencies: `pip install -r requirements.txt`
2. Start app: `python app.py`
3. Open `http://127.0.0.1:5000`

## Usage (Desktop app, local)

1. Install dependencies: `pip install -r requirements.txt`
2. Run desktop launcher: `python desktop_main.py`

The desktop launcher starts the Flask server locally and opens a native app window.

## Build Desktop Packages

### macOS (.app + .dmg)

1. `bash scripts/build_desktop_mac.sh`
2. Output:
- `dist/CardOptimiser.app`
- `dist/CardOptimiser-mac.dmg`

### Windows (single-file `.exe` + optional installer)

1. `powershell -ExecutionPolicy Bypass -File scripts/build_desktop_windows.ps1`
2. Output:
- `dist/CardOptimiser.exe`
- `dist/CardOptimiserSetup.exe` (if Inno Setup `ISCC.exe` is installed)

## Publish Downloads via GitHub

This repo includes a GitHub Actions workflow that builds desktop packages and publishes them to GitHub Releases when you push a version tag (`v*`).

1. Commit and push your changes.
2. Create and push a version tag:
   - `git tag v1.0.0`
   - `git push origin v1.0.0`
3. Wait for workflow `Build Desktop Packages` to finish.
4. Open GitHub Releases. Your release will include:
   - `CardOptimiser-mac.dmg`
   - `CardOptimiser.exe`

Direct download URLs (for website buttons):
- `https://github.com/<owner>/<repo>/releases/latest/download/CardOptimiser-mac.dmg`
- `https://github.com/<owner>/<repo>/releases/latest/download/CardOptimiser.exe`

## Configuration

Edit `config.yaml` to set:
- Card list
- Vendor list
- Shipping costs
- Vendor penalty
- Optional cards and minimums
- Card tags and tag constraints

### Card Tagging Example

```yaml
optional_cards:
  - Carrion Feeder [black, sacrifice]
  - Arcbound Mouser [artifact]

tag_constraints:
  black:
    minimum: 5
    maximum: 10
  sacrifice:
    target: 3
```

## Notes

- Desktop mode stores writable data (config/results/cache) in a user app-data directory.
- `requirements-build.txt` includes build-only tooling (`pyinstaller`).
- If Windows reports `No compatible MILP solver could be executed`, rebuild with current specs so bundled PuLP CBC solver files are included.

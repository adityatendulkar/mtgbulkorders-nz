#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt
python3 -m PyInstaller --clean desktop.spec

DMG_PATH="dist/CardOptimiser-mac.dmg"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "Card Optimiser" \
  -srcfolder "dist/CardOptimiser.app" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Built macOS app bundle: dist/CardOptimiser.app"
echo "Built macOS DMG: $DMG_PATH"

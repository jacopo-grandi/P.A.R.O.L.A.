#!/bin/sh
# Build dist/PAROLA.app (decision 0028). Step 1 of phase 8: a development build that runs the
# engine of this repo (.venv/bin/parola) on the calls in data/private/calls. The self-contained
# build, with Python and its packages inside the app, is step 3.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
app="$repo/dist/PAROLA.app"
version=$(sed -n 's/^version = "\(.*\)"/\1/p' "$repo/pyproject.toml" | head -1)

swift build -c release --package-path "$here"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$here/.build/release/PAROLA" "$app/Contents/MacOS/PAROLA"

cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>PAROLA</string>
  <key>CFBundleIdentifier</key><string>dev.parola.app</string>
  <key>CFBundleName</key><string>PAROLA</string>
  <key>CFBundleDisplayName</key><string>P.A.R.O.L.A.</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$version</string>
  <key>CFBundleVersion</key><string>$version</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>P.A.R.O.L.A. registra il tuo microfono per trascrivere in locale la tua parte della call.</string>
  <key>NSAudioCaptureUsageDescription</key><string>P.A.R.O.L.A. registra l'audio della call per trascrivere in locale gli altri partecipanti.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>PAROLAEngine</key><string>$repo/.venv/bin/parola</string>
  <key>PAROLADataDir</key><string>$repo/data/private/calls</string>
</dict>
</plist>
PLIST

# Apple Silicon runs only signed code: an ad-hoc signature, until there is a Developer ID.
codesign --force --sign - "$app"
echo "built $app"

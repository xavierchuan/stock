#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LITE_DIR="$PROJECT_ROOT/lite_tool"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"

APP_NAME="${APP_NAME:-BuffettLite}"
BUNDLE_ID="${BUNDLE_ID:-com.dlc39degree.buffettlite}"
TEAM_ID="${TEAM_ID:-}"
CERT_NAME="${CERT_NAME:-}"
KEYCHAIN_PROFILE="${KEYCHAIN_PROFILE:-AC_NOTARY}"
SKIP_NOTARIZE="${SKIP_NOTARIZE:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"
LICENSE_FILE="${LICENSE_FILE:-}"

DIST_DIR="$LITE_DIR/dist_signed"
WORK_DIR="$LITE_DIR/build_signed"
APP_PATH="$DIST_DIR/$APP_NAME.app"
ZIP_PATH="$DIST_DIR/$APP_NAME.app.zip"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python not found at $PYTHON_BIN"
  exit 1
fi

for cmd in codesign ditto spctl xcrun; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing command: $cmd"
    exit 1
  fi
done

if [[ ! -f "$LITE_DIR/public_key.pem" ]]; then
  echo "Missing $LITE_DIR/public_key.pem"
  echo "Run: python3 $LITE_DIR/generate_keys.py && cp ~/.factor_lab_keys/public_key.pem $LITE_DIR/public_key.pem"
  exit 1
fi

if [[ -z "$CERT_NAME" ]]; then
  echo "Missing CERT_NAME. Use a Developer ID Application certificate."
  echo "Example:"
  echo "  CERT_NAME='Developer ID Application: Your Name (TEAMID)' TEAM_ID=TEAMID $LITE_DIR/build_sign_notarize_app.sh"
  exit 1
fi

if ! security find-identity -v -p codesigning | grep -F "$CERT_NAME" >/dev/null 2>&1; then
  echo "Certificate not found in keychain: $CERT_NAME"
  echo "Current identities:"
  security find-identity -v -p codesigning | sed -n '1,40p'
  exit 1
fi

if ! security find-identity -v -p codesigning | grep "Developer ID Application" >/dev/null 2>&1; then
  echo "No 'Developer ID Application' certificate found."
  echo "Apple Development cert is not enough for notarized external distribution."
  exit 1
fi

if [[ "$SKIP_BUILD" != "1" ]]; then
  rm -rf "$WORK_DIR" "$DIST_DIR"
  mkdir -p "$WORK_DIR" "$DIST_DIR"

  "$PYTHON_BIN" -m PyInstaller \
    --noconfirm \
    --windowed \
    --onedir \
    --name "$APP_NAME" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    --specpath "$WORK_DIR" \
    --collect-all streamlit \
    --add-data "$LITE_DIR/__init__.py:lite_tool" \
    --add-data "$LITE_DIR/app.py:lite_tool" \
    --add-data "$LITE_DIR/akshare_provider.py:lite_tool" \
    --add-data "$LITE_DIR/config.py:lite_tool" \
    --add-data "$LITE_DIR/limits.py:lite_tool" \
    --add-data "$LITE_DIR/licensing.py:lite_tool" \
    --add-data "$LITE_DIR/scoring.py:lite_tool" \
    --add-data "$LITE_DIR/public_key.pem:lite_tool" \
    "$LITE_DIR/desktop_entry.py"
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "Build output not found: $APP_PATH"
  exit 1
fi

if [[ -n "$LICENSE_FILE" ]]; then
  if [[ ! -f "$LICENSE_FILE" ]]; then
    echo "LICENSE_FILE not found: $LICENSE_FILE"
    exit 1
  fi
  cp "$LICENSE_FILE" "$APP_PATH/Contents/MacOS/license.key"
fi

echo "Signing app..."
codesign --force --deep --options runtime --timestamp \
  --sign "$CERT_NAME" \
  "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "Creating zip for notarization..."
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

if [[ "$SKIP_NOTARIZE" == "1" ]]; then
  echo "SKIP_NOTARIZE=1 set. Build+sign finished."
  echo "App: $APP_PATH"
  echo "Zip: $ZIP_PATH"
  exit 0
fi

if [[ -z "$TEAM_ID" ]]; then
  echo "Missing TEAM_ID for notarization."
  exit 1
fi

if ! xcrun notarytool history --keychain-profile "$KEYCHAIN_PROFILE" >/dev/null 2>&1; then
  echo "Notary profile not found: $KEYCHAIN_PROFILE"
  echo "Run setup first:"
  echo "  TEAM_ID=$TEAM_ID APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx $LITE_DIR/setup_notary_profile.sh"
  exit 1
fi

echo "Submitting to Apple notarization..."
xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$KEYCHAIN_PROFILE" --wait

echo "Stapling notarization ticket..."
xcrun stapler staple "$APP_PATH"

echo "Verifying Gatekeeper status..."
spctl -a -vv "$APP_PATH"

echo "Done."
echo "App: $APP_PATH"
echo "Zip: $ZIP_PATH"

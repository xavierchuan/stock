#!/bin/bash
set -euo pipefail

APPLE_ID="${APPLE_ID:-lxcxavier@outlook.com}"
TEAM_ID="${TEAM_ID:-}"
APP_SPECIFIC_PASSWORD="${APP_SPECIFIC_PASSWORD:-}"
KEYCHAIN_PROFILE="${KEYCHAIN_PROFILE:-AC_NOTARY}"

if ! command -v xcrun >/dev/null 2>&1; then
  echo "xcrun not found. Please install Xcode Command Line Tools first."
  exit 1
fi

if [[ -z "$TEAM_ID" ]]; then
  echo "Missing TEAM_ID. Example:"
  echo "  TEAM_ID=XXXXXXXXXX APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx ./lite_tool/setup_notary_profile.sh"
  exit 1
fi

if [[ -z "$APP_SPECIFIC_PASSWORD" ]]; then
  echo "Missing APP_SPECIFIC_PASSWORD (Apple ID app-specific password)."
  exit 1
fi

echo "Storing notary profile '$KEYCHAIN_PROFILE' for Apple ID '$APPLE_ID'..."
xcrun notarytool store-credentials "$KEYCHAIN_PROFILE" \
  --apple-id "$APPLE_ID" \
  --team-id "$TEAM_ID" \
  --password "$APP_SPECIFIC_PASSWORD"

echo "Done. You can now run build_sign_notarize_app.sh"

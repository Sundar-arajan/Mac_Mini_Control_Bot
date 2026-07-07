#!/bin/bash
set -euo pipefail

SERVICE_LABEL="com.macmini.controlbot"
PLIST_PATH="$HOME/Library/LaunchAgents/$SERVICE_LABEL.plist"

launchctl unload "$PLIST_PATH" 2>/dev/null || true
rm -f "$PLIST_PATH"

echo "Uninstalled: $SERVICE_LABEL"

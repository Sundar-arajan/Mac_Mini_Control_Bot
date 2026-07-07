#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_LABEL="com.macmini.controlbot"
PLIST_PATH="$HOME/Library/LaunchAgents/$SERVICE_LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Library/Logs"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$SERVICE_LABEL</string>

    <key>ProgramArguments</key>
    <array>
      <string>$PROJECT_DIR/.venv/bin/python</string>
      <string>$PROJECT_DIR/bot.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/macmini_controlbot.out.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/macmini_controlbot.err.log</string>
  </dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
launchctl start "$SERVICE_LABEL"

echo "Installed and started: $SERVICE_LABEL"
echo "Logs:"
echo "  $HOME/Library/Logs/macmini_controlbot.out.log"
echo "  $HOME/Library/Logs/macmini_controlbot.err.log"

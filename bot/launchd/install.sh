#!/usr/bin/env bash
# Agenda `orb-bot run-day` de segunda a sexta às 10:00 (hora local do Mac).
# O bot dorme sozinho até a abertura de NY, então funciona com e sem horário de verão US.
set -euo pipefail

LABEL="com.traider.orb-bot"
BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$BOT_DIR/.venv/bin/orb-bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
START_HOUR="${ORB_BOT_START_HOUR:-10}"

[[ -x "$BIN" ]] || { echo "Rode 'uv sync' em $BOT_DIR primeiro."; exit 1; }

weekdays=""
for day in 1 2 3 4 5; do
  weekdays+="<dict><key>Weekday</key><integer>$day</integer><key>Hour</key><integer>$START_HOUR</integer><key>Minute</key><integer>0</integer></dict>"
done

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string><string>-is</string>
    <string>$BIN</string><string>run-day</string>
  </array>
  <key>WorkingDirectory</key><string>$BOT_DIR</string>
  <key>StartCalendarInterval</key><array>$weekdays</array>
  <key>StandardOutPath</key><string>$BOT_DIR/state/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$BOT_DIR/state/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Instalado: $PLIST (seg–sex às ${START_HOUR}:00 locais)"
echo "Remover:   launchctl bootout gui/\$(id -u)/$LABEL && rm $PLIST"

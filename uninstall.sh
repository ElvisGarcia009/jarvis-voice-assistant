#!/usr/bin/env bash
# Removes Jarvis. Your settings and Groq key are kept unless you pass --purge.
set -euo pipefail

systemctl --user disable --now jarvis.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/jarvis.service"
systemctl --user daemon-reload
rm -rf "$HOME/.local/share/jarvis" "$HOME/.local/state/jarvis"

if [ "${1:-}" = "--purge" ]; then
  rm -rf "$HOME/.config/jarvis"
  echo "Jarvis, its settings and your Groq key were removed."
else
  echo "Jarvis was removed. Settings kept in ~/.config/jarvis (use --purge to delete them)."
fi

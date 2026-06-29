#!/usr/bin/env bash
set -euo pipefail

archive_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
enable_startup=0
if [[ "${1:-}" == "--enable-startup" ]]; then
  enable_startup=1
  shift
fi

binary="${1:-$archive_dir/AiOS-Assistant}"
desktop_file="${2:-$archive_dir/aios-assistant.desktop}"
icon="${3:-$archive_dir/aios-assistant.svg}"

install -Dm755 "$binary" "$HOME/.local/bin/AiOS-Assistant"
install -Dm644 "$desktop_file" "$HOME/.local/share/applications/aios-assistant.desktop"
install -Dm644 "$icon" "$HOME/.local/share/icons/hicolor/scalable/apps/aios-assistant.svg"

if [[ "$enable_startup" == "1" ]]; then
  install -Dm644 "$desktop_file" "$HOME/.config/autostart/aios-assistant.desktop"
fi

command -v update-desktop-database >/dev/null && \
  update-desktop-database "$HOME/.local/share/applications" || true

echo "AiOS Assistant installed for $USER."
if [[ "$enable_startup" == "1" ]]; then
  echo "AiOS Assistant will start when you log in."
fi

#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"

python -m pip install --user -r requirements-desktop.txt
python -m PyInstaller --clean --noconfirm desktop_app.spec

release_dir="$repo/release/arch"
mkdir -p "$release_dir"
install -Dm755 "dist/AiOS-Assistant" "$release_dir/AiOS-Assistant"
install -Dm644 "packaging/linux/aios-assistant.desktop" "$release_dir/aios-assistant.desktop"
install -Dm644 "app/static/icons/aios-icon.svg" "$release_dir/aios-assistant.svg"
install -Dm755 "packaging/linux/install-arch.sh" "$release_dir/install-arch.sh"

tar -C "$release_dir" -czf "$repo/release/AiOS-Assistant-arch-x86_64.tar.gz" \
  AiOS-Assistant aios-assistant.desktop aios-assistant.svg install-arch.sh

echo "Built $repo/release/AiOS-Assistant-arch-x86_64.tar.gz"

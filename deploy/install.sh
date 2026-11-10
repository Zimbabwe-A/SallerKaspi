#!/bin/zsh
# Ставит бэкенд и сайт в автозапуск macOS (работают без Claude, поднимаются после перезагрузки).
set -e
cd "$(dirname "$0")"
mkdir -p ~/Library/Logs/SallerKaspi ~/Library/LaunchAgents
for s in backend web; do
  launchctl bootout gui/$(id -u)/kz.sallerkaspi.$s 2>/dev/null || true
  cp kz.sallerkaspi.$s.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/kz.sallerkaspi.$s.plist
done
echo "Готово. Сайт: http://localhost:5173  Логи: ~/Library/Logs/SallerKaspi"

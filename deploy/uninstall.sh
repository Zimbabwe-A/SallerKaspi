#!/bin/zsh
# Убирает автозапуск.
for s in backend web; do
  launchctl bootout gui/$(id -u)/kz.sallerkaspi.$s 2>/dev/null || true
  rm -f ~/Library/LaunchAgents/kz.sallerkaspi.$s.plist
done
echo "Автозапуск удалён."

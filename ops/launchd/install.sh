#!/bin/sh
# Install (or re-install) the two launchd jobs for THIS checkout -- run it
# from the prod worktree, never from the dev checkout (AGENTS.md §8).
#
#   ops/launchd/install.sh [python]      # default: <repo>/venv/bin/python
#   ops/launchd/install.sh uninstall
set -eu
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

if [ "${1:-}" = "uninstall" ]; then
  for job in com.volley.inbox com.volley.backup; do
    launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
    rm -f "$AGENTS/$job.plist"
  done
  echo "uninstalled"
  exit 0
fi

PYTHON="${1:-$REPO/venv/bin/python}"
mkdir -p "$AGENTS" "$REPO/data"
for job in com.volley.inbox com.volley.backup; do
  sed -e "s|__REPO__|$REPO|g" -e "s|__PYTHON__|$PYTHON|g" \
    "$REPO/ops/launchd/$job.plist" > "$AGENTS/$job.plist"
  plutil -lint "$AGENTS/$job.plist" >/dev/null
  launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$AGENTS/$job.plist"
  echo "installed $job (repo $REPO)"
done
echo "logs: $REPO/data/inbox.log, $REPO/data/backup.log"

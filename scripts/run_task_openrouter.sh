#!/bin/bash
# usage: run_task_openrouter.sh <prompt_file> <log_file>
cd "$(dirname "$0")/.." || exit 1   # the repo root, wherever it is checked out
export PI_CODING_AGENT_DIR=$HOME/.pi-openroute
pi -p --model ${MODEL:-stealth/space-bunny-alpha} --thinking ${THINK:-max} "$(cat "$1")" > "$2" 2>&1 < /dev/null
echo "EXIT $?" >> "$2"

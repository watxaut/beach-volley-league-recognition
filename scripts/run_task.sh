#!/bin/bash
# usage: run_task.sh <prompt_file> <log_file>
cd "$(dirname "$0")/.." || exit 1   # the repo root, wherever it is checked out
export PI_CODING_AGENT_DIR=$HOME/.pi/agent
pi -p --model zai/glm-5.3-flash --thinking ${THINK:-high} "$(cat "$1")" > "$2" 2>&1 < /dev/null
echo "EXIT $?" >> "$2"

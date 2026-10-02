#!/bin/bash
# usage: run_task_openrouter.sh <prompt_file> <log_file>
cd /Users/joan.heredia/Documents/personal/projects/volley_recognition
export PI_CODING_AGENT_DIR=$HOME/.pi-openroute
pi -p --model ${MODEL:-stealth/space-bunny-alpha} --thinking ${THINK:-max} "$(cat "$1")" > "$2" 2>&1 < /dev/null
echo "EXIT $?" >> "$2"

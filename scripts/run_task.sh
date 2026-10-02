#!/bin/bash
# usage: run_task.sh <prompt_file> <log_file>
cd /Users/joan.heredia/Documents/personal/projects/volley_recognition
export PI_CODING_AGENT_DIR=$HOME/.pi/agent
pi -p --model zai/glm-5.3-flash --thinking ${THINK:-high} "$(cat "$1")" > "$2" 2>&1 < /dev/null
echo "EXIT $?" >> "$2"

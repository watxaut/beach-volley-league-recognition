#!/bin/bash
# usage: run_task.sh <prompt_file> <log_file>
# use GLM 5.3 for more reasoning tasks, use GLM 5.3 flash for faster work and tasks that require reading images
cd /Users/joan.heredia/Documents/personal/projects/volley_recognition
export PI_CODING_AGENT_DIR=$HOME/.pi/agent
pi -p --model ${MODEL:-zai/glm-5.3} --thinking ${THINK:-max} "$(cat "$1")" > "$2" 2>&1 < /dev/null
echo "EXIT $?" >> "$2"

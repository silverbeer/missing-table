#!/bin/bash
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name')
PERCENT_USED=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
REMAINING=$((100 - ${PERCENT_USED%.*}))

if [ "$REMAINING" -le 25 ]; then
    echo "[$MODEL] Context: ${PERCENT_USED}% - ⚠️ COMPACT SOON"
else
    echo "[$MODEL] Context: ${PERCENT_USED}%"
fi

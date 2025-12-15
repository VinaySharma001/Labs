#!/usr/bin/env bash
# validator.sh - checks app health and long-term fix
set -e
OK=true
MSG=()

# 1) check /health
if ! curl -s -S http://127.0.0.1:8080/health >/dev/null; then
  OK=false
  MSG+=("Health endpoint not reachable")
else
  MSG+=("Health endpoint ok")
fi

# 2) check process (flask app)
if ! pgrep -f app.py >/dev/null; then
  OK=false
  MSG+=("App process not running")
else
  MSG+=("App process running")
fi

# 3) check long-term fix marker
if [ -f /opt/app/long_term_fix.txt ]; then
  MSG+=("Long-term fix detected")
else
  OK=false
  MSG+=("Long-term fix not detected")
fi

if [ "$OK" = true ]; then
  echo "PASS"
  for m in "${MSG[@]}"; do printf "%s\n" "$m"; done
  exit 0
else
  echo "FAIL"
  for m in "${MSG[@]}"; do printf "%s\n" "$m"; done
  exit 2
fi

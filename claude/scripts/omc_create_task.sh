#!/bin/bash
# omc_create_task.sh - Safe task creation wrapper for omc team CLI
#
# Background:
#   omc team api create-task interleaves a stderr-like line "[team] canonicalized
#   duplicate worker entries: worker-1" with its JSON response on stdout. This
#   breaks naive `... --json | python -m json.tool` pipelines and has caused
#   duplicate task creation when retried.
#
# This wrapper:
#   1. Reads task description from a file (avoids shell escaping issues with
#      long descriptions containing quotes, $, backticks).
#   2. Composes a JSON payload via python (proper escaping of newlines/unicode).
#   3. Calls omc team api create-task and filters out stderr lines via `grep '^{'`.
#   4. Parses the JSON response and prints the new task_id.
#   5. Exits non-zero on failure with a clear error message.
#
# Usage:
#   omc_create_task.sh <team_name> <subject> <description_file>
#   omc_create_task.sh <team_name> <subject> -  (description from stdin)
#
# Examples:
#   omc_create_task.sh defense-ppt-editor-worker-for "P3 swap figures" /tmp/p3_desc.md
#   echo "Short task" | omc_create_task.sh my-team "Quick task" -
#
# Exit codes:
#   0 = task created, task_id printed to stdout
#   1 = omc CLI failure
#   2 = JSON parse failure
#   3 = invalid args
#   4 = description file not found

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <team_name> <subject> <description_file_or_->" >&2
  exit 3
fi

TEAM="$1"
SUBJECT="$2"
DESC_FILE="$3"

if [[ "$DESC_FILE" == "-" ]]; then
  DESC="$(cat)"
elif [[ -f "$DESC_FILE" ]]; then
  DESC="$(cat "$DESC_FILE")"
else
  echo "[err] description file not found: $DESC_FILE" >&2
  exit 4
fi

# Build JSON payload safely via python (handles newlines, quotes, unicode)
PAYLOAD=$(python3 - "$TEAM" "$SUBJECT" "$DESC" <<'PYEOF'
import json, sys
team, subject, desc = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({"team_name": team, "subject": subject, "description": desc}, ensure_ascii=False))
PYEOF
)

# Call omc + strip non-JSON lines (omc emits "[team] canonicalized..." on stdout)
RAW=$(omc team api create-task --input "$PAYLOAD" --json 2>&1) || {
  echo "[err] omc team api create-task failed" >&2
  echo "$RAW" | head -10 >&2
  exit 1
}

# Filter to JSON-only line(s) and parse
JSON_LINE=$(echo "$RAW" | grep '^{' | head -1)
if [[ -z "$JSON_LINE" ]]; then
  echo "[err] no JSON response from omc CLI" >&2
  echo "$RAW" | head -10 >&2
  exit 2
fi

# Extract task_id
TASK_ID=$(python3 - "$JSON_LINE" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
    if not d.get("ok"):
        print(f"[err] omc reported failure: {d}", file=sys.stderr)
        sys.exit(2)
    t = d["data"]["task"]
    print(t["id"])
except Exception as e:
    print(f"[err] JSON parse: {e}", file=sys.stderr)
    print(f"raw: {sys.argv[1][:200]}", file=sys.stderr)
    sys.exit(2)
PYEOF
) || exit 2

echo "$TASK_ID"

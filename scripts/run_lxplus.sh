#!/usr/bin/env bash
set -euo pipefail
RELEASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# This candidate path comes from the collected startup.sh. Its existence and
# imports are verified by the first environment command; it is not assumed valid.
ANALYSIS_PYTHON="${JPSIDSTAR_PYTHON:-/eos/user/j/jgomespi/.mamba-jpsidstar/envs/python310-jpsidstar/bin/python}"
if [[ ! -x "$ANALYSIS_PYTHON" ]]; then
  echo "Analysis Python is not executable: $ANALYSIS_PYTHON" >&2
  echo "Set JPSIDSTAR_PYTHON to the actual analysis interpreter and rerun." >&2
  exit 2
fi
exec env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH PYTHONNOUSERSITE=1 \
  "$ANALYSIS_PYTHON" -u "$RELEASE_ROOT/scripts/run_reproduction.py" "$@"

#!/usr/bin/env bash
# run_codex_exec.sh - Codex CLI wrapper script (em-review plugin SSOT)
#
# Usage:
#   run_codex_exec.sh readonly  "prompt"           # Review/analysis (no file changes)
#   run_codex_exec.sh readwrite "prompt"           # Code generation (file changes allowed)
#   run_codex_exec.sh readonly  -C /path "prompt"  # With working directory
#   run_codex_exec.sh readonly  --output-schema schema.json "prompt"
#
# Options passed through to codex exec:
#   -C DIR             Set working directory
#   --output-schema F  Pass JSON Schema for structured output
#
# Model is determined by the user's ~/.codex/config.toml.
# Timeout and flags are read from references/codex-cli.yaml.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../references/codex-cli.yaml"

# --- Parse codex-cli.yaml ---
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

# Simple YAML parser using grep/sed (no external dependencies)
parse_yaml_value() {
  local key="$1"
  grep "^${key}:" "$CONFIG_FILE" | sed "s/^${key}: *//" | tr -d '"' | tr -d "'"
}

TIMEOUT="$(parse_yaml_value 'timeout')"

# --- Parse arguments ---
if [[ $# -lt 2 ]]; then
  echo "Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] [--output-schema F] \"prompt\"" >&2
  exit 1
fi

MODE="$1"
shift

# Validate mode
case "$MODE" in
  readonly)
    SANDBOX_FLAG="-s read-only"
    PROMPT_CONSTRAINT="IMPORTANT: Do NOT modify, create, or delete any files. Provide analysis and recommendations only."
    ;;
  readwrite)
    SANDBOX_FLAG="-s workspace-write"
    PROMPT_CONSTRAINT=""
    ;;
  *)
    echo "ERROR: Invalid mode '$MODE'. Use 'readonly' or 'readwrite'." >&2
    exit 1
    ;;
esac

# Parse optional flags
WORKDIR_FLAG=""
SCHEMA_FLAG=""
while [[ "${1:-}" == -* ]]; do
  case "$1" in
    -C)
      if [[ $# -lt 3 ]]; then
        echo "ERROR: -C requires a directory argument" >&2
        exit 1
      fi
      WORKDIR_FLAG="-C $2"
      shift 2
      ;;
    --output-schema)
      if [[ $# -lt 3 ]]; then
        echo "ERROR: --output-schema requires a file argument" >&2
        exit 1
      fi
      SCHEMA_FLAG="--output-schema $2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown flag '$1'" >&2
      exit 1
      ;;
  esac
done

# Remaining argument is the prompt
if [[ $# -lt 1 ]]; then
  echo "ERROR: No prompt provided" >&2
  exit 1
fi

PROMPT="$1"

# --- Build final prompt ---
if [[ -n "$PROMPT_CONSTRAINT" ]]; then
  FULL_PROMPT="${PROMPT_CONSTRAINT}

${PROMPT}"
else
  FULL_PROMPT="$PROMPT"
fi

# --- Execute ---
# stdin is redirected from /dev/null so `codex exec` does not block reading
# additional input when invoked under a parent that leaves stdin as an open
# pipe (e.g. Claude Code's Bash tool). Without this, codex prints
# "Reading additional input from stdin..." and hangs until EOF, producing
# non-deterministic timeouts when multiple reviewers run in parallel.
# shellcheck disable=SC2086
timeout "$TIMEOUT" codex exec \
  --color never \
  --skip-git-repo-check \
  $SANDBOX_FLAG \
  $WORKDIR_FLAG \
  $SCHEMA_FLAG \
  "$FULL_PROMPT" </dev/null 2>&1

exit_code=$?

if [[ $exit_code -eq 124 ]]; then
  echo "CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds" >&2
  exit 124
fi

exit $exit_code

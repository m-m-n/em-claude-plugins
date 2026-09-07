#!/usr/bin/env bash
# run_codex_exec.sh - Codex CLI wrapper script (em-workflow plugin SSOT)
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
# Model: --ignore-user-config skips ~/.codex/config.toml (auth is kept), so
# with no -m flag Codex resolves its recommended default model (auto-track).
# Timeout and flags are read from references/codex-cli.yaml.
# Reasoning effort: readonly (review) mode forces xhigh via -c override;
# readwrite mode runs with the model's default effort.
#
# Provider fallback chain: three fixed entries are tried, in order, on a
# provider outage. Entry 1 is the invocation above, unmodified. Entry 1
# hands over to entry 2 on a usage-limit response; entry 2 hands over to
# entry 3 on a provider error. Any other non-zero outcome -- including a
# timeout, with its existing diagnostic and exit code -- is NOT a switch
# condition: it surfaces to the caller unchanged and the chain stops there.
# On entry 1 the wrapper's output is byte-identical to the invocation above,
# with no marker of any kind. When and only when a later entry answered,
# exactly one line prefixed `CODEX_FALLBACK:` is written to stderr (never
# stdout), naming which entry answered. The chain, its order, its entry
# definitions and its switch conditions live only in this script.

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
    SANDBOX_FLAG=(-s read-only)
    EFFORT_FLAG=(-c 'model_reasoning_effort="xhigh"')
    PROMPT_CONSTRAINT="IMPORTANT: Do NOT modify, create, or delete any files. Provide analysis and recommendations only."
    ;;
  readwrite)
    SANDBOX_FLAG=(-s workspace-write)
    EFFORT_FLAG=()
    PROMPT_CONSTRAINT=""
    ;;
  *)
    echo "ERROR: Invalid mode '$MODE'. Use 'readonly' or 'readwrite'." >&2
    exit 1
    ;;
esac

# Parse optional flags
WORKDIR_FLAG=()
SCHEMA_FLAG=()
while [[ "${1:-}" == -* ]]; do
  case "$1" in
    -C)
      if [[ $# -lt 3 ]]; then
        echo "ERROR: -C requires a directory argument" >&2
        exit 1
      fi
      WORKDIR_FLAG=(-C "$2")
      shift 2
      ;;
    --output-schema)
      if [[ $# -lt 3 ]]; then
        echo "ERROR: --output-schema requires a file argument" >&2
        exit 1
      fi
      SCHEMA_FLAG=(--output-schema "$2")
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

# --- Provider chain (fallback on outage) ---
# Entry 1 is today's invocation, unmodified (no override). Entries 2 and 3
# are named provider configurations applied via -c overrides, so an
# observer of the invocation can tell which entry is being attempted.
PROVIDER_ARGS_1=()
PROVIDER_ARGS_2=(-c 'model_provider="codex-fallback-provider-beta"')
PROVIDER_ARGS_3=(-c 'model_provider="codex-fallback-provider-gamma"')
PROVIDER_NAME_2="codex-fallback-provider-beta"
PROVIDER_NAME_3="codex-fallback-provider-gamma"

OUTFILE="$(mktemp)"
trap 'rm -f "$OUTFILE"' EXIT

# Runs one chain entry; extra provider args (if any) are passed as "$@".
# Writes the attempt's combined stdout+stderr to $OUTFILE (truncating
# whatever a prior attempt left there) and sets $ATTEMPT_EXIT_CODE.
#
# stdin is redirected from /dev/null so `codex exec` does not block reading
# additional input when invoked under a parent that leaves stdin as an open
# pipe (e.g. Claude Code's Bash tool). Without this, codex prints
# "Reading additional input from stdin..." and hangs until EOF, producing
# non-deterministic timeouts when multiple reviewers run in parallel.
# The `|| ATTEMPT_EXIT_CODE=$?` guard is required: under `set -e` an
# unguarded non-zero exit (e.g. timeout's 124) would terminate the script
# before the handler below ever runs, silencing the CODEX_TIMEOUT
# diagnostic.
# --ignore-rules: the reviewed repository is untrusted input, but without
# this flag codex loads project-local execpolicy `.rules` from the workdir,
# letting the repo under review configure the reviewer's own execution
# policy. Trade-off (deliberate, personal-use premise): user-level `.rules`
# are skipped too — there is no flag that ignores only project rules.
run_attempt() {
  ATTEMPT_EXIT_CODE=0
  timeout "$TIMEOUT" codex exec \
    --color never \
    --skip-git-repo-check \
    --ignore-rules \
    --ignore-user-config \
    "${SANDBOX_FLAG[@]}" \
    "${EFFORT_FLAG[@]}" \
    "${WORKDIR_FLAG[@]}" \
    "${SCHEMA_FLAG[@]}" \
    "$@" \
    "$FULL_PROMPT" </dev/null > "$OUTFILE" 2>&1 || ATTEMPT_EXIT_CODE=$?
}

# Response-shape recognition: the underlying CLI's output is the only signal
# available, so a switch condition is a text match on the captured attempt,
# never an exit-code match alone (a timeout's 124 must never be mistaken for
# either shape below).
is_usage_limit_response() { grep -qi 'usage limit' "$OUTFILE"; }
is_provider_error_response() { grep -qi 'provider error' "$OUTFILE"; }

emit_timeout_and_exit() {
  cat "$OUTFILE"
  echo "CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds" >&2
  exit 124
}

# Entry 1
run_attempt "${PROVIDER_ARGS_1[@]}"
exit_code=$ATTEMPT_EXIT_CODE
answering_entry=1

if [[ $exit_code -eq 124 ]]; then
  emit_timeout_and_exit
fi

if [[ $exit_code -ne 0 ]] && is_usage_limit_response; then
  # Entry 2
  run_attempt "${PROVIDER_ARGS_2[@]}"
  exit_code=$ATTEMPT_EXIT_CODE
  answering_entry=2

  if [[ $exit_code -eq 124 ]]; then
    emit_timeout_and_exit
  fi

  if [[ $exit_code -ne 0 ]] && is_provider_error_response; then
    # Entry 3
    run_attempt "${PROVIDER_ARGS_3[@]}"
    exit_code=$ATTEMPT_EXIT_CODE
    answering_entry=3

    if [[ $exit_code -eq 124 ]]; then
      emit_timeout_and_exit
    fi
  fi
fi

cat "$OUTFILE"

if [[ $exit_code -eq 0 && $answering_entry -ne 1 ]]; then
  case "$answering_entry" in
    2) echo "CODEX_FALLBACK: entry 2 (${PROVIDER_NAME_2}) answered" >&2 ;;
    3) echo "CODEX_FALLBACK: entry 3 (${PROVIDER_NAME_3}) answered" >&2 ;;
  esac
fi

exit $exit_code

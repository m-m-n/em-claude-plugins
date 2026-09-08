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
# provider outage. Entry 1 is the invocation above, unmodified (still with
# --ignore-user-config). Entries 2 and 3 select the litellm proxy's
# Vertex-fronted and Muse-fronted models (`-p litellm -m vertex-glm-5.2` /
# `-p litellm -m muse-spark`) -- the SAME proxy profile and model-selection
# form the review chain's litellm harness already uses
# (references/reviewers.yaml), never a second description of a deployment
# this script does not own. Entries 2/3 do NOT pass --ignore-user-config,
# so the `litellm` profile they select is not suppressed by the same
# invocation that selects it. Entry 1 hands over to entry 2 on a
# usage-limit response; entry 2 hands over to entry 3 on a provider error.
# Any other non-zero outcome -- including a timeout, with its existing
# diagnostic and exit code -- is NOT a switch condition: it surfaces to the
# caller unchanged and the chain stops there.
#
# Switch-shape stream: a switch is recognized ONLY from an attempt's
# STDERR -- the underlying CLI's own diagnostic -- never from stdout (the
# model-generated reply, which quotes the reviewed repository and is
# attacker-influenceable). A shape appearing only on stdout never switches.
#
# Fallback environment prerequisites: entries 2 and 3 both require the
# LITELLM_API_KEY environment variable (proxy auth) to be non-empty AND
# ~/.codex/litellm.config.toml (the `-p litellm` profile) to exist -- the
# same two conditions references/review-phase.md's harness probe already
# checks. When a switch condition fires but either is absent, the chain
# stops immediately without attempting that entry: the caller receives the
# failing entry's own exit code and output, and exactly one stderr
# diagnostic prefixed `CODEX_FALLBACK_UNCONFIGURED:` names the fallback
# entry that was not configured.
#
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
# Entry 1 is today's invocation, unmodified. Entries 2 and 3 select the
# litellm proxy's Vertex-fronted and Muse-fronted models by reusing the
# SAME proxy profile (`-p litellm`) and model-selection flag (`-m <model>`)
# the review chain's litellm harness already depends on
# (references/reviewers.yaml) -- never a provider definition this script
# invents on its own.
ENTRY_ARGS_1=(--ignore-user-config)
ENTRY_ARGS_2=(-p litellm -m vertex-glm-5.2)
ENTRY_ARGS_3=(-p litellm -m muse-spark)
PROVIDER_NAME_2="litellm/vertex-glm-5.2"
PROVIDER_NAME_3="litellm/muse-spark"

# Fallback environment prerequisites (see header comment): both non-primary
# entries need the SAME litellm proxy auth and profile. Checked once per
# switch point -- before launching an invocation that can only fail -- so
# the caller can tell "the fallback was never available" from "the
# fallback was tried and failed".
FALLBACK_PROFILE_FILE="${HOME:-}/.codex/litellm.config.toml"
fallback_prerequisites_present() {
  [[ -n "${LITELLM_API_KEY:-}" ]] && [[ -f "$FALLBACK_PROFILE_FILE" ]]
}

OUTFILE="$(mktemp)"
ERRFILE="$(mktemp)"
trap 'rm -f "$OUTFILE" "$ERRFILE"' EXIT

# Runs one chain entry; extra provider args (if any) are passed as "$@".
# Writes the attempt's stdout to $OUTFILE and stderr to $ERRFILE separately
# (truncating whatever a prior attempt left there) and sets
# $ATTEMPT_EXIT_CODE. Kept separate (rather than 2>&1 into one file) so the
# switch-condition matches below can be scoped to the CLI's own stderr
# diagnostics and never to Codex's model-generated stdout reply, which
# quotes the reviewed repository and is attacker-influenceable.
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
    "${SANDBOX_FLAG[@]}" \
    "${EFFORT_FLAG[@]}" \
    "${WORKDIR_FLAG[@]}" \
    "${SCHEMA_FLAG[@]}" \
    "$@" \
    "$FULL_PROMPT" </dev/null > "$OUTFILE" 2> "$ERRFILE" || ATTEMPT_EXIT_CODE=$?
}

# Response-shape recognition: matches run only against $ERRFILE (the CLI's
# own stderr diagnostics), never against $OUTFILE (Codex's model-generated
# stdout reply, which quotes the reviewed repository and is
# attacker-influenceable). A switch condition is a text match on the
# captured attempt's stderr, never an exit-code match alone (a timeout's 124
# must never be mistaken for either shape below).
is_usage_limit_response() { grep -qi 'usage limit' "$ERRFILE"; }
is_provider_error_response() { grep -qi 'provider error' "$ERRFILE"; }

emit_timeout_and_exit() {
  cat "$OUTFILE" "$ERRFILE"
  echo "CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds" >&2
  exit 124
}

# Entry 1
run_attempt "${ENTRY_ARGS_1[@]}"
exit_code=$ATTEMPT_EXIT_CODE
answering_entry=1

if [[ $exit_code -eq 124 ]]; then
  emit_timeout_and_exit
fi

if [[ $exit_code -ne 0 ]] && is_usage_limit_response; then
  if fallback_prerequisites_present; then
    # Entry 2
    run_attempt "${ENTRY_ARGS_2[@]}"
    exit_code=$ATTEMPT_EXIT_CODE
    answering_entry=2

    if [[ $exit_code -eq 124 ]]; then
      emit_timeout_and_exit
    fi

    if [[ $exit_code -ne 0 ]] && is_provider_error_response; then
      if fallback_prerequisites_present; then
        # Entry 3
        run_attempt "${ENTRY_ARGS_3[@]}"
        exit_code=$ATTEMPT_EXIT_CODE
        answering_entry=3

        if [[ $exit_code -eq 124 ]]; then
          emit_timeout_and_exit
        fi
      else
        echo "CODEX_FALLBACK_UNCONFIGURED: entry 3 (${PROVIDER_NAME_3}) was not configured -- LITELLM_API_KEY or ${FALLBACK_PROFILE_FILE} not present, so it was not attempted" >&2
      fi
    fi
  else
    echo "CODEX_FALLBACK_UNCONFIGURED: entry 2 (${PROVIDER_NAME_2}) was not configured -- LITELLM_API_KEY or ${FALLBACK_PROFILE_FILE} not present, so it was not attempted" >&2
  fi
fi

cat "$OUTFILE" "$ERRFILE"

if [[ $exit_code -eq 0 && $answering_entry -ne 1 ]]; then
  case "$answering_entry" in
    2) echo "CODEX_FALLBACK: entry 2 (${PROVIDER_NAME_2}) answered" >&2 ;;
    3) echo "CODEX_FALLBACK: entry 3 (${PROVIDER_NAME_3}) answered" >&2 ;;
  esac
fi

exit $exit_code

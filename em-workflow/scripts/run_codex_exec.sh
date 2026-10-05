#!/usr/bin/env bash
# run_codex_exec.sh - Codex CLI wrapper script (em-workflow plugin SSOT)
#
# Usage:
#   run_codex_exec.sh readonly  "prompt"           # Review/analysis (no file changes)
#   run_codex_exec.sh readwrite "prompt"           # Code generation (file changes allowed)
#   run_codex_exec.sh readonly  -C /path "prompt"  # With working directory
#   run_codex_exec.sh readonly  --output-schema schema.json "prompt"
#   run_codex_exec.sh readonly  --litellm muse-spark "prompt"
#
# Options passed through to codex exec:
#   -C DIR             Set working directory
#   --output-schema F  Pass JSON Schema for structured output
#   --litellm MODEL    Route through the local LiteLLM proxy: expands to
#                      `-p litellm -m MODEL` and drops --ignore-user-config,
#                      because that flag suppresses the profile layering
#                      `-p litellm` depends on. MODEL is passed verbatim.
#                      The launch runs in a launch-dedicated Codex home that
#                      holds only the user's litellm profile (see "Launch
#                      home on the --litellm route" below).
#
# Model: --ignore-user-config skips ~/.codex/config.toml (auth is kept), so
# with no -m flag Codex resolves its recommended default model (auto-track).
# --litellm names the model explicitly instead.
# Timeout and flags are read from references/codex-cli.yaml.
# Reasoning effort: readonly (review) mode forces xhigh via -c override;
# readwrite mode runs with the model's default effort.
#
# `codex exec` is launched exactly once per invocation of this script. Its
# own exit code is this script's exit code, except that exceeding the
# configured timeout below yields exit code 124 together with one stderr
# diagnostic. Nothing about the launch's own output shapes what happens
# next -- there is no response-shape recognition of any kind here.

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
  echo "Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] [--output-schema F] [--litellm MODEL] \"prompt\"" >&2
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
PROFILE_FLAG=()
# Cleared by --litellm: see the flag's entry below.
USER_CONFIG_FLAG=(--ignore-user-config)
# Set to 1 by --litellm: the launch then gets a Codex home of its own (below).
LITELLM_ROUTE=0
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
    --litellm)
      if [[ $# -lt 3 ]]; then
        echo "ERROR: --litellm requires a model argument" >&2
        exit 1
      fi
      PROFILE_FLAG=(-p litellm -m "$2")
      # `-p litellm` layers ${CODEX_HOME:-$HOME/.codex}/litellm.config.toml
      # over the user config; --ignore-user-config suppresses that layering,
      # so this path must not carry it. Reading the user config is what lets
      # a trust entry reach Codex, so the launch is given a Codex home of its
      # own instead (see "Launch home on the --litellm route" below).
      USER_CONFIG_FLAG=()
      LITELLM_ROUTE=1
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

# --- OpenTelemetry ---
# --ignore-user-config also drops the user's [otel] section, so when
# CODEX_OTLP_ENDPOINT is set the exporter is passed as -c overrides instead.
# The value is used verbatim as the OTLP/HTTP logs URL (e.g.
# http://127.0.0.1:4318/v1/logs); codex does not append /v1/logs itself.
OTEL_FLAG=()
if [[ -n "${CODEX_OTLP_ENDPOINT:-}" ]]; then
  OTEL_FLAG=(
    -c 'otel.environment="local"'
    -c "otel.exporter={otlp-http={endpoint=\"${CODEX_OTLP_ENDPOINT}\",protocol=\"binary\"}}"
  )
fi

# --- Interactive-guard hook ---
# Every launch registers scripts/codex-hook-interactive-guard.py (the copy next
# to this wrapper) as a PreToolUse hook for Bash tool calls. A hook given by
# -c has no persisted trust (Codex reports it as untrusted), so
# --dangerously-bypass-hook-trust is what lets it run. That flag lifts the
# hook-trust gate for every hook Codex loads, so what matters is which
# configuration layers Codex loads. Observed on Codex 0.160.0
# (feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md): the hook
# tables of the working directory's .codex/config.toml and its
# .codex/hooks.json (and those of the directories above it up to the project
# root) are loaded only when the user-level Codex configuration marks the
# project trusted -- or, on a launch that reads the user-level configuration,
# when the sandbox is writable, because Codex then marks an unmarked project
# trusted itself.
#   - Default route: --ignore-user-config means no trust entry is read, so
#     repository hooks did not run in either mode; that flag stays on the
#     launch below, as does --ignore-rules.
#   - --litellm route: repository hooks ran (project trusted in the user
#     config; or untrusted with a writable sandbox). The launch therefore runs
#     in a launch-dedicated Codex home (see "Launch home on the --litellm
#     route" below); the wrapper's own PreToolUse registration here still
#     fires and runs alongside any repository PreToolUse hook.
# The path is derived from this script's own location, never from the caller's
# working directory. The wrapper does not check that the file exists: when it
# is missing, Codex runs the Bash call unguarded (fail-open by design).
#
# Codex 0.160.0 runs the hook command through a POSIX shell, so the absolute
# path is single-quoted for the shell first, and the resulting command is then
# written as a TOML basic string. Both layers round-trip any path, including
# one with spaces, quotes, backslashes or other shell metacharacters.

# Prints $1 single-quoted for a POSIX shell.
shell_single_quote() {
  local rest="$1" out="'" q="'"
  while [[ "$rest" == *"$q"* ]]; do
    out+="${rest%%"$q"*}'\\''"
    rest="${rest#*"$q"}"
  done
  out+="${rest}'"
  printf '%s' "$out"
}

# Prints $1 as a TOML basic string, surrounding double quotes included.
# Backslash and double quote are escaped; control characters become \uXXXX.
toml_basic_string() {
  local s="$1" out="" c code i
  local LC_ALL=C
  for (( i = 0; i < ${#s}; i++ )); do
    c="${s:i:1}"
    case "$c" in
      '\') out+='\\' ;;
      '"') out+='\"' ;;
      *)
        printf -v code '%d' "'$c"
        if (( code < 32 || code == 127 )); then
          printf -v c '\\u%04X' "$code"
        fi
        out+="$c"
        ;;
    esac
  done
  printf '"%s"' "$out"
}

HOOK_SCRIPT="${SCRIPT_DIR}/codex-hook-interactive-guard.py"
HOOK_COMMAND="python3 $(shell_single_quote "$HOOK_SCRIPT")"
HOOK_FLAG=(
  -c "hooks.PreToolUse=[{matcher=\"Bash\", hooks=[{type=\"command\", command=$(toml_basic_string "$HOOK_COMMAND")}]}]"
  --dangerously-bypass-hook-trust
)

# --- Launch home on the --litellm route ---
# The default route reads no user-level Codex configuration, so no project
# trust reaches it. The --litellm route has to read it (the profile layers on
# top of it), and with it the user's project trust entries -- which make Codex
# load the reviewed repository's .codex/ hooks, outside the Codex sandbox and
# with the hook-trust gate lifted above. A writable sandbox does the same on
# its own: Codex records an unmarked working directory as trusted and loads it
# in the same run. An explicit `untrusted` entry is respected in both cases.
# So this route runs in a Codex home of its own, created per launch and
# removed afterwards: it holds a copy of the user's litellm profile and a
# config.toml marking the working directory -- in each spelling Codex may key
# it by -- and every directory above it as `untrusted`. No other file and no
# trust entry of the user's real Codex home reaches the launch, and the real
# home is never written. Credentials stay in the environment (LITELLM_API_KEY)
# and are never copied.

# Prints, NUL-terminated, directory $1 (made absolute) and every directory
# above it, once each, under the spellings Codex may key a project by: as
# given, logical (`pwd` after cd) and physical (`pwd -P` after cd).
untrusted_directories() {
  local dir="$1" spelling d known found
  local -a spellings chain
  [[ "$dir" == /* ]] || dir="${PWD}/${dir}"
  while [[ "$dir" == */ && "$dir" != "/" ]]; do dir="${dir%/}"; done
  spellings=("$dir")
  spelling="$(cd "$dir" 2>/dev/null && pwd)" || spelling=""
  if [[ -n "$spelling" ]]; then spellings+=("$spelling"); fi
  spelling="$(cd "$dir" 2>/dev/null && pwd -P)" || spelling=""
  if [[ -n "$spelling" ]]; then spellings+=("$spelling"); fi
  chain=()
  for spelling in "${spellings[@]}"; do
    d="$spelling"
    while :; do
      found=0
      for known in ${chain[@]+"${chain[@]}"}; do
        if [[ "$known" == "$d" ]]; then found=1; break; fi
      done
      if [[ $found -eq 0 ]]; then chain+=("$d"); fi
      if [[ "$d" == "/" ]]; then break; fi
      d="${d%/*}"
      if [[ -z "$d" ]]; then d="/"; fi
    done
  done
  printf '%s\0' "${chain[@]}"
}

OUTFILE="$(mktemp)"
ERRFILE="$(mktemp)"
LAUNCH_HOME=""
trap 'rm -f "$OUTFILE" "$ERRFILE"; if [[ -n "$LAUNCH_HOME" ]]; then rm -rf -- "$LAUNCH_HOME"; fi' EXIT

if [[ "$LITELLM_ROUTE" -eq 1 ]]; then
  USER_CODEX_HOME="${CODEX_HOME:-${HOME:-}/.codex}"
  LAUNCH_HOME="$(mktemp -d "${TMPDIR:-/tmp}/codex-launch-home.XXXXXX")"
  if [[ -f "${USER_CODEX_HOME}/litellm.config.toml" ]]; then
    cp -- "${USER_CODEX_HOME}/litellm.config.toml" "${LAUNCH_HOME}/litellm.config.toml"
  fi
  {
    while IFS= read -r -d '' untrusted_dir; do
      printf '[projects.%s]\ntrust_level = "untrusted"\n\n' "$(toml_basic_string "$untrusted_dir")"
    done < <(untrusted_directories "${WORKDIR_FLAG[1]:-$PWD}")
  } > "${LAUNCH_HOME}/config.toml"
  export CODEX_HOME="$LAUNCH_HOME"
fi

# Writes stdout to $OUTFILE and stderr to $ERRFILE separately, rather than
# into one combined stream: the underlying CLI writes a large banner to
# its diagnostic stream on every run, and interleaving it would place
# banner text inside a schema-constrained JSON reply. The two are
# concatenated stdout-first below, once the launch has completed.
#
# stdin is redirected from /dev/null so `codex exec` does not block reading
# additional input when invoked under a parent that leaves stdin as an open
# pipe (e.g. Claude Code's Bash tool). Without this, codex prints
# "Reading additional input from stdin..." and hangs until EOF, producing
# non-deterministic timeouts when multiple reviewers run in parallel.
# The `|| exit_code=$?` guard is required: under `set -e` an unguarded
# non-zero exit (e.g. timeout's 124) would terminate the script before the
# diagnostic below ever runs.
# --ignore-rules: the reviewed repository is untrusted input, but without
# this flag codex loads project-local execpolicy `.rules` from the workdir,
# letting the repo under review configure the reviewer's own execution
# policy. Trade-off (deliberate, personal-use premise): user-level `.rules`
# are skipped too — there is no flag that ignores only project rules.
exit_code=0
timeout "$TIMEOUT" codex exec \
  --color never \
  --skip-git-repo-check \
  --ignore-rules \
  "${SANDBOX_FLAG[@]}" \
  "${EFFORT_FLAG[@]}" \
  "${WORKDIR_FLAG[@]}" \
  "${SCHEMA_FLAG[@]}" \
  "${PROFILE_FLAG[@]}" \
  "${USER_CONFIG_FLAG[@]}" \
  "${OTEL_FLAG[@]}" \
  "${HOOK_FLAG[@]}" \
  "$FULL_PROMPT" </dev/null > "$OUTFILE" 2> "$ERRFILE" || exit_code=$?

if [[ $exit_code -eq 124 ]]; then
  cat "$OUTFILE" "$ERRFILE"
  echo "CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds" >&2
  exit 124
fi

cat "$OUTFILE" "$ERRFILE"
exit $exit_code

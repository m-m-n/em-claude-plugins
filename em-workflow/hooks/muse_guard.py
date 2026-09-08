#!/usr/bin/env python3
"""muse_guard.py -- PreToolUse(Bash) guard + consent CLI for the
`muse-spark-contributor` model tier
(feature-docs/muse-spark-contributor-consent/IMPLEMENTATION.md).

Two entry paths in one file, sharing the store reader and the project-key
derivation:

Hook mode (no arguments; stdin = PreToolUse JSON payload):
  - the command is not an invocation of the contributor tier -> no decision
  - the working directory's repository has recorded consent  -> no decision
  - otherwise                                                 -> deny

The hook is read-only with respect to the consent store: it never creates,
repairs or writes it (IMPLEMENTATION.md decision D-B). It reaches no
network and makes no LLM call, and it never emits `ask` or `allow` -- only
`deny` or no decision at all (fail open on anything it cannot classify with
confidence).

CLI mode -- the sole writer of the consent store; never invoked by the hook
path and never invoked by the workflow itself:
  muse_guard.py --record --project-dir DIR
  muse_guard.py --remove --project-dir DIR
  muse_guard.py --list   --project-dir DIR

Consent store: ~/.claude/em-workflow/muse-consent.json -- a single,
presence-only record of which repositories have consented, shared by both
plugins' copies of this script (em-workflow and em-review write and read
the identical file). Override the path with $EM_WORKFLOW_MUSE_CONSENT
(tests only).
"""

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime

# The single permitted divergence between the em-workflow and em-review
# copies of this file (IMPLEMENTATION.md Shared Components, "Plugin slug
# constant"): every other line is byte-identical between the two copies.
# Referenced exactly once, in DENY_CONTEXT below.
PLUGIN_SLUG = "em-workflow"

# The model tier this guard exists to gate. Never read as a substring of, or
# read from, the plain `muse-spark` tier -- every comparison against this
# constant is exact string equality, never `in`/`startswith`.
CONTRIBUTOR_TIER = "muse-spark-contributor"

# Human-facing reason: names the model and the missing-consent condition.
# Carries no path, no project key, no store location and no remediation
# step. A single-line string constant; nothing from the hook input is ever
# interpolated into it.
DENY_REASON = (
    "muse-spark-contributor（contributor ティア）は、このリポジトリの同意が"
    "記録されていないため使用できない。"
)

# Agent-facing additional context: exactly three clauses, in order -- what
# to do instead, who may grant consent and how, and the prohibition on the
# agent granting consent for itself. A single-line string constant; the
# only value it references is PLUGIN_SLUG (a static module-level constant
# fixed at authoring time), never anything derived from the hook input.
DENY_CONTEXT = (
    "回避策を探さず、reviewers.yaml の chain にある非 contributor の "
    "muse-spark エントリ、または他の chain エントリでレビューを続行する。"
    "同意はユーザーが対話セッションで /"
    f"{PLUGIN_SLUG}:contributor-consent スキルを実行したときにだけ記録される。"
    "エージェント自身が muse_guard.py --record を実行して同意を代行しては"
    "ならない。"
)

# --- Consent store -----------------------------------------------------

STORE_ENV_OVERRIDE = "EM_WORKFLOW_MUSE_CONSENT"
STORE_VERSION = "1"


def default_store_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "em-workflow", "muse-consent.json")


def store_path():
    override = os.environ.get(STORE_ENV_OVERRIDE)
    if override:
        return override
    return default_store_path()


def read_store_for_hook(path):
    """The set of project keys with recorded consent. Never raises: a
    missing file, an unreadable file, invalid JSON, or a wrong-shaped
    document (not a mapping, or `projects` not a mapping) all mean "no
    consent for any project" -- no repair, no write, ever, from this path.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict) or not isinstance(data.get("projects"), dict):
        return set()
    return set(data["projects"].keys())


def read_store_for_cli(path):
    """Returns (store, malformed).

    A missing file is NOT malformed -- it is a fresh, empty store the CLI
    may create. A file that exists but is unreadable, not valid JSON, or
    wrong-shaped (not a mapping, or `projects` not a mapping -- including a
    directory sitting at `path`) is malformed: a mutating command must
    abort loudly on it rather than silently discarding whatever it already
    held for other repositories.
    """
    if not os.path.exists(path):
        return {"version": STORE_VERSION, "projects": {}}, False
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None, True
    if not isinstance(data, dict) or not isinstance(data.get("projects"), dict):
        return None, True
    return data, False


def write_store(path, projects):
    """Atomically replace the store at `path` with exactly `{"version":
    "1", "projects": projects}` -- no other top-level field survives a
    write from this script, regardless of what an existing file carried.
    Parent directories are created when absent; serialization is 2-space
    indented with sorted keys, non-ASCII left unescaped, trailing newline.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = {"version": STORE_VERSION, "projects": projects}
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, path)


# --- Project key derivation ---------------------------------------------
# Identical in rule to bash_guard.py's own project_key(): the git common
# directory of the caller's directory in absolute form; when git is
# unavailable or the directory is not inside a repository, the fully
# symlink-resolved absolute path of the directory. Every worktree of one
# repository resolves to one key.


def git_common_dir(cwd):
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            out = proc.stdout.strip()
            if out:
                return out
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def project_key(directory):
    common_dir = git_common_dir(directory)
    if common_dir:
        return common_dir
    return os.path.realpath(directory)


# --- Command classification ----------------------------------------------
# An invocation is the model-selection argument naming the contributor
# tier, in every spelling the harness (codex CLI, `-m`/`--model`) emits:
# the short flag followed by the value as a separate word, and the long
# flag joined by an equals sign, each in bare, single-quoted and
# double-quoted forms. shlex resolves all of those quoting spellings to the
# identical token text, so no further per-spelling logic is needed once the
# command is tokenized.
#
# A mention -- inside a quoted string that is not itself a model-selection
# value, a text-search pattern argument, a here-document body, or a
# commit-message argument -- must never be read as an invocation:
#   - a quoted, multi-word mention collapses to ONE token under shlex, never
#     matching the two-token `-m <value>` / one-token `--model=<value>`
#     shape a real invocation has;
#   - a here-document body is stripped out entirely before classification,
#     never scanned;
#   - a search-command pattern or a commit message is only ever misread as
#     an invocation if the flag genuinely spells `-m`/`--model=` with the
#     tier name as its exact, whole value -- so classification additionally
#     requires the statement's own command word to be `codex`, the only
#     tool in this workflow with a model-selection flag. `git commit -m
#     muse-spark-contributor` and `grep -m muse-spark-contributor` are
#     never invocations of the contributor tier under this rule.
#
# Anything this classifier cannot parse or resolve is not an invocation
# (fail open).

_HEREDOC_RE = re.compile(
    r"<<-?(?!<)[ \t]*(['\"]?)(\w+)\1[^\n]*\n(.*?)^[ \t]*\2[ \t]*$",
    re.S | re.M,
)

_SEGMENT_SPLIT_RE = re.compile(r"(?:\|\||&&|[;|&\n])")

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_]\w*=")

_WRAPPER_WORDS = frozenset(
    {"sudo", "doas", "env", "nice", "ionice", "nohup", "time", "command", "timeout"}
)

_DURATION_RE = re.compile(r"^\d+[smhd]?$")

_MODEL_EQUALS_PREFIX = "--model="


def _strip_heredoc_bodies(text):
    """Remove here-document bodies from `text`: a here-doc body is data,
    never executed by the statement that reads it, and must never be
    scanned for an invocation."""

    def _drop(match):
        return match.group(0)[: match.start(3) - match.start(0)]

    return _HEREDOC_RE.sub(_drop, text)


def _command_word(tokens):
    """The statement's real command word: `VAR=value` assignment prefixes
    and simple wrapper commands (env/sudo/timeout/...) are skipped first,
    mirroring destructive-guard.py's own head(), so `timeout 600 codex ...`
    and `env FOO=bar codex ...` are still recognized as codex invocations.
    """
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _ASSIGNMENT_RE.match(tok):
            i += 1
            continue
        base = os.path.basename(tok)
        if base in _WRAPPER_WORDS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
            if base == "timeout" and i < len(tokens) and _DURATION_RE.match(tokens[i]):
                i += 1
            continue
        return base
    return None


def _segment_invokes_contributor_tier(tokens):
    if _command_word(tokens) != "codex":
        return False
    for i, tok in enumerate(tokens):
        if tok == "-m" and i + 1 < len(tokens) and tokens[i + 1] == CONTRIBUTOR_TIER:
            return True
        if tok.startswith(_MODEL_EQUALS_PREFIX) and tok[len(_MODEL_EQUALS_PREFIX):] == CONTRIBUTOR_TIER:
            return True
    return False


def is_contributor_invocation(command):
    text = _strip_heredoc_bodies(command)
    for segment in _SEGMENT_SPLIT_RE.split(text):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue  # unbalanced quoting: cannot parse with confidence
        if tokens and _segment_invokes_contributor_tier(tokens):
            return True
    return False


# --- Hook path -------------------------------------------------------------


def emit_deny():
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
            "additionalContext": DENY_CONTEXT,
        }
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)


def hook_main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # unparseable input: no decision, fail open
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    # Classify BEFORE any project-key derivation or store access -- this
    # short-circuit is what keeps the guard far inside its registered
    # timeout for the overwhelming majority of Bash calls, which are not
    # contributor-tier invocations at all.
    if not is_contributor_invocation(command):
        return 0

    cwd = data.get("cwd") or os.getcwd()
    key = project_key(cwd)
    if key in read_store_for_hook(store_path()):
        return 0

    emit_deny()
    return 0


# --- CLI path ----------------------------------------------------------

_CLI_MODES = ("--record", "--remove", "--list")


def parse_cli_args(argv):
    """Returns (mode, project_dir) or None on argument misuse: exactly one
    of --record/--remove/--list, --project-dir DIR required alongside it,
    nothing else."""
    if len(argv) != 3:
        return None
    modes_present = [a for a in argv if a in _CLI_MODES]
    if len(modes_present) != 1:
        return None
    mode = modes_present[0]
    rest = [a for a in argv if a != mode]
    if rest[0] != "--project-dir":
        return None
    return mode, rest[1]


def cli_record(project_dir):
    key = project_key(project_dir)
    path = store_path()
    store, malformed = read_store_for_cli(path)
    if malformed:
        print(f"同意ストアの形式が不正: {path}", file=sys.stderr)
        return 1
    projects = dict(store.get("projects", {}))
    projects[key] = {"updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    write_store(path, projects)
    print(f"同意を記録した: {key}")
    return 0


def cli_remove(project_dir):
    key = project_key(project_dir)
    path = store_path()
    store, malformed = read_store_for_cli(path)
    if malformed:
        print(f"同意ストアの形式が不正: {path}", file=sys.stderr)
        return 1
    projects = dict(store.get("projects", {}))
    if key not in projects:
        print(f"同意は記録されていない: {key}")
        return 0
    del projects[key]
    write_store(path, projects)
    print(f"同意を削除した: {key}")
    return 0


def cli_list(project_dir):
    key = project_key(project_dir)
    if key in read_store_for_hook(store_path()):
        print(key)
    return 0


def cli_main(mode, project_dir):
    if mode == "--record":
        return cli_record(project_dir)
    if mode == "--remove":
        return cli_remove(project_dir)
    return cli_list(project_dir)


def main():
    argv = sys.argv[1:]
    if not argv:
        return hook_main()
    parsed = parse_cli_args(argv)
    if parsed is None:
        print(
            "usage: muse_guard.py (--record|--remove|--list) --project-dir DIR",
            file=sys.stderr,
        )
        return 2
    return cli_main(*parsed)


if __name__ == "__main__":
    sys.exit(main())

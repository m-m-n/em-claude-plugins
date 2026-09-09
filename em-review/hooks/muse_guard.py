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

`--record` and `--remove` additionally require that the process's standard
input is an interactive terminal (the consent-write provenance boundary,
IMPLEMENTATION.md Shared Components) -- a provenance proxy, not proof of
human operation, that keeps an agent's ordinary Bash call path from
recording consent. The check is evaluated before project-key derivation and
before any store access. `--list` is outside this precondition.

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
PLUGIN_SLUG = "em-review"

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
# The recognition pipeline, restated as five stages
# (feature-docs/muse-spark-contributor-consent/tasks/task0007.md Design,
# IMPLEMENTATION.md decision D-H):
#
# Stage 0 -- one quote-aware scan, first: `_scan_statements` walks the raw
#   command text once, tracking single-/double-quote state and backslash
#   escaping character by character, exactly as a POSIX shell would. A
#   statement separator (`;`, `|`, `&`, `&&`, `||`, or a newline) is a
#   boundary ONLY when it occurs outside any quoted region and is not
#   itself escaped -- inside a quote, or immediately after a backslash, it
#   is ordinary text. This is the fix for the root cause the verify phase
#   found (D-H): the previous pipeline split the raw string into segments
#   with a quote-blind regular expression BEFORE anything honoured
#   quoting, so a quoted separator both broke a real invocation apart and
#   carved a mere mention into a standalone one. An unterminated quote
#   makes the scan's result untrustworthy -- `_scan_statements` raises
#   `ValueError` rather than returning a partial split, and the caller
#   treats that as "cannot classify" (fail open, NFR2).
# Stage 1 -- here-document handling, on the same scan: a `<<WORD` sequence
#   starts a here-document only when the scan sees it OUTSIDE any quoted
#   region; its body and terminator line are removed before anything is
#   split into statements, so a body that merely names the tier still
#   produces no decision. A header-looking sequence inside a quoted region
#   is left untouched, so text that follows it stays visible.
# Stage 2 -- statements and substitutions, from the same scan: a statement
#   is the text between two unquoted, unescaped separators. Command
#   substitutions -- both the parenthesized `$(...)` form and the backtick
#   form -- are additionally extracted as their own statements, in
#   addition to the statement that contains them, but ONLY from unquoted
#   or double-quoted regions (a substitution-looking sequence inside a
#   single-quoted region is inert text and is never extracted, matching
#   real shell semantics). Each statement's WORD-level tokenization --
#   quote removal, backslash unescaping, joining adjacent quoted/unquoted
#   parts of one argument -- is delegated to the standard library's own
#   shell tokenizer (`shlex.split`), since stages 0-2 already guarantee a
#   statement's quoting is balanced by the time it gets there.
# Stage 3 -- command-word resolution: `_resolve_command` walks a
#   statement's tokens, stepping over `VAR=value` assignment prefixes and
#   known wrapper words to find the statement's real command word --
#   mirroring destructive-guard.py's own head(). A wrapper's own options
#   are known per wrapper (`_WRAPPER_VALUE_OPTIONS`): an option that takes
#   a separate value has that value stepped over too, so a wrapper invoked
#   with a value option (`nice -n 10 codex ...`, `xargs -n 1 codex ...`)
#   still resolves to the wrapped command. An option NOT in that wrapper's
#   table stops resolution outright -- the statement is left unclassified
#   rather than guessing whether it takes a value (fail open, a documented
#   residual: this does not model shell option parsing in general). When
#   the resolved command word is a shell, the argument following its
#   command-string flag (`-c`, standalone OR bundled with other short
#   options in one token, e.g. `-xc`) is classified as its own command
#   text, recursively, bounded at `_MAX_NEST_DEPTH` -- anything nested
#   deeper is not classified at all (fail open) rather than scanned
#   indefinitely.
# Stage 4 -- model-selection matching: only for a statement whose resolved
#   command word is `codex` is the argument list scanned for a
#   model-selection argument whose value is the contributor tier, across
#   the three shapes in `_extract_model_flag_values` -- the flag as its
#   own token with the value in the FOLLOWING token; a single token whose
#   head up to the first `=` is the flag and whose tail is the value; and
#   the short-form flag with the value attached directly to it. Because
#   quoting was already consumed by stage 2's `shlex.split`, no separate
#   per-quoting-style row is needed -- bare, single-quoted and
#   double-quoted spellings all arrive as the identical token text. Every
#   comparison against CONTRIBUTOR_TIER is EXACT string equality, never a
#   prefix/suffix/substring test.
#
# The restriction to a resolved `codex` command word (stage 3) is what
# keeps a commit-message argument or a search-pattern argument from being
# read as a model selection (`git commit -m muse-spark-contributor` and
# `grep -m muse-spark-contributor` are never invocations under this rule),
# and it is load-bearing for the no-misfire floor.
#
# Anything this classifier cannot parse or resolve is not an invocation
# (fail open).

_HEREDOC_HEADER_RE = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1")

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_]\w*=")

_WRAPPER_WORDS = frozenset(
    {
        "sudo",
        "doas",
        "env",
        "nice",
        "ionice",
        "nohup",
        "time",
        "command",
        "timeout",
        "xargs",
    }
)

# Wrapper options that consume the FOLLOWING token as their own value,
# keyed by wrapper word (Design, Stage 3). An option token for a
# recognized wrapper that is not in that wrapper's set here -- and is not
# the wrapper's own bare positional handled separately (`timeout`'s
# duration) -- stops resolution outright: the statement is left
# unclassified rather than guessing whether the flag takes a value. This
# is a deliberately small, closed table, not a model of each wrapper's
# full option grammar (Out of Scope).
_WRAPPER_VALUE_OPTIONS = {
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p"},
    "xargs": {"-n", "-P", "-I", "-L", "-l", "-s", "-a", "-d", "-E"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "env": {"-u", "-C", "-S"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-U"},
    "doas": {"-u", "-C"},
}

_DURATION_RE = re.compile(r"^\d+[smhd]?$")

_SHELL_WORDS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})

# The command-string flag, standalone (`-c`) or bundled as the LAST letter
# of a cluster of short options in one token (`-xc`, `-vxc`) -- a cluster
# that carries the letter anywhere but last (`-cv`) is a different,
# unmodelled shape (the value would be attached, not the next token) and
# is deliberately left unrecognized rather than guessed (Design, Stage 3).
_SHELL_DASH_C_RE = re.compile(r"^-[A-Za-z]*c$")

_MODEL_FLAG_NAMES = ("-m", "--model")

# A command is nested at most this many levels deep -- a shell's
# command-string argument, or a command-substitution body, each add one
# level. Anything nested past this bound is not classified at all (fail
# open) rather than being scanned indefinitely.
_MAX_NEST_DEPTH = 2


def _extract_balanced(text, start, close_ch):
    """Returns (body, index_after_close) for the span starting at `start`
    (already past the opening character) that balances against `close_ch`,
    treating every `(` as an opening character that must be balanced first
    -- this also correctly handles arithmetic expansion `$((...))`, whose
    inner `(` would otherwise be mistaken for a nested paren belonging to
    something else. An unbalanced span consumes the rest of `text`."""
    depth = 1
    i = start
    n = len(text)
    while i < n:
        if text[i] == "(":
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], n


def _scan_statements(text):
    """Stages 0-2 in one left-to-right pass over `text`, tracking single-
    and double-quote state and backslash escaping exactly as a POSIX shell
    would (see the stage commentary above `_HEREDOC_HEADER_RE`).

    Returns (statements, substitutions):
      - `statements` is the list of raw statement strings the text splits
        into at an unquoted, unescaped separator (`;`, `|`, `&`, `&&`,
        `||`, or a newline); a genuine here-document's header line is kept
        in its own statement, and its body and terminator line are
        removed entirely, before any splitting happens.
      - `substitutions` is the list of raw text found inside `$(...)` and
        backtick command-substitution bodies, found outside single quotes
        only (real shell semantics: single quotes suppress all expansion,
        double quotes still allow substitution). Each body is left in
        place in its enclosing statement too -- the statement is still
        classified as before; substitutions are classified IN ADDITION.

    Raises ValueError when the text ends with an unterminated single- or
    double-quoted region: the tolerance clause (NFR2) requires that this
    be reported as "cannot classify", never papered over with whatever was
    scanned so far.
    """
    substitutions = []
    statements = []
    current = []
    i = 0
    n = len(text)
    in_single = False
    in_double = False

    def flush():
        segment = "".join(current).strip()
        if segment:
            statements.append(segment)
        current.clear()

    while i < n:
        c = text[i]
        if in_single:
            current.append(c)
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                current.append(text[i : i + 2])
                i += 2
                continue
            if c == '"':
                in_double = False
                current.append(c)
                i += 1
                continue
            if c == "$" and text.startswith("$(", i):
                body, end = _extract_balanced(text, i + 2, ")")
                substitutions.append(body)
                current.append(text[i:end])
                i = end
                continue
            if c == "`":
                end = text.find("`", i + 1)
                if end == -1:
                    current.append(c)
                    i += 1
                    continue
                substitutions.append(text[i + 1 : end])
                current.append(text[i : end + 1])
                i = end + 1
                continue
            current.append(c)
            i += 1
            continue
        # unquoted
        if c == "\\" and i + 1 < n:
            current.append(text[i : i + 2])
            i += 2
            continue
        if c == "'":
            in_single = True
            current.append(c)
            i += 1
            continue
        if c == '"':
            in_double = True
            current.append(c)
            i += 1
            continue
        if c == "$" and text.startswith("$(", i):
            body, end = _extract_balanced(text, i + 2, ")")
            substitutions.append(body)
            current.append(text[i:end])
            i = end
            continue
        if c == "`":
            end = text.find("`", i + 1)
            if end == -1:
                current.append(c)
                i += 1
                continue
            substitutions.append(text[i + 1 : end])
            current.append(text[i : end + 1])
            i = end + 1
            continue
        if c == "<" and text.startswith("<<", i):
            header = _HEREDOC_HEADER_RE.match(text, i)
            if header:
                word = header.group(2)
                line_end = text.find("\n", header.end())
                if line_end != -1:
                    body_start = line_end + 1
                    terminator = re.compile(
                        r"^[ \t]*" + re.escape(word) + r"[ \t]*$", re.M
                    ).search(text, body_start)
                    if terminator:
                        current.append(text[i:body_start])
                        # The header line ends its own statement -- the
                        # heredoc's body and terminator are skipped below,
                        # and whatever follows the terminator is a fresh
                        # statement, exactly as a real newline there would
                        # produce (it must not be glued onto "cat ...").
                        flush()
                        term_end = text.find("\n", terminator.end())
                        i = len(text) if term_end == -1 else term_end + 1
                        continue
        if c in "|&;":
            # Pipe / background / statement separator, unquoted and
            # unescaped: cut the statement here. `&&` / `||` are
            # two-character operators; consume both characters as one
            # boundary so neither leaks into the next statement.
            flush()
            if c in "|&" and i + 1 < n and text[i + 1] == c:
                i += 2
            else:
                i += 1
            continue
        if c == "\n":
            flush()
            i += 1
            continue
        current.append(c)
        i += 1

    if in_single or in_double:
        raise ValueError("unterminated quote")
    flush()
    return statements, substitutions


def _resolve_command(tokens):
    """Walks `tokens`, skipping `VAR=value` assignment prefixes and
    wrapper words (with their own known options, per
    `_WRAPPER_VALUE_OPTIONS`), to find the segment's real command word --
    mirroring destructive-guard.py's own head(), so `timeout 600 codex ...`
    and `env FOO=bar codex ...` are still recognized as codex invocations.
    Returns (command_word, rest): `rest` is exactly the token list that
    follows the resolved command word, which is what both stage 4's flag
    scan and stage 3's command-string resolution operate on. Returns
    (None, []) when the segment resolves to nothing -- assignments only,
    an empty statement, or a wrapper option this function does not
    recognize (fail open rather than guessing, Design Stage 3).
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if _ASSIGNMENT_RE.match(tok):
            i += 1
            continue
        base = os.path.basename(tok)
        if base in _WRAPPER_WORDS:
            i += 1
            value_options = _WRAPPER_VALUE_OPTIONS.get(base, frozenset())
            while i < n and tokens[i].startswith("-") and tokens[i] not in ("-", "--"):
                opt = tokens[i]
                if opt not in value_options:
                    return None, []  # unrecognized option: fail open
                i += 1
                if i >= n:
                    return None, []  # the option's value is missing
                i += 1
            if base == "timeout" and i < n and _DURATION_RE.match(tokens[i]):
                i += 1
            continue
        return base, tokens[i + 1 :]
    return None, []


def _extract_model_flag_values(tokens):
    """Yields every candidate value `tokens` presents for a
    model-selection argument, across the three shapes stage 4 recognizes:
    the flag as its own token with the value in the FOLLOWING token; a
    single token whose head up to the first `=` is the flag and whose tail
    is the value; and the short-form flag with the value attached directly
    to it. `shlex.split` has already resolved bare/single-/double-quoted
    spellings to the identical token text by the time these tokens are
    seen, so no further per-quoting-style logic is needed here.
    """
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok in _MODEL_FLAG_NAMES and i + 1 < n:
            yield tokens[i + 1]
        head, sep, tail = tok.partition("=")
        if sep and head in _MODEL_FLAG_NAMES:
            yield tail
        if tok.startswith("-m") and tok != "-m" and not tok.startswith("-m="):
            yield tok[2:]


def _has_contributor_model_flag(tokens):
    return any(value == CONTRIBUTOR_TIER for value in _extract_model_flag_values(tokens))


def _shell_command_string_argument(tokens):
    for i, tok in enumerate(tokens):
        if _SHELL_DASH_C_RE.match(tok) and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _classify_text(text, depth):
    """True when `text` -- the raw command, a command-substitution body, or
    a shell's command-string argument -- carries an invocation of the
    contributor tier at or within `depth` levels of nesting. `depth` 0 is
    the top-level command text; it increases by one for each level of
    command-substitution or shell command-string nesting resolved. Nesting
    past `_MAX_NEST_DEPTH` is not classified at all (fail open) rather
    than raising or scanning indefinitely.
    """
    if depth > _MAX_NEST_DEPTH:
        return False
    try:
        statements, substitutions = _scan_statements(text)
    except ValueError:
        return False  # the tokenizer refuses (e.g. an unterminated quote)
    for sub in substitutions:
        if _classify_text(sub, depth + 1):
            return True
    for segment in statements:
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue  # unbalanced quoting within an otherwise-parsed statement
        if not tokens:
            continue
        command_word, rest = _resolve_command(tokens)
        if command_word == "codex":
            if _has_contributor_model_flag(rest):
                return True
        elif command_word in _SHELL_WORDS:
            nested = _shell_command_string_argument(rest)
            if nested is not None and _classify_text(nested, depth + 1):
                return True
    return False


def is_contributor_invocation(command):
    return _classify_text(command, 0)


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

# Consent-write provenance boundary (IMPLEMENTATION.md Shared Components):
# the two mutating commands refuse to touch the store unless standard input
# is an interactive terminal. This is a provenance proxy, not proof of human
# operation (SPEC a12) -- it establishes that an agent's ordinary Bash call
# path cannot record consent, never that the store is unbypassable by other
# means. The refusal message states the requirement only; it carries no
# path, no project key and no store content.
PROVENANCE_REFUSAL = "対話的な端末からの実行でなければ、同意の記録や削除はできない。"


def _stdin_is_interactive():
    """True when the process's standard input is an interactive terminal.
    Never raises: a stdin lacking isatty() entirely is treated as
    non-interactive rather than propagating an exception."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError, OSError):
        return False


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
    # The provenance check precedes project-key derivation and any store
    # access for both mutating commands -- a refused run launches no git
    # subprocess and touches no file (IMPLEMENTATION.md Shared Components,
    # "Consent-write provenance boundary").
    if mode in ("--record", "--remove") and not _stdin_is_interactive():
        print(PROVENANCE_REFUSAL, file=sys.stderr)
        return 1
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

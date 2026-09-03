#!/usr/bin/env python3
"""PreToolUse(Bash) guard that blocks cleanup of a failed em-workflow run.

Denies exactly three command shapes when they target an em-workflow
integration worktree whose `workflow.yaml` still records a failed top-level
step -- so the state needed to investigate the failure is not destroyed by
the very run that hit it:

  S1: `git worktree remove <path>`
  S2: `git branch -d|--delete <branch>` (the non-force spelling only; `-D`,
      or `-d`/`--delete` combined with `--force`, is destructive-guard's own
      concern)
  S3: `gh pr create` (target resolved from the payload's `cwd` alone)

Everything else -- and every mention of one of these shapes inside quotes,
inside a here-document body, or as an argument to some other command -- is
out of scope and produces no decision at all.

Decision model:

  deny  -- the resolved target feature's workflow.yaml has a step whose
            `status` is `failed`
  ask   -- the target cannot be resolved statically (variable expansion,
            command substitution, or a glob decides it), demoted to `deny`
            under CLAUDE_BATCH (same discipline as kill-guard/destructive-
            guard)
  (none) -- every other case: out-of-scope command, unresolved target,
            missing/unparsable workflow.yaml, unavailable YAML parser, or
            any unexpected internal error

This guard never emits `allow`. Static analysis only: no external process is
started and nothing is written; the only file access is bounded read-only
path/existence checks to locate the target worktree, plus at most one
`workflow.yaml` read per resolved target.

`workflow.yaml` is untrusted, read-only input: only the structured
`status` field of each top-level workflow step is consulted. Free-text
fields (e.g. `goal`) are never scanned for the failure phrase, and no
natural-language content in the file ever influences the decision.

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import json
import os
import re
import shlex
import sys

try:
    import yaml
except ImportError:  # decision D4: fail-open when the parser is unavailable
    yaml = None

# Set by claude-batch on the claude process it launches; hooks inherit it.
BATCH_ENV = "CLAUDE_BATCH"
BATCH_OFF = ("", "0", "false", "no")

# A here-document and its body, up to the line bearing the delimiter. The
# whole match (opening line, body, closing delimiter line) is replaced with
# just its opening line, so a target command written only inside a
# here-document body is data, never scanned as an invocation.
HEREDOC = re.compile(
    r"<<-?(?!<)[ \t]*(['\"]?)(\w+)\1[^\n]*\n(.*?)^[ \t]*\2[ \t]*$",
    re.S | re.M,
)

# Statement separators, recognized only outside quotes/backticks/parens (see
# statements()).
SEPARATORS = frozenset(";|&\n")

# A token whose value cannot be resolved by reading the command alone:
# variable expansion, command substitution, or a glob metacharacter.
DYNAMIC = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]|\*|\?|\[")

# Wrapper commands that pass their remaining argument list through to a
# nested command word, mirroring destructive-guard.py's WRAPPERS skip so the
# two classifiers agree on the same set of shapes.
WRAPPERS = frozenset(
    {"sudo", "env", "nohup", "time", "command", "nice", "ionice", "doas"}
)

# S2's branch-name spelling; the feature is its middle segment.
BRANCH_RE = re.compile(r"^em-workflow/([a-z0-9][a-z0-9-]*)/integration$")

# The trailing path segments an em-workflow integration worktree path must
# spell, in order: a `.claude/worktrees` pair, `em-workflow`, the feature
# (wildcard position), then `integration`.
WORKTREE_TAIL_LEN = 5

# Bound on how many ancestors of the payload's cwd are probed to locate the
# worktree a branch-name target (S2) resolves to -- deep enough to reach a
# repository root from a task worktree several levels below it, never
# unbounded.
MAX_ANCESTOR_STEPS = 12

_UNRESOLVABLE = object()


def unattended():
    """True when this session runs under claude-batch with nobody watching."""
    return os.environ.get(BATCH_ENV, "").strip().lower() not in BATCH_OFF


def decide(decision, reason):
    """Emit a PreToolUse permission decision and stop. Never called with
    "allow" -- this guard's only decisions are "deny" and "ask"."""
    if decision == "ask" and unattended():
        decision = "deny"
        reason = (
            f"{reason}\n"
            f"無人実行（claude-batch）のため確認を取れないので、`ask` を `deny` に降格した。"
        )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": f"[failed-run-cleanup-guard] {reason}",
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def strip_heredocs(command):
    """Replace each here-document's body and closing delimiter line with
    nothing, keeping only the opening `<<WORD` line -- so a target command
    written only inside the body is never seen as its own statement."""
    return HEREDOC.sub(lambda m: m.group(0)[: m.start(3) - m.start(0)], command)


def statements(command):
    """Yield each top-level statement of COMMAND: heredoc bodies removed,
    and quote-aware so that a separator character inside a single-quoted or
    double-quoted span, inside a backtick span, or inside the parentheses of
    a subshell/command-substitution never produces a false statement
    boundary. A target command quoted this way is data, not an invocation.
    """
    chunk = strip_heredocs(command)
    segments, buf = [], []
    quote = None
    depth = 0
    i, n = 0, len(chunk)
    while i < n:
        c = chunk[i]
        if quote:
            buf.append(c)
            if quote == '"' and c == "\\" and i + 1 < n:
                buf.append(chunk[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(chunk[i + 1])
            i += 2
            continue
        if c == "`":
            buf.append(c)
            i += 1
            while i < n and chunk[i] != "`":
                buf.append(chunk[i])
                i += 1
            if i < n:
                buf.append(chunk[i])
                i += 1
            continue
        if c == "(":
            depth += 1
            buf.append(c)
            i += 1
            continue
        if c == ")":
            depth = max(0, depth - 1)
            buf.append(c)
            i += 1
            continue
        if depth == 0 and c in SEPARATORS:
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    segments.append("".join(buf))
    return [s for s in segments if s.strip()]


def head(tokens):
    """Skip leading `VAR=value` assignment tokens, then skip any leading
    wrapper commands (sudo/env/nohup/time/command/nice/ionice/doas) along
    with their own option and assignment tokens, so a wrapped invocation
    classifies the same as its bare form; return (command word, remaining
    args), or (None, []) when nothing but assignments/wrappers remain."""
    i = 0
    n = len(tokens)
    while True:
        while i < n and re.match(r"^[A-Za-z_]\w*=", tokens[i]):
            i += 1
        if i >= n:
            return None, []
        word = os.path.basename(tokens[i])
        if word not in WRAPPERS:
            return word, tokens[i + 1 :]
        i += 1
        # Skip the wrapper's own options (and, for `env`, its VAR=value
        # assignment tokens) before looking at what follows it.
        while i < n and (
            tokens[i].startswith("-") or re.match(r"^[A-Za-z_]\w*=", tokens[i])
        ):
            i += 1


def git_subcommand(args):
    """Strip git's own global options and return (subcommand, its args)."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if a.startswith("--git-dir=") or a.startswith("--work-tree="):
            i += 1
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a, args[i + 1 :]
    return None, []


def first_non_flag(tokens):
    for t in tokens:
        if not t.startswith("-"):
            return t
    return None


def classify(tokens):
    """Return ("worktree_remove"|"branch_delete", operand) for S1/S2,
    ("pr_create", None) for S3, or None when TOKENS is not a real invocation
    of any of the three shapes."""
    word, args = head(tokens)
    if word is None:
        return None

    if word == "git":
        sub, rest = git_subcommand(args)
        if sub == "worktree" and rest[:1] == ["remove"]:
            operand = first_non_flag(rest[1:])
            if operand is None:
                return None
            return ("worktree_remove", operand)
        if sub == "branch":
            has_force_delete = "-D" in rest
            has_delete = "-d" in rest or "--delete" in rest
            has_force_flag = "--force" in rest
            if has_delete and not has_force_delete and not has_force_flag:
                operand = first_non_flag(
                    [a for a in rest if a not in ("-d", "--delete")]
                )
                if operand is None:
                    return None
                return ("branch_delete", operand)
        return None

    if word == "gh":
        non_flags = [a for a in args if not a.startswith("-")]
        if non_flags[:2] == ["pr", "create"]:
            return ("pr_create", None)
        return None

    return None


def is_dynamic(text):
    return bool(DYNAMIC.search(text))


def resolve_worktree_remove(operand, cwd):
    """S1: OPERAND is the `git worktree remove` target path."""
    last_seg = operand.rstrip("/").rsplit("/", 1)[-1]
    if last_seg and not is_dynamic(last_seg) and last_seg != "integration":
        # The trailing segment is statically known and cannot spell the
        # integration worktree shape, regardless of any dynamic parts
        # earlier in the path (e.g. `$WT_ROOT/task0001`) -- out of scope,
        # no decision needed.
        return None
    if is_dynamic(operand):
        return _UNRESOLVABLE
    path = operand
    if not os.path.isabs(path):
        path = os.path.join(cwd, path) if cwd else path
    normalized = os.path.normpath(path)
    segs = [s for s in normalized.split(os.sep) if s]
    if len(segs) < WORKTREE_TAIL_LEN:
        return None
    tail = segs[-WORKTREE_TAIL_LEN:]
    if (
        tail[0] == ".claude"
        and tail[1] == "worktrees"
        and tail[2] == "em-workflow"
        and tail[4] == "integration"
    ):
        return (tail[3], normalized)
    return None


def locate_worktree_by_ancestor_walk(cwd, feature):
    """S2: branch names carry no path, so the worktree is found by walking
    upward from the payload's cwd through a bounded number of ancestors,
    taking the first one that actually contains the integration worktree
    directory for FEATURE."""
    if not cwd:
        return None
    current = os.path.normpath(cwd)
    for _ in range(MAX_ANCESTOR_STEPS):
        candidate = os.path.join(
            current, ".claude", "worktrees", "em-workflow", feature, "integration"
        )
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def resolve_branch_delete(operand, cwd):
    """S2: OPERAND is the `git branch -d`/`--delete` target branch name."""
    parts = operand.split("/")
    if len(parts) == 3:
        first, _feature, last = parts
        if (
            not is_dynamic(first)
            and first != "em-workflow"
            or not is_dynamic(last)
            and last != "integration"
        ):
            # The statically-known literal parts already rule out the
            # `em-workflow/<feature>/integration` shape -- out of scope,
            # no decision needed, regardless of any dynamic feature segment.
            return None
    elif not is_dynamic(operand):
        # Fully static and not 3 segments: cannot match BRANCH_RE at all.
        return None
    if is_dynamic(operand):
        return _UNRESOLVABLE
    m = BRANCH_RE.match(operand)
    if not m:
        return None
    feature = m.group(1)
    worktree_dir = locate_worktree_by_ancestor_walk(cwd, feature)
    if worktree_dir is None:
        return None
    return (feature, worktree_dir)


def resolve_pr_create(cwd):
    """S3: the feature comes from the payload's cwd ALONE (FR4) -- never
    from command arguments such as `--head`. Only a cwd that is the
    integration worktree, or a descendant of it, resolves a feature."""
    if not cwd:
        return None
    normalized = os.path.normpath(cwd)
    segs = [s for s in normalized.split(os.sep) if s]
    for i in range(len(segs) - (WORKTREE_TAIL_LEN - 1)):
        window = segs[i : i + WORKTREE_TAIL_LEN]
        if (
            window[0] == ".claude"
            and window[1] == "worktrees"
            and window[2] == "em-workflow"
            and window[4] == "integration"
        ):
            feature = window[3]
            prefix = segs[: i + WORKTREE_TAIL_LEN]
            worktree_dir = os.sep.join(prefix)
            if normalized.startswith(os.sep):
                worktree_dir = os.sep + worktree_dir
            return (feature, worktree_dir)
    return None


def read_workflow_steps(worktree_dir, feature):
    """The top-level `workflow:` step sequence of the target worktree's own
    `feature-docs/{feature}/workflow.yaml`, or None on any failure to read
    or parse it (FR10, NFR4: fail-open, this is not the guard's problem)."""
    path = os.path.join(worktree_dir, "feature-docs", feature, "workflow.yaml")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    steps = data.get("workflow")
    if not isinstance(steps, list):
        return None
    return steps


def failed_step_id(steps):
    """The `id` of the first top-level step whose `status` is exactly
    `failed` (decision D3: structured field only, never a text scan --
    `needs_update`/`pending`/`in_progress`, and any per-task or free-text
    content, are never consulted here)."""
    for step in steps:
        if isinstance(step, dict) and step.get("status") == "failed":
            return step.get("id")
    return None


def evaluate(kind, operand, cwd):
    """Resolve one classified statement to a decision, or None for no
    decision. Emits directly via decide() on ask/deny."""
    if kind == "worktree_remove":
        target = resolve_worktree_remove(operand, cwd)
    elif kind == "branch_delete":
        target = resolve_branch_delete(operand, cwd)
    else:  # pr_create
        target = resolve_pr_create(cwd)

    if target is _UNRESOLVABLE:
        decide(
            "ask",
            "対象のパス/ブランチ名に変数展開・コマンド置換・グロブが含まれており、"
            "静的に確定できない。展開後の実際の値をコマンドに直接書いて、"
            "静的に解決できる形に書き換えて続行する。",
        )
        return

    if target is None:
        return

    feature, worktree_dir = target
    if yaml is None:
        return  # D4: fail-open when the parser is unavailable

    steps = read_workflow_steps(worktree_dir, feature)
    if steps is None:
        return

    step_id = failed_step_id(steps)
    if step_id is None:
        return

    decide(
        "deny",
        f"feature `{feature}` は workflow のステップ `{step_id}` が failed のまま"
        f"停止している。この状態を消すクリーンアップは行わず、状況を報告して停止する。",
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail-open: a malformed payload is not our problem

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command.strip():
        sys.exit(0)
    cwd = payload.get("cwd") or ""

    for segment in statements(command):
        try:
            tokens = shlex.split(segment, comments=True)
        except ValueError:
            continue
        if not tokens:
            continue
        classified = classify(tokens)
        if classified is None:
            continue
        kind, operand = classified
        try:
            evaluate(kind, operand, cwd)
        except Exception:
            continue  # fail-open: an unexpected internal error is not ours

    sys.exit(0)


if __name__ == "__main__":
    main()

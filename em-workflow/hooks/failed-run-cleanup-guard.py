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

# Wrapper options that take a value of their own (a separate token), keyed by
# wrapper name -- mirrors destructive-guard.py's WRAPPER_VALUE_FLAGS so the
# two classifiers agree on where the wrapped command word starts. Without
# consuming these, the value token is mistaken for the wrapped command word
# (`env -u NAME cp …` would read `NAME` as the command).
WRAPPER_VALUE_FLAGS = {
    "sudo": {
        "-u", "-g", "-p", "-C", "-h", "-R", "-T", "-U", "-D", "-r", "-t",
        "--user", "--group", "--prompt", "--close-from", "--host",
        "--chroot", "--type", "--other-user", "--role", "--chdir",
    },
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata", "--pid"},
    "time": {"-o", "--output"},
    "doas": {"-u", "-C"},
    "command": set(),
    "nohup": set(),
}

# Shell command words whose `-c <script>` argument is itself a command line
# to be scanned, so `bash -c '...'` cannot hide a target shape.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})

# Bound on how many levels statements() recurses into subshells/brace
# groups/command substitutions/`-c` scripts, so a pathological nesting
# cannot recurse unboundedly.
MAX_NEST_DEPTH = 5

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


def split_tokens(text):
    """shlex.split(text, comments=True), with whitespace-only tokens
    dropped -- a `\\` + newline line continuation surfaces from shlex as a
    token containing only the newline, which must never be read as an
    operand or subcommand. ValueError propagates unchanged."""
    return [t for t in shlex.split(text, comments=True) if t.strip()]


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
    written only inside the body is never seen as its own statement.

    Exception: when the opening line's own command word (after skipping
    leading assignments/wrappers) is a shell sink (sh/bash/zsh/dash/ksh),
    the body is itself a script the sink will execute -- its text is
    returned alongside the stripped command so the caller can scan it too,
    the same way a `-c` script argument is scanned."""
    kept_nested = []

    def repl(m):
        line_start = command.rfind("\n", 0, m.start(0)) + 1
        head_line = command[line_start : m.start(0)]
        try:
            toks = split_tokens(head_line)
        except ValueError:
            toks = []
        cmdword, _ = head(toks) if toks else (None, [])
        if cmdword in SHELLS:
            kept_nested.append(m.group(3))
        return m.group(0)[: m.start(3) - m.start(0)]

    stripped = HEREDOC.sub(repl, command)
    return stripped, kept_nested


def statements(command, _depth=0):
    """Yield each top-level statement of COMMAND: heredoc bodies removed,
    and quote-aware so that a separator character inside a single-quoted or
    double-quoted span, inside a backtick span, or inside the parentheses of
    a subshell/command-substitution never produces a false statement
    boundary. A target command quoted this way is data, not an invocation.

    Also recursive (bounded by MAX_NEST_DEPTH): the body of a subshell
    `( … )`, a brace group `{ … }`, a command substitution `$( … )` or
    backtick span, and the `-c` script argument of a nested
    sh/bash/zsh/dash/ksh invocation are each split and yielded too, so a
    target shape hidden inside one of those cannot evade the guard.
    """
    chunk, heredoc_nested = strip_heredocs(command)
    segments, buf = [], []
    nested = list(heredoc_nested)
    quote = None
    depth = 0
    paren_start = None
    brace_depth = 0
    brace_start = None
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
        if c == "$" and i + 1 < n and chunk[i + 1] == "(":
            j = i + 2
            d = 1
            while j < n and d > 0:
                if chunk[j] == "(":
                    d += 1
                elif chunk[j] == ")":
                    d -= 1
                j += 1
            nested.append(chunk[i + 2 : j - 1 if d == 0 else j])
            buf.append(chunk[i:j])
            i = j
            continue
        if c == "`":
            j = i + 1
            while j < n and chunk[j] != "`":
                j += 1
            nested.append(chunk[i + 1 : j])
            buf.append(chunk[i : min(j + 1, n)])
            i = j + 1 if j < n else j
            continue
        if c == "(":
            if depth == 0:
                paren_start = i + 1
            depth += 1
            buf.append(c)
            i += 1
            continue
        if c == ")":
            if depth == 1 and paren_start is not None:
                nested.append(chunk[paren_start:i])
                paren_start = None
            depth = max(0, depth - 1)
            buf.append(c)
            i += 1
            continue
        if c == "{" and depth == 0 and (i == 0 or chunk[i - 1] != "$"):
            if brace_depth == 0:
                brace_start = i + 1
            brace_depth += 1
            buf.append(c)
            i += 1
            continue
        if c == "}" and brace_depth > 0:
            brace_depth -= 1
            if brace_depth == 0 and brace_start is not None:
                nested.append(chunk[brace_start:i])
                brace_start = None
            buf.append(c)
            i += 1
            continue
        if depth == 0 and brace_depth == 0 and c in SEPARATORS:
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    segments.append("".join(buf))
    top = [s for s in segments if s.strip()]

    if _depth < MAX_NEST_DEPTH:
        for seg in top:
            try:
                tokens = split_tokens(seg)
            except ValueError:
                tokens = []
            if not tokens:
                continue
            word = os.path.basename(tokens[0])
            if word in SHELLS:
                args = tokens[1:]
                for idx, a in enumerate(args):
                    if a == "-c" and idx + 1 < len(args):
                        nested.append(args[idx + 1])
                        break
                    if a == "<<<" and idx + 1 < len(args):
                        nested.append(args[idx + 1])
                        break
            elif word == "eval":
                args = tokens[1:]
                if args:
                    nested.append(" ".join(args))

    results = list(top)
    if _depth < MAX_NEST_DEPTH:
        for nested_text in nested:
            results.extend(statements(nested_text, _depth + 1))
    return results


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
        if word in ("mise", "asdf") and i + 1 < n and tokens[i + 1] == "exec":
            i += 2
            # `mise exec [args] -- <command>` / `asdf exec [args] -- <command>`:
            # skip everything up to and including the `--` separator, so the
            # wrapped invocation classifies the same as its bare form.
            while i < n and tokens[i] != "--":
                i += 1
            if i < n and tokens[i] == "--":
                i += 1
                continue
            return None, []
        if word not in WRAPPERS:
            return word, tokens[i + 1 :]
        value_flags = WRAPPER_VALUE_FLAGS.get(word, set())
        i += 1
        # Skip the wrapper's own options (and, for `env`, its VAR=value
        # assignment tokens) before looking at what follows it. An option
        # that takes a separate value token (per WRAPPER_VALUE_FLAGS) has
        # that value token skipped too, so it is never mistaken for the
        # wrapped command word.
        while i < n and (
            tokens[i].startswith("-") or re.match(r"^[A-Za-z_]\w*=", tokens[i])
        ):
            flag = tokens[i]
            i += 1
            if flag in value_flags and i < n:
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
            flat = []
            for a in rest:
                if re.fullmatch(r"-[A-Za-z]+", a):
                    flat.extend("-" + c for c in a[1:])
                else:
                    flat.append(a)
            has_force_delete = "-D" in flat
            has_delete = "-d" in flat or "--delete" in flat
            has_force_flag = "--force" in flat
            if has_delete and not has_force_delete and not has_force_flag:
                operands = [
                    a
                    for a in rest
                    if not (re.fullmatch(r"-[A-Za-z]+", a) or a.startswith("-"))
                ]
                if not operands:
                    return None
                operand = None
                for a in operands:
                    if is_dynamic(a) or BRANCH_RE.match(a):
                        operand = a
                        break
                if operand is None:
                    operand = operands[0]
                return ("branch_delete", operand)
        return None

    if word == "gh":
        # `-R`/`--repo` take a value token of their own (`gh -R owner/repo pr
        # create`); without skipping it the repo spelling is mistaken for the
        # first positional and `pr create` is missed. Kept identical to
        # destructive-guard.py's matches_target_shape().
        non_flags = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a in ("-R", "--repo"):
                skip_next = True
                continue
            if a.startswith("--repo="):
                continue
            if a.startswith("-"):
                continue
            non_flags.append(a)
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


_FAILED_SCAN_CACHE = {}


def any_failed_worktree(cwd):
    """Whether the `ask` for a statically-unresolvable operand should be
    kept, based on em-workflow integration worktrees reachable from the
    given cwd (walking ancestors, same as locate_worktree_by_ancestor_walk).

    Returns False (silent, no ask) only when at least one em-workflow
    integration worktree could be enumerated and every one of them is
    healthy. Returns True (keep the `ask`) both when some enumerable
    worktree still records a failed step in its own workflow.yaml, and
    when no worktree can be enumerated at all -- the inability to enumerate
    must not be read as "healthy" (FR7's protection is preserved).

    The answer depends only on cwd, so it is memoized: a command carrying
    several unresolvable target statements must not re-read and re-parse
    every worktree's workflow.yaml once per statement."""
    if cwd in _FAILED_SCAN_CACHE:
        return _FAILED_SCAN_CACHE[cwd]
    found_any_worktree = False
    found_failed = False
    if cwd and yaml is not None:
        current = os.path.normpath(cwd)
        for _ in range(MAX_ANCESTOR_STEPS):
            base = os.path.join(current, ".claude", "worktrees", "em-workflow")
            if os.path.isdir(base):
                try:
                    entries = os.listdir(base)
                except Exception:
                    entries = []
                for feature in entries:
                    integration_dir = os.path.join(base, feature, "integration")
                    if not os.path.isdir(integration_dir):
                        continue
                    found_any_worktree = True
                    steps = read_workflow_steps(integration_dir, feature)
                    if steps is not None and failed_step_id(steps) is not None:
                        found_failed = True
                        break  # 判定はもう変わらない
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    result = found_failed or not found_any_worktree
    _FAILED_SCAN_CACHE[cwd] = result
    return result


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
        # Before asking, check whether every em-workflow integration
        # worktree reachable from the payload's cwd is healthy (see
        # any_failed_worktree()); if none could even be enumerated, or any
        # has a failed step, the ask is kept.
        if not any_failed_worktree(cwd):
            return
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
            tokens = split_tokens(segment)
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

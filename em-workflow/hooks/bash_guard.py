#!/usr/bin/env python3
"""em-workflow Bash guard: PreToolUse hook + approval-store CLI.

Deterministic runtime enforcement for the em-workflow command-execution
protocol (references/command-execution-protocol.md). The hook is code, not
an LLM — a prompt-injected agent cannot talk it out of a decision.

Hook mode (no arguments; stdin = PreToolUse JSON):
  - refusal pattern in the command        -> deny (even if approved)
  - exact match in the approval store     -> allow
  - cd "<path>" && <approved command>     -> allow (see "cd prefix" below)
  - declared in workflow.yaml, unapproved -> deny (run the approval gate)
  - anything else                         -> no decision (exit 0, no output;
                                             normal permission flow applies)

The hook only ever decides on commands that are workflow-relevant (declared
in a feature-docs/*/workflow.yaml or present in the approval store, or a cd
prefix in front of an approved command). All other Bash commands pass through
untouched.

cd prefix: a subagent's working directory does not survive between Bash
calls, so an implementer runs an approved command as one call of the form
`cd "<path>" && <approved command>`. The hook allows that form only when all
of these hold; a command that fails any of them is judged exactly as if it
had no cd prefix (never a new deny):
  - syntax: `cd`, blanks, one double-quoted absolute path (no `"`, `$`,
    backtick, backslash or line break in it), blanks, then the first `&&`;
    everything after that `&&` is the remainder
  - path: the area is <main worktree>/.claude/worktrees/em-workflow, where
    the main worktree is the parent of the git common dir of the hook's cwd.
    The logical path (the realpath of <path> with each `..` first collapsed
    against the component written before it, as Bash's default cd does) and
    the physical path (the realpath of <path> exactly as written, each `..`
    applying to the directory already resolved) are compared per path
    component. When the logical path is an existing directory, the logical
    path and the physical path must both be existing directories strictly
    below the area. Otherwise the physical path alone must be an existing
    directory strictly below the area, which is where Bash lands through its
    physical-path fallback. A resolution error counts as not below.
    <path> is only resolved, never used as the directory or argument of a
    child process
  - approval: the remainder, with surrounding blanks removed, equals one
    approved string of the cwd's project
The refusal patterns are applied to the whole command first.

Approval store: ~/.claude/em-workflow/approvals.json — user-owned, outside
any repository, so a cloned repo can never ship approvals. Projects are
keyed by `git rev-parse --path-format=absolute --git-common-dir`, which is
identical across all worktrees of the same repository.

CLI modes (used by the approval gate, never by the hook itself):
  bash_guard.py --record --project-dir DIR   # stdin: one command per line
  bash_guard.py --remove --project-dir DIR   # stdin: one command per line
  bash_guard.py --list   --project-dir DIR

Override the store path with $EM_WORKFLOW_APPROVALS (tests only).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

COMMAND_KEY_RE = re.compile(
    r"^\s*(build_command|test_command|format_command|e2e_test_command):\s*(.+?)\s*$"
)

# Aligned with the "Refusal cases" section of command-execution-protocol.md.
# Evaluated only for workflow-relevant commands, so false positives cannot
# disturb unrelated Bash usage.
REFUSAL_PATTERNS = (
    (re.compile(r"(^|[;&|(]\s*|\s)(sudo|doas)(\s|$)"), "privilege escalation (sudo/doas)"),
    (re.compile(r"(^|[;&|(]\s*|\s)su(\s+-|\s+\w|$)"), "privilege escalation (su)"),
    (
        re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(env\s+)?(ba|z|da)?sh\b"),
        "piping fetched content into a shell",
    ),
    (
        re.compile(r"""\brm\s+(-[a-zA-Z]+\s+)*(--\s+)?['"]?(/(?!tmp(/|\s|['"]|$))|~|\$HOME)"""),
        "filesystem destruction outside the project",
    ),
)


def refusal_reason(cmd):
    for pattern, reason in REFUSAL_PATTERNS:
        if pattern.search(cmd):
            return reason
    return None


def approvals_path():
    override = os.environ.get("EM_WORKFLOW_APPROVALS")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".claude", "em-workflow", "approvals.json")


def git_out(cwd, *args):
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def git_common_dir(directory):
    return git_out(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")


def project_key(directory):
    """Stable per-repository key, shared by all worktrees."""
    common_dir = git_common_dir(directory)
    if common_dir:
        return common_dir
    return os.path.realpath(directory)


def strip_yaml_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def declared_commands(roots):
    """Command strings declared in any feature-docs/*/workflow.yaml under roots.

    Line-based extraction on purpose: the workflow.yaml schema declares the
    four *_command fields as single-line scalars. Anything this parser cannot
    see simply gets no hook decision and falls back to the normal permission
    prompt — fail-open to the user, never to silent execution.
    """
    commands = set()
    for root in roots:
        docs_dir = os.path.join(root, "feature-docs")
        if not os.path.isdir(docs_dir):
            continue
        try:
            features = os.listdir(docs_dir)
        except OSError:
            continue
        for feature in features:
            wf_path = os.path.join(docs_dir, feature, "workflow.yaml")
            if not os.path.isfile(wf_path):
                continue
            try:
                with open(wf_path, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        match = COMMAND_KEY_RE.match(line)
                        if not match:
                            continue
                        value = strip_yaml_quotes(match.group(2))
                        if value and value not in ("null", "~"):
                            commands.add(value.strip())
            except OSError:
                continue
    return commands


def load_store(path):
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
        if isinstance(store, dict) and isinstance(store.get("projects"), dict):
            return store
    except (OSError, ValueError):
        pass
    return {"version": 1, "projects": {}}


def approved_for(store, key):
    entry = store["projects"].get(key) or {}
    commands = entry.get("approved_commands") or []
    return {c.strip() for c in commands if isinstance(c, str) and c.strip()}


# `cd`, blanks, one double-quoted absolute path, blanks, the first `&&`.
# The path may not contain a quote, `$`, a backtick, a backslash or a line
# break; the remainder is everything after the `&&`.
CD_PREFIX_RE = re.compile(r'cd[ \t]+"(/[^"$`\\\r\n]*)"[ \t]*&&(.*)', re.DOTALL)

WORKTREE_AREA_PARTS = (".claude", "worktrees", "em-workflow")

# additionalContext of the unapproved deny: one sentence per audience.
UNAPPROVED_GUIDANCE = (
    "オーケストレーターへ: command-execution-protocol.md の承認ゲート"
    "（AskUserQuestion で一括承認 → bash_guard.py --record で記録）を実行してから、"
    "単独の cd で作業ディレクトリへ移動し、承認された文字列をそのまま実行して。"
    'implementer へ: 承認された文字列は cd "{worktree_path}" && <承認文字列> の '
    "1 回の Bash 呼び出しで実行して。"
    "AskUserQuestion を持たないサブエージェントは、deny された後に再試行せず、"
    "実行を諦めて notes で報告すること。"
    "環境変数の前置などで承認文字列そのものを変形しないこと。"
)


def split_cd_prefix(command):
    """(path, remainder) when the command has the cd prefix form, else None."""
    match = CD_PREFIX_RE.fullmatch(command)
    if not match:
        return None
    return match.group(1), match.group(2)


def worktree_area(common_dir):
    """Realpath of <main worktree>/.claude/worktrees/em-workflow, or None."""
    if not common_dir:
        return None
    main_tree = os.path.dirname(os.path.normpath(common_dir))
    try:
        return os.path.realpath(os.path.join(main_tree, *WORKTREE_AREA_PARTS))
    except (OSError, ValueError):
        return None


def strictly_below(path, area):
    """True when path lies strictly below area, compared per path component.
    The area itself, and a sibling that only shares a name prefix, are not
    below it."""
    area_parts = area.split(os.sep)
    path_parts = path.split(os.sep)
    return (
        len(path_parts) > len(area_parts)
        and path_parts[: len(area_parts)] == area_parts
    )


def is_below(path, area):
    """True when path reaches an existing directory strictly below area the
    way Bash's cd does. path is only resolved, never handed to a child process.

    Bash first moves to the logical path (each `..` collapsed against the
    component written before it, then links resolved). When that move fails
    it falls back to the physical path (links resolved component by component,
    each `..` applying to the directory already resolved). So:
      - logical path is an existing directory: both paths must be existing
        directories strictly below area;
      - otherwise: the physical path alone must be an existing directory
        strictly below area.
    Any resolution error is False.
    """
    try:
        physical = os.path.realpath(path)
        logical = os.path.realpath(os.path.normpath(path))
        if os.path.isdir(logical):
            return (
                os.path.isdir(physical)
                and strictly_below(logical, area)
                and strictly_below(physical, area)
            )
        return os.path.isdir(physical) and strictly_below(physical, area)
    except (OSError, ValueError):
        return False


def is_cd_prefixed_approved(command, approved, common_dir):
    """True for `cd "<path>" && <approved>` with <path> in the worktree area."""
    parts = split_cd_prefix(command)
    if parts is None:
        return False
    path, remainder = parts
    if remainder.strip() not in approved:
        return False
    area = worktree_area(common_dir)
    return area is not None and is_below(path, area)


def emit(decision, reason, additional_context=None):
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    if additional_context:
        output["hookSpecificOutput"]["additionalContext"] = additional_context
    json.dump(output, sys.stdout, ensure_ascii=False)


def hook_main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0  # unparseable input: no decision, normal permission flow
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    command = command.strip()
    cwd = data.get("cwd") or os.getcwd()

    roots = []
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        git_out(cwd, "rev-parse", "--show-toplevel"),
        cwd,
    ):
        if candidate and os.path.isdir(candidate) and candidate not in roots:
            roots.append(candidate)

    declared = declared_commands(roots)
    store_path = approvals_path()
    if command not in declared and not os.path.isfile(store_path):
        return 0

    common_dir = git_common_dir(cwd)
    key = common_dir or os.path.realpath(cwd)
    approved = approved_for(load_store(store_path), key)
    cd_prefixed = is_cd_prefixed_approved(command, approved, common_dir)
    if command not in declared and command not in approved and not cd_prefixed:
        return 0  # not workflow-relevant: stay silent

    reason = refusal_reason(command)
    if reason:
        emit(
            "deny",
            f"em-workflow guard: 禁止パターン（{reason}）を含むコマンドは承認の有無に関わらず実行できないよ",
            "workflow.yaml のコマンド定義からこのパターンを除去して。回避策を探さず、"
            "ユーザーに定義の修正を報告すること。",
        )
    elif command in approved:
        emit("allow", "em-workflow guard: 承認済みコマンド（approvals.json に完全一致）")
    elif cd_prefixed:
        emit(
            "allow",
            "em-workflow guard: 承認済みコマンドの worktree への cd 前置形"
            "（cd より後ろが approvals.json に完全一致）",
        )
    else:
        emit(
            "deny",
            "em-workflow guard: workflow.yaml 由来のコマンドが未承認だよ。コマンド承認ゲートを実行してから再試行して",
            UNAPPROVED_GUIDANCE,
        )
    return 0


def read_stdin_commands():
    commands = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            commands.append(line)
    return commands


def cli_main(mode, project_dir):
    key = project_key(project_dir)
    store_path = approvals_path()
    store = load_store(store_path)

    if mode == "--list":
        for command in sorted(approved_for(store, key)):
            print(command)
        return 0

    commands = read_stdin_commands()
    if not commands:
        print("bash_guard: no commands on stdin", file=sys.stderr)
        return 1

    if mode == "--record":
        refused = [(c, refusal_reason(c)) for c in commands if refusal_reason(c)]
        if refused:
            for command, reason in refused:
                print(f"bash_guard: REFUSED ({reason}): {command}", file=sys.stderr)
            return 1
        merged = approved_for(store, key) | set(commands)
    else:  # --remove
        merged = approved_for(store, key) - set(commands)

    entry = store["projects"].setdefault(key, {})
    entry["approved_commands"] = sorted(merged)
    entry["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if not merged:
        del store["projects"][key]

    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    tmp_path = store_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp_path, store_path)

    print(f"project: {key}")
    for command in sorted(merged):
        print(f"approved: {command}")
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        return hook_main()
    if args[0] in ("--record", "--remove", "--list"):
        if len(args) == 3 and args[1] == "--project-dir":
            return cli_main(args[0], args[2])
        print(
            f"usage: bash_guard.py {args[0]} --project-dir DIR",
            file=sys.stderr,
        )
        return 1
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

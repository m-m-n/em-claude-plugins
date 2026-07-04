#!/usr/bin/env python3
"""em-workflow Bash guard: PreToolUse hook + approval-store CLI.

Deterministic runtime enforcement for the em-workflow command-execution
protocol (references/command-execution-protocol.md). The hook is code, not
an LLM — a prompt-injected agent cannot talk it out of a decision.

Hook mode (no arguments; stdin = PreToolUse JSON):
  - refusal pattern in the command        -> deny (even if approved)
  - exact match in the approval store     -> allow
  - declared in workflow.yaml, unapproved -> deny (run the approval gate)
  - anything else                         -> no decision (exit 0, no output;
                                             normal permission flow applies)

The hook only ever decides on commands that are workflow-relevant (declared
in a feature-docs/*/workflow.yaml or present in the approval store). All
other Bash commands pass through untouched.

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


def project_key(directory):
    """Stable per-repository key, shared by all worktrees."""
    common_dir = git_out(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")
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

    approved = approved_for(load_store(store_path), project_key(cwd))
    if command not in declared and command not in approved:
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
    else:
        emit(
            "deny",
            "em-workflow guard: workflow.yaml 由来のコマンドが未承認だよ。コマンド承認ゲートを実行してから再試行して",
            "オーケストレーターへ: command-execution-protocol.md の承認ゲート"
            "（AskUserQuestion で一括承認 → bash_guard.py --record で記録）を実行してから、"
            "承認された文字列と一字一句同じコマンドを再実行して。cd や環境変数の前置で"
            "コマンド文字列を変形しないこと（作業ディレクトリは事前に単独の cd で移動する）。"
            "AskUserQuestion を持たないサブエージェントは、実行を諦めて notes で報告すること。",
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

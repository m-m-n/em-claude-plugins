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
  - path: <path> must be a canonical absolute path strictly below the area
    (<main worktree>/.claude/worktrees/em-workflow), at any depth; the area
    itself is not below it. The main worktree is the parent of the git common
    dir of the hook's cwd, and the area is used only when its realpath lies
    strictly below the realpath of the main worktree; otherwise no cd prefix
    form is allowed. A canonical absolute path (a) is absolute and has no
    empty, `.` or `..` component other than the root, (b) lies strictly below
    the area when the text as written is compared per path component, (c)
    equals its own realpath, with every component existing and every link
    resolved, and (d) is an existing directory. <path> is never normalized
    and then accepted. A path whose length in bytes in the file-system
    encoding is greater than or equal to the path-length limit that the
    operating system reports for the root directory, obtained at run time, is
    refused before the area is resolved and before any file-system access; so
    is a path that cannot be encoded, and so is every path when the limit
    cannot be obtained or is not positive. A resolution error counts as not
    below. <path> is only resolved, never used as the directory or argument of
    a child process
  - approval: the remainder, with surrounding blanks removed, equals one
    approved string of the cwd's project
  - operators: no lone `&`, `;`, `||` or line break at the top level of the
    remainder (outside quotes and backslash escapes); a line break counts
    inside quotes too. The recognized tokens (`&&`, `|&`, `>&`, `<&`, `&>`,
    `&>>`) are not counted, and a `|` that starts none of them is a pipe and
    is not counted. Nesting is never parsed
  - safe side: the remainder has none of these: an unclosed quote; a trailing
    backslash; `$'` or `$"` anywhere; `#` anywhere, inside quotes too; `(`,
    `)`, `{` or `}` outside quotes and backslash escapes; `$(`, `${` or a
    backtick anywhere, inside single quotes too
The refusal patterns are applied to the whole command first; that check does
not depend on the operator conditions above. A cd prefix form that meets the
syntax, path and approval conditions but fails an operator or safe-side
condition keeps its place among the workflow-relevant commands: it is judged
by the same table as the bare command (exact approval allows, a whole-command
declaration in workflow.yaml denies as unapproved, otherwise no decision).

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
    """Realpath of <main worktree>/.claude/worktrees/em-workflow, or None.

    The main worktree is the parent of the git common dir. The resolved area
    is returned only when it lies strictly below the realpath of the main
    worktree; a link at the area or at one of its ancestors that leads out of
    the main worktree makes the answer None. Never raises."""
    if not common_dir:
        return None
    try:
        main_tree = os.path.dirname(os.path.normpath(common_dir))
        main_real = os.path.realpath(main_tree)
        area = os.path.realpath(os.path.join(main_tree, *WORKTREE_AREA_PARTS))
    except (OSError, ValueError):
        return None
    return area if strictly_below(area, main_real) else None


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


def within_length_bound(path):
    """True when the byte length of path in the file-system encoding is less
    than the path-length limit that the operating system reports for the root
    directory, obtained at run time. False when the length reaches the limit,
    when the limit cannot be obtained or is not positive, or when path cannot
    be encoded. Touches no file; never raises."""
    try:
        bound = os.pathconf("/", "PC_PATH_MAX")
        if not isinstance(bound, int) or bound <= 0:
            return False
        return len(os.fsencode(path)) < bound
    except (OSError, ValueError):
        return False


def is_canonical_text(path):
    """True when path, read as text, is absolute and has no empty, `.` or `..`
    component other than the root. The file system is not consulted."""
    if not path.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in path[1:].split("/"))


def is_below(path, area):
    """True when path is a canonical absolute path strictly below area, at any
    depth. area is an area that worktree_area accepted: the resolved
    <main worktree>/.claude/worktrees/em-workflow, whose realpath lies strictly
    below the realpath of the main worktree. path is only resolved, never used
    as the directory or argument of a child process.

    path is never normalized and then accepted: the text as written is what is
    compared. A canonical absolute path
      (a) is absolute and has no empty, `.` or `..` component other than the
          root;
      (b) lies strictly below the area when the text as written is compared
          per path component;
      (c) equals its own realpath, with every component existing and every
          link resolved;
      (d) is an existing directory.
    A path whose length in bytes in the file-system encoding is greater than
    or equal to the path-length limit that the operating system reports for the
    root directory is refused first, before any file-system access; so is a
    path that cannot be encoded, and so is every path when the limit cannot be
    obtained or is not positive. Conditions (a) and (b) are decided on the text
    alone, before the file system is consulted. A resolution error counts as
    not below, and the answer is False; this function never raises.
    """
    try:
        if not within_length_bound(path):
            return False
        if not is_canonical_text(path) or not strictly_below(path, area):
            return False
        if os.path.realpath(path, strict=True) != path:
            return False
        return os.path.isdir(path)
    except (OSError, ValueError):
        return False


def is_cd_prefixed_approved(command, approved, common_dir):
    """True for `cd "<path>" && <approved>` with <path> in the worktree area.

    This is the cd prefix candidate: it decides whether the command is
    workflow-relevant. Whether the cd prefix allow is given is decided by
    cd_prefix_allowed. The length bound is checked first, so an over-long path
    never reaches worktree_area or the file system.
    """
    parts = split_cd_prefix(command)
    if parts is None:
        return False
    path, remainder = parts
    if not within_length_bound(path):
        return False
    if remainder.strip() not in approved:
        return False
    area = worktree_area(common_dir)
    return area is not None and is_below(path, area)


# Remainder text that excludes the cd prefix allow wherever it appears, inside
# quotes included (rules E7, E8, E10).
EXCLUDED_ANYWHERE = ("$'", '$"', "#", "$(", "${", "`")

# Characters that exclude the cd prefix allow when unquoted and unescaped (E9).
EXCLUDED_UNQUOTED = "(){}"

# Tokens consumed as one unit in the unquoted state, longest match first. The
# `&` inside them is not a lone `&`.
UNCOUNTED_TOKENS = ("&>>", "&&", "&>", "|&", ">&", "<&")

# Characters that a backslash escapes inside double quotes (Bash); any other
# backslash there is an ordinary character.
DOUBLE_QUOTE_ESCAPED = '$`"\\\n'


def cd_remainder_excluded(remainder):
    """True when the remainder of a cd prefix form is excluded from the cd
    prefix allow (rules E1 to E10 of the cd-prefix-toplevel-operators plan).

    One left-to-right pass with three quoting states (unquoted, single-quoted,
    double-quoted). Pure: no file read, no child process. Nesting is never
    parsed; one hit of any rule is enough. The remainder is trimmed first, so
    the scanned string is the one compared with the approval store.
    """
    text = remainder.strip()
    # E4: a line break anywhere. E7, E8, E10: position-independent text.
    if "\n" in text or "\r" in text:
        return True
    if any(piece in text for piece in EXCLUDED_ANYWHERE):
        return True

    quote = ""  # "", "'" or '"'
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if quote == "'":
            # Every character is ordinary, a backslash included.
            if char == "'":
                quote = ""
            index += 1
        elif quote == '"':
            if char == "\\":
                if index + 1 >= size:
                    return True  # E6
                escapes = text[index + 1] in DOUBLE_QUOTE_ESCAPED
                index += 2 if escapes else 1
            else:
                if char == '"':
                    quote = ""
                index += 1
        elif char == "\\":
            if index + 1 >= size:
                return True  # E6
            index += 2  # an escaped character is never counted
        elif char in "'\"":
            quote = char
            index += 1
        elif char == ";" or char in EXCLUDED_UNQUOTED:
            return True  # E2, E9
        elif char in "&|<>":
            token = next((t for t in UNCOUNTED_TOKENS if text.startswith(t, index)), None)
            if token:
                index += len(token)
            elif char == "&" or text.startswith("||", index):
                return True  # E1, E3
            else:
                index += 1  # a pipe or a redirection character
        else:
            index += 1
    return quote != ""  # E5


def cd_prefix_allowed(command, candidate):
    """True when the cd prefix candidate also passes the exclusion rules."""
    if not candidate:
        return False
    parts = split_cd_prefix(command)
    return parts is not None and not cd_remainder_excluded(parts[1])


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
    cd_candidate = is_cd_prefixed_approved(command, approved, common_dir)
    if command not in declared and command not in approved and not cd_candidate:
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
    elif cd_prefix_allowed(command, cd_candidate):
        emit(
            "allow",
            "em-workflow guard: 承認済みコマンドの worktree への cd 前置形"
            "（cd より後ろが approvals.json に完全一致）",
        )
    elif command in declared:
        emit(
            "deny",
            "em-workflow guard: workflow.yaml 由来のコマンドが未承認だよ。コマンド承認ゲートを実行してから再試行して",
            UNAPPROVED_GUIDANCE,
        )
    # Otherwise no decision: only an excluded cd prefix candidate that is
    # neither approved nor declared as a whole reaches this point.
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

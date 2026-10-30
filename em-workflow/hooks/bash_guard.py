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
    physical-path fallback. A path under /proc or /dev/fd fails the path
    check: it is under /proc when its first component is `proc`, and under
    /dev/fd when its first two components are `dev` and `fd`, empty and `.`
    components ignored. This is judged on the path as written, on each stage
    reached while resolving the logical path and the physical path component
    by component, and on the target of each link followed, not on the final
    realpath alone. The lexical check of a link's target text applies only to
    an absolute target; a relative target is joined to the directory that holds
    the link and judged at the resolution stages. A resolution error counts as
    not below.
    <path> is only resolved, never used as the directory or argument of a
    child process
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
import stat
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


def resolves_to_directory(path):
    """True when the operating system resolves path exactly as written to a
    directory. The kernel applies each `..` to the directory already reached,
    so a regular file, a missing component, or a link to either, placed before
    a `..`, makes the resolution fail. Raises OSError or ValueError when path
    cannot be resolved (the caller treats that as not a directory)."""
    return stat.S_ISDIR(os.stat(path).st_mode)


# The most links the Linux kernel follows while resolving one path. A loop
# always exceeds it, so it is also the loop detection of the stage walk.
FOLLOWED_LINK_LIMIT = 40


def _under_proc_or_dev_fd(text):
    """True when text, read lexically, names /proc or /dev/fd or a location
    below one of them: after dropping empty components and `.`, the first
    component is `proc`, or the first two are `dev` then `fd`. `..` is not
    interpreted, and the file system is not consulted."""
    parts = [part for part in text.split("/") if part not in ("", ".")]
    return parts[:1] == ["proc"] or parts[:2] == ["dev", "fd"]


def _stage_walk_refuses(path):
    """True when resolving the absolute path text component by component, the
    way the kernel does, reaches a stage under /proc or /dev/fd, or follows a
    link whose absolute target text is under one, or follows more than
    FOLLOWED_LINK_LIMIT links, or meets an error other than an absent or
    non-directory stage. The walk stops at the first refused stage, so it never
    resolves anything inside /proc.

    The lexical check of a link's target text applies only to an absolute
    target; a relative target is joined to the directory that holds the link
    and judged at the resolution stages. Every stage it leads to, the location
    left after each `..` included, is checked like any other stage, so a
    relative target is refused only when a stage it leads to is under /proc or
    /dev/fd.

    A stage that does not exist, or a non-directory, ends the walk without
    refusal: the operating system cannot resolve any further stage of the
    path, and the caller's rule decides it exactly as before."""
    pending = path.split("/")
    reached = []  # components of the location reached so far; never a link
    followed = 0
    try:
        while pending:
            name = pending.pop(0)
            if name in ("", "."):
                continue
            if name == "..":
                if reached:
                    reached.pop()
                if _under_proc_or_dev_fd("/" + "/".join(reached)):
                    return True
                continue
            stage = "/" + "/".join(reached + [name])
            if _under_proc_or_dev_fd(stage):
                return True
            try:
                mode = os.lstat(stage).st_mode
            except (FileNotFoundError, NotADirectoryError):
                return False
            if stat.S_ISLNK(mode):
                followed += 1
                if followed > FOLLOWED_LINK_LIMIT:
                    return True
                target = os.readlink(stage)
                if target.startswith("/"):
                    if _under_proc_or_dev_fd(target):
                        return True
                    reached = []
                # A relative target starts from the directory that holds the
                # link, which is `reached`; the stage checks of this loop
                # judge each stage it leads to.
                pending = target.split("/") + pending
                continue
            if not stat.S_ISDIR(mode):
                return False
            reached.append(name)
    except (OSError, ValueError):
        return True
    return False


def is_below(path, area):
    """True when path reaches an existing directory strictly below area the
    way Bash's cd does. path is only resolved, never handed to a child process.

    A path under /proc or /dev/fd fails the path check: the operating system
    resolves such a path against the process that asks, and the hook process is
    not the Bash process. This is judged on the path as written, on each stage
    reached while resolving the logical path and the physical path component by
    component, and on the target of each link followed, never on the final
    realpath alone. The lexical check of a link's target text applies only to
    an absolute target; a relative target is joined to the directory that holds
    the link and judged at the resolution stages. A link loop or more than
    FOLLOWED_LINK_LIMIT followed links fails the check as well. This
    precondition runs before the rule below and never replaces it.

    Bash first moves to the logical path (each `..` collapsed against the
    component written before it, then links resolved). When that move fails
    it falls back to the physical path (links resolved component by component,
    each `..` applying to the directory already resolved). The physical path
    is an existing directory only when the operating system itself resolves
    path as written to a directory; the lenient realpath is used for the
    location compared against area, never to decide that. So:
      - logical path is an existing directory: both paths must be existing
        directories strictly below area;
      - otherwise: the physical path alone must be an existing directory
        strictly below area.
    Any resolution error is False.
    """
    try:
        if _under_proc_or_dev_fd(path):
            return False
        if _stage_walk_refuses(os.path.normpath(path)) or _stage_walk_refuses(path):
            return False
        physical = os.path.realpath(path)
        logical = os.path.realpath(os.path.normpath(path))
        physical_is_directory = os.path.isdir(physical) and resolves_to_directory(path)
        if os.path.isdir(logical):
            return (
                physical_is_directory
                and strictly_below(logical, area)
                and strictly_below(physical, area)
            )
        return physical_is_directory and strictly_below(physical, area)
    except (OSError, ValueError):
        return False


def is_cd_prefixed_approved(command, approved, common_dir):
    """True for `cd "<path>" && <approved>` with <path> in the worktree area.

    This is the cd prefix candidate: it decides whether the command is
    workflow-relevant. Whether the cd prefix allow is given is decided by
    cd_prefix_allowed.
    """
    parts = split_cd_prefix(command)
    if parts is None:
        return False
    path, remainder = parts
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

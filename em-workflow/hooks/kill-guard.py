#!/usr/bin/env python3
"""PreToolUse(Bash) guard for process-termination commands.

Blocks kill / pkill / killall invocations that would reach a process outside
the agent's own process subtree. The motivating incident: an agent ran
`pkill -f "/usr/bin/emterm"` to clean up a hung helper and killed the user's
terminal emulator, which was an ANCESTOR of the Claude Code process — taking
the whole session down with it.

This is a backstop, not the primary mechanism. The rule is to start long-lived
processes with the Bash tool's `run_in_background` and stop them with
TaskStop — no PID, no kill, nothing to guard. This hook only sees commands
that reached for `kill` directly.

Decision model:

  target is an ancestor of the claude process -> deny, always
  every target is a descendant                -> allow silently
  anything else, or unresolvable              -> ask the user

The middle tier is `ask`, not `deny`, on purpose. Provenance cannot be
established mechanically: the Bash tool starts each command in its own
session, and anything backgrounded there is orphaned onto init the moment the
tool call returns, so a process the agent legitimately started stops being a
descendant almost immediately. Denying that case outright would reproduce the
"cannot kill the thing I need to kill" problem this guard is meant to avoid,
so the ambiguous case goes to the human instead.

That last tier assumes a human is watching. Under `claude-batch` nobody is:
an `ask` renders a confirmation prompt into a detached tmux pane and the run
sits there until someone attaches. It happened — a subagent's throwaway
`kill $PID` cleanup froze an 8-task batch for nine hours with seven tasks
already merged. So when CLAUDE_BATCH marks the run as unattended, `ask` is
demoted to `deny`: the agent gets the reason back as tool feedback and can
rewrite the command into a form that needs no kill at all, and the batch keeps
moving.

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import json
import os
import re
import shlex
import subprocess
import sys

# Command words we inspect. Anything else passes straight through.
KILLERS = ("kill", "pkill", "killall")

# Set by claude-batch on the claude process it launches; hooks inherit it.
# Its presence means no human is in front of this session.
BATCH_ENV = "CLAUDE_BATCH"

# Values that mean "not set" even when the variable exists.
BATCH_OFF = ("", "0", "false", "no")

# Statement separators after which a new command word can begin. The incident
# command was `pkill -f "..." 2>/dev/null; sleep 1; ps aux | grep ...`, so
# scanning only the first word of the string would have missed it entirely.
#
# Deliberately does NOT split on `$(` or a backtick: a statement such as
# `kill $(pgrep foo)` must keep its substitution attached so the DYNAMIC check
# below sees it. Substitution bodies are scanned separately (see statements()).
SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|&\n])")

# Bodies of command substitutions, extracted so a killer hidden inside one
# (`echo $(pkill foo)`) is scanned too.
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")

# Redirection operands (`2>/dev/null`, `>out`, `&>log`) are not kill arguments.
# The original incident command ended in `2>/dev/null`, and treating that as
# the pkill pattern made the guard match nothing and wave the command through.
REDIRECTION = re.compile(r"^(?:\d*[<>]|&>|>&)")

# Substitutions we cannot resolve statically.
DYNAMIC = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]")


def read_ppid(pid):
    """Parent of `pid`, or None if it cannot be read."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            data = fh.read()
        # comm may contain spaces/parens; fields after the final ')' are safe.
        after = data[data.rindex(b")") + 1:].split()
        return int(after[1])  # ppid is the 2nd field after state
    except Exception:
        return None


def ancestors(pid):
    """Every PID from `pid` up to the root, inclusive."""
    out, seen = [], set()
    cur = pid
    while cur and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = read_ppid(cur)
        if cur in (0, None):
            break
    return out


def comm(pid):
    try:
        with open(f"/proc/{pid}/comm") as fh:
            return fh.read().strip()
    except Exception:
        return "?"


def claude_root(chain):
    """The `claude` process in our ancestry — the root of 'our' subtree.

    Falls back to this process when no claude ancestor is visible, which keeps
    the guard conservative rather than accidentally widening the allowed set.
    """
    for pid in chain:
        if comm(pid) == "claude":
            return pid
    return chain[0] if chain else os.getpid()


def descendants(root):
    """Every PID under `root`, via a parent -> children map built from /proc."""
    children = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        ppid = read_ppid(pid)
        if ppid is not None:
            children.setdefault(ppid, []).append(pid)

    out, stack = set(), [root]
    while stack:
        cur = stack.pop()
        for child in children.get(cur, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def pgrep(args):
    """PIDs matching a pgrep-style argument list, or None on failure."""
    try:
        res = subprocess.run(
            ["pgrep", *args], capture_output=True, text=True, timeout=5
        )
    except Exception:
        return None
    if res.returncode not in (0, 1):  # 1 = no match, which is a valid answer
        return None
    return [int(x) for x in res.stdout.split() if x.isdigit()]


def statements(command):
    """Candidate command statements, including command-substitution bodies.

    Substitution bodies are yielded IN ADDITION to the statements that contain
    them, so `kill $(pgrep foo)` is seen both as an unresolvable `kill` (the
    outer statement still holds the `$(`) and as a plain `pgrep` (the body).
    """
    out = [s.strip() for s in SEGMENT_SPLIT.split(command) if s.strip()]
    for match in SUBSTITUTION.finditer(command):
        body = match.group(1) if match.group(1) is not None else match.group(2)
        if body and body.strip():
            out.extend(s.strip() for s in SEGMENT_SPLIT.split(body) if s.strip())
    return out


def resolve(seg):
    """Resolve one segment to (killer, targets, reason).

    targets is None when the segment is a killer we could not resolve.
    killer is None when the segment is not a termination command at all.
    """
    # shlex strips the quoting the shell would have removed, so a pattern
    # written as `pkill -f "/usr/bin/emterm"` resolves to /usr/bin/emterm
    # rather than to a literal with quotes that matches nothing.
    raw = seg
    try:
        parts = shlex.split(seg, comments=False)
    except ValueError:
        # Unbalanced quoting: only a problem if this segment is a killer.
        head = seg.split()
        if head and os.path.basename(head[0]) in KILLERS:
            return os.path.basename(head[0]), None, "引用符が閉じておらず引数を解釈できない"
        return None, None, None

    parts = [p for p in parts if not REDIRECTION.match(p)]
    if not parts:
        return None, None, None

    # shlex drops the `$(`/backtick markers that DYNAMIC looks for, so the
    # dynamic check must consult the original text.
    seg = raw

    # Skip leading env assignments and common prefixes.
    idx = 0
    while idx < len(parts) and ("=" in parts[idx] and not parts[idx].startswith("-")):
        idx += 1
    if idx >= len(parts):
        return None, None, None

    word = os.path.basename(parts[idx])
    if word not in KILLERS:
        return None, None, None

    args = parts[idx + 1:]
    if DYNAMIC.search(seg):
        return word, None, "引数に変数展開・コマンド置換が含まれ、対象 PID を静的に解決できない"

    if word == "kill":
        pids, sig_zero, end_of_opts = [], False, False
        for a in args:
            # Everything after `--` is an operand, including a negative PID
            # (the unambiguous `kill -- -PGID` process-group form).
            if not end_of_opts and a == "--":
                end_of_opts = True
                continue
            if not end_of_opts and a.startswith("-") and not a[1:].isdigit():
                if a in ("-0", "-s0", "-sSIGZERO"):
                    sig_zero = True
                continue
            if not end_of_opts and a.startswith("-") and a[1:].isdigit():
                # A bare `-N` before `--` is a signal number, not a PID.
                if a == "-0":
                    sig_zero = True
                continue
            if a.startswith("%"):
                return word, None, "ジョブ指定 (%n) は PID に解決できない"
            if a.lstrip("-").isdigit():
                val = int(a)
                if val < 0:
                    return word, None, (
                        f"負の PID {val} はプロセスグループ全体が対象になり、"
                        f"どのプロセスに届くか静的に確定できない"
                    )
                pids.append(val)
            else:
                return word, None, f"PID として解釈できない引数: {a}"
        if sig_zero:
            # Signal 0 delivers nothing; it is a liveness probe, so it is safe
            # against any target including an ancestor.
            return word, [], "signal 0 (存在確認のみ)"
        return word, pids, None

    if word == "pkill":
        flags = [a for a in args if a.startswith("-")]
        rest = [a for a in args if not a.startswith("-")]
        if not rest:
            return word, None, "パターンが特定できない"
        pattern_flags = [f for f in flags if f in ("-f", "-x", "-a", "-i")]
        # pkill takes the pattern as its FIRST operand.
        pids = pgrep([*pattern_flags, rest[0]])
        if pids is None:
            return word, None, "pgrep での対象解決に失敗した"
        return word, pids, None

    # killall matches on exact process name.
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        return word, None, "プロセス名が特定できない"
    pids = pgrep(["-x", rest[0]])
    if pids is None:
        return word, None, "pgrep での対象解決に失敗した"
    return word, pids, None


def unattended():
    """True when this session runs under claude-batch with nobody watching."""
    return os.environ.get(BATCH_ENV, "").strip().lower() not in BATCH_OFF


def decide(decision, reason):
    """Emit a PreToolUse permission decision and stop.

    `ask` becomes `deny` in an unattended run: a prompt nobody can answer stops
    the batch outright, while a denial comes back as tool feedback the agent
    can act on.
    """
    if decision == "ask" and unattended():
        decision = "deny"
        reason = (
            f"{reason}\n"
            f"無人実行（claude-batch）のため確認を取れないので、`ask` を `deny` に"
            f"降格した。kill を使わない形に書き換えて続行する。\n"
            f"検証用に自分で起こしたプロセスなら、`timeout <秒> <コマンド>` で寿命を"
            f"持たせるか、Bash を run_in_background で起動して TaskStop で止める。\n"
            f"既存プロセスを落とす必要が本当にあるなら、ユーザーに報告して指示を仰ぐ。"
        )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": f"[kill-guard] {reason}",
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail-open: a malformed payload is not our problem

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or not any(k in command for k in KILLERS):
        sys.exit(0)

    # The protected set is the claude process and everything above it — the
    # branch this session is sitting on. Intermediate processes between this
    # hook and claude (a shell that spawned it during testing, say) are NOT
    # protected: they are inside claude's own subtree, so the descendant rule
    # governs them.
    root = claude_root(ancestors(os.getpid()))
    chain_set = set(ancestors(root))
    subtree = descendants(root)

    for seg in statements(command):
        killer, targets, reason = resolve(seg)
        if killer is None:
            continue

        if targets is None:
            decide(
                "ask",
                f"`{killer}`: {reason}。対象プロセスを静的に確定できないため確認する。\n"
                f"意図した対象が分かっているなら、`pgrep -a <pattern>` で目視してから "
                f"`kill <数値PID>` の形で撃ち直すと確認不要になる。",
            )

        if not targets:
            continue  # nothing matched, or signal 0

        hit_ancestor = [p for p in targets if p in chain_set]
        if hit_ancestor:
            names = ", ".join(f"{p} ({comm(p)})" for p in hit_ancestor)
            decide(
                "deny",
                f"`{killer}` の対象に **このセッションの祖先プロセス** が含まれる → {names}\n"
                f"これを殺すとホスト端末ごと Claude Code のセッションが落ちる。例外なく拒否。\n"
                f"長時間プロセスは run_in_background で起動し TaskStop で止める。",
            )

        outside = [p for p in targets if p not in subtree]
        if outside:
            names = ", ".join(f"{p} ({comm(p)})" for p in outside[:8])
            more = "" if len(outside) <= 8 else f" ほか{len(outside) - 8}件"
            decide(
                "ask",
                f"`{killer}` の対象が Claude Code の子孫プロセスではない → {names}{more}\n"
                f"自分で起動したプロセスでも、バックグラウンド実行後に孤児化していれば"
                f"ここに来る。無関係なプロセスでないか確認してほしい。\n"
                f"検証用のプロセスなら、Bash を run_in_background で起動して TaskStop で"
                f"止めれば kill 自体が不要になる（無人実行でも止まらない）。",
            )

    sys.exit(0)


if __name__ == "__main__":
    main()

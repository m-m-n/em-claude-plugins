#!/usr/bin/env python3
"""Expectation suite for destructive-guard.py.

    python3 em-workflow/hooks/tests/run-destructive-guard.py

Exits non-zero on the first mismatch, so it drops straight into CI or a
pre-push check. Pass a path to test a copy elsewhere, e.g. the installed
one under ~/.claude/hooks/.

Two halves carry equal weight. The `deny` and `ask` cases guard the point of
the hook: a genuinely destructive command must not slip through. The `allow`
cases guard the cost of getting there: every false positive stalls an
unattended run, and each one here is a shape that actually did — a `rm -rf`
written inside a quoted string, a here-doc body holding shell examples, a
redirect to /dev/null read as another path to delete.

CLAUDE_BATCH is cleared for every run. The hook demotes `ask` to `deny` when
it sees that variable (nobody is there to answer), which would fail every
`ask` case if the suite happened to run inside a batch session. The demotion
itself is covered by the last case, which sets the variable back.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "destructive-guard-cases.json")
GUARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "destructive-guard.py")


def verdict(command, batch=False):
    """Run the guard over one command and return (decision, reason)."""
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)
    if batch:
        env["CLAUDE_BATCH"] = "1"
    proc = subprocess.run(
        [sys.executable, GUARD],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return "(exit %d)" % proc.returncode, (proc.stderr or "").strip()
    if not proc.stdout.strip():
        return "(silent)", "フックが判定を出さずに終了した。"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


def main():
    cases = json.load(open(CASES, encoding="utf-8"))
    failed = []

    for want, label, command in cases:
        got, reason = verdict(command)
        if got != want:
            failed.append((label, want, got, reason))
        print(f"{'ok  ' if got == want else 'FAIL'} {want:5} {label}")
        if got != want:
            print(f"       got={got} {reason[:150]}")

    # The unattended demotion: with nobody to answer, `ask` has to become
    # `deny` rather than hang a batch run on a prompt.
    got, reason = verdict("echo x > ~/.claude/settings.json", batch=True)
    label = "無人実行では ask が deny に降格"
    if got != "deny":
        failed.append((label, "deny", got, reason))
    print(f"{'ok  ' if got == 'deny' else 'FAIL'} deny  {label}")

    total = len(cases) + 1
    print(f"\n{total - len(failed)}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

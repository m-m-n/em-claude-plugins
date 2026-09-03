"""Parity check between `em-workflow/hooks/failed-run-cleanup-guard.py` (the
"new guard") and `em-workflow/hooks/destructive-guard.py` (task0004, D7):
one fixed corpus of command strings is fed to BOTH guards as subprocesses,
with a JSON payload on stdin -- the same contract Claude Code uses and the
same one `em-workflow/hooks/tests/run-destructive-guard.py` and
`tests/test_failed_run_cleanup_guard.py` already use -- and the SUPERSET
invariant (IMPLEMENTATION.md "Target invocation shapes (S1/S2/S3)") is
asserted directly instead of living only as a sentence there:

    whenever the new guard emits ANY decision (ask or deny -- CLAUDE_BATCH
    is left unset for this corpus; an ask and a deny are both "a decision"
    for this invariant, and pinning the ask->deny demotion under batch is
    TS-4's job, not this module's), destructive-guard must not emit `allow`
    for the same command.

...plus the narrowness converse: a quoted mention, a here-doc body, a near
miss of the same command family, and an unrelated command must all leave
the new guard silent AND destructive-guard's blanket allow intact.

Neither guard is imported; neither is refactored to be importable. The
corpus is DATA -- a later target shape or grouping construct is added as a
row here, never as new assertion code.

Standard library only, per test/README.md.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEW_GUARD = REPO_ROOT / "em-workflow" / "hooks" / "failed-run-cleanup-guard.py"
DESTRUCTIVE_GUARD = REPO_ROOT / "em-workflow" / "hooks" / "destructive-guard.py"

FEATURE = "some-feature"


def run_guard(path, command, cwd):
    """Run one guard script over COMMAND with CWD in the payload; return its
    `permissionDecision` string, or None when it emitted no decision at all
    (silent, exit 0) -- matching both guards' "no output on stdout" no-
    decision contract.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)  # ask/deny are both "a decision" here (Test Notes)
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


class WorktreeFixture:
    """A temporary root reproducing `.claude/worktrees/em-workflow/{feature}/
    integration/feature-docs/{feature}/workflow.yaml` with a FAILED top-level
    step, so failed-run-cleanup-guard.py actually reaches a decision (Test
    Notes: "only then does the new guard emit a decision at all; a corpus
    row would silently become vacuous against a healthy fixture").

    Duplicated from (not imported from) test_failed_run_cleanup_guard.py's
    own fixture, per this repository's established substitute for a shared
    module between per-task test files: a small duplicated primitive, pinned
    here by exercising both guards against the same on-disk shape rather
    than by a dedicated comparison test (IMPLEMENTATION.md Layer Structure).
    """

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def close(self):
        self._tmp.cleanup()

    def worktree_dir(self, feature):
        return self.root / ".claude" / "worktrees" / "em-workflow" / feature / "integration"

    def write_failed_workflow(self, feature):
        docs = self.worktree_dir(feature) / "feature-docs" / feature
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "workflow.yaml").write_text(
            "workflow:\n"
            "  - id: create-spec\n"
            "    status: completed\n"
            "  - id: implement\n"
            "    status: failed\n"
        )
        return self.worktree_dir(feature)


# Grouping constructs named in D7 / the task plan's AC-2 & AC-4: each wraps a
# real invocation one level in, so the statement's REAL head is not the
# grouping token itself.
GROUPINGS = [
    ("subshell", lambda c: f"({c})"),
    ("brace group", lambda c: f"{{ {c}; }}"),
    ("function defined and invoked in the same command", lambda c: f"f() {{ {c}; }}; f"),
    ("command substitution", lambda c: f"x=$({c})"),
    ("inline interpreter string", lambda c: f"bash -c '{c}'"),
]


def build_corpus(wt, root):
    """One fixed corpus: (category, label, command, cwd, mode).

    WT is the fixture's integration worktree dir (ends in
    `.../{FEATURE}/integration`); ROOT is the fixture's temp root, which
    doubles as the ancestor S2's branch-name resolution walks up from.

    mode is the assertion this row proves:
      - "decide_not_allow": the new guard must decide (ask/deny); destructive
        -guard must not emit allow (the superset invariant, D2/D7).
      - "decide_deny_exact": as above, but destructive-guard must specifically
        deny (Test Notes' compound edge case: the deferral suppresses only
        the trailing allow, never the checks).
      - "decide_silent_exact": as above, but destructive-guard must emit no
        decision at all (the compound row's narrowness counterpart: a benign
        second statement must not spuriously deny).
      - "silent_allow": the narrowness converse (D2/AC-5) -- the new guard
        must stay silent, and destructive-guard's blanket allow must survive.
    """
    wt_str = str(wt)
    root_str = str(root)

    s1_plain = f"git worktree remove {wt_str}"
    s2_plain = f"git branch -d em-workflow/{FEATURE}/integration"
    s3_plain = "gh pr create --title x --body y"

    rows = []

    for shape, plain_cmd, cwd in (
        ("S1", s1_plain, root_str),
        ("S2", s2_plain, root_str),
        ("S3", s3_plain, wt_str),
    ):
        rows.append((shape, f"{shape} plain form", plain_cmd, cwd, "decide_not_allow"))
        for gname, wrap in GROUPINGS:
            rows.append(
                (shape, f"{shape} nested in {gname}", wrap(plain_cmd), cwd, "decide_not_allow")
            )

    # Unresolvable-operand forms (AC-3): S1/S2 carry a textual operand that
    # can be dynamic; S3 resolves from cwd alone and has no operand to make
    # unresolvable, so it is not represented here.
    rows += [
        (
            "S1",
            "S1 unresolvable: variable expansion",
            'git worktree remove "$WT"',
            root_str,
            "decide_not_allow",
        ),
        (
            "S1",
            "S1 unresolvable: glob star",
            f"git worktree remove {wt.parent}/*",
            root_str,
            "decide_not_allow",
        ),
        (
            "S1",
            "S1 unresolvable: bracket-form glob",
            f"git worktree remove {wt.parent}/inte[gr]ation",
            root_str,
            "decide_not_allow",
        ),
        (
            "S1",
            "S1 unresolvable: command substitution (whole operand)",
            "git worktree remove $(get_target_path)",
            root_str,
            "decide_not_allow",
        ),
        (
            "S2",
            "S2 unresolvable: variable expansion",
            'git branch -d "em-workflow/$FEATURE/integration"',
            root_str,
            "decide_not_allow",
        ),
        (
            "S2",
            "S2 unresolvable: bracket-form glob",
            f"git branch -d em-workflow/{FEATURE}/integrat[io]n",
            root_str,
            "decide_not_allow",
        ),
        (
            "S2",
            "S2 unresolvable: command substitution (whole operand)",
            "git branch -d $(get_branch_name)",
            root_str,
            "decide_not_allow",
        ),
    ]

    # Narrowness (AC-5): the new guard stays silent, destructive-guard's
    # blanket allow survives.
    rows += [
        (
            "narrow",
            "narrow: quoted mention (S1)",
            f'echo "git worktree remove {wt_str}"',
            root_str,
            "silent_allow",
        ),
        (
            "narrow",
            "narrow: here-document body (S3)",
            "cat <<'EOF'\ngh pr create --title x\nEOF",
            wt_str,
            "silent_allow",
        ),
        (
            "narrow",
            "narrow: near miss of the same command family (S1, worktree list)",
            "git worktree list",
            root_str,
            "silent_allow",
        ),
        (
            "narrow",
            "narrow: near miss of the same command family (S2, branch create not delete)",
            f"git branch em-workflow/{FEATURE}/integration",
            root_str,
            "silent_allow",
        ),
        (
            "narrow",
            "narrow: near miss of the same command family (S3, pr list not create)",
            "gh pr list",
            wt_str,
            "silent_allow",
        ),
        (
            "narrow",
            "narrow: unrelated command",
            "echo hello world",
            root_str,
            "silent_allow",
        ),
    ]

    # Compound edge case (Test Notes): the deferral suppresses only the
    # trailing allow, never the checks -- and, conversely, a benign second
    # statement must not spuriously turn into a deny just because the first
    # statement is a deferred target shape.
    rows += [
        (
            "compound",
            "compound: target shape then a genuinely destructive statement",
            f"{s1_plain}; rm -rf /home/sakura/unrelated-target",
            root_str,
            "decide_deny_exact",
        ),
        (
            "compound",
            "compound narrowness counterpart: target shape then a benign statement",
            f"{s1_plain}; echo done",
            root_str,
            "decide_silent_exact",
        ),
    ]

    return rows


def evaluate_row(mode, new_decision, destructive_decision):
    """Return None when the row's invariant holds, else a failure message."""
    new_decided = new_decision is not None
    if mode == "decide_not_allow":
        if not new_decided:
            return "failed-run-cleanup-guard emitted no decision (vacuous row)"
        if destructive_decision == "allow":
            return "destructive-guard emitted allow while the new guard decided"
    elif mode == "decide_deny_exact":
        if not new_decided:
            return "failed-run-cleanup-guard emitted no decision (vacuous row)"
        if destructive_decision != "deny":
            return f"expected destructive-guard deny, got {destructive_decision!r}"
    elif mode == "decide_silent_exact":
        if not new_decided:
            return "failed-run-cleanup-guard emitted no decision (vacuous row)"
        if destructive_decision is not None:
            return f"expected destructive-guard silent, got {destructive_decision!r}"
    elif mode == "silent_allow":
        if new_decided:
            return f"failed-run-cleanup-guard unexpectedly decided ({new_decision!r})"
        if destructive_decision != "allow":
            return f"expected destructive-guard allow, got {destructive_decision!r}"
    else:  # pragma: no cover - corpus authoring error, not a runtime case
        raise ValueError(f"unknown corpus row mode: {mode!r}")
    return None


class GuardDeferralParityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = WorktreeFixture()
        cls.wt = cls.fixture.write_failed_workflow(FEATURE)
        cls.corpus = build_corpus(cls.wt, cls.fixture.root)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()


# ---------------------------------------------------------------------------
# Test Notes: "the module asserts up front that the plain form of each shape
# does produce a decision" -- guards against every superset row below
# passing vacuously because the fixture failed to wire up a real failure.
# ---------------------------------------------------------------------------
class TestFixtureProducesRealDecisions(GuardDeferralParityTestCase):
    def test_plain_form_of_each_shape_yields_a_decision_from_the_new_guard(self):
        plain_rows = [row for row in self.corpus if row[1].endswith("plain form")]
        self.assertEqual(len(plain_rows), 3, "expected exactly one plain-form row per shape")
        for shape, label, command, cwd, mode in plain_rows:
            with self.subTest(label=label):
                decision = run_guard(NEW_GUARD, command, cwd)
                self.assertIsNotNone(
                    decision,
                    f"{label}: fixture produced no decision at all -- "
                    "the corpus below would pass vacuously",
                )


# ---------------------------------------------------------------------------
# AC-2, AC-3, AC-4: the superset direction, plus the compound edge case.
# ---------------------------------------------------------------------------
class TestSupersetInvariantHoldsAcrossTheCorpus(GuardDeferralParityTestCase):
    def test_superset_invariant(self):
        superset_modes = {"decide_not_allow", "decide_deny_exact", "decide_silent_exact"}
        rows = [row for row in self.corpus if row[4] in superset_modes]
        self.assertTrue(rows, "corpus produced no superset-direction rows")
        for shape, label, command, cwd, mode in rows:
            with self.subTest(label=label):
                new_decision = run_guard(NEW_GUARD, command, cwd)
                destructive_decision = run_guard(DESTRUCTIVE_GUARD, command, cwd)
                failure = evaluate_row(mode, new_decision, destructive_decision)
                self.assertIsNone(
                    failure,
                    f"{failure} (command={command!r}, "
                    f"new={new_decision!r}, destructive={destructive_decision!r})",
                )


# ---------------------------------------------------------------------------
# AC-5: the narrowness converse.
# ---------------------------------------------------------------------------
class TestNarrownessConverseHoldsAcrossTheCorpus(GuardDeferralParityTestCase):
    def test_narrowness_converse(self):
        rows = [row for row in self.corpus if row[4] == "silent_allow"]
        self.assertTrue(rows, "corpus produced no narrowness rows")
        for shape, label, command, cwd, mode in rows:
            with self.subTest(label=label):
                new_decision = run_guard(NEW_GUARD, command, cwd)
                destructive_decision = run_guard(DESTRUCTIVE_GUARD, command, cwd)
                failure = evaluate_row(mode, new_decision, destructive_decision)
                self.assertIsNone(
                    failure,
                    f"{failure} (command={command!r}, "
                    f"new={new_decision!r}, destructive={destructive_decision!r})",
                )


if __name__ == "__main__":
    unittest.main()

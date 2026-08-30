"""Two-layer pin joining the documented hook classification (IMPLEMENTATION.md
Shared Components, "Hook classification contract") to the hook
implementations. This module reads nothing from
em-workflow/references/implement-phase.md, so it stays green in this
worktree both before and after another task's prose rewrite of that file.

Layer 1 (static source scan, negative claim): none of
queue_launch_guard.py, queue_failure_net.py, queue_taskstop_net.py performs
a per-task workflow.yaml status read. The matcher keys on the identifiers
that CONSTITUTE such a read in this codebase -- the
`task_statuses_from_workflow` helper name and the `TASK_STATUS_RE` /
`TASKS_SECTION_RE` regex names queue_stop_guard.py uses -- and never on the
bare substring `workflow.yaml` alone, since queue_taskstop_net.py's own
module docstring contains that substring while reading nothing (D6).
Accepted boundary (D6, stated rather than solved): a status read performed
by an entirely novel mechanism (e.g. a YAML library) is not caught by a
source-text pin.

Layer 2 (behavioral observation): queue_stop_guard.py is invoked as a
subprocess against a throwaway fixture whose journal last event is
`failed`, varying only that task's own workflow.yaml status between
`pending` (carve-out applies) and a non-`pending` value (it does not).
tests/test_queue_stop_guard.py already covers this discriminator
behaviorally; that coverage is deliberately duplicated here, unmodified and
not imported (D3), because this module's purpose is different -- it is the
pin joining the DOCUMENTED classification to observed behavior, and it must
fail if the hook's behavior ever diverges from what the documentation
claims.

Per Conventions' no-cross-import rule, no other test module is imported;
any fixture shape or literal borrowed from tests/test_queue_stop_guard.py
is reproduced locally with a provenance comment.
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

HOOKS_DIR = os.path.join(REPO_ROOT, "em-workflow", "hooks")
JOURNAL_ONLY_HOOK_PATHS = {
    "queue_launch_guard.py": os.path.join(HOOKS_DIR, "queue_launch_guard.py"),
    "queue_failure_net.py": os.path.join(HOOKS_DIR, "queue_failure_net.py"),
    "queue_taskstop_net.py": os.path.join(HOOKS_DIR, "queue_taskstop_net.py"),
}
STOP_GUARD_HOOK_PATH = os.path.join(HOOKS_DIR, "queue_stop_guard.py")

# Provenance: identifiers copied from em-workflow/hooks/queue_stop_guard.py
# (this worktree's checkout, commit 300b565d4985d24b77c71077368ea79cc1c68a98)
# -- the helper name and the two line-scan regex names that together
# perform the per-task status read (D6). Kept in one module-level constant
# read by both the positive and the negative-proof test (Conventions
# contract 1).
STATUS_READ_IDENTIFIERS = (
    "task_statuses_from_workflow",
    "TASK_STATUS_RE",
    "TASKS_SECTION_RE",
)

# A per-task status read, reduced to the minimum that trips the matcher.
VIOLATING_SAMPLE = '''\
def helper(workflow_yaml_path):
    statuses = task_statuses_from_workflow(workflow_yaml_path)
    return statuses.get("task0001")
'''

# The bare substring `workflow.yaml`, in a docstring position, with no
# status-read identifier anywhere in the sample (D6's accepted
# non-violation: queue_taskstop_net.py's own docstring is shaped exactly
# like this).
BARE_SUBSTRING_SAMPLE = '''\
"""This hook never touches `workflow.yaml` for any purpose."""
'''


def scan_for_status_read_violations(source_text):
    """The one reusable scan function (Design "Shape"): applied identically
    to the real hook sources and to both proof samples. Returns the sorted
    list of STATUS_READ_IDENTIFIERS whose whole-word occurrence appears in
    `source_text`. Never matches on the bare substring `workflow.yaml`
    alone -- that string is not one of the matcher keys (D6)."""
    violations = [
        identifier
        for identifier in STATUS_READ_IDENTIFIERS
        if re.search(r"\b" + re.escape(identifier) + r"\b", source_text)
    ]
    return sorted(violations)


class TestScanForStatusReadViolationsProofs(unittest.TestCase):
    """AC-2, AC-3: the scan function used against the real sources cannot
    pass over every input (a genuine status read IS reported), and cannot
    false-positive on the bare substring alone (D6)."""

    def test_violating_sample_is_reported(self):
        violations = scan_for_status_read_violations(VIOLATING_SAMPLE)
        self.assertIn("task_statuses_from_workflow", violations)

    def test_bare_workflow_yaml_substring_alone_is_not_reported(self):
        violations = scan_for_status_read_violations(BARE_SUBSTRING_SAMPLE)
        self.assertEqual(violations, [])


class TestPreChangeSampleGuards(unittest.TestCase):
    """Non-vacuity contract 4: each sample carries a positively-asserted
    RETAINED anchor, so a negative proof can never degrade into a
    tautology against an emptied sample."""

    def test_violating_sample_retains_its_status_read_call(self):
        self.assertIn("task_statuses_from_workflow(", VIOLATING_SAMPLE)

    def test_bare_substring_sample_retains_the_workflow_yaml_literal(self):
        self.assertIn("workflow.yaml", BARE_SUBSTRING_SAMPLE)


class TestQueueHookStatusReadPin(unittest.TestCase):
    """AC-1: the static scan over the three journal-only hooks' own
    sources, using the exact same scan function proven against the
    samples above."""

    def test_no_journal_only_hook_performs_a_per_task_status_read(self):
        for name, path in JOURNAL_ONLY_HOOK_PATHS.items():
            with self.subTest(hook=name):
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                violations = scan_for_status_read_violations(source)
                self.assertEqual(
                    violations,
                    [],
                    "{name} performs a per-task workflow.yaml status read "
                    "via: {violations}".format(name=name, violations=violations),
                )

    def test_taskstop_net_bare_workflow_yaml_docstring_mention_is_not_a_violation(self):
        # AC-2's live half: queue_taskstop_net.py's own module docstring
        # contains the bare substring `workflow.yaml` while reading
        # nothing (D6) -- the sanity assertion below confirms the
        # substring really is present, so the violations==[] assertion
        # that follows is not vacuous.
        path = JOURNAL_ONLY_HOOK_PATHS["queue_taskstop_net.py"]
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("workflow.yaml", source)
        violations = scan_for_status_read_violations(source)
        self.assertEqual(violations, [])


# Layer 2 fixture. Feature/task identity kept in module-level constants so
# both cases below assert against the same names.
FIXTURE_FEATURE = "carve-out-pin-feature"
FIXTURE_TASK_ID = "task0001"

DEFAULT_STOP_STDIN = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})


def _build_carveout_fixture(tmp_dir, workflow_status):
    """Builds the ONE throwaway integration-worktree layout Layer 2 needs,
    entirely under `tmp_dir`. Reused byte-for-byte for both the exit-2 and
    exit-0 cases -- only `workflow_status` differs between calls -- so a
    mis-shaped fixture makes the exit-2 case fail loudly instead of letting
    the exit-0 case pass vacuously (Test Notes).

    Layout provenance: reproduced locally and reduced to this module's
    minimum from tests/test_queue_stop_guard.py's StopGuardFixture /
    build_workflow_yaml (this worktree's checkout, commit
    f2ecb04f8ebe3cb59f3ab757e1726703ba58c0f7), per Conventions'
    no-cross-import rule.

    `worktrees_root` is `.claude/worktrees/em-workflow` directly under
    `tmp_dir` (the enumeration root the hook's ancestor walk resolves);
    the SAME `FIXTURE_FEATURE` name is used for both the worktree-side
    segment and the `feature-docs/<segment>` wildcard so the fixture is
    owned (Fixture contract, "feature layout"). Nothing outside `tmp_dir`
    is read or written (AC-6).
    """
    worktrees_root = os.path.join(tmp_dir, ".claude", "worktrees", "em-workflow")
    journal_dir = os.path.join(worktrees_root, FIXTURE_FEATURE)
    integration_dir = os.path.join(journal_dir, "integration")
    docs_dir = os.path.join(integration_dir, "feature-docs", FIXTURE_FEATURE)
    os.makedirs(docs_dir, exist_ok=True)

    workflow_yaml = "\n".join(
        [
            "schema_version: 1",
            "feature: {feature}".format(feature=FIXTURE_FEATURE),
            "workflow:",
            "  - id: implement",
            "    status: in_progress",
            "",
            "tasks:",
            "  {task_id}:".format(task_id=FIXTURE_TASK_ID),
            '    title: "carve-out pin task"',
            "    status: {status}".format(status=workflow_status),
        ]
    ) + "\n"
    with open(os.path.join(docs_dir, "workflow.yaml"), "w", encoding="utf-8") as fh:
        fh.write(workflow_yaml)

    # The journal's last event for the task is ALWAYS `failed` -- only
    # workflow_status varies between cases (Fixture contract).
    journal_line = json.dumps({"event": "failed", "task": FIXTURE_TASK_ID}) + "\n"
    with open(os.path.join(journal_dir, "journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(journal_line)

    # No sidecar is pre-created: a fresh fixture per case starts the
    # consecutive-block counter clean (Fixture contract, "sidecar").
    return tmp_dir


def _run_stop_guard(cwd):
    """Invokes queue_stop_guard.py as a subprocess with `cwd` as its
    working directory, per test/README.md's hook-contract pattern. An
    explicit timeout so a hang surfaces as a failure rather than a stalled
    run (Test Notes)."""
    return subprocess.run(
        [sys.executable, STOP_GUARD_HOOK_PATH],
        cwd=cwd,
        input=DEFAULT_STOP_STDIN,
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestQueueStopGuardCarveOutBehavioralPin(unittest.TestCase):
    """AC-4, AC-5, AC-6: the SAME fixture, differing only in the task's own
    workflow.yaml status, must swing between BLOCK and non-blocking -- the
    pin that fails if queue_stop_guard.py's carve-out behavior ever
    diverges from the documented classification (D3)."""

    def test_pending_status_applies_the_carve_out_and_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_carveout_fixture(tmp, workflow_status="pending")

            result = _run_stop_guard(tmp)

            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCK", result.stderr)
            self.assertIn(FIXTURE_TASK_ID, result.stderr)

    def test_non_pending_status_does_not_apply_the_carve_out(self):
        # Any non-`pending` value: the fixture is otherwise byte-identical,
        # only the status value changes (Test Notes).
        for status in ("failed", "in_progress", "merged", "cancelled"):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    _build_carveout_fixture(tmp, workflow_status=status)

                    result = _run_stop_guard(tmp)

                    self.assertEqual(result.returncode, 0)
                    self.assertNotIn("BLOCK", result.stderr)


class TestModuleImportsStdlibOnly(unittest.TestCase):
    """AC-6: this module itself imports only the standard library (Module
    discipline). Provenance: the AST-walk approach mirrors
    tests/test_queue_stop_guard.py's TestQueueStopGuardStdlibOnly, applied
    here to THIS module's own source rather than the hook's -- reproduced
    locally per Conventions' no-cross-import rule, not imported."""

    def test_only_stdlib_imports(self):
        this_module_path = os.path.abspath(__file__)
        with open(this_module_path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=this_module_path)

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported_names.add(node.module.split(".")[0])

        self.assertTrue(imported_names, "expected at least one import")
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        for name in imported_names:
            if stdlib_names is not None:
                self.assertIn(name, stdlib_names, f"{name} is not a stdlib module")

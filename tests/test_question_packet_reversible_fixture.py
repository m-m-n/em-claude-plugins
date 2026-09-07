"""Tests for task0002: the `reversible: true` counter-example question-packet
fixture (em-workflow/references/fixtures/question-packet/category-fail-
closed/valid-test-pinned-constraint-assumption/) and its declaration shape.

Covers task0002 Acceptance Criteria (feature-docs/assumptions-reversible-
criteria/tasks/task0002.md):

- AC-1: TestNewFixtureCaseLayout -- the new case exists at the declared path
  and its case directory contains that one member file only, matching the
  layout of the pre-existing valid-irreversible-assumption-blocking case.
- AC-2: TestNewFixtureDeclaresReversibleTrue -- the packet's assumption
  statement describes a preserved constraint pinned by an existing test,
  `reversible` is `true`, and `related_question_ids` names a blocking
  question present in the same packet.
- AC-3: TestNewFixtureAcceptedDirectly -- the validator exits 0 when run
  against the new fixture directly.
- AC-4: TestQuestionPacketFixtureSweep -- every case under the
  `question-packet` fixture kind (the new one included) is run through the
  validator and matches the exit code its directory name declares.
- AC-5: TestExistingIrreversibleFixtureUnaffected -- the pre-existing
  `valid-irreversible-assumption-blocking` fixture is byte-for-byte
  unmodified (pinned by digest), still declares `reversible: false`, and is
  still accepted.
- AC-6: this module -- standard-library imports only; every assertion here
  reads only files this task creates plus files that already exist on the
  base branch, so it is green in a worktree holding only this task's change
  (IMPLEMENTATION.md C4).

The validator is invoked as an external subprocess in every case (json,
subprocess, pathlib, unittest -- standard library only). It is never
imported as a module, and nothing is imported from tests/test_validate_
worker_output.py (a pre-existing, unedited sibling module, IMPLEMENTATION.md
C6) -- the fixture sweep here is this module's own, independent walk of the
`question-packet` fixture kind, not a delegation to that module's.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
QUESTION_PACKET_FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures" / "question-packet"
CATEGORY_FAIL_CLOSED_ROOT = QUESTION_PACKET_FIXTURES_ROOT / "category-fail-closed"

NEW_CASE_DIR = CATEGORY_FAIL_CLOSED_ROOT / "valid-test-pinned-constraint-assumption"
SIBLING_CASE_DIR = CATEGORY_FAIL_CLOSED_ROOT / "valid-irreversible-assumption-blocking"

# Byte-for-byte pin of the pre-existing sibling fixture (AC-5): this is the
# sha256 of its input.json as it exists on the base branch. Any edit to that
# file -- by this task or by anything merged alongside it -- changes this
# digest and fails the test, which is the point (Out of Scope: this task
# never edits that fixture; it is read-only reference material).
SIBLING_INPUT_SHA256 = "67e904f72f6fbcd5eff3b2b55b6f0bd2205b81dced70571d10260ffa8453beff"

# The question-packet kind's own fixed vocabulary of worker names is not
# imported here (AC-6: standard-library imports only) -- any name from it
# works for --worker, since validate_question_packet() never cross-checks
# the CLI --worker argument against the packet's own "worker" field.
A_VALID_WORKER = "implementation-planner"


def run_validator(input_path):
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--kind", "question-packet",
        "--worker", A_VALID_WORKER,
        "--input", str(input_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def load_fixture(case_dir):
    return json.loads((case_dir / "input.json").read_text(encoding="utf-8"))


def assumption_declares_reversible_on_blocking_question(data, *, reversible):
    """True iff `data["assumptions"]` contains an entry whose `reversible`
    flag is exactly `reversible` (bool identity, not truthiness) and whose
    `related_question_ids` names a question present in `data["questions"]`
    with `blocking: true`."""
    blocking_question_ids = {
        q.get("question_id") for q in data.get("questions") or [] if q.get("blocking") is True
    }
    for a in data.get("assumptions") or []:
        if a.get("reversible") is reversible and blocking_question_ids & set(
            a.get("related_question_ids") or []
        ):
            return True
    return False


def discover_question_packet_cases():
    """Yields (group, case_dir) for every leaf case directory under the
    question-packet fixture kind -- a self-contained walk (no manifest, no
    dependency on the pre-existing corpus-sweep test module), mirroring the
    directory-name convention (`valid-*` / `invalid-*`) the whole fixture
    corpus already follows."""
    for group_dir in sorted(QUESTION_PACKET_FIXTURES_ROOT.iterdir()):
        if not group_dir.is_dir():
            continue
        for case_dir in sorted(group_dir.iterdir()):
            if case_dir.is_dir():
                yield group_dir.name, case_dir


def expected_exit_code(case_dir):
    if case_dir.name.startswith("valid-"):
        return 0
    if case_dir.name.startswith("invalid-"):
        return 1
    raise AssertionError(f"fixture case dir {case_dir} must start with valid- or invalid-")


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

class TestNewFixtureCaseLayout(unittest.TestCase):
    def test_new_case_directory_exists(self):
        self.assertTrue(NEW_CASE_DIR.is_dir(), f"expected {NEW_CASE_DIR} to be a directory")

    def test_case_directory_contains_exactly_one_member_file(self):
        members = sorted(p.name for p in NEW_CASE_DIR.iterdir())
        self.assertEqual(members, ["input.json"])

    def test_layout_matches_the_sibling_case(self):
        sibling_members = sorted(p.name for p in SIBLING_CASE_DIR.iterdir())
        new_members = sorted(p.name for p in NEW_CASE_DIR.iterdir())
        self.assertEqual(new_members, sibling_members)


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------

class TestNewFixtureDeclaresReversibleTrue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_fixture(NEW_CASE_DIR)

    def test_assumption_statement_describes_a_test_pinned_preserved_constraint(self):
        assumptions = self.data.get("assumptions") or []
        self.assertTrue(assumptions, "fixture must declare an assumptions[] entry")
        statement = assumptions[0].get("statement") or ""
        self.assertIn("preserved constraint", statement)
        self.assertIn("pinned by an existing test", statement)

    def test_assumption_declares_reversible_true_on_a_blocking_question(self):
        self.assertTrue(
            assumption_declares_reversible_on_blocking_question(self.data, reversible=True),
            "fixture must carry an assumptions[] entry naming a blocking question "
            "in this packet with reversible: true",
        )

    def test_helper_rejects_the_same_fixture_mutated_to_reversible_false(self):
        # Test Notes edge case: the assertion helper must actually
        # discriminate true from false -- prove it by mutating a copy of the
        # parsed structure in memory (never the fixture file itself) and
        # checking the helper now rejects it.
        mutated = json.loads(json.dumps(self.data))
        mutated["assumptions"][0]["reversible"] = False
        self.assertFalse(
            assumption_declares_reversible_on_blocking_question(mutated, reversible=True)
        )
        # And the mutated copy now satisfies the reversible=False shape --
        # confirming the mutation actually took effect rather than the
        # helper being vacuously false for unrelated reasons.
        self.assertTrue(
            assumption_declares_reversible_on_blocking_question(mutated, reversible=False)
        )


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------

class TestNewFixtureAcceptedDirectly(unittest.TestCase):
    def test_validator_exits_0_against_the_new_fixture(self):
        result = run_validator(NEW_CASE_DIR / "input.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------

class TestQuestionPacketFixtureSweep(unittest.TestCase):
    def test_every_question_packet_fixture_matches_its_declared_exit_code(self):
        cases = list(discover_question_packet_cases())
        self.assertTrue(cases, "expected the question-packet fixture corpus to be non-empty")
        for group, case_dir in cases:
            with self.subTest(group=group, case=case_dir.name):
                expected = expected_exit_code(case_dir)
                result = run_validator(case_dir / "input.json")
                self.assertEqual(
                    result.returncode,
                    expected,
                    f"{case_dir}: expected exit {expected}, got {result.returncode}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
                )

    def test_the_new_case_is_present_in_the_sweep(self):
        cases = {case_dir.name for _, case_dir in discover_question_packet_cases()}
        self.assertIn(NEW_CASE_DIR.name, cases)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------

class TestExistingIrreversibleFixtureUnaffected(unittest.TestCase):
    def test_fixture_bytes_are_unmodified(self):
        import hashlib

        digest = hashlib.sha256((SIBLING_CASE_DIR / "input.json").read_bytes()).hexdigest()
        self.assertEqual(digest, SIBLING_INPUT_SHA256)

    def test_fixture_still_declares_reversible_false_on_a_blocking_question(self):
        data = load_fixture(SIBLING_CASE_DIR)
        self.assertTrue(
            assumption_declares_reversible_on_blocking_question(data, reversible=False)
        )

    def test_fixture_is_still_accepted(self):
        result = run_validator(SIBLING_CASE_DIR / "input.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

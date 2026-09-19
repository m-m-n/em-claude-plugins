"""Tests for task0005 (batch-structured-result-output): the audit-item
containment guard (TS9) pinning FR17/D7 -- every "## Reporting" audit item
must be carried IN FULL inside a structured-result value, never by a count
or a pointer alone, and this feature writes no new aggregated report
artifact. Per IMPLEMENTATION.md D5, this module declares SC7's item list
independently as its own expectation set and never reads `batch-mode.md`;
task0002 owns the binding assertion that batch-mode.md's own "## Reporting"
section carries this same assignment (Out of Scope).

Covers task0005 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0005.md):

- AC-6: `TestItemListSize` asserts the item list has SC7's stated member
  count (seven `detail` items). `TestContainmentCheckerAcceptsFullContent`
  proves the checker accepts a full-content sample.
  `TestContainmentCheckerRejectsCountSubstitution`,
  `TestContainmentCheckerRejectsPointerOnlySubstitution` and
  `TestContainmentCheckerRejectsMisplacedStopRecovery` each independently
  prove a rejection, every one paired with a non-vacuity guard confirming
  the forged sample is otherwise well-formed.
- AC-7: `TestNoAggregatedReportArtifactInTaskFiles` asserts no aggregated
  report artifact path appears among this feature's task `files` entries
  in `workflow.yaml`, read by indentation-based text scanning (no YAML
  parser -- D6 grants the parser exception to task0004's modules only).
  `TestModuleIsStdlibOnly` covers this module's own half of the
  discoverability/stdlib-only requirement; the sibling module,
  test_structured_result_derivation.py, covers its own half.

TDD order (Test Notes): this module first existed with `containment_checker`
and `_task_files_entries` stubbed to wrong/placeholder values, confirmed red
against every case below, then implemented to green -- see this task's test
record.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_YAML_PATH = (
    REPO_ROOT / "feature-docs" / "batch-structured-result-output" / "workflow.yaml"
)

# --- SC7's audit-item assignment, declared independently here (D5): the
# seven items `detail` must carry in full, each written as illustrative
# full-content text a real emission might produce. The exact wording is
# this module's own fixture, not a copy of batch-mode.md's -- task0002
# owns that binding assertion.
AUDIT_ITEMS = [
    "Auto-approved commands: `npm test`, `npm run build`, `git status`.",
    "Assumptions recorded: the target environment already has Node 20 "
    "installed; the feature flag defaults to off.",
    "Auto-rework rounds consumed: review 1, verify 0.",
    "Deferred findings: `a1b2c3d4e5f6a7b8` (medium, needs a follow-up "
    "ticket before merge).",
    "Unlisted-gate fallback: the `custom-lint` gate was not in the policy "
    "table; resolved to require review under the fail-closed default.",
    "Autonomous fail-closed-route resolution: the ambiguous merge conflict "
    "was resolved by adopting the parent side per the documented "
    "protocol.",
    "Kept branch: `em-workflow/example-feature/integration`. Take-over "
    "guidance: resume with `/em-workflow:develop` targeting this branch; "
    "the worktree was removed but the branch and its commits remain.",
]

STOP_RECOVERY_GUIDANCE = (
    "Resume by re-running `/em-workflow:develop --batch` once the "
    "blocking condition above is resolved; the integration branch above "
    "still holds every completed task's work."
)


def _detail_carries_every_item_in_full(detail_text):
    return all(item in detail_text for item in AUDIT_ITEMS)


def _resume_conditions_carries_stop_recovery_in_full(resume_conditions_text):
    return STOP_RECOVERY_GUIDANCE in resume_conditions_text


def containment_checker(detail_text, resume_conditions_text, state):
    """TS9's checker: True iff every SC7 audit item is present in full in
    `detail_text`, and -- only when `state` is 'stopped' -- the
    stop-recovery guidance is present in full in `resume_conditions_text`.
    The stop-recovery guidance's presence inside `detail_text` never
    substitutes for its presence in `resume_conditions_text`: SC7's
    per-value assignment is checked positionally (the right field), never
    by scanning the union of both fields."""
    if not _detail_carries_every_item_in_full(detail_text):
        return False
    if state == "stopped":
        return _resume_conditions_carries_stop_recovery_in_full(
            resume_conditions_text
        )
    return True


def _assemble_detail(items):
    return "\n".join(items)


FULL_DETAIL_SAMPLE = _assemble_detail(AUDIT_ITEMS)


class TestItemListSize(unittest.TestCase):
    """AC-6: the item list has SC7's stated member count -- a silently
    dropped item fails here."""

    def test_seven_detail_items(self):
        self.assertEqual(len(AUDIT_ITEMS), 7)


class TestContainmentCheckerAcceptsFullContent(unittest.TestCase):
    """AC-6: the containment checker accepts a full-content sample."""

    def test_accepts_full_content_when_stopped(self):
        self.assertTrue(
            containment_checker(
                FULL_DETAIL_SAMPLE, STOP_RECOVERY_GUIDANCE, "stopped"
            )
        )

    def test_accepts_detail_only_content_when_not_stopped(self):
        # FR12: resume_conditions carries content only when state is
        # stopped; an empty resume_conditions must not fail the check for
        # completed/phase_done.
        self.assertTrue(containment_checker(FULL_DETAIL_SAMPLE, "", "completed"))
        self.assertTrue(containment_checker(FULL_DETAIL_SAMPLE, "", "phase_done"))


class TestContainmentCheckerRejectsCountSubstitution(unittest.TestCase):
    """AC-6: rejects a sample in which a single item is replaced by a
    count ('3 commands auto-approved')."""

    def _forged_sample(self):
        substituted = list(AUDIT_ITEMS)
        substituted[0] = "3 commands auto-approved."
        return substituted, _assemble_detail(substituted)

    def test_rejects_count_substituted_item(self):
        _, sample = self._forged_sample()
        self.assertFalse(
            containment_checker(sample, STOP_RECOVERY_GUIDANCE, "stopped")
        )

    def test_forged_sample_is_otherwise_well_formed(self):
        # Non-vacuity: every OTHER item is present in full; only the
        # substituted one is missing.
        _, sample = self._forged_sample()
        for item in AUDIT_ITEMS[1:]:
            self.assertIn(item, sample)
        self.assertNotIn(AUDIT_ITEMS[0], sample)


class TestContainmentCheckerRejectsPointerOnlySubstitution(unittest.TestCase):
    """AC-6: rejects a sample in which a single item is replaced by a
    pointer alone (a path or an id with no content). Test Notes edge case:
    the pointer-only text still contains the item's id substring, so the
    rejection must key on the absence of the FULL content, not on the
    presence of that substring."""

    POINTER_ONLY = "Deferred findings: see `a1b2c3d4e5f6a7b8`."

    def _forged_sample(self):
        substituted = list(AUDIT_ITEMS)
        substituted[3] = self.POINTER_ONLY
        return substituted, _assemble_detail(substituted)

    def test_pointer_still_carries_the_stable_id_substring(self):
        _, sample = self._forged_sample()
        self.assertIn("a1b2c3d4e5f6a7b8", sample)

    def test_rejects_pointer_only_item(self):
        _, sample = self._forged_sample()
        self.assertFalse(
            containment_checker(sample, STOP_RECOVERY_GUIDANCE, "stopped")
        )

    def test_forged_sample_is_otherwise_well_formed(self):
        _, sample = self._forged_sample()
        for item in AUDIT_ITEMS[:3] + AUDIT_ITEMS[4:]:
            self.assertIn(item, sample)
        self.assertNotIn(AUDIT_ITEMS[3], sample)


class TestContainmentCheckerRejectsMisplacedStopRecovery(unittest.TestCase):
    """AC-6: rejects a sample in which the stop-recovery guidance sits in
    `detail` instead of `resume_conditions`."""

    def _forged_detail(self):
        return FULL_DETAIL_SAMPLE + "\n" + STOP_RECOVERY_GUIDANCE

    def test_rejects_guidance_misplaced_in_detail(self):
        misplaced_detail = self._forged_detail()
        self.assertFalse(containment_checker(misplaced_detail, "", "stopped"))

    def test_forged_sample_is_otherwise_well_formed(self):
        misplaced_detail = self._forged_detail()
        # Every detail item is still present in full...
        self.assertTrue(_detail_carries_every_item_in_full(misplaced_detail))
        # ...and the guidance text does appear SOMEWHERE in the combined
        # text -- proving the rejection is positional (right content,
        # wrong field), not a plain textual absence.
        self.assertIn(STOP_RECOVERY_GUIDANCE, misplaced_detail)


# ---------------------------------------------------------------------------
# AC-7: no new aggregated report artifact among this feature's declared
# `files` entries -- text-scanned from workflow.yaml (no YAML parser,
# matching the repository's stdlib-only convention; D6 grants the parser
# exception to task0004's modules only).
# ---------------------------------------------------------------------------

# This feature's own declared non-test change set (SPEC.md's File
# Structure / Declared Change Set section): three reference SSOT
# documents, one skill document and two version manifests. Anything else
# showing up as a non-test `files` entry would be a new artifact this
# feature never declared -- including a new aggregated report path (FR17).
KNOWN_NON_TEST_FILES = {
    "em-workflow/references/batch-terminal-line.md",
    "em-workflow/references/batch-mode.md",
    "em-workflow/references/implement-phase.md",
    "em-workflow/skills/develop/SKILL.md",
    "em-workflow/.claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
}


def _task_files_entries(workflow_yaml_text):
    """Collects every path listed under each task's `files:` key, by
    indentation-based text scanning -- no YAML parser (Test Notes)."""
    entries = []
    lines = workflow_yaml_text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "files:":
            i += 1
            while i < len(lines) and re.match(r"^\s*-\s+\S", lines[i]):
                entries.append(lines[i].split("-", 1)[1].strip())
                i += 1
            continue
        i += 1
    return entries


def _is_test_module_path(path):
    return path.startswith("tests/") and path.endswith(".py")


def _offenders(entries):
    return [
        e for e in entries if not _is_test_module_path(e) and e not in KNOWN_NON_TEST_FILES
    ]


class TestNoAggregatedReportArtifactInTaskFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_YAML_PATH.read_text(encoding="utf-8")
        cls.entries = _task_files_entries(cls.text)

    def test_scan_is_non_vacuous(self):
        self.assertTrue(self.entries)
        self.assertIn(
            "em-workflow/references/batch-terminal-line.md", self.entries
        )

    def test_no_unexpected_non_test_file_in_the_declared_change_set(self):
        offenders = _offenders(self.entries)
        self.assertEqual(offenders, [], f"unexpected non-test file(s): {offenders}")


class TestTaskFilesScannerNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_task_files_entries` / the
    offender filter, over a synthetic sample."""

    def test_scanner_extracts_a_synthetic_report_artifact_entry(self):
        sample = (
            "tasks:\n"
            "  taskX:\n"
            "    files:\n"
            "    - em-workflow/references/batch-terminal-line.md\n"
            "    - feature-docs/{feature}/audit-report.md\n"
            "    skills: []\n"
        )
        entries = _task_files_entries(sample)
        self.assertEqual(
            entries,
            [
                "em-workflow/references/batch-terminal-line.md",
                "feature-docs/{feature}/audit-report.md",
            ],
        )
        self.assertEqual(
            _offenders(entries), ["feature-docs/{feature}/audit-report.md"]
        )

    def test_scanner_finds_nothing_offending_in_a_clean_sample(self):
        sample = (
            "tasks:\n"
            "  taskX:\n"
            "    files:\n"
            "    - tests/test_example.py\n"
            "    skills: []\n"
        )
        entries = _task_files_entries(sample)
        self.assertEqual(_offenders(entries), [])


class TestModuleIsStdlibOnly(unittest.TestCase):
    """AC-7 (this module's own half)."""

    def test_module_filename(self):
        self.assertEqual(
            Path(__file__).name, "test_structured_result_reporting_containment.py"
        )

    def test_only_imports_standard_library_modules(self):
        own_source = Path(__file__).read_text(encoding="utf-8")
        allowed_top_level_modules = {"re", "unittest", "pathlib"}
        imported = set(
            re.findall(
                r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                own_source,
                re.MULTILINE,
            )
        )
        offenders = imported - allowed_top_level_modules
        self.assertEqual(offenders, set(), f"non-stdlib import(s): {offenders}")


if __name__ == "__main__":
    unittest.main()

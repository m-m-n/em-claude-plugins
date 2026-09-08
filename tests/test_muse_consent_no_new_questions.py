"""Tests for task0005: pin the interactive-question budget of the develop
and review paths.

Covers task0005 Acceptance Criteria
(feature-docs/muse-spark-contributor-consent/tasks/task0005.md):

- AC-1: the develop-path and review-path documents of both plugins are
  enumerated by walking their document directories (`references/` and
  `skills/`), so no such document is outside the measurement.
- AC-2: the baseline is a literal table of per-file counts in this module,
  taken by reading the base revision; no assertion derives its expected
  value from the same tree it checks.
- AC-3: the comparison fails when a measured file's count exceeds its
  pinned value, and fails when a file outside the table has a nonzero
  count; it passes when counts are unchanged or lower. Both directions are
  demonstrated on synthetic counts, independent of the real tree.
- AC-4: the two `contributor-consent` skill documents are the only
  excluded files, named explicitly here rather than matched by a pattern.
- AC-5: standard-library only, runs under
  `python3 -m unittest discover -s tests`.

This is the automated static equivalent of "run develop in a project that
has not consented and observe that no new question appears" -- the
property being checked belongs to the documents that drive develop and
review, not to a live run of either (task0005.md Design). A red result
means some document on the develop or review path gained an occurrence of
the interactive-question tool name; the baseline is never raised to make
that pass.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The interactive-question tool whose occurrences this module budgets.
TOOL_NAME = "AskUserQuestion"

PLUGINS = ("em-workflow", "em-review")
PLUGIN_DOC_DIRS = ("references", "skills")

# AC-4: the only two files excluded from the "zero outside the table" rule.
# Each is the out-of-band contributor-consent skill: it legitimately asks
# exactly one question, and it is reachable only when a user runs it in an
# interactive session. Named explicitly, not matched by a pattern. Per
# task0005.md Test Notes, these documents may not exist yet in a given
# worktree -- their absence is acceptable and their presence is excluded.
EXCLUDED_FILES = frozenset(
    {
        "em-workflow/skills/contributor-consent/SKILL.md",
        "em-review/skills/contributor-consent/SKILL.md",
    }
)

# AC-2: the literal baseline, read from the base revision (the tree before
# this feature's implementation tasks landed) rather than recomputed here.
# Every file below is one that currently contains at least one occurrence
# of TOOL_NAME under either plugin's references/ or skills/ directory.
BASELINE_COUNTS = {
    "em-review/references/review-phase.md": 4,
    "em-review/skills/multi-review/SKILL.md": 1,
    "em-workflow/references/batch-mode.md": 8,
    "em-workflow/references/command-execution-protocol.md": 8,
    "em-workflow/references/contracts/analyst-contract.md": 2,
    "em-workflow/references/contracts/planner-contract.md": 1,
    "em-workflow/references/contracts/rework-planner-contract.md": 1,
    "em-workflow/references/gen-license.md": 5,
    "em-workflow/references/implement-phase.md": 4,
    "em-workflow/references/phases/create-spec-phase.md": 3,
    "em-workflow/references/phase-state.md": 1,
    "em-workflow/references/question-packet-schema.md": 4,
    "em-workflow/references/question-resolution.md": 2,
    "em-workflow/references/review-phase.md": 9,
    "em-workflow/skills/design/SKILL.md": 2,
    "em-workflow/skills/develop/SKILL.md": 7,
    "em-workflow/skills/gen-license/SKILL.md": 1,
    "em-workflow/skills/retrospect/SKILL.md": 2,
    "em-workflow/skills/review/SKILL.md": 1,
    "em-workflow/skills/worktree-task-workflow/SKILL.md": 1,
}


def iter_document_files():
    """AC-1: enumerate develop-path and review-path documents of both
    plugins by walking their document directories, rather than
    hand-listing paths -- so a document added later cannot slip out of the
    measurement.

    Returns a sorted list of relative POSIX-style path strings (relative to
    REPO_ROOT), one per regular file found under each plugin's
    `references/` and `skills/` directories.
    """
    paths = []
    for plugin in PLUGINS:
        for doc_dir in PLUGIN_DOC_DIRS:
            base = REPO_ROOT / plugin / doc_dir
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    paths.append(path.relative_to(REPO_ROOT).as_posix())
    return sorted(paths)


def count_occurrences(rel_path):
    """Count plain substring occurrences of TOOL_NAME in a document's text.

    A document mentioning the tool name in prose still counts -- the
    conservative direction (task0005.md Test Notes).
    """
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
    return text.count(TOOL_NAME)


def find_budget_violations(measured, baseline, excluded=frozenset()):
    """AC-3: the comparison helper the whole module relies on.

    `measured` and `baseline` are ``{relative_path: count}`` mappings.
    Returns a sorted list of the relative paths that violate the budget:

    - a path present in `baseline` whose measured count exceeds the pinned
      value, or
    - a path absent from `baseline` (and not in `excluded`) whose measured
      count is nonzero.

    A path in `excluded` never violates, regardless of its count or table
    membership. A path with a zero measured count that has no baseline
    entry is fine (removal elsewhere does not turn the test red).
    """
    violations = []
    for path, count in measured.items():
        if path in excluded:
            continue
        pinned = baseline.get(path)
        if pinned is None:
            if count > 0:
                violations.append(path)
        elif count > pinned:
            violations.append(path)
    return sorted(violations)


class TestDocumentEnumeration(unittest.TestCase):
    """AC-1."""

    def test_walks_only_references_and_skills_of_both_plugins(self):
        paths = iter_document_files()
        self.assertTrue(
            paths, "expected at least one document under references/ or skills/"
        )
        for rel in paths:
            parts = Path(rel).parts
            self.assertIn(parts[0], PLUGINS)
            self.assertIn(parts[1], PLUGIN_DOC_DIRS)

    def test_known_develop_and_review_documents_are_included(self):
        paths = set(iter_document_files())
        for expected in (
            "em-workflow/skills/develop/SKILL.md",
            "em-workflow/skills/review/SKILL.md",
            "em-workflow/references/review-phase.md",
            "em-review/references/review-phase.md",
            "em-review/skills/multi-review/SKILL.md",
        ):
            self.assertIn(expected, paths)


class TestBaselineIsLiteral(unittest.TestCase):
    """AC-2: the baseline table is a plain literal of positive ints, not a
    value derived from the working tree at test-collection time."""

    def test_baseline_is_a_plain_positive_int_literal_table(self):
        self.assertIsInstance(BASELINE_COUNTS, dict)
        self.assertTrue(BASELINE_COUNTS)
        for path, count in BASELINE_COUNTS.items():
            self.assertIsInstance(path, str)
            self.assertIsInstance(count, int)
            self.assertGreater(count, 0)

    def test_baseline_and_excluded_files_are_disjoint(self):
        self.assertTrue(BASELINE_COUNTS.keys().isdisjoint(EXCLUDED_FILES))


class TestBudgetComparisonHelper(unittest.TestCase):
    """AC-3, demonstrated on synthetic counts so a bug in the helper cannot
    make the whole suite vacuously green."""

    def test_passes_when_measured_equals_baseline(self):
        measured = {"a": 3, "b": 1}
        baseline = {"a": 3, "b": 1}
        self.assertEqual(find_budget_violations(measured, baseline), [])

    def test_passes_when_measured_is_lower_than_baseline(self):
        measured = {"a": 1}
        baseline = {"a": 3}
        self.assertEqual(find_budget_violations(measured, baseline), [])

    def test_fails_when_measured_exceeds_baseline(self):
        measured = {"a": 4}
        baseline = {"a": 3}
        self.assertEqual(find_budget_violations(measured, baseline), ["a"])

    def test_fails_when_a_file_outside_the_table_has_an_occurrence(self):
        measured = {"a": 3, "new-doc.md": 1}
        baseline = {"a": 3}
        self.assertEqual(
            find_budget_violations(measured, baseline), ["new-doc.md"]
        )

    def test_passes_when_a_file_outside_the_table_has_zero_occurrences(self):
        measured = {"a": 3, "unrelated.md": 0}
        baseline = {"a": 3}
        self.assertEqual(find_budget_violations(measured, baseline), [])

    def test_excluded_file_never_violates_even_when_uncounted_and_present(self):
        excluded_path = "em-workflow/skills/contributor-consent/SKILL.md"
        measured = {"a": 3, excluded_path: 1}
        baseline = {"a": 3}
        excluded = frozenset({excluded_path})
        self.assertEqual(
            find_budget_violations(measured, baseline, excluded), []
        )

    def test_removal_of_an_unrelated_occurrence_does_not_turn_the_test_red(self):
        # A file's count dropping below its pinned value (e.g. an
        # unrelated edit removed a question) must never be flagged.
        measured = {"a": 0}
        baseline = {"a": 5}
        self.assertEqual(find_budget_violations(measured, baseline), [])


class TestInteractiveQuestionBudgetIsNotExceeded(unittest.TestCase):
    """AC-3 applied to the real tree, AC-4 exclusion applied. This is the
    module's actual gate: a red result here means a develop-path or
    review-path document gained an interactive question."""

    def test_no_develop_or_review_document_exceeds_its_pinned_budget(self):
        measured = {rel: count_occurrences(rel) for rel in iter_document_files()}
        violations = find_budget_violations(measured, BASELINE_COUNTS, EXCLUDED_FILES)
        self.assertEqual(
            violations,
            [],
            "interactive-question budget exceeded in: " + ", ".join(violations),
        )


class TestExcludedFilesAreExactlyTheContributorConsentSkillDocs(unittest.TestCase):
    """AC-4."""

    def test_excluded_set_is_exactly_the_two_contributor_consent_skill_docs(self):
        self.assertEqual(
            EXCLUDED_FILES,
            frozenset(
                {
                    "em-workflow/skills/contributor-consent/SKILL.md",
                    "em-review/skills/contributor-consent/SKILL.md",
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()

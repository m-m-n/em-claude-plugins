"""Tests for task0003 (sca-per-project-scan-binding): Phase R2's axis-2 text
states that partial coverage also spans several projects within one
ecosystem, by appending only.

Covers task0003 Acceptance Criteria
(feature-docs/sca-per-project-scan-binding/tasks/task0003.md):

- AC-1: in Phase R2 (from "## Phase R2: Fan-out" up to "## Phase R2b:
  Cross-model fallback"), whitespace-normalized, a passage located after the
  existing partial-coverage paragraph states that (1) changed manifests /
  lockfiles in several project directories of one selected ecosystem are
  scanned as separate projects, each in its own directory, (2) a project
  that did not complete -- including one that cannot be bound to its
  directory, reported with the path-free reason
  `<ecosystem>_project_unbindable` -- makes the axis-2 row skipped with
  `skip_reason` carrying the combined machine-stable reasons, each reason
  once, and (3) the findings of the projects that did complete still enter
  Phase R3a's evaluator input unchanged; it contains "partial coverage" and
  names `<ecosystem>_project_unbindable`.
- AC-2: the existing paragraph from "A skipped axis-2 run also covers
  partial coverage across several selected" through "unchanged." is present
  byte-for-byte (line breaks included), exactly once, and the phrases
  tests/test_sca_scan_execution.py pins for Phase R2 are still present. The
  phrases tests/test_sca_axis_review_phase_r0_r3.py pins for Phase R2 are
  asserted by that module, which runs in the same suite.
- AC-3: this module imports only standard-library modules (asserted below);
  `python3 -m unittest discover -s tests` and
  `python3 em-workflow/scripts/check-plugin-invariants.py .` both exit 0 --
  verified by actually running both commands (recorded in the implementer
  report); a suite cannot assert its own full-suite outcome.

That the file diff holds only added lines is checked at verification time
against the feature's base commit (a unit test cannot see the base
revision); AC-2's exact-paragraph assertion is the part of that invariant a
unit test can pin.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"

R2_HEADING = "## Phase R2: Fan-out"
R2B_HEADING = "## Phase R2b: Cross-model fallback"
CONTRIBUTOR_HEADING = "### Contributor-tier pre-dispatch criteria"

# The pre-existing paragraph, exactly as it stands in review-phase.md
# (line breaks included). It must stay untouched: not reworded, not
# re-wrapped.
EXISTING_PARAGRAPH = (
    "A skipped axis-2 run also covers partial coverage across several selected\n"
    "ecosystems: when any one of them did not complete, the row's `skip_reason`\n"
    "carries the combined machine-stable reasons, and the findings the other\n"
    "selected ecosystems did produce still enter Phase R3a's evaluator input\n"
    "unchanged."
)
EXISTING_FINAL_SENTENCE = "evaluator input unchanged."


def _norm(text):
    return re.sub(r"\s+", " ", text)


class _R2Fixture:
    """Reads review-phase.md once and slices Phase R2 on its literal
    headings."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = REVIEW_PHASE_PATH.read_text(encoding="utf-8")
        return cls._text

    @classmethod
    def r2(cls):
        text = cls.text()
        start = text.index(R2_HEADING)
        end = text.index(R2B_HEADING)
        return text[start:end]

    @classmethod
    def appended_passage(cls):
        """Normalized text between the existing paragraph's end and the
        Contributor-tier heading: the place the appended passage lives."""
        r2 = cls.r2()
        after_existing = r2[r2.index(EXISTING_PARAGRAPH) + len(EXISTING_PARAGRAPH):]
        return _norm(after_existing[: after_existing.index(CONTRIBUTOR_HEADING)])


# ---------------------------------------------------------------------------
# AC-1: the appended passage states facts 1-3 and uses the term.
# ---------------------------------------------------------------------------


class TestAC1AppendedPassageStatesMultiProjectCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = _norm(_R2Fixture.r2())
        cls.passage = _R2Fixture.appended_passage()

    def test_ac1_passage_sits_after_the_existing_paragraph_inside_r2(self):
        # The passage's key phrase comes after the existing paragraph's final
        # sentence and before the Contributor-tier heading, all inside R2.
        final_pos = self.norm.index(EXISTING_FINAL_SENTENCE)
        key_pos = self.norm.index("`<ecosystem>_project_unbindable`")
        heading_pos = self.norm.index(CONTRIBUTOR_HEADING)
        self.assertGreater(key_pos, final_pos)
        self.assertLess(key_pos, heading_pos)
        self.assertTrue(self.passage.strip())

    def test_ac1_passage_uses_the_term_partial_coverage(self):
        self.assertIn("partial coverage", self.passage)

    def test_ac1_fact1_several_project_directories_scanned_as_separate_projects(self):
        self.assertIn("one selected ecosystem", self.passage)
        self.assertIn("several project directories", self.passage)
        self.assertIn("manifests or lockfiles", self.passage)
        self.assertIn("separate project", self.passage)
        self.assertIn("its own directory", self.passage)

    def test_ac1_fact2_unfinished_project_makes_the_row_skipped(self):
        self.assertIn("did not complete", self.passage)
        self.assertIn("cannot be bound to its directory", self.passage)
        self.assertIn("path-free reason `<ecosystem>_project_unbindable`", self.passage)
        self.assertIn("skipped", self.passage)

    def test_ac1_fact2_skip_reason_carries_combined_reasons_each_once(self):
        self.assertIn("`skip_reason`", self.passage)
        self.assertIn("combined machine-stable reasons", self.passage)
        self.assertIn("each reason once", self.passage)

    def test_ac1_fact3_completed_projects_findings_still_enter_r3a_unchanged(self):
        self.assertIn("findings of the projects that did complete", self.passage)
        self.assertIn("Phase R3a's evaluator input", self.passage)
        self.assertIn("unchanged", self.passage)

    def test_ac1_passage_does_not_restate_scanner_rules_in_detail(self):
        # Design: the passage states only the four facts; scan-dependencies.py
        # rules (anchors, path checks) are not restated.
        for word in ("anchor", "symlink", "realpath", "resolve"):
            self.assertNotIn(word, self.passage.lower())


# ---------------------------------------------------------------------------
# AC-2: the pre-existing text is preserved.
# ---------------------------------------------------------------------------


class TestAC2ExistingTextPreserved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _R2Fixture.text()
        cls.r2 = _R2Fixture.r2()
        cls.norm = _norm(cls.r2)

    def test_ac2_existing_paragraph_present_byte_for_byte_inside_r2(self):
        self.assertIn(EXISTING_PARAGRAPH, self.r2)

    def test_ac2_existing_paragraph_occurs_exactly_once(self):
        self.assertEqual(self.text.count(EXISTING_PARAGRAPH), 1)

    def test_ac2_existing_paragraph_start_is_a_paragraph_start(self):
        start = self.r2.index(EXISTING_PARAGRAPH)
        self.assertEqual(self.r2[start - 2:start], "\n\n")

    def test_ac2_phrases_pinned_by_scan_execution_tests_still_present(self):
        # tests/test_sca_scan_execution.py,
        # TestReviewPhasePartialCoverageStatement.
        for phrase in (
            "partial coverage",
            "skip_reason",
            "combined",
            "findings",
            "recorded exactly as this",
            "ordinary skip",
            "never as a retryable chain-walk `skip_reason`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.norm)
        self.assertIn("evaluator", self.norm.lower())

    def test_ac2_contributor_tier_section_still_follows_inside_r2(self):
        self.assertIn(CONTRIBUTOR_HEADING, self.r2)
        self.assertLess(
            self.r2.index(EXISTING_PARAGRAPH), self.r2.index(CONTRIBUTOR_HEADING)
        )


# ---------------------------------------------------------------------------
# AC-3 (standard-library-only side): this module's imports.
# ---------------------------------------------------------------------------


class TestAC3OwnModuleStdlibOnly(unittest.TestCase):
    def test_ac3_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()

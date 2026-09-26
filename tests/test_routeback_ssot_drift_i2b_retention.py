"""Tests for task0002 (routeback-ssot-drift): pins the I.2.b step 1
third-case Residual outcome in
`em-workflow/references/implement-phase.md` so a later edit cannot drop
it silently
(feature-docs/routeback-ssot-drift/tasks/task0002.md).

`implement-phase.md` is read-only for this task
(feature-docs/routeback-ssot-drift/IMPLEMENTATION.md D2): the pinned text
already exists at the task's base commit, so every retention assertion
below passes on its first run -- the red step for each is its own
non-vacuity proof (the same matcher observed failing on a copy of the
section with the pinned literal removed), not the presence assertion
itself. This task edits nothing under `em-workflow/` and creates only
this module.

Covers task0002 Acceptance Criteria:

- AC-1, AC-2 (FR6): dropped at the merge into main -- main's
  routeback-deferred-findings task0003 routed the partial-artifact state
  through the orphan-recovery proof chain, so the pinned Residual text no
  longer exists
- AC-3 (FR7): TestThirdCaseRetention.test_definition_present
- AC-4 (FR7): TestThirdCaseRetention.test_residual_treatment_present
- AC-5: every ``test_*_non_vacuity`` method below (one per pinned
  literal), plus TestI2bSectionSlicing (the slicer raises naming the
  missing heading rather than returning an empty-string match)
- AC-6 (NFR1): TestModuleUsesOnlyStandardLibrary covers "the new module
  uses only the standard library"; "python3 -m unittest discover -s
  tests exits 0 from the worktree root" and "the task's diff contains
  only the new module" are outcome-level facts verified by actually
  running the suite and by this task's own file-scope discipline (this
  module is the only file the task creates), not by an assertion inside
  this module.

Matcher -> negative-proof inventory (IMPLEMENTATION.md Conventions,
"Negative proofs"; every assertion below is a retention assertion --
text that already exists and must stay):

- THIRD_CASE_DEFINITION: TestThirdCaseRetention.test_definition_present /
  test_definition_non_vacuity
- THIRD_CASE_RESIDUAL_TREATMENT:
  TestThirdCaseRetention.test_residual_treatment_present /
  test_residual_treatment_non_vacuity
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENT_PHASE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "implement-phase.md"
)

I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"

# Pinned literals -- each copied verbatim from implement-phase.md at this
# task's base commit (D2: the file is read-only for this task) and
# defined once, referenced by name (IMPLEMENTATION.md Conventions,
# "Pinned literals"). Already whitespace-normalized (single spaces, no
# embedded newlines) to match what `_normalize_ws` produces from the
# section text, per this repository's existing convention
# (tests/test_implement_routeback_gate.py).

THIRD_CASE_DEFINITION = (
    'A third case exists alongside the two the previous paragraph defines: the '
    'Agent index lookup resolves to a candidate, but the harness stop tool stops '
    'nothing, or the stop-tool recorder does not append a terminal event for it.'
)

THIRD_CASE_RESIDUAL_TREATMENT = (
    'In that case the journal is unchanged exactly as it is in the '
    'unresolvable/ambiguous case, so this third case receives the same Residual '
    'treatment described next, not the failed handling above.'
)


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space (IMPLEMENTATION.md Conventions, "Text normalization")."""
    return re.sub(r"\s+", " ", text).strip()


def _read_phase_md():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _slice_section(text, start_heading, end_heading):
    """Slice `text` from `start_heading` up to (not including)
    `end_heading`. Raises, naming the missing heading, when either is
    absent -- never an empty-string match (task0002 Design)."""
    if start_heading not in text:
        raise AssertionError(f"missing heading: {start_heading!r}")
    start = text.index(start_heading)
    if end_heading not in text[start:]:
        raise AssertionError(f"missing heading: {end_heading!r}")
    end = text.index(end_heading, start)
    return text[start:end]


def _i2b_section(text):
    """The `### I.2.b: Wake phase` section, sliced from its heading up to
    the `### I.2.c: Failed handling` heading (IMPLEMENTATION.md Shared
    Components)."""
    return _slice_section(text, I2B_HEADING, I2C_HEADING)


class TestI2bSectionSlicing(unittest.TestCase):
    """AC-5: the slicer fails, naming the missing heading, when either
    boundary heading is absent -- never an empty-string match."""

    def test_missing_start_heading_raises_naming_it(self):
        text = _read_phase_md().replace(I2B_HEADING, "### I.2.zzz: Renamed")
        with self.assertRaises(AssertionError) as ctx:
            _i2b_section(text)
        self.assertIn(I2B_HEADING, str(ctx.exception))

    def test_missing_end_heading_raises_naming_it(self):
        text = _read_phase_md().replace(I2C_HEADING, "### I.2.zzz: Renamed")
        with self.assertRaises(AssertionError) as ctx:
            _i2b_section(text)
        self.assertIn(I2C_HEADING, str(ctx.exception))


class TestThirdCaseRetention(unittest.TestCase):
    """AC-3, AC-4 (FR7): the I.2.b section keeps the third-case definition
    (stop tool stops nothing, or the recorder appends no terminal event)
    and its Residual treatment (not the failed handling)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2b_section(_read_phase_md()))

    def test_definition_present(self):
        self.assertIn(THIRD_CASE_DEFINITION, self.section)

    def test_definition_non_vacuity(self):
        without_it = self.section.replace(THIRD_CASE_DEFINITION, "")
        self.assertNotIn(THIRD_CASE_DEFINITION, without_it)

    def test_residual_treatment_present(self):
        self.assertIn(THIRD_CASE_RESIDUAL_TREATMENT, self.section)

    def test_residual_treatment_non_vacuity(self):
        without_it = self.section.replace(THIRD_CASE_RESIDUAL_TREATMENT, "")
        self.assertNotIn(THIRD_CASE_RESIDUAL_TREATMENT, without_it)


class TestModuleUsesOnlyStandardLibrary(unittest.TestCase):
    """AC-6 (NFR1) partial: this module imports nothing beyond the
    standard library."""

    def test_only_stdlib_imports(self):
        stdlib_names = sys.stdlib_module_names
        source = Path(__file__).read_text(encoding="utf-8")
        import_re = re.compile(r"^(?:import|from)\s+([\w.]+)", re.MULTILINE)
        found = [m.group(1).split(".")[0] for m in import_re.finditer(source)]
        self.assertIn("unittest", found)
        for top_level in found:
            self.assertIn(
                top_level, stdlib_names, f"non-stdlib import: {top_level}"
            )


if __name__ == "__main__":
    unittest.main()

"""Tests for task0001 (tests-yaml-existing-test-search):
em-workflow/skills/tdd-testing/SKILL.md gains a new section requiring
implementers to search for existing tests before an acceptance-test entry
in `*.tests.yaml` declares that no existing test covers a criterion, and
em-workflow/agents/implementer.md Step 4c references that section.

Covers task0001 Acceptance Criteria
(feature-docs/tests-yaml-existing-test-search/tasks/task0001.md):

- AC-1 (FR1): the new SKILL.md section states the two trigger forms
  (`tests: []` / `red_confirmed: false` citing absence) and that searching
  by repository-relative path and filename is mandatory, including for
  build/lint-verified criteria.
- AC-2 (FR2): the same section states the found-case recording rules (list
  under `tests:`, the three-part red_reason shape, red_confirmed reflects
  the observed fact) and the synthetic-fixture exclusion, and restates the
  not-found case.
- AC-3 (FR3, NFR4): implementer.md's Step 4c range references the SKILL.md
  section by skill name and heading string, and that heading exists as a
  real heading line in SKILL.md. (The "no `# Task assignment` heading"
  half of AC-3 is verified by
  tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant
  against the real repository, not here -- see this task's tests.yaml.)
- AC-4 (FR4, NFR1): this module itself -- discovered by `unittest
  discover`, standard-library-only imports, NFR1 naming.
- AC-5 (FR4): each matcher (M1-M5) has a negative case: a fake sample
  missing the element it checks fails, and a fake sample with every
  element present passes.

Judgement is confined to the text sliced out by heading (Test Notes: "判定
は切り出した範囲の中だけで行う"), never the surrounding document, and is
identifier-word based rather than exact-sentence based, tolerant of case
and line-break placement (Test Notes).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "tdd-testing" / "SKILL.md"
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"

# The new SKILL.md section's heading text (module-wide single source, per
# Test Notes: "モジュール内の定数として1か所で持つ").
SECTION_TITLE = "Search existing tests before declaring none exist"

STEP_4C_START_HEADING = "#### 4c. Write the test record"
STEP_5_HEADING = "### Step 5: Commit"


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section_to_next_heading(text, start_heading, heading_marker="## "):
    """Slice from `start_heading` to the next line starting with
    `heading_marker` (or end of text). Raises ValueError -- reported as a
    test error, never silently returning empty text -- if `start_heading`
    is not present."""
    start = text.index(start_heading)
    rest = text[start + len(start_heading):]
    m = re.search(r"^" + re.escape(heading_marker), rest, re.MULTILINE)
    end = start + len(start_heading) + (m.start() if m else len(rest))
    return text[start:end]


def _extract_section_between(text, start_heading, end_heading):
    """Slice from `start_heading` up to (not including) `end_heading`.
    Raises ValueError -- reported as a test error -- if either heading is
    missing."""
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _normalize(text):
    """Case- and line-break-insensitive substring matching surface."""
    return re.sub(r"\s+", " ", text.lower())


def heading_exists_as_heading_line(doc_text, heading_title):
    """True iff `heading_title` appears as the text of an ATX heading line
    (any level) somewhere in `doc_text` -- not merely as running prose."""
    pattern = r"^#{1,6}\s*" + re.escape(heading_title) + r"\s*$"
    return bool(re.search(pattern, doc_text, re.MULTILINE))


# --- Matchers ---------------------------------------------------------
#
# Each takes the already-sliced section text and returns True iff every
# element it is responsible for is present. Identifier-word based, per
# Test Notes, not full-sentence matching.

def matches_m1_trigger_and_mandatory_search(section_text):
    """M1: E1 (both trigger forms: `tests: []` and `red_confirmed: false`
    citing an absence) + E2 (searching is mandatory)."""
    n = _normalize(section_text)
    return (
        "tests: []" in n
        and "red_confirmed: false" in n
        and "must" in n
        and "search" in n
    )


def matches_m2_search_keys(section_text):
    """M2: E3 -- both repository-relative path and filename (basename)."""
    n = _normalize(section_text)
    return "relative path" in n and "basename" in n


def matches_m3_found_case(section_text):
    """M3: E4 (list tests: as module/class), E5 (red_reason three-part
    shape: dedicated module out of scope / existing test detects / no red
    occurred), E6 (red_confirmed reflects the observed fact)."""
    n = _normalize(section_text)
    lists_tests = (
        "tests:" in n
        and ("module" in n or "class" in n)
        and "list" in n
    )
    red_reason_shape = (
        "out of scope" in n
        and "detect" in n
        and "no red state" in n
    )
    red_confirmed_observed = "red_confirmed" in n and "observ" in n
    return lists_tests and red_reason_shape and red_confirmed_observed


def matches_m4_synthetic_fixture_exclusion(section_text):
    """M4: E7 -- a hit against a synthetic/fixture copy is excluded."""
    n = _normalize(section_text)
    names_synthetic = "synthetic" in n or "fixture" in n
    excludes_it = (
        "does not count" in n
        or "discard" in n
        or "not count as coverage" in n
    )
    return names_synthetic and excludes_it


def matches_m5_reference(step4c_text, skill_text, section_title=SECTION_TITLE):
    """M5: implementer.md's Step 4c range names the tdd-testing skill and
    the section heading string, and that heading genuinely exists as a
    heading line in the referenced document."""
    n = _normalize(step4c_text)
    references_skill = "tdd-testing" in n
    references_heading = section_title.lower() in n
    heading_is_real = heading_exists_as_heading_line(skill_text, section_title)
    return references_skill and references_heading and heading_is_real


# --- Fake samples for negative proofs (AC-5) ---------------------------
#
# Self-contained: independent of the real documents' wording, so these
# stay meaningful even if the real prose is later rephrased.

FAKE_FULL_SECTION = """## Search existing tests before declaring none exist

Before you write `tests: []` for a criterion, or cite the absence of an
existing test as the reason for `red_confirmed: false`, you must search
the test directory. Search by both the file's repository-relative path
and its basename.

If found, list the test's module or class under `tests:`. Write
red_reason as: a dedicated module is out of scope, but the existing test
detects the behavior; no red state occurred for this change. Record
red_confirmed as the observed fact.

A hit against a synthetic fixture copy does not count as coverage;
discard it and keep searching.

If nothing is found, write `tests: []` as before.
"""

FAKE_SECTION_MISSING_M1 = """## Search existing tests before declaring none exist

Search by both the file's repository-relative path and its basename.

If found, list the test's module or class under `tests:`. Write
red_reason as: a dedicated module is out of scope, but the existing test
detects the behavior; no red state occurred for this change. Record
red_confirmed as the observed fact.

A hit against a synthetic fixture copy does not count as coverage;
discard it and keep searching.
"""

FAKE_SECTION_MISSING_M2 = """## Search existing tests before declaring none exist

Before you write `tests: []` for a criterion, or cite the absence of an
existing test as the reason for `red_confirmed: false`, you must search
the test directory.

If found, list the test's module or class under `tests:`. Write
red_reason as: a dedicated module is out of scope, but the existing test
detects the behavior; no red state occurred for this change. Record
red_confirmed as the observed fact.

A hit against a synthetic fixture copy does not count as coverage;
discard it and keep searching.
"""

FAKE_SECTION_MISSING_M3 = """## Search existing tests before declaring none exist

Before you write `tests: []` for a criterion, or cite the absence of an
existing test as the reason for `red_confirmed: false`, you must search
the test directory. Search by both the file's repository-relative path
and its basename.

A hit against a synthetic fixture copy does not count as coverage;
discard it and keep searching.
"""

FAKE_SECTION_MISSING_M4 = """## Search existing tests before declaring none exist

Before you write `tests: []` for a criterion, or cite the absence of an
existing test as the reason for `red_confirmed: false`, you must search
the test directory. Search by both the file's repository-relative path
and its basename.

If found, list the test's module or class under `tests:`. Write
red_reason as: a dedicated module is out of scope, but the existing test
detects the behavior; no red state occurred for this change. Record
red_confirmed as the observed fact.
"""

FAKE_STEP4C_WITH_REFERENCE = (
    "#### 4c. Write the test record\n\n"
    "Follow the tdd-testing skill's "
    '"Search existing tests before declaring none exist" section before '
    "declaring an absence.\n"
)

FAKE_STEP4C_NO_REFERENCE = (
    "#### 4c. Write the test record\n\n"
    "Write the test record file as usual.\n"
)

FAKE_STEP4C_WRONG_HEADING = (
    "#### 4c. Write the test record\n\n"
    "Follow the tdd-testing skill's "
    '"A heading that does not exist anywhere" section before declaring an '
    "absence.\n"
)

FAKE_SKILL_WITH_HEADING = (
    "# tdd-testing\n\n"
    "## Search existing tests before declaring none exist\n\n"
    "Body.\n"
)

FAKE_SKILL_WITHOUT_HEADING = (
    "# tdd-testing\n\n"
    "## Some other section\n\n"
    "Body.\n"
)


class TestSectionExtractionHelper(unittest.TestCase):
    """The extraction helpers fail loudly -- never silently return empty
    text -- when a heading is missing (Design: '空のテキストで黙って通さ
    ない')."""

    def test_missing_start_heading_raises(self):
        with self.assertRaises(ValueError):
            _extract_section_to_next_heading("no headings here", "## Nope")

    def test_missing_end_heading_raises(self):
        with self.assertRaises(ValueError):
            _extract_section_between("### Start\nbody", "### Start", "### Missing")

    def test_extracts_up_to_next_level2_heading(self):
        text = "## A\nbody a\n## B\nbody b\n"
        section = _extract_section_to_next_heading(text, "## A")
        self.assertIn("body a", section)
        self.assertNotIn("body b", section)

    def test_extracts_to_end_of_text_when_no_further_heading(self):
        text = "## Only\nbody only\n"
        section = _extract_section_to_next_heading(text, "## Only")
        self.assertIn("body only", section)


class TestMatcherM1TriggerAndMandatorySearch(unittest.TestCase):
    def test_fake_full_section_passes(self):
        self.assertTrue(matches_m1_trigger_and_mandatory_search(FAKE_FULL_SECTION))

    def test_fake_section_missing_trigger_and_mandate_fails(self):
        self.assertFalse(
            matches_m1_trigger_and_mandatory_search(FAKE_SECTION_MISSING_M1)
        )

    def test_real_skill_section_passes(self):
        full = _read(SKILL_PATH)
        section = _extract_section_to_next_heading(
            full, "## " + SECTION_TITLE
        )
        self.assertTrue(
            matches_m1_trigger_and_mandatory_search(section), section
        )


class TestMatcherM2SearchKeys(unittest.TestCase):
    def test_fake_full_section_passes(self):
        self.assertTrue(matches_m2_search_keys(FAKE_FULL_SECTION))

    def test_fake_section_missing_search_keys_fails(self):
        self.assertFalse(matches_m2_search_keys(FAKE_SECTION_MISSING_M2))

    def test_real_skill_section_passes(self):
        full = _read(SKILL_PATH)
        section = _extract_section_to_next_heading(
            full, "## " + SECTION_TITLE
        )
        self.assertTrue(matches_m2_search_keys(section), section)


class TestMatcherM3FoundCase(unittest.TestCase):
    def test_fake_full_section_passes(self):
        self.assertTrue(matches_m3_found_case(FAKE_FULL_SECTION))

    def test_fake_section_missing_found_case_fails(self):
        self.assertFalse(matches_m3_found_case(FAKE_SECTION_MISSING_M3))

    def test_real_skill_section_passes(self):
        full = _read(SKILL_PATH)
        section = _extract_section_to_next_heading(
            full, "## " + SECTION_TITLE
        )
        self.assertTrue(matches_m3_found_case(section), section)


class TestMatcherM4SyntheticFixtureExclusion(unittest.TestCase):
    def test_fake_full_section_passes(self):
        self.assertTrue(matches_m4_synthetic_fixture_exclusion(FAKE_FULL_SECTION))

    def test_fake_section_missing_exclusion_fails(self):
        self.assertFalse(
            matches_m4_synthetic_fixture_exclusion(FAKE_SECTION_MISSING_M4)
        )

    def test_real_skill_section_passes(self):
        full = _read(SKILL_PATH)
        section = _extract_section_to_next_heading(
            full, "## " + SECTION_TITLE
        )
        self.assertTrue(matches_m4_synthetic_fixture_exclusion(section), section)


class TestMatcherM5Reference(unittest.TestCase):
    def test_fake_full_reference_and_real_heading_passes(self):
        self.assertTrue(
            matches_m5_reference(FAKE_STEP4C_WITH_REFERENCE, FAKE_SKILL_WITH_HEADING)
        )

    def test_fake_step4c_missing_reference_fails(self):
        self.assertFalse(
            matches_m5_reference(FAKE_STEP4C_NO_REFERENCE, FAKE_SKILL_WITH_HEADING)
        )

    def test_fake_step4c_references_a_heading_absent_from_skill_fails(self):
        self.assertFalse(
            matches_m5_reference(FAKE_STEP4C_WRONG_HEADING, FAKE_SKILL_WITH_HEADING)
        )

    def test_fake_reference_present_but_skill_lacks_the_heading_fails(self):
        self.assertFalse(
            matches_m5_reference(
                FAKE_STEP4C_WITH_REFERENCE, FAKE_SKILL_WITHOUT_HEADING
            )
        )

    def test_real_implementer_step4c_references_real_skill_section(self):
        implementer_text = _read(IMPLEMENTER_PATH)
        step4c = _extract_section_between(
            implementer_text, STEP_4C_START_HEADING, STEP_5_HEADING
        )
        skill_text = _read(SKILL_PATH)
        self.assertTrue(
            matches_m5_reference(step4c, skill_text), step4c
        )


class TestNewSectionHeadingExistsInSkillDocument(unittest.TestCase):
    """AC-3's other half: the heading implementer.md references must be a
    genuine heading line in SKILL.md, not merely quoted prose."""

    def test_section_title_is_a_real_heading_line_in_skill_md(self):
        skill_text = _read(SKILL_PATH)
        self.assertTrue(heading_exists_as_heading_line(skill_text, SECTION_TITLE))


if __name__ == "__main__":
    unittest.main()

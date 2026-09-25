"""Tests for task0001 (tests-yaml-record-contract): the tests.yaml recording
rules in `em-workflow/agents/implementer.md` Step 4c and Step 6
(feature-docs/tests-yaml-record-contract/tasks/task0001.md).

This is a document-contract test: it reads implementer.md and asserts that
each of the task's five rules (R1-R5 in the task plan) is present in the
document, by section. It never executes the agent; it only checks the
contract text an implementer subagent is instructed by.

Covers task0001 Acceptance Criteria:

- AC-1 (FR1): `test_r1_no_executable_red_recording` -- a criterion with no
  executable red gets `tests: []`, `red_confirmed: false`, a `red_reason`,
  and an `unconfirmed_reds` report entry; documentation-only tasks are named
  as covered; the rule applies per criterion, not as a blanket exemption.
- AC-2 (FR2): `test_r2_red_confirmed_true_meaning` -- `red_confirmed: true`
  means only an actually observed pre-implementation failure (build/lint
  included), reading or searching for a document is not observing a red,
  and the field meanings cannot be locally redefined in `notes` or
  elsewhere.
- AC-3 (FR3): `test_r3_unconfirmed_reds_is_the_report_destination` -- the
  report's `unconfirmed_reds` is named as the destination for
  `red_confirmed: false` criteria, and the pre-change phrase routing them to
  the report's `notes` is gone from Step 4c.
- AC-4 (FR4): `test_r4_final_failures_recording_discipline` -- the
  `final_failures` comment records the actually re-executed run; the re-run
  may be skipped only when no file the suite reads changed at all, with
  "not re-run; baseline inherited" written plus a reason and the report's
  `notes` also stating no re-run happened; an unconfirmable skip condition
  forces a re-run; the same run result is never presented as two
  independent observations across `baseline_failures` and `final_failures`.
- AC-5 (FR5): `test_r5_mandatory_rerun_after_parent_side_adoption` -- Step 6
  states the skip condition never applies after parent-side adoption, that
  the suite is always re-run with both fields updated, and that this holds
  on every adoption in the conflict loop, not only the first.
- AC-6 (FR6, NFR4): `TestOwnModuleStdlibOnly` -- this module imports only
  the standard library, per test/README.md's "no external dependencies"
  rule for test code, and is discovered by
  `python3 -m unittest discover -s tests`. The AC-1 to AC-5 red-to-green
  observation itself is not re-asserted by a test in this module (a suite
  cannot assert its own past execution history); it is recorded in
  tests.yaml and the implementer report instead, per the task plan's Test
  Notes.

Section extraction (`_extract_section`) locates each heading by a
distinctive substring and takes everything up to the next heading of the
same or a shallower Markdown level -- never a hardcoded end-heading string
-- so a future heading rename elsewhere in the document does not silently
truncate or extend the wrong section. `TestSectionsFound` asserts both
sections are non-empty BEFORE any rule check runs, so a missing/renamed
heading fails loudly instead of making a negative check (AC-3's "phrase is
gone") pass vacuously over an empty string.

Every phrase list below is a whitespace-normalized substring check
(`_normalize_ws` collapses Markdown line-wrap whitespace to single spaces,
matching the repository's existing document-contract test convention in
tests/test_batch_quiet_output_audit_record_contract.py). Per rule, at least
one checked phrase is new wording absent from the pre-change section (noted
inline); the AC-3 check is the task's one negative proof, targeting the
exact pre-change routing phrase rather than the bare word `notes` (per the
task plan's Processing flow step 6).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

STEP_4C_HEADING = "4c. Write the test record"
STEP_6_HEADING = "Step 6: Merge"

# The exact pre-change phrase (Step 4c, before this task's edit) that routed
# a `red_confirmed: false` criterion to the report's `notes`. Identified
# from the pre-change file per the task plan's Processing flow step 6 --
# used as a negative check, never the bare word `notes` (Step 4c's new
# wording legitimately mentions `notes` twice: the no-local-redefinition
# rule and the skipped-re-run statement).
PRE_CHANGE_NOTES_ROUTING_PHRASE = "and carry it into your report's `notes`."


def _read(path):
    return path.read_text(encoding="utf-8")


def _heading_level(line):
    match = HEADING_RE.match(line)
    return len(match.group(1)) if match else None


def _extract_section(text, heading_substring):
    """Returns the text of the section whose heading line contains
    `heading_substring`, from that heading line up to (excluding) the next
    heading line whose level is the same as or shallower than the found
    heading's level. Raises AssertionError -- loudly, at extraction time --
    when no matching heading line exists, rather than returning an empty
    string a later `assertNotIn` could pass against vacuously."""
    lines = text.splitlines()
    start_index = None
    start_level = None
    for index, line in enumerate(lines):
        level = _heading_level(line)
        if level is not None and heading_substring in line:
            start_index = index
            start_level = level
            break
    if start_index is None:
        raise AssertionError(
            f"no heading line containing {heading_substring!r} found in "
            f"{IMPLEMENTER_PATH}"
        )
    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        level = _heading_level(lines[index])
        if level is not None and level <= start_level:
            end_index = index
            break
    return "\n".join(lines[start_index:end_index])


def _normalize_ws(text):
    """Collapse Markdown line-wrap whitespace to single spaces, matching
    tests/test_batch_quiet_output_audit_record_contract.py's convention."""
    return re.sub(r"\s+", " ", text).strip()


class DocumentSections:
    """Loads implementer.md and extracts both sections exactly once per
    test run, so every rule-check class below shares one read+extraction
    rather than re-parsing the file per test method."""

    _text = None
    _step_4c = None
    _step_6 = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(IMPLEMENTER_PATH)
        return cls._text

    @classmethod
    def step_4c(cls):
        if cls._step_4c is None:
            cls._step_4c = _extract_section(cls.text(), STEP_4C_HEADING)
        return cls._step_4c

    @classmethod
    def step_6(cls):
        if cls._step_6 is None:
            cls._step_6 = _extract_section(cls.text(), STEP_6_HEADING)
        return cls._step_6


class TestSectionsFound(unittest.TestCase):
    """Non-vacuity guard, run before any rule check relies on section
    extraction: both sections must actually be found and non-empty."""

    def test_step_4c_section_found_and_nonempty(self):
        section = DocumentSections.step_4c()
        self.assertTrue(section.strip(), "Step 4c section extracted as empty")

    def test_step_6_section_found_and_nonempty(self):
        section = DocumentSections.step_6()
        self.assertTrue(section.strip(), "Step 6 section extracted as empty")

    def test_extraction_fails_loudly_on_a_missing_heading(self):
        with self.assertRaises(AssertionError):
            _extract_section(DocumentSections.text(), "no such heading exists")


class TestR1NoExecutableRedRecording(unittest.TestCase):
    """AC-1 / FR1: a criterion with no executable red."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(DocumentSections.step_4c())

    def test_required_phrases_present(self):
        for phrase in (
            "tests: []",
            "red_confirmed: false",
            "red_reason",
            # New wording (absent before this task's edit):
            "unconfirmed_reds",
            "Documentation-only tasks are covered by this rule",
            "Apply it per criterion",
            "not a blanket exemption",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


class TestR2RedConfirmedTrueMeaning(unittest.TestCase):
    """AC-2 / FR2: what `red_confirmed: true` means, and the
    no-local-redefinition rule."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(DocumentSections.step_4c())

    def test_required_phrases_present(self):
        for phrase in (
            # New wording (absent before this task's edit):
            "with no implementation present, the executed check was "
            "actually observed to fail",
            "the failure of that check was actually observed before "
            "implementation",
            "Reading, searching for, or locating a document or an anchor "
            "is not observing a red.",
            "must not be locally redefined in `notes` or in any other "
            "text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


class TestR3UnconfirmedRedsIsTheReportDestination(unittest.TestCase):
    """AC-3 / FR3: `unconfirmed_reds` replaces the report's `notes` as the
    destination for `red_confirmed: false` criteria."""

    @classmethod
    def setUpClass(cls):
        cls.section = DocumentSections.step_4c()
        cls.normalized = _normalize_ws(cls.section)

    def test_unconfirmed_reds_named_as_destination(self):
        self.assertIn(
            "list the criterion in the Step 7 report's `unconfirmed_reds`",
            self.normalized,
        )

    def test_pre_change_notes_routing_phrase_is_gone(self):
        # Negative proof: the exact pre-change phrase must not survive,
        # checked against both the raw and the whitespace-normalized text
        # (the phrase wrapped across a Markdown line break pre-change).
        self.assertNotIn(PRE_CHANGE_NOTES_ROUTING_PHRASE, self.section)
        self.assertNotIn(
            _normalize_ws(PRE_CHANGE_NOTES_ROUTING_PHRASE), self.normalized
        )

    def test_negative_proof_would_have_caught_the_pre_change_phrase(self):
        # Non-vacuity guard for the negative proof above: the pre-change
        # phrase, if it were still present, is actually detectable by the
        # same check.
        forged_section = (
            "leave it `false`, say why in `red_reason`, "
            + PRE_CHANGE_NOTES_ROUTING_PHRASE
        )
        self.assertIn(PRE_CHANGE_NOTES_ROUTING_PHRASE, forged_section)

    def test_new_legitimate_notes_mentions_remain(self):
        # R3 only removes the false-red routing phrase; the R2
        # no-redefinition mention and the R4 skipped-re-run mention of
        # `notes` are legitimate and must stay (task plan R3).
        self.assertIn(
            "must not be locally redefined in `notes` or in any other "
            "text",
            self.normalized,
        )
        self.assertIn(
            "the report's `notes` also states that no re-run was "
            "performed",
            self.normalized,
        )


class TestR4FinalFailuresRecordingDiscipline(unittest.TestCase):
    """AC-4 / FR4: the `final_failures` comment's recording discipline."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(DocumentSections.step_4c())

    def test_required_phrases_present(self):
        for phrase in (
            # New wording (absent before this task's edit):
            "records the output of the run actually re-executed after "
            "implementation",
            "no file the suite reads",
            "source, tests, and documents the tests read",
            "not re-run; baseline inherited",
            "the report's `notes` also states that no re-run was "
            "performed",
            "cannot be confirmed that the skip condition holds",
            "a task that changed a document the tests read cannot skip",
            "never written into both `baseline_failures` and "
            "`final_failures`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_tests_yaml_schema_keys_unchanged(self):
        # NFR1 (task plan Design): only the final_failures comment text
        # may change in the shown tests.yaml example; its keys stay as
        # they are.
        for key in (
            "task_id:",
            "baseline_failures:",
            "final_failures:",
            "acceptance_tests:",
        ):
            with self.subTest(key=key):
                self.assertIn(key, self.normalized)


class TestR5MandatoryRerunAfterParentSideAdoption(unittest.TestCase):
    """AC-5 / FR5: Step 6's mandatory re-run after parent-side adoption."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(DocumentSections.step_6())

    def test_required_phrases_present(self):
        for phrase in (
            # New wording (absent before this task's edit):
            "After parent-side adoption, the `final_failures` skip "
            "condition never applies",
            "the suite is always re-run",
            "both `baseline_failures` and `final_failures` are updated",
            "on every adoption within this conflict loop, not only the "
            "first",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6 / FR6, NFR4: this module imports the standard library only."""

    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


class TestFileExists(unittest.TestCase):
    def test_implementer_md_exists(self):
        self.assertTrue(IMPLEMENTER_PATH.is_file())


if __name__ == "__main__":
    unittest.main()

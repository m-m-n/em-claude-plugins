"""Document-contract test for task0005 (tests-yaml-test-id-resolution): the
record-writing rules in `em-workflow/agents/implementer.md` Step 4c and the
ID format and record notation in `test/README.md`
(feature-docs/tests-yaml-test-id-resolution/tasks/task0005.md).

It reads both documents as text and asserts, per rule, phrases that the rule
keeps in the document. It never imports or executes either document, and it
imports the standard library only.

One test per rule, so a missing rule surfaces under its own test name:

- AC-1 (FR10): `TestImplementerStep4cRules.test_rule1_tests_element_is_a_directly_selectable_id`
  -- each `tests` element is an ID the project's test command selects
  directly; free text, abbreviations, wildcards and runner script paths are
  not written there; explanations go in `red_reason`. The wording constraint
  (the added text names no programming language, test framework, module of
  this repository, or the `tests.` prefix) is asserted over the added
  paragraphs by `TestAddedTextStaysLanguageIndependent`.
- AC-2 (FR11): `TestImplementerStep4cRules.test_rule2_project_test_command_runs_after_writing_the_record`
  -- after writing the record, `project_commands.test` runs, no failure
  absent from the baseline may remain, and a failure caused by the record is
  fixed in the record.
- AC-3 (FR12): `TestImplementerStep4cRules.test_rule3_other_records_broken_by_a_rename_or_deletion_are_fixed`
  -- IDs of other features' or tasks' records that fail the record check
  because of a rename or deletion are fixed too; file changes outside the
  planned files are reported in `deviations`; a request to extend the
  planned files names the existing AC, the path and the failing check.
- AC-4 (FR13): `TestReadmeRules.test_rule4_id_format_is_stated`
  -- IDs start with `tests.`, are dot-separated, are accepted at module,
  class or method level, and are judged as under the project test command
  run from the repository root.
- AC-5 (FR7): `TestReadmeRules.test_rule5_record_notation_is_stated`
  -- every supported form, the opaque-value rule and every error condition
  of the record notation, and the record check module's name.
- AC-6 (TS-9): `TestOwnModule` and `TestRuleChecksDetectRemovedText` --
  this module imports the standard library only, never imports or runs the
  documents, is named and placed so `python3 -m unittest discover -s tests`
  collects it, and each rule's check fails when that rule's text is removed
  (and only that rule's check).

Added by task0005 of tests-yaml-id-resolution-gaps
(feature-docs/tests-yaml-id-resolution-gaps/tasks/task0005.md), which realigns
the README's Syntax gate and non-execution guarantee with the record check's
behavior:

- AC-1 (FR6, FR7): `TestReadmeGateAndGuaranteeWording` -- the Syntax gate says
  "two or more dot-separated segments", and the superseded "one or more
  dot-separated segments" wording is gone from the README.
- AC-2 (FR6, FR7): `TestReadmeGateAndGuaranteeWording` -- the README states
  both halves of the canonical non-execution guarantee (test method bodies
  are never executed; Loader confirmation instantiates the test classes,
  including a custom `__init__`, and runs `load_tests` hooks), and no
  statement that resolved objects are never called or instantiated remains.
- AC-3 (FR6): `TestReadmeGateAndGuaranteeWording` -- Structural resolution
  names a dunder last segment of a method ID as rejected with
  `not a test method`; Loader confirmation names a non-suite result and an
  exception during the suite walk as failure conditions.
- AC-4 (FR7, TS-6): `TestGateAndGuaranteeChecksDetectRemovedText` -- each
  check is a predicate over README text; it passes on the real README and
  fails on an in-memory copy from which its own wording was removed, and
  only that predicate fails.
- AC-6 (NFR1, NFR2): `TestOwnModule` (standard library only, collected by
  the normal run).

The implementer.md assertions are limited to the Step 4c section, from its
heading to the next step heading; the README assertions are limited to the
subsection that holds the rule.

Every phrase is a whitespace-normalized substring check, so Markdown
line-wrap placement does not matter.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"
README_PATH = REPO_ROOT / "test" / "README.md"

STEP_4C_HEADING = "4c. Write the test record"
README_ID_FORMAT_HEADING = "Test ID format"
README_NOTATION_HEADING = "Record notation read by the record check"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


# --- Rule phrases ------------------------------------------------------
#
# Each tuple is the set of phrases one rule keeps in its document. The
# first phrase of every tuple is the anchor that locates the rule's block
# for the removal checks below.

RULE1_PHRASES = (
    "Each element of `tests` is an ID that the project's test command can "
    "select directly",
    "Free text, abbreviations, wildcards and runner script paths are never "
    "written in `tests`",
    "explanations go in `red_reason`",
)

RULE2_PHRASES = (
    "After writing the record, run `project_commands.test` again",
    "no failure absent from the baseline you recorded in Step 4a remains",
    "A failure caused by the record is fixed in the record",
)

RULE3_PHRASES = (
    "When renaming or deleting a test makes a record that belongs to "
    "another feature or another task fail the project's record check",
    "fix that record's IDs as well",
    "File changes outside the planned files (`expected_files`) are "
    "reported in `deviations`",
    "A request to extend the planned files names the existing acceptance "
    "criterion that needs it",
    "the path needed",
    "the check that fails without the change",
)

RULE4_PHRASES = (
    "IDs start with `tests.` and are dot-separated",
    "IDs are accepted at module, class or method level",
    "judged as under `python3 -m unittest discover -s tests` run from the "
    "repository root",
    # The acceptance criterion summarised from the three evaluation steps.
    "Syntax gate",
    "the first segment is exactly `tests`",
    "valid Python identifier",
    "`path::Class::method`",
    "Structural resolution",
    "without calling anything",
    "`unittest.TestCase`",
    "Loader confirmation",
    "`loadTestsFromName`",
    "failed-test placeholder",
)

RULE5_PHRASES = (
    "`tests/test_tests_yaml_id_resolution.py`",
    # Supported forms.
    "full-line comments",
    "document start marker `---`",
    "plain or single-line quoted key",
    "`acceptance_tests` occurs exactly once",
    "Every key name is accepted as an AC key",
    "Exactly one field is `tests`",
    "Flow sequence",
    "`[]` is the empty list",
    "Block sequence",
    "plain, single-quoted or double-quoted",
    "two consecutive single quotes stand for one",
    "backslash-quote and backslash-backslash",
    # The opaque-value rule.
    "is opaque",
    "never interpreted",
    "`baseline_failures` / `final_failures`",
    "multi-line `red_reason`",
    # Error conditions.
    "Unsupported notation",
    "a tab in indentation",
    "a `tests` item that is a mapping, a sequence, multi-line or empty",
    "a flow sequence spanning lines",
    "an inline value after `acceptance_tests:` or after an AC key",
    "inconsistent indentation within one level",
    "a second `acceptance_tests`",
    "a `tests` key with neither a value nor items",
    "Duplicate AC key",
    "Duplicate `tests` key within one AC",
    "Missing `tests` key in an AC",
    "Missing `acceptance_tests`",
    "Unreadable record",
    "cannot be decoded as UTF-8",
    "never treated as an empty list",
)


# --- Gate and guarantee wording (tests-yaml-id-resolution-gaps) -------------
#
# Each check below is a predicate over README text (a string in, a bool out),
# so the same predicate runs on the real README and on an in-memory copy with
# its wording removed.

TWO_OR_MORE_SEGMENTS = "two or more dot-separated segments"
SUPERSEDED_SEGMENTS = "one or more dot-separated segments"

# The two halves of the canonical non-execution guarantee (IMPLEMENTATION.md
# D1), used verbatim in the README.
BODIES_NEVER_EXECUTED = "Test method bodies are never executed."
LOADER_INSTANTIATES_AND_RUNS_HOOKS = (
    "Loader confirmation, like ordinary test collection, instantiates the "
    "test classes (including any custom `__init__`) and runs `load_tests` "
    "hooks."
)

DUNDER_REJECTION_PHRASES = (
    "last segment is a dunder name",
    "(for example `__init__`) is rejected as `not a test method`",
    "even when the test class defines it",
)
LOADER_FAILURE_PHRASES = (
    "returns something that is not a suite",
    "an exception is raised while walking the returned suite",
)

# A claim that resolved objects are never called or instantiated. The
# Structural resolution step's "without calling anything" is not such a claim:
# it describes one step, not the whole check.
NEVER_CALLED_CLAIM_RE = re.compile(
    r"\bnever\s+(?:calls?|called|calling|instantiates?|instantiated|instantiating)\b"
    r"|\b(?:is|are|be)\s+not\s+(?:called|instantiated)\b",
    re.IGNORECASE,
)


def _states_all(text, phrases):
    return not _missing(text, phrases)


def states_two_or_more_segments(text):
    return _states_all(text, (TWO_OR_MORE_SEGMENTS,))


def states_bodies_never_executed(text):
    return _states_all(text, (BODIES_NEVER_EXECUTED,))


def states_loader_instantiates_and_runs_hooks(text):
    return _states_all(text, (LOADER_INSTANTIATES_AND_RUNS_HOOKS,))


def states_dunder_rejection(text):
    return _states_all(text, DUNDER_REJECTION_PHRASES)


def states_loader_non_suite_and_walk_exception(text):
    return _states_all(text, LOADER_FAILURE_PHRASES)


def makes_no_superseded_claim(text):
    """True when `text` carries neither the "one or more" segment wording nor
    a statement that resolved objects are never called or instantiated."""
    normalized = _normalize_ws(text)
    return SUPERSEDED_SEGMENTS not in normalized and not NEVER_CALLED_CLAIM_RE.search(
        normalized
    )


# Check table: name -> (predicate, the wording the predicate requires, each
# piece of which the removal checks cut out in turn).
GATE_AND_GUARANTEE_CHECKS = {
    "two-or-more-segments": (
        states_two_or_more_segments,
        (TWO_OR_MORE_SEGMENTS,),
    ),
    "bodies-never-executed": (
        states_bodies_never_executed,
        (BODIES_NEVER_EXECUTED,),
    ),
    "loader-instantiates-and-runs-hooks": (
        states_loader_instantiates_and_runs_hooks,
        (LOADER_INSTANTIATES_AND_RUNS_HOOKS,),
    ),
    "dunder-rejection": (states_dunder_rejection, DUNDER_REJECTION_PHRASES),
    "loader-non-suite-and-walk-exception": (
        states_loader_non_suite_and_walk_exception,
        LOADER_FAILURE_PHRASES,
    ),
}


# --- Document access ---------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _heading_level(line):
    match = HEADING_RE.match(line)
    return len(match.group(1)) if match else None


def _extract_section(text, heading_substring, source):
    """Text of the section whose heading line contains `heading_substring`,
    from that heading line up to (excluding) the next heading line of the
    same or a shallower level. Raises AssertionError when no heading line
    contains the substring, so a renamed heading fails loudly instead of
    leaving later checks to run over an empty string."""
    lines = text.splitlines()
    start = None
    level = None
    for index, line in enumerate(lines):
        found = _heading_level(line)
        if found is not None and heading_substring in line:
            start, level = index, found
            break
    if start is None:
        raise AssertionError(
            f"no heading line containing {heading_substring!r} in {source}"
        )
    end = len(lines)
    for index in range(start + 1, len(lines)):
        found = _heading_level(lines[index])
        if found is not None and found <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _missing(section_text, phrases):
    """The phrases of `phrases` that `section_text` does not contain."""
    normalized = _normalize_ws(section_text)
    return [phrase for phrase in phrases if phrase not in normalized]


def _blocks(section_text):
    return re.split(r"\n[ \t]*\n", section_text)


def _block_containing(section_text, phrase):
    for block in _blocks(section_text):
        if phrase in _normalize_ws(block):
            return block
    raise AssertionError(f"no block contains {phrase!r}")


def _without_block_containing(section_text, phrase):
    anchor = _block_containing(section_text, phrase)
    kept = [block for block in _blocks(section_text) if block != anchor]
    return "\n\n".join(kept)


def _remove_phrase(text, phrase):
    """`text` with every occurrence of `phrase` cut out, whatever line wrap
    sits between the phrase's words. Raises AssertionError when the phrase is
    absent, so a removal case cannot pass vacuously on text that never had the
    phrase."""
    pattern = r"\s+".join(re.escape(word) for word in phrase.split())
    reduced, count = re.subn(pattern, "", text)
    if count == 0:
        raise AssertionError(f"{phrase!r} is not in the text")
    return reduced


class Documents:
    """Reads each document once and slices out each rule's section."""

    _cache = {}

    @classmethod
    def _text(cls, path):
        if path not in cls._cache:
            cls._cache[path] = _read(path)
        return cls._cache[path]

    @classmethod
    def readme(cls):
        return cls._text(README_PATH)

    @classmethod
    def step_4c(cls):
        return _extract_section(
            cls._text(IMPLEMENTER_PATH), STEP_4C_HEADING, IMPLEMENTER_PATH
        )

    @classmethod
    def readme_id_format(cls):
        return _extract_section(
            cls._text(README_PATH), README_ID_FORMAT_HEADING, README_PATH
        )

    @classmethod
    def readme_notation(cls):
        return _extract_section(
            cls._text(README_PATH), README_NOTATION_HEADING, README_PATH
        )


# Rule table: name -> (section reader, phrases). One entry per rule, used by
# the removal checks.
RULES = {
    "rule1": (Documents.step_4c, RULE1_PHRASES),
    "rule2": (Documents.step_4c, RULE2_PHRASES),
    "rule3": (Documents.step_4c, RULE3_PHRASES),
    "rule4": (Documents.readme_id_format, RULE4_PHRASES),
    "rule5": (Documents.readme_notation, RULE5_PHRASES),
}


class TestSectionsFound(unittest.TestCase):
    """Non-vacuity guard: every section a rule check slices out exists and
    is non-empty, and a missing heading fails loudly."""

    def test_step_4c_section_is_found_and_nonempty(self):
        self.assertTrue(Documents.step_4c().strip())

    def test_readme_id_format_section_is_found_and_nonempty(self):
        self.assertTrue(Documents.readme_id_format().strip())

    def test_readme_notation_section_is_found_and_nonempty(self):
        self.assertTrue(Documents.readme_notation().strip())

    def test_missing_heading_raises_instead_of_returning_empty_text(self):
        with self.assertRaises(AssertionError):
            _extract_section("# Title\n\ntext\n", "no such heading", "sample")


class TestImplementerStep4cRules(unittest.TestCase):
    """AC-1 to AC-3: the rules in Step 4c of implementer.md."""

    def assert_rule_present(self, phrases):
        missing = _missing(Documents.step_4c(), phrases)
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                if phrase in missing:
                    self.fail(f"Step 4c of implementer.md lacks {phrase!r}")

    def test_rule1_tests_element_is_a_directly_selectable_id(self):
        self.assert_rule_present(RULE1_PHRASES)

    def test_rule2_project_test_command_runs_after_writing_the_record(self):
        self.assert_rule_present(RULE2_PHRASES)

    def test_rule3_other_records_broken_by_a_rename_or_deletion_are_fixed(self):
        self.assert_rule_present(RULE3_PHRASES)


class TestReadmeRules(unittest.TestCase):
    """AC-4 and AC-5: the ID format and the record notation in
    test/README.md."""

    def assert_rule_present(self, section, phrases):
        missing = _missing(section, phrases)
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                if phrase in missing:
                    self.fail(f"test/README.md section lacks {phrase!r}")

    def test_rule4_id_format_is_stated(self):
        self.assert_rule_present(Documents.readme_id_format(), RULE4_PHRASES)

    def test_rule5_record_notation_is_stated(self):
        self.assert_rule_present(Documents.readme_notation(), RULE5_PHRASES)


# Names that the text added to implementer.md must not carry (AC-1): the
# agent serves every project, so it names no programming language, test
# framework, module of this repository, or the `tests.` prefix.
FORBIDDEN_IN_ADDED_TEXT = (
    ("programming language", r"\b(python|java|javascript|typescript|ruby|rust|golang)\b"),
    ("test framework", r"\b(unittest|pytest|nose|jest|mocha|junit|rspec|phpunit)\b"),
    ("module of this repository", r"test_tests_yaml|\btests/"),
    ("the `tests.` prefix", r"`tests\.`|\btests\.\w"),
)


class TestAddedTextStaysLanguageIndependent(unittest.TestCase):
    """AC-1's wording constraint, over the paragraphs that carry rules 1 to
    3."""

    def test_added_paragraphs_name_no_language_framework_module_or_prefix(self):
        section = Documents.step_4c()
        for rule in ("rule1", "rule2", "rule3"):
            phrases = RULES[rule][1]
            paragraph = _normalize_ws(_block_containing(section, phrases[0])).lower()
            for label, pattern in FORBIDDEN_IN_ADDED_TEXT:
                with self.subTest(rule=rule, forbidden=label):
                    self.assertIsNone(
                        re.search(pattern, paragraph),
                        f"{rule}'s paragraph names {label}",
                    )

    def test_forbidden_name_check_would_catch_a_violation(self):
        sample = (
            "ids such as tests.test_x.TestY are written with pytest in python; "
            "see tests/test_x.py"
        )
        for label, pattern in FORBIDDEN_IN_ADDED_TEXT:
            with self.subTest(forbidden=label):
                self.assertIsNotNone(re.search(pattern, sample))


class TestRuleChecksDetectRemovedText(unittest.TestCase):
    """AC-6: each rule's check fails when that rule's text is removed, and
    only that rule's check."""

    def test_removing_a_rules_block_makes_its_check_fail(self):
        for name, (read_section, phrases) in RULES.items():
            with self.subTest(rule=name):
                section = read_section()
                self.assertEqual(_missing(section, phrases), [])
                reduced = _without_block_containing(section, phrases[0])
                self.assertNotEqual(_missing(reduced, phrases), [])

    def test_removing_one_implementer_rule_leaves_the_other_rules_passing(self):
        section = Documents.step_4c()
        for removed in ("rule1", "rule2", "rule3"):
            reduced = _without_block_containing(section, RULES[removed][1][0])
            for other in ("rule1", "rule2", "rule3"):
                if other == removed:
                    continue
                with self.subTest(removed=removed, other=other):
                    self.assertEqual(_missing(reduced, RULES[other][1]), [])

    def test_removing_the_id_format_leaves_the_notation_rule_passing(self):
        notation = Documents.readme_notation()
        self.assertEqual(_missing(notation, RULE5_PHRASES), [])
        id_format = Documents.readme_id_format()
        reduced = _without_block_containing(id_format, RULE4_PHRASES[0])
        self.assertNotEqual(_missing(reduced, RULE4_PHRASES), [])


class TestReadmeGateAndGuaranteeWording(unittest.TestCase):
    """AC-1 to AC-3 of task0005: the Syntax gate, Structural resolution,
    Loader confirmation and non-execution guarantee wording in the README's
    Test ID format subsection."""

    def assert_check_passes(self, name):
        predicate, _wording = GATE_AND_GUARANTEE_CHECKS[name]
        self.assertTrue(
            predicate(Documents.readme_id_format()),
            f"test/README.md Test ID format section fails the {name} check",
        )

    def test_ac1_syntax_gate_says_two_or_more_dot_separated_segments(self):
        self.assert_check_passes("two-or-more-segments")

    def test_ac1_one_or_more_segments_wording_no_longer_appears(self):
        self.assertNotIn(SUPERSEDED_SEGMENTS, _normalize_ws(Documents.readme()))

    def test_ac2_guarantee_states_that_test_method_bodies_are_never_executed(self):
        self.assert_check_passes("bodies-never-executed")

    def test_ac2_guarantee_states_that_loader_confirmation_instantiates_and_runs_hooks(
        self,
    ):
        self.assert_check_passes("loader-instantiates-and-runs-hooks")

    def test_ac2_no_statement_that_resolved_objects_are_never_called_or_instantiated(
        self,
    ):
        self.assertTrue(makes_no_superseded_claim(Documents.readme()))

    def test_ac3_structural_resolution_rejects_a_dunder_last_segment(self):
        self.assert_check_passes("dunder-rejection")

    def test_ac3_loader_confirmation_names_non_suite_result_and_walk_exception(self):
        self.assert_check_passes("loader-non-suite-and-walk-exception")


class TestGateAndGuaranteeChecksDetectRemovedText(unittest.TestCase):
    """AC-4 of task0005: each check is a predicate over README text; it fails
    on an in-memory copy with its wording removed, and only it fails. The real
    README is never edited."""

    def test_each_check_fails_when_a_piece_of_its_wording_is_removed(self):
        section = Documents.readme_id_format()
        for name, (predicate, wording) in GATE_AND_GUARANTEE_CHECKS.items():
            self.assertTrue(predicate(section), name)
            for piece in wording:
                with self.subTest(check=name, removed=piece):
                    self.assertFalse(predicate(_remove_phrase(section, piece)))

    def test_removing_one_checks_wording_leaves_the_other_checks_passing(self):
        section = Documents.readme_id_format()
        for name, (_predicate, wording) in GATE_AND_GUARANTEE_CHECKS.items():
            for piece in wording:
                reduced = _remove_phrase(section, piece)
                for other, (other_predicate, _other_wording) in (
                    GATE_AND_GUARANTEE_CHECKS.items()
                ):
                    if other == name:
                        continue
                    with self.subTest(removed=piece, other=other):
                        self.assertTrue(other_predicate(reduced))

    def test_removing_a_whole_guarantee_half_fails_its_check_only(self):
        section = Documents.readme_id_format()
        for removed, failing, passing in (
            (
                BODIES_NEVER_EXECUTED,
                states_bodies_never_executed,
                states_loader_instantiates_and_runs_hooks,
            ),
            (
                LOADER_INSTANTIATES_AND_RUNS_HOOKS,
                states_loader_instantiates_and_runs_hooks,
                states_bodies_never_executed,
            ),
        ):
            with self.subTest(removed=removed):
                reduced = _remove_phrase(section, removed)
                self.assertFalse(failing(reduced))
                self.assertTrue(passing(reduced))

    def test_removing_the_segment_wording_from_the_gate_fails_the_check(self):
        reduced = _remove_phrase(Documents.readme_id_format(), TWO_OR_MORE_SEGMENTS)
        self.assertFalse(states_two_or_more_segments(reduced))

    def test_removal_helper_refuses_text_that_lacks_the_phrase(self):
        with self.assertRaises(AssertionError):
            _remove_phrase("nothing to cut here", TWO_OR_MORE_SEGMENTS)

    def test_removal_helper_cuts_a_phrase_across_a_line_wrap(self):
        wrapped = "ids of two or more\ndot-separated segments are fine"
        self.assertFalse(
            states_two_or_more_segments(_remove_phrase(wrapped, TWO_OR_MORE_SEGMENTS))
        )
        self.assertTrue(states_two_or_more_segments(wrapped))

    def test_superseded_claim_check_catches_the_old_wording(self):
        old_lines = (
            "the ID consists of one or more dot-separated segments, each a "
            "valid Python identifier",
            "The record check never calls anything it resolved and never runs "
            "a returned test.",
            "Resolved classes are never instantiated.",
            "Resolved objects are never called or instantiated.",
            "The resolved class is not instantiated.",
        )
        for line in old_lines:
            with self.subTest(line=line):
                self.assertFalse(makes_no_superseded_claim(line))

    def test_superseded_claim_check_accepts_the_new_wording(self):
        new_lines = (
            TWO_OR_MORE_SEGMENTS,
            BODIES_NEVER_EXECUTED + " " + LOADER_INSTANTIATES_AND_RUNS_HOOKS,
            "the remaining segments are looked up as attributes without "
            "calling anything.",
        )
        for line in new_lines:
            with self.subTest(line=line):
                self.assertTrue(makes_no_superseded_claim(line))


class TestOwnModule(unittest.TestCase):
    """AC-6: this module imports the standard library only, reads the
    documents as text, and is collected by the project test command."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    def imported_top_level_modules(self):
        modules = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        return modules

    def test_only_standard_library_modules_are_imported(self):
        non_stdlib = sorted(
            m for m in self.imported_top_level_modules() if m not in sys.stdlib_module_names
        )
        self.assertEqual(non_stdlib, [])

    def test_no_module_that_imports_or_runs_a_document_is_imported(self):
        runners = {"importlib", "runpy", "subprocess", "imp", "pkgutil"}
        self.assertEqual(sorted(self.imported_top_level_modules() & runners), [])

    def test_module_is_placed_and_named_for_unittest_discovery(self):
        path = Path(__file__).resolve()
        self.assertEqual(path.parent, REPO_ROOT / "tests")
        self.assertRegex(path.name, r"^test.*\.py$")


if __name__ == "__main__":
    unittest.main()

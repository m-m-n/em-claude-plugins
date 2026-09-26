"""Tests for tier-rules.yaml's `question_set` bucket descriptions and
`codex_output_schema` fact fields (feature-docs/tier-decision-staged-jev,
task0002).

Structural checks (AC-1, AC-4, AC-5) read the parsed YAML via
importlib-loaded decide-tier.py's `_load_rules` helper -- the same
technique tests/test_tier_rules.py already uses -- rather than importing
PyYAML directly in this test module (NFR7: test code imports no
third-party package). Raw-text checks (AC-2, AC-3) operate on the
`question_set` section's own text, isolated from the rest of the file by
its dash-delimited banner comment, so a violation hidden inside a comment
still fails. Each raw-text matcher is paired with a negative proof against
a forged sample and a non-vacuity guard (task plan Test Notes;
IMPLEMENTATION.md "Test module convention").

Covers task0002 Acceptance Criteria:
- AC-1: `question_set` defines exactly four bucket descriptions keyed "0"
  to "3"; bucket 1 names the rule-addition + test-addition combination;
  bucket 0 excludes both test changes and new logic.
- AC-2: the `question_set` comment states the descriptions are passed to
  both Jev calls (description-only and final) and no longer assigns the
  bucket wording to an external skill.
- AC-3: no line of the `question_set` section (descriptions + comment) at
  least 30 characters long (whitespace-normalized) appears verbatim in
  the jev skill doc or the typesafe-ai skill doc; a skip when a document
  is absent is reported with a reason and never counts as a pass.
- AC-4: `codex_output_schema` contains all seven new fact fields, each
  with exactly the listed value vocabulary.
- AC-5: every codex_output_schema field name present before this task is
  still present; the section states Codex reports facts only.
- AC-6: the rule table still parses as YAML (exercised implicitly by
  every test below loading it), and this module's own raw-text matchers
  each carry a negative proof and a non-vacuity guard.
"""

import ast
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIER_RULES_PATH = REPO_ROOT / "em-workflow" / "references" / "tier-rules.yaml"
DECIDE_TIER_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "decide-tier.py"
THIS_TEST_FILE = Path(__file__).resolve()

JEV_SKILL_DOC = Path.home() / ".claude" / "skills" / "jev" / "SKILL.md"
CLAUDE_HOME = Path.home() / ".claude"

# Pre-existing codex_output_schema field names, recorded by reading the
# file before this task edited it (task plan Test Notes).
PRE_EXISTING_CODEX_FIELDS = [
    "files_expected",
    "changed_lines_approx",
    "new_functions_needed",
    "new_files_needed",
    "new_dependencies_needed",
    "covering_tests_exist",
    "spillover_modules",
    "work_still_required",
]

# The seven new fact fields and their exact value vocabulary (task plan
# Design table).
NEW_FACT_FIELDS = {
    "test_change_kind": {
        "kind": "enum",
        "values": ["none", "extend_existing_one_to_one", "new_behavior_tests"],
    },
    "added_test_cases_approx": {"kind": "type", "type": "integer"},
    "body_change_kind": {
        "kind": "enum",
        "values": ["wording_or_rule_addition", "new_logic"],
    },
    "change_containment": {
        "kind": "enum",
        "values": ["single_function", "single_module", "multiple_modules"],
    },
    "caller_and_dependency_count": {"kind": "type", "type": "integer"},
    "changes_external_contract": {"kind": "type", "type": "boolean"},
    "changes_behavior": {"kind": "type", "type": "boolean"},
}

DASH_LINE = re.compile(r"^#\s*-{5,}\s*$")


def load_decide_tier_module():
    spec = importlib.util.spec_from_file_location(
        "_decide_tier_under_test_buckets_facts", DECIDE_TIER_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dt = load_decide_tier_module()


def find_typesafe_skill_docs():
    """Locate the typesafe-ai skill's SKILL.md by its skill name, searched
    across the whole ~/.claude directory tree (task plan Test Notes: "the
    typesafe-ai skill's SKILL.md located by its skill name in the same
    directory tree"). Returns every match found (there may be more than
    one: cache + marketplace checkouts), since checking against every
    resolvable copy only strengthens the duplication guard."""
    if not CLAUDE_HOME.is_dir():
        return []
    matches = [
        p
        for p in CLAUDE_HOME.rglob("SKILL.md")
        if p.parent.name == "typesafe-ai" and p.parent.parent.name == "skills"
    ]
    return sorted(set(matches))


def extract_banner_section(text, key):
    """Return the dash-delimited banner comment immediately preceding
    `{key}:` together with that key's own body, stopping right before the
    next section's banner (or EOF). Isolates "the question_set section
    (descriptions and comment)" from the rest of the file, per the task
    plan's Test Notes scoping."""
    lines = text.splitlines()
    key_line_idx = next(
        i for i, line in enumerate(lines) if line.startswith(f"{key}:")
    )

    i = key_line_idx - 1
    while i >= 0 and lines[i].strip() == "":
        i -= 1
    if i < 0 or not DASH_LINE.match(lines[i]):
        raise AssertionError(f"no closing banner dash found above {key}:")
    closing_dash_idx = i
    j = closing_dash_idx - 1
    while j >= 0 and not DASH_LINE.match(lines[j]):
        j -= 1
    if j < 0:
        raise AssertionError(f"no opening banner dash found above {key}:")
    start = j

    k = key_line_idx + 1
    while k < len(lines) and not DASH_LINE.match(lines[k]):
        k += 1
    end = k

    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# AC-1: exactly four bucket descriptions keyed "0" to "3"
# ---------------------------------------------------------------------------


class TestBucketDescriptionsStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)
        cls.bucket_descriptions = cls.rules["question_set"]["bucket_descriptions"]

    def test_exactly_four_keys_0_to_3(self):
        self.assertEqual(set(self.bucket_descriptions.keys()), {"0", "1", "2", "3"})

    def test_keys_are_strings_not_integers(self):
        for key in self.bucket_descriptions.keys():
            with self.subTest(key=key):
                self.assertIsInstance(key, str)

    def test_key_set_matcher_would_fail_on_a_forged_extra_key(self):
        forged = dict(self.bucket_descriptions)
        forged["4"] = "a fifth bucket that should not exist"
        self.assertNotEqual(set(forged.keys()), {"0", "1", "2", "3"})
        # Non-vacuity: the real structure does satisfy the check.
        self.assertEqual(set(self.bucket_descriptions.keys()), {"0", "1", "2", "3"})

    def test_key_set_matcher_would_fail_on_a_forged_missing_key(self):
        forged = dict(self.bucket_descriptions)
        del forged["3"]
        self.assertNotEqual(set(forged.keys()), {"0", "1", "2", "3"})

    def test_bucket_1_names_rule_addition_and_test_addition(self):
        desc = self.bucket_descriptions["1"]
        self.assertRegex(desc, r"rule addition")
        self.assertRegex(desc, r"test addition")

    def test_bucket_1_matcher_would_fail_on_a_forged_unrelated_description(self):
        forged = "a description naming neither concept at all"
        self.assertNotRegex(forged, r"rule addition")
        self.assertNotRegex(forged, r"test addition")
        # Non-vacuity: the real description does name both.
        desc = self.bucket_descriptions["1"]
        self.assertRegex(desc, r"rule addition")
        self.assertRegex(desc, r"test addition")

    def test_bucket_0_excludes_test_changes_and_new_logic(self):
        desc = self.bucket_descriptions["0"]
        self.assertRegex(desc, r"no new logic")
        self.assertRegex(desc, r"no test")

    def test_bucket_0_matcher_would_fail_on_a_forged_description_naming_new_logic(self):
        forged = "a change that includes new logic and a new test"
        self.assertNotRegex(forged, r"no new logic")
        self.assertNotRegex(forged, r"no test")
        # Non-vacuity: the real bucket-0 description does exclude both.
        desc = self.bucket_descriptions["0"]
        self.assertRegex(desc, r"no new logic")
        self.assertRegex(desc, r"no test")


# ---------------------------------------------------------------------------
# AC-2: the question_set comment - passed to both Jev calls, no external
# skill assignment
# ---------------------------------------------------------------------------

OLD_EXTERNAL_ASSIGNMENT_PATTERN = re.compile(r"owned by.{0,60}skill", re.IGNORECASE)
PASSED_TO_BOTH_PATTERN = re.compile(r"passed to both Jev calls")
DESCRIPTION_ONLY_PATTERN = re.compile(r"description-only")
FINAL_CALL_PATTERN = re.compile(r"final call")


def flatten_comment_text(section_text):
    """Collapse the section's lines into one whitespace-normalized string,
    stripping each comment line's leading '#' marker, so a phrase that a
    banner comment wraps across two source lines is still found as one
    contiguous run (a raw-text check must not depend on where the author
    happened to break the line)."""
    cleaned = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped:
            cleaned.append(stripped)
    return " ".join(cleaned)


class TestQuestionSetCommentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full_text = TIER_RULES_PATH.read_text(encoding="utf-8")
        cls.section_text = extract_banner_section(cls.full_text, "question_set")
        cls.flat_text = flatten_comment_text(cls.section_text)

    def test_section_was_located_and_is_non_empty(self):
        # Non-vacuity guard for every check below: the section text must
        # actually have been found before any positive/negative assertion
        # about its content is meaningful.
        self.assertGreater(len(self.section_text.strip()), 0)
        self.assertIn("question_set:", self.section_text)

    def test_states_descriptions_passed_to_both_jev_calls(self):
        self.assertRegex(self.flat_text, PASSED_TO_BOTH_PATTERN)
        self.assertRegex(self.flat_text, DESCRIPTION_ONLY_PATTERN)
        self.assertRegex(self.flat_text, FINAL_CALL_PATTERN)

    def test_passed_to_both_matcher_would_fail_on_a_forged_section_missing_it(self):
        forged = PASSED_TO_BOTH_PATTERN.sub("", self.flat_text)
        self.assertNotRegex(forged, PASSED_TO_BOTH_PATTERN)
        # Non-vacuity: the real section does state it.
        self.assertRegex(self.flat_text, PASSED_TO_BOTH_PATTERN)

    def test_no_longer_assigns_bucket_wording_to_an_external_skill(self):
        self.assertIsNone(OLD_EXTERNAL_ASSIGNMENT_PATTERN.search(self.flat_text))

    def test_external_assignment_matcher_fires_on_the_old_pre_task_comment(self):
        # Non-vacuity + negative proof: the OLD comment this task replaced
        # ("...are owned by the two skills named above...") must be
        # detected by the same pattern, proving the checker actually
        # discriminates rather than passing vacuously.
        old_comment = (
            "  # Question wording, the System One/Two model choice, and any\n"
            "  # model-behaviour guidance are owned by the two skills named\n"
            "  # above. Neither is reproduced here.\n"
        )
        self.assertIsNotNone(OLD_EXTERNAL_ASSIGNMENT_PATTERN.search(old_comment))


# ---------------------------------------------------------------------------
# AC-3 (TS-10): no long line of the question_set section duplicated
# verbatim from either external skill document
# ---------------------------------------------------------------------------

MIN_DUP_LINE_LEN_AC3 = 30


def normalized_lines(text, min_len):
    return [
        " ".join(line.split())
        for line in text.splitlines()
        if len(" ".join(line.split())) >= min_len
    ]


class TestQuestionSetNotDuplicatedFromExternalDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full_text = TIER_RULES_PATH.read_text(encoding="utf-8")
        section_text = extract_banner_section(full_text, "question_set")
        cls.section_lines = normalized_lines(section_text, MIN_DUP_LINE_LEN_AC3)

    def test_non_vacuity_section_has_at_least_one_long_line(self):
        self.assertGreater(len(self.section_lines), 0)

    def test_no_long_line_duplicated_from_jev_skill_doc(self):
        if not JEV_SKILL_DOC.is_file():
            self.skipTest(f"{JEV_SKILL_DOC} not readable in this environment")
        jev_text = " ".join(JEV_SKILL_DOC.read_text(encoding="utf-8").split())
        offenders = [line for line in self.section_lines if line in jev_text]
        self.assertEqual(
            offenders, [], f"lines duplicated verbatim from the jev skill doc: {offenders}"
        )

    def test_no_long_line_duplicated_from_typesafe_skill_doc(self):
        docs = find_typesafe_skill_docs()
        if not docs:
            self.skipTest("typesafe-ai skill SKILL.md not readable in this environment")
        for doc in docs:
            with self.subTest(doc=str(doc)):
                doc_text = " ".join(doc.read_text(encoding="utf-8").split())
                offenders = [line for line in self.section_lines if line in doc_text]
                self.assertEqual(
                    offenders,
                    [],
                    f"lines duplicated verbatim from {doc}: {offenders}",
                )

    def test_duplication_matcher_fires_on_a_line_copied_from_the_jev_doc(self):
        # Negative proof: a forged section line copied verbatim from the
        # fixture document must be caught by the same matcher.
        if not JEV_SKILL_DOC.is_file():
            self.skipTest(f"{JEV_SKILL_DOC} not readable in this environment")
        jev_lines = normalized_lines(
            JEV_SKILL_DOC.read_text(encoding="utf-8"), MIN_DUP_LINE_LEN_AC3
        )
        self.assertGreater(len(jev_lines), 0, "fixture doc has no line long enough to copy")
        forged_section_lines = self.section_lines + [jev_lines[0]]
        jev_text = " ".join(JEV_SKILL_DOC.read_text(encoding="utf-8").split())
        offenders = [line for line in forged_section_lines if line in jev_text]
        self.assertNotEqual(offenders, [])


# ---------------------------------------------------------------------------
# AC-4: codex_output_schema's seven new fact fields, each with the exact
# listed value vocabulary
# ---------------------------------------------------------------------------


class TestCodexFactFieldsVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)
        cls.fact_fields = cls.rules["codex_output_schema"]["fact_fields"]

    def test_all_seven_new_fields_present(self):
        self.assertEqual(set(self.fact_fields.keys()), set(NEW_FACT_FIELDS.keys()))

    def test_enum_fields_have_exactly_the_listed_values(self):
        for name, spec in NEW_FACT_FIELDS.items():
            if spec["kind"] != "enum":
                continue
            with self.subTest(field=name):
                actual = self.fact_fields[name].get("values")
                self.assertEqual(list(actual), spec["values"])

    def test_typed_fields_declare_the_correct_type(self):
        for name, spec in NEW_FACT_FIELDS.items():
            if spec["kind"] != "type":
                continue
            with self.subTest(field=name):
                self.assertEqual(self.fact_fields[name].get("type"), spec["type"])

    def test_field_set_matcher_would_fail_on_a_forged_missing_field(self):
        forged = dict(self.fact_fields)
        del forged["changes_behavior"]
        self.assertNotEqual(set(forged.keys()), set(NEW_FACT_FIELDS.keys()))
        # Non-vacuity: the real structure does satisfy the check.
        self.assertEqual(set(self.fact_fields.keys()), set(NEW_FACT_FIELDS.keys()))

    def test_enum_values_matcher_would_fail_on_a_forged_extra_value(self):
        forged = list(self.fact_fields["body_change_kind"]["values"]) + ["extra_value"]
        self.assertNotEqual(forged, NEW_FACT_FIELDS["body_change_kind"]["values"])
        # Non-vacuity: the real values do match exactly.
        self.assertEqual(
            list(self.fact_fields["body_change_kind"]["values"]),
            NEW_FACT_FIELDS["body_change_kind"]["values"],
        )

    def test_typed_field_matcher_would_fail_on_a_forged_wrong_type(self):
        self.assertNotEqual("string", NEW_FACT_FIELDS["changes_behavior"]["type"])
        # Non-vacuity: the real declared type does match "boolean".
        self.assertEqual(
            self.fact_fields["changes_behavior"]["type"],
            NEW_FACT_FIELDS["changes_behavior"]["type"],
        )


# ---------------------------------------------------------------------------
# AC-5: every pre-existing codex_output_schema field name still present;
# the section states Codex reports facts only
# ---------------------------------------------------------------------------


class TestCodexOutputSchemaBackwardCompatible(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)
        cls.schema = cls.rules["codex_output_schema"]

    def test_every_pre_existing_field_name_still_present(self):
        fields = self.schema.get("fields")
        self.assertIsInstance(fields, list)
        for name in PRE_EXISTING_CODEX_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, fields)

    def test_pre_existing_field_matcher_would_fail_on_a_forged_removal(self):
        forged = [f for f in self.schema["fields"] if f != "files_expected"]
        self.assertNotIn("files_expected", forged)
        # Non-vacuity: the real list does still carry it.
        self.assertIn("files_expected", self.schema["fields"])

    def test_section_states_codex_reports_facts_only(self):
        role_text = self.schema.get("role", "")
        self.assertRegex(role_text, r"facts")
        self.assertRegex(role_text, r"no size judgment")
        self.assertRegex(role_text, r"no tier judgment")

    def test_facts_only_matcher_would_fail_on_a_forged_role_naming_a_judgment(self):
        forged = "Codex decides the tier directly."
        self.assertNotRegex(forged, r"no tier judgment")
        # Non-vacuity: the real role text does state the exclusion.
        self.assertRegex(self.schema.get("role", ""), r"no tier judgment")


# ---------------------------------------------------------------------------
# AC-6: this module's own stdlib-only imports (mirrors test_tier_rules.py's
# AC-7 convention for the sibling task's test module)
# ---------------------------------------------------------------------------


class TestThisModuleImportsOnlyTheStandardLibrary(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = THIS_TEST_FILE.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()

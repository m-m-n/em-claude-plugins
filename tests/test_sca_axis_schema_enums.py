"""Tests for task0001 (review-sca-axis): review-output-schema.json's
additive enum widening -- root `source` gains `tool`, finding `category`
gains `vulnerability` -- with the invariance side pinned explicitly.

Covers task0001 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0001.md):

- AC-8: review-output-schema.json parses as JSON; its root `source` enum
  contains `tool` while still containing `claude`, `codex` and `litellm`;
  its finding `category` enum contains `vulnerability` while still
  containing all six existing perspective categories.
- AC-9: the schema's invariance side holds -- the root `required` list, the
  finding `required` list, both `additionalProperties` flags and the
  `severity` enum are unchanged from their pre-change values -- and
  `tests/test_reviewer_roles_protocol.py`'s `FROZEN_SOURCE_ENUM` is the
  four-value list `claude`, `codex`, `litellm`, `tool` in that order.

Per Test Notes: both enum assertions check FULL expected membership (the
exact resulting list), not just "the new value is present" -- so an edit
that REPLACES an existing value instead of appending is caught.
TestFullMembershipCatchesReplacement proves that assertion style actually
rejects a forged replacement, per tdd-testing discipline (a check that
cannot fail is not a check).

The "every other assertion in that module untouched" half of AC-9 is not
re-asserted here (this module has no way to introspect a sibling module's
other assertions without importing it): it is what the pre-existing
`TestReviewOutputSchemaCategoryWidened` class in
tests/test_reviewer_roles_protocol.py already checks against the SAME
widened schema, and that whole module is part of every run of `python3 -m
unittest discover -s tests` this task's own definition of done requires.
"""

import ast
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "review-output-schema.json"
REVIEWER_ROLES_TEST_PATH = REPO_ROOT / "tests" / "test_reviewer_roles_protocol.py"

EXPECTED_SOURCE_ENUM = ["claude", "codex", "litellm", "tool"]
EXPECTED_CATEGORY_ENUM = [
    "security",
    "performance",
    "architecture",
    "spec",
    "comprehensive",
    "license",
    "vulnerability",
]
EXPECTED_ROOT_REQUIRED = ["findings", "summary", "skipped", "skip_reason", "source"]
EXPECTED_FINDING_REQUIRED = [
    "file",
    "line",
    "line_end",
    "severity",
    "category",
    "title",
    "description",
    "suggestion",
]
EXPECTED_SEVERITY_ENUM = ["critical", "high", "medium"]


def _load_schema():
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    return text, json.loads(text)


class TestSchemaEnumsWidenedAdditively(unittest.TestCase):
    """AC-8: `source`/`category` enums widened; each equals the full
    expected list (pre-existing values plus the new one, in order) -- not
    merely "contains" the new value, so a replacement would be caught."""

    @classmethod
    def setUpClass(cls):
        cls.raw, cls.data = _load_schema()

    def test_schema_parses_as_json(self):
        # setUpClass already parsed it; re-parse here so THIS test fails
        # (not an error at class setup) on malformed JSON.
        json.loads(self.raw)

    def test_source_enum_is_exactly_four_values_tool_appended(self):
        self.assertEqual(
            EXPECTED_SOURCE_ENUM,
            self.data["properties"]["source"]["enum"],
            "AC-8: root source enum must be claude/codex/litellm/tool, in "
            "that order",
        )

    def test_category_enum_is_exactly_seven_values_vulnerability_appended(self):
        category_enum = self.data["properties"]["findings"]["items"]["properties"][
            "category"
        ]["enum"]
        self.assertEqual(
            EXPECTED_CATEGORY_ENUM,
            category_enum,
            "AC-8: finding category enum must keep all six existing "
            "perspectives plus vulnerability, in that order",
        )


class TestSchemaInvarianceSideUnchanged(unittest.TestCase):
    """AC-9: required lists, additionalProperties flags and the severity
    enum are byte-for-byte their pre-change values."""

    @classmethod
    def setUpClass(cls):
        _, cls.data = _load_schema()

    def test_root_required_unchanged(self):
        self.assertEqual(EXPECTED_ROOT_REQUIRED, self.data["required"])

    def test_root_additional_properties_unchanged(self):
        self.assertFalse(self.data["additionalProperties"])

    def test_finding_required_unchanged(self):
        finding_schema = self.data["properties"]["findings"]["items"]
        self.assertEqual(EXPECTED_FINDING_REQUIRED, finding_schema["required"])

    def test_finding_additional_properties_unchanged(self):
        finding_schema = self.data["properties"]["findings"]["items"]
        self.assertFalse(finding_schema["additionalProperties"])

    def test_severity_enum_unchanged(self):
        severity_enum = self.data["properties"]["findings"]["items"]["properties"][
            "severity"
        ]["enum"]
        self.assertEqual(EXPECTED_SEVERITY_ENUM, severity_enum)


class TestFrozenSourceEnumPinIsFourValueList(unittest.TestCase):
    """AC-9: the sibling module's FROZEN_SOURCE_ENUM constant is literally
    the four-value list, in order -- read as text and parsed with
    `ast.literal_eval` (never imported, so this module's own imports stay
    standard-library-only per NFR7 / this feature's Test Notes)."""

    def test_frozen_source_enum_constant_is_four_value_list(self):
        text = REVIEWER_ROLES_TEST_PATH.read_text(encoding="utf-8")
        match = re.search(r"^FROZEN_SOURCE_ENUM\s*=\s*(\[[^\]]*\])", text, re.MULTILINE)
        self.assertIsNotNone(match, "FROZEN_SOURCE_ENUM constant must be present")
        value = ast.literal_eval(match.group(1))
        self.assertEqual(["claude", "codex", "litellm", "tool"], value)


class TestFullMembershipCatchesReplacement(unittest.TestCase):
    """Regression proof (tdd-testing discipline): the full-expected-list
    assertion style used above actually rejects a REPLACEMENT (tool
    replacing litellm, not appended alongside it), not just a missing
    value."""

    def test_replacement_enum_is_rejected_by_full_list_equality(self):
        replaced = ["claude", "codex", "tool"]  # litellm dropped, not appended
        self.assertNotEqual(EXPECTED_SOURCE_ENUM, replaced)

    def test_genuine_append_is_accepted_by_full_list_equality(self):
        appended = ["claude", "codex", "litellm", "tool"]
        self.assertEqual(EXPECTED_SOURCE_ENUM, appended)


if __name__ == "__main__":
    unittest.main()

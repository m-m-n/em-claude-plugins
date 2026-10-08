"""Tests for task0001 (security-review-repro-steps): the `reproduction`
field in the reviewer output contract of both plugins.

Covers task0001 Acceptance Criteria
(feature-docs/security-review-repro-steps/tasks/task0001.md):

- AC-1: both `review-output-schema.json` files parse as JSON; the finding
  object's `properties.reproduction` accepts exactly a string or null
  (written in the any-of form the schema already uses for its nullable
  fields); finding `required` is the existing eight names in their existing
  order followed by `reproduction`; the finding and root
  `additionalProperties` flags are both false.
- AC-2: in each schema, root `required`, the severity enum, the category
  enum and the root source enum equal that file's pre-change values.
- AC-3: in both `review-protocol.md` files, the Output Schema section's
  example finding contains `reproduction` after `suggestion`, and its Rules
  list states the four reproduction rules (always present; security =
  steps or confirmation method naming input, path and observable result,
  null only when neither can be given; every other perspective always null;
  empty or whitespace-only treated as null).
- AC-4: every finding returned by `_build_finding` in
  `em-workflow/scripts/scan-dependencies.py` has the key `reproduction`
  with value null, and carries exactly the schema's finding properties.
- AC-6: this module covers AC-1 to AC-4 for both plugins and imports only
  standard-library modules.

Comparisons are by full equality (never membership) so a replacement of an
existing value is caught. Phrase checks are whitespace-normalized and scoped
to the Output Schema section (the text between the `## Output Schema`
heading and the next `## ` heading). The `Test...CatchesForgery` classes
prove each assertion helper rejects forged input, per tdd-testing (a check
that cannot fail is not a check).
"""

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGINS = ("em-workflow", "em-review")

SCAN_SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _schema_path(plugin):
    return REPO_ROOT / plugin / "references" / "review-output-schema.json"


def _protocol_path(plugin):
    return REPO_ROOT / plugin / "references" / "review-protocol.md"


# Pre-change values of each schema file (the invariance side of AC-2).
EXISTING_FINDING_REQUIRED = [
    "file",
    "line",
    "line_end",
    "severity",
    "category",
    "title",
    "description",
    "suggestion",
]
EXPECTED_FINDING_REQUIRED = EXISTING_FINDING_REQUIRED + ["reproduction"]
EXPECTED_ROOT_REQUIRED = ["findings", "summary", "skipped", "skip_reason", "source"]
EXPECTED_SEVERITY_ENUM = ["critical", "high", "medium"]
EXPECTED_CATEGORY_ENUM = {
    "em-workflow": [
        "security",
        "performance",
        "architecture",
        "spec",
        "comprehensive",
        "license",
        "vulnerability",
    ],
    "em-review": [
        "security",
        "performance",
        "architecture",
        "spec",
        "comprehensive",
    ],
}
EXPECTED_SOURCE_ENUM = {
    "em-workflow": ["claude", "codex", "litellm", "tool"],
    "em-review": ["claude", "codex", "litellm"],
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _finding_schema(schema):
    return schema["properties"]["findings"]["items"]


# ---------------------------------------------------------------------------
# AC-1 / AC-2: schema assertions, written as helpers over a schema dict so
# the forgery tests below can run them against mutated copies.
# ---------------------------------------------------------------------------


def assert_reproduction_property(testcase, schema):
    """AC-1: `properties.reproduction` accepts exactly a string or null."""
    properties = _finding_schema(schema)["properties"]
    testcase.assertIn("reproduction", properties)
    prop = properties["reproduction"]
    testcase.assertEqual(["anyOf"], list(prop.keys()))
    testcase.assertEqual(
        [{"type": "string"}, {"type": "null"}],
        prop["anyOf"],
        "AC-1: reproduction must accept exactly a string or null",
    )
    # Same any-of form the schema already uses for its nullable fields.
    testcase.assertEqual(
        prop,
        schema["properties"]["skip_reason"],
        "AC-1: reproduction uses the same any-of form as skip_reason",
    )


def assert_reproduction_property_after_suggestion(testcase, schema):
    names = list(_finding_schema(schema)["properties"].keys())
    testcase.assertEqual("suggestion", names[-2])
    testcase.assertEqual("reproduction", names[-1])


def assert_finding_required(testcase, schema):
    testcase.assertEqual(
        EXPECTED_FINDING_REQUIRED,
        _finding_schema(schema)["required"],
        "AC-1: finding required must be the existing eight names in their "
        "existing order followed by reproduction",
    )


def assert_additional_properties_false(testcase, schema):
    testcase.assertIs(False, schema["additionalProperties"])
    testcase.assertIs(False, _finding_schema(schema)["additionalProperties"])


def assert_invariants_unchanged(testcase, plugin, schema):
    """AC-2: everything this task must not touch."""
    testcase.assertEqual(EXPECTED_ROOT_REQUIRED, schema["required"])
    properties = _finding_schema(schema)["properties"]
    testcase.assertEqual(EXPECTED_SEVERITY_ENUM, properties["severity"]["enum"])
    testcase.assertEqual(
        EXPECTED_CATEGORY_ENUM[plugin], properties["category"]["enum"]
    )
    testcase.assertEqual(
        EXPECTED_SOURCE_ENUM[plugin], schema["properties"]["source"]["enum"]
    )


class TestReproductionSchemaProperty(unittest.TestCase):
    """AC-1 for both plugins."""

    def test_schemas_parse_as_json(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                json.loads(_read(_schema_path(plugin)))

    def test_reproduction_accepts_exactly_string_or_null(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                schema = json.loads(_read(_schema_path(plugin)))
                assert_reproduction_property(self, schema)

    def test_reproduction_property_is_placed_after_suggestion(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                schema = json.loads(_read(_schema_path(plugin)))
                assert_reproduction_property_after_suggestion(self, schema)

    def test_finding_required_is_existing_eight_then_reproduction(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                schema = json.loads(_read(_schema_path(plugin)))
                assert_finding_required(self, schema)

    def test_finding_and_root_additional_properties_are_false(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                schema = json.loads(_read(_schema_path(plugin)))
                assert_additional_properties_false(self, schema)

    def test_added_lines_are_identical_in_both_files(self):
        """The added property line and required entry are identical in both
        plugins (Parallel-plugin parity)."""
        property_lines = []
        required_lines = []
        for plugin in PLUGINS:
            lines = _read(_schema_path(plugin)).splitlines()
            property_lines.append(
                [l for l in lines if l.lstrip().startswith('"reproduction"')]
            )
            required_lines.append(
                [l for l in lines if l.lstrip().startswith('"required": ["file"')]
            )
        self.assertEqual(1, len(property_lines[0]))
        self.assertEqual(property_lines[0], property_lines[1])
        self.assertEqual(1, len(required_lines[0]))
        self.assertEqual(required_lines[0], required_lines[1])


class TestSchemaInvariantsUnchanged(unittest.TestCase):
    """AC-2: root required, severity / category / source enums are each
    file's pre-change values."""

    def test_invariants_hold_in_both_schemas(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                schema = json.loads(_read(_schema_path(plugin)))
                assert_invariants_unchanged(self, plugin, schema)

    def test_existing_per_plugin_differences_are_kept(self):
        wf = json.loads(_read(_schema_path("em-workflow")))
        rv = json.loads(_read(_schema_path("em-review")))
        self.assertEqual(7, len(_finding_schema(wf)["properties"]["category"]["enum"]))
        self.assertEqual(4, len(wf["properties"]["source"]["enum"]))
        self.assertEqual(5, len(_finding_schema(rv)["properties"]["category"]["enum"]))
        self.assertEqual(3, len(rv["properties"]["source"]["enum"]))


class TestSchemaAssertionsCatchForgery(unittest.TestCase):
    """Self-check: each helper above rejects a forged schema."""

    @classmethod
    def setUpClass(cls):
        cls.good = json.loads(_read(_schema_path("em-workflow")))

    def _forge(self):
        return copy.deepcopy(self.good)

    def test_schema_lacking_reproduction_in_required_fails(self):
        forged = self._forge()
        _finding_schema(forged)["required"].remove("reproduction")
        with self.assertRaises(AssertionError):
            assert_finding_required(self, forged)

    def test_required_in_wrong_order_fails(self):
        forged = self._forge()
        req = _finding_schema(forged)["required"]
        req[-1], req[-2] = req[-2], req[-1]
        with self.assertRaises(AssertionError):
            assert_finding_required(self, forged)

    def test_schema_lacking_reproduction_property_fails(self):
        forged = self._forge()
        del _finding_schema(forged)["properties"]["reproduction"]
        with self.assertRaises(AssertionError):
            assert_reproduction_property(self, forged)

    def test_string_only_reproduction_fails(self):
        forged = self._forge()
        _finding_schema(forged)["properties"]["reproduction"] = {"type": "string"}
        with self.assertRaises(AssertionError):
            assert_reproduction_property(self, forged)

    def test_reproduction_accepting_extra_type_fails(self):
        forged = self._forge()
        _finding_schema(forged)["properties"]["reproduction"] = {
            "anyOf": [{"type": "string"}, {"type": "null"}, {"type": "integer"}]
        }
        with self.assertRaises(AssertionError):
            assert_reproduction_property(self, forged)

    def test_reproduction_before_suggestion_fails(self):
        forged = self._forge()
        props = _finding_schema(forged)["properties"]
        reordered = {k: v for k, v in props.items() if k != "suggestion"}
        reordered["suggestion"] = props["suggestion"]
        _finding_schema(forged)["properties"] = reordered
        with self.assertRaises(AssertionError):
            assert_reproduction_property_after_suggestion(self, forged)

    def test_open_finding_additional_properties_fails(self):
        forged = self._forge()
        _finding_schema(forged)["additionalProperties"] = True
        with self.assertRaises(AssertionError):
            assert_additional_properties_false(self, forged)

    def test_open_root_additional_properties_fails(self):
        forged = self._forge()
        forged["additionalProperties"] = True
        with self.assertRaises(AssertionError):
            assert_additional_properties_false(self, forged)

    def test_replaced_category_value_fails(self):
        forged = self._forge()
        enum = _finding_schema(forged)["properties"]["category"]["enum"]
        enum[0] = "sec"
        with self.assertRaises(AssertionError):
            assert_invariants_unchanged(self, "em-workflow", forged)

    def test_changed_root_required_fails(self):
        forged = self._forge()
        forged["required"] = forged["required"] + ["extra"]
        with self.assertRaises(AssertionError):
            assert_invariants_unchanged(self, "em-workflow", forged)

    def test_changed_source_enum_fails(self):
        forged = self._forge()
        forged["properties"]["source"]["enum"].remove("tool")
        with self.assertRaises(AssertionError):
            assert_invariants_unchanged(self, "em-workflow", forged)

    def test_changed_severity_enum_fails(self):
        forged = self._forge()
        _finding_schema(forged)["properties"]["severity"]["enum"].append("low")
        with self.assertRaises(AssertionError):
            assert_invariants_unchanged(self, "em-workflow", forged)


# ---------------------------------------------------------------------------
# AC-3: review-protocol.md Output Schema section
# ---------------------------------------------------------------------------


def _normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_output_schema_section(text):
    """The text between the `## Output Schema` heading and the next `## `
    heading (a `### ` subsection stays inside the section)."""
    match = re.search(r"^## Output Schema\s*$", text, re.MULTILINE)
    if match is None:
        raise AssertionError("missing `## Output Schema` heading")
    rest = text[match.end():]
    following = re.search(r"^## ", rest, re.MULTILINE)
    return rest if following is None else rest[: following.start()]


def example_finding_keys(section):
    """Keys of the first finding object in the section's JSON example."""
    block = re.search(r"```json\n(.*?)\n```", section, re.DOTALL)
    if block is None:
        raise AssertionError("Output Schema section has no json example")
    example = json.loads(block.group(1))
    return list(example["findings"][0].keys())


def rules_bullets(section):
    """Bullets of the `Rules:` list, whitespace-normalized, one string per
    bullet (the list ends at the first `### ` subsection heading)."""
    start = re.search(r"^Rules:\s*$", section, re.MULTILINE)
    if start is None:
        raise AssertionError("Output Schema section has no `Rules:` list")
    body = section[start.end():]
    end = re.search(r"^### ", body, re.MULTILINE)
    if end is not None:
        body = body[: end.start()]
    bullets = []
    for line in body.splitlines():
        if line.startswith("- "):
            bullets.append(line[2:])
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + line.strip()
    return [_normalize_whitespace(b) for b in bullets]


# Each rule: phrases that must co-occur inside ONE bullet that mentions
# `reproduction`, so scattered phrases elsewhere cannot satisfy a rule.
REPRODUCTION_RULES = {
    "always present": [
        "`reproduction` is one of the finding fields that MUST always be present",
    ],
    "security perspective": [
        "`security`",
        "steps that reproduce the finding, or an equivalent confirmation method",
        "naming the input, the path by which it reaches the code, and the "
        "observable result",
        "`null` only when neither can be given",
    ],
    "every other perspective": [
        "every other perspective",
        "always `null`",
    ],
    "empty or whitespace-only": [
        "empty or whitespace-only",
        "treated as `null`",
        "no steps",
    ],
}


def assert_reproduction_rules(testcase, section):
    bullets = [b for b in rules_bullets(section) if "`reproduction`" in b]
    for name, phrases in REPRODUCTION_RULES.items():
        testcase.assertTrue(
            any(all(p in b for p in phrases) for b in bullets),
            f"AC-3: no single Rules bullet states the {name!r} rule "
            f"(phrases: {phrases})",
        )


class TestProtocolOutputSchemaSection(unittest.TestCase):
    """AC-3 for both plugins."""

    def _section(self, plugin):
        return extract_output_schema_section(_read(_protocol_path(plugin)))

    def test_example_finding_has_reproduction_after_suggestion(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                keys = example_finding_keys(self._section(plugin))
                self.assertEqual(
                    EXISTING_FINDING_REQUIRED + ["reproduction"],
                    keys,
                    "AC-3: the example finding shows reproduction after "
                    "suggestion",
                )

    def test_rules_state_the_four_reproduction_rules(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                assert_reproduction_rules(self, self._section(plugin))

    def test_reproduction_rules_text_is_identical_in_both_protocols(self):
        wf, rv = (
            [b for b in rules_bullets(self._section(p)) if "`reproduction`" in b]
            for p in PLUGINS
        )
        self.assertTrue(wf)
        self.assertEqual(wf, rv)

    def test_example_reproduction_line_is_identical_in_both_protocols(self):
        lines = []
        for plugin in PLUGINS:
            section = self._section(plugin)
            lines.append(
                [l for l in section.splitlines() if l.lstrip().startswith('"reproduction"')]
            )
        self.assertEqual(1, len(lines[0]))
        self.assertEqual(lines[0], lines[1])


class TestProtocolAssertionsCatchForgery(unittest.TestCase):
    """Self-check: the AC-3 helpers reject forged Output Schema sections."""

    @classmethod
    def setUpClass(cls):
        cls.good = extract_output_schema_section(_read(_protocol_path("em-workflow")))

    def test_section_without_reproduction_in_example_fails(self):
        forged = re.sub(r',\n\s*"reproduction":[^\n]*', "", self.good)
        self.assertNotEqual(self.good, forged)
        keys = example_finding_keys(forged)
        self.assertNotEqual(EXISTING_FINDING_REQUIRED + ["reproduction"], keys)

    def test_section_without_any_reproduction_rule_fails(self):
        forged = "\n".join(
            l for l in self.good.splitlines() if "`reproduction`" not in l
        )
        with self.assertRaises(AssertionError):
            assert_reproduction_rules(self, forged)

    def test_section_missing_the_other_perspective_rule_fails(self):
        forged = self.good.replace("every other perspective", "some perspective")
        self.assertNotEqual(self.good, forged)
        with self.assertRaises(AssertionError):
            assert_reproduction_rules(self, forged)

    def test_section_missing_the_whitespace_rule_fails(self):
        forged = self.good.replace("whitespace-only", "blank")
        self.assertNotEqual(self.good, forged)
        with self.assertRaises(AssertionError):
            assert_reproduction_rules(self, forged)

    def test_rule_phrases_scattered_over_separate_bullets_fail(self):
        scattered = (
            "Rules:\n\n"
            "- `reproduction` is one of the finding fields that MUST always be present.\n"
            "- security steps that reproduce the finding, or an equivalent "
            "confirmation method.\n"
            "- naming the input, the path by which it reaches the code, and "
            "the observable result; `null` only when neither can be given.\n"
            "- every other perspective: always `null`.\n"
            "- empty or whitespace-only is treated as `null` (no steps).\n"
        )
        with self.assertRaises(AssertionError):
            assert_reproduction_rules(self, scattered)

    def test_extract_requires_the_heading(self):
        with self.assertRaises(AssertionError):
            extract_output_schema_section("## Something Else\n\nbody\n")


# ---------------------------------------------------------------------------
# AC-4: the dependency-vulnerability scanner's finding builder
# ---------------------------------------------------------------------------


def _load_scanner():
    spec = importlib.util.spec_from_file_location("scan_dependencies", SCAN_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_scanner()

BUILD_FINDING_CASES = [
    (
        "full arguments",
        dict(
            manifest_file="package.json",
            package="left-pad",
            advisory_id="GHSA-xxxx-yyyy-zzzz",
            title="Prototype pollution",
            affected_range="<1.3.0",
            fixed_version="1.3.0",
            summary="An attacker can pollute the prototype.",
            severity="high",
        ),
    ),
    (
        "no fixed version, no range, no summary",
        dict(
            manifest_file="Cargo.toml",
            package="serde",
            advisory_id="RUSTSEC-2024-0001",
            title="Unsound deserialization",
            affected_range=None,
            fixed_version=None,
            summary=None,
            severity="critical",
        ),
    ),
    (
        "whitespace-laden title",
        dict(
            manifest_file="requirements.txt",
            package="requests",
            advisory_id="PYSEC-2023-1",
            title="  Multi\nline \t title  ",
            affected_range="<2.0",
            fixed_version="2.0",
            summary="",
            severity="high",
        ),
    ),
]


def assert_finding_matches_schema_properties(testcase, finding, schema):
    finding_schema = _finding_schema(schema)
    testcase.assertEqual(
        set(finding_schema["properties"].keys()),
        set(finding.keys()),
        "AC-4: the finding carries exactly the schema's finding properties",
    )
    for key in finding_schema["required"]:
        testcase.assertIn(key, finding)


def assert_reproduction_is_null(testcase, finding):
    testcase.assertIn("reproduction", finding)
    testcase.assertIsNone(finding["reproduction"])


class TestScannerFindingBuilderEmitsNullReproduction(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(_read(_schema_path("em-workflow")))

    def test_every_built_finding_has_reproduction_null(self):
        for label, kwargs in BUILD_FINDING_CASES:
            with self.subTest(case=label):
                assert_reproduction_is_null(self, SCAN._build_finding(**kwargs))

    def test_built_finding_carries_exactly_the_schema_properties(self):
        for label, kwargs in BUILD_FINDING_CASES:
            with self.subTest(case=label):
                assert_finding_matches_schema_properties(
                    self, SCAN._build_finding(**kwargs), self.schema
                )

    def test_other_finding_fields_are_unchanged(self):
        label, kwargs = BUILD_FINDING_CASES[0]
        finding = SCAN._build_finding(**kwargs)
        self.assertEqual("package.json", finding["file"])
        self.assertIsNone(finding["line"])
        self.assertIsNone(finding["line_end"])
        self.assertEqual("high", finding["severity"])
        self.assertEqual("vulnerability", finding["category"])
        self.assertEqual(
            "left-pad: GHSA-xxxx-yyyy-zzzz — Prototype pollution",
            finding["title"],
        )
        self.assertEqual(
            "affected: <1.3.0 | fixed: 1.3.0 | An attacker can pollute the prototype.",
            finding["description"],
        )
        self.assertEqual(
            "Update left-pad to 1.3.0 to resolve GHSA-xxxx-yyyy-zzzz.",
            finding["suggestion"],
        )

    def test_finding_is_json_serializable(self):
        label, kwargs = BUILD_FINDING_CASES[0]
        decoded = json.loads(json.dumps(SCAN._build_finding(**kwargs)))
        self.assertIn("reproduction", decoded)
        self.assertIsNone(decoded["reproduction"])


class TestScannerAssertionsCatchForgery(unittest.TestCase):
    """Self-check: the AC-4 helpers reject a finding without `reproduction`
    or with a non-null value."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(_read(_schema_path("em-workflow")))
        label, kwargs = BUILD_FINDING_CASES[0]
        cls.good = SCAN._build_finding(**kwargs)

    def test_finding_without_reproduction_key_fails(self):
        forged = dict(self.good)
        del forged["reproduction"]
        with self.assertRaises(AssertionError):
            assert_reproduction_is_null(self, forged)
        with self.assertRaises(AssertionError):
            assert_finding_matches_schema_properties(self, forged, self.schema)

    def test_finding_with_string_reproduction_fails(self):
        forged = dict(self.good, reproduction="1. send input")
        with self.assertRaises(AssertionError):
            assert_reproduction_is_null(self, forged)

    def test_finding_with_extra_property_fails(self):
        forged = dict(self.good, unexpected=1)
        with self.assertRaises(AssertionError):
            assert_finding_matches_schema_properties(self, forged, self.schema)


# ---------------------------------------------------------------------------
# AC-6: standard-library-only imports
# ---------------------------------------------------------------------------


class TestModuleImportsStandardLibraryOnly(unittest.TestCase):
    def test_imports_are_standard_library(self):
        import ast
        import sys

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported)
        self.assertLessEqual(imported, set(sys.stdlib_module_names))


if __name__ == "__main__":
    unittest.main()

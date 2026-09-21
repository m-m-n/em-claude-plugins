"""Tests for task0008 (task-tier-reduction): the em-workflow plugin version
bump to the next minor value, applied to both distribution registries, and
the whole-suite absence of the retired major/minor literal pin.

Covers task0008 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0008.md):

- AC-5 (NFR4, TS-21): both manifests parse, carry the same version string,
  that string is strictly greater than the pre-change value under
  per-component numeric comparison, and its minor component is greater than
  the pre-change minor component with the major component unchanged.
- AC-6: the other plugin's (em-review) marketplace entry keeps its name,
  author, category and source, and its version is still a dotted numeric
  string asserted by shape, never against a literal.
- AC-7: this module is discovered by `python3 -m unittest discover -s
  tests`, imports only the standard library, and pairs each matcher with a
  negative proof and a non-vacuity guard -- including a case proving the
  comparison is per-component numeric rather than whole-string.
- AC-8 (TS-21): no module under `tests/` asserts the major/minor pair
  against a literal any more -- every module in this repository's `tests/`
  directory is scanned for the retired `assertEqual((major, minor), ...)`
  pattern.

The pre-change baseline (0, 1, 86) is captured from the feature's base
commit (`6c4971e`, `em-workflow/.claude-plugin/plugin.json`), per the task
plan's Test Notes edge case: "the pre-change baseline constant must be
captured from the base commit, not assumed, since sibling features may have
moved it."
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
PLUGIN_MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Captured from the feature's base commit (6c4971e), not assumed -- see the
# Test Notes edge case above.
BASELINE_VERSION = (0, 1, 86)

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array index, the
    marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _parse_version(version):
    """Parse X.Y.Z into (major, minor, patch) ints, or None if not of that
    shape. Returning None (rather than raising) lets callers distinguish a
    parse failure from a comparison failure."""
    match = VERSION_RE.match(version or "")
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_versions_equal(test, version_a, version_b):
    test.assertEqual(version_a, version_b)


def _assert_minor_bump_over_baseline(test, version, baseline=BASELINE_VERSION):
    """AC-5: `version` is strictly greater than `baseline` under
    per-component numeric comparison, its minor component is strictly
    greater than the baseline's, and its major component is unchanged --
    never a raw whole-string comparison."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    test.assertGreater(parts, baseline)
    major, minor, _patch = parts
    base_major, base_minor, _base_patch = baseline
    test.assertEqual(major, base_major, f"major component changed: {version!r} vs baseline {baseline!r}")
    test.assertGreater(minor, base_minor, f"minor component did not advance: {version!r} vs baseline {baseline!r}")


DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def _is_dotted_numeric_version(value):
    """A dotted numeric version string: one or more '.'-separated
    non-negative integers, e.g. "0.5.11"."""
    return isinstance(value, str) and DOTTED_NUMERIC_VERSION_RE.match(value) is not None


EM_REVIEW_NAME = "em-review"
EM_REVIEW_AUTHOR = {"name": "em"}
EM_REVIEW_CATEGORY = "code-review"
EM_REVIEW_SOURCE = "./em-review"


def _assert_em_review_entry_unchanged(test, entry):
    """AC-6: identity fields pinned exactly; the `version` field is asserted
    by shape only -- present and dotted numeric -- never against a literal,
    since em-review's version changes independently of this feature."""
    test.assertEqual(entry.get("name"), EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EM_REVIEW_SOURCE)
    test.assertTrue(
        _is_dotted_numeric_version(entry.get("version")),
        f"em-review version {entry.get('version')!r} is not a dotted numeric string",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-5: the plugin manifest's version is a minor bump over the
    pre-change baseline, and its name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_is_a_minor_bump_over_the_baseline(self):
        _assert_minor_bump_over_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-5: the em-workflow marketplace entry (found by name, not
    position) agrees with the plugin manifest and is a minor bump over the
    baseline."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_entry_version_is_a_minor_bump_over_the_baseline(self):
        _assert_minor_bump_over_baseline(self, self.entry.get("version"))

    def test_entry_version_matches_plugin_manifest(self):
        _assert_versions_equal(self, self.entry.get("version"), self.manifest.get("version"))


class TestOtherPluginEntryUnchanged(unittest.TestCase):
    """AC-6: em-review's marketplace entry keeps its identity fields; its
    version is asserted by shape only, never against a literal."""

    def test_em_review_entry_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_unchanged(self, entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-7: a negative proof per matcher, a non-vacuity guard per matcher,
    and the per-component-numeric trap case."""

    def test_forged_baseline_version_is_well_formed(self):
        baseline_str = ".".join(str(p) for p in BASELINE_VERSION)
        self.assertIsNotNone(_parse_version(baseline_str))

    def test_minor_bump_matcher_rejects_the_baseline_itself(self):
        baseline_str = ".".join(str(p) for p in BASELINE_VERSION)
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, baseline_str)

    def test_minor_bump_matcher_rejects_a_patch_only_bump(self):
        # AC-5 requires the MINOR component to advance, not merely the
        # version to compare greater -- a patch-only bump over the baseline
        # is numerically greater but must still be rejected here.
        patch_only = f"0.1.{BASELINE_VERSION[2] + 1}"
        self.assertGreater(_parse_version(patch_only), BASELINE_VERSION)  # numerically greater...
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, patch_only)  # ...but still rejected

    def test_minor_bump_matcher_rejects_a_major_bump(self):
        # A major bump leaves the major component changed, which this
        # matcher's major-unchanged clause rejects.
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "1.0.0")

    def test_minor_bump_matcher_accepts_the_actual_bump_target(self):
        _assert_minor_bump_over_baseline(self, "0.2.0")  # must not raise

    def test_minor_bump_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "0.2")

    def test_forged_differing_versions_are_both_well_formed(self):
        self.assertIsNotNone(_parse_version("0.2.0"))
        self.assertIsNotNone(_parse_version("0.2.1"))

    def test_equality_matcher_rejects_forged_differing_versions(self):
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, "0.2.0", "0.2.1")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_entry_lookup_succeeds_on_a_present_entry_name(self):
        # Non-vacuity guard for the guard above.
        forged = {"plugins": [{"name": "em-workflow", "version": "9.9.9"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertEqual(entry.get("version"), "9.9.9")

    FORGED_EM_REVIEW_ENTRY = {
        "name": EM_REVIEW_NAME,
        "author": EM_REVIEW_AUTHOR,
        "category": EM_REVIEW_CATEGORY,
        "source": EM_REVIEW_SOURCE,
        "version": "0.5.11",
    }

    def test_em_review_matcher_rejects_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
        ):
            with self.subTest(field=field):
                forged = dict(self.FORGED_EM_REVIEW_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_unchanged(self, forged)

    def test_em_review_matcher_rejects_missing_or_malformed_version(self):
        missing = {k: v for k, v in self.FORGED_EM_REVIEW_ENTRY.items() if k != "version"}
        malformed = dict(self.FORGED_EM_REVIEW_ENTRY, version="not-a-version")
        for forged in (missing, malformed):
            with self.assertRaises(AssertionError):
                _assert_em_review_entry_unchanged(self, forged)

    def test_em_review_matcher_accepts_forged_higher_version(self):
        # AC-6: the matcher never compares the version against a literal.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="99.0.0")
        _assert_em_review_entry_unchanged(self, forged)  # must not raise

    def test_minor_component_comparison_is_numeric_not_lexicographic(self):
        # AC-7's per-component-numeric trap case. As raw strings, "0.10.0"
        # sorts BELOW "0.9.0" (the second character '1' < '9') even though
        # 10 > 9 numerically -- exactly the trap a future double-digit
        # minor component would fall into under a naive string comparison.
        self.assertLess("0.10.0", "0.9.0")
        self.assertGreater(_parse_version("0.10.0"), _parse_version("0.9.0"))
        _assert_minor_bump_over_baseline(self, "0.10.0", baseline=(0, 9, 0))  # must not raise

    def test_parse_version_distinguishes_parse_failure_from_none(self):
        self.assertIsNone(_parse_version("not-a-version"))
        self.assertIsNone(_parse_version(None))
        self.assertIsNotNone(_parse_version("0.2.0"))


# ---------------------------------------------------------------------------
# AC-8 (TS-21): no module under tests/ asserts the major/minor pair against
# a literal (or a named baseline constant) any more.
# ---------------------------------------------------------------------------

# The retired pattern: comparing the parsed (major, minor) 2-tuple via
# assertEqual, regardless of what the right-hand side is (a literal 2-tuple
# such as (0, 1), or a named baseline constant such as BASELINE_MAJOR_MINOR
# or (base_major, base_minor)) -- every one of those forms pins the pair as
# a durable invariant, which is exactly what NFR4 retires. Matched against
# raw source text, mirroring this suite's existing document/text-conformance
# convention (e.g. tests/test_implement_routeback_gate.py's bare-git-line
# scan) rather than parsing the AST.
RETIRED_PATTERN = re.compile(r"assertEqual\(\s*\(major,\s*minor\)\s*,")

THIS_FILE_NAME = Path(__file__).name


def _tests_modules_excluding_self():
    return sorted(p for p in TESTS_DIR.glob("test_*.py") if p.name != THIS_FILE_NAME)


class TestNoModuleUnderTestsPinsMajorMinorLiteral(unittest.TestCase):
    def test_no_module_pins_the_major_minor_pair(self):
        offenders = []
        for path in _tests_modules_excluding_self():
            text = path.read_text(encoding="utf-8")
            if RETIRED_PATTERN.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [], f"modules still pinning major/minor: {offenders}")

    def test_scan_is_non_vacuous(self):
        # Non-vacuity guard: the glob actually finds a substantial number of
        # modules to scan (this repository's tests/ directory is large).
        self.assertGreater(len(_tests_modules_excluding_self()), 100)

    def test_pattern_matcher_detects_a_forged_offender(self):
        forged_literal = "    test.assertEqual((major, minor), (0, 1))\n"
        forged_named = "    test.assertEqual((major, minor), BASELINE_MAJOR_MINOR)\n"
        self.assertIsNotNone(RETIRED_PATTERN.search(forged_literal))
        self.assertIsNotNone(RETIRED_PATTERN.search(forged_named))

    def test_pattern_matcher_does_not_flag_the_replacement_form(self):
        forged_replacement = "    test.assertGreater(parts, (0, 1, BASELINE_PATCH))\n"
        self.assertIsNone(RETIRED_PATTERN.search(forged_replacement))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-7: this new module imports only the standard library."""

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


if __name__ == "__main__":
    unittest.main()

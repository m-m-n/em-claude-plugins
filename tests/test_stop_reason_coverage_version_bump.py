"""Tests for task0004 (stop-reason-coverage): the em-workflow plugin version
bump to a value strictly greater than 0.2.0 in both registries.

Covers task0004 Acceptance Criteria
(feature-docs/stop-reason-coverage/tasks/task0004.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` parses as JSON, its
  `version` reads `0.2.1`, and its `name` reads `em-workflow`.
- AC-2: `.claude-plugin/marketplace.json` parses as JSON. The `em-workflow`
  entry's `version` reads `0.2.1` and equals the manifest's. The `em-review`
  entry is unchanged.
- AC-3: the new baseline matcher accepts the live versions and rejects a
  forged `0.2.0`, with a non-vacuity guard showing the forged value parses.
- AC-4: the new equality matcher accepts the live pair and rejects a forged
  differing pair, with a non-vacuity guard. The module imports the standard
  library only.
- AC-5: `tests/test_batch_stop_contract_version_bump.py` passes unmodified,
  and `python3 -m unittest discover -s tests` passes.

Per IMPLEMENTATION.md D7, the baseline matcher asserts a version strictly
greater than (0, 2, 0) under per-component numeric comparison -- it never
pins the literal `0.2.1`, so a later legitimate bump keeps this module
green. The literal `0.2.1` itself is verified only by the plan's own AC-1 /
AC-2 tests below, which read the live files directly. JSON files are parsed,
never pattern-matched, following the pattern established by
tests/test_batch_stop_contract_version_bump.py.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

BASELINE_VERSION = (0, 2, 0)

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


def _assert_version_past_baseline(test, version, baseline=BASELINE_VERSION):
    """The baseline matcher: durable invariant is a version strictly greater
    than `baseline` under per-component numeric comparison -- never a raw
    whole-string comparison, and never pinned to the literal `0.2.1`."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    test.assertGreater(parts, baseline)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the two registries must report the identical
    version string."""
    test.assertEqual(version_a, version_b)


EM_REVIEW_NAME = "em-review"
EM_REVIEW_AUTHOR = {"name": "em"}
EM_REVIEW_CATEGORY = "code-review"
EM_REVIEW_SOURCE = "./em-review"

DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def _is_dotted_numeric_version(value):
    """A dotted numeric version string: one or more '.'-separated
    non-negative integers, e.g. "0.5.11"."""
    return isinstance(value, str) and DOTTED_NUMERIC_VERSION_RE.match(value) is not None


def _assert_em_review_entry_unchanged(test, entry):
    """AC-2: identity fields pinned exactly; the `version` field is asserted
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
    """AC-1: the plugin manifest parses as JSON, its version is past
    baseline and reads the literal 0.2.1, and its name field reads
    em-workflow."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_version_is_the_literal_bump_target(self):
        # AC-1's literal check: read directly, never pinned by the durable
        # baseline matcher above.
        # abort-docs-commit-precedence/task0001: bumped to 0.2.2, per
        # tests/test_codex_wrapper_fallback_removal_version_bump.py's
        # documented convention for later version bumps.
        self.assertEqual(self.data.get("version"), "0.2.2")

    def test_name_field_reads_em_workflow(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2: the em-workflow marketplace entry parses, its version is past
    baseline, reads the literal 0.2.1, and matches the plugin manifest."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_entry_version_is_the_literal_bump_target(self):
        # abort-docs-commit-precedence/task0001: bumped to 0.2.2.
        self.assertEqual(self.entry.get("version"), "0.2.2")

    def test_entry_version_matches_plugin_manifest(self):
        _assert_versions_equal(self, self.entry.get("version"), self.manifest.get("version"))


class TestOtherPluginEntryUnchanged(unittest.TestCase):
    """AC-2: em-review's marketplace entry is unchanged."""

    def test_em_review_entry_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_unchanged(self, entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-3 / AC-4: a negative proof per matcher, plus a non-vacuity guard
    per matcher showing the forged sample is itself well-formed, so the
    proof exercises the comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.2.0"
    FORGED_VERSION_A = "0.2.1"
    FORGED_VERSION_B = "0.2.2"

    def test_forged_pre_bump_version_is_well_formed(self):
        """Non-vacuity guard for the baseline matcher."""
        self.assertIsNotNone(_parse_version(self.FORGED_PRE_BUMP_VERSION))

    def test_baseline_matcher_rejects_forged_pre_bump_version(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, self.FORGED_PRE_BUMP_VERSION)

    def test_baseline_matcher_accepts_the_live_version(self):
        # AC-3: the matcher accepts the live (bumped) version -- must not raise.
        data = _load_json(PLUGIN_MANIFEST_PATH)
        _assert_version_past_baseline(self, data.get("version"))

    def test_forged_differing_versions_are_both_well_formed(self):
        """Non-vacuity guard for the equality matcher."""
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_A))
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_B))

    def test_equality_matcher_rejects_forged_differing_versions(self):
        self.assertNotEqual(self.FORGED_VERSION_A, self.FORGED_VERSION_B)
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, self.FORGED_VERSION_A, self.FORGED_VERSION_B)

    def test_equality_matcher_accepts_the_live_pair(self):
        # AC-4: the matcher accepts the live registry pair -- must not raise.
        marketplace = _load_json(MARKETPLACE_PATH)
        manifest = _load_json(PLUGIN_MANIFEST_PATH)
        entry = _marketplace_entry(marketplace, "em-workflow")
        _assert_versions_equal(self, entry.get("version"), manifest.get("version"))

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
        # AC-2: the matcher never compares the version against a literal.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="99.0.0")
        _assert_em_review_entry_unchanged(self, forged)  # must not raise

    def test_baseline_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.2")

    def test_parse_version_distinguishes_parse_failure_from_none(self):
        self.assertIsNone(_parse_version("not-a-version"))
        self.assertIsNone(_parse_version(None))
        self.assertIsNotNone(_parse_version("0.2.1"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-4: this new module imports only the standard library."""

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

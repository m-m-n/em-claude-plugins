"""Tests for task0006 (batch-codex-autonomous-decisions): the em-workflow
plugin version bump from 0.1.63 to a value strictly greater, applied to both
registries.

Covers task0006 Acceptance Criteria
(feature-docs/batch-codex-autonomous-decisions/tasks/task0006.md):

- AC-1 (FR23): the plugin manifest's version parses as major.minor.patch,
  keeps the baseline major and minor, and has a patch strictly greater than
  the baseline patch.
- AC-2 (FR23): the marketplace entry for this plugin, looked up by name,
  carries exactly the same version string as the plugin manifest.
- AC-3 (FR23): the other plugin's (em-review) marketplace entry version is
  unchanged from its pre-task value.
- AC-4 (FR23): the marketplace lookup fails loudly when the named entry is
  absent, proved against a forged sample, with a companion assertion showing
  the lookup succeeds when the name is present.
- AC-5 (NFR9): each matcher has a negative proof against forged data plus a
  well-formedness guard, the module imports only the standard library, and
  the full suite passes.

Follows the pattern established by
tests/test_failed_kind_version_bump.py: the "past baseline" comparison is a
dot-separated numeric tuple, not a whole-string comparison, so a future
two-digit patch component still sorts correctly (a naive string comparison
would get "0.1.9" > "0.1.10" backwards).
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

# Pre-task baseline (task0006.md, Design): both registries read 0.1.63
# before this task's edit.
BASELINE_MAJOR_MINOR = (0, 1)
BASELINE_PATCH = 63

# Pre-task snapshot of the em-review marketplace entry's version (AC-3: this
# task must not move it).
EM_REVIEW_VERSION_SNAPSHOT = "0.5.9"

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
    parse failure from a comparison failure -- AC-5's non-vacuity guard
    depends on that distinction."""
    match = VERSION_RE.match(version or "")
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version):
    """major.minor pinned at BASELINE_MAJOR_MINOR, patch strictly greater
    than BASELINE_PATCH. Never a fixed literal comparison of the whole
    version string, so this keeps passing across future unrelated bumps
    instead of going stale (and never a naive string comparison, which
    would sort a two-digit patch backwards)."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = parts
    test.assertEqual((major, minor), BASELINE_MAJOR_MINOR)
    test.assertGreater(patch, BASELINE_PATCH)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the two registries must report the identical
    version string."""
    test.assertEqual(version_a, version_b)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: the plugin manifest's version is past baseline and its name
    field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-1/AC-2/AC-4: the em-workflow marketplace entry, looked up by
    name, is past baseline and matches the plugin manifest exactly."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        # Guard against silently succeeding when the entry is missing.
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_equal(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestOtherMarketplaceEntriesUnchanged(unittest.TestCase):
    """AC-3: this task bumps only the em-workflow entry; the em-review
    entry's version stays at its pre-task snapshot."""

    def test_em_review_entry_version_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        self.assertEqual(entry.get("version"), EM_REVIEW_VERSION_SNAPSHOT)


class TestMarketplaceEntryLookupGuard(unittest.TestCase):
    """AC-4: the lookup fails rather than silently passing when the named
    entry is missing (non-vacuity guard, proved against synthetic data)."""

    def test_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_lookup_succeeds_on_a_present_entry_name(self):
        # Non-vacuity guard for the guard above: the forged sample used to
        # prove failure is well-formed enough that a present name resolves.
        forged = {"plugins": [{"name": "em-workflow", "version": "9.9.9"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertEqual(entry.get("version"), "9.9.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-5 (NFR9): a negative proof per matcher -- one synthetic sample
    left at the pre-task baseline, one where the two registries' (forged)
    versions disagree -- plus a non-vacuity guard per matcher showing the
    forged sample is itself well-formed, so the proof exercises the
    comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.1.63"
    FORGED_VERSION_A = "0.1.64"
    FORGED_VERSION_B = "0.1.65"

    def test_forged_pre_bump_version_is_well_formed(self):
        """Non-vacuity guard for the baseline matcher."""
        self.assertIsNotNone(_parse_version(self.FORGED_PRE_BUMP_VERSION))

    def test_baseline_matcher_rejects_forged_pre_bump_version(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, self.FORGED_PRE_BUMP_VERSION)

    def test_forged_differing_versions_are_both_well_formed(self):
        """Non-vacuity guard for the equality matcher."""
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_A))
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_B))

    def test_equality_matcher_rejects_forged_differing_versions(self):
        self.assertNotEqual(self.FORGED_VERSION_A, self.FORGED_VERSION_B)
        with self.assertRaises(AssertionError):
            _assert_versions_equal(
                self, self.FORGED_VERSION_A, self.FORGED_VERSION_B
            )

    def test_baseline_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "abc")

    def test_two_digit_patch_component_sorts_correctly_as_a_tuple(self):
        # Edge case from the task plan's Test Notes: a naive string
        # comparison would order a two-digit patch component wrongly
        # ("0.1.9" > "0.1.10" lexically); the forged sample below would
        # pass a string comparison against BASELINE_PATCH but must fail
        # the tuple-based one because its major.minor does not match.
        self.assertGreater("0.1.9", "0.1.10")
        naive_string_pass = "0.1.9" > f"0.1.{BASELINE_PATCH}"
        self.assertTrue(naive_string_pass)
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1.9")

    def test_parse_version_distinguishes_parse_failure_from_none(self):
        # AC-5: the parser returns None (not an exception) on a bad shape,
        # so a caller can tell "did not parse" apart from "parsed and
        # failed comparison".
        self.assertIsNone(_parse_version("not-a-version"))
        self.assertIsNone(_parse_version(None))
        self.assertIsNotNone(_parse_version("0.1.64"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-5 (NFR9): this new module imports only the standard library (no
    third-party dependency introduced by test code)."""

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

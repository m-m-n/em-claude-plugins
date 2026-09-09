"""Tests for task0005 (batch-verify-rework-lineage-cap): the em-workflow
plugin version bump from 0.1.61 to a value strictly greater, applied to both
registries.

Covers task0005 Acceptance Criteria
(feature-docs/batch-verify-rework-lineage-cap/tasks/task0005.md):

- AC-1 (FR12): `em-workflow/.claude-plugin/plugin.json`'s `version` and the
  em-workflow entry's `version` in `.claude-plugin/marketplace.json` agree.
- AC-2 (FR12): that value is on the `0.1.x` line with patch strictly greater
  than the pre-task baseline (61) -- only the patch component moved.
- AC-3 (FR12): the em-review marketplace entry's version is unchanged.
- AC-4 (regression): the existing tests/test_plugin_version_parity.py module
  keeps exercising the same em-workflow version parity/comparison behavior
  it always has (see Notes below on its one pre-existing, unrelated
  baseline failure).
- AC-5 (NFR3, NFR4): this module imports only the standard library, and each
  matcher has a negative proof against synthetic data -- one left at the
  pre-task baseline, one where the two registries disagree.

Follows the pattern established by
tests/test_batch_stop_contract_version_bump.py and
tests/test_routeback_reset_scope_version_bump.py: the "past baseline"
comparison is a dot-separated numeric tuple, not a whole-string comparison,
so a future two-digit patch component still sorts correctly (a naive
string comparison would get "0.1.9" > "0.1.10" backwards).

Note on AC-4: `tests/test_plugin_version_parity.py` already carries one
failure unrelated to this task -- `TestEmReviewEntryHasNoVersionKey` pins
the em-review marketplace entry as carrying no `version` key, but that
entry already has one (`0.5.7`) on the tree this task started from. That
failure predates this task's changes and is out of this task's scope (it
concerns the em-review entry, not the em-workflow version bump this task
performs); this module does not touch it or attempt to fix it.
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

# Pre-task baseline (task0005.md, Design): both registries read 0.1.61
# before this task's edit.
BASELINE_MAJOR_MINOR = (0, 1)
BASELINE_PATCH = 61

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
    """AC-1/AC-2: the plugin manifest's version is past baseline and its
    name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-1/AC-2: the em-workflow marketplace entry's version is past
    baseline and matches the plugin manifest exactly."""

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


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-5 (NFR4): a negative proof per matcher -- one synthetic sample
    left at the pre-task baseline, one where the two registries'
    (forged) versions disagree -- plus a non-vacuity guard per matcher
    showing the forged sample is itself well-formed, so the proof
    exercises the comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.1.61"
    FORGED_VERSION_A = "0.1.62"
    FORGED_VERSION_B = "0.1.63"

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


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-5 (NFR3): this new module imports only the standard library (no
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

"""Tests for task0001 (routeback-residual-connections): the em-workflow
plugin version bump to a patch strictly greater than 0.2.0 in both
registries.

Covers task0001 Acceptance Criteria
(feature-docs/routeback-residual-connections/tasks/task0001.md):

- AC-6 (FR7; TS-5): `em-workflow/.claude-plugin/plugin.json` and the
  em-workflow entry of `.claude-plugin/marketplace.json` both parse as
  JSON and report a version strictly greater than (0, 2, 0), by
  per-component numeric comparison, and the two report the identical
  version string; the em-review entry is not asserted here (IMPLEMENTATION.md
  D6: this module reads only `implement-phase.md`'s own document-contract
  concerns; the em-review-entry-untouched regression guard already lives
  in `tests/test_routeback_reset_scope_version_bump.py` and is not
  restated).
- AC-8 (NFR9): this module exists, is discovered by
  `python3 -m unittest discover -s tests` from the repository root, uses
  only the standard library, and gives every matcher a negative proof plus
  a non-vacuity guard, per IMPLEMENTATION.md D8.

This is a documentation/registry task (Test Notes: unit-level
document-contract assertions over parsed JSON), following the pattern
established by `tests/test_routeback_reset_scope_version_bump.py`
(IMPLEMENTATION.md D5) -- kept in its own module rather than folded into
`tests/test_routeback_reset_scope_consistency.py` so that module keeps
reading only `implement-phase.md`. JSON files are parsed, never
pattern-matched; no literal version is pinned (a durable baseline, so this
module never goes stale on the next legitimate patch bump).

Matcher -> negative-proof inventory (D8):

- `_assert_version_past_baseline` (the baseline matcher): negative proof is
  `test_baseline_matcher_rejects_forged_pre_bump_version`, non-vacuity
  guard is `test_forged_pre_bump_version_is_well_formed`.
- `_assert_versions_equal` (the equality matcher): negative proof is
  `test_equality_matcher_rejects_forged_differing_versions`, non-vacuity
  guard is `test_forged_differing_versions_are_both_well_formed`.
- `_marketplace_entry`'s lookup (em-workflow entry found): non-vacuity is
  itself the guard -- `TestMarketplaceEntryVersion` would error via
  `AssertionError` from `_marketplace_entry` if the entry were missing,
  which is exercised directly by `test_marketplace_entry_lookup_raises_when_entry_missing`.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

BASELINE_VERSION = (0, 2, 0)

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    for entry in data["plugins"]:
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _parse_version(version):
    """Parses X.Y.Z, returning (major, minor, patch) as ints, or None when
    the string is not of that form. Returning None (rather than raising)
    lets callers distinguish a parse failure from a comparison failure --
    the non-vacuity guards below depend on that distinction."""
    match = VERSION_RE.match(version)
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version):
    """The baseline matcher: durable invariant is a version strictly
    greater than BASELINE_VERSION under per-component numeric comparison --
    never a fixed literal, which would go stale on the next legitimate
    bump."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    test.assertGreater(parts, BASELINE_VERSION)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the two registries must report the identical
    version string."""
    test.assertEqual(version_a, version_b)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-6 (FR7): the plugin manifest's version is past baseline and its
    name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data["version"])

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-6 (FR7): the em-workflow marketplace entry's version is past
    baseline and matches the plugin manifest exactly."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)

    def test_em_workflow_entry_is_found(self):
        # Non-vacuity: the lookup this module depends on actually resolves.
        entry = _marketplace_entry(self.data, "em-workflow")
        self.assertIsNotNone(entry)

    def test_em_workflow_entry_version_is_past_baseline(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        _assert_version_past_baseline(self, entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        _assert_versions_equal(self, entry.get("version"), self.manifest["version"])

    def test_marketplace_entry_lookup_raises_when_entry_missing(self):
        # Non-vacuity guard for `_marketplace_entry`'s own lookup: proves
        # the helper actually fails when the named entry is absent, rather
        # than silently returning None.
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-8 / NFR9: a negative proof per matcher, plus a non-vacuity guard
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

    def test_forged_differing_versions_are_both_well_formed(self):
        """Non-vacuity guard for the equality matcher."""
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_A))
        self.assertIsNotNone(_parse_version(self.FORGED_VERSION_B))

    def test_equality_matcher_rejects_forged_differing_versions(self):
        self.assertNotEqual(self.FORGED_VERSION_A, self.FORGED_VERSION_B)
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, self.FORGED_VERSION_A, self.FORGED_VERSION_B)


if __name__ == "__main__":
    unittest.main()

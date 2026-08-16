"""Tests for task0003 (batch-stop-contract): the em-workflow plugin version
bump to a patch strictly greater than 39 in both registries.

Covers task0003 Acceptance Criteria
(feature-docs/batch-stop-contract/tasks/task0003.md):

- AC-1 (FR9): `em-workflow/.claude-plugin/plugin.json` parses as JSON, its
  `version` is on the `0.1.x` line with patch strictly greater than the
  IMPLEMENTATION.md D8 baseline (39), and its `name` still reads
  `em-workflow`.
- AC-2 (FR9): `.claude-plugin/marketplace.json` parses as JSON; the
  `plugins[]` entry named `em-workflow` reports a `version` equal, as a
  string, to the plugin manifest's; the entry named `em-review` still has
  `source` `./em-review` and still carries no `version` key.
- AC-3 (FR8, NFR1): this module exists, is discovered by
  `python3 -m unittest discover -s tests` from the repository root, and
  uses only the Python standard library.
- AC-4 (NFR4): per IMPLEMENTATION.md D8, each matcher has a negative proof --
  the baseline matcher rejects a forged pre-bump `0.1.39` version string,
  and the equality matcher rejects a forged pair of differing version
  strings -- plus a non-vacuity guard per matcher showing the forged sample
  is itself a well-formed `X.Y.Z` value the parser accepts, so the proof
  exercises the comparison rather than a parse failure.
- AC-5 (NFR2): the full suite passes with every pre-existing module
  unmodified.

This is a documentation/registry task (Test Notes: unit-level
document-contract assertions over parsed JSON), following the pattern
established by tests/test_routeback_reset_scope_version_bump.py, raising the
baseline patch from 38 to 39 per IMPLEMENTATION.md D8 (this feature's own
version-bump module must go red on the un-bumped `0.1.39` tree, which the
predecessor's baseline of 38 would not do). JSON files are parsed, never
pattern-matched.

Matcher -> negative-proof inventory (D8):

- `_assert_version_past_baseline` (the baseline matcher): negative proof is
  `test_baseline_matcher_rejects_forged_pre_bump_version`, non-vacuity guard
  is `test_forged_pre_bump_version_is_well_formed`.
- `_assert_versions_equal` (the equality matcher): negative proof is
  `test_equality_matcher_rejects_forged_differing_versions`, non-vacuity
  guard is `test_forged_differing_versions_are_both_well_formed`.
- `_marketplace_entry`'s lookups (`em-review` source / no-version-key) are
  pure regression guards over retained, pre-change fields -- no matcher is
  asserting new wording, so D8 exempts them from a negative proof.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

BASELINE_PATCH = 39

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
    AC-4's non-vacuity guard depends on that distinction."""
    match = VERSION_RE.match(version)
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version):
    """The baseline matcher: durable invariant (major, minor) == (0, 1) and
    patch > BASELINE_PATCH. A fixed literal would go stale on the very next
    unrelated version bump, per the pattern in
    tests/test_routeback_reset_scope_version_bump.py."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = parts
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, BASELINE_PATCH)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the two registries must report the identical
    version string."""
    test.assertEqual(version_a, version_b)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1 (FR9): the plugin manifest's version is past baseline and its
    name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data["version"])

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2 (FR9): the em-workflow marketplace entry's version is past
    baseline and matches the plugin manifest exactly; the em-review entry is
    untouched."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)

    def test_em_workflow_entry_version_is_past_baseline(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        _assert_version_past_baseline(self, entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        _assert_versions_equal(self, entry.get("version"), self.manifest["version"])

    def test_em_review_entry_source_unchanged(self):
        entry = _marketplace_entry(self.data, "em-review")
        self.assertEqual(entry.get("source"), "./em-review")

    def test_em_review_entry_has_no_version_key(self):
        entry = _marketplace_entry(self.data, "em-review")
        self.assertNotIn("version", entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4 / NFR4: a negative proof per matcher, plus a non-vacuity guard
    per matcher showing the forged sample is itself well-formed, so the
    proof exercises the comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.1.39"
    FORGED_VERSION_A = "0.1.40"
    FORGED_VERSION_B = "0.1.41"

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

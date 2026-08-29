"""Tests for task0004 (batch-quiet-output): the em-workflow plugin version
bump to a patch strictly greater than 51 in both registries.

Covers task0004 Acceptance Criteria
(feature-docs/batch-quiet-output/tasks/task0004.md):

- AC-1 (FR13): `em-workflow/.claude-plugin/plugin.json` parses as JSON, its
  `version` is of the form `X.Y.Z` with `(major, minor) == (0, 1)` and
  `patch` strictly greater than `51`, and its `name` still reads
  `em-workflow`.
- AC-2 (FR13): `.claude-plugin/marketplace.json` parses as JSON; its
  `plugins[]` entry named `em-workflow` carries a `version` equal, as a
  string, to the plugin manifest's, and the entry named `em-review` still
  has `source` `./em-review` and still carries no `version` key.
- AC-3: each matcher this module introduces (the baseline matcher and the
  equality matcher) has a negative proof -- a forged pre-bump version and a
  forged pair of differing versions are each rejected -- plus a non-vacuity
  guard showing the forged sample is itself a well-formed `X.Y.Z` value, so
  the proof exercises the comparison rather than a parse failure.
- AC-4: this module is discovered by `python3 -m unittest discover -s
  tests` from the repository root, imports the Python standard library
  only, and the whole suite passes with no pre-existing module modified.

This is a documentation/registry task (Test Notes: unit-level assertions
over parsed JSON; there is no runtime behaviour to integration-test),
following the pattern established by
tests/test_batch_stop_contract_version_bump.py, raising the baseline patch
from 39 to 51 per IMPLEMENTATION.md D8 (this feature's own version-bump
module must go red on the un-bumped `0.1.51` tree, which the predecessor's
baseline of 39 would not do). `tests/test_plugin_version_parity.py` already
exists and guards parity independently; per the task plan this module adds
the feature-specific baseline and does not modify that pre-existing module.
JSON files are parsed, never pattern-matched.

Matcher -> negative-proof inventory:

- `_assert_version_past_baseline` (the baseline matcher): negative proof is
  `test_baseline_matcher_rejects_forged_pre_bump_version`, non-vacuity guard
  is `test_forged_pre_bump_version_is_well_formed`.
- `_assert_versions_equal` (the equality matcher): negative proof is
  `test_equality_matcher_rejects_forged_differing_versions`, non-vacuity
  guard is `test_forged_differing_versions_are_both_well_formed`.
- `_marketplace_entry`'s lookups (`em-review` source / no-version-key) are
  pure regression guards over retained, pre-change fields -- no matcher is
  asserting new wording, so this module exempts them from a negative proof.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

BASELINE_PATCH = 51

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
    AC-3's non-vacuity guard depends on that distinction."""
    match = VERSION_RE.match(version)
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version):
    """The baseline matcher: durable invariant (major, minor) == (0, 1) and
    patch > BASELINE_PATCH. A fixed literal would go stale on the very next
    unrelated version bump, per the pattern in
    tests/test_batch_stop_contract_version_bump.py."""
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
    """AC-1 (FR13): the plugin manifest's version is past baseline and its
    name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data["version"])

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2 (FR13): the em-workflow marketplace entry's version is past
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
    """AC-3: a negative proof per matcher, plus a non-vacuity guard per
    matcher showing the forged sample is itself well-formed, so the proof
    exercises the comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.1.51"
    FORGED_VERSION_A = "0.1.52"
    FORGED_VERSION_B = "0.1.53"

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

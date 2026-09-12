"""Tests for destructive-guard-command-substitution: the em-workflow plugin
version bump to a patch strictly greater than 74 in both registries.

Covers task0002 Acceptance Criteria
(feature-docs/destructive-guard-command-substitution/tasks/task0002.md):

- AC-1: both manifests report the identical version string, of the form
  `0.1.<patch>` with patch strictly greater than 74.
- AC-2: both files still parse as JSON; no field other than the em-workflow
  version changes in either file; the sibling plugin's entry keeps its own
  `source` and its own, different version.
- AC-3: this module is discovered by `python3 -m unittest discover -s
  tests`, parses both manifests as JSON rather than pattern-matching their
  text, and looks the marketplace entry up by its `name` field.
- AC-4: the module carries a negative proof and a non-vacuity guard for
  each of its two matchers, and reverting only the two manifest edits makes
  the module fail -- the failure names the version comparison, not a parse
  error.
- AC-5: `python3 -m unittest discover -s tests` passes as a whole with the
  new module present -- including the repository-wide plugin version parity
  check -- and `python3 em-workflow/scripts/check-plugin-invariants.py .`
  exits 0. Not unit-testable from inside this module; verified by actually
  running both commands, recorded in the implementer report.

This module follows the shape of the repository's established per-feature
version-bump modules -- mirrored here from
`tests/test_heredoc_stdin_guard_version_bump.py` -- with the baseline patch
raised to 74 per IMPLEMENTATION.md D2 (the pre-change baseline for this
feature). JSON files are parsed, never pattern-matched.

Matcher -> negative-proof inventory (AC-4):

- `_assert_version_past_baseline` (the baseline matcher): negative proof is
  `test_baseline_matcher_rejects_forged_pre_bump_version`, non-vacuity
  guard is `test_forged_pre_bump_version_is_well_formed`.
- `_assert_versions_equal` (the equality matcher): negative proof is
  `test_equality_matcher_rejects_forged_differing_versions`, non-vacuity
  guard is `test_forged_differing_versions_are_both_well_formed`.
- `_marketplace_entry`'s lookups (the plugin manifest's `name` field, the
  `em-review` entry's `source`) are pure regression guards over retained,
  pre-change fields -- no matcher is asserting new wording, so these need
  no negative proof.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-change baseline: both registries read 0.1.74 before this task's edit
# (IMPLEMENTATION.md D2).
BASELINE_PATCH = 74

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array position."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _parse_version(version):
    """Parses X.Y.Z, returning (major, minor, patch) as ints, or None when
    the string is not of that form. Returning None (rather than raising)
    lets callers distinguish a parse failure from a comparison failure --
    AC-4's non-vacuity guard depends on that distinction."""
    match = VERSION_RE.match(version or "")
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version):
    """The baseline matcher: durable invariant (major, minor) == (0, 1) and
    patch > BASELINE_PATCH. A fixed literal would go stale on the very next
    unrelated version bump."""
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
    """AC-1/AC-2: the plugin manifest's version is past baseline and its
    name field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-1/AC-2: the em-workflow marketplace entry's version is past
    baseline and matches the plugin manifest exactly; the sibling
    (em-review) entry is untouched."""

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

    def test_em_review_entry_version_not_dragged_along(self):
        # em-review carries its own independent version; this feature must
        # not move it.
        entry = _marketplace_entry(self.data, "em-review")
        self.assertNotEqual(entry.get("version"), self.manifest["version"])


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4: a negative proof per matcher, plus a non-vacuity guard per
    matcher showing the forged sample is itself well-formed, so the proof
    exercises the comparison rather than a parse failure."""

    FORGED_PRE_BUMP_VERSION = "0.1.74"
    FORGED_VERSION_A = "0.1.74"
    FORGED_VERSION_B = "0.1.75"

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

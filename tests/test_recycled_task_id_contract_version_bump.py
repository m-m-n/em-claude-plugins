"""Tests for task0002 (recycled-task-id-contract): the em-workflow plugin
version bump by exactly one patch increment in both registries.

Covers task0002 Acceptance Criteria
(feature-docs/recycled-task-id-contract/tasks/task0002.md):

- AC-1 (FR6): `em-workflow/.claude-plugin/plugin.json` parses as JSON and its
  `version` is one patch increment above the pre-change value (0.1.44), with
  the major/minor family (0, 1) unchanged.
- AC-2 (FR6): the em-workflow entry of `.claude-plugin/marketplace.json`
  parses as JSON and its `version` is byte-identical to the plugin
  manifest's version.
- AC-3 (FR6): no field other than the two version values changes in either
  file -- the plugin manifest's `name`, and the marketplace entries' `name`
  and `source` values, are unchanged; the marketplace `plugins` array gains
  or loses no entry.
- AC-4 (NFR1, NFR2): this module lives under `tests/` as a `test_*.py`
  module, is discovered by `python3 -m unittest discover -s tests` from the
  repository root, imports only the standard library, and asserts AC-1 to
  AC-3 by parsing both files as JSON.
- AC-5 (NFR2, NFR3): the version assertion is a durable invariant (family
  plus a recorded baseline floor -- never a hard-coded exact version, which
  would go stale on the next unrelated bump), each matcher has a negative
  proof that a pre-bump/forged value fails it, no hook source file is
  modified by this task, and the full suite passes.

This is a documentation/registry task (Test Notes: unit-level, two JSON
reads and value assertions, no fixture, no temporary directory), following
the established pattern in this suite
(tests/test_batch_policy_option_id_version_bump.py,
tests/test_batch_stop_contract_version_bump.py). JSON files are PARSED,
never pattern-matched. Per IMPLEMENTATION.md D5, this module asserts nothing
about `em-workflow/references/implement-phase.md` -- task0001 rewrites that
document in the same feature and the two tasks merge in an unspecified
order.

Negative-proof discipline (Test Notes edge cases):

- `_assert_version_past_baseline` (the durable baseline matcher): negative
  proof is `test_baseline_matcher_rejects_forged_pre_bump_version`; a
  version string not of the three-part dotted shape must fail rather than
  pass by accident, proven by
  `test_baseline_matcher_rejects_malformed_version_shape`.
- `_assert_versions_equal` (the equality matcher): negative proof is
  `test_equality_matcher_rejects_forged_differing_versions` -- the
  assertion must fail if only one file were bumped. All negative proofs run
  against forged in-test values, never against a mutated repository file.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-task baseline (task0002.md, Design): both registries read 0.1.44
# before this task's edit. The new version must compare strictly greater --
# a fixed literal ("0.1.45") would go stale on the next unrelated bump.
BASELINE_PATCH = 44

# Snapshot of the marketplace entries' name/source fields, taken before this
# task's edit (task0002.md, Scope: "no other entry and no other field
# changes"; AC-3).
MARKETPLACE_NAME_SOURCE_BASELINE = {
    "em-review": "./em-review",
    "em-workflow": "./em-workflow",
}


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


def _version_tuple(version):
    """Parse 'X.Y.Z' into a tuple of ints. Raises AssertionError (rather
    than returning None) for anything not of that three-part dotted shape,
    so a malformed version fails the assertion instead of passing by
    accident (Test Notes edge case)."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version or "")
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_version_past_baseline(test, version, baseline_patch=BASELINE_PATCH):
    """Durable invariant: (major, minor) == (0, 1) and patch > baseline_patch.
    States the family plus a recorded baseline floor -- never a hard-coded
    exact version (task0002.md, Design)."""
    major, minor, patch = _version_tuple(version)
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, baseline_patch)


def _assert_versions_equal(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1 (FR6): the plugin manifest parses as JSON, its version is one
    patch increment above the pre-change value with the major/minor family
    unchanged, and its `name` field is untouched."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2 (FR6): the em-workflow marketplace entry parses as JSON, its
    version is byte-identical to the plugin manifest's version, and its
    `name`/`source` fields are untouched."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_equal(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_em_workflow_entry_name_and_source_unchanged(self):
        self.assertEqual(self.entry.get("name"), "em-workflow")
        self.assertEqual(self.entry.get("source"), "./em-workflow")


class TestMarketplaceOtherFieldsUnchanged(unittest.TestCase):
    """AC-3 (FR6): no field other than the two version values changes --
    every marketplace entry's `name`/`source` matches the pre-task snapshot,
    and the `plugins` array gains or loses no entry."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)

    def test_entry_count_unchanged(self):
        self.assertEqual(
            len(self.data.get("plugins", [])),
            len(MARKETPLACE_NAME_SOURCE_BASELINE),
        )

    def test_every_entry_name_and_source_matches_baseline(self):
        for name, source in MARKETPLACE_NAME_SOURCE_BASELINE.items():
            entry = _marketplace_entry(self.data, name)
            self.assertEqual(entry.get("source"), source)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-5 (NFR2, NFR3): a negative proof per matcher, plus the malformed-
    shape edge case named in Test Notes. All forged values are constructed
    in-test, never derived from a mutated repository file."""

    def test_baseline_matcher_rejects_forged_pre_bump_version(self):
        forged_pre_bump_version = f"0.1.{BASELINE_PATCH}"
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, forged_pre_bump_version)

    def test_baseline_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1")

    def test_equality_matcher_rejects_forged_differing_versions(self):
        forged_version_a = f"0.1.{BASELINE_PATCH + 1}"
        forged_version_b = f"0.1.{BASELINE_PATCH + 2}"
        self.assertNotEqual(forged_version_a, forged_version_b)
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, forged_version_a, forged_version_b)


if __name__ == "__main__":
    unittest.main()

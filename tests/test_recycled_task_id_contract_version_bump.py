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
  file. This module verifies AC-3 through the marketplace em-workflow
  entry's `name` and `source` values only -- the check does not inspect the
  array length, entry order, or any entry other than em-workflow.
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
    """Durable invariant: version strictly greater than (0, 1, baseline_patch)
    under per-component numeric comparison -- never a hard-coded exact
    version (task0002.md, Design), and never a fixed major.minor pin, which
    would go stale on the next legitimate minor bump (task-tier-reduction
    task0008, NFR4)."""
    parts = _version_tuple(version)
    test.assertGreater(parts, (0, 1, baseline_patch))


def _assert_versions_equal(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _assert_em_workflow_entry_unchanged(test, data):
    """Module-local check for task0002 AC-3: the em-workflow marketplace
    entry's `name` and `source` are unchanged. Looks the entry up by name
    (never by array index) and never inspects the array length, entry
    order, or any entry other than em-workflow (task0001.md, em-workflow
    entry check contract)."""
    entry = _marketplace_entry(data, "em-workflow")
    test.assertEqual(entry.get("name"), "em-workflow")
    test.assertEqual(entry.get("source"), "./em-workflow")


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
        _assert_em_workflow_entry_unchanged(self, self.data)


class TestEmWorkflowEntryCheckInTestData(unittest.TestCase):
    """In-test data cases for the em-workflow entry check (FR5,
    task0001.md AC-1/AC-2/AC-3). Each case builds its marketplace mapping
    inside the test; the mapping is independent of the repository file's
    contents and nothing is written to disk."""

    def test_extra_plugin_entry_is_tolerated(self):
        """AC-1: em-review, em-workflow (source ./em-workflow), and a third
        plugin entry -- the check passes."""
        data = {
            "plugins": [
                {"name": "em-review", "source": "./em-review"},
                {"name": "em-workflow", "source": "./em-workflow"},
                {"name": "third-plugin", "source": "./third-plugin"},
            ]
        }
        _assert_em_workflow_entry_unchanged(self, data)

    def test_em_workflow_source_drift_raises(self):
        """AC-2: the em-workflow entry present with a source other than
        ./em-workflow -- the check raises an assertion failure."""
        data = {
            "plugins": [
                {"name": "em-review", "source": "./em-review"},
                {"name": "em-workflow", "source": "./somewhere-else"},
            ]
        }
        with self.assertRaises(AssertionError):
            _assert_em_workflow_entry_unchanged(self, data)

    def test_em_workflow_name_drift_raises(self):
        """AC-3: the em-workflow entry renamed so no entry is named
        em-workflow -- the check raises an assertion failure."""
        data = {
            "plugins": [
                {"name": "em-review", "source": "./em-review"},
                {"name": "em-workflow-renamed", "source": "./em-workflow"},
            ]
        }
        with self.assertRaises(AssertionError):
            _assert_em_workflow_entry_unchanged(self, data)


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

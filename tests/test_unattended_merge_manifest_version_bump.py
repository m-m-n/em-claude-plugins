"""Tests for task0009 (unattended-merge): the em-workflow manifest
descriptions mention the merge skill, and the em-workflow version's minor
component is raised in both registries.

Covers task0009 Acceptance Criteria
(feature-docs/unattended-merge/tasks/task0009.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` parse as JSON, and the em-workflow
  description in each (the marketplace entry found by `name`, never by array
  position) mentions the merge skill `/em-workflow:merge`.
- AC-2: the em-workflow version is identical in the two files and its
  `(major, minor)` pair is strictly greater than the pre-task `(0, 3)`
  under per-component integer comparison. The exact relation to the
  integration base commit (minor one greater, patch zero, major unchanged)
  depends on that commit, so it is checked in the verify phase (TS26) by
  comparing against the integration base; this module deliberately pins no
  literal version and keeps holding after later bumps.
- AC-3: the other plugins' entries and the existing plugin-invariant tests
  are covered by the pre-existing modules (`test_plugin_version_parity.py`,
  `test_batch_policy_option_id_version_bump.py`, ...); this module asserts
  that the lookup by name is not vacuous.

Matcher -> negative-proof inventory:

- `_assert_mentions_merge_skill`: negative proofs are
  `test_description_matcher_rejects_text_without_the_skill` and
  `test_description_matcher_rejects_non_string`.
- `_assert_minor_past_baseline`: negative proofs are
  `test_fails_when_version_equals_baseline_pair`,
  `test_fails_when_only_patch_is_raised` and
  `test_fails_for_malformed_version_shape`; the numeric (not textual)
  comparison is shown by `test_minor_comparison_is_numeric`.
- `_assert_versions_agree`: negative proof is `test_fails_when_versions_differ`.
- `_marketplace_entry`: negative proof is
  `test_entry_lookup_fails_on_a_missing_entry_name`.
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

MERGE_SKILL = "/em-workflow:merge"

# Pre-task (major, minor) pair of the em-workflow version. The new version's
# pair must compare strictly greater; the patch component is not compared
# because it keeps advancing with every push to main.
BASELINE_MAJOR_MINOR = (0, 3)

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array position; the
    marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse "X.Y.Z" into an int 3-tuple so comparison is per-component and
    numeric; a missing or malformed version fails loudly instead of
    comparing vacuously."""
    if not isinstance(version, str):
        raise AssertionError(f"version {version!r} is not a string")
    match = VERSION_RE.match(version)
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_mentions_merge_skill(test, description):
    test.assertIsInstance(description, str, "description is not a string")
    test.assertIn(MERGE_SKILL, description)


def _assert_minor_past_baseline(test, version, baseline=BASELINE_MAJOR_MINOR):
    test.assertGreater(_version_tuple(version)[:2], tuple(baseline))


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


class TestPluginManifest(unittest.TestCase):
    """AC-1/AC-2: plugin.json parses, describes the merge skill, and carries
    a version whose minor is past the baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_name_is_em_workflow(self):
        self.assertEqual(self.data.get("name"), "em-workflow")

    def test_description_mentions_the_merge_skill(self):
        _assert_mentions_merge_skill(self, self.data.get("description"))

    def test_version_minor_is_past_baseline(self):
        _assert_minor_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntry(unittest.TestCase):
    """AC-1/AC-2/AC-3: the em-workflow marketplace entry (found by name)
    describes the merge skill and agrees with plugin.json on the version."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)
        self.assertIn("description", self.entry)

    def test_other_plugin_entries_still_present(self):
        names = [entry.get("name") for entry in self.data.get("plugins", [])]
        for other in ("em-review", "plugin-dev"):
            self.assertIn(other, names)

    def test_description_mentions_the_merge_skill(self):
        _assert_mentions_merge_skill(self, self.entry.get("description"))

    def test_version_minor_is_past_baseline(self):
        _assert_minor_past_baseline(self, self.entry.get("version"))

    def test_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestValidationDetectsRegressions(unittest.TestCase):
    """Negative proofs: each matcher above rejects the failure it exists to
    catch."""

    def test_description_matcher_rejects_text_without_the_skill(self):
        with self.assertRaises(AssertionError):
            _assert_mentions_merge_skill(self, "/em-workflow:develop drives a flow")

    def test_description_matcher_rejects_non_string(self):
        with self.assertRaises(AssertionError):
            _assert_mentions_merge_skill(self, None)

    def test_description_matcher_accepts_text_with_the_skill(self):
        _assert_mentions_merge_skill(self, "x /em-workflow:merge y")

    def test_fails_when_version_equals_baseline_pair(self):
        with self.assertRaises(AssertionError):
            _assert_minor_past_baseline(self, "0.3.0")

    def test_fails_when_only_patch_is_raised(self):
        with self.assertRaises(AssertionError):
            _assert_minor_past_baseline(self, "0.3.999")

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_minor_past_baseline(self, "abc")

    def test_minor_comparison_is_numeric(self):
        # As raw strings "0.10.0" < "0.9.0"; the parsed pair ranks it above.
        self.assertLess("0.10.0", "0.9.0")
        _assert_minor_past_baseline(self, "0.10.0", baseline=(0, 9))

    def test_accepts_a_raised_minor_with_zero_patch(self):
        _assert_minor_past_baseline(self, "0.4.0")

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.4.0", "0.4.1")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """This module imports only the standard library, so it runs under
    `python3 -m unittest discover -s tests` with no extra install."""

    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()

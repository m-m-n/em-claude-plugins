"""Tests for task0003 (assumptions-reversible-criteria): the em-workflow
plugin version bump from 0.1.64 to 0.1.65 in both registries.

Covers task0003 Acceptance Criteria
(feature-docs/assumptions-reversible-criteria/tasks/task0003.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` reports version `0.1.65`.
- AC-2: the `em-workflow` entry of `.claude-plugin/marketplace.json`
  reports the same version as AC-1.
- AC-3: that version is strictly greater than 0.1.64 at the patch
  component, with major and minor unchanged.
- AC-4: the `em-review` entry of the marketplace manifest is unchanged at
  0.5.7.
- AC-5: this module asserts AC-2 through AC-4, and each of those three
  checks has a negative proof against forged data plus a non-vacuity
  companion.
- AC-6: this module imports only standard-library names and passes in a
  worktree containing only this task's changes.

Follows the negative-proof style of tests/test_plugin_version_parity.py
(task0004 of develop-once-option), the repository's existing version-bump
test module referenced by task0003.md's Test Notes; that module is not
modified by this task (IMPLEMENTATION.md C6).
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

# Pre-task baseline (task0003.md, Design): both registries read 0.1.64
# before this task's edit; the new value is pinned to 0.1.65
# (IMPLEMENTATION.md C5).
BASELINE_VERSION = "0.1.64"
NEW_VERSION = "0.1.65"
EM_REVIEW_VERSION = "0.5.7"

# Exactly major.minor.patch -- the AC-3 comparison operates on parsed
# numeric components, never on the raw string.
DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


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
    """Parse a major.minor.patch string into an int 3-tuple, so comparison
    happens per-component and numerically -- never as a whole-string
    comparison, which would sort a two-digit component backwards (e.g.
    "0.1.100" < "0.1.64" lexically)."""
    if not isinstance(version, str) or not DOTTED_NUMERIC_VERSION_RE.match(version):
        raise AssertionError(f"version {version!r} is not a major.minor.patch string")
    return tuple(int(p) for p in version.split("."))


def _assert_versions_agree(test, version_a, version_b):
    """Property 1 (AC-2): both registries report the same version string."""
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _assert_patch_bump_over_baseline(test, version, baseline=BASELINE_VERSION):
    """Property 2 (AC-3): `version` is strictly greater than `baseline` at
    the patch component, with major and minor unchanged."""
    major, minor, patch = _version_tuple(version)
    base_major, base_minor, base_patch = _version_tuple(baseline)
    test.assertEqual(
        (major, minor),
        (base_major, base_minor),
        f"major.minor changed: {version!r} vs baseline {baseline!r}",
    )
    test.assertGreater(
        patch,
        base_patch,
        f"patch component did not increase: {version!r} vs baseline {baseline!r}",
    )


def _assert_em_review_unchanged(test, entry, expected_version=EM_REVIEW_VERSION):
    """Property 3 (AC-4): the em-review entry's version reads its current
    pinned value -- the bump did not spill into the neighbouring plugin."""
    test.assertEqual(entry.get("name"), "em-review")
    test.assertEqual(
        entry.get("version"),
        expected_version,
        f"em-review version drifted: {entry.get('version')!r} != {expected_version!r}",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: plugin.json's version is a patch bump over the baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_patch_bump_over_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2/AC-3: the em-workflow marketplace entry (found by name, not
    position) agrees with the plugin manifest and is a valid patch bump."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        # Guard against silently succeeding when the entry is missing.
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_em_workflow_entry_version_is_a_patch_bump_over_baseline(self):
        _assert_patch_bump_over_baseline(self, self.entry.get("version"))


class TestEmReviewEntryUnchanged(unittest.TestCase):
    """AC-4: the em-review entry's version is unchanged at 0.5.7."""

    def test_em_review_entry_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_unchanged(self, entry)


class TestVersionsAgreeMatcherNegativeProof(unittest.TestCase):
    """AC-5 property 1: `_assert_versions_agree` negative proof plus
    non-vacuity companion."""

    def test_rejects_disagreeing_versions(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.65", "0.1.66")

    def test_accepts_agreeing_versions(self):
        _assert_versions_agree(self, "0.1.65", "0.1.65")  # must not raise


class TestPatchBumpMatcherNegativeProof(unittest.TestCase):
    """AC-5 property 2: `_assert_patch_bump_over_baseline` negative proof
    plus non-vacuity companion, including the Test Notes edge cases: a
    version equal to the baseline is rejected (strictly greater, not
    greater-or-equal), and a minor or major bump is rejected even though
    numerically greater, since AC-3 requires major.minor unchanged."""

    def test_rejects_version_equal_to_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, BASELINE_VERSION)

    def test_rejects_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "0.1.10")

    def test_rejects_minor_bump(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "0.2.0")

    def test_rejects_major_bump(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "1.1.65")

    def test_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "0.1")

    def test_accepts_valid_patch_bump(self):
        _assert_patch_bump_over_baseline(self, NEW_VERSION)  # must not raise

    def test_accepts_two_digit_patch_component_numerically(self):
        # "0.1.100" must compare correctly against "0.1.64" as parsed
        # numeric components, even though it sorts lower as a raw string
        # (demonstrated by the sanity assertion below).
        self.assertLess("0.1.100", "0.1.64")  # sanity: the string trap exists
        _assert_patch_bump_over_baseline(self, "0.1.100")  # must not raise


class TestEmReviewUnchangedMatcherNegativeProof(unittest.TestCase):
    """AC-5 property 3: `_assert_em_review_unchanged` negative proof plus
    non-vacuity companion."""

    def test_rejects_drifted_version(self):
        forged = {"name": "em-review", "version": "0.5.8"}
        with self.assertRaises(AssertionError):
            _assert_em_review_unchanged(self, forged)

    def test_rejects_wrong_name(self):
        forged = {"name": "em-review-forked", "version": EM_REVIEW_VERSION}
        with self.assertRaises(AssertionError):
            _assert_em_review_unchanged(self, forged)

    def test_accepts_unchanged_entry(self):
        forged = {"name": "em-review", "version": EM_REVIEW_VERSION}
        _assert_em_review_unchanged(self, forged)  # must not raise


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6: this new module imports only the standard library (test/
    README.md's "no external dependencies" rule for test code)."""

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

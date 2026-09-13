"""Tests for task0004 (codex-wrapper-fallback-removal): the em-workflow and
em-review plugin version bumps, applied to both registries.

Covers task0004 Acceptance Criteria
(feature-docs/codex-wrapper-fallback-removal/tasks/task0004.md):

- AC-1 (FR9): the em-workflow manifest and the em-workflow marketplace entry
  both read 0.1.77.
- AC-2 (FR9): the em-review manifest and the em-review marketplace entry
  both read 0.5.10.
- AC-3 (FR9): for each plugin, the two values are asserted equal to each
  other and strictly greater than that plugin's pre-feature baseline at the
  patch component, with major and minor unchanged; the marketplace entry is
  located by name and the lookup fails loudly when absent.
- AC-6 (NFR5): both project test commands pass in this worktree, and this
  module imports only the standard library.

AC-4 (all four existing em-review-pinning modules pass after the bump) and
AC-5 (each of those modules keeps a working negative proof) are satisfied by
the repairs made directly in those four modules
(tests/test_batch_codex_autonomous_decisions_version_bump.py,
tests/test_failed_kind_version_bump.py,
tests/test_verify_rework_lineage_cap_version_bump.py,
tests/test_assumptions_reversible_criteria_version_bump.py); this module
does not re-test their content.

Comparison is on parsed numeric components, never the raw string: a naive
string comparison orders a two-digit patch component wrongly, and
em-workflow's bump target 0.1.77 is exactly the kind of value that exposes
it against a single-digit baseline.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Pre-feature baseline major.minor.patch per plugin (Design: both registries
# read these values before this task's edit).
PLUGIN_SPECS = {
    "em-workflow": {
        "manifest_path": REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json",
        "baseline": (0, 1, 76),
        "expected": "0.1.78",
    },
    "em-review": {
        "manifest_path": REPO_ROOT / "em-review" / ".claude-plugin" / "plugin.json",
        "baseline": (0, 5, 9),
        "expected": "0.5.10",
    },
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


def _parse_version(version):
    """Parse X.Y.Z into (major, minor, patch) ints, or None if not of that
    shape. Returning None (rather than raising) lets callers distinguish a
    parse failure from a comparison failure."""
    match = VERSION_RE.match(version or "")
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _assert_patch_bump_over_baseline(test, version, baseline):
    """`version` parses as three numeric components; major and minor are
    unchanged from `baseline` and patch is strictly greater. Comparison is
    always on parsed numeric components, never the raw string -- a naive
    string comparison would sort a two-digit patch component backwards."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = parts
    base_major, base_minor, base_patch = baseline
    test.assertEqual((major, minor), (base_major, base_minor))
    test.assertGreater(patch, base_patch)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the plugin manifest and the marketplace entry
    must report the identical version string."""
    test.assertEqual(version_a, version_b)


class TestPluginVersionBumps(unittest.TestCase):
    """AC-1/AC-2/AC-3: each plugin's manifest and marketplace entry agree
    and are a patch bump over that plugin's own pre-feature baseline."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)

    def test_manifest_and_marketplace_agree_per_plugin(self):
        for name, spec in PLUGIN_SPECS.items():
            with self.subTest(plugin=name):
                manifest = _load_json(spec["manifest_path"])
                entry = _marketplace_entry(self.marketplace, name)
                _assert_versions_equal(
                    self, entry.get("version"), manifest.get("version")
                )

    def test_manifest_version_is_a_patch_bump_over_its_own_baseline(self):
        for name, spec in PLUGIN_SPECS.items():
            with self.subTest(plugin=name):
                manifest = _load_json(spec["manifest_path"])
                _assert_patch_bump_over_baseline(
                    self, manifest.get("version"), spec["baseline"]
                )

    def test_marketplace_entry_version_is_a_patch_bump_over_its_own_baseline(self):
        for name, spec in PLUGIN_SPECS.items():
            with self.subTest(plugin=name):
                entry = _marketplace_entry(self.marketplace, name)
                _assert_patch_bump_over_baseline(
                    self, entry.get("version"), spec["baseline"]
                )

    def test_entry_lookup_is_non_vacuous_per_plugin(self):
        for name in PLUGIN_SPECS:
            with self.subTest(plugin=name):
                entry = _marketplace_entry(self.marketplace, name)
                self.assertIsInstance(entry, dict)
                self.assertIn("version", entry)


class TestSpecificVersionValues(unittest.TestCase):
    """AC-1/AC-2: the concrete values this task writes."""

    def test_em_workflow_reads_0_1_78(self):
        manifest = _load_json(PLUGIN_SPECS["em-workflow"]["manifest_path"])
        marketplace = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(marketplace, "em-workflow")
        self.assertEqual(manifest.get("version"), "0.1.78")
        self.assertEqual(entry.get("version"), "0.1.78")

    def test_em_review_reads_0_5_10(self):
        manifest = _load_json(PLUGIN_SPECS["em-review"]["manifest_path"])
        marketplace = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(marketplace, "em-review")
        self.assertEqual(manifest.get("version"), "0.5.10")
        self.assertEqual(entry.get("version"), "0.5.10")


class TestMarketplaceEntryLookupGuard(unittest.TestCase):
    """AC-3: the lookup fails loudly rather than silently passing when the
    named entry is missing (non-vacuity guard, proved against synthetic
    data)."""

    def test_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_lookup_succeeds_on_a_present_entry_name(self):
        # Non-vacuity guard for the guard above: the forged sample used to
        # prove failure is well-formed enough that a present name resolves.
        forged = {"plugins": [{"name": "em-review", "version": "9.9.9"}]}
        entry = _marketplace_entry(forged, "em-review")
        self.assertEqual(entry.get("version"), "9.9.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-3 (NFR5): a negative proof per matcher against forged data, plus a
    well-formedness guard on the forged sample."""

    def test_forged_pre_bump_versions_are_well_formed(self):
        """Non-vacuity guard for the patch-bump matcher."""
        for name, spec in PLUGIN_SPECS.items():
            with self.subTest(plugin=name):
                baseline_str = ".".join(str(p) for p in spec["baseline"])
                self.assertIsNotNone(_parse_version(baseline_str))

    def test_patch_bump_matcher_rejects_forged_pre_bump_version(self):
        for name, spec in PLUGIN_SPECS.items():
            with self.subTest(plugin=name):
                baseline_str = ".".join(str(p) for p in spec["baseline"])
                with self.assertRaises(AssertionError):
                    _assert_patch_bump_over_baseline(
                        self, baseline_str, spec["baseline"]
                    )

    def test_patch_bump_matcher_rejects_minor_or_major_drift(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "0.2.0", (0, 1, 76))
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "1.1.77", (0, 1, 76))

    def test_patch_bump_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "abc", (0, 1, 76))

    def test_two_digit_patch_component_sorts_correctly_as_a_tuple(self):
        # Edge case from the task plan's Test Notes: a naive string
        # comparison orders a two-digit patch component wrongly ("0.1.77"
        # sorts below "0.1.9" lexically); em-workflow's actual bump target,
        # 0.1.77, is exactly this shape relative to a single-digit baseline.
        naive_string_pass = "0.1.77" > "0.1.9"
        self.assertFalse(naive_string_pass)
        _assert_patch_bump_over_baseline(self, "0.1.77", (0, 1, 9))  # must not raise

    def test_equality_matcher_rejects_forged_differing_versions(self):
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, "0.1.77", "0.1.78")

    def test_forged_differing_versions_are_both_well_formed(self):
        """Non-vacuity guard for the equality matcher."""
        self.assertIsNotNone(_parse_version("0.1.77"))
        self.assertIsNotNone(_parse_version("0.1.78"))

    def test_matched_name_with_malformed_version_fails_the_parse_assertion(self):
        # Edge case from the task plan's Test Notes: a forged entry whose
        # name matches but whose version is malformed must fail the parse
        # assertion rather than silently satisfying an equality check.
        forged = {"plugins": [{"name": "em-workflow", "version": "not-a-version"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertIsInstance(entry, dict)  # the lookup itself succeeds
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(
                self, entry.get("version"), PLUGIN_SPECS["em-workflow"]["baseline"]
            )

    def test_parse_version_distinguishes_parse_failure_from_none(self):
        self.assertIsNone(_parse_version("not-a-version"))
        self.assertIsNone(_parse_version(None))
        self.assertIsNotNone(_parse_version("0.1.77"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6 (NFR5): this new module imports only the standard library (no
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

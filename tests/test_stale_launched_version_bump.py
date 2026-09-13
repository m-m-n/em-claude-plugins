"""Version-parity and bump-over-baseline tests for the em-workflow plugin
(task0004, stale-launched-retry-recovery).

Covers task0004 Acceptance Criteria
(feature-docs/stale-launched-retry-recovery/tasks/task0004.md):

- AC-4 (FR11): the em-workflow plugin manifest and the em-workflow entry of
  the marketplace registry carry the identical version string, and that
  string parses as three numeric components whose major and minor equal the
  baseline 0.1 and whose patch is strictly greater than 77 -- compared on
  parsed numeric components, never on the raw string.
- AC-5 (FR11): the marketplace entry is located by its name field, and the
  lookup fails loudly when no entry of that name exists; each matcher has a
  negative proof against forged data, plus a well-formedness guard on the
  forged sample.
- AC-8 (NFR6): this module imports only the standard library.

AC-6 (every pre-existing version-pinning module passes after the bump,
including the one whose exact-value assertions this task re-anchors) and
AC-7 (`python3 -m unittest discover -s tests` passes from the repository
root) are properties of the whole `tests/` run, not of this module alone;
they are recorded in this task's test record rather than re-tested here.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Pre-feature baseline major.minor.patch (Design: both registries read
# 0.1.77 before this task's edit).
BASELINE = (0, 1, 77)


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


class TestEmWorkflowVersionBump(unittest.TestCase):
    """AC-4: the em-workflow manifest and marketplace entry agree and are a
    patch bump over the recorded pre-feature baseline 0.1.77."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_manifest_and_marketplace_agree(self):
        _assert_versions_equal(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_manifest_version_is_a_patch_bump_over_baseline(self):
        _assert_patch_bump_over_baseline(self, self.manifest.get("version"), BASELINE)

    def test_marketplace_entry_version_is_a_patch_bump_over_baseline(self):
        _assert_patch_bump_over_baseline(self, self.entry.get("version"), BASELINE)

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)


class TestMarketplaceEntryLookupGuard(unittest.TestCase):
    """AC-5: the lookup fails loudly rather than silently passing when the
    named entry is missing (non-vacuity guard, proved against synthetic
    data)."""

    def test_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_lookup_succeeds_on_a_present_entry_name(self):
        # Non-vacuity guard for the guard above: the forged sample used to
        # prove failure is well-formed enough that a present name resolves.
        forged = {"plugins": [{"name": "em-workflow", "version": "9.9.9"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertEqual(entry.get("version"), "9.9.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-5: a negative proof per matcher against forged data, plus a
    well-formedness guard on the forged sample."""

    def test_forged_baseline_version_is_well_formed(self):
        """Non-vacuity guard for the patch-bump matcher."""
        baseline_str = ".".join(str(p) for p in BASELINE)
        self.assertIsNotNone(_parse_version(baseline_str))

    def test_patch_bump_matcher_rejects_forged_baseline_version(self):
        baseline_str = ".".join(str(p) for p in BASELINE)
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, baseline_str, BASELINE)

    def test_patch_bump_matcher_rejects_minor_or_major_drift(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "0.2.0", BASELINE)
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "1.1.78", BASELINE)

    def test_patch_bump_matcher_rejects_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, "abc", BASELINE)

    def test_equality_matcher_rejects_forged_differing_versions(self):
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, "0.1.77", "0.1.78")

    def test_forged_differing_versions_are_both_well_formed(self):
        """Non-vacuity guard for the equality matcher."""
        self.assertIsNotNone(_parse_version("0.1.77"))
        self.assertIsNotNone(_parse_version("0.1.78"))

    def test_matched_name_with_malformed_version_fails_the_parse_assertion(self):
        # A forged entry whose name matches but whose version is malformed
        # must fail the parse assertion rather than silently satisfying an
        # equality check.
        forged = {"plugins": [{"name": "em-workflow", "version": "not-a-version"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertIsInstance(entry, dict)  # the lookup itself succeeds
        with self.assertRaises(AssertionError):
            _assert_patch_bump_over_baseline(self, entry.get("version"), BASELINE)

    def test_parse_version_distinguishes_parse_failure_from_none(self):
        self.assertIsNone(_parse_version("not-a-version"))
        self.assertIsNone(_parse_version(None))
        self.assertIsNotNone(_parse_version("0.1.78"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-8 (NFR6): this new module imports only the standard library (no
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

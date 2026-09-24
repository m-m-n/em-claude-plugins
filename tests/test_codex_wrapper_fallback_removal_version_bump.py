"""Tests for task0004 (codex-wrapper-fallback-removal): the em-workflow and
em-review plugin version bumps, applied to both registries.

Covers task0004 Acceptance Criteria
(feature-docs/codex-wrapper-fallback-removal/tasks/task0004.md):

- AC-1 (FR9): the em-workflow manifest and the em-workflow marketplace entry
  both read the same version.
- AC-2 (FR9): the em-review manifest and the em-review marketplace entry
  both read the same version.
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
# read these values before this task's edit). `baseline` backs the
# patch-bump-over-baseline checks below (TestPluginVersionBumps /
# TestValidationDetectsRegressions). `floor` (repo-suite-pinned-test-drift
# task0004, FR8) reuses that same already-recorded lower bound as the floor
# for the form/floor/agreement matcher (IMPLEMENTATION.md D2, Shared
# Components: Lower-bound comparison) -- a historical value, used only
# through comparison, never compared with the current version (NFR2).
PLUGIN_SPECS = {
    "em-workflow": {
        "manifest_path": REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json",
        "baseline": (0, 1, 76),
        "floor": "0.1.76",
    },
    "em-review": {
        "manifest_path": REPO_ROOT / "em-review" / ".claude-plugin" / "plugin.json",
        "baseline": (0, 5, 9),
        "floor": "0.5.9",
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
    """`version` parses as three numeric components and is strictly greater
    than `baseline` under per-component numeric comparison. Never a fixed
    major.minor pin -- that form goes stale on the next legitimate minor
    bump (task-tier-reduction task0008, NFR4) -- and never the raw string,
    which would sort a two-digit patch component backwards. The name is
    kept (rather than renamed to something version-agnostic) because most
    callers in this module still exercise a patch-only bump; only
    em-workflow's own bump in this task advances the minor component."""
    parts = _parse_version(version)
    test.assertIsNotNone(parts, f"version {version!r} is not of the form X.Y.Z")
    test.assertGreater(parts, tuple(baseline))


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher: the plugin manifest and the marketplace entry
    must report the identical version string."""
    test.assertEqual(version_a, version_b)


def _is_well_formed_version(value):
    """Version form rule (IMPLEMENTATION.md D2, Shared Components): `value`
    is well-formed only if it is a string of exactly three dot-separated
    components, each a non-empty run of ASCII decimal digits. Everything
    else -- wrong component count, a non-digit component, a "v" prefix, a
    pre-release/build suffix, surrounding whitespace, the empty string, or a
    non-string value -- is malformed."""
    return isinstance(value, str) and VERSION_RE.match(value) is not None


def _assert_well_formed_version(test, value):
    test.assertTrue(
        _is_well_formed_version(value), f"version {value!r} is not well-formed"
    )


def _assert_manifest_and_entry_pass_floor_and_agree(
    test, manifest_version, entry_version, floor
):
    """FR8 matcher (IMPLEMENTATION.md D2 row): the manifest version and the
    marketplace entry version are each well-formed (Version form rule) and
    identical to each other (Registry agreement), and the manifest version
    sits at or above the plugin's recorded floor (Lower-bound comparison).
    Never a fixed current-version literal (NFR2)."""
    _assert_well_formed_version(test, manifest_version)
    _assert_well_formed_version(test, entry_version)
    _assert_well_formed_version(test, floor)
    test.assertEqual(
        manifest_version,
        entry_version,
        f"registries disagree: {manifest_version!r} != {entry_version!r}",
    )
    test.assertGreaterEqual(_parse_version(manifest_version), _parse_version(floor))


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
    """AC-1 (FR8, repo-suite-pinned-test-drift task0004): for each plugin,
    the manifest version and the marketplace entry version are both
    well-formed (Version form rule), agree with each other (Registry
    agreement), and the manifest version sits at or above that plugin's
    recorded floor (Lower-bound comparison)."""

    def test_em_workflow_manifest_and_entry_agree_on_the_current_version(self):
        spec = PLUGIN_SPECS["em-workflow"]
        manifest = _load_json(spec["manifest_path"])
        marketplace = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(marketplace, "em-workflow")
        _assert_manifest_and_entry_pass_floor_and_agree(
            self, manifest.get("version"), entry.get("version"), spec["floor"]
        )

    def test_em_review_manifest_and_entry_agree_on_the_current_version(self):
        spec = PLUGIN_SPECS["em-review"]
        manifest = _load_json(spec["manifest_path"])
        marketplace = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(marketplace, "em-review")
        _assert_manifest_and_entry_pass_floor_and_agree(
            self, manifest.get("version"), entry.get("version"), spec["floor"]
        )


class TestFR8NegativeProofs(unittest.TestCase):
    """repo-suite-pinned-test-drift task0004, AC-3: the FR8 negative proofs
    from the task plan's Design -- forged (manifest, entry, floor) triples
    fed to the FR8 matcher (NFR3: hermetic, forged in-memory data only)."""

    def test_forged_higher_version_in_both_is_accepted(self):
        _assert_manifest_and_entry_pass_floor_and_agree(
            self, "99.0.0", "99.0.0", PLUGIN_SPECS["em-workflow"]["floor"]
        )  # must not raise

    def test_forged_version_below_floor_in_both_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_manifest_and_entry_pass_floor_and_agree(
                self, "0.1.0", "0.1.0", PLUGIN_SPECS["em-workflow"]["floor"]
            )

    def test_forged_malformed_manifest_version_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_manifest_and_entry_pass_floor_and_agree(
                self, "not-a-version", "0.2.0", PLUGIN_SPECS["em-workflow"]["floor"]
            )

    def test_forged_malformed_entry_version_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_manifest_and_entry_pass_floor_and_agree(
                self, "0.2.0", "not-a-version", PLUGIN_SPECS["em-workflow"]["floor"]
            )

    def test_forged_disagreeing_values_are_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_manifest_and_entry_pass_floor_and_agree(
                self, "0.2.0", "0.2.1", PLUGIN_SPECS["em-workflow"]["floor"]
            )

    def test_forged_version_above_floor_numerically_but_below_lexicographically_is_accepted(
        self,
    ):
        # "0.10.0" sorts below "0.9.0" as a raw string but is numerically
        # above it (Lower-bound comparison: integers, never strings).
        naive_string_pass = "0.10.0" > "0.9.0"
        self.assertFalse(naive_string_pass)
        _assert_manifest_and_entry_pass_floor_and_agree(
            self, "0.10.0", "0.10.0", "0.9.0"
        )  # must not raise


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

    def test_matcher_accepts_a_minor_or_major_advance_over_baseline(self):
        # task-tier-reduction/task0008 (NFR4): a minor or major bump is now
        # a legitimate advance over the baseline -- this matcher must not
        # reject it merely because major.minor changed. The concrete case
        # this task performs is exactly a minor bump on em-workflow.
        _assert_patch_bump_over_baseline(self, "0.2.0", (0, 1, 76))  # must not raise
        _assert_patch_bump_over_baseline(self, "1.1.77", (0, 1, 76))  # must not raise

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

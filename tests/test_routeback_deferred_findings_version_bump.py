"""Version-lockstep tests for the em-workflow plugin (task0006,
routeback-deferred-findings): the version bump from 0.2.10 to 0.2.11 in
both registries.

Covers task0006 Acceptance Criteria
(feature-docs/routeback-deferred-findings/tasks/task0006.md):

- AC-1 (FR9): `em-workflow/.claude-plugin/plugin.json`'s `version` is
  0.2.11.
- AC-2 (FR9): the em-workflow entry in `.claude-plugin/marketplace.json`
  (found by its `name` field, never by array position) has `version`
  0.2.11, equal to the plugin manifest.
- AC-3 (FR9, FR10): both versions parse as three integer components, are
  strictly greater than the baseline 0.2.10 under per-component integer
  comparison, and are equal to each other. Never pinned to the literal
  0.2.11, so this module keeps holding after later legitimate bumps.
- AC-4 (FR10, NFR8): this module imports only the standard library.

AC-4's remaining clause (the existing version-pinning modules pass
unmodified and `python3 -m unittest discover -s tests` passes) is a
property of the whole suite, not of this module alone; it is verified by
actually running the command (recorded in the implementer report), not
re-tested here.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Pre-feature baseline (task0006.md, Goal/Design): both registries read
# 0.2.10 before this task's edit. The new version must compare strictly
# greater, by per-component integer comparison -- never pinned to exactly
# 0.2.11, so this module survives later legitimate bumps.
BASELINE = (0, 2, 10)


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array index; the
    marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _parse_version(version):
    """Parse "X.Y.Z" into an (int, int, int) tuple, or raise AssertionError
    when the value is not of that shape -- a missing or malformed version
    must fail loudly, never compare vacuously."""
    if not isinstance(version, str):
        raise AssertionError(f"version {version!r} is not a string")
    match = VERSION_RE.match(version)
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version, baseline=BASELINE):
    test.assertGreater(_parse_version(version), tuple(baseline))


def _assert_versions_equal(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: plugin.json parses as JSON and its version is past baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MANIFEST_PATH)

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_manifest_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2: the em-workflow marketplace entry's version (found by name, not
    position) agrees with the plugin manifest's version and is past
    baseline."""

    @classmethod
    def setUpClass(cls):
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        # Guard against silently succeeding when the entry is missing:
        # confirm the lookup actually returned something with a version.
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_entry_version_matches_plugin_manifest(self):
        _assert_versions_equal(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestVersionComparisonIsPerComponentNumeric(unittest.TestCase):
    """AC-3 (Design): the raw-string comparison trap -- a two-digit patch
    component sorts below a one-digit one as text ("0.2.10" < "0.2.9"
    lexically) -- so the comparison must use parsed integer components,
    never the raw string."""

    def test_naive_string_comparison_gets_two_digit_patch_backwards(self):
        self.assertLess("0.2.10", "0.2.9")

    def test_parsed_tuple_orders_two_digit_patch_correctly(self):
        self.assertGreater(_parse_version("0.2.10"), _parse_version("0.2.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # "0.2.10" must be accepted as past a synthetic baseline of "0.2.9",
        # even though "0.2.9" > "0.2.10" as a raw string comparison (proved
        # above) -- this would raise if the helper used naive string
        # comparison instead of the parsed tuple.
        _assert_version_past_baseline(self, "0.2.10", baseline=(0, 2, 9))


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-3: negative proofs -- a version equal to the baseline is
    rejected, two differing versions are rejected, and a malformed version
    shape is rejected."""

    def test_fails_when_version_equals_baseline(self):
        baseline_str = ".".join(str(p) for p in BASELINE)
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, baseline_str)

    def test_forged_baseline_version_is_well_formed(self):
        # Non-vacuity guard for the assertion above: the string used to
        # prove rejection is itself a well-formed version.
        baseline_str = ".".join(str(p) for p in BASELINE)
        self.assertIsNotNone(_parse_version(baseline_str))

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, "0.2.11", "0.2.12")

    def test_forged_differing_versions_are_both_well_formed(self):
        # Non-vacuity guard for the assertion above.
        self.assertIsNotNone(_parse_version("0.2.11"))
        self.assertIsNotNone(_parse_version("0.2.12"))

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "abc")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_entry_lookup_succeeds_on_a_present_entry_name(self):
        # Non-vacuity guard for the guard above.
        forged = {"plugins": [{"name": "em-workflow", "version": "9.9.9"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        self.assertEqual(entry.get("version"), "9.9.9")

    def test_fails_when_marketplace_entry_missing_version_member(self):
        forged = {"plugins": [{"name": "em-workflow"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, entry.get("version"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-4: this new module imports only the standard library."""

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

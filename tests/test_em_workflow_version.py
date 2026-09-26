"""Tests for task0005 (tier-decision-staged-jev): the em-workflow plugin
version bump from 0.2.9 to 0.2.10 in both registries.

Covers task0005 Acceptance Criteria
(feature-docs/tier-decision-staged-jev/tasks/task0005.md):

- AC-1 (NFR5; TS-12): the `version` in the em-workflow plugin manifest
  (`em-workflow/.claude-plugin/plugin.json`) equals the `version` of the
  em-workflow entry in the marketplace file (`.claude-plugin/marketplace.json`),
  the entry found by its plugin `name` rather than array position.
- AC-2 (NFR5; TS-12): that version compares strictly greater than 0.2.9
  under dot-separated, per-component integer comparison. The comparison is
  proven numeric (not a plain text comparison) by showing "0.2.10" ranks
  *below* "0.2.9" as a raw string (because the second character of the
  patch component, "1" < "9", decides it before the third character is
  ever read) while the per-component integer tuple ranks it correctly
  above.
- AC-3 (NFR3): both manifests still parse as JSON, and this module uses
  only the Python standard library so it runs under
  `python3 -m unittest discover -s tests`. That full-suite invocation
  exiting 0 is a property of the whole suite, not self-testable from
  inside one module without recursion; it is verified by actually running
  the command (recorded in the implementer report), not asserted here.

Test Notes (task0005.md): the comparison never pins the literal "0.2.10" --
only "greater than 0.2.9" -- so this module keeps holding after future
version bumps, per the pattern already used by
`tests/test_task_id_allocation_ssot_version_bump.py` and sibling
`*_version_bump.py` modules.
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

# Pre-task baseline (task0005.md, Design/AC-2): both registries read 0.2.9
# before this task's edit. The new version must compare strictly greater,
# by per-component integer comparison -- never pinned to exactly 0.2.10,
# so this module survives later legitimate bumps.
BASELINE_VERSION = "0.2.9"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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
    """Parses "X.Y.Z" into an (int, int, int) tuple, or raises AssertionError
    when the value is not of that shape -- a missing or malformed version
    must fail loudly, never compare vacuously."""
    if not isinstance(version, str):
        raise AssertionError(f"version {version!r} is not a string")
    match = VERSION_RE.match(version)
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(group) for group in match.groups())


def _assert_version_past_baseline(test, version, baseline=BASELINE_VERSION):
    test.assertGreater(_parse_version(version), _parse_version(baseline))


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1/AC-3: plugin.json parses as JSON and carries a version."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-1/AC-2: the em-workflow marketplace entry's version (found by
    name, not position) agrees with the plugin manifest's version and is
    past baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        # Guard against silently succeeding when the entry is missing:
        # confirm the lookup actually returned something with a version.
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestVersionComparisonIsPerComponentNumeric(unittest.TestCase):
    """AC-2 (Design): comparison must be per-component numeric, never a
    whole-string comparison. "0.2.10" vs "0.2.9" is the concrete case named
    in task0005.md: as raw strings, "0.2.10" < "0.2.9" because the second
    character of the patch component ("1" < "9") decides the comparison
    before the third character is ever read -- a plain text comparison
    ranks 0.2.9 above 0.2.10, which is backwards."""

    def test_naive_string_comparison_gets_it_backwards(self):
        self.assertLess("0.2.10", "0.2.9")

    def test_parsed_tuple_ranks_0_2_10_above_0_2_9(self):
        self.assertGreater(_parse_version("0.2.10"), _parse_version("0.2.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # 0.2.10 must be accepted as past a baseline of 0.2.9, even though
        # the raw strings compare the other way (proved above) -- this
        # would raise if the helper used naive string comparison.
        _assert_version_past_baseline(self, "0.2.10", baseline="0.2.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-2: proof that the checks above fail meaningfully -- when the two
    registries' versions differ, when a version is at or below the
    baseline, and when the marketplace entry or a version member is
    missing (never a silent pass)."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.2.10", "0.2.11")

    def test_fails_when_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, BASELINE_VERSION)

    def test_fails_when_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.2.5")

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "abc")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_fails_when_marketplace_entry_missing_version_member(self):
        forged = {"plugins": [{"name": "em-workflow"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, entry.get("version"))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-3: this new module imports only the standard library (test/
    README.md's "no external dependencies" rule for test code), so it runs
    under `python3 -m unittest discover -s tests` with no extra install."""

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

"""Tests for task0006 (review-perspective-model-effort): the minor version
bump of em-workflow and em-review, and the agreement of each plugin manifest
with its marketplace entry.

Covers task0006 Acceptance Criteria
(feature-docs/review-perspective-model-effort/tasks/task0006.md; TS-18,
NFR4, NFR5):

- AC-1: `em-workflow/.claude-plugin/plugin.json` carries the base major and
  is at or above (base major, base minor + 1, 0), against the base-commit
  version recorded below as `EM_WORKFLOW_BASELINE`. This is a lower bound:
  the patch is unchecked beyond that comparison and the minor has no upper
  bound, so a later CI patch bump or a later minor bump still passes. A
  patch-only bump, an unchanged version, a lowered minor and a different
  major are rejected.
- AC-2: `em-review/.claude-plugin/plugin.json` follows the same rule against
  `EM_REVIEW_BASELINE`.
- AC-3: the `em-workflow` and `em-review` entries of
  `.claude-plugin/marketplace.json`, found by `name` (never by array
  position), carry exactly their manifests' versions. That no other byte of
  the three files changed is not a property a module can read off the final
  files; it is checked against the base commit with
  `git diff --stat` / `git diff` when the task is verified. What this module
  adds is that the lookup is not vacuous and that the other marketplace
  entries are still present.
- AC-4: this module asserts AC-1 to AC-3 with negative proofs (below), using
  the standard library only.
- AC-5: the full suite, including every existing `*_version_bump.py` and
  version-parity module, is run as a command and is not self-testable from
  inside one module without recursion.

Baselines are the versions read from the task's base commit when this module
was written: em-workflow 0.4.28 and em-review 0.5.54. They are tuples of ints
and are compared per component, never as strings.

Matcher -> negative-proof inventory:

- `_version_tuple`: negative proofs are
  `test_version_tuple_rejects_malformed_values` (shape, non-string, signs,
  whitespace, leading zeros).
- `_assert_minor_bump_over_baseline`: negative proofs are
  `test_rejects_patch_only_bump`, `test_rejects_unchanged_version`,
  `test_rejects_major_change` and `test_rejects_lowered_minor`; the lower
  bound's tolerance (patch unchecked, minor without an upper bound) is shown
  by `test_accepts_minor_bump_with_nonzero_patch` and
  `test_accepts_minor_raised_by_two`; the numeric (not textual) comparison is
  shown by `test_string_ordering_trap_accepts_a_numeric_bump` and
  `test_string_ordering_trap_rejects_a_numerically_lower_version`.
- `_assert_versions_agree`: negative proof is
  `test_rejects_a_disagreeing_marketplace_entry`.
- `_marketplace_entry`: negative proofs are
  `test_entry_lookup_fails_on_a_missing_entry_name` and
  `test_entry_lookup_fails_on_a_duplicated_entry_name`.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
EM_REVIEW_MANIFEST_PATH = REPO_ROOT / "em-review" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Versions at this task's base commit (before the bump), as int 3-tuples.
EM_WORKFLOW_BASELINE = (0, 4, 28)
EM_REVIEW_BASELINE = (0, 5, 54)

# Canonical numeric components: no sign, no whitespace, no leading zeros.
# `fullmatch` (not `$`) so a trailing newline cannot slip through.
VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array position; the
    marketplace plugin list's order is not a contract. Exactly one entry must
    carry the name, so a duplicated entry cannot hide a disagreeing one."""
    matches = [
        entry
        for entry in data.get("plugins", [])
        if isinstance(entry, dict) and entry.get("name") == name
    ]
    if not matches:
        raise AssertionError(f"no marketplace entry named {name!r}")
    if len(matches) > 1:
        raise AssertionError(
            f"{len(matches)} marketplace entries named {name!r}; expected exactly one"
        )
    return matches[0]


def _version_tuple(version):
    """Parse "X.Y.Z" into an int 3-tuple so comparison is per component and
    numeric; a missing or malformed version fails loudly instead of
    comparing vacuously."""
    if not isinstance(version, str):
        raise AssertionError(f"version {version!r} is not a string")
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_minor_bump_over_baseline(test, version, baseline):
    """The bump rule, a lower bound: the candidate has the baseline's major
    and is at or above (baseline major, baseline minor + 1, 0), compared by
    integer components. The patch is unchecked beyond that comparison and the
    minor has no upper bound, so a later CI patch bump or a later minor bump
    still passes. A patch-only bump, an unchanged version and a lowered minor
    are rejected, and so is a different major even when it is numerically
    above the bound. A missing or malformed version is rejected by
    `_version_tuple` before the comparison."""
    candidate = _version_tuple(version)
    base_major, base_minor, _base_patch = baseline
    test.assertEqual(
        candidate[0],
        base_major,
        f"major of {version!r} differs from baseline {baseline}",
    )
    lower_bound = (base_major, base_minor + 1, 0)
    test.assertGreaterEqual(
        candidate,
        lower_bound,
        f"{version!r} is below the lower bound {lower_bound} "
        f"(baseline minor {base_minor} plus one, patch 0)",
    )


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


class TestEmWorkflowManifest(unittest.TestCase):
    """AC-1: the em-workflow manifest parses and carries the bumped version."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(EM_WORKFLOW_MANIFEST_PATH)

    def test_manifest_name_is_em_workflow(self):
        self.assertEqual(self.data.get("name"), "em-workflow")

    def test_version_is_a_minor_bump_over_baseline(self):
        _assert_minor_bump_over_baseline(
            self, self.data.get("version"), EM_WORKFLOW_BASELINE
        )


class TestEmReviewManifest(unittest.TestCase):
    """AC-2: the em-review manifest parses and carries the bumped version."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(EM_REVIEW_MANIFEST_PATH)

    def test_manifest_name_is_em_review(self):
        self.assertEqual(self.data.get("name"), "em-review")

    def test_version_is_a_minor_bump_over_baseline(self):
        _assert_minor_bump_over_baseline(
            self, self.data.get("version"), EM_REVIEW_BASELINE
        )


class TestMarketplaceEntries(unittest.TestCase):
    """AC-3: the em-workflow and em-review marketplace entries (found by
    name) carry exactly their manifests' versions."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.workflow_manifest = _load_json(EM_WORKFLOW_MANIFEST_PATH)
        cls.review_manifest = _load_json(EM_REVIEW_MANIFEST_PATH)
        cls.workflow_entry = _marketplace_entry(cls.data, "em-workflow")
        cls.review_entry = _marketplace_entry(cls.data, "em-review")

    def test_entry_lookups_are_non_vacuous(self):
        for entry in (self.workflow_entry, self.review_entry):
            self.assertIsInstance(entry, dict)
            self.assertIsInstance(entry.get("version"), str)

    def test_em_workflow_entry_version_matches_manifest(self):
        _assert_versions_agree(
            self, self.workflow_entry.get("version"), self.workflow_manifest.get("version")
        )

    def test_em_review_entry_version_matches_manifest(self):
        _assert_versions_agree(
            self, self.review_entry.get("version"), self.review_manifest.get("version")
        )

    def test_em_workflow_entry_version_is_a_minor_bump_over_baseline(self):
        _assert_minor_bump_over_baseline(
            self, self.workflow_entry.get("version"), EM_WORKFLOW_BASELINE
        )

    def test_em_review_entry_version_is_a_minor_bump_over_baseline(self):
        _assert_minor_bump_over_baseline(
            self, self.review_entry.get("version"), EM_REVIEW_BASELINE
        )

    def test_other_plugin_entry_is_still_present(self):
        names = [entry.get("name") for entry in self.data.get("plugins", [])]
        self.assertIn("plugin-dev", names)


class TestBumpRuleDetectsRegressions(unittest.TestCase):
    """Negative proofs: each matcher rejects the failure it exists to catch,
    on forged input."""

    BASELINE = (0, 4, 28)

    def test_accepts_the_correct_bump(self):
        _assert_minor_bump_over_baseline(self, "0.5.0", self.BASELINE)

    def test_rejects_patch_only_bump(self):
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "0.4.29", self.BASELINE)

    def test_rejects_unchanged_version(self):
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "0.4.28", self.BASELINE)

    def test_accepts_minor_raised_by_two(self):
        # The minor has no upper bound: a later minor bump still satisfies
        # the lower-bound rule.
        _assert_minor_bump_over_baseline(self, "0.6.0", self.BASELINE)

    def test_accepts_minor_bump_with_nonzero_patch(self):
        # The patch is unchecked: a CI patch bump after the minor bump still
        # satisfies the lower-bound rule.
        _assert_minor_bump_over_baseline(self, "0.5.1", self.BASELINE)

    def test_rejects_major_change(self):
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "1.5.0", self.BASELINE)

    def test_rejects_lowered_minor(self):
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "0.3.0", self.BASELINE)

    def test_string_ordering_trap_accepts_a_numeric_bump(self):
        # As raw strings "0.10.0" < "0.9.3"; per component 0.10.0 is the
        # minor bump over 0.9.3. A string comparison would reject it.
        self.assertLess("0.10.0", "0.9.3")
        _assert_minor_bump_over_baseline(self, "0.10.0", (0, 9, 3))

    def test_string_ordering_trap_rejects_a_numerically_lower_version(self):
        # As raw strings "0.9.0" > "0.10.5"; per component 0.9.0 is below
        # the baseline. A string comparison would accept it.
        self.assertGreater("0.9.0", "0.10.5")
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, "0.9.0", (0, 10, 5))

    def test_version_tuple_rejects_malformed_values(self):
        for bad in (
            "abc",
            "0.5",
            "0.5.0.1",
            "0.5.x",
            "0.5.0\n",
            " 0.5.0",
            "+0.5.0",
            "0.-5.0",
            "0.05.0",
            "",
            None,
            5,
            ["0", "5", "0"],
        ):
            with self.subTest(version=bad):
                with self.assertRaises(AssertionError):
                    _version_tuple(bad)

    def test_version_tuple_returns_integers(self):
        self.assertEqual(_version_tuple("0.10.0"), (0, 10, 0))

    def test_rejects_a_disagreeing_marketplace_entry(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.5.0", "0.5.1")

    def test_accepts_agreeing_versions(self):
        _assert_versions_agree(self, "0.5.0", "0.5.0")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_entry_lookup_fails_on_a_duplicated_entry_name(self):
        forged = {
            "plugins": [
                {"name": "em-workflow", "version": "0.5.0"},
                {"name": "em-workflow", "version": "0.5.1"},
            ]
        }
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_entry_lookup_finds_by_name_not_position(self):
        forged = {
            "plugins": [
                {"name": "plugin-dev", "version": "0.1.1"},
                {"name": "em-workflow", "version": "0.5.0"},
            ]
        }
        self.assertEqual(_marketplace_entry(forged, "em-workflow")["version"], "0.5.0")

    def test_entry_without_a_version_fails_the_bump_check(self):
        forged = {"plugins": [{"name": "em-workflow"}]}
        entry = _marketplace_entry(forged, "em-workflow")
        with self.assertRaises(AssertionError):
            _assert_minor_bump_over_baseline(self, entry.get("version"), self.BASELINE)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-4 (NFR4): this module imports only the standard library, so it
    runs under `python3 -m unittest discover -s tests` with no extra
    install."""

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

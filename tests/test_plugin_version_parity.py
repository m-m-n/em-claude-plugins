"""Tests for task0004 (develop-once-option): the em-workflow plugin version
bump from 0.1.50 to 0.1.51 in both registries.

Covers task0004 Acceptance Criteria
(feature-docs/develop-once-option/tasks/task0004.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json`'s `version` and the
  em-workflow entry's `version` in `.claude-plugin/marketplace.json` are
  both `0.1.51`.
- AC-2: this module verifies (a) the two registries agree on the version,
  and (b) that value compares strictly greater than 0.1.50 under
  dot-separated numeric comparison (not a string comparison), selecting the
  marketplace entry by `name` rather than array position.
- AC-3: `python3 em-workflow/scripts/check-plugin-invariants.py` against the
  repository root and `python3 -m unittest discover -s tests` both exit 0.
  Not unit-testable from inside this module (a suite cannot assert its own
  full-suite outcome without recursion, and the invariants checker's exit
  code is a CLI-level property already covered by
  test_check_plugin_invariants.py); verified by actually running both
  commands, recorded in the implementer report.

Per the task plan's Design and Test Notes, the "past baseline" comparison
uses a dot-separated numeric tuple, not a whole-string comparison -- a
future two-digit patch component would otherwise sort incorrectly under
naive string comparison (e.g. "0.1.9" > "0.1.10" lexically). This keeps the
test passing across future bumps instead of pinning to exactly 0.1.51.
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

# Pre-task baseline (task0004.md, Design): both registries read 0.1.50
# before this task's edit. The new version must compare strictly greater.
BASELINE_VERSION = "0.1.50"


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array index, the
    marketplace plugin list's order is not a contract (task0004.md Design:
    "照合は配列のインデックスではなく name で引く")."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse a dot-separated version string into a tuple of ints, so
    comparison happens per-component and numerically -- never as a
    whole-string comparison, which would sort a two-digit component
    backwards (e.g. "0.1.9" > "0.1.10" lexically)."""
    parts = (version or "").split(".")
    if not parts or not all(re.fullmatch(r"\d+", p) for p in parts):
        raise AssertionError(f"version {version!r} is not a dotted numeric sequence")
    return tuple(int(p) for p in parts)


def _assert_version_past_baseline(test, version, baseline=BASELINE_VERSION):
    test.assertGreater(_version_tuple(version), _version_tuple(baseline))


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


EM_REVIEW_NAME = "em-review"
EM_REVIEW_AUTHOR = {"name": "em"}
EM_REVIEW_CATEGORY = "code-review"
EM_REVIEW_SOURCE = "./em-review"

DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def _is_dotted_numeric_version(value):
    """A dotted numeric version string: one or more '.'-separated
    non-negative integers, e.g. "0.5.7"."""
    return isinstance(value, str) and DOTTED_NUMERIC_VERSION_RE.match(value) is not None


def _assert_em_review_entry_matches(test, entry):
    """The em-review matcher (task0005.md): identity fields (name, author,
    category, source) are pinned exactly; the `version` field is asserted
    by shape only -- present and dotted numeric -- never against a literal
    value, since `.claude/rules/core-plugin-version-bump.md` requires it to
    change over time."""
    test.assertEqual(entry.get("name"), EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EM_REVIEW_SOURCE)
    test.assertTrue(
        _is_dotted_numeric_version(entry.get("version")),
        f"em-review version {entry.get('version')!r} is not a dotted numeric string",
    )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: plugin.json parses as JSON and carries a version."""

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


class TestEmReviewEntryHasNoVersionKey(unittest.TestCase):
    """Edge case (task0004.md Test Notes): the em-review entry's shape a
    uniform-scan implementation must tolerate. Its identity fields (name,
    author, category, source) are pinned exactly; its `version` is asserted
    present and dotted numeric, never against a literal value, since
    `.claude/rules/core-plugin-version-bump.md` requires it to change over
    time (task0005.md)."""

    def test_em_review_entry_has_a_dotted_numeric_version(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_matches(self, entry)


class TestVersionComparisonIsDotSeparatedNumeric(unittest.TestCase):
    """Test Notes (hermetic): the comparison helper against synthetic
    version pairs, including a case where whole-string comparison and
    per-component numeric comparison disagree because of a two-digit patch
    component -- proves the "past baseline" check survives future bumps
    rather than being pinned to exactly 0.1.51."""

    def test_naive_string_comparison_gets_two_digit_patch_backwards(self):
        # Sanity: demonstrates the failure mode a plain string comparison
        # of full version strings would fall into.
        self.assertGreater("0.1.9", "0.1.10")

    def test_version_tuple_orders_two_digit_patch_correctly(self):
        self.assertGreater(_version_tuple("0.1.10"), _version_tuple("0.1.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # "0.1.10" must be accepted as past a synthetic baseline of "0.1.9",
        # even though "0.1.9" > "0.1.10" as a raw string comparison (proved
        # above) -- this would raise if the helper used naive string
        # comparison instead of the parsed tuple.
        _assert_version_past_baseline(self, "0.1.10", baseline="0.1.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-2: proof that the checks above fail meaningfully in both
    directions -- when the two registries' versions differ, and when a
    version is at or below the baseline (not merely above it)."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.51", "0.1.52")

    def test_fails_when_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, BASELINE_VERSION)

    def test_fails_when_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1.5")

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "abc")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    FORGED_EM_REVIEW_ENTRY = {
        "name": "em-review",
        "author": {"name": "em"},
        "category": "code-review",
        "source": "./em-review",
        "version": "0.5.7",
    }

    def test_em_review_matcher_rejects_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
        ):
            with self.subTest(field=field):
                forged = dict(self.FORGED_EM_REVIEW_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_matches(self, forged)

    def test_em_review_matcher_rejects_missing_or_malformed_version(self):
        missing = {
            key: value
            for key, value in self.FORGED_EM_REVIEW_ENTRY.items()
            if key != "version"
        }
        malformed = dict(self.FORGED_EM_REVIEW_ENTRY, version="not-a-version")
        for forged in (missing, malformed):
            with self.assertRaises(AssertionError):
                _assert_em_review_entry_matches(self, forged)

    def test_em_review_matcher_accepts_forged_higher_version(self):
        # AC-3: the matcher never compares the version against a literal,
        # so a forged sample differing only by a higher version is accepted.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="99.0.0")
        _assert_em_review_entry_matches(self, forged)  # must not raise


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-3: this new module imports only the standard library (test/
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

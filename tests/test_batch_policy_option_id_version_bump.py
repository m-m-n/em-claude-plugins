"""Tests for task0003 (batch-policy-option-id-consistency): the em-workflow
plugin version bump past 0.1.41 in both registries.

Covers task0003 Acceptance Criteria
(feature-docs/batch-policy-option-id-consistency/tasks/task0003.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` parses as JSON and its
  `version` compares strictly greater than 0.1.41 under per-component
  numeric comparison.
- AC-2: the em-workflow entry in `.claude-plugin/marketplace.json` carries a
  `version` string identical to the plugin manifest's.
- AC-3: every other plugin entry in the marketplace manifest is unchanged by
  this task. Per task0005.md, each such entry's identity fields (name,
  author, category, source, and the description's stable substring anchor)
  are pinned exactly; a `version` field is asserted present and dotted
  numeric, never against a literal, per
  `.claude/rules/core-plugin-version-bump.md`.
- AC-4: a test fails when the two versions differ, and fails when the plugin
  version is at or below the baseline; both directions are proven, not
  merely asserted about the current values.
- AC-5: `python3 -m unittest discover -s tests` passes for the whole suite.
  Not unit-testable from inside this module (a suite cannot assert its own
  full-suite outcome without recursion); verified by actually running the
  discovery command, recorded in the implementer report.

Per the task plan's Design, the comparison is per-component numeric, not a
string comparison of the whole version -- a two-digit patch component would
otherwise sort incorrectly (`"0.1.9" > "0.1.10"` lexically). The hermetic
tests below (`TestVersionComparisonIsPerComponentNumeric`) prove that
disagreement on synthetic pairs and prove the module's helper takes the
numeric side of it, independent of the real files' current values.

`_assert_other_entries_match_expected_shape` (the other-marketplace-entries
matcher, task0005.md): negative proofs are
`test_em_review_matcher_rejects_altered_identity_field` and
`test_em_review_matcher_rejects_missing_or_malformed_version`; the positive
proof that the version is asserted by shape, never by literal, is
`test_em_review_matcher_accepts_forged_higher_version`; the key-set edge
case is `test_em_review_matcher_rejects_new_unexpected_key`.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-task baseline (task0003.md, Design): both registries read 0.1.41
# before this task's edit. The new version must compare strictly greater.
BASELINE_PATCH = 41

# Snapshot of every marketplace plugin entry other than em-workflow, taken
# before this task's edit (task0003.md, Out of Scope: "Changing the version
# of any plugin other than em-workflow" / "No other entry ... is touched").
# Per task0005.md, each entry's identity fields are pinned exactly; its
# `version` is asserted by shape (present, dotted numeric) rather than
# pinned into this snapshot, since `.claude/rules/core-plugin-version-bump.md`
# requires it to change over time -- see
# `_assert_other_entries_match_expected_shape`.
OTHER_PLUGIN_ENTRIES_BASELINE = [
    {
        "name": "em-review",
        "description_anchor": (
            "/em-review:multi-review reviews the current git diff"
        ),
        "author": {"name": "em"},
        "category": "code-review",
        "source": "./em-review",
    },
]

EXPECTED_OTHER_ENTRY_KEYS = {"name", "description", "author", "category", "source", "version"}

DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def _is_dotted_numeric_version(value):
    """A dotted numeric version string: one or more '.'-separated
    non-negative integers, e.g. "0.5.7"."""
    return isinstance(value, str) and DOTTED_NUMERIC_VERSION_RE.match(value) is not None


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
    """Parse 'X.Y.Z' into a tuple of ints, so comparison happens
    per-component and numerically -- never as a whole-string comparison,
    which would sort a two-digit component (e.g. patch 10 vs 9) backwards."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version or "")
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_version_past_baseline(test, version, baseline_patch=BASELINE_PATCH):
    major, minor, patch = _version_tuple(version)
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, baseline_patch)


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _assert_other_entries_match_expected_shape(test, other_entries, baseline_entries):
    """The other-marketplace-entries matcher (task0005.md): each entry's
    identity fields (name, author, category, source, and the description's
    stable substring anchor) are pinned exactly; its `version` field is
    asserted by shape only -- present and dotted numeric -- never against a
    literal value, since `.claude/rules/core-plugin-version-bump.md`
    requires it to change over time. The key set is checked explicitly per
    entry so the split does not silently degrade into a subset check when
    an unexpected key is added (task0005.md edge case)."""
    test.assertEqual(len(other_entries), len(baseline_entries))
    for actual, expected in zip(other_entries, baseline_entries):
        test.assertEqual(set(actual.keys()), EXPECTED_OTHER_ENTRY_KEYS)
        test.assertEqual(actual.get("name"), expected["name"])
        test.assertEqual(actual.get("author"), expected["author"])
        test.assertEqual(actual.get("category"), expected["category"])
        test.assertEqual(actual.get("source"), expected["source"])
        test.assertIn(expected["description_anchor"], actual.get("description", ""))
        test.assertTrue(
            _is_dotted_numeric_version(actual.get("version")),
            f"{actual.get('name')!r} version {actual.get('version')!r} "
            "is not a dotted numeric string",
        )


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: plugin.json parses as JSON and its version compares strictly
    greater than 0.1.41 under per-component numeric comparison."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_is_valid_json_with_version_key(self):
        self.assertIn("version", self.data)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2: the em-workflow marketplace entry's version is identical to the
    plugin manifest's version string (found by name, not position)."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestOtherMarketplaceEntriesUnchanged(unittest.TestCase):
    """AC-3: every plugin entry in the marketplace manifest other than
    em-workflow matches its pre-task identity exactly, with its `version`
    field asserted by shape (task0005.md) -- this task only edits the
    em-workflow entry's version field."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)

    def test_other_entries_match_expected_identity_and_version_shape(self):
        other_entries = [
            entry for entry in self.data["plugins"] if entry.get("name") != "em-workflow"
        ]
        _assert_other_entries_match_expected_shape(
            self, other_entries, OTHER_PLUGIN_ENTRIES_BASELINE
        )


class TestVersionComparisonIsPerComponentNumeric(unittest.TestCase):
    """Test Notes (hermetic): the comparison helper against synthetic
    version pairs, including a case where whole-string comparison and
    per-component numeric comparison disagree because of a two-digit patch
    component."""

    def test_naive_string_comparison_gets_two_digit_patch_backwards(self):
        # Sanity: demonstrates the failure mode a plain string comparison
        # of full version strings would fall into.
        self.assertGreater("0.1.9", "0.1.10")

    def test_version_tuple_orders_two_digit_patch_correctly(self):
        self.assertGreater(_version_tuple("0.1.10"), _version_tuple("0.1.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # version "0.1.10" must be accepted as past a synthetic baseline
        # patch of 9, even though "0.1.9" > "0.1.10" as a raw string
        # comparison (proved above) -- this would raise if the helper used
        # naive string comparison instead of the parsed tuple.
        _assert_version_past_baseline(self, "0.1.10", baseline_patch=9)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4: proof that the checks above fail meaningfully in both
    directions -- when the two registries' versions differ, and when the
    plugin version is at or below the baseline (not merely above it)."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.42", "0.1.43")

    def test_fails_when_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, f"0.1.{BASELINE_PATCH}")

    def test_fails_when_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1.5")

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    FORGED_EM_REVIEW_ENTRY = {
        "name": "em-review",
        "description": (
            "Standalone version of the em-workflow review phase. "
            "/em-review:multi-review reviews the current git diff (whole "
            "codebase when no diff)."
        ),
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
                    _assert_other_entries_match_expected_shape(
                        self, [forged], OTHER_PLUGIN_ENTRIES_BASELINE
                    )

    def test_em_review_matcher_rejects_missing_or_malformed_version(self):
        missing = {
            key: value
            for key, value in self.FORGED_EM_REVIEW_ENTRY.items()
            if key != "version"
        }
        malformed = dict(self.FORGED_EM_REVIEW_ENTRY, version="not-a-version")
        for forged in (missing, malformed):
            with self.assertRaises(AssertionError):
                _assert_other_entries_match_expected_shape(
                    self, [forged], OTHER_PLUGIN_ENTRIES_BASELINE
                )

    def test_em_review_matcher_accepts_forged_higher_version(self):
        # AC-3 (task0005.md): the matcher never compares the version
        # against a literal, so a forged sample differing only by a higher
        # version is accepted.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="99.0.0")
        _assert_other_entries_match_expected_shape(
            self, [forged], OTHER_PLUGIN_ENTRIES_BASELINE
        )  # must not raise

    def test_em_review_matcher_rejects_new_unexpected_key(self):
        # Edge case (task0005.md): loosening only the version field must not
        # turn the comparison into a subset check -- a wholly new key must
        # still fail.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, extra_field="surprise")
        with self.assertRaises(AssertionError):
            _assert_other_entries_match_expected_shape(
                self, [forged], OTHER_PLUGIN_ENTRIES_BASELINE
            )


if __name__ == "__main__":
    unittest.main()

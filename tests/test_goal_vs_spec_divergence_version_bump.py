"""Tests for task0011 (goal-vs-spec-divergence): the em-workflow plugin
version bump to a patch strictly greater than 48 in both registries, with no
other field of either manifest changed.

Covers task0011 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0011.md):

- AC-1 (NFR6): `em-workflow/.claude-plugin/plugin.json` parses as JSON and
  its `version` is strictly greater than the value recorded as this
  feature's baseline (48).
- AC-2 (NFR6): `.claude-plugin/marketplace.json` parses as JSON and its
  em-workflow entry's `version` equals plugin.json's `version` exactly.
- AC-3 (NFR6): no field other than `version` changed in either manifest.
- AC-4 (NFR5): the new test module is discovered by
  `python3 -m unittest discover -s tests` and imports only the standard
  library. Verified by running that command from the repository root and
  observing this module's classes execute (discovery), plus manual review
  of the import block below (stdlib-only: json, re, unittest, pathlib) --
  not a dedicated test, since a module cannot assert its own discovery from
  inside itself.
- AC-5 (NFR6): the version comparison is a component-wise semantic-version
  comparison, not a string comparison.
- AC-6 (NFR8): every pre-existing module that reads either manifest still
  passes, including the ones asserting the plugin description and an
  earlier baseline comparison (test_spec_file_set_completeness_version_bump,
  test_routeback_reset_scope_version_bump, test_batch_stop_contract_version_
  bump, test_batch_policy_option_id_version_bump, and the
  test_recycled_task_id_*_version_bump family). Verified by running the
  full suite; not a dedicated test in this module, since it asserts over
  files this module does not own.
- AC-7 (NFR8): the full suite passes. Verified by running
  `python3 -m unittest discover -s tests` and observing zero new failures
  beyond this task's own baseline; not a dedicated test in this module.

This is a documentation/registry task (Test Notes: unit-level
document-contract assertions over parsed JSON), following the pattern
established by tests/test_spec_file_set_completeness_version_bump.py,
raising the baseline patch from 44 (the highest pre-existing BASELINE_PATCH
constant in this family, in test_recycled_task_id_carveout_version_bump.py /
test_recycled_task_id_contract_version_bump.py) to 48 -- this feature's own
version-bump module must go red on the un-bumped `0.1.48` tree, which any
lower predecessor baseline would not do. JSON files are parsed, never
pattern-matched.

Per task0011.md Design step 3 ("No other field of either manifest changes
-- in particular the plugin description stays as it is, since other
modules assert its content"), AC-3 is checked via key-set checks (catches
any added/removed field) plus per-field pins for every field this task must
not touch. Descriptions are pinned by a stable substring ANCHOR rather than
full literal text, following the precedent and its stated rationale in
test_spec_file_set_completeness_version_bump.py: a future unrelated feature
may legitimately reword a plugin description while bumping the version, and
a full-text pin here would make this now-pre-existing module (NFR4: no
pre-existing module may be edited except by the task owning the document it
pins) block that legitimate future edit. The two versions' equality check
(AC-2) and the marketplace top-level/owner/small identity fields (short and
structurally stable across every prior bump in this family) ARE pinned by
exact value, since those are true retention invariants for this task.

Matcher -> negative-proof inventory (Test Notes "Negative proof" + edge
case):

- `_assert_version_past_baseline` (the ordering matcher) ->
  `test_ordering_matcher_flags_forged_non_increasing_version` (a synthetic
  version equal to the baseline patch, i.e. non-increasing).
- `_assert_versions_equal` (the equality matcher) ->
  `test_equality_matcher_rejects_forged_differing_versions`.
- Component-wise vs string comparison (AC-5) ->
  `test_component_wise_comparison_is_numeric_not_lexicographic` (proves
  `0.1.10` sorts after `0.1.9` numerically while a raw string comparison of
  the same two values disagrees).
- Edge case (more/fewer than three components must not crash) ->
  `test_parser_does_not_crash_on_version_with_two_components` and
  `test_parser_does_not_crash_on_version_with_four_components`: the parser
  returns a plain tuple (never raises) and the ordering matcher fails with
  a controlled `AssertionError` (a short component list) or normalizes by
  using only the first three components (an over-long list), never with an
  unhandled Python exception.

Retention matchers (no negative proof needed, per the module docstring
convention in tests/test_spec_file_set_completeness_version_bump.py): the
key-set checks and the small identity-field pins (name/author/category/
source/$schema/owner/plugins-count) and the description anchors -- this
task does not touch any of those fields, so there is nothing for this
task's own edit to have broken; a forged sample there would only prove the
equality operator works, not that this task's edit respected the field.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-change baseline: both registries read 0.1.48 before this task's edit.
# The highest pre-existing BASELINE_PATCH in the tests/*_version_bump.py
# family was 44 (test_recycled_task_id_carveout/contract_version_bump.py).
BASELINE_PATCH = 48

COMPONENT_RE = re.compile(r"^\d+$")

EXPECTED_MANIFEST_KEYS = {"name", "description", "author", "version"}
EXPECTED_MANIFEST_NAME = "em-workflow"
EXPECTED_MANIFEST_AUTHOR = {"name": "em"}
MANIFEST_DESCRIPTION_ANCHOR = "/em-workflow:develop drives"

EXPECTED_MARKETPLACE_TOP_KEYS = {"$schema", "name", "description", "owner", "plugins"}
EXPECTED_MARKETPLACE_SCHEMA = "https://anthropic.com/claude-code/marketplace.schema.json"
EXPECTED_MARKETPLACE_NAME = "em-claude-plugins"
EXPECTED_MARKETPLACE_DESCRIPTION = (
    "Personal marketplace of Claude Code plugins maintained by em"
)
EXPECTED_MARKETPLACE_OWNER = {"name": "em"}
EXPECTED_PLUGINS_COUNT = 2

EXPECTED_EM_WORKFLOW_ENTRY_KEYS = {
    "name",
    "description",
    "author",
    "category",
    "source",
    "version",
}
EXPECTED_EM_WORKFLOW_NAME = "em-workflow"
EXPECTED_EM_WORKFLOW_AUTHOR = {"name": "em"}
EXPECTED_EM_WORKFLOW_CATEGORY = "workflow"
EXPECTED_EM_WORKFLOW_SOURCE = "./em-workflow"
EM_WORKFLOW_ENTRY_DESCRIPTION_ANCHOR = "/em-workflow:develop drives a git-setup gate"

EXPECTED_EM_REVIEW_ENTRY_KEYS = {"name", "description", "author", "category", "source"}
EXPECTED_EM_REVIEW_NAME = "em-review"
EXPECTED_EM_REVIEW_AUTHOR = {"name": "em"}
EXPECTED_EM_REVIEW_CATEGORY = "code-review"
EXPECTED_EM_REVIEW_SOURCE = "./em-review"
EM_REVIEW_ENTRY_DESCRIPTION_ANCHOR = (
    "/em-review:multi-review reviews the current git diff"
)


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


def _parse_version_components(version):
    """Splits a version string on '.' and coerces each component to int,
    returning a tuple whose length equals the number of components present
    (2, 3, 4, ...). Returns None -- never raises -- when `version` is not a
    string or any component is not a base-10 integer, so a version with more
    or fewer than three components is a comparable-but-differently-sized
    value, never a crash (Test Notes edge case)."""
    if not isinstance(version, str) or not version:
        return None
    parts = version.split(".")
    components = []
    for part in parts:
        if not COMPONENT_RE.match(part):
            return None
        components.append(int(part))
    return tuple(components)


def _assert_version_past_baseline(test, version):
    """The ordering matcher (AC-5): a component-wise, numeric semantic-
    version comparison -- never a string comparison. A version with fewer
    than three components fails with a controlled AssertionError (never an
    unhandled exception); a version with more than three components is
    normalized by using only its first three (major, minor, patch),
    ignoring any trailing build-style components."""
    components = _parse_version_components(version)
    test.assertIsNotNone(components, f"version {version!r} has non-numeric components")
    test.assertGreaterEqual(
        len(components), 3, f"version {version!r} has fewer than three components"
    )
    major, minor, patch = components[0], components[1], components[2]
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, BASELINE_PATCH)


def _assert_versions_equal(test, version_a, version_b):
    """The equality matcher (AC-2): the two registries must report the
    identical version string, checked by parsing both files, never by
    substring search."""
    test.assertEqual(version_a, version_b)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1, AC-3: the plugin manifest's version is past baseline; every
    other field is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_key_set_unchanged(self):
        self.assertEqual(set(self.data.keys()), EXPECTED_MANIFEST_KEYS)

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], EXPECTED_MANIFEST_NAME)

    def test_author_field_unchanged(self):
        self.assertEqual(self.data["author"], EXPECTED_MANIFEST_AUTHOR)

    def test_description_field_retains_stable_anchor(self):
        self.assertIn(MANIFEST_DESCRIPTION_ANCHOR, self.data["description"])


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2, AC-3: marketplace.json's em-workflow entry version is past
    baseline and equals the plugin manifest's exactly; no other field of
    the file, the em-workflow entry, or the em-review entry changed."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.em_workflow_entry = _marketplace_entry(cls.data, "em-workflow")
        cls.em_review_entry = _marketplace_entry(cls.data, "em-review")

    # -- top-level fields --

    def test_top_level_key_set_unchanged(self):
        self.assertEqual(set(self.data.keys()), EXPECTED_MARKETPLACE_TOP_KEYS)

    def test_schema_field_unchanged(self):
        self.assertEqual(self.data.get("$schema"), EXPECTED_MARKETPLACE_SCHEMA)

    def test_top_level_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), EXPECTED_MARKETPLACE_NAME)

    def test_top_level_description_field_unchanged(self):
        self.assertEqual(self.data.get("description"), EXPECTED_MARKETPLACE_DESCRIPTION)

    def test_owner_field_unchanged(self):
        self.assertEqual(self.data.get("owner"), EXPECTED_MARKETPLACE_OWNER)

    def test_plugins_list_length_unchanged(self):
        self.assertEqual(len(self.data.get("plugins", [])), EXPECTED_PLUGINS_COUNT)

    # -- em-workflow entry --

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.em_workflow_entry.get("version"))

    def test_em_workflow_entry_version_equals_plugin_manifest_exactly(self):
        _assert_versions_equal(
            self,
            self.em_workflow_entry.get("version"),
            self.manifest.get("version"),
        )

    def test_em_workflow_entry_key_set_unchanged(self):
        self.assertEqual(
            set(self.em_workflow_entry.keys()), EXPECTED_EM_WORKFLOW_ENTRY_KEYS
        )

    def test_em_workflow_entry_name_unchanged(self):
        self.assertEqual(self.em_workflow_entry.get("name"), EXPECTED_EM_WORKFLOW_NAME)

    def test_em_workflow_entry_author_unchanged(self):
        self.assertEqual(
            self.em_workflow_entry.get("author"), EXPECTED_EM_WORKFLOW_AUTHOR
        )

    def test_em_workflow_entry_category_unchanged(self):
        self.assertEqual(
            self.em_workflow_entry.get("category"), EXPECTED_EM_WORKFLOW_CATEGORY
        )

    def test_em_workflow_entry_source_unchanged(self):
        self.assertEqual(
            self.em_workflow_entry.get("source"), EXPECTED_EM_WORKFLOW_SOURCE
        )

    def test_em_workflow_entry_description_retains_stable_anchor(self):
        self.assertIn(
            EM_WORKFLOW_ENTRY_DESCRIPTION_ANCHOR,
            self.em_workflow_entry.get("description", ""),
        )

    # -- em-review entry (out of scope; every field retained) --

    def test_em_review_entry_key_set_unchanged(self):
        self.assertEqual(
            set(self.em_review_entry.keys()), EXPECTED_EM_REVIEW_ENTRY_KEYS
        )

    def test_em_review_entry_name_unchanged(self):
        self.assertEqual(self.em_review_entry.get("name"), EXPECTED_EM_REVIEW_NAME)

    def test_em_review_entry_author_unchanged(self):
        self.assertEqual(self.em_review_entry.get("author"), EXPECTED_EM_REVIEW_AUTHOR)

    def test_em_review_entry_category_unchanged(self):
        self.assertEqual(
            self.em_review_entry.get("category"), EXPECTED_EM_REVIEW_CATEGORY
        )

    def test_em_review_entry_source_unchanged(self):
        self.assertEqual(self.em_review_entry.get("source"), EXPECTED_EM_REVIEW_SOURCE)

    def test_em_review_entry_description_retains_stable_anchor(self):
        self.assertIn(
            EM_REVIEW_ENTRY_DESCRIPTION_ANCHOR,
            self.em_review_entry.get("description", ""),
        )

    def test_em_review_entry_has_no_version_key(self):
        self.assertNotIn("version", self.em_review_entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Negative proofs (Test Notes) and the edge case (component count must
    never crash the comparison)."""

    FORGED_NON_INCREASING_VERSION = f"0.1.{BASELINE_PATCH}"
    FORGED_VERSION_A = "0.1.49"
    FORGED_VERSION_B = "0.1.50"

    def test_ordering_matcher_flags_forged_non_increasing_version(self):
        """Test Notes: "a synthetic non-increasing version must fail the
        ordering matcher." A version equal to the baseline patch is not
        strictly greater, so it is non-increasing relative to the required
        advance."""
        self.assertIsNotNone(
            _parse_version_components(self.FORGED_NON_INCREASING_VERSION)
        )
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, self.FORGED_NON_INCREASING_VERSION)

    def test_equality_matcher_rejects_forged_differing_versions(self):
        """Test Notes: "a synthetic pair of manifests with mismatched
        versions must fail the equality matcher."""
        self.assertIsNotNone(_parse_version_components(self.FORGED_VERSION_A))
        self.assertIsNotNone(_parse_version_components(self.FORGED_VERSION_B))
        self.assertNotEqual(self.FORGED_VERSION_A, self.FORGED_VERSION_B)
        with self.assertRaises(AssertionError):
            _assert_versions_equal(self, self.FORGED_VERSION_A, self.FORGED_VERSION_B)

    def test_component_wise_comparison_is_numeric_not_lexicographic(self):
        """AC-5: the comparison is component-wise semantic-version, not a
        string comparison. Numerically, 0.1.10 sorts after 0.1.9; as raw
        strings, the two disagree ("0.1.10" < "0.1.9" lexicographically),
        so this proves the parser/comparison is genuinely numeric."""
        lower = _parse_version_components("0.1.9")
        higher = _parse_version_components("0.1.10")
        self.assertLess(lower, higher)
        self.assertLess("0.1.10", "0.1.9")

    def test_parser_does_not_crash_on_version_with_two_components(self):
        """Edge case: fewer than three components must not crash the
        comparison -- the parser still returns a tuple, and the ordering
        matcher fails with a controlled AssertionError."""
        components = _parse_version_components("0.1")
        self.assertEqual(components, (0, 1))
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1")

    def test_parser_does_not_crash_on_version_with_four_components(self):
        """Edge case: more than three components must not crash the
        comparison -- the parser returns all components, and the ordering
        matcher normalizes by comparing only the first three."""
        components = _parse_version_components(f"0.1.{BASELINE_PATCH + 1}.7")
        self.assertEqual(components, (0, 1, BASELINE_PATCH + 1, 7))
        _assert_version_past_baseline(self, f"0.1.{BASELINE_PATCH + 1}.7")

    def test_parser_returns_none_for_non_numeric_component(self):
        self.assertIsNone(_parse_version_components("0.1.x"))

    def test_entry_lookup_flags_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


if __name__ == "__main__":
    unittest.main()

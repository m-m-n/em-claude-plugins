"""Tests for task0003 (spec-file-set-completeness): the em-workflow plugin
version bump from `0.1.40` to `0.1.41` in both registries.

Covers task0003 Acceptance Criteria
(feature-docs/spec-file-set-completeness/tasks/task0003.md):

- AC-1 (FR9): `em-workflow/.claude-plugin/plugin.json` parses as JSON and
  its version reads `0.1.41`; every other field is unchanged.
- AC-2 (FR9): `.claude-plugin/marketplace.json` parses as JSON and its
  `em-workflow` entry reads version `0.1.41`; the `em-review` entry and
  every other field of the file are unchanged.
- AC-3 (FR9, NFR5): this module exists, is discovered by
  `python3 -m unittest discover -s tests` from the repository root,
  imports nothing outside the standard library, and asserts -- by parsing
  both files -- that the version has the shape `X.Y.Z`, that its major and
  minor are unchanged and its patch is strictly greater than `40`, that
  the two registries agree, and that the `em-review` entry is unchanged.
- AC-4 (NFR5): each matcher has a negative-proof test flagging a forged
  violating sample (baseline-patch version, mismatched registry pair,
  altered em-review entry).
- AC-5 (FR8, NFR1, NFR4): no file outside this task's three declared files
  is created or modified, every pre-existing module under `tests/` is
  byte-unchanged, and the full suite passes from the repository root. Not
  unit-testable from inside this module; verified by `git status`/`git
  diff --stat` against this task's declared file set and by running the
  full suite, both recorded in the implementer report rather than as a
  test here.

Per IMPLEMENTATION.md D4, the version assertion is the DURABLE invariant
(major/minor unchanged, patch strictly greater than the pre-change
baseline `40`, both registries agree with each other) rather than the
literal `0.1.41` -- following the precedent in
`tests/test_recycled_task_id_version_bump.py`, where a pinned literal was
rejected because the next unrelated version bump makes it stale. The
literal `0.1.41` itself is checked at verify time by direct file read
(VERIFICATION.md, AC-9).

"Every other field is unchanged" (AC-1, AC-2) is checked by (a) asserting
the top-level key set of each JSON structure is unchanged, and (b) pinning
the small, structurally-stable identity fields (`name`, `author`,
`category`, `source`) as literals, plus a stable-substring anchor for the
long free-text `description` fields. The `description` fields are
deliberately NOT pinned verbatim for `plugin.json` / the `em-workflow`
marketplace entry, for the same staleness reason D4 gives for the version
literal: a future unrelated feature could legitimately reword a plugin
description without touching the version, and this module -- once merged
-- becomes a pre-existing module future tasks may not edit (NFR4). The
`em-review` marketplace entry is the one exception: its full pre-change
field set (name, description, author, category, source) IS pinned
verbatim, per this task's plan (Design table: "its pre-change fields are
asserted unchanged") and because every task in this feature is explicitly
forbidden from touching it (task0003.md, Out of Scope) -- these are
retention anchors over a file this feature declares off-limits, not
durable-invariant candidates.

Matcher -> negative-proof inventory (AC-4; every matcher this module
adds):

- version shape/advancement (`_assert_version_past_baseline`) ->
  `test_version_matcher_flags_forged_baseline_patch_version` (plus
  `test_version_matcher_flags_malformed_shape` for the shape half)
- registries agree (`_assert_versions_agree`) ->
  `test_agreement_matcher_flags_a_mismatched_pair`
- em-review entry unchanged (`_assert_em_review_entry_unchanged`) ->
  `test_em_review_matcher_flags_an_altered_entry`
- marketplace entry lookup by name, never by index
  (`_marketplace_entry`) -> `test_entry_lookup_flags_a_missing_entry_name`

Retention matchers (no negative proof needed, per the module docstring
convention in `tests/test_recycled_task_id_consistency.py`): the key-set
and name/author/category/source identity checks, and the description
stable-substring anchors -- this task does not touch any of those fields,
so there is nothing for this task to have broken; a forged sample there
would only prove the equality/substring operator works, not that this
task's edit respected the field.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-change baseline: both registries read 0.1.40 before this task's edit.
BASELINE_PATCH = 40

EXPECTED_MANIFEST_KEYS = {"name", "description", "author", "version"}
EXPECTED_MANIFEST_NAME = "em-workflow"
EXPECTED_MANIFEST_AUTHOR = {"name": "em"}
# A short, stable substring of plugin.json's description, present at the
# very start of the text -- not the whole description (staleness reason
# above), just a non-vacuity anchor proving the field was not emptied or
# replaced wholesale.
MANIFEST_DESCRIPTION_ANCHOR = "/em-workflow:develop drives"

EXPECTED_MARKETPLACE_TOP_KEYS = {"$schema", "name", "description", "owner", "plugins"}
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
EM_WORKFLOW_ENTRY_DESCRIPTION_ANCHOR = "/em-workflow:develop drives"

# em-review is out of scope for every task in this feature (task0003.md,
# "Out of Scope"); its full pre-change field set is pinned verbatim, per
# the task plan's Design table ("its pre-change fields are asserted
# unchanged"). Captured from .claude-plugin/marketplace.json at this
# task's base revision. No `version` key -- the entry has never carried
# one (Test Notes edge case): comparing the whole dict, rather than
# fetching `entry.get("version")` and assuming presence, is what makes
# that edge case correct here.
EXPECTED_EM_REVIEW_ENTRY = {
    "name": "em-review",
    "description": (
        "Standalone version of the em-workflow review phase. "
        "/em-review:multi-review reviews the current git diff (whole "
        "codebase when no diff) with two-layer dynamic perspective "
        "selection, skill-injected generic reviewers (Claude + "
        "conditional cross-model validation via GPT/Codex and, when the "
        "separately-installed vertex-review plugin is present, Vertex AI "
        "MaaS / Meta Muse through its LiteLLM harness), cross-model "
        "agreement scoring, and bounded auto-fix (≤ 3 loops, skip "
        "with --report-only). Never commits; records default to /tmp "
        "(--records <dir> to override). Also reviews GitHub PRs by "
        "number/URL (report-only)."
    ),
    "author": {"name": "em"},
    "category": "code-review",
    "source": "./em-review",
}


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array index, the
    marketplace plugin list's order is not a contract (task0003.md,
    Design)."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _assert_version_past_baseline(test, version):
    """Durable invariant (IMPLEMENTATION.md D4): the version has the shape
    X.Y.Z, (major, minor) == (0, 1), and patch > BASELINE_PATCH. A fixed
    literal is guaranteed to go stale on the next unrelated version bump,
    per the precedent in tests/test_recycled_task_id_version_bump.py."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version or "")
    test.assertIsNotNone(match, f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = (int(g) for g in match.groups())
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, BASELINE_PATCH)


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _assert_em_review_entry_unchanged(test, entry):
    test.assertEqual(entry, EXPECTED_EM_REVIEW_ENTRY)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1 (FR9): plugin.json parses as JSON; its version is past the
    baseline patch (the durable form of "reads 0.1.41" -- D4); every other
    field is unchanged."""

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
    """AC-2 (FR9): marketplace.json parses as JSON; its em-workflow entry's
    version is past the baseline patch and agrees with the plugin
    manifest's version; the em-review entry and every other field of the
    file are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_agrees_with_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_top_level_key_set_unchanged(self):
        self.assertEqual(set(self.data.keys()), EXPECTED_MARKETPLACE_TOP_KEYS)

    def test_em_workflow_entry_key_set_unchanged(self):
        self.assertEqual(set(self.entry.keys()), EXPECTED_EM_WORKFLOW_ENTRY_KEYS)

    def test_em_workflow_entry_name_unchanged(self):
        self.assertEqual(self.entry["name"], EXPECTED_EM_WORKFLOW_NAME)

    def test_em_workflow_entry_author_unchanged(self):
        self.assertEqual(self.entry["author"], EXPECTED_EM_WORKFLOW_AUTHOR)

    def test_em_workflow_entry_category_unchanged(self):
        self.assertEqual(self.entry["category"], EXPECTED_EM_WORKFLOW_CATEGORY)

    def test_em_workflow_entry_source_unchanged(self):
        self.assertEqual(self.entry["source"], EXPECTED_EM_WORKFLOW_SOURCE)

    def test_em_workflow_entry_description_retains_stable_anchor(self):
        self.assertIn(
            EM_WORKFLOW_ENTRY_DESCRIPTION_ANCHOR, self.entry["description"]
        )

    def test_em_review_entry_unchanged(self):
        entry = _marketplace_entry(self.data, "em-review")
        _assert_em_review_entry_unchanged(self, entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- a
    negative-proof test for each of the module's matchers (AC-4), against
    exactly the three forged sample kinds task0003.md names: a version
    string at the baseline patch, a mismatched pair of versions, and an
    altered em-review entry."""

    def test_version_matcher_flags_forged_baseline_patch_version(self):
        forged_version = f"0.1.{BASELINE_PATCH}"
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, forged_version)

    def test_version_matcher_flags_malformed_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1")

    def test_agreement_matcher_flags_a_mismatched_pair(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.41", "0.1.42")

    def test_em_review_matcher_flags_an_altered_entry(self):
        forged = dict(EXPECTED_EM_REVIEW_ENTRY)
        forged["source"] = "./em-review-forked"
        with self.assertRaises(AssertionError):
            _assert_em_review_entry_unchanged(self, forged)

    def test_entry_lookup_flags_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


if __name__ == "__main__":
    unittest.main()

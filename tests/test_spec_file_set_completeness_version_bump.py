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
  altered em-review entry). Per task0005.md, the em-review entry's identity
  fields (name, author, category, source, and the description's stable
  substring anchor) are pinned exactly; its `version` is asserted present
  and dotted numeric, never against a literal, per
  `.claude/rules/core-plugin-version-bump.md`.
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
`em-review` marketplace entry (task0005.md, since the entry now legitimately
carries a `version` that changes over time per
`.claude/rules/core-plugin-version-bump.md`): its identity fields (name,
author, category, source) are pinned by literal, its description by the
same stable-substring-anchor convention as the other descriptions in this
module, and its `version` is asserted present and dotted numeric rather
than against a literal value -- the split keeps the property this task's
plan was placed to hold ("this feature's task altered nothing in the
em-review entry") for everything that is genuinely invariant, while stating
the one legitimately mutable field as a shape constraint. An explicit
key-set check is retained alongside the split so a new, unexpected key on
the entry still fails -- loosening only the version field must not turn the
comparison into a subset check (task0005.md edge case).

Matcher -> negative-proof inventory (AC-4; every matcher this module
adds):

- version shape/advancement (`_assert_version_past_baseline`) ->
  `test_version_matcher_flags_forged_baseline_patch_version` (plus
  `test_version_matcher_flags_malformed_shape` for the shape half)
- registries agree (`_assert_versions_agree`) ->
  `test_agreement_matcher_flags_a_mismatched_pair`
- em-review entry matches expected shape (`_assert_em_review_entry_matches`,
  task0005.md) -> `test_em_review_matcher_rejects_altered_identity_field`
  and `test_em_review_matcher_rejects_missing_or_malformed_version`; the
  positive proof that the version is asserted by shape, never by literal,
  is `test_em_review_matcher_accepts_forged_higher_version`; the key-set
  edge case is `test_em_review_matcher_rejects_new_unexpected_key`.
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
# "Out of Scope"); its identity fields are pinned verbatim, per the task
# plan's Design table ("its pre-change fields are asserted unchanged").
# Captured from .claude-plugin/marketplace.json at this task's base
# revision. Per task0005.md, the entry now legitimately carries a `version`
# that changes over time (`.claude/rules/core-plugin-version-bump.md`), so
# `version` is asserted by shape (present, dotted numeric) rather than
# pinned into this snapshot -- see `_assert_em_review_entry_matches`.
EXPECTED_EM_REVIEW_ENTRY_KEYS = {
    "name",
    "description",
    "author",
    "category",
    "source",
    "version",
}
EXPECTED_EM_REVIEW_NAME = "em-review"
EM_REVIEW_ENTRY_DESCRIPTION_ANCHOR = (
    "/em-review:multi-review reviews the current git diff"
)
EXPECTED_EM_REVIEW_AUTHOR = {"name": "em"}
EXPECTED_EM_REVIEW_CATEGORY = "code-review"
EXPECTED_EM_REVIEW_SOURCE = "./em-review"

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


def _assert_em_review_entry_matches(test, entry):
    """The em-review matcher (task0005.md): identity fields (name, author,
    category, source, and the description's stable substring anchor) are
    pinned exactly; the `version` field is asserted by shape only --
    present and dotted numeric -- never against a literal value, since
    `.claude/rules/core-plugin-version-bump.md` requires it to change over
    time. The key set is checked explicitly so the split does not silently
    degrade into a subset check when an unexpected key is added (task0005.md
    edge case)."""
    test.assertEqual(set(entry.keys()), EXPECTED_EM_REVIEW_ENTRY_KEYS)
    test.assertEqual(entry.get("name"), EXPECTED_EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EXPECTED_EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EXPECTED_EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EXPECTED_EM_REVIEW_SOURCE)
    test.assertIn(
        EM_REVIEW_ENTRY_DESCRIPTION_ANCHOR, entry.get("description", "")
    )
    test.assertTrue(
        _is_dotted_numeric_version(entry.get("version")),
        f"em-review version {entry.get('version')!r} is not a dotted numeric string",
    )


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

    def test_em_review_entry_matches_expected_shape(self):
        entry = _marketplace_entry(self.data, "em-review")
        _assert_em_review_entry_matches(self, entry)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- a
    negative-proof test for each of the module's matchers (AC-4), against
    the forged sample kinds task0003.md names (a version string at the
    baseline patch, a mismatched pair of versions, an altered em-review
    entry) plus the em-review shape proofs added by task0005.md (an altered
    identity field, a missing/malformed version, a forged higher version
    accepted, and a wholly new unexpected key rejected)."""

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

    def test_em_review_matcher_rejects_new_unexpected_key(self):
        # Edge case (task0005.md): loosening only the version field must not
        # turn the comparison into a subset check -- a wholly new key must
        # still fail.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, extra_field="surprise")
        with self.assertRaises(AssertionError):
            _assert_em_review_entry_matches(self, forged)

    def test_entry_lookup_flags_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


if __name__ == "__main__":
    unittest.main()

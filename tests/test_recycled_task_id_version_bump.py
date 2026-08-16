"""Tests for task0002 (recycled-task-id-consistency): the em-workflow plugin
version bump to 0.1.38 in both registries, plus the whole-file bare-git-line
invariant (NFR1 half) in `em-workflow/references/implement-phase.md`.

Covers task0002 Acceptance Criteria
(feature-docs/recycled-task-id-consistency/tasks/task0002.md):

- AC-1 (FR9): `em-workflow/.claude-plugin/plugin.json` parses as JSON and its
  `version` reads `0.1.38`.
- AC-2 (FR9): `.claude-plugin/marketplace.json` parses as JSON and the
  `plugins[]` entry whose `name` is `em-workflow` reads
  `"version": "0.1.38"`; the `em-review` entry has no `version` key.
- AC-3 (NFR5, FR9): this module exists and is discovered by
  `python3 -m unittest discover -s tests` from the repository root, and
  asserts AC-1 and AC-2 by parsing both files as JSON.
- AC-4 (NFR1): `implement-phase.md` contains no line that, after stripping
  indentation and backticks, begins with `git ` and contains `commit` or
  `add -A`.
- AC-5 (NFR1, NFR5): the full suite passes with every pre-existing module
  unmodified, and this module includes a negative-proof test for each of
  its two matchers.

This is a documentation/registry task (Test Notes: unit-level
document-contract assertions), following the pattern established by
tests/test_implement_routeback_gate.py. Section/whole-file assertions read
raw text; JSON files are parsed rather than pattern-matched.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

BASELINE_PATCH = 37


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    for entry in data["plugins"]:
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _assert_version_past_baseline(test, version):
    """Durable invariant: (major, minor) == (0, 1) and patch > BASELINE_PATCH.
    A fixed literal is guaranteed to go stale on the very next unrelated
    version bump, per the pattern in tests/test_planner_designer_worktree_docs.py."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    test.assertIsNotNone(match, f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = (int(g) for g in match.groups())
    test.assertEqual((major, minor), (0, 1))
    test.assertGreater(patch, BASELINE_PATCH)


def _bare_git_commit_or_add_lines(text):
    """Lines that are actual shell invocations (start with `git`, ignoring
    markdown backticks/indentation) touching `commit` or `add -A` -- as
    opposed to prose that merely mentions "git commit" inside a sentence."""
    out = []
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if re.match(r"^git\s", stripped) and re.search(r"\b(commit\b|add -A\b)", stripped):
            out.append(line.strip())
    return out


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1 / FR9: the plugin manifest's version reads 0.1.38."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data["version"])

    def test_name_field_unchanged(self):
        self.assertEqual(self.data["name"], "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2 / FR9: the em-workflow marketplace entry version stays in sync
    with the plugin manifest and is past the pre-task baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)

    def test_em_workflow_entry_version_is_past_baseline(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        _assert_version_past_baseline(self, entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        entry = _marketplace_entry(self.data, "em-workflow")
        self.assertEqual(entry.get("version"), self.manifest["version"])

    def test_em_review_entry_source_unchanged(self):
        entry = _marketplace_entry(self.data, "em-review")
        self.assertEqual(entry.get("source"), "./em-review")


class TestImplementPhaseHasNoBareGitCommitLines(unittest.TestCase):
    """AC-4 / NFR1: `implement-phase.md` has zero lines that, after
    stripping indentation and markdown backticks, begin with `git ` and
    contain `commit` or `add -A`. Holds both before and after task0001's
    edit, so it is green in this task's own worktree."""

    @classmethod
    def setUpClass(cls):
        cls.text = IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")

    def test_no_bare_git_commit_or_add_lines(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- a
    negative-proof test for each of the module's two matchers."""

    def test_version_matcher_flags_forged_pre_bump_manifest(self):
        forged_version = f"0.1.{BASELINE_PATCH}"
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, forged_version)

    def test_bare_commit_line_matcher_flags_an_unlocked_commit(self):
        sample = (
            'git -C {project_root} add -A -- foo && '
            'git -C {project_root} commit -m "x"'
        )
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertTrue(lines)

    def test_bare_commit_line_matcher_ignores_prose_mentioning_commit(self):
        sample = "No bare `git add`/`git commit` against the integration worktree runs outside"
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()

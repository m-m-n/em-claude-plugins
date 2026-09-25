"""Tests for task0001 (implement-guard-compatible-git-ops): the FR1-FR4
wording edits to `em-workflow/references/implement-phase.md` that make its
in-scope git operations pass `destructive-guard.py` unchanged.

Covers task0001 Acceptance Criteria
(feature-docs/implement-guard-compatible-git-ops/tasks/task0001.md):

- AC-1 (FR1): Step I.2.b step 4's fenced block no longer spells
  `git branch -D`; it instead runs the canonical non-forced step-4 branch
  deletion shape (`git -C {integration_worktree} branch -d
  "em-workflow/{feature}/{T}"`) after the unchanged `git worktree remove
  "$WT_ROOT/{T}"`; the old comment justifying forced deletion via the
  base_branch HEAD is gone, replaced by a comment naming the integration
  worktree's HEAD (the integration branch, containing the merge-base
  --is-ancestor-verified task branch) as the reason the non-forced deletion
  succeeds.
- AC-2 (FR2): the same step 4 item states, after the fenced block, that a
  failed branch deletion never falls back to a forced deletion (`-D` /
  `--force`), leaves the branch in place, and writes its name into the wake
  phase's own report; step 3's status write and step 5 are unaffected; the
  Batch mode paragraph after step 5 is untouched.
- AC-3 (FR3): the Branch & Worktree Model's refresh bullet states the
  literal-target rule naming all five excluded forms (shell variable,
  captured SHA, `HEAD`, `refs/heads/` prefix, omitted target), occurring
  exactly once in the file; the exit-4 recovery bullet that follows is
  untouched; the refresh literal survives at every in-scope site.
- AC-4 (FR4): the "Every workflow artifact" bullet states that artifacts
  are written with the Write tool (never a Bash heredoc) and that the Bash
  call running `commit-docs.sh` itself contains no heredoc; the bullet's
  opening line is unchanged; no new git command is introduced.

This module reads only `em-workflow/references/implement-phase.md`,
`em-workflow/references/phase-state.md`, `em-workflow/skills/develop/SKILL.md`
and `em-workflow/references/phases/create-spec-phase.md`. It does not
import from, and is not imported by, any other test module.

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
byte-identity assertions (fenced-block line ordering/content) compare the
raw, un-normalized text -- the two are never mixed in one assertion
(IMPLEMENTATION.md Conventions).

Every matcher asserting NEW wording is paired with a negative proof against
a verbatim pre-change sample of the same region, captured from this task's
own base revision (commit 6adfa1146151f119c553fee7026e639ef7c30ebf) --
never reconstructed -- plus a non-vacuity guard proving the sample is itself
well-formed (tdd-testing discipline).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
CREATE_SPEC_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

STEP4_START = "4. **Clean up** every newly-merged task's worktree and branch:"
STEP4_END = "5. **Refill**:"

REFRESH_BULLET_START = "- `merge-task.sh` advances `refs/heads/em-workflow/{feature}/integration` via"
EXIT4_BULLET_MARKER = "- **exit-4 recovery** (bounded;"

ARTIFACT_BULLET_START = "- Every workflow artifact —"
ARTIFACT_BULLET_END = "- At develop completion the user chooses"

BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model (READ FIRST)"
STEP_I0_HEADING = "## Step I.0: Preconditions"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so a multi-word assertion never depends on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _slice(text, start_anchor, end_anchor, search_start=0):
    start = text.index(start_anchor, search_start)
    end = text.index(end_anchor, start)
    return text[start:end]


def _step4_region(text):
    return _slice(text, STEP4_START, STEP4_END)


def _refresh_bullet(text):
    start = text.index(REFRESH_BULLET_START)
    end = text.index(EXIT4_BULLET_MARKER, start)
    return text[start:end]


def _artifact_bullet(text):
    return _slice(text, ARTIFACT_BULLET_START, ARTIFACT_BULLET_END)


def _branch_worktree_model_section(text):
    return _slice(text, BRANCH_WORKTREE_HEADING, STEP_I0_HEADING)


# --- AC-1: Step I.2.b step 4's branch deletion shape -----------------------


class TestStep4BranchDeletionShape(unittest.TestCase):
    """AC-1 (FR1)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.raw_region = _step4_region(cls.text)
        cls.region = _normalize_ws(cls.raw_region)

    def test_no_forced_branch_delete_spelling(self):
        self.assertNotIn("git branch -D", self.region)

    def test_worktree_remove_line_is_byte_identical_and_first(self):
        worktree_idx = self.raw_region.index('git worktree remove "$WT_ROOT/{T}"')
        branch_idx = self.raw_region.index(
            'git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"'
        )
        self.assertLess(worktree_idx, branch_idx)

    def test_canonical_step4_branch_deletion_present(self):
        self.assertIn(
            'git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"',
            self.raw_region,
        )

    def test_old_force_justification_comment_gone(self):
        self.assertNotIn("orchestrator's HEAD is", self.region)
        self.assertNotIn("base_branch, which does not", self.region)
        self.assertNotIn("-d would REFUSE here", self.region)

    def test_new_comment_names_integration_head_and_verified_merge(self):
        self.assertIn("integration worktree's HEAD is the integration", self.region)
        self.assertIn("merge-base --is-ancestor", self.region)

    def test_no_force_flagged_git_line_in_region(self):
        for line in self.raw_region.splitlines():
            candidate = line.strip()
            if candidate.startswith("git"):
                self.assertNotIn("-D", candidate)
                self.assertNotIn("--force", candidate)


# --- AC-2: the failure rule after the fenced block --------------------------


class TestStep4FailureRule(unittest.TestCase):
    """AC-2 (FR2)."""

    @classmethod
    def setUpClass(cls):
        cls.region = _normalize_ws(_step4_region(_read(IMPLEMENT_PHASE_PATH)))

    def test_no_forced_fallback_named_only_as_flags(self):
        self.assertIn("`-D` / `--force`", self.region)
        self.assertIn("do NOT fall back to a forced deletion", self.region)

    def test_branch_left_in_place(self):
        self.assertIn("leave the branch in place", self.region)

    def test_name_written_into_wake_phase_report(self):
        self.assertIn("write its name into this wake phase's own report", self.region)

    def test_step3_status_and_step5_unaffected(self):
        self.assertIn("task's status set in step 3", self.region)
        self.assertIn("step 5 below proceeds as before", self.region)


BATCH_MODE_PARAGRAPH_OPEN = (
    "**Batch mode**: in a `--batch` run, this applies only when step 5 "
    "re-enters\nthe launch phase (I.2.a) and ends the turn again"
)


class TestBatchModeParagraphAfterStep5Untouched(unittest.TestCase):
    """AC-2: the Batch mode paragraph following step 5 is not edited."""

    def test_batch_mode_paragraph_survives_byte_identical(self):
        text = _read(IMPLEMENT_PHASE_PATH)
        self.assertIn(BATCH_MODE_PARAGRAPH_OPEN, text)


# --- AC-3: literal refresh-target rule --------------------------------------


LITERAL_TARGET_RULE_ANCHOR = (
    "The reset target of every such refresh is always written as the "
    "literal branch name"
)


class TestLiteralRefreshTargetRule(unittest.TestCase):
    """AC-3 (FR3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.section = _normalize_ws(_branch_worktree_model_section(cls.text))

    def test_rule_present(self):
        self.assertIn(LITERAL_TARGET_RULE_ANCHOR, self.section)
        self.assertIn("em-workflow/{feature}/integration", self.section)

    def test_rule_names_all_five_excluded_forms(self):
        for phrase in (
            "shell variable",
            "captured SHA",
            "`HEAD`",
            "`refs/heads/`-prefixed name",
            "omitted target",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_rule_occurs_exactly_once_in_whole_file(self):
        normalized_whole_file = _normalize_ws(self.text)
        self.assertEqual(
            normalized_whole_file.count(LITERAL_TARGET_RULE_ANCHOR), 1
        )

    def test_rule_precedes_exit4_recovery_bullet(self):
        rule_idx = self.section.index(LITERAL_TARGET_RULE_ANCHOR)
        exit4_idx = self.section.index("**exit-4 recovery**")
        self.assertLess(rule_idx, exit4_idx)

    def test_added_text_has_no_git_prefixed_code_span(self):
        raw_bullet = _refresh_bullet(self.text)
        added_start = raw_bullet.index("NFR2).") + len("NFR2).")
        added_text = raw_bullet[added_start:]
        self.assertIn("reset target", added_text)
        for span in re.findall(r"`([^`]*)`", added_text, re.DOTALL):
            self.assertFalse(
                _normalize_ws(span).strip().startswith("git"),
                f"added text must introduce no git-prefixed code span, got: {span!r}",
            )

    def test_added_text_avoids_negative_anchor_spellings(self):
        raw_bullet = _refresh_bullet(self.text)
        added_start = raw_bullet.index("NFR2).") + len("NFR2).")
        added_text = raw_bullet[added_start:]
        for forbidden in (
            'reset --hard "$LAUNCH_TIP"',
            'reset --hard "$COMPLETION_TIP"',
        ):
            self.assertNotIn(forbidden, added_text)
        self.assertNotRegex(added_text, r'reset --hard "\$\{[^}]+\}"')

    def test_exit4_recovery_bullet_wording_untouched(self):
        self.assertIn("RE-CAPTURE the tip from the branch ref", self.section)


class TestRefreshLiteralSurvivesAtEveryOtherFile(unittest.TestCase):
    """AC-3: every in-scope refresh site outside implement-phase.md (Part C
    of the task plan) still contains the refresh literal targeting
    `em-workflow/{feature}/integration`; those three files are not edited
    by this task at all (Test Notes / A3 constraints)."""

    REFRESH_LITERAL = "em-workflow/{feature}/integration"

    def test_phase_state_exit4_recoveries_contain_the_literal(self):
        text = _read(PHASE_STATE_PATH)
        phase_state_section = _slice(
            text,
            "### Phase-state exit-4 recovery",
            "### Consecutive retry limit",
        )
        self.assertIn("reset --hard em-workflow/{feature}/integration", phase_state_section)

    def test_develop_skill_step_a_and_exit4_contain_the_literal(self):
        text = _read(DEVELOP_SKILL_PATH)
        step_a_section = _normalize_ws(_slice(text, "## Step A:", "\n### tier 決定\n"))
        self.assertIn("reset --hard em-workflow/{feature}/integration", step_a_section)
        exit4_section = _normalize_ws(
            _slice(text, "**exit-4 リカバリ**", "**batch: verify の cap 到達")
        )
        self.assertIn(self.REFRESH_LITERAL, exit4_section)

    def test_create_spec_stale_handling_contains_the_literal(self):
        text = _read(CREATE_SPEC_PHASE_PATH)
        stale_section = _slice(
            text, "5. **Stale handling**:", "Running step 1 before evaluating"
        )
        self.assertIn(self.REFRESH_LITERAL, stale_section)


# --- AC-4: artifact-write rule ----------------------------------------------


class TestArtifactWriteRule(unittest.TestCase):
    """AC-4 (FR4)."""

    @classmethod
    def setUpClass(cls):
        cls.raw_bullet = _artifact_bullet(_read(IMPLEMENT_PHASE_PATH))
        cls.bullet = _normalize_ws(cls.raw_bullet)

    def test_opening_line_unchanged(self):
        self.assertTrue(
            self.raw_bullet.startswith(
                "- Every workflow artifact — `feature-docs/{feature}/` (REQUIREMENTS.md,"
            )
        )

    def test_states_write_tool_never_bash_heredoc(self):
        self.assertIn("uses the Write tool, never a Bash heredoc", self.bullet)

    def test_states_commit_docs_call_has_no_heredoc(self):
        self.assertIn(
            "the Bash call that runs `commit-docs.sh` itself contains no heredoc",
            self.bullet,
        )

    def test_no_new_git_command_introduced(self):
        added_start = self.raw_bullet.index("Every such write uses the Write tool")
        added_text = self.raw_bullet[added_start:]
        # only up to the pre-existing "Nothing is ever written..." sentence
        added_text = added_text[: added_text.index("Nothing is ever written")]
        for span in re.findall(r"`([^`]*)`", added_text, re.DOTALL):
            self.assertFalse(_normalize_ws(span).strip().startswith("git"))


# --- Negative proofs: verbatim pre-change samples (captured via
# `git show 6adfa1146151f119c553fee7026e639ef7c30ebf:<path>`, this task's
# own base revision, before its edit landed) demonstrating the matchers
# above reject the old text. ---

PRE_CHANGE_STEP4_SAMPLE = (
    "4. **Clean up** every newly-merged task's worktree and branch:\n"
    "   ```bash\n"
    '   git worktree remove "$WT_ROOT/{T}"\n'
    '   git branch -D "em-workflow/{feature}/{T}"   # -D: merge already verified\n'
    "                                               # via merge-base --is-ancestor.\n"
    "                                               # -d would REFUSE here: the\n"
    "                                               # orchestrator's HEAD is\n"
    "                                               # base_branch, which does not\n"
    "                                               # contain the task branch (it\n"
    "                                               # was merged into integration,\n"
    "                                               # not base_branch).\n"
    "   ```\n"
)

PRE_CHANGE_REFRESH_BULLET_TAIL = (
    "  (safe: the integration worktree never carries uncommitted state across\n"
    "  turns — every workflow.yaml / document write, in every phase, is followed\n"
    "  by a `commit-docs.sh` commit in the same step; NFR2).\n"
)

PRE_CHANGE_ARTIFACT_BULLET_HEAD = (
    "  directly at its project-relative path inside the integration worktree, each\n"
    "  write followed by a `commit-docs.sh` commit (`docs({feature}): {summary}`).\n"
    "  Nothing is ever written to the main working tree by the workflow (the sole\n"
)


class TestPreChangeSampleGuards(unittest.TestCase):
    """Non-vacuity guards: every pre-change sample above really is a
    verbatim excerpt of the old, guard-incompatible text (tdd-testing
    discipline: a test that can never fail proves nothing)."""

    def test_step4_sample_is_well_formed(self):
        self.assertIn("git branch -D", PRE_CHANGE_STEP4_SAMPLE)
        self.assertIn("orchestrator's HEAD is", PRE_CHANGE_STEP4_SAMPLE)

    def test_refresh_bullet_tail_sample_is_well_formed(self):
        self.assertIn("NFR2)", PRE_CHANGE_REFRESH_BULLET_TAIL)

    def test_artifact_bullet_head_sample_is_well_formed(self):
        self.assertIn(
            "Nothing is ever written to the main working tree",
            PRE_CHANGE_ARTIFACT_BULLET_HEAD,
        )


class TestValidationDetectsRegressions(unittest.TestCase):
    """Negative proofs: each matcher asserting new wording fails
    meaningfully against the pre-change sample it targets."""

    def test_canonical_branch_deletion_matcher_flags_absence_in_pre_change(self):
        self.assertNotIn(
            'git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"',
            PRE_CHANGE_STEP4_SAMPLE,
        )

    def test_new_comment_matcher_flags_absence_in_pre_change(self):
        normalized = _normalize_ws(PRE_CHANGE_STEP4_SAMPLE)
        self.assertNotIn("integration worktree's HEAD is the integration", normalized)

    def test_old_comment_matcher_flags_presence_in_pre_change(self):
        normalized = _normalize_ws(PRE_CHANGE_STEP4_SAMPLE)
        self.assertIn("orchestrator's HEAD is", normalized)

    def test_failure_rule_matcher_flags_absence_in_pre_change(self):
        normalized = _normalize_ws(PRE_CHANGE_STEP4_SAMPLE)
        self.assertNotIn("do NOT fall back to a forced deletion", normalized)
        self.assertNotIn("write its name into this wake phase's own report", normalized)

    def test_literal_target_rule_matcher_flags_absence_in_pre_change(self):
        normalized = _normalize_ws(PRE_CHANGE_REFRESH_BULLET_TAIL)
        self.assertNotIn(LITERAL_TARGET_RULE_ANCHOR, normalized)

    def test_write_tool_matcher_flags_absence_in_pre_change(self):
        normalized = _normalize_ws(PRE_CHANGE_ARTIFACT_BULLET_HEAD)
        self.assertNotIn("uses the Write tool, never a Bash heredoc", normalized)


if __name__ == "__main__":
    unittest.main()

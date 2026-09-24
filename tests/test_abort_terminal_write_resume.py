"""Tests for task0002 (abort-docs-commit-precedence): the abort
terminal-commit exception -- the uncommitted terminal status write the
batch second-failure abort's Step I.2.c abort-phase terminal status commit
leaves behind on a second exit 4, its disposal at develop's resume entry,
and the re-derivation on the next run.

Covers task0002 Acceptance Criteria
(feature-docs/abort-docs-commit-precedence/tasks/task0002.md):

- AC-1 (FR4, FR8, TS-3): implement-phase.md's Branch & Worktree Model
  section names the "abort terminal-commit exception", states the
  uncommitted-write fact, scopes it to the "never carries uncommitted
  state across turns" claim for exactly this stop, and points to
  develop/SKILL.md Step A for the discard.
- AC-2 (FR6, TS-5): the same exception states re-derivation from committed
  facts only (task status, retry-consumed marker, journal), grants no
  additional automatic retry, and binds a successful re-applied commit to
  `implement_task_failed`.
- AC-3 (FR7, TS-5): the same exception states the `detail` /
  `resume_conditions` content for this stop.
- AC-4 (FR5, TS-4): develop/SKILL.md Step A's existing-workflow.yaml resume
  branch contains the resume-entry refresh, positioned before the Step A.5
  hand-off, running for batch and interactive alike, before Step B reads
  workflow.yaml.
- AC-5 (FR9, NFR4, TS-9): commit-docs.sh's RECOVERY CONTRACT comment no
  longer states the unqualified justification, names the exception (and
  defers to implement-phase.md), and the pinned FR9 phrases / carve-out
  sentence stay intact.
- AC-6 (NFR2, TS-3): not independently re-asserted here -- the byte-identity
  pins on the I.2.c batch-mode paragraph, the Branch & Worktree Model
  exit-4 bullet phrases, and the SKILL.md exit-4 リカバリ pins belong to
  `tests/test_tip_capture_idiom_uniformity.py` and other existing modules
  (IMPLEMENTATION.md Conventions: no task modifies an existing test
  module); this module's own new content never touches those regions.

This module reads only `em-workflow/references/implement-phase.md`,
`em-workflow/skills/develop/SKILL.md` and `em-workflow/scripts/commit-docs.sh`.
It does not import from, and is not imported by, any other test module
(repository convention, `tests/test_tip_capture_idiom_uniformity.py`).

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
the one byte-identity assertion (the RECOVERY CONTRACT carve-out sentence)
compares the raw, un-normalized text -- the two are never mixed in one
assertion (IMPLEMENTATION.md Conventions).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
COMMIT_DOCS_SH_PATH = PLUGIN_ROOT / "scripts" / "commit-docs.sh"

BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model (READ FIRST)"
STEP_I0_HEADING = "## Step I.0: Preconditions"

SKILL_RESUME_BRANCH_START = "- **存在する**（通常の再開）:"
SKILL_RESUME_BRANCH_END = (
    "- **存在しない**（ブランチ + worktree だけが作られ、create-spec が"
)

HANDOFF_PHRASE = "そのまま Step A.5 → Step B へ進む"
REFRESH_COMMAND_PHRASE = "reset --hard em-workflow/{feature}/integration"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so a multi-word assertion never depends on where this
    task's prose happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _normalize_comment_block(text):
    """Strip each line's leading `#` comment marker and indentation, then
    whitespace-normalize -- so a phrase a shell comment block wraps across
    several `#`-prefixed lines can still be asserted as one contiguous
    string."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped[1:].strip()
        lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _skill_resume_branch_section(text):
    start = text.index(SKILL_RESUME_BRANCH_START)
    end = text.index(SKILL_RESUME_BRANCH_END, start)
    return text[start:end]


def _recovery_contract_block(text):
    start = text.index("RECOVERY CONTRACT")
    end = text.index("# Non-artifact untracked", start)
    return text[start:end]


# --- AC-1: the exception is named and scoped (TS-3). ---


class TestImplementPhaseAbortExceptionNamedAndScoped(unittest.TestCase):
    """AC-1 (FR4, FR8, TS-3)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(
            _branch_worktree_model_section(_read(IMPLEMENT_PHASE_PATH))
        )

    def test_names_the_exception(self):
        self.assertIn("abort terminal-commit exception", self.section)

    def test_names_the_call_site(self):
        self.assertIn("Step I.2.c abort-phase terminal status commit", self.section)

    def test_states_the_uncommitted_write_fact(self):
        # The kind field's own name ("failed_kind") is deliberately never
        # spelled out here: implement-phase.md's existing
        # citation-discipline pin (tests/test_failed_kind_write_paths.py)
        # requires the FIRST occurrence of that literal anywhere in this
        # document to stay Step I.1's phase-start write -- a fact this
        # bullet's location (earlier, in Branch & Worktree Model) would
        # otherwise displace, so this bullet paraphrases the field instead
        # of restating its literal name.
        self.assertIn("`implement: failed`", self.section)
        self.assertIn("accompanying kind field valued `decision`", self.section)
        self.assertIn(
            "stays uncommitted in the integration worktree", self.section
        )
        self.assertIn("is not on the branch", self.section)

    def test_scopes_to_the_never_carries_uncommitted_state_claim(self):
        self.assertIn(
            "never carries uncommitted state across turns", self.section
        )
        self.assertIn("exactly this stop", self.section)

    def test_points_to_develop_skill_step_a_for_the_discard(self):
        self.assertIn("`skills/develop/SKILL.md` Step A", self.section)


# --- AC-2: re-derivation from committed facts only, no extra retry,
# binding to implement_task_failed (TS-5). ---


class TestImplementPhaseReDerivationAndBinding(unittest.TestCase):
    """AC-2 (FR6, TS-5)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(
            _branch_worktree_model_section(_read(IMPLEMENT_PHASE_PATH))
        )

    def test_re_derivation_names_committed_task_status(self):
        self.assertIn("committed task status", self.section)

    def test_re_derivation_names_retry_consumed_marker(self):
        self.assertIn("retry-consumed marker in `tasks.{T}.notes`", self.section)

    def test_re_derivation_names_the_journal(self):
        self.assertIn("and the journal", self.section)

    def test_grants_no_additional_automatic_retry(self):
        self.assertIn("grants no additional automatic retry", self.section)

    def test_successful_commit_binds_to_implement_task_failed(self):
        # The reason-code literal itself ("implement_task_failed") is
        # deliberately never spelled out here: implement-phase.md is one of
        # the four documents tests/test_batch_quiet_output_phase_wiring.py
        # and tests/test_batch_stop_contract_skill_wiring.py forbid from
        # restating any batch-terminal-line.md reason code -- the binding
        # is cited by its stop-point name instead, per this task's own
        # Design ("Cite it; do not restate it").
        self.assertIn("existing `implement-second-failure`", self.section)
        self.assertIn("binding", self.section)
        self.assertIn(
            "`references/batch-terminal-line.md`'s Precedence rule",
            self.section,
        )
        self.assertNotIn("implement_task_failed", self.section)


# --- AC-3: `detail` / `resume_conditions` content for this stop (TS-5). ---


class TestImplementPhaseDetailAndResumeConditions(unittest.TestCase):
    """AC-3 (FR7, TS-5)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(
            _branch_worktree_model_section(_read(IMPLEMENT_PHASE_PATH))
        )

    def test_detail_names_call_site_tasks_and_uncommitted_state(self):
        self.assertIn(
            "`detail` names the Step I.2.c abort-phase terminal status "
            "commit, the failing task(s), and that the terminal status "
            "write is uncommitted",
            self.section,
        )

    def test_resume_conditions_states_discard_and_re_derivation(self):
        self.assertIn(
            "`resume_conditions` states that the next run discards the "
            "leftover write at develop's resume entry and re-derives the "
            "abort from committed facts",
            self.section,
        )


# --- AC-4: develop/SKILL.md's resume-entry refresh (TS-4). ---


class TestSkillResumeRefresh(unittest.TestCase):
    """AC-4 (FR5, TS-4)."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _skill_resume_branch_section(_read(SKILL_PATH))
        cls.section = _normalize_ws(cls.raw_section)

    def test_contains_the_refresh_command(self):
        self.assertIn(REFRESH_COMMAND_PHRASE, self.section)

    def test_refresh_precedes_step_a5_handoff(self):
        # Non-vacuity: the hand-off phrase this task never touches is still
        # present in the sliced branch.
        self.assertIn(HANDOFF_PHRASE, self.section)
        refresh_idx = self.section.index(REFRESH_COMMAND_PHRASE)
        handoff_idx = self.section.index(HANDOFF_PHRASE)
        self.assertLess(refresh_idx, handoff_idx)

    def test_states_purpose_is_discarding_the_exception_leftover(self):
        self.assertIn("abort terminal-commit exception", self.section)

    def test_states_runs_for_batch_and_interactive_alike(self):
        self.assertIn("対話 / batch を問わず", self.section)

    def test_states_unconditional_not_gated_on_detection(self):
        self.assertIn("検出したかどうかにはゲートしない", self.section)

    def test_states_runs_before_step_b_reads_workflow_yaml(self):
        self.assertIn("Step B が workflow.yaml を読むより前", self.section)

    def test_states_discards_tracked_only_untracked_remain(self):
        self.assertIn("追跡対象ファイルの未コミット変更のみ", self.section)
        self.assertIn("untracked ファイルは残る", self.section)


# --- AC-5: commit-docs.sh's RECOVERY CONTRACT comment (TS-9). ---

# The five FR9-pinned phrases plus the byte-pinned carve-out sentence
# (IMPLEMENTATION.md Kept byte-identical list / task0002.md Kept
# byte-identical list) -- must survive this task's comment edit unchanged.
FR9_PINNED_PHRASES = (
    "EXCEPT a call site whose",
    "a proof of unreachability",
    "a defined terminal for an unexpected non-zero exit",
    "em-workflow/references/implement-phase.md",
    "I.2.c's route-back commit",
)

RECOVERY_CARVE_OUT_SENTENCE = (
    "#       RECOVERY CONTRACT (binding on every caller EXCEPT a call site whose\n"
    "#       owning protocol document states both a proof of unreachability and\n"
    "#       a defined terminal for an unexpected non-zero exit — today exactly\n"
    "#       one such site: `em-workflow/references/implement-phase.md` Step\n"
    "#       I.2.c's route-back commit): on exit 4 the caller"
)

OLD_UNQUALIFIED_JUSTIFICATION = (
    "safe per NFR2, this worktree never carries uncommitted state across turns"
)


class TestCommitDocsRecoveryContractQualified(unittest.TestCase):
    """AC-5 (FR9, NFR4, TS-9)."""

    @classmethod
    def setUpClass(cls):
        cls.raw_text = _read(COMMIT_DOCS_SH_PATH)
        cls.block = _normalize_comment_block(
            _recovery_contract_block(cls.raw_text)
        )

    def test_unqualified_justification_no_longer_present(self):
        self.assertNotIn(OLD_UNQUALIFIED_JUSTIFICATION, self.block)

    def test_names_the_exception_and_defers_to_implement_phase(self):
        self.assertIn("abort terminal-commit exception", self.block)
        self.assertIn("em-workflow/references/implement-phase.md", self.block)
        self.assertIn("Branch & Worktree", self.block)

    def test_fr9_pinned_phrases_intact(self):
        for phrase in FR9_PINNED_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.block)

    def test_carve_out_sentence_is_byte_identical(self):
        self.assertIn(RECOVERY_CARVE_OUT_SENTENCE, self.raw_text)

    def test_recapture_then_refresh_phrasing_still_pinned(self):
        # This task never touches the recapture-then-refresh phrasing the
        # sibling module (tests/test_tip_capture_idiom_uniformity.py) pins;
        # confirmed here too since this module already reads the same
        # block for its own qualifier assertions.
        recapture_idx = self.block.index("re-capture the tip from the branch ref")
        refresh_idx = self.block.index("refresh this worktree to that branch tip")
        self.assertLess(recapture_idx, refresh_idx)


# --- Negative proofs: verbatim pre-change samples (captured from the base
# revision via `git show HEAD:<path>`, before this task's edit landed --
# not paraphrased, not reconstructed) demonstrating the matchers above
# reject the old text. ---

PRE_CHANGE_EXIT4_BULLET_TAIL = (
    "  path: route back proceeds only when\n"
    "  no implementer of this feature can be running, so no `merge-task.sh` call\n"
    "  against this branch can be in flight either; therefore no concurrent ref\n"
    "  advance can occur between the route-back call site's refresh and its\n"
    "  commit attempt. The residual assumption is that no process outside this\n"
    "  develop run advances this ref; the route-back call site's own\n"
    "  stop-with-report terminal (Step I.2.c below) covers the case where that\n"
    "  assumption fails and an unexpected non-zero exit occurs there anyway.\n"
    "- Every workflow artifact — `feature-docs/{feature}/` (REQUIREMENTS.md,\n"
)

PRE_CHANGE_SKILL_RESUME_BRANCH = (
    "   - **存在する**（通常の再開）: そのまま Step A.5 → Step B へ進む\n"
)

PRE_CHANGE_RECOVERY_CONTRACT_BLOCK = (
    "RECOVERY CONTRACT (binding on every caller EXCEPT a call site whose\n"
    "#       owning protocol document states both a proof of unreachability and\n"
    "#       a defined terminal for an unexpected non-zero exit — today exactly\n"
    "#       one such site: `em-workflow/references/implement-phase.md` Step\n"
    "#       I.2.c's route-back commit): on exit 4 the caller\n"
    "#       MUST (1) re-capture the tip from the branch ref (e.g. `git\n"
    "#       rev-parse` against the branch — never the worktree's own `HEAD`),\n"
    "#       (2) refresh this worktree to that branch tip (e.g. `git reset\n"
    "#       --hard` to the branch name — safe per NFR2, this worktree never\n"
    "#       carries uncommitted state across turns), (3) re-apply the artifact\n"
    "#       edits this invocation was trying to commit, and (4) retry this\n"
    "#       script once. The protocol-side implementation of that loop (which\n"
    "#       caller performs steps 1-3, at which point in the orchestrator\n"
    "#       flow) is out of this script's scope.\n"
)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Negative proofs: each matcher above fails meaningfully against a
    verbatim pre-change sample, paired with a non-vacuity guard proving the
    sample is itself well-formed (tdd-testing discipline: a test that can
    never fail is not a test)."""

    def test_pre_change_implement_phase_tail_is_well_formed(self):
        # Non-vacuity guard: the sample really is the tail of the exit-4
        # bullet leading into the next bullet.
        self.assertIn("Every workflow artifact", PRE_CHANGE_EXIT4_BULLET_TAIL)

    def test_pre_change_implement_phase_tail_lacks_the_exception(self):
        normalized = _normalize_ws(PRE_CHANGE_EXIT4_BULLET_TAIL)
        self.assertNotIn("abort terminal-commit exception", normalized)
        self.assertNotIn("Step I.2.c abort-phase terminal status commit", normalized)

    def test_pre_change_skill_resume_branch_is_well_formed(self):
        # Non-vacuity guard: the sample still carries the hand-off phrase.
        self.assertIn(HANDOFF_PHRASE, PRE_CHANGE_SKILL_RESUME_BRANCH)

    def test_pre_change_skill_resume_branch_lacks_the_refresh(self):
        normalized = _normalize_ws(PRE_CHANGE_SKILL_RESUME_BRANCH)
        self.assertNotIn(REFRESH_COMMAND_PHRASE, normalized)
        self.assertNotIn("abort terminal-commit exception", normalized)

    def test_pre_change_recovery_contract_block_is_well_formed(self):
        # Non-vacuity guard: the sample carries the old unqualified
        # justification this task's edit removes.
        block = _normalize_comment_block(PRE_CHANGE_RECOVERY_CONTRACT_BLOCK)
        self.assertIn(OLD_UNQUALIFIED_JUSTIFICATION, block)

    def test_pre_change_recovery_contract_block_lacks_the_exception(self):
        block = _normalize_comment_block(PRE_CHANGE_RECOVERY_CONTRACT_BLOCK)
        self.assertNotIn("abort terminal-commit exception", block)


if __name__ == "__main__":
    unittest.main()

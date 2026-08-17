"""Tests for task0001 and task0003 (routeback-gate-postcondition).

task0001 widened the I.2.c route-back gate to a conjunction of both
blockers, collapsed the rejected path to a single generalized terminal, and
corrected the Branch & Worktree Model's exit-4 call-site enumeration in
`em-workflow/references/implement-phase.md`.

task0003 (rework round 1) grounds three surfaces that round-1 review found
ungrounded: (A) the rejected path now performs and commits an actual
`implement: failed` write instead of asserting the status "stays" that way
with no write producing it; (B) the gate's `in_progress` half is stated as a
union of workflow.yaml's status AND Step I.2.b's last-event-per-task
in-flight rule, never restated, only cited; (C) the exit-4 recovery
carve-out (`commit-docs.sh`'s RECOVERY CONTRACT header and
`em-workflow/skills/develop/SKILL.md`'s exit-4 scoping parenthetical) is
narrowed to match `implement-phase.md`'s own enumeration, which now also
lists the new rejected-path terminal commit as bound by the bounded
recovery, names the route-back commit as the sole carve-out, and restates
the unreachability proof over every path able to advance the integration
branch ref (not just `merge-task.sh` callers); the admitted route-back
path's write set/commit/cleanup order is also corrected (commit before
cleanup) so an unexpected non-zero exit at that commit never leaves
worktrees/branches deleted with the write set uncommitted.

Covers task0001 Acceptance Criteria
(feature-docs/routeback-gate-postcondition/tasks/task0001.md):

- AC-1 (FR1, NFR2): the gate is the conjunction of "no task has status
  `merged`" and "no task has status `in_progress`", both read from
  workflow.yaml task statuses, independent of the preceding drain.
- AC-2 (FR1): the four write-set instructions stay present and ordered
  before the worktree/branch cleanup, and the section still cites
  `references/workflow-patch.md`'s `replace_all` permission conditions as
  the owner without restating them.
- AC-3 (FR2): the rejected path states exactly one terminal, phrased to
  cover both blockers, with no retry/alternative/degraded route back
  offered; the sibling retry/abort options, the "NO skip option"
  paragraph, the heading and the batch-mode paragraph stay unchanged
  (heading and batch-mode paragraph byte-identical).
- AC-4 (FR3): in document order, the gate decision precedes the
  integration-worktree refresh, the tip capture, the write set, the
  cleanup and the `commit-docs.sh` invocation; an explicit sentence states
  the rejected path commits nothing and starts no cleanup.
- AC-5 (FR4): the Branch & Worktree Model's exit-4 recovery bullet no
  longer lists the I.2.c route-back commit as an applicable call site,
  still names Step I.1's and Step I.2.b's commits, and states the
  unreachability justification chain tied to the widened gate; the I.2.c
  call site no longer points at the bounded recovery procedure and
  instead states the unreachability plus a stop-with-report terminal.
- AC-6 (FR5, NFR3): all test changes live in this module; the module's
  test method count does not decrease; no test is skipped; every new
  absence assertion is paired with a proof that its matcher flags the
  pre-change wording.
- AC-7 (NFR1, NFR3): covered by this task's own file-set discipline (the
  diff touches only this file and the target document) and by the full
  suite passing.

Covers task0003 Acceptance Criteria
(feature-docs/routeback-gate-postcondition/tasks/task0003.md):

- AC-1 (FR2): the rejected path states that `implement` is SET to `failed`
  and that write is committed; "stays `failed`" (or any equivalent
  status-without-a-write phrasing) no longer appears on that path.
- AC-2 (FR3): the rejected path's scope sentence states no route-back write
  set / no cleanup / no route-back commit, with the terminal write plus its
  own commit as the only side effect; document order still gates before
  every side effect.
- AC-3 (FR1, NFR2): the gate's `in_progress` half is a union of
  workflow.yaml's status and Step I.2.b's last-event-per-task rule, cited
  not restated; both original conjuncts and the write set survive.
- AC-4 (FR4): the exit-4 enumeration lists the new rejected-path terminal
  commit as bound, names the route-back commit as the sole carve-out, and
  restates the unreachability proof over every ref-advancing path.
- AC-5 (FR4): the route back's write set -> commit -> cleanup order, and
  the resulting no-worktree-deleted-yet / leftover-state prose.
- AC-6 (FR4, NFR1): `commit-docs.sh`'s header and `develop/SKILL.md`'s
  parenthetical both state and scope the same carve-out.
- AC-7 (FR5, NFR3): all test changes stay in this module; no test removed
  or skipped; every new absence assertion is paired with a regression
  proof.
- AC-8 (NFR1, NFR3): full suite green; only this task's four files touched.

This is a documentation task (Test Notes: unit-level document-contract
assertions), following the pattern established by
tests/test_review_implement_develop_lock_contracts.py (task0007). Content
assertions compare against a whitespace-normalized copy of the section so
that line-wrap choices inside the prose never make an assertion brittle;
byte-identity assertions (AC-3's heading/batch-mode-paragraph clause)
compare the raw, un-normalized text.

Also covers task0002 Acceptance Criteria
(feature-docs/abort-phase-terminal/tasks/task0002.md), relocated here by
task0003 (abort-phase-terminal, rework round 1: SC-F containment fix; see
feature-docs/abort-phase-terminal/tasks/task0003.md) from the undeclared
module tests/test_abort_phase_terminal_batch_mode.py, which no longer
exists:

- AC-1 (FR7, NFR6): the `implement.failed-task` Non-packet gate row's Batch
  behavior cell in `em-workflow/references/batch-mode.md` states that the
  second failure on the same task takes the abort terminal in which the
  `implement` step's `status` is written to `failed` and that write is
  committed, and no longer contains the phrase "`implement` stays
  `failed`".
- AC-2 (FR7): the same row still contains the retry clause, the
  route-back-never-automatic clause, the gate id, and the detail pointer.
- AC-4 (FR7): a paired negative proof that the removed phrase is exactly
  the literal that was in the row before task0002's edit, plus a
  non-vacuity guard and a proof that the new-wording matcher also fails
  against the pre-change capture.

These relocated assertions read only `em-workflow/references/batch-mode.md`
and use the standard library only, unchanged in substance from their
original module.
"""

import json
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
COMMIT_DOCS_SH_PATH = PLUGIN_ROOT / "scripts" / "commit-docs.sh"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = PLUGIN_ROOT.parent / ".claude-plugin" / "marketplace.json"

I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"

# Current literal (task0001, abort-phase-terminal, brought to the
# post-change text) -- AC-3's/TS-9's byte-identity assertion needs this
# exact value. Captured via:
#   text.index("Batch mode (`references/batch-mode.md`")
#   .. text.index("### Supporting cast")
PRE_CHANGE_BATCH_MODE_PARAGRAPH = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase**: refresh\n"
    "the integration worktree, capture the tip, then set and commit the\n"
    "`implement` step's `status` to `failed` via `commit-docs.sh` (no\n"
    "`create-plan` `needs_update`, no task status or notes write set, no\n"
    "worktree or branch cleanup — the terminal status write and its own commit\n"
    "are the ONLY side effect), then report and stop; control returns via\n"
    "develop's stop condition 3, firing on the next Step B iteration reading\n"
    "`implement: failed`. The external service cuts a follow-up task.\n"
    "Route-back-to-planning is never taken automatically. Track the\n"
    "retry-consumed state per task in `tasks.{T}.notes`.\n"
    "\n"
)

# Historical regression guards, pre-dating this feature: the self-falsifying
# gate phrasing and the delegation mis-citation from an earlier round of
# this same section. This task neither introduces nor removes either, but
# both remain standing proof that the section has not regressed to them.
OLD_SELF_FALSIFYING_GATE_PHRASE = "every existing task is still `pending`"
OLD_DELEGATION_MISCITATION_PHRASE = "create-plan exemption owns that precedence"

# This task's own removed wording (task0001, routeback-gate-postcondition),
# captured before the edit landed -- needed for the absence assertions'
# paired regression proofs (AC-6).
OLD_DRAIN_AS_JUSTIFICATION_PHRASE = (
    "the drain above has already retired every `in_progress` sibling by "
    "this point"
)
OLD_MERGED_ONLY_TERMINAL_PHRASE = (
    "If any task has already merged, this automatic re-entry does not apply"
)
OLD_EXIT4_ENUMERATION_TAIL = (
    "Step I.2.b's wake-phase commit, and Step I.2.c's route-back commit"
)
OLD_I2C_RECOVERY_POINTER = "(exit-4 recovery: Branch & Worktree Model above)"

# This task's own removed wording (task0001, exit4-recovery-scope), captured
# before the edit landed -- needed for the absence assertion's paired
# regression proof (AC-1 / FR1).
OLD_EXIT4_CLOSED_ENUMERATION_CLAIM = (
    "the three `commit-docs.sh` call sites in this phase where exit 4 can "
    "occur"
)

# task0003's own removed wording (routeback-gate-postcondition, rework
# round 1), captured before the edit landed -- needed for the absence
# assertions' paired regression proofs (AC-7).
OLD_IMPLEMENT_STAYS_FAILED_PHRASE = "implement` stays `failed`"
OLD_UNSCOPED_REJECTED_PATH_PHRASE = (
    "nothing is committed and no worktree/branch cleanup is started"
)
OLD_EXIT4_MERGETASK_ONLY_PHRASE = (
    "implementers are the only callers of `merge-task.sh` against this "
    "integration branch"
)
OLD_COMMIT_DOCS_UNSCOPED_PHRASE = "binding on every caller):"
OLD_SKILL_EXIT4_UNSCOPED_PHRASE = "含む）: 戻り値 4"

# This task's own removed wording (task0001, abort-phase-terminal),
# captured before the edit landed -- needed for the absence assertion's
# paired regression proof (AC-1).
ABORT_PHASE_OPTION_MARKER = "- **abort phase**"
OLD_ABORT_MANUAL_HANDLING_PHRASE = (
    "leave `implement` as `failed` for manual handling"
)

# Shared SC-1-terminal phrases this task's abort-phase option and
# batch-mode paragraph both state (AC-3, IMPLEMENTATION.md SC-1).
EXCLUSION_PHRASES = (
    "no `create-plan` `needs_update`",
    "no task status or notes write set",
    "no worktree or branch cleanup",
)
ONLY_SIDE_EFFECT_PHRASE = (
    "the terminal status write and its own commit are the ONLY side effect"
)

# Relocated from tests/test_abort_phase_terminal_batch_mode.py (task0003,
# abort-phase-terminal, rework round 1: SC-F containment fix). These assert
# task0002's `implement.failed-task` Non-packet gate row in
# `em-workflow/references/batch-mode.md`. Names carry a `BATCH_MODE_` prefix
# so none of them rebinds a constant already defined above in this module
# (task0003 Design: "the relocated module-level constants to carry
# batch-mode-specific names").
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

BATCH_MODE_GATE_ID = "implement.failed-task"

# The exact phrase task0002's edit removes from the row's Batch behavior
# cell.
BATCH_MODE_REMOVED_PHRASE = "`implement` stays `failed`"

# The row's Batch behavior cell, byte-for-byte, exactly as it read before
# task0002's edit (captured verbatim via `repr()` against the base-commit
# file so the negative proof below is provably about the same literal the
# positive assertion checks the absence of -- the regression-guard pattern
# used elsewhere in this module).
BATCH_MODE_PRE_CHANGE_ROW = (
    "| `implement.failed-task` — Step I.2.c task failure after the "
    "parent-side-adoption protocol is exhausted "
    "(`references/implement-phase.md` Step I.2.c: retry / "
    "route-back-to-planning / abort via AskUserQuestion) | Auto-select "
    "**retry** once per task (kept worktree, I.2.a resume guard). A "
    "second failure on the SAME task → **abort phase** (`implement` "
    "stays `failed`). Route-back-to-planning is never taken "
    "automatically. Full detail: `references/implement-phase.md` Step "
    "I.2.c |"
)

# Elements that must survive task0002's edit unchanged in substance
# (task0002 plan Design section, "Elements of the row that MUST survive
# unchanged").
BATCH_MODE_RETRY_CLAUSE = (
    "Auto-select **retry** once per task (kept worktree, I.2.a resume "
    "guard)"
)
BATCH_MODE_ROUTE_BACK_CLAUSE = "Route-back-to-planning is never taken automatically"
BATCH_MODE_DETAIL_POINTER = "Full detail: `references/implement-phase.md` Step I.2.c"

# The new wording task0002 introduces to state SC-1's write-and-commit
# terminal.
BATCH_MODE_STATUS_WRITTEN_FAILED_PHRASE = (
    "`implement` step's `status` is written to `failed`"
)
BATCH_MODE_WRITE_COMMITTED_PHRASE = "that write is committed"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _read_batch_mode():
    return BATCH_MODE_PATH.read_text(encoding="utf-8")


def _batch_mode_gate_row(text):
    """Locates the single line of batch-mode.md's Non-packet gates table
    containing the gate id (task0002 Test Notes: "read the file, select the
    single line containing the gate id")."""
    matches = [line for line in text.splitlines() if BATCH_MODE_GATE_ID in line]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one line containing {BATCH_MODE_GATE_ID!r} in "
            f"{BATCH_MODE_PATH}, found {len(matches)}"
        )
    return matches[0]


def _read_commit_docs_sh():
    return COMMIT_DOCS_SH_PATH.read_text(encoding="utf-8")


def _read_develop_skill():
    return DEVELOP_SKILL_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where this
    task's prose happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _normalize_comment_block(text):
    """Strip each line's leading `#` comment marker and indentation, then
    whitespace-normalize -- so a phrase that a shell comment block wraps
    across several `#`-prefixed lines can still be asserted as one
    contiguous string, the same way `_normalize_ws` does for markdown
    prose."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped[1:].strip()
        lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _commit_docs_recovery_contract_header(text):
    """The RECOVERY CONTRACT header comment block inside commit-docs.sh's
    top-of-file exit-code documentation."""
    start = text.index("RECOVERY CONTRACT")
    end = text.index("# Non-artifact untracked", start)
    return text[start:end]


def _skill_exit4_paragraph(text):
    """The `**exit-4 リカバリ**` paragraph in develop/SKILL.md, sliced from
    its bold label to the sentence-final `しない）。` that closes it."""
    start = text.index("**exit-4 リカバリ**")
    end = text.index("しない）。", start) + len("しない）。")
    return text[start:end]


def _i2c_section(text):
    """The `### I.2.c: Failed handling` section, sliced from its heading to
    the next section heading -- includes the route-back/retry/abort
    bullets, the "NO skip option" paragraph and the batch-mode paragraph."""
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    """The `## Branch & Worktree Model` section, sliced from its heading to
    the next top-level step heading -- includes the exit-4 recovery
    bullet."""
    start = text.index("## Branch & Worktree Model")
    end = text.index("## Step I.0")
    return text[start:end]


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


class TestRouteBackGateIsConjunctionOfBothBlockers(unittest.TestCase):
    """AC-1 / FR1, NFR2: route-back admissibility is the conjunction of "no
    task has status `merged`" and "no task has status `in_progress`", both
    read from workflow.yaml task statuses, as an independent check -- never
    inferred from the preceding drain."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_gate_states_no_merged_task_conjunct(self):
        self.assertIn("no task has status `merged`", self.section)

    def test_gate_states_no_in_progress_task_conjunct(self):
        self.assertIn("no task has status `in_progress`", self.section)

    def test_conjuncts_are_joined_in_one_sentence(self):
        section = self.section
        idx1 = section.index("no task has status `merged`")
        idx2 = section.index("no task has status `in_progress`")
        self.assertLess(idx1, idx2)
        between = section[idx1:idx2]
        self.assertNotIn(". ", between)

    def test_conjuncts_are_read_from_workflow_yaml_task_statuses(self):
        self.assertIn("re-read from workflow.yaml task statuses", self.section)

    def test_gate_is_independent_of_the_drain(self):
        self.assertIn("not inferred from the drain above", self.section)

    def test_drain_not_presented_as_in_progress_justification(self):
        self.assertNotIn(OLD_DRAIN_AS_JUSTIFICATION_PHRASE, self.section)

    def test_stale_in_progress_entry_blocks_like_a_merged_task(self):
        self.assertIn("stale or unretired `in_progress` entry", self.section)
        self.assertIn(
            "blocks this path exactly as a `merged` task does", self.section
        )

    def test_old_self_falsifying_gate_phrasing_absent(self):
        # Historical regression guard (pre-dates this feature).
        self.assertNotIn(OLD_SELF_FALSIFYING_GATE_PHRASE, self.section)

    def test_in_progress_half_is_stated_as_a_union(self):
        # task0003 AC-3 / FR1, NFR2.
        self.assertIn("a union of two independent sources", self.section)

    def test_union_second_source_is_step_i2b_last_event_rule(self):
        self.assertIn(
            "Step I.2.b's last-event-per-task rule reporting a task "
            "in-flight",
            self.section,
        )

    def test_union_cites_step_i2b_as_owner_without_restating(self):
        self.assertIn("cited here as the owning rule, not restated", self.section)


class TestRouteBackWriteSetUnchanged(unittest.TestCase):
    """AC-2 / FR1: the four write-set instructions (`create-plan` ->
    `needs_update`; `implement` -> `pending`; failure reason into
    `tasks.{T}.notes`; every failed task's status -> `pending`) stay
    present and ordered before the worktree/branch cleanup, and the
    section still cites `references/workflow-patch.md`'s `replace_all`
    permission conditions as the owner without restating them."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_failure_reason_stays_recorded_in_notes(self):
        self.assertIn("tasks.{T}.notes", self.section)
        self.assertIn("failure reason", self.section)

    def test_failed_task_status_is_reset_to_pending(self):
        self.assertIn("tasks.{T}.status", self.section)
        # the reset targets `pending`, distinct from a bare mention of the
        # field -- assert the two tokens are close together, not merely
        # both present somewhere in the (large) section.
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx: idx + 60]
        self.assertIn("pending", window)

    def test_status_reset_create_plan_and_implement_are_one_write_set(self):
        section = self.section
        self.assertIn("create-plan` to `needs_update`", section)
        self.assertIn("implement` step back to `pending`", section)
        self.assertIn("tasks.{T}.status` back to `pending`", section)
        # all three writes, plus the notes-preservation clause, occur
        # before the worktree/branch cleanup starts -- i.e. they belong to
        # one coherent write description, not scattered after cleanup.
        cleanup_idx = section.index("git worktree remove --force")
        for token in (
            "create-plan` to `needs_update`",
            "implement` step back to `pending`",
            "tasks.{T}.status` back to `pending`",
            "tasks.{T}.notes",
        ):
            self.assertLess(section.index(token), cleanup_idx)

    def test_status_reset_cites_workflow_patch_as_owner_without_restating(self):
        # the reset is explained as what makes `replace_planning`
        # admissible on re-entry, citing workflow-patch.md's `replace_all`
        # permission conditions as the owner -- never restating the rule.
        self.assertIn("replace_planning", self.section)
        self.assertIn("references/workflow-patch.md", self.section)
        self.assertIn("replace_all", self.section)


class TestGateDecisionPrecedesAllSideEffects(unittest.TestCase):
    """AC-4 (task0001) / task0003 AC-2, AC-5: in document order, the gate
    decision precedes every side effect on both branches. task0003
    reordered the admitted path to write set -> commit -> cleanup (AC-5)
    and gave the rejected path its own write + commit (AC-2), so the
    ordering is re-expressed per-branch rather than as one flat chain."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup(self):
        # task0003 AC-5: commit now precedes cleanup (was cleanup then
        # commit before this task).
        section = self.section
        gate_idx = section.index(
            "This automatic re-entry applies only when the gate holds"
        )
        refresh_idx = section.index("Refresh the integration worktree first")
        tip_idx = section.index("ROUTEBACK_TIP")
        write_set_idx = section.index("make one ordered workflow.yaml write set")
        commit_idx = section.index("Commit that write set next, BEFORE any cleanup")
        cleanup_idx = section.index("Only once that commit")
        self.assertLess(gate_idx, refresh_idx)
        self.assertLess(refresh_idx, tip_idx)
        self.assertLess(tip_idx, write_set_idx)
        self.assertLess(write_set_idx, commit_idx)
        self.assertLess(commit_idx, cleanup_idx)

    def test_rejected_path_order_gate_terminal_write_terminal_commit(self):
        # task0003 AC-2: the rejected path's own gate < write < commit
        # order, independent of the admitted path's.
        section = self.section
        gate_idx = section.index("When the gate does not hold")
        write_idx = section.index("TERMINAL_TIP")
        commit_idx = section.index("implement route-back gate rejected")
        self.assertLess(gate_idx, write_idx)
        self.assertLess(write_idx, commit_idx)

    def test_no_route_back_instruction_after_the_gate_rejects(self):
        # task0003 AC-2: none of the admitted (route-back) path's own
        # write-set/cleanup instructions leak into the rejected branch.
        section = self.section
        tail = section[section.index("When the gate does not hold"):]
        self.assertNotIn("make one ordered workflow.yaml write set", tail)
        self.assertNotIn("git worktree remove --force", tail)
        self.assertNotIn("ROUTEBACK_TIP", tail)

    def test_rejected_path_states_rescoped_no_side_effect_sentence(self):
        # task0003 AC-2: replaces the old unscoped sentence (rewritten,
        # never deleted -- IMPLEMENTATION.md D4).
        self.assertIn(
            "There is no route-back write set, no worktree/branch "
            "cleanup and no route-back commit on this path — the "
            "terminal status write and its own commit are the ONLY side "
            "effect.",
            self.section,
        )

    def test_old_unscoped_no_side_effect_sentence_absent(self):
        self.assertNotIn(OLD_UNSCOPED_REJECTED_PATH_PHRASE, self.section)


class TestRejectedPathHasSingleGeneralizedTerminal(unittest.TestCase):
    """AC-3 (task0001) / task0003 AC-1: when the gate does not hold -- for
    any blocker -- the section states exactly one terminal: `create-plan`
    not set to `needs_update`, `implement` set (and committed) to `failed`
    -- task0003 replaced the old "stays `failed`" phrasing, which asserted
    the status without any write producing it -- control returned via
    develop's stop condition 3 (the same terminal as "abort phase"), with
    no retry, alternative recovery or degraded route back offered."""

    @classmethod
    def setUpClass(cls):
        # Slice on the normalized copy: the split point's anchor phrase
        # can straddle a line-wrap boundary in the raw markdown, which
        # would make `.index()` raise on a value that is genuinely
        # present.
        cls.section = _normalize_ws(_i2c_section(_read()))
        start = cls.section.index("When the gate does not hold")
        end = cls.section.index("- **abort phase**", start)
        cls.branch = cls.section[start:end]

    def test_covers_the_merged_blocker(self):
        self.assertIn("because a task has status `merged`", self.branch)

    def test_covers_the_in_progress_blocker(self):
        self.assertIn("because a task has status `in_progress`", self.branch)

    def test_create_plan_not_set_to_needs_update(self):
        self.assertIn(
            "create-plan` is NOT set to `needs_update`", self.branch
        )

    def test_implement_is_written_to_failed_and_committed(self):
        # task0003 AC-1: replaces the old status-without-a-write phrasing
        # (rewritten, never deleted -- IMPLEMENTATION.md D4).
        self.assertIn(
            "sets the `implement` step's `status` to `failed`", self.branch
        )
        self.assertIn("the single write this path makes", self.branch)
        self.assertIn("commits exactly that write", self.branch)

    def test_old_stays_failed_phrasing_absent(self):
        # task0003 AC-1: "stays `failed`" (or any equivalent
        # status-without-a-write formulation) no longer appears on this
        # path.
        self.assertNotIn(OLD_IMPLEMENT_STAYS_FAILED_PHRASE, self.branch)

    def test_control_returns_via_stop_condition_3(self):
        self.assertIn("stop condition 3", self.branch)
        self.assertIn("abort phase", self.branch)

    def test_no_retry_alternative_or_degraded_route_back_offered(self):
        self.assertIn(
            "No retry loop, no alternative recovery route, and no "
            "degraded route back is offered",
            self.branch,
        )

    def test_no_rework_or_append_handoff(self):
        self.assertNotIn("rework", self.branch)
        self.assertNotIn("append", self.branch)

    def test_old_single_blocker_only_phrasing_absent(self):
        self.assertNotIn(OLD_MERGED_ONLY_TERMINAL_PHRASE, self.section)


class TestExit4EnumerationExcludesRouteBackCommit(unittest.TestCase):
    """AC-5 (task0001) / task0003 AC-4: the Branch & Worktree Model's
    exit-4 recovery bullet no longer lists the I.2.c route-back commit as
    an applicable call site, still names Step I.1's baseline commit and
    Step I.2.b's wake-phase commit, and additionally lists task0003's new
    rejected-path terminal status commit as bound by the bounded recovery.
    task0003 restated the unreachability proof over every path able to
    advance the integration branch ref (not just `merge-task.sh` callers)
    and named the residual assumption plus its covering terminal; the
    bounded recovery procedure sentences themselves are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_branch_worktree_model_section(_read()))

    def test_enumeration_names_step_i1_and_step_i2b(self):
        self.assertIn("Step I.1's baseline commit", self.section)
        self.assertIn("Step I.2.b's wake-phase commit", self.section)

    def test_enumeration_names_rejected_path_terminal_commit_as_bound(self):
        # task0003 AC-4: the new call site is enumerated as bound by the
        # bounded recovery (never as an unreachable exclusion).
        self.assertIn(
            "Step I.2.c's rejected-path terminal status commit", self.section
        )

    def test_enumeration_no_longer_lists_i2c_route_back_commit(self):
        self.assertNotIn(OLD_EXIT4_ENUMERATION_TAIL, self.section)

    def test_carve_out_names_route_back_commit_explicitly(self):
        # task0003 AC-4: the single carve-out is named "route-back" in
        # those words, distinct from the (bound) rejected-path terminal
        # commit just enumerated above.
        self.assertIn(
            "The single carve-out is Step I.2.c's **route-back** commit",
            self.section,
        )

    def test_states_unreachability_chain_tied_to_widened_gate(self):
        section = self.section
        self.assertIn(
            "`merge-task.sh`, run only by this feature's implementers",
            section,
        )
        self.assertIn(
            "the orchestrator's own `commit-docs.sh` calls", section
        )
        self.assertIn("no implementer of this feature can be running", section)
        self.assertIn("no concurrent ref advance can occur", section)

    def test_proof_enumerates_both_ref_advancing_paths(self):
        # task0003 AC-4: the proof enumerates the paths able to advance
        # the ref, rather than reasoning only over `merge-task.sh` callers.
        section = self.section
        self.assertIn("enumerates the paths able to advance", section)
        self.assertIn(
            "which never race each other because the orchestrator is "
            "single-threaded",
            section,
        )

    def test_old_merge_task_sh_only_callers_phrase_absent(self):
        self.assertNotIn(OLD_EXIT4_MERGETASK_ONLY_PHRASE, self.section)

    def test_names_residual_assumption_and_its_covering_terminal(self):
        section = self.section
        self.assertIn(
            "residual assumption is that no process outside this develop "
            "run advances this ref",
            section,
        )
        self.assertIn(
            "the route-back call site's own stop-with-report terminal",
            section,
        )

    def test_recovery_procedure_sentences_survive(self):
        # IMPLEMENTATION.md D4: only the enumeration changes; the recovery
        # procedure sentences themselves stay as they are.
        section = self.section
        self.assertIn("retry `commit-docs.sh` once", section)
        self.assertIn("second exit 4", section)
        self.assertIn("stops the phase", section)

    def test_scope_is_universal_over_every_call_site(self):
        # task0001 (exit4-recovery-scope) AC-1 / FR1, FR2: the bounded
        # recovery's scope is stated as a universal quantifier over every
        # `commit-docs.sh` call site in the implement phase, not a closed
        # list of named sites.
        self.assertIn(
            "applies to every `commit-docs.sh` call site in the implement "
            "phase",
            self.section,
        )

    def test_old_closed_enumeration_exhaustiveness_claim_absent(self):
        # task0001 (exit4-recovery-scope) AC-1 / FR1: the tail asserting
        # that the listed sites are the three `commit-docs.sh` call sites
        # in this phase where exit 4 can occur no longer appears anywhere
        # in the document.
        self.assertNotIn(OLD_EXIT4_CLOSED_ENUMERATION_CLAIM, self.section)
        self.assertNotIn(
            OLD_EXIT4_CLOSED_ENUMERATION_CLAIM, _normalize_ws(_read())
        )

    def test_bound_side_names_step_i2a_launch_time_write(self):
        # task0001 (exit4-recovery-scope) AC-2: Step I.2.a's launch-time
        # task status / task branch write is named on the bound side
        # inside this same bullet -- scoped to the Branch & Worktree Model
        # section (narrower than the whole file, where "Step I.2.a" also
        # occurs elsewhere without naming this write).
        self.assertIn(
            "Step I.2.a's launch-time task status / task branch write",
            self.section,
        )

    def test_bound_side_names_step_i3_completion_write(self):
        # task0001 (exit4-recovery-scope) AC-2: Step I.3's
        # implement-completed / completed-commit write is named on the
        # bound side inside this same bullet -- same scoping rationale as
        # the I.2.a assertion above.
        self.assertIn(
            "Step I.3's implement-completed / completed-commit write",
            self.section,
        )


class TestI2cCallSiteNoLongerPointsAtRecoveryProcedure(unittest.TestCase):
    """AC-5 / FR4 (second half): the I.2.c route-back commit no longer
    points at the bounded exit-4 recovery procedure -- it states that exit
    4 cannot occur at this call site and that an unexpected non-zero exit
    stops the phase with a report. task0003 AC-5 additionally moved this
    commit to precede the worktree/branch cleanup, so the same unexpected
    non-zero exit now stops the phase with nothing deleted yet, and the
    section names the one leftover state the new order can still produce
    plus the existing Step I.2.a rule that covers it."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_old_recovery_pointer_removed(self):
        self.assertNotIn(OLD_I2C_RECOVERY_POINTER, self.section)

    def test_states_exit4_unreachable_at_this_call_site(self):
        self.assertIn("exit 4 cannot occur at this call site", self.section)

    def test_states_stop_with_report_terminal_for_unexpected_exit(self):
        self.assertIn(
            "stops the phase immediately with a report", self.section
        )

    def test_points_to_branch_worktree_model_for_justification(self):
        self.assertIn(
            "Branch & Worktree Model's exit-4 recovery bullet above",
            self.section,
        )

    def test_states_no_worktree_or_branch_deleted_yet_at_that_commit(self):
        # task0003 AC-5: the commit now precedes cleanup, so an
        # unexpected non-zero exit here has nothing destroyed yet.
        self.assertIn(
            "a report, at a point where no worktree or branch has been "
            "deleted",
            self.section,
        )

    def test_states_leftover_state_and_i2a_rule_that_covers_it(self):
        # task0003 AC-5: the one residual leftover state the new order
        # can produce, plus the existing rule that already covers it.
        self.assertIn(
            "this order's one residual leftover state is the commit "
            "succeeding and the cleanup not yet running",
            self.section,
        )
        self.assertIn(
            "Step I.2.a's resume guard and its recycled-task-id rule "
            "already cover",
            self.section,
        )


class TestAbortPhaseOptionHasSC1Terminal(unittest.TestCase):
    """AC-1 (task0001, abort-phase-terminal) / FR1, NFR2: the slice from
    `- **abort phase**` to the batch-mode paragraph's start states, in
    order, the worktree refresh (containing the literal `reset --hard
    em-workflow/{feature}/integration`), a `rev-parse HEAD` tip capture, a
    write of the `implement` step's `status` to `failed`, and a
    `commit-docs.sh` invocation carrying that captured tip as its third
    argument. The old "leave `implement` as `failed` for manual handling"
    phrasing is gone; the bullet still opens with the exact literal
    `- **abort phase**`; the section heading stays byte-identical."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.raw_section = _i2c_section(cls.text)
        cls.section = _normalize_ws(cls.raw_section)
        start = cls.section.index(ABORT_PHASE_OPTION_MARKER)
        end = cls.section.index("Batch mode (`references/batch-mode.md`", start)
        cls.slice = cls.section[start:end]

    def test_abort_bullet_opens_with_exact_literal(self):
        idx = self.raw_section.index("- **abort phase**")
        self.assertEqual(
            self.raw_section[idx : idx + len("- **abort phase**")],
            "- **abort phase**",
        )

    def test_states_worktree_refresh(self):
        self.assertIn(
            "reset --hard em-workflow/{feature}/integration", self.slice
        )

    def test_states_tip_capture(self):
        self.assertIn("rev-parse HEAD", self.slice)

    def test_states_implement_failed_write(self):
        self.assertIn(
            "set the `implement` step's `status` to `failed`", self.slice
        )

    def test_states_commit_docs_sh_with_captured_tip(self):
        self.assertIn("commit-docs.sh", self.slice)
        self.assertIn("$ABORT_TIP", self.slice)

    def test_order_refresh_before_tip_before_write_before_commit(self):
        section = self.slice
        refresh_idx = section.index(
            "reset --hard em-workflow/{feature}/integration"
        )
        tip_idx = section.index("ABORT_TIP=$(git")
        write_idx = section.index(
            "set the `implement` step's `status` to `failed`"
        )
        commit_idx = section.index("commit-docs.sh")
        self.assertLess(refresh_idx, tip_idx)
        self.assertLess(tip_idx, write_idx)
        self.assertLess(write_idx, commit_idx)

    def test_old_manual_handling_phrase_absent(self):
        self.assertNotIn(OLD_ABORT_MANUAL_HANDLING_PHRASE, self.section)

    def test_heading_still_byte_identical(self):
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx : idx + len(I2C_HEADING)], I2C_HEADING)


class TestBothAbortDescriptionsShareTheSameTerminal(unittest.TestCase):
    """AC-3 (task0001, abort-phase-terminal) / FR3, FR4: both abort
    descriptions -- the `- **abort phase**` option and the batch-mode
    second-failure abort -- state that the terminal status write and its
    commit are the only side effect (naming the exclusions: no
    `create-plan` `needs_update`, no task status or notes write set, no
    worktree or branch cleanup), and both name develop's stop condition 3
    together with the "next Step B iteration reading `implement: failed`"
    formulation. The rejected path's own two side-effect sentences are
    untouched."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))
        abort_start = cls.section.index(ABORT_PHASE_OPTION_MARKER)
        batch_start = cls.section.index(
            "Batch mode (`references/batch-mode.md`", abort_start
        )
        cls.abort_bullet = cls.section[abort_start:batch_start]
        cls.batch_paragraph = cls.section[batch_start:]

    def test_abort_bullet_states_exclusions_and_only_side_effect(self):
        for phrase in EXCLUSION_PHRASES:
            self.assertIn(phrase, self.abort_bullet)
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self.abort_bullet)

    def test_batch_mode_paragraph_states_exclusions_and_only_side_effect(self):
        for phrase in EXCLUSION_PHRASES:
            self.assertIn(phrase, self.batch_paragraph)
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self.batch_paragraph)

    def test_abort_bullet_names_stop_condition_3_with_step_b_formulation(self):
        self.assertIn("stop condition 3", self.abort_bullet)
        self.assertIn(
            "next Step B iteration reading `implement: failed`",
            self.abort_bullet,
        )

    def test_batch_mode_paragraph_names_stop_condition_3_with_step_b_formulation(
        self,
    ):
        self.assertIn("stop condition 3", self.batch_paragraph)
        self.assertIn(
            "next Step B iteration reading `implement: failed`",
            self.batch_paragraph,
        )

    def test_rejected_path_side_effect_sentences_untouched(self):
        self.assertIn(
            "There is no route-back write set, no worktree/branch "
            "cleanup and no route-back commit on this path — the "
            "terminal status write and its own commit are the ONLY side "
            "effect.",
            self.section,
        )


class TestExit4EnumerationNamesAbortPhaseCommit(unittest.TestCase):
    """AC-5 (task0001, abort-phase-terminal) / FR6: the Branch & Worktree
    Model's exit-4 recovery bullet names the abort terminal status commit
    among the call sites bound by the bounded recovery; the three
    previously-named entries survive; the single carve-out stays exactly
    Step I.2.c's route-back commit (the abort call site is never
    described as carved out); the withdrawn closed-enumeration literal
    stays absent."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_branch_worktree_model_section(_read()))

    def test_names_abort_phase_terminal_status_commit(self):
        self.assertIn(
            "Step I.2.c's abort-phase terminal status commit", self.section
        )

    def test_three_prior_entries_still_named(self):
        self.assertIn("Step I.1's baseline commit", self.section)
        self.assertIn("Step I.2.b's wake-phase commit", self.section)
        self.assertIn(
            "Step I.2.c's rejected-path terminal status commit", self.section
        )

    def test_carve_out_still_single_route_back_commit(self):
        self.assertIn(
            "The single carve-out is Step I.2.c's **route-back** commit",
            self.section,
        )

    def test_abort_call_site_never_described_as_carved_out(self):
        # The carve-out sentence names only the route-back commit; the new
        # abort entry sits in the bound (`for example`) list, not here.
        idx = self.section.index(
            "The single carve-out is Step I.2.c's **route-back** commit"
        )
        window = self.section[idx : idx + 200]
        self.assertNotIn("abort-phase", window)

    def test_closed_enumeration_claim_still_absent(self):
        self.assertNotIn(OLD_EXIT4_CLOSED_ENUMERATION_CLAIM, self.section)


class TestDelegationCitesStopCondition3Clause(unittest.TestCase):
    """Regression coverage (out of this task's scope, per task0001.md
    Surface B's out-of-scope note): the delegation sentence naming Step
    B's stop-condition-3 precedence clause is untouched by this task's
    edits."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_names_stop_condition_3_precedence_clause(self):
        self.assertIn("skills/develop/SKILL.md", self.section)
        self.assertIn("Step B's stop-condition-3 precedence clause", self.section)

    def test_no_longer_attributes_precedence_to_create_plan_exemption(self):
        # Historical regression guard (pre-dates this feature).
        self.assertNotIn(OLD_DELEGATION_MISCITATION_PHRASE, self.section)


class TestContainmentAndInvariants(unittest.TestCase):
    """AC-3 (heading/batch-mode-paragraph clause) / NFR1: the heading and
    the batch-mode paragraph stay byte-identical, and implement-phase.md
    has no bare `git commit` / `git add -A` line. The rest of AC-7
    (file-set containment; the full suite passing unmodified elsewhere) is
    covered by this task's own file-set discipline and by the suites
    outside this file, run unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_is_byte_identical(self):
        self.assertIn(I2C_HEADING, self.text)
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx: idx + len(I2C_HEADING)], I2C_HEADING)

    def test_batch_mode_paragraph_is_byte_identical(self):
        section = _i2c_section(self.text)
        start = section.index("Batch mode (`references/batch-mode.md`")
        actual = section[start:]
        self.assertEqual(actual, PRE_CHANGE_BATCH_MODE_PARAGRAPH)

    def test_no_bare_git_commit_or_add_lines(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")


class TestPluginVersionBumpedInLockstep(unittest.TestCase):
    """AC-6 (task0001, exit4-recovery-scope): the plugin manifest and the
    marketplace entry for em-workflow agree on the same version, bumped to
    0.1.43 in this task. Test Notes: assert the two manifests agree on the
    same value rather than checking each file in isolation."""

    @classmethod
    def setUpClass(cls):
        cls.plugin_manifest = json.loads(
            PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        cls.marketplace_entry = next(
            entry
            for entry in marketplace["plugins"]
            if entry.get("name") == "em-workflow"
        )

    def test_plugin_manifest_and_marketplace_agree_on_version(self):
        self.assertEqual(
            self.plugin_manifest["version"], self.marketplace_entry["version"]
        )

    def test_shared_version_is_past_the_pre_task_baseline(self):
        # Durable form (repo convention, see
        # tests/test_recycled_task_id_version_bump.py): major/minor fixed,
        # patch strictly greater than the pre-task baseline 42. Pinning the
        # literal 0.1.43 would go red on the next unrelated bump.
        for version in (
            self.plugin_manifest["version"],
            self.marketplace_entry["version"],
        ):
            major, minor, patch = (int(part) for part in version.split("."))
            self.assertEqual((major, minor), (0, 1))
            self.assertGreater(patch, 42)


class TestExit4CarveOutStatedInAllThreeSSOTs(unittest.TestCase):
    """task0003 AC-6 / FR4, NFR1: `commit-docs.sh`'s RECOVERY CONTRACT
    header and `em-workflow/skills/develop/SKILL.md`'s exit-4 scoping
    parenthetical both narrow to match `implement-phase.md`'s carve-out --
    each states that the contract binds every caller EXCEPT a call site
    whose owning protocol document proves unreachability and defines a
    terminal for an unexpected non-zero exit, and both name
    `implement-phase.md` Step I.2.c's route-back commit as the only such
    site today. Comment/prose-only change: AC-6's "no executable line of
    commit-docs.sh changes" half is verified by inspecting `git diff` on
    that file, per Test Notes (FR5 forbids a committed checker for it)."""

    @classmethod
    def setUpClass(cls):
        cls.commit_docs_text = _read_commit_docs_sh()
        cls.commit_docs_header = _normalize_comment_block(
            _commit_docs_recovery_contract_header(cls.commit_docs_text)
        )
        cls.skill_text = _read_develop_skill()
        cls.skill_paragraph = _normalize_ws(
            _skill_exit4_paragraph(cls.skill_text)
        )

    def test_commit_docs_header_states_the_carve_out(self):
        header = self.commit_docs_header
        self.assertIn("EXCEPT a call site whose", header)
        self.assertIn("a proof of unreachability", header)
        self.assertIn(
            "a defined terminal for an unexpected non-zero exit", header
        )

    def test_commit_docs_header_names_implement_phase_route_back_commit(self):
        header = self.commit_docs_header
        self.assertIn("em-workflow/references/implement-phase.md", header)
        self.assertIn("I.2.c's route-back commit", header)

    def test_old_commit_docs_unscoped_binding_phrase_absent(self):
        self.assertNotIn(OLD_COMMIT_DOCS_UNSCOPED_PHRASE, self.commit_docs_text)

    def test_skill_paragraph_states_the_carve_out(self):
        paragraph = self.skill_paragraph
        self.assertIn("対象外", paragraph)
        self.assertIn("到達不能性の証明", paragraph)

    def test_skill_paragraph_names_implement_phase_route_back_commit(self):
        paragraph = self.skill_paragraph
        self.assertIn("em-workflow/references/implement-phase.md", paragraph)
        self.assertIn("Step I.2.c", paragraph)
        self.assertIn("route-back", paragraph)

    def test_old_skill_unscoped_closing_phrase_absent(self):
        self.assertNotIn(OLD_SKILL_EXIT4_UNSCOPED_PHRASE, self.skill_text)

    def test_skill_pinned_recovery_loop_sentences_survive_byte_identical(self):
        # AC-6: the retry/no-infinite-retry sentences pinned by
        # tests/test_develop_skill_rewiring.py must not move -- asserted
        # against the raw text (Test Notes: byte-stability criteria are
        # never checked against a normalized copy).
        self.assertIn("exit-4 リカバリ", self.skill_text)
        self.assertIn(
            "`commit-docs.sh` を 1 回だけ再試行する。2 回目も", self.skill_text
        )
        self.assertIn("無限リトライ\nしない", self.skill_text)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- demonstrated
    against the pre-change wording itself (AC-6: every new absence
    assertion is paired with such a proof)."""

    def test_old_self_falsifying_gate_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "This automatic re-entry applies only when every existing "
            "task is still `pending` (i.e. none has merged yet)."
        )
        self.assertIn(OLD_SELF_FALSIFYING_GATE_PHRASE, sample)

    def test_old_delegation_miscitation_matcher_flags_pre_change_wording(self):
        sample = (
            "`skills/develop/SKILL.md` Step B's create-plan exemption "
            "owns that precedence"
        )
        self.assertIn(OLD_DELEGATION_MISCITATION_PHRASE, sample)

    def test_drain_justification_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "This automatic re-entry applies only when no task has status "
            "`merged` — the absence of any `merged` task; the drain above "
            "has already retired every `in_progress` sibling by this "
            "point. Refresh the integration worktree first."
        )
        self.assertIn(OLD_DRAIN_AS_JUSTIFICATION_PHRASE, sample)

    def test_merged_only_terminal_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "the normal SPEC.md update path first. If any task has "
            "already merged, this automatic re-entry does not apply: "
            "`create-plan` is NOT set to `needs_update`."
        )
        self.assertIn(OLD_MERGED_ONLY_TERMINAL_PHRASE, sample)

    def test_exit4_enumeration_tail_matcher_flags_pre_change_wording(self):
        sample = (
            "applies to every `commit-docs.sh` call site in this phase — "
            "Step I.1's baseline commit, Step I.2.b's wake-phase commit, "
            "and Step I.2.c's route-back commit): exit 4 means a "
            "concurrent `merge-task.sh` advanced the branch ref"
        )
        self.assertIn(OLD_EXIT4_ENUMERATION_TAIL, sample)

    def test_i2c_recovery_pointer_matcher_flags_pre_change_wording(self):
        sample = (
            '"docs({feature}): implement route back to planning" '
            '"$ROUTEBACK_TIP"` (exit-4 recovery: Branch & Worktree Model '
            "above). End the phase with a clear report."
        )
        self.assertIn(OLD_I2C_RECOVERY_POINTER, sample)

    def test_old_implement_stays_failed_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "`create-plan` is NOT set to `needs_update`, `implement` "
            "stays `failed`, and the phase reports and returns control "
            "to the user via develop's stop condition 3"
        )
        self.assertIn(OLD_IMPLEMENT_STAYS_FAILED_PHRASE, sample)

    def test_old_unscoped_rejected_path_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "No retry loop, no alternative recovery route, and no "
            "degraded route back is offered for this path; nothing is "
            "committed and no worktree/branch cleanup is started."
        )
        self.assertIn(OLD_UNSCOPED_REJECTED_PATH_PHRASE, sample)

    def test_old_merge_task_sh_only_callers_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "so no\nimplementer of this feature can be running at that "
            "point; implementers\nare the only callers of "
            "`merge-task.sh` against this integration branch;\n"
            "therefore no concurrent ref advance can occur"
        )
        self.assertIn(
            OLD_EXIT4_MERGETASK_ONLY_PHRASE, _normalize_ws(sample)
        )

    def test_old_commit_docs_unscoped_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "RECOVERY CONTRACT (binding on every caller): on exit 4 the "
            "caller MUST (1) refresh this worktree to the new branch tip"
        )
        self.assertIn(OLD_COMMIT_DOCS_UNSCOPED_PHRASE, sample)

    def test_old_skill_unscoped_closing_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "ドキュメントコミット、および下記の verify / retrospect "
            "フェーズのコミットを\n含む）: 戻り値 4（stale worktree — "
            "並行する merge-task.sh がこの worktree の"
        )
        self.assertIn(OLD_SKILL_EXIT4_UNSCOPED_PHRASE, sample)

    def test_old_exit4_closed_enumeration_claim_matcher_flags_pre_change_wording(self):
        sample = (
            "applies to Step I.1's baseline commit, Step I.2.b's "
            "wake-phase commit and Step I.2.c's rejected-path terminal "
            "status commit — the three `commit-docs.sh` call sites in "
            "this phase where exit 4 can occur): exit 4 means a "
            "concurrent `merge-task.sh` advanced the branch ref"
        )
        self.assertIn(OLD_EXIT4_CLOSED_ENUMERATION_CLAIM, sample)

    def test_old_abort_manual_handling_phrase_matcher_flags_pre_change_wording(
        self,
    ):
        sample = (
            "- **abort phase** — leave `implement` as `failed` for manual "
            "handling."
        )
        self.assertIn(OLD_ABORT_MANUAL_HANDLING_PHRASE, sample)

    def test_bare_commit_line_matcher_flags_an_unlocked_commit(self):
        sample = 'git -C {project_root} add -A -- foo && git -C {project_root} commit -m "x"'
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertTrue(lines)

    def test_bare_commit_line_matcher_ignores_prose_mentioning_commit(self):
        sample = "No bare `git add`/`git commit` against the integration worktree runs outside"
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertEqual(lines, [])


class TestImplementFailedTaskRowStatesWriteAndCommitTerminal(unittest.TestCase):
    """Relocated from tests/test_abort_phase_terminal_batch_mode.py (task0003,
    abort-phase-terminal, rework round 1: SC-F containment fix). Covers
    task0002 AC-1 (FR7, NFR6): the `implement.failed-task` row's Batch
    behavior cell states that the second failure on the same task takes the
    abort terminal in which the `implement` step's `status` is written to
    `failed` and that write is committed, and no longer contains the phrase
    "`implement` stays `failed`"."""

    @classmethod
    def setUpClass(cls):
        cls.row = _batch_mode_gate_row(_read_batch_mode())

    def test_row_states_status_written_to_failed(self):
        self.assertIn(BATCH_MODE_STATUS_WRITTEN_FAILED_PHRASE, self.row)

    def test_row_states_the_write_is_committed(self):
        self.assertIn(BATCH_MODE_WRITE_COMMITTED_PHRASE, self.row)

    def test_row_no_longer_claims_implement_stays_failed(self):
        self.assertNotIn(BATCH_MODE_REMOVED_PHRASE, self.row)


class TestImplementFailedTaskRowRetainsExistingClauses(unittest.TestCase):
    """Relocated from tests/test_abort_phase_terminal_batch_mode.py (task0003,
    abort-phase-terminal, rework round 1). Covers task0002 AC-2 (FR7): the
    same row still contains the retry clause, the route-back-never-automatic
    clause, the gate id, and the detail pointer."""

    @classmethod
    def setUpClass(cls):
        cls.row = _batch_mode_gate_row(_read_batch_mode())

    def test_gate_id_present(self):
        self.assertIn(f"`{BATCH_MODE_GATE_ID}`", self.row)

    def test_retry_clause_survives(self):
        self.assertIn(BATCH_MODE_RETRY_CLAUSE, self.row)

    def test_route_back_clause_survives(self):
        self.assertIn(BATCH_MODE_ROUTE_BACK_CLAUSE, self.row)

    def test_detail_pointer_survives(self):
        self.assertIn(BATCH_MODE_DETAIL_POINTER, self.row)


class TestBatchModeGateRowRegressionGuard(unittest.TestCase):
    """Relocated from tests/test_abort_phase_terminal_batch_mode.py (task0003,
    abort-phase-terminal, rework round 1). Covers task0002 AC-4 (FR7): a
    paired negative proof that BATCH_MODE_REMOVED_PHRASE is exactly the
    literal that was in the row before task0002's edit -- the absence
    matcher in TestImplementFailedTaskRowStatesWriteAndCommitTerminal would
    have failed against the row as it read pre-change, and the
    write-and-commit matcher would likewise have failed to find its new
    wording there. Named distinctly from this module's pre-existing
    TestValidationDetectsRegressions class so the two never collide
    (task0003 Design: "never a second class of the same name" -- a
    duplicate would silently shadow the first and drop its tests from
    discovery)."""

    def test_removed_phrase_matcher_flags_pre_change_row(self):
        self.assertIn(BATCH_MODE_REMOVED_PHRASE, BATCH_MODE_PRE_CHANGE_ROW)

    def test_pre_change_row_sample_is_not_vacuous(self):
        # Non-vacuity guard: the captured sample is genuinely the row (not
        # an empty or unrelated string) -- scoped by the same gate id and
        # retained clauses the live lookup keys off, so the proof above is
        # not `assertIn(X, "")`-style vacuous.
        self.assertIn(f"`{BATCH_MODE_GATE_ID}`", BATCH_MODE_PRE_CHANGE_ROW)
        self.assertIn(BATCH_MODE_RETRY_CLAUSE, BATCH_MODE_PRE_CHANGE_ROW)
        self.assertIn(BATCH_MODE_ROUTE_BACK_CLAUSE, BATCH_MODE_PRE_CHANGE_ROW)
        self.assertIn(BATCH_MODE_DETAIL_POINTER, BATCH_MODE_PRE_CHANGE_ROW)

    def test_new_wording_matcher_flags_absence_in_pre_change_row(self):
        # Proof the new-wording matcher would have failed against the
        # pre-change row too -- the write-and-commit phrasing is new.
        self.assertNotIn(
            BATCH_MODE_STATUS_WRITTEN_FAILED_PHRASE, BATCH_MODE_PRE_CHANGE_ROW
        )


if __name__ == "__main__":
    unittest.main()

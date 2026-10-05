"""Tests for task0003 (prelaunch-inprogress-routeback): Step I.2.a's
launch-state commit also records, as `failed`, a task that launched in this
entry and had already failed by the time the journal is re-read, in
`em-workflow/references/implement-phase.md` (Region L only).

Covers task0003 Acceptance Criteria
(feature-docs/prelaunch-inprogress-routeback/tasks/task0003.md):

- AC-1 (FR7, FR2): Region L defines both parts of the single write set --
  the in_progress part (re-read last event `launched`) and the failed part
  (a `launched` appended after the selection-time replay and a re-read last
  event `failed`) -- and the failed part is written
  `tasks.{T}.status = failed` / `tasks.{T}.branch` in the same write set and
  the same launch-state commit, never `in_progress`.
- AC-2 (FR7): a selected task with no `launched` appended after the
  selection-time replay is not written (naming the task already
  `pending` + `failed` at selection that did not launch), and the
  launch-state write does not change
  `tasks.{T}.routeback_failed_journal_line`.
- AC-3 (FR2, FR3): the commit names every task of both parts; a partial
  launch still yields one write set and one commit; the write and the commit
  are omitted only when both parts are empty; the turn ends after the commit
  or its omission.
- AC-4 (FR4): a last event `merged` is never written and is left to I.2.b;
  no terminal task is written `in_progress`; on the exit-4 retry both parts
  are re-derived from the journal re-read after the re-capture and refresh;
  the second exit 4 still stops keeping the launch records, worktrees and
  branches.
- AC-5 (FR6, NFR4): this module itself -- standard library `unittest` only,
  every new-wording literal a module-level constant read by both its
  positive test and its negative-proof test, every new-wording matcher
  failing against a verbatim pre-change sample of Region L, each failure
  backed by a non-vacuity guard.
- AC-6 (NFR1, NFR2, NFR3): only Region L changes. This module pins, by
  digest of the raw text, the sections that no task of this feature edits
  (the Step I.2 intro and the Branch & Worktree Model, which carries the
  exit-4 recovery bullet). The I.2.c section is deliberately not pinned by
  digest here: task0004 adds one write-set item to it, so a digest would
  turn red when that task merges; its pinned phrases are guarded by
  tests/test_implement_routeback_gate.py. The other modules named in the
  task plan are satisfied by running them unmodified, not by this module.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import from, and is not imported by, any other test module.

Content assertions compare against a whitespace-normalized copy of the
relevant text (line-wrap choices never make a prose assertion brittle);
byte-identity assertions (AC-6) run on raw text. The two modes are never
mixed in one assertion (IMPLEMENTATION.md Conventions).
"""

import hashlib
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

# --- Section anchors, the same boundaries the existing modules use. ---

STEP_I2_HEADING = (
    "## Step I.2: Task loop (work queue, background launch + wake-phase "
    "refill)"
)
I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model"
STEP_I0_HEADING = "## Step I.0"

# Region L starts at the paragraph that opens "For each selected task T"
# and ends at the I.2.b heading; Region P is the text before it, back to the
# I.2.a heading (IMPLEMENTATION.md, Shared Components).
REGION_L_START = "For each selected task T"

# Sub-section boundaries inside Region L (whitespace-normalized text).
WRITE_SET_PARAGRAPH_START = "**Journal re-read and write set**"
FAILED_PART_START = "- **failed part**:"
NOT_WRITTEN_INTRO = "A selected task outside the write set is not written"
PARTIAL_LAUNCH_START = "A partial launch still yields"
STEP3_START = "3. **write**,"
STEP4_START = "4. **commit**"
STEP4_END = "Capture precedes refresh"
EMPTY_PARAGRAPH_START = "**Empty write set**"
EXIT4_PARAGRAPH_START = "**exit 4**: the bounded recovery"
END_OF_TURN_START = "**End the turn**"

# --- AC-1 literals (FR7, FR2). ---

IN_PROGRESS_PART_LABEL = "**in_progress part**"
FAILED_PART_LABEL = "**failed part**"
IN_PROGRESS_PART_DEFINITION = (
    "a selected task whose re-read journal last event is `launched`"
)
FAILED_PART_LAUNCHED_AFTER_REPLAY = (
    "a `launched` event for the task appears in the re-read journal after "
    "the extent replayed at selection time"
)
FAILED_PART_REPLAY_TERM = (
    "the **selection-time replay**, the replay at the top of this section"
)
FAILED_PART_LAST_EVENT_FAILED = "the re-read journal last event is `failed`"
FAILED_PART_WRITE_AND_COMMIT = (
    "`tasks.{T}.status = failed` and `tasks.{T}.branch` are written in the "
    "same write set and the same launch-state commit"
)
FAILED_PART_NEVER_LEFT_PENDING = "never left `pending`"
NEVER_IN_PROGRESS_PHRASE = "never written `in_progress`"
IN_PROGRESS_WRITE_LITERAL = "`tasks.{T}.status = in_progress`"
STEP3_FAILED_WRITE = (
    "`tasks.{T}.status = failed` and `tasks.{T}.branch` for each task of "
    "the failed part"
)
STEP3_IN_PROGRESS_WRITE = (
    "`tasks.{T}.status = in_progress` and `tasks.{T}.branch` for each task "
    "of the in_progress part"
)
SELECTION_REPLAY_ANCHOR = "by replaying the journal"

# --- AC-2 literals (FR7). ---

NO_LAUNCHED_APPENDED_PHRASE = (
    "no `launched` appended after the selection-time replay"
)
STAYS_PENDING_PHRASE = "the task stays `pending` in workflow.yaml"
PENDING_FAILED_NOT_LAUNCHED_PHRASE = (
    "a task that was already `pending` + `failed` at selection and did not "
    "launch this time"
)
ROUTEBACK_RECORD_UNTOUCHED_PHRASE = (
    "never sets or changes `tasks.{T}.routeback_failed_journal_line`"
)

# --- AC-3 literals (FR2, FR3). ---

COMMIT_NAMES_BOTH_PARTS_PHRASE = "naming every task in the write set, both parts"
PARTIAL_LAUNCH_PHRASE = (
    "A partial launch still yields exactly one write set and one commit"
)
PARTIAL_LAUNCH_BOTH_PARTS_PHRASE = (
    "which hold the in_progress part and the failed part together"
)
EMPTY_WRITE_SET_PHRASES = (
    "when the write set is empty",
    "the write and the commit are omitted",
)
EMPTY_ONLY_WHEN_BOTH_PARTS_PHRASE = "only when both parts are empty"
TURN_ENDS_AFTER_OMISSION_PHRASE = "the turn still ends after that omission"
END_OF_TURN_PHRASE = (
    "**End the turn** after the launch-state commit, or after its omission"
)

# --- AC-4 literals (FR4). ---

MERGED_LEFT_TO_I2B_PHRASE = (
    "last event `merged` → not in the write set; it is never written and "
    "is left to I.2.b"
)
TERMINAL_NEVER_IN_PROGRESS_PHRASE = (
    "last event `merged` or `failed` is " + NEVER_IN_PROGRESS_PHRASE
)
RETRY_REREAD_PHRASES = (
    "on the retry, the journal is re-read again after the re-capture and "
    "refresh",
    "the write set is re-derived the same way",
)
RETRY_BOTH_PARTS_PHRASE = "both parts are re-derived by the same rule"
RETRY_FAILED_BETWEEN_PHRASE = (
    "a task that reached `failed` between the first attempt and the retry"
)
RETRY_EMPTY_NO_COMMIT_PHRASE = (
    "an empty re-derived write set means no retry commit"
)
# Retained wording (not new): the second exit 4 still stops the phase.
SECOND_EXIT4_PHRASES = (
    "A second exit 4 stops the phase with a report naming",
    "Step I.2.a's launch-state commit",
    "the tasks in the write set",
    "keeps the journal's launch records and the tasks' worktrees and "
    "branches",
    "nothing is deleted or rolled back",
)
EXIT4_CITATION_PHRASE = "the Branch & Worktree Model's exit-4 recovery"
# Phrases of the exit-4 recovery bullet itself; Region L cites that bullet
# and must not restate them.
EXIT4_BULLET_PHRASES = (
    "RE-CAPTURE the tip from the branch ref",
    "never loop unbounded",
    "re-apply the SAME intended state transition",
)

# --- Region L constraints kept from earlier tasks. ---

LAUNCH_STATE_COMMIT_TERM = "launch-state commit"
MARKER_ONLY_SENTENCE_RE = re.compile(
    r"[Ii]n a `--batch` run,? .{0,200}?this (?:wake )?turn's final assistant "
    r"message is the marker line `references/batch-mode\.md` defines "
    r"and nothing else"
)

# --- Anchors present in both the pre-change sample and the live Region L
# and not edited by this task, so a failing negative proof is not a failure
# to find anything at all. The second group are the section boundaries the
# matchers slice on; they exist in the sample too. ---

NON_VACUITY_ANCHORS = (
    "Branch point = integration branch AT THIS MOMENT (includes every task "
    "merged so far).",
    "in this normative order",
    "ONCE per entry into Step I.2.a",
    "capture-first form above",
)
SLICE_BOUNDARY_ANCHORS = (
    WRITE_SET_PARAGRAPH_START,
    NOT_WRITTEN_INTRO,
    PARTIAL_LAUNCH_START,
    STEP3_START,
    STEP4_START,
    STEP4_END,
    EMPTY_PARAGRAPH_START,
    EXIT4_PARAGRAPH_START,
    END_OF_TURN_START,
)

# --- Digests of raw sections that no task of this feature edits (AC-6),
# captured from the document at this task's base revision. ---

STEP_I2_INTRO_SHA256 = (
    "91e91fd9edb90965054ac12859526e27a3e17a6f70038bba6589a1352df44f34"
)
BRANCH_WORKTREE_MODEL_SHA256 = (
    "8363469d8dc8d914e304fbb4f2fbb3bea4502ec014bc2803b93df4158fdda632"
)

# --- Verbatim pre-change sample, captured BEFORE this task's edit landed:
# Region L of em-workflow/references/implement-phase.md at the task's base
# revision (`git show HEAD:em-workflow/references/implement-phase.md`),
# from the "For each selected task T" paragraph through the "**End the
# turn**" paragraph. Not paraphrased, not reconstructed after the edit. ---

PRE_CHANGE_REGION_L = (
    'For each selected task T (every task selected in this single entry into\n'
    'Step I.2.a), create its worktree:\n'
    '\n'
    '```bash\n'
    'git worktree add -b "em-workflow/{feature}/{T}" "$WT_ROOT/{T}" \\\n'
    '    "em-workflow/{feature}/integration"\n'
    '```\n'
    '\n'
    'Branch point = integration branch AT THIS MOMENT (includes every task merged\n'
    'so far).\n'
    '\n'
    '**Resume guard**: before running `git worktree add -b` for task T, check\n'
    'whether `em-workflow/{feature}/{T}` and/or `$WT_ROOT/{T}` already exist (this\n'
    'happens on re-entry after a prior failed/interrupted run whose worktree was\n'
    'kept for diagnosis per I.2.c, or an in-flight retry). Do NOT run\n'
    '`git worktree add -b` blindly in that case:\n'
    '- Retry on the same worktree (user chose "retry" in I.2.c): reuse the\n'
    '  existing worktree as-is and re-launch the implementer against it.\n'
    '- Clean re-attempt (fresh implementer, no prior branch state to keep): first\n'
    '  `git worktree remove --force "$WT_ROOT/{T}"` and\n'
    '  `git branch -D "em-workflow/{feature}/{T}"`, then recreate the worktree and\n'
    '  branch from the current integration branch as above.\n'
    '\n'
    'Before launching, verify every `project_commands` string (build/test/format)\n'
    'used by the selected tasks is in the approval store (`bash_guard.py\n'
    '--list`; command-execution-protocol.md). Anything unapproved: run the\n'
    "protocol's approval gate now (AskUserQuestion → `--record`) — the PreToolUse\n"
    'hook denies unapproved workflow.yaml strings inside implementer worktrees,\n'
    'so approving up front avoids mid-launch failures. Commands the user rejects\n'
    'stay unapproved: the hook denies them and the implementer reports failure\n'
    'instead of working around it (worktree-task-workflow skill). Batch mode:\n'
    'auto-record instead of asking; refusal patterns still hard-fail\n'
    "(`references/batch-policies.yaml`'s `create-spec.command-approval` entry —\n"
    "the same approval gate, regardless of which phase's task launch triggers\n"
    'it).\n'
    '\n'
    'Launch each selected task as a BACKGROUND `Task(subagent_type="em-workflow:implementer")`\n'
    'call. Synchronous fan-out-and-wait for a batch of implementers is explicitly\n'
    'FORBIDDEN: it reintroduces the barrier this feature removes, and it starves\n'
    'the Stop hook of the turn-end event it needs to catch a forgotten refill.\n'
    '\n'
    'Prompt payload per task:\n'
    '\n'
    '```\n'
    '# Task assignment\n'
    'task_id: {T}\n'
    'worktree_path: {absolute path to $WT_ROOT/{T}}\n'
    "task_plan_path: {absolute path to the integration worktree's feature-docs/{feature}/tasks/{T}.md}\n"
    "implementation_md_path: {absolute path to the integration worktree's feature-docs/{feature}/IMPLEMENTATION.md}\n"
    "lessons_path: {absolute path to the MAIN working tree's feature-docs/LESSONS.md; OMIT this line when the file does not exist — LESSONS.md is the one cross-feature artifact that stays outside the integration worktree}\n"
    'parent_branch: em-workflow/{feature}/integration\n'
    'merge_script: {resolved MERGE_SCRIPT absolute path}\n'
    'skills_to_load: {tasks.{T}.skills, prefixed em-workflow: — e.g. ["em-workflow:backend-impl"]; may be empty}\n'
    'project_commands:\n'
    '  build: {workflow.yaml project.components.*.build_command}\n'
    '  test: {...test_command}\n'
    '  format: {...format_command}\n'
    'expected_files: {tasks.{T}.files}\n'
    'tests_yaml_path: {absolute path to $WT_ROOT/{T}/test-docs/{feature}/{T}.tests.yaml}\n'
    '```\n'
    '\n'
    'Do NOT inline task-plan content into the prompt — the implementer Reads its\n'
    'plan itself. Command strings come from workflow.yaml and are subject to the\n'
    "implementer's command-approval discipline (worktree-task-workflow skill).\n"
    '\n'
    "`tests_yaml_path` points INSIDE the task's own worktree, never into the\n"
    'integration worktree: the implementer writes its test record there and\n'
    'commits it with the implementation, so the record merges into the parent\n'
    'along with the code it describes. One file per task\n'
    '(`{T}.tests.yaml`) means parallel tasks never write the same path and the\n'
    "records cannot conflict. It carries the implementer's `baseline_failures` /\n"
    '`final_failures` (which tests were already red when the task started, so a\n'
    'later failure is attributed by set difference instead of re-investigated)\n'
    'and the AC → test mapping with the observed red for each criterion. Build\n'
    'the path yourself and pass it — the implementer does not know `{feature}`\n'
    'and must not derive it from other paths.\n'
    '\n'
    'The PreToolUse(Task|Agent) launch guard (`queue_launch_guard.py`) records\n'
    'each allowed launch as a `launched` journal event as the call goes through\n'
    '(the only writer of `launched`); it also denies double-launching a task\n'
    'that is already in flight or already merged, as a net under the\n'
    "orchestrator's own bookkeeping.\n"
    '\n'
    '**Journal re-read and write set**: after the launch loop, re-read the latest\n'
    'journal (the same replay as at the top of this section, last event per\n'
    'task). The write set is the tasks selected in this entry whose journal last\n'
    'event is `launched` — the launches the journal confirms. A selected task\n'
    'outside the write set is not written:\n'
    '\n'
    '- no event for the task (stopped at the approval gate, denied by the launch\n'
    '  guard, or `Task()` never issued) → not in the write set; the task stays\n'
    '  `pending` in workflow.yaml;\n'
    '- last event `merged` or `failed` (terminal) → not in the write set; never\n'
    '  written `in_progress`.\n'
    '\n'
    'A partial launch still yields exactly one write set and one commit.\n'
    '\n'
    'Write the launch state for the write set in this normative order — the\n'
    'capture precedes the refresh, the refresh precedes the write, and the\n'
    'write precedes the commit:\n'
    '\n'
    '1. **capture** the tip —\n'
    '   `LAUNCH_TIP=$(git -C {integration_worktree} rev-parse em-workflow/{feature}/integration)`\n'
    '2. **refresh** the integration worktree to the branch —\n'
    '   `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`\n'
    '3. **write**, on the worktree just refreshed, `tasks.{T}.status =\n'
    '   in_progress` and `tasks.{T}.branch` into workflow.yaml for every task\n'
    '   in the write set (not every selected task) — one write set, not one per\n'
    '   task\n'
    '4. **commit** that single write set — the launch-state commit — with the\n'
    '   captured tip as the third argument —\n'
    '   `commit-docs.sh {integration_worktree} "docs({feature}): launch {T1},\n'
    '   {T2}, …"  "$LAUNCH_TIP"` (naming every task in the write set; the\n'
    '   third argument is `expected_base_tip`; exit-4 recovery: Branch &\n'
    '   Worktree Model above — the "a second exit 4 stops the phase" counter\n'
    '   there is counted per commit attempt, i.e. per entry into this sequence,\n'
    '   not per task named in the commit)\n'
    '\n'
    'Capture precedes refresh, and refresh always targets the branch NAME,\n'
    'deliberately, guaranteeing two invariants. First, the refresh target is\n'
    "the branch name, never a captured SHA: a linked worktree's `HEAD` is an\n"
    'attached symref to the branch, so `git reset --hard <a captured SHA>`\n'
    'would move the BRANCH REF itself backward to that SHA, silently\n'
    'discarding any `merge-task.sh update-ref` that advanced the branch since\n'
    'the capture; `reset --hard em-workflow/{feature}/integration` moves the\n'
    'ref to where it already points and can never rewind it. Second, the\n'
    'capture precedes the refresh: if the branch advances in the window\n'
    'between the two, the refreshed tree holds the NEW (post-advance) tip\n'
    "while `$LAUNCH_TIP` holds the OLD one, so `commit-docs.sh`'s tip check\n"
    'is guaranteed to see the mismatch and exit 4 — entering the bounded\n'
    'exit-4 recovery — rather than silently committing a stale tree.\n'
    'Capturing afterwards with `rev-parse HEAD` would instead read the branch\n'
    'ref AT READ TIME, which could hand `commit-docs.sh` a tip the working\n'
    'tree was never built on and let the check pass while silently committing\n'
    'a stale tree.\n'
    '\n'
    '**Idiom split is transitional (NFR1)**: the four call sites that already\n'
    "pass a tip — Step I.1's baseline capture, Step I.2.b step 2's wake-phase\n"
    "capture, and Step I.2.c's two terminal-status captures — still refresh\n"
    'first and capture with `rev-parse HEAD`. The reasoning above\n'
    'supersedes that older idiom, but converting those four sites is out of\n'
    'scope here and is tracked as its own change; until it lands, the two\n'
    'shapes coexist by design. Read them as one mechanism mid-migration, not\n'
    'as a contradiction in this document, and write any NEW call site in the\n'
    'capture-first form above.\n'
    '\n'
    '**Refill (FR5)**: this sequence runs ONCE per entry into Step I.2.a —\n'
    'including the refill re-entry from Step I.2.b step 5 within the same\n'
    'turn — covering the write set of that entry with a single capture, a\n'
    'single refresh, one write set, and one commit (at most one write set and\n'
    'one commit per entry); a fresh `LAUNCH_TIP` is captured each time (i.e. on\n'
    'each such entry, not per task). `$RECONCILE_TIP` is never reused as this\n'
    "step's third argument: it is captured at Step I.2.b step 2, BEFORE Step\n"
    "I.2.b step 3's own commit advances the branch tip, so by the time the\n"
    'refill path re-enters Step I.2.a, `$RECONCILE_TIP` is already stale.\n'
    '\n'
    '**Empty write set**: when the write set is empty (no confirmed launch, or\n'
    'every confirmed task already terminal at the re-read), the write and the\n'
    'commit are omitted.\n'
    '\n'
    "**exit 4**: the bounded recovery is the Branch & Worktree Model's exit-4\n"
    'recovery, cited here and not restated. Applied to the launch-state commit:\n'
    'on the retry, the journal is re-read again after the re-capture and refresh,\n'
    'and the write set is re-derived the same way (terminal tasks excluded; an\n'
    'empty re-derived write set means no retry commit). A second exit 4 stops the\n'
    "phase with a report naming the call site (Step I.2.a's launch-state commit)\n"
    "and the tasks in the write set; the stop keeps the journal's launch records\n"
    "and the tasks' worktrees and branches — nothing is deleted or rolled back.\n"
    'Those tasks then read `pending` with journal last event `launched` and are\n'
    'in-flight under the in-flight rule in the selection rules above (cited, not\n'
    'restated).\n'
    '\n'
    '**End the turn** after the launch-state commit, or after its omission when\n'
    'the write set is empty — no polling, no synchronous wait. In a `--batch`\n'
    "run, this turn's final assistant message is the marker line\n"
    '`references/batch-mode.md` defines and nothing else.'
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _region_l(text):
    section = _i2a_section(text)
    return section[section.index(REGION_L_START):]


def _region_p(text):
    section = _i2a_section(text)
    return section[: section.index(REGION_L_START)]


def _step_i2_intro(text):
    start = text.index(STEP_I2_HEADING)
    end = text.index(I2A_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _slice(text, start_marker, end_marker=None):
    """Whitespace-normalized `text` from the first `start_marker` to the
    next `end_marker` after it (or to the end). None when a marker is
    missing, so a matcher never passes on a slice it could not find."""
    start = text.find(start_marker)
    if start < 0:
        return None
    if end_marker is None:
        return text[start:]
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        return None
    return text[start:end]


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _has_all(text, phrases):
    return text is not None and all(phrase in text for phrase in phrases)


# --- The new-wording matchers. Each takes the whitespace-normalized text
# of Region L and returns True when the new wording holds. Each one is run
# against the live Region L (must hold) and against the pre-change sample
# (must not hold). ---


def _both_parts_named(t):
    return _has_all(
        t,
        (
            IN_PROGRESS_PART_LABEL,
            FAILED_PART_LABEL,
            IN_PROGRESS_PART_DEFINITION,
        ),
    )


def _failed_part_definition(t):
    bullet = _slice(t, FAILED_PART_START, NOT_WRITTEN_INTRO)
    return _has_all(
        bullet,
        (
            FAILED_PART_REPLAY_TERM,
            FAILED_PART_LAUNCHED_AFTER_REPLAY,
            FAILED_PART_LAST_EVENT_FAILED,
        ),
    )


def _failed_part_written_failed_never_in_progress(t):
    bullet = _slice(t, FAILED_PART_START, NOT_WRITTEN_INTRO)
    return (
        _has_all(
            bullet,
            (
                FAILED_PART_WRITE_AND_COMMIT,
                NEVER_IN_PROGRESS_PHRASE,
                FAILED_PART_NEVER_LEFT_PENDING,
            ),
        )
        and IN_PROGRESS_WRITE_LITERAL not in bullet
    )


def _write_step_carries_the_failed_write(t):
    step3 = _slice(t, STEP3_START, STEP4_START)
    return _has_all(step3, (STEP3_IN_PROGRESS_WRITE, STEP3_FAILED_WRITE))


def _unlaunched_not_written(t):
    not_written = _slice(t, NOT_WRITTEN_INTRO, PARTIAL_LAUNCH_START)
    return _has_all(
        not_written,
        (
            NO_LAUNCHED_APPENDED_PHRASE,
            STAYS_PENDING_PHRASE,
            PENDING_FAILED_NOT_LAUNCHED_PHRASE,
        ),
    )


def _routeback_record_untouched(t):
    region = _slice(t, WRITE_SET_PARAGRAPH_START, EXIT4_PARAGRAPH_START)
    return _has_all(region, (ROUTEBACK_RECORD_UNTOUCHED_PHRASE,))


def _commit_names_both_parts(t):
    step4 = _slice(t, STEP4_START, STEP4_END)
    return _has_all(step4, (COMMIT_NAMES_BOTH_PARTS_PHRASE,))


def _partial_launch_one_write_set_both_parts(t):
    return _has_all(
        t, (PARTIAL_LAUNCH_PHRASE, PARTIAL_LAUNCH_BOTH_PARTS_PHRASE)
    )


def _empty_only_when_both_parts_empty(t):
    empty = _slice(t, EMPTY_PARAGRAPH_START, EXIT4_PARAGRAPH_START)
    return _has_all(
        empty,
        EMPTY_WRITE_SET_PHRASES
        + (EMPTY_ONLY_WHEN_BOTH_PARTS_PHRASE, TURN_ENDS_AFTER_OMISSION_PHRASE),
    )


def _turn_ends_after_commit_or_omission(t):
    return _has_all(t, (END_OF_TURN_PHRASE,))


def _merged_left_to_i2b(t):
    not_written = _slice(t, NOT_WRITTEN_INTRO, PARTIAL_LAUNCH_START)
    return _has_all(
        not_written,
        (MERGED_LEFT_TO_I2B_PHRASE, TERMINAL_NEVER_IN_PROGRESS_PHRASE),
    )


def _retry_rederives_both_parts(t):
    # Searched after the exit-4 paragraph opens, so the first-commit text
    # (which also says the journal is re-read) cannot satisfy it.
    exit4 = _slice(t, EXIT4_PARAGRAPH_START, END_OF_TURN_START)
    return _has_all(
        exit4,
        RETRY_REREAD_PHRASES
        + (
            RETRY_BOTH_PARTS_PHRASE,
            RETRY_FAILED_BETWEEN_PHRASE,
            RETRY_EMPTY_NO_COMMIT_PHRASE,
        ),
    )


NEW_WORDING_MATCHERS = {
    "AC-1 both parts of the write set named": _both_parts_named,
    "AC-1 failed part definition": _failed_part_definition,
    "AC-1 failed part written failed, never in_progress": (
        _failed_part_written_failed_never_in_progress
    ),
    "AC-1 write step carries the failed write": (
        _write_step_carries_the_failed_write
    ),
    "AC-2 unlaunched selected tasks are not written": _unlaunched_not_written,
    "AC-2 routeback record left alone": _routeback_record_untouched,
    "AC-3 commit names both parts": _commit_names_both_parts,
    "AC-3 partial launch one write set one commit": (
        _partial_launch_one_write_set_both_parts
    ),
    "AC-3 empty only when both parts are empty": (
        _empty_only_when_both_parts_empty
    ),
    "AC-4 merged last event left to I.2.b": _merged_left_to_i2b,
    "AC-4 retry re-derives both parts": _retry_rederives_both_parts,
}


class TestAC1BothPartsOfTheWriteSet(unittest.TestCase):
    """AC-1 (FR7, FR2): the write set has an in_progress part and a failed
    part; the failed part is written `failed` in the same write set and the
    same launch-state commit, never `in_progress`."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.region = _normalize_ws(_region_l(text))
        cls.region_p = _normalize_ws(_region_p(text))

    def test_both_parts_are_named_and_the_in_progress_part_is_defined(self):
        self.assertTrue(_both_parts_named(self.region))

    def test_failed_part_needs_a_launched_after_the_selection_time_replay_and_a_failed_last_event(
        self,
    ):
        self.assertTrue(_failed_part_definition(self.region))

    def test_failed_part_is_written_failed_in_the_same_commit_never_in_progress(
        self,
    ):
        self.assertTrue(
            _failed_part_written_failed_never_in_progress(self.region)
        )

    def test_write_step_writes_failed_and_branch_for_the_failed_part(self):
        self.assertTrue(_write_step_carries_the_failed_write(self.region))

    def test_in_progress_write_literal_stays_in_the_write_step(self):
        step3 = _slice(self.region, STEP3_START, STEP4_START)
        self.assertIn(IN_PROGRESS_WRITE_LITERAL, step3)

    def test_selection_time_replay_named_by_the_failed_part_exists_in_region_p(
        self,
    ):
        self.assertIn(SELECTION_REPLAY_ANCHOR, self.region_p)

    def test_failed_part_wording_lives_in_region_l_not_region_p(self):
        for literal in (FAILED_PART_LABEL, IN_PROGRESS_PART_LABEL):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, self.region_p)


class TestAC2UnlaunchedSelectedTasksAreNotWritten(unittest.TestCase):
    """AC-2 (FR7): a selected task with no `launched` appended after the
    selection-time replay is not written; the launch-state write leaves
    `tasks.{T}.routeback_failed_journal_line` alone."""

    @classmethod
    def setUpClass(cls):
        cls.region = _normalize_ws(_region_l(_read()))

    def test_no_launched_appended_means_not_written_and_stays_pending(self):
        self.assertTrue(_unlaunched_not_written(self.region))

    def test_pending_failed_at_selection_and_not_launched_is_named(self):
        not_written = _slice(self.region, NOT_WRITTEN_INTRO, PARTIAL_LAUNCH_START)
        self.assertIn(PENDING_FAILED_NOT_LAUNCHED_PHRASE, not_written)

    def test_launch_state_write_leaves_the_routeback_record_alone(self):
        self.assertTrue(_routeback_record_untouched(self.region))

    def test_region_l_never_writes_the_routeback_record(self):
        # The record is named only as a field this write leaves alone: every
        # occurrence of its name is inside the untouched-record sentence.
        name = "tasks.{T}.routeback_failed_journal_line"
        self.assertEqual(
            self.region.count(name),
            self.region.count(ROUTEBACK_RECORD_UNTOUCHED_PHRASE),
        )
        self.assertGreater(self.region.count(name), 0)

    def test_earlier_unconfirmed_launch_causes_are_kept(self):
        for phrase in (
            "stopped at the approval gate",
            "denied by the launch guard",
            "`Task()` never issued",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.region)


class TestAC3CommitNamesBothPartsAndEmptySet(unittest.TestCase):
    """AC-3 (FR2, FR3): the commit names every task of both parts; one write
    set and one commit; omitted only when both parts are empty; the turn
    ends after the commit or its omission."""

    @classmethod
    def setUpClass(cls):
        cls.region = _normalize_ws(_region_l(_read()))

    def test_commit_message_names_every_task_in_the_write_set_both_parts(self):
        self.assertTrue(_commit_names_both_parts(self.region))

    def test_partial_launch_yields_one_write_set_and_one_commit_for_both_parts(
        self,
    ):
        self.assertTrue(_partial_launch_one_write_set_both_parts(self.region))

    def test_write_and_commit_are_omitted_only_when_both_parts_are_empty(self):
        self.assertTrue(_empty_only_when_both_parts_empty(self.region))

    def test_turn_ends_after_the_commit_or_its_omission(self):
        self.assertTrue(_turn_ends_after_commit_or_omission(self.region))

    def test_the_end_of_turn_paragraph_follows_the_empty_write_set_paragraph(
        self,
    ):
        empty_idx = self.region.index(EMPTY_PARAGRAPH_START)
        end_idx = self.region.index(END_OF_TURN_PHRASE)
        self.assertLess(empty_idx, end_idx)

    def test_batch_marker_only_sentence_occurs_exactly_once(self):
        self.assertEqual(len(MARKER_ONLY_SENTENCE_RE.findall(self.region)), 1)

    def test_region_l_keeps_the_launch_state_commit_term(self):
        self.assertIn(LAUNCH_STATE_COMMIT_TERM, self.region)


class TestAC4TerminalTasksAndTheExit4Retry(unittest.TestCase):
    """AC-4 (FR4): a last event `merged` is left to I.2.b; no terminal task
    is written `in_progress`; the retry re-derives both parts; the second
    exit 4 still stops keeping the records, worktrees and branches."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.region = _normalize_ws(_region_l(text))
        cls.exit4 = _slice(cls.region, EXIT4_PARAGRAPH_START, END_OF_TURN_START)
        cls.branch_model = _normalize_ws(_branch_worktree_model_section(text))

    def test_merged_last_event_is_never_written_and_left_to_i2b(self):
        self.assertTrue(_merged_left_to_i2b(self.region))

    def test_no_terminal_task_is_written_in_progress(self):
        self.assertIn(TERMINAL_NEVER_IN_PROGRESS_PHRASE, self.region)

    def test_retry_re_derives_both_parts_after_the_re_capture_and_refresh(self):
        self.assertTrue(_retry_rederives_both_parts(self.region))

    def test_retry_phrases_are_found_in_the_exit4_paragraph_not_before_it(self):
        # The exit-4 paragraph is a proper tail of Region L, and the retry
        # phrase that is new is not found anywhere before it.
        before = self.region[: self.region.index(EXIT4_PARAGRAPH_START)]
        self.assertNotIn(RETRY_BOTH_PARTS_PHRASE, before)
        self.assertIn(RETRY_BOTH_PARTS_PHRASE, self.exit4)

    def test_second_exit4_still_stops_and_keeps_records_worktrees_branches(
        self,
    ):
        for phrase in SECOND_EXIT4_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.exit4)

    def test_exit4_recovery_is_cited_not_restated(self):
        self.assertIn(EXIT4_CITATION_PHRASE, self.exit4)
        for phrase in EXIT4_BULLET_PHRASES:
            with self.subTest(phrase=phrase):
                # Non-vacuity: the bullet really says it, so absence from
                # Region L means "not restated" rather than "never existed".
                self.assertIn(phrase, self.branch_model)
                self.assertNotIn(phrase, self.region)


class TestAC5NewWordingMatchersFailOnPreChangeSample(unittest.TestCase):
    """AC-5 (FR6, NFR4): every new-wording matcher holds on the live
    Region L and fails on the verbatim pre-change sample, and each failure
    is backed by a non-vacuity guard."""

    @classmethod
    def setUpClass(cls):
        live_raw = _region_l(_read())
        cls.live = _normalize_ws(live_raw)
        cls.sample = _normalize_ws(PRE_CHANGE_REGION_L)

    def test_every_matcher_holds_on_the_live_region_l(self):
        for name, matcher in NEW_WORDING_MATCHERS.items():
            with self.subTest(matcher=name):
                self.assertTrue(matcher(self.live))

    def test_every_matcher_fails_on_the_pre_change_sample(self):
        for name, matcher in NEW_WORDING_MATCHERS.items():
            with self.subTest(matcher=name):
                self.assertFalse(matcher(self.sample))

    def test_the_sample_is_the_whole_pre_change_region_l(self):
        self.assertTrue(PRE_CHANGE_REGION_L.startswith(REGION_L_START))
        self.assertTrue(
            self.sample.endswith(
                "marker line `references/batch-mode.md` defines and nothing "
                "else."
            )
        )

    def test_non_vacuity_anchors_are_in_both_sample_and_live_region_l(self):
        for anchor in NON_VACUITY_ANCHORS:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.sample)
                self.assertIn(anchor, self.live)

    def test_slice_boundaries_the_matchers_use_are_in_both(self):
        # A matcher that slices between two boundaries fails on the sample
        # because the new wording is missing, not because a boundary is.
        for anchor in SLICE_BOUNDARY_ANCHORS:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.sample)
                self.assertIn(anchor, self.live)

    def test_sample_still_has_the_old_single_part_wording(self):
        # The sample is what the new wording replaces: a write set of the
        # launched tasks only, with terminal tasks excluded outright.
        self.assertIn(
            "The write set is the tasks selected in this entry whose journal "
            "last event is `launched`",
            self.sample,
        )
        self.assertIn(
            "last event `merged` or `failed` (terminal) → not in the write "
            "set; never written `in_progress`",
            self.sample,
        )
        self.assertNotIn(FAILED_PART_LABEL, self.sample)

    def test_the_phrases_kept_by_the_earlier_task_are_in_both(self):
        for phrase in (
            "The write set is the tasks selected in this entry whose journal "
            "last event is `launched`",
            "re-read the latest journal",
            NEVER_IN_PROGRESS_PHRASE,
            LAUNCH_STATE_COMMIT_TERM,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.sample)
                self.assertIn(phrase, self.live)


class TestAC6OnlyRegionLChanges(unittest.TestCase):
    """AC-6 (NFR1, NFR2, NFR3): the sections no task of this feature edits
    are byte-identical to the base revision. Run on raw text."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_step_i2_intro_is_byte_identical_to_the_base_revision(self):
        self.assertEqual(
            _digest(_step_i2_intro(self.text)), STEP_I2_INTRO_SHA256
        )

    def test_branch_worktree_model_is_byte_identical_to_the_base_revision(self):
        self.assertEqual(
            _digest(_branch_worktree_model_section(self.text)),
            BRANCH_WORKTREE_MODEL_SHA256,
        )

    def test_digest_is_sensitive_to_a_one_character_change(self):
        # Non-vacuity guard: the digest comparison above would notice an edit.
        section = _branch_worktree_model_section(self.text)
        self.assertNotEqual(_digest(section + " "), BRANCH_WORKTREE_MODEL_SHA256)
        self.assertNotEqual(_digest(section[1:]), BRANCH_WORKTREE_MODEL_SHA256)

    def test_region_l_is_a_proper_slice_between_the_two_headings(self):
        i2a = _i2a_section(self.text)
        region_p = _region_p(self.text)
        region_l = _region_l(self.text)
        self.assertTrue(i2a.startswith(I2A_HEADING))
        self.assertEqual(region_p + region_l, i2a)
        self.assertTrue(region_l.startswith(REGION_L_START))
        self.assertIn(END_OF_TURN_START, region_l)


if __name__ == "__main__":
    unittest.main()

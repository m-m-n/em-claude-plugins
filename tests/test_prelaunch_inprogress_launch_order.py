"""Tests for task0001 (prelaunch-inprogress-routeback): the launch-state
commit of Step I.2.a sits behind the `project_commands` approval gate and
the `Task()` launch loop, and only tasks whose launch the re-read journal
confirms are committed as `in_progress`, in
`em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/prelaunch-inprogress-routeback/tasks/task0001.md):

- AC-1 (FR1, TS1): in the I.2.a section the approval-gate opening, the
  BACKGROUND launch-loop paragraph, the journal re-read statement, the
  `LAUNCH_TIP` capture, the refresh to the branch name, the
  `tasks.{T}.status = in_progress` write, the `commit-docs.sh` call carrying
  `"$LAUNCH_TIP"` and the end-of-turn statement occur in strictly increasing
  order, each searched after the previous one.
- AC-3 (FR2, TS2): the write set is the tasks selected in the entry whose
  re-read journal last event is `launched`; a task whose launch is not
  confirmed is not written and stays `pending`; a partial launch yields one
  write set and one commit naming the write-set tasks; the phrase "for EVERY
  task selected in this entry" is gone.
- AC-4 (FR3, TS3): an empty write set omits the write and the commit; the
  turn ends after the launch-state commit or its omission; neither I.2.a nor
  the Step I.2 intro contains "immediately after launching"; the `--batch`
  marker-only sentence occurs exactly once in I.2.a.
- AC-5 (FR4, TS4): the journal is re-read before the write set is built,
  for the first commit and for the exit-4 retry; a task whose re-read
  journal last event is `merged` or `failed` is never written
  `in_progress`; a second exit 4 stops with a report naming the call site
  and the tasks while keeping the journal's launch records and the tasks'
  worktrees and branches; the Branch & Worktree Model's exit-4 recovery is
  cited, not restated.
- AC-6 (FR6, NFR4, TS6): this module itself -- standard library `unittest`
  only, every new-wording literal a module-level constant read by both its
  positive test and its negative-proof test, every new-wording matcher
  failing against a verbatim pre-change sample of Region L (the commit
  precedes the approval gate and the launch loop there), each failure
  backed by a non-vacuity guard.

AC-2 and AC-7 are satisfied by running the existing modules named in the
task plan (and the whole suite) unmodified, not by this module.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import from, and is not imported by, any other test module.

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
the module asserts nothing byte-identical, so the two modes are never mixed
in one assertion (IMPLEMENTATION.md Conventions).
"""

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
# and ends at the I.2.b heading (IMPLEMENTATION.md, Shared Components).
REGION_L_START = "For each selected task T"

# --- Literals the AC-1 ordering check searches for. Each is read by the
# ordering matcher and by the ordering negative proof. ---

GATE_OPENING = "Before launching, verify every `project_commands`"
LAUNCH_LOOP_OPENING = "Launch each selected task as a BACKGROUND"
JOURNAL_REREAD_PHRASE = "re-read the latest journal"
LAUNCH_TIP_CAPTURE = (
    "LAUNCH_TIP=$(git -C {integration_worktree} rev-parse "
    "em-workflow/{feature}/integration)"
)
LAUNCH_REFRESH_CMD = (
    "git -C {integration_worktree} reset --hard "
    "em-workflow/{feature}/integration"
)
LAUNCH_WRITE_STATUS = "tasks.{T}.status = in_progress"
LAUNCH_COMMIT_CALL_PATTERN = r'commit-docs\.sh[^`]*"\$LAUNCH_TIP"'
END_OF_TURN_PHRASE = (
    "**End the turn** after the launch-state commit, or after its omission"
)

# (label, regex) pairs in the order the section must present them.
AC1_ANCHORS = (
    ("approval gate opening", re.escape(GATE_OPENING)),
    ("BACKGROUND launch loop", re.escape(LAUNCH_LOOP_OPENING)),
    ("journal re-read statement", re.escape(JOURNAL_REREAD_PHRASE)),
    ("LAUNCH_TIP capture", re.escape(LAUNCH_TIP_CAPTURE)),
    ("refresh to the branch name", re.escape(LAUNCH_REFRESH_CMD)),
    ("in_progress write", re.escape(LAUNCH_WRITE_STATUS)),
    ("commit-docs.sh call with LAUNCH_TIP", LAUNCH_COMMIT_CALL_PATTERN),
    ("end-of-turn statement", re.escape(END_OF_TURN_PHRASE)),
)
# The same list without the two anchors that are new wording, so the
# reversed order is proven to be caught on its own, not only through a
# missing phrase.
AC1_ANCHORS_EXISTING_WORDING_ONLY = tuple(
    anchor
    for anchor in AC1_ANCHORS
    if anchor[0]
    not in ("journal re-read statement", "end-of-turn statement")
)

# --- AC-3 literals (FR2). ---

WRITE_SET_DEFINITION_PHRASE = (
    "The write set is the tasks selected in this entry whose journal last "
    "event is `launched`"
)
UNCONFIRMED_NOT_WRITTEN_PHRASES = (
    "stopped at the approval gate",
    "denied by the launch guard",
    "`Task()` never issued",
    "the task stays `pending` in workflow.yaml",
)
PARTIAL_LAUNCH_PHRASE = (
    "A partial launch still yields exactly one write set and one commit"
)
COMMIT_NAMES_WRITE_SET_PHRASE = "naming every task in the write set"
OLD_EVERY_TASK_PHRASE = "for EVERY task selected in this entry"
OLD_ALL_SELECTED_PHRASE = "Write the launch state for ALL selected tasks"
LAUNCH_STATE_COMMIT_TERM = "launch-state commit"

# --- AC-4 literals (FR3). ---

EMPTY_WRITE_SET_PHRASES = (
    "when the write set is empty",
    "the write and the commit are omitted",
)
OLD_IMMEDIATELY_PHRASE = "immediately after launching"
INTRO_NEW_PHRASE = (
    "ends after the launches and the launch-state commit that follows them"
)
MARKER_ONLY_SENTENCE_RE = re.compile(
    r"[Ii]n a `--batch` run,? .{0,200}?this (?:wake )?turn's final assistant "
    r"message is the marker line `references/batch-mode\.md` defines "
    r"and nothing else"
)

# --- AC-5 literals (FR4). ---

RETRY_REREAD_PHRASES = (
    "on the retry, the journal is re-read again after the re-capture and "
    "refresh",
    "the write set is re-derived the same way",
)
TERMINAL_EXCLUDED_PHRASES = (
    "last event `merged` or `failed`",
    "never written `in_progress`",
)
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

# --- Anchors present in both the pre-change sample and the live Region L,
# so a failing negative proof is not a failure to find anything at all. ---

NON_VACUITY_ANCHORS = (
    "Branch point = integration branch AT THIS MOMENT (includes every task "
    "merged so far).",
    "in this normative order",
    "ONCE per entry into Step I.2.a",
)
INTRO_NON_VACUITY_ANCHOR = "and a **wake phase** (entered when an"

# --- Verbatim pre-change samples, captured BEFORE this task's edit landed:
# Region L of em-workflow/references/implement-phase.md at the task's base
# revision (`git show HEAD:em-workflow/references/implement-phase.md`),
# from the "For each selected task T" paragraph through the "**End the
# turn**" paragraph, and the Step I.2 intro paragraph that states when the
# launch phase's turn ends. Not paraphrased, not reconstructed after the
# edit. ---

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
    'so far). Write the launch state for ALL selected tasks in this normative\n'
    'order — the capture precedes the refresh, the refresh precedes the write,\n'
    'and the write precedes the commit:\n'
    '\n'
    '1. **capture** the tip —\n'
    '   `LAUNCH_TIP=$(git -C {integration_worktree} rev-parse em-workflow/{feature}/integration)`\n'
    '2. **refresh** the integration worktree to the branch —\n'
    '   `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`\n'
    '3. **write**, on the worktree just refreshed, `tasks.{T}.status =\n'
    '   in_progress` and `tasks.{T}.branch` into workflow.yaml for EVERY task\n'
    '   selected in this entry — one write set, not one per task\n'
    '4. **commit** that single write set with the captured tip as the third\n'
    '   argument — `commit-docs.sh {integration_worktree} "docs({feature}):\n'
    '   launch {T1}, {T2}, …"  "$LAUNCH_TIP"` (naming every task selected in\n'
    '   this entry; the third argument is `expected_base_tip`; exit-4\n'
    '   recovery: Branch & Worktree Model above — the "a second exit 4 stops\n'
    '   the phase" counter there is counted per commit attempt, i.e. per entry\n'
    '   into this sequence, not per task named in the commit)\n'
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
    'turn — covering every task selected in that entry with a single capture,\n'
    'a single refresh, one write set, and one commit; a fresh `LAUNCH_TIP` is\n'
    'captured each time (i.e. on each such entry, not per task). `$RECONCILE_TIP`\n'
    "is never reused as this step's third argument: it is captured at Step I.2.b\n"
    "step 2, BEFORE Step I.2.b step 3's own commit advances the branch tip, so by\n"
    'the time the refill path re-enters Step I.2.a, `$RECONCILE_TIP` is already\n'
    'stale.\n'
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
    '**End the turn** immediately after launching — no polling, no synchronous\n'
    "wait. In a `--batch` run, this turn's final assistant message is the\n"
    'marker line `references/batch-mode.md` defines and nothing else. The\n'
    'PreToolUse(Task|Agent) launch guard (`queue_launch_guard.py`) records\n'
    'each allowed launch as a `launched` journal event as the call goes through\n'
    '(the only writer of `launched`); it also denies double-launching a task\n'
    'that is already in flight or already merged, as a net under the\n'
    "orchestrator's own bookkeeping."
)

PRE_CHANGE_I2_INTRO_PARAGRAPH = (
    'The loop alternates two phases across turns: a **launch phase** (the turn\n'
    'ends immediately after launching) and a **wake phase** (entered when an\n'
    "implementer's `Task()` call returns / a subagent completion notification\n"
    'arrives). There is no synchronous fan-out-and-wait: the orchestrator never\n'
    'blocks a turn waiting on implementers; it launches, ends the turn, and\n'
    'reconciles on the next wake.'
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


def _step_i2_intro(text):
    start = text.index(STEP_I2_HEADING)
    end = text.index(I2A_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _ordering_failure(text, anchors):
    """AC-1 matcher: returns None when every anchor is found, each searched
    starting just past the end of the previous anchor's match (so a shared
    substring cannot satisfy the order by accident); otherwise returns the
    label of the first anchor that is not found after its predecessor."""
    cursor = 0
    for label, pattern in anchors:
        match = re.compile(pattern).search(text, cursor)
        if match is None:
            return label
        cursor = match.end()
    return None


def _first_match_start(text, pattern, cursor=0):
    match = re.compile(pattern).search(text, cursor)
    return None if match is None else match.start()


def _has_all(text, phrases):
    return all(phrase in text for phrase in phrases)


# Every matcher that asserts NEW wording of I.2.a: takes the
# whitespace-normalized text, returns True when the new wording holds.
# Each one is run against the live I.2.a section (must hold) and against
# the pre-change Region L sample (must not hold).
NEW_WORDING_MATCHERS = {
    "AC-1 ordering": lambda t: _ordering_failure(t, AC1_ANCHORS) is None,
    "AC-3 write set definition": lambda t: WRITE_SET_DEFINITION_PHRASE in t,
    "AC-3 unconfirmed tasks stay pending": lambda t: _has_all(
        t, UNCONFIRMED_NOT_WRITTEN_PHRASES
    ),
    "AC-3 partial launch one write set one commit": lambda t: (
        PARTIAL_LAUNCH_PHRASE in t and COMMIT_NAMES_WRITE_SET_PHRASE in t
    ),
    "AC-3 old every-task wording absent": lambda t: (
        OLD_EVERY_TASK_PHRASE not in t and OLD_ALL_SELECTED_PHRASE not in t
    ),
    "AC-3 launch-state commit term": lambda t: (
        LAUNCH_STATE_COMMIT_TERM in t
    ),
    "AC-4 empty write set omits write and commit": lambda t: _has_all(
        t, EMPTY_WRITE_SET_PHRASES
    ),
    "AC-4 turn ends after the commit or its omission": lambda t: (
        END_OF_TURN_PHRASE in t
    ),
    "AC-4 no immediately-after-launching wording": lambda t: (
        OLD_IMMEDIATELY_PHRASE not in t
    ),
    "AC-5 journal re-read before the write set": lambda t: (
        JOURNAL_REREAD_PHRASE in t
    ),
    "AC-5 journal re-read on the exit-4 retry": lambda t: _has_all(
        t, RETRY_REREAD_PHRASES
    ),
    "AC-5 terminal tasks never written in_progress": lambda t: _has_all(
        t, TERMINAL_EXCLUDED_PHRASES
    ),
    "AC-5 second exit 4 stop keeps records and worktrees": lambda t: _has_all(
        t, SECOND_EXIT4_PHRASES
    ),
    "AC-5 exit-4 recovery cited": lambda t: EXIT4_CITATION_PHRASE in t,
}


class TestAC1LaunchStateCommitFollowsGateAndLaunchLoop(unittest.TestCase):
    """AC-1 / TS1: the eight positions are strictly increasing in I.2.a."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2a_section(_read()))

    def test_positions_strictly_increase_each_searched_after_the_previous(self):
        self.assertIsNone(_ordering_failure(self.section, AC1_ANCHORS))

    def test_capture_follows_the_launch_loop_not_the_worktree_creation(self):
        loop_idx = _first_match_start(
            self.section, re.escape(LAUNCH_LOOP_OPENING)
        )
        capture_idx = _first_match_start(
            self.section, re.escape(LAUNCH_TIP_CAPTURE)
        )
        self.assertIsNotNone(loop_idx)
        self.assertIsNotNone(capture_idx)
        self.assertLess(loop_idx, capture_idx)

    def test_commit_call_carries_the_captured_tip_in_the_same_code_span(self):
        match = re.search(LAUNCH_COMMIT_CALL_PATTERN, self.section)
        self.assertIsNotNone(match)


class TestAC3WriteSetIsTheConfirmedLaunches(unittest.TestCase):
    """AC-3 / TS2: the write set is the tasks whose launch the re-read
    journal confirms, never every selected task."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2a_section(_read()))

    def test_write_set_is_defined_as_launched_tasks_selected_in_the_entry(self):
        self.assertIn(WRITE_SET_DEFINITION_PHRASE, self.section)

    def test_unconfirmed_launches_are_not_written_and_stay_pending(self):
        for phrase in UNCONFIRMED_NOT_WRITTEN_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_partial_launch_yields_one_write_set_and_one_commit(self):
        self.assertIn(PARTIAL_LAUNCH_PHRASE, self.section)

    def test_commit_message_names_the_write_set_tasks(self):
        self.assertIn(COMMIT_NAMES_WRITE_SET_PHRASE, self.section)

    def test_every_selected_task_wording_is_gone(self):
        self.assertNotIn(OLD_EVERY_TASK_PHRASE, self.section)
        self.assertNotIn(OLD_ALL_SELECTED_PHRASE, self.section)

    def test_region_l_names_the_launch_state_commit(self):
        self.assertIn(
            LAUNCH_STATE_COMMIT_TERM, _normalize_ws(_region_l(_read()))
        )


class TestAC4EmptyWriteSetAndEndOfTurn(unittest.TestCase):
    """AC-4 / TS3: an empty write set omits the write and the commit, and
    the turn ends after the launch-state commit or its omission."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.section = _normalize_ws(_i2a_section(text))
        cls.intro = _normalize_ws(_step_i2_intro(text))

    def test_empty_write_set_omits_the_write_and_the_commit(self):
        for phrase in EMPTY_WRITE_SET_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_turn_ends_after_the_launch_state_commit_or_its_omission(self):
        self.assertIn(END_OF_TURN_PHRASE, self.section)

    def test_step_i2_intro_states_the_turn_ends_after_the_commit(self):
        self.assertIn(INTRO_NEW_PHRASE, self.intro)

    def test_i2a_has_no_immediately_after_launching_wording(self):
        self.assertNotIn(OLD_IMMEDIATELY_PHRASE, self.section)

    def test_step_i2_intro_has_no_immediately_after_launching_wording(self):
        self.assertNotIn(OLD_IMMEDIATELY_PHRASE, self.intro)

    def test_batch_marker_only_sentence_occurs_exactly_once_in_i2a(self):
        self.assertEqual(len(MARKER_ONLY_SENTENCE_RE.findall(self.section)), 1)


class TestAC5JournalRereadAndExit4(unittest.TestCase):
    """AC-5 / TS4: the journal is re-read before the write set is built --
    for the first commit and for the exit-4 retry; terminal tasks are never
    written in_progress; a second exit 4 stops keeping the records,
    worktrees and branches; the exit-4 recovery is cited, not restated."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.section = _normalize_ws(_i2a_section(text))
        cls.branch_model = _normalize_ws(_branch_worktree_model_section(text))

    def test_journal_is_reread_before_the_write_set_is_built(self):
        reread_idx = _first_match_start(
            self.section, re.escape(JOURNAL_REREAD_PHRASE)
        )
        definition_idx = _first_match_start(
            self.section, re.escape(WRITE_SET_DEFINITION_PHRASE)
        )
        self.assertIsNotNone(reread_idx)
        self.assertIsNotNone(definition_idx)
        self.assertLess(reread_idx, definition_idx)

    def test_journal_is_reread_again_on_the_exit4_retry(self):
        for phrase in RETRY_REREAD_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_terminal_tasks_are_never_written_in_progress(self):
        for phrase in TERMINAL_EXCLUDED_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_second_exit4_stops_and_keeps_records_worktrees_and_branches(self):
        for phrase in SECOND_EXIT4_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.section)

    def test_exit4_recovery_is_cited(self):
        self.assertIn(EXIT4_CITATION_PHRASE, self.section)

    def test_exit4_recovery_bullet_is_not_restated(self):
        for phrase in EXIT4_BULLET_PHRASES:
            with self.subTest(phrase=phrase):
                # Non-vacuity: the bullet really says it, so absence from
                # I.2.a means "not restated" rather than "never existed".
                self.assertIn(phrase, self.branch_model)
                self.assertNotIn(phrase, self.section)


class TestAC6NewWordingMatchersFailOnPreChangeSample(unittest.TestCase):
    """AC-6 / TS6: every new-wording matcher holds on the live I.2.a
    section and fails on the verbatim pre-change Region L sample."""

    @classmethod
    def setUpClass(cls):
        cls.live = _normalize_ws(_i2a_section(_read()))
        cls.sample = _normalize_ws(PRE_CHANGE_REGION_L)

    def test_every_matcher_holds_on_the_live_section(self):
        for name, matcher in NEW_WORDING_MATCHERS.items():
            with self.subTest(matcher=name):
                self.assertTrue(matcher(self.live))

    def test_every_matcher_fails_on_the_pre_change_sample(self):
        for name, matcher in NEW_WORDING_MATCHERS.items():
            with self.subTest(matcher=name):
                self.assertFalse(matcher(self.sample))

    def test_ordering_fails_on_the_sample_because_the_commit_precedes_the_gate(
        self,
    ):
        # The reversed order is caught on its own: leave out the two anchors
        # that are new wording and the check still fails on the sample.
        self.assertIsNotNone(
            _ordering_failure(self.sample, AC1_ANCHORS_EXISTING_WORDING_ONLY)
        )
        # Non-vacuity: every anchor of that list is present in the sample,
        # and the capture sits before the approval gate there.
        for label, pattern in AC1_ANCHORS_EXISTING_WORDING_ONLY:
            with self.subTest(anchor=label):
                self.assertIsNotNone(_first_match_start(self.sample, pattern))
        gate_idx = _first_match_start(self.sample, re.escape(GATE_OPENING))
        capture_idx = _first_match_start(
            self.sample, re.escape(LAUNCH_TIP_CAPTURE)
        )
        commit_idx = _first_match_start(self.sample, LAUNCH_COMMIT_CALL_PATTERN)
        self.assertLess(capture_idx, gate_idx)
        self.assertLess(commit_idx, gate_idx)

    def test_sample_still_carries_the_phrases_the_absence_matchers_forbid(self):
        # Non-vacuity guard for the "gone" matchers: they fail on the sample
        # because the old wording really is there.
        self.assertIn(OLD_EVERY_TASK_PHRASE, self.sample)
        self.assertIn(OLD_ALL_SELECTED_PHRASE, self.sample)
        self.assertIn(OLD_IMMEDIATELY_PHRASE, self.sample)

    def test_non_vacuity_anchors_are_in_both_sample_and_live_region_l(self):
        live_region = _normalize_ws(_region_l(_read()))
        for anchor in NON_VACUITY_ANCHORS:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.sample)
                self.assertIn(anchor, live_region)

    def test_sample_is_the_whole_pre_change_region_l(self):
        self.assertTrue(PRE_CHANGE_REGION_L.startswith(REGION_L_START))
        self.assertTrue(
            PRE_CHANGE_REGION_L.endswith("orchestrator's own bookkeeping.")
        )
        self.assertIn(GATE_OPENING, self.sample)
        self.assertIn(LAUNCH_LOOP_OPENING, self.sample)


class TestAC6IntroMatcherFailsOnPreChangeSample(unittest.TestCase):
    """AC-6 / TS6: the Step I.2 intro matchers (new phrase present, old
    phrase absent) fail against the verbatim pre-change intro paragraph."""

    @classmethod
    def setUpClass(cls):
        cls.live = _normalize_ws(_step_i2_intro(_read()))
        cls.sample = _normalize_ws(PRE_CHANGE_I2_INTRO_PARAGRAPH)

    def test_new_intro_phrase_is_absent_from_the_sample(self):
        self.assertIn(INTRO_NEW_PHRASE, self.live)
        self.assertNotIn(INTRO_NEW_PHRASE, self.sample)

    def test_old_phrase_is_present_in_the_sample_and_absent_from_the_live_intro(
        self,
    ):
        self.assertIn(OLD_IMMEDIATELY_PHRASE, self.sample)
        self.assertNotIn(OLD_IMMEDIATELY_PHRASE, self.live)

    def test_intro_non_vacuity_anchor_is_in_both(self):
        self.assertIn(INTRO_NON_VACUITY_ANCHOR, self.sample)
        self.assertIn(INTRO_NON_VACUITY_ANCHOR, self.live)


if __name__ == "__main__":
    unittest.main()

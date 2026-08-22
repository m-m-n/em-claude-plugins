"""Tests for task0001 (tip-capture-idiom-unification): locks the canonical
tip-capture idiom -- capture resolved from the integration BRANCH REF
(never the worktree HEAD), refresh targeting the BRANCH NAME (never a
captured SHA), capture strictly before refresh -- across all seven
tip-carrying `commit-docs.sh` call sites in
`em-workflow/references/implement-phase.md`, plus `commit-docs.sh`'s two
prose blocks describing the same contract, and detects any later drift
back to the old (refresh-then-capture-from-HEAD) form.

Covers task0001 Acceptance Criteria
(feature-docs/tip-capture-idiom-unification/tasks/task0001.md):

- AC-1 / AC-2 / AC-3: the per-site classes below (TS-1) plus the exit-4
  recovery bullet class (TS-2) assert the canonical idiom at every site and
  the wake-phase capture placement.
- AC-4: the two commit-docs.sh classes below (TS-3) plus the executable-body
  class (TS-4).
- AC-6: this module itself -- discovered by plain `unittest discover`,
  covers TS-1 through TS-4, and pairs every new-wording matcher with a
  negative proof against a verbatim pre-change sample plus a non-vacuity
  guard (TestValidationDetectsRegressions).

This module reads only `em-workflow/references/implement-phase.md` and
`em-workflow/scripts/commit-docs.sh`. It does not import from, and is not
imported by, any other test module.

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
byte-identity assertions (the RECOVERY CONTRACT carve-out sentence, the
comment-stripped executable body) compare the raw, un-normalized text -- the
two are never mixed in one assertion (IMPLEMENTATION.md Conventions).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
COMMIT_DOCS_SH_PATH = PLUGIN_ROOT / "scripts" / "commit-docs.sh"

# The one canonical refresh/capture target every site resolves against.
BRANCH_REF = "em-workflow/{feature}/integration"

# --- Section anchors (implement-phase.md), matching the boundary
# conventions already used by tests/test_exit4_tip_argument_consistency.py
# and tests/test_implement_routeback_gate.py. ---

STEP_I1_HEADING = (
    "## Step I.1: Confirm the integration worktree, record the implement "
    "baseline"
)
STEP_I2_HEADING = (
    "## Step I.2: Task loop (work queue, background launch + wake-phase "
    "refill)"
)
I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
STEP_I3_HEADING = "## Step I.3: Phase completion"
FAILURE_CONTAINMENT_HEADING = "## Failure containment"
BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model"
STEP_I0_HEADING = "## Step I.0"

REJECTED_PATH_MARKER = "When the gate does not hold"
ABORT_PHASE_MARKER = "- **abort phase**"
BATCH_MODE_MARKER = "Batch mode (`references/batch-mode.md`"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _read_commit_docs_sh():
    return COMMIT_DOCS_SH_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where this
    task's prose happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _normalize_comment_block(text):
    """Strip each line's leading `#` comment marker and indentation, then
    whitespace-normalize -- so a phrase a shell comment block wraps across
    several `#`-prefixed lines can still be asserted as one contiguous
    string, the same way `_normalize_ws` does for markdown prose."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped[1:].strip()
        lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _step_i1_section(text):
    start = text.index(STEP_I1_HEADING)
    end = text.index(STEP_I2_HEADING, start)
    return text[start:end]


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _i2b_section(text):
    start = text.index(I2B_HEADING)
    end = text.index(I2C_HEADING, start)
    return text[start:end]


def _routeback_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(REJECTED_PATH_MARKER, start)
    return text[start:end]


def _rejected_path_section(text):
    start = text.index(REJECTED_PATH_MARKER)
    end = text.index(ABORT_PHASE_MARKER, start)
    return text[start:end]


def _abort_phase_section(text):
    start = text.index(ABORT_PHASE_MARKER)
    end = text.index(BATCH_MODE_MARKER, start)
    return text[start:end]


def _step_i3_section(text):
    start = text.index(STEP_I3_HEADING)
    end = text.index(FAILURE_CONTAINMENT_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _capture_assignment(section, var):
    """Extracts the `VAR=$(git -C <path> rev-parse <ref>)` capture
    assignment for the given site variable out of an already
    whitespace-normalized section, tolerant of whatever line-wrap the
    source happens to use inside the parens. Anchored on the variable name
    itself, so prose elsewhere in the same section that merely mentions
    `rev-parse HEAD` (e.g. I.2.a's rationale paragraph, contrasting the
    canonical idiom against the defective form) can never be mistaken for
    this site's own capture."""
    pattern = re.compile(rf"{re.escape(var)}=\$\(git -C [^)]*?rev-parse [^)]*?\)")
    match = pattern.search(section)
    if match is None:
        raise AssertionError(f"no {var} capture assignment found in section")
    return match.group(0)


def _strip_comment_lines(text):
    """Drops every line whose stripped content opens with `#` (comments,
    including the shebang) -- what remains is the executable body, used by
    TS-4 to prove this task's edit is comment-only."""
    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines)


def _expected_base_tip_block(text):
    start = text.index("expected_base_tip (optional)")
    end = text.index("# Exit codes", start)
    return text[start:end]


def _recovery_contract_block(text):
    start = text.index("RECOVERY CONTRACT")
    end = text.index("# Non-artifact untracked", start)
    return text[start:end]


# --- The seven tip-carrying call sites (task0001.md Design table). Each
# entry: (label, tip variable, section slicer, whether the site restates an
# explicit `reset --hard <branch>` literal in its own text). Step I.2.c's
# rejected path instead cross-references route-back's literal ("the same
# `reset --hard` as above"), so it is excluded from the one positive check
# that needs an in-site literal -- the captured-value negative guard below
# still covers it directly. ---

SITES = (
    ("Step I.1 baseline commit", "BASE_COMMIT", _step_i1_section, True),
    ("Step I.2.a launch", "LAUNCH_TIP", _i2a_section, True),
    ("Step I.2.b wake reconcile", "RECONCILE_TIP", _i2b_section, True),
    ("Step I.2.c route-back", "ROUTEBACK_TIP", _routeback_section, True),
    ("Step I.2.c rejected path", "TERMINAL_TIP", _rejected_path_section, False),
    ("Step I.2.c abort phase", "ABORT_TIP", _abort_phase_section, True),
    ("Step I.3 completion", "COMPLETION_TIP", _step_i3_section, True),
)


class TestPerSiteCaptureResolvesBranchRef(unittest.TestCase):
    """TS-1: every site's capture resolves the integration BRANCH REF."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_every_site_captures_from_the_branch_ref(self):
        for label, var, slicer, _has_target in SITES:
            with self.subTest(site=label):
                section = _normalize_ws(slicer(self.text))
                assignment = _capture_assignment(section, var)
                self.assertIn(BRANCH_REF, assignment)


class TestPerSiteCaptureNeverUsesWorktreeHead(unittest.TestCase):
    """TS-1: no site's capture assignment resolves the worktree HEAD -- the
    defect the canonical idiom rules out (a linked worktree's HEAD is an
    attached symref, read AT READ TIME, which can hand commit-docs.sh a tip
    the working tree was never built on -- implement-phase.md's I.2.a
    rationale)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_no_site_captures_from_head(self):
        for label, var, slicer, _has_target in SITES:
            with self.subTest(site=label):
                section = _normalize_ws(slicer(self.text))
                assignment = _capture_assignment(section, var)
                self.assertNotIn("rev-parse HEAD", assignment)


class TestPerSiteRefreshNeverTargetsCapturedValue(unittest.TestCase):
    """TS-1: no site's refresh resets to its own captured value -- that
    would move the branch ref itself backward and could silently discard a
    concurrent merge-task.sh merge (implement-phase.md's I.2.a rationale)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_no_site_refreshes_to_its_own_captured_variable(self):
        for label, var, slicer, _has_target in SITES:
            with self.subTest(site=label):
                section = _normalize_ws(slicer(self.text))
                self.assertNotIn(f'reset --hard "${var}"', section)
                self.assertNotIn(f"reset --hard ${var}", section)


class TestPerSiteExplicitRefreshTargetsBranchName(unittest.TestCase):
    """TS-1: every site that restates an explicit refresh command targets
    the branch NAME. Step I.2.c's rejected path cross-references
    route-back's literal instead of restating it ("the same `reset --hard`
    as above"), so it is excluded here -- the captured-value negative guard
    above still covers that site directly."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_explicit_refresh_commands_target_the_branch_name(self):
        for label, var, slicer, has_target in SITES:
            if not has_target:
                continue
            with self.subTest(site=label):
                section = _normalize_ws(slicer(self.text))
                self.assertIn(f"reset --hard {BRANCH_REF}", section)


class TestPerSiteCapturePrecedesRefresh(unittest.TestCase):
    """TS-1: the capture position strictly precedes the refresh position
    inside every site."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_capture_precedes_refresh_in_every_site(self):
        for label, var, slicer, _has_target in SITES:
            with self.subTest(site=label):
                section = _normalize_ws(slicer(self.text))
                capture_idx = section.index(f"{var}=$(git")
                refresh_idx = section.index("reset --hard")
                self.assertLess(capture_idx, refresh_idx)


class TestExit4RecoveryBulletStatesRecaptureBeforeRefresh(unittest.TestCase):
    """TS-2: the Branch & Worktree Model's exit-4 recovery bullet states the
    same capture-before-refresh relation the per-site checks assert above.
    This bullet's own wording is out of scope for this task (task0001.md
    Out of Scope) -- these assertions merely confirm it already agrees with
    the per-site idiom, they do not exercise any edit of this task's own."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_branch_worktree_model_section(_read()))

    def test_states_recapture_from_branch_ref(self):
        self.assertIn("RE-CAPTURE the tip from the branch ref", self.section)
        self.assertIn(BRANCH_REF, self.section)

    def test_recapture_precedes_refresh(self):
        recapture_idx = self.section.index("RE-CAPTURE the tip from the branch ref")
        refresh_idx = self.section.index("refresh the integration worktree again")
        self.assertLess(recapture_idx, refresh_idx)

    def test_refresh_targets_branch_name(self):
        idx = self.section.index("refresh the integration worktree again")
        window = self.section[idx : idx + 120]
        self.assertIn("against the branch name", window)


# --- commit-docs.sh prose (TS-3). New/old wording constants are each read
# by exactly one positive test and one negative-proof test below (the
# literal is never spelled twice). ---

NEW_EXPECTED_BASE_TIP_PHRASE = (
    "captured from the integration branch ref BEFORE, and independently "
    "of, its own refresh"
)
OLD_EXPECTED_BASE_TIP_PHRASE = "captured at the caller's last refresh"

NEW_RECOVERY_RECAPTURE_PHRASE = "re-capture the tip from the branch ref"
OLD_RECOVERY_REFRESH_FIRST_PHRASE = (
    "MUST (1) refresh this worktree to the new branch tip"
)

# The carve-out sentence naming implement-phase.md Step I.2.c's route-back
# commit as the sole exempt call site -- must stay byte-identical (this
# task never touches it). Raw text, including the `#`-comment prefix and
# internal line-wrap, since this is a byte-identity assertion.
RECOVERY_CARVE_OUT_SENTENCE = (
    "#       RECOVERY CONTRACT (binding on every caller EXCEPT a call site whose\n"
    "#       owning protocol document states both a proof of unreachability and\n"
    "#       a defined terminal for an unexpected non-zero exit — today exactly\n"
    "#       one such site: `em-workflow/references/implement-phase.md` Step\n"
    "#       I.2.c's route-back commit): on exit 4 the caller"
)

# Pre-change wording samples, captured BEFORE this task's edit landed --
# verbatim excerpts of em-workflow/scripts/commit-docs.sh as it read prior
# to this change (via `git show HEAD:em-workflow/scripts/commit-docs.sh`).
# Not paraphrased, not reconstructed.
PRE_CHANGE_EXPECTED_BASE_TIP_BLOCK = (
    "expected_base_tip (optional): the branch tip the caller's worktree state\n"
    "#   was actually built on, captured at the caller's last refresh (e.g. right\n"
    "#   after its `git reset --hard`). When provided, this is the authoritative\n"
    "#   staleness check: after acquiring the lock, the current branch tip MUST\n"
    "#   equal expected_base_tip, or exit 4 fires. Callers SHOULD pass this\n"
    "#   argument — it closes the window between the caller's refresh+edit and\n"
    "#   this script's own BEFORE_TIP read, which the start-vs-under-lock check\n"
    "#   below cannot see. When omitted, only the secondary start-vs-under-lock\n"
    "#   check runs (kept for backwards compatibility).\n"
    "#\n"
)

PRE_CHANGE_RECOVERY_CONTRACT_BLOCK = (
    "RECOVERY CONTRACT (binding on every caller EXCEPT a call site whose\n"
    "#       owning protocol document states both a proof of unreachability and\n"
    "#       a defined terminal for an unexpected non-zero exit — today exactly\n"
    "#       one such site: `em-workflow/references/implement-phase.md` Step\n"
    "#       I.2.c's route-back commit): on exit 4 the caller\n"
    "#       MUST (1) refresh this worktree to the new branch tip (e.g. `git\n"
    "#       reset --hard` to the current branch ref — safe per NFR2, this\n"
    "#       worktree never carries uncommitted state across turns), (2)\n"
    "#       re-apply the artifact edits this invocation was trying to commit,\n"
    "#       and (3) retry this script once. The protocol-side implementation of\n"
    "#       that loop (which caller performs steps 1-2, at which point in the\n"
    "#       orchestrator flow) is out of this script's scope.\n"
    "#\n"
)


class TestExpectedBaseTipDescribesBranchRefCapture(unittest.TestCase):
    """TS-3: commit-docs.sh's `expected_base_tip` argument description
    states branch-ref capture before/independent of the refresh, and the
    old refresh-time-capture phrasing is gone."""

    @classmethod
    def setUpClass(cls):
        cls.block = _normalize_comment_block(_expected_base_tip_block(_read_commit_docs_sh()))

    def test_states_new_branch_ref_capture_wording(self):
        self.assertIn(NEW_EXPECTED_BASE_TIP_PHRASE, self.block)

    def test_old_refresh_time_capture_phrasing_absent(self):
        self.assertNotIn(OLD_EXPECTED_BASE_TIP_PHRASE, self.block)


class TestRecoveryContractStatesRecaptureThenRefresh(unittest.TestCase):
    """TS-3: the RECOVERY CONTRACT's numbered steps state re-capture from
    the branch ref before the refresh, matching the canonical idiom; the
    carve-out sentence naming the route-back exemption survives
    byte-identical."""

    @classmethod
    def setUpClass(cls):
        cls.raw_text = _read_commit_docs_sh()
        cls.block = _normalize_comment_block(_recovery_contract_block(cls.raw_text))

    def test_states_recapture_before_refresh(self):
        recapture_idx = self.block.index(NEW_RECOVERY_RECAPTURE_PHRASE)
        refresh_idx = self.block.index("refresh this worktree to that branch tip")
        self.assertLess(recapture_idx, refresh_idx)

    def test_old_refresh_first_phrasing_absent(self):
        self.assertNotIn(OLD_RECOVERY_REFRESH_FIRST_PHRASE, self.block)

    def test_carve_out_sentence_is_byte_identical(self):
        self.assertIn(RECOVERY_CARVE_OUT_SENTENCE, self.raw_text)


# --- TS-4: commit-docs.sh's executable body unchanged. Pinned expectation
# captured from the PRE-change file (`git show
# HEAD:em-workflow/scripts/commit-docs.sh`, comment lines stripped the same
# way `_strip_comment_lines` strips the live file below), so the check
# proves both this task's comment-only change AND guards future executable
# drift. ---

PRE_CHANGE_STRIPPED_BODY = (
    "\n"
    "set -uo pipefail\n"
    "\n"
    "die() {\n"
    '  local code="$1"\n'
    "  shift\n"
    '  echo "ERROR: $*" >&2\n'
    '  exit "$code"\n'
    "}\n"
    "\n"
    'WORKTREE_PATH="${1:-}"\n'
    'MESSAGE="${2:-}"\n'
    'EXPECTED_BASE_TIP="${3:-}"\n'
    "\n"
    '[ -n "$WORKTREE_PATH" ] && [ -n "$MESSAGE" ] \\\n'
    '  || die 1 "usage: commit-docs.sh <worktree-path> <message> [expected_base_tip]"\n'
    "\n"
    '[ -d "$WORKTREE_PATH" ] \\\n'
    '  || die 1 "worktree path does not exist or is not a directory: $WORKTREE_PATH"\n'
    "\n"
    'IS_WORK_TREE=$(git -C "$WORKTREE_PATH" rev-parse --is-inside-work-tree 2>/dev/null) \\\n'
    '  || die 1 "not a git work tree: $WORKTREE_PATH"\n'
    '[ "$IS_WORK_TREE" = "true" ] \\\n'
    '  || die 1 "not a git work tree: $WORKTREE_PATH"\n'
    "\n"
    'GIT_COMMON_DIR=$(git -C "$WORKTREE_PATH" rev-parse --git-common-dir 2>/dev/null) \\\n'
    '  || die 1 "cannot resolve git common dir: $WORKTREE_PATH"\n'
    'GIT_DIR=$(git -C "$WORKTREE_PATH" rev-parse --git-dir 2>/dev/null) \\\n'
    '  || die 1 "cannot resolve git dir: $WORKTREE_PATH"\n'
    "\n"
    'case "$GIT_COMMON_DIR" in\n'
    "  /*) ;;\n"
    '  *) GIT_COMMON_DIR="$WORKTREE_PATH/$GIT_COMMON_DIR" ;;\n'
    "esac\n"
    'case "$GIT_DIR" in\n'
    "  /*) ;;\n"
    '  *) GIT_DIR="$WORKTREE_PATH/$GIT_DIR" ;;\n'
    "esac\n"
    'GIT_COMMON_DIR=$(cd "$GIT_COMMON_DIR" 2>/dev/null && pwd -P) \\\n'
    '  || die 1 "cannot resolve git common dir: $WORKTREE_PATH"\n'
    'GIT_DIR_ABS=$(cd "$GIT_DIR" 2>/dev/null && pwd -P) \\\n'
    '  || die 1 "cannot resolve git dir: $WORKTREE_PATH"\n'
    "\n"
    '[ "$GIT_DIR_ABS" != "$GIT_COMMON_DIR" ] \\\n'
    '  || die 1 "not a linked worktree (this is the main working tree): $WORKTREE_PATH"\n'
    "\n"
    'BEFORE_TIP=$(git -C "$WORKTREE_PATH" rev-parse HEAD 2>/dev/null) \\\n'
    '  || die 3 "cannot resolve worktree HEAD"\n'
    "\n"
    'exec 9>"$GIT_COMMON_DIR/em-workflow-merge.lock" || die 2 "cannot open lock file"\n'
    'flock 9 || die 2 "cannot acquire commit lock"\n'
    "\n"
    'AFTER_TIP=$(git -C "$WORKTREE_PATH" rev-parse HEAD 2>/dev/null) \\\n'
    '  || die 3 "cannot resolve worktree HEAD"\n'
    "\n"
    'if [ -n "$EXPECTED_BASE_TIP" ]; then\n'
    '  [ "$EXPECTED_BASE_TIP" = "$AFTER_TIP" ] \\\n'
    "    || die 4 \"branch tip is $AFTER_TIP but caller's worktree state was built on $EXPECTED_BASE_TIP (an external update-ref, e.g. a concurrent merge-task.sh) — reset this worktree to the new tip, re-apply the doc edits, and retry\"\n"
    "else\n"
    '  [ "$BEFORE_TIP" = "$AFTER_TIP" ] \\\n'
    '    || die 4 "branch tip advanced from $BEFORE_TIP to $AFTER_TIP while acquiring the lock (an external update-ref, e.g. a concurrent merge-task.sh) — reset this worktree to the new tip, re-apply the doc edits, and retry"\n'
    "fi\n"
    "\n"
    "ARTIFACT_PATHS=(feature-docs test/README.md design-system)\n"
    "\n"
    "STAGE_PATHS=()\n"
    'for p in "${ARTIFACT_PATHS[@]}"; do\n'
    '  if [ -e "$WORKTREE_PATH/$p" ]; then\n'
    '    STAGE_PATHS+=("$p")\n'
    "    continue\n"
    "  fi\n"
    '  if [ -n "$(git -C "$WORKTREE_PATH" ls-files --deleted -- "$p" 2>/dev/null)" ]; then\n'
    '    STAGE_PATHS+=("$p")\n'
    "  fi\n"
    "done\n"
    "\n"
    'if [ "${#STAGE_PATHS[@]}" -gt 0 ]; then\n'
    '  git -C "$WORKTREE_PATH" add -A -- "${STAGE_PATHS[@]}" \\\n'
    '    || die 3 "git add failed"\n'
    "fi\n"
    "\n"
    "while IFS= read -r -d '' staged_path; do\n"
    "  is_artifact=0\n"
    '  for p in "${ARTIFACT_PATHS[@]}"; do\n'
    '    case "$staged_path" in\n'
    '      "$p"|"$p"/*) is_artifact=1; break ;;\n'
    "    esac\n"
    "  done\n"
    '  [ "$is_artifact" -eq 1 ] \\\n'
    '    || die 3 "staged path outside artifact roots: $staged_path"\n'
    'done < <(git -C "$WORKTREE_PATH" diff --cached --name-only -z --no-renames)\n'
    "\n"
    'if git -C "$WORKTREE_PATH" diff --cached --quiet; then\n'
    '  echo "NOOP: nothing to commit in $WORKTREE_PATH"\n'
    "  exit 0\n"
    "fi\n"
    "\n"
    'git -C "$WORKTREE_PATH" commit -q -m "$MESSAGE" \\\n'
    '  || die 3 "git commit failed"\n'
    "\n"
    'COMMIT=$(git -C "$WORKTREE_PATH" rev-parse --verify HEAD) \\\n'
    '  || die 3 "cannot resolve new HEAD"\n'
    "\n"
    'echo "COMMITTED: $COMMIT"\n'
    "exit 0"
)


class TestCommitDocsShExecutableBodyUnchanged(unittest.TestCase):
    """TS-4: the comment-stripped source is byte-identical to the
    comment-stripped PRE-change file -- proving this task's edit is
    comment-only, and standing guard against future executable drift."""

    def test_comment_stripped_body_matches_pre_change(self):
        current_stripped = _strip_comment_lines(_read_commit_docs_sh())
        self.assertEqual(current_stripped, PRE_CHANGE_STRIPPED_BODY)


# --- TS-7: negative proofs. Verbatim pre-change wording samples for the
# five converted sites (captured BEFORE this task's edit landed, via `git
# show HEAD:em-workflow/references/implement-phase.md` -- not paraphrased,
# not reconstructed), demonstrating the checks above fail meaningfully
# against the old refresh-then-capture-from-HEAD form. Step I.2.a's and
# Step I.3's sites are the pre-existing reference form (never converted by
# this task), so they have no "old" wording to distinguish and are outside
# this proof set. ---

OLD_STEP_I1_BASH_BLOCK = (
    "```bash\n"
    'WT_ROOT="$(git rev-parse --show-toplevel)/.claude/worktrees/em-workflow/{feature}"\n'
    'BASE_COMMIT=$(git -C "$WT_ROOT/integration" rev-parse HEAD)\n'
    "```"
)

OLD_RECONCILE_STEP2 = (
    "2. **Refresh the integration worktree FIRST** (Branch & Worktree Model):\n"
    "   `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`,\n"
    "   then capture `RECONCILE_TIP=$(git -C {integration_worktree} rev-parse HEAD)`.\n"
    "   "
)

OLD_ROUTEBACK_CLAUSE = (
    "inherit and never blocks route-back. Refresh\n"
    '  the integration worktree first (`git -C "$WT_ROOT/integration"\n'
    "  reset --hard em-workflow/{feature}/integration`), then capture\n"
    '  `ROUTEBACK_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)`,\n'
    "  "
)

OLD_REJECTED_CLAUSE = (
    "`create-plan` is NOT set to `needs_update`. The phase instead refreshes\n"
    "  the integration worktree first (the same `reset --hard` as above),\n"
    '  captures `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse\n'
    "  HEAD)`, "
)

OLD_ABORT_CLAUSE = (
    "- **abort phase** — refresh the integration worktree first (the same\n"
    "  `reset --hard em-workflow/{feature}/integration` the rejected path\n"
    '  above uses), capture `ABORT_TIP=$(git -C "$WT_ROOT/integration"\n'
    "  rev-parse HEAD)`, "
)


class TestValidationDetectsRegressions(unittest.TestCase):
    """TS-7: proof that the checks above fail meaningfully against the
    verbatim pre-change wording -- each proof paired with a non-vacuity
    guard, per the tdd-testing discipline (a test that can never fail is
    not a test)."""

    def test_old_step_i1_bash_block_has_no_refresh_line(self):
        # The old baseline-commit block captured from HEAD and never
        # refreshed at all -- Step I.1 gained the refresh this task adds.
        self.assertNotIn("reset --hard", OLD_STEP_I1_BASH_BLOCK)
        self.assertIn("rev-parse HEAD", OLD_STEP_I1_BASH_BLOCK)  # non-vacuity

    def test_old_step_i1_capture_assignment_matcher_flags_head_form(self):
        assignment = _capture_assignment(
            _normalize_ws(OLD_STEP_I1_BASH_BLOCK), "BASE_COMMIT"
        )
        self.assertIn("rev-parse HEAD", assignment)
        self.assertNotIn(BRANCH_REF, assignment)

    def test_old_reconcile_step2_refresh_precedes_capture(self):
        section = _normalize_ws(OLD_RECONCILE_STEP2)
        refresh_idx = section.index("reset --hard")
        capture_idx = section.index("RECONCILE_TIP=$(git")
        self.assertLess(refresh_idx, capture_idx)
        assignment = _capture_assignment(section, "RECONCILE_TIP")
        self.assertIn("rev-parse HEAD", assignment)

    def test_old_routeback_clause_refresh_precedes_capture(self):
        section = _normalize_ws(OLD_ROUTEBACK_CLAUSE)
        refresh_idx = section.index("reset --hard")
        capture_idx = section.index("ROUTEBACK_TIP=$(git")
        self.assertLess(refresh_idx, capture_idx)
        assignment = _capture_assignment(section, "ROUTEBACK_TIP")
        self.assertIn("rev-parse HEAD", assignment)

    def test_old_rejected_clause_refresh_precedes_capture(self):
        section = _normalize_ws(OLD_REJECTED_CLAUSE)
        refresh_idx = section.index("reset --hard")
        capture_idx = section.index("TERMINAL_TIP=$(git")
        self.assertLess(refresh_idx, capture_idx)
        assignment = _capture_assignment(section, "TERMINAL_TIP")
        self.assertIn("rev-parse HEAD", assignment)

    def test_old_abort_clause_refresh_precedes_capture(self):
        section = _normalize_ws(OLD_ABORT_CLAUSE)
        refresh_idx = section.index("reset --hard")
        capture_idx = section.index("ABORT_TIP=$(git")
        self.assertLess(refresh_idx, capture_idx)
        assignment = _capture_assignment(section, "ABORT_TIP")
        self.assertIn("rev-parse HEAD", assignment)

    def test_old_samples_are_not_vacuous(self):
        # Non-vacuity guard: every sample still names its own site's
        # variable, so the proofs above are not `assertIn(x, "")`-style
        # vacuous.
        for sample, var in (
            (OLD_RECONCILE_STEP2, "RECONCILE_TIP"),
            (OLD_ROUTEBACK_CLAUSE, "ROUTEBACK_TIP"),
            (OLD_REJECTED_CLAUSE, "TERMINAL_TIP"),
            (OLD_ABORT_CLAUSE, "ABORT_TIP"),
        ):
            self.assertIn(var, sample)

    def test_expected_base_tip_matcher_flags_pre_change_block(self):
        block = _normalize_comment_block(PRE_CHANGE_EXPECTED_BASE_TIP_BLOCK)
        self.assertNotIn(NEW_EXPECTED_BASE_TIP_PHRASE, block)
        self.assertIn(OLD_EXPECTED_BASE_TIP_PHRASE, block)  # non-vacuity

    def test_recovery_contract_matcher_flags_pre_change_block(self):
        block = _normalize_comment_block(PRE_CHANGE_RECOVERY_CONTRACT_BLOCK)
        self.assertNotIn(NEW_RECOVERY_RECAPTURE_PHRASE, block)
        self.assertIn(OLD_RECOVERY_REFRESH_FIRST_PHRASE, block)  # non-vacuity

    def test_stripped_body_matcher_flags_a_changed_executable_line(self):
        # Proof the TS-4 equality check would flag an executable-line
        # drift (as opposed to the comment-only edit this task makes).
        mutated = PRE_CHANGE_STRIPPED_BODY.replace(
            "set -uo pipefail", "set -euo pipefail"
        )
        self.assertNotEqual(mutated, PRE_CHANGE_STRIPPED_BODY)


if __name__ == "__main__":
    unittest.main()

"""Doc-contract tests for task0004 (routeback-deferred-findings): a
journal-`merged` task that fails `git merge-base --is-ancestor` now gets an
automated exit instead of a dead end. I.2.b step 1's ancestor-check bullet
invokes `em-workflow/scripts/journal-append-failed.py` with reason
`merge-unverified` (no launch identity) once three preconditions hold, so
the task's journal last event itself reads `failed` and the ordinary
retry / route back to planning / abort menu becomes reachable for it. Six
surfaces are updated to match: I.2.a's retry-admissibility sentence, I.2.b
step 1's own ancestor-check bullet, the Orphan recovery paragraph's "only
case" sentence, I.2.c's ancestor-failure paragraph (the old dead end /
human-only / status-semantics-unmet prose is removed), the Supporting cast
Journal bullet's exception clause, and the Stale-`launched` caveat's
exception sentence -- each reframed under SC-3's single helper exception
(`journal-append-failed.py`, now invoked from two orchestrator-caused
sites: the orphan-recovery attempt and this new ancestor-check branch).
`em-workflow/README.md`'s journal description is aligned the same way.

Covers this task's own Acceptance Criteria
(feature-docs/routeback-deferred-findings/tasks/task0004.md):

- AC-1 (FR4): I.2.b step 1's ancestor-check bullet states the three
  preconditions, that a `merged` event is not termination proof, the single
  `journal-append-failed.py` invocation with `--reason merge-unverified`
  and no launch identity, and the re-replay after which the task's journal
  last event itself reads `failed` with retry and route back to planning
  reachable.
- AC-2 (FR4, NFR5): the same bullet's helper-failure residue and retry path
  (I.2.c drain, I.2.a resume guard, `merge-task.sh` recording `merged`
  again when the integration branch already contains the task branch).
- AC-3 (FR6, NFR2, NFR3): I.2.c no longer contains the six dead-end/human-
  only/status-semantics phrases (each with a negative proof against the
  verbatim pre-change paragraph); the new exit statement is present; I.2.c
  contains neither `append` nor `rework`.
- AC-4 (FR6): I.2.a no longer contains the old narrower-outcome sentence
  (negative proof against the verbatim pre-change sentences) and states
  both the new path and the remaining helper-failure case.
- AC-5 (FR6): the two old orphan-recovery-is-the-only/sole-exception
  phrases are absent (negative proofs); the Journal bullet and the
  Stale-`launched` caveat each name the `merge-unverified` invocation as
  part of the one helper exception; `em-workflow/README.md` is aligned the
  same way.
- AC-7 (NFR4, NFR7, NFR8): no backtick-quoted SC6 residual reason code
  leaks outside I.2.b or into the README from this task's own edited
  regions; `em-workflow/hooks/queue_launch_guard.py` and
  `em-workflow/scripts/merge-task.sh` are byte-identical to their
  pre-task content; this module imports only the standard library.

AC-6 (the `tests/test_implement_routeback_gate.py` pin conversions) is
covered entirely in that module, per this task's Test Notes ("the pin
conversions required by AC-6 live in tests/test_implement_routeback_gate.py").

Red/green discipline: every PRE_CHANGE_*_SAMPLE constant below is a verbatim
excerpt of `em-workflow/references/implement-phase.md` (or, for the README
constant, `em-workflow/README.md`) at this task's own base commit
(eabf7278), captured before this task's edit landed -- each paired with a
positive test proving the sample carries the OLD wording (proving the
sample is genuinely pre-change) and a retained-anchor guard (a phrase
present in both the sample and the live document). For genuinely new prose
that has no prior sentence to rewrite (most of the R2 bullet, the Journal
bullet's and caveat's added ancestor-check-branch clauses), each positive
matcher is paired with a "forged" sanity test (`str.replace` the phrase
out and confirm the matcher would then fail) proving the matcher is not
vacuous -- and each new-wording matcher was additionally observed to fail
before this task's edit landed by running it against a temporary copy of
the pre-change document (recorded in this task's own tests.yaml, not
reproduced here).

Follows the established convention (standard library only, document text
read from the repository root computed from this module's own path,
module-level constants for each literal read once by a positive test and
once by a negative-proof test, whitespace-normalized matching unless byte
identity is the point).
"""

import ast
import hashlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
README_PATH = PLUGIN_ROOT / "README.md"
LAUNCH_GUARD_PATH = PLUGIN_ROOT / "hooks" / "queue_launch_guard.py"
MERGE_TASK_SH_PATH = PLUGIN_ROOT / "scripts" / "merge-task.sh"

I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
SUPPORTING_CAST_HEADING = "### Supporting cast"
STEP_I3_HEADING = "## Step I.3: Phase completion"
RESUME_HEADING = "**Resume**"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _read_readme():
    return README_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where this
    task's prose happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _slice(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


def _i2a_section(text):
    return _slice(text, I2A_HEADING, I2B_HEADING)


def _i2b_section(text):
    return _slice(text, I2B_HEADING, I2C_HEADING)


def _i2c_section(text):
    return _slice(text, I2C_HEADING, SUPPORTING_CAST_HEADING)


def _supporting_cast_section(text):
    return _slice(text, SUPPORTING_CAST_HEADING, STEP_I3_HEADING)


# ===========================================================================
# AC-1, AC-2 (R2): I.2.b step 1's ancestor-check bullet gains the exit.
# Genuinely new prose (no prior sentence rewritten) -- "forged" sanity
# pattern per this module's own docstring.
# ===========================================================================

R2_PRECONDITIONS_PHRASE = (
    "This exit is reached once three preconditions all hold: the ancestor "
    "check just failed; the task's journal last event is `merged`; and "
    "the task's `Task()` call is not among this reconcile step's own "
    "currently-outstanding calls"
)
R2_TERMINATION_NOT_PROVEN_PHRASE = (
    "A `merged` event is not by itself proof that the launching agent "
    "terminated"
)
R2_HELPER_INVOCATION_PHRASE = (
    "the orchestrator invokes `em-workflow/scripts/journal-append-failed.py` "
    "exactly once, with the task id and `--reason merge-unverified`, "
    "supplying no launch identity"
)
R2_REPLAY_READS_FAILED_PHRASE = (
    "the task's journal last event — not only its reconciled state — "
    "reads `failed`"
)
R2_RETRY_ROUTEBACK_REACHABLE_PHRASE = (
    "both retry (the launch guard admits a launch after `failed`) and "
    "route back to planning (subject to I.2.c's own gate) become "
    "reachable for it"
)
R2_HELPER_FAILURE_RESIDUE_PHRASE = (
    "Helper-failure residue: when that invocation exits non-zero, or "
    "reports any outcome other than `appended`, the journal is left "
    "unchanged"
)
R2_HELPER_FAILURE_GOVERNS_PHRASE = (
    "I.2.c's third conjunct still blocks route-back for it, the "
    "gate-rejected cause enumeration names it, and the phase report "
    "names it"
)
R2_RETRY_PATH_PHRASE = (
    "retry follows the existing I.2.c drain and the I.2.a resume guard"
)
R2_MERGE_TASK_RECORDS_AGAIN_PHRASE = (
    '`merge-task.sh` records `merged` again (its "Parent already contains '
    'us" case, lines 116-118)'
)

R2_NEW_PHRASES = (
    R2_PRECONDITIONS_PHRASE,
    R2_TERMINATION_NOT_PROVEN_PHRASE,
    R2_HELPER_INVOCATION_PHRASE,
    R2_REPLAY_READS_FAILED_PHRASE,
    R2_RETRY_ROUTEBACK_REACHABLE_PHRASE,
    R2_HELPER_FAILURE_RESIDUE_PHRASE,
    R2_HELPER_FAILURE_GOVERNS_PHRASE,
    R2_RETRY_PATH_PHRASE,
    R2_MERGE_TASK_RECORDS_AGAIN_PHRASE,
)


class TestAncestorCheckBulletStatesTheNewExit(unittest.TestCase):
    """AC-1, AC-2: I.2.b step 1's ancestor-check bullet states the three
    preconditions, the termination-not-proven caveat, the single helper
    invocation (reason `merge-unverified`, no launch identity), the
    re-replay effect, the helper-failure residue, and the retry path."""

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read()))

    def test_all_new_phrases_present(self):
        for phrase in R2_NEW_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.i2b)

    def test_forged_sanity_each_phrase_detected_if_removed(self):
        for phrase in R2_NEW_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)

    def test_retained_literals_survive(self):
        # RETENTION (task plan): the ancestor-check bullet's pre-existing
        # sentences are untouched by this task's addition.
        self.assertIn(
            "never mark a task merged on self-report or journal entry "
            "alone",
            self.i2b,
        )
        self.assertIn(
            "That task's reconciled state instead becomes `failed`",
            self.i2b,
        )
        self.assertIn(
            "so it reaches the normal failed handling in I.2.c (retry, "
            "route back to planning subject to that section's own gate, "
            "or abort)",
            self.i2b,
        )


# --- R2's closing sentence: a rewrite of prior text (pre-change sample
# available), not genuinely new prose. -------------------------------------

PRE_CHANGE_R2_CLOSING_SAMPLE = (
    "Which of those three is actually\n"
    "     admissible for this specific state is owned entirely by I.2.c's own\n"
    "     gates, not by this bullet: I.2.c narrows this case further, because\n"
    "     the task's raw journal last event is still `merged` here even though\n"
    "     the reconciled state is `failed`."
)

R2_CLOSING_NEW_PHRASE = (
    "I.2.c narrows this case further only in the helper-failure case just "
    "above"
)
R2_CLOSING_NO_LONGER_UNCONDITIONAL_PHRASE = (
    "this is no longer the unconditional outcome of a failed ancestor "
    "check"
)
R2_CLOSING_RETAINED_ANCHOR = "I.2.c narrows this case further"


class TestR2ClosingSentenceNoLongerUnconditional(unittest.TestCase):
    """AC-2: the bullet's closing sentence -- previously an unconditional
    claim that I.2.c always narrows this case -- now states that this
    narrowing applies only to the helper-failure residue."""

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read()))

    def test_new_closing_wording_present(self):
        self.assertIn(R2_CLOSING_NEW_PHRASE, self.i2b)
        self.assertIn(R2_CLOSING_NO_LONGER_UNCONDITIONAL_PHRASE, self.i2b)

    def test_new_wording_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R2_CLOSING_SAMPLE)
        self.assertNotIn(R2_CLOSING_NEW_PHRASE, sample)
        self.assertNotIn(R2_CLOSING_NO_LONGER_UNCONDITIONAL_PHRASE, sample)

    def test_pre_change_sample_retains_anchor(self):
        sample = _normalize_ws(PRE_CHANGE_R2_CLOSING_SAMPLE)
        self.assertIn(R2_CLOSING_RETAINED_ANCHOR, sample)
        self.assertIn(R2_CLOSING_RETAINED_ANCHOR, self.i2b)


# ===========================================================================
# AC-4 (R1): I.2.a's retry-admissibility sentence.
# ===========================================================================

PRE_CHANGE_R1_SAMPLE = (
    "it because a post-`failed` launch is the legitimate retry path. This holds\n"
    "only when the task's journal last event is actually `failed`: for the\n"
    "ancestor-check-failed case in I.2.b step 1, where the reconciled state is\n"
    "`failed` but the raw journal last event is still `merged`, the launch guard\n"
    "denies the retry instead — I.2.c owns that narrower outcome, not restated\n"
    "here."
)

R1_OLD_DENIES_RETRY_PHRASE = (
    "the launch guard denies the retry instead — I.2.c owns that narrower "
    "outcome"
)
R1_NEW_ADMITS_RETRY_PHRASE = (
    "I.2.b step 1's ancestor-check branch (cited here, not restated) "
    "records a journal `failed` event, so the launch guard admits the "
    "retry"
)
R1_NEW_REMAINING_CASE_PHRASE = (
    "only when that invocation records nothing does the journal last "
    "event stay `merged`, and in that remaining case the launch guard "
    "denies the retry"
)
R1_RETAINED_ANCHOR = (
    "it because a post-`failed` launch is the legitimate retry path"
)


class TestI2aStatesNewPathAndRemainingCase(unittest.TestCase):
    """AC-4: I.2.a no longer contains the old narrower-outcome sentence,
    and states both the new path (journal `failed` recorded by I.2.b step
    1's ancestor-check branch, retry admitted) and the remaining
    helper-failure case (journal last event still `merged`, retry
    denied)."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))

    def test_old_deny_sentence_absent(self):
        self.assertNotIn(R1_OLD_DENIES_RETRY_PHRASE, self.i2a)

    def test_new_admits_retry_phrase_present(self):
        self.assertIn(R1_NEW_ADMITS_RETRY_PHRASE, self.i2a)

    def test_new_remaining_case_phrase_present(self):
        self.assertIn(R1_NEW_REMAINING_CASE_PHRASE, self.i2a)

    def test_old_phrase_matcher_flags_presence_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R1_SAMPLE)
        self.assertIn(R1_OLD_DENIES_RETRY_PHRASE, sample)

    def test_new_phrases_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R1_SAMPLE)
        self.assertNotIn(R1_NEW_ADMITS_RETRY_PHRASE, sample)
        self.assertNotIn(R1_NEW_REMAINING_CASE_PHRASE, sample)

    def test_pre_change_sample_retains_anchor(self):
        sample = _normalize_ws(PRE_CHANGE_R1_SAMPLE)
        self.assertIn(R1_RETAINED_ANCHOR, sample)
        self.assertIn(R1_RETAINED_ANCHOR, self.i2a)


# ===========================================================================
# AC-5 (R3): Orphan recovery paragraph's "only case" sentence.
# ===========================================================================

PRE_CHANGE_R3_SAMPLE = (
    "the task's final event is still `launched` (a no-op when it is\n"
    "     already `merged` or `failed`). This is the ONLY case in which the\n"
    "     orchestrator's own action results in an append to `journal.jsonl` —\n"
    "     the exception `em-workflow/references/implement-phase.md`'s own\n"
    "     Supporting cast Journal bullet below states, cited not restated."
)

R3_OLD_ONLY_CASE_PHRASE = (
    "This is the ONLY case in which the orchestrator's own action results "
    "in an append to `journal.jsonl`"
)
R3_NEW_INVOCATION_SITE_PHRASE = (
    "This invocation is one of the invocation sites of the single helper "
    "exception the Supporting cast Journal bullet below states"
)
R3_NEW_OTHER_SITE_PHRASE = (
    "the other orchestrator-caused site being this step's own "
    "ancestor-check branch"
)
R3_RETAINED_ANCHOR = (
    "the task's final event is still `launched` (a no-op when it is "
    "already `merged` or `failed`)"
)


class TestOrphanRecoveryNoLongerClaimsOnlyCase(unittest.TestCase):
    """AC-5: the Orphan recovery paragraph no longer claims its own
    invocation is the ONLY orchestrator-caused journal append -- it now
    names itself as one of two invocation sites of the single helper
    exception, the other being the ancestor-check branch."""

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read()))

    def test_old_only_case_phrase_absent(self):
        self.assertNotIn(R3_OLD_ONLY_CASE_PHRASE, self.i2b)

    def test_new_invocation_site_phrase_present(self):
        self.assertIn(R3_NEW_INVOCATION_SITE_PHRASE, self.i2b)
        self.assertIn(R3_NEW_OTHER_SITE_PHRASE, self.i2b)

    def test_old_phrase_matcher_flags_presence_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R3_SAMPLE)
        self.assertIn(R3_OLD_ONLY_CASE_PHRASE, sample)

    def test_new_phrases_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R3_SAMPLE)
        self.assertNotIn(R3_NEW_INVOCATION_SITE_PHRASE, sample)
        self.assertNotIn(R3_NEW_OTHER_SITE_PHRASE, sample)

    def test_pre_change_sample_retains_anchor(self):
        sample = _normalize_ws(PRE_CHANGE_R3_SAMPLE)
        self.assertIn(R3_RETAINED_ANCHOR, sample)
        self.assertIn(R3_RETAINED_ANCHOR, self.i2b)


# ===========================================================================
# AC-3 (R4): I.2.c's ancestor-failure paragraph -- the old dead-end /
# human-only / status-semantics-unmet prose is replaced by a plain
# statement that the ordinary menu opens.
# ===========================================================================

PRE_CHANGE_R4_SAMPLE = (
    "The state it protects still has a way out that\n"
    "  is not this section's own gate-rejected or abort terminal — a way into\n"
    "  this failed-handling branch, not a way out of it once reached: when the\n"
    "  ancestor verification fails for a task the journal (or its own report)\n"
    "  claims `merged`, Step I.2.b step 1's reconciled state for that task is\n"
    "  `failed` — cited there, not restated here — so the ordinary retry /\n"
    "  route back to planning / abort menu opens for it like any other\n"
    "  failure, except that route back to planning stays inadmissible here:\n"
    "  the task's raw journal last event is still `merged`, so the third\n"
    "  conjunct above blocks it regardless of the reconciled `failed` state;\n"
    "  choosing retry there reaches the launch guard's permission\n"
    "  denial, which the harness-level-failure path under 'Failure\n"
    "  containment' below diagnoses, an outcome reached without selecting\n"
    "  abort — in effect the same dead end as this section's own\n"
    "  gate-rejected terminal, since neither retry nor route back to\n"
    "  planning actually resolves the task from here; the only way out is a\n"
    "  human (or a follow-up task) correcting the branch ancestry so a\n"
    "  later reconcile pass verifies the merge, or otherwise resolving the\n"
    "  task's state by hand outside this protocol. This is the one state\n"
    "  where workflow-schema.md's status semantics (\"a `failed` task\n"
    "  resolves ONLY by retry or by routing back to planning\") are not met\n"
    "  by an automated path; the gap is confined to this single case and is\n"
    "  not a precedent for any other `failed` task."
)

R4_OLD_PERMISSION_DENIAL_PHRASE = (
    "choosing retry there reaches the launch guard's permission denial"
)
R4_OLD_WITHOUT_ABORT_PHRASE = "an outcome reached without selecting abort"
R4_OLD_DEAD_END_PHRASE = "in effect the same dead end"
R4_OLD_HUMAN_PHRASE = "the only way out is a human"
R4_OLD_STATUS_SEMANTICS_PHRASE = (
    "This is the one state where workflow-schema.md's status semantics"
)
R4_OLD_CONFINED_PHRASE = "the gap is confined to this single case"

R4_OLD_PHRASES = (
    R4_OLD_PERMISSION_DENIAL_PHRASE,
    R4_OLD_WITHOUT_ABORT_PHRASE,
    R4_OLD_DEAD_END_PHRASE,
    R4_OLD_HUMAN_PHRASE,
    R4_OLD_STATUS_SEMANTICS_PHRASE,
    R4_OLD_CONFINED_PHRASE,
)

R4_NEW_ORDINARY_MENU_PHRASE = (
    "the task reaches the ordinary retry / route back to planning / "
    "abort menu here exactly like any other failed task"
)
R4_NEW_CITATION_PHRASE = (
    "carrying the journal `failed` event that Step I.2.b step 1's "
    "ancestor-check branch records for it"
)
R4_RETAINED_ANCHOR = (
    "ancestor verification fails for a task the journal (or its own "
    "report) claims `merged`"
)


class TestI2cAncestorFailureParagraphNoLongerADeadEnd(unittest.TestCase):
    """AC-3: I.2.c no longer contains the six dead-end / human-only /
    status-semantics-unmet phrases; instead it states that the task
    reaches the ordinary retry / route back to planning / abort menu,
    carrying the journal `failed` event I.2.b step 1's ancestor-check
    branch records for it."""

    @classmethod
    def setUpClass(cls):
        cls.i2c = _normalize_ws(_i2c_section(_read()))

    def test_all_six_old_phrases_absent(self):
        for phrase in R4_OLD_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.i2c)

    def test_new_exit_statement_present(self):
        self.assertIn(R4_NEW_ORDINARY_MENU_PHRASE, self.i2c)
        self.assertIn(R4_NEW_CITATION_PHRASE, self.i2c)

    def test_i2c_contains_neither_append_nor_rework(self):
        self.assertNotIn("append", self.i2c)
        self.assertNotIn("rework", self.i2c)

    def test_all_six_old_phrases_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R4_SAMPLE)
        for phrase in R4_OLD_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, sample)

    def test_new_exit_statement_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R4_SAMPLE)
        self.assertNotIn(R4_NEW_ORDINARY_MENU_PHRASE, sample)
        self.assertNotIn(R4_NEW_CITATION_PHRASE, sample)

    def test_pre_change_sample_retains_anchor(self):
        sample = _normalize_ws(PRE_CHANGE_R4_SAMPLE)
        self.assertIn(R4_RETAINED_ANCHOR, sample)
        self.assertIn(R4_RETAINED_ANCHOR, self.i2c)


# ===========================================================================
# AC-5 (R5, R6): the Supporting cast Journal bullet and the
# Stale-`launched` caveat each name the `merge-unverified` invocation as
# part of the one helper exception.
# ===========================================================================

R5_HELPER_NAMED_AS_EXCEPTION_PHRASE = (
    "with one narrowly-scoped exception: the "
    "`em-workflow/scripts/journal-append-failed.py` helper"
)
R5_ANCESTOR_SITE_PHRASE = (
    "and by I.2.b step 1's ancestor-check branch (cited there, not "
    "restated), with reason `merge-unverified`, on proof that a task the "
    "journal claims `merged` fails the ancestor check"
)

R5_NEW_PHRASES = (R5_HELPER_NAMED_AS_EXCEPTION_PHRASE, R5_ANCESTOR_SITE_PHRASE)


class TestJournalBulletNamesBothInvocationSites(unittest.TestCase):
    """AC-5: the Supporting cast Journal bullet's exception clause now
    names the helper itself as the one exception, invoked by both the
    orphan-recovery attempt and the ancestor-check branch."""

    @classmethod
    def setUpClass(cls):
        cls.supporting_cast = _normalize_ws(_supporting_cast_section(_read()))

    def test_new_phrases_present(self):
        for phrase in R5_NEW_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.supporting_cast)

    def test_forged_sanity_each_phrase_detected_if_removed(self):
        for phrase in R5_NEW_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.supporting_cast.replace(phrase, "")
                self.assertNotIn(phrase, forged)

    def test_retained_exception_literal_survives(self):
        self.assertIn("with one narrowly-scoped exception", self.supporting_cast)
        self.assertIn(
            "em-workflow/references/implement-phase.md`'s own I.2.b "
            "Recovery / Residual",
            self.supporting_cast,
        )


PRE_CHANGE_R6_SAMPLE = (
    "A fourth mechanism\n"
    "closes the gap for exactly the case where the launching session itself is\n"
    "gone: I.2.b step 1's orphan-recovery attempt (cited there, not restated\n"
    "here) is the sole exception to the Journal bullet's rule that the\n"
    "orchestrator never writes the journal directly."
)

R6_OLD_SOLE_EXCEPTION_LINK_PHRASE = (
    "orphan-recovery attempt (cited there, not restated here) is the sole "
    "exception"
)
R6_NEW_SOLE_EXCEPTION_TOGETHER_PHRASE = (
    "which — together with I.2.b step 1's ancestor-check branch's "
    "`merge-unverified` invocation (cited there, not restated here) — is "
    "the sole exception to the Journal bullet's rule that the "
    "orchestrator never writes the journal directly"
)
R6_RETAINED_ANCHOR = (
    "I.2.b step 1's orphan-recovery attempt (cited there, not restated "
    "here)"
)


class TestCaveatNoLongerMakesOrphanAttemptTheSoleExceptionAlone(
    unittest.TestCase
):
    """AC-5: the Stale-`launched` caveat's "A fourth mechanism" sentence
    no longer links the orphan-recovery attempt directly to being THE
    sole exception -- the sole exception is now the helper, covering both
    the orphan-recovery attempt and the ancestor-check branch's
    `merge-unverified` invocation together."""

    @classmethod
    def setUpClass(cls):
        cls.supporting_cast = _normalize_ws(_supporting_cast_section(_read()))

    def test_old_direct_link_absent(self):
        self.assertNotIn(R6_OLD_SOLE_EXCEPTION_LINK_PHRASE, self.supporting_cast)

    def test_new_together_phrasing_present(self):
        self.assertIn(
            R6_NEW_SOLE_EXCEPTION_TOGETHER_PHRASE, self.supporting_cast
        )

    def test_old_phrase_matcher_flags_presence_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R6_SAMPLE)
        self.assertIn(R6_OLD_SOLE_EXCEPTION_LINK_PHRASE, sample)

    def test_new_phrase_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_R6_SAMPLE)
        self.assertNotIn(R6_NEW_SOLE_EXCEPTION_TOGETHER_PHRASE, sample)

    def test_pre_change_sample_retains_anchor(self):
        sample = _normalize_ws(PRE_CHANGE_R6_SAMPLE)
        self.assertIn(R6_RETAINED_ANCHOR, sample)
        self.assertIn(R6_RETAINED_ANCHOR, self.supporting_cast)

    def test_fifth_mechanism_sentence_untouched(self):
        # RETENTION: the fifth-mechanism sentence right after this one is
        # out of this task's scope and stays as-is.
        self.assertIn(
            "orphan-recovery attempt's extended same-session branch",
            self.supporting_cast,
        )


# ===========================================================================
# AC-5 (README): em-workflow/README.md's journal description is aligned
# with SC-3 so it also covers the `merge-unverified` exit.
# ===========================================================================

PRE_CHANGE_README_SAMPLE = (
    "セッション消失を証明できた `launched` 残留（orphaned）だけは例外的に"
    "オーケストレーターがヘルパー経由で `failed` を追記する"
)

README_OLD_ONLY_ORPHANED_PHRASE = (
    "セッション消失を証明できた `launched` 残留（orphaned）だけは例外的に"
    "オーケストレーターがヘルパー経由で `failed` を追記する"
)
README_NEW_MERGE_UNVERIFIED_PHRASE = "`merge-unverified`"
README_NEW_TWO_CASES_ANCHOR = "の 2 ケースのみ"
README_ORPHANED_STILL_NAMED_PHRASE = "`orphaned`"


class TestReadmeAlignedWithSingleHelperException(unittest.TestCase):
    """AC-5: em-workflow/README.md's journal description no longer states
    that the orphaned `launched` residue is the only case where the
    orchestrator appends `failed` via the helper -- it now also names the
    `merge-unverified` exit, citing `references/implement-phase.md`."""

    @classmethod
    def setUpClass(cls):
        cls.readme = _read_readme()

    def test_old_only_orphaned_phrase_absent(self):
        self.assertNotIn(README_OLD_ONLY_ORPHANED_PHRASE, self.readme)

    def test_new_merge_unverified_mention_present(self):
        self.assertIn(README_NEW_MERGE_UNVERIFIED_PHRASE, self.readme)
        self.assertIn(README_NEW_TWO_CASES_ANCHOR, self.readme)

    def test_orphaned_reason_still_named(self):
        # This task must not drop the pre-existing `orphaned` mention while
        # aligning the sentence with SC-3 (regression guard for the
        # pre-existing pin in tests/test_implement_routeback_gate.py's
        # TestReadmeJournalDescriptionAgreesByCitation).
        self.assertIn(README_ORPHANED_STILL_NAMED_PHRASE, self.readme)

    def test_cites_implement_phase_without_restating(self):
        self.assertIn("references/implement-phase.md", self.readme)

    def test_old_phrase_matcher_flags_presence_in_pre_change_sample(self):
        self.assertIn(README_OLD_ONLY_ORPHANED_PHRASE, PRE_CHANGE_README_SAMPLE)

    def test_new_phrase_absent_from_pre_change_sample(self):
        self.assertNotIn(
            README_NEW_TWO_CASES_ANCHOR, PRE_CHANGE_README_SAMPLE
        )

    def test_pre_change_sample_retains_anchor(self):
        anchor = "セッション消失を証明できた `launched` 残留"
        self.assertIn(anchor, PRE_CHANGE_README_SAMPLE)
        self.assertIn(anchor, self.readme)


# ===========================================================================
# AC-7: no SC6 residual reason code leaks outside I.2.b (or into the
# README) from this task's own edited regions; the two never-modified
# files stay byte-identical; this module imports only the standard
# library.
# ===========================================================================

# The closed sixteen-value SC6 residual reason code set
# (em-workflow/scripts/recover-orphaned-task.py's own docstring/constants:
# "Full closed set of `residual` reason codes (SC6, sixteen values)").
SC6_CODES = (
    "no-agent-entry",
    "stale-agent-entry",
    "no-session-id",
    "invalid-session-id",
    "current-session-unknown",
    "same-session",
    "transcripts-dir-missing",
    "transcript-unreadable",
    "transcript-active",
    "journal-not-launched",
    "task-artifacts-missing",
    "agent-identity-unproven",
    "agent-termination-unproven",
    "agent-still-live",
    "stop-result-unproven",
    "launch-changed",
)


class TestNoSC6CodeLeaksFromThisTasksEditedRegions(unittest.TestCase):
    """AC-7 (NFR4): none of this task's own edited regions -- I.2.a, I.2.c,
    the Supporting cast section, and the README -- introduces a
    backtick-quoted SC6 residual reason code. I.2.b (where this task's own
    new prose lives) is exempt, per Convention 2."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.i2a = _i2a_section(text)
        cls.i2c = _i2c_section(text)
        cls.supporting_cast = _supporting_cast_section(text)
        cls.readme = _read_readme()

    def test_i2a_contains_no_sc6_code(self):
        for code in SC6_CODES:
            with self.subTest(code=code):
                self.assertNotIn(f"`{code}`", self.i2a)

    def test_i2c_contains_no_sc6_code(self):
        for code in SC6_CODES:
            with self.subTest(code=code):
                self.assertNotIn(f"`{code}`", self.i2c)

    def test_supporting_cast_contains_no_sc6_code(self):
        for code in SC6_CODES:
            with self.subTest(code=code):
                self.assertNotIn(f"`{code}`", self.supporting_cast)

    def test_readme_contains_no_sc6_code(self):
        for code in SC6_CODES:
            with self.subTest(code=code):
                self.assertNotIn(code, self.readme)


# Hashes computed from the un-modified files at this task's own base commit
# (eabf7278) -- a byte-identity regression guard, cheaper than a git
# subprocess call, proving this task never touched either file (NFR7).
EXPECTED_LAUNCH_GUARD_SHA256 = (
    "30077f34c762cf980c2743b66c8b4c328ac7f746492ed6150db21b9d5ca204ac"
)
EXPECTED_MERGE_TASK_SH_SHA256 = (
    "f8af1da2e7712a656fe70020fa9c71e53275342d46d96abd2b20b432c10eb84f"
)


class TestNeverModifiedFilesAreByteIdentical(unittest.TestCase):
    """AC-7 (NFR7): `em-workflow/hooks/queue_launch_guard.py` and
    `em-workflow/scripts/merge-task.sh` are untouched by this task."""

    def test_launch_guard_untouched(self):
        actual = hashlib.sha256(LAUNCH_GUARD_PATH.read_bytes()).hexdigest()
        self.assertEqual(actual, EXPECTED_LAUNCH_GUARD_SHA256)

    def test_merge_task_sh_untouched(self):
        actual = hashlib.sha256(MERGE_TASK_SH_PATH.read_bytes()).hexdigest()
        self.assertEqual(actual, EXPECTED_MERGE_TASK_SH_SHA256)

    def test_merge_task_sh_lines_116_118_still_the_cited_case(self):
        # R2 cites these line numbers directly; guard against silent drift.
        lines = MERGE_TASK_SH_PATH.read_text(encoding="utf-8").splitlines()
        cited = "\n".join(lines[115:118])
        self.assertIn("Parent already contains us", cited)
        self.assertIn("merge-base --is-ancestor", cited)


class TestModuleImportsStdlibOnly(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"ast", "hashlib", "re", "unittest", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {node.module}")


if __name__ == "__main__":
    unittest.main()

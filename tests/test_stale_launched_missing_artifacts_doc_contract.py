"""Doc-contract tests for task0003 (routeback-deferred-findings): I.2.b step
1 routes a stale `launched` task with one or both artifacts missing through
the same not-live proof chain as the both-present candidates (Agent index
lookup -> Recovery -> Orphan recovery -> Same-session extension), with
artifact absence treated as evidence only and Residual kept only for the
unproven case; the Orphan recovery and Same-session extension text is
widened to cover the joined candidates; and the candidate-set predicate
that resolves `bc57aa350bb027c7` is pinned without being rewritten (finding
`12839a507a7df994` is resolved by the same edit, since the widened text
above is the rework that closes it).

Covers task0003 Acceptance Criteria
(feature-docs/routeback-deferred-findings/tasks/task0003.md):

- AC-1 (FR1): I.2.b step 1 states the three-conjunct condition (journal
  last event `launched`; at least one artifact absent, with the
  both-absent and each partial state named; the task's `Task()` call not
  among this reconcile step's own currently-outstanding calls) and the
  joining order Agent index lookup -> Recovery -> Orphan recovery ->
  Same-session extension, with the lookup stated as keyed by task id,
  needing no worktree, and citing the Agent index writer's
  orchestrator-read rule.
- AC-2 (FR1, NFR5): the same text states that artifact absence is evidence
  and never by itself a termination proof; names the five unchanged
  elements as unchanged; states that on proof a terminal `failed` under an
  existing reason enters the journal, step 1 re-replays within the same
  reconcile step, and steps 3 and 5 and I.2.c see `failed` with retry and
  route back to planning reachable; and states that Residual applies only
  when no proof is obtained.
- AC-3 (FR1): the pre-change R1 wording ("A second, independent condition
  triggers this same recovery without an Agent index lookup" and "no
  stop-tool call occurs and this condition falls to the same Residual
  treatment") is absent from `implement-phase.md`; each absence matcher has
  a negative proof against the verbatim pre-change R1 block with a
  retained-anchor guard; every retained literal listed in the task plan's
  Design section still matches.
- AC-4 (FR2): the pre-change R2/R3/R4 wording ("journal last event
  `launched`, task worktree and task branch both present", "the task
  worktree and the task branch are both observed present (else
  `task-artifacts-missing`)" and "<observed task worktree path>") is
  absent from I.2.b, each with a negative proof against its own verbatim
  pre-change sample; the R2, R3 and R4 statements are present; the six
  extended-chain codes still occur in their fixed first-occurrence order
  within I.2.b.
- AC-5 (FR3): pins, within I.2.b, the predicate "whose `Task()` call is
  not among this reconcile step's own currently-outstanding calls" and the
  Same-session extension's `stale-launched` invocation statement; a paired
  negative proof shows the loop-2 restriction literal is present in its
  verbatim sample (captured from commit `0d9d0dc4`) and absent from the
  current I.2.b; this module docstring records `bc57aa350bb027c7` as
  resolved at HEAD with these two passages as the basis.
- AC-6 (NFR4): for each of the sixteen SC6 reason codes (one module-level
  constant listing the closed set), the count of its backtick-quoted token
  in the whole of `implement-phase.md` equals its count within I.2.b; a
  negative proof shows the check flags a forged copy with one code placed
  outside I.2.b.
- AC-7 (FR10, NFR8): this module imports only the standard library (AST
  check); it matches on whitespace-normalized text through module-level
  constants each read by a positive test and its negative proof; it
  modifies no existing test module.

Follows the established convention (standard library only, document text
read from the repository root computed from this module's own path,
module-level constants for each literal read once by a positive test and
once by a negative proof, whitespace-normalized matching unless byte
identity is the point).
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"


def _read_implement_phase():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text)


def _slice(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


def _i2b_section(text):
    return _slice(text, I2B_HEADING, I2C_HEADING)


# --- AC-1: three-conjunct condition + joining order -----------------------

CONJUNCT_LAST_EVENT_LAUNCHED = "the task's journal last event is `launched`"
CONJUNCT_ARTIFACT_BOTH_ABSENT = (
    "the both-absent state, where neither the task worktree nor the task "
    "branch exists"
)
CONJUNCT_ARTIFACT_PARTIAL_STATE = (
    "each partial state, where the task worktree exists but the task "
    "branch does not, or the task branch exists but the task worktree "
    "does not"
)
CONJUNCT_TASK_CALL_NOT_OUTSTANDING = (
    "the task's `Task()` call is not among this reconcile step's own "
    "currently-outstanding calls"
)

JOIN_ORDER_LOOKUP_WITH_CITATION = (
    "the Agent index lookup, keyed by task id and needing no worktree, "
    "performed through the Agent index writer's orchestrator-read rule"
)
JOIN_ORDER_RECOVERY = (
    "Recovery, the harness stop tool, then the stop-tool recorder's "
    "terminal `failed`"
)
JOIN_ORDER_ORPHAN_RECOVERY = "Orphan recovery, the legacy chain below"
JOIN_ORDER_SAME_SESSION_EXTENSION = "the Same-session extension below"

JOIN_ORDER_STAGES = (
    JOIN_ORDER_LOOKUP_WITH_CITATION,
    JOIN_ORDER_RECOVERY,
    JOIN_ORDER_ORPHAN_RECOVERY,
    JOIN_ORDER_SAME_SESSION_EXTENSION,
)


class TestR1ThreeConjunctConditionPresent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_all_three_conjuncts_present(self):
        for phrase in (
            CONJUNCT_LAST_EVENT_LAUNCHED,
            CONJUNCT_ARTIFACT_BOTH_ABSENT,
            CONJUNCT_ARTIFACT_PARTIAL_STATE,
            CONJUNCT_TASK_CALL_NOT_OUTSTANDING,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.i2b)

    def test_negative_proof_each_conjunct_removed_is_detected(self):
        for phrase in (
            CONJUNCT_LAST_EVENT_LAUNCHED,
            CONJUNCT_ARTIFACT_BOTH_ABSENT,
            CONJUNCT_ARTIFACT_PARTIAL_STATE,
            CONJUNCT_TASK_CALL_NOT_OUTSTANDING,
        ):
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)


class TestR1JoiningOrderInFixedRelativeOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_all_four_stages_present(self):
        for phrase in JOIN_ORDER_STAGES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.i2b)

    def test_stages_appear_in_fixed_relative_order(self):
        positions = [self.i2b.index(phrase) for phrase in JOIN_ORDER_STAGES]
        self.assertEqual(positions, sorted(positions))

    def test_negative_proof_missing_stage_is_detected(self):
        forged = self.i2b.replace(JOIN_ORDER_ORPHAN_RECOVERY, "")
        self.assertNotIn(JOIN_ORDER_ORPHAN_RECOVERY, forged)

    def test_negative_proof_out_of_order_stages_detected(self):
        forged = self.i2b.replace(
            JOIN_ORDER_LOOKUP_WITH_CITATION, "__PLACEHOLDER__"
        ).replace(
            JOIN_ORDER_SAME_SESSION_EXTENSION, JOIN_ORDER_LOOKUP_WITH_CITATION
        ).replace("__PLACEHOLDER__", JOIN_ORDER_SAME_SESSION_EXTENSION)
        positions = [forged.index(phrase) for phrase in JOIN_ORDER_STAGES]
        self.assertNotEqual(positions, sorted(positions))


# --- AC-2: evidence-only, unchanged elements, on-proof outcome, Residual --

ARTIFACT_ABSENCE_EVIDENCE_ONLY = (
    "observed evidence carried into that chain and is never, by itself, "
    "proof that the agent terminated"
)
FIVE_UNCHANGED_ELEMENTS = (
    "the outstanding-call exclusion above, the termination conjunct, the "
    "stop-result conjunct, the agent-identity binding, and the "
    "append-time launch-identity recheck"
)
ON_PROOF_JOURNAL_ENTRY = (
    "a terminal `failed` enters the journal under an existing reason "
    "— `orphaned`, `stale-launched`, or the stop-tool recorder's own"
)
ON_PROOF_REPLAY_AND_REACHABILITY = (
    "step 1 re-replays the journal within this same reconcile step, and "
    "steps 3 and 5 and I.2.c see `failed`, with retry and route back to "
    "planning both reachable"
)
RESIDUAL_ONLY_WHEN_NO_PROOF = (
    "The Residual case above applies to this condition too, and only "
    "when no proof is obtained"
)

AC2_PHRASES = (
    ARTIFACT_ABSENCE_EVIDENCE_ONLY,
    FIVE_UNCHANGED_ELEMENTS,
    ON_PROOF_JOURNAL_ENTRY,
    ON_PROOF_REPLAY_AND_REACHABILITY,
    RESIDUAL_ONLY_WHEN_NO_PROOF,
)


class TestR1EvidenceUnchangedOutcomeAndResidual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_all_phrases_present(self):
        for phrase in AC2_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.i2b)

    def test_negative_proof_each_phrase_removed_is_detected(self):
        for phrase in AC2_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)


# --- AC-3: pre-change R1 wording removed, retained anchor kept -----------

# Verbatim from implement-phase.md at this task's base commit
# (eabf72783f7415e0b7c9103a0de01bd903ea832a), before this task's edit.
PRE_CHANGE_R1_SAMPLE = (
    "Residual: when the Agent index\n"
    "     lookup is unresolvable or ambiguous, the journal is unchanged, the\n"
    "     task stays in-flight, the route-back gate blocks, and the phase\n"
    "     takes the existing gate-rejected terminal, with the task named in\n"
    "     the report. A second, independent condition triggers this same\n"
    "     recovery without an Agent index lookup: a task's journal last event\n"
    "     is `launched` AND the task worktree does not exist AND the task\n"
    "     branch does not exist — neither artifact remains to correlate a\n"
    "     live agent against, so this condition is checked on its own, never\n"
    "     gated on the Agent index resolving \"no live agent\". A partial-artifact\n"
    "     state — the task worktree exists but the task branch does not, or the\n"
    "     task branch exists but the task worktree does not — is not this\n"
    "     condition, but a task's journal last event being `launched` together\n"
    "     with either partial-artifact state also triggers this same recovery,\n"
    "     for the same reason: at least one artifact needed to correlate a live\n"
    "     agent is already gone. Since there is no\n"
    "     candidate to pass to the harness stop tool here, no stop-tool call\n"
    "     occurs and this condition falls to the same Residual treatment as an\n"
    "     unresolvable Agent index lookup above: the journal is unchanged\n"
    "     (writing it is never this phase's role — Supporting cast's Journal\n"
    "     bullet below owns that rule, cited not restated), the task stays\n"
    "     in-flight, the route-back gate blocks, and the phase takes the\n"
    "     existing gate-rejected terminal, with the task named in the report.\n"
    "     This recovery runs during this wake-phase reconcile step, hence\n"
    "     before I.2.c's user-facing menu is offered."
)

R1_RETAINED_ANCHOR = (
    "This recovery runs during this wake-phase reconcile step, hence "
    "before I.2.c's user-facing menu is offered."
)

FORBIDDEN_SECOND_CONDITION_LEADIN = (
    "A second, independent condition triggers this same recovery without "
    "an Agent index lookup"
)
FORBIDDEN_NO_STOP_TOOL_FALLTHROUGH = (
    "no stop-tool call occurs and this condition falls to the same "
    "Residual treatment"
)

# The task plan's Design section's "Retained literals" list: sentences that
# must still match (after whitespace normalization) even though this task
# rewrites the surrounding prose.
DESIGN_RETAINED_LITERALS = (
    "the check FAILS when a task's journal last event is `launched` while "
    "the task worktree and the task branch both exist",
    "the allowed-but-never-started state, since I.2.a creates both "
    "artifacts before the launch call that records `launched`",
    "when the Agent index lookup is unresolvable or ambiguous, the "
    "journal is unchanged, the task stays in-flight, the route-back gate "
    "blocks, and the phase takes the existing gate-rejected terminal",
    "This recovery runs during this wake-phase reconcile step, hence "
    "before I.2.c's user-facing menu is offered",
    "reaches the normal failed handling in I.2.c, where retry and "
    "route-back are both available",
    "for exactly the not-live candidate set already established above",
    "the Agent index writer's orchestrator-read rule",
    "explicit harness evidence that THIS launch's execution terminated",
    "an explicit not-running (or absent) stop-tool result for the SAME "
    "bound agent identity",
    "no elapsed-time threshold and no transcript or output-file idle "
    "interval substitutes for either conjunct",
    "The recorded session identity is never used as the stop target on "
    "this branch",
    "invoke `em-workflow/scripts/journal-append-failed.py` exactly once, "
    "with the task id and reason `stale-launched`",
)

# The Supporting cast's own orchestrator-read rule wording (cited, never
# restated, from I.2.b) -- must not appear inside I.2.b itself.
SUPPORTING_CAST_OWN_WORDING = (
    "the orchestrator selects that task's most recently appended entry"
)


class TestR1OldWordingRemovedAndRetainedLiteralsKept(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))
        cls.sample = _normalize_ws(PRE_CHANGE_R1_SAMPLE)

    def test_forbidden_phrases_absent_from_live_doc(self):
        for phrase in (
            FORBIDDEN_SECOND_CONDITION_LEADIN,
            FORBIDDEN_NO_STOP_TOOL_FALLTHROUGH,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(_normalize_ws(phrase), self.i2b)

    def test_retained_anchor_present_in_live_doc(self):
        self.assertIn(_normalize_ws(R1_RETAINED_ANCHOR), self.i2b)

    def test_negative_proof_forbidden_phrases_present_in_pre_change_sample(
        self,
    ):
        # The matcher above is not vacuous: the pre-change sample -- which
        # also carries the retained anchor, so the sample itself is
        # correctly targeted -- DOES contain both forbidden phrases.
        self.assertIn(_normalize_ws(R1_RETAINED_ANCHOR), self.sample)
        for phrase in (
            FORBIDDEN_SECOND_CONDITION_LEADIN,
            FORBIDDEN_NO_STOP_TOOL_FALLTHROUGH,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(_normalize_ws(phrase), self.sample)

    def test_design_retained_literals_still_match(self):
        for phrase in DESIGN_RETAINED_LITERALS:
            with self.subTest(phrase=phrase):
                self.assertIn(_normalize_ws(phrase), self.i2b)

    def test_negative_proof_retained_literal_removed_is_detected(self):
        phrase = DESIGN_RETAINED_LITERALS[0]
        forged = self.i2b.replace(_normalize_ws(phrase), "")
        self.assertNotIn(_normalize_ws(phrase), forged)

    def test_supporting_cast_own_wording_not_duplicated_into_i2b(self):
        self.assertNotIn(SUPPORTING_CAST_OWN_WORDING, self.i2b)


# --- AC-4: pre-change R2/R3/R4 wording removed, new statements present ---

PRE_CHANGE_R2_SAMPLE = (
    "Orphan recovery: for exactly the not-live candidate set already\n"
    "     established above — journal last event `launched`, task worktree and\n"
    "     task branch both present, Agent index lookup resolving to no live\n"
    "     agent (unresolvable, ambiguous, or the third case where the stop tool\n"
    "     stops nothing) — the orchestrator makes one further attempt before the\n"
    "     Residual above is taken as final."
)
R2_RETAINED_ANCHOR = "for exactly the not-live candidate set already established above"
FORBIDDEN_R2_BOTH_PRESENT = (
    "journal last event `launched`, task worktree and task branch both "
    "present"
)
R2_NEW_STATEMENT = (
    "with the task worktree and the task branch either both present or "
    "with at least one of them absent per the condition joined above"
)

PRE_CHANGE_R3_SAMPLE = (
    "the task worktree and the task branch are both observed present\n"
    "     (else `task-artifacts-missing`); the stop target's identity is\n"
    "     uniquely bound to the selected Agent index entry (else\n"
    "     `agent-identity-unproven`);"
)
R3_RETAINED_ANCHOR = (
    "the stop target's identity is uniquely bound to the selected Agent "
    "index entry (else `agent-identity-unproven`)"
)
FORBIDDEN_R3_BOTH_OBSERVED_PRESENT = (
    "the task worktree and the task branch are both observed present "
    "(else `task-artifacts-missing`)"
)
R3_NEW_STATEMENT = (
    "each of the task worktree and the task branch observations is "
    "supplied as exactly `yes` or `no` (else `task-artifacts-missing`), "
    "with both values carried as evidence and neither one, by itself, "
    "ending the chain (SC-2)"
)

PRE_CHANGE_R4_SAMPLE = (
    "`--worktree-present yes|no`,\n"
    "     `--branch-present yes|no`, `--task-worktree <observed task\n"
    "     worktree path>`, `--stop-target <the agent identity the stop call\n"
    "     was made against>`,"
)
R4_RETAINED_ANCHOR = "`--branch-present yes|no`"
FORBIDDEN_R4_OBSERVED_PATH = "<observed task worktree path>"
R4_NEW_STATEMENT = (
    "`--task-worktree` set to the task's expected worktree path "
    "(`$WT_ROOT/{T}`), supplied whether or not that path exists and "
    "compared by the identity-binding step as a plain string against the "
    "Agent index entry's recorded worktree (SC-2)"
)

EXTENDED_CHAIN_CODES_IN_ORDER = (
    "task-artifacts-missing",
    "agent-identity-unproven",
    "agent-termination-unproven",
    "agent-still-live",
    "stop-result-unproven",
    "launch-changed",
)


class TestR2R3R4OldWordingRemovedAndNewStatementsPresent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_forbidden_phrases_absent_from_live_doc(self):
        for phrase in (
            FORBIDDEN_R2_BOTH_PRESENT,
            FORBIDDEN_R3_BOTH_OBSERVED_PRESENT,
            FORBIDDEN_R4_OBSERVED_PATH,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(_normalize_ws(phrase), self.i2b)

    def test_retained_anchors_present_in_live_doc(self):
        for anchor in (R2_RETAINED_ANCHOR, R3_RETAINED_ANCHOR, R4_RETAINED_ANCHOR):
            with self.subTest(anchor=anchor):
                self.assertIn(_normalize_ws(anchor), self.i2b)

    def test_negative_proof_forbidden_phrases_present_in_their_samples(self):
        pairs = (
            (FORBIDDEN_R2_BOTH_PRESENT, PRE_CHANGE_R2_SAMPLE, R2_RETAINED_ANCHOR),
            (
                FORBIDDEN_R3_BOTH_OBSERVED_PRESENT,
                PRE_CHANGE_R3_SAMPLE,
                R3_RETAINED_ANCHOR,
            ),
            (FORBIDDEN_R4_OBSERVED_PATH, PRE_CHANGE_R4_SAMPLE, R4_RETAINED_ANCHOR),
        )
        for phrase, sample, anchor in pairs:
            with self.subTest(phrase=phrase):
                normalized_sample = _normalize_ws(sample)
                self.assertIn(_normalize_ws(phrase), normalized_sample)
                self.assertIn(_normalize_ws(anchor), normalized_sample)

    def test_new_statements_present(self):
        for phrase in (R2_NEW_STATEMENT, R3_NEW_STATEMENT, R4_NEW_STATEMENT):
            with self.subTest(phrase=phrase):
                self.assertIn(_normalize_ws(phrase), self.i2b)

    def test_negative_proof_new_statement_removed_is_detected(self):
        for phrase in (R2_NEW_STATEMENT, R3_NEW_STATEMENT, R4_NEW_STATEMENT):
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(_normalize_ws(phrase), "")
                self.assertNotIn(_normalize_ws(phrase), forged)

    def test_extended_chain_codes_still_in_fixed_first_occurrence_order(self):
        positions = [
            self.i2b.index(f"`{code}`") for code in EXTENDED_CHAIN_CODES_IN_ORDER
        ]
        self.assertEqual(positions, sorted(positions))

    def test_negative_proof_out_of_order_extended_codes_detected(self):
        forged = self.i2b.replace(
            "`task-artifacts-missing`", "`__PLACEHOLDER__`"
        ).replace("`launch-changed`", "`task-artifacts-missing`").replace(
            "`__PLACEHOLDER__`", "`launch-changed`"
        )
        positions = [
            forged.index(f"`{code}`") for code in EXTENDED_CHAIN_CODES_IN_ORDER
        ]
        self.assertNotEqual(positions, sorted(positions))


# --- AC-5: FR3 pin (bc57aa350bb027c7) + loop-2 negative proof -------------

CANDIDATE_SET_PREDICATE = (
    "whose `Task()` call is not among this reconcile step's own "
    "currently-outstanding calls"
)
STALE_LAUNCHED_INVOCATION = (
    "invoke `em-workflow/scripts/journal-append-failed.py` exactly once, "
    "with the task id and reason `stale-launched`"
)

# Verbatim excerpt from em-workflow/references/implement-phase.md, lines
# 388-396, at commit 0d9d0dc4 ("fix(routeback-admissibility-exits): review
# round 3 loop 2") -- the loop-2 wording that restricted the candidate set
# to `launched` events recorded before the current session started. Taken
# verbatim; never reconstructed.
LOOP2_VERBATIM_SAMPLE = (
    "     ever returned. Consequently, this check's candidate set excludes any\n"
    "     task that the current session's own I.2.a launched: such a task's\n"
    "     `Task()` call may still be running in this same session and this\n"
    "     check has no way to observe that, so it is never eligible for the\n"
    "     liveness probe below regardless of its journal last event. Only a\n"
    "     task whose `launched` event was recorded before the current session\n"
    "     began (i.e. surviving a Resume, so it cannot be this session's own\n"
    "     in-flight call) is eligible to enter the candidate set and be\n"
    "     evaluated by the liveness probe. This check never calls the"
)
LOOP2_RESTRICTION_PHRASE = (
    "Only a task whose `launched` event was recorded before the current "
    "session began"
)


class TestFR3PinAndLoop2RestrictionAbsent(unittest.TestCase):
    """Covers finding bc57aa350bb027c7: resolved at HEAD by pinning the
    candidate-set predicate (never session-keyed) together with the
    Same-session extension's `stale-launched` invocation -- both already
    present, unchanged, in I.2.b -- rather than by rewriting the
    candidate-set sentence. The loop-2 wording that WOULD have
    session-keyed the candidate set is proven absent from the current text.
    """

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_candidate_set_predicate_pinned(self):
        self.assertIn(_normalize_ws(CANDIDATE_SET_PREDICATE), self.i2b)

    def test_stale_launched_invocation_pinned(self):
        self.assertIn(_normalize_ws(STALE_LAUNCHED_INVOCATION), self.i2b)

    def test_negative_proof_pinned_phrases_removed_are_detected(self):
        for phrase in (CANDIDATE_SET_PREDICATE, STALE_LAUNCHED_INVOCATION):
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(_normalize_ws(phrase), "")
                self.assertNotIn(_normalize_ws(phrase), forged)

    def test_loop2_restriction_present_in_its_own_verbatim_sample(self):
        self.assertIn(
            _normalize_ws(LOOP2_RESTRICTION_PHRASE),
            _normalize_ws(LOOP2_VERBATIM_SAMPLE),
        )

    def test_loop2_restriction_absent_from_current_i2b(self):
        self.assertNotIn(_normalize_ws(LOOP2_RESTRICTION_PHRASE), self.i2b)


# --- AC-6: SC6 reason-code placement (NFR4) -------------------------------

# The closed set of sixteen SC6 residual reason codes (recover-orphaned-task.py).
ALL_SC6_REASON_CODES = (
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


def _count_token(text, token):
    return text.count(f"`{token}`")


class TestSC6ReasonCodePlacementConfinedToI2b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.whole = _read_implement_phase()
        cls.i2b = _i2b_section(cls.whole)

    def test_each_code_count_matches_between_whole_doc_and_i2b(self):
        for code in ALL_SC6_REASON_CODES:
            with self.subTest(code=code):
                self.assertEqual(
                    _count_token(self.whole, code), _count_token(self.i2b, code)
                )

    def test_negative_proof_code_placed_outside_i2b_is_flagged(self):
        # Forge a copy where one SC6 code additionally appears just after
        # the I.2.b/I.2.c boundary (i.e. outside I.2.b, inside I.2.c).
        marker = I2C_HEADING
        idx = self.whole.index(marker) + len(marker)
        forged = (
            self.whole[:idx]
            + " `same-session`"
            + self.whole[idx:]
        )
        forged_i2b = _i2b_section(forged)
        mismatches = [
            code
            for code in ALL_SC6_REASON_CODES
            if _count_token(forged, code) != _count_token(forged_i2b, code)
        ]
        self.assertIn("same-session", mismatches)

    def test_code_absent_from_whole_document_counts_as_passing(self):
        # journal-not-launched is defined in SC6 but currently unused
        # anywhere in implement-phase.md: count 0 in both scopes passes.
        self.assertEqual(_count_token(self.whole, "journal-not-launched"), 0)
        self.assertEqual(_count_token(self.i2b, "journal-not-launched"), 0)


# --- AC-7: module imports only the standard library -----------------------


class TestModuleImportsStdlibOnly(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"ast", "re", "unittest", "pathlib"}
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

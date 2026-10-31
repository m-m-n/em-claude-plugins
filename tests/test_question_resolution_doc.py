"""Structural assertions for em-workflow/references/question-resolution.md.

Pre-existing coverage (kept passing per this task's Test Notes, not tied to
this task's own acceptance criteria):
- deduplication rules in order, the priority sort, `depends_on` deferral,
  and the presentation limits.
- the batch resolution sequence, including that a missing option ID is a
  protocol error and label matching may not substitute for it.
- the Codex consultation procedure's substance (availability probe, wrapper
  invocation, one turn per call, trajectory judgement, turn ceiling, who
  decides, untrusted-output rule) and the fail-closed classification's
  content (category values, explicit gate list, irreversible-assumption
  signal, cross-check reference, intentional behaviour-change note).

Batch classification gate (this task's own acceptance criteria — see
task0004's AC-1): the fail-closed classification's four abort arms become
three abort arms (`security`, `license`, `reversible: false`) plus one
routed arm (`spec-change` / `rework.spec-change`, routed to the
Classification gate in batch; asked directly in interactive). The retention
pins below assert the three unchanged abort arms individually, plus the
"regardless of ..." clauses that make them non-overridable, and the
four-category sentence pin is replaced with a three-category-plus-routed
pin of the same specificity (C5). The Classification gate section itself is
pinned in `tests/test_classification_gate.py`.

task0022 acceptance criteria (round2.yaml findings bs2, bs3, bs6, bs8 —
correcting round1's "presenter" criterion to gate-identifier presence):

- AC-1: the document states the jurisdiction as gate-identifier presence
  (a `gate_id` resolves the same way whether packet-borne or
  orchestrator-opened), not as "packet vs non-packet by presenter".
- AC-3: the Batch resolution sequence's entry condition covers an
  orchestrator-opened gate (no worker packet) and states how an answer is
  formed in that case (`packet_id` null, direct action instead of
  re-dispatch).
- AC-4 (bs2): the fail-closed classification is hoisted into its own
  section, appearing before ANY policy lookup — so it applies to a listed
  `gate_id` exactly as it applies to an unlisted one — and the
  Unlisted-gate fallback references it rather than restating it.
- AC-6 (bs6): the Codex consultation carries a bound independent of
  question count (packet-level batching, not one consultation per
  question), and the re-sent history is capped/summarized rather than
  growing every turn.
- AC-7 (bs8): no feature-docs task identifier (`task00NN`) is cited as the
  attribution for the category/on_unanswered cross-check; the citation
  instead points at `references/question-packet-schema.md`, which states
  the constraint AND names the enforcing script itself (a second,
  independent assertion below covers question-packet-schema.md's own
  text, since AC-7 spans both documents).

task0019 acceptance criteria (round2 findings 87ae09bcfe6410c0,
61c73dc71f323f45 -- confidence 95: the gate's routing and its origin check
both consumed values the worker under scrutiny supplied):

- AC-1: the routed arm's entry condition is stated as the question's
  `gate_id` being `rework.spec-change`, and the section states that the
  worker-set `category` never selects a route.
- AC-2: a packet whose `gate_id` is `rework.spec-change` but whose
  `category` is not `spec-change` is stated to abort as malformed -- it
  reaches neither the routed arm nor the unlisted-gate fallback.
- AC-3: irreversibility is decided from orchestrator-held metadata about
  the operation, and a packet's `reversible: false` still aborts in
  addition; omitting the assumption cannot remove the abort.
- AC-4 (retention): the three immediate-abort conditions and the
  precedence reservation survive unchanged (asserted individually by the
  pre-existing retention tests above; this task adds one consolidated
  confirmation).
- AC-9 (NFR3, partial): the new malformed-pairing and orchestrator-held
  irreversibility stops each state that their reason is recorded. (The
  origin-verification half of AC-9 is pinned in
  tests/test_classification_gate.py, alongside the section it belongs to.)

The Classification gate's own step 3 (origin verification) rewrite --
AC-5 through AC-7 -- is pinned in tests/test_classification_gate.py, per
C4's one-module-per-section convention; question-packet-schema.md's
evidence-carried origin identifier field (renamed `origin_id` by
rework-contract-drift/task0004, AC-7's schema half) is pinned in
tests/test_worker_contract_docs.py, alongside that document's other field
pins.

task0025 acceptance criteria (feature-docs/goal-vs-spec-divergence review
round3 rework, AC-1 half): the routed arm's exit sentence at Batch
resolution sequence step 2 no longer ends the question's story in place
("the gate's own proceed/stop outcome and its audit record are the
resolution for that question") -- it now points at the Classification
gate's own Outcome step (pinned in tests/test_classification_gate.py,
alongside the section it belongs to, per C4). The pins below cover only
the citation change at step 2 and the NFR1 non-duplication guard (the
packet/answer-model rule the Outcome step states must not be restated a
second time anywhere else in this document, including the Batch resolution
sequence itself).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)
SCHEMA_DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-packet-schema.md"
)


# ---------------------------------------------------------------------------
# codex-consult-output-scratchpad (task0001): the saved-output placement rule
# in step 2 ("Wrapper invocation") of the Codex consultation procedure.
#
# The matchers below are plain predicates over a text argument, so the real
# assertion and its negative twin (the pre-fix step 2 text) run the identical
# check. Every phrase match runs on the whitespace-collapsed rendering of the
# region, so Markdown line-wrapping never affects the result.
# ---------------------------------------------------------------------------

STEP2_START_MARKER = "2. **Wrapper invocation.**"
STEP2_END_MARKER = "3. **One turn per call.**"

# The phrases the rule is pinned by (compared on collapsed whitespace).
SAVED_OUTPUT_CONDITION_PHRASE = (
    "When the output of a `run_codex_exec.sh` call (stdout or stderr) is "
    "saved to a file"
)
SCRATCHPAD_PLACEMENT_PHRASE = (
    "that file is placed in the session scratchpad directory"
)
PROJECT_ROOT_PROHIBITION_PHRASE = "never written under `{project_root}`"
CWD_RELATIVE_PROHIBITION_PHRASE = (
    "the redirect target is never a path relative to the current directory"
)
BOTH_HARNESS_ENTRIES_PHRASE = (
    "on either harness entry, including the turns after a "
    "mid-consultation move from `codex` to `litellm`"
)
TIMEOUT_SENTENCE = (
    "Run this Bash tool call with a timeout of 600000 milliseconds."
)

# The step 2 invocation line and its `--litellm` values, which the rule must
# never disturb (retention pin).
INVOCATION_LINE = (
    '`"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly '
    '-C "{project_root}" "$PROMPT"`'
)
LITELLM_CONTRIBUTOR_VALUE = "`--litellm muse-spark-contributor`"
LITELLM_PLAIN_VALUE = "`--litellm muse-spark`"

# Pre-fix step 2 text, copied from the base revision (the revision before the
# saved-output rule existed), including the head of step 3 so the region
# extractor sees both markers. This literal is the negative twin's input; it
# is deliberately NOT read from the edited document, so that the twin keeps
# representing the bug after the fix.
PRE_FIX_STEP2_TEXT = """\
2. **Wrapper invocation.** Each turn calls the wrapper directly — never a
   Task-dispatched agent — in read-only mode with the project root, on the
   entry step 1 selected:
   `"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C "{project_root}" "$PROMPT"`,
   and for the `litellm` entry the same call with a `--litellm` flag
   inserted before `-C`, chosen by the `contributor_consented` value step 1
   fixed for this consultation: `--litellm muse-spark-contributor` when it
   is true, which the wrapper expands to
   `-p litellm -m muse-spark-contributor`, and `--litellm muse-spark` when
   it is false, which the wrapper expands to `-p litellm -m muse-spark`.
   Run this Bash tool call with a timeout of 600000 milliseconds.
   A turn whose wrapper call exits non-zero — including the wrapper's own
   exit 124 (`CODEX_TIMEOUT`) — moves the consultation to the NEXT
   available entry of the chain and continues it there. That advance is
   decided on the exit code alone: the reply is never inspected to
   classify why the launch failed, matching the wrapper's own contract
   that nothing about a launch's output shapes what happens next. Turns
   already spent still count against the ceiling below. A non-zero exit on
   the last available entry ends the consultation, and whatever is still
   unmapped goes to the Opus escalation exactly as the ceiling case does.
3. **One turn per call.** The wrapper holds no conversation state across
   invocations — each call is a single request/response.
"""


def _collapse_ws(text):
    return re.sub(r"\s+", " ", text)


def _wrapper_invocation_region(text):
    """The step 2 region -- the text between the "2. **Wrapper invocation.**"
    and "3. **One turn per call.**" markers -- whitespace-collapsed. Fails
    (an AssertionError, never a silent empty string) when either marker is
    missing or ambiguous, when the markers are out of order, or when the
    region between them is empty."""
    norm = _collapse_ws(text)
    for marker in (STEP2_START_MARKER, STEP2_END_MARKER):
        count = norm.count(marker)
        if count != 1:
            raise AssertionError(
                f"expected marker exactly once, found {count}x: {marker!r}"
            )
    start = norm.index(STEP2_START_MARKER)
    end = norm.index(STEP2_END_MARKER)
    if end < start:
        raise AssertionError(
            "step 2 markers are out of order: "
            f"{STEP2_END_MARKER!r} precedes {STEP2_START_MARKER!r}"
        )
    region = norm[start + len(STEP2_START_MARKER) : end]
    if not region.strip():
        raise AssertionError("step 2 region is empty")
    return region


def _states_scratchpad_placement(region):
    """AC-1 matcher: the rule is conditional on a `run_codex_exec.sh` call's
    output being saved to a file, names both streams, and places that file in
    the session scratchpad directory."""
    return (
        SAVED_OUTPUT_CONDITION_PHRASE in region
        and "stdout" in region
        and "stderr" in region
        and SCRATCHPAD_PLACEMENT_PHRASE in region
    )


def _states_project_root_and_cwd_prohibitions(region):
    """AC-2 matcher: the saved file is never written under `{project_root}`
    and the redirect target is never a current-directory-relative path."""
    return (
        PROJECT_ROOT_PROHIBITION_PHRASE in region
        and CWD_RELATIVE_PROHIBITION_PHRASE in region
    )


def _rule_governs_both_harness_entries(region):
    """The rule sits outside the `litellm`-only sentence: it is stated after
    the timeout sentence and says it holds on either harness entry."""
    timeout_end = region.find(TIMEOUT_SENTENCE)
    rule_start = region.find(SAVED_OUTPUT_CONDITION_PHRASE)
    return (
        timeout_end != -1
        and rule_start > timeout_end
        and BOTH_HARNESS_ENTRIES_PHRASE in region
    )


def _retains_invocation_form(region):
    """AC-7 (b) matcher: the invocation line, both `--litellm` values and the
    600000-millisecond timeout sentence are still present verbatim."""
    return all(
        piece in region
        for piece in (
            INVOCATION_LINE,
            LITELLM_CONTRIBUTOR_VALUE,
            LITELLM_PLAIN_VALUE,
            TIMEOUT_SENTENCE,
        )
    )


_FORBIDDEN_PROVIDER_NAMES = (
    "gemini",
    "openrouter",
    "openai",
    "gpt-4",
    "gpt-5",
    "grok",
    "mistral",
    "llama",
    "deepseek",
    "qwen",
)


def _forbidden_tokens_in(region):
    """AC-7 matcher (NFR2, NFR4): tokens the step 2 region must never carry."""
    found = []
    lowered = region.lower()
    for token in ("rate limit", "rate-limit", "notion.so", "/home/", "/users/"):
        if token in lowered:
            found.append(token)
    if "429" in region:
        found.append("429")
    for name in _FORBIDDEN_PROVIDER_NAMES:
        if name in lowered:
            found.append(name)
    if re.search(r"task\d{4}", region):
        found.append("taskNNNN")
    if re.search(r"`gate_id`\s+is\s+`", region) or re.search(
        r"`gate_id:\s*[\w.\-]+`", region
    ):
        found.append("gate_id literal")
    return found


_BRACED_VARIABLE_RE = re.compile(r"\$\{[^}]*\}")
_BARE_VARIABLE_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_GUARDED_VARIABLE_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-[^}]*\}")


def _shell_variable_tokens(text):
    """Every shell-variable token in `text`, braced (`${NAME...}`) and bare
    (`$NAME`) alike. Braced tokens are taken first and blanked out, so a
    variable nested in a braced default is not counted twice."""
    tokens = _BRACED_VARIABLE_RE.findall(text)
    remainder = _BRACED_VARIABLE_RE.sub(" ", text)
    tokens += _BARE_VARIABLE_RE.findall(remainder)
    return tokens


def _unguarded_new_variables(region, pre_fix_region):
    """NFR1 check (AC-6): every shell-variable token in `region` is either
    already present in the pre-fix region or in the guarded default form
    `${VAR:-default}`. Returns the offending tokens."""
    allowed = set(_shell_variable_tokens(pre_fix_region))
    return [
        token
        for token in _shell_variable_tokens(region)
        if token not in allowed and not _GUARDED_VARIABLE_RE.fullmatch(token)
    ]


class TestQuestionResolutionDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        # Whitespace-collapsed rendering for phrase assertions that must not
        # be sensitive to Markdown line-wrapping.
        cls.norm = re.sub(r"\s+", " ", cls.text)

    # --- pre-existing: deduplication rules, in order ----------------------

    def test_dedup_rule_same_question_id(self):
        self.assertIn("question_id", self.text)
        self.assertIn("worker protocol violation", self.text)

    def test_dedup_rule_supersedes(self):
        self.assertIn("supersedes", self.text)
        self.assertIn("obsoletes", self.text.lower())

    def test_dedup_rule_gate_evidence_field_match(self):
        self.assertIn("gate_id", self.text)
        self.assertIn("evidence", self.text)
        self.assertIn("duplicate candidate", self.text)

    def test_dedup_rule_no_prose_judgment(self):
        self.assertIn("prose differences", self.text)
        self.assertIn("stable question ID", self.text)

    def test_dedup_rule_answered_never_represented(self):
        self.assertIn("never re-presented", self.text)

    def test_dedup_rules_appear_in_order(self):
        markers = [
            "question_id",
            "supersedes",
            "duplicate candidate",
            "prose differences",
            "never re-presented",
        ]
        positions = [self.text.index(m) for m in markers]
        self.assertEqual(positions, sorted(positions))

    # --- pre-existing: priority sort + depends_on deferral ----------------

    def test_priority_sort_blocking_first(self):
        self.assertIn("blocking", self.text)

    def test_priority_sort_priority_levels_in_order(self):
        match = re.search(
            r"critical\s*→\s*high\s*→\s*normal\s*→\s*low", self.text
        )
        self.assertIsNotNone(match, "priority levels not stated in order")

    def test_priority_sort_category_order(self):
        for category in [
            "feature-identity",
            "business-objective",
            "functional-requirement",
            "acceptance-criteria",
            "security",
            "technical-requirement",
            "testing",
            "edge-case",
        ]:
            self.assertIn(category, self.text)

    def test_depends_on_deferral(self):
        self.assertIn("depends_on", self.text)
        self.assertIn("withheld from presentation", self.text)

    # --- pre-existing: presentation limits, as numbers --------------------

    def test_presentation_limits_are_numeric(self):
        self.assertIn("3 questions", self.text)
        self.assertIn("4 options", self.text)
        self.assertIn("32 questions", self.text)

    # --- pre-existing: batch resolution sequence --------------------------

    def test_batch_resolution_sequence_present(self):
        self.assertIn("needs_user_input", self.text)
        self.assertIn("batch-policies.yaml", self.text)
        self.assertIn("source: batch-decision-table", self.text)

    def test_missing_option_id_is_protocol_error(self):
        self.assertIn("protocol error", self.text)

    def test_label_matching_forbidden_as_substitute(self):
        self.assertIn("label matching is never substituted", self.text)

    # --- AC-1: jurisdiction stated as gate-identifier presence -------------
    # --- (round2 bs3: the criterion is identifier presence, never who     --
    # --- presents the gate)                                               --

    def test_jurisdiction_stated_as_identifier_presence_not_presenter(self):
        self.assertIn(
            "whether a worker returned it inside a question", self.norm
        )
        self.assertIn(
            "packet or the orchestrator raised the question directly "
            "outside of any",
            self.norm,
        )

    def test_artifact_overwrite_family_named_as_orchestrator_opened_example(self):
        self.assertIn("{phase}.artifact-overwrite", self.text)
        self.assertIn(
            "references/contracts/spec-writer-contract.md", self.text
        )

    def test_jurisdiction_does_not_turn_on_presenter(self):
        self.assertIn(
            "the jurisdiction below never turns on which one happened",
            self.norm,
        )

    # --- AC-3: batch resolution sequence covers orchestrator-opened gates -

    def _batch_sequence_section(self):
        marker = "## Batch resolution sequence"
        self.assertIn(marker, self.text)
        end_marker = "## Unlisted-gate fallback"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def test_entry_condition_covers_both_packet_and_orchestrator_opened(self):
        section = self._batch_sequence_section()
        self.assertIn("status: needs_user_input", section)
        self.assertIn(
            "the orchestrator raises the question directly outside any",
            section,
        )

    def test_answer_formed_without_a_packet_is_described(self):
        section = self._batch_sequence_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("`packet_id` is null", norm_section)
        self.assertIn(
            "`question_id` is the gate's own `gate_id`", norm_section
        )

    def test_no_packet_means_direct_action_not_redispatch(self):
        section = self._batch_sequence_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "the orchestrator instead acts on the decision directly at the",
            norm_section,
        )
        self.assertIn("rather than re-dispatching a worker turn", norm_section)

    # --- AC-4 (bs2): classification hoisted above BOTH branches -----------

    def test_classification_section_precedes_batch_resolution_sequence(self):
        classify_idx = self.text.index("## Fail-closed classification")
        sequence_idx = self.text.index("## Batch resolution sequence")
        self.assertLess(
            classify_idx,
            sequence_idx,
            "the classification section must precede the batch resolution "
            "sequence in document order",
        )

    def test_classification_precedes_any_policy_lookup(self):
        classify_idx = self.text.index("## Fail-closed classification")
        lookup_idx = self.text.index(
            "Look up the `gate_id` in `references/batch-policies.yaml`."
        )
        self.assertLess(
            classify_idx,
            lookup_idx,
            "the classification must precede the policy-table lookup, so "
            "a LISTED gate is classified too",
        )

    def test_classification_precedes_unlisted_gate_fallback(self):
        classify_idx = self.text.index("## Fail-closed classification")
        fallback_idx = self.text.index("## Unlisted-gate fallback")
        self.assertLess(classify_idx, fallback_idx)

    def test_classification_applies_regardless_of_listing(self):
        self.assertIn(
            "regardless of whether that `gate_id` turns out to have an "
            "entry in",
            self.norm,
        )
        self.assertIn(
            "this is what makes a listed gate classified too", self.norm.lower()
        )

    def test_fallback_references_classification_rather_than_restating(self):
        marker = "## Unlisted-gate fallback"
        section = self.text.split(marker, 1)[1]
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "the fail-closed classification above has already run",
            norm_section.lower(),
        )
        self.assertIn(
            "this fallback does not re-classify and does not restate the "
            "rule",
            norm_section,
        )

    def test_old_four_category_sentence_is_gone(self):
        # Negative proof (Test Notes): no surviving sentence names
        # spec-change among the immediate, unconditional aborts.
        self.assertNotIn(
            "Specification change, security, licensing, and irreversible "
            "operations abort",
            self.text,
        )

    # --- task0001 AC-1: the batch relaxation (mode-conditional route for
    # --- the three previously-unconditional abort arms) --------------------

    def _batch_relaxation_section(self):
        start = self.text.index("**The batch relaxation.**")
        end = self.text.index("**The surviving aborts.**")
        return self.text[start:end]

    def test_batch_relaxation_present_and_mode_conditioned(self):
        self.assertIn("**The batch relaxation.**", self.text)
        section = re.sub(r"\s+", " ", self._batch_relaxation_section()).lower()
        self.assertIn(
            "conditioned on the `--batch` invocation flag alone", section
        )
        self.assertIn(
            "`workflow.yaml`'s `batch` block never activates it", section
        )

    def test_batch_relaxation_states_interactive_branch_verbatim_retained(
        self,
    ):
        section = re.sub(r"\s+", " ", self._batch_relaxation_section()).lower()
        self.assertIn(
            "in interactive, each aborts the phase immediately, before "
            "any policy-table lookup, before the codex consultation "
            "described under the unlisted-gate fallback below, before "
            "`on_unanswered` is read, and before any option is selected",
            section,
        )
        self.assertIn("retained verbatim as the interactive branch", section)

    def test_batch_relaxation_states_batch_joins_consultation(self):
        section = re.sub(r"\s+", " ", self._batch_relaxation_section()).lower()
        self.assertIn(
            "in batch, each instead takes the relaxed route", section
        )
        self.assertIn(
            "joins the packet's single batched codex consultation", section
        )
        self.assertIn("rather than aborting", section)

    def test_batch_relaxation_old_unconditional_wording_is_gone(self):
        # AC-1 negative proof: the superseded "unchanged force / outside
        # this revision's scope" sentence must not survive anywhere.
        self.assertNotIn(
            "at unchanged force and outside this revision's scope",
            self.text,
        )
        self.assertNotIn("is not available to any of the three", self.text)
        self.assertNotIn(
            "Security, licensing, and irreversible operations abort the "
            "phase\nimmediately, at unchanged force",
            self.text,
        )

    # --- task0001 AC-2: the surviving-abort set, enumerated once -----------

    def _surviving_aborts_section(self):
        start = self.text.index("**The surviving aborts.**")
        end = self.text.index("**The routed arm.**")
        return self.text[start:end]

    def test_surviving_aborts_enumerated_once_and_abort_both_modes(self):
        section = re.sub(r"\s+", " ", self._surviving_aborts_section()).lower()
        self.assertIn("the following abort in both modes", section)
        self.assertIn("enumerated here, once", section)
        for member in [
            "the explicit fail-closed gate-list slot above",
            "`category: spec-change` whose `gate_id` is not exactly "
            "`rework.spec-change`",
            "both directions of the malformed `gate_id` / `category` "
            "pairing below",
            "the classification gate's direction-1 origin-membership "
            "failure below (origin absent, unresolvable, or not a "
            "member of the bound set)",
        ]:
            self.assertIn(member.lower(), section)

    # --- task0008 AC-1: the enumeration narrows to direction 1 alone ------

    def test_surviving_aborts_old_step_3_wording_is_gone(self):
        # AC-1 negative proof: the superseded member string, which
        # conflated both directions of the Classification gate's step 3,
        # must not survive anywhere in the document.
        self.assertNotIn(
            "the Classification gate's step-3 origin-verification "
            "failures",
            self.norm,
        )

    def test_surviving_aborts_old_wording_negative_proof_would_be_caught(
        self,
    ):
        # Non-vacuity guard: the matcher above must actually flag the
        # pre-task0008 wording it supersedes.
        fake_section = (
            "and the Classification gate's step-3 origin-verification "
            "failures below."
        )
        self.assertIn(
            "the Classification gate's step-3 origin-verification "
            "failures",
            fake_section,
        )

    def test_ac2_no_passage_states_batch_direction_2_question_aborts(self):
        # AC-2 (retention): direction 1's final-and-non-overridable
        # wording and direction 2's batch-relaxation wording are both
        # unchanged (asserted elsewhere); no passage states that a batch
        # question tripping direction 2 aborts.
        self.assertNotIn(
            "a batch question that trips direction 2 aborts",
            self.norm.lower(),
        )
        self.assertNotIn(
            "a routed question that trips direction 2 aborts",
            self.norm.lower(),
        )

    def test_surviving_aborts_routed_arm_cannot_convert_them(self):
        section = re.sub(r"\s+", " ", self._surviving_aborts_section()).lower()
        self.assertIn(
            "the routed arm below never converts any of them into a "
            "classification",
            section,
        )

    def test_surviving_aborts_heading_appears_exactly_once(self):
        # Enumeration guard (AC-2): the set is stated once, not re-listed.
        self.assertEqual(self.text.count("**The surviving aborts.**"), 1)

    # --- retention pins (TS-4): the three unchanged abort arms, individually

    def test_security_and_license_abort_arm_retained(self):
        self.assertIn(
            "the question's `category` "
            "(`references/question-packet-schema.md`) is `security` or "
            "`license`",
            self.norm,
        )

    def test_irreversible_assumption_abort_arm_retained(self):
        self.assertIn(
            "an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation.",
            self.norm,
        )

    def test_explicit_gate_list_mechanism_retained_as_a_slot(self):
        # The list mechanism survives for a future entry; `rework.spec-change`
        # is explicitly removed from it (see the routed-arm tests below).
        self.assertIn(
            "the `gate_id` appears on the explicit fail-closed gate list",
            self.norm,
        )

    def test_spec_change_no_longer_cited_as_todays_gate_list_entry(self):
        # Negative proof: the old wording that made `rework.spec-change` an
        # abort-arm example ("today, per the comment in
        # references/batch-policies.yaml") is gone.
        self.assertNotIn(
            "`rework.spec-change` today, per the comment in", self.text
        )

    # --- AC-1/FR7/FR8/D8: the routed arm ------------------------------------

    def test_routed_arm_present_and_not_aborting(self):
        self.assertIn("**The routed arm.**", self.text)
        self.assertIn(
            "does not abort here", self.norm
        )

    def test_routed_arm_states_batch_routes_to_classification_gate(self):
        # AC-1/AC-2: batch routes spec-change to the classification gate
        # instead of aborting.
        self.assertIn(
            "in batch, it is routed to the classification gate below "
            "instead of aborting",
            self.norm.lower(),
        )

    def test_routed_arm_states_interactive_asks_directly(self):
        # AC-2/FR8/D8: interactive keeps asking the user directly; no new
        # interactive question is introduced.
        self.assertIn(
            "in interactive, the question is asked directly, exactly as "
            "today",
            self.norm.lower(),
        )
        self.assertIn(
            "this revision introduces no new interactive question",
            self.norm.lower(),
        )

    def test_no_sentence_aborts_spec_change_unconditionally_in_batch(self):
        # Negative proof (Test Notes): the fail-closed section's abort
        # sentence no longer includes spec-change.
        classify_idx = self.text.index("## Fail-closed classification")
        gate_idx = self.text.index("## Classification gate")
        section = self.text[classify_idx:gate_idx]
        self.assertNotIn("`spec-change`, `security`, or `license`", section)

    def test_abort_ignores_on_unanswered_value(self):
        self.assertIn(
            "regardless of the question's",
            self.norm,
        )
        self.assertIn("`on_unanswered` value", self.norm)

    def test_abort_ignores_gate_listing_elsewhere(self):
        self.assertIn(
            "regardless of whether the `gate_id` is later found to be "
            "listed elsewhere",
            self.norm,
        )

    def test_abort_ignores_codex_mapping(self):
        self.assertIn(
            "regardless of whether a Codex suggestion would have mapped "
            "onto one of the question's existing `option_id`s",
            self.norm,
        )

    def test_none_of_three_can_override(self):
        self.assertIn(
            "none of those three can override this step", self.norm
        )

    def test_intentional_behaviour_change_stated(self):
        self.assertIn("intentional", self.text.lower())
        self.assertIn("not a regression", self.text)
        self.assertIn("continue-on-success-path", self.text)

    # --- task0012 AC-1 (FR11): routed-arm exit from the Batch resolution
    # --- sequence, at step 2 -----------------------------------------------

    def test_step_2_states_routed_arm_also_exits_the_sequence(self):
        section = re.sub(r"\s+", " ", self._batch_sequence_section())
        self.assertIn(
            "a question the routed arm instead sends to the classification "
            "gate below also leaves the sequence here",
            section.lower(),
        )

    def test_step_2_names_all_three_things_the_routed_question_never_reaches(
        self,
    ):
        section = re.sub(r"\s+", " ", self._batch_sequence_section()).lower()
        self.assertIn("neither step 3's policy lookup", section)
        self.assertIn("nor the unlisted-gate fallback", section)
        self.assertIn("nor `on_unanswered`", section)

    def test_step_2_negative_proof_abort_only_wording_would_not_satisfy_matcher(
        self,
    ):
        # Non-vacuity guard (Test Notes): a step 2 that states only the
        # abort-exit half (the pre-task0012 wording) must not satisfy the
        # routed-arm-exit matcher above.
        fake_step_2 = (
            "Apply the Fail-closed classification above. A question it "
            "aborts never reaches step 3."
        )
        self.assertNotIn(
            "a question the routed arm instead sends to the classification "
            "gate below also leaves the sequence here",
            fake_step_2.lower(),
        )

    # --- task0001 AC-3: step 2 states the two-mode split for the relaxed --
    # --- arms (batch skips step 3 for a different reason than interactive)

    def test_step_2_states_batch_relaxed_arms_route_directly(self):
        section = re.sub(r"\s+", " ", self._batch_sequence_section()).lower()
        self.assertIn(
            "true of the surviving aborts in both modes, and of the three "
            "relaxed arms in interactive",
            section,
        )
        self.assertIn(
            "in batch, none of the three relaxed arms reaches step 3 "
            "either, but for a different reason",
            section,
        )
        self.assertIn(
            "each instead takes the relaxed route, joining the packet's "
            "single batched codex consultation directly",
            section,
        )

    # --- task0008 AC-3: the batch direction-2 continuation is stated once -

    def test_batch_direction_2_continuation_stated_at_exactly_one_site(self):
        # AC-3: a counting assertion, not a presence assertion -- a
        # presence assertion would pass on a document stating the fact
        # three times, which is the defect being fixed. Counted over the
        # whitespace-normalized rendering since the source wraps long
        # paragraphs across markdown lines.
        phrase = (
            "a routed question that trips direction 2 leaves the "
            "Classification gate, joins the packet's batched "
            "consultation, and may reach the Unlisted-gate fallback "
            "below and, from there, `on_unanswered`"
        )
        self.assertEqual(self.norm.count(phrase), 1)

    def test_step_2_old_direction_2_wording_is_gone(self):
        # Negative proof: the pre-task0008 wording at step 2 itself, which
        # is superseded by the single-statement phrase above, must not
        # survive alongside it.
        self.assertNotIn(
            "does not stop at the classification gate: it leaves the "
            "gate and joins the packet's batched consultation, so it "
            "may still reach the unlisted-gate fallback below and, from "
            "there, `on_unanswered` — consistent with that fallback's "
            "own step 3 and step 6.",
            self.norm.lower(),
        )

    def test_fallback_step_3_cites_step_2_for_direction_2_routing(self):
        section = re.sub(r"\s+", " ", self._unlisted_gate_fallback_section())
        self.assertIn(
            "or through the Classification gate's direction 2 above "
            "(Batch resolution sequence step 2 above states this "
            "routing fact; cited here, not restated), rather than "
            "through the `gate_id` policy lookup",
            section,
        )

    def test_fallback_step_3_old_uncited_wording_is_gone(self):
        # Negative proof: the pre-task0008 wording, which named direction
        # 2 as an arrival source without citing where the routing fact
        # itself is stated, must not survive.
        self.assertNotIn(
            "Classification gate's direction 2 above, rather than "
            "through the `gate_id` policy lookup",
            self.norm,
        )

    # --- task0025 AC-1: step 2's exit cites the Outcome step instead of ----
    # --- ending the question's story in place -------------------------------

    def test_step_2_cites_the_outcome_step_instead_of_restating(self):
        section = re.sub(r"\s+", " ", self._batch_sequence_section())
        self.assertIn(
            "the Classification gate's Outcome step above", section
        )
        self.assertIn(
            "is the resolution for that question; it is not restated here",
            section,
        )

    def test_step_2_old_ending_wording_is_gone(self):
        # Negative proof (Test Notes): the pre-task0025 wording, which ended
        # the question's story in place instead of pointing at a named
        # section, must not survive anywhere in the document.
        self.assertNotIn(
            "the gate's own proceed/stop outcome and its audit record are "
            "the resolution for that question",
            self.text,
        )

    def test_step_2_negative_proof_old_ending_would_have_satisfied_neither_matcher(
        self,
    ):
        # Non-vacuity guard: proves the two matchers above actually
        # distinguish the old wording from the new one -- the old ending
        # does not contain the new citation, and (trivially) the new
        # citation string is not the old sentence.
        fake_old_ending = (
            "it reaches neither step 3's policy lookup, nor the "
            "Unlisted-gate fallback, nor `on_unanswered` -- the gate's own "
            "proceed/stop outcome and its audit record are the resolution "
            "for that question."
        )
        self.assertNotIn(
            "the Classification gate's Outcome step above", fake_old_ending
        )

    # --- task0025 NFR1: the packet/answer-model rule is stated exactly once

    def test_batch_resolution_sequence_does_not_restate_packet_effects(self):
        # NFR1 (Test Notes: "check the whole file for a second statement of
        # the packet effects"): the Outcome step's own vocabulary -- the
        # answer-source value it introduces and the packet status it names
        # for a stopped gate -- must appear nowhere inside the Batch
        # resolution sequence section, which now only cites the Outcome
        # step instead of restating what it says.
        section = self._batch_sequence_section()
        self.assertNotIn("batch-classification-gate", section)
        self.assertNotIn("obsolete", section)

    def test_outcome_step_vocabulary_appears_in_the_classification_gate_section(
        self,
    ):
        # Non-vacuity companion to the guard above: proves the vocabulary
        # searched for there is genuinely present somewhere in the
        # document (inside the Classification gate section), so an absent
        # feature could not trivially pass the restatement guard too.
        classify_idx = self.text.index("## Classification gate")
        sequence_idx = self.text.index("## Batch resolution sequence")
        gate_section = self.text[classify_idx:sequence_idx]
        self.assertIn("batch-classification-gate", gate_section)
        self.assertIn("obsolete", gate_section)

    # --- task0012 AC-3 (NFR2): precedence reservation on the routed arm ----

    def _precedence_reservation_section(self):
        start = self.text.index("**Precedence reservation.**")
        end = self.text.index("## Classification gate")
        return self.text[start:end]

    def test_routed_arm_states_precedence_reservation(self):
        self.assertIn("**Precedence reservation.**", self.text)
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "the routed arm applies only when none of the three "
            "immediate-abort conditions above holds",
            section,
        )

    def test_precedence_reservation_names_all_three_conditions(self):
        section = re.sub(r"\s+", " ", self._precedence_reservation_section())
        self.assertIn("`category: security`", section)
        self.assertIn("`category: license`", section)
        self.assertIn("`reversible: false`", section)

    def test_precedence_reservation_states_abort_final_and_non_overridable(
        self,
    ):
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "the abort arm is evaluated first and its abort is final and "
            "non-overridable",
            section,
        )
        self.assertIn(
            "the routed arm never converts an abort into a classification",
            section,
        )

    def test_precedence_reservation_negative_proof_omitted_reservation_fails(
        self,
    ):
        # Non-vacuity guard: a routed-arm paragraph that OMITS the
        # precedence reservation (the pre-task0012 wording) must not carry
        # the marker the section-locator above depends on.
        fake_routed_arm = (
            "**The routed arm.** A question whose `category` is "
            "`spec-change` -- `gate_id: rework.spec-change` -- does not "
            "abort here. In batch, it is routed to the Classification gate "
            "below instead of aborting."
        )
        self.assertNotIn("**Precedence reservation.**", fake_routed_arm)

    # --- task0001 AC-3: precedence reservation's batch-mode addition -------

    def test_precedence_reservation_states_batch_takes_relaxed_route(self):
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "in batch, a question satisfying both the routed arm's "
            "condition and one of the three relaxed arms takes the "
            "relaxed route",
            section,
        )
        self.assertIn("rather than aborting", section)

    def test_precedence_reservation_states_both_modes_never_convert_surviving_abort(
        self,
    ):
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "in both modes, the routed arm never converts one of the "
            "surviving aborts into a classification",
            section,
        )

    # --- task0012 AC-2 (FR11, NFR2): Unlisted-gate fallback distinguishes
    # --- the aborted set from the routed set --------------------------------

    def _fallback_block_branch(self):
        marker = "## Unlisted-gate fallback"
        end_marker = "### Codex consultation procedure"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        section = self.text[start:end]
        block_idx = section.index("8. `block`")
        next_idx = section.index("9. `use_batch_policy`")
        return section[block_idx:next_idx]

    def test_block_branch_distinguishes_aborted_set_from_routed_set(self):
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertIn(
            "the fail-closed classification above owns which questions "
            "those abort and by which rule, cited here, not restated",
            section,
        )
        self.assertIn(
            "specification-change questions never reach here either, but "
            "for a different reason",
            section,
        )
        self.assertIn(
            "the routed arm's removal at batch resolution sequence "
            "step 2 above owns that exclusion, cited here, not restated",
            section,
        )

    # --- task0008 AC-4: the block branch cites, rather than re-narrates,
    # --- the upstream abort ownership and the routed-arm removal ---------
    # --- ownership -----------------------------------------------------

    def test_block_branch_old_ownership_narration_is_gone(self):
        # Negative proof: the pre-task0008 narrative restating WHY the
        # abort/removal happens, instead of citing where it is stated,
        # must not survive.
        norm_lower = re.sub(r"\s+", " ", self.text).lower()
        self.assertNotIn(
            "because the fail-closed classification above has already "
            "aborted them before this branch is reached",
            norm_lower,
        )
        self.assertNotIn(
            "the routed arm removed them from the sequence entirely at "
            "step 2 of the batch resolution sequence, so they were "
            "never subject to this fallback in the first place",
            norm_lower,
        )

    def test_block_branch_old_ownership_narration_negative_proof_would_be_caught(
        self,
    ):
        # Non-vacuity guard: the matchers above must actually flag the
        # pre-task0008 wording they supersede.
        fake_section = (
            "in interactive, security, licensing and irreversible-"
            "operation questions never reach here because the "
            "Fail-closed classification above has already ABORTED them "
            "before this branch is reached; in interactive, "
            "specification-change questions never reach here either, "
            "but for a different reason -- the routed arm REMOVED them "
            "from the sequence entirely at step 2 of the Batch "
            "resolution sequence, so they were never subject to this "
            "fallback in the first place."
        )
        norm_lower = re.sub(r"\s+", " ", fake_section).lower()
        self.assertIn(
            "because the fail-closed classification above has already "
            "aborted them before this branch is reached",
            norm_lower,
        )
        self.assertIn(
            "the routed arm removed them from the sequence entirely at "
            "step 2 of the batch resolution sequence, so they were "
            "never subject to this fallback in the first place",
            norm_lower,
        )

    def test_block_branch_direction_2_subset_cites_step_2_not_restated(self):
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertIn(
            "batch resolution sequence step 2 above states how that "
            "subset reaches the packet's batched consultation (cited "
            "here, not restated)",
            section,
        )
        self.assertIn("reaches this branch after all", section)

    def test_block_branch_old_direction_2_restatement_is_gone(self):
        # Negative proof: the pre-task0008 wording, which restated the
        # routing mechanism (leaves the gate, joins the consultation)
        # rather than citing it, must not survive.
        self.assertNotIn(
            "a routed spec-change question that trips the "
            "Classification gate's direction 2 leaves the gate and "
            "joins the packet's",
            self.norm,
        )

    def test_block_branch_no_claim_of_unreachability_contradicts_single_site(
        self,
    ):
        # AC-4: no claim of unreachability for the direction-2 subset
        # contradicts the single statement site (which says it CAN reach
        # the Unlisted-gate fallback and, from there, `on_unanswered`).
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertNotIn("direction-2 subset never reaches", section)
        self.assertNotIn("direction 2 subset never reaches", section)

    def test_superseded_single_mechanism_sentence_is_gone(self):
        # C5: the absence half. Non-vacuity: the block-branch locator above
        # already proves the region was found and is non-empty (it would
        # have raised ValueError otherwise).
        section = self._fallback_block_branch()
        self.assertTrue(section.strip())
        self.assertNotIn(
            "The Fail-closed classification above has already aborted "
            "every specification-change, security, licensing and "
            "irreversible-operation question before this branch is "
            "reached",
            section,
        )

    def test_block_branch_negative_proof_old_sentence_would_be_caught(self):
        # Non-vacuity guard (Test Notes): the matcher above must actually
        # flag the pre-task0012 wording it supersedes.
        fake_section = (
            "8. `block` → The Fail-closed classification above has "
            "already aborted every specification-change, security, "
            "licensing and irreversible-operation question before this "
            "branch is reached, so this branch only ever sees the "
            "remainder."
        )
        self.assertIn(
            "The Fail-closed classification above has already aborted "
            "every specification-change, security, licensing and "
            "irreversible-operation question before this branch is "
            "reached",
            fake_section,
        )

    # --- task0001 AC-3: block branch's batch-mode arrival via the relaxed
    # --- route (security/license/reversible-false can now reach `block`) --

    def test_block_branch_states_batch_arrival_via_relaxed_route(self):
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertIn(
            "in batch, the same three arrive here, through the relaxed "
            "route",
            section,
        )
        self.assertIn(
            "whenever neither the codex consultation nor the opus "
            "escalation maps or decides one of their options",
            section,
        )
        self.assertIn(
            "this branch then takes the option with the smallest side "
            "effect for them exactly as for any other question",
            section,
        )

    def test_block_branch_interactive_arm_still_never_reaches_here(self):
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertIn(
            "in interactive, security, licensing and irreversible-"
            "operation questions never reach here — the fail-closed "
            "classification above owns which questions those abort and "
            "by which rule, cited here, not restated".lower(),
            section,
        )

    # --- classification is stated mechanically -----------------------------

    def test_classification_names_category_values(self):
        for value in ["`spec-change`", "`security`", "`license`"]:
            self.assertIn(value, self.text)

    def test_classification_names_explicit_gate_list(self):
        self.assertIn("explicit fail-closed gate list", self.norm)
        self.assertIn("rework.spec-change", self.text)

    def test_classification_names_irreversible_assumption_signal(self):
        self.assertIn("assumptions[]", self.text)
        self.assertIn("related_question_ids", self.text)
        self.assertIn("reversible: false", self.text)
        self.assertIn("irreversible operation", self.norm)

    # --- worker-set fields are cross-checked by the validator ---------------

    def test_worker_set_fields_not_trusted_alone(self):
        self.assertIn("trusted alone", self.norm)

    def test_validator_cross_check_referenced(self):
        self.assertIn("scripts/validate-worker-output.py", self.text)
        self.assertIn("cross-checks", self.norm)

    def test_validator_rule_not_restated(self):
        self.assertIn("does not restate the check itself", self.norm)

    # --- AC-7 (bs8): no feature-docs task identifier; schema cited instead -

    def test_no_feature_docs_task_identifier_cited(self):
        self.assertIsNone(
            re.search(r"task\d{4}", self.text),
            "question-resolution.md must not attribute a rule to a "
            "feature-docs task identifier that does not exist in the "
            "distributed plugin (round2.yaml bs8)",
        )

    def test_cross_check_attributed_to_the_packet_schema(self):
        self.assertIn("references/question-packet-schema.md", self.text)
        self.assertIn(
            "states the constraint this check enforces", self.norm
        )

    # --- AC-6 (bs6): consultation budget independent of question count ----

    def test_codex_procedure_section_present(self):
        self.assertIn("### Codex consultation procedure", self.text)

    def _codex_procedure_section(self):
        marker = "### Codex consultation procedure"
        self.assertIn(marker, self.text)
        return self.text.split(marker, 1)[1]

    def test_codex_procedure_availability_probe(self):
        section = self._codex_procedure_section()
        self.assertIn("Availability probe", section)
        self.assertIn("run_codex_exec.sh", section)
        self.assertIn("command -v codex", section)

    def test_codex_procedure_wrapper_invocation(self):
        section = self._codex_procedure_section()
        self.assertIn("Wrapper invocation", section)
        self.assertIn("readonly", section)
        self.assertIn('-C "{project_root}"', section)

    def test_codex_procedure_one_turn_per_call(self):
        section = self._codex_procedure_section()
        self.assertIn("One turn per call", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("prior exchange", norm_section)

    def test_history_is_capped_or_summarized_not_resent_in_full(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("compressed to its concluding", norm_section)
        self.assertIn(
            "caps the prompt size instead of letting it grow with every "
            "turn",
            norm_section,
        )
        # The old unbounded wording must be gone.
        self.assertNotIn("includes the FULL", self.text)

    def test_codex_procedure_trajectory_judgement(self):
        section = self._codex_procedure_section()
        self.assertIn("Trajectory judgement", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("turn 3", norm_section)
        self.assertIn("third turn", norm_section)

    def test_codex_procedure_five_turn_ceiling(self):
        section = self._codex_procedure_section()
        self.assertIn("Five-turn ceiling", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("five turns total", norm_section)

    def test_ceiling_bounds_per_packet_not_per_question(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("bounds the total launches per packet", norm_section)
        self.assertIn("not per question", norm_section)

    def test_packet_batching_stated_in_fallback_sequence(self):
        marker = "## Unlisted-gate fallback"
        section = self.text.split(marker, 1)[1]
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "batch every unresolved question from the same packet",
            norm_section.lower(),
        )
        self.assertIn(
            "bounds the total number of consultations to one per packet "
            "rather than one per question",
            norm_section,
        )

    def test_per_command_fallback_cache_referenced(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("per-command approval fallback", norm_section)

    def test_codex_procedure_decision_stays_with_claude(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("stays with Claude", norm_section)

    def test_codex_procedure_output_untrusted(self):
        # Untrusted-output rule is stated both at the fallback mapping step
        # and again, in the procedure itself.
        self.assertGreaterEqual(self.text.count("untrusted"), 2)
        section = self._codex_procedure_section()
        self.assertIn("untrusted", section)

    def test_codex_procedure_availability_precedes_wrapper_invocation(self):
        section = self._codex_procedure_section()
        probe_idx = section.index("Availability probe")
        wrapper_idx = section.index("Wrapper invocation")
        self.assertLess(probe_idx, wrapper_idx)

    # --- task0001 AC-5: the Codex-absent route runs the Opus escalation ----
    # --- instead of skipping straight to `on_unanswered` -------------------

    def test_availability_probe_unavailable_runs_escalation(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "skip straight to the Opus escalation below, which runs in "
            "Codex's place",
            norm_section,
        )
        self.assertIn(
            "if the escalation leaves a question undecided too, that "
            "question falls through to step 6",
            norm_section,
        )

    def test_old_unavailable_immediate_on_unanswered_wording_is_gone(self):
        # AC-5 negative proof: the pre-rewrite wording, which skipped
        # straight to `on_unanswered` with no escalation in between, must
        # be gone.
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section).lower()
        self.assertNotIn(
            "skip straight to step 6 of the fallback sequence above "
            "(`on_unanswered`) without ever reaching codex",
            norm_section,
        )

    def test_trajectory_judgement_hands_off_to_escalation(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section).lower()
        self.assertIn(
            "diverging → stop consulting and hand the packet's "
            "still-unmapped questions to the opus escalation below",
            norm_section,
        )

    def test_five_turn_ceiling_hands_off_to_escalation(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section).lower()
        self.assertIn(
            "whatever remains unmapped when the ceiling is reached passes "
            "to the opus escalation below",
            norm_section,
        )
        self.assertIn(
            "the escalation itself is dispatched separately and is "
            "counted outside this ceiling",
            norm_section,
        )

    def test_wrapper_fallback_provider_claim_is_absent(self):
        # task0002 AC-5: the claim that the wrapper's own reply may come
        # from a fallback provider instead of the primary one is removed
        # from the consultation procedure's wrapper-invocation step.
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertNotIn(
            "The wrapper's reply may come from a fallback provider "
            "instead of the primary one",
            norm_section,
        )
        self.assertNotIn(
            "with no provider name or detection mechanism named here",
            norm_section,
        )

    def test_wrapper_fallback_provider_claim_absence_non_vacuity(self):
        # Non-vacuity guard: proves the matcher above would have caught the
        # withdrawn sentence had it still been present in the section.
        fake_section = (
            "2. Wrapper invocation. Each turn calls the wrapper directly. "
            "The wrapper's reply may come from a fallback provider instead "
            "of the primary one, with no provider name or detection "
            "mechanism named here."
        )
        self.assertIn(
            "The wrapper's reply may come from a fallback provider "
            "instead of the primary one",
            fake_section,
        )
        self.assertIn(
            "with no provider name or detection mechanism named here",
            fake_section,
        )

    # --- task0001 AC-5: the Opus escalation subsection itself --------------

    def _opus_escalation_section(self):
        marker = "### Opus escalation"
        self.assertIn(marker, self.text)
        return self.text.split(marker, 1)[1]

    def test_opus_escalation_section_present_after_codex_procedure(self):
        codex_idx = self.text.index("### Codex consultation procedure")
        escalation_idx = self.text.index("### Opus escalation")
        self.assertLess(codex_idx, escalation_idx)

    def test_opus_escalation_dispatch_is_single_per_packet(self):
        section = re.sub(r"\s+", " ", self._opus_escalation_section())
        self.assertIn("Exactly one dispatch per packet", section)
        self.assertIn(
            "carrying every question of that packet still unmapped when "
            "the consultation ended",
            section,
        )

    def test_opus_escalation_counted_outside_five_turn_ceiling(self):
        section = re.sub(r"\s+", " ", self._opus_escalation_section()).lower()
        self.assertIn(
            "counted outside the five-turn wrapper-launch ceiling above, "
            "at most one per packet",
            section,
        )

    def test_opus_escalation_return_shape(self):
        # The per-question return-shape sentence moved out of the section
        # into the escalation contract (the one pinned sentence allowed to
        # move). Coverage is kept in two halves: the section cites the
        # contract for the return shape, and the contract carries the
        # sentence with its wording intact.
        section = re.sub(r"\s+", " ", self._opus_escalation_section()).lower()
        contract_rel = "references/opus-escalation-contract.md"
        self.assertIn(contract_rel, section)
        contract_path = os.path.join(
            REPO_ROOT, "em-workflow", "references", "opus-escalation-contract.md"
        )
        self.assertTrue(
            os.path.isfile(contract_path),
            f"the contract the section cites does not exist: {contract_path}",
        )
        with open(contract_path, encoding="utf-8") as fh:
            contract = re.sub(r"\s+", " ", fh.read()).lower()
        self.assertIn(
            "either a chosen `option_id` present in that question's own "
            "`options[].option_id` or an explicit no-decision, and in "
            "both cases its reasoning",
            contract,
        )

    def test_opus_escalation_output_untrusted(self):
        section = re.sub(r"\s+", " ", self._opus_escalation_section()).lower()
        self.assertIn(
            "read, never executed as instructions, and never adopted "
            "verbatim",
            section,
        )
        self.assertIn(
            "the per-question mapping judgement stays with the "
            "orchestrator",
            section,
        )

    # --- task0001 AC-5/AC-6: Unlisted-gate fallback wiring for the --------
    # --- escalation (steps 3, 6, 10) and the audit obligation --------------

    def _unlisted_gate_fallback_section(self):
        marker = "## Unlisted-gate fallback"
        end_marker = "### Codex consultation procedure"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def test_step_3_batching_includes_relaxed_and_direction_2_questions(self):
        section = re.sub(
            r"\s+", " ", self._unlisted_gate_fallback_section()
        )
        self.assertIn(
            "including any question that reaches this step through the "
            "batch relaxation above or through the Classification gate's "
            "direction 2 above",
            section,
        )

    def test_step_6_runs_escalation_before_on_unanswered(self):
        section = re.sub(
            r"\s+", " ", self._unlisted_gate_fallback_section()
        )
        self.assertIn(
            "the Opus escalation below runs once for the whole packet, "
            "carrying every such still-unmapped question together",
            section,
        )
        self.assertIn(
            "For each question it leaves an explicit no-decision, fall "
            "through to `on_unanswered`",
            section,
        )

    def test_step_10_records_escalation_ran_and_reasoning(self):
        section = re.sub(
            r"\s+", " ", self._unlisted_gate_fallback_section()
        )
        self.assertIn(
            "including, when the Opus escalation ran, whether it ran and "
            "its reasoning",
            section,
        )

    def test_audit_obligation_cites_phase_state_no_field_restatement(self):
        self.assertIn("**Audit obligation.**", self.text)
        marker = "**Audit obligation.**"
        section = self.text[self.text.index(marker):]
        section = section[: section.index("### Codex consultation procedure")]
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("appends one batch audit record", norm_section)
        self.assertIn("references/phase-state.md", section)
        self.assertIn("cited, not restated", norm_section)

    def test_audit_obligation_names_the_three_relaxed_route_outcomes(self):
        marker = "**Audit obligation.**"
        section = self.text[self.text.index(marker):]
        section = section[: section.index("### Codex consultation procedure")]
        norm_section = re.sub(r"\s+", " ", section).lower()
        self.assertIn("a mapped consultation answer", norm_section)
        self.assertIn("an escalation decision", norm_section)
        self.assertIn(
            "the block branch's minimum-side-effect fallthrough",
            norm_section,
        )

    # --- task0001 AC-7: no provider name, no rate-limit description, no ---
    # --- new gate_id --------------------------------------------------------

    def test_no_fallback_provider_name_leaked(self):
        for name in [
            "gemini",
            "openrouter",
            "openai",
            "gpt-4",
            "gpt-5",
            "grok",
            "mistral",
            "llama",
            "deepseek",
            "qwen",
        ]:
            self.assertNotIn(name, self.text.lower())

    def test_no_rate_limit_detection_description(self):
        self.assertNotIn("rate limit", self.text.lower())
        self.assertNotIn("rate-limit", self.text.lower())
        self.assertNotIn("429", self.text)

    def test_no_new_gate_id_minted(self):
        gate_ids = set(
            re.findall(r"`gate_id`\s+is\s+`([\w.\-]+)`", self.text)
        )
        gate_ids |= set(re.findall(r"`gate_id:\s*([\w.\-]+)`", self.text))
        allowed = {"rework.spec-change"}
        self.assertTrue(
            gate_ids <= allowed,
            f"unexpected gate_id literal(s) found: {gate_ids - allowed}",
        )

    # --- Design note: decision basis recorded -----------------------------

    def test_resolution_basis_recorded(self):
        self.assertIn("resolution_note", self.text)
        self.assertIn("run report", self.text)

    # --- codex-consult-output-scratchpad task0001: saved wrapper output ----
    # --- goes into the session scratchpad (step 2, Wrapper invocation) -----

    def test_wrapper_invocation_region_lies_inside_codex_procedure(self):
        # The region is located inside "### Codex consultation procedure",
        # after its heading and before the next level-3 heading.
        heading = self.text.index("### Codex consultation procedure")
        next_heading = self.text.index("### Opus escalation")
        start = self.text.index(STEP2_START_MARKER)
        end = self.text.index(STEP2_END_MARKER)
        self.assertLess(heading, start)
        self.assertLess(start, end)
        self.assertLess(end, next_heading)

    def test_ac1_saved_output_goes_to_session_scratchpad(self):
        region = _wrapper_invocation_region(self.text)
        self.assertIn(SAVED_OUTPUT_CONDITION_PHRASE, region)
        self.assertIn(SCRATCHPAD_PLACEMENT_PHRASE, region)
        self.assertTrue(_states_scratchpad_placement(region))

    def test_ac1_scratchpad_is_named_in_prose_as_the_harness_directory(self):
        region = _wrapper_invocation_region(self.text)
        self.assertIn(
            "the per-session scratchpad directory the harness provides", region
        )

    def test_ac1_saving_stays_optional(self):
        region = _wrapper_invocation_region(self.text)
        self.assertIn("Saving the output stays optional", region)
        self.assertIn("when nothing is saved, this rule imposes nothing", region)

    def test_ac1_rule_governs_every_turn_on_either_harness_entry(self):
        region = _wrapper_invocation_region(self.text)
        self.assertTrue(_rule_governs_both_harness_entries(region))

    def test_ac2_project_root_and_cwd_relative_paths_are_prohibited(self):
        region = _wrapper_invocation_region(self.text)
        self.assertIn(PROJECT_ROOT_PROHIBITION_PHRASE, region)
        self.assertIn(CWD_RELATIVE_PROHIBITION_PHRASE, region)
        self.assertTrue(_states_project_root_and_cwd_prohibitions(region))

    def test_ac6_step2_introduces_no_unguarded_shell_variable(self):
        region = _wrapper_invocation_region(self.text)
        pre_fix_region = _wrapper_invocation_region(PRE_FIX_STEP2_TEXT)
        self.assertEqual(_unguarded_new_variables(region, pre_fix_region), [])

    def test_ac6_step2_variable_tokens_are_the_pre_fix_ones(self):
        # Non-vacuity of the check above: the region does carry shell
        # variables (the invocation line), and none beyond the pre-fix set
        # was added, since the rule names the scratchpad in prose.
        region = _wrapper_invocation_region(self.text)
        pre_fix_region = _wrapper_invocation_region(PRE_FIX_STEP2_TEXT)
        self.assertEqual(
            sorted(_shell_variable_tokens(pre_fix_region)),
            ["$PROMPT", "${CLAUDE_PLUGIN_ROOT}"],
        )
        self.assertEqual(
            sorted(_shell_variable_tokens(region)),
            sorted(_shell_variable_tokens(pre_fix_region)),
        )

    def test_ac7_step2_retains_invocation_line_litellm_values_and_timeout(self):
        region = _wrapper_invocation_region(self.text)
        self.assertIn(INVOCATION_LINE, region)
        self.assertIn(LITELLM_CONTRIBUTOR_VALUE, region)
        self.assertIn(LITELLM_PLAIN_VALUE, region)
        self.assertIn(TIMEOUT_SENTENCE, region)
        self.assertTrue(_retains_invocation_form(region))

    def test_ac7_step2_carries_no_forbidden_token(self):
        region = _wrapper_invocation_region(self.text)
        self.assertEqual(_forbidden_tokens_in(region), [])

    def test_ac7_rule_is_defined_only_in_this_document(self):
        # "This is the only place the rule is defined": the placement phrase
        # occurs exactly once in this document.
        self.assertEqual(_collapse_ws(self.text).count(SCRATCHPAD_PLACEMENT_PHRASE), 1)


class TestClassificationTrustBoundaryFix(unittest.TestCase):
    """task0019 AC-1 through AC-4, AC-9 (round2 findings 87ae09bcfe6410c0,
    61c73dc71f323f45): the routed arm and the irreversibility abort must not
    depend on values the worker under scrutiny supplies.

    - AC-1: the routed arm's entry condition is the question's `gate_id`
      being `rework.spec-change`; a worker-set `category` never selects a
      route on its own.
    - AC-2: a packet whose `gate_id` is `rework.spec-change` but whose
      `category` disagrees is malformed and aborts, reaching neither the
      routed arm nor the Unlisted-gate fallback.
    - AC-3: irreversibility is decided from orchestrator-held metadata
      about the operation, independent of the packet; a packet's
      `reversible: false` assumption still aborts in addition, and
      omitting it can never remove the orchestrator-held abort.
      **Superseded by task0024 (D11, round 3): no orchestrator-held
      metadata source exists anywhere in the repository, so this claim is
      withdrawn and replaced by an accurate statement of the abort's only
      actual basis — see the AC-3 methods below, now pinning the
      replacement text instead of the withdrawn claim.**
    - AC-4: the three pre-existing abort arms and the precedence
      reservation are not weakened, merged or removed by the above.
    - AC-9 (partial): the two new stop paths each state their reason is
      recorded.
    """

    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def _fail_closed_section(self):
        start = self.text.index("## Fail-closed classification")
        end = self.text.index("## Classification gate")
        return self.text[start:end]

    def _fail_closed_norm(self):
        return re.sub(r"\s+", " ", self._fail_closed_section()).lower()

    # --- AC-1: routed arm keyed on gate_id, never on category --------------

    def test_routed_arm_condition_is_gate_id_not_category(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the routed arm's entry condition is the question's `gate_id` "
            "being `rework.spec-change`",
            section,
        )
        self.assertIn(
            "a worker-set `category` value never selects a route on its "
            "own",
            section,
        )

    def test_routed_arm_condition_negative_twin_category_keyed_wording_fails(
        self,
    ):
        # Test Notes: a synthetic sample describing the route as keyed on
        # `category` must fail the matcher above, otherwise the pin would
        # pass on any prose merely containing the word `gate_id`.
        fake_section = (
            "**The routed arm.** A question whose `category` is "
            "`spec-change` is routed to the Classification gate below, "
            "keyed on `gate_id: rework.spec-change` for bookkeeping only."
        )
        self.assertNotIn(
            "the routed arm's entry condition is the question's `gate_id` "
            "being `rework.spec-change`",
            fake_section.lower(),
        )

    # --- AC-2: malformed gate_id/category pairing aborts --------------------

    def test_malformed_pairing_aborts_reaching_neither_arm(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "a question whose `gate_id` is `rework.spec-change` and whose "
            "`category` is anything other than `spec-change` is malformed "
            "and aborts here, recording that reason",
            section,
        )
        self.assertIn(
            "it reaches neither the routed arm above nor the unlisted-gate "
            "fallback below",
            section,
        )

    def test_malformed_pairing_negative_twin_no_mismatch_rule_fails(self):
        fake_section = (
            "**The routed arm.** A question whose `gate_id` is "
            "`rework.spec-change` is routed to the Classification gate, "
            "regardless of its `category`."
        )
        self.assertNotIn("is malformed and aborts", fake_section.lower())

    # --- task0024 AC-2: malformed pairing becomes bidirectional -------------

    def test_malformed_pairing_reverse_direction_also_aborts(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the reverse mismatch is equally malformed", section
        )
        self.assertIn(
            "a question whose `category` is `spec-change` and whose "
            "`gate_id` is anything other than `rework.spec-change` also "
            "aborts, recording that reason",
            section,
        )

    def test_malformed_pairing_neither_direction_reaches_policy_lookup_or_on_unanswered(
        self,
    ):
        section = self._fail_closed_norm()
        self.assertIn(
            "neither mismatched pairing reaches the policy lookup in the "
            "batch resolution sequence below, the unlisted-gate fallback, "
            "or `on_unanswered`",
            section,
        )

    def test_malformed_pairing_reverse_direction_negative_twin_fails(self):
        # Non-vacuity guard: the pre-task0024 single-direction wording alone
        # must not satisfy the reverse-direction matcher above.
        fake_section = (
            "**Malformed pairing.** A question whose `gate_id` is "
            "`rework.spec-change` and whose `category` is anything other "
            "than `spec-change` is malformed and aborts here, recording "
            "that reason: it reaches neither the routed arm above nor the "
            "Unlisted-gate fallback below."
        )
        self.assertNotIn(
            "the reverse mismatch is equally malformed",
            fake_section.lower(),
        )

    # --- AC-3 (superseded by task0024's own AC-3, D11): the task0019-era
    # --- orchestrator-held-metadata claim named a defence with no
    # --- definition anywhere in the repository; task0024 withdraws it and
    # --- replaces it with an accurate statement of the abort's only actual
    # --- basis (the packet's own `assumptions[].reversible: false`,
    # --- worker-declared). The four methods below pin the replacement text
    # --- in place of the withdrawn claim; the abort's own force (it still
    # --- fires, still records its reason) is retained, per AC-3/AC-6.

    def test_irreversibility_basis_is_the_packets_own_declaration(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the irreversibility abort's basis is the packet's own "
            "declaration",
            section,
        )
        self.assertIn(
            "is this abort's only current trigger", section
        )

    def test_irreversibility_basis_named_worker_declared_limitation(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "this basis is worker-declared", section
        )
        self.assertIn(
            "a stated limitation of the current design, not a second, "
            "independent defence",
            section,
        )

    def test_no_orchestrator_held_source_claimed(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "no orchestrator-held source constrains it today", section
        )

    def test_irreversibility_abort_still_records_its_reason(self):
        # Retention (AC-3: "the abort's own force is unchanged"): the abort
        # still fires and still records its reason, exactly as before the
        # claim was withdrawn.
        section = self._fail_closed_norm()
        self.assertIn(
            "this abort records its reason exactly as every abort in this "
            "section does",
            section,
        )

    def test_orchestrator_held_irreversible_operations_list_claim_is_gone(
        self,
    ):
        # AC-3 negative proof: no sentence claims an orchestrator-held
        # metadata source or irreversible-operations list -- the withdrawn
        # task0019-era claim must not survive anywhere in the document.
        self.assertNotIn(
            "decided from metadata the orchestrator holds about that "
            "operation",
            self.norm.lower(),
        )
        self.assertNotIn("irreversible-operations list", self.text.lower())
        self.assertNotIn(
            "independently of whatever the packet's `assumptions[]` does "
            "or does not declare",
            self.norm,
        )

    def test_irreversibility_negative_twin_bare_bullet_wording_fails(self):
        # Non-vacuity guard (Test Notes): the bare bullet alone (no
        # replacement paragraph) must not satisfy the replacement-statement
        # matchers above -- proves the matcher is not vacuous against an
        # empty/renamed section.
        fake_section = (
            "- an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation."
        )
        self.assertNotIn(
            "the irreversibility abort's basis is the packet's own "
            "declaration",
            fake_section.lower(),
        )

    # --- AC-4: retention, consolidated (individual pins already exist above)

    def test_ac4_all_three_abort_arms_and_precedence_reservation_survive(
        self,
    ):
        section = re.sub(r"\s+", " ", self._fail_closed_section())
        self.assertIn(
            "the question's `category` "
            "(`references/question-packet-schema.md`) is `security` or "
            "`license`",
            section,
        )
        self.assertIn(
            "an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation.",
            section,
        )
        self.assertIn("**Precedence reservation.**", self._fail_closed_section())


class TestQuestionPacketSchemaCategoryBlockingConstraint(unittest.TestCase):
    """AC-7 (round2.yaml bs8): the packet-shape SSOT (question-packet-
    schema.md) states the category-to-blocking constraint itself and names
    the enforcing script, instead of leaving the rule undocumented at its
    own source of truth and attributed elsewhere to a feature-docs task
    identifier that does not exist in the distributed plugin."""

    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def test_constraint_states_the_three_categories_require_block(self):
        self.assertIn(
            "A question whose `category` is `spec-change`, `security`, or "
            "`license` must carry `on_unanswered: block`",
            self.norm,
        )

    def test_enforcing_script_named(self):
        self.assertIn("scripts/validate-worker-output.py", self.text)
        self.assertIn("enforces this constraint", self.norm)

    def test_no_feature_docs_task_identifier_cited(self):
        self.assertIsNone(
            re.search(r"task\d{4}", self.text),
            "question-packet-schema.md must not attribute ownership to a "
            "feature-docs task identifier that does not exist in the "
            "distributed plugin (round2.yaml bs8)",
        )


class TestWrapperOutputPlacementMatchers(unittest.TestCase):
    """codex-consult-output-scratchpad task0001 (AC-3, AC-6, AC-7): the
    step 2 region extractor fails loudly, and every matcher is run against
    the pre-fix step 2 text (the negative twin) to show it can fail. The
    twin goes through the same extractor and the identical predicate the
    real-document assertions use."""

    def setUp(self):
        self.pre_fix_region = _wrapper_invocation_region(PRE_FIX_STEP2_TEXT)

    # --- region extractor: fails loudly, never a silent empty string -------

    def test_extractor_returns_whitespace_collapsed_region(self):
        region = _wrapper_invocation_region(PRE_FIX_STEP2_TEXT)
        self.assertNotIn("\n", region)
        self.assertNotIn("  ", region)
        self.assertIn("Each turn calls the wrapper directly", region)
        self.assertNotIn("One turn per call", region)

    def test_extractor_fails_when_start_marker_missing(self):
        forged = PRE_FIX_STEP2_TEXT.replace(STEP2_START_MARKER, "2. Invocation.")
        with self.assertRaises(AssertionError):
            _wrapper_invocation_region(forged)

    def test_extractor_fails_when_end_marker_missing(self):
        forged = PRE_FIX_STEP2_TEXT.replace(STEP2_END_MARKER, "3. Next turn.")
        with self.assertRaises(AssertionError):
            _wrapper_invocation_region(forged)

    def test_extractor_fails_when_markers_are_out_of_order(self):
        start = PRE_FIX_STEP2_TEXT.index(STEP2_START_MARKER)
        end = PRE_FIX_STEP2_TEXT.index(STEP2_END_MARKER)
        forged = PRE_FIX_STEP2_TEXT[end:] + PRE_FIX_STEP2_TEXT[start:end]
        with self.assertRaises(AssertionError):
            _wrapper_invocation_region(forged)

    def test_extractor_fails_when_a_marker_occurs_twice(self):
        forged = PRE_FIX_STEP2_TEXT + PRE_FIX_STEP2_TEXT
        with self.assertRaises(AssertionError):
            _wrapper_invocation_region(forged)

    def test_extractor_fails_when_region_is_empty(self):
        forged = STEP2_START_MARKER + "\n" + STEP2_END_MARKER + " text\n"
        with self.assertRaises(AssertionError):
            _wrapper_invocation_region(forged)

    def test_pre_fix_literal_is_non_trivial(self):
        # Guards the twin against becoming vacuous (e.g. truncated).
        self.assertGreater(len(self.pre_fix_region), 1000)
        self.assertTrue(_retains_invocation_form(self.pre_fix_region))

    # --- AC-3: the AC-1 and AC-2 matchers do not match the pre-fix text ----

    def test_ac3_placement_matcher_does_not_match_pre_fix_step2(self):
        self.assertFalse(_states_scratchpad_placement(self.pre_fix_region))

    def test_ac3_prohibition_matcher_does_not_match_pre_fix_step2(self):
        self.assertFalse(
            _states_project_root_and_cwd_prohibitions(self.pre_fix_region)
        )

    def test_ac3_harness_entry_matcher_does_not_match_pre_fix_step2(self):
        self.assertFalse(_rule_governs_both_harness_entries(self.pre_fix_region))

    def test_ac3_each_phrase_is_absent_from_pre_fix_step2(self):
        for phrase in (
            SAVED_OUTPUT_CONDITION_PHRASE,
            SCRATCHPAD_PLACEMENT_PHRASE,
            PROJECT_ROOT_PROHIBITION_PHRASE,
            CWD_RELATIVE_PROHIBITION_PHRASE,
            BOTH_HARNESS_ENTRIES_PHRASE,
        ):
            self.assertNotIn(phrase, self.pre_fix_region)

    def test_ac3_matchers_pass_on_a_region_that_carries_the_rule(self):
        # Non-vacuity: the matchers are not constant-False. A region with the
        # rule sentences appended after the timeout sentence satisfies them.
        rule = (
            "When the output of a `run_codex_exec.sh` call (stdout or stderr) "
            "is saved to a file, that file is placed in the session scratchpad "
            "directory. This holds on every turn, on either harness entry, "
            "including the turns after a mid-consultation move from `codex` to "
            "`litellm`. The file is never written under `{project_root}`, and "
            "the redirect target is never a path relative to the current "
            "directory."
        )
        forged = PRE_FIX_STEP2_TEXT.replace(
            "   A turn whose wrapper call exits non-zero",
            "   " + rule + "\n   A turn whose wrapper call exits non-zero",
        )
        region = _wrapper_invocation_region(forged)
        self.assertTrue(_states_scratchpad_placement(region))
        self.assertTrue(_states_project_root_and_cwd_prohibitions(region))
        self.assertTrue(_rule_governs_both_harness_entries(region))

    def test_ac3_placement_matcher_needs_both_stream_names(self):
        rule = (
            "When the output of a `run_codex_exec.sh` call (stdout or stderr) "
            "is saved to a file, that file is placed in the session scratchpad "
            "directory."
        )
        self.assertTrue(_states_scratchpad_placement(rule))
        self.assertFalse(
            _states_scratchpad_placement(rule.replace("stderr", "output"))
        )
        self.assertFalse(
            _states_scratchpad_placement(rule.replace("stdout", "output"))
        )

    def test_ac3_prohibition_matcher_needs_both_prohibitions(self):
        both = (
            "The file is never written under `{project_root}`, and the "
            "redirect target is never a path relative to the current "
            "directory."
        )
        self.assertTrue(_states_project_root_and_cwd_prohibitions(both))
        self.assertFalse(
            _states_project_root_and_cwd_prohibitions(
                both.replace("never written under", "written under")
            )
        )
        self.assertFalse(
            _states_project_root_and_cwd_prohibitions(
                both.replace("never a path relative", "a path relative")
            )
        )

    # --- AC-7: retention and forbidden-token matchers can fail -------------

    def test_ac7_retention_matcher_fails_when_timeout_sentence_changes(self):
        forged = self.pre_fix_region.replace("600000", "300000")
        self.assertFalse(_retains_invocation_form(forged))

    def test_ac7_retention_matcher_fails_when_a_litellm_value_is_dropped(self):
        forged = self.pre_fix_region.replace(
            "`--litellm muse-spark-contributor`", "`--litellm other`"
        )
        self.assertFalse(_retains_invocation_form(forged))

    def test_ac7_retention_matcher_fails_when_invocation_line_changes(self):
        forged = self.pre_fix_region.replace('-C "{project_root}"', "-C .")
        self.assertFalse(_retains_invocation_form(forged))

    def test_ac7_forbidden_token_matcher_is_clean_on_pre_fix_step2(self):
        self.assertEqual(_forbidden_tokens_in(self.pre_fix_region), [])

    def test_ac7_forbidden_token_matcher_detects_each_forbidden_token(self):
        for sample, expected in (
            ("hit a rate limit", "rate limit"),
            ("on a rate-limit", "rate-limit"),
            ("status 429", "429"),
            ("via OpenRouter", "openrouter"),
            ("see task0042", "taskNNNN"),
            ("`gate_id` is `x.y`", "gate_id literal"),
            ("`gate_id: x.y`", "gate_id literal"),
            ("https://www.notion.so/abc", "notion.so"),
            ("under /home/someone/work", "/home/"),
        ):
            with self.subTest(sample=sample):
                self.assertIn(
                    expected,
                    _forbidden_tokens_in(self.pre_fix_region + " " + sample),
                )

    # --- AC-6 (NFR1): the unguarded-variable check can fail ---------------

    def test_ac6_pre_fix_region_passes_the_variable_check(self):
        self.assertEqual(
            _unguarded_new_variables(self.pre_fix_region, self.pre_fix_region),
            [],
        )

    def test_ac6_bare_redirect_through_undefined_variable_fails_the_check(self):
        # The incident's form: the orchestrator-local `$S` used as the
        # redirect directory.
        forged = (
            self.pre_fix_region
            + " Redirect with `> $S/consult1.out 2> $S/consult1.err`."
        )
        self.assertEqual(
            _unguarded_new_variables(forged, self.pre_fix_region),
            ["$S", "$S"],
        )

    def test_ac6_braced_variable_without_default_fails_the_check(self):
        forged = self.pre_fix_region + " Redirect with `> ${S}/consult1.out`."
        self.assertEqual(
            _unguarded_new_variables(forged, self.pre_fix_region), ["${S}"]
        )

    def test_ac6_guarded_default_form_is_accepted(self):
        forged = (
            self.pre_fix_region
            + " Redirect with `> ${SCRATCH_DIR:-/tmp}/consult1.out`."
        )
        self.assertEqual(_unguarded_new_variables(forged, self.pre_fix_region), [])

    def test_ac6_variable_nested_in_a_guarded_default_is_not_double_counted(self):
        tokens = _shell_variable_tokens("${CODEX_HOME:-$HOME/.codex} and $PROMPT")
        self.assertEqual(tokens, ["${CODEX_HOME:-$HOME/.codex}", "$PROMPT"])


if __name__ == "__main__":
    unittest.main()

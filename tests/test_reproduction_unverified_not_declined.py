"""Tests for task0007 (security-review-repro-steps): on the orchestrator
verification paths of both review phases, an `unverifiable` security finding
whose basis the orchestrator does not confirm by its own reading is recorded
as `unresolved` (reason beginning `unverified`), never `declined`.

Covers task0007 Acceptance Criteria
(feature-docs/security-review-repro-steps/tasks/task0007.md):

- AC-1: em-workflow `review-phase.md` Phase R3b maps an unconfirmed
  `unverifiable` basis to `resolution: unresolved` with a `resolution_reason`
  beginning `unverified`, keeps the "stays a target only when the basis is
  confirmed" rule and the truncation / 4096-byte rule, and no sentence of the
  document maps `unverifiable` / `unverified` to `declined`.
- AC-2: the same for em-review `review-phase.md` Phase R3, whose mapping keeps
  "`unverifiable` -> never declined on that ground alone" and in which the
  phrase "`resolution: declined` with `resolution_reason` beginning
  `unverified`" occurs nowhere.
- AC-3: both documents carry the two shared sentences, byte-identical after
  whitespace normalization, inside their reproduction-verification section and
  after its round-context suppression text.
- AC-4: Phase R4's candidate gate of both documents excludes a finding left
  `unresolved` as `unverified` and does not count it in the residual
  critical/high count; em-review's re-aggregation sentence states the same
  for the loop decision.
- AC-5: Phase R5 of em-workflow records such a finding as `unresolved`, keeps
  it out of `residual_critical_high`, out of the residual findings
  rework-planner receives and out of the batch rework-cap `deferred`
  re-marking; Phase R5 of em-review names it in the `residual_critical_high`
  exclusion and states it is not carried as a decline. Round-context
  suppression of both documents still drops only `declined` entries.
- AC-6: the unchanged outcomes keep their mappings (`not reproduced`, no
  steps, and the merged-finding rule byte-identical to its former text).
- AC-8: this module imports only standard-library modules and carries
  self-checks that forged texts fail their checks.

AC-7 (the three updated test modules, the hash refresh, the pinned counts) is
carried by those modules themselves and by the sibling review-phase suites;
the pinned counts are re-asserted here against the real documents.

Every check is a pure function of the text it receives, so each is paired
with a forged input that must fail it. Phrase checks are whitespace-normalized
and scoped to the section they concern.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"
EM_REVIEW_PATH = REPO_ROOT / "em-review" / "references" / "review-phase.md"
THIS_MODULE_PATH = Path(__file__).resolve()

USER_QUESTION_TOOL = "AskUserQuestion"
WORKFLOW_QUESTION_COUNT = 9
EM_REVIEW_QUESTION_COUNT = 4
EVALUATOR_DISPATCH = 'Task(subagent_type="em-workflow:review-evaluator")'

# The two sentences both verification sections gain (IMPLEMENTATION.md D7),
# whitespace-normalized.
SHARED_START = "An `unverifiable` finding whose basis"
SHARED_END = "the next round verifies it again."
SHARED_SENTENCES = (
    "An `unverifiable` finding whose basis the orchestrator does not confirm "
    "by its own reading is never `declined`: it is recorded with "
    "`resolution: unresolved` and a `resolution_reason` beginning "
    "`unverified`. Such a finding is neither an auto-fix candidate nor "
    "counted in the residual critical/high count, so it is never sent back "
    "for a fix on that ground; round-context suppression does not drop it, "
    "because it is not `declined`, and the next round verifies it again."
)

# The merged-finding rule (D6) as it read before this task; it must stay
# byte-identical in both documents.
MERGED_FINDING_RULE = (
    "For a merged finding, every kept value (`reproduction` and each "
    "`reproduction_alternates` value) is verified, and the finding-level "
    "outcome is decided over them. The finding is `reproduced` when at least "
    "one kept value is reproduced; verification may stop at the first value "
    "that is reproduced. The finding is `not reproduced` only when every kept "
    "value is positively confirmed not to hold and `reproduction_overflow` is "
    "false. Otherwise the finding is `unverifiable`, and overflow is never "
    "grounds for `declined` as `not reproduced`. The effects of each outcome "
    "are unchanged and apply to the finding-level outcome. For example, a "
    "short value that holds, merged with a longer value that does not, leaves "
    "the finding `reproduced` and a target."
)

W_R3B = "## Phase R3b: Mechanical gates on the evaluation"
W_R4 = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
W_R5 = "## Phase R5: Persist the round record"
W_R6 = "## Phase R6: Report (Japanese)"
W_SUPPRESSION_LEAD = "**Round-context suppression**"
W_FLOOR_LEAD = "**Evaluator accountability floor**"
W_VERIFICATION_LEAD = "**Reproduction verification on orchestrator paths**"

E_R3 = "## Phase R3: Aggregate, sanitize, score"
E_R4 = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
E_R5 = "## Phase R5: Persist the round record"
E_R6 = "## Phase R6: Report (Japanese)"
E_SUPPRESSION_LEAD = "**Round-context suppression**"
E_VERIFICATION_LEAD = "**Reproduction verification**"
E_CONFIDENCE = "Confidence:"

GATE_START = "Candidate gate per loop:"
CLASSIFICATION_START = "Classification (mechanical only"


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start + len(start_marker))
    return text[start:end]


def _bold_paragraph(text, lead):
    """The block that starts at the bold `lead` and runs up to the next
    paragraph that itself starts with a bold lead."""
    start = text.index(lead)
    nxt = text.find("\n\n**", start + len(lead))
    return text[start:] if nxt == -1 else text[start:nxt]


def _sentences(text):
    return re.split(r"(?<=\.) ", _norm(text))


def _sentence_with(text, markers):
    """True iff one sentence of `text` contains every marker."""
    for sentence in _sentences(text):
        if all(marker in sentence for marker in markers):
            return True
    return False


class WorkflowDoc:
    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(WORKFLOW_PATH)
        return cls._text

    @classmethod
    def r3b(cls):
        return _slice(cls.text(), W_R3B, W_R4)

    @classmethod
    def suppression(cls):
        return _bold_paragraph(cls.r3b(), W_SUPPRESSION_LEAD)

    @classmethod
    def verification(cls):
        return _bold_paragraph(cls.r3b(), W_VERIFICATION_LEAD)

    @classmethod
    def r4(cls):
        return _slice(cls.text(), W_R4, W_R5)

    @classmethod
    def gate(cls):
        return _slice(cls.r4(), GATE_START, CLASSIFICATION_START)

    @classmethod
    def r5(cls):
        return _slice(cls.text(), W_R5, W_R6)


class EmReviewDoc:
    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(EM_REVIEW_PATH)
        return cls._text

    @classmethod
    def r3(cls):
        return _slice(cls.text(), E_R3, E_R4)

    @classmethod
    def suppression(cls):
        return _slice(cls.r3(), E_SUPPRESSION_LEAD, E_VERIFICATION_LEAD)

    @classmethod
    def verification(cls):
        return _slice(cls.r3(), E_VERIFICATION_LEAD, E_CONFIDENCE)

    @classmethod
    def r4(cls):
        return _slice(cls.text(), E_R4, E_R5)

    @classmethod
    def gate(cls):
        return _slice(cls.r4(), GATE_START, CLASSIFICATION_START)

    @classmethod
    def termination(cls):
        return _slice(cls.r4(), "Loop termination:")

    @classmethod
    def r5(cls):
        return _slice(cls.text(), E_R5, E_R6)

    @classmethod
    def r5_yaml(cls):
        r5 = cls.r5()
        start = r5.index("```yaml")
        end = r5.index("```", start + len("```yaml"))
        return r5[start:end]

    @classmethod
    def carry_over(cls):
        return _slice(
            cls.r5(),
            "**Carry-over of not-reproduced declines**",
            "**Completion gate**",
        )


# ---------------------------------------------------------------------------
# Checks: pure functions of the text they receive (so a forged text can be fed
# to them for the negative proofs).
# ---------------------------------------------------------------------------


def unverifiable_declined_offenders(text):
    """Sentences that map `unverifiable` / `unverified` to `declined`.

    A sentence is an offender when it contains both `unverifi` and `declined`
    without the word "never", at either sentence granularity (split on `.` /
    `;` boundaries, and additionally on `->`); or when the clause that follows
    ", otherwise " / ": otherwise " names `declined` while the sentence talks
    about `unverifi...` (a "never" earlier in the sentence does not excuse a
    decline mapping in its "otherwise" branch)."""
    normalized = _norm(text)
    offenders = []
    for pattern in (r"(?<=[.;]) ", r"(?<=[.;]) |→"):
        for sentence in re.split(pattern, normalized):
            lowered = sentence.lower()
            if "unverifi" in lowered and "declined" in lowered:
                if "never" not in lowered:
                    offenders.append(sentence)
    for sentence in re.split(r"(?<=[.;]) ", normalized):
        if "unverifi" not in sentence.lower():
            continue
        match = re.search(r"[,:] otherwise (.*)", sentence)
        if match and "declined" in match.group(1):
            offenders.append(sentence)
    return offenders


def workflow_unverifiable_bullet(verification):
    """The `unverifiable` bullet of the em-workflow verification paragraph,
    whitespace-normalized."""
    start = verification.index("- `unverifiable`:")
    nxt = verification.find("\n- ", start + 1)
    end = verification.find("\n\n", start + 1)
    candidates = [i for i in (nxt, end) if i != -1]
    stop = min(candidates) if candidates else len(verification)
    return _norm(verification[start:stop])


def workflow_bullet_maps_unconfirmed_to_unresolved(bullet):
    return (
        "stays a target only when the orchestrator confirms the basis by "
        "reading" in bullet
        and "otherwise it is recorded with `resolution: unresolved` and a "
        "`resolution_reason` beginning `unverified`" in bullet
        and "`declined`" not in bullet
    )


def workflow_bullet_keeps_truncation_rule(bullet):
    return (
        "ends in step 4's truncation marker" in bullet
        and "exceeds 4096 bytes" in bullet
        and "is `unverifiable`" in bullet
    )


def em_review_maps_unconfirmed_to_unresolved(verification):
    normalized = _norm(verification)
    return (
        "`unverifiable` → never declined on that ground alone" in normalized
        and "only when the orchestrator confirms the finding's basis by its "
        "own reading" in normalized
        and "otherwise `resolution: unresolved` with `resolution_reason` "
        "beginning `unverified`" in normalized
    )


def old_decline_phrase_absent(text):
    return (
        "`resolution: declined` with `resolution_reason` beginning "
        "`unverified`" not in _norm(text)
    )


def extract_shared(section):
    normalized = _norm(section)
    start = normalized.find(SHARED_START)
    if start == -1:
        return None
    end = normalized.find(SHARED_END, start)
    if end == -1:
        return None
    return normalized[start:end + len(SHARED_END)]


def shared_sentences_match(section):
    return extract_shared(section) == SHARED_SENTENCES


def shared_pair_identical(section_a, section_b):
    a, b = extract_shared(section_a), extract_shared(section_b)
    return a is not None and a == b


def shared_sentences_keep_it_out_of_fix_and_residual(section):
    shared = extract_shared(section)
    if shared is None:
        return False
    return (
        "is neither an auto-fix candidate nor counted in the residual "
        "critical/high count" in shared
        and "is never `declined`" in shared
    )


def in_order(text, markers):
    indices = []
    for marker in markers:
        idx = text.find(marker)
        if idx == -1:
            return False
        indices.append(idx)
    return indices == sorted(indices) and len(set(indices)) == len(indices)


def workflow_gate_excludes_unverified(gate):
    normalized = _norm(gate)
    return (
        "excludes a finding `declined` by reproduction verification" in normalized
        and "the residual critical/high count excludes it too" in normalized
        and _sentence_with(
            gate,
            [
                "`unresolved`",
                "`unverified`",
                "is excluded from the candidate gate",
                "residual critical/high count",
            ],
        )
    )


def em_review_gate_excludes_unverified(gate):
    normalized = _norm(gate)
    return (
        "The candidate gate also excludes a finding declined by reproduction "
        "verification (Phase R3)" in normalized
        and _sentence_with(
            gate,
            [
                "`unresolved`",
                "`unverified`",
                "neither a candidate nor counted in the residual "
                "critical/high count",
            ],
        )
    )


def em_review_reaggregation_excludes_unverified(termination):
    normalized = _norm(termination)
    return (
        "a finding declined by reproduction verification is not counted as "
        "residual." in normalized
        and _sentence_with(
            termination,
            [
                "`unresolved`",
                "`unverified`",
                "not counted as residual",
                "`clean` / `loop-cap` / `no-progress`",
            ],
        )
    )


def workflow_r5_records_unverified(r5):
    return _sentence_with(
        r5,
        [
            "`unverifiable`",
            "`resolution: unresolved`",
            "`resolution_reason` beginning `unverified`",
            "not counted in `residual_critical_high`",
            "not among the residual findings rework-planner receives",
            "not re-marked `deferred` by the batch rework-cap step",
        ],
    )


def em_review_r5_comment_names_unverified(yaml_block):
    match = re.search(r"(?m)^residual_critical_high:.*$", yaml_block)
    if match is None:
        return False
    line = match.group(0)
    return "declined by reproduction verification" in line and "unverified" in line


def em_review_carry_over_states_not_a_decline(carry_over):
    return _sentence_with(
        carry_over,
        [
            "`unresolved`",
            "`unverified`",
            "not carried as a decline",
            "the next run verifies it again",
        ],
    )


def suppression_drops_only_declined(suppression):
    normalized = _norm(suppression)
    return (
        "with resolution `declined`" in normalized
        and "unresolved" not in normalized
        and "unverified" not in normalized
    )


def imported_top_level_modules(source):
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return modules


# ---------------------------------------------------------------------------
# AC-1: em-workflow Phase R3b mapping
# ---------------------------------------------------------------------------


class TestAc1WorkflowMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verification = WorkflowDoc.verification()
        cls.bullet = workflow_unverifiable_bullet(cls.verification)

    def test_slice_is_not_vacuous(self):
        self.assertTrue(self.verification.startswith(W_VERIFICATION_LEAD))
        self.assertTrue(self.bullet.startswith("- `unverifiable`:"))

    def test_unconfirmed_basis_maps_to_unresolved_with_unverified_reason(self):
        self.assertTrue(
            workflow_bullet_maps_unconfirmed_to_unresolved(self.bullet), self.bullet
        )

    def test_truncation_and_4096_byte_rule_is_kept(self):
        self.assertTrue(workflow_bullet_keeps_truncation_rule(self.bullet), self.bullet)

    def test_no_sentence_of_the_document_maps_unverifiable_to_declined(self):
        self.assertEqual(unverifiable_declined_offenders(WorkflowDoc.text()), [])

    def test_every_unverifi_declined_pair_says_never_and_includes_the_overflow_rule(self):
        pairs = [
            s
            for s in re.split(r"(?<=[.;]) ", _norm(WorkflowDoc.text()))
            if "unverifi" in s.lower() and "declined" in s.lower()
        ]
        self.assertTrue(
            all("never" in s.lower() for s in pairs), pairs
        )
        self.assertTrue(
            any("overflow is never grounds for `declined`" in s for s in pairs)
        )


# ---------------------------------------------------------------------------
# AC-2: em-review Phase R3 mapping
# ---------------------------------------------------------------------------


class TestAc2EmReviewMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verification = EmReviewDoc.verification()

    def test_slice_is_not_vacuous(self):
        self.assertTrue(self.verification.startswith(E_VERIFICATION_LEAD))

    def test_unconfirmed_basis_maps_to_unresolved_with_unverified_reason(self):
        self.assertTrue(em_review_maps_unconfirmed_to_unresolved(self.verification))

    def test_old_decline_phrase_occurs_nowhere_in_the_document(self):
        self.assertTrue(old_decline_phrase_absent(EmReviewDoc.text()))

    def test_no_sentence_of_the_document_maps_unverifiable_to_declined(self):
        self.assertEqual(unverifiable_declined_offenders(EmReviewDoc.text()), [])


# ---------------------------------------------------------------------------
# AC-3: shared sentences
# ---------------------------------------------------------------------------


class TestAc3SharedSentences(unittest.TestCase):
    def test_workflow_carries_the_shared_sentences(self):
        self.assertTrue(shared_sentences_match(WorkflowDoc.verification()))

    def test_em_review_carries_the_shared_sentences(self):
        self.assertTrue(shared_sentences_match(EmReviewDoc.verification()))

    def test_the_two_documents_carry_the_same_pair(self):
        self.assertTrue(
            shared_pair_identical(
                WorkflowDoc.verification(), EmReviewDoc.verification()
            )
        )

    def test_workflow_places_them_after_suppression_and_the_merged_rule(self):
        r3b = WorkflowDoc.r3b()
        verification = _norm(WorkflowDoc.verification())
        self.assertTrue(
            in_order(r3b, [W_SUPPRESSION_LEAD, W_VERIFICATION_LEAD, SHARED_START])
        )
        self.assertTrue(
            in_order(
                verification,
                [
                    "leaves the finding `reproduced` and a target.",
                    SHARED_START,
                    "A finding `declined` here is neither an auto-fix candidate",
                ],
            ),
            verification,
        )

    def test_em_review_places_them_after_suppression_and_the_merged_rule(self):
        r3 = EmReviewDoc.r3()
        verification = _norm(EmReviewDoc.verification())
        self.assertTrue(
            in_order(r3, [E_SUPPRESSION_LEAD, E_VERIFICATION_LEAD, SHARED_START])
        )
        self.assertTrue(
            in_order(
                verification,
                [
                    "leaves the finding `reproduced` and a target.",
                    SHARED_START,
                    "A finding declined here is neither an auto-fix candidate",
                ],
            ),
            verification,
        )

    def test_the_shared_sentences_keep_it_out_of_fix_and_residual(self):
        for section in (WorkflowDoc.verification(), EmReviewDoc.verification()):
            self.assertTrue(shared_sentences_keep_it_out_of_fix_and_residual(section))

    def test_the_shared_sentences_occur_once_per_document(self):
        for text in (WorkflowDoc.text(), EmReviewDoc.text()):
            self.assertEqual(_norm(text).count(SHARED_START), 1)


# ---------------------------------------------------------------------------
# AC-4: Phase R4 candidate gate and loop decision
# ---------------------------------------------------------------------------


class TestAc4PhaseR4(unittest.TestCase):
    def test_workflow_gate_excludes_unverified_findings(self):
        self.assertTrue(workflow_gate_excludes_unverified(WorkflowDoc.gate()))

    def test_workflow_gate_keeps_its_existing_conjuncts(self):
        gate = _norm(WorkflowDoc.gate())
        self.assertIn(
            "`severity ∈ {critical, high}` AND `category != spec`", gate
        )
        self.assertIn('`sources != ["claude:evaluator"]`', gate)

    def test_em_review_gate_excludes_unverified_findings(self):
        self.assertTrue(em_review_gate_excludes_unverified(EmReviewDoc.gate()))

    def test_em_review_gate_keeps_its_existing_sentence(self):
        self.assertIn(
            "Candidate gate per loop: `severity ∈ {critical, high}` AND "
            "`category != spec` AND `stable_id ∉ aborted_stable_ids` AND "
            "non-empty suggestion AND `file ∈ changed_files`.",
            _norm(EmReviewDoc.gate()),
        )

    def test_em_review_reaggregation_excludes_unverified_findings(self):
        self.assertTrue(
            em_review_reaggregation_excludes_unverified(EmReviewDoc.termination())
        )


# ---------------------------------------------------------------------------
# AC-5: Phase R5 records and round-context suppression
# ---------------------------------------------------------------------------


class TestAc5PhaseR5AndSuppression(unittest.TestCase):
    def test_workflow_r5_records_unverified_findings_as_unresolved(self):
        self.assertTrue(workflow_r5_records_unverified(WorkflowDoc.r5()))

    def test_workflow_r5_keeps_the_declined_record_sentence(self):
        self.assertIn(
            "A finding `declined` by the orchestrator's reproduction "
            "verification is recorded as an ordinary finding with "
            "`resolution: declined` and its `resolution_reason`.",
            _norm(WorkflowDoc.r5()),
        )

    def test_em_review_r5_comment_names_unverified_findings(self):
        self.assertTrue(em_review_r5_comment_names_unverified(EmReviewDoc.r5_yaml()))

    def test_em_review_carry_over_states_it_is_not_a_decline(self):
        self.assertTrue(
            em_review_carry_over_states_not_a_decline(EmReviewDoc.carry_over())
        )

    def test_em_review_carry_over_keeps_its_existing_statements(self):
        carry_over = _norm(EmReviewDoc.carry_over())
        self.assertIn(
            "verified again only after its file changes since the recorded "
            "`head_commit`",
            carry_over,
        )
        self.assertIn(
            "records written before this feature (no `reproduction`) are read "
            "as before",
            carry_over,
        )

    def test_workflow_suppression_still_drops_only_declined_entries(self):
        self.assertTrue(suppression_drops_only_declined(WorkflowDoc.suppression()))

    def test_em_review_suppression_still_drops_only_declined_entries(self):
        self.assertTrue(suppression_drops_only_declined(EmReviewDoc.suppression()))


# ---------------------------------------------------------------------------
# AC-6: unchanged outcomes
# ---------------------------------------------------------------------------


class TestAc6UnchangedOutcomes(unittest.TestCase):
    def test_workflow_not_reproduced_is_declined_with_prefix(self):
        self.assertIn(
            "- `not reproduced`: `resolution: declined`, with a "
            "`resolution_reason` beginning `not reproduced`.",
            _norm(WorkflowDoc.verification()),
        )

    def test_em_review_not_reproduced_is_declined_with_prefix(self):
        self.assertIn(
            "`not reproduced` → `resolution: declined`, `resolution_reason` "
            "beginning `not reproduced`",
            _norm(EmReviewDoc.verification()),
        )

    def test_workflow_no_steps_judgment_is_unchanged(self):
        self.assertIn(
            "- no steps (`reproduction` null, empty or whitespace-only): the "
            "orchestrator judges whether to address the finding; a finding it "
            "judges not to address is `declined`, with that judgment as the "
            "`resolution_reason`; any other finding stays a target.",
            _norm(WorkflowDoc.verification()),
        )

    def test_em_review_no_steps_judgment_is_unchanged(self):
        self.assertIn(
            "*No steps* (`reproduction` null, empty or whitespace-only) is not "
            "an outcome. The orchestrator judges whether to address the "
            "finding: judged not to address → `resolution: declined` with "
            "that judgment as `resolution_reason`; otherwise the finding "
            "stays a target.",
            _norm(EmReviewDoc.verification()),
        )

    def test_workflow_merged_finding_rule_is_byte_identical(self):
        self.assertIn(MERGED_FINDING_RULE, _norm(WorkflowDoc.verification()))

    def test_em_review_merged_finding_rule_is_byte_identical(self):
        self.assertIn(MERGED_FINDING_RULE, _norm(EmReviewDoc.verification()))

    def test_workflow_reproduced_stays_a_target(self):
        self.assertIn(
            "- `reproduced`: the finding stays a target.",
            _norm(WorkflowDoc.verification()),
        )

    def test_em_review_reproduced_stays_a_target(self):
        self.assertIn(
            "`reproduced` → the finding stays a target.",
            _norm(EmReviewDoc.verification()),
        )


# ---------------------------------------------------------------------------
# AC-7 (pinned counts re-asserted against the real documents)
# ---------------------------------------------------------------------------


class TestAc7PinnedText(unittest.TestCase):
    def test_workflow_user_question_tool_count_is_unchanged(self):
        self.assertEqual(
            WorkflowDoc.text().count(USER_QUESTION_TOOL), WORKFLOW_QUESTION_COUNT
        )

    def test_em_review_user_question_tool_count_is_unchanged(self):
        self.assertEqual(
            EmReviewDoc.text().count(USER_QUESTION_TOOL), EM_REVIEW_QUESTION_COUNT
        )

    def test_no_gate_id_line_or_batch_policies_mention_is_added(self):
        for text in (WorkflowDoc.text(), EmReviewDoc.text()):
            self.assertNotIn("gate_id:", text)
            self.assertNotIn("batch-policies.yaml", text)

    def test_workflow_evaluator_dispatch_literal_occurs_exactly_once(self):
        self.assertEqual(WorkflowDoc.text().count(EVALUATOR_DISPATCH), 1)


# ---------------------------------------------------------------------------
# AC-8: self-checks (forged inputs must fail) and standard-library imports
# ---------------------------------------------------------------------------


class TestAc8SelfChecks(unittest.TestCase):
    # -- a forged `unverifiable` -> `declined` mapping ---------------------

    def test_forged_workflow_bullet_declining_unverifiable_fails(self):
        forged = (
            "- `unverifiable`: the finding stays a target only when the "
            "orchestrator confirms the basis by reading; otherwise it is "
            "`declined`, with a `resolution_reason` beginning `unverified`."
        )
        self.assertFalse(workflow_bullet_maps_unconfirmed_to_unresolved(forged))
        self.assertNotEqual(unverifiable_declined_offenders(forged), [])

    def test_forged_em_review_mapping_declining_unverifiable_fails(self):
        forged = "`unverifiable` → `resolution: declined` with reason `unverified`."
        self.assertFalse(em_review_maps_unconfirmed_to_unresolved(forged))
        self.assertNotEqual(unverifiable_declined_offenders(forged), [])

    def test_forged_never_declined_with_a_declined_otherwise_branch_fails(self):
        forged = (
            "`unverifiable` → never declined on that ground alone: it stays a "
            "target only when the orchestrator confirms the finding's basis by "
            "its own reading, otherwise `resolution: declined` with "
            "`resolution_reason` beginning `unverified`."
        )
        self.assertFalse(old_decline_phrase_absent(forged))
        self.assertFalse(em_review_maps_unconfirmed_to_unresolved(forged))
        self.assertNotEqual(unverifiable_declined_offenders(forged), [])

    def test_the_arrow_split_does_not_hide_a_decline_mapping(self):
        forged = "`unverifiable` → `resolution: declined`, reason `unverified`."
        self.assertNotEqual(unverifiable_declined_offenders(forged), [])

    def test_a_sentence_with_never_and_no_decline_mapping_passes(self):
        ok = (
            "Otherwise the finding is `unverifiable`, and overflow is never "
            "grounds for `declined` as `not reproduced`."
        )
        self.assertEqual(unverifiable_declined_offenders(ok), [])

    def test_a_forged_bullet_without_the_confirmed_basis_rule_fails(self):
        forged = (
            "- `unverifiable`: the finding is recorded with `resolution: "
            "unresolved` and a `resolution_reason` beginning `unverified`."
        )
        self.assertFalse(workflow_bullet_maps_unconfirmed_to_unresolved(forged))

    def test_a_forged_bullet_without_the_truncation_rule_fails(self):
        forged = "- `unverifiable`: the finding stays a target only when confirmed."
        self.assertFalse(workflow_bullet_keeps_truncation_rule(forged))

    # -- shared sentences that differ between the two documents ------------

    def test_forged_pair_that_differs_between_documents_fails(self):
        a = "- " + SHARED_SENTENCES
        b = "- " + SHARED_SENTENCES.replace("never sent back", "sometimes sent back")
        self.assertNotEqual(a, b)
        self.assertTrue(shared_pair_identical(a, "  " + SHARED_SENTENCES))
        self.assertFalse(shared_pair_identical(a, b))
        self.assertFalse(shared_sentences_match(b))

    def test_forged_pair_missing_from_a_document_fails(self):
        self.assertFalse(shared_pair_identical(SHARED_SENTENCES, "nothing here"))
        self.assertFalse(shared_sentences_match("nothing here"))

    def test_forged_pair_with_a_word_changed_fails(self):
        forged = SHARED_SENTENCES.replace("its own reading", "a reading")
        self.assertFalse(shared_sentences_match(forged))

    # -- a version that keeps it as a fix candidate / counts it residual ---

    def test_forged_shared_sentences_keeping_it_a_fix_candidate_fail(self):
        forged = (
            "An `unverifiable` finding whose basis the orchestrator does not "
            "confirm by its own reading is never `declined`: it is recorded "
            "with `resolution: unresolved` and a `resolution_reason` beginning "
            "`unverified`. Such a finding is an auto-fix candidate and counted "
            "in the residual critical/high count, so it is sent back for a fix; "
            "round-context suppression does not drop it, because it is not "
            "`declined`, and the next round verifies it again."
        )
        self.assertFalse(shared_sentences_match(forged))
        self.assertFalse(shared_sentences_keep_it_out_of_fix_and_residual(forged))

    def test_forged_workflow_gate_without_the_exclusion_fails(self):
        forged = (
            "Candidate gate per loop: `severity ∈ {critical, high}`. The "
            "candidate gate also excludes a finding `declined` by reproduction "
            "verification, and the residual critical/high count excludes it "
            "too."
        )
        self.assertFalse(workflow_gate_excludes_unverified(forged))

    def test_forged_workflow_gate_that_keeps_it_a_candidate_fails(self):
        forged = (
            "The candidate gate also excludes a finding `declined` by "
            "reproduction verification, and the residual critical/high count "
            "excludes it too. A finding left `unresolved` as `unverified` is "
            "still a candidate and is counted in the residual critical/high "
            "count."
        )
        self.assertFalse(workflow_gate_excludes_unverified(forged))

    def test_forged_em_review_gate_and_reaggregation_without_it_fail(self):
        self.assertFalse(
            em_review_gate_excludes_unverified(
                "The candidate gate also excludes a finding declined by "
                "reproduction verification (Phase R3): it is neither a "
                "candidate nor counted in the residual critical/high count."
            )
        )
        self.assertFalse(
            em_review_reaggregation_excludes_unverified(
                "The re-aggregation applies Phase R3 step 6's `reproduction` "
                "normalization before the `clean` / `loop-cap` / `no-progress` "
                "decision; a finding declined by reproduction verification is "
                "not counted as residual."
            )
        )

    def test_forged_workflow_r5_counting_it_residual_fails(self):
        forged = (
            "A finding left `unverifiable` without a confirmed basis is "
            "recorded with `resolution: unresolved` and its `resolution_reason` "
            "beginning `unverified`, is counted in `residual_critical_high`, "
            "and is re-marked `deferred` by the batch rework-cap step."
        )
        self.assertFalse(workflow_r5_records_unverified(forged))

    def test_forged_em_review_r5_without_the_unverified_exclusion_fails(self):
        yaml_block = (
            "residual_critical_high: 0    # excludes findings declined by "
            "reproduction verification\n"
        )
        self.assertFalse(em_review_r5_comment_names_unverified(yaml_block))
        self.assertFalse(
            em_review_carry_over_states_not_a_decline(
                "**Carry-over of not-reproduced declines**: a finding declined "
                "as `not reproduced` is carried into later runs."
            )
        )

    def test_forged_suppression_dropping_unresolved_entries_fails(self):
        forged = (
            "**Round-context suppression**: drop any deduped finding whose "
            "`stable_id` appears in `round_context` with resolution `declined` "
            "or `unresolved`."
        )
        self.assertFalse(suppression_drops_only_declined(forged))

    # -- the unchanged merged-finding rule ---------------------------------

    def test_forged_merged_finding_rule_with_a_changed_word_is_not_identical(self):
        forged = MERGED_FINDING_RULE.replace("only when every", "when any")
        self.assertNotEqual(forged, MERGED_FINDING_RULE)
        self.assertNotIn(MERGED_FINDING_RULE, _norm(forged))


class TestAc8StandardLibraryOnly(unittest.TestCase):
    def test_imports_are_standard_library_modules(self):
        stdlib = getattr(sys, "stdlib_module_names", None)
        self.assertIsNotNone(stdlib, "sys.stdlib_module_names unavailable")
        modules = imported_top_level_modules(_read(THIS_MODULE_PATH))
        self.assertTrue(modules, "no imports found")
        self.assertEqual(sorted(m for m in modules if m not in stdlib), [])

    def test_self_check_forged_third_party_import_is_detected(self):
        forged = "import re\nimport yaml\nfrom requests import get\n"
        modules = imported_top_level_modules(forged)
        stdlib = sys.stdlib_module_names
        self.assertEqual(
            sorted(m for m in modules if m not in stdlib), ["requests", "yaml"]
        )


if __name__ == "__main__":
    unittest.main()

"""Tests for task0002 (llm-led-review): the review phase protocol rewired
for one primary reviewer per perspective plus a single Opus evaluator, and
the new `review-evaluator` agent definition.

Covers task0002 Acceptance Criteria
(feature-docs/llm-led-review/tasks/task0002.md):

- AC-1: Phase R2 dispatches exactly one non-Claude primary reviewer per
  selected perspective from the first available `primary_chain` entry,
  dispatches the Claude reviewer only on the no-available-entry branch, and
  the document contains no surviving description of a Claude + cross-model
  parallel double-run or of agreement scoring.
- AC-2: Phase R2b still lists exactly the three retryable skip reasons with
  unchanged advance semantics and the two-fallback cap, keeps the
  one-message-per-hop rule, and states that the evaluator dispatch happens
  only after the walk completes.
- AC-3: a `Phase R3a` section with the pinned heading dispatches
  `em-workflow:review-evaluator` exactly once per round with every input
  field name of IMPLEMENTATION.md's "Evaluator input block", and
  `em-workflow/agents/review-evaluator.md` exists with the pinned
  frontmatter, no `# Task assignment` heading, and no `Write` / `Edit` tool.
- AC-4: a `Phase R3b` section with the pinned heading performs the seven
  ordered checks of IMPLEMENTATION.md D3, and the only confidence
  arithmetic left in the document is the two mechanical corrections -- the
  old agreement-based confidence table and the forced `comprehensive`
  relabel are gone.
- AC-5: the document states the evaluator-failure degradation (the round
  continues from the reviewers' own findings, the evaluator run is recorded
  as failed, the phase does not abort) and that `recommended_action` is
  advice the orchestrator may override; no new AskUserQuestion and no new
  `gate_id` appears.
- AC-6: Phase R5's `perspective_runs` documents the `role` vocabulary and
  an evaluator entry, while the round-record path, file name and every
  downstream-read field are unchanged, and every protected literal of
  IMPLEMENTATION.md D7 is still present verbatim.
- AC-7: this module asserts AC-1..AC-6 against raw file text; both
  `python3 -m unittest discover -s tests` and
  `python3 em-workflow/scripts/check-plugin-invariants.py .` must exit 0
  in this task's worktree (verified by actually running both commands,
  recorded in the implementer report -- a suite cannot assert its own
  full-suite outcome).

This is a documentation task (task0002.md Test Notes): verification is by
structural/textual assertion over review-phase.md's raw text and
review-evaluator.md's frontmatter, following the pattern of
tests/test_review_implement_develop_lock_contracts.py and
tests/test_rework_synthesis_contract.py. Negative assertions (the removed
agreement table, the removed forced relabel, the absence of a second
cross-model dispatch) matter as much as the positive ones -- both are
written below.

Per task0002.md Test Notes: the evaluation contract PATH is asserted as
text inside review-phase.md; the contract file itself
(references/review-evaluation-contract.md) is NOT asserted to exist on disk
-- it is task0001's deliverable and will not be present in this task's
worktree.

Also covers task0006 (rework round 1) Acceptance Criteria
(feature-docs/llm-led-review/tasks/task0006.md), in classes prefixed
`TestTask0006`:

- AC-1: Phase R3b's Evaluator-failure degradation lists exactly two
  triggers (evaluator Task failure, missing required root field), no
  surviving coverage-gate discard of the whole evaluation, and a
  Task-succeeded-but-floor-lifted-sites run is recorded `status: completed`
  plus `degraded: true`, never `status: failed`.
- AC-3: the per-site accountability floor -- `same_site` against neither
  `findings` nor `dismissed_sites` lifts a site individually with the
  pinned values; no `(file, line_bucket)` site reduction survives.
- AC-5: `source_run_ids` has zero occurrences in review-phase.md and in
  `agents/review-evaluator.md`; `sources` is the field name in both, and
  both still state the orchestrator-overwrite / `claude:evaluator`
  fallback rule.
- AC-6: Phase R3b's category gate is equality with the dispatched
  perspective of the finding's source run(s), not set membership, and
  keeps "drop unconditionally" / "never relabel".
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
EVALUATOR_AGENT_PATH = PLUGIN_ROOT / "agents" / "review-evaluator.md"

R2_HEADING = "## Phase R2: Fan-out (ONE message, N Task calls)"
R2B_HEADING = "## Phase R2b: Cross-model fallback (chain walk)"
R3A_HEADING = "## Phase R3a: Evaluation (single Opus evaluator)"
R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
R5_HEADING = "## Phase R5: Persist the round record"
R6_HEADING = "## Phase R6: Report (Japanese)"

EVALUATOR_DISPATCH = 'Task(subagent_type="em-workflow:review-evaluator")'
CODEX_REVIEWER_DISPATCH = 'Task(subagent_type="em-workflow:codex-reviewer")'
VERTEX_REVIEWER_DISPATCH = 'Task(subagent_type="vertex-review:vertex-reviewer")'
CLAUDE_REVIEWER_DISPATCH = 'Task(subagent_type="em-workflow:reviewer")'

# The old scheme's literals that must have no surviving occurrence anywhere
# in the document (AC-1 / AC-4): a Claude + cross-model parallel double-run
# description, and the agreement-based confidence table / forced relabel.
FORBIDDEN_OLD_LITERALS = [
    "gets the cross-model double-run too",
    "force `category = comprehensive`",
    "Confidence: claude+cross-model (any harness) same perspective same_site",
    "cross-model agreement",
]

# IMPLEMENTATION.md Shared Components "Evaluator input block": every field
# name that must appear (as an exact backtick-quoted token) inside Phase R3a.
EVALUATOR_INPUT_FIELDS = [
    "evaluation_contract_path",
    "project_root",
    "review_mode",
    "changed_files",
    "round",
    "cross_validation",
    "perspectives_dispatched",
    "reviewer_outputs",
    "round_context",
    "spec_path",
    "lessons",
    "run_id",
    "perspective",
    "role",
    "status",
    "skip_reason",
    "model",
]

# The unchanged normalization formula block (IMPLEMENTATION.md D3 item 5;
# task0002.md Design: "stays verbatim, including same_site and
# coupling_id"), pinned here byte-for-byte from the pre-task Phase R3.
NORMALIZATION_BLOCK = (
    "title_normalized = sha256(lowercase → strip non-printables → "
    "[^a-z0-9]→space\n"
    "                             → collapse spaces → trim)[:16]"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _has_exact_token(text, token):
    """True iff `token` occurs as an exact inline-code span (backtick
    delimited), not merely as a substring of a longer identifier or of
    surrounding prose (test_worker_contract_docs.py precedent)."""
    pattern = r"`" + re.escape(token) + r"`"
    return re.search(pattern, text) is not None


def _contains_any(text, literals):
    return [lit for lit in literals if lit in text]


class DocumentFixture:
    """Reads review-phase.md once and slices out the sections every test
    class below needs."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r1(cls):
        return _slice(
            cls.text(),
            "## Phase R1: Perspective selection (two layers)",
            R2_HEADING,
        )

    @classmethod
    def r2(cls):
        return _slice(cls.text(), R2_HEADING, R2B_HEADING)

    @classmethod
    def r2b(cls):
        return _slice(cls.text(), R2B_HEADING, R3A_HEADING)

    @classmethod
    def r3a(cls):
        return _slice(cls.text(), R3A_HEADING, R3B_HEADING)

    @classmethod
    def r3b(cls):
        return _slice(cls.text(), R3B_HEADING, R4_HEADING)

    @classmethod
    def r5(cls):
        return _slice(cls.text(), R5_HEADING, R6_HEADING)

    @classmethod
    def r6(cls):
        return _slice(cls.text(), R6_HEADING)


# ---------------------------------------------------------------------------
# AC-1: Phase R2 primary-reviewer dispatch
# ---------------------------------------------------------------------------


class TestAC1PhaseR2PrimaryReviewerDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DocumentFixture.text()
        cls.r1 = DocumentFixture.r1()
        cls.r2 = DocumentFixture.r2()

    def test_r2_heading_present(self):
        self.assertIn(R2_HEADING, self.text)

    def test_walks_primary_chain_from_the_front(self):
        self.assertIn("primary_chain", self.r2)
        self.assertIn("FIRST entry whose harness is available", self.r2)

    def test_codex_and_litellm_primary_dispatch_present(self):
        self.assertIn(CODEX_REVIEWER_DISPATCH, self.r2)
        self.assertIn(VERTEX_REVIEWER_DISPATCH, self.r2)

    def test_claude_reviewer_dispatched_only_on_no_available_entry_branch(self):
        self.assertIn(CLAUDE_REVIEWER_DISPATCH, self.r2)
        no_entry_idx = self.r2.index("No entry of the chain available")
        dispatch_idx = self.r2.index(CLAUDE_REVIEWER_DISPATCH)
        self.assertLess(
            no_entry_idx,
            dispatch_idx,
            "the Claude reviewer dispatch must be introduced by the "
            "no-available-entry branch, not stand alone",
        )
        # And the no-available-entry sentence must be the ONLY thing
        # preceding this dispatch string within the branch -- i.e. no
        # unconditional/parallel dispatch of the Claude reviewer exists
        # elsewhere in R2.
        self.assertEqual(self.r2.count(CLAUDE_REVIEWER_DISPATCH), 1)

    def test_exactly_one_primary_reviewer_per_perspective_stated(self):
        norm = _norm(self.r2)
        self.assertIn("Dispatch exactly ONE primary reviewer", norm)
        self.assertIn("Exactly one primary reviewer runs", norm)

    def test_claude_and_harness_reviewer_are_mutually_exclusive(self):
        self.assertIn("mutually exclusive", self.r2)

    def test_model_passed_through_verbatim_never_substituted(self):
        self.assertIn("never substitute a model of your own choosing", self.r2)

    def test_all_task_calls_go_in_a_single_message(self):
        self.assertIn(
            "All Task calls go in a SINGLE message.", self.r2
        )

    def test_no_second_dispatch_when_cross_validation_fires_r1(self):
        # AC-1 (D2): the Phase R1 sentence describing what firing
        # `cross_validation` CAUSES must no longer describe a second
        # dispatch; it must describe the evaluator high-intensity marker.
        norm = _norm(self.r1)
        self.assertIn("no longer adds a second dispatch", norm)
        self.assertIn("high-intensity for the evaluator", norm)

    def test_document_has_no_surviving_double_run_or_agreement_description(self):
        offenders = _contains_any(self.text, FORBIDDEN_OLD_LITERALS)
        self.assertEqual(offenders, [], f"forbidden old literals found: {offenders}")


# ---------------------------------------------------------------------------
# AC-2: Phase R2b chain walk retargeted at primary reviewers
# ---------------------------------------------------------------------------


class TestAC2PhaseR2bChainWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = DocumentFixture.r2b()

    def test_r2b_heading_unchanged(self):
        self.assertIn(R2B_HEADING, DocumentFixture.text())

    def test_applies_to_r2_primary_reviewer_dispatch(self):
        self.assertIn(
            "Applies to every perspective whose R2 primary-reviewer "
            "dispatch returned",
            self.r2b,
        )

    def test_exactly_three_retryable_skip_reasons_unchanged(self):
        table = (
            "| `skip_reason` | What it means | Advance to |\n"
            "|---|---|---|\n"
            "| `rate_limited` | upstream congestion (Codex rate limit, "
            "Vertex 429) | the next entry in the chain |\n"
            "| `budget_exhausted` | the harness's own budget is spent "
            "(LiteLLM's monthly virtual-key cap) | the next entry of a "
            "**different** harness |\n"
            "| `harness_unavailable` | the harness could not be reached "
            "at all (proxy down, profile broken, wrapper missing) | the "
            "next entry of a **different** harness |"
        )
        self.assertIn(table, self.r2b)
        # Exactly three retryable reasons -- no fourth was added.
        self.assertEqual(self.r2b.count("| the next entry"), 3)

    def test_two_fallback_cap_unchanged(self):
        self.assertIn(
            "**At most 2 fallback dispatches per perspective**", self.r2b
        )

    def test_one_message_per_hop_rule_kept(self):
        self.assertIn(
            "all perspectives falling back at the same hop", _norm(self.r2b)
        )
        self.assertIn("go in ONE message", self.r2b)

    def test_exhausted_chain_triggers_one_claude_fallback_dispatch(self):
        # task0007 AC-1: chain exhaustion (or no eligible entry) now
        # dispatches exactly ONE Claude fallback, after the walk, never
        # concurrently with a harness reviewer.
        self.assertIn(
            "the perspective receives exactly ONE Claude fallback",
            _norm(self.r2b),
        )
        self.assertIn('Task(subagent_type="em-workflow:reviewer")', self.r2b)
        self.assertIn("issued after the walk", _norm(self.r2b))
        self.assertIn(
            "never concurrently with a harness reviewer", _norm(self.r2b)
        )

    def test_old_no_claude_rerun_prohibition_is_gone(self):
        # task0007 AC-1: "the current sentence forbidding a Claude re-run at
        # exhaustion is gone" -- explicit absence check (a document that
        # kept both the old prohibition and the new permission would
        # otherwise pass the positive assertion above).
        self.assertNotIn("a skip contribution, not a Claude re-run", self.r2b)
        self.assertNotIn(
            "the Claude fallback branch is decided in R2 from availability",
            _norm(self.r2b),
        )

    def test_evaluator_dispatch_happens_only_after_walk_completes(self):
        self.assertIn(
            "dispatched only after every selected", _norm(self.r2b)
        )
        self.assertIn("chain walk", self.r2b)
        self.assertIn("has finished", self.r2b)
        # task0007 AC-1: the walk this waits on now includes the
        # chain-exhaustion Claude fallback dispatch, not just the harness
        # hops.
        self.assertIn(
            "including any chain-exhaustion Claude fallback",
            _norm(self.r2b),
        )

    def test_harness_level_failure_carveout_kept(self):
        self.assertIn(
            "A reviewer that fails at the **harness** level never reaches "
            "this table",
            self.r2b,
        )


# ---------------------------------------------------------------------------
# AC-3: Phase R3a + the review-evaluator agent definition
# ---------------------------------------------------------------------------


class TestAC3PhaseR3aAndEvaluatorAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DocumentFixture.text()
        cls.r3a = DocumentFixture.r3a()

    def test_r3a_heading_pinned(self):
        self.assertIn(R3A_HEADING, self.text)

    def test_evaluator_dispatched_exactly_once_per_round(self):
        # Exactly one dispatch site in the WHOLE document, inside R3a.
        self.assertEqual(self.text.count(EVALUATOR_DISPATCH), 1)
        self.assertIn(EVALUATOR_DISPATCH, self.r3a)

    def test_every_evaluator_input_field_name_present(self):
        missing = [
            field
            for field in EVALUATOR_INPUT_FIELDS
            if not _has_exact_token(self.r3a, field)
        ]
        self.assertEqual(missing, [], f"missing input fields in R3a: {missing}")

    def test_evaluator_agent_file_exists(self):
        self.assertTrue(
            EVALUATOR_AGENT_PATH.is_file(),
            f"{EVALUATOR_AGENT_PATH} does not exist",
        )

    def test_evaluator_agent_frontmatter_pinned(self):
        text = _read(EVALUATOR_AGENT_PATH)
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(frontmatter_match, "no frontmatter block found")
        frontmatter = frontmatter_match.group(1)
        self.assertIn("name: review-evaluator", frontmatter)
        self.assertIn("model: opus", frontmatter)
        self.assertIn("effort: xhigh", frontmatter)
        tools_match = re.search(r"^tools:\s*(.+)$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(tools_match, "no tools: line in frontmatter")
        tools = {t.strip() for t in tools_match.group(1).split(",")}
        self.assertEqual(tools, {"Read", "Glob", "Grep", "Bash"})

    def test_evaluator_agent_has_no_task_assignment_heading(self):
        text = _read(EVALUATOR_AGENT_PATH)
        # Byte-identical to check-plugin-invariants.py's
        # TASK_ASSIGNMENT_HEADING_RE.
        self.assertIsNone(re.search(r"(?m)^# Task assignment\s*$", text))

    def test_evaluator_agent_does_not_restate_the_output_object_field_list(self):
        text = _read(EVALUATOR_AGENT_PATH)
        # The contract owns the output object's field list
        # (findings / round_summary / recommended_action / action_rationale)
        # -- the agent prompt must not restate it verbatim as a group.
        self.assertNotIn("round_summary", text)
        self.assertNotIn("action_rationale", text)


# ---------------------------------------------------------------------------
# AC-4: Phase R3b mechanical gates (D3's seven ordered checks)
# ---------------------------------------------------------------------------


class TestAC4PhaseR3bMechanicalGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DocumentFixture.text()
        cls.r3b = DocumentFixture.r3b()

    def test_r3b_heading_pinned(self):
        self.assertIn(R3B_HEADING, self.text)

    def test_seven_ordered_checks_present_in_order(self):
        norm = _norm(self.r3b)
        markers = [
            "`file` lexical check: reject absolute paths",
            "`severity` ∈ {critical, high, medium} else drop.",
            "`category` must equal the dispatched perspective",
            "**drop unconditionally**",
            "Cap `title`/`description`/`suggestion` at 4096 bytes each",
            "`stable_id` recomputed from the unchanged normalization formula",
            "`sources` rebuilt by mapping the evaluator-supplied `sources`",
            "Confidence = the evaluator's value, then the two mechanical corrections",
        ]
        indices = [norm.index(m) for m in markers]
        self.assertEqual(indices, sorted(indices), "the seven checks are out of order")

    def test_category_never_relabeled_forced_comprehensive_relabel_removed(self):
        self.assertIn("never relabel", self.r3b)
        self.assertIn("relabelling launders", self.r3b)
        self.assertIn("keeps its category", self.r3b)
        self.assertNotIn("force `category = comprehensive`", self.r3b)

    def test_normalization_formula_kept_verbatim(self):
        self.assertIn(NORMALIZATION_BLOCK, self.r3b)
        self.assertIn("same_site(a,b) := a.file == b.file", self.r3b)
        self.assertIn("coupling_id  = sha256(file", self.r3b)

    def test_only_two_confidence_corrections_remain(self):
        norm = _norm(self.r3b)
        self.assertIn("+15", norm)
        self.assertIn("cap 100", norm)
        self.assertIn("hard cap `50`", norm)
        self.assertIn("These are the ONLY", norm)
        self.assertNotIn(
            "Confidence: claude+cross-model (any harness) same perspective same_site",
            self.r3b,
        )

    def test_evaluator_failure_degradation_stated(self):
        norm = _norm(self.r3b)
        self.assertIn("Evaluator-failure degradation", norm)
        self.assertIn("does NOT abort or skip the round", norm)
        self.assertIn("status: failed", norm)
        self.assertIn("perspective_runs", norm)

    def test_recommended_action_advisory_stated(self):
        norm = _norm(self.r3b)
        self.assertIn("never a decision", norm)
        self.assertIn("residual_critical_high == 0", norm)
        self.assertIn("--report-only", norm)
        self.assertIn("auto-fix loop cap", norm)
        self.assertIn("batch rework cap", norm)
        self.assertIn("rework-task-synthesis.md` Section 10", norm)


# ---------------------------------------------------------------------------
# AC-5: no new AskUserQuestion / gate_id in the new path
# ---------------------------------------------------------------------------


class TestAC5NoNewGateInTheNewPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new_path = "\n".join(
            [
                DocumentFixture.r2(),
                DocumentFixture.r2b(),
                DocumentFixture.r3a(),
                DocumentFixture.r3b(),
            ]
        )

    def test_no_askuserquestion_dispatch_in_the_new_path(self):
        self.assertNotIn("AskUserQuestion(", self.new_path)

    def test_no_gate_id_declaration_in_the_new_path(self):
        self.assertNotIn("gate_id:", self.new_path)

    def test_r3b_states_writes_commits_gates_stay_orchestrator_exclusive(self):
        norm = _norm(DocumentFixture.r3b())
        self.assertIn(
            "Writes, commits and AskUserQuestion stay orchestrator-exclusive",
            norm,
        )
        self.assertIn("no new AskUserQuestion and no new gate identifier", norm)


# ---------------------------------------------------------------------------
# AC-6: Phase R5 role vocabulary + evaluator entry + D7 protected literals
# ---------------------------------------------------------------------------


class TestAC6PhaseR5RoleVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DocumentFixture.text()
        cls.r5 = DocumentFixture.r5()
        cls.r6 = DocumentFixture.r6()

    def test_r5_heading_unchanged(self):
        self.assertIn(R5_HEADING, self.text)
        self.assertIn(R6_HEADING, self.text)

    def test_role_vocabulary_documented(self):
        norm = _norm(self.r5)
        self.assertIn("`role` field", norm)
        self.assertIn("`primary`", norm)
        self.assertIn("`fallback`", norm)
        self.assertIn("`evaluator`", norm)

    def test_perspective_runs_example_has_role_and_evaluator_entry(self):
        self.assertIn("role: primary", self.r5)
        self.assertIn("role: fallback", self.r5)
        self.assertIn("role: evaluator", self.r5)
        # The evaluator entry has no `perspective` field.
        evaluator_line = next(
            line for line in self.r5.splitlines() if "role: evaluator" in line
        )
        self.assertNotIn("perspective:", evaluator_line)

    def test_source_claude_now_means_fallback(self):
        self.assertIn(
            "`source: claude` on a perspective entry now means the fallback run",
            _norm(self.r5),
        )

    def test_round_record_path_and_file_name_unchanged(self):
        self.assertIn(
            "Write `reviews/round{N}.yaml`", self.r5
        )
        self.assertIn(
            "feature-docs/{feature}/reviews/round{N}.yaml", self.r5
        )

    def test_downstream_read_fields_unchanged(self):
        for field in [
            "stable_id: {id}",
            "severity: high",
            "category: security",
            "file: src/foo.go",
            "line: 42",
            "resolution: fixed",
            "resolution_reason:",
            "residual_critical_high: 0",
            "rework_required: false",
        ]:
            self.assertIn(field, self.r5)

    # -- IMPLEMENTATION.md D7 protected literals --

    def test_d7_fix_commit_lock_literals_present(self):
        self.assertIn("em-workflow-merge.lock", self.text)
        self.assertIn("flock 9", self.text)
        add_idx = self.text.index(
            'git -C "$PROJECT_ROOT" add -A -- "${authorized_files[@]}" || exit 1'
        )
        commit_idx = self.text.index(
            'git -C "$PROJECT_ROOT" commit -m "fix({feature}): review round '
            '{round} loop {N}" || exit 1'
        )
        self.assertLess(add_idx, commit_idx)

    def test_d7_r6_withheld_report_body_unchanged(self):
        self.assertIn("not emitted into the main context", _norm(self.r6))

    def test_d7_r5_rework_ordering_citations_unchanged(self):
        completion_gate_idx = self.r5.index("**Completion gate**")
        batch_mode_idx = self.r5.index("Batch mode (develop-駆動 only): no offer")
        interactive_branch = self.r5[completion_gate_idx:batch_mode_idx]
        batch_branch = self.r5[batch_mode_idx:]
        self.assertIn("rework-task-synthesis.md", interactive_branch)
        self.assertIn("rework-task-synthesis.md", batch_branch)
        self.assertIn("review.needs_rework = true", self.r5)
        self.assertIn("is carried inside that patch", self.r5)


# ---------------------------------------------------------------------------
# Validation-detects-regressions: proof the forbidden-literal scan and the
# evaluator-dispatch-count check fail meaningfully (tdd-testing discipline:
# "a test that can never fail is not a test").
# ---------------------------------------------------------------------------


class TestValidationDetectsRegressions(unittest.TestCase):
    def test_forbidden_literal_scan_flags_a_reintroduced_old_literal(self):
        forged = (
            "some prose ... force `category = comprehensive` ... more prose"
        )
        self.assertEqual(
            _contains_any(forged, FORBIDDEN_OLD_LITERALS),
            ["force `category = comprehensive`"],
        )

    def test_forbidden_literal_scan_is_empty_on_clean_text(self):
        self.assertEqual(_contains_any("clean text with no offenders", FORBIDDEN_OLD_LITERALS), [])

    def test_exact_token_matcher_rejects_substring_only_occurrence(self):
        # Edge case: a field name appearing only as part of a longer word
        # must NOT satisfy the exact-token check.
        self.assertFalse(_has_exact_token("`spec_path_extra` is unrelated", "spec_path"))
        self.assertTrue(_has_exact_token("the `spec_path` field", "spec_path"))

    def test_dispatch_count_matcher_flags_a_second_dispatch(self):
        forged = EVALUATOR_DISPATCH + " ... " + EVALUATOR_DISPATCH
        self.assertEqual(forged.count(EVALUATOR_DISPATCH), 2)


# ---------------------------------------------------------------------------
# task0006 (rework round 1) Acceptance Criteria.
# ---------------------------------------------------------------------------


class TestTask0006AC1EvaluatorFailureDegradationNarrowedTriggers(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.r3b = DocumentFixture.r3b()

    def test_no_coverage_gate_or_whole_evaluation_discard_survives(self):
        lowered = self.r3b.lower()
        self.assertNotIn("evaluator coverage gate", lowered)
        self.assertNotIn("treated as unusable", lowered)
        self.assertNotIn("all-or-nothing", lowered)

    def test_exactly_two_structural_triggers_stated(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "either of exactly two structural triggers fires — the "
            "evaluator's Task failed, or the returned object is missing a "
            "required root field",
            norm,
        )
        self.assertIn("Coverage is never a trigger", norm)

    def test_successful_task_with_lifted_sites_recorded_completed_degraded(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "the evaluator run is instead recorded with `status: "
            "completed` and `degraded: true` in `perspective_runs`",
            norm,
        )
        self.assertIn("never `status: failed`", norm)

    def test_regression_check_old_two_trigger_wording_not_reintroduced_verbatim(self):
        # tdd-testing "a test that can never fail is not a test": prove the
        # exact-triggers assertion above actually discriminates by forging
        # the OLD three-trigger phrasing and confirming it does not match.
        forged = (
            "if the evaluator's Task fails, returns an object missing a "
            "required root field, or fails the coverage gate above"
        )
        self.assertNotIn(
            "either of exactly two structural triggers fires", forged
        )


class TestTask0006AC3AccountabilityFloor(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.r3b = DocumentFixture.r3b()

    def test_floor_heading_present(self):
        self.assertIn("**Evaluator accountability floor**", self.r3b)

    def test_floor_checked_by_same_site_against_findings_and_dismissed_sites(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "that site must appear — by `same_site`, the same predicate "
            "step 5 defines",
            norm,
        )
        self.assertIn(
            "in either the evaluation's `findings` or its `dismissed_sites`",
            norm,
        )

    def test_lifted_site_carries_the_pinned_values(self):
        norm = _norm(self.r3b)
        self.assertIn("lifted into `findings` on its own", norm)
        self.assertIn("the reviewer run's own text", norm)
        self.assertIn("that run's orchestrator-assigned source identity", norm)
        self.assertIn("the dispatching perspective as `category`", norm)
        self.assertIn("confidence `60`", norm)
        self.assertIn("nothing else about the evaluation is discarded", norm)
        self.assertIn("no relabelling occurs", norm)

    def test_all_dismissed_case_lifts_nothing_and_keeps_the_evaluation(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "A round where every reviewer critical/high site is "
            "legitimately dismissed lifts nothing and the evaluation is "
            "kept as-is",
            norm,
        )

    def test_no_file_line_bucket_site_reduction_survives(self):
        self.assertNotIn("(file, line_bucket)", self.r3b)

    def test_same_site_named_as_the_floor_predicate(self):
        idx = self.r3b.index("**Evaluator accountability floor**")
        window = self.r3b[idx : idx + 400]
        self.assertIn("`same_site`", window)


class TestTask0006AC5SourcesRename(unittest.TestCase):
    """AC-5."""

    def test_source_run_ids_has_zero_occurrences_in_review_phase(self):
        self.assertNotIn("source_run_ids", DocumentFixture.text())

    def test_sources_field_and_orchestrator_overwrite_stated_in_review_phase(self):
        text = DocumentFixture.text()
        self.assertTrue(_has_exact_token(text, "sources"))
        norm = _norm(text)
        self.assertIn("orchestrator itself assigned", norm)
        self.assertIn("claude:evaluator", text)

    def test_source_run_ids_has_zero_occurrences_in_evaluator_agent(self):
        text = _read(EVALUATOR_AGENT_PATH)
        self.assertNotIn("source_run_ids", text)


class TestTask0006AC6CategoryGateEquality(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.r3b = DocumentFixture.r3b()

    def test_category_gate_is_equality_with_source_run_dispatched_perspective(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "`category` must equal the dispatched perspective of the "
            "finding's source run(s)",
            norm,
        )
        self.assertNotIn(
            "`category` must be one of THIS round's dispatched perspectives",
            norm,
        )

    def test_no_valid_run_case_still_requires_dispatched_category(self):
        norm = _norm(self.r3b)
        self.assertIn(
            "a finding left with no valid run (attributed to "
            "`claude:evaluator`) must instead carry a category that was "
            "dispatched this round",
            norm,
        )

    def test_still_drop_unconditionally_never_relabel(self):
        self.assertIn("**drop unconditionally**", self.r3b)
        self.assertIn("never relabel", self.r3b)


class TestTask0006EvaluatorAgentDismissedSitesAndInspectionDuty(unittest.TestCase):
    """task0006 AC-2 / AC-4 as they land in agents/review-evaluator.md
    (the contract's own AC-2/AC-4 coverage lives in
    tests/test_review_evaluation_contract.py, which owns the contract
    document; this class owns only the agent file)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(EVALUATOR_AGENT_PATH)

    def test_states_dismissed_sites_accountability_obligation(self):
        self.assertIn("`dismissed_sites`", self.text)
        lowered = self.text.lower()
        self.assertIn("account for", lowered)

    def test_states_independent_inspection_duty(self):
        lowered = self.text.lower()
        self.assertIn("independently inspect", lowered)
        self.assertIn("perspectives_dispatched", self.text)
        self.assertIn("empty findings set", _norm(lowered))

    def test_still_does_not_restate_round_summary_or_action_rationale(self):
        # Re-confirms TestAC3PhaseR3aAndEvaluatorAgent's discipline holds
        # after task0006's additions to this same file.
        self.assertNotIn("round_summary", self.text)
        self.assertNotIn("action_rationale", self.text)


# ---------------------------------------------------------------------------
# AC-7 / test ownership convention: standard-library-only imports.
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


# ---------------------------------------------------------------------------
# task0007 (rework round 1): fallback reachability at chain exhaustion.
#
# Covers task0007 Acceptance Criteria
# (feature-docs/llm-led-review/tasks/task0007.md):
#
# - AC-1: covered above by TestAC2PhaseR2bChainWalk's
#   test_exhausted_chain_triggers_one_claude_fallback_dispatch (the new
#   permission) and test_old_no_claude_rerun_prohibition_is_gone (explicit
#   absence of the removed prohibition).
# - AC-2: the fallback dispatch does not consume the 2-hop harness budget,
#   and every perspective reaching that state in the same round is
#   dispatched in ONE message -- TestAC2FallbackBudgetAndBatching below.
# - AC-4: Phase R5's Unreviewed-perspective disclosure only lists a
#   perspective after its Claude fallback has been dispatched and produced
#   no completed run; field name / root position / present-and-empty rule /
#   non-blocking status stay unchanged; the committed round record is named
#   as the batch-visible channel; no new gate_id -- TestAC4
#   UnreviewedPerspectiveDisclosureAfterFallback below.
# - AC-5: Phase R3a's evaluator input block carries
#   `unreviewed_perspectives`, and Phase R5's `role` note covers both routes
#   to `role: fallback` without adding/redefining any `perspective_runs`
#   field -- TestAC5EvaluatorInputAndRoleNoteWidened below.
# ---------------------------------------------------------------------------


class TestAC2FallbackBudgetAndBatching(unittest.TestCase):
    """AC-2: the chain-exhaustion fallback dispatch does not consume the
    2-hop harness budget, and all perspectives reaching that state in the
    same round go in ONE message (FR9)."""

    @classmethod
    def setUpClass(cls):
        cls.r2b = DocumentFixture.r2b()

    def test_fallback_dispatch_does_not_consume_the_two_hop_budget(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "This dispatch does NOT consume the 2-hop budget above", norm
        )
        self.assertIn("that budget counts harness dispatches", norm)

    def test_perspectives_reaching_exhaustion_state_go_in_one_message(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "every perspective reaching this state in the same round", norm
        )
        self.assertIn("is dispatched in ONE message (FR9)", norm)

    def test_fallback_failure_ends_the_round_unreviewed_but_degrades(self):
        norm = _norm(self.r2b)
        self.assertIn("has no further reviewer to try", norm)
        self.assertIn(
            "the round continues and degrades rather than aborting", norm
        )


class TestAC4UnreviewedPerspectiveDisclosureAfterFallback(unittest.TestCase):
    """AC-4: a perspective is listed in `unreviewed_perspectives` only after
    its Claude fallback has been dispatched and produced no completed run;
    the field's name/position/empty-rule/non-blocking status are unchanged;
    the committed round record is named as the batch-visible channel; no new
    `gate_id` anywhere in the file set."""

    @classmethod
    def setUpClass(cls):
        cls.text = DocumentFixture.text()
        cls.r5 = DocumentFixture.r5()

    def test_disclosure_gated_on_fallback_having_been_dispatched(self):
        norm = _norm(self.r5)
        self.assertIn(
            "a perspective is listed here ONLY after its Phase R2b Claude "
            "fallback",
            norm,
        )
        self.assertIn(
            "has itself been dispatched and produced no `status: "
            "completed` entry",
            norm,
        )

    def test_field_name_root_position_and_empty_rule_unchanged(self):
        self.assertIn(
            "List such perspectives under a round-record-root "
            "`unreviewed_perspectives` field",
            _norm(self.r5),
        )
        self.assertIn(
            "(present and empty when there are none)", self.r5
        )

    def test_non_blocking_status_unchanged(self):
        norm = _norm(self.r5)
        self.assertIn(
            "This is disclosure, not a gate: the step still completes "
            "whenever `residual_critical_high == 0`",
            norm,
        )

    def test_committed_round_record_named_as_batch_visible_channel(self):
        norm = _norm(self.r5)
        self.assertIn("The committed round record `reviews/round{N}.yaml`", norm)
        self.assertIn("does not touch", norm)
        self.assertIn("is the batch-visible channel", norm)

    def test_no_new_gate_id_or_batch_policies_reference_introduced(self):
        self.assertNotIn("gate_id:", self.r5)
        self.assertNotIn("batch-policies.yaml", self.text)


class TestAC5EvaluatorInputAndRoleNoteWidened(unittest.TestCase):
    """AC-5: Phase R3a's evaluator input block lists
    `unreviewed_perspectives`, and Phase R5's `role` note covers both routes
    to `role: fallback` without adding or redefining any `perspective_runs`
    field."""

    @classmethod
    def setUpClass(cls):
        cls.r3a = DocumentFixture.r3a()
        cls.r5 = DocumentFixture.r5()

    def test_r3a_input_block_lists_unreviewed_perspectives(self):
        self.assertTrue(_has_exact_token(self.r3a, "unreviewed_perspectives"))
        norm = _norm(self.r3a)
        self.assertIn(
            "the same list Phase R5 records at the round-record root", norm
        )

    def test_r5_role_note_covers_both_routes_to_fallback(self):
        norm = _norm(self.r5)
        self.assertIn("`fallback`", norm)
        self.assertIn(
            "whether that was decided at Phase R2 fan-out", norm
        )
        self.assertIn(
            "discovered only after Phase R2b's chain walk exhausted every "
            "entry",
            norm,
        )
        self.assertIn("R2b's\nmalformed-result case", self.r5)

    def test_role_note_adds_no_new_perspective_runs_field(self):
        # The role vocabulary itself (primary/fallback/evaluator) is
        # unchanged -- no new role value and no new field name introduced.
        self.assertIn("`role` field: `primary`", self.r5)
        for forbidden in ["`unreviewed`", "`exhausted`"]:
            self.assertNotIn(forbidden, self.r5)


if __name__ == "__main__":
    unittest.main()

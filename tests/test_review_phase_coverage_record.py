"""Text-inspection tests for task0005 of large-diff-review-coverage: Phase
R3b's rescue-run finding rule, Phase R4's per-loop shards and run_ids, and
Phase R5's coverage record in em-workflow/references/review-phase.md.

Acceptance criteria covered (feature-docs/large-diff-review-coverage/tasks/
task0005.md):

- AC-1: Phase R3b states the rescue-run finding rule (scope, the
  missing-implementation judgment with undecidable findings counted as
  missing-implementation, the `unresolved` resolution with a
  `resolution_reason` beginning `unverified`, exclusion from auto-fix
  candidates, the residual count and the rework input, and its application on
  the evaluator path, the evaluator-failure degradation and Phase R4
  re-review).
- AC-2: Phase R4 rebuilds shards from the current diff for each productive
  loop, applies the cap per loop, re-dispatches per shard under the Phase R2b
  rules and records the pass (loop, files its fix changed, manifest).
- AC-3: Phase R4 re-review run_ids follow `loop{N}.{chain_index|fallback}`,
  the Phase R5 example comment states the full run_id grammar, and the old
  `{perspective}#loop{N}` form is gone from Phase R4 and Phase R5.
- AC-4: Phase R5 takes both coverage fields from the `coverage` operation
  over every pass and row, lists every dispatched perspective with no
  completed run whatever its last skip_reason, and shows both root fields
  before the triage-filing block of the YAML example.
- AC-5: the Completion gate paragraph is unchanged, both fields are
  disclosure only, a coverage failure aborts before the record is written,
  and the fields hold project-relative paths only.

The tests slice Phase R3b, Phase R4 and Phase R5 by their headings and match
whitespace-normalized phrases. Every check is a pure function of the text it
receives, so a forged text can be fed to it: each group ends with negative
proofs showing the matcher rejects a forged text. No whole-section digest is
used.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"

R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
R5_HEADING = "## Phase R5: Persist the round record"
R6_HEADING = "## Phase R6: Report (Japanese)"

VERIFICATION_LEAD = "**Reproduction verification on orchestrator paths**"
RESCUE_LEAD = "**Rescue-run findings**"
ADVICE_LEAD = "**`recommended_action` is advice, never a decision**"
GATE_START = "Candidate gate per loop:"
CLASSIFICATION_START = "Classification (mechanical only"
PER_LOOP_LEAD = "Re-review shards and pass record:"
TERMINATION_LEAD = "Loop termination:"
TRIAGE_HEADING = "### Triage filing"
COVERAGE_LEAD = "Before writing the record, the orchestrator runs the `coverage`"
DISCLOSURE_LEAD = "**Unreviewed-perspective disclosure**"
PARTIAL_LEAD = "**Partial-review disclosure**"
ROLE_LEAD = "Rework path (interactive)"
COMPLETION_LEAD = "**Completion gate**"

OLD_LOOP_RUN_ID = "{perspective}#loop{N}"
LOOP_RUN_ID_R4 = "{perspective}[@s{k}]#loop{N}.{chain_index|fallback}"
RUN_ID_GRAMMAR_R5 = "{perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}"


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


def _paragraph(text, lead):
    """The block that starts at `lead` and runs up to the next blank line."""
    start = text.index(lead)
    end = text.find("\n\n", start + len(lead))
    return text[start:] if end == -1 else text[start:end]


def missing_phrases(text, phrases):
    """The phrases that do not occur in the whitespace-normalized `text`."""
    norm = _norm(text)
    return [phrase for phrase in phrases if phrase not in norm]


class Doc:
    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r3b(cls):
        return _slice(cls.text(), R3B_HEADING, R4_HEADING)

    @classmethod
    def rescue(cls):
        return _paragraph(cls.r3b(), RESCUE_LEAD)

    @classmethod
    def r4(cls):
        return _slice(cls.text(), R4_HEADING, R5_HEADING)

    @classmethod
    def gate(cls):
        return _slice(cls.r4(), GATE_START, CLASSIFICATION_START)

    @classmethod
    def per_loop(cls):
        return _paragraph(cls.r4(), PER_LOOP_LEAD)

    @classmethod
    def termination(cls):
        return _slice(cls.r4(), TERMINATION_LEAD, TRIAGE_HEADING)

    @classmethod
    def r5(cls):
        return _slice(cls.text(), R5_HEADING, R6_HEADING)

    @classmethod
    def r5_yaml(cls):
        r5 = cls.r5()
        start = r5.index("```yaml")
        end = r5.index("\n```", start + len("```yaml"))
        return r5[start:end]

    @classmethod
    def coverage_paragraph(cls):
        return _paragraph(cls.r5(), COVERAGE_LEAD)

    @classmethod
    def disclosure(cls):
        return _paragraph(cls.r5(), DISCLOSURE_LEAD)

    @classmethod
    def partial(cls):
        return _paragraph(cls.r5(), PARTIAL_LEAD)

    @classmethod
    def completion_gate(cls):
        return _paragraph(cls.r5(), COMPLETION_LEAD)


# ---------------------------------------------------------------------------
# AC-1: Phase R3b rescue-run finding rule
# ---------------------------------------------------------------------------

RESCUE_SCOPE = [
    "in a pass where spec ran rescue runs",
    "every finding of category `spec` whose `sources` include the identity of "
    "a spec reviewer run is a rescue-run finding",
    "a finding whose only source is the evaluator is out of scope",
]
RESCUE_JUDGMENT = [
    "A missing-implementation finding asserts that the implementation of a "
    "requirement is absent from the visible diff, rather than an error at a "
    "changed location",
    "a finding the orchestrator cannot decide counts as a "
    "missing-implementation finding",
]
RESCUE_RESOLUTION = [
    "A missing-implementation finding is recorded with `resolution: "
    "unresolved` and a `resolution_reason` beginning `unverified`",
]
RESCUE_EXCLUSIONS = [
    "It is not an auto-fix candidate, is not counted in the residual "
    "critical/high count, and is not among the residual findings "
    "rework-planner receives",
]
RESCUE_PATHS = [
    "The same rule runs on the evaluator path, in the evaluator-failure "
    "degradation and on Phase R4 re-review output",
]
RESCUE_TIMING = [
    "It runs at the same point as the reproduction verification above: after "
    "round-context suppression and before the auto-fix candidate gate and "
    "the residual count of Phase R4",
]


class TestAC1RescueRunFindingRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r3b = Doc.r3b()
        cls.par = _norm(Doc.rescue())

    def test_paragraph_follows_the_reproduction_verification_in_r3b(self):
        verification = self.r3b.index(VERIFICATION_LEAD)
        rescue = self.r3b.index(RESCUE_LEAD)
        advice = self.r3b.index(ADVICE_LEAD)
        self.assertLess(verification, rescue)
        self.assertLess(rescue, advice)

    def test_scope_is_spec_findings_with_a_spec_reviewer_source(self):
        self.assertEqual(missing_phrases(self.par, RESCUE_SCOPE), [])

    def test_missing_implementation_judgment_counts_the_undecidable(self):
        self.assertEqual(missing_phrases(self.par, RESCUE_JUDGMENT), [])

    def test_missing_implementation_is_recorded_unresolved_unverified(self):
        self.assertEqual(missing_phrases(self.par, RESCUE_RESOLUTION), [])

    def test_missing_implementation_is_excluded_from_fix_residual_and_rework(
        self,
    ):
        self.assertEqual(missing_phrases(self.par, RESCUE_EXCLUSIONS), [])

    def test_rule_also_runs_on_the_three_other_paths(self):
        self.assertEqual(missing_phrases(self.par, RESCUE_PATHS), [])

    def test_rule_runs_at_the_reproduction_verification_point(self):
        self.assertEqual(missing_phrases(self.par, RESCUE_TIMING), [])

    def test_rule_adds_no_user_question_and_no_gate_identifier(self):
        self.assertEqual(
            missing_phrases(
                self.par, ["no new user question and no new gate identifier"]
            ),
            [],
        )
        self.assertNotIn("AskUserQuestion", self.par)
        self.assertNotIn("gate_id:", self.par)

    def test_negative_proof_a_rule_that_counts_rescue_findings_in_the_residual(
        self,
    ):
        forged = self.par.replace(
            "is not counted in the residual critical/high count",
            "is counted in the residual critical/high count",
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_EXCLUSIONS), [])

    def test_negative_proof_a_rule_that_sends_rescue_findings_to_rework(self):
        forged = self.par.replace(
            "is not among the residual findings rework-planner receives",
            "is among the residual findings rework-planner receives",
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_EXCLUSIONS), [])

    def test_negative_proof_a_rule_that_keeps_rescue_findings_as_fix_candidates(
        self,
    ):
        forged = self.par.replace(
            "It is not an auto-fix candidate", "It is an auto-fix candidate"
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_EXCLUSIONS), [])

    def test_negative_proof_a_scope_that_takes_in_evaluator_only_findings(self):
        forged = self.par.replace(
            "a finding whose only source is the evaluator is out of scope",
            "a finding whose only source is the evaluator is in scope",
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_SCOPE), [])

    def test_negative_proof_an_undecidable_finding_that_is_not_counted(self):
        forged = self.par.replace(
            "counts as a missing-implementation finding",
            "does not count as a missing-implementation finding",
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_JUDGMENT), [])

    def test_negative_proof_a_rule_that_skips_the_evaluator_failure_path(self):
        forged = self.par.replace(
            "in the evaluator-failure degradation and ", ""
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, RESCUE_PATHS), [])


# ---------------------------------------------------------------------------
# AC-2: Phase R4 per-loop shards and the pass record
# ---------------------------------------------------------------------------

PER_LOOP_PHRASES = [
    "before each productive loop's re-review, the orchestrator runs "
    "review-shards again (the Phase R2 step, cited here and not restated) "
    "with the same `diff_base`, `changed_files` and `perspective_count` as "
    "the round's Phase R2 run, so that the shards are rebuilt from the "
    "current diff",
    "It applies the cap again for that loop",
    "dispatches the re-review per shard under the Phase R2b rules per shard, "
    "spec order and rescue runs included",
    "A non-zero exit of that run aborts the review phase before the "
    "re-review is dispatched, and no round record is written",
    "The orchestrator records the pass: the loop number, the files that "
    "loop's fix changed, and the manifest exactly as review-shards returned "
    "it",
]
GATE_PHRASES = [
    "excludes a finding `declined` by reproduction verification",
    "or by the rescue-run finding rule (Phase R3b, \"Rescue-run findings\") "
    "is excluded from the candidate gate and from the residual critical/high "
    "count",
    "In the `file ∈ changed_files` condition, `changed_files` is the round's "
    "full list, not the paths of one shard",
]
PINNED_TERMINATION = (
    "Loop termination: re-run ALL selected reviewers after any productive "
    "loop"
)


class TestAC2PhaseR4PerLoopShards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4 = Doc.r4()
        cls.par = _norm(Doc.per_loop())
        cls.gate = _norm(Doc.gate())
        cls.termination = Doc.termination()

    def test_each_productive_loop_rebuilds_shards_and_records_its_pass(self):
        self.assertEqual(missing_phrases(self.par, PER_LOOP_PHRASES), [])

    def test_the_shard_step_precedes_the_loop_termination_decision(self):
        self.assertLess(
            self.r4.index(PER_LOOP_LEAD), self.r4.index(TERMINATION_LEAD)
        )

    def test_the_pinned_re_run_all_sentence_stays(self):
        self.assertIn(PINNED_TERMINATION, _norm(self.termination))

    def test_candidate_gate_names_the_rescue_rule(self):
        self.assertEqual(missing_phrases(self.gate, GATE_PHRASES), [])

    def test_re_review_findings_also_pass_the_rescue_rule_before_the_decision(
        self,
    ):
        self.assertEqual(
            missing_phrases(
                self.termination,
                [
                    "They also pass the rescue-run finding rule of Phase R3b "
                    "(\"Rescue-run findings\") at the same point, before the "
                    "decision below",
                ],
            ),
            [],
        )

    def test_negative_proof_a_loop_that_reuses_the_loop_0_shards(self):
        forged = self.par.replace(
            "runs review-shards again", "reuses the shards of loop 0"
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, PER_LOOP_PHRASES), [])

    def test_negative_proof_a_loop_that_applies_the_cap_once_per_round(self):
        forged = self.par.replace(
            "It applies the cap again for that loop",
            "It keeps the cap of loop 0",
        )
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, PER_LOOP_PHRASES), [])

    def test_negative_proof_a_pass_record_without_the_fixed_files(self):
        forged = self.par.replace("the files that loop's fix changed, ", "")
        self.assertNotEqual(forged, self.par)
        self.assertNotEqual(missing_phrases(forged, PER_LOOP_PHRASES), [])

    def test_negative_proof_a_gate_that_reads_changed_files_per_shard(self):
        forged = self.gate.replace(
            "`changed_files` is the round's full list, not the paths of one "
            "shard",
            "`changed_files` is the paths of one shard",
        )
        self.assertNotEqual(forged, self.gate)
        self.assertNotEqual(missing_phrases(forged, GATE_PHRASES), [])


# ---------------------------------------------------------------------------
# AC-3: run_id grammar in Phase R4 and Phase R5
# ---------------------------------------------------------------------------


def old_loop_run_id_present(text):
    return OLD_LOOP_RUN_ID in text


class TestAC3RunIdGrammar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4 = Doc.r4()
        cls.r5 = Doc.r5()
        cls.yaml = Doc.r5_yaml()

    def test_phase_r4_re_review_run_id_follows_the_loop_grammar(self):
        self.assertEqual(
            missing_phrases(
                self.r4,
                [
                    "A re-review run's run_id is `" + LOOP_RUN_ID_R4 + "` for "
                    "loop N",
                    "`@s{k}` is present only for a run in a split pass",
                    "the part after `loop{N}.` is the chain index of the "
                    "dispatched entry or `fallback` for the Claude fallback",
                ],
            ),
            [],
        )

    def test_phase_r5_example_comment_states_the_full_grammar(self):
        comment_lines = [
            line for line in self.yaml.splitlines() if line.lstrip().startswith("#")
        ]
        comment = _norm(" ".join(line.lstrip()[1:] for line in comment_lines))
        for phrase in (
            "`" + RUN_ID_GRAMMAR_R5 + "`",
            "`@s{k}`",
            "`loop{N}.`",
            "chain_index",
            "`fallback`",
            "`evaluator`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, comment)

    def test_the_old_loop_form_is_gone_from_phase_r4_and_phase_r5(self):
        self.assertFalse(old_loop_run_id_present(self.r4))
        self.assertFalse(old_loop_run_id_present(self.r5))

    def test_negative_proof_the_old_form_is_detected(self):
        forged = self.r5.replace(
            "`" + RUN_ID_GRAMMAR_R5 + "`", "`" + OLD_LOOP_RUN_ID + "`", 1
        )
        self.assertNotEqual(forged, self.r5)
        self.assertTrue(old_loop_run_id_present(forged))

    def test_negative_proof_the_new_form_does_not_contain_the_old_one(self):
        self.assertFalse(old_loop_run_id_present(LOOP_RUN_ID_R4))
        self.assertFalse(old_loop_run_id_present(RUN_ID_GRAMMAR_R5))


# ---------------------------------------------------------------------------
# AC-4: Phase R5 coverage fields
# ---------------------------------------------------------------------------

COVERAGE_PHRASES = [
    "Before writing the record, the orchestrator runs the `coverage` "
    "operation of `em-workflow/scripts/review-coverage.py` with the round's "
    "`perspectives`",
    "`passes` (every pass of the round: Phase R2 as loop 0 and each Phase R4 "
    "loop, each with its `loop`, `fixed_files` and `manifest`)",
    "`perspective_runs` (every row, as recorded)",
]
FR4_PHRASES = [
    "a perspective is listed here whenever it has no `status: completed` "
    "run, whatever its last `skip_reason` was",
    "excluding any `requires_spec` perspective skipped there because "
    "`spec_available == false`",
    "excluding axis 2's `source: tool` run",
    "copied as given from the `unreviewed_perspectives` output of the "
    "`coverage` operation",
    "List such perspectives under a round-record-root "
    "`unreviewed_perspectives` field",
]
PARTIAL_PHRASES = [
    "the round record also holds a root field "
    "`partially_reviewed_perspectives` (present and empty when there are "
    "none), copied as given from the `partially_reviewed_perspectives` "
    "output of the `coverage` operation",
    "Each entry holds `perspective`, `unreviewed_files` and `reason`",
    "`changed_after_review`, `shard_cap_exceeded`, `run_not_completed` and "
    "`spec_rescue`",
    "A perspective listed in `unreviewed_perspectives` is not listed here "
    "too",
]
OLD_GATED_DISCLOSURE = (
    "a perspective is listed here ONLY after its Phase R2b Claude fallback "
    "(the chain-exhausted case, the malformed-result case, or the "
    "harness-level-failure case) has itself been dispatched and produced no "
    "`status: completed` entry"
)
FORGED_OLD_DISCLOSURE = (
    "**Unreviewed-perspective disclosure** (record-keeping only — never a\n"
    "completion blocker): among perspectives actually dispatched this round in\n"
    "Phase R2, " + OLD_GATED_DISCLOSURE + ". List such perspectives under a\n"
    "round-record-root `unreviewed_perspectives` field (present and empty when\n"
    "there are none)."
)


def lists_only_after_fallback(text):
    return "ONLY after its Phase R2b Claude fallback" in _norm(text)


def root_fields_of_yaml(yaml_block):
    """(name, value-before-comment) of every root-level key of the fenced
    YAML example, in order."""
    fields = []
    for line in yaml_block.splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z_0-9]*):\s*(.*)$", line)
        if match:
            value = match.group(2).partition("#")[0].strip()
            fields.append((match.group(1), value))
    return fields


def coverage_fields_precede_triage_filing(yaml_block):
    fields = root_fields_of_yaml(yaml_block)
    names = [name for name, _ in fields]
    values = dict(fields)
    if "triage_filing" not in names:
        return False
    for name in ("unreviewed_perspectives", "partially_reviewed_perspectives"):
        if name not in names or values[name] != "[]":
            return False
        if names.index(name) > names.index("triage_filing"):
            return False
    return True


FORGED_YAML_AFTER_TRIAGE = (
    "```yaml\n"
    "rework_required: false\n"
    "triage_filing:\n"
    "  executed: false\n"
    "  unattempted_packages: []\n"
    "unreviewed_perspectives: []\n"
    "partially_reviewed_perspectives: []\n"
)
FORGED_YAML_INSIDE_TRIAGE = (
    "```yaml\n"
    "rework_required: false\n"
    "triage_filing:\n"
    "  executed: false\n"
    "  unreviewed_perspectives: []\n"
    "  partially_reviewed_perspectives: []\n"
    "  unattempted_packages: []\n"
)
FORGED_YAML_BEFORE_TRIAGE = (
    "```yaml\n"
    "rework_required: false\n"
    "unreviewed_perspectives: []\n"
    "partially_reviewed_perspectives: []\n"
    "triage_filing:\n"
    "  executed: false\n"
    "  unattempted_packages: []\n"
)


class TestAC4PhaseR5CoverageFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = Doc.r5()
        cls.yaml = Doc.r5_yaml()
        cls.coverage = _norm(Doc.coverage_paragraph())
        cls.disclosure_raw = Doc.disclosure()
        cls.disclosure = _norm(cls.disclosure_raw)
        cls.partial = _norm(Doc.partial())

    def test_coverage_operation_runs_over_every_pass_and_every_row(self):
        self.assertEqual(missing_phrases(self.coverage, COVERAGE_PHRASES), [])

    def test_coverage_operation_runs_before_the_record_is_written(self):
        self.assertLess(
            self.r5.index(COVERAGE_LEAD),
            self.r5.index("Write `reviews/round{N}.yaml`"),
        )

    def test_unreviewed_lists_every_dispatched_perspective_without_a_completed_run(
        self,
    ):
        self.assertEqual(missing_phrases(self.disclosure, FR4_PHRASES), [])

    def test_unreviewed_is_not_gated_on_the_claude_fallback_dispatch(self):
        self.assertFalse(lists_only_after_fallback(self.r5))
        self.assertNotIn("ONLY after", _norm(self.disclosure))

    def test_partial_field_is_a_root_field_with_the_three_entry_keys(self):
        self.assertEqual(missing_phrases(self.partial, PARTIAL_PHRASES), [])

    def test_both_fields_precede_the_triage_filing_block_in_the_example(self):
        self.assertTrue(coverage_fields_precede_triage_filing(self.yaml))

    def test_both_fields_sit_after_rework_required_in_the_example(self):
        names = [name for name, _ in root_fields_of_yaml(self.yaml)]
        self.assertLess(
            names.index("rework_required"), names.index("unreviewed_perspectives")
        )
        self.assertLess(
            names.index("unreviewed_perspectives"),
            names.index("partially_reviewed_perspectives"),
        )

    def test_negative_proof_a_disclosure_listing_only_after_the_fallback(self):
        forged_r5 = self.r5.replace(self.disclosure_raw, FORGED_OLD_DISCLOSURE)
        self.assertNotEqual(forged_r5, self.r5)
        self.assertTrue(lists_only_after_fallback(forged_r5))
        forged = _paragraph(forged_r5, DISCLOSURE_LEAD)
        self.assertNotEqual(missing_phrases(forged, FR4_PHRASES), [])

    def test_negative_proof_a_disclosure_that_drops_the_skip_reason_clause(self):
        forged = self.disclosure.replace(
            "whatever its last `skip_reason` was", "when it was skipped"
        )
        self.assertNotEqual(forged, self.disclosure)
        self.assertNotEqual(missing_phrases(forged, FR4_PHRASES), [])

    def test_negative_proof_a_disclosure_that_lists_the_axis_2_tool_run(self):
        forged = self.disclosure.replace(
            "excluding axis 2's `source: tool` run",
            "including axis 2's `source: tool` run",
        )
        self.assertNotEqual(forged, self.disclosure)
        self.assertNotEqual(missing_phrases(forged, FR4_PHRASES), [])

    def test_negative_proof_a_partial_field_derived_by_hand(self):
        forged = self.partial.replace(
            "copied as given from the `partially_reviewed_perspectives` "
            "output of the `coverage` operation",
            "worked out by the orchestrator",
        )
        self.assertNotEqual(_norm(forged), _norm(self.partial))
        self.assertNotEqual(missing_phrases(forged, PARTIAL_PHRASES), [])

    def test_negative_proof_new_fields_after_the_triage_filing_block(self):
        self.assertFalse(
            coverage_fields_precede_triage_filing(FORGED_YAML_AFTER_TRIAGE)
        )

    def test_negative_proof_new_fields_inside_the_triage_filing_block(self):
        self.assertFalse(
            coverage_fields_precede_triage_filing(FORGED_YAML_INSIDE_TRIAGE)
        )

    def test_non_vacuity_a_well_formed_example_passes_the_order_check(self):
        self.assertTrue(
            coverage_fields_precede_triage_filing(FORGED_YAML_BEFORE_TRIAGE)
        )


# ---------------------------------------------------------------------------
# AC-5: gate unchanged, disclosure only, abort before the record, paths
# ---------------------------------------------------------------------------

COMPLETION_GATE_TEXT = (
    "**Completion gate**: the review step may be marked `completed` ONLY when "
    "`residual_critical_high == 0`. Otherwise: offer another round / rework / "
    "explicit user acceptance (recorded as `deferred` with reason — this is "
    "the opt-out that keeps committed records free of undisclosed critical "
    "items). Batch mode: same rule, recorded as `deferred` per "
    "`references/batch-mode.md`'s Non-packet gates table (gate "
    "`review.residual-critical-high`) rather than offered interactively."
)
DISCLOSURE_ONLY_PHRASES = [
    "This is disclosure only: it adds no gate, no gate identifier and no "
    "question, and the completion gate above is unchanged",
]
ABORT_PHRASES = [
    "A non-zero exit aborts the review phase before the round record is "
    "written; a record without both coverage fields is never written",
]
PATH_PHRASES = [
    "Both coverage fields hold project-relative paths and perspective names "
    "only, never an absolute path and never reviewer-written text",
]
UNREVIEWED_DISCLOSURE_GATE_PHRASES = [
    "This is disclosure, not a gate: the step still completes whenever "
    "`residual_critical_high == 0`",
]


def has_absolute_home_path(text):
    return re.search(r"(?:/home/|/Users/|~/)", text) is not None


class TestAC5GateAndDisclosureOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = Doc.r5()
        cls.coverage = _norm(Doc.coverage_paragraph())
        cls.disclosure = _norm(Doc.disclosure())
        cls.partial = _norm(Doc.partial())
        cls.gate_par = Doc.completion_gate()

    def test_completion_gate_paragraph_is_unchanged(self):
        self.assertEqual(_norm(self.gate_par), COMPLETION_GATE_TEXT)

    def test_unreviewed_disclosure_still_completes_on_zero_residual(self):
        self.assertEqual(
            missing_phrases(self.disclosure, UNREVIEWED_DISCLOSURE_GATE_PHRASES),
            [],
        )

    def test_partial_disclosure_is_disclosure_only(self):
        self.assertEqual(
            missing_phrases(self.partial, DISCLOSURE_ONLY_PHRASES), []
        )

    def test_a_coverage_failure_aborts_before_the_record_is_written(self):
        self.assertEqual(missing_phrases(self.coverage, ABORT_PHRASES), [])
        self.assertEqual(
            missing_phrases(
                self.coverage, ["adds no question and no gate identifier"]
            ),
            [],
        )

    def test_fields_hold_project_relative_paths_only(self):
        self.assertEqual(missing_phrases(self.partial, PATH_PHRASES), [])
        for text in (self.coverage, self.disclosure, self.partial):
            self.assertFalse(has_absolute_home_path(text))

    def test_no_gate_identifier_or_batch_policy_reference_is_added(self):
        self.assertNotIn("gate_id:", self.r5)
        self.assertNotIn("batch-policies.yaml", self.r5)

    def test_rescue_findings_are_not_re_marked_deferred_by_the_rework_cap(self):
        self.assertEqual(
            missing_phrases(
                self.r5,
                [
                    "A missing-implementation finding of a spec rescue run "
                    "(Phase R3b, \"Rescue-run findings\") is recorded the "
                    "same way: `resolution: unresolved` with a "
                    "`resolution_reason` beginning `unverified`, not counted "
                    "in `residual_critical_high`, not among the residual "
                    "findings rework-planner receives, and not re-marked "
                    "`deferred` by the batch rework-cap step",
                ],
            ),
            [],
        )

    def test_negative_proof_a_completion_gate_with_an_added_condition(self):
        forged = COMPLETION_GATE_TEXT.replace(
            "`residual_critical_high == 0`",
            "`residual_critical_high == 0` AND `unreviewed_perspectives == []`",
            1,
        )
        self.assertNotEqual(forged, COMPLETION_GATE_TEXT)
        self.assertNotEqual(_norm(forged), _norm(self.gate_par))

    def test_negative_proof_a_partial_field_that_blocks_completion(self):
        forged = self.partial.replace(
            "This is disclosure only: it adds no gate, no gate identifier and "
            "no question",
            "This is a gate",
        )
        self.assertNotEqual(_norm(forged), _norm(self.partial))
        self.assertNotEqual(
            missing_phrases(forged, DISCLOSURE_ONLY_PHRASES), []
        )

    def test_negative_proof_a_coverage_failure_that_still_writes_the_record(
        self,
    ):
        forged = self.coverage.replace(
            "aborts the review phase before the round record is written",
            "is ignored and the round record is written",
        )
        self.assertNotEqual(_norm(forged), _norm(self.coverage))
        self.assertNotEqual(missing_phrases(forged, ABORT_PHRASES), [])

    def test_negative_proof_an_absolute_home_path_is_detected(self):
        self.assertTrue(has_absolute_home_path("src/a.py and /home/dev/x.py"))
        self.assertFalse(has_absolute_home_path("src/a.py and src/b.py"))


if __name__ == "__main__":
    unittest.main()

"""Document tests for worker-self-write-digest task0003.

The three dispatch sites (the design step branch of `skills/develop/SKILL.md`,
`references/phases/create-plan-phase.md` and
`references/rework-task-synthesis.md`) record the dispatch-time map, run the
self-write script after scope verification, compare (or validate) against the
substituted digest_source, persist the self-write set and, on a resumed
create-plan run, apply the persisted substitution. Each site cites Rule R1
(`references/contracts/worker-envelope.md`, "Recomputation and comparison
timing") instead of restating it.

Covers task0003's Acceptance Criteria
(feature-docs/worker-self-write-digest/tasks/task0003.md):

- AC-1 (FR7, FR8, FR10): the design step branch.
- AC-2 (FR5, FR7, FR8, FR10): create-plan sections 4, 8 and 9.
- AC-3 (FR6, TM-4): create-plan section 3.
- AC-4 (FR5, FR7, FR8, FR10): rework section 10.
- AC-5 (NFR3, NFR6): `dispatch_digest_wiring` on the real repository, the
  registered sections' artifact-digest citations, and no restatement of the
  matrix or the substitution at any site (each cites R1).
- AC-6 (NFR4): the whole suite (not a test of its own).

Method (the task plan's Test Notes): slice by heading, whitespace-normalize,
compare the first positions of named tokens for "in this order". Never
full-document equality and never a line-break position. Every absence
assertion is paired with a forged-text case proving its matcher would fire.
The tests assert this task's citation text only; they never assert that the
script file exists or that R1 already states the new rule (both land in other
worktrees). Standard library only.
"""

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
REWORK_SYNTHESIS_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
CHECKER_PATH = PLUGIN_ROOT / "scripts" / "check-plugin-invariants.py"

SCRIPT_TOKEN = "scripts/self-write-digest.py"
ENVELOPE_PATH_TOKEN = "references/contracts/worker-envelope.md"
R1_TOKENS = (ENVELOPE_PATH_TOKEN, "Rule R1", "Recomputation and comparison timing")
OWNER_CITATION = "references/artifact-digest.md"
GIT_HASH_OBJECT = "git hash-object"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Helpers (document slicing and matchers)
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-normalize: any run of whitespace becomes one space."""
    return " ".join(text.split())


def _squash(text):
    """Remove all whitespace, lowercase. Makes token comparison immune to
    where a document wraps a line (Japanese text wraps with no space)."""
    return "".join(text.split()).lower()


def _has(text, token):
    return _squash(token) in _squash(text)


def _pos(text, token):
    """First position of `token` in the squashed text, or -1."""
    return _squash(text).find(_squash(token))


def _headings(text):
    found = []
    in_fence = False
    for idx, line in enumerate(text.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((idx, len(match.group(1)), match.group(2)))
    return found


def _section(text, title, level):
    """The body of the one level-`level` heading titled `title`, up to the
    next heading of the same or a higher level."""
    lines = text.splitlines()
    heads = _headings(text)
    hits = [(i, h) for i, h in enumerate(heads) if h[2] == title and h[1] == level]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one level-{level} heading {title!r}, found {len(hits)}"
        )
    pos, (start, lvl, _title) = hits[0]
    end = len(lines)
    for nxt_line, nxt_lvl, _nxt in heads[pos + 1:]:
        if nxt_lvl <= lvl:
            end = nxt_line
            break
    return "\n".join(lines[start + 1:end])


def _numbered_item(text, number):
    """The list item that starts with `<number>. ` at column 0, up to the next
    unindented non-blank line."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{number}\.\s", line):
            start = i
            break
    if start is None:
        raise AssertionError(f"no list item numbered {number}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.strip() and not line[0].isspace():
            end = j
            break
    return "\n".join(lines[start:end])


def _paragraphs(text):
    return [b for b in re.split(r"\n\s*\n", text) if b.strip()]


def _paragraph_with(text, token):
    """The blank-line-delimited block that contains `token`."""
    for block in _paragraphs(text):
        if _has(block, token):
            return block
    raise AssertionError(f"no paragraph contains {token!r}")


def _sentences(text):
    """Sentences of the whitespace-normalized text (split on the Japanese
    full stop or on a period followed by a space)."""
    return [s for s in re.split(r"。|(?<=[.!?])\s+", _norm(text)) if s.strip()]


def _sentence_with(text, *tokens):
    """The first sentence that contains every one of `tokens`."""
    for sentence in _sentences(text):
        if all(_has(sentence, t) for t in tokens):
            return sentence
    raise AssertionError(f"no sentence contains all of {tokens!r}")


def _assert_in_order(testcase, text, tokens, label):
    positions = [(t, _pos(text, t)) for t in tokens]
    for tok, pos in positions:
        testcase.assertGreaterEqual(pos, 0, f"{label}: {tok!r} not found")
    ordered = [p for _t, p in positions]
    testcase.assertEqual(
        ordered, sorted(set(ordered)),
        f"{label}: tokens are not in the required order: {positions}",
    )


def _assert_cites_r1(testcase, text, label):
    for token in R1_TOKENS:
        testcase.assertTrue(
            _has(text, token), f"{label}: R1 citation lacks {token!r}"
        )


# Negative probes for "no restatement" (NFR6). The matrix is stated only in
# R1; so is the substitution. A site that re-words either would carry
# action-by-kind wording or the substitution's absent-key wording.
MATRIX_PROBES = (
    re.compile(r"\bnot a member\b", re.I),
    re.compile(r"\bmember only when\b", re.I),
    re.compile(
        r"`(?:create|replace_own|replace_authorized|extend_only|regenerate|preserve)`"
        r"[^.]{0,80}\b(?:created|modified|deleted)\b",
        re.I,
    ),
)
SUBSTITUTION_PROBES = (
    re.compile(r"\babsent key\b", re.I),
    re.compile(r"\bis absent from\b", re.I),
    re.compile(r"\bholds the dispatch-time (?:value|digest)\b", re.I),
    re.compile(r"dispatch\s*時点?の値に置き換え"),
)


def _restatement_hits(text):
    flat = _norm(text)
    return [p.pattern for p in MATRIX_PROBES + SUBSTITUTION_PROBES if p.search(flat)]


# ---------------------------------------------------------------------------
# Documents and slices (read once)
# ---------------------------------------------------------------------------

_DEVELOP = _read(DEVELOP_SKILL_PATH)
_CREATE_PLAN = _read(CREATE_PLAN_PATH)
_REWORK = _read(REWORK_SYNTHESIS_PATH)

DESIGN_BRANCH = _section(_DEVELOP, "design ステップ分岐", 3)
DESIGN_STEP_4 = _numbered_item(DESIGN_BRANCH, 4)
DESIGN_STEP_5 = _numbered_item(DESIGN_BRANCH, 5)

CP_SECTION_3 = _section(_CREATE_PLAN, "3. Reconcile on entry", 2)
CP_SECTION_4 = _section(_CREATE_PLAN, "4. Planner dispatch", 2)
CP_SECTION_8 = _section(_CREATE_PLAN, "8. Validation", 2)
CP_SECTION_9 = _section(
    _CREATE_PLAN,
    "9. Planning invariants — the validator-implemented subset, and human review for the rest",
    2,
)

RW_SECTION_10 = _section(_REWORK, "10. Workflow state transition", 2)

SITE_SLICES = (
    ("design step branch", DESIGN_BRANCH),
    ("create-plan section 3", CP_SECTION_3),
    ("create-plan section 4", CP_SECTION_4),
    ("create-plan section 8", CP_SECTION_8),
    ("create-plan section 9", CP_SECTION_9),
    ("rework section 10", RW_SECTION_10),
)


# ---------------------------------------------------------------------------
# AC-1: the design step branch
# ---------------------------------------------------------------------------


class TestAC1DesignStepBranch(unittest.TestCase):
    """AC-1 (FR7, FR8, FR10; TS-11, TS-12; TM-4)."""

    def test_ac1_dispatch_step_records_dispatch_digest_inputs(self):
        self.assertTrue(_has(DESIGN_STEP_4, "dispatch_digest_inputs"))
        self.assertTrue(_has(DESIGN_STEP_4, "worker_runs"))
        self.assertTrue(_has(DESIGN_STEP_4, "phase-state/design.yaml"))

    def test_ac1_dispatch_step_points_at_phase_state_for_the_field(self):
        sentence = _sentence_with(DESIGN_STEP_4, "dispatch_digest_inputs")
        self.assertTrue(_has(sentence, "references/phase-state.md"), sentence)

    def test_ac1_script_is_named_after_scope_verification_before_layer_5(self):
        _assert_in_order(
            self,
            DESIGN_STEP_5,
            ["Scope verification", SCRIPT_TOKEN, "Layer 5 recording"],
            "design step 5",
        )

    def test_ac1_step_5_names_the_identify_and_substitute_operation(self):
        self.assertTrue(_has(DESIGN_STEP_5, "identify_and_substitute"))

    def test_ac1_step_5_cites_rule_r1_with_the_timing_paragraph(self):
        _assert_cites_r1(self, DESIGN_STEP_5, "design step 5")

    def test_ac1_step_5_says_mismatch_or_nonzero_exit_is_stale(self):
        tail = DESIGN_STEP_5[DESIGN_STEP_5.index("self-write-digest.py"):]
        for token in ("不一致", "終了コード", "stale"):
            self.assertTrue(_has(tail, token), f"{token!r} missing after the script")
        sentence = _sentence_with(tail, "不一致", "終了コード", "stale")
        self.assertTrue(_has(sentence, "input_digest"), sentence)

    def test_ac1_stale_handling_points_at_scope_verification_section(self):
        sentence = _sentence_with(DESIGN_STEP_5, "stale", "終了コード")
        rest = DESIGN_STEP_5[DESIGN_STEP_5.index("self-write-digest.py"):]
        self.assertTrue(
            _has(rest, "references/phases/create-spec-phase.md"), sentence
        )

    def test_ac1_self_write_set_shares_the_layer_5_phase_state_write(self):
        sentence = _sentence_with(DESIGN_STEP_5, "self_write_set", "artifacts")
        self.assertTrue(_has(sentence, "同一の phase-state 書き込み"), sentence)

    def test_ac1_self_write_set_is_recorded_before_artifact_verification(self):
        _assert_in_order(
            self,
            DESIGN_STEP_5,
            ["self_write_set", "成果物", "completed_at_commit"],
            "design step 5",
        )

    def test_ac1_orchestrator_is_the_actor(self):
        self.assertTrue(_has(DESIGN_STEP_5, "オーケストレーター"))


# ---------------------------------------------------------------------------
# AC-2: create-plan sections 4, 8 and 9
# ---------------------------------------------------------------------------


class TestAC2Section4PlannerDispatch(unittest.TestCase):
    """AC-2 (FR7; TS-11): create-plan section 4."""

    def test_ac2_section_4_records_dispatch_digest_inputs(self):
        self.assertTrue(_has(CP_SECTION_4, "dispatch_digest_inputs"))
        self.assertTrue(_has(CP_SECTION_4, "worker_runs"))

    def test_ac2_section_4_points_at_phase_state_for_the_field(self):
        sentence = _sentence_with(CP_SECTION_4, "dispatch_digest_inputs")
        self.assertTrue(_has(sentence, "references/phase-state.md"), sentence)


class TestAC2Section8Validation(unittest.TestCase):
    """AC-2 (FR5, FR8, FR10; TS-2, TS-11): create-plan section 8."""

    @classmethod
    def setUpClass(cls):
        cls.SEQUENCE = _paragraph_with(CP_SECTION_8, SCRIPT_TOKEN)

    def test_ac2_section_8_order_scope_script_validator_layer_5(self):
        _assert_in_order(
            self,
            self.SEQUENCE,
            [
                "scope verification",
                SCRIPT_TOKEN,
                "validate-worker-output.py",
                "Layer 5 recording",
                "self_write_set",
            ],
            "create-plan section 8",
        )

    def test_ac2_section_8_runs_the_identify_and_substitute_operation(self):
        self.assertTrue(_has(self.SEQUENCE, "identify_and_substitute"))

    def test_ac2_section_8_validator_run_takes_the_substituted_digest_source(self):
        after_script = self.SEQUENCE[self.SEQUENCE.index("self-write-digest.py"):]
        sentence = _sentence_with(
            after_script, "validate-worker-output.py", "--digest-source",
            "substituted digest_source",
        )
        self.assertTrue(sentence)

    def test_ac2_section_8_cites_rule_r1_with_the_timing_paragraph(self):
        _assert_cites_r1(self, self.SEQUENCE, "create-plan section 8")

    def test_ac2_section_8_says_mismatch_or_nonzero_exit_is_stale(self):
        after_script = self.SEQUENCE[self.SEQUENCE.index("self-write-digest.py"):]
        sentence = _sentence_with(after_script, "stale", "exit")
        self.assertTrue(_has(sentence, "0"), sentence)

    def test_ac2_section_8_self_write_set_shares_the_layer_5_write(self):
        sentence = _sentence_with(self.SEQUENCE, "self_write_set", "Layer 5 recording")
        self.assertTrue(_has(sentence, "same phase-state write"), sentence)

    def test_ac2_section_8_orchestrator_is_the_actor(self):
        self.assertTrue(_has(self.SEQUENCE, "orchestrator"))



class TestAC2Section9CanonicalInvocation(unittest.TestCase):
    """AC-2 (FR5; TS-2): create-plan section 9."""

    def test_ac2_section_9_names_the_substituted_digest_source_for_the_flag(self):
        after_block = CP_SECTION_9.split("```")[-1]
        sentence = _sentence_with(
            after_block, "--digest-source", "substituted digest_source", "returned"
        )
        self.assertTrue(_has(sentence, "self-write-digest.py"), sentence)

    def test_ac2_section_9_canonical_command_block_is_unchanged(self):
        self.assertIn("--digest-source {digest-source.json}", CP_SECTION_9)
        self.assertIn("--dry-run-apply", CP_SECTION_9)


# ---------------------------------------------------------------------------
# AC-3: create-plan section 3 (resume)
# ---------------------------------------------------------------------------


class TestAC3CreatePlanResume(unittest.TestCase):
    """AC-3 (FR6; TS-8, TS-11; TM-4)."""

    @classmethod
    def setUpClass(cls):
        cls.RESUME = _paragraph_with(CP_SECTION_3, "substitute_only")

    def test_ac3_resume_comparison_uses_substitute_only(self):
        sentence = _sentence_with(self.RESUME, "substitute_only", "last_input_digest")
        self.assertTrue(sentence)

    def test_ac3_pending_patch_rule_1_check_uses_substitute_only(self):
        sentence = _sentence_with(self.RESUME, "substitute_only", "pending patch")
        self.assertTrue(_has(sentence, "rule 1"), sentence)

    def test_ac3_persisted_fields_are_selected_per_phase_state(self):
        self.assertTrue(_has(self.RESUME, "dispatch_digest_inputs"))
        self.assertTrue(_has(self.RESUME, "self_write_set"))
        self.assertTrue(_has(self.RESUME, "references/phase-state.md"))

    def test_ac3_artifact_body_comparison_still_runs(self):
        sentence = _sentence_with(self.RESUME, "artifact bodies", "recorded digest")
        self.assertTrue(_has(sentence, "still"), sentence)

    def test_ac3_resume_cites_rule_r1(self):
        _assert_cites_r1(self, self.RESUME, "create-plan section 3")

    def test_ac3_orchestrator_is_the_actor(self):
        self.assertTrue(_has(self.RESUME, "orchestrator"))

    def test_ac3_existing_resume_decision_table_sentence_is_kept(self):
        self.assertTrue(
            _has(CP_SECTION_3, "the artifact bodies against their recorded digests")
        )


# ---------------------------------------------------------------------------
# AC-4: rework section 10
# ---------------------------------------------------------------------------


class TestAC4ReworkSection10(unittest.TestCase):
    """AC-4 (FR5, FR7, FR8, FR10; TS-3, TS-11)."""

    @classmethod
    def setUpClass(cls):
        cls.RETURN_TIME = _paragraph_with(RW_SECTION_10, SCRIPT_TOKEN)

    def test_ac4_dispatch_digest_inputs_is_recorded_for_rework_planner(self):
        self.assertTrue(_has(RW_SECTION_10, "dispatch_digest_inputs"))
        self.assertTrue(_has(self.RETURN_TIME, "dispatch_digest_inputs"))
        self.assertTrue(_has(self.RETURN_TIME, "phase-state/rework.yaml"))

    def test_ac4_script_follows_scope_verification_and_precedes_patch_validation(self):
        _assert_in_order(
            self,
            self.RETURN_TIME,
            ["scope verification", SCRIPT_TOKEN, "step 3 validates"],
            "rework section 10",
        )

    def test_ac4_rule_1_is_validated_against_the_substituted_digest_source(self):
        after_script = self.RETURN_TIME[self.RETURN_TIME.index("self-write-digest.py"):]
        sentence = _sentence_with(after_script, "rule 1", "substituted digest_source")
        self.assertTrue(sentence)

    def test_ac4_self_write_set_is_recorded_with_the_layer_5_write(self):
        sentence = _sentence_with(self.RETURN_TIME, "self_write_set", "Layer 5 recording")
        self.assertTrue(_has(sentence, "phase-state/rework.yaml"), sentence)
        self.assertTrue(_has(sentence, "same phase-state write"), sentence)

    def test_ac4_mismatch_or_nonzero_exit_is_stale(self):
        sentence = _sentence_with(self.RETURN_TIME, "stale", "exit")
        self.assertTrue(sentence)

    def test_ac4_names_the_identify_and_substitute_operation(self):
        self.assertTrue(_has(self.RETURN_TIME, "identify_and_substitute"))

    def test_ac4_orchestrator_is_the_actor(self):
        self.assertTrue(_has(self.RETURN_TIME, "orchestrator"))


# ---------------------------------------------------------------------------
# AC-5: citations, no restatement, dispatch_digest_wiring
# ---------------------------------------------------------------------------


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "_check_plugin_invariants_for_self_write_wiring", CHECKER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# (label, slice, owner sections the registry row covers)
REGISTERED_SITES = (
    ("design step branch", DESIGN_BRANCH,
     ("Pre-dispatch verification", "Layer 5 recording")),
    ("create-plan section 4", CP_SECTION_4, ("Pre-dispatch verification",)),
    ("create-plan section 8", CP_SECTION_8, ("Layer 5 recording",)),
    ("rework section 10", RW_SECTION_10,
     ("Pre-dispatch verification", "Layer 5 recording")),
)


class TestAC5CitationsAndNoRestatement(unittest.TestCase):
    """AC-5 (NFR3, NFR6; TS-10, TS-15)."""

    def test_ac5_dispatch_digest_wiring_passes_on_the_real_repository(self):
        result = _load_checker().check_dispatch_digest_wiring(str(REPO_ROOT))
        self.assertEqual(result.name, "dispatch_digest_wiring")
        self.assertTrue(result.passed, result.offenders)

    def test_ac5_registered_sections_still_cite_the_digest_owner(self):
        for label, body, covers in REGISTERED_SITES:
            with self.subTest(site=label):
                self.assertIn(OWNER_CITATION, _norm(body))
                for name in covers:
                    self.assertIn(name, _norm(body))

    def test_ac5_no_site_names_git_hash_object(self):
        for label, body in SITE_SLICES:
            with self.subTest(site=label):
                self.assertNotIn(GIT_HASH_OBJECT, _norm(body))

    def test_ac5_each_site_cites_r1_instead_of_restating_it(self):
        for label, body in (
            ("design step branch", DESIGN_STEP_5),
            ("create-plan section 8", _paragraph_with(CP_SECTION_8, SCRIPT_TOKEN)),
            ("rework section 10", _paragraph_with(RW_SECTION_10, SCRIPT_TOKEN)),
        ):
            with self.subTest(site=label):
                _assert_cites_r1(self, body, label)

    def test_ac5_no_site_restates_the_membership_matrix_or_the_substitution(self):
        for label, body in SITE_SLICES:
            with self.subTest(site=label):
                self.assertEqual(_restatement_hits(body), [])

    def test_ac5_probes_fire_on_forged_matrix_wording(self):
        forged = (
            "A path is not a member of the set when its action is `create` and "
            "its change is modified."
        )
        self.assertNotEqual(_restatement_hits(forged), [])
        forged_action_by_kind = "`replace_own` admits a path that was modified."
        self.assertNotEqual(_restatement_hits(forged_action_by_kind), [])

    def test_ac5_probes_fire_on_forged_substitution_wording(self):
        forged = "When the path is an absent key of the map it is absent from the digest."
        self.assertNotEqual(_restatement_hits(forged), [])
        forged_ja = "dispatch 時の値に置き換える。"
        self.assertNotEqual(_restatement_hits(forged_ja), [])

    def test_ac5_probes_stay_quiet_on_a_citing_sentence(self):
        citing = (
            "The orchestrator runs `scripts/self-write-digest.py` as "
            "`references/contracts/worker-envelope.md`, Rule R1, "
            '"Recomputation and comparison timing" states.'
        )
        self.assertEqual(_restatement_hits(citing), [])


class TestSliceHelpers(unittest.TestCase):
    """The slicing helpers the assertions above rely on."""

    def test_numbered_item_stops_at_the_next_unindented_line(self):
        text = "1. a\n   cont\n2. b\n   more\n\ntrailing\n"
        self.assertEqual(_norm(_numbered_item(text, 1)), "1. a cont")
        self.assertEqual(_norm(_numbered_item(text, 2)), "2. b more")

    def test_assert_in_order_rejects_a_swapped_pair(self):
        case = unittest.TestCase()
        with self.assertRaises(AssertionError):
            _assert_in_order(case, "beta then alpha", ["alpha", "beta"], "forged")

    def test_section_requires_exactly_one_heading(self):
        with self.assertRaises(AssertionError):
            _section("# a\n\n## x\n\n## x\n", "x", 2)

    def test_sentence_with_requires_every_token_in_one_sentence(self):
        with self.assertRaises(AssertionError):
            _sentence_with("alpha is here. beta is there.", "alpha", "beta")


if __name__ == "__main__":
    unittest.main()

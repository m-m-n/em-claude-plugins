"""Tests for large-diff-review-coverage/task0006: the evaluator receives both
coverage fields, and the Phase R6 report and the batch final result show both,
so an unreviewed range is never presented as a clean review.

Covers task0006 Acceptance Criteria
(feature-docs/large-diff-review-coverage/tasks/task0006.md):

- AC-1 (FR16): Phase R3a's input block carries `unreviewed_perspectives` and
  `partially_reviewed_perspectives` from the `coverage` operation over the
  loop-0 pass after Phase R2b, each present and empty when none, and states
  that only `unreviewed_perspectives` is exempt from the Independent
  Inspection Duty.
- AC-2 (FR16): the evaluation contract's Input Block and Independent
  Inspection Duty, and the evaluator's Step 3, state that a perspective in
  `partially_reviewed_perspectives` remains subject to the duty while one in
  `unreviewed_perspectives` is exempt; neither file restates the retryable
  skip_reason strings.
- AC-3 (FR15, TM-8): Phase R6 renders every unreviewed perspective and every
  partial entry with its reason and full unreviewed file list from the round
  record, as disclosure only.
- AC-4 (FR15, TM-8): batch-mode.md's Reporting list holds the new item
  immediately before the triage item, the audit-item source map holds the new
  row immediately before the triage row mapped to the two round-record
  fields, and the section names no provider or model and carries none of the
  restatement phrases.
- AC-5 (pins and counts): the Reporting sentence, the source-map
  expectations and the four row counts are updated in their own modules; this
  module re-checks the position of the triage and kept-branch rows, the
  level-2 headings and the `gate_id` count of batch-mode.md.
- AC-6: this module checks AC-1 to AC-4 on the real files, and every
  matcher is fed a forged text that it must reject, next to a non-vacuity
  guard that the same text with the element restored is accepted.

Every document is sliced by its headings (or by the leading token of a
bullet) so a statement landing in the wrong place fails, and phrases are
matched over whitespace-normalized text so a line wrap does not matter.

Matcher -> negative-control inventory:

- `_r3a_input_block_is_well_formed` (AC-1)
- `_contract_input_block_is_well_formed` (AC-2)
- `_contract_duty_is_well_formed` (AC-2)
- `_evaluator_step3_is_well_formed` (AC-2)
- `_r6_discloses_coverage` (AC-3)
- `_reporting_item_is_well_formed` (AC-4)
- `_source_map_row_is_well_formed` (AC-4)
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "review-evaluation-contract.md"
EVALUATOR_PATH = PLUGIN_ROOT / "agents" / "review-evaluator.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

R3A_HEADING = "## Phase R3a: Evaluation (single Opus evaluator)"
R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R6_HEADING = "## Phase R6: Report (Japanese)"

UNREVIEWED = "`unreviewed_perspectives`"
PARTIAL = "`partially_reviewed_perspectives`"

ROUND_RECORD_PATH = "feature-docs/{feature}/reviews/roundN.yaml"
REVIEW_PHASE_CITATION = "references/review-phase.md"
TRIAGE_PHRASE = "triage filing incomplete"
KEPT_BRANCH_PHRASE = "kept integration branch name"
REPORTING_ITEM_START = (
    "every review round's `unreviewed_perspectives` and "
    "`partially_reviewed_perspectives`"
)
TRIAGE_ITEM_START = "every review round whose triage filing was incomplete"

BATCH_MODE_GATE_ID_COUNT = 8
BATCH_MODE_LEVEL2_HEADINGS = [
    "Purpose & activation",
    "Non-packet gates",
    "workflow.yaml `batch` block",
    "Structured result",
    "Reporting",
    "Batch quiet output",
]

RESTATEMENT_PHRASES = (
    "processing order",
    "malformed",
    "automatic retry",
    "duplicate detection",
)
FORBIDDEN_PROVIDER_TOKENS = ("GPT", "Vertex", "Muse", "GLM")
FORBIDDEN_USAGE_LIMIT_PHRASES = ("usage-limit", "usage limit")
RETRYABLE_SKIP_STRINGS = (
    "rate_limited",
    "budget_exhausted",
    "harness_unavailable",
    "review_data_too_large",
)


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


def _sentences(text):
    return re.split(r"(?<=\.)\s+", _norm(text))


def _bullet(section, name):
    """The whitespace-normalized text of the bullet that begins with
    `- `name``, or None. A bullet runs over its indented continuation lines."""
    collected = None
    for line in section.splitlines():
        match = re.match(r"- `([^`]+)`", line)
        if match:
            if collected is not None:
                break
            if match.group(1) == name:
                collected = [line]
            continue
        if collected is not None:
            if line.startswith("  ") and line.strip():
                collected.append(line)
            else:
                break
    return _norm(" ".join(collected)) if collected else None


def _paragraph_containing(section, needle):
    for paragraph in re.split(r"\n\s*\n", section):
        if needle in paragraph:
            return _norm(paragraph)
    return None


def _table_rows(section_text):
    """Each data row of a Markdown table in `section_text` as a list of cell
    strings, skipping the header row and the `---` separator row."""
    raw_rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


def _backtick_tokens(cell):
    return re.findall(r"`([^`]+)`", cell)


def _exemption_split_holds(text):
    """The duty exemption covers `unreviewed_perspectives` only: every
    sentence that says the duty does not apply names the unreviewed field and
    not the partial one, and at least one sentence says the duty still applies
    to the partial field and not the unreviewed one."""
    sentences = _sentences(text)
    exempt = [s for s in sentences if "does not apply" in s]
    applies = [s for s in sentences if "still applies" in s]
    if not exempt or not applies:
        return False
    if not all(UNREVIEWED in s and PARTIAL not in s for s in exempt):
        return False
    if not any(PARTIAL in s for s in applies):
        return False
    return not any(UNREVIEWED in s for s in applies)


# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------


class Docs:
    _cache = {}

    @classmethod
    def _text(cls, path):
        if path not in cls._cache:
            cls._cache[path] = _read(path)
        return cls._cache[path]

    @classmethod
    def r3a(cls):
        return _slice(cls._text(REVIEW_PHASE_PATH), R3A_HEADING, R3B_HEADING)

    @classmethod
    def r6(cls):
        return _slice(cls._text(REVIEW_PHASE_PATH), R6_HEADING)

    @classmethod
    def contract_input_block(cls):
        return _slice(
            cls._text(CONTRACT_PATH), "## Input Block", "## Output Object"
        )

    @classmethod
    def contract_duty(cls):
        return _slice(
            cls._text(CONTRACT_PATH),
            "## Independent Inspection Duty",
            "## Reproduction Verification",
        )

    @classmethod
    def evaluator_step3(cls):
        return _slice(
            cls._text(EVALUATOR_PATH),
            "## Step 3: Independently inspect every dispatched perspective",
            "## Read-only constraint",
        )

    @classmethod
    def batch_text(cls):
        return cls._text(BATCH_MODE_PATH)

    @classmethod
    def reporting(cls):
        return _slice(cls.batch_text(), "## Reporting\n", "\n## Batch quiet output")

    @classmethod
    def quiet_output(cls):
        return _slice(cls.batch_text(), "## Batch quiet output")


# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------


def _r3a_input_block_is_well_formed(r3a):
    unreviewed = _bullet(r3a, "unreviewed_perspectives")
    partial = _bullet(r3a, "partially_reviewed_perspectives")
    if unreviewed is None or partial is None:
        return False
    for phrase in (
        "the same list Phase R5 records at the round-record root",
        "present and empty when there are none",
        "`coverage` operation",
        "loop-0 pass",
        "right after Phase R2b",
        "before the evaluator dispatch",
        "exits non-zero",
        "aborts",
    ):
        if phrase not in unreviewed:
            return False
    for phrase in (
        "the same source",
        "present and empty when there are none",
        "`perspective`",
        "`unreviewed_files`",
        "`reason`",
    ):
        if phrase not in partial:
            return False
    return _exemption_split_holds(r3a)


def _contract_input_block_is_well_formed(input_block):
    unreviewed = _bullet(input_block, "unreviewed_perspectives")
    partial = _bullet(input_block, "partially_reviewed_perspectives")
    if unreviewed is None or partial is None:
        return False
    if "does not apply" not in unreviewed:
        return False
    for phrase in (
        "present and empty when there are none",
        "`perspective`",
        "`unreviewed_files`",
        "`reason`",
        "Independent Inspection Duty",
        "still applies",
    ):
        if phrase not in partial:
            return False
    return "does not apply" not in partial


def _contract_duty_is_well_formed(duty):
    if not _exemption_split_holds(duty):
        return False
    norm = _norm(duty)
    return "inspected like any other" in norm and (
        "unreviewed files may be among" in norm
    )


def _evaluator_step3_is_well_formed(step3):
    norm = _norm(step3)
    if not re.search(r"never a perspective listed in `unreviewed_perspectives`", norm):
        return False
    mentions = [s for s in _sentences(step3) if PARTIAL in s]
    if len(mentions) != 1:
        return False
    sentence = mentions[0]
    if re.search(r"\b(never|not|exempt)\b", sentence):
        return False
    return "inspected" in sentence and "unreviewed files" in sentence


def _r6_discloses_coverage(r6):
    paragraph = _paragraph_containing(r6, PARTIAL)
    if paragraph is None:
        return False
    for phrase in (
        UNREVIEWED,
        PARTIAL,
        "round record",
        "`reason`",
        "full `unreviewed_files` list",
        "disclosure only",
        "no new gate identifier",
        "never affects the completion gate",
        "batch final result",
        "references/batch-mode.md",
    ):
        if phrase not in paragraph:
            return False
    return True


def _reporting_item_is_well_formed(reporting):
    norm = _norm(reporting)
    if norm.count(REPORTING_ITEM_START) != 1 or norm.count(TRIAGE_ITEM_START) != 1:
        return False
    start = norm.index(REPORTING_ITEM_START)
    triage = norm.index(TRIAGE_ITEM_START)
    if "with its reasoning)" not in norm:
        return False
    if not norm.index("with its reasoning)") < start < triage:
        return False
    segment = norm[start:triage]
    if segment.count("every ") != 1:
        return False
    if "reason" not in segment or "unreviewed files" not in segment:
        return False
    lowered = norm.lower()
    return not any(p in lowered for p in RESTATEMENT_PHRASES)


def _source_map_row_is_well_formed(rows):
    named = [r for r in rows if UNREVIEWED in r[0] and PARTIAL in r[0]]
    if len(named) != 1 or len(rows) < 3:
        return False
    row = named[0]
    if rows[-3] is not row:
        return False
    if TRIAGE_PHRASE not in rows[-2][0] or KEPT_BRANCH_PHRASE not in rows[-1][0]:
        return False
    source = row[1]
    if set(_backtick_tokens(source)) != {
        ROUND_RECORD_PATH,
        "unreviewed_perspectives",
        "partially_reviewed_perspectives",
        REVIEW_PHASE_CITATION,
    }:
        return False
    if "Phase R5" not in source:
        return False
    return not any(p in " ".join(row).lower() for p in RESTATEMENT_PHRASES)


# ---------------------------------------------------------------------------
# Forged samples (hand-built, mirroring the shape of the real text)
# ---------------------------------------------------------------------------

WELL_FORMED_R3A = """\
- `unreviewed_perspectives` — the same list Phase R5 records at the
  round-record root; present and empty when there are none. The orchestrator
  computes it with `partially_reviewed_perspectives` by the `coverage`
  operation over the loop-0 pass, right after Phase R2b and before the
  evaluator dispatch. When the operation exits non-zero, the review phase
  aborts before the round record is written.
- `partially_reviewed_perspectives` — the same source and the same empty
  rule: present and empty when there are none. Each entry carries
  `perspective`, `unreviewed_files` and `reason`.

The evaluator's Independent Inspection Duty does not apply to a perspective
listed in `unreviewed_perspectives`: there is no reviewer output to
corroborate. The duty still applies to a perspective listed in
`partially_reviewed_perspectives`.
"""

WELL_FORMED_CONTRACT_INPUT_BLOCK = """\
- `unreviewed_perspectives` — perspectives with no completed reviewer run
  this round; present and empty when there are none. The Independent
  Inspection Duty (below) does not apply to a perspective listed here.
- `partially_reviewed_perspectives` — present and empty when there are none.
  Each entry carries `perspective`, `unreviewed_files` and `reason`. The
  Independent Inspection Duty (below) still applies to a perspective listed
  here.
"""

WELL_FORMED_CONTRACT_DUTY = """\
For every perspective dispatched this round, the evaluator inspects the
files. The duty does not apply to a perspective listed in
`unreviewed_perspectives`: there is no reviewer output to corroborate. The duty
still applies to a perspective listed in `partially_reviewed_perspectives`: it
is inspected like any other, and its unreviewed files may be among those the
evaluator reads.
"""

WELL_FORMED_EVALUATOR_STEP3 = """\
For every perspective in `perspectives_dispatched` (never a perspective listed
in `unreviewed_perspectives` — there is no reviewer output there to
corroborate), inspect the round's `changed_files` yourself. A perspective
listed in `partially_reviewed_perspectives` is inspected like any other; its
unreviewed files may be among the files you read.
"""

WELL_FORMED_R6 = """\
Rendering rules.

The report also renders, from the round record, every perspective of
`unreviewed_perspectives` and every entry of
`partially_reviewed_perspectives` with its `reason` and its full
`unreviewed_files` list. This is disclosure only: it introduces no new gate
identifier and never affects the completion gate. The batch final result
carries the same content through `references/batch-mode.md`'s Reporting item
list.
"""

WELL_FORMED_REPORTING = """\
report: auto-rework rounds consumed (review / verify), every autonomous
fail-closed-route resolution (gate / option chosen / whether the Opus
escalation ran, with its
reasoning), every review round's `unreviewed_perspectives` and
`partially_reviewed_perspectives`, each partial entry with its reason and its
unreviewed files, every review round whose triage filing was incomplete
(reported as "triage filing incomplete"), and the kept integration branch name
"""

WELL_FORMED_ROWS = [
    ["Any deferred findings with their stable_ids", "`x` `stable_id`"],
    [
        "Every review round's `unreviewed_perspectives` and "
        "`partially_reviewed_perspectives`",
        "`feature-docs/{feature}/reviews/roundN.yaml` "
        "`unreviewed_perspectives` / `partially_reviewed_perspectives` "
        "(`references/review-phase.md` Phase R5)",
    ],
    [
        'Every review round reported as "triage filing incomplete"',
        "`feature-docs/{feature}/reviews/roundN.yaml` "
        "`triage_filing.unattempted_packages`",
    ],
    ["The kept integration branch name", "`workflow.yaml` `parent_branch`"],
]


def _rows(**replacements):
    rows = [list(row) for row in WELL_FORMED_ROWS]
    for needle, replacement in replacements.items():
        rows[1][1] = rows[1][1].replace(needle, replacement)
    return rows


def _mutated(text, old, new):
    """`text` with `old` replaced by `new`; proves the edit took effect so a
    negative proof cannot pass because the replacement matched nothing."""
    result = text.replace(old, new)
    assert result != text, f"mutation matched nothing: {old!r}"
    return result


# ---------------------------------------------------------------------------
# AC-1: Phase R3a input block
# ---------------------------------------------------------------------------


class TestAC1PhaseR3aInputBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r3a = Docs.r3a()

    def test_real_phase_r3a_is_well_formed(self):
        self.assertTrue(_r3a_input_block_is_well_formed(self.r3a), self.r3a)

    def test_both_fields_are_input_bullets(self):
        self.assertIsNotNone(_bullet(self.r3a, "unreviewed_perspectives"))
        self.assertIsNotNone(_bullet(self.r3a, "partially_reviewed_perspectives"))

    def test_fields_come_from_the_coverage_operation_over_loop_zero(self):
        bullet = _bullet(self.r3a, "unreviewed_perspectives")
        self.assertIn("`coverage` operation", bullet)
        self.assertIn("loop-0 pass", bullet)
        self.assertIn("right after Phase R2b", bullet)

    def test_unreviewed_definition_through_the_claude_fallback_is_gone(self):
        bullet = _bullet(self.r3a, "unreviewed_perspectives")
        self.assertNotIn("Claude fallback", bullet)

    def test_only_unreviewed_perspectives_is_exempt_from_the_duty(self):
        self.assertTrue(_exemption_split_holds(self.r3a))

    def test_phase_r3a_adds_no_gate_identifier(self):
        self.assertNotIn("gate_id", self.r3a)


class TestAC1MatcherCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_template_passes(self):
        self.assertTrue(_r3a_input_block_is_well_formed(WELL_FORMED_R3A))

    def test_forged_r3a_that_exempts_partially_reviewed_perspectives_fails(self):
        forged = _mutated(
            WELL_FORMED_R3A,
            "The duty still applies to a perspective listed in\n"
            "`partially_reviewed_perspectives`.",
            "The duty does not apply to a perspective listed in\n"
            "`partially_reviewed_perspectives` either.",
        )
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_exempting_both_in_one_sentence_fails(self):
        forged = _mutated(
            WELL_FORMED_R3A,
            "listed in `unreviewed_perspectives`: there is",
            "listed in `unreviewed_perspectives` or "
            "`partially_reviewed_perspectives`: there is",
        )
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_real_r3a_with_the_partial_sentence_turned_into_an_exemption_fails(self):
        forged = _mutated(Docs.r3a(), "still applies", "does not apply")
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_missing_the_partial_bullet_fails(self):
        forged = _mutated(
            WELL_FORMED_R3A, "- `partially_reviewed_perspectives` —", "- other —"
        )
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_without_the_empty_rule_on_the_partial_bullet_fails(self):
        forged = _mutated(
            WELL_FORMED_R3A,
            "rule: present and empty when there are none.",
            "rule.",
        )
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_without_the_coverage_operation_fails(self):
        forged = _mutated(WELL_FORMED_R3A, "`coverage`\n  operation", "script")
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_without_the_loop_zero_pass_fails(self):
        forged = _mutated(WELL_FORMED_R3A, "loop-0 pass", "final pass")
        self.assertFalse(_r3a_input_block_is_well_formed(forged))

    def test_forged_r3a_without_the_abort_on_failure_fails(self):
        forged = _mutated(WELL_FORMED_R3A, "exits non-zero", "finishes")
        self.assertFalse(_r3a_input_block_is_well_formed(forged))


# ---------------------------------------------------------------------------
# AC-2: evaluation contract and evaluator agent
# ---------------------------------------------------------------------------


class TestAC2EvaluationContractAndEvaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input_block = Docs.contract_input_block()
        cls.duty = Docs.contract_duty()
        cls.step3 = Docs.evaluator_step3()

    def test_contract_input_block_is_well_formed(self):
        self.assertTrue(
            _contract_input_block_is_well_formed(self.input_block), self.input_block
        )

    def test_contract_duty_section_is_well_formed(self):
        self.assertTrue(_contract_duty_is_well_formed(self.duty), self.duty)

    def test_evaluator_step3_is_well_formed(self):
        self.assertTrue(_evaluator_step3_is_well_formed(self.step3), self.step3)

    def test_contract_duty_keeps_its_existing_opening_text(self):
        norm = _norm(self.duty)
        self.assertIn("not, by itself, evidence", norm)
        self.assertIn("No second reviewer is dispatched", norm)

    def test_neither_file_restates_the_retryable_skip_reason_strings(self):
        for path in (CONTRACT_PATH, EVALUATOR_PATH):
            text = _read(path)
            for token in RETRYABLE_SKIP_STRINGS:
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, text)


class TestAC2MatchersCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_templates_pass(self):
        self.assertTrue(
            _contract_input_block_is_well_formed(WELL_FORMED_CONTRACT_INPUT_BLOCK)
        )
        self.assertTrue(_contract_duty_is_well_formed(WELL_FORMED_CONTRACT_DUTY))
        self.assertTrue(_evaluator_step3_is_well_formed(WELL_FORMED_EVALUATOR_STEP3))

    def test_forged_input_block_without_the_partial_bullet_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_INPUT_BLOCK,
            "- `partially_reviewed_perspectives` —",
            "- other —",
        )
        self.assertFalse(_contract_input_block_is_well_formed(forged))

    def test_forged_input_block_exempting_the_partial_bullet_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_INPUT_BLOCK,
            "(below) still applies to a perspective listed\n  here.",
            "(below) does not apply to a perspective listed\n  here.",
        )
        self.assertFalse(_contract_input_block_is_well_formed(forged))

    def test_forged_input_block_without_the_entry_keys_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_INPUT_BLOCK, "`unreviewed_files` and ", ""
        )
        self.assertFalse(_contract_input_block_is_well_formed(forged))

    def test_forged_duty_exempting_the_partial_field_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_DUTY,
            "The duty\nstill applies to a perspective listed in "
            "`partially_reviewed_perspectives`",
            "The duty\ndoes not apply to a perspective listed in "
            "`partially_reviewed_perspectives`",
        )
        self.assertFalse(_contract_duty_is_well_formed(forged))

    def test_forged_duty_exempting_both_fields_in_one_sentence_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_DUTY,
            "`unreviewed_perspectives`: there",
            "`unreviewed_perspectives` or `partially_reviewed_perspectives`: there",
        )
        self.assertFalse(_contract_duty_is_well_formed(forged))

    def test_forged_duty_without_the_unreviewed_files_statement_fails(self):
        forged = _mutated(
            WELL_FORMED_CONTRACT_DUTY, ", and its unreviewed files may be among", " and"
        )
        self.assertFalse(_contract_duty_is_well_formed(forged))

    def test_forged_step3_exempting_the_partial_field_fails(self):
        forged = _mutated(
            WELL_FORMED_EVALUATOR_STEP3,
            "is inspected like any other",
            "is never inspected",
        )
        self.assertFalse(_evaluator_step3_is_well_formed(forged))

    def test_forged_step3_without_the_partial_field_fails(self):
        forged = _mutated(
            WELL_FORMED_EVALUATOR_STEP3,
            "A perspective\nlisted in `partially_reviewed_perspectives` is inspected "
            "like any other; its\nunreviewed files may be among the files you read.",
            "",
        )
        self.assertFalse(_evaluator_step3_is_well_formed(forged))

    def test_forged_step3_without_the_unreviewed_exemption_fails(self):
        forged = _mutated(
            WELL_FORMED_EVALUATOR_STEP3, "never a perspective", "every perspective"
        )
        self.assertFalse(_evaluator_step3_is_well_formed(forged))


# ---------------------------------------------------------------------------
# AC-3: Phase R6
# ---------------------------------------------------------------------------


class TestAC3PhaseR6Disclosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r6 = Docs.r6()

    def test_real_phase_r6_discloses_both_fields(self):
        self.assertTrue(_r6_discloses_coverage(self.r6), self.r6)

    def test_disclosure_renders_from_the_round_record(self):
        paragraph = _paragraph_containing(self.r6, PARTIAL)
        self.assertIn("round record", paragraph)

    def test_disclosure_affects_no_gate(self):
        paragraph = _paragraph_containing(self.r6, PARTIAL)
        self.assertIn("disclosure only", paragraph)
        self.assertIn("never affects the completion gate", paragraph)

    def test_existing_r6_withholding_and_rendering_rules_are_kept(self):
        norm = _norm(self.r6)
        self.assertIn("not emitted into the main context", norm)
        self.assertIn("triage filing incomplete", norm)
        self.assertIn("タメ語・女性・体言止めなし", self.r6)

    def test_phase_r6_adds_no_gate_identifier(self):
        self.assertNotIn("gate_id", self.r6)


class TestAC3MatcherCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_template_passes(self):
        self.assertTrue(_r6_discloses_coverage(WELL_FORMED_R6))

    def test_forged_r6_without_the_partial_field_fails(self):
        forged = _mutated(
            WELL_FORMED_R6,
            "and every entry of\n`partially_reviewed_perspectives` with its "
            "`reason` and its full\n`unreviewed_files` list",
            "",
        )
        self.assertFalse(_r6_discloses_coverage(forged))

    def test_forged_r6_without_the_reason_fails(self):
        forged = _mutated(WELL_FORMED_R6, "with its `reason` and its full", "with its full")
        self.assertFalse(_r6_discloses_coverage(forged))

    def test_forged_r6_with_a_truncated_file_list_fails(self):
        forged = _mutated(WELL_FORMED_R6, "its full\n`unreviewed_files` list", "a\n`unreviewed_files` sample")
        self.assertFalse(_r6_discloses_coverage(forged))

    def test_forged_r6_that_is_not_disclosure_only_fails(self):
        forged = _mutated(WELL_FORMED_R6, "disclosure only", "a gate")
        self.assertFalse(_r6_discloses_coverage(forged))

    def test_forged_r6_without_the_batch_final_result_fails(self):
        forged = _mutated(WELL_FORMED_R6, "batch final result", "final line")
        self.assertFalse(_r6_discloses_coverage(forged))


# ---------------------------------------------------------------------------
# AC-4: batch-mode.md Reporting item and audit-item source-map row
# ---------------------------------------------------------------------------


class TestAC4ReportingItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reporting = Docs.reporting()

    def test_real_reporting_item_is_well_formed(self):
        self.assertTrue(_reporting_item_is_well_formed(self.reporting), self.reporting)

    def test_item_sits_immediately_before_the_triage_item(self):
        norm = _norm(self.reporting)
        segment = norm[
            norm.index(REPORTING_ITEM_START) : norm.index(TRIAGE_ITEM_START)
        ]
        self.assertEqual(segment.count("every "), 1)

    def test_item_follows_the_autonomous_fail_closed_route_item(self):
        norm = _norm(self.reporting)
        self.assertLess(
            norm.index("with its reasoning)"), norm.index(REPORTING_ITEM_START)
        )

    def test_kept_branch_item_is_still_last(self):
        norm = _norm(self.reporting)
        self.assertLess(
            norm.index(TRIAGE_ITEM_START), norm.index("and the kept integration branch")
        )

    def test_reporting_section_names_no_provider_or_usage_limit(self):
        for token in FORBIDDEN_PROVIDER_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, self.reporting)
        lowered = self.reporting.lower()
        for phrase in FORBIDDEN_USAGE_LIMIT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)


class TestAC4SourceMapRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _table_rows(Docs.quiet_output())

    def test_real_source_map_row_is_well_formed(self):
        self.assertTrue(_source_map_row_is_well_formed(self.rows), self.rows)

    def test_row_sits_immediately_before_the_triage_row(self):
        self.assertIn(UNREVIEWED, self.rows[-3][0])
        self.assertIn(TRIAGE_PHRASE, self.rows[-2][0])
        self.assertIn(KEPT_BRANCH_PHRASE, self.rows[-1][0])

    def test_row_maps_to_the_two_round_record_fields(self):
        source = self.rows[-3][1]
        self.assertEqual(
            set(_backtick_tokens(source)),
            {
                ROUND_RECORD_PATH,
                "unreviewed_perspectives",
                "partially_reviewed_perspectives",
                REVIEW_PHASE_CITATION,
            },
        )

    def test_row_cites_phase_r5(self):
        self.assertIn("Phase R5", self.rows[-3][1])


class TestAC4DocumentWide(unittest.TestCase):
    def test_batch_mode_names_no_provider_or_usage_limit(self):
        text = Docs.batch_text()
        for token in FORBIDDEN_PROVIDER_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, text)
        lowered = text.lower()
        for phrase in FORBIDDEN_USAGE_LIMIT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

    def test_gate_id_count_is_unchanged(self):
        self.assertEqual(
            Docs.batch_text().count("gate_id"), BATCH_MODE_GATE_ID_COUNT
        )

    def test_level2_heading_list_is_unchanged(self):
        headings = re.findall(r"^## (.+?)\s*$", Docs.batch_text(), re.MULTILINE)
        self.assertEqual(headings, BATCH_MODE_LEVEL2_HEADINGS)


class TestAC4MatchersCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_samples_pass(self):
        self.assertTrue(_reporting_item_is_well_formed(WELL_FORMED_REPORTING))
        self.assertTrue(_source_map_row_is_well_formed(_rows()))

    def test_forged_reporting_without_the_item_fails(self):
        forged = _mutated(
            WELL_FORMED_REPORTING,
            "every review round's `unreviewed_perspectives` and\n"
            "`partially_reviewed_perspectives`, each partial entry with its reason "
            "and its\nunreviewed files, ",
            "",
        )
        self.assertFalse(_reporting_item_is_well_formed(forged))

    def test_forged_reporting_with_the_item_after_the_triage_item_fails(self):
        item = (
            "every review round's `unreviewed_perspectives` and\n"
            "`partially_reviewed_perspectives`, each partial entry with its reason "
            "and its\nunreviewed files, "
        )
        forged = _mutated(WELL_FORMED_REPORTING, item, "")
        forged = _mutated(
            forged, "and the kept integration branch name", item + "and the kept integration branch name"
        )
        self.assertFalse(_reporting_item_is_well_formed(forged))

    def test_forged_reporting_with_an_item_between_it_and_the_triage_item_fails(self):
        forged = _mutated(
            WELL_FORMED_REPORTING,
            "unreviewed files, every review round whose",
            "unreviewed files, every other thing, every review round whose",
        )
        self.assertFalse(_reporting_item_is_well_formed(forged))

    def test_forged_reporting_without_the_reason_and_files_fails(self):
        forged = _mutated(
            WELL_FORMED_REPORTING,
            ", each partial entry with its reason and its\nunreviewed files",
            "",
        )
        self.assertFalse(_reporting_item_is_well_formed(forged))

    def test_forged_reporting_restating_a_definition_fails(self):
        forged = _mutated(
            WELL_FORMED_REPORTING, "unreviewed files,", "unreviewed files in processing order,"
        )
        self.assertFalse(_reporting_item_is_well_formed(forged))

    def test_forged_source_map_with_the_new_row_after_the_triage_row_fails(self):
        rows = _rows()
        rows[1], rows[2] = rows[2], rows[1]
        self.assertFalse(_source_map_row_is_well_formed(rows))

    def test_forged_source_map_with_the_new_row_after_the_kept_branch_row_fails(self):
        rows = _rows()
        rows.append(rows.pop(1))
        self.assertFalse(_source_map_row_is_well_formed(rows))

    def test_forged_source_map_without_the_new_row_fails(self):
        rows = _rows()
        del rows[1]
        self.assertFalse(_source_map_row_is_well_formed(rows))

    def test_forged_source_map_row_missing_the_partial_field_fails(self):
        forged = _rows(**{" / `partially_reviewed_perspectives`": ""})
        self.assertFalse(_source_map_row_is_well_formed(forged))

    def test_forged_source_map_row_missing_the_review_phase_citation_fails(self):
        forged = _rows(**{"`references/review-phase.md`": "review-phase"})
        self.assertFalse(_source_map_row_is_well_formed(forged))

    def test_forged_source_map_row_with_an_extra_source_fails(self):
        forged = _rows(
            **{"(`references/review-phase.md`": "`workflow.yaml` (`references/review-phase.md`"}
        )
        self.assertFalse(_source_map_row_is_well_formed(forged))

    def test_forged_source_map_row_restating_a_definition_fails(self):
        forged = _rows(**{"Phase R5": "Phase R5 in processing order"})
        self.assertFalse(_source_map_row_is_well_formed(forged))


class TestAC4RealRowsCanFail(unittest.TestCase):
    """The same mutations applied to the real source map, so the matcher is
    shown to reject a forged copy of the real table, not only a hand-built
    one."""

    def test_real_table_with_the_new_row_moved_after_the_triage_row_fails(self):
        rows = _table_rows(Docs.quiet_output())
        rows[-3], rows[-2] = rows[-2], rows[-3]
        self.assertFalse(_source_map_row_is_well_formed(rows))

    def test_real_table_without_the_new_row_fails(self):
        rows = _table_rows(Docs.quiet_output())
        del rows[-3]
        self.assertFalse(_source_map_row_is_well_formed(rows))


if __name__ == "__main__":
    unittest.main()

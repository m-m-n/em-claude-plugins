"""Document-structure tests for review-gate-abort-recovery task0001: the
gate-abort status rule, the resume path and the legacy recovery procedure
that Phase R5 of `em-workflow/references/review-phase.md` defines, plus the
stated scope of that document's `status: failed` reservation.

Acceptance criteria covered:

- AC-1 (FR1): the SC1 block (label `Spec-change gate abort (review-sourced
  rework)`) sits in Phase R5 after the batch-mode paragraphs and before the
  Phase R6 heading, and states elements E1-E7.
- AC-2 (FR3, NFR2): the SC1 block states the resume path (E8a-E8f), the
  stop-report guidance (E9) and the no-new-control-flow statement (E10).
- AC-3 (FR4): the SC2 block (label `Legacy review-failure recovery`) follows
  the SC1 block and states R1-R6.
- AC-4 (FR5, NFR5): the reservation paragraph keeps its sentence verbatim and
  states the reservation's scope, citing the SC1 label; the status value
  sets in `workflow-schema.md` are unchanged.
- AC-5 (NFR2, NFR3, NFR4): each label's bold form occurs exactly once and the
  substring `gate_id` occurs zero times in the pinned document.
- AC-6 (FR6): every matcher has a negative twin (a synthetic block lacking
  exactly one element, a value-flipped mutant, or the pre-change text) and
  every sliced region has a non-vacuity check.

Files read: `review-phase.md` and `workflow-schema.md`, by literal path from
the repository root, read-only. Matching runs on whitespace-collapsed text.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GAR_REVIEW_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"
GAR_SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-schema.md"

GAR_SC1_LABEL = "Spec-change gate abort (review-sourced rework)"
GAR_SC2_LABEL = "Legacy review-failure recovery"
GAR_R5_HEADING_RE = re.compile(r"^## Phase R5: Persist the round record$", re.M)
GAR_R6_HEADING_RE = re.compile(r"^## Phase R6: Report \(Japanese\)$", re.M)
GAR_BATCH_OPENER = "This batch auto-rework / defer-at-cap behaviour above"
GAR_RESERVATION_SENTENCE = (
    "`status: failed` is reserved for the two structural degradation "
    "triggers of Phase R3b."
)
GAR_ORDER_WINDOW = 400

# The reservation paragraph exactly as it stood before this change.
GAR_PRE_CHANGE_RESERVATION_PARAGRAPH = """\
`perspective_runs` entries gain a `role` field: `primary` (a `primary_chain`
entry ran for that perspective), `fallback` (the entry's `source` is
`claude`; no chain entry was available — whether that was decided at Phase
R2 fan-out from the availability probes, or discovered only after Phase
R2b's chain walk exhausted every entry, or reached via R2b's
malformed-result case), or `evaluator` (the round's single evaluator run —
the only entry with no `perspective` field). `source: claude` on a
perspective entry now means the fallback run — whichever of those routes
triggered it (IMPLEMENTATION.md D1, D9); it is never a second, parallel run
alongside a harness reviewer for the same perspective. The `evaluator`
entry additionally carries `degraded: true` whenever its Task succeeded but
Phase R3b's accountability floor had to lift one or more sites into
`findings`; its `status` stays `completed` in that case (IMPLEMENTATION.md
D8) — `status: failed` is reserved for the two structural degradation
triggers of Phase R3b.
"""

GAR_RESERVATION_SCOPE_STATEMENT = (
    "That reservation governs the `status` of `perspective_runs` entries — "
    "the `evaluator` entry's — and not the review step's "
    "`workflow[review].status` or the top-level `review.status`; for those "
    "under a gate abort, see `references/review-phase.md` Phase R5, "
    "`Spec-change gate abort (review-sourced rework)`."
)

GAR_EXPECTED_STEP_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "failed",
    "needs_update",
}
GAR_EXPECTED_REVIEW_STATUSES = {"pending", "in_progress", "completed", "failed"}


# ---------------------------------------------------------------------------
# Reading, slicing, matching helpers
# ---------------------------------------------------------------------------


def gar_read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def gar_collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def gar_bold(label):
    return "**" + label + "**"


def gar_slice_phase_r5(text):
    """Raw text from the Phase R5 heading up to the Phase R6 heading."""
    start = GAR_R5_HEADING_RE.search(text)
    end = GAR_R6_HEADING_RE.search(text)
    if start is None or end is None or end.start() < start.start():
        return ""
    return text[start.start() : end.start()]


def gar_slice_sc1(r5_text):
    """From the SC1 bold label up to the SC2 bold label."""
    start = r5_text.find(gar_bold(GAR_SC1_LABEL))
    end = r5_text.find(gar_bold(GAR_SC2_LABEL))
    if start < 0 or end < start:
        return ""
    return r5_text[start:end]


def gar_slice_sc2(r5_text):
    """From the SC2 bold label up to the end of Phase R5."""
    start = r5_text.find(gar_bold(GAR_SC2_LABEL))
    if start < 0:
        return ""
    return r5_text[start:]


def gar_reservation_paragraph(text):
    """Collapsed blank-line-bounded paragraph holding the reservation sentence."""
    for paragraph in re.split(r"\n[ \t]*\n", text):
        collapsed = gar_collapse(paragraph)
        if GAR_RESERVATION_SENTENCE in collapsed:
            return collapsed
    return ""


def gar_nonvacuous(region):
    return bool(region) and bool(region.strip())


def gar_in_order(text, patterns, window=GAR_ORDER_WINDOW):
    """Every pattern matches, in the given order, each within `window`
    characters of the end of the previous match."""
    pos = None
    for pattern in patterns:
        start_at = 0 if pos is None else pos
        match = re.compile(pattern, re.IGNORECASE).search(text, start_at)
        if match is None:
            return False
        if pos is not None and match.start() - pos > window:
            return False
        pos = match.end()
    return True


def gar_matcher(patterns):
    return lambda text: gar_in_order(text, patterns)


def gar_obsolete_sentences_are_scoped(text):
    """Every sentence naming `obsolete` also names the `inapplicable`
    outcome: obsolescence is claimed for the Classification gate's stop and
    inapplicable outcomes only."""
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if "obsolete" in sentence.lower() and "inapplicable" not in sentence.lower():
            return False
    return True


def gar_label_bold_count(text, label):
    return text.count(gar_bold(label))


def gar_label_single_bold(text, label):
    return gar_label_bold_count(text, label) == 1


def gar_label_opens_paragraph(text, label):
    pattern = r"(?:\A|\n[ \t]*\n)" + re.escape(gar_bold(label))
    return re.search(pattern, text) is not None


def gar_placement_ok(text):
    """R5 heading < batch-mode opener < SC1 label < SC2 label < R6 heading,
    all measured on whitespace-collapsed text."""
    flat = gar_collapse(text)
    positions = []
    for needle in (
        "## Phase R5: Persist the round record",
        GAR_BATCH_OPENER,
        gar_bold(GAR_SC1_LABEL),
        gar_bold(GAR_SC2_LABEL),
        "## Phase R6: Report (Japanese)",
    ):
        idx = flat.find(needle)
        if idx < 0:
            return False
        positions.append(idx)
    return positions == sorted(positions) and len(set(positions)) == len(positions)


def gar_gate_id_absent(text):
    return "gate_id" not in text


GAR_REWORK_GATE_LITERAL = "rework" + ".spec-change"


def gar_rework_gate_literal_absent(text):
    """The dotted gate-identifier literal of the rework spec-change question
    stays out of the pinned document (an existing gate-coverage module pins
    the same absence); the block names it "the spec-change question"."""
    return GAR_REWORK_GATE_LITERAL not in text


def gar_reservation_sentence_verbatim(paragraph):
    return GAR_RESERVATION_SENTENCE in paragraph


GAR_RESERVATION_SCOPE_PATTERNS = [
    r"reservation governs the `status` of `perspective_runs` entries",
    r"`evaluator` entry's",
    r"not the review step's `workflow\[review\]\.status` or the top-level "
    r"`review\.status`",
    r"`references/review-phase\.md`",
    r"Phase R5",
    r"Spec-change gate abort \(review-sourced rework\)",
]


def gar_reservation_scope_ok(paragraph):
    if GAR_RESERVATION_SENTENCE not in paragraph:
        return False
    tail = paragraph[paragraph.index(GAR_RESERVATION_SENTENCE) :]
    return gar_in_order(tail, GAR_RESERVATION_SCOPE_PATTERNS)


def gar_parse_status_sets(schema_text):
    """(step status set, top-level review status set) from the value-set
    comments in workflow-schema.md's schema block."""

    def comment_set(block_header_re, indent_re):
        lines = schema_text.splitlines()
        in_block = False
        for line in lines:
            if re.match(block_header_re, line):
                in_block = True
                continue
            if in_block and re.match(r"^[A-Za-z]", line):
                return set()
            if in_block:
                m = re.match(indent_re, line)
                if m:
                    return {
                        tok.strip()
                        for tok in m.group(1).split("|")
                        if re.fullmatch(r"[a-z_]+", tok.strip())
                    }
        return set()

    pattern = r"^\s+status: \S+\s+# ([a-z_ |]+)$"
    return (
        comment_set(r"^workflow:", pattern),
        comment_set(r"^review:", pattern),
    )


def gar_schema_sets_ok(schema_text):
    step_set, review_set = gar_parse_status_sets(schema_text)
    return (
        step_set == GAR_EXPECTED_STEP_STATUSES
        and review_set == GAR_EXPECTED_REVIEW_STATUSES
    )


# ---------------------------------------------------------------------------
# SC1 elements: (key, synthetic segment, ordered patterns)
# ---------------------------------------------------------------------------

GAR_E2_SEGMENT = (
    "Exactly four stops are gate aborts, each defined in "
    "`references/question-resolution.md` and not restated here: the "
    "Classification gate's verdict stop (including the stop that verdict (a), "
    "goal not met, produces), the Classification gate's inapplicable case, "
    "the Classification gate's origin-membership failure, and the malformed "
    "spec-change pairing abort."
)

GAR_SC1_ELEMENTS = [
    (
        "E1",
        "in review-sourced rework, after step 1 of "
        "`references/rework-task-synthesis.md` Section 10 has written "
        "`review.needs_rework = true` and `review.status = pending`, a "
        "spec-change question that ends the run is a gate abort.",
        [
            r"after step 1 of `references/rework-task-synthesis\.md` Section 10 "
            r"has written `review\.needs_rework = true` and "
            r"`review\.status = pending`",
            r"spec-change question that ends the run",
        ],
    ),
    (
        "E2",
        GAR_E2_SEGMENT,
        [
            r"exactly four",
            r"`references/question-resolution\.md`",
            r"verdict stop",
            r"verdict \(a\), goal not met",
            r"inapplicable case",
            r"origin-membership failure",
            r"malformed spec-change pairing",
        ],
    ),
    (
        "E3",
        "At a gate abort the orchestrator writes `workflow[review].status` as "
        "`pending` (it was `in_progress` from Step B); `review.status` stays "
        "`pending` and `review.needs_rework` stays `true`.",
        [
            r"writes `workflow\[review\]\.status` as `pending`",
            r"`in_progress`",
            r"`review\.status` stays `pending`",
            r"`review\.needs_rework` stays `true`",
        ],
    ),
    (
        "E4",
        "`failed` is written to neither `workflow[review].status` nor "
        "`review.status`.",
        [
            r"`failed` is written to neither `workflow\[review\]\.status` "
            r"nor `review\.status`",
        ],
    ),
    (
        "E5",
        "The write is committed with `commit-docs.sh` before the run stops; "
        "an exit 4 follows the exit-4 recovery of `skills/develop/SKILL.md` "
        "Step B (cited, not restated).",
        [
            r"committed with `commit-docs\.sh` before the run stops",
            r"exit 4 follows the exit-4 recovery of "
            r"`skills/develop/SKILL\.md` Step B",
            r"cited, not restated",
        ],
    ),
    (
        "E6a",
        "None of the five steps of the Section 10 specification-change "
        "transition runs, so the create-spec, create-plan and implement "
        "statuses are unchanged.",
        [
            r"none of the five steps of the Section 10 specification-change "
            r"transition runs",
            r"create-spec, create-plan and implement statuses are unchanged",
        ],
    ),
    (
        "E6b",
        "`batch.review_rework_count` is not incremented (its increment "
        "belongs to the applied-patch path of the batch-mode paragraph "
        "above).",
        [
            r"`batch\.review_rework_count` is not incremented",
            r"increment belongs to the applied-patch path of the batch-mode "
            r"paragraph",
        ],
    ),
    (
        "E7",
        "A spec-change gate stop in verify-sourced rework is outside this "
        "block.",
        [r"spec-change gate stop in verify-sourced rework is outside this block"],
    ),
    (
        "E8a1",
        "After such a stop, `/em-workflow:develop <feature>` resumes the run: "
        "Step B selects `review` (`pending`) as the next step",
        [
            r"`/em-workflow:develop <feature>`",
            r"Step B selects `review` \(`pending`\) as the next step",
        ],
    ),
    (
        "E8a2",
        "and stop condition 3 does not fire.",
        [r"stop condition 3 does not fire"],
    ),
    (
        "E8b",
        "The review phase then runs a new round,",
        [r"review phase then runs a new round"],
    ),
    (
        "E8c",
        "and the Completion gate leads into the ordinary rework path above.",
        [r"Completion gate leads into the ordinary rework path"],
    ),
    (
        "E8d",
        "In interactive mode, the spec-change question rework-planner returns is "
        "asked to the user directly.",
        [
            r"interactive mode, the spec-change question rework-planner returns "
            r"is asked to the user directly",
        ],
    ),
    (
        "E8e",
        "The packet that the Classification gate's stop or inapplicable "
        "outcome closed as `obsolete` is not re-presented "
        "(`references/question-resolution.md`, Classification gate, Outcome "
        "step).",
        [
            r"packet that the Classification gate's stop or inapplicable "
            r"outcome closed as `obsolete` is not re-presented",
            r"`references/question-resolution\.md`, Classification gate, "
            r"Outcome step",
        ],
    ),
    (
        "E9",
        "The stop's report — in batch, the `resume_conditions` value included "
        "— conveys that running `/em-workflow:develop <feature>` in "
        "interactive mode re-runs a review round and then reaches the "
        "spec-change decision.",
        [
            r"stop's report",
            r"`resume_conditions` value included",
            r"conveys that running `/em-workflow:develop <feature>` in "
            r"interactive mode re-runs a review round and then reaches the "
            r"spec-change decision",
        ],
    ),
    (
        "E10",
        "This block adds no Step B branch, no stop-condition-3 exception and "
        "no interactive question.",
        [
            r"adds no Step B branch",
            r"no stop-condition-3 exception",
            r"no interactive question",
        ],
    ),
]

# Value-flipping and part-removing mutants per element: (old, new). A mutant
# is a single-claim weakening of the segment and must be rejected.
GAR_SC1_MUTANTS = {
    "E1": [
        ("after step 1 of", "before step 1 of"),
        ("a spec-change question that ends the run", "any question"),
    ],
    "E2": [
        ("Exactly four", "Several"),
        (
            "each defined in `references/question-resolution.md` and not "
            "restated here",
            "each defined elsewhere",
        ),
        (
            " (including the stop that verdict (a), goal not met, produces)",
            "",
        ),
        (
            "the Classification gate's verdict stop (including the stop that "
            "verdict (a), goal not met, produces), ",
            "",
        ),
        ("the Classification gate's inapplicable case, ", ""),
        ("the Classification gate's origin-membership failure, and ", "and "),
        (", and the malformed spec-change pairing abort", ""),
    ],
    "E3": [
        ("writes `workflow[review].status` as `pending`", "writes `workflow[review].status` as `failed`"),
        ("(it was `in_progress` from Step B)", ""),
        ("`review.status` stays `pending`", "`review.status` becomes `completed`"),
        ("`review.needs_rework` stays `true`", "`review.needs_rework` becomes `false`"),
    ],
    "E4": [
        (
            "is written to neither `workflow[review].status` nor `review.status`",
            "is written to `workflow[review].status`",
        ),
    ],
    "E5": [
        ("committed with `commit-docs.sh` before the run stops", "committed later"),
        (
            "an exit 4 follows the exit-4 recovery of `skills/develop/SKILL.md` Step B",
            "an exit 4 is ignored",
        ),
        (" (cited, not restated)", ""),
    ],
    "E6a": [
        ("None of the five steps", "Two of the five steps"),
        ("statuses are unchanged", "statuses are reset"),
    ],
    "E6b": [
        ("is not incremented", "is incremented"),
        ("(its increment belongs to the applied-patch path of the batch-mode paragraph above)", ""),
    ],
    "E7": [("is outside this block", "is inside this block")],
    "E8a1": [
        ("Step B selects `review` (`pending`) as the next step", "Step B selects `review`"),
    ],
    "E8a2": [("does not fire", "fires")],
    "E8d": [("is asked to the user directly", "is answered by the batch policy")],
    "E8e": [
        ("is not re-presented", "is re-presented"),
        (
            " (`references/question-resolution.md`, Classification gate, Outcome step)",
            "",
        ),
    ],
    "E9": [
        ("in interactive mode re-runs a review round", "in batch mode re-runs a review round"),
        ("the `resume_conditions` value included", "the exit status included"),
    ],
    "E10": [
        ("no Step B branch, ", ""),
        ("no stop-condition-3 exception and ", ""),
        (" and no interactive question", ""),
    ],
}

GAR_SC1_MATCHERS = {key: gar_matcher(patterns) for key, _seg, patterns in GAR_SC1_ELEMENTS}
GAR_SC1_MATCHERS["E8f"] = gar_obsolete_sentences_are_scoped
GAR_SC1_SEGMENTS = {key: seg for key, seg, _patterns in GAR_SC1_ELEMENTS}
GAR_SC1_ORDER = [key for key, _seg, _patterns in GAR_SC1_ELEMENTS]

# E8f is a scope guard over the E8e claim: it accepts a block with no
# `obsolete` sentence at all (E8e is what requires one), and rejects an added
# sentence claiming obsolescence for a stop the gate does not close.
GAR_E8F_OVERREACH_SENTENCE = (
    "The packet of an origin-membership failure is also closed as `obsolete`."
)

# ---------------------------------------------------------------------------
# SC2 elements
# ---------------------------------------------------------------------------

GAR_SC2_ELEMENTS = [
    (
        "R1",
        "a review step already left `failed` by a gate abort is recovered by "
        "the orchestrator when both hold: `workflow[review].status` is "
        "`failed`, and the last entry of `classification` in "
        "`phase-state/rework.yaml` (record shape: `references/phase-state.md`) "
        "has `decision: stop`.",
        [
            r"both hold",
            r"`workflow\[review\]\.status` is `failed`",
            r"last entry of `classification` in `phase-state/rework\.yaml`",
            r"`references/phase-state\.md`",
            r"has `decision: stop`",
        ],
    ),
    (
        "R2",
        "The procedure restores `workflow[review].status` and `review.status` "
        "to `pending`, and `review.needs_rework` to `true`.",
        [
            r"restores `workflow\[review\]\.status` and `review\.status` to "
            r"`pending`",
            r"`review\.needs_rework` to `true`",
        ],
    ),
    (
        "R3",
        "The write is committed with `commit-docs.sh`.",
        [r"committed with `commit-docs\.sh`"],
    ),
    (
        "R4",
        "When the record does not confirm both conditions — the file is "
        "absent, the `classification` list is empty, or its last entry is "
        "not `decision: stop` — the procedure is not applied and stop "
        "condition 3's ordinary stop stands.",
        [
            r"record does not confirm",
            r"file is absent",
            r"`classification` list is empty",
            r"last entry is not `decision: stop`",
            r"procedure is not applied",
            r"stop condition 3's ordinary stop stands",
        ],
    ),
    (
        "R5",
        "After the procedure, the run resumes through the resume path of the "
        "`Spec-change gate abort (review-sourced rework)` block above.",
        [
            r"resumes through the resume path of the "
            r"`Spec-change gate abort \(review-sourced rework\)` block",
        ],
    ),
    (
        "R6",
        "The procedure adds no Step B branch and no stop-condition-3 "
        "exception.",
        [r"adds no Step B branch and no stop-condition-3 exception"],
    ),
]

GAR_SC2_MUTANTS = {
    "R1": [
        ("when both hold", "when either holds"),
        ("`workflow[review].status` is `failed`", "`workflow[review].status` is `pending`"),
        ("the last entry of `classification`", "the first entry of `classification`"),
        ("(record shape: `references/phase-state.md`)", ""),
        ("has `decision: stop`", "has `decision: proceed`"),
    ],
    "R2": [
        ("`workflow[review].status` and `review.status` to `pending`", "`workflow[review].status` to `pending`"),
        ("`review.needs_rework` to `true`", "`review.needs_rework` to `false`"),
    ],
    "R3": [("is committed with `commit-docs.sh`", "is left uncommitted")],
    "R4": [
        ("When the record does not confirm both conditions", "When the record is read"),
        ("the file is absent, ", ""),
        ("the `classification` list is empty, or ", ""),
        ("its last entry is not `decision: stop`", "its last entry is unreadable"),
        ("the procedure is not applied", "the procedure is applied"),
        ("stop condition 3's ordinary stop stands", "the run continues"),
    ],
    "R5": [
        ("resumes through the resume path of the", "resumes through a path unrelated to the"),
    ],
    "R6": [
        ("adds no Step B branch and no stop-condition-3 exception", "adds a Step B branch"),
    ],
}

GAR_SC2_MATCHERS = {key: gar_matcher(patterns) for key, _seg, patterns in GAR_SC2_ELEMENTS}
GAR_SC2_SEGMENTS = {key: seg for key, seg, _patterns in GAR_SC2_ELEMENTS}
GAR_SC2_ORDER = [key for key, _seg, _patterns in GAR_SC2_ELEMENTS]


def gar_synth_block(label, order, segments, skip=None, replace=None, extra=""):
    """A minimal synthetic block: bold label, then the segments in order,
    optionally lacking one key, with one (old, new) mutation applied to one
    key's segment, or with an extra sentence appended."""
    parts = []
    for key in order:
        if key == skip:
            continue
        seg = segments[key]
        if replace is not None and replace[0] == key:
            old, new = replace[1]
            if old not in seg:
                raise AssertionError("mutant text not found in %s: %r" % (key, old))
            seg = seg.replace(old, new)
        parts.append(seg)
    return gar_collapse(gar_bold(label) + ": " + " ".join(parts) + " " + extra)


# ---------------------------------------------------------------------------
# Tests against the pinned documents
# ---------------------------------------------------------------------------


class TestPinnedDocumentRegions(unittest.TestCase):
    """AC-1, AC-3, AC-5, AC-6: regions are present and non-empty; the labels
    occur once, open a paragraph and sit in the stated order."""

    @classmethod
    def setUpClass(cls):
        cls.text = gar_read(GAR_REVIEW_PHASE_PATH)
        cls.r5 = gar_slice_phase_r5(cls.text)

    def test_phase_r5_region_is_present_and_non_empty(self):
        self.assertTrue(gar_nonvacuous(self.r5))

    def test_sc1_region_is_present_and_non_empty(self):
        self.assertTrue(gar_nonvacuous(gar_slice_sc1(self.r5)))

    def test_sc2_region_is_present_and_non_empty(self):
        self.assertTrue(gar_nonvacuous(gar_slice_sc2(self.r5)))

    def test_reservation_paragraph_is_present_and_non_empty(self):
        self.assertTrue(gar_nonvacuous(gar_reservation_paragraph(self.text)))

    def test_sc1_label_bold_form_occurs_exactly_once(self):
        self.assertTrue(gar_label_single_bold(self.text, GAR_SC1_LABEL))

    def test_sc2_label_bold_form_occurs_exactly_once(self):
        self.assertTrue(gar_label_single_bold(self.text, GAR_SC2_LABEL))

    def test_sc1_label_opens_a_paragraph(self):
        self.assertTrue(gar_label_opens_paragraph(self.r5, GAR_SC1_LABEL))

    def test_sc2_label_opens_a_paragraph(self):
        self.assertTrue(gar_label_opens_paragraph(self.r5, GAR_SC2_LABEL))

    def test_blocks_are_placed_after_batch_paragraphs_and_before_r6(self):
        self.assertTrue(gar_placement_ok(self.text))

    def test_gate_id_substring_is_absent(self):
        self.assertTrue(gar_gate_id_absent(self.text))

    def test_rework_gate_literal_is_absent(self):
        self.assertTrue(gar_rework_gate_literal_absent(self.text))


class TestSc1BlockInDocument(unittest.TestCase):
    """AC-1 (E1-E7) and AC-2 (E8-E10): each element is stated in the SC1
    block of the pinned document."""

    @classmethod
    def setUpClass(cls):
        text = gar_read(GAR_REVIEW_PHASE_PATH)
        cls.sc1 = gar_collapse(gar_slice_sc1(gar_slice_phase_r5(text)))

    def test_sc1_block_is_non_empty(self):
        self.assertTrue(gar_nonvacuous(self.sc1))

    def test_every_sc1_element_has_a_matcher(self):
        self.assertEqual(
            set(GAR_SC1_ORDER) | {"E8f"}, set(GAR_SC1_MATCHERS.keys())
        )

    def test_each_sc1_element_is_stated(self):
        for key in GAR_SC1_ORDER + ["E8f"]:
            with self.subTest(element=key):
                self.assertTrue(
                    GAR_SC1_MATCHERS[key](self.sc1),
                    "SC1 element %s is not stated in the SC1 block" % key,
                )


class TestSc2BlockInDocument(unittest.TestCase):
    """AC-3: R1-R6 are stated in the SC2 block of the pinned document."""

    @classmethod
    def setUpClass(cls):
        text = gar_read(GAR_REVIEW_PHASE_PATH)
        cls.sc2 = gar_collapse(gar_slice_sc2(gar_slice_phase_r5(text)))

    def test_sc2_block_is_non_empty(self):
        self.assertTrue(gar_nonvacuous(self.sc2))

    def test_each_sc2_element_is_stated(self):
        for key in GAR_SC2_ORDER:
            with self.subTest(element=key):
                self.assertTrue(
                    GAR_SC2_MATCHERS[key](self.sc2),
                    "SC2 element %s is not stated in the SC2 block" % key,
                )


class TestReservationParagraphInDocument(unittest.TestCase):
    """AC-4: the reservation sentence is unchanged and its paragraph states
    the reservation's scope, citing the SC1 label."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = gar_reservation_paragraph(gar_read(GAR_REVIEW_PHASE_PATH))

    def test_reservation_sentence_is_verbatim(self):
        self.assertTrue(gar_reservation_sentence_verbatim(self.paragraph))

    def test_reservation_scope_statement_is_present(self):
        self.assertTrue(gar_reservation_scope_ok(self.paragraph))


class TestSchemaStatusSetsUnchanged(unittest.TestCase):
    """AC-4 (NFR5): workflow-schema.md's status value sets are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = gar_read(GAR_SCHEMA_PATH)

    def test_parsed_sets_are_non_empty(self):
        step_set, review_set = gar_parse_status_sets(self.text)
        self.assertTrue(step_set)
        self.assertTrue(review_set)

    def test_step_status_value_set_is_unchanged(self):
        step_set, _ = gar_parse_status_sets(self.text)
        self.assertEqual(GAR_EXPECTED_STEP_STATUSES, step_set)

    def test_review_block_status_value_set_is_unchanged(self):
        _, review_set = gar_parse_status_sets(self.text)
        self.assertEqual(GAR_EXPECTED_REVIEW_STATUSES, review_set)


# ---------------------------------------------------------------------------
# Negative twins: each matcher rejects what it must
# ---------------------------------------------------------------------------


class TestSc1NegativeTwins(unittest.TestCase):
    """AC-1, AC-2, AC-6: a synthetic SC1 block with every element is accepted
    by every matcher; the variant lacking exactly one element is rejected by
    that element's matcher and still accepted by every other matcher."""

    def _block(self, **kwargs):
        return gar_synth_block(
            GAR_SC1_LABEL, GAR_SC1_ORDER, GAR_SC1_SEGMENTS, **kwargs
        )

    def test_full_synthetic_block_is_accepted_by_every_matcher(self):
        block = self._block()
        for key, matcher in GAR_SC1_MATCHERS.items():
            with self.subTest(element=key):
                self.assertTrue(matcher(block))

    def test_variant_lacking_one_element_is_rejected_by_that_matcher_only(self):
        for key in GAR_SC1_ORDER:
            variant = self._block(skip=key)
            with self.subTest(removed=key):
                self.assertFalse(
                    GAR_SC1_MATCHERS[key](variant),
                    "matcher %s accepted a block lacking its element" % key,
                )
                for other, matcher in GAR_SC1_MATCHERS.items():
                    if other == key:
                        continue
                    self.assertTrue(
                        matcher(variant),
                        "removing %s also broke matcher %s" % (key, other),
                    )

    def test_each_weakened_mutant_is_rejected_by_its_matcher(self):
        for key, mutants in GAR_SC1_MUTANTS.items():
            for index, mutant in enumerate(mutants):
                variant = self._block(replace=(key, mutant))
                with self.subTest(element=key, mutant=index):
                    self.assertNotEqual(variant, self._block())
                    self.assertFalse(
                        GAR_SC1_MATCHERS[key](variant),
                        "matcher %s accepted weakened mutant %d" % (key, index),
                    )

    def test_every_mutated_key_names_a_real_element(self):
        self.assertTrue(set(GAR_SC1_MUTANTS) <= set(GAR_SC1_ORDER))

    def test_every_sc1_element_has_a_removal_twin(self):
        # The removal-twin loop above walks GAR_SC1_ORDER; the matcher table
        # must hold exactly those keys plus the scope guard.
        self.assertEqual(
            set(GAR_SC1_ORDER) | {"E8f"}, set(GAR_SC1_MATCHERS.keys())
        )

    def test_overreaching_obsolescence_claim_is_rejected_by_scope_guard(self):
        variant = self._block(extra=GAR_E8F_OVERREACH_SENTENCE)
        self.assertFalse(GAR_SC1_MATCHERS["E8f"](variant))
        self.assertTrue(GAR_SC1_MATCHERS["E8e"](variant))

    def test_scope_guard_accepts_block_with_no_obsolete_sentence(self):
        self.assertTrue(
            GAR_SC1_MATCHERS["E8f"](self._block(skip="E8e"))
        )


class TestSc2NegativeTwins(unittest.TestCase):
    """AC-3, AC-6: the same twin discipline for the SC2 block."""

    def _block(self, **kwargs):
        return gar_synth_block(
            GAR_SC2_LABEL, GAR_SC2_ORDER, GAR_SC2_SEGMENTS, **kwargs
        )

    def test_full_synthetic_block_is_accepted_by_every_matcher(self):
        block = self._block()
        for key, matcher in GAR_SC2_MATCHERS.items():
            with self.subTest(element=key):
                self.assertTrue(matcher(block))

    def test_variant_lacking_one_element_is_rejected_by_that_matcher_only(self):
        for key in GAR_SC2_ORDER:
            variant = self._block(skip=key)
            with self.subTest(removed=key):
                self.assertFalse(
                    GAR_SC2_MATCHERS[key](variant),
                    "matcher %s accepted a block lacking its element" % key,
                )
                for other, matcher in GAR_SC2_MATCHERS.items():
                    if other == key:
                        continue
                    self.assertTrue(
                        matcher(variant),
                        "removing %s also broke matcher %s" % (key, other),
                    )

    def test_each_weakened_mutant_is_rejected_by_its_matcher(self):
        for key, mutants in GAR_SC2_MUTANTS.items():
            for index, mutant in enumerate(mutants):
                variant = self._block(replace=(key, mutant))
                with self.subTest(element=key, mutant=index):
                    self.assertNotEqual(variant, self._block())
                    self.assertFalse(
                        GAR_SC2_MATCHERS[key](variant),
                        "matcher %s accepted weakened mutant %d" % (key, index),
                    )

    def test_every_mutated_key_names_a_real_element(self):
        self.assertTrue(set(GAR_SC2_MUTANTS) <= set(GAR_SC2_ORDER))

    def test_every_sc2_element_has_a_matcher_and_a_mutant_or_removal_twin(self):
        self.assertEqual(set(GAR_SC2_ORDER), set(GAR_SC2_MATCHERS.keys()))


class TestReservationNegativeTwins(unittest.TestCase):
    """AC-4, AC-6: the scope matcher rejects the pre-change paragraph."""

    def _post_change_paragraph(self):
        return gar_collapse(
            GAR_PRE_CHANGE_RESERVATION_PARAGRAPH
            + GAR_RESERVATION_SCOPE_STATEMENT
        )

    def test_pre_change_paragraph_keeps_the_verbatim_sentence(self):
        paragraph = gar_collapse(GAR_PRE_CHANGE_RESERVATION_PARAGRAPH)
        self.assertTrue(gar_reservation_sentence_verbatim(paragraph))

    def test_scope_matcher_rejects_the_pre_change_paragraph_verbatim(self):
        paragraph = gar_collapse(GAR_PRE_CHANGE_RESERVATION_PARAGRAPH)
        self.assertFalse(gar_reservation_scope_ok(paragraph))

    def test_scope_matcher_accepts_the_post_change_paragraph(self):
        self.assertTrue(gar_reservation_scope_ok(self._post_change_paragraph()))

    def test_paragraph_finder_locates_the_synthetic_paragraph(self):
        doc = "intro\n\n" + GAR_PRE_CHANGE_RESERVATION_PARAGRAPH + "\nnext\n\ntail\n"
        found = gar_reservation_paragraph(doc)
        self.assertIn(GAR_RESERVATION_SENTENCE, found)
        self.assertNotIn("tail", found)

    def test_paragraph_finder_returns_empty_without_the_sentence(self):
        self.assertEqual("", gar_reservation_paragraph("intro\n\nother\n"))

    def test_scope_matcher_rejects_each_weakened_variant(self):
        scope = GAR_RESERVATION_SCOPE_STATEMENT
        weakened = [
            scope.replace(
                "governs the `status` of `perspective_runs` entries",
                "governs every status",
            ),
            scope.replace("the `evaluator` entry's — ", ""),
            scope.replace(
                "and not the review step's `workflow[review].status` or the "
                "top-level `review.status`",
                "and the review step's `workflow[review].status`",
            ),
            scope.replace("`references/review-phase.md` ", ""),
            scope.replace("Phase R5, ", ""),
            scope.replace(
                "`Spec-change gate abort (review-sourced rework)`", "that block"
            ),
        ]
        for index, tail in enumerate(weakened):
            self.assertNotEqual(tail, scope)
            paragraph = gar_collapse(GAR_PRE_CHANGE_RESERVATION_PARAGRAPH + tail)
            with self.subTest(variant=index):
                self.assertFalse(gar_reservation_scope_ok(paragraph))

    def test_verbatim_matcher_rejects_an_altered_sentence(self):
        altered = gar_collapse(
            GAR_PRE_CHANGE_RESERVATION_PARAGRAPH.replace(
                "reserved for the two structural", "reserved for the structural"
            )
        )
        self.assertFalse(gar_reservation_sentence_verbatim(altered))

    def test_scope_matcher_rejects_text_without_the_reservation_sentence(self):
        self.assertFalse(gar_reservation_scope_ok(GAR_RESERVATION_SCOPE_STATEMENT))


class TestLabelNegativeTwins(unittest.TestCase):
    """AC-5, AC-6: the label matchers and the placement matcher reject
    forged texts."""

    def _doc(self, body):
        return (
            "## Phase R5: Persist the round record\n\n"
            + GAR_BATCH_OPENER
            + " rest of the paragraph.\n\n"
            + body
            + "\n\n## Phase R6: Report (Japanese)\n\ntail\n"
        )

    def _sc1(self):
        return gar_bold(GAR_SC1_LABEL) + ": text."

    def _sc2(self):
        return gar_bold(GAR_SC2_LABEL) + ": text."

    def test_well_formed_synthetic_document_is_accepted(self):
        doc = self._doc(self._sc1() + "\n\n" + self._sc2())
        self.assertTrue(gar_label_single_bold(doc, GAR_SC1_LABEL))
        self.assertTrue(gar_label_single_bold(doc, GAR_SC2_LABEL))
        self.assertTrue(gar_label_opens_paragraph(doc, GAR_SC1_LABEL))
        self.assertTrue(gar_label_opens_paragraph(doc, GAR_SC2_LABEL))
        self.assertTrue(gar_placement_ok(doc))

    def test_label_twice_is_rejected_by_single_occurrence_matcher(self):
        for label in (GAR_SC1_LABEL, GAR_SC2_LABEL):
            doc = self._doc(
                self._sc1() + "\n\n" + self._sc2() + "\n\n" + gar_bold(label) + ": again."
            )
            with self.subTest(label=label):
                self.assertFalse(gar_label_single_bold(doc, label))

    def test_missing_label_is_rejected_by_single_occurrence_matcher(self):
        doc = self._doc(self._sc1())
        self.assertFalse(gar_label_single_bold(doc, GAR_SC2_LABEL))

    def test_label_inside_a_paragraph_is_rejected_by_paragraph_start_matcher(self):
        doc = self._doc("Some earlier words " + self._sc1() + "\n\n" + self._sc2())
        self.assertFalse(gar_label_opens_paragraph(doc, GAR_SC1_LABEL))

    def test_sc2_before_sc1_is_rejected_by_placement_matcher(self):
        doc = self._doc(self._sc2() + "\n\n" + self._sc1())
        self.assertFalse(gar_placement_ok(doc))

    def test_sc1_before_the_batch_opener_is_rejected_by_placement_matcher(self):
        doc = (
            "## Phase R5: Persist the round record\n\n"
            + self._sc1()
            + "\n\n"
            + GAR_BATCH_OPENER
            + " rest.\n\n"
            + self._sc2()
            + "\n\n## Phase R6: Report (Japanese)\n"
        )
        self.assertFalse(gar_placement_ok(doc))

    def test_blocks_after_the_r6_heading_are_rejected_by_placement_matcher(self):
        doc = (
            "## Phase R5: Persist the round record\n\n"
            + GAR_BATCH_OPENER
            + " rest.\n\n## Phase R6: Report (Japanese)\n\n"
            + self._sc1()
            + "\n\n"
            + self._sc2()
            + "\n"
        )
        self.assertFalse(gar_placement_ok(doc))

    def test_missing_block_is_rejected_by_placement_matcher(self):
        doc = self._doc(self._sc1())
        self.assertFalse(gar_placement_ok(doc))

    def test_gate_id_in_text_is_rejected_by_absence_matcher(self):
        self.assertTrue(gar_gate_id_absent("the spec-change question"))
        self.assertFalse(gar_gate_id_absent("the `gate_id` of the question"))

    def test_rework_gate_literal_in_text_is_rejected_by_absence_matcher(self):
        self.assertTrue(gar_rework_gate_literal_absent("the spec-change question"))
        self.assertFalse(
            gar_rework_gate_literal_absent(
                "the `" + GAR_REWORK_GATE_LITERAL + "` question"
            )
        )


class TestRegionNonVacuityTwins(unittest.TestCase):
    """AC-6: the non-vacuity check rejects empty regions, and each slicer
    yields an empty region when its anchors are missing."""

    def test_nonvacuity_check_rejects_empty_and_blank_regions(self):
        self.assertFalse(gar_nonvacuous(""))
        self.assertFalse(gar_nonvacuous("  \n\t "))
        self.assertTrue(gar_nonvacuous("text"))

    def test_phase_slicer_yields_empty_region_without_its_headings(self):
        self.assertEqual("", gar_slice_phase_r5("no headings here\n"))
        self.assertEqual(
            "", gar_slice_phase_r5("## Phase R5: Persist the round record\nbody\n")
        )

    def test_block_slicers_yield_empty_regions_without_their_labels(self):
        self.assertEqual("", gar_slice_sc1("body without labels"))
        self.assertEqual("", gar_slice_sc2("body without labels"))
        only_sc2 = gar_bold(GAR_SC2_LABEL) + ": text"
        self.assertEqual("", gar_slice_sc1(only_sc2))

    def test_block_slicers_split_at_the_sc2_label(self):
        r5 = (
            "lead\n\n"
            + gar_bold(GAR_SC1_LABEL)
            + ": one\n\n"
            + gar_bold(GAR_SC2_LABEL)
            + ": two\n"
        )
        self.assertIn("one", gar_slice_sc1(r5))
        self.assertNotIn("two", gar_slice_sc1(r5))
        self.assertIn("two", gar_slice_sc2(r5))
        self.assertNotIn("one", gar_slice_sc2(r5))


class TestSchemaNegativeTwins(unittest.TestCase):
    """AC-4, AC-6: the schema guard rejects a forged value-set comment."""

    GENUINE = (
        "workflow:\n"
        "  - id: create-spec\n"
        "    status: completed    # pending | in_progress | completed | failed "
        "| needs_update\n"
        "tasks:\n"
        "  t:\n"
        "    status: pending      # pending | in_progress | merged | failed\n"
        "review:\n"
        "  status: pending        # pending | in_progress | completed | failed\n"
        "  rounds_completed: 0\n"
    )

    def test_genuine_synthetic_schema_is_accepted(self):
        self.assertTrue(gar_schema_sets_ok(self.GENUINE))

    def test_forged_step_comment_with_an_extra_value_is_rejected(self):
        forged = self.GENUINE.replace(
            "failed | needs_update", "failed | needs_update | paused"
        )
        self.assertNotEqual(forged, self.GENUINE)
        self.assertFalse(gar_schema_sets_ok(forged))

    def test_forged_review_comment_with_an_extra_value_is_rejected(self):
        forged = self.GENUINE.replace(
            "  status: pending        # pending | in_progress | completed | failed",
            "  status: pending        # pending | in_progress | completed | failed | paused",
        )
        self.assertNotEqual(forged, self.GENUINE)
        self.assertFalse(gar_schema_sets_ok(forged))

    def test_forged_comment_missing_a_value_is_rejected(self):
        forged = self.GENUINE.replace("completed | failed | needs_update", "completed | needs_update")
        self.assertNotEqual(forged, self.GENUINE)
        self.assertFalse(gar_schema_sets_ok(forged))

    def test_text_without_the_blocks_parses_to_empty_sets(self):
        self.assertEqual((set(), set()), gar_parse_status_sets("nothing here\n"))
        self.assertFalse(gar_schema_sets_ok("nothing here\n"))


if __name__ == "__main__":
    unittest.main()

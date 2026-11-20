"""Text-inspection tests for task0004 of review-perspective-model-effort: the
review phase sends a codex entry's `effort` to the reviewer and records it.

Acceptance criteria covered (feature-docs/review-perspective-model-effort/
tasks/task0004.md):

- AC-1: in both `review-phase.md` files, the Phase R2 codex bullet states that
  an entry's `effort: E` is added to the input block as `effort: E`, passed
  through verbatim with no allow-list check; the litellm bullet adds no
  `effort`; the chain entry shape reads `{harness, model?, effort?}`.
- AC-2: em-workflow's Phase R2b and Phase R4 "same input block" sentences are
  unchanged (pinned literally; neither section mentions `effort`).
- AC-3: em-workflow's Phase R3a `perspectives_dispatched` description lists
  `effort` for codex runs given an `effort`; its Phase R5 `perspective_runs`
  example has a codex row carrying `effort`, and the comment there says
  `effort` is attached only to a codex run given one.
- AC-4: em-review's round-record `perspective_runs` example has a codex row
  carrying `effort` and the same comment; no litellm example row in either
  document carries `effort`.
- AC-6: every check here is a pure function of the text it receives, scoped to
  its own region (the R2 codex bullet, the R2 litellm bullet, the R3a
  `perspectives_dispatched` bullet, the `perspective_runs` block of the R5
  example), and each has a negative proof on forged text.

Test Notes followed:
- Each region is sliced between phase headings, so a mention of `effort`
  elsewhere in the document cannot satisfy a check.
- The record comment is Japanese; its phrases are matched with all whitespace
  removed, because the comment wraps at arbitrary points.
- AC-5 (the pinned digest refresh) is asserted by
  `tests/test_tier_record_schema_v2.py`, not here.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"
EM_REVIEW_PATH = REPO_ROOT / "em-review" / "references" / "review-phase.md"

R2_HEADING = "## Phase R2: Fan-out"
R2B_HEADING = "## Phase R2b: Cross-model fallback"
R3A_HEADING = "## Phase R3a: Evaluation"
R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R4_HEADING = "## Phase R4: Bounded auto-fix"
R5_HEADING = "## Phase R5: Persist the round record"
R6_HEADING = "## Phase R6: Report (Japanese)"

CODEX_BULLET_LEAD = "- `{harness: codex}`"
LITELLM_BULLET_LEAD = "- `{harness: litellm"
DISPATCHED_BULLET_LEAD = "- `perspectives_dispatched`"

OLD_CHAIN_SHAPE = "`{harness, model?}`"
NEW_CHAIN_SHAPE = "`{harness, model?, effort?}`"

# The one sentence of the codex bullet that sends the effort. It is a single
# sentence with no period inside it.
EFFORT_SENTENCE = re.compile(r"When the entry names `effort: E`[^.]*\.")
EFFORT_SENTENCE_PHRASES = (
    "add `effort: E` to the same input block",
    "passed through verbatim",
    "with no allow-list check",
)
ONLY_THIS_BULLET_PHRASE = "Only this bullet adds `effort`"

# Pinned literally: R2b's and R4's "same input block" sentences, byte for byte
# as they stood before this task. Their wording already covers `effort`.
R2B_SAME_INPUT_BLOCK = (
    "- Every dispatch in this chain walk — including the chain-exhaustion "
    "Claude\n"
    "  fallback — carries the same review-protocol input block Phase R2\n"
    "  assembled for that perspective (for that shard, in a split pass); for "
    "the\n"
    "  `security` perspective this includes the same `threat_model_path` "
    "value the\n"
    "  round's R2 dispatch carried, unchanged across every hop.\n"
)
R4_SAME_INPUT_BLOCK = (
    "note). Each re-reviewed perspective's dispatch carries the same\n"
    "review-protocol input block as the round's R2 dispatch; for the "
    "`security`\n"
    "perspective this includes the same `threat_model_path` value, "
    "unchanged.\n"
)

# The Japanese sentences of the `perspective_runs` comment, whitespace removed.
MODEL_COMMENT_SENTENCE = (
    "`model`はlitellmハーネスと、`model`を渡したcodexのときだけ付ける。"
)
EFFORT_COMMENT_START = "`effort`は`effort`を渡したcodexのときだけ付ける。"
EFFORT_COMMENT_NOT_LITELLM = "litellmの行には付けず"
EFFORT_COMMENT_NOT_BARE_CODEX = "`effort`を渡していないcodexの行にも付けない。"


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _compact(text):
    return re.sub(r"\s+", "", text)


def section(text, start_heading, end_heading):
    """The text from the heading line `start_heading` up to `end_heading`."""
    start = re.search(r"^" + re.escape(start_heading), text, re.M)
    if start is None:
        raise ValueError("heading not found: %s" % start_heading)
    end = re.search(r"^" + re.escape(end_heading), text[start.end():], re.M)
    if end is None:
        raise ValueError("heading not found: %s" % end_heading)
    return text[start.start():start.end() + end.start()]


def bullet(text, lead):
    """The list item whose first line starts with `lead` (after indent), with
    its continuation lines (more deeply indented), up to the next item."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith(lead):
            continue
        indent = len(line) - len(stripped)
        item = [line]
        for following in lines[index + 1:]:
            if not following.strip():
                break
            if len(following) - len(following.lstrip()) <= indent:
                break
            item.append(following)
        return "\n".join(item)
    raise ValueError("bullet not found: %s" % lead)


# -- AC-1: the Phase R2 codex bullet and litellm bullet -----------------------


def codex_bullet_problems(bullet_text):
    """What is missing from a Phase R2 codex bullet; empty when it is right."""
    norm = _norm(bullet_text)
    match = EFFORT_SENTENCE.search(norm)
    if match is None:
        return ["no sentence 'When the entry names `effort: E`, ...'"]
    problems = []
    for phrase in EFFORT_SENTENCE_PHRASES:
        if phrase not in match.group(0):
            problems.append("effort sentence lacks: %s" % phrase)
    if ONLY_THIS_BULLET_PHRASE not in norm:
        problems.append("missing: %s" % ONLY_THIS_BULLET_PHRASE)
    return problems


def litellm_bullet_mentions_effort(bullet_text):
    return "effort" in bullet_text.lower()


def chain_shape_problems(r2_text):
    """The R2 text must name the chain entry shape with `effort?` only."""
    norm = _norm(r2_text)
    problems = []
    if NEW_CHAIN_SHAPE not in norm:
        problems.append("missing %s" % NEW_CHAIN_SHAPE)
    if OLD_CHAIN_SHAPE in norm:
        problems.append("still names %s" % OLD_CHAIN_SHAPE)
    return problems


# -- AC-3: the R3a `perspectives_dispatched` bullet ---------------------------

DISPATCHED_MODEL_PHRASE = (
    "`model` for litellm runs and for codex runs given a `model`"
)
DISPATCHED_EFFORT_PHRASE = "`effort` for codex runs given an `effort`"


def dispatched_bullet_problems(bullet_text):
    norm = _norm(bullet_text)
    problems = []
    if DISPATCHED_MODEL_PHRASE not in norm:
        problems.append("lost: %s" % DISPATCHED_MODEL_PHRASE)
    if DISPATCHED_EFFORT_PHRASE not in norm:
        problems.append("missing: %s" % DISPATCHED_EFFORT_PHRASE)
    if "`effort` for litellm" in norm:
        problems.append("lists `effort` for litellm runs")
    return problems


# -- AC-3 / AC-4: the `perspective_runs` example of the round record ----------


def perspective_runs_block(record_section):
    match = re.search(
        r"^perspective_runs:\n(.*?)(?=^findings:)",
        record_section,
        re.M | re.S,
    )
    if match is None:
        raise ValueError("perspective_runs example block not found")
    return match.group(1)


def example_rows(block):
    return [line for line in block.split("\n") if re.match(r"\s*- \{", line)]


def comment_lines(block):
    return [line for line in block.split("\n") if line.lstrip().startswith("#")]


def _source_of(row):
    match = re.search(r"\bsource: (\w+)", row)
    return match.group(1) if match else None


def codex_rows_with_model_and_effort(block):
    return [
        row
        for row in example_rows(block)
        if _source_of(row) == "codex"
        and re.search(r"\bmodel: [\w.\-]+", row)
        and re.search(r"\beffort: [a-z]+", row)
    ]


def rows_with_effort_outside_codex(block):
    return [
        row
        for row in example_rows(block)
        if "effort" in row and _source_of(row) != "codex"
    ]


def litellm_rows(block):
    return [row for row in example_rows(block) if _source_of(row) == "litellm"]


def comment_problems(block):
    """What the Japanese comment lacks about when `effort` is attached."""
    compact = _compact("".join(
        line.lstrip().lstrip("#") for line in comment_lines(block)
    ))
    problems = []
    if MODEL_COMMENT_SENTENCE not in compact:
        problems.append("lost the `model` sentence")
    start = compact.find(EFFORT_COMMENT_START)
    if start == -1:
        return problems + ["no `effort` sentence"]
    # The `effort` statement is two sentences: the opening one found above,
    # then the one that excludes a litellm row and a codex row without
    # `effort`. Scope the exclusion checks to those two sentences.
    second_end = compact.find("。", start + len(EFFORT_COMMENT_START))
    statement = compact[start:] if second_end == -1 else compact[start:second_end + 1]
    if EFFORT_COMMENT_NOT_LITELLM not in statement:
        problems.append("does not exclude litellm")
    if EFFORT_COMMENT_NOT_BARE_CODEX not in statement:
        problems.append("does not exclude a codex run without `effort`")
    return problems


class _R2Checks:
    """Phase R2 checks, run once per plugin."""

    PATH = None

    @classmethod
    def setUpClass(cls):
        cls.text = _read(cls.PATH)
        cls.r2 = section(cls.text, R2_HEADING, R2B_HEADING)
        cls.codex = bullet(cls.r2, CODEX_BULLET_LEAD)
        cls.litellm = bullet(cls.r2, LITELLM_BULLET_LEAD)

    # AC-1 positive checks

    def test_codex_bullet_sends_effort_verbatim_without_allow_list(self):
        self.assertEqual(codex_bullet_problems(self.codex), [])

    def test_litellm_bullet_never_adds_effort(self):
        self.assertFalse(litellm_bullet_mentions_effort(self.litellm))

    def test_chain_entry_shape_names_effort(self):
        self.assertEqual(chain_shape_problems(self.r2), [])

    # non-vacuity guards

    def test_non_vacuity_codex_bullet_still_sends_model(self):
        self.assertIn("add `model: M` to the input block", _norm(self.codex))

    def test_non_vacuity_litellm_bullet_still_sends_model(self):
        self.assertIn("`model: M`", _norm(self.litellm))

    def test_non_vacuity_effort_sentence_is_inside_the_codex_bullet_only(self):
        self.assertIn("effort", self.codex)
        self.assertEqual(self.r2.count(CODEX_BULLET_LEAD), 1)

    # negative proofs on forged text

    def test_forged_bullet_without_the_effort_sentence_is_rejected(self):
        forged = EFFORT_SENTENCE.sub("", _norm(self.codex))
        self.assertNotEqual(forged, _norm(self.codex), "forge changed nothing")
        self.assertNotEqual(codex_bullet_problems(forged), [])

    def test_forged_bullet_that_adds_an_allow_list_check_is_rejected(self):
        forged = _norm(self.codex).replace(
            "with no allow-list check", "after an allow-list check"
        )
        self.assertNotEqual(forged, _norm(self.codex), "forge changed nothing")
        self.assertNotEqual(codex_bullet_problems(forged), [])

    def test_forged_bullet_that_rewrites_the_value_is_rejected(self):
        forged = _norm(self.codex).replace(
            "passed through verbatim, with no allow-list check",
            "normalized to lowercase, with no allow-list check",
        )
        self.assertNotEqual(forged, _norm(self.codex), "forge changed nothing")
        self.assertNotEqual(codex_bullet_problems(forged), [])

    def test_forged_bullet_without_the_only_this_bullet_sentence_is_rejected(self):
        forged = _norm(self.codex).replace(ONLY_THIS_BULLET_PHRASE, "Any bullet adds")
        self.assertNotEqual(forged, _norm(self.codex), "forge changed nothing")
        self.assertNotEqual(codex_bullet_problems(forged), [])

    def test_forged_litellm_bullet_that_adds_effort_is_rejected(self):
        forged = self.litellm + "\n  Also add `effort: E` to the input block.\n"
        self.assertTrue(litellm_bullet_mentions_effort(forged))

    def test_forged_section_with_the_old_chain_shape_is_rejected(self):
        forged = _norm(self.r2).replace(NEW_CHAIN_SHAPE, OLD_CHAIN_SHAPE)
        self.assertNotEqual(forged, _norm(self.r2), "forge changed nothing")
        self.assertNotEqual(chain_shape_problems(forged), [])

    def test_forged_section_with_both_chain_shapes_is_rejected(self):
        forged = _norm(self.r2) + " Also " + OLD_CHAIN_SHAPE
        self.assertNotEqual(chain_shape_problems(forged), [])


class _RecordChecks:
    """`perspective_runs` example checks, run once per plugin."""

    PATH = None

    @classmethod
    def setUpClass(cls):
        cls.text = _read(cls.PATH)
        cls.r5 = section(cls.text, R5_HEADING, R6_HEADING)
        cls.block = perspective_runs_block(cls.r5)

    # AC-3 / AC-4 positive checks

    def test_a_codex_example_row_carries_model_and_effort(self):
        self.assertNotEqual(codex_rows_with_model_and_effort(self.block), [])

    def test_no_non_codex_example_row_carries_effort(self):
        self.assertEqual(rows_with_effort_outside_codex(self.block), [])

    def test_comment_says_effort_is_attached_only_to_a_codex_run_given_one(self):
        self.assertEqual(comment_problems(self.block), [])

    # non-vacuity guards

    def test_non_vacuity_example_has_litellm_rows(self):
        self.assertNotEqual(litellm_rows(self.block), [])

    def test_non_vacuity_example_has_codex_rows(self):
        self.assertNotEqual(
            [r for r in example_rows(self.block) if _source_of(r) == "codex"], []
        )

    def test_non_vacuity_litellm_rows_still_carry_model(self):
        for row in litellm_rows(self.block):
            self.assertRegex(row, r"\bmodel: ")

    # negative proofs on forged text

    def test_forged_litellm_row_carrying_effort_is_rejected(self):
        forged = self.block.replace(
            "source: litellm, model: muse-spark,",
            "source: litellm, model: muse-spark, effort: high,",
            1,
        )
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertNotEqual(rows_with_effort_outside_codex(forged), [])

    def test_forged_claude_row_carrying_effort_is_rejected(self):
        forged = self.block + (
            "  - {perspective: spec, source: claude, effort: high, "
            "status: completed}\n"
        )
        self.assertNotEqual(rows_with_effort_outside_codex(forged), [])

    def test_forged_block_without_an_effort_row_is_rejected(self):
        forged = re.sub(r" effort: [a-z]+,", "", self.block)
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertEqual(codex_rows_with_model_and_effort(forged), [])

    def test_forged_block_with_effort_but_no_model_is_rejected(self):
        forged = re.sub(r" model: gpt[\w.\-]*,", "", self.block)
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertEqual(codex_rows_with_model_and_effort(forged), [])

    def test_forged_comment_without_the_effort_sentence_is_rejected(self):
        forged = "\n".join(
            line for line in self.block.split("\n")
            if not (line.lstrip().startswith("#") and "`effort`" in line)
        )
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertNotEqual(comment_problems(forged), [])

    def test_forged_comment_that_attaches_effort_to_litellm_is_rejected(self):
        forged = re.sub(r"litellm の行には付けず", "litellm の行にも付け", self.block)
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertNotEqual(comment_problems(forged), [])

    def test_forged_comment_that_attaches_effort_to_every_codex_run_is_rejected(self):
        forged = re.sub(
            r"`effort` を渡していない codex の行にも付けない",
            "`effort` を渡していない codex の行にも付ける",
            self.block,
        )
        self.assertNotEqual(forged, self.block, "forge changed nothing")
        self.assertNotEqual(comment_problems(forged), [])


class EmWorkflowR2Test(_R2Checks, unittest.TestCase):
    PATH = EM_WORKFLOW_PATH


class EmReviewR2Test(_R2Checks, unittest.TestCase):
    PATH = EM_REVIEW_PATH


class EmWorkflowRecordTest(_RecordChecks, unittest.TestCase):
    PATH = EM_WORKFLOW_PATH


class EmReviewRecordTest(_RecordChecks, unittest.TestCase):
    PATH = EM_REVIEW_PATH


class EmWorkflowR3aDispatchedTest(unittest.TestCase):
    """AC-3: em-workflow's R3a `perspectives_dispatched` description."""

    @classmethod
    def setUpClass(cls):
        text = _read(EM_WORKFLOW_PATH)
        cls.r3a = section(text, R3A_HEADING, R3B_HEADING)
        cls.bullet = bullet(cls.r3a, DISPATCHED_BULLET_LEAD)

    def test_lists_effort_for_codex_runs_given_an_effort(self):
        self.assertEqual(dispatched_bullet_problems(self.bullet), [])

    def test_non_vacuity_bullet_still_lists_the_other_entry_fields(self):
        norm = _norm(self.bullet)
        for field in ("`run_id`", "`perspective`", "`role`", "`status`",
                      "`skip_reason`"):
            self.assertIn(field, norm)

    def test_forged_bullet_without_effort_is_rejected(self):
        forged = re.sub(r",? and `effort` for codex runs given an `effort`", "",
                        _norm(self.bullet))
        self.assertNotEqual(forged, _norm(self.bullet), "forge changed nothing")
        self.assertNotEqual(dispatched_bullet_problems(forged), [])

    def test_forged_bullet_listing_effort_for_litellm_runs_is_rejected(self):
        forged = _norm(self.bullet).replace(
            DISPATCHED_EFFORT_PHRASE,
            "`effort` for litellm runs and for codex runs given an `effort`",
        )
        self.assertNotEqual(forged, _norm(self.bullet), "forge changed nothing")
        self.assertNotEqual(dispatched_bullet_problems(forged), [])


class EmWorkflowR2bR4UnchangedTest(unittest.TestCase):
    """AC-2: R2b's and R4's "same input block" sentences are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(EM_WORKFLOW_PATH)
        cls.r2b = section(cls.text, R2B_HEADING, R3A_HEADING)
        cls.r4 = section(cls.text, R4_HEADING, R5_HEADING)

    def test_r2b_same_input_block_sentence_is_byte_identical(self):
        self.assertIn(R2B_SAME_INPUT_BLOCK, self.r2b)

    def test_r4_same_input_block_sentence_is_byte_identical(self):
        self.assertIn(R4_SAME_INPUT_BLOCK, self.r4)

    def test_r2b_does_not_mention_effort(self):
        self.assertNotIn("effort", self.r2b)

    def test_r4_does_not_mention_effort(self):
        self.assertNotIn("effort", self.r4)

    def test_forged_r2b_sentence_with_effort_is_not_the_pinned_one(self):
        forged = self.r2b.replace(
            "carries the same review-protocol input block Phase R2",
            "carries the same review-protocol input block (and `effort`) Phase R2",
        )
        self.assertNotEqual(forged, self.r2b, "forge changed nothing")
        self.assertNotIn(R2B_SAME_INPUT_BLOCK, forged)

    def test_forged_r4_section_mentioning_effort_is_rejected(self):
        forged = self.r4 + "\nThe re-review carries `effort`.\n"
        self.assertIn("effort", forged)


if __name__ == "__main__":
    unittest.main()

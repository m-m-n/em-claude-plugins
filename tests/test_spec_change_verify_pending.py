"""Recurrence tests for task0001 of spec-change-rework-reentry (FR7 (a)):
the SPEC-change transition returns `verify` to `pending`.

Covers the task0001 Acceptance Criteria
(feature-docs/spec-change-rework-reentry/tasks/task0001.md):

- AC-1: in `em-workflow/references/rework-task-synthesis.md`, step 2 of the
  `**When rework needs a SPEC.md change**` block names `create-plan`,
  `implement`, `review` and `verify` as set to `pending` and states that only
  their `status` is written (`verify`'s `result` / `failed_items` stay until
  the next verify run); the block has exactly the numbered steps 1-5, directly
  followed by the "Step 2's `create-plan` re-entry" paragraph.
- AC-2: in `em-workflow/references/contracts/rework-planner-contract.md`,
  step 2 of `## Specification-change transition` names the same four steps
  and the section's numbered steps are exactly 1-5.
- AC-3: in `em-workflow/agents/rework-planner.md`, the five-step summary of
  `## Specification-change transition` names `verify` among the steps set to
  `pending` and still describes a fixed five-step sequence.
- AC-4: `em-workflow/skills/develop/SKILL.md` 「verify フェーズ」 item 6
  carries one sentence that cites `references/rework-task-synthesis.md`
  Section 10 and states that `verify` also returns to `pending` when
  rework-planner returns `gate_id` `rework.spec-change` and the SPEC change
  is selected; the sentence lists none of the transition's steps; the
  「ターンを終わらせていい唯一の条件」 block is byte-identical to the base
  revision (held as a SHA-256 digest).
- AC-5: every matcher below is backed by a negative proof. The pre-change
  step 2 of each of the three documents and the pre-change item 6 are held
  verbatim as constants and the matchers reject them.
- AC-6: the four documents contain no Notion URL and no absolute path under
  `/home/`.

No assertion of this module reads Section 11 of
`rework-task-synthesis.md`: another task changes it in parallel. Standard
library only; the repository root is computed from this file's path. Wording
that may wrap is compared whitespace-normalised (the Japanese item 6 wraps
without a space, so every whitespace character is removed there).
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNTHESIS_PATH = REPO_ROOT / "em-workflow" / "references" / "rework-task-synthesis.md"
CONTRACT_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "rework-planner-contract.md"
)
AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "rework-planner.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "develop" / "SKILL.md"

# The four steps the SPEC-change transition's step 2 sets to `pending`.
STEP_NAMES = ("create-plan", "implement", "review", "verify")

# --- Section 10 of rework-task-synthesis.md --------------------------------
SYNTHESIS_BLOCK_LABEL = "**When rework needs a SPEC.md change**"
SYNTHESIS_REENTRY_PARAGRAPH = "Step 2's `create-plan` re-entry"
SYNTHESIS_PENDING_MARKER = "→ `pending`"
# What step 2 states after the list: only `status` is written and the
# verify result is left to the next verify run (SPEC A4).
STATUS_ONLY_FRAGMENTS = (
    "only these steps' `status`",
    "`verify`'s `result`",
    "`failed_items`",
    "next verify run",
)

# --- rework-planner-contract.md ---------------------------------------------
CONTRACT_HEADING = "\n## Specification-change transition\n"
CONTRACT_END_HEADING = (
    "\n## Other conditions under which a question packet may be returned\n"
)
CONTRACT_PENDING_MARKER = "to `pending`"

# --- agents/rework-planner.md -----------------------------------------------
AGENT_HEADING = "\n## Specification-change transition\n"
AGENT_CLAUSE_START = "`create-spec` step → `needs_update`;"
AGENT_CLAUSE_END = "`workflow[implement].base_commit`"
AGENT_FIXED_SEQUENCE = "a fixed five-step sequence"
AGENT_NEVER_PERFORM = "you never perform any of its five steps yourself"

# --- skills/develop/SKILL.md ------------------------------------------------
ITEM6_START = "6. fail → verify を `failed` にし"
ITEM6_END = "**batch 自動 rework の系譜 cap**"
# The last existing sentence of item 6; the added sentence follows it.
ITEM6_LAST_SENTENCE = "いずれの分岐も workflow.yaml 更新後に commit-docs.sh でコミットする"
STOP_LIST_START = "### ターンを終わらせていい唯一の条件"
STOP_LIST_END = "### してはならないこと"

# What the added sentence of item 6 must say (matched with every whitespace
# character removed). The path and "Section 10" are required in the added
# sentence itself: the pre-change item 6 already names both earlier.
ITEM6_ADDED_REQUIRED = (
    "`gate_id`",
    "`rework.spec-change`",
    "SPEC 変更",
    "references/rework-task-synthesis.md",
    "Section 10",
    "`verify`",
    "`pending`",
)
# The transition's steps and record fields: SKILL.md cites Section 10 and
# lists none of them (NFR1). 文書のみの回 is excluded because an existing
# test locates the docs-only clause by that term.
ITEM6_ADDED_FORBIDDEN = (
    "create-spec",
    "create-plan",
    "implement",
    "review",
    "needs_update",
    "base_commit",
    "replan_authorized",
    "rework.yaml",
    "spec_change",
    "文書のみの回",
)

# SHA-256 of the block from 「### ターンを終わらせていい唯一の条件」 up to
# (not including) 「### してはならないこと」, taken from the base revision of
# em-workflow/skills/develop/SKILL.md.
BASE_STOP_LIST_SHA256 = (
    "d03b360a2cf7a9795e9522a7ecc14a72213edd668209db2bc8d99eeea7cbe4d4"
)

# --- redaction (NFR4) -------------------------------------------------------
REDACTION_MARKERS = ("notion.so", "notion.site", "notion.com", "/home/")


# --- verbatim pre-change constants (AC-5 negative samples) ------------------
PRE_SYNTHESIS_STEP2 = "2. `create-plan` / `implement` / `review` steps → `pending`\n"

PRE_CONTRACT_STEP2 = (
    "2. Set the `create-plan` / `implement` / `review` steps to `pending`.\n"
)

PRE_AGENT_PARAGRAPH = """\
When a rework decision requires a SPEC.md change, create no task. Return
`status: needs_user_input` with `gate_id: rework.spec-change` instead. Once
the user selects the SPEC change, the orchestrator drives a fixed five-step
sequence: `create-spec` step → `needs_update`; `create-plan` / `implement` /
`review` steps → `pending`; `workflow[implement].base_commit` preserved
unchanged; phase-state `rework.yaml` records the interruption reason and the
finding's `stable_id`; the develop state machine re-enters at `create-spec`.
**You trigger this sequence only by returning the question** — you never
perform any of its five steps yourself.
"""

PRE_ITEM6 = """\
6. fail → verify を `failed` にし、AskUserQuestion で差し戻し先を確認
   （implement へ rework / review へ / 中断）。「implement へ rework」を
   選んだ場合は `${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md`
   Section 10 が定める verify 由来の遷移に従う（`needs_rework` は review
   専用フィールドのため書かない — Section 10 の step 1 は行わず step 2 から
   始める）:
   `Task(subagent_type="em-workflow:rework-planner")` を dispatch し、
   検証・適用した patch の
   `step_patches` の中で implement / verify を `pending` に戻す（新しい
   rework task が 1 件以上 workflow.yaml へ登録されるまで戻さない — 同
   SSOT Invariant 1）。ただし rework-planner の検証済みの結果が文書のみの回
   （`${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` の
   `### Docs-only correction route`、文書のみ修正経路）の場合は、適用した
   patch は `verify` だけを `pending` に戻し、`implement` は `completed` の
   まま残して、この変更を commit-docs.sh でコミットする。
   タスク合成の中身（grouping / task ID 割当 /
   metadata 導出 / 検証カバレッジ等）は同 SSOT が定義し、ここでは繰り返さ
   ない。pass → `completed`
   （batch: 確認せず自動 rework。cap 判定は次段落「batch 自動 rework の
   系譜 cap」のとおり系譜 cap と hard cap を独立に評価する。どちらも
   未到達なら interactive と同じ手順で rework-planner を dispatch し、
   `${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` に従って
   patch を検証・適用して implement / verify を `pending` に戻す
   （`implement` の `pending` 復帰は同 patch の中で行う — 別書き込みには
   しない）。ただし rework-planner の検証済みの結果が文書のみの回
   （`${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` の
   `### Docs-only correction route`、文書のみ修正経路）の場合は、自動 rework でも
   適用した patch は `verify` だけを `pending` に戻し、`implement` は
   `completed` のまま残して、この変更を commit-docs.sh でコミットする。
   どちらか一方でも到達していれば rework を回さず、
   `verify.status` は `failed` のまま走行を停止せず retrospect フェーズへ
   進む。残った `failed_items` に `deferred` を与えない）。
   いずれの分岐も workflow.yaml 更新後に commit-docs.sh でコミットする

"""

# The sentence item 6 is expected to carry after the pre-change text. It is a
# positive control for the item 6 matcher, not a pin on the document's
# line breaks.
GOOD_ADDED_SENTENCE = """\
   rework-planner が `gate_id` `rework.spec-change` を返して SPEC 変更が
   選ばれた場合は、`${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md`
   Section 10 の遷移が `verify` も `pending` に戻す（interactive でも
   batch でも同じ）。
"""


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _strip_ws(text):
    return re.sub(r"\s+", "", text)


def _numbered_items(text):
    """(number, whitespace-normalised text) for each numbered list item of
    `text`; an indented line directly under an item continues it."""
    items = []
    open_item = False
    for line in text.splitlines():
        match = re.match(r"(\d+)\. (.*)$", line)
        if match:
            items.append([match.group(1), match.group(2).strip()])
            open_item = True
        elif open_item and line.strip() and line[0] in " \t":
            items[-1][1] += " " + line.strip()
        else:
            open_item = False
    return [(number, _norm(body)) for number, body in items]


def _item(items, number):
    for item_number, body in items:
        if item_number == number:
            return body
    return None


def _numbers(items):
    return [number for number, _ in items]


def _pending_names_problems(step_text, marker):
    """Problems with a step-2 text: it must hold `marker` and name every one
    of STEP_NAMES before it."""
    if step_text is None:
        return ["step 2 is absent"]
    head, found, _ = step_text.partition(marker)
    if not found:
        return [f"step 2 does not hold {marker!r}"]
    return [
        f"step 2 does not name `{name}` before {marker!r}"
        for name in STEP_NAMES
        if f"`{name}`" not in head
    ]


# --- Section 10 matchers ------------------------------------------------------


def synthesis_block(text):
    start = text.find(SYNTHESIS_BLOCK_LABEL)
    if start < 0:
        return None
    end = text.find(SYNTHESIS_REENTRY_PARAGRAPH, start)
    if end < 0:
        return None
    return text[start:end]


def synthesis_step2(text):
    block = synthesis_block(text)
    if block is None:
        return None
    return _item(_numbered_items(block), "2")


def synthesis_step2_problems(step_text):
    problems = _pending_names_problems(step_text, SYNTHESIS_PENDING_MARKER)
    if step_text is not None:
        tail = step_text.partition(SYNTHESIS_PENDING_MARKER)[2]
        problems += [
            f"step 2 lacks {fragment!r} after the list"
            for fragment in STATUS_ONLY_FRAGMENTS
            if fragment not in tail
        ]
    return problems


def synthesis_structure_problems(text):
    """The block holds exactly the numbered steps 1-5 and the re-entry
    paragraph follows them directly, as a paragraph of its own."""
    block = synthesis_block(text)
    if block is None:
        return ["block label or re-entry paragraph is absent"]
    problems = []
    numbers = _numbers(_numbered_items(block))
    if numbers != ["1", "2", "3", "4", "5"]:
        problems.append(f"numbered steps are {numbers}, expected 1-5")
    if not block.endswith("\n\n"):
        problems.append("the re-entry paragraph is not a paragraph of its own")
    seen_item = False
    for line in block.splitlines():
        if re.match(r"\d+\. ", line):
            seen_item = True
        elif seen_item and line.strip() and line[0] not in " \t":
            problems.append(f"a paragraph sits between the steps and the re-entry: {line!r}")
    return problems


# --- contract matchers --------------------------------------------------------


def contract_section(text):
    start = text.find(CONTRACT_HEADING)
    if start < 0:
        return None
    end = text.find(CONTRACT_END_HEADING, start)
    if end < 0:
        return None
    return text[start:end]


def contract_step2(text):
    section = contract_section(text)
    if section is None:
        return None
    return _item(_numbered_items(section), "2")


def contract_step2_problems(step_text):
    return _pending_names_problems(step_text, CONTRACT_PENDING_MARKER)


def contract_numbering_problems(text):
    section = contract_section(text)
    if section is None:
        return ["section is absent"]
    numbers = _numbers(_numbered_items(section))
    if numbers != ["1", "2", "3", "4", "5"]:
        return [f"numbered steps are {numbers}, expected 1-5"]
    return []


# --- agent prompt matchers ------------------------------------------------------


def agent_section(text):
    start = text.find(AGENT_HEADING)
    if start < 0:
        return None
    end = text.find("\n## ", start + len(AGENT_HEADING))
    if end < 0:
        end = len(text)
    return text[start:end]


def agent_problems(section):
    if section is None:
        return ["section is absent"]
    normalised = _norm(section)
    problems = []
    start = normalised.find(AGENT_CLAUSE_START)
    end = normalised.find(AGENT_CLAUSE_END, start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        problems.append("the create-spec ... base_commit summary is absent")
    else:
        clause = normalised[start + len(AGENT_CLAUSE_START) : end]
        problems += _pending_names_problems(clause, SYNTHESIS_PENDING_MARKER)
    if AGENT_FIXED_SEQUENCE not in normalised:
        problems.append(f"does not state {AGENT_FIXED_SEQUENCE!r}")
    if AGENT_NEVER_PERFORM not in normalised:
        problems.append(f"does not state {AGENT_NEVER_PERFORM!r}")
    return problems


# --- SKILL.md matchers ----------------------------------------------------------


def skill_item6(text):
    start = text.find(ITEM6_START)
    if start < 0:
        return None
    end = text.find(ITEM6_END, start)
    if end < 0:
        return None
    return text[start:end]


def item6_added_text(item6):
    """The text (whitespace removed) after the last existing sentence of
    item 6; None when that sentence is absent."""
    stripped = _strip_ws(item6)
    anchor = _strip_ws(ITEM6_LAST_SENTENCE)
    index = stripped.find(anchor)
    if index < 0:
        return None
    return stripped[index + len(anchor) :].lstrip("。")


def item6_problems(item6):
    if item6 is None:
        return ["item 6 is absent"]
    added = item6_added_text(item6)
    if added is None:
        return ["the commit-docs.sh sentence closing item 6 is absent"]
    if not added:
        return ["item 6 has no sentence after the commit-docs.sh sentence"]
    problems = [
        f"the added sentence lacks {fragment!r}"
        for fragment in ITEM6_ADDED_REQUIRED
        if _strip_ws(fragment) not in added
    ]
    problems += [
        f"the added sentence lists {token!r}"
        for token in ITEM6_ADDED_FORBIDDEN
        if token in added
    ]
    if not added.endswith("。") or added.count("。") != 1:
        problems.append("the added text is not exactly one sentence")
    return problems


def skill_stop_list(text):
    start = text.find(STOP_LIST_START)
    if start < 0:
        return None
    end = text.find(STOP_LIST_END, start)
    if end < 0:
        return None
    return text[start:end]


def sha256_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redaction_hits(text):
    lowered = text.lower()
    return [marker for marker in REDACTION_MARKERS if marker in lowered]


# =============================================================================
# AC-1
# =============================================================================


class TestAC1SynthesisSection10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SYNTHESIS_PATH)

    def test_ac1_step2_names_four_steps_and_states_status_only_write(self):
        self.assertEqual(synthesis_step2_problems(synthesis_step2(self.text)), [])

    def test_ac1_block_keeps_five_numbered_steps_before_the_reentry_paragraph(self):
        self.assertEqual(synthesis_structure_problems(self.text), [])


# =============================================================================
# AC-2
# =============================================================================


class TestAC2ContractStep2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_ac2_step2_names_the_same_four_steps_as_pending(self):
        self.assertEqual(contract_step2_problems(contract_step2(self.text)), [])

    def test_ac2_section_keeps_numbered_steps_one_to_five(self):
        self.assertEqual(contract_numbering_problems(self.text), [])


# =============================================================================
# AC-3
# =============================================================================


class TestAC3AgentSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(AGENT_PATH)

    def test_ac3_summary_names_verify_among_the_pending_steps(self):
        self.assertEqual(agent_problems(agent_section(self.text)), [])


# =============================================================================
# AC-4
# =============================================================================


class TestAC4SkillItem6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_ac4_item6_cites_section_10_and_returns_verify_to_pending(self):
        self.assertEqual(item6_problems(skill_item6(self.text)), [])

    def test_ac4_stop_condition_list_is_byte_identical_to_the_base_revision(self):
        block = skill_stop_list(self.text)
        self.assertIsNotNone(block, "stop-condition block not found")
        self.assertEqual(sha256_of(block), BASE_STOP_LIST_SHA256)


# =============================================================================
# AC-5: negative proofs for every matcher
# =============================================================================


class TestAC5NegativeProofs(unittest.TestCase):
    # --- pre-change constants are rejected ---------------------------------

    def test_ac5_synthesis_matcher_rejects_the_pre_change_step2(self):
        step = _item(_numbered_items(PRE_SYNTHESIS_STEP2), "2")
        self.assertIsNotNone(step)
        problems = synthesis_step2_problems(step)
        self.assertIn("step 2 does not name `verify` before '→ `pending`'", problems)
        self.assertTrue(any("lacks" in p for p in problems), problems)

    def test_ac5_contract_matcher_rejects_the_pre_change_step2(self):
        step = _item(_numbered_items(PRE_CONTRACT_STEP2), "2")
        self.assertIsNotNone(step)
        self.assertEqual(
            contract_step2_problems(step),
            ["step 2 does not name `verify` before 'to `pending`'"],
        )

    def test_ac5_agent_matcher_rejects_the_pre_change_summary(self):
        section = AGENT_HEADING + "\n" + PRE_AGENT_PARAGRAPH + "\n## Next\n"
        self.assertEqual(
            agent_problems(agent_section(section)),
            ["step 2 does not name `verify` before '→ `pending`'"],
        )

    def test_ac5_item6_matcher_rejects_the_pre_change_item(self):
        self.assertEqual(
            item6_problems(PRE_ITEM6),
            ["item 6 has no sentence after the commit-docs.sh sentence"],
        )

    # --- positive controls --------------------------------------------------

    def test_ac5_item6_matcher_accepts_the_expected_sentence(self):
        self.assertEqual(item6_problems(PRE_ITEM6 + GOOD_ADDED_SENTENCE), [])

    def test_ac5_synthesis_matcher_accepts_a_well_formed_step2(self):
        good = (
            "2. `create-plan` / `implement` / `review` / `verify` steps → `pending`\n"
            "   (only these steps' `status` is written; `verify`'s `result` and\n"
            "   `failed_items` stay until the next verify run overwrites them)\n"
        )
        self.assertEqual(
            synthesis_step2_problems(_item(_numbered_items(good), "2")), []
        )

    def test_ac5_contract_matcher_accepts_a_well_formed_step2(self):
        good = "2. Set the `create-plan` / `implement` / `review` / `verify` steps to `pending`.\n"
        self.assertEqual(contract_step2_problems(_item(_numbered_items(good), "2")), [])

    # --- other samples that lack the statement ------------------------------

    def test_ac5_synthesis_matcher_rejects_four_steps_without_the_status_only_rule(self):
        sample = "2. `create-plan` / `implement` / `review` / `verify` steps → `pending`\n"
        problems = synthesis_step2_problems(_item(_numbered_items(sample), "2"))
        self.assertEqual(len(problems), len(STATUS_ONLY_FRAGMENTS))

    def test_ac5_synthesis_matcher_rejects_verify_named_only_after_the_marker(self):
        sample = (
            "2. `create-plan` / `implement` / `review` steps → `pending`; "
            "`verify` is not touched; only these steps' `status` is written, "
            "`verify`'s `result` and `failed_items` stay until the next verify run\n"
        )
        self.assertEqual(
            synthesis_step2_problems(_item(_numbered_items(sample), "2")),
            ["step 2 does not name `verify` before '→ `pending`'"],
        )

    def test_ac5_synthesis_matcher_rejects_a_step_that_is_not_set_to_pending(self):
        sample = "2. `create-plan` / `implement` / `review` / `verify` steps → `completed`\n"
        self.assertEqual(
            synthesis_step2_problems(_item(_numbered_items(sample), "2")),
            ["step 2 does not hold '→ `pending`'"]
            + [
                f"step 2 lacks {fragment!r} after the list"
                for fragment in STATUS_ONLY_FRAGMENTS
            ],
        )

    def test_ac5_step_matchers_reject_a_document_without_step_2(self):
        self.assertEqual(synthesis_step2_problems(None), ["step 2 is absent"])
        self.assertEqual(contract_step2_problems(None), ["step 2 is absent"])
        self.assertIsNone(synthesis_step2("no block here"))
        self.assertIsNone(contract_step2("no section here"))

    def test_ac5_contract_matcher_rejects_verify_named_only_after_the_marker(self):
        sample = "2. Set the `create-plan` / `implement` / `review` steps to `pending`, `verify`.\n"
        self.assertEqual(
            contract_step2_problems(_item(_numbered_items(sample), "2")),
            ["step 2 does not name `verify` before 'to `pending`'"],
        )

    def test_ac5_agent_matcher_rejects_a_summary_that_drops_the_fixed_sequence(self):
        paragraph = PRE_AGENT_PARAGRAPH.replace(
            "`review` steps", "`review` / `verify` steps"
        ).replace("a fixed five-step\nsequence", "a sequence")
        self.assertNotIn("fixed five-step", _norm(paragraph))
        section = AGENT_HEADING + "\n" + paragraph + "\n## Next\n"
        self.assertEqual(
            agent_problems(agent_section(section)),
            [f"does not state {AGENT_FIXED_SEQUENCE!r}"],
        )

    def test_ac5_agent_matcher_accepts_the_summary_with_verify(self):
        paragraph = PRE_AGENT_PARAGRAPH.replace(
            "`review` steps", "`review` / `verify` steps"
        )
        self.assertNotEqual(paragraph, PRE_AGENT_PARAGRAPH)
        section = AGENT_HEADING + "\n" + paragraph + "\n## Next\n"
        self.assertEqual(agent_problems(agent_section(section)), [])

    def test_ac5_agent_matcher_rejects_a_summary_that_performs_the_steps(self):
        paragraph = PRE_AGENT_PARAGRAPH.replace(
            "`review` steps", "`review` / `verify` steps"
        ).replace(
            "you never\nperform any of its five steps yourself", "you perform the steps"
        )
        section = AGENT_HEADING + "\n" + paragraph + "\n## Next\n"
        self.assertEqual(
            agent_problems(agent_section(section)),
            [f"does not state {AGENT_NEVER_PERFORM!r}"],
        )

    def test_ac5_agent_matcher_rejects_a_missing_section(self):
        self.assertEqual(agent_problems(agent_section("no section")), ["section is absent"])

    def test_ac5_item6_matcher_rejects_a_sentence_without_the_citation(self):
        # PRE_ITEM6 already names the path and Section 10 earlier, so the
        # citation must be matched inside the added sentence itself.
        sample = PRE_ITEM6 + (
            "   rework-planner が `gate_id` `rework.spec-change` を返して SPEC 変更が\n"
            "   選ばれた場合は、`verify` も `pending` に戻す。\n"
        )
        self.assertEqual(
            item6_problems(sample),
            [
                "the added sentence lacks 'references/rework-task-synthesis.md'",
                "the added sentence lacks 'Section 10'",
            ],
        )

    def test_ac5_item6_matcher_rejects_a_sentence_that_lists_the_transition_steps(self):
        sample = PRE_ITEM6 + GOOD_ADDED_SENTENCE.replace(
            "に戻す（", "に戻し、`create-spec` を `needs_update` にする（"
        )
        self.assertEqual(
            item6_problems(sample),
            [
                "the added sentence lists 'create-spec'",
                "the added sentence lists 'needs_update'",
            ],
        )

    def test_ac5_item6_matcher_rejects_a_sentence_that_names_implement_or_review(self):
        sample = PRE_ITEM6 + GOOD_ADDED_SENTENCE.replace(
            "`verify` も", "`implement` / `review` / `verify` も"
        )
        self.assertEqual(
            item6_problems(sample),
            [
                "the added sentence lists 'implement'",
                "the added sentence lists 'review'",
            ],
        )

    def test_ac5_item6_matcher_rejects_the_docs_only_term(self):
        sample = PRE_ITEM6 + GOOD_ADDED_SENTENCE.replace(
            "の遷移が", "の遷移（文書のみの回を除く）が"
        )
        self.assertEqual(
            item6_problems(sample),
            ["the added sentence lists '文書のみの回'"],
        )

    def test_ac5_item6_matcher_rejects_a_sentence_without_the_gate_id(self):
        sample = PRE_ITEM6 + GOOD_ADDED_SENTENCE.replace(
            "`gate_id` `rework.spec-change` ", ""
        )
        self.assertEqual(
            item6_problems(sample),
            [
                "the added sentence lacks '`gate_id`'",
                "the added sentence lacks '`rework.spec-change`'",
            ],
        )

    def test_ac5_item6_matcher_rejects_two_added_sentences(self):
        sample = PRE_ITEM6 + GOOD_ADDED_SENTENCE + "   以上。\n"
        self.assertEqual(
            item6_problems(sample), ["the added text is not exactly one sentence"]
        )

    def test_ac5_item6_matcher_rejects_text_without_the_closing_commit_sentence(self):
        self.assertEqual(
            item6_problems(GOOD_ADDED_SENTENCE),
            ["the commit-docs.sh sentence closing item 6 is absent"],
        )
        self.assertEqual(item6_problems(None), ["item 6 is absent"])

    def test_ac5_item6_extractor_returns_none_without_both_markers(self):
        self.assertIsNone(skill_item6("no markers"))
        self.assertIsNone(skill_item6(ITEM6_START + " only the start"))

    # --- structure matcher (Section 10) -------------------------------------

    def _block(self, steps, between=""):
        lines = [SYNTHESIS_BLOCK_LABEL + ": the orchestrator's transition is fixed:", ""]
        lines += [f"{number}. step {number}" for number in steps]
        text = "\n".join(lines) + "\n\n" + between
        return text + SYNTHESIS_REENTRY_PARAGRAPH + " is not rejected.\n"

    def test_ac5_structure_matcher_accepts_five_steps_then_the_paragraph(self):
        self.assertEqual(synthesis_structure_problems(self._block(range(1, 6))), [])

    def test_ac5_structure_matcher_rejects_a_sixth_step(self):
        self.assertEqual(
            synthesis_structure_problems(self._block(range(1, 7))),
            ["numbered steps are ['1', '2', '3', '4', '5', '6'], expected 1-5"],
        )

    def test_ac5_structure_matcher_rejects_a_missing_step(self):
        self.assertEqual(
            synthesis_structure_problems(self._block([1, 2, 4, 5])),
            ["numbered steps are ['1', '2', '4', '5'], expected 1-5"],
        )

    def test_ac5_structure_matcher_rejects_a_paragraph_between_steps_and_reentry(self):
        sample = self._block(range(1, 6), between="A stray paragraph.\n\n")
        self.assertEqual(
            synthesis_structure_problems(sample),
            ["a paragraph sits between the steps and the re-entry: 'A stray paragraph.'"],
        )

    def test_ac5_structure_matcher_rejects_a_reentry_paragraph_glued_to_the_steps(self):
        sample = self._block(range(1, 6))
        glued = sample.replace("\n\n" + SYNTHESIS_REENTRY_PARAGRAPH, "\n" + SYNTHESIS_REENTRY_PARAGRAPH)
        self.assertNotEqual(sample, glued)
        self.assertEqual(
            synthesis_structure_problems(glued),
            ["the re-entry paragraph is not a paragraph of its own"],
        )

    def test_ac5_structure_matcher_rejects_a_document_without_the_block(self):
        self.assertEqual(
            synthesis_structure_problems("nothing"),
            ["block label or re-entry paragraph is absent"],
        )

    def test_ac5_contract_numbering_matcher_rejects_other_numbering(self):
        def section(steps):
            body = "".join(f"{n}. step {n}\n" for n in steps)
            return (
                "head" + CONTRACT_HEADING + "\n" + body + CONTRACT_END_HEADING + "tail"
            )

        self.assertEqual(contract_numbering_problems(section(range(1, 6))), [])
        self.assertEqual(
            contract_numbering_problems(section(range(1, 5))),
            ["numbered steps are ['1', '2', '3', '4'], expected 1-5"],
        )
        self.assertEqual(
            contract_numbering_problems(section(range(1, 7))),
            ["numbered steps are ['1', '2', '3', '4', '5', '6'], expected 1-5"],
        )
        self.assertEqual(contract_numbering_problems("nothing"), ["section is absent"])

    def test_ac5_numbered_item_parser_continues_only_indented_lines(self):
        text = "1. one\n   continued\n2. two\nplain\n   not a continuation\n3. three\n"
        self.assertEqual(
            _numbered_items(text),
            [("1", "one continued"), ("2", "two"), ("3", "three")],
        )

    # --- stop-condition list digest -----------------------------------------

    def test_ac5_digest_changes_when_the_stop_list_is_edited(self):
        block = skill_stop_list(_read(SKILL_PATH))
        self.assertEqual(sha256_of(block), BASE_STOP_LIST_SHA256)
        for edited in (
            block + "6. 新しい条件\n",
            block.replace("スタック", "スタック状態", 1),
            block.replace("2 回連続", "3 回連続", 1),
            block.rstrip("\n"),
        ):
            self.assertNotEqual(edited, block)
            self.assertNotEqual(sha256_of(edited), BASE_STOP_LIST_SHA256)

    def test_ac5_stop_list_extractor_reads_between_the_two_headings(self):
        text = f"before\n{STOP_LIST_START}\n\nbody\n\n{STOP_LIST_END}\nafter\n"
        self.assertEqual(skill_stop_list(text), f"{STOP_LIST_START}\n\nbody\n\n")
        self.assertIsNone(skill_stop_list("no headings"))
        self.assertIsNone(skill_stop_list(STOP_LIST_START + "\nno end"))

    # --- redaction ----------------------------------------------------------

    def test_ac5_redaction_matcher_flags_each_marker(self):
        samples = {
            "notion.so": "see https://www.notion.so/page-1",
            "notion.site": "see https://team.notion.site/page",
            "notion.com": "see https://notion.com/page",
            "/home/": "read /home/someone/project/file.md",
        }
        for marker, sample in samples.items():
            with self.subTest(marker=marker):
                self.assertEqual(redaction_hits(sample), [marker])

    def test_ac5_redaction_matcher_is_case_insensitive_for_notion(self):
        self.assertEqual(redaction_hits("NOTION.SO/abc"), ["notion.so"])

    def test_ac5_redaction_matcher_passes_clean_text(self):
        self.assertEqual(redaction_hits(PRE_ITEM6 + PRE_AGENT_PARAGRAPH), [])


# =============================================================================
# AC-6
# =============================================================================


class TestAC6Redaction(unittest.TestCase):
    def _assert_clean(self, path):
        self.assertEqual(redaction_hits(_read(path)), [], str(path))

    def test_ac6_synthesis_has_no_notion_url_or_home_path(self):
        self._assert_clean(SYNTHESIS_PATH)

    def test_ac6_contract_has_no_notion_url_or_home_path(self):
        self._assert_clean(CONTRACT_PATH)

    def test_ac6_agent_prompt_has_no_notion_url_or_home_path(self):
        self._assert_clean(AGENT_PATH)

    def test_ac6_develop_skill_has_no_notion_url_or_home_path(self):
        self._assert_clean(SKILL_PATH)


if __name__ == "__main__":
    unittest.main()

"""Tests for task0001 (resume-steps-actor-labels): the actor-label rule for
stop-recovery steps, owned by `em-workflow/references/batch-terminal-line.md`
and cited by the develop skill's stop report.

Covers task0001 Acceptance Criteria
(feature-docs/resume-steps-actor-labels/tasks/task0001.md):

- AC-1: the `resume_conditions` bullet of `## Field values`, sliced to the
  next top-level bullet, holds the two labels, the human label's reason
  frame, the three reasons, the human-only-for-three-reasons statement and
  the approval-of-an-irreversible-change statement; the section's
  backticked-key bullets still name the eight keys in order and the `## `
  heading set is unchanged.
- AC-2: the same bullet states the AI-first ordering without exception, that
  no human step is followed by an AI step, and the fold-in of AI work that
  depends on a human decision.
- AC-3: the `## Result format` example, decoded per `## Escaping` and split
  on the decoded line feed, carries a labelled `resume_conditions` value
  that follows the label rule; the example stays eight lines with the eight
  keys in order.
- AC-4: `RESULT_FORMAT_TEXT` of `tests/test_batch_stop_contract.py` equals
  the new `## Result format` text, which differs from the pre-change text
  only in the `resume_conditions` line; `## Escaping` is unchanged.
- AC-5: the develop skill's stop-report section keeps its pre-change text
  and gains one plain paragraph after the YAML bullet that cites the owner
  document and states that batch and interactive reports take the same form.
- AC-6: this module uses the standard library only and imports no other test
  module; every matcher of AC-1, AC-2, AC-3 and AC-5 has a negative proof
  built from pre-change or forged wording and a non-vacuity guard.
- AC-7: the whole-suite run and the four-file change set are checked by the
  implementer's run of `python3 -m unittest discover -s tests` and a diff
  against the base commit; nothing in this module can observe either.

Matcher -> negative-proof inventory (every matcher is a pure function over
text; its proofs sit in the `Test...NegativeProofs` classes):

- `_resume_conditions_bullet` (bullet slice): the rule text placed in the
  next bullet is not found; a bullet cut short by a forged top-level
  bullet loses the rule text.
- `_states_labels_and_reasons` (AC-1 matcher): the real pre-change bullet;
  a forged bullet lacking each fixed string, the frame, the human-only
  statement or the irreversible-approval statement.
- `_states_order_and_fold_in` (AC-2 matcher): the real pre-change bullet; a
  forged bullet holding all five fixed strings but no ordering or fold-in
  statement; forged bullets holding only one of the two statements.
- `_top_level_key_bullets` / `_headings`: a forged top-level bullet opening
  with a backticked key; a forged extra heading.
- `_example_satisfies_label_rule` (AC-3 matcher): the real pre-change
  example; forged human-then-AI values; forged human labels with no reason,
  an empty reason, two reasons and an unknown reason; an unlabelled step; a
  single step; a value with a literal newline; an escaped backslash
  followed by `n`.
- `_example_last_step_folds_in`: a forged value ending with an AI step; a
  forged human step without the fold-in phrase.
- `_differs_only_in_resume_line` (AC-4 matcher): the pre-change text itself;
  forged texts changing another line or two lines.
- `_target_paragraph` / `_paragraph_forbidden_hits` / `_section_is_pre_change_prefixed`
  / `_added_headings` / `_question_tool_count` (AC-5 matchers): the real
  pre-change section; forged sections each dropping one anchor, putting the
  paragraph before the bullets, turning it into a bullet, splitting the
  anchors over two paragraphs; forged paragraphs each carrying one
  forbidden item.
- `_import_violations` (AC-6 matcher): forged sources importing a
  third-party module, another test module and a relative module.

Every forged value is built from a test-owned well-formed constant by
exactly one change, and each proof first shows the well-formed constant is
accepted and the forged one is found by the same extraction, so a
rejection cannot come from a malformed fixture.

Matching: English anchors in `batch-terminal-line.md` are compared after
collapsing whitespace runs; anchors in `SKILL.md`'s Japanese prose are
compared with all whitespace removed (the file hard-wraps Japanese without
a space at the break).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-terminal-line.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "develop" / "SKILL.md"
CONTRACT_TEST_PATH = REPO_ROOT / "tests" / "test_batch_stop_contract.py"

# --- The label vocabulary (IMPLEMENTATION.md, Actor-label vocabulary) ------
AI_LABEL = "AI がやれる"
HUMAN_LABEL = "人の判断が要る"
REASON_FRAME = "（理由: "
REASONS = ("物理的に人しかできない", "戻せない変更の承認", "価値判断")
FIVE_FIXED_STRINGS = (AI_LABEL, HUMAN_LABEL) + REASONS
FOLD_IN_FIXED = "判断の後、AI が"
FOLD_IN_PATTERN = "判断の後、AI が ... を実行する"

KEYS = (
    "state",
    "step",
    "reason",
    "detail",
    "feature",
    "branch",
    "pr_url",
    "resume_conditions",
)
CONTRACT_HEADINGS = (
    "Purpose",
    "Result format",
    "Escaping",
    "Field values",
    "Stop reason codes",
    "Stop point coverage",
    "Consumer constraints",
    "No result on a wait turn",
    "Responsibility boundary",
)

# --- Pre-change texts, verbatim from the base commit -----------------------
PRE_CHANGE_RESUME_BULLET = (
    "- `resume_conditions` — the stop-recovery guidance: non-whitespace\n"
    "  whenever `state` is `stopped` — never empty and never whitespace-only —\n"
    "  empty for every other `state`. Its value is NOT put through `detail`'s\n"
    "  normalization: any Markdown newlines, indentation and trailing spaces it\n"
    "  carries survive as `## Escaping`'s escapes rather than being collapsed."
)

PRE_CHANGE_RESUME_LINE = (
    'resume_conditions: "Resolve the conflict manually and re-run implement '
    'for task0004."'
)

PRE_CHANGE_RESULT_FORMAT = (
    "\n"
    "The final assistant message of a terminal batch turn is exactly one bare\n"
    "YAML mapping and nothing else: no code fence, no surrounding prose, no\n"
    "document separator (`---`), no comments, and no key beyond the eight\n"
    "below. The mapping carries exactly these eight keys, each written once,\n"
    "in this fixed order:\n"
    "\n"
    "```yaml\n"
    'state: "stopped"\n'
    'step: "implement"\n'
    'reason: "step_stuck"\n'
    'detail: "implementer task0004 stuck after 3 conflict cycles"\n'
    'feature: "batch-structured-result-output"\n'
    'branch: "em-workflow/batch-structured-result-output/integration"\n'
    'pr_url: ""\n'
    + PRE_CHANGE_RESUME_LINE
    + "\n"
    "```\n"
    "\n"
    "Every value is a double-quoted scalar; an empty value is written as an\n"
    'empty pair of double quotes (`""`), never omitted and never left\n'
    "unquoted. Each key sits at the start of its own physical line, so the\n"
    "result is always exactly eight physical lines: no value may contain a\n"
    "literal, unescaped newline (see `## Escaping`). Emitting the result needs\n"
    "no external tool: it is eight lines of text written as the final\n"
    "assistant message. The result is emitted only in a batch-mode run — an\n"
    "interactive run emits nothing here.\n"
    "\n"
)

STOP_REPORT_START = "## 停止時の報告（停止条件 2-4 のみ）"
STOP_REPORT_END = "## バッチ構造化結果"
YAML_BULLET = "- YAML エラー: 内容と `git restore` 等のリカバリ案を報告"

PRE_CHANGE_STOP_REPORT_SECTION = (
    "## 停止時の報告（停止条件 2-4 のみ）\n"
    "\n"
    "batch: 下記 3 件に加えて、停止条件 6、フェーズ内のゲート中断、Step A の\n"
    "feature 解決失敗、commit-docs.sh の 2 回目の exit 4 によるフェーズ中断、\n"
    "Step C 内の中断、そして implement / verify フェーズが定める終端停止\n"
    "（下記「バッチ構造化結果」が列挙する停止点のすべてを含む）は、いずれも\n"
    "`${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` の出力抑制規律が定める\n"
    "停止/中断の例外であり、対話時と同じ内容を全文報告する。この報告は、下記\n"
    "「バッチ構造化結果」が定める規則に従い、そのターンの最後の assistant\n"
    "メッセージより前のメッセージで出力する。停止の原因・影響範囲・リカバリ\n"
    "手順は、この報告に加えて、構造化結果の値の中にも全文で運ぶ —\n"
    "原因と影響範囲は `detail` に、リカバリ手順は `resume_conditions` に。\n"
    "この報告は追加であり、置き換えではない。\n"
    "\n"
    "- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`\n"
    "- 中断: `{step} が {status} のため中断。再開するには /em-workflow:develop を実行してね`\n"
    "- YAML エラー: 内容と `git restore` 等のリカバリ案を報告\n"
    "\n"
    "停止条件 3 が `review` step の `failed` で発火して停止するときは、この\n"
    "報告と、batch では `resume_conditions` の値が、\n"
    "`references/review-phase.md` の Phase R5 の Legacy review-failure recovery ブロックが定める復旧手順を運ぶ。\n"
    "運ぶのは、そのブロックの所在と、ブロックが述べる内容の両方であり、所在\n"
    "だけを示すことは認めない（全文で運ぶ規則は\n"
    "`references/batch-terminal-line.md` が持つ）。ここでは手順の内容を繰り返さない。\n"
    "\n"
)

# --- Test-owned well-formed wording (the base of every forged variant) -----
GOOD_RULE_TEXT = (
    "\n"
    "  Every recovery step the value carries begins with exactly one of two\n"
    "  fixed labels, whatever the language of the step text: 「AI がやれる」, or\n"
    "  「人の判断が要る（理由: X）」 where X is exactly one of\n"
    "  「物理的に人しかできない」, 「戻せない変更の承認」 and 「価値判断」. A step\n"
    "  is a human step only when one of those three reasons applies; every\n"
    "  other step is an AI step. Approval of a change that cannot be undone is\n"
    "  always a human step, with the reason 「戻せない変更の承認」."
)
GOOD_ORDER_TEXT = (
    "\n"
    "  Every AI step comes before every human step, without exception: no\n"
    "  human step is followed by an AI step."
)
GOOD_FOLD_IN_TEXT = (
    "\n"
    "  AI work that can only run after a human decision is not a step of its\n"
    "  own; it is written inside that human step as\n"
    "  「判断の後、AI が ... を実行する」."
)
GOOD_BULLET = (
    PRE_CHANGE_RESUME_BULLET + GOOD_RULE_TEXT + GOOD_ORDER_TEXT + GOOD_FOLD_IN_TEXT
)

GOOD_STEPS = (
    "AI がやれる: task0004 の worktree でコンフリクトしたファイルを一覧にする。",
    "人の判断が要る（理由: 価値判断）: どちらの変更を残すかを決める。"
    "判断の後、AI が task0004 の implement を実行する。",
)

GOOD_PARAGRAPH = (
    "この報告が運ぶリカバリ手順は、上の 3 件のテンプレートが指す手順を含めて、\n"
    "`references/batch-terminal-line.md` の `resume_conditions` の規則に従う。\n"
    "各手順は先頭にその規則のラベルを置き、AI で実行できる手順を人が判断する\n"
    "手順より先に並べ、人が判断する手順にはその理由を付ける。この形は、batch\n"
    "実行の値でも、対話実行の報告でも同じ形で出す。"
)
GOOD_SECTION = PRE_CHANGE_STOP_REPORT_SECTION + GOOD_PARAGRAPH + "\n\n"

PARAGRAPH_PATH_ANCHOR = "references/batch-terminal-line.md"
PARAGRAPH_NAME_ANCHOR = "`resume_conditions`"
PARAGRAPH_STRIPPED_ANCHORS = ("3件", "対話実行", "同じ形")

REASON_CODES = (
    "step_stuck",
    "step_needs_intervention",
    "workflow_yaml_unparseable",
    "git_setup_aborted",
    "gate_fail_closed",
    "gate_option_unavailable",
    "implement_task_failed",
    "verify_rework_cap_reached",
    "completion_aborted",
    "feature_resolution_aborted",
    "docs_commit_conflict_aborted",
    "no_work_required",
    "unmapped_stop",
    "context_budget_reached",
)
OTHER_FIELD_NAME_TOKENS = tuple(f"`{key}`" for key in KEYS if key != "resume_conditions")
PARAGRAPH_FORBIDDEN_LITERALS = (
    REASON_CODES
    + OTHER_FIELD_NAME_TOKENS
    + (
        "no-step",
        "AskUserQuestion",
        "decision: stop",
        "needs_rework",
        "classification",
        "gate_id",
        "${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md",
        "Legacy review-failure recovery",
        AI_LABEL,
        HUMAN_LABEL,
    )
    + REASONS
)
QUESTION_TOOL_NAME = "AskUserQuestion"
QUESTION_TOOL_BASELINE_COUNT = 7


# --- Shared text helpers ---------------------------------------------------
def _read(path):
    return path.read_text(encoding="utf-8")


def _collapse_ws(text):
    return re.sub(r"\s+", " ", text)


def _strip_ws(text):
    return re.sub(r"\s+", "", text)


HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
KEY_BULLET_RE = re.compile(r"^- `([a-z_]+)`", re.MULTILINE)
FENCED_YAML_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)
HUMAN_LABEL_RE = re.compile(r"^人の判断が要る（理由: ([^）]*)）")
KEY_LINE_RE = re.compile(r"^([a-z_]+): ")


def _contract_sections(text):
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end]
    return sections


def _headings(text):
    return tuple(match.group(1) for match in HEADING_RE.finditer(text))


# --- Matchers over batch-terminal-line.md ----------------------------------
def _resume_conditions_bullet(contract_text):
    """The `resume_conditions` bullet of `## Field values`, from its opening
    line to the line before the next top-level bullet (or the section end);
    None when the section or the bullet is missing."""
    section = _contract_sections(contract_text).get("Field values")
    if section is None:
        return None
    lines = section.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.startswith("- `resume_conditions`"):
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("- "):
            end = index
            break
    return "\n".join(lines[start:end]).rstrip("\n")


def _top_level_key_bullets(contract_text):
    section = _contract_sections(contract_text).get("Field values", "")
    return tuple(KEY_BULLET_RE.findall(section))


def _states_labels_and_reasons(bullet):
    """AC-1 matcher: the five fixed strings, the human label's reason
    frame, the human-only-for-three-reasons statement and the
    irreversible-approval statement."""
    if bullet is None:
        return False
    flat = _collapse_ws(bullet)
    lowered = flat.lower()
    return (
        all(fixed in flat for fixed in FIVE_FIXED_STRINGS)
        and REASON_FRAME in flat
        and "only when one of those three reasons applies" in lowered
        and "every other step is an ai step" in lowered
        and "approval of a change that cannot be undone is always a human step"
        in lowered
    )


def _states_order_and_fold_in(bullet):
    """AC-2 matcher: AI first without exception, never AI after human, and
    the fold-in of AI work that depends on a human decision."""
    if bullet is None:
        return False
    flat = _collapse_ws(bullet)
    lowered = flat.lower()
    return (
        "every ai step comes before every human step, without exception"
        in lowered
        and "no human step is followed by an ai step" in lowered
        and "is not a step of its own" in lowered
        and "written inside that human step" in lowered
        and FOLD_IN_PATTERN in flat
    )


# --- Matchers over the Result format example -------------------------------
def _result_format_section(contract_text):
    return _contract_sections(contract_text).get("Result format")


def _example_lines(result_format_section):
    match = FENCED_YAML_RE.search(result_format_section or "")
    if match is None:
        return None
    body = match.group(1)
    if body.endswith("\n"):
        body = body[:-1]
    return body.split("\n")


def _is_eight_key_example(lines):
    if lines is None or len(lines) != 8:
        return False
    found = []
    for line in lines:
        match = KEY_LINE_RE.match(line)
        if match is None:
            return False
        found.append(match.group(1))
    return tuple(found) == KEYS


SIMPLE_ESCAPES = {"\\": "\\", '"': '"', "r": "\r", "n": "\n", "t": "\t"}


def _decode_quoted_scalar(text):
    """Decodes a double-quoted scalar as `## Escaping` writes it, left to
    right, never re-reading a decoded character. `text` starts at the
    opening quote and must end at the closing quote."""
    if not text.startswith('"'):
        raise ValueError("no opening quote")
    out = []
    index = 1
    while index < len(text):
        char = text[index]
        if char == '"':
            if index != len(text) - 1:
                raise ValueError("characters after the closing quote")
            return "".join(out)
        if char == "\\":
            index += 1
            if index >= len(text):
                raise ValueError("dangling backslash")
            escape = text[index]
            if escape in SIMPLE_ESCAPES:
                out.append(SIMPLE_ESCAPES[escape])
                index += 1
            elif escape == "u":
                digits = text[index + 1 : index + 5]
                if re.fullmatch(r"[0-9a-f]{4}", digits) is None:
                    raise ValueError("bad unicode escape")
                out.append(chr(int(digits, 16)))
                index += 5
            else:
                raise ValueError("unknown escape")
            continue
        out.append(char)
        index += 1
    raise ValueError("unterminated scalar")


def _encode_value(decoded):
    """The `## Escaping` rule for the characters these tests use."""
    return (
        decoded.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _example_steps(result_format_section):
    """The decoded `resume_conditions` value split on the decoded line feed;
    None when the example is not eight key lines or the value is malformed."""
    lines = _example_lines(result_format_section)
    if not _is_eight_key_example(lines):
        return None
    prefix = "resume_conditions: "
    for line in lines:
        if line.startswith(prefix):
            try:
                return _decode_quoted_scalar(line[len(prefix) :]).split("\n")
            except ValueError:
                return None
    return None


def _step_kind(step):
    if step.startswith(AI_LABEL):
        return "ai"
    match = HUMAN_LABEL_RE.match(step)
    if match is not None and match.group(1) in REASONS:
        return "human"
    return None


def _steps_follow_label_rule(steps):
    if steps is None or len(steps) < 2:
        return False
    kinds = [_step_kind(step) for step in steps]
    if any(kind is None for kind in kinds) or kinds[0] != "ai":
        return False
    seen_human = False
    for kind in kinds:
        if kind == "human":
            seen_human = True
        elif seen_human:
            return False
    return True


def _example_satisfies_label_rule(result_format_section):
    """AC-3 matcher: eight key lines in order, one decoded value of at least
    two labelled steps, the first an AI step, no AI step after a human step,
    each human label holding exactly one of the three reasons."""
    return _steps_follow_label_rule(_example_steps(result_format_section))


def _example_last_step_folds_in(result_format_section):
    steps = _example_steps(result_format_section)
    return (
        bool(steps)
        and _step_kind(steps[-1]) == "human"
        and FOLD_IN_FIXED in steps[-1]
    )


def _with_example_value(decoded_value):
    """The pre-change Result format section with the example's
    `resume_conditions` line replaced by the given decoded value."""
    assert PRE_CHANGE_RESUME_LINE in PRE_CHANGE_RESULT_FORMAT
    return PRE_CHANGE_RESULT_FORMAT.replace(
        PRE_CHANGE_RESUME_LINE,
        'resume_conditions: "' + _encode_value(decoded_value) + '"',
    )


def _differs_only_in_resume_line(section, pre_change_section):
    """AC-4 matcher: same line count, exactly one differing line, and that
    line is the `resume_conditions` line on both sides."""
    new_lines = section.split("\n")
    old_lines = pre_change_section.split("\n")
    if len(new_lines) != len(old_lines):
        return False
    differing = [
        (old, new) for old, new in zip(old_lines, new_lines) if old != new
    ]
    return len(differing) == 1 and all(
        old.startswith("resume_conditions: ") and new.startswith("resume_conditions: ")
        for old, new in differing
    )


def _literal_constant(source, name):
    """The value of a module-level `name = <literal>` assignment, read from
    source text without importing the module; None when absent."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    return None


# --- Matchers over the develop skill ---------------------------------------
def _stop_report_section(skill_text):
    start = skill_text.find(STOP_REPORT_START)
    if start == -1:
        return None
    end = skill_text.find(STOP_REPORT_END, start)
    if end == -1:
        return None
    return skill_text[start:end]


def _is_bullet_block(block):
    return block.lstrip().startswith("- ")


def _carries_paragraph_anchors(block):
    stripped = _strip_ws(block)
    return (
        PARAGRAPH_PATH_ANCHOR in block
        and PARAGRAPH_NAME_ANCHOR in block
        and all(anchor in stripped for anchor in PARAGRAPH_STRIPPED_ANCHORS)
    )


def _target_paragraph(section):
    """The first non-bullet block after the YAML bullet that carries every
    anchor of the stop-report paragraph; None when there is none."""
    if section is None:
        return None
    blocks = section.split("\n\n")
    bullet_index = None
    for index, block in enumerate(blocks):
        if YAML_BULLET in block:
            bullet_index = index
            break
    if bullet_index is None:
        return None
    for block in blocks[bullet_index + 1 :]:
        if not _is_bullet_block(block) and _carries_paragraph_anchors(block):
            return block
    return None


def _paragraph_forbidden_hits(block):
    stripped = _strip_ws(block).lower()
    return [
        literal
        for literal in PARAGRAPH_FORBIDDEN_LITERALS
        if _strip_ws(literal).lower() in stripped
    ] + (["## heading"] if re.search(r"^## ", block, re.MULTILINE) else [])


def _section_is_pre_change_prefixed(section):
    return section is not None and section.startswith(PRE_CHANGE_STOP_REPORT_SECTION)


def _added_headings(section):
    """Level-2 headings inside the section after its own heading line."""
    body = section.split("\n", 1)[1] if "\n" in section else ""
    return re.findall(r"^## .*$", body, re.MULTILINE)


def _question_tool_count(text):
    return text.count(QUESTION_TOOL_NAME)


def _skill_text_around(section):
    """A minimal develop-skill text whose stop-report section is `section`,
    so the section locator finds it the way it finds the real one."""
    return "# develop\n\n" + section + STOP_REPORT_END + "\n\nbody\n"


# --- Matcher over this module's own imports --------------------------------
def _import_violations(source):
    """Imported module names that are not standard library, name another
    test module, or are relative."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = ["." * node.level + (node.module or "")]
        else:
            continue
        for name in names:
            root = name.split(".")[0]
            if (
                name.startswith(".")
                or root == "tests"
                or root.startswith("test_")
                or root.startswith("_")
                and root != "__future__"
                or root not in sys.stdlib_module_names
            ):
                violations.append(name)
    return violations


def _contract_doc_with_bullet(bullet):
    """A minimal contract document whose `## Field values` section carries
    `bullet` as the `resume_conditions` bullet between the seven earlier
    key bullets and a following top-level bullet."""
    return (
        "# Structured Result Contract\n\n"
        "## Purpose\n\nx\n\n"
        "## Field values\n\n"
        + "".join(f"- `{key}` — x\n" for key in KEYS[:-1])
        + bullet
        + "\n"
        "- Every audit item `batch-mode.md`'s `## Reporting` enumerates is\n"
        "  carried in full inside `detail`.\n\n"
        "## Stop reason codes\n\nx\n"
    )


# ==========================================================================
# AC-1 / AC-2: the rule inside the `resume_conditions` bullet
# ==========================================================================
class TestAC1AC2RuleInBullet(unittest.TestCase):
    """AC-1 and AC-2 over the real contract document."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.bullet = _resume_conditions_bullet(cls.text)

    def test_bullet_slice_is_found_and_keeps_pre_change_sentences(self):
        self.assertIsNotNone(self.bullet)
        self.assertTrue(self.bullet.startswith("- `resume_conditions`"))
        self.assertTrue(self.bullet.startswith(PRE_CHANGE_RESUME_BULLET))
        self.assertNotIn("- Every audit item", self.bullet)

    def test_ac1_bullet_states_labels_reasons_and_human_only_rule(self):
        self.assertTrue(_states_labels_and_reasons(self.bullet))

    def test_ac2_bullet_states_order_and_fold_in(self):
        self.assertTrue(_states_order_and_fold_in(self.bullet))

    def test_ac1_top_level_key_bullets_still_name_the_eight_keys_in_order(self):
        self.assertEqual(_top_level_key_bullets(self.text), KEYS)

    def test_ac1_heading_set_is_unchanged(self):
        self.assertEqual(_headings(self.text), CONTRACT_HEADINGS)

    def test_each_fixed_string_sits_unbroken_on_one_physical_line(self):
        lines = self.bullet.split("\n")
        for fixed in FIVE_FIXED_STRINGS + (FOLD_IN_FIXED,):
            with self.subTest(fixed=fixed):
                self.assertTrue(any(fixed in line for line in lines))


class TestAC1AC2NegativeProofs(unittest.TestCase):
    """Negative proofs for the bullet slice and the AC-1 / AC-2 matchers."""

    def test_good_bullet_is_accepted_by_both_matchers(self):
        self.assertTrue(_states_labels_and_reasons(GOOD_BULLET))
        self.assertTrue(_states_order_and_fold_in(GOOD_BULLET))

    def test_good_bullet_is_found_by_the_slice_inside_a_document(self):
        doc = _contract_doc_with_bullet(GOOD_BULLET)
        self.assertEqual(_resume_conditions_bullet(doc), GOOD_BULLET)
        self.assertEqual(_top_level_key_bullets(doc), KEYS)

    def test_pre_change_bullet_is_found_but_rejected_by_both_matchers(self):
        found = _resume_conditions_bullet(_contract_doc_with_bullet(PRE_CHANGE_RESUME_BULLET))
        self.assertEqual(found, PRE_CHANGE_RESUME_BULLET)
        self.assertFalse(_states_labels_and_reasons(found))
        self.assertFalse(_states_order_and_fold_in(found))

    def test_bullet_lacking_one_fixed_string_is_rejected(self):
        for fixed in FIVE_FIXED_STRINGS:
            with self.subTest(fixed=fixed):
                forged = GOOD_BULLET.replace(fixed, "X")
                self.assertNotEqual(forged, GOOD_BULLET)
                self.assertEqual(
                    _resume_conditions_bullet(_contract_doc_with_bullet(forged)), forged
                )
                self.assertFalse(_states_labels_and_reasons(forged))

    def test_bullet_lacking_the_reason_frame_is_rejected(self):
        forged = GOOD_BULLET.replace(REASON_FRAME, "（")
        self.assertNotEqual(forged, GOOD_BULLET)
        self.assertFalse(_states_labels_and_reasons(forged))

    def test_bullet_lacking_the_human_only_statement_is_rejected(self):
        forged = GOOD_BULLET.replace(
            "only when one of those three reasons applies", "sometimes"
        )
        self.assertNotEqual(forged, GOOD_BULLET)
        self.assertFalse(_states_labels_and_reasons(forged))
        forged = GOOD_BULLET.replace("every\n  other step is an AI step", "x")
        self.assertNotEqual(forged, GOOD_BULLET)
        self.assertFalse(_states_labels_and_reasons(forged))

    def test_bullet_lacking_the_irreversible_approval_statement_is_rejected(self):
        forged = GOOD_BULLET.replace(
            "Approval of a change that cannot be undone is\n  always a human step",
            "Approval is a step",
        )
        self.assertNotEqual(forged, GOOD_BULLET)
        self.assertFalse(_states_labels_and_reasons(forged))

    def test_bullet_with_all_five_strings_but_no_order_or_fold_in_is_rejected(self):
        forged = PRE_CHANGE_RESUME_BULLET + GOOD_RULE_TEXT
        doc = _contract_doc_with_bullet(forged)
        found = _resume_conditions_bullet(doc)
        self.assertEqual(found, forged)
        # Non-vacuity: the AC-1 matcher accepts it, so it is well formed.
        self.assertTrue(_states_labels_and_reasons(found))
        self.assertTrue(all(fixed in found for fixed in FIVE_FIXED_STRINGS))
        self.assertFalse(_states_order_and_fold_in(found))

    def test_bullet_with_order_but_no_fold_in_is_rejected(self):
        forged = PRE_CHANGE_RESUME_BULLET + GOOD_RULE_TEXT + GOOD_ORDER_TEXT
        self.assertTrue(_states_labels_and_reasons(forged))
        self.assertFalse(_states_order_and_fold_in(forged))

    def test_bullet_with_fold_in_but_no_order_is_rejected(self):
        forged = PRE_CHANGE_RESUME_BULLET + GOOD_RULE_TEXT + GOOD_FOLD_IN_TEXT
        self.assertTrue(_states_labels_and_reasons(forged))
        self.assertFalse(_states_order_and_fold_in(forged))

    def test_bullet_lacking_one_order_phrase_is_rejected(self):
        for phrase in (
            "Every AI step comes before every human step, without exception",
            "no\n  human step is followed by an AI step",
            "is not a step of its\n  own",
            "written inside that human step",
            FOLD_IN_PATTERN,
        ):
            with self.subTest(phrase=phrase):
                forged = GOOD_BULLET.replace(phrase, "X")
                self.assertNotEqual(forged, GOOD_BULLET)
                self.assertTrue(_states_labels_and_reasons(forged))
                self.assertFalse(_states_order_and_fold_in(forged))

    def test_rule_text_in_the_next_bullet_is_not_in_the_slice(self):
        doc = _contract_doc_with_bullet(PRE_CHANGE_RESUME_BULLET).replace(
            "  carried in full inside `detail`.",
            "  carried in full inside `detail`." + GOOD_RULE_TEXT + GOOD_ORDER_TEXT
            + GOOD_FOLD_IN_TEXT,
        )
        # Non-vacuity: the rule text is in the document, after the bullet.
        self.assertIn("always a human step", doc)
        self.assertTrue(_states_labels_and_reasons(doc))
        found = _resume_conditions_bullet(doc)
        self.assertEqual(found, PRE_CHANGE_RESUME_BULLET)
        self.assertFalse(_states_labels_and_reasons(found))
        self.assertFalse(_states_order_and_fold_in(found))

    def test_forged_top_level_bullet_cuts_the_slice_and_breaks_the_key_order(self):
        forged = GOOD_BULLET.replace(
            GOOD_ORDER_TEXT, "\n- `note` — x" + GOOD_ORDER_TEXT
        )
        self.assertNotEqual(forged, GOOD_BULLET)
        doc = _contract_doc_with_bullet(forged)
        found = _resume_conditions_bullet(doc)
        self.assertTrue(_states_labels_and_reasons(found))
        self.assertFalse(_states_order_and_fold_in(found))
        self.assertNotEqual(_top_level_key_bullets(doc), KEYS)
        self.assertEqual(
            _top_level_key_bullets(doc), KEYS[:-1] + ("resume_conditions", "note")
        )

    def test_forged_extra_heading_changes_the_heading_set(self):
        text = _contract_doc_with_bullet(GOOD_BULLET)
        self.assertEqual(
            _headings(text), ("Purpose", "Field values", "Stop reason codes")
        )
        forged = text + "\n## Extra\n\nx\n"
        self.assertEqual(
            _headings(forged),
            ("Purpose", "Field values", "Stop reason codes", "Extra"),
        )
        self.assertNotEqual(_headings(forged), _headings(text))

    def test_missing_field_values_section_yields_no_bullet(self):
        self.assertIsNone(_resume_conditions_bullet("# x\n\n## Purpose\n\nx\n"))
        self.assertFalse(_states_labels_and_reasons(None))
        self.assertFalse(_states_order_and_fold_in(None))


# ==========================================================================
# AC-3: the decoded Result format example
# ==========================================================================
class TestDecoder(unittest.TestCase):
    """The decoder follows `## Escaping`, left to right, never re-reading a
    character it has decoded."""

    def test_decodes_each_escape(self):
        self.assertEqual(_decode_quoted_scalar('"a\\\\b"'), "a\\b")
        self.assertEqual(_decode_quoted_scalar('"a\\"b"'), 'a"b')
        self.assertEqual(_decode_quoted_scalar('"a\\rb\\nc\\td"'), "a\rb\nc\td")
        self.assertEqual(_decode_quoted_scalar('"a\\u2028b"'), "a b")

    def test_escaped_backslash_then_n_is_a_backslash_and_an_n(self):
        decoded = _decode_quoted_scalar('"a\\\\nb"')
        self.assertEqual(decoded, "a\\nb")
        self.assertNotIn("\n", decoded)

    def test_escaped_quote_does_not_end_the_value(self):
        self.assertEqual(_decode_quoted_scalar('"say \\"hi\\" now"'), 'say "hi" now')

    def test_malformed_scalars_raise(self):
        for written in ('abc', '"abc', '"a"b"', '"a\\', '"a\\q"', '"a\\u12"'):
            with self.subTest(written=written):
                with self.assertRaises(ValueError):
                    _decode_quoted_scalar(written)

    def test_encode_then_decode_round_trips(self):
        value = 'a\\b"c\rd\ne\tf'
        self.assertEqual(_decode_quoted_scalar('"' + _encode_value(value) + '"'), value)


class TestAC3ExampleInRealDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.section = _result_format_section(cls.text)

    def test_example_is_eight_lines_with_the_eight_keys_in_order(self):
        self.assertTrue(_is_eight_key_example(_example_lines(self.section)))

    def test_decoded_value_follows_the_label_rule(self):
        self.assertTrue(_example_satisfies_label_rule(self.section))

    def test_example_value_is_one_physical_line_with_the_line_feed_escaped(self):
        lines = _example_lines(self.section)
        resume = [line for line in lines if line.startswith("resume_conditions: ")]
        self.assertEqual(len(resume), 1)
        self.assertIn("\\n", resume[0])
        steps = _example_steps(self.section)
        self.assertGreaterEqual(len(steps), 2)
        self.assertEqual(_step_kind(steps[0]), "ai")

    def test_last_step_is_a_human_step_using_the_fold_in_phrase(self):
        self.assertTrue(_example_last_step_folds_in(self.section))


class TestAC3NegativeProofs(unittest.TestCase):
    def test_good_value_is_accepted(self):
        section = _with_example_value("\n".join(GOOD_STEPS))
        self.assertTrue(_is_eight_key_example(_example_lines(section)))
        self.assertEqual(_example_steps(section), list(GOOD_STEPS))
        self.assertTrue(_example_satisfies_label_rule(section))
        self.assertTrue(_example_last_step_folds_in(section))

    def _assert_rejected(self, steps_or_section):
        if isinstance(steps_or_section, str):
            section = steps_or_section
        else:
            section = _with_example_value("\n".join(steps_or_section))
            # Non-vacuity: the example is still well formed and decodes.
            self.assertTrue(_is_eight_key_example(_example_lines(section)))
            self.assertEqual(_example_steps(section), list(steps_or_section))
        self.assertFalse(_example_satisfies_label_rule(section))

    def test_pre_change_example_is_rejected(self):
        # Non-vacuity: the pre-change example is eight key lines in order.
        self.assertTrue(_is_eight_key_example(_example_lines(PRE_CHANGE_RESULT_FORMAT)))
        self.assertEqual(
            _example_steps(PRE_CHANGE_RESULT_FORMAT),
            ["Resolve the conflict manually and re-run implement for task0004."],
        )
        self.assertFalse(_example_satisfies_label_rule(PRE_CHANGE_RESULT_FORMAT))
        self.assertFalse(_example_last_step_folds_in(PRE_CHANGE_RESULT_FORMAT))

    def test_human_step_followed_by_ai_step_is_rejected(self):
        ai, human = GOOD_STEPS
        self._assert_rejected([human, ai])
        self._assert_rejected([ai, human, "AI がやれる: task0004 を再度確認する。"])

    def test_human_label_with_no_reason_is_rejected(self):
        ai, _ = GOOD_STEPS
        self._assert_rejected([ai, "人の判断が要る: どちらの変更を残すかを決める。"])
        self._assert_rejected([ai, "人の判断が要る（理由: ）: どちらを残すか決める。"])

    def test_human_label_with_two_reasons_is_rejected(self):
        ai, _ = GOOD_STEPS
        self._assert_rejected(
            [ai, "人の判断が要る（理由: 価値判断、戻せない変更の承認）: 決める。"]
        )

    def test_human_label_with_an_unknown_reason_is_rejected(self):
        ai, _ = GOOD_STEPS
        self._assert_rejected([ai, "人の判断が要る（理由: 気分）: 決める。"])

    def test_unlabelled_step_is_rejected(self):
        ai, human = GOOD_STEPS
        self._assert_rejected([ai, "Resolve the conflict manually.", human])

    def test_single_step_is_rejected(self):
        self._assert_rejected([GOOD_STEPS[0]])

    def test_empty_trailing_step_is_rejected(self):
        self._assert_rejected(list(GOOD_STEPS) + [""])

    def test_value_with_a_literal_newline_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        written = 'resume_conditions: "' + _encode_value("\n".join(GOOD_STEPS)) + '"'
        self.assertIn(written, good)
        forged = good.replace(written, written.replace("\\n", "\n"))
        self.assertNotEqual(forged, good)
        self.assertFalse(_is_eight_key_example(_example_lines(forged)))
        self.assertFalse(_example_satisfies_label_rule(forged))

    def test_escaped_backslash_then_n_does_not_split_the_steps(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        written = 'resume_conditions: "' + _encode_value("\n".join(GOOD_STEPS)) + '"'
        forged = good.replace(written, written.replace("\\n", "\\\\n"))
        self.assertNotEqual(forged, good)
        self.assertTrue(_is_eight_key_example(_example_lines(forged)))
        self.assertEqual(len(_example_steps(forged)), 1)
        self.assertFalse(_example_satisfies_label_rule(forged))

    def test_example_with_a_reordered_or_missing_key_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        self.assertTrue(_example_satisfies_label_rule(good))
        reordered = good.replace('state: "stopped"\nstep: "implement"\n', 'step: "implement"\nstate: "stopped"\n')
        self.assertNotEqual(reordered, good)
        self.assertFalse(_example_satisfies_label_rule(reordered))
        missing = good.replace('pr_url: ""\n', "")
        self.assertNotEqual(missing, good)
        self.assertFalse(_example_satisfies_label_rule(missing))

    def test_malformed_value_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        forged = good.replace('"\n```', '\n```')
        self.assertNotEqual(forged, good)
        self.assertFalse(_example_satisfies_label_rule(forged))

    def test_last_step_without_fold_in_phrase_is_rejected(self):
        ai, human = GOOD_STEPS
        no_fold_in = human.replace("判断の後、AI が", "その後")
        self.assertNotEqual(no_fold_in, human)
        section = _with_example_value("\n".join([ai, no_fold_in]))
        # Non-vacuity: the value satisfies the label rule.
        self.assertTrue(_example_satisfies_label_rule(section))
        self.assertFalse(_example_last_step_folds_in(section))

    def test_last_step_being_an_ai_step_is_rejected(self):
        ai, human = GOOD_STEPS
        section = _with_example_value("\n".join([ai, ai]))
        self.assertFalse(_example_last_step_folds_in(section))


# ==========================================================================
# AC-4: the Result format section differs only in the resume_conditions line
# ==========================================================================
class TestAC4ResultFormatSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _result_format_section(_read(CONTRACT_PATH))

    def test_section_differs_from_pre_change_only_in_resume_line(self):
        self.assertTrue(_differs_only_in_resume_line(self.section, PRE_CHANGE_RESULT_FORMAT))

    def test_result_format_text_constant_equals_the_section(self):
        constant = _literal_constant(_read(CONTRACT_TEST_PATH), "RESULT_FORMAT_TEXT")
        self.assertIsNotNone(constant)
        self.assertEqual(constant, self.section)

    def test_escaping_text_constant_equals_the_escaping_section(self):
        sections = _contract_sections(_read(CONTRACT_PATH))
        constant = _literal_constant(_read(CONTRACT_TEST_PATH), "ESCAPING_TEXT")
        self.assertIsNotNone(constant)
        self.assertEqual(constant, sections["Escaping"])


class TestAC4NegativeProofs(unittest.TestCase):
    def test_changed_resume_line_only_is_accepted(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        self.assertTrue(_differs_only_in_resume_line(good, PRE_CHANGE_RESULT_FORMAT))

    def test_pre_change_text_itself_is_rejected(self):
        self.assertFalse(
            _differs_only_in_resume_line(PRE_CHANGE_RESULT_FORMAT, PRE_CHANGE_RESULT_FORMAT)
        )

    def test_another_changed_line_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        forged = good.replace('step: "implement"', 'step: "review"')
        self.assertNotEqual(forged, good)
        self.assertFalse(_differs_only_in_resume_line(forged, PRE_CHANGE_RESULT_FORMAT))

    def test_prose_change_in_addition_to_the_resume_line_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        forged = good.replace("exactly eight physical lines", "exactly nine physical lines")
        self.assertNotEqual(forged, good)
        self.assertFalse(_differs_only_in_resume_line(forged, PRE_CHANGE_RESULT_FORMAT))

    def test_a_line_added_to_the_section_is_rejected(self):
        good = _with_example_value("\n".join(GOOD_STEPS))
        forged = good + "extra line\n"
        self.assertFalse(_differs_only_in_resume_line(forged, PRE_CHANGE_RESULT_FORMAT))

    def test_literal_constant_reader_finds_assignments_and_ignores_others(self):
        source = 'A = "x\\ny"\nB = 1\n'
        self.assertEqual(_literal_constant(source, "A"), "x\ny")
        self.assertEqual(_literal_constant(source, "B"), 1)
        self.assertIsNone(_literal_constant(source, "C"))


# ==========================================================================
# AC-5: the stop-report paragraph in the develop skill
# ==========================================================================
class TestAC5StopReportParagraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _stop_report_section(cls.text)

    def test_section_is_found_and_keeps_the_pre_change_text(self):
        self.assertIsNotNone(self.section)
        self.assertTrue(self.section.startswith(STOP_REPORT_START))
        self.assertTrue(_section_is_pre_change_prefixed(self.section))

    def test_no_heading_is_added_before_the_structured_result_section(self):
        self.assertEqual(_added_headings(self.section), [])

    def test_new_plain_paragraph_cites_the_rule_and_states_the_same_form(self):
        paragraph = _target_paragraph(self.section)
        self.assertIsNotNone(paragraph)
        self.assertFalse(_is_bullet_block(paragraph))
        self.assertIn(PARAGRAPH_PATH_ANCHOR, paragraph)
        self.assertIn(PARAGRAPH_NAME_ANCHOR, paragraph)

    def test_new_paragraph_is_after_the_yaml_bullet(self):
        paragraph = _target_paragraph(self.section)
        self.assertIsNotNone(paragraph)
        self.assertGreater(self.section.index(paragraph), self.section.index(YAML_BULLET))

    def test_new_paragraph_carries_no_forbidden_item(self):
        paragraph = _target_paragraph(self.section)
        self.assertIsNotNone(paragraph)
        self.assertEqual(_paragraph_forbidden_hits(paragraph), [])

    def test_interactive_question_tool_count_is_unchanged(self):
        self.assertEqual(_question_tool_count(self.text), QUESTION_TOOL_BASELINE_COUNT)


class TestAC5NegativeProofs(unittest.TestCase):
    def test_good_section_is_accepted_and_found_by_the_locator(self):
        skill = _skill_text_around(GOOD_SECTION)
        section = _stop_report_section(skill)
        self.assertEqual(section, GOOD_SECTION)
        self.assertTrue(_section_is_pre_change_prefixed(section))
        self.assertEqual(_target_paragraph(section), GOOD_PARAGRAPH)
        self.assertEqual(_paragraph_forbidden_hits(GOOD_PARAGRAPH), [])
        self.assertEqual(_added_headings(section), [])

    def test_pre_change_section_is_rejected(self):
        section = _stop_report_section(_skill_text_around(PRE_CHANGE_STOP_REPORT_SECTION))
        # Non-vacuity: found by the extraction, and it already names the
        # path and `resume_conditions` in a non-bullet block after the YAML
        # bullet and says 「対話時と同じ内容」.
        self.assertEqual(section, PRE_CHANGE_STOP_REPORT_SECTION)
        self.assertIn(YAML_BULLET, section)
        review_block = section.split("\n\n")[3]
        self.assertFalse(_is_bullet_block(review_block))
        self.assertIn(PARAGRAPH_PATH_ANCHOR, review_block)
        self.assertIn(PARAGRAPH_NAME_ANCHOR, review_block)
        self.assertIn("対話時と同じ内容", _strip_ws(section))
        self.assertIsNone(_target_paragraph(section))

    def test_paragraph_lacking_one_anchor_is_rejected(self):
        variants = {
            "path": (PARAGRAPH_PATH_ANCHOR, "references/other.md"),
            "name": (PARAGRAPH_NAME_ANCHOR, "resume_conditions"),
            "3 件": ("上の 3 件の", "上の"),
            "対話実行": ("対話実行", "対話"),
            "同じ形": ("同じ形", "同じ内容"),
        }
        for label, (old, new) in variants.items():
            with self.subTest(dropped=label):
                forged_paragraph = GOOD_PARAGRAPH.replace(old, new)
                self.assertNotEqual(forged_paragraph, GOOD_PARAGRAPH)
                section = _stop_report_section(
                    _skill_text_around(
                        PRE_CHANGE_STOP_REPORT_SECTION + forged_paragraph + "\n\n"
                    )
                )
                self.assertTrue(_section_is_pre_change_prefixed(section))
                self.assertIn(forged_paragraph, section)
                self.assertIsNone(_target_paragraph(section))

    def test_paragraph_placed_before_the_bullets_is_rejected(self):
        head, rest = PRE_CHANGE_STOP_REPORT_SECTION.split("\n\n", 1)
        forged = head + "\n\n" + GOOD_PARAGRAPH + "\n\n" + rest
        section = _stop_report_section(_skill_text_around(forged))
        self.assertIn(GOOD_PARAGRAPH, section)
        self.assertIn(YAML_BULLET, section)
        self.assertFalse(_section_is_pre_change_prefixed(section))
        self.assertIsNone(_target_paragraph(section))

    def test_paragraph_written_as_a_bullet_is_rejected(self):
        forged_paragraph = "- " + GOOD_PARAGRAPH
        section = _stop_report_section(
            _skill_text_around(PRE_CHANGE_STOP_REPORT_SECTION + forged_paragraph + "\n\n")
        )
        self.assertIn(forged_paragraph, section)
        self.assertIsNone(_target_paragraph(section))

    def test_anchors_split_over_two_paragraphs_are_rejected(self):
        first = (
            "この報告が運ぶリカバリ手順は、上の 3 件のテンプレートが指す手順を含めて、\n"
            "`references/batch-terminal-line.md` の `resume_conditions` の規則に従う。"
        )
        second = "この形は、batch 実行でも、対話実行の報告でも同じ形で出す。"
        section = _stop_report_section(
            _skill_text_around(
                PRE_CHANGE_STOP_REPORT_SECTION + first + "\n\n" + second + "\n\n"
            )
        )
        self.assertIn(first, section)
        self.assertIn(second, section)
        self.assertIsNone(_target_paragraph(section))

    def test_changed_bullet_or_existing_paragraph_breaks_the_prefix_check(self):
        for old, new in (
            ("- スタック:", "- スタック !"),
            ("対話時と同じ内容を全文報告する", "全文報告する"),
            ("ここでは手順の内容を繰り返さない。", "ここでは繰り返さない。"),
        ):
            with self.subTest(old=old):
                self.assertIn(old, GOOD_SECTION)
                forged = GOOD_SECTION.replace(old, new)
                self.assertNotEqual(forged, GOOD_SECTION)
                self.assertIsNotNone(_target_paragraph(forged))
                self.assertFalse(_section_is_pre_change_prefixed(forged))

    def test_added_heading_is_detected(self):
        forged = GOOD_SECTION + "## 追加\n\nx\n\n"
        self.assertEqual(_added_headings(GOOD_SECTION), [])
        self.assertEqual(_added_headings(forged), ["## 追加"])

    def test_each_forbidden_item_in_the_paragraph_is_detected(self):
        self.assertEqual(_paragraph_forbidden_hits(GOOD_PARAGRAPH), [])
        for literal in PARAGRAPH_FORBIDDEN_LITERALS:
            with self.subTest(literal=literal):
                forged = GOOD_PARAGRAPH + "（" + literal + "）"
                self.assertIsNotNone(
                    _target_paragraph(
                        PRE_CHANGE_STOP_REPORT_SECTION + forged + "\n\n"
                    )
                )
                self.assertTrue(_paragraph_forbidden_hits(forged))

    def test_heading_inside_the_paragraph_is_detected(self):
        forged = GOOD_PARAGRAPH + "\n## 見出し"
        self.assertEqual(_paragraph_forbidden_hits(forged), ["## heading"])

    def test_question_tool_count_matcher_detects_an_extra_mention(self):
        text = "x " + QUESTION_TOOL_NAME + " y"
        self.assertEqual(_question_tool_count(text), 1)
        self.assertEqual(_question_tool_count(text + QUESTION_TOOL_NAME), 2)
        self.assertNotEqual(
            _question_tool_count(_read(SKILL_PATH) + QUESTION_TOOL_NAME),
            QUESTION_TOOL_BASELINE_COUNT,
        )


# ==========================================================================
# AC-6: this module's own hygiene
# ==========================================================================
class TestAC6ModuleHygiene(unittest.TestCase):
    def test_module_imports_only_the_standard_library(self):
        source = _read(Path(__file__))
        self.assertEqual(_import_violations(source), [])

    def test_import_scanner_sees_this_modules_imports(self):
        source = _read(Path(__file__))
        names = {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertTrue({"ast", "re", "sys", "unittest"} <= names)

    def test_third_party_import_is_flagged(self):
        self.assertEqual(_import_violations("import yaml\n"), ["yaml"])
        self.assertEqual(_import_violations("import re\nimport os.path\n"), [])

    def test_another_test_module_import_is_flagged(self):
        for source, expected in (
            ("from tests.test_batch_stop_contract import X\n", "tests.test_batch_stop_contract"),
            ("import test_batch_stop_contract\n", "test_batch_stop_contract"),
            ("from _gate_vocabulary import X\n", "_gate_vocabulary"),
        ):
            with self.subTest(source=source):
                self.assertEqual(_import_violations(source), [expected])

    def test_relative_import_is_flagged(self):
        self.assertEqual(_import_violations("from . import helper\n"), ["."])
        self.assertEqual(_import_violations("from .helper import X\n"), [".helper"])


if __name__ == "__main__":
    unittest.main()

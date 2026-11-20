"""Tests for task0005 (review-perspective-model-effort): the user-facing
description of the per-perspective `effort` -- the em-review README's chain
table, the one sentence each README carries about how a codex entry's
`effort` reaches the wrapper, and the security-review-model skill.

Covers task0005 Acceptance Criteria
(feature-docs/review-perspective-model-effort/tasks/task0005.md):

- AC-2: em-review's README chain table lists security, performance, spec and
  architecture with "codex -> litellm/muse-spark", and no row puts litellm
  first.
- AC-3: in each README, the sentence right after the `model` -> `-m`
  sentence states that a codex entry's `effort` goes the same way to the
  wrapper's `--effort`. The text after the `model` sentence is what is
  checked, never the whole file, so an `effort` mention elsewhere cannot
  satisfy it.
- AC-4: the skill's SKILL.md holds none of the wrapper-fixed phrase, the
  "other perspectives write no `model`" statement and the literal
  `model_reasoning_effort="xhigh"`; it states that the security codex
  entry's `effort` sets the reasoning depth, its step 2 checks support for
  that effort, and its description still names the security review.
- AC-5: this module asserts AC-2, AC-3 and AC-4. Each matcher has negative
  proofs on forged text: a litellm-first em-review row, a README without the
  effort sentence, and a SKILL.md that still holds the xhigh-fixed line.
- AC-1 (em-workflow's chain table) is asserted by
  `tests/test_llm_led_review_user_docs.py` through its `PINNED_CHAINS`; this
  module adds the row-level check that ties each of the six perspectives to
  its own "codex -> litellm `muse-spark`" row.

Each matcher returns a list of problem identifiers (an empty list means the
text is fine), so a negative proof can name the one problem its forged text
must raise and show that nothing else is wrong with it. Standard library
only, per test/README.md.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_README = REPO_ROOT / "em-workflow" / "README.md"
EM_REVIEW_README = REPO_ROOT / "em-review" / "README.md"
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "security-review-model" / "SKILL.md"

# ---------------------------------------------------------------------------
# README: the em-review chain table
# ---------------------------------------------------------------------------

CHAIN_TABLE_HEADER = "| 観点 | チェーン（1st → 2nd） |"
EM_REVIEW_CHAIN = "codex → litellm/muse-spark"
EM_REVIEW_CHAIN_PERSPECTIVES = ("security", "performance", "spec", "architecture")
EM_WORKFLOW_CHAIN = "codex → litellm `muse-spark`"
EM_WORKFLOW_CHAIN_PERSPECTIVES = (
    "security",
    "comprehensive",
    "license",
    "performance",
    "spec",
    "architecture",
)


def chain_table_rows(text):
    """Return the chain table's data rows as (perspective names, chain)
    pairs, or None when the table is absent. The first cell is split on
    "/" into perspective names; the second cell is the chain string."""
    lines = text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == CHAIN_TABLE_HEADER
        )
    except StopIteration:
        return None
    rows = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: "):
            continue  # the |---|---| separator row
        names = [name.strip() for name in cells[0].split("/")]
        rows.append((names, cells[1]))
    return rows


def chain_problems(text, expected_chain, perspectives):
    """Check that every perspective in `perspectives` sits on a chain-table
    row whose chain is exactly `expected_chain`, and that no row at all puts
    litellm first."""
    rows = chain_table_rows(text)
    if rows is None:
        return ["chain-table-missing"]
    problems = []
    if any(chain.startswith("litellm") for _names, chain in rows):
        problems.append("litellm-first-row")
    chain_by_perspective = {
        name: chain for names, chain in rows for name in names
    }
    for perspective in perspectives:
        if chain_by_perspective.get(perspective) != expected_chain:
            problems.append(f"chain-not-codex-first:{perspective}")
    return problems


def em_review_chain_problems(text):
    return chain_problems(text, EM_REVIEW_CHAIN, EM_REVIEW_CHAIN_PERSPECTIVES)


def em_workflow_chain_problems(text):
    return chain_problems(text, EM_WORKFLOW_CHAIN, EM_WORKFLOW_CHAIN_PERSPECTIVES)


def _rewrite_chain_cell(text, perspective, new_chain):
    """Forge a copy of `text` whose chain-table row naming `perspective`
    carries `new_chain` instead. Raises when no row names it, so a forged
    fixture can never silently equal the original."""
    out, applied = [], False
    in_table = False
    for line in text.splitlines(keepends=True):
        if line.strip() == CHAIN_TABLE_HEADER:
            in_table = True
        elif in_table and not line.strip().startswith("|"):
            in_table = False
        if in_table and line.strip() != CHAIN_TABLE_HEADER:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            names = [n.strip() for n in cells[0].split("/")]
            if perspective in names and len(cells) >= 2:
                line = f"| {cells[0]} | {new_chain} |\n"
                applied = True
        out.append(line)
    if not applied:
        raise AssertionError(f"no chain-table row names {perspective!r}")
    return "".join(out)


# ---------------------------------------------------------------------------
# README: the effort sentence right after the model sentence
# ---------------------------------------------------------------------------

MODEL_SENTENCE = "`reviewers.yaml` が渡した `model` をレビュアーはそのまま `-m` に流す。"
EFFORT_SENTENCE_TOKENS = ("codex", "`effort`", "同じ", "ラッパー", "`--effort`")


def sentence_after_model_sentence(text):
    """Return the sentence that directly follows MODEL_SENTENCE (on the same
    line or the next line of the same paragraph), or None when the model
    sentence is absent or nothing follows it in its paragraph."""
    index = text.find(MODEL_SENTENCE)
    if index < 0:
        return None
    rest = text[index + len(MODEL_SENTENCE) :]
    paragraph = rest.split("\n\n", 1)[0].lstrip()
    end = paragraph.find("。")
    if not paragraph or end < 0:
        return None
    return paragraph[: end + 1]


def effort_sentence_problems(text):
    if MODEL_SENTENCE not in text:
        return ["model-sentence-missing"]
    sentence = sentence_after_model_sentence(text)
    if sentence is None:
        return ["effort-sentence-missing"]
    return [
        f"effort-sentence-lacks:{token}"
        for token in EFFORT_SENTENCE_TOKENS
        if token not in sentence
    ]


# ---------------------------------------------------------------------------
# SKILL.md
# ---------------------------------------------------------------------------

WRAPPER_FIXED_PHRASE = "ラッパーが固定する"
NO_MODEL_STATEMENT_RE = re.compile(r"`model`\s*を書かず")
XHIGH_LITERAL = 'model_reasoning_effort="xhigh"'
EFFORT_PLACEHOLDER_LITERAL = 'model_reasoning_effort="<effort>"'
LOCATION_EXAMPLE_RE = re.compile(
    r"\{harness: codex, model: <slug>, effort: <effort>\}"
)


def markdown_section(text, heading):
    """Return the body of the "## heading" section (up to the next "## "
    heading or the end), or None when the section is absent."""
    match = re.search(
        rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M
    )
    return match.group(1) if match else None


def frontmatter_description(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return None
    for line in match.group(1).splitlines():
        if line.startswith("description:"):
            return line[len("description:") :].strip()
    return None


def skill_problems(text):
    problems = []
    if WRAPPER_FIXED_PHRASE in text:
        problems.append("wrapper-fixed-phrase")
    if NO_MODEL_STATEMENT_RE.search(text):
        problems.append("other-perspectives-write-no-model")
    if XHIGH_LITERAL in text:
        problems.append("xhigh-literal")

    policy = markdown_section(text, "方針")
    policy_lines = (policy or "").splitlines()
    if not any(
        line.startswith("- ")
        and "セキュリティ" in line
        and "`effort`" in line
        and "推論の深さ" in line
        for line in policy_lines
    ):
        problems.append("policy-lacks-security-effort-depth")
    if not any(
        line.startswith("- ")
        and "`reviewers.yaml`" in line
        and "codex" in line
        and "`model`" in line
        and "`effort`" in line
        for line in policy_lines
    ):
        problems.append("policy-lacks-per-perspective-model-and-effort")

    location = markdown_section(text, "指定している場所")
    if location is None or not LOCATION_EXAMPLE_RE.search(location):
        problems.append("location-example-lacks-effort")

    procedure = markdown_section(text, "更新手順")
    step2 = re.search(r"^2\. (.*)$", procedure or "", re.M)
    if step2 is None or "`effort`" not in step2.group(1) or "対応" not in step2.group(1):
        problems.append("step2-lacks-effort-support-check")
    elif "xhigh" in step2.group(1):
        problems.append("step2-names-xhigh")
    if EFFORT_PLACEHOLDER_LITERAL not in (procedure or ""):
        problems.append("step3-lacks-effort-placeholder")

    description = frontmatter_description(text)
    if description is None or "セキュリティ" not in description:
        problems.append("description-lacks-security-review")
    return problems


def _replace_once(text, old, new):
    """Forge a copy of `text`; raises when `old` is absent so the forgery
    can never silently equal the original."""
    if old not in text:
        raise AssertionError(f"forgery anchor not found: {old!r}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# AC-2: em-review's chain table
# ---------------------------------------------------------------------------


class TestEmReviewChainTable(unittest.TestCase):
    """AC-2: security, performance, spec and architecture all run codex
    first in em-review's chain table, and no row puts litellm first."""

    @classmethod
    def setUpClass(cls):
        cls.text = EM_REVIEW_README.read_text(encoding="utf-8")

    def test_ac2_real_readme_chain_table_is_codex_first(self):
        self.assertEqual(em_review_chain_problems(self.text), [])

    def test_ac2_each_perspective_is_listed_with_the_codex_first_chain(self):
        rows = chain_table_rows(self.text)
        self.assertIsNotNone(rows)
        chain_by_perspective = {n: chain for names, chain in rows for n in names}
        for perspective in EM_REVIEW_CHAIN_PERSPECTIVES:
            with self.subTest(perspective=perspective):
                self.assertEqual(chain_by_perspective.get(perspective), EM_REVIEW_CHAIN)

    def test_ac2_no_row_puts_litellm_first(self):
        for _names, chain in chain_table_rows(self.text):
            self.assertFalse(chain.startswith("litellm"), chain)

    def test_ac5_forged_litellm_first_row_is_rejected(self):
        forged = _rewrite_chain_cell(
            self.text, "performance", "litellm/muse-spark → codex"
        )
        problems = em_review_chain_problems(forged)
        self.assertIn("litellm-first-row", problems)
        self.assertIn("chain-not-codex-first:performance", problems)

    def test_ac5_forged_litellm_first_security_row_is_rejected(self):
        forged = _rewrite_chain_cell(self.text, "security", "litellm/muse-spark → codex")
        self.assertIn("litellm-first-row", em_review_chain_problems(forged))

    def test_ac5_forged_chain_without_the_codex_entry_is_rejected(self):
        forged = _rewrite_chain_cell(self.text, "spec", "litellm/muse-spark")
        self.assertIn("chain-not-codex-first:spec", em_review_chain_problems(forged))

    def test_ac5_forged_table_without_a_perspective_is_rejected(self):
        # Every row keeps a codex-first chain, but `architecture` is no
        # longer named anywhere in the table.
        forged = _rewrite_chain_cell(self.text, "architecture", "（なし。Claude 専用）")
        self.assertIn(
            "chain-not-codex-first:architecture", em_review_chain_problems(forged)
        )

    def test_ac5_forged_readme_without_the_table_is_rejected(self):
        forged = _replace_once(self.text, CHAIN_TABLE_HEADER, "| 観点 | チェーン |")
        self.assertEqual(em_review_chain_problems(forged), ["chain-table-missing"])


class TestEmWorkflowChainTableRows(unittest.TestCase):
    """AC-1 (row level): every perspective sits on a row whose chain is
    "codex -> litellm `muse-spark`" in em-workflow's chain table. The
    `PINNED_CHAINS` check in tests/test_llm_led_review_user_docs.py looks for
    each chain string anywhere in the table block; this class ties each
    perspective to its own row."""

    @classmethod
    def setUpClass(cls):
        cls.text = EM_WORKFLOW_README.read_text(encoding="utf-8")

    def test_ac1_real_readme_chain_table_is_codex_first_for_all_six(self):
        self.assertEqual(em_workflow_chain_problems(self.text), [])

    def test_ac1_forged_litellm_first_row_is_rejected(self):
        forged = _rewrite_chain_cell(
            self.text, "architecture", "litellm `muse-spark` → codex"
        )
        problems = em_workflow_chain_problems(forged)
        self.assertIn("litellm-first-row", problems)
        self.assertIn("chain-not-codex-first:architecture", problems)

    def test_ac1_forged_readme_without_the_table_is_rejected(self):
        forged = _replace_once(self.text, CHAIN_TABLE_HEADER, "| 観点 | チェーン |")
        self.assertEqual(em_workflow_chain_problems(forged), ["chain-table-missing"])


# ---------------------------------------------------------------------------
# AC-3: the effort sentence in both READMEs
# ---------------------------------------------------------------------------


class _EffortSentenceMixin:
    readme_path = None

    @classmethod
    def setUpClass(cls):
        cls.text = cls.readme_path.read_text(encoding="utf-8")

    def test_ac3_real_readme_has_the_effort_sentence_after_the_model_sentence(self):
        self.assertEqual(effort_sentence_problems(self.text), [])

    def test_ac3_the_sentence_right_after_the_model_sentence_names_effort_and_the_flag(self):
        sentence = sentence_after_model_sentence(self.text)
        self.assertIsNotNone(sentence)
        self.assertIn("`effort`", sentence)
        self.assertIn("`--effort`", sentence)

    def test_ac3_model_sentence_itself_is_kept(self):
        self.assertIn(MODEL_SENTENCE, self.text)

    def test_ac5_forged_readme_without_the_effort_sentence_is_rejected(self):
        sentence = sentence_after_model_sentence(self.text)
        forged = _replace_once(self.text, sentence, "")
        self.assertEqual(effort_sentence_problems(forged), ["effort-sentence-missing"])

    def test_ac5_effort_mentioned_elsewhere_does_not_satisfy_the_check(self):
        sentence = sentence_after_model_sentence(self.text)
        self.assertEqual(self.text.count(sentence), 1)
        forged = _replace_once(self.text, sentence, "") + f"\n\n{sentence}\n"
        self.assertIn(sentence, forged)
        self.assertEqual(effort_sentence_problems(forged), ["effort-sentence-missing"])

    def test_ac5_forged_sentence_without_the_wrapper_flag_is_rejected(self):
        sentence = sentence_after_model_sentence(self.text)
        forged = _replace_once(
            self.text, sentence, "codex エントリの `effort` も同じ経路でラッパーに渡る。"
        )
        self.assertEqual(
            effort_sentence_problems(forged), ["effort-sentence-lacks:`--effort`"]
        )

    def test_ac5_forged_sentence_that_is_not_about_codex_is_rejected(self):
        sentence = sentence_after_model_sentence(self.text)
        forged = _replace_once(
            self.text,
            sentence,
            "`effort` も同じ経路でラッパーの `--effort` に届く。",
        )
        self.assertEqual(
            effort_sentence_problems(forged), ["effort-sentence-lacks:codex"]
        )

    def test_ac5_forged_readme_without_the_model_sentence_is_rejected(self):
        forged = _replace_once(self.text, MODEL_SENTENCE, "")
        self.assertEqual(effort_sentence_problems(forged), ["model-sentence-missing"])


class TestEmWorkflowReadmeEffortSentence(_EffortSentenceMixin, unittest.TestCase):
    """AC-3 on em-workflow/README.md."""

    readme_path = EM_WORKFLOW_README


class TestEmReviewReadmeEffortSentence(_EffortSentenceMixin, unittest.TestCase):
    """AC-3 on em-review/README.md."""

    readme_path = EM_REVIEW_README


# ---------------------------------------------------------------------------
# AC-4: the security-review-model skill
# ---------------------------------------------------------------------------


class TestSecurityReviewModelSkill(unittest.TestCase):
    """AC-4: the skill describes setting effort through the registry."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_ac4_real_skill_has_no_problems(self):
        self.assertEqual(skill_problems(self.text), [])

    def test_ac4_wrapper_fixed_phrase_is_gone(self):
        self.assertNotIn(WRAPPER_FIXED_PHRASE, self.text)

    def test_ac4_other_perspectives_write_no_model_statement_is_gone(self):
        self.assertIsNone(NO_MODEL_STATEMENT_RE.search(self.text))

    def test_ac4_literal_xhigh_effort_override_is_gone(self):
        self.assertNotIn(XHIGH_LITERAL, self.text)

    def test_ac4_security_entry_effort_sets_the_reasoning_depth(self):
        policy = markdown_section(self.text, "方針")
        self.assertTrue(
            any(
                "セキュリティ" in line and "`effort`" in line and "推論の深さ" in line
                for line in policy.splitlines()
            ),
            policy,
        )

    def test_ac4_step_2_checks_support_for_the_entry_effort(self):
        procedure = markdown_section(self.text, "更新手順")
        step2 = re.search(r"^2\. (.*)$", procedure, re.M).group(1)
        self.assertIn("`effort`", step2)
        self.assertIn("対応", step2)
        self.assertNotIn("xhigh", step2)

    def test_ac4_step_3_command_uses_the_effort_placeholder(self):
        procedure = markdown_section(self.text, "更新手順")
        self.assertIn(EFFORT_PLACEHOLDER_LITERAL, procedure)

    def test_ac4_location_example_shows_the_codex_entry_with_effort(self):
        location = markdown_section(self.text, "指定している場所")
        self.assertRegex(location, LOCATION_EXAMPLE_RE)

    def test_ac4_description_still_names_the_security_review(self):
        description = frontmatter_description(self.text)
        self.assertIsNotNone(description)
        self.assertIn("セキュリティ", description)

    def test_ac4_untouched_steps_keep_their_content(self):
        procedure = markdown_section(self.text, "更新手順")
        self.assertIn("`codex debug models`", procedure)
        self.assertIn("`tests/test_reviewers_primary_chains.py` の `EXPECTED_CHAINS`", procedure)
        self.assertIn("python3 -m unittest tests.test_codex_wrapper_model_flag", procedure)


class TestSkillMatcherDetectsRegressions(unittest.TestCase):
    """AC-5: the skill matcher rejects forged text that restores the old
    wording or drops the new statements. Each forgery names the one
    problem it must raise and nothing else."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_ac5_real_text_is_the_clean_baseline_for_the_forgeries(self):
        self.assertEqual(skill_problems(self.text), [])

    def test_ac5_skill_that_still_holds_the_xhigh_fixed_line_is_rejected(self):
        forged = self.text + "\n- 推論の深さはラッパーが固定する `xhigh` のままにする。\n"
        self.assertEqual(skill_problems(forged), ["wrapper-fixed-phrase"])

    def test_ac5_skill_that_still_says_other_perspectives_write_no_model_is_rejected(self):
        forged = (
            self.text
            + "\n- それ以外の観点は `model` を書かず、Codex の推奨既定モデルを使う。\n"
        )
        self.assertEqual(skill_problems(forged), ["other-perspectives-write-no-model"])

    def test_ac5_skill_that_still_holds_the_literal_xhigh_override_is_rejected(self):
        forged = (
            self.text
            + "\n    codex exec -c 'model_reasoning_effort=\"xhigh\"' \"Reply with just OK\"\n"
        )
        self.assertEqual(skill_problems(forged), ["xhigh-literal"])

    def test_ac5_skill_whose_step_2_checks_xhigh_support_is_rejected(self):
        procedure = markdown_section(self.text, "更新手順")
        step2 = re.search(r"^2\. .*$", procedure, re.M).group(0)
        forged = _replace_once(
            self.text, step2, "2. 対象モデルが `xhigh` に対応していることを確かめる。"
        )
        self.assertEqual(skill_problems(forged), ["step2-lacks-effort-support-check"])

    def test_ac5_skill_whose_step_3_command_lacks_the_effort_placeholder_is_rejected(self):
        forged = _replace_once(
            self.text, EFFORT_PLACEHOLDER_LITERAL, 'model_reasoning_effort="high"'
        )
        self.assertEqual(skill_problems(forged), ["step3-lacks-effort-placeholder"])

    def test_ac5_skill_whose_location_example_lacks_effort_is_rejected(self):
        forged = _replace_once(
            self.text, "{harness: codex, model: <slug>, effort: <effort>}",
            "{harness: codex, model: <slug>}",
        )
        self.assertEqual(skill_problems(forged), ["location-example-lacks-effort"])

    def test_ac5_skill_without_the_security_effort_depth_statement_is_rejected(self):
        policy = markdown_section(self.text, "方針")
        line = next(
            ln for ln in policy.splitlines()
            if "セキュリティ" in ln and "推論の深さ" in ln
        )
        forged = _replace_once(self.text, line + "\n", "")
        self.assertEqual(skill_problems(forged), ["policy-lacks-security-effort-depth"])

    def test_ac5_skill_without_the_per_perspective_statement_is_rejected(self):
        policy = markdown_section(self.text, "方針")
        line = next(
            ln for ln in policy.splitlines()
            if "`reviewers.yaml`" in ln and "`model`" in ln and "`effort`" in ln
        )
        forged = _replace_once(self.text, line + "\n", "")
        self.assertEqual(
            skill_problems(forged), ["policy-lacks-per-perspective-model-and-effort"]
        )

    def test_ac5_skill_whose_description_drops_the_security_review_is_rejected(self):
        description = frontmatter_description(self.text)
        forged = _replace_once(
            self.text, f"description: {description}", "description: レビューのモデルの更新手順。"
        )
        self.assertEqual(skill_problems(forged), ["description-lacks-security-review"])


# ---------------------------------------------------------------------------
# Module hygiene
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """NFR4: this module imports only the standard library."""

    def test_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), [])


if __name__ == "__main__":
    unittest.main()

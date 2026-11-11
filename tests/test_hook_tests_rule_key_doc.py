"""The destructive-guard part of `.claude/rules/hook-tests.md` describes the
case table's optional `rule` key and the mixed-case guidance
(destructive-guard-mixed-rm-precedence task0002, FR7).

The document is read as text. The "destructive-guard part" is the text from
the top heading through the end of the first `## Rules` list, i.e. everything
before `## Rationale`. Checks are structural: each one looks for the key terms
of an acceptance criterion inside the bullet that must carry it, and none pins
the exact wording of a sentence. Whitespace is dropped before terms are
looked up, so a sentence wrapped over several lines is still one sentence.

The text after the Rules list is left to the tests that read it (they pin
their own phrases). Here it is only checked that the sections follow in the
same order and that the new key is not described in any of them.

Standard library only, per test/README.md.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = REPO_ROOT / ".claude" / "rules" / "hook-tests.md"

RULES_HEADING = "## Rules"
BOUNDARY_HEADING = "## Rationale"

# The sections that follow the destructive-guard part, in document order.
LATER_HEADINGS = (
    "## Rationale",
    "## interpreter-mismatch-guard",
    "## loop-command-guard",
    "## codex-hook-interactive-guard",
    "## cross-repo-write-guard",
    "## doc-redaction-guard",
    "## gitleaks のガード",
)


def read_rule_text():
    return RULE_PATH.read_text(encoding="utf-8")


def destructive_guard_part(text):
    """The text before the `## Rationale` heading."""
    boundary = text.find("\n" + BOUNDARY_HEADING + "\n")
    if boundary == -1:
        raise AssertionError("no `%s` heading in the rule document" % BOUNDARY_HEADING)
    return text[:boundary]


def rules_bullets(part):
    """The top-level bullets of the part's Rules list. Each is the bullet's
    own lines plus its wrapped continuation lines and nested bullets."""
    start = part.find("\n" + RULES_HEADING + "\n")
    if start == -1:
        raise AssertionError("no `%s` heading in the destructive-guard part" % RULES_HEADING)
    bullets = []
    for line in part[start:].splitlines()[2:]:
        if line.startswith("- "):
            bullets.append([line])
        elif bullets:
            bullets[-1].append(line)
    return ["\n".join(lines) for lines in bullets]


def facts(bullet):
    """The sentences and nested bullets of BULLET, one string each, with all
    whitespace removed."""
    text = re.sub(r"\n[ \t]*- ", "。", bullet)
    text = re.sub(r"\s+", "", text)
    return [piece for piece in text.split("。") if piece]


def some_fact_has(bullet, *terms):
    return any(all(term in fact for term in terms) for fact in facts(bullet))


def fourth_element_bullet(part):
    found = [b for b in rules_bullets(part) if "4 要素目" in b]
    if len(found) != 1:
        raise AssertionError(
            "expected one bullet describing the fourth element, found %d" % len(found)
        )
    return found[0]


def mixed_case_bullet(part):
    """The bullet, other than the fourth-element bullet, that tells a case
    combining a recursive delete with a non-rm check to carry `rule`."""
    fourth = fourth_element_bullet(part)
    found = [
        b
        for b in rules_bullets(part)
        if b != fourth and "`rule`" in b and "再帰削除" in b
    ]
    if len(found) != 1:
        raise AssertionError("expected one mixed-case guidance bullet, found %d" % len(found))
    return found[0]


class RuleDocCase(unittest.TestCase):
    def setUp(self):
        self.text = read_rule_text()
        self.part = destructive_guard_part(self.text)


class TestFourthElementDescription(RuleDocCase):
    """AC-1: the fourth-element description names `rule` beside `cwd` and
    `batch` and states what `rule` does."""

    def test_ac1_the_example_object_shows_cwd_batch_and_rule(self):
        objects = re.findall(r"\{[^{}\n]*\}", self.part)
        self.assertTrue(
            any(all('"%s"' % key in obj for key in ("cwd", "batch", "rule")) for obj in objects),
            "no example object holds the keys cwd, batch and rule: %r" % objects,
        )

    def test_ac1_all_three_keys_are_stated_optional(self):
        bullet = fourth_element_bullet(self.part)
        self.assertNotIn("どちらのキー", bullet, "still describes two keys")
        self.assertTrue(some_fact_has(bullet, "省略できる"))
        self.assertRegex(
            "".join(f for f in facts(bullet) if "省略できる" in f),
            r"(3つ|どれも|すべて)",
        )

    def test_ac1_rule_is_a_non_empty_string_compared_with_the_leading_reason_id(self):
        bullet = fourth_element_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "`rule`", "空でない文字列"))
        self.assertTrue(
            some_fact_has(bullet, "permissionDecisionReason", "[destructive-guard/<rule>]", "理由ID")
        )

    def test_ac1_a_mismatch_fails_the_case_and_the_fail_line_shows_the_reason_id(self):
        bullet = fourth_element_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "判定", "理由ID", "失敗"))
        self.assertTrue(some_fact_has(bullet, "FAIL", "得られた理由ID"))

    def test_ac1_a_case_without_rule_is_judged_on_the_decision_only(self):
        bullet = fourth_element_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "`rule`が無いケース", "判定だけ"))


class TestMalformedCases(RuleDocCase):
    """AC-2: an unknown key, a `rule` that is not a string and an empty
    `rule` stop the run as a malformed case."""

    def test_ac2_the_three_malformed_shapes_stop_the_run(self):
        bullet = fourth_element_bullet(self.part)
        self.assertTrue(
            some_fact_has(
                bullet, "知らないキー", "文字列でない`rule`", "空の`rule`", "malformed", "実行を止める"
            ),
            "no sentence of the fourth-element description names the malformed shapes",
        )


class TestMixedCaseGuidance(RuleDocCase):
    """AC-3: a case combining a recursive delete with a non-rm check carries
    `rule`; the bullet summarises the precedence those cases pin."""

    def test_ac3_a_case_combining_a_recursive_delete_with_a_non_rm_check_carries_rule(self):
        bullet = mixed_case_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "再帰削除", "rm以外", "`rule`"))
        self.assertTrue(some_fact_has(bullet, "判定", "理由ID"))

    def test_ac3_a_recursive_delete_deny_wins_over_a_non_rm_ask_in_either_order(self):
        bullet = mixed_case_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "再帰削除", "`deny`", "`ask`", "順序に関係なく"))

    def test_ac3_a_protected_target_in_the_same_statement_keeps_the_self_modification_ask(self):
        bullet = mixed_case_bullet(self.part)
        self.assertTrue(
            some_fact_has(bullet, "同じ文", "削除対象", "自己設定パス", "self-modification", "`ask`")
        )

    def test_ac3_the_batch_demotion_comes_after_the_precedence(self):
        bullet = mixed_case_bullet(self.part)
        self.assertTrue(some_fact_has(bullet, "`CLAUDE_BATCH`", "降格", "優先", "後"))


class TestLaterSectionsStayInPlace(RuleDocCase):
    """AC-4 (structure only): the sections after the destructive-guard part
    follow in the same order, and none of them describes the new key. The
    byte-for-byte comparison with the task's base is made with git diff."""

    def test_ac4_the_later_sections_keep_their_order(self):
        positions = [self.text.find("\n" + heading + "\n") for heading in LATER_HEADINGS]
        self.assertNotIn(-1, positions, positions)
        self.assertEqual(sorted(positions), positions)
        self.assertGreater(positions[0], self.text.find("\n" + RULES_HEADING + "\n"))

    def test_ac4_the_rule_key_is_not_described_after_the_rules_list(self):
        later = self.text[len(self.part) :]
        self.assertNotIn("`rule`", later)
        self.assertNotIn("[destructive-guard/", later)

    def test_ac4_the_phrases_other_tests_require_stay_in_the_destructive_guard_part(self):
        for phrase in (
            '"cwd"',
            '"batch"',
            "4 要素目",
            "{merge_fixture}",
            "worktree",
            "em-workflow/demo/integration",
            "unregistered",
            "python3 em-workflow/hooks/tests/run-destructive-guard.py",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.part)


if __name__ == "__main__":
    unittest.main()

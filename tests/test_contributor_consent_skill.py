"""Tests for task0002: the `contributor-consent` skill shipped identically
in em-workflow and em-review.

Covers task0002 Acceptance Criteria (feature-docs/muse-spark-contributor-
consent/tasks/task0002.md):

- AC-1: both skill documents exist at the stated paths, carry valid skill
  frontmatter, and no `commands/` file was added for this feature in either
  plugin.
- AC-2: each document describes the availability probe by reference to its
  own plugin's review-phase definition and states the not-installed exit
  with the exact message, ending the run before any fact collection,
  question or store access.
- AC-3: each document presents exactly three facts as one explicitly
  labeled group, with the fixed labels, the fixed order and the stated
  value vocabulary including the unavailable-value rendering; neither
  document lists the unpushed-commit state as a presented fact.
- AC-4: each document specifies exactly one interactive question round,
  with both state-dependent wordings and two options each, and states that
  dismissal takes the non-mutating branch and writes nothing.
- AC-5: each document records consent through the guard CLI's `--record`
  and revokes it through `--remove`, and neither document reads or writes
  the store file directly.
- AC-6: neither document is referenced from any develop-phase document in
  either plugin (this task never edits an existing file, so it also adds
  no occurrence of the interactive-question tool name to any develop-phase
  or review-phase document -- that half of AC-6 is a structural guarantee
  of the task's file scope rather than a separate assertion here).
- AC-7: this module itself -- imports no third-party package and passes
  under `python3 -m unittest discover -s tests` (verified by running the
  suite, not by a test within this module).

Frontmatter is parsed with a hand-rolled scalar `key: value` splitter (no
PyYAML), the same dependency-free convention `tests/test_new_worker_agents.py`
documents for agent frontmatter (PyYAML is a plugin runtime dependency, not
a test dependency -- IMPLEMENTATION.md Technology Stack).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGINS = {
    "em-workflow": {
        "plugin_root": REPO_ROOT / "em-workflow",
        "skill_path": REPO_ROOT
        / "em-workflow"
        / "skills"
        / "contributor-consent"
        / "SKILL.md",
        # em-workflow/references/review-phase.md, "## Phase R0" step 6 is
        # the litellm availability probe definition.
        "probe_step": "6",
    },
    "em-review": {
        "plugin_root": REPO_ROOT / "em-review",
        "skill_path": REPO_ROOT
        / "em-review"
        / "skills"
        / "contributor-consent"
        / "SKILL.md",
        # em-review/references/review-phase.md, "## Phase R0" step 8 is the
        # litellm availability probe definition.
        "probe_step": "8",
    },
}

NOT_INSTALLED_LINE = (
    "vertex-review の LiteLLM ハーネスが見つからない。"
    "contributor ティアはこの環境では使えないため、同意の記録は不要。"
)
NO_WRITE_LINE = "同意ストアは変更していない。"

FACT_LABELS = ["リモートの可視性", "ライセンス", "コントリビューター"]

QUESTION_NOT_CONSENTED = (
    "このリポジトリの差分を muse-spark contributor ティアへ送ることに同意する?"
)
OPTIONS_NOT_CONSENTED = ["同意する", "同意しない"]

QUESTION_ALREADY_CONSENTED = (
    "このリポジトリの contributor ティア同意は記録済み。どうする?"
)
OPTIONS_ALREADY_CONSENTED = ["維持する", "撤回する"]

UNPUSHED_WORDINGS = ["未push", "未プッシュ", "unpushed", "un-pushed"]

STORE_INTERNALS = ["muse-consent.json", "EM_WORKFLOW_MUSE_CONSENT"]

HEADING_RE = re.compile(r"^#{1,6}\s")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a prose assertion survives a wrap-column edit that changes no
    word. NOT used for line-anchored extraction (headings, bullet counts,
    numbered-list parsing) -- only for multi-word substring checks below."""
    return re.sub(r"\s+", " ", text)


def _split_frontmatter(text):
    """Return (frontmatter_text, body_text) for a `---`-delimited YAML
    frontmatter block, without requiring a YAML parser dependency."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise AssertionError(f"expected a --- delimited frontmatter block, got: {text[:80]!r}")
    return match.group(1), match.group(2)


def _parse_flat_frontmatter(frontmatter_text):
    """Minimal hand-rolled parser for scalar `key: value` frontmatter lines
    (the shape every SKILL.md in this repository uses)."""
    data = {}
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if not kv:
            raise AssertionError(f"could not parse frontmatter line: {line!r}")
        data[kv.group(1)] = kv.group(2).strip()
    return data


def _extract_section(body, heading_pattern):
    """Return the text strictly between the first line matching
    heading_pattern and the next markdown heading line (or EOF)."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(heading_pattern, line):
            start = i + 1
            break
    if start is None:
        raise AssertionError(f"heading not found: {heading_pattern!r}")
    end = len(lines)
    for j in range(start, len(lines)):
        if HEADING_RE.match(lines[j]):
            end = j
            break
    return "\n".join(lines[start:end])


class ContributorConsentSkillTest(unittest.TestCase):
    def _load(self, plugin):
        info = PLUGINS[plugin]
        text = _read(info["skill_path"])
        fm_text, body = _split_frontmatter(text)
        return _parse_flat_frontmatter(fm_text), body

    # AC-1
    def test_ac1_files_exist_with_valid_frontmatter_and_no_commands_dir(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                self.assertTrue(
                    info["skill_path"].is_file(),
                    f"missing {info['skill_path']}",
                )
                fm, _body = self._load(plugin)
                self.assertEqual(fm.get("name"), "contributor-consent")
                self.assertTrue(fm.get("description"))

                commands_dir = info["plugin_root"] / "commands"
                if commands_dir.is_dir():
                    for f in commands_dir.rglob("*"):
                        self.assertNotIn(
                            "contributor-consent",
                            f.name,
                            f"unexpected commands/ file for this feature: {f}",
                        )

    # AC-2
    def test_ac2_probe_by_reference_and_not_installed_exit(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                self.assertIn("review-phase.md", body)
                self.assertIn(f"Phase R0 手順 {info['probe_step']}", body)

                step1 = _extract_section(body, r"^### 1\.")
                self.assertIn(NOT_INSTALLED_LINE, step1)
                self.assertIn(
                    "事実収集・質問・ストアへのアクセスを一切行わずに終了する",
                    _normalize_ws(step1),
                )
                # the exit happens inside step 1, strictly before step 2
                # (state determination), step 3 (facts) and step 4
                # (question) begin
                self.assertLess(
                    body.index("### 1."),
                    body.index("### 2."),
                )
                self.assertLess(body.index("### 2."), body.index("### 3."))
                self.assertLess(body.index("### 3."), body.index("### 4."))

    # AC-3
    def test_ac3_exactly_three_facts_fixed_labels_order_and_vocabulary(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                facts_heading_idx = body.index("提示する 3 つの事実")
                step3 = _extract_section(body, r"^### 3\.")

                # the subject line is described before the facts heading,
                # inside step 3, and is never itself inside the facts list
                self.assertLess(body.index("### 3."), facts_heading_idx)
                subject_prose = body[body.index("### 3.") : facts_heading_idx]
                self.assertIn("対象", subject_prose)
                self.assertIn("同じキーを共有", subject_prose)

                facts_section = _extract_section(
                    body, r"^#### 提示する 3 つの事実"
                )
                item_lines = re.findall(
                    r"^\d+\.\s+\*\*(.+?)\*\*:\s*(.*)$",
                    facts_section,
                    re.MULTILINE,
                )
                self.assertEqual(
                    len(item_lines),
                    3,
                    f"expected exactly 3 labeled facts, got: {item_lines}",
                )
                labels = [label for label, _value in item_lines]
                self.assertEqual(labels, FACT_LABELS)

                by_label = dict(item_lines)
                self.assertIn("public", by_label["リモートの可視性"])
                self.assertIn("private", by_label["リモートの可視性"])
                self.assertIn("internal", by_label["リモートの可視性"])
                self.assertIn("取得できず", by_label["リモートの可視性"])

                self.assertIn("なし", by_label["ライセンス"])
                self.assertIn("取得できず", by_label["ライセンス"])

                self.assertIn("あなたのみ", by_label["コントリビューター"])
                self.assertIn("あなたを含む N 名", by_label["コントリビューター"])
                self.assertIn("取得できず", by_label["コントリビューター"])

                # each fixed label occurs exactly once within the group
                for label in FACT_LABELS:
                    self.assertEqual(
                        facts_section.count(f"**{label}**"),
                        1,
                        f"{label} should appear exactly once in the facts group",
                    )

                for wording in UNPUSHED_WORDINGS:
                    self.assertNotIn(wording, body)

    # AC-4
    def test_ac4_exactly_one_question_round_with_two_options_each(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                self.assertEqual(
                    body.count("AskUserQuestion"),
                    1,
                    "expected exactly one interactive-question construct",
                )

                not_consented = _extract_section(
                    body, r"^#### 未同意のとき"
                )
                self.assertIn(QUESTION_NOT_CONSENTED, not_consented)
                for option in OPTIONS_NOT_CONSENTED:
                    self.assertIn(f"- {option}", not_consented)
                self.assertEqual(
                    len(re.findall(r"^- ", not_consented, re.MULTILINE)), 2
                )

                already_consented = _extract_section(
                    body, r"^#### 同意済みのとき"
                )
                self.assertIn(QUESTION_ALREADY_CONSENTED, already_consented)
                for option in OPTIONS_ALREADY_CONSENTED:
                    self.assertIn(f"- {option}", already_consented)
                self.assertEqual(
                    len(re.findall(r"^- ", already_consented, re.MULTILINE)), 2
                )

                step6 = _extract_section(body, r"^### 6\.")
                self.assertIn(NO_WRITE_LINE, step6)
                self.assertIn("非破壊側", step6)
                self.assertIn("CLI を呼び出さず", step6)

    # AC-5
    def test_ac5_record_remove_via_cli_never_the_store_file(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                self.assertIn("--record", body)
                self.assertIn("--remove", body)
                self.assertIn("--list", body)
                self.assertIn(
                    "ストアファイルを直接読み書きしない", body
                )

                for internal in STORE_INTERNALS:
                    self.assertNotIn(internal, body)

    # AC-6
    def test_ac6_no_develop_phase_document_references_the_skill(self):
        skill_paths = {info["skill_path"] for info in PLUGINS.values()}
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                for md_path in info["plugin_root"].rglob("*.md"):
                    if md_path in skill_paths:
                        continue
                    text = _read(md_path)
                    self.assertNotIn(
                        "contributor-consent",
                        text,
                        f"{md_path} unexpectedly references the skill",
                    )


if __name__ == "__main__":
    unittest.main()

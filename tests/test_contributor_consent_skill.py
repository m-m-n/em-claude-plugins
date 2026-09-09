"""Tests for the `contributor-consent` skill shipped identically in
em-workflow and em-review.

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
- AC-5: each document queries state through the guard CLI's `--list`, and
  neither document reads or writes the store file directly. (Narrowed by
  task0009 below: recording/revoking is no longer described as an action
  the skill performs -- see task0009 AC-1.)
- AC-6: neither document is referenced from any develop-phase document in
  either plugin (this task never edits an existing file, so it also adds
  no occurrence of the interactive-question tool name to any develop-phase
  or review-phase document -- that half of AC-6 is a structural guarantee
  of the task's file scope rather than a separate assertion here).
- AC-7: this module itself -- imports no third-party package and passes
  under `python3 -m unittest discover -s tests` (verified by running the
  suite, not by a test within this module).

Covers task0009 Acceptance Criteria (feature-docs/muse-spark-contributor-
consent/tasks/task0009.md) -- the amended FR13, under which the skill
presents the mutating command instead of running it:

- AC-1: both documents describe presenting the recording command and the
  removal command as command lines the user runs in their own terminal,
  each naming that plugin's own guard script path and the project-directory
  option, and neither document contains any step, fallback or retry in
  which the skill itself runs a mutating command.
- AC-2: both documents still describe, in order, the same six steps as
  task0002 (probe/exit, read-only check, three facts, one question round,
  command presentation, no-write line on dismissal); neither presents
  unpushed-commit state.
- AC-3: the accompanying context line states that the write path requires
  an interactive terminal, and asserts no impossibility of writing the
  store by other means.
- AC-4: neither document gains an occurrence of the interactive-question
  tool name relative to task0002 (still exactly one `AskUserQuestion` per
  document) and neither is referenced by any develop-phase document (reuses
  the AC-6 check above).
- AC-5: both documents keep valid skill frontmatter, no `commands/` file
  was added for either plugin, and the two documents differ only where
  they name their own plugin (asserted structurally).
- AC-6: this module asserts AC-1 through AC-3 and AC-5 mechanically for
  both documents, imports the standard library only, and
  `python3 -m unittest discover -s tests` passes.

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

# task0009: the two mutating commands are PRESENTED to the user, never
# executed by the skill. These are the exact, ready-to-copy command lines.
PRESENTED_RECORD_CMD = (
    'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py'
    ' --project-dir "$(pwd)" --record'
)
PRESENTED_REMOVE_CMD = (
    'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py'
    ' --project-dir "$(pwd)" --remove'
)

# task0009 AC-3: two exact, single-line sentences (each authored to fit on
# one physical source line, so no Japanese no-space line-wrap can silently
# insert a token into the middle of the checked text -- _normalize_ws only
# recovers word-for-word text across a wrap for space-delimited prose).
# CONTEXT_REQUIREMENT_LINE states the interactive-terminal requirement;
# CONTEXT_NOT_IMPOSSIBLE_LINE explicitly disclaims that this is the only way
# the store could ever be changed (SPEC a12 -- the boundary is a provenance
# proxy, not unbypassability).
CONTEXT_REQUIREMENT_LINE = (
    "コマンドは自分の端末で実行する。エージェント経由の実行は、"
    "書き込み経路が対話的な端末を要求するため拒否される。"
)
CONTEXT_NOT_IMPOSSIBLE_LINE = (
    "これは、エージェントの通常の呼び出し経路からは記録・撤回できないという"
    "意味であり、あらゆる手段による変更が不可能という意味ではない。"
)

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

    # task0009 AC-1
    def test_task0009_ac1_presents_mutating_commands_never_executes_them(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                step5 = _extract_section(body, r"^### 5\.")
                constraints = _extract_section(
                    body, r"^## このスキルの制約"
                )

                # exactly one presented, ready-to-copy command line per
                # mutating branch, and nowhere else in the document
                self.assertEqual(step5.count(PRESENTED_RECORD_CMD), 1)
                self.assertEqual(body.count(PRESENTED_RECORD_CMD), 1)
                self.assertEqual(step5.count(PRESENTED_REMOVE_CMD), 1)
                self.assertEqual(body.count(PRESENTED_REMOVE_CMD), 1)

                # each mutating flag occurs only in a presented-command
                # context: the command line itself (step 5), and the
                # constraints sentence that introduces "presented, not
                # executed" -- never anywhere the skill would be described
                # as performing the write itself
                self.assertEqual(step5.count("--record"), 1)
                self.assertEqual(constraints.count("--record"), 1)
                self.assertEqual(body.count("--record"), 2)
                self.assertEqual(step5.count("--remove"), 1)
                self.assertEqual(constraints.count("--remove"), 1)
                self.assertEqual(body.count("--remove"), 2)

                # no step, fallback or retry in which the skill itself
                # invokes a mutating command (the old "呼び出す" phrasing
                # for --record/--remove must be gone)
                self.assertNotIn("呼び出す", step5)
                self.assertNotIn("--record` で呼び出", body)
                self.assertNotIn("--remove` で呼び出", body)

                # the presented commands name this plugin's own guard
                # script path (via the shared ${CLAUDE_PLUGIN_ROOT}
                # convention already used by the read-only --list call)
                # and the project-directory option
                self.assertIn(
                    '"${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py', step5
                )
                self.assertIn('--project-dir "$(pwd)"', step5)

                # the read-only command is still described as run by the
                # skill itself -- the negative assertions above are not
                # satisfied by removing CLI use altogether
                step2 = _extract_section(body, r"^### 2\.")
                self.assertIn("--list", step2)
                self.assertIn("呼び出し", step2)

    # task0009 AC-2
    def test_task0009_ac2_all_six_steps_present_in_order(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                positions = [body.index(f"### {n}.") for n in range(1, 7)]
                self.assertEqual(positions, sorted(positions))
                for wording in UNPUSHED_WORDINGS:
                    self.assertNotIn(wording, body)

    # task0009 AC-3
    def test_task0009_ac3_context_line_states_requirement_not_impossibility(
        self,
    ):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                self.assertIn(CONTEXT_REQUIREMENT_LINE, body)
                self.assertIn(CONTEXT_NOT_IMPOSSIBLE_LINE, body)

    # task0009 AC-5
    def test_task0009_ac5_valid_frontmatter_and_only_plugin_naming_differs(
        self,
    ):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
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

        # structural cross-plugin equality: normalize the two known,
        # documented divergences (own plugin name; own review-phase step
        # number) and assert the two documents are then identical, so any
        # other drift between them fails this test
        workflow_info = PLUGINS["em-workflow"]
        review_info = PLUGINS["em-review"]
        workflow_text = _read(workflow_info["skill_path"]).replace(
            "em-workflow", "<PLUGIN>"
        ).replace(f"手順 {workflow_info['probe_step']}", "手順 <N>")
        review_text = _read(review_info["skill_path"]).replace(
            "em-review", "<PLUGIN>"
        ).replace(f"手順 {review_info['probe_step']}", "手順 <N>")
        self.assertEqual(workflow_text, review_text)


if __name__ == "__main__":
    unittest.main()

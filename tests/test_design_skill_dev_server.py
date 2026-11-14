"""Tests for task0001 (design-mock-hot-reload): the dev server in the design
skill's agreement loop.

Covers task0001 Acceptance Criteria
(feature-docs/design-mock-hot-reload/tasks/task0001.md):

- AC-1 (FR1, NFR5, TM-1): Step 4 starts a local dev server for the target
  feature's mocks through Bash with `run_in_background`, gives the example
  form `bun ./<mock>.html`, guides the user to the local URL read from the
  server output's `url` / `Routes` lines and presents the server as local
  development use; the instruction that only asks the user to open the mock
  in a browser is gone from Step 4; the whole file holds neither `0.0.0.0`
  nor a `--host` option nor a `--port` option.
- AC-2 (FR1): Step 4 starts the server only when the feature has a mock and
  not in the system-wide scope; `tokens.html` is not given to the server and
  is still opened directly; a mock added during the loop that the running
  server does not serve leads to `TaskStop` and one restart with all the
  feature's mocks, each served at `/<file name without extension>`.
- AC-3 (FR2, TM-2): Step 6 stops the server task started in Step 4 with
  `TaskStop`, does nothing when no server was started and continues closing
  when the task has already ended; the frontmatter `allowed-tools` lists
  `TaskStop` and Bash.
- AC-4 (FR5): Step 4 checks that the command exists (`command -v bun`)
  through Bash with the Bash tool's timeout parameter; when the command is
  missing or the start fails it guides the mock file path (direct open,
  reload by hand) without asking a question; it tells the user that
  `?state=<name>` shows one state with or without the server and names
  designer.md's mock rules as where the rule lives.
- AC-5 (FR3, FR6): Step 4 states that the browser updates through the dev
  server's own update feature and that no reload code goes into the mock
  file; the mock-discipline summary (self-contained / token CSS variables /
  every SPEC state) stays.
- AC-6 (NFR1, TM-2): none of kill, pkill and killall appears as a whole
  word, compared case-insensitively, anywhere in the file, and `TaskStop` is
  the only means of stopping the server that the file names.
- AC-7 (NFR2, NFR3, NFR4): the literal `AskUserQuestion` still occurs exactly
  twice in the file. (The 境界 section and the change set are checked by diff
  against the implement base commit, not by this module; the whole suite is
  run by `python3 -m unittest discover -s tests`.)

Documentation-only task: unit-level structural assertions over the raw text
of em-workflow/skills/design/SKILL.md. Each test slices the part its
criterion names (frontmatter, Step 4, Step 6) and asserts on that slice.
No test starts a dev server or any other process; the live behaviour (start,
update on edit, stop) is a manual check at verify (TS-7). Standard library
only. The document is hard-wrapped Japanese, so phrase checks compare with
all whitespace removed.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_SKILL = REPO_ROOT / "em-workflow" / "skills" / "design" / "SKILL.md"

# The signal-sending command names AC-6 forbids as whole words.
SIGNAL_COMMAND_RE = re.compile(r"\b(?:kill|pkill|killall)\b", re.IGNORECASE)
# Other ways of stopping a process that the file must not name either.
OTHER_STOP_MEANS = ("SIGTERM", "SIGINT", "SIGKILL", "SIGHUP", "Ctrl-C", "Ctrl+C")


def _read():
    return DESIGN_SKILL.read_text(encoding="utf-8")


def _squash(text):
    """Remove all whitespace so hard-wrapped Japanese compares as one run."""
    return re.sub(r"\s+", "", text)


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "design SKILL.md has no frontmatter block"
    return match.group(1)


def _section(text, heading_prefix):
    """Return the text from the `## {heading_prefix}` heading up to the next
    `## ` heading (a `###` subheading does not end the section)."""
    lines = text.split("\n")
    start = None
    for index, line in enumerate(lines):
        if re.match(r"##(?!#)\s", line) and line[3:].startswith(heading_prefix):
            start = index
            break
    assert start is not None, "heading '## %s' not found" % heading_prefix
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"##(?!#)\s", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def _items(section):
    """Split a section into bullet items (a `- ` line plus its continuation
    and nested lines, up to the next top-level bullet or blank line), each
    whitespace-squashed."""
    items = []
    current = None
    for line in section.split("\n"):
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = [line]
        elif current is not None and line.strip() and not line.startswith("#"):
            current.append(line)
        else:
            if current is not None:
                items.append(current)
            current = None
    if current is not None:
        items.append(current)
    return [_squash("\n".join(item)) for item in items]


def _item_with(section, *anchors):
    """Return the squashed items of `section` that contain every anchor."""
    wanted = [_squash(anchor) for anchor in anchors]
    return [item for item in _items(section) if all(a in item for a in wanted)]


def _step4():
    return _section(_read(), "Step 4")


def _step6():
    return _section(_read(), "Step 6")


class TestHelpers(unittest.TestCase):
    """Non-vacuity proofs for the slicing helpers and the AC-6 matcher."""

    SAMPLE = (
        "---\nname: x\nallowed-tools: A, B\n---\n\n# T\n\n"
        "## Step 4: loop\n\nintro\n\n### sub\n\n- one\n  cont\n- two\n\n"
        "## Step 5: next\n\n- five\n"
    )

    def test_section_stops_at_next_two_hash_heading_not_three_hash(self):
        section = _section(self.SAMPLE, "Step 4")
        self.assertIn("### sub", section)
        self.assertIn("- two", section)
        self.assertNotIn("five", section)

    def test_section_fails_loudly_when_heading_is_missing(self):
        with self.assertRaises(AssertionError):
            _section(self.SAMPLE, "Step 9")

    def test_items_join_continuation_lines_and_split_bullets(self):
        self.assertEqual(
            _items(_section(self.SAMPLE, "Step 4")), ["-onecont", "-two"]
        )

    def test_frontmatter_returns_only_the_block(self):
        self.assertEqual(_frontmatter(self.SAMPLE), "name: x\nallowed-tools: A, B")

    def test_signal_matcher_catches_the_three_names_in_any_case(self):
        for sample in ("kill 123", "pkill -f x", "killall node", "Kill it", "KILL"):
            self.assertTrue(SIGNAL_COMMAND_RE.search(sample), sample)

    def test_signal_matcher_catches_a_name_inside_a_hyphenated_name(self):
        self.assertTrue(SIGNAL_COMMAND_RE.search("kill-guard"))

    def test_signal_matcher_ignores_words_that_only_contain_the_letters(self):
        for sample in ("TaskStop", "skilled", "killer", "skills"):
            self.assertIsNone(SIGNAL_COMMAND_RE.search(sample), sample)


class TestAc1DevServerStartAndGuide(unittest.TestCase):
    """AC-1 (FR1, NFR5, TM-1)."""

    def test_step4_starts_the_server_through_bash_with_run_in_background(self):
        self.assertIn("run_in_background", _step4())
        self.assertTrue(_item_with(_step4(), "run_in_background", "Bash"))

    def test_step4_gives_the_example_command_form(self):
        self.assertIn("bun ./<mock>.html", _step4())

    def test_step4_guides_the_url_read_from_the_url_and_routes_lines(self):
        items = _item_with(_step4(), "`url`", "Routes", "URL")
        self.assertTrue(items, "no Step 4 item reads the URL from url / Routes")
        self.assertIn("案内", items[0])

    def test_step4_presents_the_server_as_local_development_use(self):
        text = _squash(_step4())
        self.assertIn("ローカル", text)
        self.assertIn("開発用", text)

    def test_step4_states_that_the_port_is_not_fixed(self):
        self.assertIn("ポートは決め打ちしない", _squash(_step4()))

    def test_step4_no_longer_only_asks_the_user_to_open_the_mock(self):
        self.assertNotIn("モックはブラウザで開いてもらう", _squash(_step4()))

    def test_file_holds_no_widened_listening_address_or_port_option(self):
        text = _read()
        self.assertNotIn("0.0.0.0", text)
        self.assertNotIn("--host", text)
        self.assertNotIn("--port", text)


class TestAc2StartScopeAndRestart(unittest.TestCase):
    """AC-2 (FR1)."""

    def test_server_starts_only_with_a_mock_and_not_in_system_wide_scope(self):
        items = _item_with(_step4(), "システム全体", "起動しない")
        self.assertTrue(items, "no Step 4 item says nothing starts system-wide")
        self.assertIn("モック", items[0])

    def test_tokens_html_is_not_given_to_the_server_and_is_opened_directly(self):
        items = _item_with(_step4(), "tokens.html", "サーバーに渡さ", "直接開")
        self.assertTrue(items, "no Step 4 item keeps tokens.html off the server")

    def test_added_mock_stops_the_task_and_restarts_one_server_with_all_mocks(self):
        items = _item_with(_step4(), "TaskStop", "起動し直す", "モックが増え")
        self.assertTrue(items, "no Step 4 item covers a mock added in the loop")
        self.assertIn("全", items[0])

    def test_each_mock_is_served_at_its_file_name_without_extension(self):
        self.assertIn(
            "/<ファイル名から拡張子を除いた名前>", _squash(_step4())
        )

    def test_several_mocks_go_to_one_server_together(self):
        self.assertTrue(_item_with(_step4(), "run_in_background", "まとめて"))


class TestAc3StepSixStopsTheServer(unittest.TestCase):
    """AC-3 (FR2, TM-2)."""

    def test_step6_stops_the_server_task_with_taskstop(self):
        items = _item_with(_step6(), "TaskStop", "Step 4")
        self.assertTrue(items, "no Step 6 item stops the Step 4 task with TaskStop")

    def test_step6_does_nothing_when_no_server_was_started(self):
        items = _item_with(_step6(), "起動していない", "何もしない")
        self.assertTrue(items, "no Step 6 item covers the no-server case")

    def test_step6_continues_closing_when_the_task_has_already_ended(self):
        items = _item_with(_step6(), "すでに終わって", "締めを続ける")
        self.assertTrue(items, "no Step 6 item covers the already-ended task")

    def test_frontmatter_allowed_tools_lists_taskstop_and_bash(self):
        line = [
            candidate
            for candidate in _frontmatter(_read()).split("\n")
            if candidate.startswith("allowed-tools:")
        ]
        self.assertEqual(len(line), 1)
        tools = [tool.strip() for tool in line[0].split(":", 1)[1].split(",")]
        self.assertIn("TaskStop", tools)
        self.assertIn("Bash", tools)


class TestAc4FallbackAndStateSwitch(unittest.TestCase):
    """AC-4 (FR5)."""

    def test_step4_checks_the_command_exists_with_a_bash_timeout_parameter(self):
        items = _item_with(_step4(), "command -v bun", "Bash", "timeout")
        self.assertTrue(items, "no Step 4 item checks the command with a timeout")
        self.assertIn("パラメータ", items[0])

    def test_step4_does_not_use_a_shell_timeout_command(self):
        items = _item_with(_step4(), "command -v bun", "timeout")
        self.assertTrue(items)
        self.assertIn("シェルのtimeoutコマンドは使わない", items[0])

    def test_missing_command_or_failed_start_guides_the_file_path_to_open_directly(self):
        items = _item_with(_step4(), "コマンドが無い", "起動に失敗", "直接開")
        self.assertTrue(items, "no Step 4 item states the fallback")
        item = items[0]
        self.assertIn("モックファイルのパス", item)
        self.assertIn("手で再読み込み", item)

    def test_fallback_asks_no_question_and_the_loop_continues(self):
        items = _item_with(_step4(), "手で再読み込み", "質問はしない")
        self.assertTrue(items, "the fallback does not say that no question is asked")
        self.assertIn("ループは続く", items[0])

    def test_step4_adds_no_literal_interactive_question_tool_name(self):
        self.assertNotIn("AskUserQuestion", _step4())

    def test_state_switch_is_told_to_the_user_and_points_to_designer_md(self):
        items = _item_with(_step4(), "?state=<name>", "designer.md", "モック規律")
        self.assertTrue(items, "no Step 4 item tells the user about ?state=<name>")
        self.assertIn("1つの状態", items[0])

    def test_state_switch_applies_with_and_without_the_server(self):
        items = _item_with(_step4(), "?state=<name>")
        self.assertTrue(items)
        self.assertIn("サーバーを使うときも直接開くときも", items[0])

    def test_step4_does_not_restate_the_state_switch_rule(self):
        self.assertNotIn("data-state", _step4())


class TestAc5ReloadStanceAndMockDiscipline(unittest.TestCase):
    """AC-5 (FR3, FR6)."""

    def test_browser_updates_through_the_dev_servers_own_update_feature(self):
        items = _item_with(_step4(), "更新機能", "ブラウザ")
        self.assertTrue(items, "no Step 4 item names the server's update feature")

    def test_no_reload_code_is_written_into_the_mock_file(self):
        items = _item_with(_step4(), "更新機能", "再読み込みのコードは書かない")
        self.assertTrue(items, "Step 4 does not forbid reload code in the mock file")

    def test_step4_keeps_the_mock_discipline_summary(self):
        items = _item_with(
            _step4(), "self-contained", "token CSS 変数", "SPEC 状態網羅"
        )
        self.assertTrue(items, "the mock-discipline summary is gone from Step 4")


class TestAc6TaskStopIsTheOnlyStopMeans(unittest.TestCase):
    """AC-6 (NFR1, TM-2)."""

    def test_no_signal_sending_command_name_appears_as_a_word_anywhere(self):
        found = SIGNAL_COMMAND_RE.findall(_read())
        self.assertEqual(found, [])

    def test_no_other_means_of_stopping_a_process_is_named(self):
        text = _read()
        for token in OTHER_STOP_MEANS:
            self.assertNotIn(token, text)

    def test_taskstop_is_named_for_the_restart_and_for_the_closing_step(self):
        self.assertIn("TaskStop", _step4())
        self.assertIn("TaskStop", _step6())

    def test_no_other_stop_means_is_allowed_after_a_taskstop_failure(self):
        items = _item_with(_step6(), "TaskStop", "止められない", "他の手段")
        self.assertTrue(items, "Step 6 does not rule out other stopping means")


class TestAc7ProtectedWording(unittest.TestCase):
    """AC-7 (NFR3): the occurrence count of the interactive-question tool name
    stays at 2 (the frontmatter and Step 1)."""

    def test_interactive_question_tool_name_occurs_exactly_twice(self):
        self.assertEqual(_read().count("AskUserQuestion"), 2)


if __name__ == "__main__":
    unittest.main()

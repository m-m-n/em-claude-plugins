"""Tests for task0001 (feature-docs/unattended-merge): the merge result
contract `em-workflow/references/merge-result.md` and its renderer
`em-workflow/scripts/merge-result.py`.

The renderer is exercised two ways. Rendering rules are unit tests on the
importable `render_result` function; the command line (exit code, stdout,
unreadable input) runs the script as a child process. The script is loaded by
path from its source text, so importing it writes no bytecode cache next to it.
Every test that depends on the home directory supplies a placeholder home
through the environment variable the renderer reads (`HOME`); no test relies
on the real home path.

Covers task0001 Acceptance Criteria
(feature-docs/unattended-merge/tasks/task0001.md):

- AC-1 (FR21, TS12): every reason code renders `not_merged` with the eight
  keys in order, each value double-quoted and escaped; `merged` and
  `already_merged` render with an empty reason (TestAc1ReasonCodesRender).
- AC-2 (FR21, TM-14): an input outside the contract renders
  `not_merged` / `internal_error`, names the field and never echoes the
  value (TestAc2InvalidInput).
- AC-3 (TS12, TM-14): one escaped single line per value, nothing but the
  eight keys, no injected key or second result (TestAc3EscapingAndInjection).
- AC-4 (TS21, TM-15): absolute paths and Notion URLs are replaced before
  rendering (TestAc4Redaction).
- AC-5 (FR21): a missing, unreadable or non-object input document still
  yields a conformant result with exit code 0 (TestAc5CommandLine).
- AC-6 (FR21, NFR8): the contract document defines the key order, the three
  vocabularies and the fallback result, holds no gate identifier, and agrees
  with the renderer and with the 28 reason codes of the shared vocabulary
  (TestAc6ContractDocument).

The tests import the standard library only.
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-result.py"
CONTRACT = REPO_ROOT / "em-workflow" / "references" / "merge-result.md"

# Upper bound for one child process; only a hang can reach it.
CALL_TIMEOUT_SECONDS = 20

# The contract's vocabularies, written out independently of the renderer so a
# drift in either direction is caught.
KEYS = [
    "merge_result",
    "feature",
    "route",
    "reason",
    "pr_url",
    "merge_commit",
    "worktree_removed",
    "detail",
]
RESULT_VALUES = ["merged", "already_merged", "not_merged"]
ROUTE_VALUES = ["pr", "local", "none"]
REASON_CODES = [
    "invalid_arguments",
    "invalid_feature_name",
    "integration_branch_missing",
    "record_unreadable",
    "base_branch_invalid",
    "precondition_unmet",
    "unresolved_findings",
    "commands_unapproved",
    "remote_unresolved",
    "remote_not_github",
    "pr_closed",
    "pr_draft",
    "pr_conflicting",
    "pr_create_failed",
    "lock_busy",
    "lock_lost",
    "worktree_not_clean",
    "conflict_unattributable",
    "verification_failed",
    "push_rejected",
    "ci_failed",
    "ci_timeout",
    "pr_head_moved",
    "base_moving",
    "main_tree_not_ready",
    "merge_failed",
    "git_failed",
    "internal_error",
]

PLACEHOLDER_HOME = "/home/placeholder-user"
PROJECT_ROOT = PLACEHOLDER_HOME + "/work/zz-checkout"
SAMPLE_SHA = "0123456789abcdef0123456789abcdef01234567"
SAMPLE_PR_URL = "https://github.com/example-org/sample-repo/pull/12"

CONTROL_CHARS = re.compile("[\x00-\x1f\x7f-\x9f  ￾￿]")
RESULT_LINE = re.compile(r'([a-z_]+): "((?:[^"\\]|\\.)*)"')
SIMPLE_ESCAPES = {"\\": "\\", '"': '"', "r": "\r", "n": "\n", "t": "\t"}
HEX4 = re.compile(r"[0-9a-f]{4}")


def load_script():
    """Load the renderer by path without writing a bytecode cache."""
    source = SCRIPT.read_text(encoding="utf-8")
    module = types.ModuleType("merge_result_under_test")
    module.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), module.__dict__)
    return module


def unescape(escaped):
    """Decode the contract's escapes; any other backslash use is an error."""
    out = []
    i = 0
    while i < len(escaped):
        ch = escaped[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = escaped[i + 1 : i + 2]
        if nxt in SIMPLE_ESCAPES:
            out.append(SIMPLE_ESCAPES[nxt])
            i += 2
        elif nxt == "u" and HEX4.fullmatch(escaped[i + 2 : i + 6]):
            out.append(chr(int(escaped[i + 2 : i + 6], 16)))
            i += 6
        else:
            raise AssertionError("invalid escape at %d in %r" % (i, escaped))
    return "".join(out)


def parse_result(test, text):
    """Strictly parse one result: exactly the eight keys, in order, each on
    its own physical line, each value a double-quoted escaped scalar. Returns
    the decoded values as a dict."""
    test.assertIsInstance(text, str)
    text.encode("utf-8")
    test.assertEqual(
        CONTROL_CHARS.findall(text.replace("\n", "")),
        [],
        "a control character survived into the result text",
    )
    lines = text.split("\n")
    test.assertEqual(len(lines), 8, "a result is exactly eight physical lines")
    parsed = []
    for line in lines:
        match = RESULT_LINE.fullmatch(line)
        test.assertIsNotNone(match, "line is not key: \"value\": %r" % line)
        parsed.append((match.group(1), unescape(match.group(2))))
    test.assertEqual([key for key, _ in parsed], KEYS)
    return dict(parsed)


def valid_input(**override):
    data = {
        "result": "not_merged",
        "feature": "unattended-merge",
        "route": "pr",
        "reason": "ci_failed",
        "pr_url": SAMPLE_PR_URL,
        "merge_commit": "",
        "worktree_removed": False,
        "detail": "a pull request check failed",
    }
    data.update(override)
    return data


def run_script(args, home=PLACEHOLDER_HOME):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": home,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT)] + list(args),
        capture_output=True,
        env=env,
        timeout=CALL_TIMEOUT_SECONDS,
    )


class RendererTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def render(self, data, home=PLACEHOLDER_HOME):
        with mock.patch.dict(os.environ, {"HOME": home}):
            text = self.mod.render_result(data)
        return text, parse_result(self, text)

    def assert_internal_error(self, parsed, field, forbidden=()):
        self.assertEqual(parsed["merge_result"], "not_merged")
        self.assertEqual(parsed["reason"], "internal_error")
        self.assertIn(field, parsed["detail"])
        text = "\n".join(parsed.values())
        for value in forbidden:
            self.assertNotIn(value, text)


class TestAc1ReasonCodesRender(RendererTestCase):
    def test_every_reason_code_renders_not_merged_with_the_eight_keys_in_order(self):
        for code in REASON_CODES:
            with self.subTest(reason=code):
                _, parsed = self.render(valid_input(reason=code))
                self.assertEqual(list(parsed), KEYS)
                self.assertEqual(parsed["merge_result"], "not_merged")
                self.assertEqual(parsed["reason"], code)
                self.assertEqual(parsed["feature"], "unattended-merge")
                self.assertEqual(parsed["route"], "pr")
                self.assertEqual(parsed["pr_url"], SAMPLE_PR_URL)
                self.assertEqual(parsed["merge_commit"], "")
                self.assertEqual(parsed["worktree_removed"], "false")
                self.assertEqual(parsed["detail"], "a pull request check failed")

    def test_every_route_renders_with_not_merged(self):
        for route in ROUTE_VALUES:
            with self.subTest(route=route):
                _, parsed = self.render(valid_input(route=route))
                self.assertEqual(parsed["route"], route)

    def test_merged_and_already_merged_render_with_an_empty_reason(self):
        for result in ("merged", "already_merged"):
            with self.subTest(result=result):
                _, parsed = self.render(
                    valid_input(
                        result=result,
                        reason="",
                        merge_commit=SAMPLE_SHA,
                        worktree_removed=True,
                        detail="",
                    )
                )
                self.assertEqual(parsed["merge_result"], result)
                self.assertEqual(parsed["reason"], "")
                self.assertEqual(parsed["merge_commit"], SAMPLE_SHA)
                self.assertEqual(parsed["worktree_removed"], "true")
                self.assertEqual(parsed["detail"], "")

    def test_exact_text_of_a_not_merged_result(self):
        text, _ = self.render(valid_input(detail='say "hi" \\ done'))
        self.assertEqual(
            text,
            "\n".join(
                [
                    'merge_result: "not_merged"',
                    'feature: "unattended-merge"',
                    'route: "pr"',
                    'reason: "ci_failed"',
                    'pr_url: "' + SAMPLE_PR_URL + '"',
                    'merge_commit: ""',
                    'worktree_removed: "false"',
                    'detail: "say \\"hi\\" \\\\ done"',
                ]
            ),
        )

    def test_worktree_removed_renders_as_the_quoted_words_true_and_false(self):
        for raw, expected in ((True, "true"), (False, "false"), ("true", "true"), ("false", "false")):
            with self.subTest(raw=raw):
                text, parsed = self.render(valid_input(worktree_removed=raw))
                self.assertEqual(parsed["worktree_removed"], expected)
                self.assertIn('worktree_removed: "%s"' % expected, text)

    def test_an_empty_feature_pr_url_and_merge_commit_are_written_as_empty_quotes(self):
        text, parsed = self.render(valid_input(feature="", pr_url="", route="none"))
        self.assertEqual(parsed["feature"], "")
        self.assertEqual(parsed["pr_url"], "")
        self.assertIn('feature: ""', text)
        self.assertIn('pr_url: ""', text)
        self.assertIn('merge_commit: ""', text)

    def test_unknown_input_keys_are_never_rendered(self):
        _, parsed = self.render(valid_input(extra_key="x", detail_2="y"))
        self.assertEqual(list(parsed), KEYS)


class TestAc2InvalidInput(RendererTestCase):
    # (label, override, offending field, text that must not be echoed)
    CASES = [
        ("result outside the vocabulary", {"result": "zz_bad_result"}, "result", ["zz_bad_result"]),
        ("result in another case", {"result": "Merged", "reason": ""}, "result", ["Merged"]),
        ("route outside the vocabulary", {"route": "zz_bad_route"}, "route", ["zz_bad_route"]),
        ("reason outside the vocabulary", {"reason": "zz_bad_reason"}, "reason", ["zz_bad_reason"]),
        ("not_merged with an empty reason", {"reason": ""}, "reason", []),
        ("merged carrying a reason", {"result": "merged", "reason": "ci_failed"}, "reason", ["ci_failed"]),
        ("already_merged carrying a reason", {"result": "already_merged", "reason": "git_failed"}, "reason", ["git_failed"]),
        ("short merge_commit", {"merge_commit": "abc123"}, "merge_commit", ["abc123"]),
        ("upper-case merge_commit", {"merge_commit": "A" * 40}, "merge_commit", ["A" * 40]),
        ("41-digit merge_commit", {"merge_commit": "b" * 41}, "merge_commit", ["b" * 41]),
        ("non-hex merge_commit", {"merge_commit": "g" * 40}, "merge_commit", ["g" * 40]),
        ("merge_commit with a trailing line feed", {"merge_commit": "c" * 40 + "\n"}, "merge_commit", ["c" * 40]),
        ("http pr_url", {"pr_url": "http://zz.example/pull/1"}, "pr_url", ["zz.example"]),
        ("ftp pr_url", {"pr_url": "ftp://zz.example/x"}, "pr_url", ["zz.example"]),
        ("script pr_url", {"pr_url": "javascript:zz_alert(1)"}, "pr_url", ["zz_alert"]),
        ("scheme-less pr_url", {"pr_url": "zz.example/pull/1"}, "pr_url", ["zz.example"]),
        ("pr_url without a host", {"pr_url": "https://"}, "pr_url", []),
        ("pr_url with a space", {"pr_url": "https://zz.example/a b"}, "pr_url", ["zz.example"]),
        ("pr_url with a line break", {"pr_url": "https://zz.example/a\nb"}, "pr_url", ["zz.example"]),
        ("pr_url with a double quote", {"pr_url": 'https://zz.example/a"b'}, "pr_url", ["zz.example"]),
        ("pr_url naming a Notion page", {"pr_url": "https://www.notion.so/zz-secret-page-1"}, "pr_url", ["notion", "zz-secret"]),
        ("feature with upper case", {"feature": "Zz-Feature"}, "feature", ["Zz-Feature"]),
        ("feature with a leading hyphen", {"feature": "-zz-feature"}, "feature", ["-zz-feature"]),
        ("feature with a space", {"feature": "zz feature"}, "feature", ["zz feature"]),
        ("feature with a slash", {"feature": "zz/feature"}, "feature", ["zz/feature"]),
        ("feature with an underscore", {"feature": "zz_feature"}, "feature", ["zz_feature"]),
        ("feature with a trailing line feed", {"feature": "zz-feature\n"}, "feature", ["zz-feature"]),
        ("worktree_removed as a word", {"worktree_removed": "zz_maybe"}, "worktree_removed", ["zz_maybe"]),
        ("worktree_removed as a capitalised word", {"worktree_removed": "True"}, "worktree_removed", []),
        ("worktree_removed as an integer", {"worktree_removed": 1}, "worktree_removed", []),
        ("worktree_removed as null", {"worktree_removed": None}, "worktree_removed", []),
        ("worktree_removed as a list", {"worktree_removed": [True]}, "worktree_removed", []),
        ("result as an integer", {"result": 5}, "result", []),
        ("route as null", {"route": None}, "route", []),
        ("reason as a list", {"reason": ["ci_failed"]}, "reason", []),
        ("feature as an integer", {"feature": 5}, "feature", []),
        ("pr_url as an integer", {"pr_url": 5}, "pr_url", []),
        ("merge_commit as an integer", {"merge_commit": 5}, "merge_commit", []),
        ("detail as null", {"detail": None}, "detail", []),
        ("detail as an integer", {"detail": 5}, "detail", []),
        ("detail as a mapping", {"detail": {"zz_inner": "zz_value"}}, "detail", ["zz_inner", "zz_value"]),
    ]

    def test_each_invalid_input_renders_internal_error_naming_the_field(self):
        for label, override, field, forbidden in self.CASES:
            with self.subTest(label):
                _, parsed = self.render(valid_input(**override))
                self.assert_internal_error(parsed, field, forbidden)

    def test_every_missing_key_renders_internal_error_naming_the_field(self):
        for name in (
            "result",
            "feature",
            "route",
            "reason",
            "pr_url",
            "merge_commit",
            "worktree_removed",
            "detail",
        ):
            with self.subTest(missing=name):
                data = valid_input()
                del data[name]
                _, parsed = self.render(data)
                self.assert_internal_error(parsed, name)

    def test_a_value_that_is_valid_on_its_own_survives_into_the_internal_error(self):
        _, parsed = self.render(
            valid_input(
                reason="zz_bad_reason",
                merge_commit=SAMPLE_SHA,
                worktree_removed=True,
            )
        )
        self.assert_internal_error(parsed, "reason", ["zz_bad_reason"])
        self.assertEqual(parsed["feature"], "unattended-merge")
        self.assertEqual(parsed["route"], "pr")
        self.assertEqual(parsed["pr_url"], SAMPLE_PR_URL)
        self.assertEqual(parsed["merge_commit"], SAMPLE_SHA)
        self.assertEqual(parsed["worktree_removed"], "true")

    def test_an_invalid_value_is_replaced_by_the_default_in_the_internal_error(self):
        _, parsed = self.render(
            valid_input(
                feature="Zz Bad",
                route="zz_bad_route",
                pr_url="http://zz.example/x",
                merge_commit="abc",
                worktree_removed="zz",
            )
        )
        self.assert_internal_error(parsed, "feature")
        self.assertEqual(parsed["feature"], "")
        self.assertEqual(parsed["route"], "none")
        self.assertEqual(parsed["pr_url"], "")
        self.assertEqual(parsed["merge_commit"], "")
        self.assertEqual(parsed["worktree_removed"], "false")

    def test_the_first_offending_field_in_key_order_is_named(self):
        _, parsed = self.render(valid_input(route="zz_bad_route", merge_commit="abc"))
        self.assertIn("route", parsed["detail"])
        self.assertNotIn("merge_commit", parsed["detail"])

    def test_an_input_that_is_not_a_mapping_renders_internal_error(self):
        for raw in (None, [], [valid_input()], "text", 5, True):
            with self.subTest(raw=raw):
                _, parsed = self.render(raw)
                self.assertEqual(parsed["merge_result"], "not_merged")
                self.assertEqual(parsed["reason"], "internal_error")

    def test_every_internal_error_uses_a_reason_from_the_vocabulary(self):
        for label, override, _, _ in self.CASES:
            with self.subTest(label):
                _, parsed = self.render(valid_input(**override))
                self.assertIn(parsed["reason"], REASON_CODES)


class TestAc3EscapingAndInjection(RendererTestCase):
    def test_line_breaks_quotes_backslashes_and_controls_render_as_one_escaped_line(self):
        detail = (
            'first\nsecond\r\nthird\ttab "quoted" back\\slash '
            "nul\x00 esc\x1b del\x7f c1\x85 ls  ps  nf￾ nf￿ end"
        )
        text, parsed = self.render(valid_input(detail=detail))
        self.assertEqual(list(parsed), KEYS)
        self.assertEqual(
            parsed["detail"],
            'first second third tab "quoted" back\\slash nul esc del c1 ls ps nf nf end',
        )
        self.assertEqual(len(text.split("\n")), 8)
        self.assertNotIn("\r", text)
        self.assertIn('\\"quoted\\"', text)
        self.assertIn("back\\\\slash", text)

    def test_the_written_text_holds_no_literal_control_character(self):
        text, _ = self.render(valid_input(detail="a\x00b\x01c\x1fd\x7fe\x80f\x9fg h i￾j￿k"))
        self.assertEqual(CONTROL_CHARS.findall(text.replace("\n", "")), [])

    def test_a_detail_cannot_inject_another_key_or_a_second_result(self):
        attacks = [
            'x"\nmerge_result: "merged"\nreason: ""',
            'x", route: "local',
            'x"}\nfeature: "evil"',
            "x\r\nmerge_result: \"merged\"",
            'x\\"\nreason: "',
            "x merge_result: \"merged\"",
            "---\nmerge_result: \"merged\"\n...",
        ]
        for attack in attacks:
            with self.subTest(attack=attack):
                text, parsed = self.render(valid_input(detail=attack))
                self.assertEqual(list(parsed), KEYS)
                self.assertEqual(parsed["merge_result"], "not_merged")
                self.assertEqual(parsed["reason"], "ci_failed")
                self.assertEqual(parsed["route"], "pr")
                self.assertEqual(len(text.split("\n")), 8)
                for key in KEYS:
                    self.assertEqual(text.count("\n" + key + ": ") + text.startswith(key + ": "), 1)

    def test_a_field_other_than_detail_cannot_carry_a_line_break_into_the_result(self):
        for override in (
            {"feature": 'ok"\nmerge_result: "merged'},
            {"pr_url": 'https://zz.example/a"\nreason: "'},
            {"merge_commit": "a" * 40 + '"\nroute: "pr'},
            {"route": 'pr"\nreason: "'},
            {"reason": 'ci_failed"\nroute: "'},
            {"result": 'merged"\nreason: "'},
        ):
            with self.subTest(override=override):
                text, parsed = self.render(valid_input(**override))
                self.assertEqual(list(parsed), KEYS)
                self.assertEqual(parsed["reason"], "internal_error")
                self.assertEqual(len(text.split("\n")), 8)

    def test_input_keys_with_hostile_names_never_reach_the_output(self):
        data = valid_input()
        data['evil"\nmerge_result'] = "merged"
        data["detail\n"] = "second"
        text, parsed = self.render(data)
        self.assertEqual(list(parsed), KEYS)
        self.assertNotIn("evil", text)
        self.assertEqual(parsed["detail"], "a pull request check failed")

    def test_runs_of_spaces_collapse_and_the_ends_are_trimmed(self):
        _, parsed = self.render(valid_input(detail="  a   b \n\n c  "))
        self.assertEqual(parsed["detail"], "a b c")

    def test_a_detail_of_only_whitespace_and_controls_renders_empty(self):
        _, parsed = self.render(valid_input(detail=" \n\t\x00 "))
        self.assertEqual(parsed["detail"], "")

    def test_characters_outside_the_control_set_are_kept_unchanged(self):
        _, parsed = self.render(valid_input(detail="日本語 \U0001f600 é"))
        self.assertEqual(parsed["detail"], "日本語 \U0001f600 é")

    def test_an_unpaired_surrogate_cannot_break_the_output(self):
        text, parsed = self.render(valid_input(detail="a\ud800b"))
        text.encode("utf-8")
        self.assertEqual(parsed["detail"], "a b")

    def test_a_detail_at_the_cap_is_kept_whole(self):
        cap = self.mod.DETAIL_CAP
        _, parsed = self.render(valid_input(detail="x" * cap))
        self.assertEqual(parsed["detail"], "x" * cap)

    def test_a_detail_over_the_cap_is_cut_to_exactly_the_cap_and_marked(self):
        cap = self.mod.DETAIL_CAP
        _, parsed = self.render(valid_input(detail="x" * (cap + 1)))
        self.assertEqual(len(parsed["detail"]), cap)
        self.assertTrue(parsed["detail"].endswith("..."))
        self.assertEqual(parsed["detail"], "x" * (cap - 3) + "...")

    def test_the_cap_is_applied_after_redaction(self):
        long_path = PROJECT_ROOT + "/" + "d" * 2000
        with mock.patch.dict(os.environ, {"HOME": PLACEHOLDER_HOME}):
            text = self.mod.render_result(valid_input(detail=long_path, project_root=PROJECT_ROOT))
        parsed = parse_result(self, text)
        self.assertLessEqual(len(parsed["detail"]), self.mod.DETAIL_CAP)
        self.assertNotIn("zz-checkout", text)
        self.assertNotIn(PLACEHOLDER_HOME, text)


class TestAc4Redaction(RendererTestCase):
    def render_detail(self, detail, project_root=PROJECT_ROOT, home=PLACEHOLDER_HOME):
        data = valid_input(detail=detail)
        if project_root is not None:
            data["project_root"] = project_root
        _, parsed = self.render(data, home=home)
        return parsed["detail"]

    def test_a_path_under_the_project_root_renders_repository_relative(self):
        detail = "see %s/em-workflow/scripts/x.py and %s/.claude/worktrees/a/b" % (
            PROJECT_ROOT,
            PROJECT_ROOT,
        )
        self.assertEqual(
            self.render_detail(detail),
            "see em-workflow/scripts/x.py and .claude/worktrees/a/b",
        )

    def test_the_project_root_itself_renders_as_a_dot(self):
        self.assertEqual(self.render_detail("in " + PROJECT_ROOT), "in .")
        self.assertEqual(self.render_detail("in %s/ now" % PROJECT_ROOT), "in . now")

    def test_the_project_root_with_a_trailing_slash_in_the_input_still_matches(self):
        self.assertEqual(
            self.render_detail("%s/a.txt" % PROJECT_ROOT, project_root=PROJECT_ROOT + "/"),
            "a.txt",
        )

    def test_any_other_path_under_the_home_directory_renders_as_tilde(self):
        self.assertEqual(
            self.render_detail("log at %s/notes/n.txt" % PLACEHOLDER_HOME),
            "log at ~/notes/n.txt",
        )
        self.assertEqual(self.render_detail("home is " + PLACEHOLDER_HOME), "home is ~")

    def test_a_path_under_the_home_directory_renders_as_tilde_without_a_project_root(self):
        self.assertEqual(
            self.render_detail("%s/work/zz-checkout/a.txt" % PLACEHOLDER_HOME, project_root=None),
            "~/work/zz-checkout/a.txt",
        )

    def test_the_project_root_wins_over_the_home_directory(self):
        self.assertEqual(
            self.render_detail("%s/a.txt and %s/b.txt" % (PROJECT_ROOT, PLACEHOLDER_HOME + "/other")),
            "a.txt and ~/other/b.txt",
        )

    def test_a_project_root_outside_the_home_directory_is_made_relative(self):
        self.assertEqual(
            self.render_detail("/srv/repo/x/y.txt", project_root="/srv/repo"),
            "x/y.txt",
        )

    def test_the_project_root_is_never_printed(self):
        text, parsed = self.render(valid_input(project_root=PROJECT_ROOT, detail=""))
        self.assertNotIn("zz-checkout", text)
        self.assertNotIn(PLACEHOLDER_HOME, text)
        self.assertEqual(list(parsed), KEYS)

    def test_a_path_outside_the_home_directory_and_the_project_root_is_left_alone(self):
        self.assertEqual(
            self.render_detail("/usr/bin/git and /tmp/x"),
            "/usr/bin/git and /tmp/x",
        )

    def test_a_directory_that_only_shares_a_prefix_with_the_home_is_left_alone(self):
        detail = "%s2/x and %s-old/y and %s.bak/z" % ((PLACEHOLDER_HOME,) * 3)
        self.assertEqual(self.render_detail(detail, project_root=None), detail)

    def test_a_path_that_only_ends_in_the_home_path_is_left_alone(self):
        detail = "at /mnt/backup%s/x" % PLACEHOLDER_HOME
        self.assertEqual(self.render_detail(detail, project_root=None), detail)

    def test_a_url_whose_path_contains_the_home_path_is_left_alone(self):
        detail = "see https://example.com%s/x/pull/1" % PLACEHOLDER_HOME
        self.assertEqual(self.render_detail(detail, project_root=None), detail)

    def test_a_pr_url_is_not_altered(self):
        _, parsed = self.render(valid_input(project_root=PROJECT_ROOT))
        self.assertEqual(parsed["pr_url"], SAMPLE_PR_URL)

    def test_paths_next_to_punctuation_are_replaced(self):
        self.assertEqual(
            self.render_detail('cwd:%s/a, "%s/b" (%s/c)' % ((PROJECT_ROOT,) * 3)),
            'cwd:a, "b" (c)',
        )

    def test_every_notion_url_form_renders_as_the_placeholder(self):
        urls = [
            "https://www.notion.so/Spec-1234567890abcdef",
            "https://acme.notion.site/Page-abc?pvs=4#frag",
            "http://notion.com/x/y",
            "HTTPS://WWW.NOTION.SO/Upper-Case",
            "https://notion.so",
            "https://notion.so:443/p",
        ]
        for url in urls:
            with self.subTest(url=url):
                detail = self.render_detail("see %s for more" % url, project_root=None)
                self.assertEqual(detail, "see <notion-url> for more")

    def test_a_notion_url_in_quotes_or_brackets_keeps_the_surrounding_text(self):
        self.assertEqual(
            self.render_detail('a "https://www.notion.so/p-1" b (https://www.notion.so/p-2) c', project_root=None),
            'a "<notion-url>" b (<notion-url>) c',
        )

    def test_a_url_on_another_host_is_left_alone(self):
        detail = "https://example.com/notion.so/x and https://mynotion.so/y"
        self.assertEqual(self.render_detail(detail, project_root=None), detail)

    def test_a_notion_url_and_a_path_in_the_same_detail_are_both_replaced(self):
        detail = "%s/a.txt https://www.notion.so/p-1 %s/b.txt" % (PROJECT_ROOT, PLACEHOLDER_HOME)
        self.assertEqual(self.render_detail(detail), "a.txt <notion-url> ~/b.txt")

    def test_a_notion_url_in_any_other_value_never_reaches_the_output(self):
        for key in ("feature", "pr_url", "merge_commit", "route", "reason", "result"):
            with self.subTest(key=key):
                text, parsed = self.render(valid_input(**{key: "https://www.notion.so/zz-secret-1"}))
                self.assertNotIn("notion.so", text)
                self.assertNotIn("zz-secret", text)
                self.assertEqual(parsed["reason"], "internal_error")

    def test_a_home_path_in_any_other_value_never_reaches_the_output(self):
        for key in ("feature", "pr_url", "merge_commit", "route", "reason", "result"):
            with self.subTest(key=key):
                text, parsed = self.render(valid_input(**{key: PLACEHOLDER_HOME + "/zz-secret"}))
                self.assertNotIn(PLACEHOLDER_HOME, text)
                self.assertEqual(parsed["reason"], "internal_error")

    def test_a_home_directory_too_shallow_to_name_a_user_replaces_nothing(self):
        for home in ("/", "/root", ""):
            with self.subTest(home=home):
                self.assertEqual(
                    self.render_detail("/usr/bin/git /root/x /a/b", project_root=None, home=home),
                    "/usr/bin/git /root/x /a/b",
                )

    def test_an_unusable_project_root_is_ignored(self):
        for root in (5, None, "", "relative/path", "/", ["/x"]):
            with self.subTest(root=root):
                data = valid_input(detail="%s/a.txt" % PLACEHOLDER_HOME, project_root=root)
                _, parsed = self.render(data)
                self.assertEqual(parsed["detail"], "~/a.txt")

    def test_the_command_line_reads_the_home_directory_from_the_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "input.json"
            doc.write_text(
                '{"result": "not_merged", "feature": "f", "route": "none", "reason": "git_failed",'
                ' "pr_url": "", "merge_commit": "", "worktree_removed": false,'
                ' "detail": "%s/notes/n.txt https://www.notion.so/p-1", "project_root": "%s"}'
                % (PLACEHOLDER_HOME, PROJECT_ROOT),
                encoding="utf-8",
            )
            proc = run_script([str(doc)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        parsed = parse_result(self, proc.stdout.decode("utf-8")[:-1])
        self.assertEqual(parsed["detail"], "~/notes/n.txt <notion-url>")


class TestAc5CommandLine(unittest.TestCase):
    def run_on_document(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "input.json"
            if isinstance(content, bytes):
                doc.write_bytes(content)
            else:
                doc.write_text(content, encoding="utf-8")
            return run_script([str(doc)])

    def assert_cli_internal_error(self, proc, forbidden=()):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        out = proc.stdout.decode("utf-8")
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))
        parsed = parse_result(self, out[:-1])
        self.assertEqual(parsed["merge_result"], "not_merged")
        self.assertEqual(parsed["reason"], "internal_error")
        for value in forbidden:
            self.assertNotIn(value, out)
        return parsed

    def test_a_valid_document_prints_exactly_the_rendered_result(self):
        mod = load_script()
        data = valid_input(project_root=PROJECT_ROOT, detail=PROJECT_ROOT + "/a.txt")
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "input.json"
            doc.write_text(json.dumps(data), encoding="utf-8")
            proc = run_script([str(doc)])
            with mock.patch.dict(os.environ, {"HOME": PLACEHOLDER_HOME}):
                expected = mod.render_result(data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(proc.stdout.decode("utf-8"), expected + "\n")
        self.assertEqual(parse_result(self, expected)["detail"], "a.txt")

    def test_a_missing_document_yields_a_conformant_internal_error_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "zz-no-such-input.json")
            proc = run_script([missing])
        parsed = self.assert_cli_internal_error(proc, forbidden=["zz-no-such-input"])
        self.assertTrue(parsed["detail"])

    def test_a_directory_in_place_of_the_document_yields_internal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_script([tmp])
        self.assert_cli_internal_error(proc, forbidden=[tmp])

    def test_a_document_that_is_not_json_yields_internal_error(self):
        for content in ("not json {", "", "{", '{"result": "merged",}', "\x00\x01"):
            with self.subTest(content=content):
                proc = self.run_on_document(content)
                self.assert_cli_internal_error(proc, forbidden=["not json"])

    def test_a_document_with_invalid_utf8_yields_internal_error(self):
        proc = self.run_on_document(b'{"detail": "\xff\xfe"}')
        self.assert_cli_internal_error(proc)

    def test_a_document_that_is_not_a_json_object_yields_internal_error(self):
        for content in ('["merged"]', '"merged"', "5", "null", "true", "[]"):
            with self.subTest(content=content):
                proc = self.run_on_document(content)
                self.assert_cli_internal_error(proc)

    def test_a_deeply_nested_document_yields_internal_error(self):
        proc = self.run_on_document("[" * 100000)
        self.assert_cli_internal_error(proc)

    def test_a_json_object_that_breaks_the_contract_yields_internal_error_naming_the_field(self):
        proc = self.run_on_document('{"result": "merged"}')
        parsed = self.assert_cli_internal_error(proc)
        self.assertIn("feature", parsed["detail"])

    def test_a_wrong_number_of_arguments_still_prints_a_result_with_exit_zero(self):
        for args in ([], ["a.json", "b.json"]):
            with self.subTest(args=args):
                proc = run_script(args)
                self.assert_cli_internal_error(proc)

    def test_an_unexpected_failure_while_rendering_prints_the_fixed_fallback(self):
        mod = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "input.json"
            doc.write_text("{}", encoding="utf-8")
            captured = _CapturedStdout()
            with mock.patch.object(mod, "render_result", side_effect=RuntimeError("zz boom")):
                with mock.patch.object(sys, "stdout", captured):
                    code = mod.main([str(doc)])
        self.assertEqual(code, 0)
        self.assertEqual(captured.getvalue().decode("utf-8"), mod.FALLBACK_RESULT + "\n")

    def test_the_exit_code_is_non_zero_only_when_nothing_could_be_printed(self):
        mod = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "input.json"
            doc.write_text("{}", encoding="utf-8")
            with mock.patch.object(sys, "stdout", _BrokenStdout()):
                code = mod.main([str(doc)])
        self.assertNotEqual(code, 0)


class _CapturedStdout:
    def __init__(self):
        self.buffer = _Sink()

    def getvalue(self):
        return bytes(self.buffer.data)

    def write(self, text):  # pragma: no cover - the renderer writes bytes
        raise AssertionError("the renderer must write bytes to stdout.buffer")

    def flush(self):
        pass


class _Sink:
    def __init__(self):
        self.data = bytearray()

    def write(self, payload):
        self.data += payload
        return len(payload)

    def flush(self):
        pass


class _BrokenStdout:
    class _Buffer:
        def write(self, payload):
            raise BrokenPipeError("closed")

        def flush(self):
            raise BrokenPipeError("closed")

    def __init__(self):
        self.buffer = self._Buffer()

    def write(self, text):
        raise BrokenPipeError("closed")

    def flush(self):
        raise BrokenPipeError("closed")


class TestAc6ContractDocument(RendererTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = CONTRACT.read_text(encoding="utf-8")

    @staticmethod
    def section(text, heading):
        match = re.search(r"^## " + re.escape(heading) + r"[ \t]*$", text, re.M)
        if match is None:
            raise AssertionError("missing section: ## " + heading)
        rest = text[match.end() :]
        following = re.search(r"^## ", rest, re.M)
        return rest[: following.start()] if following else rest

    @staticmethod
    def first_column(section_text):
        values = []
        for line in section_text.splitlines():
            if not line.startswith("|"):
                continue
            first = line.strip().strip("|").split("|")[0].strip()
            match = re.fullmatch(r"`([^`]+)`", first)
            if match:
                values.append(match.group(1))
        return values

    @staticmethod
    def yaml_block(section_text):
        match = re.search(r"```yaml\n(.*?)\n```", section_text, re.S)
        if match is None:
            raise AssertionError("no fenced yaml block in the section")
        return match.group(1)

    def test_the_contract_document_exists(self):
        self.assertTrue(CONTRACT.is_file())

    def test_the_document_contains_no_gate_identifier(self):
        self.assertIsNone(re.search(r"\bgate[\s_-]*ids?\b", self.doc, re.I))

    def test_the_document_example_lists_the_eight_keys_in_order(self):
        block = self.yaml_block(self.section(self.doc, "Result format"))
        parsed = parse_result(self, block)
        self.assertEqual(list(parsed), KEYS)

    def test_the_document_example_is_a_fixed_point_of_the_renderer(self):
        block = self.yaml_block(self.section(self.doc, "Result format"))
        parsed = parse_result(self, block)
        data = {
            "result": parsed["merge_result"],
            "feature": parsed["feature"],
            "route": parsed["route"],
            "reason": parsed["reason"],
            "pr_url": parsed["pr_url"],
            "merge_commit": parsed["merge_commit"],
            "worktree_removed": parsed["worktree_removed"],
            "detail": parsed["detail"],
        }
        text, _ = self.render(data)
        self.assertEqual(text, block)

    def test_the_renderer_keys_and_vocabularies_match_the_contract_values(self):
        self.assertEqual(list(self.mod.KEYS), KEYS)
        self.assertEqual(list(self.mod.RESULT_VALUES), RESULT_VALUES)
        self.assertEqual(list(self.mod.ROUTE_VALUES), ROUTE_VALUES)

    def test_the_document_result_and_route_vocabularies_equal_the_renderer_values(self):
        self.assertEqual(self.first_column(self.section(self.doc, "Result values")), RESULT_VALUES)
        self.assertEqual(self.first_column(self.section(self.doc, "Route values")), ROUTE_VALUES)

    def test_the_reason_code_table_equals_the_renderer_vocabulary_and_the_shared_28_codes(self):
        table = self.first_column(self.section(self.doc, "Reason codes"))
        self.assertEqual(len(table), len(set(table)), "a reason code is listed twice")
        self.assertEqual(len(REASON_CODES), 28)
        self.assertEqual(set(table), set(REASON_CODES))
        self.assertEqual(set(table), set(self.mod.REASON_CODES))
        self.assertEqual(len(self.mod.REASON_CODES), len(set(self.mod.REASON_CODES)))

    def test_every_reason_code_row_names_a_condition_and_an_emitter(self):
        for line in self.section(self.doc, "Reason codes").splitlines():
            if re.match(r"\| `[a-z_]+` \|", line):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                self.assertEqual(len(cells), 3, line)
                self.assertTrue(cells[1] and cells[2], line)

    def test_the_fallback_block_equals_the_renderer_fallback_and_is_a_conformant_internal_error(self):
        block = self.yaml_block(self.section(self.doc, "Fallback result"))
        self.assertEqual(block, self.mod.FALLBACK_RESULT)
        parsed = parse_result(self, block)
        self.assertEqual(parsed["merge_result"], "not_merged")
        self.assertEqual(parsed["reason"], "internal_error")
        self.assertIn(parsed["route"], ROUTE_VALUES)
        self.assertIn(parsed["worktree_removed"], ("true", "false"))
        self.assertTrue(parsed["detail"])

    def test_the_fallback_result_passes_through_the_renderer_unchanged_in_shape(self):
        parsed = parse_result(self, self.mod.FALLBACK_RESULT)
        data = {
            "result": parsed["merge_result"],
            "feature": parsed["feature"],
            "route": parsed["route"],
            "reason": parsed["reason"],
            "pr_url": parsed["pr_url"],
            "merge_commit": parsed["merge_commit"],
            "worktree_removed": parsed["worktree_removed"],
            "detail": parsed["detail"],
        }
        text, _ = self.render(data)
        self.assertEqual(text, self.mod.FALLBACK_RESULT)

    def test_the_document_cites_the_terminal_line_format_sections_instead_of_restating_them(self):
        self.assertIn("references/batch-terminal-line.md", self.doc)
        self.assertIn("`## Result format`", self.doc)
        self.assertIn("`## Escaping`", self.doc)
        self.assertNotIn("Source character", self.doc)
        self.assertNotIn("U+2028", self.doc)

    def test_the_document_cites_the_redaction_document(self):
        self.assertIn("references/doc-redaction.md", self.doc)

    def test_the_detail_cap_stated_in_the_document_equals_the_renderer_cap(self):
        match = re.search(r"at most (\d+) characters", self.section(self.doc, "Field values"))
        self.assertIsNotNone(match, "the Field values section states no detail cap")
        self.assertEqual(int(match.group(1)), self.mod.DETAIL_CAP)

    def test_the_document_names_no_home_path_and_no_notion_url(self):
        self.assertNotIn("/home/", self.doc)
        self.assertIsNone(re.search(r"https?://[^\s`]*notion\.", self.doc, re.I))

    def test_the_script_imports_only_what_the_output_layer_needs(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, {"json", "os", "re", "sys"})

    def test_the_script_starts_with_a_python3_shebang(self):
        first_line = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first_line, "#!/usr/bin/env python3")


if __name__ == "__main__":
    unittest.main()

"""destructive-guard allows exactly the canonical `gh pr merge` from an
integration worktree (unattended-merge task0007).

The exhaustive table lives in em-workflow/hooks/tests/destructive-guard-cases.json
and runs through run-destructive-guard.py. This module names the acceptance
criteria and pins one or more representatives of each, and checks the runner's
optional per-case working directory / CLAUDE_BATCH element on its own, against
a stub guard. The guard is exercised as the real hook is: a subprocess fed a
PreToolUse payload, with CLAUDE_BATCH set or cleared in its environment.

No test here writes a bytecode cache under em-workflow/.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "em-workflow", "hooks", "tests")
RUNNER = os.path.join(TESTS_DIR, "run-destructive-guard.py")
CASES_JSON = os.path.join(TESTS_DIR, "destructive-guard-cases.json")
GUARD = os.path.join(REPO_ROOT, "em-workflow", "hooks", "destructive-guard.py")
README = os.path.join(REPO_ROOT, "em-workflow", "README.md")
HOOK_TESTS_RULE = os.path.join(REPO_ROOT, ".claude", "rules", "hook-tests.md")

# The cases that existed before this task: their number and the digest of
# their JSON form. Every one of them must still be there, unchanged.
PRE_EXISTING_CASE_COUNT = 942
PRE_EXISTING_CASES_DIGEST = (
    "4f98f135c2f1f4cb7386cc424ba6037e3a36db288eee09cb75a642fe3d31f66d"
)

ROOT = "/tmp/merge-guard-fixture"
WORKTREES = ROOT + "/.claude/worktrees/em-workflow"
WORKTREE = WORKTREES + "/demo/integration"
SHA = "0123456789abcdef0123456789abcdef01234567"
CANON = "gh pr merge 42 --merge --match-head-commit " + SHA


def load_runner(argv):
    """The runner as a module, loaded as `python3 run-destructive-guard.py
    *ARGV[1:]` would see it, without leaving a bytecode cache behind."""
    spec = importlib.util.spec_from_file_location("run_destructive_guard_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "argv", argv), mock.patch.object(
        sys, "dont_write_bytecode", True
    ):
        spec.loader.exec_module(module)
    return module


RUNNER_MODULE = load_runner([RUNNER, GUARD])


def decision(command, cwd=WORKTREE, batch=False):
    """The guard's decision for COMMAND in the given situation."""
    return RUNNER_MODULE.verdict(command, batch=batch, cwd=cwd)[0]


def both_settings(test, command, cwd, ask_means):
    """COMMAND is asked about without CLAUDE_BATCH and denied with it."""
    test.assertEqual(decision(command, cwd), ask_means[0], msg=(command, cwd))
    test.assertEqual(decision(command, cwd, batch=True), ask_means[1], msg=(command, cwd))


ASK_THEN_DENY = ("ask", "deny")


class TestAC1CanonicalFormIsAllowed(unittest.TestCase):
    """AC-1: the canonical form from an integration worktree, with and
    without CLAUDE_BATCH."""

    def test_ac1_allowed_from_the_integration_worktree(self):
        self.assertEqual(decision(CANON, WORKTREE), "allow")
        self.assertEqual(decision(CANON, WORKTREE, batch=True), "allow")

    def test_ac1_allowed_from_a_subdirectory_of_the_worktree(self):
        sub = WORKTREE + "/em-workflow/hooks"
        self.assertEqual(decision(CANON, sub), "allow")
        self.assertEqual(decision(CANON, sub, batch=True), "allow")


class TestAC2OtherShapesKeepAsk(unittest.TestCase):
    """AC-2: every variant asks without CLAUDE_BATCH and is denied with it."""

    def test_ac2_one_extra_flag_or_token(self):
        for extra in (
            "--admin", "--auto", "--squash", "--rebase", "--delete-branch",
            "-s", "-r", "-d", "--repo x/y", "-R x/y", "--unknown-flag", "extra",
        ):
            with self.subTest(extra=extra):
                both_settings(self, CANON + " " + extra, WORKTREE, ASK_THEN_DENY)

    def test_ac2_equals_joined_option(self):
        both_settings(
            self, "gh pr merge 42 --merge --match-head-commit=" + SHA, WORKTREE, ASK_THEN_DENY
        )
        both_settings(self, CANON + " --repo=x/y", WORKTREE, ASK_THEN_DENY)

    def test_ac2_environment_assignment_prefix(self):
        both_settings(self, "GH_REPO=x/y " + CANON, WORKTREE, ASK_THEN_DENY)

    def test_ac2_sha_missing_short_long_or_not_hex(self):
        for what, tail in (
            ("missing", ""),
            ("39 characters", " " + SHA[:39]),
            ("41 characters", " " + SHA + "0"),
            ("non-hex", " " + SHA[:39] + "g"),
            ("uppercase", " " + SHA.upper()),
        ):
            with self.subTest(sha=what):
                command = "gh pr merge 42 --merge --match-head-commit" + tail
                both_settings(self, command, WORKTREE, ASK_THEN_DENY)

    def test_ac2_pr_number_missing_or_not_a_positive_number(self):
        for what, number in (
            ("missing", ""), ("word", " abc"), ("zero", " 0"), ("negative", " -42"),
            ("trailing letters", " 42abc"), ("variable", " $PR"),
        ):
            with self.subTest(pr=what):
                command = "gh pr merge%s --merge --match-head-commit %s" % (number, SHA)
                both_settings(self, command, WORKTREE, ASK_THEN_DENY)

    def test_ac2_main_tree_or_another_path(self):
        both_settings(self, CANON, ROOT, ASK_THEN_DENY)
        both_settings(self, CANON, "/tmp/elsewhere", ASK_THEN_DENY)
        both_settings(self, CANON, None, ASK_THEN_DENY)


class TestAC3LaterSegmentsAreStillJudged(unittest.TestCase):
    """AC-3: the canonical form followed by a dangerous segment gets that
    segment's own decision, never allow."""

    def test_ac3_force_push_after_the_merge_is_denied(self):
        for joiner in (" && ", " ; ", "\n"):
            with self.subTest(joiner=repr(joiner)):
                command = CANON + joiner + "git push --force origin main"
                self.assertEqual(decision(command), "deny")
                self.assertEqual(decision(command, batch=True), "deny")

    def test_ac3_recursive_delete_after_the_merge_is_denied(self):
        command = CANON + " ; rm -rf /home/user/valuable"
        self.assertEqual(decision(command), "deny")
        self.assertEqual(decision(command, batch=True), "deny")

    def test_ac3_an_ask_segment_after_the_merge_asks_and_is_denied_in_a_batch(self):
        command = CANON + " && systemctl stop example.service"
        self.assertEqual(decision(command), "ask")
        self.assertEqual(decision(command, batch=True), "deny")

    def test_ac3_a_second_non_canonical_merge_asks(self):
        command = CANON + " && gh pr merge 43 --admin"
        both_settings(self, command, WORKTREE, ASK_THEN_DENY)

    def test_ac3_a_harmless_segment_does_not_change_the_allow(self):
        self.assertEqual(decision(CANON + " && echo done"), "allow")

    def test_ac3_a_statement_that_changes_directory_or_environment_asks(self):
        for command in (
            "cd /tmp/elsewhere && " + CANON,
            "export GH_REPO=x/y && " + CANON,
            "GH_REPO=x/y ; " + CANON,
            "gh() { echo hi; } ; " + CANON,
            CANON + " ; cd /tmp/elsewhere",
        ):
            with self.subTest(command=command):
                both_settings(self, command, WORKTREE, ASK_THEN_DENY)


class TestAC4WorkingDirectoryShape(unittest.TestCase):
    """AC-4: working directories that do not have the integration shape ask
    (deny in a batch), however they are spelled."""

    def test_ac4_reaching_the_shape_only_through_parent_segments(self):
        for cwd in (
            WORKTREES + "/demo/other/../integration",
            WORKTREES + "/../em-workflow/demo/integration",
            ROOT + "/x/../.claude/worktrees/em-workflow/demo/integration",
        ):
            with self.subTest(cwd=cwd):
                both_settings(self, CANON, cwd, ASK_THEN_DENY)

    def test_ac4_leaving_the_shape_through_parent_segments(self):
        for cwd in (
            WORKTREE + "/..",
            WORKTREE + "/sub/../..",
            WORKTREE + "/../../other/integration",
        ):
            with self.subTest(cwd=cwd):
                both_settings(self, CANON, cwd, ASK_THEN_DENY)

    def test_ac4_a_climb_that_stays_inside_the_worktree_is_normalized(self):
        self.assertEqual(decision(CANON, WORKTREE + "/sub/.."), "allow")
        self.assertEqual(decision(CANON, WORKTREES + "/demo/./integration/."), "allow")

    def test_ac4_feature_segment_failing_the_pattern(self):
        for feature in ("Demo", "-demo", "demo_x", "demo.x", ""):
            with self.subTest(feature=feature):
                cwd = WORKTREES + "/" + feature + "/integration"
                both_settings(self, CANON, cwd, ASK_THEN_DENY)

    def test_ac4_segment_after_the_feature_is_not_exactly_integration(self):
        for tail in (
            "integration-x", "Integration", "integrations", "integration.old",
            "task0001", "sub/integration", "",
        ):
            with self.subTest(tail=tail):
                cwd = WORKTREES + "/demo/" + tail
                both_settings(self, CANON, cwd, ASK_THEN_DENY)

    def test_ac4_relative_or_empty_working_directory(self):
        both_settings(self, CANON, ".claude/worktrees/em-workflow/demo/integration", ASK_THEN_DENY)
        both_settings(self, CANON, "", ASK_THEN_DENY)


STUB_GUARD = textwrap.dedent(
    """\
    import json, os, sys
    payload = json.load(sys.stdin)
    seen = {"cwd": payload.get("cwd"), "batch": os.environ.get("CLAUDE_BATCH")}
    # allow only for cwd=/x/y with CLAUDE_BATCH set, or for neither
    ok = (seen["cwd"], seen["batch"]) in (("/x/y", "1"), (None, None))
    out = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow" if ok else "deny",
        "permissionDecisionReason": "stub " + json.dumps(seen),
    }}
    json.dump(out, sys.stdout)
    """
)


class TestAC5RunnerOptionalElement(unittest.TestCase):
    """AC-5: the runner honours the optional per-case element, and keeps
    the path-argument mode."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stub = os.path.join(self.tmp.name, "stub-guard.py")
        with open(self.stub, "w", encoding="utf-8") as f:
            f.write(STUB_GUARD)
        self.runner = load_runner([RUNNER, self.stub])

    def run_cases(self, cases):
        path = os.path.join(self.tmp.name, "cases.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cases, f)
        out = io.StringIO()
        with mock.patch.object(self.runner, "CASES", path), contextlib.redirect_stdout(out):
            code = self.runner.main()
        return code, out.getvalue()

    def test_ac5_verdict_sends_the_working_directory_and_batch_setting(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_BATCH", None)
            reason = self.runner.verdict("echo", batch=True, cwd="/x/y")[1]
            self.assertEqual(json.loads(reason[len("stub "):]), {"cwd": "/x/y", "batch": "1"})
            reason = self.runner.verdict("echo")[1]
            self.assertEqual(json.loads(reason[len("stub "):]), {"cwd": None, "batch": None})

    def test_ac5_a_three_element_case_sends_no_cwd_and_clears_batch(self):
        with mock.patch.dict(os.environ, {"CLAUDE_BATCH": "1"}):
            code, out = self.run_cases([["allow", "plain", "echo"]])
        self.assertEqual(code, 0, out)

    def test_ac5_a_fourth_element_sets_cwd_and_batch_for_that_case_only(self):
        cases = [
            ["allow", "plain", "echo"],
            ["allow", "cwd and batch", "echo", {"cwd": "/x/y", "batch": True}],
            ["deny", "cwd only", "echo", {"cwd": "/x/y"}],
            ["deny", "batch only", "echo", {"batch": True}],
            ["allow", "empty options", "echo", {}],
        ]
        code, out = self.run_cases(cases)
        self.assertEqual(code, 0, out)
        self.assertIn("6/6 passed", out)

    def test_ac5_a_mismatch_under_a_fourth_element_fails_the_run(self):
        code, out = self.run_cases([["allow", "wrong", "echo", {"cwd": "/x/y"}]])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)

    def test_ac5_a_malformed_fourth_element_ends_the_run(self):
        for case in (
            ["allow", "x", "echo", "not an object"],
            ["allow", "x", "echo", {"cwd": 5}],
            ["allow", "x", "echo", {"batch": "yes"}],
            ["allow", "x", "echo", {"unknown": 1}],
            ["allow", "x", "echo", {}, "fifth"],
        ):
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    self.run_cases([case])

    def test_ac5_path_argument_mode_checks_the_given_guard_copy(self):
        self.assertEqual(self.runner.GUARD, self.stub)
        self.assertIn("stub ", self.runner.verdict("echo")[1])
        default = load_runner([RUNNER])
        self.assertEqual(os.path.normpath(default.GUARD), os.path.normpath(GUARD))

    def test_ac5_no_bytecode_cache_was_written_next_to_the_runner(self):
        self.assertFalse(os.path.exists(os.path.join(TESTS_DIR, "__pycache__")))


class TestAC6ExistingCasesAndDocs(unittest.TestCase):
    """AC-6: every pre-existing case is still present and unchanged; the
    README row and the case-format rule describe the change."""

    def setUp(self):
        with open(CASES_JSON, encoding="utf-8") as f:
            self.cases = json.load(f)

    def test_ac6_every_pre_existing_case_is_present_and_unchanged(self):
        existing = self.cases[:PRE_EXISTING_CASE_COUNT]
        self.assertEqual(len(existing), PRE_EXISTING_CASE_COUNT)
        digest = hashlib.sha256(json.dumps(existing, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(digest.hexdigest(), PRE_EXISTING_CASES_DIGEST)
        self.assertTrue(all(len(case) == 3 for case in existing))

    def test_ac6_new_cases_cover_both_settings_and_use_the_optional_element(self):
        new = self.cases[PRE_EXISTING_CASE_COUNT:]
        self.assertTrue(new)
        carrying = [case for case in new if len(case) == 4]
        self.assertTrue(any(case[3].get("batch") for case in carrying))
        self.assertTrue(any("cwd" in case[3] for case in carrying))
        self.assertTrue(any(case[0] == "allow" for case in new))
        self.assertTrue(any(case[0] == "ask" for case in new))
        self.assertTrue(any(case[0] == "deny" for case in new))

    def test_ac6_the_new_cases_use_a_neutral_root_not_a_home_directory(self):
        for case in self.cases[PRE_EXISTING_CASE_COUNT:]:
            if len(case) == 4:
                self.assertNotRegex(case[3].get("cwd", ""), r"^/(home|Users)/")

    def test_ac6_readme_row_describes_the_limited_allow(self):
        with open(README, encoding="utf-8") as f:
            rows = [l for l in f if l.startswith("| `hooks/destructive-guard.py`")]
        self.assertEqual(len(rows), 1)
        self.assertIn("gh pr merge", rows[0])
        self.assertIn("integration worktree", rows[0])

    def test_ac6_case_format_rule_describes_the_optional_element(self):
        with open(HOOK_TESTS_RULE, encoding="utf-8") as f:
            text = f.read()
        self.assertRegex(text, r'"cwd"')
        self.assertRegex(text, r'"batch"')
        self.assertRegex(text, r"4 要素目")


if __name__ == "__main__":
    unittest.main()

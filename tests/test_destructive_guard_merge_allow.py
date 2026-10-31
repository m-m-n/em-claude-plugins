"""destructive-guard allows exactly the canonical `gh pr merge` from a
registered integration worktree (unattended-merge task0007 and task0012).

The exhaustive table lives in em-workflow/hooks/tests/destructive-guard-cases.json
and runs through run-destructive-guard.py. This module names the acceptance
criteria and pins one or more representatives of each, and checks the runner's
optional per-case working directory / CLAUDE_BATCH element and its
`{merge_fixture}` placeholder on their own, against a stub guard. The guard is
exercised as the real hook is: a subprocess fed a PreToolUse payload, with
CLAUDE_BATCH set or cleared in its environment.

The working directories the guard is judged in are real: every test class
builds, in a temporary directory, a git repository whose integration
worktrees are registered with `git worktree add`, plus plain directories of
the same shape that are not registered (task0012). The exception itself lives
in em-workflow/hooks/merge_pr_allow.py (task0012 AC-1).

No test here writes a bytecode cache under em-workflow/.
"""

import ast
import contextlib
import glob
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "em-workflow", "hooks")
TESTS_DIR = os.path.join(HOOKS_DIR, "tests")
RUNNER = os.path.join(TESTS_DIR, "run-destructive-guard.py")
CASES_JSON = os.path.join(TESTS_DIR, "destructive-guard-cases.json")
GUARD = os.path.join(HOOKS_DIR, "destructive-guard.py")
MODULE = os.path.join(HOOKS_DIR, "merge_pr_allow.py")
README = os.path.join(REPO_ROOT, "em-workflow", "README.md")
HOOK_TESTS_RULE = os.path.join(REPO_ROOT, ".claude", "rules", "hook-tests.md")

# The cases that existed before task0007: their number and the digest of
# their JSON form. Every one of them must still be there, unchanged.
PRE_EXISTING_CASE_COUNT = 942
PRE_EXISTING_CASES_DIGEST = (
    "4f98f135c2f1f4cb7386cc424ba6037e3a36db288eee09cb75a642fe3d31f66d"
)

PLACEHOLDER = "{merge_fixture}"
SHA = "0123456789abcdef0123456789abcdef01234567"
CANON = "gh pr merge 42 --merge --match-head-commit " + SHA
ASK_THEN_DENY = ("ask", "deny")

# Used as the `cwd` argument of FixtureCase.decision() when the test wants the
# class's registered integration worktree.
WORKTREE_DEFAULT = object()


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


def load_merge_module(path=MODULE):
    """The merge_pr_allow module, loaded without leaving a bytecode cache."""
    spec = importlib.util.spec_from_file_location("merge_pr_allow_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "dont_write_bytecode", True):
        spec.loader.exec_module(module)
    return module


RUNNER_MODULE = load_runner([RUNNER, GUARD])


# --- real worktree fixtures ---------------------------------------------------


def git_env(home):
    """A scrubbed environment: the developer's global git configuration, hooks
    and repository variables cannot change the result."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": home,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }


def run_git(repo, home, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=fixture",
            "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false",
            "-c", "core.hooksPath=" + os.devnull,
            *args,
        ],
        cwd=repo,
        env=git_env(home),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


class Fixture:
    """A temporary repository with one commit. Each feature in REGISTERED has
    an integration worktree added with `git worktree add` on the branch
    `em-workflow/<feature>/integration`; each in PLAIN has a plain directory of
    the same shape that is not a worktree. WRONG_BRANCH features have a
    registered worktree at the integration path on some other branch."""

    def __init__(self, registered=("demo",), plain=("unregistered",), wrong_branch=()):
        self.tmp = tempfile.TemporaryDirectory()
        base = os.path.realpath(self.tmp.name)
        home = self.home = os.path.join(base, "home")
        os.makedirs(home)
        self.root = os.path.join(base, "repo")
        os.makedirs(self.root)
        run_git(self.root, home, "init", "-q")
        run_git(self.root, home, "commit", "-q", "--allow-empty", "-m", "fixture")
        self.worktrees = self.root + "/.claude/worktrees/em-workflow"
        for feature in registered:
            run_git(
                self.root, home, "worktree", "add", "-q",
                "-b", "em-workflow/%s/integration" % feature,
                ".claude/worktrees/em-workflow/%s/integration" % feature,
            )
        for feature in wrong_branch:
            run_git(
                self.root, home, "worktree", "add", "-q",
                "-b", "some-other-branch-%s" % feature,
                ".claude/worktrees/em-workflow/%s/integration" % feature,
            )
        for feature in plain:
            os.makedirs(self.worktrees + "/%s/integration" % feature)

    def cleanup(self):
        self.tmp.cleanup()


class FixtureCase(unittest.TestCase):
    """A test class that judges the guard against its own fixture."""

    REGISTERED = ("demo",)
    PLAIN = ("unregistered",)
    WRONG_BRANCH = ()

    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture(cls.REGISTERED, cls.PLAIN, cls.WRONG_BRANCH)
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.ROOT = cls.fixture.root
        cls.WORKTREES = cls.fixture.worktrees
        cls.WORKTREE = cls.WORKTREES + "/demo/integration"

    def decision(self, command, cwd=WORKTREE_DEFAULT, batch=False):
        """The guard's decision for COMMAND in the given situation."""
        if cwd is WORKTREE_DEFAULT:
            cwd = self.WORKTREE
        return RUNNER_MODULE.verdict(command, batch=batch, cwd=cwd)[0]

    def both_settings(self, command, cwd, ask_means=ASK_THEN_DENY):
        """COMMAND is asked about without CLAUDE_BATCH and denied with it."""
        self.assertEqual(self.decision(command, cwd), ask_means[0], msg=(command, cwd))
        self.assertEqual(
            self.decision(command, cwd, batch=True), ask_means[1], msg=(command, cwd)
        )


class TestAC1CanonicalFormIsAllowed(FixtureCase):
    """AC-1: the canonical form from an integration worktree, with and
    without CLAUDE_BATCH."""

    REGISTERED = ("demo", "2fa-login-v2")

    def test_ac1_allowed_from_the_integration_worktree(self):
        self.assertEqual(self.decision(CANON, self.WORKTREE), "allow")
        self.assertEqual(self.decision(CANON, self.WORKTREE, batch=True), "allow")

    def test_ac1_allowed_from_a_subdirectory_of_the_worktree(self):
        sub = self.WORKTREE + "/em-workflow/hooks"
        self.assertEqual(self.decision(CANON, sub), "allow")
        self.assertEqual(self.decision(CANON, sub, batch=True), "allow")

    def test_ac1_a_feature_name_with_digits_and_hyphens_is_allowed(self):
        cwd = self.WORKTREES + "/2fa-login-v2/integration"
        self.assertEqual(self.decision(CANON, cwd), "allow")


class TestAC2OtherShapesKeepAsk(FixtureCase):
    """AC-2: every variant asks without CLAUDE_BATCH and is denied with it."""

    def test_ac2_one_extra_flag_or_token(self):
        for extra in (
            "--admin", "--auto", "--squash", "--rebase", "--delete-branch",
            "-s", "-r", "-d", "--repo x/y", "-R x/y", "--unknown-flag", "extra",
        ):
            with self.subTest(extra=extra):
                self.both_settings(CANON + " " + extra, self.WORKTREE)

    def test_ac2_equals_joined_option(self):
        self.both_settings(
            "gh pr merge 42 --merge --match-head-commit=" + SHA, self.WORKTREE
        )
        self.both_settings(CANON + " --repo=x/y", self.WORKTREE)

    def test_ac2_environment_assignment_prefix(self):
        self.both_settings("GH_REPO=x/y " + CANON, self.WORKTREE)

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
                self.both_settings(command, self.WORKTREE)

    def test_ac2_pr_number_missing_or_not_a_positive_number(self):
        for what, number in (
            ("missing", ""), ("word", " abc"), ("zero", " 0"), ("negative", " -42"),
            ("trailing letters", " 42abc"), ("variable", " $PR"),
        ):
            with self.subTest(pr=what):
                command = "gh pr merge%s --merge --match-head-commit %s" % (number, SHA)
                self.both_settings(command, self.WORKTREE)

    def test_ac2_main_tree_or_another_path(self):
        self.both_settings(CANON, self.ROOT)
        self.both_settings(CANON, "/tmp/elsewhere")
        self.both_settings(CANON, None)


class TestAC3LaterSegmentsAreStillJudged(FixtureCase):
    """AC-3: the canonical form followed by a dangerous segment gets that
    segment's own decision, never allow."""

    def test_ac3_force_push_after_the_merge_is_denied(self):
        for joiner in (" && ", " ; ", "\n"):
            with self.subTest(joiner=repr(joiner)):
                command = CANON + joiner + "git push --force origin main"
                self.assertEqual(self.decision(command), "deny")
                self.assertEqual(self.decision(command, batch=True), "deny")

    def test_ac3_recursive_delete_after_the_merge_is_denied(self):
        command = CANON + " ; rm -rf /home/user/valuable"
        self.assertEqual(self.decision(command), "deny")
        self.assertEqual(self.decision(command, batch=True), "deny")

    def test_ac3_an_ask_segment_after_the_merge_asks_and_is_denied_in_a_batch(self):
        command = CANON + " && systemctl stop example.service"
        self.assertEqual(self.decision(command), "ask")
        self.assertEqual(self.decision(command, batch=True), "deny")

    def test_ac3_a_second_non_canonical_merge_asks(self):
        command = CANON + " && gh pr merge 43 --admin"
        self.both_settings(command, self.WORKTREE)

    def test_ac3_a_harmless_segment_makes_the_merge_ask(self):
        # The canonical merge is allowed only as the whole command (task0012).
        self.both_settings(CANON + " && echo done", self.WORKTREE)

    def test_ac3_a_statement_that_changes_directory_or_environment_asks(self):
        for command in (
            "cd /tmp/elsewhere && " + CANON,
            "export GH_REPO=x/y && " + CANON,
            "GH_REPO=x/y ; " + CANON,
            "gh() { echo hi; } ; " + CANON,
            CANON + " ; cd /tmp/elsewhere",
        ):
            with self.subTest(command=command):
                self.both_settings(command, self.WORKTREE)


class TestAC4WorkingDirectoryShape(FixtureCase):
    """AC-4: working directories that do not have the integration shape ask
    (deny in a batch), however they are spelled. The feature names that fail
    the pattern are registered worktrees here, so the shape is the only thing
    that can turn them down."""

    REGISTERED = ("demo", "Demo", "demo_x", "demo.x", "-demo")

    def test_ac4_reaching_the_shape_only_through_parent_segments(self):
        for cwd in (
            self.WORKTREES + "/demo/other/../integration",
            self.WORKTREES + "/../em-workflow/demo/integration",
            self.ROOT + "/x/../.claude/worktrees/em-workflow/demo/integration",
        ):
            with self.subTest(cwd=cwd):
                self.both_settings(CANON, cwd)

    def test_ac4_leaving_the_shape_through_parent_segments(self):
        for cwd in (
            self.WORKTREE + "/..",
            self.WORKTREE + "/sub/../..",
            self.WORKTREE + "/../../other/integration",
        ):
            with self.subTest(cwd=cwd):
                self.both_settings(CANON, cwd)

    def test_ac4_a_climb_that_stays_inside_the_worktree_is_normalized(self):
        self.assertEqual(self.decision(CANON, self.WORKTREE + "/sub/.."), "allow")
        self.assertEqual(
            self.decision(CANON, self.WORKTREES + "/demo/./integration/."), "allow"
        )

    def test_ac4_feature_segment_failing_the_pattern(self):
        for feature in ("Demo", "-demo", "demo_x", "demo.x", ""):
            with self.subTest(feature=feature):
                cwd = self.WORKTREES + "/" + feature + "/integration"
                self.both_settings(CANON, cwd)

    def test_ac4_segment_after_the_feature_is_not_exactly_integration(self):
        for tail in (
            "integration-x", "Integration", "integrations", "integration.old",
            "task0001", "sub/integration", "",
        ):
            with self.subTest(tail=tail):
                cwd = self.WORKTREES + "/demo/" + tail
                self.both_settings(CANON, cwd)

    def test_ac4_relative_or_empty_working_directory(self):
        self.both_settings(CANON, ".claude/worktrees/em-workflow/demo/integration")
        self.both_settings(CANON, "")


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


# --- task0012 -------------------------------------------------------------------


def merge_cases(cases):
    """The cases that judge a `gh pr merge` command."""
    return [case for case in cases if "gh pr merge" in case[2]]


class TestTask0012AC1ModuleSeparation(unittest.TestCase):
    """task0012 AC-1: the unattended-merge parts live in merge_pr_allow.py;
    destructive-guard.py keeps only a generic call into it."""

    FORBIDDEN_DEFINITIONS = (
        "is_canonical_merge",
        "is_integration_worktree_cwd",
        "_is_registered_integration_worktree",
    )

    def setUp(self):
        with open(GUARD, encoding="utf-8") as f:
            self.guard_source = f.read()

    def test_ac1_the_guard_holds_no_merge_specific_string(self):
        for text in ("--match-head-commit", "refs/heads/em-workflow/"):
            with self.subTest(text=text):
                self.assertNotIn(text, self.guard_source)

    def test_ac1_the_guard_defines_none_of_the_moved_functions(self):
        defined = {
            node.name
            for node in ast.walk(ast.parse(self.guard_source))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in self.FORBIDDEN_DEFINITIONS:
            with self.subTest(name=name):
                self.assertNotIn(name, defined)
                self.assertNotIn("def " + name, self.guard_source)

    def test_ac1_the_guard_consults_the_module(self):
        self.assertIn("merge_pr_allow", self.guard_source)

    def test_ac1_the_module_holds_the_canonical_form_and_the_registration_check(self):
        self.assertTrue(os.path.isfile(MODULE), MODULE)
        with open(MODULE, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("--match-head-commit", source)
        self.assertIn("refs/heads/em-workflow/", source)
        defined = {
            node.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef)
        }
        for name in self.FORBIDDEN_DEFINITIONS:
            with self.subTest(name=name):
                self.assertIn(name, defined)

    def test_ac1_the_module_is_not_registered_as_a_hook(self):
        with open(os.path.join(HOOKS_DIR, "hooks.json"), encoding="utf-8") as f:
            self.assertNotIn("merge_pr_allow", f.read())


class TestTask0012ModuleInterface(FixtureCase):
    """The module on its own: what the guard hands it and what it decides."""

    PLAIN = ("unregistered",)
    WRONG_BRANCH = ("wrongbranch",)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_merge_module()

    CANON_TOKENS = ["gh", "pr", "merge", "42", "--merge", "--match-head-commit", SHA]

    def test_the_canonical_seven_tokens_are_recognised(self):
        self.assertTrue(self.module.is_canonical_merge(list(self.CANON_TOKENS), True))

    def test_a_statement_that_did_not_lex_is_not_matched(self):
        self.assertFalse(self.module.is_canonical_merge(list(self.CANON_TOKENS), False))

    def test_any_other_token_list_is_not_matched(self):
        for toks in (
            self.CANON_TOKENS + ["--admin"],
            self.CANON_TOKENS[:-1],
            ["GH_REPO=x/y"] + self.CANON_TOKENS,
            self.CANON_TOKENS[:3] + ["0"] + self.CANON_TOKENS[4:],
            self.CANON_TOKENS[:-1] + [SHA.upper()],
        ):
            with self.subTest(toks=toks):
                self.assertFalse(self.module.is_canonical_merge(list(toks), True))

    def test_a_token_with_a_lexing_flag_is_not_matched(self):
        class Flagged(str):
            pass

        for flag, value in (
            ("is_operator", True),
            ("unresolved", True),
            ("substitution_only", True),
            ("trailing_cr", "\r"),
        ):
            with self.subTest(flag=flag):
                toks = list(self.CANON_TOKENS)
                flagged = Flagged(toks[3])
                setattr(flagged, flag, value)
                toks[3] = flagged
                self.assertFalse(self.module.is_canonical_merge(toks, True))

    def test_a_statement_is_allowed_only_in_a_registered_worktree(self):
        allows = self.module.allows_statement
        toks = list(self.CANON_TOKENS)
        self.assertTrue(allows(toks, True, self.WORKTREE))
        self.assertTrue(allows(toks, True, self.WORKTREE + "/em-workflow/hooks"))
        self.assertFalse(allows(toks, True, self.WORKTREES + "/unregistered/integration"))
        self.assertFalse(allows(toks, True, self.WORKTREES + "/wrongbranch/integration"))
        self.assertFalse(allows(toks, True, self.ROOT))
        self.assertFalse(allows(toks, True, ""))
        self.assertFalse(allows(toks, True, None))
        self.assertFalse(allows(toks + ["x"], True, self.WORKTREE))

    def test_the_exception_is_kept_only_for_a_sole_statement(self):
        keeps = self.module.keeps_exception
        self.assertTrue(keeps(1, False))
        self.assertFalse(keeps(2, False))
        self.assertFalse(keeps(3, False))
        self.assertFalse(keeps(1, True))
        self.assertFalse(keeps(2, True))


class TestTask0012AC2RunnerFixture(unittest.TestCase):
    """task0012 AC-2: the runner builds a registered integration worktree once
    per run and substitutes it for `{merge_fixture}` in case working
    directories; the merge cases use it and pass."""

    # Records what the guard saw: the working directory, and the state of the
    # directory it names, in the file named by STUB_LOG.
    RECORDING_GUARD = textwrap.dedent(
        """\
        import json, os, sys
        payload = json.load(sys.stdin)
        cwd = payload.get("cwd")
        info = {"cwd": cwd, "command": payload["tool_input"]["command"]}
        if cwd:
            git_file = os.path.join(cwd, ".git")
            info["isdir"] = os.path.isdir(cwd)
            info["git_is_file"] = os.path.isfile(git_file)
            if info["git_is_file"]:
                with open(git_file, encoding="utf-8") as f:
                    gitdir = f.read().split(":", 1)[1].strip()
                with open(os.path.join(gitdir, "HEAD"), encoding="utf-8") as f:
                    info["head"] = f.read().strip()
                info["gitdir_parent"] = os.path.basename(os.path.dirname(gitdir))
        with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as log:
            log.write(json.dumps(info) + "\\n")
        # The runner's closing check sends a command it expects to be denied.
        denied = payload["tool_input"]["command"].startswith("echo x >")
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if denied else "allow",
            "permissionDecisionReason": "recorded",
        }}, sys.stdout)
        """
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guard = os.path.join(self.tmp.name, "recording-guard.py")
        with open(self.guard, "w", encoding="utf-8") as f:
            f.write(self.RECORDING_GUARD)
        self.log = os.path.join(self.tmp.name, "log.jsonl")
        self.runner = load_runner([RUNNER, self.guard])
        with open(CASES_JSON, encoding="utf-8") as f:
            self.cases = json.load(f)

    def run_recording(self, cases):
        path = os.path.join(self.tmp.name, "cases.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cases, f)
        out = io.StringIO()
        with mock.patch.object(self.runner, "CASES", path), mock.patch.dict(
            os.environ, {"STUB_LOG": self.log}
        ), contextlib.redirect_stdout(out):
            code = self.runner.main()
        with open(self.log, encoding="utf-8") as f:
            return code, out.getvalue(), [json.loads(line) for line in f]

    def test_ac2_the_placeholder_is_replaced_by_a_registered_worktree_made_once(self):
        worktree = PLACEHOLDER + "/.claude/worktrees/em-workflow/demo/integration"
        cases = [
            ["allow", "root", "echo a", {"cwd": worktree}],
            ["allow", "sub", "echo b", {"cwd": worktree + "/em-workflow/hooks", "batch": True}],
            ["allow", "unregistered", "echo c", {
                "cwd": PLACEHOLDER + "/.claude/worktrees/em-workflow/unregistered/integration"}],
            ["allow", "main tree", "echo d", {"cwd": PLACEHOLDER}],
            ["allow", "elsewhere", "echo e", {"cwd": "/tmp/elsewhere"}],
            ["allow", "no cwd", "echo f"],
        ]
        code, out, seen = self.run_recording(cases)
        self.assertEqual(code, 0, out)
        by_command = {info["command"]: info for info in seen}

        root_case = by_command["echo a"]
        self.assertNotIn(PLACEHOLDER, root_case["cwd"])
        self.assertTrue(root_case["git_is_file"], root_case)
        self.assertEqual(root_case["head"], "ref: refs/heads/em-workflow/demo/integration")
        self.assertEqual(root_case["gitdir_parent"], "worktrees")
        root = root_case["cwd"].split("/.claude/worktrees/")[0]
        self.assertEqual(by_command["echo b"]["cwd"], root_case["cwd"] + "/em-workflow/hooks")
        self.assertEqual(
            by_command["echo c"]["cwd"],
            root + "/.claude/worktrees/em-workflow/unregistered/integration",
        )
        self.assertTrue(by_command["echo c"]["isdir"])
        self.assertFalse(by_command["echo c"]["git_is_file"])
        self.assertEqual(by_command["echo d"]["cwd"], root)
        # Other values go through unchanged, and need not exist.
        self.assertEqual(by_command["echo e"]["cwd"], "/tmp/elsewhere")
        self.assertIsNone(by_command["echo f"]["cwd"])
        # The temporary repository is gone when the run ends.
        self.assertFalse(os.path.exists(root))

    def test_ac2_two_runs_do_not_share_a_fixture(self):
        cases = [["allow", "root", "echo a", {"cwd": PLACEHOLDER}]]
        roots = []
        for _ in range(2):
            if os.path.exists(self.log):
                os.remove(self.log)
            _, _, seen = self.run_recording(cases)
            roots.append(seen[0]["cwd"])
        self.assertNotEqual(roots[0], roots[1])

    def test_ac2_a_run_without_the_placeholder_builds_no_fixture(self):
        with mock.patch.object(self.runner.subprocess, "run", wraps=subprocess.run) as run:
            code, out, seen = self.run_recording([["allow", "plain", "echo a"]])
        self.assertEqual(code, 0, out)
        git_calls = [c for c in run.call_args_list if c.args and c.args[0][:1] == ["git"]]
        self.assertEqual(git_calls, [])

    def test_ac2_every_integration_path_working_directory_uses_the_placeholder(self):
        for case in merge_cases(self.cases):
            if len(case) != 4 or "cwd" not in case[3]:
                continue
            cwd = case[3]["cwd"]
            with self.subTest(label=case[1]):
                self.assertNotIn("merge-guard-fixture", cwd)
                if cwd.startswith("/") and "/.claude/worktrees/" in cwd:
                    self.fail("a machine-specific integration path: %r" % cwd)

    def test_ac2_the_allow_cases_use_the_placeholder_for_root_and_subdirectory(self):
        allow = [
            case for case in merge_cases(self.cases[PRE_EXISTING_CASE_COUNT:])
            if case[0] == "allow"
        ]
        root = PLACEHOLDER + "/.claude/worktrees/em-workflow/demo/integration"
        for cwd_matches, what in (
            (lambda cwd: cwd == root, "the worktree root"),
            (lambda cwd: cwd.startswith(root + "/") and ".." not in cwd, "a subdirectory"),
        ):
            for batch in (False, True):
                with self.subTest(where=what, batch=batch):
                    self.assertTrue(
                        any(
                            cwd_matches(case[3].get("cwd", ""))
                            and bool(case[3].get("batch", False)) == batch
                            for case in allow
                            if len(case) == 4
                        )
                    )

    def test_ac2_the_allow_cases_pass_through_the_runner_against_the_real_guard(self):
        allow = [
            case for case in merge_cases(self.cases[PRE_EXISTING_CASE_COUNT:])
            if case[0] == "allow"
        ]
        self.assertTrue(allow)
        path = os.path.join(self.tmp.name, "allow-cases.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(allow, f)
        out = io.StringIO()
        with mock.patch.object(RUNNER_MODULE, "CASES", path), contextlib.redirect_stdout(out):
            code = RUNNER_MODULE.main()
        self.assertEqual(code, 0, out.getvalue())
        self.assertNotIn("FAIL", out.getvalue())


class TestTask0012AC3UnregisteredDirectory(FixtureCase):
    """task0012 AC-3: a directory of the integration shape that is not a
    registered integration worktree gets no exception."""

    PLAIN = ("unregistered",)
    WRONG_BRANCH = ("wrongbranch",)

    def test_ac3_a_plain_directory_of_the_same_shape_asks(self):
        cwd = self.WORKTREES + "/unregistered/integration"
        self.assertTrue(os.path.isdir(cwd))
        self.both_settings(CANON, cwd)
        self.both_settings(CANON, cwd + "/sub")

    def test_ac3_a_worktree_on_another_branch_asks(self):
        cwd = self.WORKTREES + "/wrongbranch/integration"
        self.assertTrue(os.path.isfile(cwd + "/.git"))
        self.both_settings(CANON, cwd)

    def test_ac3_a_directory_that_does_not_exist_asks(self):
        self.both_settings(CANON, self.WORKTREES + "/missing/integration")

    def test_ac3_a_nested_repository_below_the_worktree_asks(self):
        nested = self.WORKTREE + "/nested-repo"
        os.makedirs(nested)
        run_git(nested, self.fixture.home, "init", "-q")
        self.both_settings(CANON, nested)
        self.both_settings(CANON, nested + "/sub")

    def test_ac3_a_symlinked_directory_below_the_worktree_asks(self):
        link = self.WORKTREE + "/linked"
        os.symlink("/tmp", link)
        self.both_settings(CANON, link)

    def test_ac3_the_registered_worktree_still_allows(self):
        self.assertEqual(self.decision(CANON, self.WORKTREE), "allow")
        self.assertEqual(self.decision(CANON, self.WORKTREE, batch=True), "allow")


class TestTask0012AC4SoleStatement(FixtureCase):
    """task0012 AC-4: the canonical merge is allowed only as the whole
    command; a dangerous statement beside it still decides."""

    def test_ac4_a_harmless_statement_after_the_merge_asks(self):
        for joiner in (" && ", " ; ", "\n", " || "):
            with self.subTest(joiner=repr(joiner)):
                self.both_settings(CANON + joiner + "echo done", self.WORKTREE)

    def test_ac4_a_harmless_statement_before_the_merge_asks(self):
        for joiner in (" && ", " ; ", "\n"):
            with self.subTest(joiner=repr(joiner)):
                self.both_settings("echo start" + joiner + CANON, self.WORKTREE)

    def test_ac4_a_force_push_after_the_merge_gets_its_own_decision(self):
        command = CANON + " && git push --force origin main"
        self.assertEqual(self.decision(command), "deny")
        self.assertEqual(self.decision(command, batch=True), "deny")

    def test_ac4_a_recursive_delete_after_the_merge_gets_its_own_decision(self):
        command = CANON + " ; rm -rf /home/user/valuable"
        self.assertEqual(self.decision(command), "deny")
        self.assertEqual(self.decision(command, batch=True), "deny")

    def test_ac4_the_merge_alone_is_still_allowed(self):
        self.assertEqual(self.decision(CANON), "allow")
        self.assertEqual(self.decision(CANON, batch=True), "allow")


class TestTask0012AC5ModuleLoadFailure(FixtureCase):
    """task0012 AC-5: a missing or broken merge_pr_allow.py never allows the
    merge and never crashes the hook; every other verdict is unchanged."""

    VARIANTS = {
        "removed": None,
        "raises on import": "raise RuntimeError('broken module')\n",
        "exits on import": "import sys\nsys.exit(3)\n",
        "syntax error": "def broken(:\n",
        "without the interface": "VALUE = 1\n",
    }

    # (expected decision, command) of cases that do not involve the exception.
    SAMPLES = (
        ("allow", "echo hello"),
        ("allow", "ls -la"),
        ("ask", "systemctl stop example.service"),
        ("ask", "gh pr merge 42 --admin"),
        ("deny", "git push --force origin main"),
        ("deny", "rm -rf /home/user/valuable"),
    )

    def hooks_copy(self, module_text, keep_real_module=False):
        """A temporary copy of the hooks directory's guard, with the module
        removed (MODULE_TEXT None), replaced, or the real one copied."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        hooks = os.path.join(tmp.name, "hooks")
        os.makedirs(hooks)
        shutil.copy(GUARD, hooks)
        target = os.path.join(hooks, "merge_pr_allow.py")
        if keep_real_module:
            shutil.copy(MODULE, target)
        elif module_text is not None:
            with open(target, "w", encoding="utf-8") as f:
                f.write(module_text)
        return hooks

    def runner_for(self, hooks):
        return load_runner([RUNNER, os.path.join(hooks, "destructive-guard.py")])

    def test_ac5_the_intact_copy_allows_the_merge(self):
        runner = self.runner_for(self.hooks_copy(None, keep_real_module=True))
        self.assertEqual(runner.verdict(CANON, cwd=self.WORKTREE)[0], "allow")

    def test_ac5_the_merge_asks_and_is_denied_in_a_batch(self):
        for name, text in self.VARIANTS.items():
            with self.subTest(variant=name):
                runner = self.runner_for(self.hooks_copy(text))
                self.assertEqual(runner.verdict(CANON, cwd=self.WORKTREE)[0], "ask")
                self.assertEqual(
                    runner.verdict(CANON, batch=True, cwd=self.WORKTREE)[0], "deny"
                )

    def test_ac5_other_verdicts_are_unchanged(self):
        for name, text in self.VARIANTS.items():
            runner = self.runner_for(self.hooks_copy(text))
            for want, command in self.SAMPLES:
                with self.subTest(variant=name, command=command):
                    self.assertEqual(runner.verdict(command, cwd=self.WORKTREE)[0], want)

    def test_ac5_a_copy_uses_its_own_sibling_module(self):
        # A copy whose module raises is judged without the exception even
        # though the repository's own module next to the original works.
        runner = self.runner_for(self.hooks_copy("raise RuntimeError('own')\n"))
        self.assertEqual(runner.verdict(CANON, cwd=self.WORKTREE)[0], "ask")
        self.assertEqual(self.decision(CANON), "allow")


class TestTask0012AC6NoBytecodeCache(FixtureCase):
    """task0012 AC-6: loading the module leaves no bytecode cache behind."""

    def test_ac6_the_hook_loads_the_module_without_writing_a_cache(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        hooks = os.path.join(tmp.name, "hooks")
        os.makedirs(hooks)
        shutil.copy(GUARD, hooks)
        shutil.copy(MODULE, hooks)
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "CLAUDE_BATCH")
        }
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": CANON},
            "cwd": self.WORKTREE,
        }
        proc = subprocess.run(
            [sys.executable, os.path.join(hooks, "destructive-guard.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        decision = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "allow")
        self.assertEqual(
            glob.glob(os.path.join(hooks, "**", "__pycache__"), recursive=True), []
        )

    def test_ac6_no_cache_of_the_module_exists_in_the_repository(self):
        self.assertEqual(
            glob.glob(
                os.path.join(HOOKS_DIR, "**", "__pycache__", "merge_pr_allow*"),
                recursive=True,
            ),
            [],
        )
        self.assertFalse(os.path.exists(os.path.join(TESTS_DIR, "__pycache__")))


class TestTask0012AC7Docs(unittest.TestCase):
    """task0012 AC-7: the case-format rule names the placeholder and the
    fixture the runner builds."""

    def test_ac7_the_rule_describes_the_placeholder_and_the_fixture(self):
        with open(HOOK_TESTS_RULE, encoding="utf-8") as f:
            text = f.read()
        self.assertIn(PLACEHOLDER, text)
        self.assertIn("worktree", text)
        self.assertIn("em-workflow/demo/integration", text)
        self.assertIn("unregistered", text)

    def test_ac7_the_runner_documents_the_placeholder(self):
        with open(RUNNER, encoding="utf-8") as f:
            self.assertIn(PLACEHOLDER, f.read())


if __name__ == "__main__":
    unittest.main()

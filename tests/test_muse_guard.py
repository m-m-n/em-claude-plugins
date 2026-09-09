"""Behavioral tests for `muse_guard.py`
(feature-docs/muse-spark-contributor-consent/tasks/task0001.md).

Every case in this module is parameterized over BOTH plugin copies
(em-workflow/hooks/muse_guard.py, em-review/hooks/muse_guard.py) via
`subTest` -- a case that passes for one copy and not the other is the
failure mode this feature most needs to catch (task0001.md Test Notes).

Hook-mode cases are driven as a subprocess with the PreToolUse JSON payload
on stdin, the same contract Claude Code uses (test/README.md); CLI-mode
cases are driven as a subprocess with the documented flags. Every case
points the consent-store override ($EM_WORKFLOW_MUSE_CONSENT) at a path
under a per-test temporary directory -- no case reads or writes real
`~/.claude` state.

Standard library only, per test/README.md.
"""

import ast
import contextlib
import io
import json
import os
import pty
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent

GUARD_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / "hooks" / "muse_guard.py",
    "em-review": REPO_ROOT / "em-review" / "hooks" / "muse_guard.py",
}

CONTRIBUTOR_TIER = "muse-spark-contributor"
PLAIN_TIER = "muse-spark"

# Every quoting spelling the harness (codex CLI) emits for each shape in the
# model-selection flag table (task0006.md Design, "Stage 4"): the short flag
# with the value as a separate word, the long flag joined by `=` (both
# already recognized before task0006), plus the newly recognized shapes --
# the long flag with a separate value, the short flag joined by `=`, and the
# short flag with the value attached directly -- each in bare /
# single-quoted / double-quoted forms.
INVOCATION_COMMAND_TEMPLATES = {
    "short-bare": 'codex exec -m {tier} "review this"',
    "short-single-quoted": "codex exec -m '{tier}' \"review this\"",
    "short-double-quoted": 'codex exec -m "{tier}" "review this"',
    "long-bare": 'codex exec --model={tier} "review this"',
    "long-single-quoted": "codex exec --model='{tier}' \"review this\"",
    "long-double-quoted": 'codex exec --model="{tier}" "review this"',
    "short-equals-bare": 'codex exec -m={tier} "review this"',
    "short-equals-single-quoted": "codex exec -m='{tier}' \"review this\"",
    "short-equals-double-quoted": 'codex exec -m="{tier}" "review this"',
    "long-separate-bare": 'codex exec --model {tier} "review this"',
    "long-separate-single-quoted": "codex exec --model '{tier}' \"review this\"",
    "long-separate-double-quoted": 'codex exec --model "{tier}" "review this"',
    "short-attached-bare": 'codex exec -m{tier} "review this"',
    "short-attached-single-quoted": "codex exec -m'{tier}' \"review this\"",
    "short-attached-double-quoted": 'codex exec -m"{tier}" "review this"',
}


# The widening this task adds (IMPLEMENTATION.md D-H): a shape that must
# still deny once statement-splitting honours quoting, paired with its
# no-misfire counterpart carrying only a mention (task0007.md Test Notes --
# "two paired tables so a future shape is one row on each side").
WIDENED_DENY_SHAPES = {
    "quoted-prompt-contains-a-semicolon": 'codex exec -m {tier} "before;after"',
    "quoted-prompt-contains-a-newline": 'codex exec -m {tier} "before\nafter"',
    "quoted-value-and-quoted-prompt-both-carry-a-quote-delimiter": (
        "codex exec -m '{tier}' \"it's here; and more\""
    ),
    "shell-bundled-short-options-ending-in-the-command-string-flag": (
        "bash -xc 'codex exec -m {tier}'"
    ),
    "argument-list-expanding-wrapper-with-a-separate-value-option": (
        "xargs -n 1 codex exec -m {tier}"
    ),
    "scheduling-priority-wrapper-with-a-separate-value-option": (
        "nice -n 10 codex exec -m {tier}"
    ),
}

WIDENED_NO_MISFIRE_SHAPES = {
    "single-quoted-argument-carves-no-standalone-invocation": (
        "echo 'before; codex exec -m {tier}; after'"
    ),
    "shell-bundled-short-options-carrying-only-a-mention": (
        "bash -xc 'git commit -m {tier}'"
    ),
    "argument-list-expanding-wrapper-with-a-separate-value-option-and-a-mention": (
        "xargs -n 1 grep -m {tier}"
    ),
    "scheduling-priority-wrapper-with-a-separate-value-option-and-a-mention": (
        "nice -n 10 grep -m {tier}"
    ),
}


def run_guard(guard_path, env, payload=None, argv=None, stdin_text=None):
    cmd = [sys.executable, str(guard_path)]
    if argv:
        cmd += list(argv)
    if payload is not None:
        stdin_text = json.dumps(payload)
    return subprocess.run(
        cmd,
        input="" if stdin_text is None else stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def run_guard_with_pty_stdin(guard_path, env, argv, timeout=15):
    """Runs the guard with `argv` as a subprocess whose standard input is a
    real pseudo-terminal (`os.isatty()` true), allocated with the standard
    library's `pty` facility -- the shape the consent-write provenance
    boundary's success side requires (task0008.md Test Notes). Guarded with
    a timeout so a hung child fails the test rather than hanging the run.
    """
    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            [sys.executable, str(guard_path), *argv],
            stdin=slave_fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        os.close(slave_fd)
        slave_fd = -1
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    finally:
        if slave_fd != -1:
            os.close(slave_fd)
        os.close(master_fd)


def assert_no_decision(test, result):
    test.assertEqual(result.returncode, 0, result.stderr)
    test.assertEqual(result.stdout, "", f"expected zero bytes, got: {result.stdout!r}")


def assert_deny(test, result):
    test.assertEqual(result.returncode, 0, result.stderr)
    data = json.loads(result.stdout)
    test.assertEqual(set(data.keys()), {"hookSpecificOutput"})
    out = data["hookSpecificOutput"]
    test.assertEqual(
        set(out.keys()),
        {"hookEventName", "permissionDecision", "permissionDecisionReason", "additionalContext"},
    )
    test.assertEqual(out["hookEventName"], "PreToolUse")
    test.assertEqual(out["permissionDecision"], "deny")
    for value in out.values():
        test.assertNotIn("\n", value, f"message is not single-line: {value!r}")
    return out


class GitEnvMixin:
    """A HOME + git identity isolated from the host, so throwaway repos
    never touch the real user's git config (mirrors test_commit_docs.py)."""

    def _make_git_env(self, tmp_root):
        git_home = tmp_root / "git-home"
        git_home.mkdir(exist_ok=True)
        env = dict(os.environ)
        env.pop("CLAUDE_BATCH", None)
        env.update(
            {
                "HOME": str(git_home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        return env

    def _git(self, env, cwd, *args, check=True):
        return subprocess.run(
            ["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True, check=check
        )


class MuseGuardTestCase(unittest.TestCase, GitEnvMixin):
    """Base fixture: a temp directory, a store path under it, and a plain
    subprocess env with EM_WORKFLOW_MUSE_CONSENT pointed at that store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.store_path = self.tmp_path / "store.json"
        self.git_env = self._make_git_env(self.tmp_path)
        self.git_env["EM_WORKFLOW_MUSE_CONSENT"] = str(self.store_path)

    def init_repo(self, name="repo"):
        repo = self.tmp_path / name
        repo.mkdir()
        self._git(self.git_env, repo, "init", "-q", "-b", "main")
        self._git(self.git_env, repo, "commit", "-q", "--allow-empty", "-m", "init")
        return repo

    def record(self, guard_path, project_dir):
        # --record is a mutating command: driven with a pseudo-terminal
        # stdin so the consent-write provenance boundary lets it through
        # (task0008.md Design, "Effect on the existing CLI test cases").
        return run_guard_with_pty_stdin(
            guard_path, self.git_env, ["--record", "--project-dir", str(project_dir)]
        )

    def list_(self, guard_path, project_dir):
        # --list is outside the provenance boundary; an ordinary pipe stays
        # correct and is itself part of what AC-4 asserts.
        return run_guard(guard_path, self.git_env, argv=["--list", "--project-dir", str(project_dir)])

    def remove(self, guard_path, project_dir):
        # --remove is a mutating command: see record() above.
        return run_guard_with_pty_stdin(
            guard_path, self.git_env, ["--remove", "--project-dir", str(project_dir)]
        )

    def _assert_no_decision_for(self, command, cwd, tool_name="Bash"):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name, command=command):
                payload = {"tool_name": tool_name, "tool_input": {"command": command}, "cwd": cwd}
                result = run_guard(guard_path, self.git_env, payload=payload)
                assert_no_decision(self, result)

    def _assert_denies_for(self, command, cwd, tool_name="Bash"):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name, command=command):
                payload = {"tool_name": tool_name, "tool_input": {"command": command}, "cwd": cwd}
                result = run_guard(guard_path, self.git_env, payload=payload)
                assert_deny(self, result)


# --- AC-1: both copies exist, are executable, differ in exactly one line ---


class TestBothCopiesShape(unittest.TestCase):
    def test_both_copies_exist(self):
        for name, path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                self.assertTrue(path.is_file(), f"{path} does not exist")

    def test_both_copies_are_executable(self):
        for name, path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                self.assertTrue(os.access(path, os.X_OK), f"{path} is not executable")

    def test_copies_differ_in_exactly_one_line_the_plugin_slug(self):
        a_lines = GUARD_PATHS["em-workflow"].read_text(encoding="utf-8").splitlines()
        b_lines = GUARD_PATHS["em-review"].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(a_lines), len(b_lines), "the two copies have a different line count")
        diffs = [(i, x, y) for i, (x, y) in enumerate(zip(a_lines, b_lines)) if x != y]
        self.assertEqual(len(diffs), 1, f"expected exactly one differing line, found: {diffs}")
        _, a_line, b_line = diffs[0]
        self.assertEqual(a_line, 'PLUGIN_SLUG = "em-workflow"')
        self.assertEqual(b_line, 'PLUGIN_SLUG = "em-review"')


# --- AC-1 (payload shape) + AC-2 (deny content) ----------------------------


class TestDenyPayloadContent(MuseGuardTestCase):
    def test_deny_payload_has_exactly_four_fields_and_names_the_missing_consent(self):
        repo = self.init_repo()
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                result = run_guard(
                    guard_path,
                    self.git_env,
                    payload={
                        "tool_name": "Bash",
                        "tool_input": {"command": f"codex exec -m {CONTRIBUTOR_TIER} \"x\""},
                        "cwd": str(repo),
                    },
                )
                out = assert_deny(self, result)
                self.assertIn("muse-spark-contributor", out["permissionDecisionReason"])
                self.assertIn("同意", out["permissionDecisionReason"])
                self.assertIn("記録", out["permissionDecisionReason"])
                # No path, project key, or store location in the reason.
                self.assertNotIn(str(repo), out["permissionDecisionReason"])
                self.assertNotIn(str(self.store_path), out["permissionDecisionReason"])
                # Additional context directs the agent to a non-contributor entry.
                self.assertIn("muse-spark", out["additionalContext"])
                self.assertIn(f"{name}:contributor-consent", out["additionalContext"])

    def test_deny_never_interpolates_the_command_cwd_key_or_store_path(self):
        repo = self.init_repo()
        weird_marker = "TOTALLY-UNIQUE-MARKER-9f3c"
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                result = run_guard(
                    guard_path,
                    self.git_env,
                    payload={
                        "tool_name": "Bash",
                        "tool_input": {
                            "command": f'codex exec -m {CONTRIBUTOR_TIER} "{weird_marker}"'
                        },
                        "cwd": str(repo),
                    },
                )
                out = assert_deny(self, result)
                for value in out.values():
                    self.assertNotIn(weird_marker, value)
                    self.assertNotIn(str(repo), value)
                    self.assertNotIn(str(self.store_path), value)


# --- AC-2: every enumerated invocation spelling denies, from both copies --


class TestInvocationSpellingsDenyWithNoConsent(MuseGuardTestCase):
    def test_every_spelling_denies_from_both_copies_and_store_stays_absent(self):
        repo = self.init_repo()
        self.assertFalse(self.store_path.exists())
        for spelling, template in INVOCATION_COMMAND_TEMPLATES.items():
            command = template.format(tier=CONTRIBUTOR_TIER)
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(spelling=spelling, copy=name):
                    result = run_guard(
                        guard_path,
                        self.git_env,
                        payload={
                            "tool_name": "Bash",
                            "tool_input": {"command": command},
                            "cwd": str(repo),
                        },
                    )
                    assert_deny(self, result)
        self.assertFalse(
            self.store_path.exists(), "the hook path must never create the store"
        )


# --- AC-3: no decision for every category of non-invocation ---------------


class TestNoDecisionCases(MuseGuardTestCase):
    def test_plain_tier_in_every_spelling_is_never_denied(self):
        repo = str(self.init_repo())
        for spelling, template in INVOCATION_COMMAND_TEMPLATES.items():
            with self.subTest(spelling=spelling):
                self._assert_no_decision_for(template.format(tier=PLAIN_TIER), repo)

    def test_mention_inside_a_quoted_string_is_not_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(
            f'echo "we should not use -m {CONTRIBUTOR_TIER} directly"', repo
        )

    def test_search_pattern_argument_is_not_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"grep -rn {CONTRIBUTOR_TIER} .", repo)
        self._assert_no_decision_for(f"grep -e {CONTRIBUTOR_TIER} file.txt", repo)

    def test_heredoc_body_is_not_an_invocation(self):
        repo = str(self.init_repo())
        command = f"cat <<'EOF'\ncodex exec -m {CONTRIBUTOR_TIER}\nEOF\n"
        self._assert_no_decision_for(command, repo)

    def test_heredoc_header_look_alike_inside_a_quoted_string_does_not_hide_a_real_invocation(self):
        # AC-4: a `<<WORD` sequence starts a here-document only when it
        # occurs OUTSIDE any quoted region. Here the header-looking text is
        # inside a double-quoted string on line 1, so it must not be
        # honored -- the real invocation on line 2 stays visible and
        # denies, contrasting with test_heredoc_body_is_not_an_invocation
        # above (a GENUINE here-document body is still removed).
        repo = str(self.init_repo())
        command = (
            'echo "start <<EOF"\n'
            f'codex exec -m {CONTRIBUTOR_TIER} "x"\n'
            "EOF\n"
        )
        self._assert_denies_for(command, repo)

    def test_invocation_after_a_genuine_heredocs_terminator_still_denies(self):
        # AC-4: stripping only ever removes the heredoc's own body and
        # terminator; a real invocation placed after the terminator is
        # unaffected.
        repo = str(self.init_repo())
        command = (
            "cat <<'EOF'\n"
            f"just mentions {CONTRIBUTOR_TIER}\n"
            "EOF\n"
            f'codex exec -m {CONTRIBUTOR_TIER} "x"\n'
        )
        self._assert_denies_for(command, repo)

    def test_near_miss_tier_spellings_never_match_via_substring(self):
        # AC-1 / NFR2: every comparison against the contributor tier is
        # EXACT equality, never prefix/suffix/substring -- so a
        # near-miss spelling passed as the model value must never deny.
        repo = str(self.init_repo())
        near_misses = [
            "muse-spark-contributor-extra",
            "not-muse-spark-contributor",
            "muse-spark-contributorx",
            "xmuse-spark-contributor",
        ]
        for value in near_misses:
            with self.subTest(value=value):
                self._assert_no_decision_for(f"codex exec -m {value}", repo)

    def test_commit_message_argument_is_not_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f'git commit -m "{CONTRIBUTOR_TIER}"', repo)
        self._assert_no_decision_for(f"git commit -m {CONTRIBUTOR_TIER}", repo)

    def test_unrelated_command_is_not_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for("ls -la", repo)
        self._assert_no_decision_for("git status", repo)

    def test_payload_whose_tool_is_not_bash_is_undecided(self):
        repo = str(self.init_repo())
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                payload = {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/tmp/x"},
                    "cwd": repo,
                }
                result = run_guard(guard_path, self.git_env, payload=payload)
                assert_no_decision(self, result)

    def test_empty_command_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for("", repo)
        self._assert_no_decision_for("   ", repo)

    def test_unparseable_stdin_is_undecided(self):
        repo = str(self.init_repo())
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                result = run_guard(guard_path, self.git_env, stdin_text="{ this is not json")
                assert_no_decision(self, result)

    def test_after_consent_is_recorded_the_same_invocation_is_undecided(self):
        repo = self.init_repo()
        # Record through em-workflow's copy...
        record_result = self.record(GUARD_PATHS["em-workflow"], repo)
        self.assertEqual(record_result.returncode, 0, record_result.stderr)
        # ...and confirm BOTH copies now stay silent for every spelling,
        # including em-review's own copy (the store is shared).
        for spelling, template in INVOCATION_COMMAND_TEMPLATES.items():
            command = template.format(tier=CONTRIBUTOR_TIER)
            self._assert_no_decision_for(command, str(repo))

    def test_after_consent_recorded_through_the_other_plugins_copy_is_also_undecided(self):
        repo = self.init_repo()
        record_result = self.record(GUARD_PATHS["em-review"], repo)
        self.assertEqual(record_result.returncode, 0, record_result.stderr)
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                payload = {
                    "tool_name": "Bash",
                    "tool_input": {"command": f"codex exec -m {CONTRIBUTOR_TIER} \"x\""},
                    "cwd": str(repo),
                }
                result = run_guard(guard_path, self.git_env, payload=payload)
                assert_no_decision(self, result)


# --- AC-3: nested invocation shapes (wrappers, shells, substitutions) -----


class TestNestedInvocationRecognition(MuseGuardTestCase):
    """Stage 3 resolves a segment's command word through wrappers and
    shells rather than reading it literally; each nested construct below is
    paired with the same construct carrying only a mention, because a fix
    that widens the command word without keeping the codex-CLI restriction
    passes one and fails the other (task0006.md Test Notes)."""

    def test_shell_command_string_argument_carries_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_denies_for(f"bash -c 'codex exec -m {CONTRIBUTOR_TIER}'", repo)

    def test_shell_command_string_argument_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"bash -c 'git commit -m {CONTRIBUTOR_TIER}'", repo)

    def test_parenthesized_command_substitution_carries_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_denies_for(f"echo $(codex exec -m {CONTRIBUTOR_TIER})", repo)

    def test_parenthesized_command_substitution_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f'echo "$(git commit -m {CONTRIBUTOR_TIER})"', repo)

    def test_backtick_command_substitution_carries_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_denies_for(f"echo `codex exec -m {CONTRIBUTOR_TIER}`", repo)

    def test_backtick_command_substitution_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"echo `git commit -m {CONTRIBUTOR_TIER}`", repo)

    def test_argument_list_expanding_wrapper_carries_an_invocation(self):
        repo = str(self.init_repo())
        self._assert_denies_for(f"xargs codex exec -m {CONTRIBUTOR_TIER}", repo)

    def test_argument_list_expanding_wrapper_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"xargs grep -m {CONTRIBUTOR_TIER}", repo)

    def test_shell_command_string_flag_bundled_with_other_short_options_carries_an_invocation(self):
        # TS-27: the command-string flag must be recognized when bundled
        # with other short options in one token (`-xc`), not only standalone.
        repo = str(self.init_repo())
        self._assert_denies_for(f"bash -xc 'codex exec -m {CONTRIBUTOR_TIER}'", repo)

    def test_shell_command_string_flag_bundled_with_other_short_options_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"bash -xc 'git commit -m {CONTRIBUTOR_TIER}'", repo)

    def test_shell_bundle_not_ending_in_the_command_string_flag_is_not_recognized_as_nested(self):
        # task0007.md Design, Stage 3: a cluster that does not contain the
        # flag AS ITS LAST LETTER does not select the next token as nested
        # command text -- `-cx` is `-c` with an ATTACHED value in real
        # getopt bundling, a different, unmodelled shape, so this must stay
        # unclassified rather than guessing.
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"bash -cx 'codex exec -m {CONTRIBUTOR_TIER}'", repo)

    def test_argument_list_expanding_wrapper_with_a_separate_value_option_carries_an_invocation(self):
        # TS-27: `xargs -n 1 codex ...` -- the numeric value of `-n` must
        # be stepped over instead of being mistaken for the command word.
        repo = str(self.init_repo())
        self._assert_denies_for(f"xargs -n 1 codex exec -m {CONTRIBUTOR_TIER}", repo)

    def test_argument_list_expanding_wrapper_with_a_separate_value_option_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"xargs -n 1 grep -m {CONTRIBUTOR_TIER}", repo)

    def test_scheduling_priority_wrapper_with_a_separate_value_option_carries_an_invocation(self):
        # TS-27: `nice -n 10 codex ...` -- same shape as xargs above, for
        # the scheduling-priority wrapper.
        repo = str(self.init_repo())
        self._assert_denies_for(f"nice -n 10 codex exec -m {CONTRIBUTOR_TIER}", repo)

    def test_scheduling_priority_wrapper_with_a_separate_value_option_carrying_only_a_mention_is_undecided(self):
        repo = str(self.init_repo())
        self._assert_no_decision_for(f"nice -n 10 grep -m {CONTRIBUTOR_TIER}", repo)

    def test_wrapper_option_unknown_to_the_wrapper_table_stops_resolution(self):
        # Design, Stage 3: an option a wrapper's table does not describe
        # stops resolution and leaves the statement unclassified (fail
        # open) rather than guessing whether it takes a value -- a
        # documented residual, not modelled shell semantics in general.
        repo = str(self.init_repo())
        self._assert_no_decision_for(
            f"nice --unknown-flag codex exec -m {CONTRIBUTOR_TIER}", repo
        )

    def test_recursion_bound_is_two_levels_and_a_third_level_yields_no_decision(self):
        # The recursion bound is asserted behaviorally (task0006.md Test
        # Notes): two levels of shell `-c` nesting around a real invocation
        # still denies (AT the bound); a third level yields no decision
        # (ONE PAST the bound) rather than an error.
        repo = str(self.init_repo())
        inner = f"codex exec -m {CONTRIBUTOR_TIER}"
        one_level = f"bash -c {shlex.quote(inner)}"
        two_levels = f"bash -c {shlex.quote(one_level)}"
        three_levels = f"bash -c {shlex.quote(two_levels)}"
        self._assert_denies_for(one_level, repo)
        self._assert_denies_for(two_levels, repo)
        self._assert_no_decision_for(three_levels, repo)


# --- Verify reproductions + widening tables (task0007, IMPLEMENTATION.md
# D-H): the four scenarios verify found failing under the pre-task0007,
# quote-blind splitter (Provenance: TS-5, TS-6, TS-26, TS-27), written
# first per Test Notes, plus the paired deny / no-misfire tables so a
# future shape is one row on each side. ---


class TestVerifyReproductionsAndWideningTables(MuseGuardTestCase):
    # --- the four verify reproductions, by exact shape (Test Notes) ------

    def test_ts5_a_contributor_invocation_followed_by_a_double_quoted_prompt_containing_a_semicolon_denies(
        self,
    ):
        repo = str(self.init_repo())
        self._assert_denies_for(f'codex exec -m {CONTRIBUTOR_TIER} "before;after"', repo)

    def test_ts5_a_contributor_invocation_followed_by_a_double_quoted_prompt_containing_a_newline_denies(
        self,
    ):
        repo = str(self.init_repo())
        self._assert_denies_for(f'codex exec -m {CONTRIBUTOR_TIER} "before\nafter"', repo)

    def test_ts6_a_text_printing_commands_single_quoted_separator_delimited_invocation_looking_argument_is_undecided(
        self,
    ):
        repo = str(self.init_repo())
        self._assert_no_decision_for(
            f"echo 'before; codex exec -m {CONTRIBUTOR_TIER}; after'", repo
        )

    def test_ts27_a_shell_invoked_with_a_bundled_short_option_cluster_ending_in_the_command_string_flag_denies(
        self,
    ):
        repo = str(self.init_repo())
        self._assert_denies_for(f"bash -xc 'codex exec -m {CONTRIBUTOR_TIER}'", repo)

    def test_ts27_the_argument_list_and_scheduling_priority_wrappers_each_with_a_separate_value_numeric_option_deny(
        self,
    ):
        repo = str(self.init_repo())
        self._assert_denies_for(f"xargs -n 1 codex exec -m {CONTRIBUTOR_TIER}", repo)
        self._assert_denies_for(f"nice -n 10 codex exec -m {CONTRIBUTOR_TIER}", repo)

    # --- widening tables: every row paired on both sides (Test Notes) ----

    def test_every_widened_deny_shape_denies_from_both_copies(self):
        repo = str(self.init_repo())
        for shape, template in WIDENED_DENY_SHAPES.items():
            with self.subTest(shape=shape):
                self._assert_denies_for(template.format(tier=CONTRIBUTOR_TIER), repo)

    def test_every_widened_no_misfire_shape_is_undecided_from_both_copies(self):
        repo = str(self.init_repo())
        for shape, template in WIDENED_NO_MISFIRE_SHAPES.items():
            with self.subTest(shape=shape):
                self._assert_no_decision_for(template.format(tier=CONTRIBUTOR_TIER), repo)

    def test_widened_deny_shapes_with_the_plain_tier_are_never_denied(self):
        # AC-3 / NFR2: exact equality in both directions -- the widened
        # deny shapes must never fire for the plain tier either.
        repo = str(self.init_repo())
        for shape, template in WIDENED_DENY_SHAPES.items():
            with self.subTest(shape=shape):
                self._assert_no_decision_for(template.format(tier=PLAIN_TIER), repo)

    def test_unterminated_quote_is_undecided_not_an_exception(self):
        # Test Notes: at least one tokenizer-hostile case, asserting no
        # decision and a zero exit, pinning the tolerance clause (NFR2).
        repo = str(self.init_repo())
        self._assert_no_decision_for('echo "unterminated', repo)
        self._assert_no_decision_for(
            f"codex exec -m {CONTRIBUTOR_TIER} 'still open", repo
        )


# --- AC-4: project-key derivation matches the bash guard's own rule -------


class TestProjectKeyDerivation(MuseGuardTestCase):
    def test_two_worktrees_of_one_repository_share_one_consent_entry(self):
        main_repo = self.init_repo("main")
        branch = "feature"
        wt_path = self.tmp_path / "wt"
        self._git(self.git_env, main_repo, "worktree", "add", "-q", "-b", branch, str(wt_path))

        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name, direction="record-from-main-observe-from-worktree"):
                fresh_store = self.tmp_path / f"store-{name}-a.json"
                env = dict(self.git_env)
                env["EM_WORKFLOW_MUSE_CONSENT"] = str(fresh_store)
                rec = run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(main_repo)])
                self.assertEqual(rec.returncode, 0, rec.stderr)
                listed_from_wt = run_guard(
                    guard_path, env, argv=["--list", "--project-dir", str(wt_path)]
                )
                self.assertEqual(listed_from_wt.stdout.strip(), rec.stdout.split(": ", 1)[1].strip())

        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name, direction="revoke-from-worktree-observe-from-main"):
                fresh_store = self.tmp_path / f"store-{name}-b.json"
                env = dict(self.git_env)
                env["EM_WORKFLOW_MUSE_CONSENT"] = str(fresh_store)
                run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(main_repo)])
                removed = run_guard_with_pty_stdin(guard_path, env, ["--remove", "--project-dir", str(wt_path)])
                self.assertIn("同意を削除した", removed.stdout)
                listed_from_main = run_guard(
                    guard_path, env, argv=["--list", "--project-dir", str(main_repo)]
                )
                self.assertEqual(listed_from_main.stdout, "")

    def test_a_non_repository_directory_reached_through_a_symlink_resolves_to_its_real_path(self):
        real_dir = self.tmp_path / "real-plain-dir"
        real_dir.mkdir()
        link_dir = self.tmp_path / "link-to-plain-dir"
        link_dir.symlink_to(real_dir, target_is_directory=True)

        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                fresh_store = self.tmp_path / f"store-symlink-{name}.json"
                env = dict(self.git_env)
                env["EM_WORKFLOW_MUSE_CONSENT"] = str(fresh_store)
                rec = run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(link_dir)])
                self.assertEqual(rec.returncode, 0, rec.stderr)
                listed = run_guard(guard_path, env, argv=["--list", "--project-dir", str(real_dir)])
                self.assertEqual(listed.stdout.strip(), os.path.realpath(str(real_dir)))


# --- AC-5: malformed store, table-driven -----------------------------------


def _write_missing(path):
    if path.exists():
        path.unlink()


def _write_invalid_json(path):
    path.write_text("not json at all {{{")


def _write_wrong_shape_not_a_mapping(path):
    path.write_text(json.dumps(["a", "list", "not", "a", "mapping"]))


def _write_wrong_shape_projects_not_a_mapping(path):
    path.write_text(json.dumps({"version": "1", "projects": "not-a-mapping"}))


def _write_directory(path):
    if path.exists():
        path.unlink()
    path.mkdir()


MALFORMED_STORE_ROWS = [
    ("missing", _write_missing),
    ("invalid-json", _write_invalid_json),
    ("wrong-shape-not-a-mapping", _write_wrong_shape_not_a_mapping),
    ("wrong-shape-projects-not-a-mapping", _write_wrong_shape_projects_not_a_mapping),
    ("directory-instead-of-file", _write_directory),
]


class TestMalformedStoreOnHookPath(MuseGuardTestCase):
    def test_every_corruption_shape_denies_invocations_and_leaves_other_commands_undecided(self):
        repo = self.init_repo()
        for label, setup in MALFORMED_STORE_ROWS:
            setup(self.store_path)
            before_is_dir = self.store_path.is_dir()
            before_bytes = None if before_is_dir or not self.store_path.exists() else self.store_path.read_bytes()
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(row=label, copy=name, aspect="invocation-denies"):
                    payload = {
                        "tool_name": "Bash",
                        "tool_input": {"command": f"codex exec -m {CONTRIBUTOR_TIER} \"x\""},
                        "cwd": str(repo),
                    }
                    result = run_guard(guard_path, self.git_env, payload=payload)
                    assert_deny(self, result)
                with self.subTest(row=label, copy=name, aspect="other-command-undecided"):
                    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": str(repo)}
                    result = run_guard(guard_path, self.git_env, payload=payload)
                    assert_no_decision(self, result)
            # The store is left exactly as this row set it up -- the hook
            # path never repairs, writes, or creates it.
            if label == "missing":
                self.assertFalse(self.store_path.exists())
            elif label == "directory-instead-of-file":
                self.assertTrue(self.store_path.is_dir())
                self.assertEqual(list(self.store_path.iterdir()), [])
            else:
                self.assertEqual(self.store_path.read_bytes(), before_bytes)
            # Clean the row's fixture before the next one.
            if self.store_path.is_dir():
                shutil.rmtree(self.store_path)
            elif self.store_path.exists():
                self.store_path.unlink()


class TestMalformedStoreOnCliPath(MuseGuardTestCase):
    def test_a_mutating_command_against_a_malformed_store_fails_loudly_and_writes_nothing(self):
        repo = self.init_repo()
        for label, setup in MALFORMED_STORE_ROWS:
            if label == "missing":
                continue  # missing is a fresh store, not malformed, for the CLI
            for mode in ("--record", "--remove"):
                setup(self.store_path)
                before_is_dir = self.store_path.is_dir()
                before_bytes = None if before_is_dir else self.store_path.read_bytes()
                for name, guard_path in GUARD_PATHS.items():
                    with self.subTest(row=label, mode=mode, copy=name):
                        # A pseudo-terminal stdin so this exercises the
                        # malformed-store check itself, not the provenance
                        # boundary in front of it (task0008.md Design).
                        result = run_guard_with_pty_stdin(
                            guard_path,
                            self.git_env,
                            [mode, "--project-dir", str(repo)],
                        )
                        self.assertEqual(result.returncode, 1)
                        self.assertEqual(result.stdout, "")
                        self.assertIn("同意ストアの形式が不正", result.stderr)
                        self.assertIn(str(self.store_path), result.stderr)
                        if before_is_dir:
                            self.assertTrue(self.store_path.is_dir())
                        else:
                            self.assertEqual(self.store_path.read_bytes(), before_bytes)
                if self.store_path.is_dir():
                    shutil.rmtree(self.store_path)
                elif self.store_path.exists():
                    self.store_path.unlink()

    def test_list_never_errors_on_a_malformed_store(self):
        repo = self.init_repo()
        for label, setup in MALFORMED_STORE_ROWS:
            if label == "missing":
                continue
            setup(self.store_path)
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(row=label, copy=name):
                    result = self.list_(guard_path, repo)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
            if self.store_path.is_dir():
                shutil.rmtree(self.store_path)
            elif self.store_path.exists():
                self.store_path.unlink()


# --- task0008 AC-1..AC-4: consent-write provenance boundary on the CLI ----
# Distinctly named/grouped per task0008.md Test Notes so the parallel
# recognition task's (task0007) additions cannot collide with these in the
# same region (IMPLEMENTATION.md D-J).


class TestConsentWriteProvenanceBoundary(MuseGuardTestCase):
    """`--record` and `--remove` refuse to touch the store unless standard
    input is an interactive terminal; `--list` is unaffected
    (IMPLEMENTATION.md Shared Components, "Consent-write provenance
    boundary"; task0008.md Acceptance Criteria)."""

    def test_record_and_remove_refuse_a_non_interactive_stdin_against_an_absent_store(self):
        # AC-1 (TS-29): store path under a temporary directory that does not
        # exist yet, a temporary repository as the project directory, an
        # ordinary pipe for stdin.
        repo = self.init_repo()
        nested_store = self.tmp_path / "nested" / "store.json"
        env = dict(self.git_env)
        env["EM_WORKFLOW_MUSE_CONSENT"] = str(nested_store)
        for mode in ("--record", "--remove"):
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(mode=mode, copy=name):
                    result = run_guard(guard_path, env, argv=[mode, "--project-dir", str(repo)])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("対話的な端末", result.stderr)
                    self.assertFalse(nested_store.exists())
                    self.assertFalse(nested_store.parent.exists())

    def test_record_and_remove_leave_an_existing_store_byte_identical_when_stdin_is_non_interactive(self):
        # AC-2 (TS-29): an existing store containing an unrelated project
        # key, a non-interactive stdin -- the file must stay byte-identical.
        repo = self.init_repo()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1",
            "projects": {"an-unrelated-project-key": {"updated_at": "2020-01-01T00:00:00+00:00"}},
        }
        self.store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before_bytes = self.store_path.read_bytes()
        for mode in ("--record", "--remove"):
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(mode=mode, copy=name):
                    result = run_guard(
                        guard_path, self.git_env, argv=[mode, "--project-dir", str(repo)]
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("対話的な端末", result.stderr)
                    self.assertEqual(self.store_path.read_bytes(), before_bytes)

    def test_refusal_precedes_project_key_derivation_so_a_non_repository_directory_behaves_identically(self):
        # AC-1 / AC-2 ordering (TS-29): the refusal must behave identically
        # whether the project directory is a repository or not -- which can
        # only hold if project-key derivation (and the git subprocess it
        # would launch) never ran. Asserted behaviorally, not by inspecting
        # source (task0008.md Test Notes).
        repo = self.init_repo()
        non_repo_dir = self.tmp_path / "not-a-repo"
        non_repo_dir.mkdir()
        for mode in ("--record", "--remove"):
            for name, guard_path in GUARD_PATHS.items():
                with self.subTest(mode=mode, copy=name):
                    in_repo = run_guard(
                        guard_path, self.git_env, argv=[mode, "--project-dir", str(repo)]
                    )
                    not_repo = run_guard(
                        guard_path, self.git_env, argv=[mode, "--project-dir", str(non_repo_dir)]
                    )
                    self.assertNotEqual(in_repo.returncode, 0)
                    self.assertEqual(in_repo.returncode, not_repo.returncode)
                    self.assertEqual(in_repo.stdout, not_repo.stdout)
                    self.assertEqual(in_repo.stderr, not_repo.stderr)
        self.assertFalse(self.store_path.exists())

    def test_record_and_remove_succeed_unchanged_with_a_pseudo_terminal_stdin(self):
        # AC-3 (TS-30, TS-11): the precondition satisfied leaves the
        # pre-existing behavior, output lines and exit codes unchanged.
        repo = self.init_repo()
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                record_result = run_guard_with_pty_stdin(
                    guard_path, self.git_env, ["--record", "--project-dir", str(repo)]
                )
                self.assertEqual(record_result.returncode, 0, record_result.stderr)
                self.assertTrue(record_result.stdout.startswith("同意を記録した: "))
                key = record_result.stdout.split(": ", 1)[1].strip()
                stored = json.loads(self.store_path.read_text())
                self.assertEqual(set(stored["projects"][key].keys()), {"updated_at"})

                remove_result = run_guard_with_pty_stdin(
                    guard_path, self.git_env, ["--remove", "--project-dir", str(repo)]
                )
                self.assertEqual(remove_result.returncode, 0, remove_result.stderr)
                self.assertTrue(remove_result.stdout.startswith("同意を削除した: "))
                stored_after = json.loads(self.store_path.read_text())
                self.assertNotIn(key, stored_after["projects"])
                self.store_path.unlink()

    def test_list_is_unaffected_by_the_precondition_across_a_record_sequence(self):
        # AC-4 (TS-30): --list stays outside the precondition and reflects
        # state changes -- list (non-terminal) -> record (pseudo-terminal)
        # -> list (non-terminal) yields nothing, then a record, then the key.
        repo = self.init_repo()
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                before = self.list_(guard_path, repo)
                self.assertEqual(before.returncode, 0)
                self.assertEqual(before.stdout, "")

                record_result = run_guard_with_pty_stdin(
                    guard_path, self.git_env, ["--record", "--project-dir", str(repo)]
                )
                self.assertEqual(record_result.returncode, 0, record_result.stderr)
                key = record_result.stdout.split(": ", 1)[1].strip()

                after = self.list_(guard_path, repo)
                self.assertEqual(after.returncode, 0)
                self.assertEqual(after.stdout, key + "\n")

                run_guard_with_pty_stdin(
                    guard_path, self.git_env, ["--remove", "--project-dir", str(repo)]
                )


# --- AC-6: CLI round trip ---------------------------------------------------

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


class TestCliRoundTrip(MuseGuardTestCase):
    def test_full_round_trip_for_both_copies(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                self._round_trip(guard_path)

    def _round_trip(self, guard_path):
        repo = self.init_repo(f"repo-{guard_path.parent.parent.name}")
        store = self.tmp_path / f"store-{guard_path.parent.parent.name}.json"
        env = dict(self.git_env)
        env["EM_WORKFLOW_MUSE_CONSENT"] = str(store)

        # --list before consent: nothing, exit 0.
        before = run_guard(guard_path, env, argv=["--list", "--project-dir", str(repo)])
        self.assertEqual(before.returncode, 0)
        self.assertEqual(before.stdout, "")

        # --record: prints one line naming the key, exit 0.
        first_record = run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(repo)])
        self.assertEqual(first_record.returncode, 0, first_record.stderr)
        self.assertTrue(first_record.stdout.startswith("同意を記録した: "))
        key = first_record.stdout.split(": ", 1)[1].strip()

        first_store = json.loads(store.read_text())
        self.assertEqual(set(first_store.keys()), {"version", "projects"})
        self.assertEqual(first_store["version"], "1")
        self.assertEqual(set(first_store["projects"].keys()), {key})
        self.assertEqual(set(first_store["projects"][key].keys()), {"updated_at"})
        self.assertRegex(first_store["projects"][key]["updated_at"], TIMESTAMP_RE)

        # --record again: idempotent, refreshes the timestamp, same message
        # shape (no "already recorded" variant).
        time.sleep(1.01)
        second_record = run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(repo)])
        self.assertEqual(second_record.returncode, 0)
        self.assertEqual(second_record.stdout, first_record.stdout)
        second_store = json.loads(store.read_text())
        self.assertEqual(set(second_store["projects"].keys()), {key})
        self.assertNotEqual(
            second_store["projects"][key]["updated_at"],
            first_store["projects"][key]["updated_at"],
            "a second --record must refresh the timestamp",
        )

        # --list after consent: the key alone, one line.
        listed = run_guard(guard_path, env, argv=["--list", "--project-dir", str(repo)])
        self.assertEqual(listed.stdout, key + "\n")

        # --remove: deletes the key entirely, prints one line, exit 0.
        removed = run_guard_with_pty_stdin(guard_path, env, ["--remove", "--project-dir", str(repo)])
        self.assertEqual(removed.returncode, 0)
        self.assertTrue(removed.stdout.startswith("同意を削除した: "))
        after_remove_store = json.loads(store.read_text())
        self.assertEqual(after_remove_store["projects"], {})

        # A second --remove: reports the absence, exit 0, store untouched.
        bytes_before_second_remove = store.read_bytes()
        removed_again = run_guard_with_pty_stdin(guard_path, env, ["--remove", "--project-dir", str(repo)])
        self.assertEqual(removed_again.returncode, 0)
        self.assertTrue(removed_again.stdout.startswith("同意は記録されていない: "))
        self.assertEqual(store.read_bytes(), bytes_before_second_remove)

    def test_record_creates_parent_directories_that_do_not_exist_yet(self):
        repo = self.init_repo()
        nested_store = self.tmp_path / "a" / "b" / "c" / "store.json"
        env = dict(self.git_env)
        env["EM_WORKFLOW_MUSE_CONSENT"] = str(nested_store)
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                self.assertFalse(nested_store.parent.exists())
                result = run_guard_with_pty_stdin(guard_path, env, ["--record", "--project-dir", str(repo)])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(nested_store.is_file())
                nested_store.unlink()
                shutil.rmtree(nested_store.parent.parent.parent)

    def test_writes_go_through_a_temp_file_and_atomic_replace(self):
        # Atomicity itself is not directly observable from outside the
        # process; the source is inspected for the write-then-replace
        # pattern the store-writer contract requires (IMPLEMENTATION.md
        # Shared Components, "Consent store file" writer postcondition).
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                source = guard_path.read_text(encoding="utf-8")
                self.assertIn(".tmp", source)
                self.assertIn("os.replace(", source)

    def test_argument_misuse_exits_2(self):
        repo = self.init_repo()
        misuse_argvs = [
            [],
            ["--record"],
            ["--project-dir", str(repo)],
            ["--record", "--remove", "--project-dir", str(repo)],
            ["--record", "--list", "--project-dir", str(repo)],
            ["--bogus", "--project-dir", str(repo)],
            ["--record", "--project-dir"],
        ]
        for name, guard_path in GUARD_PATHS.items():
            for argv in misuse_argvs:
                with self.subTest(copy=name, argv=argv):
                    if not argv:
                        # No arguments at all is HOOK mode (reads stdin),
                        # not CLI misuse -- covered by the no-decision
                        # tests. Exercise it here only to document the
                        # boundary: it must not exit 2.
                        result = run_guard(guard_path, self.git_env, stdin_text="not json")
                        self.assertEqual(result.returncode, 0)
                        continue
                    result = run_guard(guard_path, self.git_env, argv=argv)
                    self.assertEqual(result.returncode, 2, result.stderr)


# --- AC-7: hygiene -----------------------------------------------------


THIRD_PARTY_BLOCKLIST_HINTS = ("yaml", "requests", "httpx", "aiohttp")
NETWORK_MODULE_NAMES = {
    "socket",
    "urllib",
    "urllib.request",
    "http",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
}


class TestSourceHygiene(unittest.TestCase):
    def _imported_module_names(self, source):
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        return names

    def test_no_third_party_imports(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                imported = self._imported_module_names(guard_path.read_text(encoding="utf-8"))
                for hint in THIRD_PARTY_BLOCKLIST_HINTS:
                    self.assertNotIn(hint, imported)

    def test_no_network_capable_imports(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                imported = self._imported_module_names(guard_path.read_text(encoding="utf-8"))
                offenders = imported & NETWORK_MODULE_NAMES
                self.assertEqual(offenders, set(), f"network-capable import(s): {offenders}")

    def test_no_ask_decision_literal(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                source = guard_path.read_text(encoding="utf-8")
                self.assertNotIn('"ask"', source)
                self.assertNotIn("'ask'", source)

    def test_no_allow_decision_literal(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                source = guard_path.read_text(encoding="utf-8")
                self.assertNotIn('"allow"', source)
                self.assertNotIn("'allow'", source)

    def test_the_only_subprocess_launched_is_the_git_call(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                source = guard_path.read_text(encoding="utf-8")
                self.assertEqual(source.count("subprocess.run("), 1)
                # The one call site must be the git key-derivation call.
                idx = source.index("subprocess.run(")
                nearby = source[idx : idx + 200]
                self.assertIn('"git"', nearby)

    def test_neither_plugins_hooks_tests_directory_gained_a_file(self):
        pre_existing = {"destructive-guard-cases.json", "run-destructive-guard.py"}
        em_workflow_tests_dir = REPO_ROOT / "em-workflow" / "hooks" / "tests"
        if em_workflow_tests_dir.is_dir():
            names = {p.name for p in em_workflow_tests_dir.iterdir()}
            self.assertEqual(names, pre_existing, f"unexpected file(s) under {em_workflow_tests_dir}")
        em_review_tests_dir = REPO_ROOT / "em-review" / "hooks" / "tests"
        self.assertFalse(
            em_review_tests_dir.exists(),
            "em-review/hooks/tests/ must not gain a file for this feature",
        )


def _load_guard_module(guard_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        f"_muse_guard_under_test_{guard_path.parent.parent.name}", guard_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNonInvocationShortCircuit(unittest.TestCase):
    """AC-7: a non-invocation command returns before the git subprocess and
    the store read. Verified white-box (the guard's own module functions),
    since call-ordering is not observable purely from stdout/exit code."""

    def test_non_invocation_never_derives_a_project_key_or_touches_the_store(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                module = _load_guard_module(guard_path)
                stdin_payload = json.dumps(
                    {"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": "/tmp"}
                )
                with mock.patch.object(module, "git_common_dir") as mocked_git, mock.patch.object(
                    module, "read_store_for_hook"
                ) as mocked_read, mock.patch(
                    "sys.stdin", io.StringIO(stdin_payload)
                ), contextlib.redirect_stdout(io.StringIO()):
                    result = module.hook_main()
                self.assertEqual(result, 0)
                mocked_git.assert_not_called()
                mocked_read.assert_not_called()

    def test_an_invocation_does_derive_a_project_key_and_read_the_store(self):
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                module = _load_guard_module(guard_path)
                stdin_payload = json.dumps(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": f"codex exec -m {CONTRIBUTOR_TIER} \"x\""},
                        "cwd": "/tmp",
                    }
                )
                with mock.patch.object(
                    module, "git_common_dir", return_value=None
                ) as mocked_git, mock.patch.object(
                    module, "read_store_for_hook", return_value=set()
                ) as mocked_read, mock.patch(
                    "sys.stdin", io.StringIO(stdin_payload)
                ), contextlib.redirect_stdout(io.StringIO()):
                    result = module.hook_main()
                self.assertEqual(result, 0)
                mocked_git.assert_called_once()
                mocked_read.assert_called_once()


# --- Latency (Test Notes: generous upper bound, not a micro-benchmark) ----


class TestLatencyStaysWellUnderTheRegisteredTimeout(MuseGuardTestCase):
    def test_a_representative_sample_of_hook_calls_completes_quickly(self):
        repo = self.init_repo()
        nested_inner = f"codex exec -m {CONTRIBUTOR_TIER}"
        nested_two_levels = f"bash -c {shlex.quote('bash -c ' + shlex.quote(nested_inner))}"
        commands = [
            "ls -la",
            "git status",
            f"codex exec -m {PLAIN_TIER} \"x\"",
            f"codex exec -m {CONTRIBUTOR_TIER} \"x\"",
            f'grep -rn {CONTRIBUTOR_TIER} .',
            nested_two_levels,
            f"echo $(codex exec -m {CONTRIBUTOR_TIER})",
            'echo "start <<EOF"\n' + f'codex exec -m {CONTRIBUTOR_TIER} "x"\n' + "EOF\n",
        ]
        for name, guard_path in GUARD_PATHS.items():
            with self.subTest(copy=name):
                start = time.monotonic()
                for command in commands:
                    payload = {
                        "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "cwd": str(repo),
                    }
                    result = run_guard(guard_path, self.git_env, payload=payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                elapsed = time.monotonic() - start
                # Registered timeout is 15s PER call; this samples several
                # calls and still expects to stay well under a single
                # timeout's budget.
                self.assertLess(elapsed, 10, f"{name}: {len(commands)} calls took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()

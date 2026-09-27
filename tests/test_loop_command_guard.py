"""Contract tests for `em-workflow/hooks/loop-command-guard.py`.

Every case drives the guard as a subprocess with PreToolUse JSON on standard
input and asserts on standard output, in the same shape as
`tests/test_interpreter_mismatch_guard.py`. `deny` cases guard the point of
the hook: a while / until loop at a command position, anywhere it is
reachable per feature-docs/loop-command-guard/tasks/task0001.md, must be
stopped. `silent` cases guard the cost: the guard must say nothing whenever
no such loop is reachable, or the input cannot be settled, so it never stops
an unattended run over an ordinary command.

Standard library only, per test/README.md.
"""

import ast
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "loop-command-guard.py"
README_PATH = REPO_ROOT / "em-workflow" / "README.md"
HOOK_TESTS_RULE_PATH = REPO_ROOT / ".claude" / "rules" / "hook-tests.md"
HOOKS_JSON_PATH = REPO_ROOT / "em-workflow" / "hooks" / "hooks.json"

# Generous bound for the AC-5 bounded-time checks: at most one third of the
# 15-second registration timeout (task0001.md Test Notes, AC-5).
BOUNDED_TIME_SECONDS = 5.0


def run_guard(payload, env=None):
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def assert_deny(case, code, out, err):
    case.assertEqual(err, "")
    case.assertEqual(code, 0)
    decision = json.loads(out)["hookSpecificOutput"]
    case.assertEqual(decision["hookEventName"], "PreToolUse")
    case.assertEqual(decision["permissionDecision"], "deny")
    case.assertTrue(
        decision["permissionDecisionReason"].startswith("[loop-command-guard]")
    )


def assert_silent(case, code, out, err):
    case.assertEqual(err, "")
    case.assertEqual(code, 0)
    case.assertEqual(out, "")


# (expected, label, command) -- expected is "deny" or "silent". CASES covers
# AC-1, AC-2 and AC-3; the AC-4 malformed payloads live in their own test
# below (task0001.md Test Notes).
CASES = [
    # AC-1 (FR1, FR2, FR6; SPEC AC1, AC2, AC7)
    ("deny", "AC1 while loop", "while true; do sleep 1; done"),
    ("deny", "AC1 until loop", "until false; do :; done"),
    ("deny", "AC1 loop backgrounded", "while true; do sleep 1; done &"),
    ("deny", "AC1 loop after &&", "true && while true; do :; done"),
    ("deny", "AC1 loop after ||", "true || while true; do :; done"),
    ("deny", "AC1 loop after ;", "true; while true; do :; done"),
    ("deny", "AC1 loop after |", "true | while read line; do echo $line; done"),
    ("deny", "AC1 loop after newline", "true\nwhile true; do :; done"),
    ("deny", "AC1 loop after (", "(while true; do :; done)"),
    ("deny", "AC1 loop after {", "{ while true; do :; done; }"),
    ("deny", "AC1 loop after !", "! while true; do :; done"),
    ("deny", "AC1 loop after then", "if true; then while true; do :; done; fi"),
    (
        "deny",
        "AC1 loop after elif",
        "if false; then :; elif true; then while true; do :; done; fi",
    ),
    (
        "deny",
        "AC1 loop after else",
        "if false; then :; else while true; do :; done; fi",
    ),
    (
        "deny",
        "AC1 loop after do inside a for loop",
        "for i in 1 2; do while true; do :; done; done",
    ),
    (
        "deny",
        "AC1 pipe into a while-read loop",
        "cat file | while read line; do echo $line; done",
    ),
    # AC-2 (FR3, FR5, A6; SPEC AC3, AC4; TM-1)
    ("deny", "AC2 bash -c", "bash -c 'while true; do :; done'"),
    ("deny", "AC2 sh -c", "sh -c 'while true; do :; done'"),
    ("deny", "AC2 zsh -c", "zsh -c 'while true; do :; done'"),
    ("deny", "AC2 bash -lc", "bash -lc 'while true; do :; done'"),
    (
        "deny",
        "AC2 bash -euo pipefail -c",
        "bash -euo pipefail -c 'while true; do :; done'",
    ),
    ("deny", "AC2 eval argument", "eval 'while true; do :; done'"),
    (
        "deny",
        "AC2 unquoted command substitution",
        "echo $(while true; do :; done)",
    ),
    ("deny", "AC2 backtick", "echo `while true; do :; done`"),
    (
        "deny",
        "AC2 command substitution in double quotes",
        'echo "$(while true; do :; done)"',
    ),
    (
        "deny",
        "AC2 command substitution in a double-quoted argument of a non-shell command",
        'grep "$(while true; do :; done)" file',
    ),
    (
        "deny",
        "AC2 loop in a heredoc body fed to bash",
        "bash <<EOF\nwhile true; do :; done\nEOF",
    ),
    (
        "deny",
        "AC2 loop in a herestring fed to bash",
        "bash <<< 'while true; do :; done'",
    ),
    (
        "deny",
        "AC2 loop nested two levels deep",
        "echo $(echo $(while true; do :; done))",
    ),
    (
        "deny",
        "AC2 timeout prefix",
        "timeout 60 bash -c 'while true; do :; done'",
    ),
    ("deny", "AC2 nohup prefix", "nohup bash -c 'while true; do :; done'"),
    ("deny", "AC2 env prefix", "env bash -c 'while true; do :; done'"),
    ("deny", "AC2 nice prefix", "nice bash -c 'while true; do :; done'"),
    ("deny", "AC2 setsid prefix", "setsid bash -c 'while true; do :; done'"),
    (
        "deny",
        "AC2 stdbuf prefix",
        "stdbuf -oL bash -c 'while true; do :; done'",
    ),
    ("deny", "AC2 command prefix", "command bash -c 'while true; do :; done'"),
    ("deny", "AC2 exec prefix", "exec bash -c 'while true; do :; done'"),
    ("deny", "AC2 time prefix", "time bash -c 'while true; do :; done'"),
    (
        "deny",
        "AC2 enclosing loop with an undecidable nested text",
        "while true; do :; done; bash -c \"echo 'unterminated\"",
    ),
    # AC-3 (FR4, FR7, A4, A6, A7; SPEC AC5; TM-2, TM-4)
    ("silent", "AC3 SPEC AC5: echo while", "echo while"),
    ("silent", "AC3 SPEC AC5: grep -r until", 'grep -r "until" .'),
    ("silent", "AC3 SPEC AC5: git commit message", "git commit -m 'while loop'"),
    (
        "silent",
        "AC3 SPEC AC5: single-quoted data",
        "echo 'while true'",
    ),
    (
        "silent",
        "AC3 SPEC AC5: loop in a heredoc body fed to a non-shell command",
        "cat <<EOF\nwhile true; do :; done\nEOF",
    ),
    ("silent", "AC3 SPEC AC5: comment", "true # while true"),
    ("silent", "AC3 SPEC AC5: python3 -c", "python3 -c 'while True: pass'"),
    ("silent", "AC3 double-quoted while", '"while"'),
    ("silent", "AC3 backslash-escaped while", "\\while"),
    ("silent", "AC3 for loop without while/until", "for i in 1 2; do echo $i; done"),
    (
        "silent",
        "AC3 select loop without while/until",
        "select x in a b; do echo $x; done",
    ),
    ("silent", "AC3 reserved word as argument", "echo do while"),
    (
        "silent",
        "AC3 single-quoted data inside a -c string",
        "bash -c \"echo 'while true'\"",
    ),
    ("silent", "AC3 arithmetic expansion", "echo $((1+2))"),
    ("silent", "AC3 find -exec sh -c", "find . -exec sh -c 'while true; do :; done' \\;"),
    ("silent", "AC3 xargs sh -c", "xargs sh -c 'while true; do :; done'"),
    ("silent", "AC3 ssh remote command", "ssh host 'while true; do :; done'"),
    (
        "silent",
        "AC3 quoted script piped into bash",
        "echo 'while true' | bash",
    ),
    (
        "silent",
        "AC3 heredoc piped into bash (attached to the non-shell command)",
        "cat <<EOF | bash\nwhile true; do :; done\nEOF",
    ),
    # task0002.md AC-1 (FR5, A6; finding 58562295e0a7b109): a value-taking
    # prefix-command option, separated from its value by a space, must not
    # make the value word the executed command.
    ("deny", "AC1 task0002: env -u X", "env -u X bash -c 'while false; do :; done'"),
    ("deny", "AC1 task0002: nice -n 5", "nice -n 5 bash -c 'while false; do :; done'"),
    (
        "deny",
        "AC1 task0002: timeout -s TERM 2",
        "timeout -s TERM 2 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC1 task0002: timeout -k 5 60",
        "timeout -k 5 60 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC1 task0002: exec -a name",
        "exec -a name bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC1 task0002: stdbuf -o L",
        "stdbuf -o L bash -c 'while false; do :; done'",
    ),
    # task0002.md AC-2 (FR5, A6): attached and long forms of the same
    # value-taking options.
    ("deny", "AC2 task0002: env -uX", "env -uX bash -c 'while false; do :; done'"),
    (
        "deny",
        "AC2 task0002: env --unset=X",
        "env --unset=X bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: env --unset X",
        "env --unset X bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: env -C /tmp",
        "env -C /tmp bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: env --chdir=/tmp",
        "env --chdir=/tmp bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: env -S X=1",
        "env -S X=1 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: env -iu X",
        "env -iu X bash -c 'while false; do :; done'",
    ),
    ("deny", "AC2 task0002: nice -n5", "nice -n5 bash -c 'while false; do :; done'"),
    (
        "deny",
        "AC2 task0002: nice --adjustment=5",
        "nice --adjustment=5 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: nice --adjustment 5",
        "nice --adjustment 5 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: nice -n -5",
        "nice -n -5 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout -sTERM 2",
        "timeout -sTERM 2 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout --signal=TERM 2",
        "timeout --signal=TERM 2 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout --signal TERM 2",
        "timeout --signal TERM 2 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout -k5 60",
        "timeout -k5 60 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout --kill-after=5 60",
        "timeout --kill-after=5 60 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: timeout --kill-after 5 60",
        "timeout --kill-after 5 60 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: exec -aname",
        "exec -aname bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: stdbuf -oL",
        "stdbuf -oL bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: stdbuf --output=L",
        "stdbuf --output=L bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: stdbuf --output L",
        "stdbuf --output L bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC2 task0002: stdbuf -i0 -o L -e L",
        "stdbuf -i0 -o L -e L bash -c 'while false; do :; done'",
    ),
    # task0002.md AC-3 (FR5, A6): chains of prefixes, `--`, and a herestring
    # behind a value-taking prefix.
    (
        "deny",
        "AC3 task0002: two prefixes with values",
        "nice -n 5 timeout -k 5 60 bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC3 task0002: env value then nice value then sh -c",
        "env -u X nice -n 5 sh -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC3 task0002: nice -n 5 -- bash -c",
        "nice -n 5 -- bash -c 'while false; do :; done'",
    ),
    (
        "deny",
        "AC3 task0002: herestring behind a prefix with a value",
        "nice -n 5 bash <<< 'while false; do :; done'",
    ),
    (
        "deny",
        "AC3 task0002: timeout -s KILL 5 zsh -lc",
        "timeout -s KILL 5 zsh -lc 'while false; do :; done'",
    ),
    # task0002.md AC-4 (FR4, FR7): the option's value is not the executed
    # command, so these stay silent.
    (
        "silent",
        "AC4 task0002: env -u bash (bash is the value, not the command)",
        "env -u bash python3 -c 'while True: pass'",
    ),
    (
        "silent",
        "AC4 task0002: exec -a sh (sh is the value, not the command)",
        "exec -a sh python3 -c 'while True: pass'",
    ),
    (
        "silent",
        "AC4 task0002: timeout -s TERM 2 python3 -c",
        "timeout -s TERM 2 python3 -c 'while True: pass'",
    ),
    ("silent", "AC4 task0002: nice -n 5 echo while", "nice -n 5 echo while"),
    ("silent", "AC4 task0002: stdbuf -o L echo until", "stdbuf -o L echo until"),
    # Edge cases (task0001.md Test Notes)
    (
        "deny",
        "edge: pipe into a while-read loop ignores the loop's condition",
        "cat file | while read line; do :; done",
    ),
    ("silent", "edge: echo then until", "echo then until"),
    ("silent", "edge: # is not a comment mid-word", "a#b while"),
    ("silent", "edge: 2>&1 is not a separator", "true 2>&1 while"),
    (
        "silent",
        "edge: backslash-newline continuation before while",
        "true \\\nwhile",
    ),
    (
        "deny",
        "edge: <<- with a tab-indented delimiter",
        "bash <<-EOF\nwhile true; do :; done\n\tEOF",
    ),
    (
        "deny",
        "edge: two heredocs on one line",
        "cat <<A; bash <<B\nignored\nA\nwhile true; do :; done\nB",
    ),
    (
        "deny",
        "edge: a quoted heredoc delimiter",
        "bash <<'EOF'\nwhile true; do :; done\nEOF",
    ),
    (
        "deny",
        "edge: a loop in a command substitution inside a double-quoted echo argument",
        'echo "prefix $(while true; do :; done) suffix"',
    ),
    (
        "silent",
        "edge: bash -c with single-quoted data mentioning while",
        "bash -c \"echo 'while true'\"",
    ),
    (
        "silent",
        "edge: a second operand after the -c string that mentions while",
        "bash -c 'echo hello' while_is_just_an_argument",
    ),
]

# AC-4 (FR8; SPEC AC6; TM-5): every one of these leaves stdout and stderr
# empty with exit status 0.
UNDECIDABLE_COMMANDS = [
    ("top-level unterminated single quote", "echo 'unterminated"),
    ("top-level unterminated double quote", 'echo "unterminated'),
    ("top-level unterminated command substitution", "echo $(unterminated"),
    ("top-level unterminated backtick", "echo `unterminated"),
    ("top-level unterminated heredoc", "cat <<EOF\nno delimiter here"),
    ("heredoc operator with no delimiter", "cat <<"),
    (
        "an undecidable command that also contains a loop",
        "while true; do :; done; echo 'unterminated",
    ),
    (
        "nested far beyond the maximum depth",
        "echo " + "$(" * 400 + "while true; do :; done" + ")" * 400,
    ),
]

MALFORMED_PAYLOADS = [
    ("non-JSON input", "not json"),
    ("a JSON value that is not an object", "[]"),
    (
        "a tool_name other than Bash",
        {"tool_name": "Write", "tool_input": {"command": "while true; do :; done"}},
    ),
    ("tool_input missing", {"tool_name": "Bash"}),
    ("tool_input not an object", {"tool_name": "Bash", "tool_input": "nope"}),
    ("command missing", {"tool_name": "Bash", "tool_input": {}}),
    ("command empty", {"tool_name": "Bash", "tool_input": {"command": ""}}),
    ("command not a string", {"tool_name": "Bash", "tool_input": {"command": 5}}),
]

class TestLoopCommandGuardCases(unittest.TestCase):
    """AC-1, AC-2, AC-3: the CASES table drives the guard's core decision --
    deny when a while / until loop is reachable, silent otherwise."""

    def test_cases(self):
        for expected, label, command in CASES:
            with self.subTest(label=label):
                code, out, err = run_guard(
                    {"tool_name": "Bash", "tool_input": {"command": command}}
                )
                if expected == "deny":
                    assert_deny(self, code, out, err)
                else:
                    assert_silent(self, code, out, err)

    def test_deny_rows_are_identical_with_claude_batch_set_or_unset(self):
        """AC-1 (FR6): the result is identical whether CLAUDE_BATCH is set
        or unset -- the guard never reads it (task0001.md Design)."""
        deny_rows = [(label, cmd) for expected, label, cmd in CASES if expected == "deny"]
        self.assertTrue(deny_rows, "no deny rows to vary CLAUDE_BATCH against")
        env_with = dict(os.environ)
        env_with["CLAUDE_BATCH"] = "1"
        env_without = dict(os.environ)
        env_without.pop("CLAUDE_BATCH", None)
        for label, command in deny_rows:
            with self.subTest(label=label):
                payload = {"tool_name": "Bash", "tool_input": {"command": command}}
                code_with, out_with, err_with = run_guard(payload, env=env_with)
                code_without, out_without, err_without = run_guard(payload, env=env_without)
                assert_deny(self, code_with, out_with, err_with)
                assert_deny(self, code_without, out_without, err_without)
                self.assertEqual(out_with, out_without)


class TestMalformedInputFailsOpen(unittest.TestCase):
    """AC-4 (FR8; SPEC AC6; TM-5): every input the guard cannot even parse
    as a Bash payload leaves stdout and stderr empty, exit status 0."""

    def test_malformed_payloads(self):
        for label, payload in MALFORMED_PAYLOADS:
            with self.subTest(label=label):
                code, out, err = run_guard(payload)
                assert_silent(self, code, out, err)

    def test_undecidable_commands(self):
        for label, command in UNDECIDABLE_COMMANDS:
            with self.subTest(label=label):
                code, out, err = run_guard(
                    {"tool_name": "Bash", "tool_input": {"command": command}}
                )
                assert_silent(self, code, out, err)


# AC-5 (NFR1, NFR2; SPEC AC9; TM-3, TM-5)
BANNED_MODULES = {
    "subprocess", "multiprocessing", "pty", "socket",
    "urllib", "http", "ftplib", "smtplib",
}
# Dangerous *builtins*, checked only as bare-name calls (`compile(...)`) so
# a legitimate attribute call like `re.compile(...)` is not mistaken for the
# code-compiling builtin of the same name.
BANNED_BUILTIN_CALLS = {"eval", "exec", "compile", "open"}
# Dangerous *methods*, checked only as attribute calls (`os.system(...)`).
BANNED_ATTR_CALLS = {
    "system", "popen", "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve", "spawnvp",
    "execl", "execle", "execlp", "execv", "execve", "execvp", "fork",
}


def _imported_top_level_modules(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _call_name_kinds(tree):
    """Return (bare_names, attr_names): the callee names of every call in
    `tree`, split by whether the call was a bare name (`compile(...)`) or an
    attribute access (`re.compile(...)`, `os.system(...)`) -- so a builtin
    name is never confused with an unrelated module's method of the same
    name."""
    bare = set()
    attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                bare.add(func.id)
            elif isinstance(func, ast.Attribute):
                attrs.add(func.attr)
    return bare, attrs


class TestSourceIsSafeAndBounded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUARD_PATH.read_text()
        cls.tree = ast.parse(cls.source)

    def test_imports_are_standard_library_only(self):
        modules = _imported_top_level_modules(self.tree)
        self.assertTrue(modules, "the guard must import something")
        non_stdlib = modules - set(sys.stdlib_module_names)
        self.assertEqual(non_stdlib, set(), f"non-standard-library imports: {non_stdlib}")

    def test_imports_exclude_process_and_networking_modules(self):
        modules = _imported_top_level_modules(self.tree)
        self.assertEqual(modules & BANNED_MODULES, set())

    def test_source_calls_no_process_or_eval_function(self):
        bare, attrs = _call_name_kinds(self.tree)
        self.assertEqual(bare & BANNED_BUILTIN_CALLS, set())
        self.assertEqual(attrs & BANNED_ATTR_CALLS, set())

    def test_stderr_is_empty_for_every_case_in_the_suite(self):
        for expected, label, command in CASES:
            with self.subTest(label=label):
                _, _, err = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertEqual(err, "")
        for label, command in UNDECIDABLE_COMMANDS:
            with self.subTest(label=label):
                _, _, err = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertEqual(err, "")
        for label, payload in MALFORMED_PAYLOADS:
            with self.subTest(label=label):
                _, _, err = run_guard(payload)
                self.assertEqual(err, "")

    def test_a_large_heredoc_fed_to_a_non_shell_command_is_bounded_and_silent(self):
        body = "x" * (1024 * 1024)
        command = f"cat <<EOF\n{body}\nEOF"
        started = time.monotonic()
        code, out, err = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
        elapsed = time.monotonic() - started
        assert_silent(self, code, out, err)
        self.assertLess(elapsed, BOUNDED_TIME_SECONDS)

    def test_the_same_large_heredoc_fed_to_bash_with_a_loop_is_bounded_and_denied(self):
        body = "x" * (1024 * 1024)
        command = f"bash <<EOF\nwhile true; do :; done\n{body}\nEOF"
        started = time.monotonic()
        code, out, err = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
        elapsed = time.monotonic() - started
        assert_deny(self, code, out, err)
        self.assertLess(elapsed, BOUNDED_TIME_SECONDS)

    def test_several_hundred_levels_of_nesting_is_bounded_and_silent(self):
        nested = "true"
        for _ in range(400):
            nested = f"$({nested})"
        command = f"echo {nested}"
        started = time.monotonic()
        code, out, err = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
        elapsed = time.monotonic() - started
        assert_silent(self, code, out, err)
        self.assertLess(elapsed, BOUNDED_TIME_SECONDS)

    def test_running_the_same_input_twice_gives_identical_output(self):
        deny_payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "while true; do sleep 1; done"},
        }
        silent_payload = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        for payload in (deny_payload, silent_payload):
            with self.subTest(payload=payload):
                first = run_guard(payload)
                second = run_guard(payload)
                self.assertEqual(first, second)

class TestDocumentationMatchesRegistration(unittest.TestCase):
    """AC-7 (FR12, FR13; SPEC AC10): the README and hook-tests.md rule stay
    in sync with the guard's registration in hooks.json. Checks are
    structural -- presence and relative order -- and do not pin exact
    wording (task0001.md Test Notes)."""

    @classmethod
    def setUpClass(cls):
        cls.readme = README_PATH.read_text()
        cls.hook_tests_rule = HOOK_TESTS_RULE_PATH.read_text()
        cls.hooks_config = json.loads(HOOKS_JSON_PATH.read_text())

    def _bash_group_order(self):
        for group in self.hooks_config["hooks"]["PreToolUse"]:
            if group.get("matcher") == "Bash":
                return [
                    hook.get("command", "").rsplit("/", 1)[-1]
                    for hook in group["hooks"]
                ]
        raise AssertionError("no PreToolUse(Bash) matcher group in hooks.json")

    def test_readme_has_a_guardrail_table_row_for_the_new_hook(self):
        for line in self.readme.splitlines():
            if "hooks/loop-command-guard.py" in line and line.strip().startswith("|"):
                self.assertIn("PreToolUse(Bash)", line)
                return
        self.fail("no guardrail table row names hooks/loop-command-guard.py")

    def test_readme_execution_order_sentence_matches_hooks_json_order(self):
        order = self._bash_group_order()
        self.assertIn("loop-command-guard.py", order)
        sentence = None
        for line in self.readme.splitlines():
            if (
                "interpreter-mismatch-guard.py" in line
                and "destructive-guard.py" in line
                and not line.strip().startswith("|")
            ):
                sentence = line
                break
        self.assertIsNotNone(sentence, "no PreToolUse(Bash) execution-order sentence found")
        positions = {name: sentence.find(name) for name in order if name in sentence}
        self.assertIn("loop-command-guard.py", positions)
        self.assertLess(
            positions["interpreter-mismatch-guard.py"], positions["loop-command-guard.py"]
        )
        self.assertLess(positions["loop-command-guard.py"], positions["destructive-guard.py"])
        named_in_order = [n for n in order if n in positions]
        self.assertEqual(sorted(named_in_order, key=lambda n: positions[n]), named_in_order)

    def test_hook_tests_rule_has_a_loop_command_guard_section(self):
        self.assertIn("loop-command-guard", self.hook_tests_rule)
        self.assertIn(
            "python3 -m unittest tests.test_loop_command_guard", self.hook_tests_rule
        )

    def test_hook_tests_rule_describes_the_case_format(self):
        for token in ("期待する判定", "ラベル", "コマンド", "deny", "silent"):
            self.assertIn(token, self.hook_tests_rule)


if __name__ == "__main__":
    unittest.main()

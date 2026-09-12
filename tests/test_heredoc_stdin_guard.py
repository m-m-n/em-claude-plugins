"""Contract tests for `em-workflow/hooks/heredoc-stdin-guard.py`
(feature-docs/heredoc-stdin-guard/tasks/task0001.md).

Every case drives the guard as a subprocess with PreToolUse JSON on
standard input -- the same contract Claude Code uses (test/README.md) --
and asserts on standard output and exit status. No test imports the guard
as a module (IMPLEMENTATION.md "Test style").

Covers task0001 Acceptance Criteria:

- AC-1 (FR2, FR3, FR5): a command containing a heredoc and no head-position
  stdin redirection is rewritten -- the cut-off token, a newline, then the
  original command text unchanged; every other `tool_input` field is
  reproduced with its original value and type.
- AC-2 (FR2): no heredoc operator, and a here-string-only candidate, both
  produce empty stdout.
- AC-3 (FR4): a command whose stdin is already redirected at its head --
  including the guard's own cut-off token -- produces empty stdout, and
  feeding the guard its own output a second time never doubles the token.
- AC-4 (FR6): malformed input, a missing/empty/non-string command, and a
  non-Bash tool name, each fail open (empty stdout, exit 0).
- AC-5 (FR3): a rewritten command, actually executed, writes the heredoc
  body byte-for-byte -- content, interior newlines and terminator intact --
  and touches no file outside its own temporary directory.
- AC-6 (NFR5): across every case here, stdout never carries a
  permission-decision member, and exit status is always 0.
- AC-7 (NFR1, NFR2): the guard's own source imports only the standard
  library.
"""

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "heredoc-stdin-guard.py"

CUTOFF = "exec < /dev/null"


def run_guard(payload=None, stdin_text=None):
    if payload is not None:
        stdin_text = json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input="" if stdin_text is None else stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


def assert_no_rewrite(test, result):
    test.assertEqual(result.returncode, 0, result.stderr)
    test.assertEqual(result.stdout, "", f"expected empty stdout, got: {result.stdout!r}")
    test.assertEqual(result.stderr, "")


def assert_rewrite(test, result, original_command):
    test.assertEqual(result.returncode, 0, result.stderr)
    test.assertEqual(result.stderr, "")
    data = json.loads(result.stdout)
    test.assertEqual(set(data.keys()), {"hookSpecificOutput"})
    out = data["hookSpecificOutput"]
    test.assertEqual(set(out.keys()), {"updatedInput"})
    test.assertNotIn("permissionDecision", out)
    updated = out["updatedInput"]
    test.assertEqual(updated["command"], f"{CUTOFF}\n{original_command}")
    return updated


# --- AC-1: rewrite target, two payload variants -----------------------


class TestRewritesBareHeredocWrite(unittest.TestCase):
    """AC-1, variant 1: a bare heredoc write with no other reader."""

    COMMAND = "cat > /tmp/heredoc-guard-example.txt <<'EOF'\nhello\nworld\nEOF\n"

    def test_rewrites_command_and_preserves_other_fields(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": self.COMMAND,
                "description": "write an example file",
                "timeout": 120000,
            },
        }
        result = run_guard(payload)
        updated = assert_rewrite(self, result, self.COMMAND)
        self.assertEqual(updated["description"], "write an example file")
        self.assertEqual(updated["timeout"], 120000)
        self.assertIsInstance(updated["timeout"], int)


class TestRewritesHeredocFollowedByStdinReader(unittest.TestCase):
    """AC-1, variant 2: a heredoc followed by a stdin-reading command
    (a harmless `cat` placeholder standing in for `codex exec ...`)."""

    COMMAND = (
        "cat > /tmp/heredoc-guard-input.txt <<'EOF'\n"
        "data\n"
        "EOF\n"
        "cat\n"
    )

    def test_rewrites_command(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": self.COMMAND}}
        result = run_guard(payload)
        assert_rewrite(self, result, self.COMMAND)


# --- AC-2: no heredoc operator / here-string only ----------------------


class TestNoRewriteWithoutHeredoc(unittest.TestCase):
    def test_plain_command_produces_no_rewrite(self):
        result = run_guard({"tool_name": "Bash", "tool_input": {"command": "ls -l"}})
        assert_no_rewrite(self, result)

    def test_here_string_alone_is_not_mistaken_for_a_heredoc(self):
        result = run_guard(
            {"tool_name": "Bash", "tool_input": {"command": "cat <<< 'just a string'"}}
        )
        assert_no_rewrite(self, result)


# --- AC-3: already redirected at the head / idempotency ----------------


class TestNoRewriteWhenAlreadyRedirected(unittest.TestCase):
    def test_command_already_starting_with_the_cutoff_token_is_not_rewritten(self):
        command = (
            f"{CUTOFF}\n"
            "cat > /tmp/heredoc-guard-example.txt <<'EOF'\n"
            "hello\n"
            "EOF\n"
        )
        result = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
        assert_no_rewrite(self, result)

    def test_command_closed_from_the_head_with_a_plain_redirect_is_not_rewritten(self):
        command = (
            "cat < /dev/null\n"
            "cat > /tmp/heredoc-guard-example.txt <<'EOF'\n"
            "hello\n"
            "EOF\n"
        )
        result = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
        assert_no_rewrite(self, result)

    def test_feeding_the_guards_own_output_back_never_doubles_the_token(self):
        original = "cat > /tmp/heredoc-guard-example.txt <<'EOF'\nhello\nEOF\n"
        first = run_guard({"tool_name": "Bash", "tool_input": {"command": original}})
        rewritten = assert_rewrite(self, first, original)

        second = run_guard(
            {"tool_name": "Bash", "tool_input": {"command": rewritten["command"]}}
        )
        assert_no_rewrite(self, second)


# --- AC-4: fail open ----------------------------------------------------


class TestFailsOpen(unittest.TestCase):
    def test_malformed_json_produces_no_rewrite(self):
        result = run_guard(stdin_text="{ this is not valid json")
        assert_no_rewrite(self, result)

    def test_missing_command_field_produces_no_rewrite(self):
        result = run_guard({"tool_name": "Bash", "tool_input": {}})
        assert_no_rewrite(self, result)

    def test_empty_command_produces_no_rewrite(self):
        result = run_guard({"tool_name": "Bash", "tool_input": {"command": ""}})
        assert_no_rewrite(self, result)

    def test_non_string_command_produces_no_rewrite(self):
        result = run_guard({"tool_name": "Bash", "tool_input": {"command": 12345}})
        assert_no_rewrite(self, result)

    def test_non_bash_tool_name_produces_no_rewrite(self):
        command = "cat > /tmp/x <<'EOF'\nhi\nEOF\n"
        result = run_guard({"tool_name": "Write", "tool_input": {"command": command}})
        assert_no_rewrite(self, result)

    def test_unterminated_quote_is_undecidable_and_produces_no_rewrite(self):
        result = run_guard(
            {"tool_name": "Bash", "tool_input": {"command": "echo 'unterminated <<EOF"}}
        )
        assert_no_rewrite(self, result)

    def test_empty_stdin_produces_no_rewrite(self):
        result = run_guard(stdin_text="")
        assert_no_rewrite(self, result)


# --- AC-5: execution test -- heredoc body survives byte-for-byte -------


class TestExecutedRewriteWritesTheOriginalHeredocBodyExactly(unittest.TestCase):
    def test_body_is_preserved_byte_for_byte_within_a_temp_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.txt"
            body = "line one\n\tline two with a leading tab\nline three\n"
            command = f"cat > {target} <<'HEREDOC_MARKER'\n{body}HEREDOC_MARKER\n"

            result = run_guard({"tool_name": "Bash", "tool_input": {"command": command}})
            updated = assert_rewrite(self, result, command)

            run = subprocess.run(
                ["bash", "-c", updated["command"]],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(target.read_text(), body)

            other_files = [p for p in Path(tmp).iterdir()]
            self.assertEqual(other_files, [target])


# --- AC-6 / AC-7: cross-cutting properties over the whole case corpus ---


class TestOutputNeverCarriesAPermissionDecision(unittest.TestCase):
    """AC-6: over every case pattern used above, stdout is either empty or
    carries only `updatedInput` -- never a permission-decision member --
    and exit status is always 0."""

    CASES = [
        {"tool_name": "Bash", "tool_input": {"command": "ls -l"}},
        {"tool_name": "Bash", "tool_input": {"command": "cat <<< 'x'"}},
        {
            "tool_name": "Bash",
            "tool_input": {"command": "cat > /tmp/x.txt <<'EOF'\nhi\nEOF\n"},
        },
        {"tool_name": "Bash", "tool_input": {"command": f"{CUTOFF}\ncat <<'EOF'\nhi\nEOF\n"}},
        {"tool_name": "Bash", "tool_input": {"command": ""}},
        {"tool_name": "Write", "tool_input": {"command": "cat <<'EOF'\nhi\nEOF\n"}},
    ]

    def test_no_case_ever_emits_a_permission_decision_and_exit_is_always_zero(self):
        for payload in self.CASES:
            with self.subTest(command=payload["tool_input"].get("command")):
                result = run_guard(payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                if result.stdout:
                    data = json.loads(result.stdout)
                    self.assertNotIn(
                        "permissionDecision", json.dumps(data),
                    )
                    self.assertEqual(set(data.keys()), {"hookSpecificOutput"})


class TestGuardImportsOnlyTheStandardLibrary(unittest.TestCase):
    """AC-7: the guard's decision path depends on nothing outside the
    Python standard library."""

    def test_only_standard_library_imports(self):
        source = GUARD_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()

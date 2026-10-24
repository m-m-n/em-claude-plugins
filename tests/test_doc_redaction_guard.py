"""Contract tests for `em-workflow/hooks/doc-redaction-guard.py`.

Every case drives the guard as a subprocess with PreToolUse JSON on standard
input and asserts on standard output. `deny` cases: a Notion URL or the home
directory path in new content under `feature-docs/` or `test-docs/`. `silent`
cases: anything else, including input the guard cannot read.

Standard library only, per test/README.md.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "doc-redaction-guard.py"
HOOKS_JSON_PATH = REPO_ROOT / "em-workflow" / "hooks" / "hooks.json"

HOME = "/home/alice"
DOC = "/repo/feature-docs/f/SPEC.md"


def run_guard(payload, home=HOME):
    env = dict(os.environ, HOME=home)
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write(file_path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


def edit(file_path, new_string, old_string="x"):
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": old_string, "new_string": new_string},
    }


def multi_edit(file_path, *new_strings):
    return {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": file_path,
            "edits": [{"old_string": "x", "new_string": s} for s in new_strings],
        },
    }


# (expected, label, payload)
CASES = [
    ("deny", "notion.so URL", write(DOC, "Notion タスク: https://www.notion.so/abc123")),
    ("deny", "app.notion.com URL", write(DOC, "https://app.notion.com/p/Title-abc123")),
    ("deny", "notion.site URL", write(DOC, "see https://team.notion.site/page")),
    ("deny", "notion URL upper case", write(DOC, "HTTPS://WWW.NOTION.SO/abc")),
    ("deny", "home path with child", write(DOC, "file: /home/alice/src/x.py")),
    ("deny", "home path alone", write(DOC, "cd /home/alice")),
    ("deny", "home path followed by quote", write(DOC, 'path: "/home/alice"')),
    ("deny", "test-docs dir", write("/repo/test-docs/f/task0001.tests.yaml", "/home/alice/x")),
    ("deny", "relative doc path", write("feature-docs/f/workflow.yaml", "https://notion.so/a")),
    ("deny", "worktree doc path", write("/repo/.claude/worktrees/t/feature-docs/f/x.md", "/home/alice/a")),
    ("deny", "Edit new_string", edit(DOC, "https://www.notion.so/abc")),
    ("deny", "MultiEdit second edit", multi_edit(DOC, "ok", "/home/alice/a")),
    ("silent", "outside doc dirs", write("/repo/src/main.py", "https://www.notion.so/abc /home/alice/a")),
    ("silent", "doc dir name as file name", write("/repo/feature-docs", "/home/alice/a")),
    ("silent", "placeholder home", write(DOC, "rm -rf /home/user/valuable")),
    ("silent", "home prefix of longer name", write(DOC, "/home/alice2/x /home/alicea")),
    ("silent", "tilde path", write(DOC, "~/src/x.py")),
    ("silent", "relative path", write(DOC, "em-workflow/hooks/x.py")),
    ("silent", "notion word without URL", write(DOC, "Notion タスク: <notion-url>")),
    ("silent", "other host containing notion", write(DOC, "https://notion.example.com/a https://notionso.com/")),
    ("silent", "Edit old_string only", edit(DOC, "<notion-url>", old_string="https://www.notion.so/abc")),
    ("silent", "other tool", {"tool_name": "Bash", "tool_input": {"command": "echo /home/alice"}}),
]


class CasesTest(unittest.TestCase):
    def test_cases(self):
        for expected, label, payload in CASES:
            with self.subTest(label=label):
                code, out, err = run_guard(payload)
                self.assertEqual(code, 0)
                self.assertEqual(err, "")
                if expected == "silent":
                    self.assertEqual(out, "")
                    continue
                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["hookEventName"], "PreToolUse")
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertTrue(
                    decision["permissionDecisionReason"].startswith("[doc-redaction-guard]")
                )


class HomeTest(unittest.TestCase):
    def test_shallow_home_is_not_matched(self):
        for home in ("/", "/root", ""):
            with self.subTest(home=home):
                self.assertEqual(run_guard(write(DOC, "/root/x"), home=home)[1], "")

    def test_trailing_slash_in_home(self):
        self.assertNotEqual(run_guard(write(DOC, "/home/alice/x"), home="/home/alice/")[1], "")


class MalformedInputTest(unittest.TestCase):
    def test_malformed_payloads_are_silent(self):
        for payload in (
            "",
            "not json",
            "[]",
            json.dumps({"tool_name": "Write"}),
            json.dumps({"tool_name": "Write", "tool_input": "x"}),
            json.dumps({"tool_name": "Write", "tool_input": {"file_path": 1, "content": "x"}}),
            json.dumps({"tool_name": "Write", "tool_input": {"file_path": DOC, "content": 1}}),
            json.dumps({"tool_name": "MultiEdit", "tool_input": {"file_path": DOC, "edits": "x"}}),
        ):
            with self.subTest(payload=payload):
                self.assertEqual(run_guard(payload), (0, "", ""))


class RegistrationTest(unittest.TestCase):
    def test_registered_for_write_edit_multiedit(self):
        hooks = json.loads(HOOKS_JSON_PATH.read_text())["hooks"]["PreToolUse"]
        commands = [
            h["command"]
            for entry in hooks
            if entry["matcher"] == "Write|Edit|MultiEdit"
            for h in entry["hooks"]
        ]
        self.assertTrue(any("doc-redaction-guard.py" in c for c in commands))


if __name__ == "__main__":
    unittest.main()

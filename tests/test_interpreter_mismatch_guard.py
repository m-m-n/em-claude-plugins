"""Contract tests for `em-workflow/hooks/interpreter-mismatch-guard.py`.

Every case drives the guard as a subprocess with PreToolUse JSON on
standard input and asserts on standard output. The guard reads the target
file, so each case runs against fixtures built in a temporary directory
that is passed as the payload's `cwd`; `{DIR}` in a command is replaced
with that directory.

`deny` cases guard the point of the hook: a non-shell script handed to a
shell must be stopped. `silent` cases guard the cost: the guard must say
nothing whenever the target is a shell script or cannot be settled, so it
never stalls an unattended run by mistake.

Standard library only, per test/README.md.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "interpreter-mismatch-guard.py"

FIXTURES = {
    "scripts/validate.py": '#!/usr/bin/env python3\n"""doc"""\nimport argparse\n',
    "scripts/tool.sh": "#!/usr/bin/env bash\necho hi\n",
    "noshebang.py": "import argparse\n",
    "envs-python": "#!/usr/bin/env -S python3 -u\nimport sys\n",
    "tool.js": "#!/usr/bin/env node\nconsole.log(1)\n",
    "py-noext": "#!/usr/bin/python3.12\nimport sys\n",
    "sh-noext": "#!/bin/sh\necho hi\n",
    "bash-shebang.py": "#!/bin/bash\necho hi\n",
    "plain.sh": "echo hi\n",
}

# (expected, label, command)
CASES = [
    ("deny", "今回の事故の形", "git status --short; bash scripts/../scripts/validate.py --help 2>&1 | head -5; python3 scripts/validate.py --help"),
    ("deny", "shebang が python3", "bash scripts/validate.py"),
    ("deny", "shebang 無しの .py", "bash noshebang.py"),
    ("deny", "env -S 経由の python", "bash envs-python"),
    ("deny", "shebang が node", "sh tool.js"),
    ("deny", "拡張子の無い python スクリプト", "zsh py-noext"),
    ("deny", "クォートされたパス", "bash 'scripts/validate.py'"),
    ("deny", "オプションの後ろ", "bash -x -e scripts/validate.py"),
    ("deny", "-n でも読むのは python", "bash -n scripts/validate.py"),
    ("deny", "-- の後ろ", "bash -- scripts/validate.py"),
    ("deny", "source", "source scripts/validate.py"),
    ("deny", "ドット", ". scripts/validate.py"),
    ("deny", "env 代入の後ろ", "FOO=1 bash scripts/validate.py"),
    ("deny", "ラッパーの後ろ", "nohup bash scripts/validate.py"),
    ("deny", "&& の後ろ", "cd . && bash scripts/validate.py"),
    ("deny", "絶対パス", "bash {DIR}/scripts/validate.py"),
    ("deny", "改行区切りの 2 行目", "echo a\nbash scripts/validate.py"),
    ("deny", "ヒアドキュメントの後ろ", "cat <<'EOF' > x\nhello\nEOF\nbash scripts/validate.py"),
    ("silent", "シェルスクリプト", "bash scripts/tool.sh"),
    ("silent", "拡張子無しのシェルスクリプト", "bash sh-noext"),
    ("silent", "shebang が bash の .py", "bash bash-shebang.py"),
    ("silent", "shebang 無しの .sh", "bash plain.sh"),
    ("silent", "python3 で実行", "python3 scripts/validate.py"),
    ("silent", "bash -c", "bash -c 'python3 scripts/validate.py'"),
    ("silent", "bash -lc", "bash -lc scripts/validate.py"),
    ("silent", "bash -s は標準入力", "bash -s scripts/validate.py < x"),
    ("silent", "bash --version", "bash --version"),
    ("silent", "標準入力", "bash < scripts/validate.py"),
    ("silent", "変数渡し", "bash \"$SCRIPT\""),
    ("silent", "変数を含むパス", "bash $DIR/validate.py"),
    ("silent", "glob", "bash scripts/*.py"),
    ("silent", "存在しないファイル", "bash missing.py"),
    ("silent", "ディレクトリ", "bash scripts"),
    ("silent", "クォート内の文字列", "echo 'bash scripts/validate.py'"),
    ("silent", "コメント内", "true # bash scripts/validate.py"),
    ("silent", "ヒアドキュメント本文", "cat <<'EOF'\nbash scripts/validate.py\nEOF"),
    ("silent", "ヒアストリング", "bash <<< 'echo hi'"),
    ("silent", "grep の引数", "grep -n bash scripts/validate.py"),
    ("silent", "bash の名前を含む別コマンド", "bashcov scripts/validate.py"),
    ("silent", "閉じないクォート", "bash 'scripts/validate.py"),
]


def run_guard(payload):
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


class TestInterpreterMismatchGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = cls._tmp.name
        for rel, body in FIXTURES.items():
            path = Path(cls.dir) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_cases(self):
        for expected, label, command in CASES:
            with self.subTest(label=label):
                code, out = run_guard(
                    {
                        "tool_name": "Bash",
                        "cwd": self.dir,
                        "tool_input": {"command": command.replace("{DIR}", self.dir)},
                    }
                )
                self.assertEqual(code, 0)
                if expected == "silent":
                    self.assertEqual(out, "")
                    continue
                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["hookEventName"], "PreToolUse")
                self.assertEqual(decision["permissionDecision"], expected)

    def test_reason_names_the_interpreter_to_use(self):
        _, out = run_guard(
            {"tool_name": "Bash", "cwd": self.dir, "tool_input": {"command": "bash scripts/validate.py"}}
        )
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("python3 scripts/validate.py", reason)

    def test_malformed_input_fails_open(self):
        for payload in (
            "not json",
            "[]",
            {"tool_name": "Write", "tool_input": {"command": "bash scripts/validate.py"}},
            {"tool_name": "Bash", "tool_input": {"command": ""}},
            {"tool_name": "Bash", "tool_input": {}},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(run_guard(payload), (0, ""))


if __name__ == "__main__":
    unittest.main()

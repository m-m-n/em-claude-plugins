"""Contract tests for `scripts/codex-hook-interactive-guard.py`, which ships
as two byte-identical copies: one in `em-workflow/` and one in `em-review/`.

Every behavior test runs a copy as a separate process: the PreToolUse JSON
goes in on standard input, and the test checks standard output, standard
error and the exit status. The hook module is never imported, so no
bytecode cache is left inside a distributed plugin directory.

`deny` cases guard the point of the hook: a launch of an interpreter or
shell in interactive mode must be stopped. `silent` cases guard the cost:
the hook must say nothing whenever the launch is not interactive or cannot
be settled, so a misreading never stalls a Codex review.

One CASES table drives both copies. Standard library only, per
test/README.md.
"""

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_NAME = "codex-hook-interactive-guard.py"
HOOK_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / "scripts" / HOOK_NAME,
    "em-review": REPO_ROOT / "em-review" / "scripts" / HOOK_NAME,
}

# (expected, label, command)
CASES = [
    # AC-1: launches with -i (FR6, FR8, FR9)
    ("deny", "python3 -i", "python3 -i"),
    ("deny", "-c より前の -i", "python3 -B -i -c 'x'"),
    ("deny", "bash -i", "bash -i"),
    ("deny", "束ねた -Bi", "python3 -Bi"),
    ("deny", "node -i", "node -i"),
    ("deny", "node --interactive", "node --interactive"),
    ("deny", "lua -i", "lua -i"),
    ("deny", "python3.14 -i", "python3.14 -i"),
    ("deny", "&& の後ろ", "cd x && python3 -i"),
    ("deny", "bash -lc のリテラル", "bash -lc 'python3 -i'"),
    # AC-2: launches with no program source (FR7)
    ("deny", "python3 単独", "python3"),
    ("deny", "node 単独", "node"),
    ("deny", "python3 -B 単独", "python3 -B"),
    ("deny", "ruby 単独", "ruby"),
    ("deny", "perl 単独", "perl"),
    ("deny", "deno 単独", "deno"),
    ("deny", "irb 単独", "irb"),
    ("deny", "ipython 単独", "ipython"),
    ("deny", "bash -s 単独", "bash -s"),
    # AC-3: not interactive (FR6, FR8, FR9, FR10, NFR2)
    ("silent", "python3 -c", "python3 -c 'print(1)'"),
    ("silent", "python3 script.py", "python3 script.py"),
    ("silent", "python3 - と heredoc", "python3 - <<EOF\nprint(1)\nEOF"),
    ("silent", "python3 と heredoc", "python3 <<EOF\nprint(1)\nEOF"),
    ("silent", "パイプの右側", "cmd | python3"),
    ("silent", "標準入力のリダイレクト", "python3 < f"),
    ("silent", "python3 --version", "python3 --version"),
    ("silent", "python3 -VV", "python3 -VV"),
    ("silent", "node -v", "node -v"),
    ("silent", "node --test", "node --test"),
    ("silent", "node --check f.js", "node --check f.js"),
    ("silent", "perl -v", "perl -v"),
    ("silent", "オペランドより後ろの -i", "python3 script.py -i"),
    ("silent", "perl -i は in-place 編集", "perl -i -pe 's/a/b/' f"),
    ("silent", "ruby -i は in-place 編集", "ruby -i -pe 'x' f"),
    ("silent", "sed -i", "sed -i 's/a/b/' f"),
    ("silent", "php -i", "php -i"),
    ("silent", "python3-config は対象外", "python3-config"),
    ("silent", "シングルクォート内", "echo 'python3 -i'"),
    ("silent", "ダブルクォート内", 'echo "python3 -i"'),
    ("silent", "コメント行", "# python3 -i"),
    ("silent", "行末コメント", "true # python3 -i"),
    ("silent", "heredoc 本文", "cat <<'EOF'\npython3 -i\nEOF"),
    ("silent", "heredoc 本文の引数なし起動", "cat <<EOF\npython3\nEOF"),
    ("silent", "<<- の heredoc 本文", "cat <<-EOF\n\tpython3 -i\n\tEOF"),
    ("silent", "第 2 段の bash -c は評価しない", "bash -c \"bash -c 'python3 -i'\""),
    ("silent", "sh -c の中の bash -lc の中", "sh -c 'bash -lc \"python3 -i\"'"),
    # AC-4: undecidable input passes (FR11)
    ("silent", "env -i", "env -i python3"),
    ("silent", "env -i と -i", "env -i python3 -i"),
    ("silent", "閉じていないクォート", "python3 -i 'abc"),
    ("silent", "閉じていないダブルクォート", 'echo "abc; python3 -i'),
    ("silent", "終端のない heredoc", "cat <<EOF\npython3 -i"),
    ("silent", "heredoc の本文が無い", "python3 -i <<EOF"),
    ("silent", "nice -n", "nice -n 5 python3 -i"),
    ("silent", "timeout -s", "timeout -s KILL 5 python3 -i"),
    ("silent", "command -v", "command -v python3"),
    ("silent", "sudo -u", "sudo -u x python3 -i"),
    ("silent", "exec -a", "exec -a x python3 -i"),
    ("silent", "time -p", "time -p python3 -i"),
    ("silent", "末尾のバックスラッシュ", "python3 -i \\"),
    ("silent", "空のコマンド", ""),
    ("silent", "空白だけ", "   \t "),
    # FR8: the interpreter name
    ("deny", "ipython3", "ipython3"),
    ("deny", "node22", "node22"),
    ("deny", "lua5.4 -i", "lua5.4 -i"),
    ("deny", "python -i", "python -i"),
    ("deny", "python3.N 単独", "python3.13"),
    ("deny", "絶対パス", "/usr/bin/python3 -i"),
    ("deny", "相対パス", "./venv/bin/python -i"),
    ("deny", "クォートされたコマンド語", "'python3' '-i'"),
    ("deny", "ダブルクォートされたコマンド語", '"python3" "-i"'),
    ("deny", "バックスラッシュ付きコマンド語", "\\python3 -i"),
    ("silent", "bashcov", "bashcov -i"),
    ("silent", "pythonista", "pythonista -i"),
    ("silent", "python3.14-config", "python3.14-config --includes"),
    ("silent", "node-gyp", "node-gyp rebuild"),
    ("silent", "luac", "luac -p x.lua"),
    ("silent", "shellcheck", "shellcheck -i x.sh"),
    ("silent", "ruby 拡張子付き", "ruby.rb"),
    ("silent", "ディレクトリ", "python3/"),
    # FR9: where a launch may sit
    ("deny", "; の後ろ", "echo a; python3 -i"),
    ("deny", "|| の後ろ", "false || python3"),
    ("deny", "改行の後ろ", "echo a\npython3 -i"),
    ("deny", "& の前", "python3 -i &"),
    ("deny", "括弧の中", "(python3 -i)"),
    ("deny", "括弧の中の cd", "(cd x && python3 -i)"),
    ("deny", "heredoc 本文の後ろ", "cat <<EOF\nbody\nEOF\npython3 -i"),
    ("deny", "heredoc の後ろの引数なし起動", "cat <<EOF\nbody\nEOF\npython3"),
    ("deny", "タブ区切り", "python3\t-i"),
    ("deny", "行継続", "python3 \\\n -i"),
    ("deny", "末尾の ;", "python3 -i;"),
    ("deny", "代入の後ろ", "PYTHONSTARTUP=x python3 -i"),
    ("deny", "env 代入の後ろ", "env FOO=1 python3 -i"),
    ("deny", "nohup", "nohup python3 -i"),
    ("deny", "timeout DURATION", "timeout 5 python3 -i"),
    ("deny", "sudo", "sudo python3 -i"),
    ("deny", "command", "command python3 -i"),
    ("deny", "exec", "exec python3 -i"),
    ("deny", "time", "time python3 -i"),
    ("deny", "nice", "nice python3 -i"),
    ("deny", "ラッパーの重ね掛け", "env FOO=1 nohup timeout 5 python3 -i"),
    ("deny", "cd の後ろの nohup", "cd x && nohup python3 &"),
    ("deny", "パイプの左側", "python3 | cat"),
    ("deny", "&& でパイプが切れる", "echo x | cat && python3"),
    ("deny", "; でパイプが切れる", "echo x | cat; python3"),
    ("deny", "stdout のリダイレクトは入力ではない", "python3 >out.txt"),
    ("deny", "stderr のリダイレクトは入力ではない", "python3 2>/dev/null"),
    ("deny", "2>&1 は入力ではない", "python3 2>&1"),
    ("deny", "&> は入力ではない", "python3 &>out.txt"),
    ("deny", "パイプの右側でも -i は拒否", "echo hi | python3 -i"),
    ("deny", "入力を渡しても -i は拒否", "python3 -i < f"),
    ("silent", "||の前", "python3 script.py || true"),
    ("silent", "括弧の右側のパイプ", "(echo a; echo b) | python3"),
    ("silent", "パイプの右側の括弧", "echo a | (python3)"),
    ("silent", "パイプの右側のオプションだけ", "echo x | python3 -B"),
    ("silent", "パイプの右側の bash -s", "echo ls | bash -s"),
    ("silent", "0< のリダイレクト", "python3 0< f"),
    ("silent", "<<< のリダイレクト", "python3 <<< 'print(1)'"),
    ("silent", "<<< と 0 の指定", "python3 0<<<'print(1)'"),
    ("silent", "/dev/null からの入力", "python3 </dev/null"),
    ("silent", "<& による入力", "python3 <&3"),
    ("silent", "bash -s と入力", "bash -s < f"),
    ("silent", "引数付きの bash -s", "bash -s arg"),
    ("silent", "- のオペランド", "python3 -"),
    ("silent", "bash -", "bash -"),
    ("silent", "文字列内のセミコロン", 'printf "%s" "x; python3 -i"'),
    ("silent", "単語途中のクォート内のセミコロン", 'echo a"b; python3 -i"c'),
    ("silent", "単語途中のシングルクォート", "echo a'b; python3 -i'c"),
    ("silent", "echo の引数", "echo python3 -i"),
    ("silent", "git commit のメッセージ", 'git commit -m "python3 -i"'),
    ("silent", "grep の引数", "grep -n 'python3 -i' f"),
    ("silent", "heredoc 本文内の引用符", "cat <<EOF\nit's python3 -i\nEOF"),
    ("silent", "コメント内のアポストロフィ", "python3 script.py # don't"),
    ("silent", "コメント内の ; ", "echo a # b; python3 -i"),
    ("silent", "パラメータ展開内の #", "echo ${x#y}; python3 script.py"),
    ("silent", "$# は単語の途中", "echo $# python3 -i"),
    # Reading options (FR6, FR7)
    ("deny", "-ic は -i のあと -c", "python3 -ic 'x'"),
    ("deny", "-iB", "python3 -iB"),
    ("deny", "-W の値の後ろの -i", "python3 -W ignore -i"),
    ("deny", "-X の値の後ろの -i", "python3 -Xdev -i"),
    ("deny", "-i とスクリプト", "python3 -i script.py"),
    ("deny", "-B -i とスクリプト", "python3 -B -i script.py"),
    ("deny", "sh -i", "sh -i"),
    ("deny", "zsh -i", "zsh -i"),
    ("deny", "dash -i", "dash -i"),
    ("deny", "ksh -i", "ksh -i"),
    ("deny", "bash -ic", "bash -ic 'x'"),
    ("deny", "bash -o の値の後ろの -i", "bash -o pipefail -i"),
    ("deny", "bash --norc -i", "bash --norc -i"),
    ("deny", "bash --rcfile の値の後ろの -i", "bash --rcfile x -i"),
    ("deny", "lua -l の値の後ろの -i", "lua -l mod -i"),
    ("deny", "lua -i とスクリプト", "lua -i script.lua"),
    ("deny", "node -r の値の後ろの -i", "node -r ./x.js -i"),
    ("deny", "node --require の値の後ろの -i", "node --require ./x.js -i"),
    ("deny", "python3 -v は verbose", "python3 -v"),
    ("deny", "python3 -m の前の -i", "python3 -i -m http.server"),
    ("deny", "bash -o の値だけ", "bash -o pipefail"),
    ("deny", "bash -x 単独", "bash -x"),
    ("deny", "ruby -I の値だけ", "ruby -I lib"),
    ("deny", "ruby -w 単独", "ruby -w"),
    ("deny", "perl -w 単独", "perl -w"),
    ("deny", "node -r の値だけ", "node -r ./x.js"),
    ("deny", "node --require の値だけ", "node --require ./x.js"),
    ("deny", "ruby -i 単独は引数なし起動", "ruby -i"),
    ("deny", "perl -i 単独は引数なし起動", "perl -i.bak"),
    ("deny", "-- だけ", "python3 --"),
    ("silent", "-c の値の後ろの -i", "python3 -c 'x' -i"),
    ("silent", "-m の値の後ろの -i", "python3 -m http.server -i"),
    ("silent", "-m pytest -i", "python3 -m pytest -i"),
    ("silent", "-- の後ろは引数", "python3 -- -i"),
    ("silent", "-- の後ろのスクリプト", "python3 -B -- script.py -i"),
    ("silent", "-ci は -c の値が i", "python3 -ci"),
    ("silent", "-Wi は -W の値が i", "python3 -Wi script.py"),
    ("silent", "-W の値のあとのスクリプト", "python3 -W ignore script.py"),
    ("silent", "-X の値のあとのスクリプト", "python3 -X dev script.py -i"),
    ("silent", "-B とスクリプト", "python3 -B script.py"),
    ("silent", "python3 -h", "python3 -h"),
    ("silent", "python3 -V", "python3 -V"),
    ("silent", "python3 --help", "python3 --help"),
    ("silent", "node --version", "node --version"),
    ("silent", "bash --version", "bash --version"),
    ("silent", "perl --help", "perl --help"),
    ("silent", "node -e", "node -e 'x'"),
    ("silent", "node -p", "node -p 1"),
    ("silent", "node -pe", "node -pe 1"),
    ("silent", "node --eval", "node --eval 'x'"),
    ("silent", "node --print", "node --print 1"),
    ("silent", "node --eval=", "node --eval=x"),
    ("silent", "node スクリプトと -i", "node app.js -i"),
    ("silent", "node -r とスクリプト", "node -r ./x.js app.js"),
    ("silent", "node --require とスクリプト", "node --require ./x.js app.js"),
    ("silent", "bash -c", "bash -c 'echo hi'"),
    ("silent", "bash script.sh", "bash script.sh"),
    ("silent", "bash script.sh -i", "bash script.sh -i"),
    ("silent", "bash -o とスクリプト", "bash -o pipefail script.sh"),
    ("silent", "bash -O と -c", "bash -O extglob -c 'echo hi'"),
    ("silent", "bash --rcfile とスクリプト", "bash --rcfile x script.sh"),
    ("silent", "sh -c のコマンド", "sh -c 'python3 -c x'"),
    ("silent", "lua スクリプト", "lua script.lua"),
    ("silent", "lua スクリプトと -i", "lua script.lua -i"),
    ("silent", "lua -e", "lua -e 'print(1)'"),
    ("silent", "lua -", "lua -"),
    ("silent", "lua -l とスクリプト", "lua -l mod script.lua"),
    ("silent", "ruby -e", "ruby -e 'x'"),
    ("silent", "ruby -I とスクリプト", "ruby -I lib script.rb"),
    ("silent", "ruby スクリプト", "ruby script.rb"),
    ("silent", "ruby -ne", "ruby -ne 'x' f"),
    ("silent", "perl -e", "perl -e 'x'"),
    ("silent", "perl -E", "perl -E 'say 1'"),
    ("silent", "perl -pi -e", "perl -pi -e 's/a/b/' f"),
    ("silent", "perl -i.bak -pe", "perl -i.bak -pe 's/a/b/' f"),
    ("silent", "perl -lane", "perl -lane 'print' f"),
    ("silent", "perl -Mstrict -e", "perl -Mstrict -e 1"),
    ("silent", "perl -I とスクリプト", "perl -I lib script.pl"),
    ("silent", "perl スクリプト", "perl script.pl"),
    ("silent", "ruby -r の値は束ねた残り", "ruby -ri18n script.rb"),
    ("silent", "deno run", "deno run x.ts"),
    ("silent", "deno --version", "deno --version"),
    ("silent", "deno fmt", "deno fmt"),
    ("silent", "irb --version", "irb --version"),
    ("silent", "ipython -c", "ipython -c 'x'"),
    ("silent", "ipython とスクリプト", "ipython script.py"),
    ("silent", "ipython -i はスクリプト実行後に対話", "ipython -i script.py"),
    ("silent", "ipython3 -c", "ipython3 -c 'x'"),
    # bash -c: one level of literals (FR9)
    ("deny", "bash -c の中の -i", 'bash -c "python3 -i"'),
    ("deny", "bash -c の中の引数なし起動", "bash -c 'python3'"),
    ("deny", "sh -c の中の cd と -i", "sh -c 'cd x && python3 -i'"),
    ("deny", "zsh -c", "zsh -c 'python3 -i'"),
    ("deny", "env 経由の bash -c", "env FOO=1 bash -c 'python3 -i'"),
    ("deny", "改行を含む bash -c", "bash -c 'echo a\npython3 -i'"),
    ("deny", "bash -c と外側の -i", "bash -i -c 'echo hi'"),
    ("deny", "bash -ic", "bash -ic 'echo hi'"),
    ("silent", "bash -c のパイプの右側", "bash -c 'echo x | python3'"),
    ("silent", "bash -c と外側の入力", "bash -c 'python3' < f"),
    ("silent", "bash -c と外側のパイプ", "echo | bash -c python3"),
    ("silent", "bash -c の変数", 'bash -c "$CMD"'),
    ("silent", "bash -c の展開を含む文字列", 'bash -c "python3 -i $X"'),
    ("silent", "bash -c の中の不正なクォート", "bash -c \"echo 'x\""),
    ("silent", "bash -c の中のクォート内", "bash -c 'echo \"python3 -i\"'"),
    ("silent", "bash -cx は -c の値が x", "bash -cx 'python3 -i'"),
    ("silent", "python3 -c の中身は評価しない", "python3 -c 'import os; os.system(\"python3 -i\")'"),
    ("silent", "bash -c の文字列が無い", "bash -c"),
    # Words the hook cannot read (NFR2)
    ("silent", "変数のコマンド語", "$PY -i"),
    ("silent", "変数の引数", 'python3 "$@"'),
    ("silent", "変数の引数 2", "python3 $SCRIPT"),
    ("silent", "-B のあとの変数", "python3 -B $SCRIPT"),
    ("silent", "コマンド置換の引数", "python3 $(echo x.py)"),
    ("silent", "バッククォートの引数", "python3 `echo x.py`"),
    ("silent", "算術展開の引数", "python3 $((1+2))"),
    ("silent", "exec の変数", 'exec "$@"'),
    ("silent", "環境変数の代入だけ", "FOO=1"),
    ("silent", "リダイレクトだけ", "> out.txt"),
    ("silent", "プロセス置換の引数", "python3 <(echo x)"),
    ("silent", "グロブの引数", "python3 *.py"),
    ("silent", "$'..' の引数", "python3 $'x y.py'"),
    ("silent", "${...} の引数", "python3 ${x:-y.py}"),
    # Compound commands
    ("deny", "後ろのコマンドだけ該当", "ls; python3 script.py; python3 -i"),
    ("deny", "-B のあとの &&", "python3 -B && python3 -i"),
    ("deny", "heredoc のあとの引数なし起動", "python3 - <<EOF\nprint(1)\nEOF\npython3"),
    ("silent", "全部非対話", "ls; python3 script.py && node app.js | cat"),
    ("silent", "heredoc を使う 2 つのコマンド", "python3 - <<EOF\nprint(1)\nEOF\npython3 script.py"),
    ("silent", "複数の heredoc", "cat <<A <<B\na\nA\nb\nB"),
]

DENY_REASON_MARKERS = ("python3 -c", "python3 - <<EOF", "スクリプトファイル")

# A spread of the table for the checks that repeat every run under a changed
# condition; running the whole table under each would only add time.
SAMPLE_CASES = [(expected, command) for expected, _, command in CASES[::12]]


def payload_for(command):
    return {
        "session_id": "s",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def run_hook(path, payload, cwd=None, env=None):
    data = payload if isinstance(payload, bytes) else (
        payload if isinstance(payload, str) else json.dumps(payload)
    )
    if isinstance(data, str):
        data = data.encode("utf-8")
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=data,
        capture_output=True,
        cwd=cwd,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class HookCopiesMixin:
    """Run each test body against both copies of the hook."""

    def for_each_copy(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                yield plugin, path


class TestCasesTable(HookCopiesMixin, unittest.TestCase):
    def test_cases_hold_both_a_deny_and_a_silent_case(self):
        verdicts = {expected for expected, _, _ in CASES}
        self.assertEqual(verdicts, {"deny", "silent"})

    def test_cases_are_unique(self):
        commands = [command for _, _, command in CASES]
        self.assertEqual(len(commands), len(set(commands)))

    def test_cases_run_against_both_copies(self):
        for plugin, path in self.for_each_copy():
            for expected, label, command in CASES:
                with self.subTest(label=label, command=command):
                    code, out, err = run_hook(path, payload_for(command))
                    self.assertEqual(code, 0)
                    self.assertEqual(err, "")
                    if expected == "silent":
                        self.assertEqual(out, "")
                        continue
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")


class TestDenyOutput(HookCopiesMixin, unittest.TestCase):
    def test_deny_prints_exactly_one_json_object_of_the_expected_shape(self):
        for plugin, path in self.for_each_copy():
            for command in ("python3 -i", "python3", "bash -lc 'python3 -i'"):
                with self.subTest(command=command):
                    code, out, err = run_hook(path, payload_for(command))
                    self.assertEqual(code, 0)
                    self.assertEqual(err, "")
                    decoder = json.JSONDecoder()
                    obj, end = decoder.raw_decode(out)
                    self.assertEqual(out[end:].strip(), "")
                    self.assertEqual(list(obj), ["hookSpecificOutput"])
                    decision = obj["hookSpecificOutput"]
                    self.assertEqual(
                        sorted(decision),
                        ["hookEventName", "permissionDecision", "permissionDecisionReason"],
                    )
                    self.assertEqual(decision["hookEventName"], "PreToolUse")
                    self.assertEqual(decision["permissionDecision"], "deny")

    def test_reason_is_japanese_and_names_the_three_alternatives(self):
        for plugin, path in self.for_each_copy():
            for command in ("python3 -i", "python3"):
                with self.subTest(command=command):
                    _, out, _ = run_hook(path, payload_for(command))
                    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
                    for marker in DENY_REASON_MARKERS:
                        self.assertIn(marker, reason)
                    self.assertTrue(
                        any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in reason),
                        "the reason holds Japanese text",
                    )

    def test_reason_does_not_echo_unreadable_text_from_the_command(self):
        # The command word is the only part of the command a reason may name,
        # and a matched name is plain ASCII by construction (FR8).
        for plugin, path in self.for_each_copy():
            code, out, err = run_hook(path, payload_for("python3 -i \ud800"))
            self.assertEqual((code, err), (0, ""))
            self.assertIn("deny", out)

    def test_output_is_utf8_whatever_the_locale(self):
        env = {"LC_ALL": "C", "LANG": "C", "PYTHONIOENCODING": "ascii"}
        for plugin, path in self.for_each_copy():
            code, out, err = run_hook(path, payload_for("python3 -i"), env=env)
            self.assertEqual((code, err), (0, ""))
            reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("スクリプトファイル", reason)


class TestFailOpen(HookCopiesMixin, unittest.TestCase):
    def assert_silent(self, path, data):
        code, out, err = run_hook(path, data)
        self.assertEqual((code, out, err), (0, "", ""))

    def test_input_that_is_not_json_passes(self):
        for plugin, path in self.for_each_copy():
            for data in ("", "not json", "{", '{"tool_input": {"command": "python3 -i"}', b"\xff\xfe\x00", "\x00"):
                with self.subTest(data=data):
                    self.assert_silent(path, data)

    def test_json_that_is_not_an_object_passes(self):
        for plugin, path in self.for_each_copy():
            for data in ("[]", "[1]", '"python3 -i"', "123", "null", "true", '["python3", "-i"]'):
                with self.subTest(data=data):
                    self.assert_silent(path, data)

    def test_missing_tool_input_passes(self):
        for plugin, path in self.for_each_copy():
            for payload in ({}, {"tool_name": "Bash"}, {"tool_input": None}, {"tool_input": "python3 -i"}, {"tool_input": []}):
                with self.subTest(payload=payload):
                    self.assert_silent(path, payload)

    def test_missing_command_passes(self):
        for plugin, path in self.for_each_copy():
            for payload in ({"tool_input": {}}, {"tool_input": {"cmd": "python3 -i"}}):
                with self.subTest(payload=payload):
                    self.assert_silent(path, payload)

    def test_non_string_command_passes(self):
        for plugin, path in self.for_each_copy():
            for command in (None, 123, True, ["python3", "-i"], {"a": "python3 -i"}, 1.5):
                with self.subTest(command=command):
                    self.assert_silent(path, {"tool_input": {"command": command}})

    def test_an_unclosed_quote_passes(self):
        for plugin, path in self.for_each_copy():
            for command in ("python3 -i 'abc", 'python3 -i "abc', "echo $'abc", "echo ${abc", "python3 -i $(echo", "python3 -i `echo"):
                with self.subTest(command=command):
                    self.assert_silent(path, payload_for(command))

    def test_an_unterminated_heredoc_passes(self):
        for plugin, path in self.for_each_copy():
            for command in ("python3 -i <<EOF", "python3 -i <<EOF\nbody", "python3 <<EOF\nbody\nEO", "cat <<''\nx"):
                with self.subTest(command=command):
                    self.assert_silent(path, payload_for(command))

    def test_env_with_an_option_passes(self):
        for plugin, path in self.for_each_copy():
            for command in ("env -i python3", "env -u X python3 -i", "env -- python3 -i"):
                with self.subTest(command=command):
                    self.assert_silent(path, payload_for(command))

    def test_a_very_long_command_still_gets_an_answer(self):
        command = "echo " + "x " * 50000 + "; python3 -i"
        for plugin, path in self.for_each_copy():
            code, out, err = run_hook(path, payload_for(command))
            self.assertEqual((code, err), (0, ""))
            self.assertIn("deny", out)


def verdict_of(result):
    """Reduce a (code, stdout, stderr) result to deny, silent or error."""
    code, out, err = result
    if (code, err) != (0, ""):
        return "error"
    if out == "":
        return "silent"
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class TestWorkingDirectoryAndEnvironment(HookCopiesMixin, unittest.TestCase):
    def test_the_verdict_does_not_depend_on_the_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Files named like an operand or the interpreter must not change
            # the verdict either.
            (Path(tmp) / "script.py").write_text("print(1)\n", encoding="utf-8")
            (Path(tmp) / "python3").write_text("", encoding="utf-8")
            for plugin, path in self.for_each_copy():
                for expected, command in SAMPLE_CASES:
                    for cwd in (str(REPO_ROOT), tmp, "/"):
                        with self.subTest(command=command, cwd=cwd):
                            result = run_hook(path, payload_for(command), cwd=cwd)
                            self.assertEqual(verdict_of(result), expected)

    def test_the_verdict_does_not_depend_on_environment_variables(self):
        bare = {"PATH": "", "HOME": "/nonexistent"}
        busy = {"PATH": "/usr/bin", "HOME": "/", "SHELL": "/bin/zsh", "TERM": "xterm", "CI": "true"}
        for plugin, path in self.for_each_copy():
            for expected, command in SAMPLE_CASES:
                for name, env in (("bare", bare), ("busy", busy)):
                    with self.subTest(command=command, env=name):
                        result = run_hook(path, payload_for(command), env=env)
                        self.assertEqual(verdict_of(result), expected)


class TestCopies(unittest.TestCase):
    def test_both_copies_exist(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertTrue(path.is_file(), f"{path} is missing")

    def test_the_two_copies_are_byte_identical(self):
        em_workflow = HOOK_PATHS["em-workflow"].read_bytes()
        em_review = HOOK_PATHS["em-review"].read_bytes()
        self.assertEqual(em_workflow, em_review)

    def test_a_run_leaves_no_bytecode_cache_in_a_plugin_directory(self):
        for plugin, path in HOOK_PATHS.items():
            run_hook(path, payload_for("python3 -i"))
            with self.subTest(copy=plugin):
                self.assertEqual(list(path.parent.glob("__pycache__/codex-hook-interactive-guard*")), [])


RULES_PATH = REPO_ROOT / ".claude" / "rules" / "hook-tests.md"
RULES_HEADING = "## codex-hook-interactive-guard"


def rules_section():
    text = RULES_PATH.read_text(encoding="utf-8")
    start = text.find(RULES_HEADING + "\n")
    if start == -1:
        return ""
    rest = text[start + len(RULES_HEADING):]
    following = rest.find("\n## ")
    return rest if following == -1 else rest[:following]


class TestRulesDocument(unittest.TestCase):
    def test_the_rules_file_has_a_section_for_this_hook(self):
        self.assertNotEqual(rules_section(), "")

    def test_the_section_gives_the_test_command(self):
        self.assertIn("python3 -m unittest tests.test_codex_hook_interactive_guard", rules_section())

    def test_the_section_gives_the_cases_format(self):
        section = rules_section()
        for expected in ("CASES", "(期待する判定, ラベル, コマンド)", "`deny`", "`silent`"):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)

    def test_the_section_says_the_same_table_runs_against_both_copies(self):
        section = rules_section()
        for path in ("em-workflow/scripts/codex-hook-interactive-guard.py", "em-review/scripts/codex-hook-interactive-guard.py"):
            with self.subTest(path=path):
                self.assertIn(path, section)
        self.assertIn("両方", section)

    def test_the_section_says_the_copies_stay_byte_identical(self):
        self.assertIn("バイト単位で同一", rules_section())


# Modules whose import means network access, process spawning or file
# writing (NFR1).
NETWORK_OR_PROCESS_MODULES = frozenset(
    {
        "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib",
        "nntplib", "telnetlib", "xmlrpc", "socketserver", "asyncio", "selectors",
        "select", "webbrowser", "subprocess", "multiprocessing", "concurrent",
        "pty", "ctypes", "shutil", "tempfile", "sqlite3", "shelve", "dbm",
    }
)
# Method names that spawn a process or write a file whatever object they are
# called on.
PROCESS_OR_WRITE_ATTRIBUTES = frozenset(
    {
        "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
        "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
        "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
        "write_text", "write_bytes", "mkdir", "makedirs", "unlink", "rmdir", "removedirs",
        "truncate", "symlink",
    }
)
# Names too common on other objects (`str.replace`, `list.remove`) to flag on
# their own; they are flagged when called on `os`.
OS_MUTATING_ATTRIBUTES = frozenset({"remove", "rename", "replace", "link", "chmod", "chown", "utime", "mkfifo"})
WRITE_MODE_LETTERS = set("wax+")


def stdlib_module_names():
    names = getattr(sys, "stdlib_module_names", None)
    if names is None:  # Python before 3.10
        names = {"ast", "json", "sys", "re", "os", "io", "string", "itertools", "functools"}
    return set(names)


def constraint_violations(source):
    """Return a list of static-constraint violations found in `source`."""
    problems = []
    tree = ast.parse(source)
    stdlib = stdlib_module_names()
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"relative import at line {node.lineno}")
                continue
            modules = [node.module or ""]
        for name in modules:
            top = name.split(".")[0]
            if top not in stdlib:
                problems.append(f"imports {name}, which is outside the standard library")
            if top in NETWORK_OR_PROCESS_MODULES:
                problems.append(f"imports {name}, which reaches the network, a process or a file")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("__import__", "exec", "eval", "compile"):
                problems.append(f"calls {func.id} at line {node.lineno}")
            if isinstance(func, ast.Name) and func.id == "open" or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            ):
                mode_nodes = list(node.args[1:2]) + [kw.value for kw in node.keywords if kw.arg == "mode"]
                for mode_node in mode_nodes:
                    constant = isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str)
                    if not constant or WRITE_MODE_LETTERS & set(mode_node.value):
                        problems.append(f"opens a file for writing (or with an unknown mode) at line {node.lineno}")
            if isinstance(func, ast.Attribute) and func.attr in PROCESS_OR_WRITE_ATTRIBUTES:
                problems.append(f"calls .{func.attr}() at line {node.lineno}")
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and func.attr in OS_MUTATING_ATTRIBUTES
            ):
                problems.append(f"calls os.{func.attr}() at line {node.lineno}")
    return problems


class TestStaticConstraints(unittest.TestCase):
    def test_each_copy_stays_within_the_constraints(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertEqual(constraint_violations(path.read_text(encoding="utf-8")), [])

    def test_the_checker_flags_a_module_outside_the_standard_library(self):
        self.assertTrue(constraint_violations("import requests\n"))
        self.assertTrue(constraint_violations("from yaml import safe_load\n"))

    def test_the_checker_flags_network_and_process_modules(self):
        for source in ("import socket\n", "import subprocess\n", "from urllib import request\n", "import os, multiprocessing\n"):
            with self.subTest(source=source):
                self.assertTrue(constraint_violations(source))

    def test_the_checker_flags_process_spawning_calls(self):
        for source in (
            "import os\nos.system('x')\n",
            "import os\nos.popen('x')\n",
            "import os\nos.execv('x', [])\n",
            "import os\nos.remove('x')\n",
            "import os\nos.rename('x', 'y')\n",
        ):
            with self.subTest(source=source):
                self.assertTrue(constraint_violations(source))

    def test_the_checker_flags_writes(self):
        for source in (
            "open('f', 'w')\n",
            "open('f', mode='a')\n",
            "open('f', 'r+')\n",
            "open('f', 'x')\n",
            "open(name, mode)\n",
            "import io\nio.open('f', 'wb')\n",
            "p.write_text('x')\n",
            "p.write_bytes(b'x')\n",
        ):
            with self.subTest(source=source):
                self.assertTrue(constraint_violations(source))

    def test_the_checker_passes_reads_and_standard_streams(self):
        source = (
            "import json\nimport sys\n"
            "open('f')\nopen('f', 'rb')\n"
            "sys.stdout.write('x')\nsys.stdout.buffer.write(b'x')\n"
            "'a'.replace('b', 'c')\n[1].remove(1)\n"
        )
        self.assertEqual(constraint_violations(source), [])


if __name__ == "__main__":
    unittest.main()

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
import shlex
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

# A digit-only word of 5000 nines: longer than any int-from-string conversion
# the interpreter accepts by default, and far past the largest file descriptor.
HUGE_FD_WORD = "9" * 5000


def json_quoted_nesting(command, depth):
    """`command` as the operand of `depth` shell `-c` levels: each level is the
    previous command quoted as a JSON string literal behind `bash -c `."""
    for _ in range(depth):
        command = "bash -c " + json.dumps(command)
    return command


# The command as the hook receives it in `tool_input.command`: the backquote
# span after `foo(` nests two backslash-escaped backquotes, and the explicit
# `-i` of the anonymous body must still be denied. The source literal escapes
# each backslash, so the decoded text holds exactly two backslashes, each
# directly followed by a backquote, and four backquotes in all.
ESCAPED_BACKQUOTE_REPRODUCTION = (
    "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } "
    "foo(`echo \\`echo x\\``)'"
)


# The inner text of the first reproduction of the case-in-substitution feature:
# the delimiter range of an anonymous-function heredoc holds a double-quoted
# `$(case ...)`, the line that closes the body repeats it without the quotes,
# and the launch comes on the third line. A shell reads it as the operand of
# `zsh -c`, so the table row quotes it for a shell.
CASE_IN_RANGE_INNER = (
    'function { :; } << foo("$(case x in x) echo foo;; esac)")\n'
    "foo($(case x in x) echo foo;; esac))\n"
    "python3 -i"
)

def delimiter_command(wrap, lines):
    """The command of a codex-guard-delim-brace-quote-per-shell row (SPEC.md
    Test Scenarios, "command の作り方"): the lines joined by newlines make the
    string S, and each holder of `wrap` (outermost first) is applied from the
    innermost one outward as `holder + " -c " + shlex.quote(S)`."""
    text = "\n".join(lines)
    for holder in reversed(wrap):
        text = holder + " -c " + shlex.quote(text)
    return text


# codex-guard-delim-brace-quote-per-shell (SPEC.md Test Scenarios TS1 to TS32):
# the `${ ... }` ranges of a heredoc delimiter in a nested `-c` string are read
# by the shell that directly holds the string. Each entry is (id, expected,
# label, wrap, lines); `delimiter_command` builds the command by the rule of
# SPEC.md. The labels are SPEC.md's.
DELIMITER_PER_SHELL_ROWS = (
    ("TS1", "deny", "bash -c の区切り語の ${...} を書かれたまま登録し、終端行の後の起動は deny (再現手順)", [],
     ["bash -c 'false && cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i'"]),
    ("TS2", "silent", "bash -c では引用を除いた ${...} の行で本文が閉じない", ["bash"],
     ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]),
    ("TS3", "deny", "bash -c の ${...} の単引用符を残す", ["bash"],
     ["cat <<${v:-'x'}", "${v:-'x'}", "python3 -i"]),
    ("TS4", "deny", "bash -c の ${...} のバックスラッシュを残す", ["bash"],
     ["cat <<${v:-\\x}", "${v:-\\x}", "python3 -i"]),
    ("TS5", "deny", "bash -c の ${...} の二重引用符の中の } で閉じず、書かれたまま登録する", ["bash"],
     ["cat <<${v:-\"a}b\"}", "${v:-\"a}b\"}", "python3 -i"]),
    ("TS6", "deny", "bash -c の入れ子の ${...} を書かれたまま登録する", ["bash"],
     ["cat <<${a:-${b:-\"x\"}}", "${a:-${b:-\"x\"}}", "python3 -i"]),
    ("TS7", "deny", "bash -c の ${...} の中の $( ) は書かれたまま", ["bash"],
     ["cat <<${v:-$(echo \"x\")}", "${v:-$(echo \"x\")}", "python3 -i"]),
    ("TS8", "deny", "bash -c の ${...} の引用の外のバックスラッシュ＋改行は取り除く", ["bash"],
     ["cat <<${v:-\\", "x}", "${v:-x}", "python3 -i"]),
    ("TS9", "deny", "bash -c の ${...} の二重引用符の中のバックスラッシュ＋改行は取り除き、引用は残す", ["bash"],
     ["cat <<${v:-\"a\\", "b\"}", "${v:-\"ab\"}", "python3 -i"]),
    ("TS10", "deny", "bash -c で ${...} の前に引用があれば語全体の引用を除く", ["bash"],
     ["cat <<'P'${v:-\"x\"}", "P${v:-x}", "python3 -i"]),
    ("TS11", "deny", "bash -c で ${...} の後ろに引用があれば語全体の引用を除く", ["bash"],
     ["cat <<${v:-\"x\"}\"\"", "${v:-x}", "python3 -i"]),
    ("TS12", "silent", "bash -c で ${...} の後ろに引用があれば書かれたままの範囲の行では本文が閉じない", ["bash"],
     ["cat <<${v:-\"x\"}\"\"", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS13", "deny", "bash -c で ${...} の前の二重引用符があれば範囲の単引用符も除く", ["bash"],
     ["cat <<\"P\"${v:-'x'}", "P${v:-x}", "python3 -i"]),
    ("TS14", "silent", "bash -c でも ${...} の中の引用されていない $' は判定不能", ["bash"],
     ["cat <<${v:-$'x'}", "${v:-'x'}", "python3 -i"]),
    ("TS15", "deny", "bash -c の <<- は先頭タブを除いて書かれたままの ${...} と比べる", ["bash"],
     ["cat <<-${v:-\"x\"}", "\t${v:-\"x\"}", "python3 -i"]),
    ("TS16", "deny", "env を経由した版数つきの bash も bash の読み", ["env bash5.2"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]),
    ("TS17", "deny", "bash --posix も bash の読み", ["bash --posix"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]),
    ("TS18", "deny", "sh -c は bash の読みの終端行の後の起動を deny（今の読みは判定不能）", ["sh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]),
    ("TS19", "deny", "sh -c は今の読みの終端行の後の起動を deny（bash の読みは判定不能）", ["sh"],
     ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i"]),
    ("TS20", "deny", "sh -c は書かれたままの終端行の後で引用を除いた行の前の起動を deny", ["sh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS21", "deny", "sh -c は引用を除いた終端行の後で書かれたままの行の前の起動を deny", ["sh"],
     ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]),
    ("TS22", "silent", "sh -c の両方の読みで本文の中にある起動は deny しない", ["sh"],
     ["cat <<${v:-\"x\"}", "python3 -i", "${v:-x}", "${v:-\"x\"}"]),
    ("TS23", "deny", "パス付きの sh も 2 通りの読み", ["/bin/sh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS24", "silent", "dash -c は今の読みだけで、書かれたままの行では本文が閉じない", ["dash"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS25", "deny", "dash -c は引用を除いた終端行の後の起動を deny", ["dash"],
     ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i"]),
    ("TS26", "deny", "ksh -c も 2 通りの読みで、書かれたままの終端行の後の起動を deny", ["ksh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS27", "deny", "ksh -c も 2 通りの読みで、引用を除いた終端行の後の起動を deny", ["ksh"],
     ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]),
    ("TS28", "silent", "zsh -c の区切り語の読みは変えない", ["zsh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS29", "silent", "フックが受け取るコマンドそのものの区切り語の読みは変えない", [],
     ["cat <<${v:-'x'}", "${v:-'x'}", "python3 -i", "${v:-x}"]),
    ("TS30", "deny", "zsh -c の中の bash -c の文字列は bash の読み", ["zsh", "bash"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]),
    ("TS31", "silent", "bash -c の中の zsh -c の文字列は zsh の読み", ["bash", "zsh"],
     ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]),
    ("TS32", "deny", "bash -c の ${...} の外のバックスラッシュ＋改行は取り除き、引用に数えない", ["bash"],
     ["cat <<P\\", "${v:-\"x\"}", "P${v:-\"x\"}", "python3 -i"]),
)

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
    ("deny", "第 2 段の bash -c の中の -i を判定する", "bash -c \"bash -c 'python3 -i'\""),
    ("deny", "sh -c の中の bash -lc の中の -i を判定する", "sh -c 'bash -lc \"python3 -i\"'"),
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
    # bash -c: literal shell `-c` strings are judged at every level (FR9)
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
    ("deny", "bash -cx は -c を値を取らない旗として読み、文字列を判定する", "bash -cx 'python3 -i'"),
    ("silent", "python3 -c の中身は評価しない", "python3 -c 'import os; os.system(\"python3 -i\")'"),
    ("silent", "bash -c の文字列が無い", "bash -c"),
    # Shell -c is a flag that takes no value (FR1)
    ("deny", "束の -ce の文字列を判定", "bash -ce 'python3 -i'"),
    ("deny", "-c の後ろの -- のあとの文字列", "bash -c -- 'python3 -i'"),
    ("deny", "-c の後ろの単独 - のあとの文字列", "bash -c - 'python3 -i'"),
    ("deny", "束の中の i は対話", "bash -ci 'python3'"),
    ("deny", "-c の後ろの別語の -i", "bash -c -i 'python3'"),
    ("deny", "-co の値の後ろの文字列", "bash -co pipefail 'python3 -i'"),
    ("deny", "-c の後ろの -o の値の後ろの文字列", "bash -c -o pipefail 'python3 -i'"),
    ("deny", "sh -cx の文字列", "sh -cx 'python3'"),
    ("deny", "-c の後ろの旗のあとの文字列", "bash -c -x 'python3 -i'"),
    ("deny", "-oc の o は次の語を値に取り c は旗", "bash -oc pipefail 'python3 -i'"),
    ("silent", "-c の文字列より後ろの -i は引数", "bash -c 'echo hi' -i"),
    ("silent", "-c の文字列より後ろの -- と -i は引数", "bash -c 'echo hi' -- -i"),
    ("silent", "bash -cx と無害な文字列", "bash -cx 'echo hi'"),
    ("silent", "bash -c -- と無害な文字列", "bash -c -- 'echo hi'"),
    ("silent", "bash -cx の文字列が無い", "bash -cx"),
    ("silent", "bash -c - の文字列が無い", "bash -c -"),
    ("silent", "bash -cx -- の文字列が無い", "bash -cx --"),
    ("silent", "bash -cx と外側のパイプ", "echo | bash -cx python3"),
    ("silent", "bash -cx と外側の入力", "bash -cx 'python3' < f"),
    ("silent", "bash -cx の動的な文字列", 'bash -cx "$CMD"'),
    ("deny", "bash -cx の文字列はどの段でも判定する", "bash -cx \"bash -c 'python3 -i'\""),
    # A literal shell -c string is judged at every nesting level, with the
    # first-level rules
    ("deny", "第 2 段の引数なし起動", "bash -c \"bash -c 'python3'\""),
    ("deny", "第 2 段の中の extglob の ? で終わる語の () のあとの括弧",
     "bash -c 'bash -O extglob -c \"time /bin/true?()\n(python3 -i)\"'"),
    ("deny", "第 3 段の -i を判定する", "bash -c \"bash -c \\\"bash -c 'python3 -i'\\\"\""),
    ("deny", "第 2 段の zsh -c", "bash -c \"zsh -c 'python3 -i'\""),
    ("deny", "第 2 段の束ねた -lc", "bash -c \"bash -lc 'python3 -i'\""),
    ("deny", "第 2 段の env 経由の bash -c", "bash -c \"env FOO=1 bash -c 'python3 -i'\""),
    ("deny", "第 2 段の中の cd と -i", "bash -c \"bash -c 'cd x && python3 -i'\""),
    ("deny", "読めない第 2 段の文字列のあとの起動も判定する", "bash -c \"bash -c 'echo \\\"x'; python3 -i\""),
    ("silent", "外側のパイプは第 2 段にも届く", "echo | bash -c \"bash -c python3\""),
    ("silent", "外側の入力リダイレクトは第 2 段にも届く", "bash -c \"bash -c python3\" < f"),
    ("silent", "第 2 段の中のパイプの右側", "bash -c \"bash -c 'echo x | python3'\""),
    ("silent", "第 2 段の動的な文字列", "bash -c 'bash -c \"$CMD\"'"),
    ("silent", "第 2 段の無害な文字列", "bash -c \"bash -c 'echo hi'\""),
    ("silent", "第 2 段の閉じていない引用符は判定不能", "bash -c \"bash -c 'python3 -i \\\"x'\""),
    ("silent", "第 2 段の中の関数定義の本体は判定しない", "bash -c \"bash -c 'f() { python3 -i; }'\""),
    # Information short options belong to each interpreter (FR2)
    ("deny", "bash -h は情報表示ではない", "bash -h"),
    ("deny", "sh -h は情報表示ではない", "sh -h"),
    ("deny", "zsh -h は情報表示ではない", "zsh -h"),
    ("deny", "zsh -V は情報表示ではない", "zsh -V"),
    ("deny", "dash -V は情報表示ではない", "dash -V"),
    ("deny", "bash -V は情報表示ではない", "bash -V"),
    # A command substitution inside double quotes is one chunk (FR3)
    ("silent", "二重引用符内の置換の中の引用符", 'echo "$(echo "; python3 -i")"'),
    ("silent", "二重引用符内のバッククォート", 'echo "`echo x`; python3 -i"'),
    ("silent", "二重引用符内の算術展開", 'echo "$((1+2)); python3 -i"'),
    ("silent", "二重引用符内の置換の中身は判定しない", 'echo "$(python3 -i)"'),
    ("silent", "二重引用符内の閉じていない置換", 'echo "$(echo "'),
    ("silent", "二重引用符内の閉じない置換と後ろの起動", 'echo "$(echo x"; python3 -i'),
    ("silent", "置換の中の単一引用符の括弧", "echo \"$(echo ')'; python3 -i)\""),
    ("deny", "置換を閉じたあとの引用符の外の起動", 'echo "$(echo x)"; python3 -i'),
    ("deny", "置換の中の引用符を読み切ったあとの起動", 'echo "$(echo "x")"; python3 -i'),
    ("deny", "置換の中のエスケープした引用符のあとの起動", 'echo "$(echo \\")"; python3 -i'),
    # Groups pass their stdin connection down (FR4)
    ("silent", "括弧のあとの入力リダイレクト", "(python3) < /dev/null"),
    ("silent", "パイプの右側の括弧の中", "printf 'print(1)\\n' | (echo ignored; python3)"),
    ("silent", "括弧のあとの 0<", "(python3) 0< f"),
    ("silent", "括弧のあとの heredoc", "(python3) <<EOF\nprint(1)\nEOF"),
    ("silent", "入れ子の括弧のあとの入力", "( (python3) ) < f"),
    ("silent", "波括弧のあとの入力リダイレクト", "{ python3; } < /dev/null"),
    ("silent", "パイプの右側の波括弧の中", "printf 'print(1)\\n' | { echo ignored; python3; }"),
    ("silent", "パイプの右側の入れ子の括弧", "echo x | ( (python3) )"),
    ("silent", "パイプの右側の入れ子の波括弧", "echo x | { echo a; { python3; }; }"),
    ("deny", "括弧のあとの stderr のリダイレクトでは接続しない", "(python3) 2>/dev/null"),
    ("deny", "括弧のあとの stdout のリダイレクトでは接続しない", "(python3) > out"),
    ("deny", "括弧の右のパイプでは接続しない", "(python3) | cat"),
    ("deny", "接続のある括弧でも -i は拒否", "(python3 -i) < /dev/null"),
    ("deny", "パイプの右側の括弧でも -i は拒否", "echo x | (python3 -i)"),
    ("deny", "波括弧のあとの stderr のリダイレクトでは接続しない", "{ python3; } 2>/dev/null"),
    ("deny", "波括弧だけでは接続しない", "{ python3; }"),
    ("deny", "グループの外の起動は接続しない", "echo x | (cat); python3"),
    ("deny", "閉じたグループのあとの別コマンドは接続しない", "(cat) < f; python3"),
    ("deny", "語の一部の波括弧はグループではない", "{a,b}; python3"),
    ("silent", "引用符内の波括弧はグループではない", "echo '{'; echo '}'"),
    ("silent", "語の一部の波括弧は引数", "echo {a,b}"),
    ("silent", "関数定義の本体は実行しない", "f() { python3; }"),
    # A group after an array assignment is not a function body; only `name()`
    # and `function name()` start a definition
    ("deny", "配列代入のあとの改行と括弧", "a=()\n(python3 -i)"),
    ("deny", "配列への追加のあとの改行と括弧", "a+=()\n(python3 -i)"),
    ("deny", "export の配列代入のあとの改行と括弧", "export a=()\n(python3 -i)"),
    ("deny", "配列代入のあとの空行と括弧", "a=()\n\n(python3)"),
    ("deny", "配列代入のあとのコメント行と括弧", "a=()\n# c\n(python3 -i)"),
    ("deny", "配列代入のあとの改行と波括弧", "a=()\n{ python3 -i; }"),
    ("deny", "配列代入のあとの ; と括弧", "a=() ; (python3 -i)"),
    ("deny", "動的な語の () のあとの括弧", "$f()\n(python3 -i)"),
    ("deny", "3 語の () のあとの括弧", "a b c()\n(python3 -i)"),
    ("silent", "関数名のあとの改行と括弧は本体", "foo()\n(python3 -i)"),
    ("silent", "識別子でない関数名のあとの改行と括弧は本体", "my-func()\n(python3 -i)"),
    ("silent", "関数名のあとの括弧は本体", "f() (python3 -i)"),
    ("silent", "function 付きの関数定義の本体は実行しない", "function f() { python3; }"),
    ("silent", "function 付きの関数名のあとの改行と波括弧は本体", "function f()\n{ python3 -i; }"),
    # A function definition written right after a leading run of reserved words
    # is still a definition: the run is removed before the words are read
    ("silent", "then の直後の関数定義", "if true; then f() { python3 -i; }; fi"),
    ("silent", "do の直後の関数定義", "for x in 1; do f() { python3 -i; }; done"),
    ("silent", "! の直後の関数定義", "! f() { python3 -i; }"),
    ("silent", "time の直後の関数定義", "time f() { python3 -i; }"),
    ("silent", "else の直後の関数定義", "if false; then :; else f() { python3 -i; }; fi"),
    ("silent", "elif の直後の関数定義", "if false; then :; elif f() { python3 -i; }; then :; fi"),
    ("silent", "if の直後の関数定義", "if f() { python3 -i; }; then :; fi"),
    ("silent", "while の直後の関数定義", "while f() { python3 -i; }; do :; done"),
    ("silent", "until の直後の関数定義", "until f() { python3 -i; }; do :; done"),
    ("silent", "time -p の直後の関数定義", "time -p f() { python3 -i; }"),
    ("silent", "! time の連なりの直後の関数定義", "! time f() { python3 -i; }"),
    ("silent", "then の直後の function 付きの関数定義", "if true; then function f() { python3 -i; }; fi"),
    ("silent", "then の直後の関数名のあとの改行と波括弧は本体", "if true; then f()\n{ python3 -i; }\nfi"),
    ("silent", "then の直後の関数名のあとの括弧は本体", "if true; then f() (python3 -i); fi"),
    # Removal leaves no word: the words are judged as they stand
    ("silent", "予約語だけの 1 語は関数名", "then()\n(python3 -i)"),
    ("deny", "time -p だけの 2 語は関数名でない", "time -p()\n(python3 -i)"),
    # A word that ends in an extglob operator character (`?` `*` `+` `@` `!`)
    # is no function name: the group after its `()` stays judged. Extglob being
    # on or off changes nothing, and neither do quotes, an escape or a space
    # between the word and the `(`
    ("deny", "extglob の ? で終わる語の () のあとの括弧（予約語の有り、bash -c の中）",
     "bash -O extglob -c 'time /bin/true?()\n(python3 -i)'"),
    ("deny", "extglob の ? で終わる語の () のあとの括弧（予約語の無し、bash -c の中）",
     "bash -O extglob -c 'f?()\n(python3 -i)'"),
    ("deny", "then の直後の ? で終わる語の () のあとの括弧", "if true; then f?()\n(python3 -i)\nfi"),
    ("deny", "time -p の直後の ? で終わる語の () のあとの括弧", "time -p f?()\n(python3 -i)"),
    ("deny", "function 付きの ? で終わる語の () のあとの波括弧", "function f?()\n{ python3 -i; }"),
    ("deny", "* で終わる語の () のあとの括弧", "f*()\n(python3 -i)"),
    ("deny", "+ で終わる語の () のあとの括弧", "f+()\n(python3 -i)"),
    ("deny", "@ で終わる語の () のあとの括弧", "f@()\n(python3 -i)"),
    ("deny", "! で終わる語の () のあとの括弧", "f!()\n(python3 -i)"),
    ("deny", "単引用符で囲んだ ? で終わる語の () のあとの括弧", "'f?'()\n(python3 -i)"),
    ("deny", "バックスラッシュで逃がした ? で終わる語の () のあとの括弧", "f\\?()\n(python3 -i)"),
    ("deny", "? で終わる語と ( の間の空白のあとの括弧", "f? ()\n(python3 -i)"),
    ("deny", "予約語だけの ! の () のあとの括弧", "!()\n(python3 -i)"),
    # A group after a head that is no definition stays judged, whatever the
    # reserved words in front of it
    ("deny", "then の直後の配列代入のあとの改行と括弧", "if true; then a=()\n(python3 -i)\nfi"),
    ("deny", "then の直後の export の配列代入のあとの改行と括弧", "if true; then export a=()\n(python3 -i)\nfi"),
    ("deny", "do の直後の配列代入のあとの改行と括弧", "for x in 1; do a=()\n(python3 -i)\ndone"),
    ("deny", "else の直後の配列代入のあとの改行と波括弧", "if false; then :; else a=()\n{ python3 -i; }\nfi"),
    ("deny", "語の途中の予約語は取り除かない", "echo then f()\n(python3 -i)"),
    ("deny", "then の直後の 2 語の () のあとの括弧", "if true; then a b()\n(python3 -i)\nfi"),
    ("deny", "then の直後の動的な語の () のあとの括弧", "if true; then $f()\n(python3 -i)\nfi"),
    ("silent", "閉じていない括弧は判定不能", "(python3"),
    ("silent", "閉じていない波括弧は判定不能", "{ python3;"),
    ("silent", "} がコマンドの位置に無い波括弧は判定不能", "{ python3 }"),
    # A pending pipe survives empty lines (FR5)
    ("silent", "パイプのあとの改行", "echo x |\npython3"),
    ("silent", "パイプのあとの空行", "echo x |\n\npython3"),
    ("silent", "パイプのあとのコメント", "echo x | # c\npython3"),
    ("silent", "パイプのあとの heredoc 本文", "cat <<EOF |\nbody\nEOF\npython3"),
    ("silent", "パイプのあとのコメント行", "echo x |\n# c\npython3"),
    ("silent", "|& のあとの改行", "echo x |&\npython3"),
    ("silent", "パイプのあとの改行と括弧", "echo x |\n(python3)"),
    ("deny", "&& のあとの改行では接続しない", "echo x &&\npython3"),
    ("deny", "|| のあとの改行では接続しない", "echo x ||\npython3"),
    ("deny", "パイプのあとのリダイレクトだけの行では接続しない", "echo x |\n>out\npython3"),
    ("deny", "パイプの右側のコマンドのあとの改行では接続しない", "echo x | cat\npython3"),
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
    # A digit-only word of any length before a redirect operator is read
    # without an error, at every nesting depth; a word above 2147483647 is no
    # fd (FR1, FR3, FR5, FR7)
    ("deny", "桁数の大きい fd 語（第 2 段）のあとの起動", json_quoted_nesting(f": {HUGE_FD_WORD}>/dev/null", 2) + "; python3 -i"),
    ("deny", "桁数の大きい fd 語（第 0 段）のあとの起動", f": {HUGE_FD_WORD}>/dev/null; python3 -i"),
    ("deny", "桁数の大きい fd 語（第 1 段）のあとの起動", f"bash -c ': {HUGE_FD_WORD}>/dev/null'; python3 -i"),
    ("silent", "0 だけの 2 桁は fd 0", "python3 00< f"),
    ("silent", "2147483648 は fd でなく引数", "python3 2147483648>/dev/null"),
    ("deny", "2147483647 は fd", "python3 2147483647>/dev/null"),
    # A lone `function` with no quote, escape or expansion is no function name:
    # the `()` after it starts no definition (a zsh anonymous function), so the
    # group after it is judged. A quoted `function`, and `function function`,
    # keep their reading as a function definition
    ("deny", "! の直後の匿名関数の本体", "zsh -c '! function () { python3 -i; }'"),
    ("deny", "then の直後の匿名関数の本体", "zsh -c 'if true; then function () { python3 -i; }; fi'"),
    ("deny", "前置のない匿名関数の本体", "zsh -c 'function () { python3 -i; }'"),
    ("silent", "単引用符で囲んだ function は関数名", "zsh -c \"'function' () { python3 -i; }\""),
    ("silent", "function function は関数定義", "function function () { python3 -i; }"),
    # The three zsh anonymous-function forms (`function { ...; }`,
    # `function () { ...; } arg`, `() { ...; } arg`): the body is judged, the
    # words after its closing brace are arguments up to the next separator, and
    # a pipe connection on the head reaches the body and nothing after it
    ("deny", "括弧なしの匿名関数の本体", "zsh -c 'function { python3 -i; }'"),
    ("deny", "閉じ波括弧の後に引数がある匿名関数の本体", "zsh -c 'function () { python3 -i; } arg'"),
    ("deny", "括弧なしの匿名関数の本体と引数", "zsh -c 'function { python3 -i; } arg'"),
    ("deny", "! の直後の括弧なしの匿名関数の本体", "zsh -c '! function { python3 -i; }'"),
    ("deny", "語の無い () の匿名関数の本体と引数", "zsh -c '() { python3 -i; } arg'"),
    ("deny", "() と { の間に改行がある匿名関数の本体と引数", "zsh -c 'function ()\n{ python3 -i; } arg'"),
    ("deny", "パイプの右側の括弧なしの匿名関数の中の -i", "zsh -c 'echo x | function { python3 -i; }'"),
    ("deny", "パイプの右側の匿名関数の後の別コマンドには接続が届かない", "zsh -c 'echo x | function { cat; }; python3'"),
    ("deny", "引数の後の区切りの先の起動", "zsh -c 'function { :; } arg; python3 -i'"),
    ("silent", "名前付きの括弧なし定義の本体は実行しない", "zsh -c 'function f { python3 -i; }'"),
    ("silent", "単引用符で囲んだ function の後の { は匿名関数でない", "zsh -c \"'function' { python3 -i; }\""),
    ("silent", "引数に置いた python3 は起動でない", "zsh -c 'function { echo hi; } python3'"),
    ("silent", "引数の後の入力リダイレクトは本体を接続する", "zsh -c 'function () { python3; } arg < f'"),
    ("silent", "パイプの右側の括弧なしの匿名関数の本体は接続される", "zsh -c 'echo x | function { python3; }'"),
    ("silent", "パイプの右側の function () の本体は接続される", "zsh -c 'echo x | function () { python3; }'"),
    ("silent", "printf からのパイプの右側の function () の本体は接続される", "zsh -c 'printf \"print(1)\\n\" | function () { python3; }'"),
    ("deny", "printf からのパイプで接続された function () の本体でも -i は拒否する", "zsh -c 'printf \"print(1)\\n\" | function () { python3 -i; }'"),
    ("silent", "パイプの右側の語の無い () の本体は接続される", "zsh -c 'echo x | () { python3; }'"),
    ("silent", "パイプの接続は匿名関数の本体の入れ子の群にも届く", "zsh -c 'echo x | function { { python3; }; }'"),
    ("silent", "匿名関数でない波括弧群の後の語は判定不能", "zsh -c '{ python3 -i; } arg'"),
    ("silent", "名前付き関数定義の本体の後の語は判定不能", "zsh -c 'f() { python3 -i; } arg'"),
    ("silent", "function 付きの名前付き関数定義の本体の後の語は判定不能", "zsh -c 'function f () { python3 -i; } arg'"),
    # A stdin redirect read in the head of an anonymous function (before
    # `function`, between `function` and `{`, or before the `(` of `()`)
    # connects the body and the groups nested in it, and nothing past the
    # separator that ends the arguments. Only a stdin redirect counts, and an
    # explicit `-i` in the body is still denied
    ("silent", "function と { の間の入力リダイレクトは括弧なしの匿名関数の本体を接続する", "zsh -c 'function < /dev/null { python3; }'"),
    ("silent", "function と () の間の入力リダイレクトは匿名関数の本体を接続する", "zsh -c 'function < /dev/null () { python3; }'"),
    ("silent", "function の前の入力リダイレクトは括弧なしの匿名関数の本体を接続する", "zsh -c '< /dev/null function { python3; }'"),
    ("silent", "語の無い () の前の入力リダイレクトは匿名関数の本体を接続する", "zsh -c '< /dev/null () { python3; }'"),
    ("silent", "function () の前の入力リダイレクトは匿名関数の本体を接続する", "zsh -c '< /dev/null function () { python3; }'"),
    ("silent", "() の前の入力リダイレクトは () と { の間の改行を越えて本体を接続する", "zsh -c '< /dev/null ()\n{ python3; }'"),
    ("silent", "頭部の入力リダイレクトの接続は匿名関数の本体の入れ子の群にも届く", "zsh -c '< /dev/null function { { python3; }; }'"),
    ("deny", "頭部の入力リダイレクトがあっても本体の -i は拒否する", "zsh -c '< /dev/null function { python3 -i; }'"),
    ("deny", "頭部の入力リダイレクトの接続は引数の後の区切りを越えない", "zsh -c '< /dev/null function { :; } arg; python3'"),
    ("deny", "入力でないリダイレクトは匿名関数の本体を接続しない", "zsh -c '2> /dev/null function { python3; }'"),
    # A `(` among the arguments of an anonymous function is read, up to its
    # matching `)`, as part of one argument word, so a stdin redirect after it
    # still connects the body. A range that holds an unquoted `;`, `&` or
    # newline is read as a group, as before. These carry the setopt prefix
    # because zsh reports `no matches found` for `foo(x)` without it
    ("silent", "( を含む引数語の後の入力リダイレクトは本体を接続する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'"),
    ("silent", "語頭の ( の引数語の後の入力リダイレクトは本体を接続する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } (x) < /dev/null'"),
    ("silent", "引数の ( ) の中の空白と | は語の一部", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(a b|c) < /dev/null'"),
    ("silent", "引数の ( ) の中の引用符で囲んだ ; は群を開かない", "zsh -c \"setopt nonomatch nobareglobqual; function { python3; } foo(';') < /dev/null\""),
    ("silent", "語の無い () の匿名関数でも引数の ( の後の入力リダイレクトは本体を接続する", "zsh -c 'setopt nonomatch nobareglobqual; () { python3; } foo(x) < /dev/null'"),
    ("deny", "引数に ( があっても本体の -i は拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(x) < /dev/null'"),
    ("deny", "( を含む引数語の後の区切りの先の起動は拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { :; } foo(x); python3'"),
    ("deny", "引数の ( ) の中に ; があれば従来どおり群として読む", "zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i)'"),
    ("deny", "引数の ( ) の中に & があれば従来どおり群として読む", "zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i)'"),
    ("deny", "引数の ( ) の中に改行があれば従来どおり群として読む", "zsh -c 'setopt nobadpattern; function { :; } foo(a\npython3 -i)'"),
    # A range that holds a backquote, unquoted or inside double quotes, is read
    # as a group too, whether or not the backquotes balance: the scan notices a
    # backquote but never reads it, so a `)` inside one closes the range and
    # the explicit `-i` of the anonymous body must not go unjudged. A backquote
    # a backslash escapes, one inside single quotes and one after the range's
    # closing `)` are no trigger
    ("deny", "引数の ( ) の中にバッククォートがあれば群として読み本体の -i を拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'"),
    ("deny", "引数の ( ) の中のダブルクォート内のバッククォートも群として読み本体の -i を拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(\"`echo \"x)\"`\")'"),
    ("deny", "引数の ( ) の中のダブルクォート内の対のバッククォートも契機になる", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(\"`echo x`\") < /dev/null'"),
    ("deny", "既知の誤拒否: 引数の ( ) の中の対のバッククォートも契機になり、後の入力リダイレクトが本体を接続しない", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'"),
    ("silent", "引数の ( ) の中のダブルクォート内のバックスラッシュで打ち消したバッククォートは群を開かない", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(\"\\`x\\`\") < /dev/null'"),
    ("silent", "引数の ( ) の中のバックスラッシュで打ち消したバッククォートは群を開かない", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(\\`x\\`) < /dev/null'"),
    ("silent", "引数の ( ) の中のシングルクォート内のバッククォートは群を開かない", "zsh -c \"setopt nonomatch nobareglobqual; function { python3; } foo('\\`x\\`') < /dev/null\""),
    ("silent", "引数の ( ) の中の閉じないバッククォートは判定不能", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x)'"),
    ("silent", "引数の ( ) の中のダブルクォート内の閉じないバッククォートは判定不能", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(\"`echo x\")'"),
    ("silent", "引数の ( ) の閉じ括弧より後のバッククォートは契機にならない", "zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null; echo `echo y`'"),
    # A backquote span read outside quotes ends at the first backquote that is
    # not part of a backslash pair (a backslash and the character after it):
    # the backquotes a backslash escapes do not close it. The span below nests
    # two escaped backquotes, so its `)` closes the argument list and the
    # explicit `-i` of the anonymous body is denied
    ("deny", "引数の ( ) の中のバッククォートの置換が逃がしたバッククォートを入れ子に持っても置換は最後のバッククォートで閉じ本体の -i を拒否する", ESCAPED_BACKQUOTE_REPRODUCTION),
    # A group opened at such a `(` is provisional. When it is never closed (the
    # `)` sits in a comment, or there is none) and the first separator read
    # directly in it is a `;` or a lone `&`, it is rescued: the `(` is read as
    # an argument-word character and the commands after that separator are
    # judged as following the anonymous function. A newline or any other first
    # separator, and a genuinely unclosed group, stay undecidable
    ("deny", "引数の ( ) の中に ; があり閉じ括弧がコメントの中なら ; の後を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'"),
    ("deny", "引数の ( ) の中に単独の & があり閉じ括弧がコメントの中なら & の後を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'"),
    ("deny", "引数の ( に閉じ括弧が無くても ; の後を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i'"),
    ("deny", "語頭の ( の閉じ括弧がコメントの中でも ; の後を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } (a; python3 -i #)'"),
    ("deny", "最初の区切りが ; なら後の改行の先も救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; b\npython3 -i #)'"),
    ("deny", "救済した区切りより前の内容も従来の読みのまま判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(python3 -i; : #)'"),
    ("deny", "引用符で囲んだ ; は最初の区切りでなく、後の ; を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a \";\" b; python3 -i #)'"),
    ("deny", "リダイレクトの >& は区切りでなく、後の ; を救済して判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a >& b; python3 -i #)'"),
    ("deny", "救済した区切りの後の入れ子の群の中の起動も判定する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; (python3 -i) #)'"),
    ("deny", "救済した区切りの後の入れ子の群は匿名関数の頭部の接続を受けない", "zsh -c 'setopt nobadpattern; function { :; } foo(a; (python3) #)'"),
    ("silent", "救済した区切りの後の入れ子の群の後の入力リダイレクトは群を接続する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; (python3) < /dev/null #)'"),
    ("silent", "救済した区切りの後の関数定義の本体は判定しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a; f() { python3 -i; } #)'"),
    ("silent", "引数の ( ) の中の最初の区切りが改行なら閉じ括弧がコメントの中でも判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(a\npython3 -i #)'"),
    ("silent", "最初の区切りが改行なら後に ; があっても判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(a\nb; python3 -i #)'"),
    ("silent", "最初の区切りが && なら救済しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a && python3 -i #)'"),
    ("silent", "最初の区切りが || なら救済しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a || python3 -i #)'"),
    ("silent", "最初の区切りが | なら救済しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a | python3 -i #)'"),
    ("silent", "最初の区切りが |& なら救済しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a |& python3 -i #)'"),
    ("silent", "最初の区切りが && なら引用符で囲んだ ; があっても救済しない", "zsh -c 'setopt nobadpattern; function { :; } foo(a \";\" b && python3 -i #)'"),
    ("silent", "リダイレクトの &> は区切りでなく救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a &>/dev/null python3 -i #)'"),
    ("silent", "リダイレクトの >& は区切りでなく救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a >& python3 -i #)'"),
    ("silent", "引用符で囲んだ ; は救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a \";\" python3 -i #)'"),
    ("silent", "バックスラッシュの後の ; は救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a \\; python3 -i #)'"),
    ("silent", "引用符で囲んだ & は救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a \"&\" python3 -i #)'"),
    ("silent", "バックスラッシュの後の & は救済の契機にならない", "zsh -c 'setopt nobadpattern; function { :; } foo(a \\& python3 -i #)'"),
    ("silent", "コマンド位置の閉じない ( は判定不能", "zsh -c '(python3 -i #)'"),
    ("silent", "外側にコマンド位置の閉じない ( があれば救済しても判定不能", "zsh -c 'setopt nobadpattern; (function { :; } foo(a; python3 -i #)'"),
    ("silent", "外側の閉じない波括弧群が残れば救済しても判定不能", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i #)'"),
    ("silent", "救済した区切りの後のコマンドの入力リダイレクトは従来どおり接続する", "zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 < /dev/null #)'"),
    ("deny", "パイプの右側の匿名関数の頭部の接続は救済した区切りの後に届かない", "zsh -c 'setopt nobadpattern; echo x | function { :; } foo(a; python3 #)'"),
    ("silent", "関数定義の本体の中の引数の ( の救済後のコマンドは本体の } で閉じても skipped なので判定しない", "zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i #)\n}'"),
    # A provisional group nested in a provisional group is rescued from the
    # inside out: the separator of the inner one is the first direct separator
    # of an outer one that has none
    ("deny", "入れ子の仮の群は内側の ; を外側の最初の区切りとして救済する", "zsh -c 'setopt nobadpattern; function { :; } foo(function { :; } bar(a; python3 -i #)'"),
    ("deny", "外側の最初の区切りが ; なら内側の仮の群も救済する", "zsh -c 'setopt nobadpattern; function { :; } foo(x; function { :; } bar(a; python3 -i #)'"),
    ("silent", "外側の最初の区切りが改行なら内側の仮の群を救済しても判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(x\nfunction { :; } bar(a; python3 -i #)'"),
    ("silent", "外側の最初の区切りが && なら内側の仮の群を救済しても判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(x && function { :; } bar(a; python3 -i #)'"),
    ("silent", "内側の最初の区切りが改行なら外側に ; があっても判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(x; function { :; } bar(a\nb; python3 -i #)'"),
    ("silent", "内側の仮の群に区切りが無ければ外側に ; があっても判定不能", "zsh -c 'setopt nobadpattern; function { :; } foo(x; function { :; } bar(a'"),
    ("silent", "引数の閉じていない ( は判定不能", "zsh -c 'function { python3 -i; } foo('"),
    ("deny", "引数の対の無い ) は区切りとして読む", "zsh -c 'function { :; } foo) python3'"),
    ("silent", "引数の対の無い ) は外側のサブシェルを閉じ、その後の入力リダイレクトが本体を接続する", "zsh -c '( function { python3; } foo) < f'"),
    # A lone bare `}` read after a rescued separator closes the enclosing `{`
    # group (a plain brace group, an anonymous body or a function body): the
    # provisional groups between are rescued when the `}` is read, and the
    # commands after the separator are judged as commands of the closed group.
    # TS1 to TS5, TS8 to TS10, TS12 and TS15 are denied; TS6, TS7, TS13 and
    # TS14 read as the closed group is connected, takes no word, or is skipped;
    # TS11 and TS16 to TS20 stay undecidable. TS21 is the subshell form: a `}`
    # does not close a `(` group, and the `)` rescue below reads it, so it is
    # denied
    ("deny", "} 救済 TS1 再現1: { で包んだ引数の ( は ; の後の起動を救済して } で閉じる", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'"),
    ("deny", "} 救済 TS2 再現2: 匿名関数の本体で包んだ引数の ( は ; の後の起動を救済して } で閉じる", "zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'"),
    ("deny", "} 救済 TS3 単独の & が区切りでも } で閉じる", "zsh -c 'setopt nobadpattern; { function { :; } foo(a & python3 -i; }'"),
    ("deny", "} 救済 TS4 コメントの中の ) は救済を妨げない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; } #)'"),
    ("deny", "} 救済 TS5 プログラムを渡さない起動も判定する", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; }'"),
    ("silent", "} 救済 TS6 閉じた { 群の入力リダイレクトが救済後のコマンドに届く", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; } < /dev/null'"),
    ("silent", "} 救済 TS7 閉じた { 群のパイプ接続が救済後のコマンドに届く", "zsh -c 'setopt nobadpattern; echo x | { function { :; } foo(a; python3; }'"),
    ("deny", "} 救済 TS8 入れ子の仮の群を内側から救済して } で閉じる", "zsh -c 'setopt nobadpattern; { function { :; } foo(function { :; } bar(a; python3 -i; }'"),
    ("deny", "} 救済 TS9 仮の群の中の入れ子の { 群は普通に閉じ、その後の } が外側を閉じる", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; { python3 -i; }; }'"),
    ("deny", "} 救済 TS10 語が残る } は閉じる { 群が匿名関数の本体なら語を確定して閉じる", "zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i }'"),
    ("silent", "} 救済 TS11 匿名でない { 群で語が残る } は普通の語のまま", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; echo }'"),
    ("deny", "} 救済 TS12 閉じた匿名本体の後の語は引数で、区切りの先の起動を判定する", "zsh -c 'setopt nobadpattern; function { function { :; } foo(a; :; } arg; python3 -i'"),
    ("silent", "} 救済 TS13 匿名でない波括弧群の後の語は判定不能", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; :; } arg'"),
    ("silent", "} 救済 TS14 関数定義の本体の中のコマンドは skipped として判定しない", "zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'"),
    ("deny", "} 救済 TS15 関数定義の本体の後の区切りの先の起動は判定する", "zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'"),
    ("silent", "} 救済 TS16 最初の区切りが改行なら救済しない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a\npython3 -i; }'"),
    ("silent", "} 救済 TS17 最初の区切りが && なら救済しない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a && python3 -i; }'"),
    ("silent", "} 救済 TS18 引用符の中の } は閉じない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; \"}\"'"),
    ("silent", "} 救済 TS19 語の一部の } は閉じない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }x'"),
    ("silent", "} 救済 TS20 リダイレクトの対象の } は閉じない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; echo > }'"),
    ("deny", ") 救済 TS-1 サブシェル版は ) が仮の群の連鎖を救済してサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'"),
    # The `)` after the close is read as a separator and closes an enclosing
    # subshell, as anywhere else; zsh reaches the inner command
    ("deny", "} 救済 外側のサブシェルは } で閉じた後の ) で閉じる", "zsh -c 'setopt nobadpattern; ( { function { :; } foo(a; python3 -i; } )'"),
    # A chain of provisional groups is rescued only when every group of it
    # holds the separator condition, and only when the group outside the chain
    # is a `{` group; a failed `}` changes nothing and the later `;` and `}`
    # are read as before
    ("silent", "} 救済 外側の仮の群の最初の区切りが && なら } で救済しない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a && function { :; } bar(b; python3 -i; }'"),
    ("deny", "} 救済 外側の仮の群の最初の区切りが ; なら内側の仮の群と合わせて } で救済する", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; function { :; } bar(b; python3 -i; }'"),
    ("silent", "} 救済 内側の仮の群に区切りが無ければ } で救済しない", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; function { :; } bar(b }'"),
    ("silent", "} 救済 仮の群のすぐ外側が ( 群なら } は閉じない (閉じ括弧はコメントの中)", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } #)'"),
    ("deny", "既知の誤拒否: } 救済 仮の群のすぐ外側が ( 群で } は閉じず、後の ) が救済してサブシェルを閉じる。zsh 5.9 は parse error を出す入力", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } )'"),
    ("deny", "} 救済 失敗した } は群の状態を変えず、後の } が閉じる", "zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; \"}\"; }'"),
    # A `}` that closes the group is followed by the reading of any group
    # closed with a `; }`: an enclosing plain brace group closes in turn
    ("deny", "} 救済 外側の波括弧群は内側を } で閉じた後の } で閉じる", "zsh -c 'setopt nobadpattern; { { function { :; } foo(a; python3 -i; } }'"),
    # An unquoted `)` read while a provisional group is the innermost open group
    # rescues the chain of provisional groups there and closes the `(` group
    # just outside the chain (TS-1 above is the reproduction). The chain must
    # meet the separator condition the `}` rescue uses: the first direct
    # separator of its innermost group is a `;` or a lone `&`, and an outer group
    # with none of its own takes the separator of the one nested in it. Words
    # pending before the `)` become a command of the closed group, the commands
    # of the rescued groups are commands of that group (a pipe into it, a stdin
    # redirect after it and a function body around it reach them), and text after
    # the close is outside it. A `)` that finds no open `(` group is a separator,
    # as anywhere else. A chain whose base is the top level or a `{` group, a
    # first separator that does not rescue, a quoted `)` and a `)` in a comment
    # keep the reading they had
    ("deny", ") 救済 TS-2 単独の & が区切りでも ) で救済してサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a & python3 -i; )'"),
    ("deny", ") 救済 TS-3 ) の前に語が残っていても救済して語をサブシェルのコマンドにする", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i )'"),
    ("deny", ") 救済 TS-4 閉じたサブシェルの後の区切りの先の起動を判定する", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; :; ); python3 -i'"),
    ("deny", ") 救済 TS-5 入れ子の仮の群の連鎖を内側から救済してサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { :; } foo(function { :; } bar(a; python3 -i; )'"),
    ("silent", ") 救済 TS-6 最初の区切りが && なら救済せず従来の読みのまま", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a && python3 -i; )'"),
    ("silent", ") 救済 TS-7 最初の区切りが改行なら救済せず従来の読みのまま", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a\npython3 -i; )'"),
    ("silent", ") 救済 TS-8 閉じたサブシェルの入力リダイレクトが救済後のコマンドに届く", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3; ) < /dev/null'"),
    ("silent", ") 救済 TS-9 閉じたサブシェルのパイプ接続が救済後のコマンドに届く", "zsh -c 'setopt nobadpattern; echo x | ( function { :; } foo(a; python3; )'"),
    ("silent", ") 救済 TS-10 関数定義の本体の中のコマンドは skipped として判定しない", "zsh -c 'setopt nobadpattern; f() ( function { :; } foo(a; python3 -i; )'"),
    ("deny", "既知の誤拒否: ) 救済 TS-13 救済で閉じた後の対の無い ) は区切りで、後の入力リダイレクトは救済後のコマンドを接続しない。zsh 5.9 は parse error を出す入力", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3) ) < /dev/null'"),
    ("silent", ") 救済 TS-14 引用符の中の ) は契機にならず、群が開いたまま残る", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; \")\"'"),
    ("deny", ") 救済 外側のサブシェルは救済で閉じた後の ) で閉じる", "zsh -c 'setopt nobadpattern; ( ( function { :; } foo(a; python3 -i; ) )'"),
    # The case mark of a provisional group is the number of `case`s read in it
    # that no `esac` has closed yet. A bare `case` read at command position
    # while the group is the innermost open group raises the mark by 1, and a
    # bare `esac` lowers it by 1: an `esac` at command position, or one that
    # comes right after `case`, one word and a bare `in` in the same simple
    # command. A provisional group opened inside a provisional group takes the
    # parent's mark plus the parent's inherited value as its own inherited
    # value, fixed once when it opens; an `esac` that finds the own mark at 0
    # lowers the inherited value instead. A group whose mark or inherited value
    # is 1 or more never rescues a chain at a `)`: the `)` is a case-pattern
    # terminator there, and it closes the provisional group itself instead of
    # the subshell outside the chain, so a stdin redirect that follows reaches
    # only that group (TS-1 to TS-4 are denied again; review finding
    # 5e71ff00fdbe5aff). Once `esac` has returned the mark and the inherited
    # value to 0 the group reads like one that was never marked, and the `)`
    # rescues again (TS-11 to TS-13; findings 285d9bc33784bb3d and
    # df4afa83e782d56a). The mark follows the keyword position: a bare
    # reserved-word prefix (`!`, `time`) keeps it, while a quoted or escaped
    # reserved word is not part of the prefix and ends it (TS-14 and TS-15;
    # finding b374e6b3c3d4b471). An argument-position `case`, a quoted one, an
    # argument-position `esac` and a quoted `esac` are no keywords (TS-7, TS-8,
    # TS-18, TS-19), and the mark is a count, so the `esac` of an inner `case`
    # leaves the outer one counted (TS-16). A redirect after the subshell and a
    # pipe into it still connect the rescued commands. TS-9 is the known miss
    # of the limitation that the main reader does not track case-pattern
    # terminators in general. The two A9 rows pin the forms in which an `esac`
    # does not lower the mark: the newline between `case x` and `in esac`, and
    # zsh's brace form `case x { ... }`
    ("deny", ") 救済 case 印 TS-1 コマンド位置の case が仮の群に印を付け、パターンの ) は外側のサブシェルを閉じない (再現手順)", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-2 先頭の ! を除いた位置の case も印を付ける", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-3 先頭の time を除いた位置の case も印を付ける", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-4 外側の仮の群の印を内側の仮の子の群が連鎖に沿って受け継ぐ", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'"),
    ("silent", ") 救済 case 印 TS-5 サブシェルの後の入力リダイレクトは救済後のコマンドを接続する", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'"),
    ("silent", ") 救済 case 印 TS-6 サブシェルへのパイプは救済後のコマンドを接続する", "zsh -c 'setopt nobadpattern; echo x | ( function { python3; } foo(a; case x in x) :;; esac; )'"),
    ("silent", ") 救済 case 印 TS-7 引数の位置の case は印を付けず従来の ) 救済のまま", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'"),
    ("silent", ") 救済 case 印 TS-8 引用符で囲んだ case は印を付けず従来の ) 救済のまま", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; \"case\" x in x) < /dev/null'"),
    # TS-7 and TS-8 end with the subshell never closed once a mark is wrongly
    # set (the string is then undecidable and silent either way), so these two
    # rows close the subshell with its own `)`: a mark on an argument-position
    # or quoted `case` would let the redirect after it connect the subshell
    ("deny", ") 救済 case 印 TS-7b 引数の位置の case は印を付けず、パターン側の ) が外側のサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) :;; esac; ) < /dev/null'"),
    ("deny", ") 救済 case 印 TS-8b 引用符で囲んだ case は印を付けず、パターン側の ) が外側のサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; \"case\" x in x) :;; esac; ) < /dev/null'"),
    ("silent", "既知の見逃し: ) 救済 case 印 TS-9匿名関数の無い入力は仮の群を開かず、メインの読みは case のパターンの終端を追わない", "zsh -c '( python3; case x in x) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-11 case x in の直後の esac が印を 0 に戻し、最後の ) は連鎖を救済して外側のサブシェルを閉じる", "zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x in esac; )'"),
    ("deny", ") 救済 case 印 TS-12 空の case を esac で閉じた後の起動は、救済で閉じたサブシェルのコマンドとして判定する", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in esac; python3 -i; )'"),
    ("deny", ") 救済 case 印 TS-13 ;; の後のコマンド位置の esac が印を 0 に戻す", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in (x) :;; esac; python3 -i; )'"),
    ("deny", ") 救済 case 印 TS-14 引用符で囲んだ time は先頭の予約語に数えず、続く case に印を付けない", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; \"time\" case; python3 -i; )'"),
    ("deny", ") 救済 case 印 TS-15 バックスラッシュで逃がした ! は先頭の予約語に数えず、続く case に印を付けない", "zsh -c 'setopt nobadpattern; ( function { :; } foo(a; \\! case; python3 -i; )'"),
    ("deny", ") 救済 case 印 TS-16 入れ子の case は印を数で持ち、内側の esac の後も外側の case が残って z) は救済しない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (x) case y in (y) :;; esac;; z) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-17 子の仮の群のコマンド位置の esac は、自分の印が 0 のとき受け継いだ値を 1 下げて最後の ) の救済を戻す", "zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in (x) :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-18 引数の位置の esac は印を下げず、x) は外側のサブシェルを閉じない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) echo esac;; x) < /dev/null :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-19 引用符で囲んだ esac は印を下げず、x) は外側のサブシェルを閉じない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) \"esac\";; x) < /dev/null :;; esac; )'"),
    # TS-4b, TS-17b and TS-17c pin the inherited value beyond TS-4 and TS-17.
    # TS-4b: a grandchild takes the parent's mark plus the parent's inherited
    # value, so the count reaches the innermost group of a chain of three.
    # TS-17b: the inherited value is a sum, so a value of 2 needs two `esac`s to
    # return to 0 (a flag would clear at the first). TS-17c: an `esac` lowers
    # the group's own mark first and the inherited value only when the own mark
    # is 0
    ("deny", ") 救済 case 印 TS-4b 受け継いだ値は親の印と親の受け継いだ値の和で、三段の仮の群の連鎖でも最も内側の ) は救済しない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; function { :; } baz(c; x} in x) < /dev/null :;; y) :;; z) :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-17b 受け継いだ値が 2 のとき esac 1 つでは 1 に下がるだけで、x) は外側のサブシェルを閉じない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; case ${w:-${y:-}; function { :; } bar(b; esac; x) < /dev/null :;; y) :;; esac; )'"),
    ("deny", ") 救済 case 印 TS-17c esac は自分の印を先に 1 下げ、自分の印が 1 以上のあいだは受け継いだ値を下げないので、x) は外側のサブシェルを閉じない", "zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; case y in (y) :;; x} in (x) :;; esac; x) < /dev/null :;; esac; )'"),
    # A9 limitations of the narrow fix: the newline between `case x` and
    # `in esac` starts a new simple command, so its `esac` is neither at
    # command position nor right after `case`, one word and `in`; the brace
    # form `case x { ... }` has no bare `in`. The mark stays at 1 in both, the
    # final `)` closes the provisional group itself, and the subshell is left
    # open (undecidable, silent). A mark lowered by either form would rescue the
    # chain, close the subshell and deny, as TS-11 does
    ("silent", "既知の見逃し: ) 救済 case 印 A9 case x の次の行の in esac は印を下げず、最後の ) は仮の群を閉じる", "zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x\nin esac; )'"),
    ("silent", "既知の見逃し: ) 救済 case 印 A9 zsh の波括弧形 case x { esac は in が無いので印を下げず、最後の ) は仮の群を閉じる", "zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x { esac; )'"),
    # A standalone bare `}` closes an anonymous body, or a `{` group inside
    # one, even with words pending: they are finalized as a command of the
    # group, as a `;` before the `}` would (FR1, FR2, FR3, FR8). A `{` group
    # outside every anonymous body does not close then (FR5), and a `}` that
    # is quoted, escaped, expanded, inside a word or a redirect target closes
    # nothing (FR4)
    ("deny", "; のない } の匿名関数の本体の前にある起動", "zsh -c 'python3 -i; function { : }'"),
    ("deny", "; のない } の匿名関数の本体の後にある起動", "zsh -c 'function { : }; python3 -i'"),
    ("deny", "; のない } の匿名関数の本体の中の -i", "zsh -c 'function { python3 -i }'"),
    ("deny", "; のない } の function () の本体の中の -i", "zsh -c 'function () { python3 -i }'"),
    ("deny", "; のない } の () の本体の中の -i", "zsh -c '() { python3 -i }'"),
    ("deny", "; のない } の匿名関数の本体と引数", "zsh -c 'function { python3 -i } arg'"),
    ("deny", "; のない } の匿名関数の本体に入れ子にした波括弧群の後の起動", "zsh -c 'function { { : } }; python3 -i'"),
    ("deny", "; のない } の匿名関数の本体の中の ( ) をはさんだ波括弧群の中の -i", "zsh -c 'function { ( { python3 -i } ) }'"),
    ("deny", "匿名関数の本体の中の関数定義の本体は語が残っていても閉じる", "zsh -c 'function { f() { : } }; python3 -i'"),
    ("deny", "匿名関数の本体の中の function 付きの関数定義の本体は語が残っていても閉じる", "zsh -c 'function { function f() { : } }; python3 -i'"),
    ("deny", "匿名関数の本体の中の ( ) の中の波括弧群は語が残っていても閉じる", "zsh -c 'function { ( { : } ) }; python3 -i'"),
    ("deny", "入れ子の匿名関数の本体は語が残っていても閉じる", "zsh -c 'function { function { : } }; python3 -i'"),
    ("deny", "括弧の中の匿名関数の本体は語が残っていても閉じる", "zsh -c '( function { : } ); python3 -i'"),
    ("deny", "; のない } の匿名関数の本体の外の波括弧群の中の入れ子の匿名関数", "zsh -c '{ function { : }; python3 -i; }'"),
    ("silent", "パイプの右側の匿名関数の本体の ; のない } は接続を受け継ぐ", "zsh -c 'echo x | function { python3 }'"),
    ("silent", "頭部の入力リダイレクトのある匿名関数の本体の ; のない } は接続を受け継ぐ", "zsh -c '< /dev/null function { python3 }'"),
    ("silent", "パイプの右側の匿名関数の本体の入れ子の ; のない } は接続を受け継ぐ", "zsh -c 'echo x | function { { python3 } }'"),
    ("silent", "閉じた後の入力リダイレクトは ; のない } の匿名関数の本体を接続する", "zsh -c 'function () { python3 } < /dev/null'"),
    ("silent", "引数の後の入力リダイレクトは ; のない } の匿名関数の本体を接続する", "zsh -c 'function { python3 } arg < /dev/null'"),
    ("silent", "引用符で囲んだ } は群を閉じず、語が残る最後の } だけが本体を閉じる", "zsh -c \"echo x | function { echo '}'; python3 }\""),
    ("silent", "引用符で囲んだ } は群を閉じない", "zsh -c \"function { echo '}'; python3 -i\""),
    ("silent", "二重引用符で囲んだ } は群を閉じない", "zsh -c 'function { echo \"}\"; python3 -i'"),
    ("silent", "エスケープした } は群を閉じない", "zsh -c 'function { echo \\}; python3 -i'"),
    ("silent", "$'..' の } は群を閉じない", "zsh -c \"function { echo \\$'}'; python3 -i\""),
    ("silent", "語の一部の } は群を閉じない", "zsh -c 'function { echo a}; python3 -i'"),
    ("silent", "リダイレクト先の } は群を閉じない", "zsh -c 'function { echo x > }; python3 -i'"),
    ("silent", "最上位の波括弧群は語が残る } で閉じない", "zsh -c '{ : }; python3 -i'"),
    ("silent", "匿名関数の外の関数定義の本体は語が残る } で閉じない", "zsh -c 'f() { : }; python3 -i'"),
    ("silent", "匿名関数の外の function 付きの関数定義の本体は語が残る } で閉じない", "zsh -c 'function f() { : }; python3 -i'"),
    ("silent", "匿名関数の外の ( ) の中の波括弧群は語が残る } で閉じない", "zsh -c '( { : } ); python3 -i'"),
    ("silent", "匿名関数の引数の後の波括弧群は匿名関数の本体の外", "zsh -c 'function { :; } arg; { : }; python3 -i'"),
    # The `(`...`)` range of an anonymous function's argument that is the
    # delimiter of `<<` / `<<-` is quote-removed the way zsh does before it is
    # registered (FR1); the part of the word outside the range is not
    # processed again (FR2); an unquoted `$'` / `$"` in the range makes the
    # input unknowable (FR3). TS-1 to TS-11 are the specification's; TS-12 and
    # TS-13 tell FR3 and FR2 from plain quote removal
    ("silent", "TS-1 範囲の引用を除いた区切り語で heredoc の本文が閉じる (再現手順)", "zsh -c \"function { :; } << foo('x')\nfoo('x')\npython3 -i\nfoo(x)\""),
    ("deny", "TS-2 範囲の単引用符を除いた区切り語の行より後の起動は deny", "zsh -c \"function { :; } << foo('x')\nfoo(x)\npython3 -i\""),
    ("silent", "TS-3 範囲より前の部分だけの行では本文が終わらない", "zsh -c 'function { :; } << foo(python3)\nfoo\npython3 -i\nfoo(python3)'"),
    ("deny", "TS-4 範囲の二重引用符を除いた区切り語の行より後の起動は deny", "zsh -c 'function { :; } << foo(\"x\")\nfoo(x)\npython3 -i'"),
    ("deny", "TS-5 範囲のバックスラッシュを除いた区切り語の行より後の起動は deny", "zsh -c 'function { :; } << foo(\\x)\nfoo(x)\npython3 -i'"),
    ("deny", "TS-6 <<- は先頭タブを除いて範囲の引用を除いた区切り語と比べる", "zsh -c \"function { :; } <<- foo('x')\n\tfoo(x)\npython3 -i\""),
    ("deny", "TS-7 区切り語の範囲を除いて閉じたあとも匿名関数の本体の -i は deny", "zsh -c \"function { python3 -i; } << foo('x')\nfoo(x)\""),
    ("silent", "TS-8 範囲内の引用されていない $' は判定不能", "function { :; } << foo($'x')\nfoo($'x')\npython3 -i"),
    ("silent", "TS-9 範囲内の引用されていない $\" は判定不能", "function { :; } << foo($\"x\")\nfoo($\"x\")\npython3 -i"),
    ("deny", "TS-10 範囲内の二重引用符の中の $' は契機にせず除去後の区切り語で読む", "function { :; } << foo(\"$'\")\nfoo($')\npython3 -i"),
    ("deny", "TS-11 範囲内のバックスラッシュで逃がした $ は契機にせず除去後の区切り語で読む", "function { :; } << foo(\\$'x')\nfoo($x)\npython3 -i"),
    ("silent", "TS-12 範囲内の $' は単なる引用除去として読まず判定不能", "function { :; } << foo($'x')\nfoo($x)\npython3 -i"),
    ("deny", "TS-13 範囲の外のバックスラッシュは二重に除去しない", "function { :; } << a\\\\b(\"x\")\na\\b(x)\npython3 -i"),
    # Readings the change leaves as they were (FR4): a range that is no
    # heredoc delimiter, the target of `<` and `<<<`, and a range that holds a
    # separator and so opens a group
    ("deny", "引数の範囲が heredoc の区切り語でなければ $' があっても判定不能にしない", "function { :; } foo($'x'); python3 -i"),
    ("deny", "<<< の目標の範囲の $' は判定不能にしない", "function { :; } <<< foo($'x')\npython3 -i"),
    ("deny", "< の目標の範囲の $' は判定不能にしない", "function { :; } < foo($'x')\npython3 -i"),
    ("deny", "<<< の目標の範囲は区切り語として登録しない", "function { :; } <<< foo('x')\npython3 -i"),
    ("deny", "範囲が ; を含めば区切り語を待っていても群を開く従来の読みで $' は判定不能にしない", "function { :; } << foo($'x'; y)\nfoo\npython3 -i"),
    # Rules of the removal beyond the specification's scenarios: a backslash
    # and a newline are dropped together, a backslash before a backquote in
    # double quotes is dropped, and the text of a `$( ... )` stays as written
    ("deny", "範囲のバックスラッシュと改行の対は両方除く", "function { :; } << foo(a\\\nb)\nfoo(ab)\npython3 -i"),
    ("deny", "範囲の二重引用符の中のバックスラッシュと改行の対は両方除く", "function { :; } << foo(\"a\\\nb\")\nfoo(ab)\npython3 -i"),
    ("deny", "範囲の単引用符の中のバックスラッシュは残す", "function { :; } << foo('a\\b')\nfoo(a\\b)\npython3 -i"),
    ("deny", "範囲の二重引用符の中の \\ の次が逃がす文字でなければ両方残す", "function { :; } << foo(\"a\\b\")\nfoo(a\\b)\npython3 -i"),
    ("deny", "範囲の二重引用符の中の逃がしたバッククォートはバックスラッシュを除く", "function { :; } << foo(\"\\`\")\nfoo(`)\npython3 -i"),
    ("silent", "範囲の $( ) の中身は引用を除かず、引用を除いた行では本文が終わらない", "function { :; } << foo($(echo 'a'))\nfoo($(echo a))\npython3 -i\nfoo($(echo 'a'))"),
    ("deny", "範囲の $ の次が引用符でなければ文字のまま残す", "function { :; } << foo($x'y')\nfoo($xy)\npython3 -i"),
    ("deny", "範囲の入れ子の括弧は文字のまま残す", "function { :; } << foo((a)'b')\nfoo((a)b)\npython3 -i"),
    ("deny", "範囲の後ろに続く部分は範囲の引用除去のあとにそのままつなぐ", "function { :; } << foo('x')'y'z\nfoo(x)yz\npython3 -i"),
    # A `$( )` or `$(( ))` inside double quotes in the range keeps its original
    # text, inner quotes included, as zsh registers it: the double-quoted unit
    # is read through the one reader that word reading uses, and a skip past
    # the range end or a substitution it cannot read is undecidable
    ("deny", "範囲の二重引用符の中の $( ) は引用を含め元の文字のまま区切り語になり、閉じた行の後の起動は deny", "zsh -c 'function { :; } << foo(\"$(echo \"x\")\")\nfoo(\"$(echo \"x\")\")\nfoo($(echo \"x\"))\npython3 -i'"),
    ("silent", "範囲の二重引用符の中の $( ) の引用を除いた行では本文が終わらず、起動は本文の中", "zsh -c 'function { :; } << foo(\"$(echo \"a\")\")\nfoo($(echo a))\npython3 -i\nfoo($(echo \"a\"))'"),
    ("deny", "範囲の二重引用符の中の $(( )) は元の文字のまま区切り語になる", "zsh -c 'function { :; } << foo(\"$((1+2))\")\nfoo($((1+2)))\npython3 -i'"),
    ("deny", "範囲の二重引用符の中の入れ子の $( ) は引用を含め元の文字のまま区切り語になる", "zsh -c 'function { :; } << foo(\"$(a \"$(b \"c\")\")\")\nfoo($(a \"$(b \"c\")\"))\npython3 -i'"),
    ("silent", "範囲の二重引用符の中の置換の読み飛ばしが範囲の終わりを越えれば判定不能", "zsh -c 'function { :; } << foo(\"$(echo \")\")\")\nfoo($(echo ))\npython3 -i'"),
    ("silent", "範囲の中の単引用符が範囲の終わりまでに閉じなければ判定不能", "function { :; } << foo(\"$(echo $'\"')\" 'x)\nfoo($(echo $')\" x)\npython3 -i"),
    ("silent", "範囲の二重引用符の中の置換が閉じなければ判定不能", "zsh -c 'function { :; } << foo(\"$(\")\nfoo($()\npython3 -i'"),
    # Word reading is unchanged by the shared reader: an empty quote pair adds
    # nothing but starts a word, so the `-i` after it is an operand's argument
    ("silent", "空の単引用符の対は語を始める", "python3 '' -i"),
    ("silent", "空の二重引用符の対は語を始める", "python3 \"\" -i"),
    # A group opened at an argument `(` whose range has a matching `)`, holds no
    # unquoted `;`, `&` or newline and holds a backquote reads an unquoted `#`
    # at word start as a word character while it is the innermost open group, so
    # the `)` after the `#` still closes the range and the explicit `-i` of the
    # anonymous body is denied. A group opened inside it starts with that
    # reading. A `;` read directly in the group ends it: the `#` after it starts
    # a comment again, the provisional group is rescued by the `;`, and the
    # launch after the newline is judged
    ("deny", "バッククォートを含む引数の ( ) の中の空白の後の # は語の文字で、本体の -i を拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'"),
    ("deny", "バッククォートを含む引数の ( ) の中の空白の後の # は語の文字で、閉じた後の改行の先の起動も拒否する", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)\npython3 -i'"),
    ("deny", "バッククォートを含む引数の ( ) の中の入れ子の ( ) も語頭の # を語の文字として読む", "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` (a #))'"),
    ("deny", "バッククォートを含む引数の ( ) の中の走査が早く止まっても、直接の ; の後の # はコメントで改行の先の起動を拒否する", "zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '\"'\"' ignored\npython3 -i'"),
    # A string the reader cannot finish is judged up to its last checkpoint
    # instead of not at all. A checkpoint is a newline the reader itself reads at
    # the top level with no group open, no pipe pending, no list continuation
    # pending and the heredoc bodies of its line read through their terminators.
    # The commands before it keep the connection and skip a full read gives
    # them. A string with no checkpoint, and a launch on the line where the
    # reading stops, stay silent. The rows labelled 既知の誤拒否 are accepted
    # false denies
    ("deny", "判定不能で止まる前に読み終えた行の起動を拒否する (再現手順)", "bash -c 'python3 -B -S -i\nfunction { :; } foo(`case x in x) echo x;; esac` # '\"'\"'\n)'"),
    ("deny", "最上位で閉じない引用符より前の行の -i を拒否する", "python3 -i\necho '"),
    ("deny", "最上位で閉じない引用符より前の行のプログラムなしの起動を拒否する", "python3\necho '"),
    ("deny", "入れ子の -c 文字列で閉じない引用符より前の行の -i を拒否する", "bash -c 'python3 -i\necho '\"'\"''"),
    ("deny", "チェックポイントより前の閉じた群の中の起動を拒否する", "( python3 -i )\necho '"),
    ("deny", "チェックポイントより前の行の -c 文字列も判定する", "bash -c 'python3 -i'\necho '"),
    ("deny", "読み終えた heredoc の後の行の起動を拒否する", "python3 - <<EOF\nprint(1)\nEOF\npython3 -i\necho '"),
    ("deny", "既知の誤拒否: zsh は後ろの構文エラーで何も実行しない", "zsh -c 'python3 -i\nfunction { :; } foo(`case x in x) echo x;; esac` # '\"'\"'\n)'"),
    ("deny", "既知の誤拒否: 改行がシェルの実行単位の境界でない if の中の行", "if false; then\npython3 -i\necho '"),
    ("silent", "同じ行の判定不能な箇所より前の起動は判定しない", "python3 -i; echo '"),
    ("silent", "| で続く行はチェックポイントにならない", "python3 -i |\necho '"),
    ("silent", "|& で続く行はチェックポイントにならない", "python3 -i |&\necho '"),
    ("silent", "&& で続く行はチェックポイントにならない", "python3 -i &&\necho '"),
    ("silent", "|| で続く行はチェックポイントにならない", "python3 -i ||\necho '"),
    ("silent", "&& の後の空行を越えても継続のまま", "python3 -i &&\n\necho '"),
    # A redirect-only simple command ends the list continuation as it ends a
    # pending pipe: a separator other than a newline ends it whatever the ended
    # command held, and a newline ends it when the command it ends held a
    # redirection. The earlier `-i` is then denied although the last line is
    # undecidable. A blank line and a comment-only line end nothing
    ("deny", "&& の後の < だけの行で継続が終わり、前の行の -i を拒否する", "python3 -i &&\n< /dev/null\necho '"),
    ("deny", "&& の後の > だけの行で継続が終わり、前の行の -i を拒否する", "python3 -i && > /dev/null\necho '"),
    ("deny", "|| の後の > だけの行で継続が終わり、前の行の -i を拒否する", "python3 -i || > /dev/null\necho '"),
    ("deny", "&& の後の > だけのコマンドを ; で区切ると継続が終わり、前の行の -i を拒否する", "python3 -i && > /dev/null;\necho '"),
    ("deny", "&& の後の heredoc だけの行で継続が終わり、前の行の -i を拒否する", "python3 -i &&\n<<EOF\nx\nEOF\necho '"),
    ("deny", "入れ子の -c 文字列でも && の後の < だけの行で継続が終わり、前の行の -i を拒否する", "bash -c " + shlex.quote("python3 -i &&\n< /dev/null\necho '")),
    ("deny", "入れ子の -c 文字列でも && の後の > だけの行で継続が終わり、前の行の -i を拒否する", "bash -c " + shlex.quote("python3 -i && > /dev/null\necho '")),
    ("deny", "入れ子の -c 文字列でも || の後の > だけの行で継続が終わり、前の行の -i を拒否する", "bash -c " + shlex.quote("python3 -i || > /dev/null\necho '")),
    ("deny", "入れ子の -c 文字列でも && の後の > だけのコマンドを ; で区切ると継続が終わり、前の行の -i を拒否する", "bash -c " + shlex.quote("python3 -i && > /dev/null;\necho '")),
    ("deny", "入れ子の -c 文字列でも && の後の heredoc だけの行で継続が終わり、前の行の -i を拒否する", "bash -c " + shlex.quote("python3 -i &&\n<<EOF\nx\nEOF\necho '")),
    ("deny", "( ) の中で && の後の < だけのコマンドを閉じる ) で継続が終わり、前の行の -i を拒否する", "(python3 -i && < /dev/null)\necho '"),
    ("deny", "( ) の中で || の後の < だけのコマンドを閉じる ) で継続が終わり、前の行の -i を拒否する", "(python3 -i || < /dev/null)\necho '"),
    ("deny", "救済される引数の ( の中でも、&& の後の < だけのコマンドを閉じる ) で継続が終わり、前の行の -i を拒否する", "(function { :; } foo(a; python3 -i && < /dev/null)\necho '"),
    ("deny", "( ) を閉じた後の ; で区切っても、閉じる ) で継続が終わり、前の行の -i を拒否する", "(python3 -i && < /dev/null);\necho '"),
    ("deny", "( ) を閉じた後の & で区切っても、閉じる ) で継続が終わり、前の行の -i を拒否する", "(python3 -i && < /dev/null) &\necho '"),
    ("silent", "&& の後のコメントだけの行を越えても継続のまま", "python3 -i &&\n# c\necho '"),
    ("silent", "&& の後に何もなく ) で閉じても継続のまま", "(python3 -i &&)\necho '"),
    ("silent", "救済される引数の ( の中でも、&& の後に何もなく ) で閉じても継続のまま", "(function { :; } foo(a; python3 -i &&)\necho '"),
    ("silent", "開いた群の中の行はチェックポイントにならない", "{ python3 -i\necho '"),
    ("silent", "heredoc の本文が終わらない行はチェックポイントにならない", "python3 -i <<EOF\nprint(1)"),
    ("silent", "チェックポイントより前の接続された群は接続の読みのまま", "( python3 ) < /dev/null\necho '"),
    ("silent", "チェックポイントより前の関数定義の本体は判定しない", "f() { python3 -i; }\necho '"),
    ("silent", "チェックポイントより前のパイプの右側は接続されている", "echo x | python3\necho '"),
    # The comment exception keeps its range: the `)` inside the backquote span
    # ends the scan early, the real `)` sits after the `#`, and the `#` is a word
    # character, so the string is read in full and the body's `-i` is denied
    ("deny", "コメントの例外の範囲は変えない: バッククォートの中の ) で走査が早く終わり、本当の ) は # の後にある", "function { python3 -i; } foo(`echo )` #)"),
    # A `case` statement inside a `$( ... )` that opens inside double quotes is
    # read: the `)` that closes a pattern closes neither the substitution nor a
    # group opened in it, so the close is found where zsh finds it and the
    # launch after the substitution in the same string is judged. `esac` closes
    # a statement only at a pattern position or at a command position of an item
    # body. The contents of the substitution are never judged, and a form whose
    # close cannot be located stays undecidable
    ("deny", "区切り語の範囲の二重引用符の中の置換にある case 文のパターンの ) で置換を閉じず、閉じた行の後の起動を拒否する (再現手順 a)", "zsh -c " + shlex.quote(CASE_IN_RANGE_INNER)),
    ("deny", "語の二重引用符の中の置換にある case 文のパターンの ) で置換を閉じず、後ろの起動を拒否する (再現手順 b)", "zsh -c " + shlex.quote('echo "$(case x in x) :;; esac)"; python3 -i')),
    ("deny", "case 文の省略できる先頭の ( を持つパターンを読み、後ろの起動を拒否する", 'echo "$(case x in (x) :;; esac)"; python3 -i'),
    ("deny", "case 文の | で区切ったパターンと zsh の終端 ;& ;| を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case x in a|b) :;& x) :;| *) :;; esac)"; python3 -i')),
    ("deny", "case 文の bash の終端 ;;& を読み、後ろの起動を拒否する", "bash -c " + shlex.quote('echo "$(case x in x) :;;& *) :;; esac)"; python3 -i')),
    ("deny", "終端を省いて ; のあとの esac で終わる最後の項目を読み、後ろの起動を拒否する", 'echo "$(case x in x) :; esac)"; python3 -i'),
    ("deny", "終端を省いて改行のあとの esac で終わる最後の項目を読み、後ろの起動を拒否する", 'echo "$(case x in x) :\nesac)"; python3 -i'),
    ("deny", "パターンを閉じた ) の直後の入れ子の case 文を読み、後ろの起動を拒否する", 'echo "$(case x in x) case y in y) :;; esac;; esac)"; python3 -i'),
    ("deny", "引用符の中の ) を持つパターンと本体のサブシェルを読み、後ろの起動を拒否する", 'echo "$(case x in \')\') (:);; x) :;; esac)"; python3 -i'),
    ("deny", "項目の本体の入れ子の置換の中の case 文を読み、後ろの起動を拒否する", 'echo "$(case x in x) echo "$(case y in y) :;; esac)";; esac)"; python3 -i'),
    ("deny", "本体の引数の esac は case 文を閉じず、後ろの起動を拒否する", 'echo "$(case x in x) echo esac;; esac)"; python3 -i'),
    ("deny", "本体のコメントの中の esac は case 文を閉じず、後ろの起動を拒否する", 'echo "$(case x in x) : # esac\n;; esac)"; python3 -i'),
    ("silent", "case 文を含む置換の中身は判定しない", 'echo "$(case x in x) python3 -i;; esac)"'),
    ("silent", "esac で閉じない case 文は判定不能で、後ろの起動を拒否しない", 'echo "$(case x in x) :;;"; python3 -i'),
    ("silent", "case 文の項目の本体の中の heredoc は判定不能で、後ろの起動を拒否しない", 'echo "$(case x in x) cat <<E\nbody\nE\n;; esac)"; python3 -i'),
    ("deny", "波括弧形式の case TS-4 zsh の case x { ... } の形を読み、後ろの起動を拒否する", 'echo "$(case x { x) :;; })"; python3 -i'),
    # codex-guard-escaped-hash-brace-case-heredoc (VERIFICATION.md TS-3, TS-12 to
    # TS-25 and the boundary rows of FR8): zsh's brace form `case x { ... }` is
    # read, whatever the kind of shell. A standalone `{` after the subject opens
    # it. It closes at a standalone, unquoted `}` at a pattern position, at a
    # standalone `esac` at a pattern position, or at a standalone `}` at a
    # command position of the item body when no `{ }` group is open there. TS-3
    # and TS-12 are wrapped in `zsh -c` as SPEC.md states them; the other rows
    # are not (SPEC.md A3, A5). Quoted or escaped braces, forms whose close is
    # not certain and heredocs stay undecidable (silent)
    ("deny", "波括弧形式の case TS-3 for の語一覧のプロセス置換の中の case x { ... } を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i')),
    ("deny", "波括弧形式の case TS-12 パターンの位置の esac でも閉じる", "zsh -c " + shlex.quote('echo "$(case x { x) :;; esac)"; python3 -i')),
    ("deny", "波括弧形式の case TS-13 項目の本体のコマンド位置の深さ 0 の } で閉じる", 'echo "$(case x { x) :; })"; python3 -i'),
    ("deny", "波括弧形式の case { の直後が改行でも in の代わりに読む", 'echo "$(case x {\nx) :;; })"; python3 -i'),
    ("deny", "波括弧形式の case { の直後が行継続とその後の空白でも in の代わりに読む", 'echo "$(case x {\\\n x) :;; })"; python3 -i'),
    ("deny", "波括弧形式の case { の直後がタブでも in の代わりに読む", 'echo "$(case x {\tx) :;; })"; python3 -i'),
    ("deny", "波括弧形式の case パターンの位置の引用符で囲んだ } は閉じず、パターンを始める", 'echo "$(case x { "}") :;; })"; python3 -i'),
    ("deny", "波括弧形式の case パターンの位置のエスケープした } は閉じず、パターンを始める", 'echo "$(case x { \\}) :;; })"; python3 -i'),
    ("deny", "波括弧形式の case はシェルの種類に関わらず読む (bash -c)", "bash -c " + shlex.quote('echo "$(case x { x) :;; })"; python3 -i')),
    ("deny", "波括弧形式の case の ; のあとの } で閉じた後の case はコマンドの位置で、case 文を開く", 'echo "$(case x { x) :; } case y in y) :;; esac)"; python3 -i'),
    ("deny", "波括弧形式の case のパターンの位置の } で閉じた後の case はコマンドの位置で、case 文を開く", 'echo "$(case x { x) :;; } case y in y) :;; esac)"; python3 -i'),
    ("silent", "波括弧形式の case TS-23 引用符で囲んだ { は in の代わりにならず判定不能", 'echo "$(case x "{" x) :;; })"; python3 -i'),
    ("silent", "波括弧形式の case エスケープした { は in の代わりにならず判定不能", 'echo "$(case x \\{ x) :;; })"; python3 -i'),
    ("silent", "波括弧形式の case 単独の語でない { は in の代わりにならず判定不能", 'echo "$(case x {x x) :;; })"; python3 -i'),
    ("silent", "波括弧形式の case { の直後が ; のときは単独の語でなく判定不能", 'echo "$(case x {; x) :;; })"; python3 -i'),
    # The body of a brace-form item: a `{ }` group opened and closed there is no
    # close (TS-14), nor is a quoted or escaped brace (TS-15), a `}` at an
    # argument position (TS-16), a brace in `${ }` or a subshell, or a brace of a
    # nested case statement, which keeps a form and a depth of its own (TS-17,
    # TS-18)
    ("deny", "波括弧形式の case TS-14 項目の本体の { } 群は閉じではない", 'echo "$(case x { x) { :; };; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の入れ子の { } 群の中の ; を挟んでも深さが戻れば閉じる", 'echo "$(case x { x) { { :; }; };; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の { } 群を閉じた後の ; のあとの } で閉じる", 'echo "$(case x { x) { :; }; })"; python3 -i'),
    ("deny", "波括弧形式の case TS-15 引用符で囲んだ括弧とエスケープした括弧は数えない", 'echo "$(case x { x) echo "}" \'{\' \\{;; })"; python3 -i'),
    ("deny", "波括弧形式の case TS-16 引数の位置の } は閉じない", 'echo "$(case x { x) echo };; })"; python3 -i'),
    ("deny", "波括弧形式の case 引数の位置の { は深さを上げない", 'echo "$(case x { x) echo {;; })"; python3 -i'),
    ("deny", "波括弧形式の case TS-17 波括弧形式の中の in 形式", 'echo "$(case x { x) case y in y) :;; esac;; })"; python3 -i'),
    ("deny", "波括弧形式の case TS-18 in 形式の中の波括弧形式", 'echo "$(case x in x) case y { y) :;; };; esac)"; python3 -i'),
    ("deny", "波括弧形式の case 入れ子の波括弧形式は自分の閉じを持つ", 'echo "$(case x { x) case y { y) :;; };; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の { } 群の中の波括弧形式の閉じは外側の深さを変えない", 'echo "$(case x { x) { case y { y) :;; }; };; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の中の in 形式の項目の本体の対にならない } は外側を閉じない", 'echo "$(case x { x) case y in y) :; };; esac;; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の function { } の { は深さを上げ、その } で閉じない", 'echo "$(case x { x) function { :; };; y) echo \'"\';; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の ${ } の中の } は数えない",'echo "$(case x { x) echo ${x:-};; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体のサブシェルの中の { } は数えない", 'echo "$(case x { x) ( { :; } );; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体のサブシェルの中の対にならない } は閉じない", 'echo "$(case x { x) ( } ); :;; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体のサブシェルの中の対にならない { は深さを上げない", 'echo "$(case x { x) ( { : ); :;; })"; python3 -i'),
    ("deny", "波括弧形式の case 項目の本体の置換の中のコマンド位置の } は閉じない", 'echo "$(case x { x) echo "$(: ; })";; })"; python3 -i'),
    ("deny", "in 形式の case のパターンの位置の } はパターンで、閉じない", 'echo "$(case x in } ) :;; esac)"; python3 -i'),
    ("deny", "in 形式の case の本体のコマンド位置の } は閉じない", 'echo "$(case x in x) :; }; esac)"; python3 -i'),
    # Forms whose close is not certain: a heredoc in a brace-form statement
    # (TS-19, rule 8), no close (TS-20), an `esac` at a command position of the
    # item body (TS-21), an item terminator while a `{ }` group is open (TS-22,
    # and the other terminators), and the contents of the substitution, which
    # are never judged (TS-24)
    ("silent", "波括弧形式の case TS-19 波括弧形式の項目の本体の中の heredoc は判定不能", 'echo "$(case x { x) cat <<E\nbody\nE\n;; })"; python3 -i'),
    ("silent", "波括弧形式の case TS-20 閉じない波括弧形式は判定不能", 'echo "$(case x { x) :;;"; python3 -i'),
    ("silent", "波括弧形式の case TS-21 波括弧形式の項目の本体のコマンド位置の esac は判定不能", 'echo "$(case x { x) :; esac)"; python3 -i'),
    ("silent", "波括弧形式の case TS-22 { } 群が開いたままの項目の終端 ;; は判定不能", 'echo "$(case x { x) { :;; })"; python3 -i'),
    ("silent", "波括弧形式の case { } 群が開いたままの項目の終端 ;& は判定不能", 'echo "$(case x { x) { :;& })"; python3 -i'),
    ("silent", "波括弧形式の case { } 群が開いたままの項目の終端 ;| は判定不能", 'echo "$(case x { x) { :;| })"; python3 -i'),
    ("silent", "波括弧形式の case { } 群が開いたままの項目の終端 ;;& は判定不能", 'echo "$(case x { x) { :;;& })"; python3 -i'),
    ("silent", "波括弧形式の case 項目の本体の引数の位置の esac は閉じず、閉じない波括弧形式は判定不能", 'echo "$(case x { x) echo esac;;"; python3 -i'),
    ("silent", "波括弧形式の case TS-24 置換の中身は判定しない", 'echo "$(case x { x) python3 -i;; })"'),
    # Rule 9: the re-read of an arithmetic command restores the brace-form
    # state. The `((` of TS-25 fails as arithmetic at the `)` that is not
    # directly followed by `)` and is read again as two subshells; the second
    # row holds a brace-form statement that is opened and closed inside the
    # first reading
    ("deny", "波括弧形式の case TS-25 算術コマンドの読み直しを挟んでも { } 群の深さが戻り、閉じる", 'echo "$(case x { x) { ((echo a) ); };; })"; python3 -i'),
    ("deny", "波括弧形式の case 算術コマンドの最初の読みで開いて閉じた波括弧形式は、読み直しの後に外側の深さを変えない", 'echo "$(case x { x) { (( $(case y { y) :;; }) ) ); }; })"; python3 -i'),
    ("deny", "区切り語の範囲の二重引用符の中で、項目が複数ある case 文を読み、閉じた行の後の起動を拒否する", "zsh -c " + shlex.quote('function { :; } << foo("$(case x in a) :;; x) echo foo;; esac)")\nfoo($(case x in a) :;; x) echo foo;; esac))\npython3 -i')),
    # Forms zsh accepts are read, not made undecidable (zsh -c, the launch after
    # the substitution is judged): an empty leading alternative, with and without
    # the optional leading parenthesis; parentheses in the subject; a numeric
    # range as the subject; a process substitution as the subject
    ("deny", "zsh が受け付けるパターンの先頭の空の選択肢 |x を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case x in |x) :;; esac)"; python3 -i')),
    ("deny", "zsh が受け付ける先頭の ( のあとの空の選択肢 (|x) を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case x in (|x) :;; esac)"; python3 -i')),
    ("deny", "zsh が受け付ける case 文の対象の語の括弧 x(a|b) を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case x(a|b) in *) :;; esac)"; python3 -i')),
    ("deny", "zsh が受け付ける case 文の対象の語の数値の範囲 <1-2> を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case <1-2> in *) :;; esac)"; python3 -i')),
    ("deny", "zsh が受け付ける case 文の対象の語のプロセス置換 <(:) を読み、後ろの起動を拒否する", "zsh -c " + shlex.quote('echo "$(case <(:) in *) :;; esac)"; python3 -i')),
    # codex-guard-case-reading-fixes (SPEC.md Test Scenarios TS1 to TS19): the
    # substitution reader reads a `case` statement correctly when `case` or
    # `esac` is an argument, when a comment follows a pattern's `)` directly,
    # and when a line continuation sits in a waiting phase or at a keyword.
    # In the notation of SPEC.md `<NL>` is a newline and `\<NL>` is a
    # backslash directly followed by a newline; the literals below hold exactly
    # those characters (`\n` and `\\\n`).
    ("silent", "case 読み TS1 引数の if の後の esac は文を閉じず、引用符の中の python3 -i を拒否しない (再現手順 1)", 'echo "$(case y in x) echo if esac;; y) echo "; python3 -i;";; esac)"'),
    ("silent", "case 読み TS2 パターンの ) の直後の # はコメントで、中の esac と引用符は何も閉じも開きもしない (再現手順 2)", 'echo "$(case x in x)#; esac\n:;; y) printf \'%s\' \'"; python3 -i; #\';; esac)"'),
    ("deny", "case 読み TS3 in の前の行継続を読み飛ばして置換の閉じを見つけ、後ろの起動を拒否する (再現手順 3)", 'echo "$(case x \\\nin x) :;; esac)"; python3 -i'),
    ("silent", "case 読み TS4 引数の then の後の esac は文を閉じない", 'echo "$(case y in x) echo then esac;; y) echo "; python3 -i;";; esac)"'),
    ("silent", "case 読み TS5 引数の ! の後の esac は文を閉じない", 'echo "$(case y in x) echo ! esac;; y) echo "; python3 -i;";; esac)"'),
    ("deny", "case 読み TS6 引数の then の後の esac が文を閉じないので、引用がずれず後ろの起動を拒否する", 'echo "$(case x in x) echo then esac;; y) echo \'"\';; esac)"; python3 -i #\''),
    ("deny", "case 読み TS7 項目の本体の外の引数の case は文を開かず、後ろの起動を拒否する", 'echo "$(echo then case x in x)"; python3 -i'),
    ("deny", "case 読み TS8 パターンの直後のコメントの中の ) は置換を閉じず、後ろの起動を拒否する", 'echo "$(case x in x)#)\n:;; esac)"; python3 -i'),
    ("deny", "case 読み TS9 対象の語の前の行継続を読み飛ばし、後ろの起動を拒否する", 'echo "$(case \\\nx in x) :;; esac)"; python3 -i'),
    ("deny", "case 読み TS10 空の case の esac の前の行継続を読み飛ばし、後ろの起動を拒否する", 'echo "$(case x in \\\nesac)"; python3 -i'),
    ("deny", "case 読み TS11 最初のパターンの前の行継続を読み飛ばし、後ろの起動を拒否する", 'echo "$(case x in \\\nx) :;; esac)"; python3 -i'),
    ("silent", "case 読み TS12 case の直後の行継続を読み飛ばして case 文を開き、引用符の中の python3 -i を拒否しない", 'echo "$(case\\\n x in x) echo "; python3 -i; ";; esac)"'),
    ("silent", "case 読み TS13 case を分断する行継続を取り除いて case 文を開き、引用符の中の python3 -i を拒否しない", 'echo "$(ca\\\nse x in x) echo "; python3 -i; ";; esac)"'),
    ("deny", "case 読み TS14 in の直後の行継続を読み飛ばし、後ろの起動を拒否する", 'echo "$(case x in\\\n x) :;; esac)"; python3 -i'),
    ("deny", "case 読み TS15 esac の直後の行継続を読み飛ばして文を閉じ、後ろの起動を拒否する", 'echo "$(case x in x) :;; esac\\\n)"; python3 -i'),
    ("deny", "case 読み TS16 in を分断する行継続を取り除いて in と読み、後ろの起動を拒否する", 'echo "$(case x i\\\nn x) :;; esac)"; python3 -i'),
    ("deny", "case 読み TS17 esac を分断する行継続を取り除いて esac と読み、後ろの起動を拒否する", 'echo "$(case x in x) :;; es\\\nac)"; python3 -i'),
    ("deny", "case 読み TS18 対を取り除くと casex になりキーワードではないので x) で置換が閉じ、引用の外の起動を拒否する", 'echo "$(ca\\\nsex in x) echo "; python3 -i; ";; esac)"'),
    ("silent", "case 読み TS19 対を取り除くと esacx のパターンになり、文を閉じない", 'echo "$(case x in es\\\nacx) echo "; python3 -i; ";; esac)"'),
    # codex-guard-case-reading-fixes (SPEC.md Test Scenarios TS23 to TS40): the
    # word after a compound-command closing (the `)` of a command-position `(`
    # or `((`, the `]]` of a command-position `[[`, a case-closing `esac`, a
    # command-position `fi`, `done` or `}`) is at a command position, so a
    # `case` after a `then`, `do` or `{` there opens a statement. After a
    # closing inside a word, a `]]` that closes no `[[` and a `fi` at an
    # argument position the following word is an argument. TS32 to TS36 are the
    # function heads (`name()`, `name ()`, `function name`, `function name()`).
    ("deny", "case 読み TS23 サブシェルの ) の後の then はコマンドの位置で、case が文を開く (finding 8aed11cf08b2dc4c の再現例)", 'echo "$(if (:) then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS24 [[ の条件式を閉じる ]] の後の then はコマンドの位置", 'echo "$(if [[ x ]] then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS25 サブシェルの ) の後の do はコマンドの位置", 'echo "$(while (false) do case x in x) printf \'%s\' \'"\';; esac; done)"; python3 -i'),
    ("deny", "case 読み TS26 算術コマンドの )) の後の then はコマンドの位置", 'echo "$(if ((1)) then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS27 コマンドの位置の fi の後の then はコマンドの位置", 'echo "$(if if :; then :; fi then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS28 コマンドの位置の done の後の then はコマンドの位置", 'echo "$(if while false; do :; done then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS29 コマンドの位置の } の後の then はコマンドの位置", 'echo "$(if { :; } then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS30 case 文を閉じる esac の後の then はコマンドの位置", 'echo "$(if case y in y) :;; esac then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS31 zsh の短い形で ]] の後の { はコマンドの位置", 'echo "$(if [[ x ]] { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("silent", "case 読み TS32 f() の後の { の中の case 文を読み、引用符の中の python3 -i を拒否しない (finding 2fe94b219da49a89 の誤拒否の形)", 'echo "$(f() { case x in x) echo "; python3 -i;";; esac; }; f)"'),
    ("deny", "case 読み TS33 f() の後の { の中の case 文を読み、置換の後の起動を拒否する (finding 2fe94b219da49a89 の拒否漏れの形)", 'echo "$(f() { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'),
    ("deny", "case 読み TS34 空白を挟んだ () の後の { はコマンドの位置", 'echo "$(f () { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'),
    ("deny", "case 読み TS35 function name の後の { はコマンドの位置", 'echo "$(function f { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'),
    ("deny", "case 読み TS36 function name() の後の { はコマンドの位置", 'echo "$(function f() { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'),
    ("deny", "case 読み TS37 語の中の置換の閉じの後の then は引数で、case は文を開かない", 'echo "$(echo "$(:)" then case x in x)"; python3 -i'),
    ("deny", "case 読み TS38 語の中の ( ) の閉じ (zsh の glob 修飾子) の後の then は引数", 'echo "$(echo x(N) then case x in x)"; python3 -i'),
    ("deny", "case 読み TS39 [[ を閉じていない ]] の後の then は引数", 'echo "$(echo ]] then case x in x)"; python3 -i'),
    ("deny", "case 読み TS40 引数の位置の fi の後の then は引数", 'echo "$(echo fi then case x in x)"; python3 -i'),
    # codex-guard-case-reading-fixes (SPEC.md Test Scenarios TS44 to TS59): the
    # word after the head of a loop, a coproc or a zsh repeat is at a command
    # position, the name after `for` is never a keyword, and a head word at an
    # argument position or quoted starts no head.
    ("deny", "case 読み TS44 算術の for の )) の後の do はコマンドの位置", 'echo "$(for ((i=0;i<1;i++)) do case x in x) printf \'%s\' \'"\';; esac; done)"; python3 -i'),
    ("deny", "case 読み TS45 for name の後の do はコマンドの位置", 'echo "$(for x do case x in x) printf \'%s\' \'"\';; esac; done)"; python3 -i'),
    ("deny", "case 読み TS46 coproc の後の { はコマンドの位置", 'echo "$(coproc { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("deny", "case 読み TS47 coproc NAME の後の { はコマンドの位置", 'echo "$(coproc c { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("deny", "case 読み TS48 for の後の名前 case はキーワードではなく、後ろの引数の case も文を開かない", 'echo "$(for case in x; do :; done; echo case x in x)"; python3 -i'),
    ("deny", "case 読み TS49 zsh の for name (words) の ) の後の { はコマンドの位置", 'echo "$(for x (a) { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("deny", "case 読み TS50 zsh の repeat word の後の { はコマンドの位置", 'echo "$(repeat 1 { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("deny", "case 読み TS51 select name の後の do はコマンドの位置", 'echo "$(select x do case x in x) printf \'%s\' \'"\';; esac; done)"; python3 -i'),
    ("silent", "case 読み TS52 for name の後の case 文の本体の、引用符の中の python3 -i を拒否しない", 'echo "$(for x do case x in x) echo "; python3 -i;";; esac; done)"'),
    ("silent", "case 読み TS53 coproc の後の case 文の本体の、引用符の中の python3 -i を拒否しない", 'echo "$(coproc { case x in x) echo "; python3 -i;";; esac; })"'),
    ("silent", "case 読み TS54 zsh の for name (words) の後の case 文の本体の、引用符の中の python3 -i を拒否しない", 'echo "$(for x (a) { case x in x) echo "; python3 -i;";; esac; })"'),
    ("silent", "case 読み TS55 zsh の repeat word の後の case 文の本体の、引用符の中の python3 -i を拒否しない", 'echo "$(repeat 1 { case x in x) echo "; python3 -i;";; esac; })"'),
    ("deny", "case 読み TS56 引数の位置の for からは頭の状態に入らず、case は文を開かない", 'echo "$(echo for x do case x in x)"; python3 -i'),
    ("deny", "case 読み TS57 引用された for からは頭の状態に入らない", 'echo "$("for" x do case x in x)"; python3 -i'),
    ("deny", "case 読み TS58 引数の位置の coproc からは頭の状態に入らない", 'echo "$(echo coproc { case x in x)"; python3 -i'),
    ("deny", "case 読み TS59 引数の位置の repeat からは頭の状態に入らない", 'echo "$(echo repeat 1 { case x in x)"; python3 -i'),
    # codex-guard-subst-reading-regressions (VERIFICATION.md TS1, TS5 to TS8 and
    # TS28): the word list of a zsh `for name (words)` is read in a context of
    # its own: a `#` comment and a newline are read as in a command list, and
    # no word of the list is at a command position.
    ("deny", "置換読み TS1 zsh の for の語一覧のコメントの中の二重引用符は引用を開かない (再現手順)", 'echo "$(for x (a # "\n) { :; })"; python3 -i'),
    ("deny", "置換読み TS5 語一覧のコメントの中の ) は語一覧を閉じない", 'echo "$(for x (a # )\n) { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("silent", "置換読み TS6 コメントを含む語一覧の後の case 文の本体の、引用符の中の python3 -i を拒否しない", 'echo "$(for x (a # \'\n) { case x in x) echo "; python3 -i;";; esac; })"'),
    ("deny", "置換読み TS7 語一覧の改行の後の case は文を開かない", 'echo "$(for x (a\ncase) { :; }; echo case x in x)"; python3 -i'),
    ("deny", "置換読み TS8 語一覧の ( の直後のコメント", 'echo "$(for x (# c\na) { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i'),
    ("deny", "置換読み TS28 語一覧の中の入れ子の ( ... ) の中の語はコマンドの位置にならず、その ) の後も語一覧として読む", 'echo "$(for x (a(case x in x)) { :; })"; python3 -i'),
    # codex-guard-for-wordlist-glob-qualifier (VERIFICATION.md TS-1, TS-2 and
    # TS-7): a `#` inside a nested `(` of the word list (a glob qualifier such
    # as `*(#qN)`) is a word character, not the start of a comment, so the
    # substitution closes where it should and the launch after it is denied.
    ("deny", "置換読み TS-1 語一覧の入れ子の ( の直後の # (glob 修飾子 *(#qN)) はコメントを始めず、置換の後の起動を拒否する (再現手順 zsh -c)", 'zsh -c \'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i\''),
    ("deny", "置換読み TS-2 語一覧の入れ子の ( の直後の # (glob 修飾子 *(#qN)) はコメントを始めず、置換の後の起動を拒否する (再現手順 最上位)", 'echo "$(for x (*(#qN)) { :; })"; python3 -i'),
    ("deny", "置換読み TS-7 語一覧の入れ子の ( ... ) の中で空白の後にある # も語の文字で、改行が無くても置換の後の起動を拒否する", 'echo "$(for x (a(b #c)) { :; })"; python3 -i'),
    # codex-guard-procsub-in-wordlist (SPEC.md Test Scenarios TS-1 to TS-14): in
    # the outermost entry of the word list of a zsh `for`, an unquoted,
    # unescaped `<(`, `>(` or `=(` at the start of a word is a process
    # substitution, read as a command list whose `)` closes inside the word;
    # any other `(` of the list stays a nested entry, where a `#` is a word
    # character. The commands are the SPEC.md Python string literals, so `\n` is
    # a newline and `\\` is one backslash.
    ("deny", "語一覧プロセス置換 TS-1 項目を開く ( の直後の <( は p で、中の空白の後の # がコメントを始めるので、後ろの起動を拒否する (拒否漏れの再現)", 'zsh -c \'echo "$(for x (<(: # "\n)) { :; })"; python3 -i\''),
    ("silent", "語一覧プロセス置換 TS-2 <( の中のコメントの ) は閉じず、後ろの引用符の中の python3 -i を拒否しない (誤拒否の再現)", 'zsh -c \'echo "$(for x (<(printf x # )))"; python3 -i; echo "\n)) { :; })"\''),
    ("deny", "語一覧プロセス置換 TS-3 >( も語の先頭で p を開く", 'echo "$(for x (>(: # "\n)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-4 =( も語の先頭で p を開く", 'echo "$(for x (=(: # "\n)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-5 空白の後の語の先頭の <( は p", 'echo "$(for x (a <(: # "\n)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-6 エスケープした < の後の ( は入れ子の w で、# は語の文字", 'echo "$(for x (\\<(b #c)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-7 語の途中の =( は入れ子の w で、# は語の文字", 'echo "$(for x (a=(b #c)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-8 数値範囲 glob <-> の後の ( は glob 修飾子で、>( は語の途中", 'echo "$(for x (<->(#qN)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-9 入れ子の項目の中の <( は入れ子の w のまま", 'echo "$(for x (a(<(b #c))) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-10 引用符で囲んだ < の後の ( は入れ子の w", 'echo "$(for x ("<"(b #c)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-11 入れ子の項目の中の =( は入れ子の w のままで、# は語の文字", 'echo "$(for x (a(=(: #c))) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-12 エスケープした空白は語の文字なので =( は語の途中", 'echo "$(for x (a\\ =(b #c)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-13 語の途中の継続行は語を区切らないので =( は語の途中", 'echo "$(for x (a\\\n=(b #c)) { :; })"; python3 -i'),
    ("deny", "語一覧プロセス置換 TS-14 空白の後の継続行は語の先頭の状態を保つので <( は p", 'echo "$(for x (a \\\n<(: # "\n)) { :; })"; python3 -i'),
    # codex-guard-case-reading-fixes (VERIFICATION.md TS61): a reserved word, a
    # closing word or a head word that a continuation pair splits is read as
    # that word.
    ("deny", "case 読み TS61 行継続の対で分断された then を then と読み、サブシェルの ) の後の case が文を開く", 'echo "$(if (:) th\\\nen case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS61 行継続の対で分断された fi を fi と読み、その後の then はコマンドの位置", 'echo "$(if if :; then :; f\\\ni then case x in x) printf \'%s\' \'"\';; esac; fi)"; python3 -i'),
    ("deny", "case 読み TS61 行継続の対で分断された for を for と読み、名前の後の do はコマンドの位置", 'echo "$(f\\\nor x do case x in x) printf \'%s\' \'"\';; esac; done)"; python3 -i'),
    # codex-guard-subst-reading-regressions (VERIFICATION.md TS2, TS9 to TS12 and
    # TS29): the `()` of a function head is empty when only spaces, tabs and
    # continuation pairs lie between the parentheses, so the `{` after it is at
    # a command position and the `case` in the body opens a statement. A
    # backslash followed by anything other than a newline is no pair.
    ("deny", "置換読み TS2 f(\\<NL>) の対を空白と同じに読み、本体の case 文を読んで、後ろの起動を拒否する (欠陥 2 の再現)", "bash -c " + shlex.quote('echo "$(f(\\\n) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')),
    ("deny", "置換読み TS9 空白を挟んだ ( の後の対を空の () と読み、後ろの起動を拒否する", "bash -c " + shlex.quote('echo "$(f (\\\n) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')),
    ("deny", "置換読み TS10 function name( の後の対を空の () と読み、後ろの起動を拒否する", "bash -c " + shlex.quote('echo "$(function f(\\\n) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')),
    ("deny", "置換読み TS11 空白と複数の対が混ざった空の () を読み、後ろの起動を拒否する", "bash -c " + shlex.quote('echo "$(f( \\\n\\\n ) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')),
    ("silent", "置換読み TS12 対を挟んだ関数の本体の、引用符の中の python3 -i を拒否しない", "bash -c " + shlex.quote('echo "$(f(\\\n) { case x in x) echo "; python3 -i;";; esac; }; f)"')),
    ("silent", "置換読み TS29 改行でない文字が続くバックスラッシュは対でなく、() は空でないので本体の case 文を読まない", 'echo "$(f(\\ ) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'),
    # codex-guard-heredoc-delim-brace-quote: the `${ ... }` of a `<<` / `<<-`
    # delimiter is read the way zsh reads it (SPEC.md Test Scenarios TS1 to TS34).
    # Each command is the scenario's line array joined with newlines; the array
    # is written as in SPEC.md, so its escapes decode to the scenario's characters.
    ("deny", "区切り語の ${...} の二重引用符を除いた終端行の後の起動は deny (再現手順)", "\n".join(["zsh -c 'cat <<${v:-\"x\"}","body","${v:-x}","python3 -i'"])),
    ("silent", "引用を除く前の ${...} の行では本文が閉じない", "\n".join(["cat <<${v:-\"x\"}","${v:-\"x\"}","python3 -i","${v:-x}"])),
    ("deny", "${...} の単引用符を除く", "\n".join(["cat <<${v:-'x'}","${v:-x}","python3 -i"])),
    ("deny", "${...} のバックスラッシュを除く", "\n".join(["cat <<${v:-\\x}","${v:-x}","python3 -i"])),
    ("deny", "${...} の引用の後ろの文字はつなぐ", "\n".join(["cat <<${v:-\"x\"y}","${v:-xy}","python3 -i"])),
    ("deny", "${v#...} の引用を除く", "\n".join(["cat <<${v#\"x\"}","${v#x}","python3 -i"])),
    ("deny", "${...} の前後の部分はそのままつなぐ", "\n".join(["cat <<foo${v:-\"x\"}bar","foo${v:-x}bar","python3 -i"])),
    ("deny", "<<- は先頭タブを除いて ${...} の引用を除いた区切り語と比べる", "\n".join(["cat <<-${v:-\"x\"}","\t${v:-x}","python3 -i"])),
    ("deny", "${...} の二重引用符の中の } で閉じない", "\n".join(["cat <<${v:-\"a}b\"}","${v:-a}b}","python3 -i"])),
    ("deny", "${...} の単引用符の中の } で閉じない", "\n".join(["cat <<${v:-'a}b'}","${v:-a}b}","python3 -i"])),
    ("deny", "${...} の逃がした } で閉じない", "\n".join(["cat <<${v:-\\}}","${v:-}}","python3 -i"])),
    ("deny", "入れ子の ${...} の閉じで外側を閉じない", "\n".join(["cat <<${a:-${b:-\"x\"}}","${a:-${b:-x}}","python3 -i"])),
    ("deny", "${...} の中の $( ) は引用を含め書かれたまま区切り語になる", "\n".join(["cat <<${v:-$(echo \"x\")}","${v:-$(echo \"x\")}","python3 -i"])),
    ("silent", "${...} の中の $( ) の引用を除いた行では本文が閉じない", "\n".join(["cat <<${v:-$(echo \"x\")}","${v:-$(echo x)}","python3 -i","${v:-$(echo \"x\")}"])),
    ("deny", "${...} の中の $( ) の } で閉じない", "\n".join(["cat <<${v:-$(echo \"}\")}","${v:-$(echo \"}\")}","python3 -i"])),
    ("deny", "${...} の二重引用符の中の $' は判定不能にしない", "\n".join(["cat <<${v:-\"$'\"}","${v:-$'}","python3 -i"])),
    ("deny", "${...} の逃がした $ は判定不能にしない", "\n".join(["cat <<${v:-\\$'x'}","${v:-$x}","python3 -i"])),
    ("silent", "${...} の中の引用されていない $' は判定不能", "\n".join(["cat <<${v:-$'x'}","${v:-$'x'}","python3 -i","${v:-x}"])),
    ("silent", "${...} の中の引用されていない $\" は判定不能", "\n".join(["cat <<${v:-$\"x\"}","${v:-$\"x\"}","python3 -i"])),
    ("silent", "${...} の閉じを確定できなければ判定不能", "\n".join(["cat <<${v:-\"a}","python3 -i"])),
    ("silent", "区切り語の引用されていない $' は判定不能", "\n".join(["cat <<$'x'","$'x'","python3 -i","x"])),
    ("silent", "区切り語の引用されていない $\" は判定不能", "\n".join(["cat <<$\"x\"","x","python3 -i","$x"])),
    ("silent", "区切り語の途中の引用されていない $' は判定不能", "\n".join(["cat <<foo$'x'","foo$'x'","python3 -i","foox"])),
    ("deny", "区切り語の二重引用符の中の $' は判定不能にしない", "\n".join(["cat <<\"$'x'\"","$'x'","python3 -i"])),
    ("deny", "区切り語の逃がした $ は判定不能にしない", "\n".join(["cat <<\\$'x'","$x","python3 -i"])),
    ("deny", "判定不能な ${...} の区切り語より前の行の起動は deny", "\n".join(["python3 -i","cat <<${v:-$'x'}","${v:-x}","python3 -i"])),
    ("deny", "判定不能な $\" の区切り語より前の行の起動は deny", "\n".join(["python3 -i","cat <<$\"x\"","x"])),
    ("silent", "判定不能な区切り語と同じ行の起動は判定しない", "\n".join(["python3 -i; cat <<$'x'","x"])),
    ("deny", "区切り語でない ${...} の読みは変えない", "\n".join(["echo ${v:-\"x\"}; python3 -i"])),
    ("deny", "<<< の目標の ${...} の $' は判定不能にしない", "\n".join(["cat <<< ${v:-$'x'}; python3 -i"])),
    ("deny", "<<< の目標の $' は判定不能にしない", "\n".join(["cat <<< $'x'; python3 -i"])),
    ("deny", "区切り語でない $\" は判定不能にしない", "\n".join(["echo $\"x\"; python3 -i"])),
    ("deny", "区切り語の二重引用符の中の ${...} の読みは変えない", "\n".join(["cat <<\"${v:-x}\"","${v:-x}","python3 -i"])),
    ("deny", "${...} の中のバッククォートは文字のまま残す", "\n".join(["cat <<${v:-`echo x`}","${v:-`echo x`}","python3 -i"])),
    # codex-guard-heredoc-delim-brace-case (VERIFICATION.md TS1 to TS9): an
    # unquoted `$( ... )` inside the `${ ... }` of a `<<` / `<<-` delimiter is
    # skipped by the case-aware substitution skip and kept as written, so a
    # case statement in it is read through to its `esac`. Each command is the
    # scenario's line array joined with newlines.
    ("deny", "区切り語の ${...} の中の case 文を含む $( ) を書かれたまま区切り語にし、終端行の後の起動は deny (再現手順)", "\n".join(["zsh -c 'cat <<${v:-$(case x in x) echo \"x\";; esac)}","${v:-$(case x in x) echo \"x\";; esac)}","python3 -i'"])),
    ("deny", "最上位の ${...} の中の case 文を含む $( ) の引用を残す", "\n".join(["cat <<${v:-$(case x in x) echo \"x\";; esac)}","${v:-$(case x in x) echo \"x\";; esac)}","python3 -i"])),
    ("silent", "case 文を含む $( ) の引用を除いた行では本文が閉じない", "\n".join(["cat <<${v:-$(case x in x) echo \"x\";; esac)}","${v:-$(case x in x) echo x;; esac)}","python3 -i","${v:-$(case x in x) echo \"x\";; esac)}"])),
    ("deny", "case 文の本体の引用の中の } で ${...} を閉じない", "\n".join(["cat <<${v:-$(case x in x) echo \"}\";; esac)}","${v:-$(case x in x) echo \"}\";; esac)}","python3 -i"])),
    ("deny", "先頭の ( を持つパターンの case 文を読む", "\n".join(["cat <<${v:-$(case x in (x) echo \"x\";; esac)}","${v:-$(case x in (x) echo \"x\";; esac)}","python3 -i"])),
    ("deny", "${...} の中の $(( )) は書かれたまま区切り語になる", "\n".join(["cat <<${v:-$((1+2))}","${v:-$((1+2))}","python3 -i"])),
    ("deny", "<<- は先頭タブを除いて case 文を含む $( ) を残した区切り語と比べる", "\n".join(["cat <<-${v:-$(case x in x) echo \"x\";; esac)}","\t${v:-$(case x in x) echo \"x\";; esac)}","python3 -i"])),
    ("silent", "${...} の中の esac で閉じない case 文は判定不能", "\n".join(["cat <<${v:-$(case x in x) echo \"x\";;}","python3 -i"])),
    ("deny", "判定不能な case 文を含む区切り語より前の行の起動は deny", "\n".join(["python3 -i","cat <<${v:-$(case x in x) :;;}","x"])),
    # Not in the scenario list: TS8 passes whichever skip reads the `$( ... )`
    # (the heredoc body is never closed), so this row adds a line equal to the
    # delimiter with its quotes removed, which only a reading that registers
    # that delimiter lets close the body.
    ("silent", "esac で閉じない case 文を含む ${...} の区切り語は、引用を除いた行があっても判定不能", "\n".join(["cat <<${v:-$(case x in x) echo \"x\";;}","${v:-$(case x in x) echo x;;}","python3 -i"])),
    # codex-guard-subst-reading-regressions (VERIFICATION.md TS3, TS4, TS13 to
    # TS24, TS30, TS31): coproc and repeat are read by the kind of the shell that
    # directly holds the string (bash, zsh or unknown), and an unknown-kind
    # string that stops undecidable is read once more with neither shell-specific
    # rule. `bash -c ` + shlex.quote(s) is the SPEC.md notation wrap_bash(s), and
    # `zsh -c ` + shlex.quote(s) is wrap_zsh(s); the wrapped rows repeat the
    # earlier feature's row command (its TS46, TS47, TS50 and TS53) literally.
    ("deny", "置換読み TS3 zsh の coproc は NAME を取らず、後ろの case は文を開かない（再現手順）", 'zsh -c \'echo "$(coproc echo case x in x)"; python3 -i\''),
    ("deny", "置換読み TS4 bash の repeat は普通のコマンドで、後ろの case は文を開かない", 'bash -c \'echo "$(repeat x case y in y)"; python3 -i\''),
    ("deny", "置換読み TS13 bash の coproc NAME の後の { はコマンドの位置", "bash -c " + shlex.quote('echo "$(coproc c { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i')),
    ("deny", "置換読み TS14 bash では coproc WORD の後の case が文を開く", "bash -c " + shlex.quote('echo "$(coproc echo case x in x) printf \'%s\' \'"\';; esac)"; python3 -i')),
    ("deny", "置換読み TS15 zsh の repeat word の後の { はコマンドの位置", "zsh -c " + shlex.quote('echo "$(repeat 1 { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i')),
    ("deny", "置換読み TS16 zsh の coproc の後の { はコマンドの位置", "zsh -c " + shlex.quote('echo "$(coproc { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i')),
    ("silent", "置換読み TS17 zsh の coproc { の後の case 文の本体の、引用符の中の python3 -i を拒否しない", "zsh -c " + shlex.quote('echo "$(coproc { case x in x) echo "; python3 -i;";; esac; })"')),
    ("deny", "置換読み TS18 bash の repeat は普通のコマンドで、{ と case は引数", 'bash -c \'echo "$(repeat 1 { case x in x)"; python3 -i\''),
    ("deny", "置換読み TS19 最上位（シェルが分からない場合）の coproc の形は、初回が判定不能で読み直しで deny", 'echo "$(coproc echo case x in x)"; python3 -i'),
    ("deny", "置換読み TS20 最上位（シェルが分からない場合）の repeat の形は、初回が判定不能で読み直しで deny", 'echo "$(repeat x case y in y)"; python3 -i'),
    ("deny", "置換読み TS21 sh の -c 文字列はシェルが分からない場合として読み直す", 'sh -c \'echo "$(coproc echo case x in x)"; python3 -i\''),
    ("deny", "置換読み TS22 読み直しも失敗したら、初回の確定済みのコマンド（チェックポイントまで）を判定する", 'python3 -i\necho "$(repeat x case y in y'),
    ("silent", "置換読み TS23 bash と分かっている文字列は読み直さない（case が文を開いて閉じない）", 'bash -c \'echo "$(coproc echo case x in x)"; python3 -i\''),
    ("deny", "置換読み TS24 外側が bash でも、内側の zsh -c の文字列は zsh として読む", "bash -c " + shlex.quote('zsh -c \'echo "$(coproc echo case x in x)"; python3 -i\'')),
    ("silent", "置換読み TS30 env とパスを経由した zsh も zsh として読み、coproc NAME の規則を使わない", "env /usr/bin/zsh -c " + shlex.quote('echo "$(coproc echo case x in x) printf \'%s\' \'"\';; esac)"; python3 -i')),
    ("silent", "置換読み TS31 env を経由した版数つきの bash は bash として読み、読み直さない", "env bash5.2 -c " + shlex.quote('echo "$(coproc echo case x in x)"; python3 -i')),
    # codex-guard-delim-subst-undecidable (SPEC.md Test Scenarios TS1 to TS15;
    # TS14 is the existing row "case 文の項目の本体の中の heredoc は判定不能..."
    # above). The shared substitution skip reads a same-line `<<` outside a case
    # statement, a command-position `((` and a parenthesis in an argument word to
    # the `)` zsh closes the substitution at, so a heredoc delimiter `${ ... }`
    # holding one of them ends where zsh ends it and the launch after the
    # terminator line is judged. The silent rows name a body that does not close
    # (terminator mismatch) or a reading that stays undecidable. TS13 is the
    # same-line `*(#qN)` form: under zsh 5.9 a delimiter split across two lines
    # (`*(e:true` / `:N))}`) is not closed by a terminator split the same way, so
    # the body takes every later line and the line-split form launches nothing.
    ("deny", "区切り語の置換の中の同じ行の << TS1 再現手順: if の中のコロンコマンドの区切り語を読み、終端行の後の起動を拒否する", "\n".join(["zsh -c 'if false; then", ": <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "fi", "python3 -i'"])),
    ("deny", "区切り語の置換の中の同じ行の << TS2 区切り語全体を終端行と比べ、後ろの起動を拒否する", "\n".join(["cat <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "python3 -i"])),
    ("silent", "区切り語の置換の中の同じ行の << TS3 終端行が EOF だけでは本文が閉じない", "\n".join(["cat <<${v:-$(echo <<EOF)}", "EOF", "python3 -i"])),
    ("deny", "区切り語の置換の中の算術コマンド TS4 コマンドの位置の (( )) の << は左シフトで、後ろの起動を拒否する", "\n".join(["cat <<${v:-$( ((1 << 2)) )}", "${v:-$( ((1 << 2)) )}", "python3 -i"])),
    ("silent", "区切り語の置換の中の算術コマンド TS5 短い終端行では本文が閉じない", "\n".join(["cat <<${v:-$( ((1 << 2)) )}", "2)) )}", "python3 -i"])),
    ("deny", "区切り語の置換の中の算術コマンド TS6 for の後の (( )) の << は左シフトで、後ろの起動を拒否する", "\n".join(["cat <<${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "python3 -i"])),
    ("deny", "区切り語の置換の中の語の括弧 TS7 foo(case x) は語の中の括弧で、後ろの起動を拒否する", "\n".join(["cat <<${v:-$(echo foo(case x))}", "${v:-$(echo foo(case x))}", "python3 -i"])),
    ("silent", "区切り語の置換の中の語の括弧 TS8 短い終端行では本文が閉じない", "\n".join(["cat <<${v:-$(echo foo(case x))}", "x))}", "python3 -i"])),
    ("deny", "区切り語の置換の中の語の括弧 TS9 foo(a;b) の ; は語の文字で、後ろの起動を拒否する", "\n".join(["cat <<${v:-$(echo foo(a;b))}", "${v:-$(echo foo(a;b))}", "python3 -i"])),
    ("deny", "語の括弧 TS10 回帰: 二重引用符の中の foo(a;b) は今のまま deny", 'echo "$(echo foo(a;b))"; python3 -i'),
    ("deny", "算術コマンドの読み直し TS11 回帰: (( の対応する閉じが )) でなければ入れ子のサブシェルとして読み、deny のまま", 'echo "$( ((echo a) ) )"; python3 -i'),
    ("deny", "置換の中の同じ行の << TS12 二重引用符の中の置換で閉じる << は判定でき、後ろの起動を拒否する", 'echo "$(cat <<EOF)"; python3 -i'),
    ("deny", "区切り語の置換の中の語の括弧 TS13 同じ行に収まる *(#qN) の形: # は語の文字で、後ろの起動を拒否する", "\n".join(["cat <<${v:-$(echo *(#qN))}", "${v:-$(echo *(#qN))}", "python3 -i"])),
    ("silent", "置換の中の << TS15 << の後、置換の中で改行が来る形は判定不能で、後ろの起動を拒否しない", 'echo "$(cat <<EOF\nbody\nEOF\n)"; python3 -i'),
    # The edges of the same readings that the scenarios above do not name.
    ("deny", "置換の中の同じ行の << <<- の形も同じ行で閉じれば判定でき、後ろの起動を拒否する", 'echo "$(cat <<-EOF)"; python3 -i'),
    ("deny", "置換の中の同じ行の << 入れ子の置換が閉じれば << の保留は外れ、外側の改行は判定不能にしない", 'echo "$(echo $(cat <<EOF)\necho foo)"; python3 -i'),
    ("deny", "置換の中の同じ行の << <<< は heredoc ではなく、後ろの起動を拒否する", 'echo "$(cat <<<x)"; python3 -i'),
    ("silent", "置換の中の << case 文の対象の語の << は判定不能のまま", 'echo "$(case <<x in x) :;; esac)"; python3 -i'),
    ("silent", "置換の中の << case 文の項目の本体の入れ子の置換の << も判定不能のまま", 'echo "$(case x in x) echo $(cat <<EOF);; esac)"; python3 -i'),
    ("silent", "置換の中の << 保留した << の後の語の括弧の中の改行は判定不能", 'echo "$(cat <<EOF foo(a\nb))"; python3 -i'),
    ("deny", "算術コマンド 単独の (( )) の << は左シフトで、後ろの起動を拒否する", 'echo "$( (( 1 << 2 )) )"; python3 -i'),
    ("deny", "算術コマンド case 文の項目の本体のコマンドの位置の (( )) も算術として読み、後ろの起動を拒否する", 'echo "$(case x in x) ((1 << 2));; esac)"; python3 -i'),
    ("deny", "算術コマンドの読み直し 入れ子のサブシェル 2 段として読み直した中の続きも読み、deny のまま", 'echo "$( ((echo a); echo b) )"; python3 -i'),
    ("deny", "算術コマンドでない空白を挟んだ ( ( は入れ子のサブシェルのまま読み、deny のまま", 'echo "$( ( (echo a) ) )"; python3 -i'),
    ("silent", "算術コマンドでない空白を挟んだ ( ( の << は heredoc で、本文の改行は判定不能のまま", 'echo "$( ( (cat <<EOF\nbody\nEOF\n) ) )"; python3 -i'),
    ("deny", "語の括弧 二重引用符の中の *(#qN) の # は語の文字で、後ろの起動を拒否する", 'echo "$(echo *(#qN))"; python3 -i'),
    ("deny", "語の括弧 入れ子の括弧は同じ文脈の入れ子で、中の ; は語の文字", 'echo "$(echo foo(a(b;c)d))"; python3 -i'),
    # codex-guard-escaped-hash-brace-case-heredoc (VERIFICATION.md TS-1, TS-2
    # and TS-5 to TS-11, task0001): the comment-start decision of the
    # substitution reader. A `#` starts a comment exactly when its effective
    # previous character, the one right before it once the continuation pairs
    # directly in front of it are left out, is a blank, a tab, a newline, `;`,
    # `&`, `|` or `(` and is not escaped (the run of backslashes in front of
    # it has even length). Every other `#` is a word character. A comment that
    # runs to the end of the input, with no newline, makes the chunk
    # undecidable, so a `silent` row holds a comment of that kind and a `deny`
    # row holds a `#` that is a word character.
    ("deny", "置換の # の判定 TS-1 語一覧のプロセス置換の中で、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'zsh -c \'echo "$(for x (<(: \\ #x)) { :; })"; python3 -i\''),
    ("deny", "置換の # の判定 TS-2 コマンド列の中で、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'zsh -c \'echo "$(: \\ #x)"; python3 -i\''),
    ("deny", "置換の # の判定 TS-5 語の文字の後の継続行の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\\n#x)"; python3 -i'),
    ("silent", "置換の # の判定 TS-6 空白の後の継続行の後の # はコメントで、コメントの中の ) で閉じず、後ろの起動を拒否しない", 'zsh -c \'echo "$(printf x \\\n# )"; python3 -i; echo "\n)"\''),
    ("deny", "置換の # の判定 TS-7 エスケープした ; の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\;#x)"; python3 -i'),
    ("deny", "置換の # の判定 TS-8 項目本体で、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(case x in x) : \\ #y;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 TS-9 パターンで、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(case x in a\\ #b) :;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 TS-10 語一覧の最も外側の項目で、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(for x (a\\ #b) { :; })"; python3 -i'),
    ("deny", "置換の # の判定 TS-11 > の直後の # は今のまま語の文字で、後ろの起動を拒否する", 'echo "$(: >#x)"; python3 -i'),
    # The continuation pairs: several of them in front of the `#` count as one
    # stretch that is left out, and the pair between an escaped blank and the
    # `#` leaves the blank escaped.
    ("deny", "置換の # の判定 語の文字の後に継続行が 2 つ続いても # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\\n\\\n#x)"; python3 -i'),
    ("silent", "置換の # の判定 空白の後に継続行が 2 つ続いても # はコメントで、コメントの中の ) で閉じず、後ろの起動を拒否しない", 'zsh -c \'echo "$(printf x \\\n\\\n# )"; python3 -i; echo "\n)"\''),
    ("deny", "置換の # の判定 エスケープした空白と # の間に継続行があっても # は語の文字で、後ろの起動を拒否する", 'echo "$(: \\ \\\n#x)"; python3 -i'),
    ("silent", "置換の # の判定 空白の後の継続行の後の # は、改行が来るまでのコメントで、閉じが無いので後ろの起動を拒否しない", 'echo "$(: \\\n#x)"; python3 -i'),
    ("silent", "置換の # の判定 エスケープしたバックスラッシュの後の改行は継続行でなく、その後ろの # はコメントで、後ろの起動を拒否しない", 'echo "$(: a\\\\\n#x)"; python3 -i'),
    # The escaped characters in front of the `#`: a tab, `&`, `|` and `(`.
    ("deny", "置換の # の判定 エスケープしたタブの後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: \\\t#x)"; python3 -i'),
    ("deny", "置換の # の判定 エスケープした & の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\&#x)"; python3 -i'),
    ("deny", "置換の # の判定 エスケープした | の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\|#x)"; python3 -i'),
    ("deny", "置換の # の判定 エスケープした ( の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: a\\(#x)"; python3 -i'),
    # The parity of the backslash run in front of the blank decides whether the
    # blank is escaped.
    ("silent", "置換の # の判定 エスケープしたバックスラッシュ (偶数個) の後の空白はエスケープされず、その後の # はコメントで、後ろの起動を拒否しない", 'echo "$(: \\\\ #x)"; python3 -i'),
    ("deny", "置換の # の判定 バックスラッシュが 3 個 (奇数個) 続いた後の空白はエスケープされ、その後の # は語の文字で、後ろの起動を拒否する", 'echo "$(: \\\\\\ #x)"; python3 -i'),
    # The other sites of the decision: a group of a pattern, a pattern and an
    # item body with a continuation pair, the outermost entry of a word list
    # with a continuation pair.
    ("deny", "置換の # の判定 パターンの括弧の群の中で、エスケープした空白の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(case x in a(b\\ #c)) :;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 パターンで、語の文字の後の継続行の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(case x in a\\\n#b) :;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 項目本体で、語の文字の後の継続行の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(case x in x) : a\\\n#y;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 語一覧の最も外側の項目で、語の文字の後の継続行の後の # は語の文字で、後ろの起動を拒否する", 'echo "$(for x (a\\\n#b) { :; })"; python3 -i'),
    ("silent", "置換の # の判定 項目本体で、空白の後の継続行の後の # はコメントで、後ろの起動を拒否しない", 'echo "$(case x in x) : \\\n#y;; esac)"; python3 -i'),
    ("silent", "置換の # の判定 パターンで、空白の後の継続行の後の # はコメントで、後ろの起動を拒否しない", 'echo "$(case x in a \\\n#b) :;; esac)"; python3 -i'),
    ("silent", "置換の # の判定 語一覧の最も外側の項目で、空白の後の継続行の後の # はコメントで、後ろの起動を拒否しない", 'echo "$(for x (a \\\n#b) { :; })"; python3 -i'),
    # The readings that stay: a `#` right after `<`, and a `#` right after the
    # `)` of a pattern with a continuation pair between them (rule 3).
    ("deny", "置換の # の判定 < の直後の # は今のまま語の文字で、後ろの起動を拒否する", 'echo "$(cat <#x)"; python3 -i'),
    ("deny", "置換の # の判定 パターンの ) と # の間に継続行があっても # はコメントで、コメントの中の ) で閉じず、後ろの起動を拒否する", 'echo "$(case x in x)\\\n# )\n:;; esac)"; python3 -i'),
    # The newline that ends a comment is never part of a continuation pair
    # (review round 1, task0003): a backslash inside a comment is comment text,
    # so the `#` at the start of the next line starts a comment again. The `'`
    # of `don't` shows it: read as code it opens a quote that never closes, and
    # the launch after the substitution would go unjudged. TS-30 to TS-34 are
    # the form at each site that reads a comment; TS-35 is the line after the
    # comment read as a comment that holds the `)` and the launch.
    ("deny", "置換の # の判定 TS-30 バックスラッシュで終わるコメントの次の行頭の # もコメントで、コメントの中の ' は引用を開かず、後ろの起動を拒否する", 'echo "$(: a #b\\\n# don\'t\n)"; python3 -i'),
    ("deny", "置換の # の判定 TS-31 項目本体で、バックスラッシュで終わるコメントの次の行頭の # もコメントで、後ろの起動を拒否する", 'echo "$(case x in x) : a #b\\\n# don\'t\n;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 TS-32 パターンの位置 (フェーズ 4) で、バックスラッシュで終わるコメントの次の行頭の # もコメントで、後ろの起動を拒否する", 'echo "$(case x in #b\\\n# don\'t\nx) :;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 TS-33 パターンの ) の直後 (フェーズ 7、規則 3) で、バックスラッシュで終わるコメントの次の行頭の # もコメントで、後ろの起動を拒否する", 'echo "$(case x in x)#b\\\n# don\'t\n:;; esac)"; python3 -i'),
    ("deny", "置換の # の判定 TS-34 語一覧の最も外側の項目で、バックスラッシュで終わるコメントの次の行頭の # もコメントで、後ろの起動を拒否する", 'echo "$(for x (a #b\\\n# don\'t\n) { :; })"; python3 -i'),
    ("silent", "置換の # の判定 TS-35 バックスラッシュで終わるコメントの次の行はコメントで、その中の ) と後ろの起動は置換を閉じず、後ろの起動を拒否しない", 'zsh -c \'echo "$(: a #b\\\n# )"; python3 -i; echo "\n)"\''),
    # codex-guard-delim-brace-quote-per-shell (SPEC.md Test Scenarios TS1 to
    # TS32), built from DELIMITER_PER_SHELL_ROWS by the construction rule of
    # SPEC.md. The shell that directly holds a nested `-c` string decides how
    # the `${ ... }` ranges of its heredoc delimiter are registered: bash by the
    # written form, sh and ksh by both readings, every other reading as before.
    *[
        (expected, label, delimiter_command(wrap, lines))
        for _, expected, label, wrap, lines in DELIMITER_PER_SHELL_ROWS
    ],
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


def run_hook(path, payload, cwd=None, env=None, timeout=None):
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
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class HookCopiesMixin:
    """Run each test body against both copies of the hook."""

    def for_each_copy(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                yield plugin, path


# The value the specification gives the re-read limit: the characters a
# second-level-and-deeper string may add to the running total.
NESTED_READ_LIMIT = 1000000


def sq(text):
    """Quote `text` for a shell inside single quotes."""
    return "'" + text.replace("'", "'\\''") + "'"


def holding(*strings):
    """Commands that each run one of `strings` as a literal shell `-c` string.
    The length of a string as the parser sees it is its own length, so the
    boundary arithmetic of the limit tests stays plain."""
    return "; ".join("bash -c " + sq(text) for text in strings)


def padded_echo(length):
    """A string of exactly `length` characters that echoes quoted padding."""
    head, tail = "echo '", "'"
    return head + "x" * (length - len(head) - len(tail)) + tail


def padded_launch(length, launch="python3 -i"):
    """A string of exactly `length` characters that echoes quoted padding and
    then runs `launch`."""
    head, tail = "echo '", "'; " + launch
    return head + "x" * (length - len(head) - len(tail)) + tail


def unreadable(length):
    """A string of exactly `length` characters with an unbalanced quote."""
    head = "echo '"
    return head + "x" * (length - len(head))


def quoted_nesting(depth):
    """`python3 -i` inside `depth` shell `-c` strings, each level quoted again.
    Return (command, counted): counted is the total length of the strings from
    the second level down, which is what the limit counts."""
    levels = ["python3 -i"]
    for _ in range(depth):
        levels.append(holding(levels[-1]))
    return levels[-1], sum(len(text) for text in levels[:depth - 1])


def deepest_nesting_within_the_limit():
    depth = 1
    while quoted_nesting(depth + 1)[1] <= NESTED_READ_LIMIT:
        depth += 1
    return depth


class TestCasesTable(HookCopiesMixin, unittest.TestCase):
    def test_cases_hold_both_a_deny_and_a_silent_case(self):
        verdicts = {expected for expected, _, _ in CASES}
        self.assertEqual(verdicts, {"deny", "silent"})

    def test_cases_are_unique(self):
        commands = [command for _, _, command in CASES]
        self.assertEqual(len(commands), len(set(commands)))

    def test_the_escaped_backquote_reproduction_is_one_deny_row(self):
        rows = [row for row in CASES if row[2] == ESCAPED_BACKQUOTE_REPRODUCTION]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "deny")

    def test_the_escaped_backquote_reproduction_decodes_to_the_intended_characters(self):
        command = ESCAPED_BACKQUOTE_REPRODUCTION
        self.assertEqual(command.count("\\"), 2)
        self.assertEqual(command.count("`"), 4)
        self.assertEqual(command.count("\\`"), 2)

    def test_the_bash_c_section_comment_says_every_level_is_judged(self):
        lines = [
            line.strip()
            for line in Path(__file__).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("# bash -c:")
        ]
        self.assertEqual(len(lines), 1)
        self.assertIn("literal shell `-c` strings are judged at every level", lines[0])
        self.assertNotIn("one level", lines[0])

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


class TestMalformedAndDeepInput(HookCopiesMixin, unittest.TestCase):
    """Input the parser cannot follow ends as a verdict, never as an error
    (NFR1, TM-3). The tests do not fix the verdict for deep input: they check
    that the process ends in time with exit status 0, that standard output is
    empty or exactly one deny object, and that nothing reaches standard error.
    """

    DEPTH = 6000  # the criteria ask for at least 5000 levels
    RESERVED_RUN = 50000  # the criteria ask for at least 50,000 reserved words
    TIMEOUT = 60

    def assert_answers(self, path, command):
        code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
        self.assertEqual(code, 0)
        self.assertEqual(err, "", "nothing may reach standard error")
        if out == "":
            return
        obj, end = json.JSONDecoder().raw_decode(out)
        self.assertEqual(out[end:].strip(), "", "standard output holds one object")
        self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "deny")

    def assert_every_copy_answers(self, command):
        for plugin, path in self.for_each_copy():
            self.assert_answers(path, command)

    def test_an_unclosed_group_is_answered(self):
        for command in ("(python3", "{ python3;", "( (python3)", "{ { python3; }"):
            with self.subTest(command=command):
                self.assert_every_copy_answers(command)

    def test_substitutions_nested_deeply_inside_double_quotes_are_answered(self):
        depth = self.DEPTH
        inputs = {
            "closed": 'echo ' + '"$(echo ' * depth + "x" + ')"' * depth,
            "unclosed": 'echo ' + '"$(echo ' * depth,
            "closed then a launch": 'echo ' + '"$(echo ' * depth + "x" + ')"' * depth + "; python3 -i",
            "arithmetic": 'echo "' + "$((" * depth + "1" + "))" * depth + '"',
            "backticks": 'echo "' + "`echo x`" * depth + '"',
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def test_groups_nested_deeply_are_answered(self):
        depth = self.DEPTH
        inputs = {
            "parentheses": "(" * depth + "python3" + ")" * depth,
            "unclosed parentheses": "(" * depth + "python3",
            "braces": "{ " * depth + "python3" + "; }" * depth,
            "unclosed braces": "{ " * depth + "python3;",
            "connected": "(" * depth + "python3" + ")" * depth + " < /dev/null",
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def test_many_checkpoint_lines_and_deep_closed_groups_before_an_unbalanced_quote_are_denied(self):
        # The checkpoint path (NFR1): every line ends at a checkpoint, the groups
        # nested DEPTH deep are all closed before the last one, a launch line
        # comes last, and an unbalanced quote makes the string undecidable
        # after it. Recording a checkpoint costs constant time and the groups
        # before it are settled once each, so the answer comes in time; the
        # deny shows the launch line was judged.
        depth = self.DEPTH
        lines = ":\n" * depth
        inputs = {
            "closed parentheses": lines + "(" * depth + ":" + ")" * depth + "\npython3 -i\necho '",
            "closed braces": lines + "{ " * depth + ":" + "; }" * depth + "\npython3 -i\necho '",
            "connected closed parentheses": (
                lines + "(" * depth + ":" + ")" * depth + " < /dev/null\npython3 -i\necho '"
            ),
        }
        for name, command in inputs.items():
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")

    def test_a_pipe_followed_by_many_empty_lines_is_answered(self):
        depth = self.DEPTH
        inputs = {
            "blank lines": "echo x |" + "\n" * depth + "python3",
            "comment lines": "echo x |" + "\n# c" * depth + "\npython3",
            "after and-and": "echo x &&" + "\n" * depth + "python3",
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def reserved_run(self):
        reserved = ("!", "do", "elif", "else", "if", "then", "time", "until", "while")
        return " ".join(reserved[i % len(reserved)] for i in range(self.RESERVED_RUN))

    def test_a_long_run_of_reserved_words_before_a_paren_is_answered(self):
        # The run before `(` is removed in one pass (TM-2): the cost stays
        # linear in the number of words, whatever the run is made of. The run
        # before a parenless `function {` is read as the words are appended
        # (TM-3): a run then a non-reserved word then a `function {` pair per
        # word of the run is where a re-read of the words at each `{` is
        # quadratic.
        run = self.reserved_run()
        inputs = {
            "run then a name and a body": run + " f() { python3 -i; }",
            "run of reserved words only": run + "()",
            "run then a parenless anonymous function": run + " function { python3 -i; }",
            "run, a word, then many function and brace pairs": run + " x" + " function {" * self.RESERVED_RUN,
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def test_a_parenless_anonymous_function_after_a_long_run_is_denied(self):
        command = self.reserved_run() + " function { python3 -i; }"
        for plugin, path in self.for_each_copy():
            code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
            self.assertEqual((code, err), (0, ""))
            decision = json.loads(out)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "deny")

    # Eight characters of a delimiter range (a single-quoted, a double-quoted
    # and a backslash-escaped `x`) that zsh reads as the three characters `xxx`.
    QUOTED_UNITS = "'x'\"x\"\\x"

    def heredoc_delimiter_ranges(self, heredocs, units):
        """`heredocs` anonymous functions, each with a heredoc whose delimiter is
        a `(`...`)` range of `units` quoted units (the delimiter itself is
        `(` + `x` * 3 * units + `)`), each closed by its true terminator, then
        a launch after the last one (TS-17). Most of the text is range text on
        the quote-removal path, and the launch is a body line unless every
        delimiter is derived the way zsh does."""
        delimiter = "(" + self.QUOTED_UNITS * units + ")"
        terminator = "(" + "x" * (3 * units) + ")"
        block = "function { :; } << foo" + delimiter + "\nfoo" + terminator + "\n"
        return block * heredocs + "python3 -i"

    def test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied(self):
        # TS-17: the quote removal of a delimiter range is one pass over the
        # range (TM-2). One range as long as the input, and many ranges each
        # closed by its terminator, both within the PAREN_SCAN_FACTOR bound;
        # the launch is denied only when every delimiter was derived so that
        # its terminator ends the body, so the verdict shows the removal ran.
        inputs = {
            "one long range": self.heredoc_delimiter_ranges(1, 30000),
            "many ranges": self.heredoc_delimiter_ranges(2000, 10),
            "many longer ranges": self.heredoc_delimiter_ranges(100, 300),
        }
        for name, command in inputs.items():
            self.assertGreater(len(command), 100000, name)
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    self.assertNotEqual(out, "", "the launch after the last terminator is denied")
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")

    def heredoc_case_substitution_ranges(self, heredocs, items):
        """`heredocs` heredocs, each with a delimiter `${v:-$( ... )}` whose
        substitution holds a case statement of `items` items, each item with a
        double-quoted word, and each heredoc closed by its true terminator line
        (the delimiter as written, quotes kept), then a launch after the last
        one. Zsh compares a body line with the delimiter as written, so the
        launch is a body line unless every delimiter was registered with the
        quotes of its substitution kept."""
        delimiter = "${v:-$(case x in " + 'x) echo "x";; ' * items + "esac)}"
        block = "cat <<" + delimiter + "\n" + delimiter + "\n"
        return block * heredocs + "python3 -i"

    def test_case_substitutions_in_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied(self):
        # AC-5 (NFR1): every `$( ... )` in a delimiter's `${ ... }` range is
        # skipped once, and the range reading goes on after it. The input is
        # read at the top level, so only the time of the reading limits it;
        # the launch is denied only when every delimiter was registered the way
        # zsh registers it, so the verdict shows the new path ran.
        inputs = {
            "one long range": self.heredoc_case_substitution_ranges(1, 4000),
            "many ranges": self.heredoc_case_substitution_ranges(1500, 1),
            "many longer ranges": self.heredoc_case_substitution_ranges(150, 30),
        }
        for name, command in inputs.items():
            self.assertGreater(len(command), 100000, name)
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    self.assertNotEqual(out, "", "the launch after the last terminator is denied")
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")

    def test_nesting_to_the_depth_the_limit_admits_is_denied(self):
        # Each level quotes the one inside it again, so the quote characters
        # multiply and the depth the limit admits stays small; the absence of
        # recursion is pinned by TestNoRecursion.
        depth = deepest_nesting_within_the_limit()
        self.assertGreater(depth, 5)
        command, counted = quoted_nesting(depth)
        self.assertLessEqual(counted, NESTED_READ_LIMIT)
        for plugin, path in self.for_each_copy():
            code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
            self.assertEqual((code, err), (0, ""))
            decision = json.loads(out)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_nesting_one_level_deeper_than_the_limit_admits_is_answered(self):
        command, counted = quoted_nesting(deepest_nesting_within_the_limit() + 1)
        self.assertGreater(counted, NESTED_READ_LIMIT)
        self.assert_every_copy_answers(command)

    def test_many_sibling_second_level_strings_over_the_limit_are_answered(self):
        each = 600
        count = NESTED_READ_LIMIT // each + 1
        strings = [padded_echo(each)] * count + ["python3 -i"]
        self.assert_every_copy_answers(holding(holding(*strings)))

    def test_nested_parens_among_anonymous_function_arguments_are_answered(self):
        # A `(` among the arguments of an anonymous function is matched to its
        # `)` by a scan toward the end of the input. When the range holds a `;`
        # the `(` opens a group instead, and the arguments of the anonymous
        # function nested in that group meet the next `(`. Restarting the scan
        # from each of them is quadratic in the input length (TM-1). The first
        # shape is the one the specification gives; the last is deep enough that
        # a quadratic scan overruns the time limit, where the linear one answers
        # in a fraction of a second.
        depth = self.DEPTH
        inputs = {
            "ranges that hold a separator": "function { :; } x(" * depth + "; :" + ")" * depth,
            "ranges that hold no separator before the last": "function { } x(" * depth + "; :" + ")" * depth,
            "unclosed ranges": "function { :; } x(" * depth + "; :",
            "closed ranges, then a launch": "function { :; } x(" * depth + "; :" + ")" * depth + "; python3 -i",
            "ranges that hold a separator, three times as deep": (
                "function { :; } x(" * (3 * depth) + "; :" + ")" * (3 * depth)
            ),
            "ranges that hold a backquote": "function { :; } x(`:` " * depth + ")" * depth,
            "unclosed ranges, then a launch": self.unclosed_ranges_then_a_launch(depth),
            "unclosed ranges, then many commands and a launch": self.unclosed_ranges_then_many_commands(depth),
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def unclosed_ranges_then_a_launch(self, depth):
        """Provisional groups nested `depth` deep, none closed, the only
        separator read directly at the innermost one, then a launch whose
        `#` hides the `)` that would close it (TS-16)."""
        return "function { :; } x(" * depth + "; python3 -i #"

    def unclosed_ranges_then_many_commands(self, depth):
        """The same nesting, then the separator and a tail of short commands
        much longer than the nesting is deep, then the launch. A rescue that
        moved the commands of the tail one at a time, once per rescued group,
        would be quadratic here."""
        return "function { :; } x(" * depth + ";" + " a;" * (10 * depth) + " python3 -i #"

    def test_unclosed_ranges_are_rescued_at_any_depth_and_the_launch_after_them_is_denied(self):
        # Every group of the nesting is a provisional group that is never
        # closed, and the first direct separator of the innermost one is a
        # `;`: the rescue runs from the inside out through all of them, and
        # the launch after the separator is judged, however many commands
        # come between (TM-1).
        depth = self.DEPTH
        inputs = {
            "a launch right after the separator": self.unclosed_ranges_then_a_launch(depth),
            "a wide tail before the launch": self.unclosed_ranges_then_many_commands(depth),
            "a lone & as the separator": "function { :; } x(" * depth + "& python3 -i #",
        }
        for name, command in inputs.items():
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")

    def test_unclosed_ranges_with_a_newline_first_stay_undecidable_at_any_depth(self):
        depth = self.DEPTH
        inputs = {
            "newline as the first separator of the innermost group": (
                "function { :; } x(" * depth + "\npython3 -i #"
            ),
            "newline as the first separator of the outermost group": (
                "function { :; } x(\n" + "function { :; } x(" * (depth - 1) + "; python3 -i #"
            ),
        }
        for name, command in inputs.items():
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, out, err), (0, "", ""))

    def test_many_closing_braces_after_a_chain_that_cannot_be_rescued_are_answered(self):
        # TS22: the chain of provisional groups is not rescuable (the first
        # direct separator of the outermost one is `&&`), and every `; }` after
        # it asks the rule at the `}` again. The check at a `}` reads values
        # fixed when each group opened, so it costs constant time (NFR1). A
        # walk over the chain at each `}` takes about depth times closings
        # steps (3.6 billion here), far past the time limit, where the linear
        # reading answers in a fraction of a second. The reading is
        # undecidable at the end: the outer `{` group is never closed.
        depth = closings = 10 * self.DEPTH
        command = "{ function { :; } x(a && " + "function { :; } x(" * depth + "; }" * closings
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual((code, out, err), (0, "", ""))

    def test_a_deep_chain_that_can_be_rescued_is_rescued_once_at_the_closing_brace(self):
        # The same nesting with a first direct separator the rescue accepts: the
        # first `}` rescues every group of the chain and closes the outer `{`
        # group, each group removed once, and the launch before it is judged.
        # Every `}` after it finds no open group and costs nothing.
        depth = closings = 10 * self.DEPTH
        inputs = {
            "one closing brace": (
                "{ function { :; } x(a; " + "function { :; } x(" * depth + "; python3 -i; }"
            ),
            "many closing braces": (
                "{ function { :; } x(a; " + "function { :; } x(" * depth + "; python3 -i" + "; }" * closings
            ),
        }
        for name, command in inputs.items():
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")

    def test_a_deep_chain_over_a_subshell_is_rescued_once_at_the_closing_paren(self):
        # TS-15: the group just outside the chain is a `(` group, and the chain
        # meets the separator condition through the first direct separator of
        # its innermost group. The one `)` rescues every group of the chain,
        # each removed once, and closes the subshell; the launch before it is
        # judged (NFR1, NFR2).
        depth = 10 * self.DEPTH
        command = "( " + "function { :; } x(" * depth + "; python3 -i; )"
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual((code, err), (0, ""))
                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")

    def test_many_closing_parens_after_a_chain_that_cannot_be_rescued_are_answered(self):
        # TS-16: the chain is blocked (the first direct separator of its
        # outermost group is `&&`), so every `)` takes the reading it had before
        # the rescue existed, and each one asks the rule again. The check reads
        # values fixed when each group opened, so it costs constant time. A walk
        # over the chain at each `)` takes about depth times closings steps (3.6
        # billion here), far past the time limit, where the linear reading
        # answers in a fraction of a second. The reading is undecidable at the
        # end: the subshell is never closed.
        depth = closings = 10 * self.DEPTH
        command = "( function { :; } x(a && " + "function { :; } x(" * depth + "; )" * closings
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual((code, out, err), (0, "", ""))

    def nested_braces_closed_with_words_pending(self, depth):
        """`depth` groups nested in an anonymous body, each closed by a `}`
        that has words pending: only a `;` or newline may come between a
        closed brace group and the next word, so every level but the innermost
        is closed after a `;`."""
        return "function {" + " { :;" * depth + " : }" + " ; : }" * depth

    def test_braces_closed_inside_an_anonymous_body_are_answered(self):
        # Whether a `{` group lies inside an anonymous body is read from a
        # value fixed when the group opened, so a `}` that closes with words
        # pending costs constant time (TM-2). A walk over the enclosing groups
        # at each `}` is quadratic: the depth below is where it overruns the
        # time limit, and the linear scan answers in a fraction of it. The
        # first shape is the one the specification gives: its `{` words after
        # the first follow a pending `:`, so they open no group. The others
        # nest real groups.
        depth = 10 * self.DEPTH
        inputs = {
            "braces after a pending word": "function {" + " { :" * depth + " }" * depth,
            "nested groups closed with words pending": self.nested_braces_closed_with_words_pending(depth),
            "nested groups closed with no word pending": (
                "function {" + " {" * depth + " :" + " }" * depth + " }"
            ),
            "nested groups under parentheses": (
                "function {" + " ( { :;" * depth + " : }" + " ) ; : }" * depth
            ),
            "nested groups closed with words pending, then a launch": (
                self.nested_braces_closed_with_words_pending(depth) + "; python3 -i"
            ),
        }
        for name, command in inputs.items():
            with self.subTest(shape=name):
                self.assert_every_copy_answers(command)

    def test_deeply_nested_braces_closed_with_words_pending_are_denied_when_a_launch_follows(self):
        depth = 10 * self.DEPTH
        inputs = {
            "braces": self.nested_braces_closed_with_words_pending(depth) + "; python3 -i",
            "braces under parentheses": (
                "function {" + " ( { :;" * depth + " : }" + " ) ; : }" * depth + "; python3 -i"
            ),
            "braces with no word pending": "function {" + " {" * depth + " :" + " }" * depth + " }; python3 -i",
        }
        for name, command in inputs.items():
            for plugin, path in self.for_each_copy():
                with self.subTest(shape=name, copy=plugin):
                    code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                    self.assertEqual((code, err), (0, ""))
                    decision = json.loads(out)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")


class TestCaseStatementsInASubstitution(HookCopiesMixin, unittest.TestCase):
    """A case statement inside a double-quoted command substitution is read in
    time whatever its shape (NFR1, TM-3): one statement with very many items,
    and statements nested very deeply, each opened as the first word of the
    body of the enclosing item. Long runs of continuation pairs and of words
    whose keyword match fails are read in time too (TS20 to TS22). The item
    count and the depth are the depth the deep-input class uses. The launch
    after the substitution is judged, so the answer is a deny: unlike the
    helper of the deep-input class, silence is not an answer here."""

    DEPTH = TestMalformedAndDeepInput.DEPTH
    TIMEOUT = TestMalformedAndDeepInput.TIMEOUT

    def assert_every_copy_denies(self, command):
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                code, out, err = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual((code, err), (0, ""))
                obj, end = json.JSONDecoder().raw_decode(out)
                self.assertEqual(out[end:].strip(), "", "standard output holds one object")
                self.assertEqual(obj["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_one_case_statement_with_many_items_is_read_and_the_launch_after_it_is_denied(self):
        command = 'echo "$(case x in' + " x) :;;" * self.DEPTH + ' esac)"; python3 -i'
        self.assert_every_copy_denies(command)

    def test_case_statements_nested_deeply_are_read_and_the_launch_after_them_is_denied(self):
        depth = self.DEPTH
        statements = "case x in x) " * depth + ":" + "; esac" * depth
        self.assert_every_copy_denies('echo "$(' + statements + ')"; python3 -i')

    # codex-guard-escaped-hash-brace-case-heredoc (NFR1, FR9): the zsh brace
    # form `case x { ... }` is read in time too. One statement with DEPTH
    # items, statements nested DEPTH deep (each opened as the first word of the
    # enclosing item body, closed by the pattern-position `}` or by the
    # depth-0 body `}`), and DEPTH `{ }` groups nested in one item body. The
    # launch after the substitution is denied.
    def test_one_brace_form_case_statement_with_many_items_is_read_and_the_launch_after_it_is_denied(self):
        command = 'echo "$(case x {' + " x) :;;" * self.DEPTH + ' })"; python3 -i'
        self.assert_every_copy_denies(command)

    def test_brace_form_case_statements_nested_deeply_are_read_and_the_launch_after_them_is_denied(self):
        depth = self.DEPTH
        shapes = {
            "closed at a pattern position": "case x { x) " * depth + ":" + ";; }" * depth,
            "closed by the body": "case x { x) " * depth + ":" + "; }" * depth,
        }
        for shape, statements in shapes.items():
            with self.subTest(shape=shape):
                self.assert_every_copy_denies('echo "$(' + statements + ')"; python3 -i')

    def test_brace_groups_nested_deeply_in_one_brace_form_item_body_are_read_and_the_launch_after_them_is_denied(self):
        depth = self.DEPTH
        statement = "case x { x) " + "{ " * depth + ":" + "; }" * depth + "; }"
        self.assert_every_copy_denies('echo "$(' + statement + ')"; python3 -i')

    # codex-guard-case-reading-fixes (SPEC.md TS20 to TS22, NFR1): long runs of
    # continuation pairs and long runs of words whose keyword match fails are
    # read in time too. A continuation pair is a backslash directly followed
    # by a newline.
    PAIR = "\\\n"

    def test_ts20_continuation_pairs_in_the_waiting_phases_and_inside_the_keywords_are_read_in_time(self):
        pairs = self.PAIR * self.DEPTH
        shapes = {
            "waiting phases": (
                "case " + pairs + "x " + pairs + "in " + pairs + "(" + pairs + "x) "
                + pairs + ":;; " + pairs + "esac"
            ),
            "inside the keywords": (
                "c" + pairs + "ase x i" + pairs + "n x) :;; e" + pairs + "s" + pairs + "a" + pairs + "c"
            ),
            "both": (
                "c" + pairs + "ase " + pairs + "x " + pairs + "i" + pairs + "n "
                + pairs + "(" + pairs + "x) " + pairs + ":;; "
                + pairs + "e" + pairs + "s" + pairs + "a" + pairs + "c"
            ),
        }
        for shape, statement in shapes.items():
            with self.subTest(shape=shape):
                self.assert_every_copy_denies('echo "$(' + statement + ')"; python3 -i')

    def test_ts21_split_words_whose_keyword_match_fails_are_read_in_time(self):
        word = "c" + self.PAIR + "a" + self.PAIR + "s" + self.PAIR + "x"
        shapes = {
            "arguments": (word + " ") * self.DEPTH,
            "command position": (word + "; ") * self.DEPTH,
        }
        for shape, body in shapes.items():
            with self.subTest(shape=shape):
                self.assert_every_copy_denies('echo "$(case x in x) ' + body + ':;; esac)"; python3 -i')

    def test_ts22_a_long_run_of_argument_reserved_words_is_read_in_time(self):
        body = "echo " + "then " * self.DEPTH
        self.assert_every_copy_denies('echo "$(case x in x) ' + body + '; esac)"; python3 -i')

    # codex-guard-subst-reading-regressions (VERIFICATION.md TS27, NFR1): a
    # top-level coproc form followed by DEPTH words. The string is of unknown
    # kind: the first read follows the `case` the coproc NAME rule opens to the
    # end of the input and stops undecidable, and the re-read reads the same
    # string to its end. Both reads are linear, and the launch after the
    # substitution is denied.
    def test_ts27_a_top_level_coproc_form_followed_by_a_long_run_is_read_twice_in_time(self):
        command = 'echo "$(coproc echo case x in x)' + " :" * self.DEPTH + '"; python3 -i'
        self.assert_every_copy_denies(command)

    # codex-guard-case-reading-fixes (SPEC.md TS41 to TS43 and TS60, NFR1):
    # compound closings, function heads and loop heads nested to DEPTH levels,
    # and a long run of closing words at an argument position, are read in
    # time and the launch after the substitution is denied.
    def test_ts41_compound_closings_nested_deeply_are_read_in_time(self):
        depth = self.DEPTH
        command = 'echo "$(' + "if (:) then " * depth + "case x in x) :;; esac" + "; fi" * depth + ')"; python3 -i'
        self.assert_every_copy_denies(command)

    def test_ts42_function_heads_nested_deeply_are_read_in_time(self):
        depth = self.DEPTH
        command = 'echo "$(' + "f() { " * depth + "case x in x) :;; esac" + "; }" * depth + ')"; python3 -i'
        self.assert_every_copy_denies(command)

    # codex-guard-subst-reading-regressions (VERIFICATION.md TS25, NFR1): DEPTH
    # continuation pairs inside the `()` of a function head are read in time
    # and the launch after the substitution is denied.
    def test_ts25_a_long_run_of_pairs_inside_an_empty_function_head_is_read_in_time(self):
        inner = 'echo "$(f(' + self.PAIR * self.DEPTH + ') { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i'
        self.assert_every_copy_denies("bash -c " + shlex.quote(inner))

    def test_ts43_a_long_run_of_closing_words_at_an_argument_position_is_read_in_time(self):
        command = 'echo "$(echo ' + "]] fi done then " * self.DEPTH + 'case x in x)"; python3 -i'
        self.assert_every_copy_denies(command)

    def test_ts60_loop_heads_nested_deeply_are_read_in_time(self):
        depth = self.DEPTH
        command = 'echo "$(' + "for x do " * depth + "case x in x) :;; esac" + "; done" * depth + ')"; python3 -i'
        self.assert_every_copy_denies(command)

    # codex-guard-subst-reading-regressions (SPEC.md TS26, NFR1): DEPTH commented
    # lines in a zsh `for` word list are read in time and the launch after the
    # substitution is denied. One more line makes the count of `"` in the
    # comments odd, so a comment that opened a quote would not be balanced.
    def test_ts26_commented_lines_in_a_for_word_list_are_read_in_time(self):
        for lines in (self.DEPTH, self.DEPTH + 1):
            with self.subTest(lines=lines):
                command = 'echo "$(for x (a' + ' # "\n' * lines + ') { :; })"; python3 -i'
                self.assert_every_copy_denies(command)

    # codex-guard-escaped-hash-brace-case-heredoc (VERIFICATION.md TS-28, NFR1,
    # TM-4): the comment-start decision looks only at the characters directly
    # in front of a `#`, so inputs that make that look long are read in time.
    # Each input is built so that every `#` is a word character (or the one
    # comment ends at a newline), and the launch after the substitution is
    # denied.
    def test_ts28_depth_escaped_blanks_before_a_hash_are_read_in_time(self):
        command = 'echo "$(:' + " \\ #" * self.DEPTH + ')"; python3 -i'
        self.assert_every_copy_denies(command)

    def test_ts28_depth_continuation_pairs_between_a_word_character_and_a_hash_are_read_in_time(self):
        shapes = {
            "one pair before each hash": 'echo "$(:' + " a" + (self.PAIR + "#a") * self.DEPTH + ')"; python3 -i',
            "one run of pairs before one hash": 'echo "$(: a' + self.PAIR * self.DEPTH + '#x)"; python3 -i',
            "one run of pairs after an escaped blank": 'echo "$(: \\ ' + self.PAIR * self.DEPTH + '#x)"; python3 -i',
        }
        for shape, command in shapes.items():
            with self.subTest(shape=shape):
                self.assert_every_copy_denies(command)

    def test_ts28_a_backslash_run_of_depth_length_before_a_blank_and_a_hash_is_read_in_time(self):
        # An even run leaves the blank unescaped, so the `#` starts a comment
        # and the newline after it ends the comment; an odd run escapes the
        # blank, so the `#` is a word character.
        shapes = {
            "even run": 'echo "$(: ' + "\\" * self.DEPTH + " #x\n)\"; python3 -i",
            "odd run": 'echo "$(: ' + "\\" * (self.DEPTH + 1) + ' #x)"; python3 -i',
        }
        for shape, command in shapes.items():
            with self.subTest(shape=shape):
                self.assert_every_copy_denies(command)

    def test_ts28_many_backslash_runs_each_before_a_blank_and_a_hash_are_read_in_time(self):
        # Each run of three backslashes escapes its blank, so every `#` is a
        # word character.
        command = 'echo "$(:' + " \\\\\\ #" * self.DEPTH + ')"; python3 -i'
        self.assert_every_copy_denies(command)

    # codex-guard-escaped-hash-brace-case-heredoc (VERIFICATION.md TS-36, NFR1,
    # TM-4): the comment-end position costs one assignment per comment and one
    # comparison per newline the look crosses. DEPTH repetitions of a comment
    # that ends in a backslash, each followed by a line that begins with `#`,
    # stand in one substitution; the `'` in the last repetition shows that
    # every one of those lines is read as a comment (read as code it would open
    # a quote that never closes). The launch after the substitution is denied.
    def test_ts36_depth_comments_ending_in_a_backslash_each_followed_by_a_hash_line_are_read_in_time(self):
        comment = "#b" + "\\\n" + "# x\n"
        last = "#b" + "\\\n" + "# don't\n"
        command = 'echo "$(: ' + comment * (self.DEPTH - 1) + last + ')"; python3 -i'
        self.assert_every_copy_denies(command)


class TestAnonymousFunctionHeadInASubstitution(HookCopiesMixin, unittest.TestCase):
    """An empty `()` right after `function`, with no name, ends the head of a
    zsh anonymous function (`function () { ... }`, FR10): the `{` after it is at
    a command position and the `case` in the body opens a statement."""

    def assert_every_copy(self, command, expected):
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                self.assertEqual(verdict_of(run_hook(path, payload_for(command))), expected)

    def test_a_launch_after_the_substitution_is_denied(self):
        self.assert_every_copy(
            'echo "$(function () { case x in x) printf \'%s\' \'"\';; esac; })"; python3 -i',
            "deny",
        )

    def test_a_quoted_launch_in_the_body_is_not_denied(self):
        self.assert_every_copy(
            'echo "$(function () { case x in x) echo "; python3 -i;";; esac; })"',
            "silent",
        )


class TestBraceCloseEqualsSemicolonBeforeIt(HookCopiesMixin, unittest.TestCase):
    """A standalone bare `}` that closes an anonymous body, or a `{` group
    inside one, while words are pending gives the verdict of the same input
    with `;` inserted immediately before that `}` (FR1, FR2, FR3, TM-1). Each
    row is (command, the same command with `;` before each `}` the rule
    closes, the verdict both carry)."""

    PAIRS = [
        ("zsh -c 'python3 -i; function { : }'", "zsh -c 'python3 -i; function { :;}'", "deny"),
        ("zsh -c 'function { : }; python3 -i'", "zsh -c 'function { :;}; python3 -i'", "deny"),
        ("zsh -c 'function { python3 -i }'", "zsh -c 'function { python3 -i;}'", "deny"),
        ("zsh -c 'function () { python3 -i }'", "zsh -c 'function () { python3 -i;}'", "deny"),
        ("zsh -c '() { python3 -i }'", "zsh -c '() { python3 -i;}'", "deny"),
        ("zsh -c 'function { python3 -i } arg'", "zsh -c 'function { python3 -i;} arg'", "deny"),
        ("zsh -c 'function { { : } }; python3 -i'", "zsh -c 'function { { :;} }; python3 -i'", "deny"),
        ("zsh -c 'function { ( { python3 -i } ) }'", "zsh -c 'function { ( { python3 -i;} ) }'", "deny"),
        ("zsh -c 'echo x | function { python3 }'", "zsh -c 'echo x | function { python3;}'", "silent"),
        ("zsh -c '< /dev/null function { python3 }'", "zsh -c '< /dev/null function { python3;}'", "silent"),
        ("zsh -c 'echo x | function { { python3 } }'", "zsh -c 'echo x | function { { python3;} }'", "silent"),
        ("zsh -c 'function { f() { : } }; python3 -i'", "zsh -c 'function { f() { :;} }; python3 -i'", "deny"),
        ("zsh -c 'function { function { : } }; python3 -i'", "zsh -c 'function { function { :;} }; python3 -i'", "deny"),
        ("zsh -c 'function () { python3 } < /dev/null'", "zsh -c 'function () { python3;} < /dev/null'", "silent"),
        ("zsh -c 'function { python3 } arg < /dev/null'", "zsh -c 'function { python3;} arg < /dev/null'", "silent"),
        ("zsh -c 'echo x |\nfunction { python3 }'", "zsh -c 'echo x |\nfunction { python3;}'", "silent"),
        ("zsh -c 'function { python3 }\npython3'", "zsh -c 'function { python3;}\npython3'", "deny"),
        ("zsh -c 'function { python3 };python3 -i'", "zsh -c 'function { python3;};python3 -i'", "deny"),
    ]

    def test_each_row_carries_the_same_verdict_with_and_without_the_semicolon(self):
        for plugin, path in self.for_each_copy():
            for command, with_semicolon, expected in self.PAIRS:
                with self.subTest(copy=plugin, command=command):
                    plain = verdict_of(run_hook(path, payload_for(command)))
                    counterpart = verdict_of(run_hook(path, payload_for(with_semicolon)))
                    self.assertEqual(counterpart, expected, with_semicolon)
                    self.assertEqual(plain, counterpart)


class TestNestedJudgmentOrder(HookCopiesMixin, unittest.TestCase):
    """The first launch to deny in judgment order decides the reason: a nested
    string is judged, command by command, before the command after its
    holder (TM-1)."""

    def reason_of(self, path, command):
        code, out, err = run_hook(path, payload_for(command))
        self.assertEqual((code, err), (0, ""))
        return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]

    def assert_program_less_reason(self, reason, name):
        self.assertIn(f"`{name}` を", reason)
        self.assertIn("プログラムを渡さずに", reason)
        self.assertNotIn("（-i）", reason)

    def assert_interactive_reason(self, reason, name):
        self.assertIn(f"`{name}` を", reason)
        self.assertIn("（-i）", reason)
        self.assertNotIn("プログラムを渡さずに", reason)

    def test_a_nested_launch_is_judged_before_a_later_level_zero_launch(self):
        for plugin, path in self.for_each_copy():
            reason = self.reason_of(path, 'bash -c "bash -c node"; python3 -i')
            self.assert_program_less_reason(reason, "node")
            self.assertNotIn("`python3` を", reason)

    def test_a_nested_launch_is_judged_before_a_later_command_of_its_holder(self):
        for plugin, path in self.for_each_copy():
            reason = self.reason_of(path, 'bash -c "bash -c node; python3 -i"')
            self.assert_program_less_reason(reason, "node")
            self.assertNotIn("`python3` を", reason)

    def test_a_launch_before_the_nested_string_decides_first(self):
        for plugin, path in self.for_each_copy():
            reason = self.reason_of(path, 'bash -c "python3 -i; bash -c node"')
            self.assert_interactive_reason(reason, "python3")
            self.assertNotIn("`node` を", reason)

    def test_the_commands_of_a_nested_string_are_judged_in_source_order(self):
        for plugin, path in self.for_each_copy():
            reason = self.reason_of(path, "bash -c \"bash -c 'node; python3 -i'\"")
            self.assert_program_less_reason(reason, "node")
            reason = self.reason_of(path, "bash -c \"bash -c 'python3 -i; node'\"")
            self.assert_interactive_reason(reason, "python3")

    def test_the_whole_nested_string_is_judged_before_the_next_command(self):
        for plugin, path in self.for_each_copy():
            command = "bash -c \"bash -c 'bash -c \\\"node\\\"'; python3 -i\""
            reason = self.reason_of(path, command)
            self.assert_program_less_reason(reason, "node")


def recursion_findings(source):
    """Name every function that calls itself and every cycle among the
    module-level functions in `source`. A function calls itself when a call in
    its body is its own bare name (a method is not meant by a bare name), or,
    for a method, when it is `self.<method>`."""
    tree = ast.parse(source)
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    findings = []
    method_ids = set()
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for member in cls.body:
            if not isinstance(member, functions):
                continue
            method_ids.add(id(member))
            for call in ast.walk(member):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "self"
                    and call.func.attr == member.name
                ):
                    findings.append(f"{cls.name}.{member.name} calls itself through self")
    for fn in ast.walk(tree):
        if not isinstance(fn, functions) or id(fn) in method_ids:
            continue
        for call in ast.walk(fn):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == fn.name
            ):
                findings.append(f"{fn.name} calls itself by name")
    module_level = {node.name: node for node in tree.body if isinstance(node, functions)}
    pending = {
        name: {
            call.func.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in module_level
            and call.func.id != name
        }
        for name, node in module_level.items()
    }
    # Drop the functions that call nothing still pending, until none is left to
    # drop. What remains lies on a cycle or leads into one.
    changed = True
    while changed:
        changed = False
        for name in [name for name, targets in pending.items() if not targets]:
            del pending[name]
            for targets in pending.values():
                targets.discard(name)
            changed = True
    if pending:
        findings.append("cycle among module-level functions: " + ", ".join(sorted(pending)))
    return findings


def called_names(node):
    return {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }


class TestNoRecursion(unittest.TestCase):
    """Nesting is followed with a work list, so the depth of nested strings
    costs no call stack (TM-2)."""

    def test_no_function_calls_itself_and_no_functions_form_a_cycle(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertEqual(recursion_findings(path.read_text(encoding="utf-8")), [])

    def test_the_checker_flags_a_direct_self_call(self):
        findings = recursion_findings("def f(n):\n    return f(n - 1)\n")
        self.assertEqual(findings, ["f calls itself by name"])

    def test_the_checker_flags_a_method_that_calls_itself_through_self(self):
        source = "class A:\n    def walk(self, node):\n        return self.walk(node)\n"
        self.assertEqual(recursion_findings(source), ["A.walk calls itself through self"])

    def test_the_checker_flags_a_two_function_cycle(self):
        source = "def a():\n    return b()\n\ndef b():\n    return a()\n"
        findings = recursion_findings(source)
        self.assertEqual(len(findings), 1)
        self.assertIn("a, b", findings[0])

    def test_the_checker_passes_a_chain_and_a_method_named_like_a_function(self):
        source = (
            "def a():\n    return b()\n\n"
            "def b():\n    return 1\n\n"
            "def parse(text):\n    return Parser(text).parse()\n\n"
            "class Parser:\n"
            "    def __init__(self, text):\n        self.text = text\n"
            "    def parse(self):\n        return self._read()\n"
            "    def _read(self):\n        return self.text\n"
        )
        self.assertEqual(recursion_findings(source), [])

    def test_scan_walks_the_nested_strings_and_find_deny_keeps_its_signature(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                functions = {
                    node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                }
                find_deny = functions["find_deny"]
                arguments = find_deny.args
                self.assertEqual([arg.arg for arg in arguments.args], ["command"])
                self.assertEqual(
                    (arguments.posonlyargs, arguments.kwonlyargs, arguments.vararg, arguments.kwarg),
                    ([], [], None, None),
                )
                self.assertIn("_scan", called_names(find_deny))
                self.assertTrue({"_judge", "parse"} <= called_names(functions["_scan"]))


def parser_methods(path):
    """The methods of the `_Parser` class in the guard at `path`, by name."""
    return parser_methods_in(path.read_text(encoding="utf-8"))


def parser_methods_in(source):
    """The methods of the `_Parser` class in the Python text `source`, by
    name."""
    tree = ast.parse(source)
    parser = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_Parser"
    )
    return {
        member.name: member
        for member in parser.body
        if isinstance(member, ast.FunctionDef)
    }


def self_calls(method):
    """The names of the `self.<name>(...)` calls in the body of `method`."""
    return {
        call.func.attr
        for call in ast.walk(method)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
    }


class TestSharedQuotedUnitReader(unittest.TestCase):
    """A backslash pair, a single-quoted unit and a double-quoted unit are read
    by one reader, which both word reading and the quote removal of a delimiter
    range call, and which is the only one that calls the substitution skip
    (AC-4, AC-5). The reader's name is not fixed, so it is found as the one
    method that calls `_skip_substitution`."""

    def test_one_method_reads_double_quotes_and_word_reading_and_range_removal_call_it(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                methods = parser_methods(path)
                readers = sorted(
                    name for name, node in methods.items()
                    if "_skip_substitution" in self_calls(node)
                )
                self.assertEqual(len(readers), 1, readers)
                for caller in ("parse", "_remove_range_quotes"):
                    self.assertIn(readers[0], self_calls(methods[caller]), caller)

    def test_the_substitution_skip_calls_neither_reader_nor_the_shared_reader(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                methods = parser_methods(path)
                readers = [
                    name for name, node in methods.items()
                    if "_skip_substitution" in self_calls(node)
                ]
                skipped = self_calls(methods["_skip_substitution"])
                self.assertEqual(len(readers), 1, readers)
                for name in readers + ["parse", "_remove_range_quotes"]:
                    self.assertNotIn(name, skipped)


def reachable_self_calls(methods, start):
    """The names of the `_Parser` methods that can be reached from the method
    `start` by following `self.<name>(...)` calls, `start` itself included only
    when a chain of calls leads back to it. A work list, so the walk is
    iterative and ends on a call cycle."""
    reached = set()
    pending = [start]
    while pending:
        method = methods.get(pending.pop())
        if method is None:
            continue
        for callee in self_calls(method):
            if callee not in reached:
                reached.add(callee)
                pending.append(callee)
    return reached


class TestSubstitutionSkipCallStructure(unittest.TestCase):
    """The substitution skip reads `case` statements with its own explicit
    stack and bounded lookups. Nothing it reaches, directly or through other
    methods, is the skip again, the shared quoted-unit reader, `parse` or
    `_remove_range_quotes`: that would be a call cycle (NFR2, TM-3)."""

    FORBIDDEN = ("_skip_substitution", "_read_quoted_unit", "parse", "_remove_range_quotes")

    def test_no_method_reachable_from_the_substitution_skip_is_the_skip_or_a_reader(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                methods = parser_methods(path)
                reached = reachable_self_calls(methods, "_skip_substitution")
                for name in self.FORBIDDEN:
                    self.assertNotIn(name, reached)

    def test_the_walk_follows_calls_through_other_methods(self):
        source = (
            "class _Parser:\n"
            "    def _skip_substitution(self):\n        return self._a()\n"
            "    def _a(self):\n        return self._b()\n"
            "    def _b(self):\n        return self._read_quoted_unit()\n"
            "    def _read_quoted_unit(self):\n        return self._skip_substitution()\n"
            "    def parse(self):\n        return 1\n"
        )
        reached = reachable_self_calls(parser_methods_in(source), "_skip_substitution")
        self.assertEqual(reached, {"_a", "_b", "_read_quoted_unit", "_skip_substitution"})

    def test_the_walk_ends_on_a_cycle_that_does_not_lead_back_to_the_start(self):
        source = (
            "class _Parser:\n"
            "    def _skip_substitution(self):\n        return self._a()\n"
            "    def _a(self):\n        return self._b()\n"
            "    def _b(self):\n        return self._a()\n"
        )
        reached = reachable_self_calls(parser_methods_in(source), "_skip_substitution")
        self.assertEqual(reached, {"_a", "_b"})


def caught_names(handler):
    """The bare names an `except` clause catches (`<bare>` for a bare except)."""
    kind = handler.type
    if kind is None:
        return {"<bare>"}
    elements = kind.elts if isinstance(kind, ast.Tuple) else [kind]
    return {element.id for element in elements if isinstance(element, ast.Name)}


def nested_parse_handler_findings(source):
    """Name what is wrong with the handling around the nested parse call in
    `_scan`. The call is the one to `parse` inside a try statement of `_scan`.
    The handlers must catch `_Undecidable` and, in addition, the general
    exception class; the handler that catches the general exception class must
    neither return nor raise, so the scan goes on with the next command."""
    tree = ast.parse(source)
    scan = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_scan"),
        None,
    )
    if scan is None:
        return ["no _scan function"]
    tries = [
        node
        for node in ast.walk(scan)
        if isinstance(node, ast.Try)
        and any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "parse"
            for statement in node.body
            for call in ast.walk(statement)
        )
    ]
    if len(tries) != 1:
        return [f"expected one try around the nested parse call in _scan, found {len(tries)}"]
    handlers = tries[0].handlers
    findings = []
    if not any("_Undecidable" in caught_names(handler) for handler in handlers):
        findings.append("_Undecidable is not caught around the nested parse call")
    general = [handler for handler in handlers if "Exception" in caught_names(handler)]
    if not general:
        findings.append("the general exception class is not caught around the nested parse call")
    for handler in general:
        for statement in handler.body:
            for node in ast.walk(statement):
                if isinstance(node, ast.Return):
                    findings.append("the handler of the general exception class returns")
                if isinstance(node, ast.Raise):
                    findings.append("the handler of the general exception class raises")
    return findings


class TestNestedParseErrorContainment(unittest.TestCase):
    """An unexpected error while a nested string is parsed skips that string
    and the walk goes on with the command after the one holding it (NFR5).
    No known input reaches that path once a digit word of any length is read
    without an error, so the handling is checked on the syntax tree."""

    GOOD = (
        "def _scan(commands):\n"
        "    while pending:\n"
        "        try:\n"
        "            inner_commands = parse(inner)\n"
        "        except _Undecidable:\n"
        "            continue\n"
        "        except Exception:\n"
        "            continue\n"
        "        pending.append(inner_commands)\n"
    )

    def source_with_handlers(self, handlers):
        return (
            "def _scan(commands):\n"
            "    while pending:\n"
            "        try:\n"
            "            inner_commands = parse(inner)\n"
            + handlers
            + "        pending.append(inner_commands)\n"
        )

    def test_each_copy_catches_the_general_exception_class_and_goes_on(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertEqual(
                    nested_parse_handler_findings(path.read_text(encoding="utf-8")), []
                )

    def test_the_checker_passes_two_handlers_that_continue(self):
        self.assertEqual(nested_parse_handler_findings(self.GOOD), [])

    def test_the_checker_passes_one_handler_for_both_classes_that_continues(self):
        source = self.source_with_handlers(
            "        except (_Undecidable, Exception):\n            continue\n"
        )
        self.assertEqual(nested_parse_handler_findings(source), [])

    def test_the_checker_flags_a_handler_for_undecidable_alone(self):
        source = self.source_with_handlers("        except _Undecidable:\n            continue\n")
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["the general exception class is not caught around the nested parse call"],
        )

    def test_the_checker_flags_a_handler_for_the_general_class_alone(self):
        source = self.source_with_handlers("        except Exception:\n            continue\n")
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["_Undecidable is not caught around the nested parse call"],
        )

    def test_the_checker_flags_a_bare_except_as_no_general_class(self):
        source = self.source_with_handlers(
            "        except _Undecidable:\n            continue\n"
            "        except:\n            continue\n"
        )
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["the general exception class is not caught around the nested parse call"],
        )

    def test_the_checker_flags_a_general_handler_that_returns(self):
        source = self.source_with_handlers(
            "        except _Undecidable:\n            continue\n"
            "        except Exception:\n            return None\n"
        )
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["the handler of the general exception class returns"],
        )

    def test_the_checker_flags_a_general_handler_that_raises(self):
        source = self.source_with_handlers(
            "        except _Undecidable:\n            continue\n"
            "        except Exception:\n            raise\n"
        )
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["the handler of the general exception class raises"],
        )

    def test_the_checker_flags_a_nested_parse_call_with_no_try(self):
        source = "def _scan(commands):\n    inner_commands = parse(inner)\n"
        self.assertEqual(
            nested_parse_handler_findings(source),
            ["expected one try around the nested parse call in _scan, found 0"],
        )

    def test_the_checker_flags_a_missing_scan_function(self):
        self.assertEqual(nested_parse_handler_findings("x = 1\n"), ["no _scan function"])


def load_guard(path):
    """The guard at `path` as a module namespace, compiled from its source text
    and run in memory. Nothing is imported from the plugin directory, so no
    bytecode cache is written there (`TestCopies`)."""
    namespace = {"__name__": "guard_under_test", "__file__": str(path)}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


class TestRereadFallback(unittest.TestCase):
    """codex-guard-subst-reading-regressions (VERIFICATION.md TS33, TM-3): when
    the one re-read of an unknown-kind string raises, whatever the exception
    class, the module-level `parse` raises the `_Undecidable` of the first read
    with the commands the first read settled up to its last checkpoint. No known
    input makes the reader raise an unexpected error, so the failure is forced
    in memory: the re-read is the second parser the module-level `parse` builds,
    and its parse method raises."""

    # `python3 -i` is settled at the checkpoint of the first line. Under both
    # readings the second line is an unclosed substitution, so the first read is
    # undecidable and the re-read would be too.
    COMMAND = 'python3 -i\necho "$(repeat x case y in y'

    def parse_with_failing_reread(self, path, make_failure):
        """Run the module-level `parse` of the guard at `path` on COMMAND with a
        re-read that raises the exception `make_failure(guard namespace)` makes.
        Return (the parsers built, the failure, the exception `parse` raised)."""
        guard = load_guard(path)
        failure = make_failure(guard)
        real = guard["_Parser"]
        parsers = []

        class FailingReread(real):
            def parse(self):
                parsers.append(self)
                if len(parsers) == 2:
                    raise failure
                return super().parse()

        guard["_Parser"] = FailingReread
        with self.assertRaises(guard["_Undecidable"]) as caught:
            guard["parse"](self.COMMAND)
        return parsers, failure, caught.exception

    def assert_first_read_checkpoint(self, error):
        self.assertEqual(
            [[word.text for word in command.words] for command in error.checkpoint_commands],
            [["python3", "-i"]],
        )

    def test_a_reread_that_raises_an_unexpected_error_falls_back_to_the_first_read(self):
        for plugin, path in HOOK_PATHS.items():
            for error_class in (RuntimeError, KeyError, RecursionError):
                with self.subTest(copy=plugin, failure=error_class.__name__):
                    parsers, failure, error = self.parse_with_failing_reread(
                        path, lambda guard: error_class("forced")
                    )
                    self.assertEqual(len(parsers), 2, "the string is read twice")
                    self.assertIsNot(error, failure)
                    self.assert_first_read_checkpoint(error)

    def test_a_reread_that_raises_undecidable_falls_back_to_the_first_read(self):
        def undecidable_with_other_commands(guard):
            failure = guard["_Undecidable"]("forced")
            failure.checkpoint_commands = ("the re-read's own commands",)
            return failure

        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, failure, error = self.parse_with_failing_reread(
                    path, undecidable_with_other_commands
                )
                self.assertEqual(len(parsers), 2, "the string is read twice")
                self.assertIsNot(error, failure)
                self.assert_first_read_checkpoint(error)


class TestNestedReadLimit(HookCopiesMixin, unittest.TestCase):
    """The characters re-read from second-level-and-deeper strings are capped
    at `NESTED_READ_LIMIT` per hook command (TM-2). First-level strings are
    never counted. The strings below are built so that the length of a
    second-level string is plain arithmetic (see `holding`)."""

    TIMEOUT = 60

    def verdict(self, path, command):
        result = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
        return verdict_of(result)

    def assert_verdict(self, expected, command):
        for plugin, path in self.for_each_copy():
            self.assertEqual(self.verdict(path, command), expected)

    def test_each_copy_defines_the_limit_once_with_the_specified_value(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                stores = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Name)
                    and node.id == "NESTED_READ_LIMIT"
                    and isinstance(node.ctx, ast.Store)
                ]
                self.assertEqual(len(stores), 1, "the constant is assigned exactly once")
                assigns = [
                    node for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "NESTED_READ_LIMIT" for t in node.targets)
                ]
                self.assertEqual(len(assigns), 1, "the assignment is at module level")
                value = assigns[0].value
                self.assertIsInstance(value, ast.Constant)
                self.assertIs(type(value.value), int)
                self.assertEqual(value.value, 1000000)

    def test_a_string_that_brings_the_total_exactly_to_the_limit_is_read(self):
        self.assert_verdict("deny", holding(holding(padded_launch(NESTED_READ_LIMIT))))

    def test_one_more_character_and_the_string_is_not_read(self):
        self.assert_verdict("silent", holding(holding(padded_launch(NESTED_READ_LIMIT + 1))))

    def test_the_total_runs_across_the_strings_of_one_first_level_string(self):
        half = NESTED_READ_LIMIT // 2
        self.assert_verdict("deny", holding(holding(padded_echo(half), padded_launch(half))))
        self.assert_verdict("silent", holding(holding(padded_echo(half), padded_launch(half + 1))))

    def test_the_total_runs_across_first_level_strings(self):
        half = NESTED_READ_LIMIT // 2
        self.assert_verdict(
            "silent", holding(holding(padded_echo(half)), holding(padded_launch(half + 1)))
        )

    def test_an_over_limit_string_in_one_first_level_string_stops_the_later_ones(self):
        command = holding(holding(padded_echo(NESTED_READ_LIMIT + 1)), holding("python3 -i"))
        self.assert_verdict("silent", command)

    def test_a_string_that_proves_undecidable_still_counts(self):
        command = holding(holding(unreadable(NESTED_READ_LIMIT)), holding("python3 -i"))
        self.assert_verdict("silent", command)

    def test_a_launch_before_an_over_limit_string_is_denied(self):
        self.assert_verdict(
            "deny", holding(holding("python3 -i", padded_echo(NESTED_READ_LIMIT + 1)))
        )
        self.assert_verdict(
            "deny", holding(holding("python3 -i"), holding(padded_echo(NESTED_READ_LIMIT + 1)))
        )

    def test_first_level_strings_are_never_counted(self):
        each = NESTED_READ_LIMIT // 2 + 1
        command = holding(padded_echo(each), padded_echo(each), "python3 -i")
        self.assert_verdict("deny", command)

    def test_a_level_zero_launch_after_the_limit_is_reached_is_denied(self):
        command = holding(holding(padded_echo(NESTED_READ_LIMIT + 1))) + "; python3 -i"
        self.assert_verdict("deny", command)

    def test_a_first_level_launch_after_the_limit_is_reached_is_denied(self):
        over = holding(padded_echo(NESTED_READ_LIMIT + 1))
        self.assert_verdict("deny", holding(over, "python3 -i"))
        self.assert_verdict("deny", holding(over + "; python3 -i"))

    # codex-guard-subst-reading-regressions (VERIFICATION.md TS32, NFR1, A3): a
    # second-level string that is held by `sh -c` is of unknown kind and is read
    # twice, because its coproc form stops the first read undecidable; it counts
    # once, at its length, toward the limit. The second second-level string
    # carries the launch, and the two lengths add up exactly to the limit, so the
    # launch is denied only if the first string was counted once.
    def reread_pair(self, second_length):
        head = 'echo "$(coproc echo case x in x)"; echo \''
        first_length = NESTED_READ_LIMIT // 2
        first = head + "x" * (first_length - len(head) - 1) + "'"
        self.assertEqual(len(first), first_length)
        second = padded_launch(second_length)
        return holding("sh -c " + sq(first) + "; bash -c " + sq(second))

    def test_ts32_a_second_level_string_that_is_read_twice_counts_once_toward_the_limit(self):
        self.assert_verdict("deny", self.reread_pair(NESTED_READ_LIMIT - NESTED_READ_LIMIT // 2))

    def test_ts32_one_more_character_in_the_second_string_and_it_is_not_read(self):
        self.assert_verdict("silent", self.reread_pair(NESTED_READ_LIMIT - NESTED_READ_LIMIT // 2 + 1))


class TestDelimiterRows(unittest.TestCase):
    """codex-guard-delim-brace-quote-per-shell (task0001 AC-1 to AC-4, FR6): the
    rows of SPEC.md's Test Scenarios are in CASES, each one built by the
    construction rule of SPEC.md and carrying its expected verdict. CASES runs
    against both copies in `TestCasesTable`."""

    def test_there_is_one_row_for_each_of_ts1_to_ts32(self):
        self.assertEqual(
            [row[0] for row in DELIMITER_PER_SHELL_ROWS], ["TS%d" % n for n in range(1, 33)]
        )

    def test_each_row_is_in_cases_with_its_verdict_and_label(self):
        for row_id, expected, label, wrap, lines in DELIMITER_PER_SHELL_ROWS:
            with self.subTest(row=row_id):
                self.assertIn((expected, label, delimiter_command(wrap, lines)), CASES)

    def test_the_construction_rule_gives_the_commands_written_out_by_hand(self):
        # TS1 has no holder: the command is the lines joined by newlines. TS2 has
        # one holder, TS30 two: the inner string is quoted for the outer shell.
        by_id = {row[0]: row for row in DELIMITER_PER_SHELL_ROWS}
        expected = {
            "TS1": "bash -c 'false && cat <<${v:-\"x\"}\n${v:-\"x\"}\npython3 -i'",
            "TS2": "bash -c 'cat <<${v:-\"x\"}\n${v:-x}\npython3 -i\n${v:-\"x\"}'",
            "TS30": "zsh -c 'bash -c '\"'\"'cat <<${v:-\"x\"}\n${v:-\"x\"}\npython3 -i'\"'\"''",
        }
        for row_id, command in expected.items():
            with self.subTest(row=row_id):
                _, _, _, wrap, lines = by_id[row_id]
                self.assertEqual(delimiter_command(wrap, lines), command)

    def test_the_expected_verdicts_are_the_ones_of_the_specification(self):
        silent = {"TS2", "TS12", "TS14", "TS22", "TS24", "TS28", "TS29", "TS31"}
        for row_id, expected, _, _, _ in DELIMITER_PER_SHELL_ROWS:
            with self.subTest(row=row_id):
                self.assertEqual(expected, "silent" if row_id in silent else "deny")


class TestDelimiterReadingDriver(unittest.TestCase):
    """codex-guard-delim-brace-quote-per-shell (task0001 AC-5, FR3, TM-2): the
    module-level `parse` reads a string held by `sh` under both delimiter
    readings, the bash form first, and combines them: no outcome of one reading
    suppresses the commands of the other. No known input makes the reader raise
    an unexpected error, so a reading's failure is forced in memory: the
    module's `_Parser` is replaced by a subclass whose parse method reads the
    string, as the real one does, and then raises when its delimiter rule is the
    one under test. The parsers it builds are counted."""

    # Both readings read this to its end. The bash form closes the heredoc at the
    # second heredoc line and reads `${v:-x}` as a command; the quote-removal form
    # closes it at the last line.
    DIFFERING = 'python3 -i\ncat <<${v:-"x"}\n${v:-"x"}\n${v:-x}'
    BASH_FORM_COMMANDS = [["python3", "-i"], ["cat"], ["${v:-x}"]]
    QUOTE_REMOVAL_COMMANDS = [["python3", "-i"], ["cat"]]
    # Both forms of the delimiter are the same text.
    COINCIDING = "python3 -i\ncat <<EOF\nEOF"
    # Unreadable under every reading: a substitution inside double quotes that is
    # never closed.
    UNREADABLE = 'echo "$('

    @staticmethod
    def words(commands):
        return [[word.text for word in command.words] for command in commands]

    def run_driver(self, path, command, failing=None, kind="KIND_UNKNOWN", reading="DELIMITER_BOTH"):
        """Run the module-level `parse` of the guard at `path` on `command` for
        the kind and the delimiter reading named. `failing` maps a delimiter rule
        (the name of a module-level value, such as DELIMITER_BASH_FORM) to a
        function that, given the guard namespace, makes the exception the parsers
        of that reading raise after they have read the string. Return (the
        parsers built, the result or None, the exception raised or None)."""
        guard = self.guard = load_guard(path)
        real = guard["_Parser"]
        parsers = []
        failures = {guard[name]: make for name, make in (failing or {}).items()}

        class Recording(real):
            def parse(self):
                parsers.append(self)
                commands = super().parse()
                make = failures.get(self.delimiter_rule)
                if make is not None:
                    raise make(guard)
                return commands

        guard["_Parser"] = Recording
        try:
            return parsers, guard["parse"](command, guard[kind], guard[reading]), None
        except Exception as error:
            return parsers, None, error

    def rules_of(self, path, parsers):
        guard = load_guard(path)
        names = {
            guard["DELIMITER_BASH_FORM"]: "bash form",
            guard["DELIMITER_QUOTE_REMOVAL"]: "quote removal",
        }
        return [names[parser.delimiter_rule] for parser in parsers]

    def test_each_reading_adds_its_commands_and_the_bash_form_comes_first(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(path, self.DIFFERING)
                self.assertIsNone(error)
                self.assertEqual(
                    self.words(result), self.BASH_FORM_COMMANDS + self.QUOTE_REMOVAL_COMMANDS
                )
                self.assertEqual(self.rules_of(path, parsers), ["bash form", "quote removal"])

    def test_an_undecidable_bash_form_reading_leaves_the_quote_removal_commands(self):
        undecidable = lambda guard: guard["_Undecidable"]("forced")
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(
                    path, self.DIFFERING, failing={"DELIMITER_BASH_FORM": undecidable}
                )
                self.assertIsNone(result)
                self.assertIsInstance(error, self.guard["_Undecidable"])
                self.assertEqual(self.words(error.checkpoint_commands), self.QUOTE_REMOVAL_COMMANDS)
                # The unknown kind re-reads the stopped reading once; the quote
                # removal reading read to its end after it.
                self.assertEqual(
                    self.rules_of(path, parsers), ["bash form", "bash form", "quote removal"]
                )

    def test_an_undecidable_quote_removal_reading_leaves_the_bash_form_commands(self):
        undecidable = lambda guard: guard["_Undecidable"]("forced")
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(
                    path, self.DIFFERING, failing={"DELIMITER_QUOTE_REMOVAL": undecidable}
                )
                self.assertIsNone(result)
                self.assertIsInstance(error, self.guard["_Undecidable"])
                self.assertEqual(self.words(error.checkpoint_commands), self.BASH_FORM_COMMANDS)
                self.assertEqual(
                    self.rules_of(path, parsers), ["bash form", "quote removal", "quote removal"]
                )

    def test_a_bash_form_reading_that_fails_with_another_exception_leaves_the_quote_removal_commands(self):
        for error_class in (RuntimeError, KeyError, RecursionError):
            failing = {"DELIMITER_BASH_FORM": lambda guard, cls=error_class: cls("forced")}
            for plugin, path in HOOK_PATHS.items():
                with self.subTest(copy=plugin, failure=error_class.__name__):
                    parsers, result, error = self.run_driver(path, self.DIFFERING, failing=failing)
                    self.assertIsNone(error)
                    self.assertEqual(self.words(result), self.QUOTE_REMOVAL_COMMANDS)

    def test_a_quote_removal_reading_that_fails_with_another_exception_leaves_the_bash_form_commands(self):
        for error_class in (RuntimeError, KeyError, RecursionError):
            failing = {"DELIMITER_QUOTE_REMOVAL": lambda guard, cls=error_class: cls("forced")}
            for plugin, path in HOOK_PATHS.items():
                with self.subTest(copy=plugin, failure=error_class.__name__):
                    parsers, result, error = self.run_driver(path, self.DIFFERING, failing=failing)
                    self.assertIsNone(error)
                    self.assertEqual(self.words(result), self.BASH_FORM_COMMANDS)

    def test_when_both_readings_fail_with_another_exception_that_of_the_bash_form_leaves(self):
        failing = {
            "DELIMITER_BASH_FORM": lambda guard: RuntimeError("bash form"),
            "DELIMITER_QUOTE_REMOVAL": lambda guard: KeyError("quote removal"),
        }
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(path, self.DIFFERING, failing=failing)
                self.assertIsNone(result)
                self.assertIsInstance(error, RuntimeError)
                self.assertEqual(error.args, ("bash form",))
                self.assertEqual(self.rules_of(path, parsers), ["bash form", "quote removal"])

    def test_a_failed_reading_next_to_an_undecidable_one_leaves_an_undecidable_with_no_commands(self):
        failing = {
            "DELIMITER_BASH_FORM": lambda guard: RuntimeError("forced"),
            "DELIMITER_QUOTE_REMOVAL": lambda guard: guard["_Undecidable"]("forced"),
        }
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(path, self.DIFFERING, failing=failing)
                self.assertIsNone(result)
                self.assertIsInstance(error, self.guard["_Undecidable"])
                self.assertEqual(list(error.checkpoint_commands), [])

    def test_a_string_whose_two_forms_coincide_builds_the_parsers_of_one_reading(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(path, self.COINCIDING)
                self.assertIsNone(error)
                self.assertEqual(self.words(result), [["python3", "-i"], ["cat"]])
                self.assertEqual(self.rules_of(path, parsers), ["bash form"])

    def test_an_unreadable_string_with_no_differing_delimiter_builds_the_parsers_of_one_reading(self):
        # The unknown kind reads the string twice within the one reading.
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(path, self.UNREADABLE)
                self.assertIsNone(result)
                self.assertIsInstance(error, self.guard["_Undecidable"])
                self.assertEqual(self.rules_of(path, parsers), ["bash form", "bash form"])

    def test_a_string_whose_forms_differ_builds_the_parsers_of_both_readings(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, _, error = self.run_driver(path, self.DIFFERING)
                self.assertIsNone(error)
                self.assertEqual(sorted(set(self.rules_of(path, parsers))), ["bash form", "quote removal"])

    def test_a_forced_reading_that_recorded_no_differing_word_does_not_run_the_other(self):
        # The skip condition is read from the parsers' records, not from the
        # string: a reading that stopped before it saw a differing word leaves
        # nothing that the other reading could add.
        stops_early = lambda guard: guard["_Undecidable"]("forced")
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                parsers, result, error = self.run_driver(
                    path, self.COINCIDING, failing={"DELIMITER_BASH_FORM": stops_early}
                )
                self.assertIsInstance(error, self.guard["_Undecidable"])
                self.assertEqual(set(self.rules_of(path, parsers)), {"bash form"})

    def test_a_single_reading_builds_the_parsers_of_that_reading_only(self):
        for plugin, path in HOOK_PATHS.items():
            for reading, name in (
                ("DELIMITER_BASH_FORM", "bash form"),
                ("DELIMITER_QUOTE_REMOVAL", "quote removal"),
            ):
                with self.subTest(copy=plugin, reading=reading):
                    parsers, _, error = self.run_driver(path, self.DIFFERING, reading=reading)
                    self.assertIsNone(error)
                    self.assertEqual(set(self.rules_of(path, parsers)), {name})

    def test_the_default_reading_is_quote_removal_and_reads_a_string_of_unknown_kind_twice(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                guard = load_guard(path)
                parsers = []
                real = guard["_Parser"]

                class Recording(real):
                    def parse(self):
                        parsers.append(self)
                        return super().parse()

                guard["_Parser"] = Recording
                with self.assertRaises(guard["_Undecidable"]):
                    guard["parse"](self.UNREADABLE)
                self.assertEqual(len(parsers), 2)
                self.assertEqual(
                    {parser.delimiter_rule for parser in parsers}, {guard["DELIMITER_QUOTE_REMOVAL"]}
                )

    def test_a_parser_records_a_differing_delimiter_word_under_either_rule(self):
        for plugin, path in HOOK_PATHS.items():
            guard = load_guard(path)
            for rule in ("DELIMITER_BASH_FORM", "DELIMITER_QUOTE_REMOVAL"):
                with self.subTest(copy=plugin, rule=rule, string="differing"):
                    parser = guard["_Parser"](self.DIFFERING, True, True, guard[rule])
                    self.assertFalse(parser.differs)
                    parser.parse()
                    self.assertTrue(parser.differs)
                with self.subTest(copy=plugin, rule=rule, string="coinciding"):
                    parser = guard["_Parser"](self.COINCIDING, True, True, guard[rule])
                    parser.parse()
                    self.assertFalse(parser.differs)

    def test_a_parser_without_a_delimiter_rule_reads_the_quote_removal_form(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                guard = load_guard(path)
                parser = guard["_Parser"](self.DIFFERING)
                self.assertEqual(parser.delimiter_rule, guard["DELIMITER_QUOTE_REMOVAL"])
                self.assertEqual(self.words(parser.parse()), self.QUOTE_REMOVAL_COMMANDS)


class TestDelimiterReadingNestedReadLimit(HookCopiesMixin, unittest.TestCase):
    """codex-guard-delim-brace-quote-per-shell (task0001 AC-6, FR5, NFR2, TM-3):
    a string held by `sh` is read under both delimiter readings and counts once
    toward `NESTED_READ_LIMIT`, at its length, before the readings run. A nested
    string counts each time the walk reaches it, so one that both readings reach
    counts twice. The strings are built so that every length is plain
    arithmetic, as in `TestNestedReadLimit`."""

    TIMEOUT = 60
    # The delimiter of this heredoc differs between the readings: the bash form
    # closes it at the first body line, quote removal at a line `${v:-x}`.
    DIFFERING_HEREDOC = 'cat <<${v:-"x"}\n${v:-"x"}\n'
    COINCIDING_HEREDOC = "cat <<EOF\nEOF"

    def verdict(self, path, command):
        return verdict_of(run_hook(path, payload_for(command), timeout=self.TIMEOUT))

    def assert_verdict(self, expected, command):
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin):
                self.assertEqual(self.verdict(path, command), expected)

    def sh_pair(self, holder_string, later_string):
        """A first-level string that runs `holder_string` under `sh -c`, and then
        `later_string` under `bash -c`; both are second-level strings."""
        return holding("sh -c " + sq(holder_string) + "; bash -c " + sq(later_string))

    # A second-level string held by `sh`, read under both readings, counts once
    # at its length: the launch it holds is denied when its length is exactly the
    # limit, and one more character leaves it unread.
    def holder_with_launch(self, length):
        head = self.DIFFERING_HEREDOC
        return head + padded_launch(length - len(head))

    def test_a_second_level_string_read_under_both_readings_counts_once_at_its_length(self):
        holder = self.holder_with_launch(NESTED_READ_LIMIT)
        self.assertEqual(len(holder), NESTED_READ_LIMIT)
        self.assert_verdict("deny", holding("sh -c " + sq(holder)))

    def test_one_more_character_and_that_string_is_not_read(self):
        holder = self.holder_with_launch(NESTED_READ_LIMIT + 1)
        self.assertEqual(len(holder), NESTED_READ_LIMIT + 1)
        self.assert_verdict("silent", holding("sh -c " + sq(holder)))

    # The third-level string sits on the holder's first line, before its heredoc,
    # so both readings reach it: the quote-removal reading stops undecidable at
    # the heredoc, after the checkpoint of that first line. The second
    # second-level string of the first-level string carries the launch; the
    # lengths add up to the limit exactly when the walk counts the third-level
    # string as many times as it reaches it.
    THIRD = padded_echo(1000)

    def holder_with_third_level(self, heredoc):
        return "bash -c " + sq(self.THIRD) + "\n" + heredoc

    def test_a_third_level_string_that_both_readings_reach_counts_each_time(self):
        holder = self.holder_with_third_level(self.DIFFERING_HEREDOC)
        room = NESTED_READ_LIMIT - len(holder) - 2 * len(self.THIRD)
        self.assert_verdict("deny", self.sh_pair(holder, padded_launch(room)))
        self.assert_verdict("silent", self.sh_pair(holder, padded_launch(room + 1)))

    def test_a_third_level_string_that_both_readings_reach_does_not_count_once(self):
        # With the count of a single reach the launch string below would be read.
        holder = self.holder_with_third_level(self.DIFFERING_HEREDOC)
        room = NESTED_READ_LIMIT - len(holder) - len(self.THIRD)
        self.assert_verdict("silent", self.sh_pair(holder, padded_launch(room)))

    def test_a_third_level_string_counts_once_when_the_two_readings_coincide(self):
        holder = self.holder_with_third_level(self.COINCIDING_HEREDOC)
        room = NESTED_READ_LIMIT - len(holder) - len(self.THIRD)
        self.assert_verdict("deny", self.sh_pair(holder, padded_launch(room)))
        self.assert_verdict("silent", self.sh_pair(holder, padded_launch(room + 1)))

    # TM-3: a first-level string held by `sh`, far longer than 100,000
    # characters, holds many heredocs whose delimiters differ between the
    # readings. Each reading is linear and a string gets a constant number of
    # reads, so it is answered within the timeout of the other limit tests.
    UNIT = 'cat <<${v:-"x"}\n${v:-"x"}\n${v:-x}\n'

    def big_string(self, last):
        units = 100000 // len(self.UNIT) + 1000
        text = self.UNIT * units + last
        self.assertGreater(len(text), 100000)
        return text

    def test_a_long_string_with_many_differing_heredocs_is_answered_in_time_and_denied(self):
        # The bash form closes the last heredoc at its second line and reads the
        # launch after it; quote removal never closes it.
        text = self.big_string('cat <<${v:-"x"}\n${v:-"x"}\npython3 -i')
        self.assert_verdict("deny", "sh -c " + sq(text))

    def test_the_same_long_string_stays_silent_when_the_launch_is_inside_the_last_body(self):
        text = self.big_string('cat <<${v:-"x"}\npython3 -i')
        self.assert_verdict("silent", "sh -c " + sq(text))


class TestArithmeticRereadBudget(HookCopiesMixin, unittest.TestCase):
    """codex-guard-delim-subst-undecidable (VERIFICATION.md TS17, NFR1, TM-2): a
    command-position `((` that does not close with `))` is read again once as two
    nested subshells, and the characters read again, summed over the skips of one
    parser, are capped by a named limit: `ARITHMETIC_REREAD_FACTOR` times the
    length of the string. The input is generated and large, so it is not a row of
    CASES. `nested(depth)` holds `depth` arithmetic commands, each with a
    substitution that holds the next one and none closed by `))`: the second
    reading of each covers all the ones inside it, so without the cap the
    characters read again grow with the square of the depth."""

    TIMEOUT = 60
    # Deep enough that, uncapped, the second readings take far longer than the
    # budget of the hook, and the cap is reached long before the innermost
    # command is back in the work.
    DEEP = 3000

    @staticmethod
    def nested(depth):
        text = "x"
        for _ in range(depth):
            text = "((a $( " + text + ") b) )"
        return text

    def command(self, depth):
        return 'echo "$( ' + self.nested(depth) + ' )"; python3 -i'

    def assert_verdict(self, expected, command):
        for plugin, path in self.for_each_copy():
            self.assertEqual(
                verdict_of(run_hook(path, payload_for(command), timeout=self.TIMEOUT)), expected
            )

    def test_each_copy_defines_the_factor_once_with_a_value_the_docstring_states(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                assigns = [
                    node for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "ARITHMETIC_REREAD_FACTOR" for t in node.targets)
                ]
                self.assertEqual(len(assigns), 1, "one assignment at module level")
                value = assigns[0].value
                self.assertIsInstance(value, ast.Constant)
                self.assertIs(type(value.value), int)
                self.assertGreater(value.value, 0)
                doc = parser_docstring(path, "_skip_substitution") or ""
                self.assertIn(
                    "`ARITHMETIC_REREAD_FACTOR` (%d) times the length of the string" % value.value, doc
                )

    def test_a_chain_within_the_budget_is_read_and_the_launch_after_it_is_denied(self):
        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                self.assert_verdict("deny", self.command(depth))

    def test_a_chain_that_would_exceed_the_budget_is_undecidable_in_time_without_an_error(self):
        # `verdict_of` reports "error" for a non-zero status or any standard error
        # output, so a recursion error or a crash fails here as well as a timeout.
        self.assert_verdict("silent", self.command(self.DEEP))

    def test_each_arithmetic_command_is_read_again_once(self):
        # Two nested ones, none closed by `))`: the inner one's second reading
        # runs first, then the outer one's, which reads the inner text again but
        # as two subshells, so the characters read again are exactly the span of
        # each from its `((` to the `)` that was not followed by a second `)`.
        command = '"$( ' + self.nested(2) + ' )"'
        inner = "((a $( x) b"
        outer = "((a $( " + self.nested(1) + ") b"
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                guard = load_guard(path)
                parser = guard["_Parser"](command)
                end = parser._skip_substitution(command.index("$("))
                self.assertEqual(end, len(command) - 1)
                spent = guard["ARITHMETIC_REREAD_FACTOR"] * len(command) - parser.arith_budget
                self.assertEqual(spent, len(inner) + len(outer))

    def test_the_budget_runs_out_across_the_skips_of_one_parser(self):
        # Separate substitutions each use some of the one budget of the string.
        guard = load_guard(next(iter(HOOK_PATHS.values())))
        unit = '"$( ((a) ) )" '
        command = unit * 4
        parser = guard["_Parser"](command)
        for k in range(4):
            parser._skip_substitution(command.index("$(", k * len(unit)))
        self.assertEqual(
            guard["ARITHMETIC_REREAD_FACTOR"] * len(command) - parser.arith_budget,
            4 * len("((a"),
        )


def module_docstring(path):
    """The module docstring with its line breaks and indentation folded into
    single spaces, so a sentence is found wherever the text wraps."""
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
    return " ".join(doc.split())


def parser_docstring(path, method=None):
    """The docstring of the `_Parser` class, or of its method `method`, with
    its line breaks and indentation folded into single spaces. None when the
    method does not exist."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_Parser"
    )
    if method is not None:
        node = next(
            (
                member for member in node.body
                if isinstance(member, ast.FunctionDef) and member.name == method
            ),
            None,
        )
        if node is None:
            return None
    return " ".join((ast.get_docstring(node) or "").split())


class TestGuardDocumentation(unittest.TestCase):
    """The judgment procedure in the module docstring follows the parser
    (FR6): the markers below are the sentences that name each behavior."""

    DOCSTRING_MARKERS = (
        # FR1
        "`-c` takes no value",
        # FR2
        "shells have no information short option",
        # FR3
        "inside double quotes",
        # FR4
        "group",
        "stdin redirect",
        # FR5
        "pending pipe",
        # A function definition starts only at `name(` or `function name(`
        "only `name()` and `function name()` start a function definition",
        # A leading run of reserved words is removed before the words are read
        "after the leading run of the reserved words `!` `do` `elif` `else` `if` "
        "`then` `time` `until` `while` is removed",
        "a non-dynamic `-p` right after `time` is removed with it",
        "When nothing remains, the original words are judged",
        "three words or more left after the removal",
        # A word that ends in an extglob operator character is no function name
        "ends in one of the extglob operator characters `?` `*` `+` `@` `!`",
        "after quote removal",
        "the group after its `()` is judged",
        "whether extglob is enabled is never checked",
        # A literal shell `-c` string is judged at every level, with the same rules
        "found inside a command string is judged too, at every level, with the same rules",
        # The nested strings are walked with an explicit stack, in a fixed order
        "walked with an explicit stack (a work list), never by recursion",
        "are judged before the commands after the command that holds it",
        "the first launch to deny decides",
        # The characters re-read from nested strings are limited
        "up to 1,000,000 characters",
        "First-level strings are not counted",
        "pass unread",
        "Passing the limit is never a reason to deny",
        # A string whose reading ends in an unexpected error is skipped too
        "a string for which an unexpected error occurred while it was being read",
        # The three zsh anonymous-function forms, their arguments and their pipe
        "`function { ...; }`",
        "`function () { ...; } arg`",
        "`() { ...; } arg`",
        "is an argument of the anonymous function",
        "A stdin redirect among or after the arguments connects the body",
        "the pipe connection passes to the body",
        # A standalone bare `}` closes an anonymous body, or a `{` group inside
        # one, with words pending (FR1, FR2), and no other group (FR5)
        "the group is the body of an anonymous function, or it is a `{` group "
        "that lies inside the body of an anonymous function, at any depth",
        "finalized first, as a command of that group, exactly as a `;` before the `}` finalizes them",
        "outside every anonymous function body",
        "the `}` is an ordinary word and the string stays undecidable",
    )

    # Sentences step 7 carried before it judged a literal `-c` string at every
    # level; the docstring no longer says them.
    STALE_DOCSTRING_SENTENCES = (
        "the first operand is judged once",
        "A literal inside the command string is not judged",
        # Step 4 limited `{` to command position before a `{` could open a group
        # right after the head of an anonymous function
        "delimit a group only as a standalone word at command position",
        # Step 4 said every group that is never closed gives no output, before a
        # provisional group left open at a `;` or a lone `&` was rescued
        "and a group that is never closed -> no output",
        # Step 4 said a provisional group is rescued only when it is never
        # closed, before a lone `}` rescued the chain it ends
        "When a provisional group is never closed (its `)` sits in a comment, or there is none)",
    )

    # How the `_Group` description said a provisional group is rescued only
    # when input ends, before a lone `}` rescued it too
    STALE_GROUP_SENTENCES = (
        "may be rescued when input ends, and no other group ever is",
    )

    # The same removal in the description of a group's `head` attribute
    GROUP_HEAD_MARKERS = (
        "the leading run of the reserved words `!` `do` `elif` `else` `if` "
        "`then` `time` `until` `while` is removed",
        "a non-dynamic `-p` right after `time` is removed with it",
        "When nothing remains, the original words are judged",
        "counts are the words left after the removal",
        "ends in one of the extglob operator characters `?` `*` `+` `@` `!`",
        "after quote removal",
        "the group after its `()` is judged",
    )

    # How the `_Group` description marks an anonymous body and where its pipe
    # connection comes from
    GROUP_ANON_MARKERS = (
        "the group is an anonymous body",
        "the words after its `}` are arguments",
        "the anonymous body takes it as its `pipe`",
        "the pipe connection comes from the head",
    )

    # How the `_Group` description marks the group as lying inside an
    # anonymous body: a value fixed once, when the group opens (NFR1)
    GROUP_IN_ANON_MARKERS = (
        "within an anonymous-function body",
        "fixed once, when the group opens",
        "inherited from the innermost group open at that moment",
        "never recomputed",
    )

    # The rule of the method that decides the parenless anonymous-function form
    PARENLESS_MARKERS = (
        "exactly one `function` that holds no quote, no escape and no expansion",
        "the same reserved-run removal",
        "constant time",
    )

    # The same rule in the docstring of the parser's function-name judgment
    NAMES_FUNCTION_MARKERS = (
        "ends in one of the extglob operator characters `?` `*` `+` `@` `!`",
        "after quote removal",
        "the group after its `()` is judged",
        "whether extglob is enabled is never checked",
    )

    def test_the_docstring_describes_the_new_behaviour(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in self.DOCSTRING_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    # The rescue rule for a group that is opened at an anonymous-function
    # argument `(` and never closed (FR7): (a) the group is provisional; (b) when
    # its first direct separator is a `;` or a lone `&`, its `(` is read as an
    # argument-word character and the commands after the separator are judged as
    # following the anonymous function; (c) a newline as the first direct
    # separator is not rescued; (d) a group that is genuinely unclosed still
    # yields no output
    RESCUE_PROVISIONAL_MARKER = "A group opened at such a `(` is provisional"
    RESCUE_MARKERS = (
        "its `(` is read as an argument-word character",
        "the commands after that separator are judged as following the anonymous function",
        "A newline as the first direct separator is not rescued",
        "A group that is genuinely unclosed still yields no output",
    )

    def test_the_module_docstring_states_the_rescue_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in (self.RESCUE_PROVISIONAL_MARKER,) + self.RESCUE_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_parser_description_states_the_rescue_rule(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parser = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Parser"
            )
            doc = " ".join((ast.get_docstring(parser) or "").split())
            for marker in (self.RESCUE_PROVISIONAL_MARKER,) + self.RESCUE_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_argument_paren_reader_states_the_rescue_rule(self):
        markers = (
            "The group opened here is provisional",
            "its `(` is read as an argument-word character",
            "the commands after that separator are judged as following the anonymous function",
            "A newline as the first direct separator is not rescued",
        )
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parser = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Parser"
            )
            method = next(
                (
                    node for node in parser.body
                    if isinstance(node, ast.FunctionDef) and node.name == "_read_argument_parens"
                ),
                None,
            )
            with self.subTest(copy=plugin, method="_read_argument_parens"):
                self.assertIsNotNone(method, "no _read_argument_parens method in _Parser")
            if method is None:
                continue
            doc = " ".join((ast.get_docstring(method) or "").split())
            for marker in markers:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    # The backquote rule (FR7): a range among the arguments of an anonymous
    # function that holds a backquote is read as a group, as one that holds an
    # unquoted `;`, `&` or newline is. One marker per docstring that states it
    BACKQUOTE_MODULE_MARKER = (
        "A range that holds a backquote, one inside double quotes included, opens a group too"
    )
    BACKQUOTE_PARSER_MARKER = (
        "or a backquote (one inside double quotes included), or no matching `)` is found"
    )
    BACKQUOTE_SCAN_MARKER = (
        "`backquoted` is whether a backquote lies between the `(` and the `)`, "
        "one inside double quotes included"
    )
    BACKQUOTE_READER_MARKER = "the range holds an unquoted `;`, `&` or newline, or a backquote"

    def test_the_module_docstring_states_the_backquote_rule(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.BACKQUOTE_MODULE_MARKER, module_docstring(path))

    def test_the_parser_description_states_the_backquote_rule(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.BACKQUOTE_PARSER_MARKER, parser_docstring(path))

    def test_the_range_scan_states_the_backquote_rule(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin, method="_scan_parens"):
                doc = parser_docstring(path, "_scan_parens")
                self.assertIsNotNone(doc, "no _scan_parens method in _Parser")
                self.assertIn(self.BACKQUOTE_SCAN_MARKER, doc or "")

    def test_the_argument_paren_reader_states_the_backquote_rule(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin, method="_read_argument_parens"):
                doc = parser_docstring(path, "_read_argument_parens")
                self.assertIsNotNone(doc, "no _read_argument_parens method in _Parser")
                self.assertIn(self.BACKQUOTE_READER_MARKER, doc or "")

    # The delimiter-range rules (FR6): a range among the arguments of an
    # anonymous function that is the delimiter of `<<` / `<<-` is quote-removed
    # before it is registered, and an unquoted `$'` / `$"` in it makes the
    # input unknowable
    DELIMITER_RANGE_MARKERS = (
        "has its text quote-removed by the rules the reader applies to any word, "
        "before the delimiter is registered",
        "The part of the word outside the range was quote-removed when it was read "
        "and is not processed again",
        "An unquoted `$'` or `$\"` inside such a range makes the whole input unknowable -> no output",
        "a `$'` or `$\"` inside quotes and a backslash-escaped `$` are no trigger",
    )

    def test_the_module_docstring_states_the_delimiter_range_rules(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in self.DELIMITER_RANGE_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    # A lone `}` read after a rescued separator closes the enclosing `{` group
    # (FR5): the sentence is in the module docstring and in the docstring of
    # `_Parser`
    BRACE_CLOSE_MARKER = (
        "A lone `}` read after a rescued separator closes the enclosing `{` group"
    )

    def test_the_module_docstring_states_that_a_brace_closes_the_group_after_a_rescue(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.BRACE_CLOSE_MARKER, module_docstring(path))

    def test_the_parser_description_states_that_a_brace_closes_the_group_after_a_rescue(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.BRACE_CLOSE_MARKER, parser_docstring(path))

    # A `)` read while a provisional group is the innermost open group rescues
    # the chain and closes the `(` group just outside it: the sentence is in the
    # module docstring and in the docstring of `_Parser`
    PAREN_CLOSE_MARKER = (
        "A `)` read while a provisional group is the innermost open group rescues "
        "the chain of provisional groups there and closes the `(` group just "
        "outside the chain"
    )

    def test_the_module_docstring_states_that_a_paren_rescues_the_chain_and_closes_the_subshell(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.PAREN_CLOSE_MARKER, module_docstring(path))

    def test_the_parser_description_states_that_a_paren_rescues_the_chain_and_closes_the_subshell(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.PAREN_CLOSE_MARKER, parser_docstring(path))

    # The comment exception (FR2 to FR4, FR8): a group opened because its range
    # held a backquote reads an unquoted `#` at word start as a word character
    # while it is the innermost open group. The rule is written in the module
    # docstring (step 4), the docstring of `_Parser`, the docstring of
    # `_read_argument_parens` and the description of the `_Group` attribute that
    # holds it: the opening condition, the word-character reading, the
    # inheritance at open, the clearing on the five direct separators, and that
    # it is the single exception to the earlier assumption
    COMMENT_EXCEPTION_MARKERS = (
        "has the comment exception: while it is the innermost open group, an "
        "unquoted `#` at word start is a word character, not the start of a comment",
        "holds no unquoted `;`, `&` or newline and holds a backquote",
        "starts with it, whatever its own opening condition",
        "a `;`, a lone `&`, `&&`, `|&` or a newline that the reader itself reads while "
        "a group with the comment exception is the innermost open group clears it",
        "`|`, `||`, `&>`, `>&`, a quoted separator and a backslash-escaped separator "
        "clear nothing",
        "the single exception to the earlier assumption that group reading adds no "
        "new reading",
    )

    def test_the_module_docstring_states_the_comment_exception(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in self.COMMENT_EXCEPTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_parser_description_states_the_comment_exception(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path)
            for marker in self.COMMENT_EXCEPTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_argument_paren_reader_states_the_comment_exception(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_read_argument_parens")
            with self.subTest(copy=plugin, method="_read_argument_parens"):
                self.assertIsNotNone(doc, "no _read_argument_parens method in _Parser")
            for marker in self.COMMENT_EXCEPTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc or "")

    def test_the_group_description_states_the_comment_exception_attribute(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            doc = " ".join((ast.get_docstring(group) or "").split())
            for marker in ("comment_exception",) + self.COMMENT_EXCEPTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    # The case mark and the inherited value (FR5): the case mark is the number
    # of unfinished `case`s of a provisional group, a bare `case` at command
    # position raises it, a bare `esac` at command position or right after
    # `case`, one word and a bare `in` lowers it, a provisional group opened
    # inside a provisional group takes the inherited value from its parent and
    # lowers it by `esac` when its own mark is 0, and a group that has either
    # one at 1 or more is not rescued at a `)`. Seven places say so: step 4 of
    # the module docstring, the docstring of `_Parser`, the field list of
    # `_Group`, and the docstrings of `_mark_provisional`, `_append_word`,
    # `_close_paren` and `_closes_paren_after_rescue`; the word `esac` is
    # required in the module docstring, `_Parser`, `_Group` and `_append_word`
    CASE_MARK_TERMS = ("case mark", "inherited value")
    CASE_MARK_PARSER_METHODS = {
        "_mark_provisional": CASE_MARK_TERMS,
        "_append_word": ("case mark", "esac"),
        "_close_paren": CASE_MARK_TERMS,
        "_closes_paren_after_rescue": CASE_MARK_TERMS,
    }
    # Statements that the mark is permanent: the mark is a count that `esac`
    # lowers, so none of these may remain in either copy
    CASE_MARK_PERMANENCE_PHRASES = (
        "The mark is never cleared",
        "It is never cleared",
        "for the rest of its life",
    )

    def test_the_seven_places_that_describe_the_paren_rescue_state_the_case_mark(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            places = {
                "module docstring": (module_docstring(path), self.CASE_MARK_TERMS + ("esac",)),
                "_Parser": (parser_docstring(path), self.CASE_MARK_TERMS + ("esac",)),
                "_Group": (
                    " ".join((ast.get_docstring(group) or "").split()),
                    self.CASE_MARK_TERMS + ("case_mark", "case_inherited", "esac"),
                ),
            }
            for method, terms in self.CASE_MARK_PARSER_METHODS.items():
                places[method] = (parser_docstring(path, method) or "", terms)
            for place, (doc, terms) in places.items():
                for term in terms:
                    with self.subTest(copy=plugin, place=place, term=term):
                        self.assertIn(term, doc)

    def test_no_copy_says_the_case_mark_is_permanent(self):
        for plugin, path in HOOK_PATHS.items():
            text = " ".join(path.read_text(encoding="utf-8").split())
            for phrase in self.CASE_MARK_PERMANENCE_PHRASES:
                with self.subTest(copy=plugin, phrase=phrase):
                    self.assertNotIn(phrase, text)

    # What step 4 says about the head's stdin redirect, a `(` among the
    # arguments of an anonymous function, and where the arguments end
    ANONYMOUS_ARGUMENT_MARKERS = (
        "A stdin redirect read in the head of an anonymous function also connects its body",
        "That connection reaches the body alone",
        "is read together with everything up to its matching `)` as part of one argument word",
        "whitespace and `|` inside the range belong to the word",
        "holds an unquoted `;`, `&` or newline, the `(` opens a group",
        "`|&` `&` or newline that lies outside a `(`...`)` range",
    )

    def test_the_docstring_describes_the_head_redirect_and_the_parens_among_the_arguments(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in self.ANONYMOUS_ARGUMENT_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_paren_search_is_not_described_as_fully_quote_aware(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            texts = [" ".join((ast.get_docstring(tree) or "").split())]
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    texts.append(" ".join((ast.get_docstring(node) or "").split()))
            with self.subTest(copy=plugin):
                for text in texts:
                    self.assertNotIn("fully quote-aware", text)
                self.assertIn("a backquote and a comment get no special reading", texts[0])

    def test_the_docstring_no_longer_limits_a_literal_c_string_to_the_first_level(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for stale in self.STALE_DOCSTRING_SENTENCES:
                with self.subTest(copy=plugin, stale=stale):
                    self.assertNotIn(stale, doc)

    # The checkpoint rule (FR2, FR6): when a string turns out undecidable, the
    # commands up to the last checkpoint are judged and a string with no
    # checkpoint gives no output. The sentences are written in the module
    # docstring (step 9), the docstring of `_Parser` and the docstring of `_scan`:
    # the four conditions, the commands judged, the connection and skip they
    # take, no output without a checkpoint, the hook command and every nested
    # literal `-c` string, the full length counted toward the limit, and the
    # errors other than `_Undecidable` that are handled as before
    CHECKPOINT_MARKERS = (
        "A checkpoint is a newline that the reader itself reads at the top level",
        "no group is open, no pipe is pending, no list continuation is pending",
        "have been read through their terminators",
        "the commands up to the last checkpoint are judged",
        "with connection and skip taken from the groups opened before it",
        "a string with no checkpoint gives no output",
        "applies to the hook command and to every nested literal shell `-c` string",
        "an undecidable string counts at its full length toward NESTED_READ_LIMIT",
        "An error other than _Undecidable is handled as before",
    )

    # The passages of the module docstring that said an undecidable string gives
    # no output: each one names the checkpoint rule (start anchor, end anchor)
    CHECKPOINT_PASSAGES = (
        ("3. Remove heredoc bodies", "4. A subshell"),
        ("4. A subshell", "5. After `|` or `|&`"),
        ("7. A shell (bash sh zsh dash ksh)", "8. Deny a launch"),
        ("9. Anything undecidable", "Everything the guard cannot positively identify passes"),
        ("Everything the guard cannot positively identify passes", "The guard uses only the standard library"),
    )
    CHECKPOINT_PASSAGE_MARKERS = (
        "the commands up to the last checkpoint are judged",
        "no checkpoint",
    )

    def test_the_module_docstring_states_the_checkpoint_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for marker in self.CHECKPOINT_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_each_module_passage_that_gave_no_output_names_the_checkpoint_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for start, end in self.CHECKPOINT_PASSAGES:
                begin = doc.find(start)
                with self.subTest(copy=plugin, passage=start):
                    self.assertNotEqual(begin, -1, "the passage is missing")
                    stop = doc.find(end, begin + len(start))
                    self.assertNotEqual(stop, -1, "the end of the passage is missing")
                    passage = doc[begin:stop]
                    for marker in self.CHECKPOINT_PASSAGE_MARKERS:
                        self.assertIn(marker, passage)

    def test_the_parser_description_states_the_checkpoint_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path)
            for marker in self.CHECKPOINT_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_scan_description_states_the_checkpoint_rule(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            scan = next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "_scan"
            )
            doc = " ".join((ast.get_docstring(scan) or "").split())
            for marker in self.CHECKPOINT_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_group_description_no_longer_limits_the_rescue_to_the_end_of_input(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            doc = " ".join((ast.get_docstring(group) or "").split())
            for stale in self.STALE_GROUP_SENTENCES:
                with self.subTest(copy=plugin, stale=stale):
                    self.assertNotIn(stale, doc)

    def test_the_group_head_description_states_the_removal(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            doc = " ".join((ast.get_docstring(group) or "").split())
            for marker in self.GROUP_HEAD_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_group_description_names_the_anonymous_body_and_its_pipe_source(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            doc = " ".join((ast.get_docstring(group) or "").split())
            for marker in self.GROUP_ANON_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_group_description_states_the_within_an_anonymous_body_attribute(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            group = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Group"
            )
            doc = " ".join((ast.get_docstring(group) or "").split())
            for marker in self.GROUP_IN_ANON_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_parenless_form_method_states_its_rule_and_its_constant_time(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parser = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Parser"
            )
            method = next(
                (
                    node for node in parser.body
                    if isinstance(node, ast.FunctionDef) and node.name == "_names_anonymous_function"
                ),
                None,
            )
            with self.subTest(copy=plugin, method="_names_anonymous_function"):
                self.assertIsNotNone(method, "no _names_anonymous_function method in _Parser")
            if method is None:
                continue
            doc = " ".join((ast.get_docstring(method) or "").split())
            for marker in self.PARENLESS_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_names_function_docstring_states_the_extglob_rule(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parser = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "_Parser"
            )
            method = next(
                node for node in parser.body
                if isinstance(node, ast.FunctionDef) and node.name == "_names_function"
            )
            doc = " ".join((ast.get_docstring(method) or "").split())
            for marker in self.NAMES_FUNCTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_no_text_makes_h_and_V_information_options_of_every_interpreter(self):
        for plugin, path in HOOK_PATHS.items():
            source = path.read_text(encoding="utf-8")
            for stale in ("INFO_LETTERS", "in every family"):
                with self.subTest(copy=plugin, stale=stale):
                    self.assertNotIn(stale, source)


class TestSubstitutionSkipDocumentation(unittest.TestCase):
    """The docstring of the substitution skip says that a case statement inside
    the chunk is read and names every form that still makes the chunk
    undecidable (FR9, D4); the module docstring keeps its sentence about a
    chunk whose close cannot be located."""

    STALE_SENTENCE = "a heredoc or a `case` inside it"
    READ_MARKERS = (
        "a case statement inside the chunk is read",
        "its pattern's `)` closes neither the chunk nor a group",
    )
    UNDECIDABLE_MARKERS = (
        "no `in`, and no standalone `{`, after the subject",
        "no closing `esac` before the input ends",
        "a `)` with no pattern at a pattern position",
        "a heredoc anywhere in the chunk (item bodies included)",
        "an unmatched `)` in an item body",
        "an unquoted `;` or `&` where a pattern must begin",
        "an unquoted newline, `;` or `&` in a pattern outside its groups",
        "an item terminator read while a `{ }` group is open in a brace-form item body",
        "an `esac` at a command position of a brace-form item body",
    )
    # codex-guard-escaped-hash-brace-case-heredoc (FR7): the stale form that
    # listed zsh's brace form among the forms with no `in` stays out.
    STALE_BRACE_FORM_SENTENCE = "no `in` after the subject (zsh's brace form included)"
    # The rule 2 description of the brace form `case x { ... }`: how it opens,
    # the three closings, the depth of the `{ }` groups of an item body, the
    # readings of quoted and escaped braces, and that the shell kind does not
    # matter. The rule 5, rule 8 and rule 9 paragraphs and the phase list say
    # their part.
    BRACE_FORM_MARKERS = {
        "rule 2 opening": (
            "The zsh brace form `case x { ... }` is read for every kind of shell that holds the string",
            "standalone `{` after the subject, decided on the characters with the continuation pairs left out and followed by a space, a tab, a newline or the end of the input, opens the statement in place of `in`",
            "a quoted `{`, an escaped `{` and a `{` that is not a standalone word are no `in`",
        ),
        "rule 2 closings": (
            "brace-form statement closes in one of three ways",
            "(a) a standalone, unquoted, unescaped `}` at a pattern position",
            "(b) a standalone `esac` at a pattern position",
            "(c) a standalone `}` read at a command position of the item body list itself while no `{ }` group is open in that body",
            "In the `in` form a `}` at a pattern position starts a pattern",
        ),
        "rule 2 depth": (
            "Each brace-form statement keeps the depth of the `{ }` groups open in its item body",
            "a standalone `{` read at a command position of the item body list itself raises it by one",
            "and so does the standalone `{` right after `function` (a zsh anonymous function reads it as its name)",
            "a standalone `}` read there lowers it by one while it is 1 or more",
            "A quoted or escaped `}` or `esac` starts a pattern at a pattern position and is an ordinary word in a body",
            "a nested case statement keeps a form and a depth of its own",
        ),
        "rule 5 closing": (
            "the `}` that closes a brace-form case statement, which gives the list that holds the statement a command position as `esac` does",
        ),
        "rule 8 heredoc": (
            "A `<<` inside a case statement (its subject, its patterns, its item bodies and every list nested in them) stays undecidable",
            "The brace form `case x { ... }` is no exception",
        ),
        "rule 9 re-read": (
            "The re-read also restores the brace-form state: the form and the depth of the statements open at the `((` are what they were there, and the values of the statements opened after it go with their stack entries",
        ),
        "phase list": (
            "3 after the subject (waiting for `in` or a standalone `{`)",
        ),
    }
    MODULE_SENTENCE = (
        "A chunk that is not closed, or whose close cannot be located with "
        "certainty -> no output"
    )

    def test_the_docstring_no_longer_says_a_case_makes_the_chunk_undecidable(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_skip_substitution")
                self.assertIsNotNone(doc, "no _skip_substitution method in _Parser")
                self.assertNotIn(self.STALE_SENTENCE, doc)

    def test_the_docstring_says_a_case_statement_inside_the_chunk_is_read(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            for marker in self.READ_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_docstring_names_each_form_that_stays_undecidable(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            for marker in self.UNDECIDABLE_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)
            with self.subTest(copy=plugin, stale=self.STALE_BRACE_FORM_SENTENCE):
                self.assertNotIn(self.STALE_BRACE_FORM_SENTENCE, doc)

    def test_the_docstring_describes_the_brace_form_of_a_case_statement(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            self.assertNotEqual(doc, "")
            for part, markers in self.BRACE_FORM_MARKERS.items():
                for marker in markers:
                    with self.subTest(copy=plugin, part=part, marker=marker):
                        self.assertIn(marker, doc)

    def test_the_module_docstring_keeps_the_sentence_about_an_unlocatable_close(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertIn(self.MODULE_SENTENCE, module_docstring(path))

    # codex-guard-case-reading-fixes (FR7): the docstring states the four rules
    # of the new reading, and the keyword decision states the pair-stripped rule.
    RULE_MARKERS = {
        "command position state": (
            "carries state of constant size: whether the next word is at a command position",
            "whether a `[[` read at a command position is still open in it",
            "The characters of the previous word are never looked at backward",
        ),
        "case open and close rule": (
            "`case` opens a statement only as a standalone word at a command position",
            "In an item body `esac` closes a statement only as a standalone word at a command position",
            "A `case` or an `esac` at an argument position, one after a reserved word or `!` that is itself at an argument position included, is an ordinary word and opens or closes nothing",
        ),
        "pattern comment rule": (
            "A `#` directly after the `)` that closes an item's pattern (no blank in between) starts a comment that runs to the end of the line",
            "after the newline the item body starts at a command position",
        ),
        "continuation rule": (
            "A continuation pair is a backslash directly followed by a newline",
            "`case`, `in` and `esac` are decided on the characters with the pairs left out",
            "a sequence that does not spell the keyword once the pairs are out is not a keyword",
            "a pair inside a word never splits it",
            "a failed match is not retried from inside the same word",
            "and so is every other word whose identity changes the reading",
            "the closing words `fi`, `done`, `}` and `]]`, `[[`, `function` and the head words `for`, `select`, `coproc` and `repeat`",
        ),
        "compound closing rule": (
            "A closing inside a word and a compound-command closing are told apart",
            "A closing inside a word goes on inside the word",
            "the `)` that closes a `(` that was not read at a command position (a zsh glob qualifier as in `x(N)`, `<(` and `>(`)",
            "the `)` that closes a `(` read at a command position (a subshell, and the `((` ... `))` arithmetic command)",
            "a standalone `]]` while a `[[` read as a standalone word at a command position is open in the same list",
            "the `esac` that closes a case statement, whether it is read in an item body or at a pattern position",
            "a standalone, unquoted `fi`, `done` or `}` read at a command position",
            "A `]]` with no open `[[`, and a `fi`, `done` or `}` at an argument position, are ordinary words",
            "the word after the target is not at a command position",
            "the `[[` is tracked only to recognise its `]]`",
        ),
        "function head rule": (
            "that `)` ends a function head and the next word is at a command position",
            "a `(` that does not form an empty `()` is read as any other `(`",
            "A standalone, unquoted, unescaped `function` read at a command position starts a head",
            "an ordinary word that is never read as a keyword or reserved word",
            "an empty `()` directly after the name or after blanks belongs to the head",
            "Multi-name zsh definitions and function-name validity are not considered",
        ),
        "loop and coproc head rule": (
            "starts only from a standalone word that is unquoted, unescaped, read at a command position",
            "the same word at an argument position, quoted or escaped starts no head",
            "After `for` or `select` the next word is the name, an ordinary word that is never a keyword",
            "A `((` directly after `for` (blanks allowed) is read as opened at a command position",
            "a `(` directly after the name (blanks allowed) opens a word list",
            "no word inside it is at a command position",
            "After `coproc` the next word is at a command position",
            "with the rule on, the word after it is at a command position as well",
            "After the zsh `repeat` the next word, the count, is an ordinary word that is never read as a keyword",
        ),
        "head lifetime rule": (
            "A head state lasts only until its head completes or the next character rules it out",
            "A separator (`;`, `&`, `|`, a newline) or the end of the list ends any head state still pending",
        ),
    }
    # The sentence of the earlier reading that said every list went on inside
    # a word after any nested context closed (FR7 asks for it to be replaced).
    STALE_CLOSING_SENTENCE = (
        "A list that goes on after a nested context closes (a substitution, a "
        "subshell, quotes, a case statement) goes on inside a word, so its "
        "state is false."
    )

    # codex-guard-delim-subst-undecidable (FR6): the docstring describes the three
    # readings added for a heredoc operator, an arithmetic command and a
    # parenthesis in a word. The sentence "a heredoc anywhere in the chunk (item
    # bodies included)" of UNDECIDABLE_MARKERS stays, for the heredocs inside a case
    # statement.
    NEW_READING_MARKERS = {
        "heredoc operator rule": (
            "Outside a case statement an unquoted `<<` that is not `<<<` does not make the chunk undecidable",
            "the word after the operator (the `<<-` form included) is read as an ordinary word at an argument position",
            "While any open list is marked, an unquoted newline in any context (a word parenthesis included, quoted text excluded) makes the chunk undecidable",
            "the mark is dropped and the list closes where it would without the operator",
            "no `<<` looks ahead, so the reading stays linear",
            "A `<<` inside a case statement (its subject, its patterns, its item bodies and every list nested in them) stays undecidable",
            "a heredoc anywhere in the chunk (item bodies included) once a case statement is open",
        ),
        "arithmetic command rule": (
            "A `((` read at a command position (a `((` directly after `for` included; two parentheses with a blank between them are not this form) opens an arithmetic command",
            "In it a `<<` is a left shift and no heredoc",
            "A `)` that closes the command must be directly followed by a second `)`",
            "everything read since the `((` is dropped and the reader goes back to that `((` and reads it as two nested subshells",
            "A `((` is read again at most once",
            "the sum may not exceed `ARITHMETIC_REREAD_FACTOR` (8) times the length of the string",
            "nothing recurses",
        ),
        "word parenthesis rule": (
            "opens a word parenthesis, the context W",
            "a `(` directly after `<`, `>` or `=` (`<(`, `>(` and `=(`)",
            "A `#` is a word character and starts no comment",
            "`;`, `&`, `|` and a newline are word characters, neither separators nor undecidable",
            "When the outermost W closes, the list that holds it goes on in the state it had before the `(`, inside the same word",
        ),
    }

    def test_the_docstring_states_the_three_readings(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            for rule, markers in self.NEW_READING_MARKERS.items():
                for marker in markers:
                    with self.subTest(copy=plugin, rule=rule, marker=marker):
                        self.assertIn(marker, doc)

    def test_the_docstring_does_not_say_a_heredoc_is_always_undecidable(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            for stale in (
                "a heredoc is always undecidable",
                "every heredoc is undecidable",
                "a heredoc in a substitution is undecidable",
                "a heredoc anywhere in the chunk (item bodies included), an unmatched",
            ):
                with self.subTest(copy=plugin, stale=stale):
                    self.assertNotIn(stale, doc)

    def test_the_docstring_no_longer_says_every_closing_goes_on_inside_a_word(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_skip_substitution") or ""
                self.assertNotEqual(doc, "")
                self.assertNotIn(self.STALE_CLOSING_SENTENCE, doc)

    def test_the_docstring_states_the_four_rules_of_the_reading(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            for rule, markers in self.RULE_MARKERS.items():
                for marker in markers:
                    with self.subTest(copy=plugin, rule=rule, marker=marker):
                        self.assertIn(marker, doc)

    # codex-guard-for-wordlist-glob-qualifier (FR1, FR2): the docstring says
    # where a `#` starts a comment in the word list of a zsh `for`: only in the
    # outermost entry; in a nested entry (a glob qualifier as in `*(#qN)`) a
    # `#` is a word character.
    WORD_LIST_HASH_MARKERS = (
        "In the word list a `#` starts a comment only in the outermost entry",
        "In a nested entry every `#` is a word character",
    )
    # The sentence of the earlier reading that gave every entry of the word
    # list the comment start of a command list.
    STALE_WORD_LIST_HASH_SENTENCE = (
        "A `#` whose previous character is a space, a tab, a newline, `;`, "
        "`&`, `|` or `(` starts a comment, the same start condition as in a "
        "command list."
    )

    def test_the_docstring_states_where_a_hash_starts_a_comment_in_a_for_word_list(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            self.assertNotEqual(doc, "")
            for marker in self.WORD_LIST_HASH_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)
            with self.subTest(copy=plugin, stale=True):
                self.assertNotIn(self.STALE_WORD_LIST_HASH_SENTENCE, doc)

    # codex-guard-procsub-in-wordlist (FR4): the docstring says that an
    # unquoted, unescaped `<(`, `>(` or `=(` at the start of a word of the
    # outermost entry of the word list opens a command list p, that the `)` of
    # that p is a closing inside a word, and how the start of a word is decided
    # (an escaped space is a word character, a continuation pair separates no
    # word). Every other `(` of the word list stays a nested entry.
    WORD_LIST_PROCESS_SUBSTITUTION_MARKERS = (
        "an unquoted, unescaped `<(`, `>(` or `=(` there opens a command list p instead of a nested entry",
        "The `)` that closes that p is a closing inside a word",
        "The start of a word is a state kept while reading, moved on before each character is read",
        "The only look at the characters behind is the comment-start decision above, and it leaves this state as it is",
        "An escaped character (an escaped space included) is a word character",
        "A continuation pair neither starts a word nor separates words, so it keeps the state",
        "in the middle of a word or inside a nested entry is read as any other `(` of w",
    )

    def test_the_docstring_states_how_a_process_substitution_in_a_for_word_list_is_read(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            self.assertNotEqual(doc, "")
            for marker in self.WORD_LIST_PROCESS_SUBSTITUTION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    # codex-guard-escaped-hash-brace-case-heredoc (FR7, task0001): the sentence
    # of the earlier reading that said the start of a word is never looked up
    # backward stays absent; the start of a word is still a state kept while
    # reading, and the comment-start decision is the one look at the characters
    # behind.
    STALE_WORD_START_SENTENCE = "never looked up backward"

    def test_the_docstring_no_longer_says_the_start_of_a_word_is_never_looked_up_backward(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_skip_substitution") or ""
                self.assertNotEqual(doc, "")
                self.assertNotIn(self.STALE_WORD_START_SENTENCE, doc)

    # codex-guard-escaped-hash-brace-case-heredoc (FR1, FR7, task0001): the
    # docstring describes the comment-start decision of the substitution
    # reader: the effective previous character with the continuation pairs left
    # out, escaped characters as word characters, the readings that stay after
    # `)`, `<` and `>`, and the bounded look that is the only place where the
    # characters in front of a `#` are looked at.
    HASH_DECISION_MARKERS = (
        "a `#` starts a comment exactly when its effective previous character is a space, a tab, a newline, `;`, `&`, `|` or `(`, and that character is not escaped",
        "Otherwise the `#` is a word character",
        "The effective previous character is the character right before the `#` once every continuation pair directly in front of the `#` is left out, a run of several pairs included",
        "A character is escaped when it is the second character of a backslash pair, that is, when the run of backslashes directly in front of it has odd length",
        "A `#` whose effective previous character is `)`, `<`, `>` or any other character stays a word character",
        "in phase 7 a `)` that closes the pattern still lets the `#` start a comment",
        "A `#` never starts a comment in a nested entry of w, a word parenthesis W, double quotes, backticks, `${ ... }` and the arithmetic contexts",
        "This bounded look is the only place where the characters in front of a `#` are looked at",
    )

    def test_the_docstring_describes_the_comment_start_decision(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            self.assertNotEqual(doc, "")
            for marker in self.HASH_DECISION_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_comment_start_decision_sits_between_rule_3_and_rule_4(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_skip_substitution") or ""
                rule_3 = doc.find("Comment after a pattern (rule 3)")
                decision = doc.find(self.HASH_DECISION_MARKERS[0])
                rule_4 = doc.find("Continuation pairs (rule 4)")
                self.assertTrue(0 <= rule_3 < decision < rule_4, (rule_3, decision, rule_4))

    # codex-guard-escaped-hash-brace-case-heredoc (FR7, FR8, task0003): the
    # decision reads the one comment-end position kept while reading, and the
    # newline that ends a comment is never part of a continuation pair. The two
    # sentences of the earlier reading that said the decision keeps no state
    # stay absent from the skip's docstring, and "It keeps no state" from the
    # helper's as well.
    COMMENT_END_MARKERS = (
        "The decision reads one value kept while reading, the comment-end position",
        "the index of the newline that ended the last comment the reader read",
        "Every branch that reads a comment records it in the same step",
        "The newline that ends a comment is never part of a continuation pair",
        "a newline at the comment-end position is an unescaped newline in the look, whatever run of backslashes stands in front of it",
        "The re-read also restores the brace-form state",
        "The comment-end position of the `#` decision goes back to its value at the `((` as well",
    )
    STALE_NO_STATE_SENTENCES = (
        "It keeps no state",
        "The decision carries no state through the reading",
    )

    def test_the_docstring_states_the_comment_end_position_and_the_newline_that_ends_a_comment(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_skip_substitution") or ""
            self.assertNotEqual(doc, "")
            for marker in self.COMMENT_END_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_docstring_no_longer_says_the_comment_start_decision_keeps_no_state(self):
        for plugin, path in HOOK_PATHS.items():
            for method in ("_skip_substitution", "_hash_starts_comment"):
                doc = parser_docstring(path, method) or ""
                self.assertNotEqual(doc, "")
                for stale in self.STALE_NO_STATE_SENTENCES:
                    with self.subTest(copy=plugin, method=method, stale=stale):
                        self.assertNotIn(stale, doc)

    def test_the_comment_start_helper_states_that_the_comment_end_newline_is_no_continuation_pair(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_hash_starts_comment") or ""
            self.assertNotEqual(doc, "")
            for marker in (
                "The newline that ends a comment is never part of a continuation pair",
                "the comment-end position",
            ):
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_keyword_decision_states_the_pair_stripped_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_keyword_end") or ""
            for marker in (
                "continuation pairs",
                "the pair-stripped rule",
                "a standalone word",
            ):
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_word_reader_states_that_every_word_is_decided_on_the_pair_stripped_sequence(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path, "_read_command_word") or ""
            for marker in (
                "Every word is decided by `_keyword_end`, on the characters with the continuation pairs left out",
                "a quoted or escaped one",
            ):
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_backward_look_at_the_previous_word_for_a_command_position_is_gone(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                methods = parser_methods(path)
                self.assertNotIn("_at_command_position", methods)


class TestDelimiterSubstitutionDocumentation(unittest.TestCase):
    """The four docstrings that touch the unquoted `$(` of a delimiter's
    `${ ... }` range say how it is read (FR5): by the same case-aware skip that
    reads a substitution inside double quotes. The sentences that limited the
    shared reader's start to a quote or a backslash, and the substitution skip
    to the inside of double quotes, are gone."""

    STALE_READER_SENTENCE = (
        "the character at `start` is a backslash, a single quote or a double quote"
    )
    STALE_SKIP_SENTENCE = "(`$(`, `$((` or a backtick) inside double quotes"
    # The sentence every one of the four docstrings carries.
    COMMON_MARKER = "unquoted `$(` inside a delimiter's `${ ... }` range"
    # What each docstring says about the reading, in its own words.
    READING_MARKERS = {
        None: "is skipped by the same case-aware skip",
        "_remove_range_quotes": "is read by the shared reader `_read_quoted_unit`",
        "_read_quoted_unit": "is skipped with `_skip_substitution`",
        "_skip_substitution": "is reached from `_read_quoted_unit`",
    }

    def docstring_of(self, path, method):
        if method is None:
            return module_docstring(path)
        return parser_docstring(path, method) or ""

    def test_the_shared_reader_docstring_no_longer_limits_its_start_to_a_quote_or_a_backslash(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_read_quoted_unit")
                self.assertIsNotNone(doc, "no _read_quoted_unit method in _Parser")
                self.assertNotIn(self.STALE_READER_SENTENCE, doc)

    def test_the_substitution_skip_docstring_no_longer_limits_it_to_double_quotes(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                doc = parser_docstring(path, "_skip_substitution")
                self.assertIsNotNone(doc, "no _skip_substitution method in _Parser")
                self.assertNotIn(self.STALE_SKIP_SENTENCE, doc)

    def test_each_docstring_names_how_an_unquoted_dollar_paren_in_a_delimiter_brace_range_is_read(self):
        for plugin, path in HOOK_PATHS.items():
            for method, reading in self.READING_MARKERS.items():
                doc = self.docstring_of(path, method)
                for marker in (self.COMMON_MARKER, reading):
                    with self.subTest(copy=plugin, docstring=method or "module", marker=marker):
                        self.assertIn(marker, doc)


class TestDelimiterReadingDocumentation(unittest.TestCase):
    """codex-guard-delim-brace-quote-per-shell (task0001 AC-7, NFR4): the module
    docstring states what decides the delimiter reading and what the readings
    are, and the docstrings of the parser and of the module-level `parse` state
    the delimiter rule and the combination."""

    MODULE_MARKERS = {
        "the delimiter reading per holder": (
            "The delimiter reading is decided by the shell that directly holds the string",
            "bash reads the bash form only",
            "zsh and dash read the quote-removal form only",
            "sh and ksh read both",
            "the hook command itself reads the quote-removal form only",
        ),
        "the condition of the bash form": (
            "when the delimiter word holds at least one `${ ... }` range and no quote unit "
            "outside its ranges",
            "a backslash-newline pair is no unit",
        ),
        "the dual reading denies when either reading denies": (
            "the dual reading denies when either reading denies",
            "no outcome of one reading suppresses the commands of the other",
        ),
        "the string counts once": (
            "A string read under both readings counts once, at its length, toward NESTED_READ_LIMIT",
            "a nested string counts each time the walk reaches it",
        ),
    }
    PARSER_MARKERS = (
        "delimiter rule",
        "bash form",
        "quote removal",
    )
    PARSE_MARKERS = (
        "the delimiter reading",
        "reading A",
        "reading B",
        "skipped only when every parser built for reading A",
    )

    def test_the_module_docstring_states_the_delimiter_reading(self):
        for plugin, path in HOOK_PATHS.items():
            doc = module_docstring(path)
            for statement, markers in self.MODULE_MARKERS.items():
                for marker in markers:
                    with self.subTest(copy=plugin, statement=statement, marker=marker):
                        self.assertIn(marker, doc)

    def test_the_module_docstring_no_longer_reads_the_range_as_always_quote_removed(self):
        stale = "a reading of its own for `${` and for `$'` and `$\"`, and only there. An unquoted `${` in it starts a range that ends at its close, and the range is quote-removed as the close is searched, in one forward scan, before the delimiter is registered."
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertNotIn(stale, module_docstring(path))

    def test_the_parser_description_states_the_delimiter_rule(self):
        for plugin, path in HOOK_PATHS.items():
            doc = parser_docstring(path)
            for marker in self.PARSER_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)

    def test_the_description_of_parse_states_the_readings_and_their_combination(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            parse = next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "parse"
            )
            doc = " ".join((ast.get_docstring(parse) or "").split())
            for marker in self.PARSE_MARKERS:
                with self.subTest(copy=plugin, marker=marker):
                    self.assertIn(marker, doc)


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


class TestUnquotedBackquoteClosing(HookCopiesMixin, unittest.TestCase):
    """Where a backquote span read outside quotes ends. The span closes at the
    first backquote that is not part of a backslash pair (a backslash and the
    character after it, whatever it is); with none left the span is unclosed
    and the input is undecidable, so the hook says nothing.

    The probe sits in the argument list of a zsh anonymous function whose body
    holds an explicit `-i`. A dynamic chunk among the arguments of `python3`
    itself is fail-open by design, so the probe stays out of them: where the
    span ends then decides between deny (the `)` after it closes the argument
    list and the body is judged) and silent (the span is unclosed).
    """

    BODY = "setopt nonomatch nobareglobqual; function { python3 -i; } foo("
    UNDECIDABLE_REFERENCE = "python3 -i `echo"  # a `quote` undecidable command
    DEEP = TestMalformedAndDeepInput.RESERVED_RUN
    TIMEOUT = TestMalformedAndDeepInput.TIMEOUT

    def anonymous_function_with(self, span, tail=")"):
        """A `zsh -c` command that runs the anonymous function with `span` as
        the start of its argument list, closed by `tail`."""
        return "zsh -c " + sq(self.BODY + span + tail)

    def assert_verdict(self, command, expected):
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin, command=command[:200]):
                result = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual(verdict_of(result), expected)

    def assert_unclosed(self, command):
        """The hook gives `command` the output it gives any `quote` undecidable
        command: exit status 0, nothing on standard output or standard error."""
        for plugin, path in self.for_each_copy():
            with self.subTest(copy=plugin, command=command[:200]):
                reference = run_hook(path, payload_for(self.UNDECIDABLE_REFERENCE))
                self.assertEqual(reference, (0, "", ""))
                result = run_hook(path, payload_for(command), timeout=self.TIMEOUT)
                self.assertEqual(result, reference)

    def test_a_backquote_after_an_even_run_of_backslashes_closes_the_span(self):
        for run in (0, 2, 4, 6):
            with self.subTest(run=run):
                span = "`x" + "\\" * run + "`"
                self.assert_verdict(self.anonymous_function_with(span), "deny")

    def test_a_backquote_after_an_odd_run_of_backslashes_does_not_close_the_span(self):
        for run in (1, 3, 5):
            with self.subTest(run=run):
                span = "`x" + "\\" * run + "`"
                self.assert_unclosed(self.anonymous_function_with(span))

    def test_a_backquote_after_an_odd_run_is_passed_over_and_a_later_one_closes(self):
        for run in (1, 3, 5):
            with self.subTest(run=run):
                span = "`x" + "\\" * run + "`y`"
                self.assert_verdict(self.anonymous_function_with(span), "deny")

    def test_the_first_backquote_after_an_even_run_closes_and_a_later_one_opens_a_new_span(self):
        for run in (0, 2, 4):
            with self.subTest(run=run):
                span = "`x" + "\\" * run + "`y`"
                self.assert_unclosed(self.anonymous_function_with(span))

    def test_a_span_whose_later_backquotes_are_all_escaped_is_unclosed(self):
        for span in ("`x\\`", "`x\\`y\\`", "`\\`\\`\\`", "`x\\\\\\`"):
            with self.subTest(span=span):
                self.assert_unclosed(self.anonymous_function_with(span))

    def test_a_span_that_runs_into_a_lone_backslash_at_the_end_of_the_text_is_unclosed(self):
        for span in ("`x\\", "`x\\\\\\", "`\\"):
            with self.subTest(span=span):
                self.assert_unclosed(self.anonymous_function_with(span, tail=""))

    def test_a_backslash_pair_hides_the_character_after_it_whatever_it_is(self):
        for span in ("`x\\)y`", "`x\\ y`", "`x\\\\y`", "`x\\'y`", '`x\\"y`'):
            with self.subTest(span=span):
                self.assert_verdict(self.anonymous_function_with(span), "deny")

    def test_a_backquote_span_outside_an_argument_list_ends_by_the_same_rule(self):
        self.assert_verdict("echo `a\\`b`; python3 -i", "deny")
        self.assert_unclosed("echo `a\\`; python3 -i")

    def test_a_deep_span_of_escaped_backquotes_is_unclosed(self):
        span = "`" + "\\`" * self.DEEP
        self.assert_unclosed(self.anonymous_function_with(span))

    def test_a_deep_span_of_backslash_pairs_without_a_closing_backquote_is_unclosed(self):
        span = "`" + "\\\\" * self.DEEP
        self.assert_unclosed(self.anonymous_function_with(span))

    def test_a_deep_span_of_backslash_pairs_ending_in_a_lone_backslash_is_unclosed(self):
        span = "`" + "\\\\" * self.DEEP + "\\"
        self.assert_unclosed(self.anonymous_function_with(span, tail=""))

    def test_a_deep_span_of_backslash_pairs_closed_by_a_backquote_is_closed(self):
        span = "`" + "\\\\" * self.DEEP + "`"
        self.assert_verdict(self.anonymous_function_with(span), "deny")


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

    def test_the_test_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        stdlib = stdlib_module_names()
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(node.level, "a relative import")
                names = [node.module or ""]
            for name in names:
                with self.subTest(module=name):
                    self.assertIn(name.split(".")[0], stdlib)

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

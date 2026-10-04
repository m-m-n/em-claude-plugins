#!/usr/bin/env python3
"""Codex PreToolUse(Bash) guard against launching an interpreter or shell in
interactive mode.

Codex gives a Bash call a pseudo terminal. A `python3 -i` started there keeps
waiting for input after the terminal is gone, and it spins as an orphan
process. The guard reads the command string of one Bash call and denies the
launches that would open a REPL.

Decision flow:

  1. Read stdin, parse it as one JSON object. Any failure -> no output.
  2. Take tool_input.command. Absent or not a string -> no output.
  3. Remove heredoc bodies and split the command into simple commands at
     `;` `&&` `||` `|` `&` and newlines. Quoted text and comments are not
     read as commands. An unbalanced quote or an unterminated heredoc ->
     no output.
  4. For each simple command: drop redirections, skip leading variable
     assignments and the option-less wrappers (`env` `nohup` `nice` `exec`
     `command` `time` `sudo` `timeout DURATION`), and match the basename of
     the command word against the interpreter families below. A wrapper
     that carries an option (`env -i`, `nice -n 5`) -> the command is not
     judged.
  5. A shell started with `-c <literal>` has that literal judged once, the
     same way. A literal inside it is not judged.
  6. Deny a launch that carries `-i` before the first operand (python, node,
     the shells and lua), and a launch that gives the interpreter no program
     to run: no operand, no code option, standard input neither redirected
     nor the right side of a pipe, and no informational option such as
     `--version`.
  7. Anything undecidable or unexpected -> no output.

Everything the guard cannot positively identify passes. A misreading costs a
missed detection, never a stalled review.

The guard uses only the standard library and touches no file, network
connection or child process. The decision depends on the command string
alone, never on the working directory or the environment.

Output: one deny object on stdout, or nothing. Exit status 0 either way.
"""

import json
import sys

HOOK_EVENT_NAME = "PreToolUse"

# Wrappers that run the next word as the command. Only option-free use is
# followed; a wrapper carrying an option makes the command undecidable.
WRAPPERS = ("env", "nohup", "nice", "exec", "command", "time", "sudo")

# Informational options that never open a REPL, in every family.
INFO_LONG = ("--version", "--help")
INFO_LETTERS = "Vh"


class _Undecidable(Exception):
    pass


class _Family:
    """One interpreter family.

    names              known command names (FR8 adds a digits-and-dots suffix)
    deny_i             `-i` opens a REPL, so a launch carrying it is denied
    interactive_long   long options that count as `-i`
    code_letters       short options that pass the program as their value
    code_long          long options that pass the program as their value
    value_letters      short options that take a value (the rest of the
                       bundle, or the next word when last)
    attached_letters   short options whose rest of the bundle is a value, and
                       which never take the next word
    value_long         long options that take the next word as their value
    info_letters       extra informational short options
    info_long          extra informational long options
    """

    def __init__(
        self,
        name,
        names,
        deny_i=False,
        interactive_long=(),
        code_letters="",
        code_long=(),
        value_letters="",
        attached_letters="",
        value_long=(),
        info_letters="",
        info_long=(),
        is_shell=False,
    ):
        self.name = name
        self.names = names
        self.deny_i = deny_i
        self.interactive_long = interactive_long
        self.code_letters = code_letters
        self.code_long = code_long
        self.value_letters = value_letters
        self.attached_letters = attached_letters
        self.value_long = value_long
        self.info_letters = info_letters
        self.info_long = info_long
        self.is_shell = is_shell


FAMILIES = (
    _Family("python", ("python",), deny_i=True, code_letters="cm", value_letters="WX",
            value_long=("--check-hash-based-pycs",)),
    _Family("node", ("node",), deny_i=True, interactive_long=("--interactive",),
            code_letters="ep", code_long=("--eval", "--print"), value_letters="rC",
            value_long=("--require", "--import", "--loader", "--experimental-loader", "--conditions"),
            info_letters="v", info_long=("--test", "--check", "--run")),
    _Family("shell", ("bash", "sh", "zsh", "dash", "ksh"), deny_i=True, code_letters="c",
            value_letters="oO", value_long=("--rcfile", "--init-file"), is_shell=True),
    _Family("lua", ("lua",), deny_i=True, code_letters="cme", value_letters="l"),
    _Family("ruby", ("ruby",), code_letters="e", value_letters="Ir", attached_letters="i0xKFW"),
    _Family("perl", ("perl",), code_letters="eE", value_letters="IMm", attached_letters="i0xFCdD",
            info_letters="v"),
    _Family("deno", ("deno",), code_letters="cme"),
    _Family("irb", ("irb",), code_letters="cme"),
    _Family("ipython", ("ipython",), code_letters="cme"),
)

DIGITS = "0123456789"


class _Word:
    __slots__ = ("text", "dynamic")

    def __init__(self, text, dynamic):
        self.text = text
        # True when the word holds an expansion, so its value is unknown.
        self.dynamic = dynamic


class _Command:
    __slots__ = ("words", "stdin", "after_pipe")

    def __init__(self, words, stdin, after_pipe):
        self.words = words
        # Standard input is redirected with `<`, `<<`, `<<<` or `<&`.
        self.stdin = stdin
        # The command sits on the right side of a pipe.
        self.after_pipe = after_pipe


class _Parser:
    """Split a command string into simple commands.

    Quotes, backslashes, comments, redirections and heredocs are read the way
    a shell reads them. Expansions are not evaluated: a word that holds one
    is marked dynamic. Raises _Undecidable on an unbalanced quote or an
    unterminated heredoc.
    """

    def __init__(self, command):
        self.s = command
        self.n = len(command)
        self.i = 0
        self.commands = []
        self.words = []
        self.stdin = False
        self.pipe_pending = False
        # Set between a redirection operator and its target word:
        # (is_heredoc, strips_leading_tabs).
        self.redirect = None
        self.heredocs = []
        self._reset_word()

    def _reset_word(self):
        self.buf = []
        self.started = False
        self.dynamic = False
        # Every character so far is an unquoted digit (a file descriptor).
        self.digits = True

    def _put(self, text, quoted=False, dynamic=False):
        self.buf.append(text)
        self.started = True
        if dynamic:
            self.dynamic = True
        if quoted or not all(ch in DIGITS for ch in text):
            self.digits = False

    def _finish_word(self):
        if not self.started:
            return
        text = "".join(self.buf)
        dynamic = self.dynamic
        self._reset_word()
        if self.redirect is not None:
            is_heredoc, strips_tabs = self.redirect
            self.redirect = None
            if is_heredoc:
                if not text:
                    raise _Undecidable("heredoc delimiter")
                self.heredocs.append((text, strips_tabs))
            return
        self.words.append(_Word(text, dynamic))

    def _separator(self, sep):
        self._finish_word()
        self.redirect = None
        if self.words:
            self.commands.append(_Command(self.words, self.stdin, self.pipe_pending))
            self.pipe_pending = False
        self.words = []
        self.stdin = False
        if sep in ("|", "|&"):
            self.pipe_pending = True
        elif sep != "(":
            self.pipe_pending = False

    def _read_heredocs(self):
        s = self.s
        for delim, strips_tabs in self.heredocs:
            while True:
                nl = s.find("\n", self.i)
                end = nl if nl != -1 else self.n
                line = s[self.i:end]
                if (line.lstrip("\t") if strips_tabs else line) == delim:
                    self.i = end + 1 if nl != -1 else self.n
                    break
                if nl == -1:
                    raise _Undecidable("heredoc body")
                self.i = end + 1
        self.heredocs = []

    def _skip_parens(self, start):
        """Return the index just after the `)` that closes the `(` at
        `start`, skipping quoted text."""
        s = self.s
        depth = 0
        j = start
        while j < self.n:
            ch = s[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "'":
                j = s.find("'", j + 1)
                if j == -1:
                    raise _Undecidable("quote")
            elif ch == '"':
                j += 1
                while j < self.n and s[j] != '"':
                    j += 2 if s[j] == "\\" else 1
                if j >= self.n:
                    raise _Undecidable("quote")
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise _Undecidable("parenthesis")

    def _double_quoted(self):
        s = self.s
        j = self.i + 1
        out = []
        dynamic = False
        while j < self.n:
            ch = s[j]
            if ch == '"':
                self._put("".join(out), quoted=True, dynamic=dynamic)
                self.i = j + 1
                return
            if ch == "\\" and j + 1 < self.n:
                nxt = s[j + 1]
                if nxt in '"\\$`':
                    out.append(nxt)
                elif nxt != "\n":
                    out.append("\\" + nxt)
                j += 2
                continue
            if ch in "$`":
                dynamic = True
            out.append(ch)
            j += 1
        raise _Undecidable("quote")

    def _dollar(self):
        s, i = self.s, self.i
        nxt = s[i + 1] if i + 1 < self.n else ""
        if nxt == "(":
            end = self._skip_parens(i + 1)
            self._put(s[i:end], quoted=True, dynamic=True)
            self.i = end
        elif nxt == "{":
            end = s.find("}", i + 2)
            if end == -1:
                raise _Undecidable("brace")
            self._put(s[i:end + 1], quoted=True, dynamic=True)
            self.i = end + 1
        elif nxt == "'":
            j = i + 2
            while j < self.n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            if j >= self.n:
                raise _Undecidable("quote")
            self._put(s[i:j + 1], quoted=True, dynamic=True)
            self.i = j + 1
        elif nxt == '"':
            self.i += 1
        else:
            self._put("$", dynamic=True)
            self.i += 1

    def _redirection(self):
        s, i = self.s, self.i
        ch = s[i]
        if i + 1 < self.n and s[i + 1] == "(":
            # Process substitution: its value is unknown.
            end = self._skip_parens(i + 1)
            self._put(s[i:end], quoted=True, dynamic=True)
            self.i = end
            return
        fd = None
        if self.started and self.digits and self.buf:
            fd = int("".join(self.buf))
            self._reset_word()
        else:
            self._finish_word()
        if ch == "<":
            for op in ("<<<", "<<-", "<<", "<&", "<>"):
                if s.startswith(op, i):
                    break
            else:
                op = "<"
        else:
            for op in (">>", ">&", ">|"):
                if s.startswith(op, i):
                    break
            else:
                op = ">"
        self.i = i + len(op)
        if fd == 0 or (fd is None and ch == "<"):
            self.stdin = True
        self.redirect = (op in ("<<", "<<-"), op == "<<-")

    def parse(self):
        s = self.s
        while self.i < self.n:
            i = self.i
            ch = s[i]
            if ch in " \t":
                self._finish_word()
                self.i += 1
            elif ch == "\n":
                self.i += 1
                self._separator("\n")
                if self.heredocs:
                    self._read_heredocs()
            elif ch == "#" and not self.started:
                end = s.find("\n", i)
                self.i = self.n if end == -1 else end
            elif ch == "\\":
                if i + 1 >= self.n:
                    raise _Undecidable("trailing backslash")
                self.i += 2
                if s[i + 1] != "\n":
                    self._put(s[i + 1], quoted=True)
            elif ch == "'":
                end = s.find("'", i + 1)
                if end == -1:
                    raise _Undecidable("quote")
                self._put(s[i + 1:end], quoted=True)
                self.i = end + 1
            elif ch == '"':
                self._double_quoted()
            elif ch == "$":
                self._dollar()
            elif ch == "`":
                end = s.find("`", i + 1)
                if end == -1:
                    raise _Undecidable("quote")
                self._put(s[i:end + 1], quoted=True, dynamic=True)
                self.i = end + 1
            elif ch == ";":
                self.i += 1
                self._separator(";")
            elif ch == "&":
                if s.startswith("&>", i):
                    self._finish_word()
                    self.i += 3 if s.startswith("&>>", i) else 2
                    self.redirect = (False, False)
                elif s.startswith("&&", i):
                    self.i += 2
                    self._separator("&&")
                else:
                    self.i += 1
                    self._separator("&")
            elif ch == "|":
                if s.startswith("||", i):
                    self.i += 2
                    self._separator("||")
                elif s.startswith("|&", i):
                    self.i += 2
                    self._separator("|&")
                else:
                    self.i += 1
                    self._separator("|")
            elif ch == "(":
                self.i += 1
                self._separator("(")
            elif ch == ")":
                self.i += 1
                self._separator(")")
            elif ch in "<>":
                self._redirection()
            else:
                self._put(ch)
                self.i += 1
        self._separator("\n")
        if self.heredocs:
            raise _Undecidable("heredoc")
        return self.commands


def parse(command):
    return _Parser(command).parse()


def _basename(text):
    return text.rsplit("/", 1)[-1]


def _is_assignment(word):
    name, eq, _ = word.text.partition("=")
    return bool(eq) and name.isidentifier()


def _family_of(name):
    """Return the family whose known name matches a command word's basename
    (FR8: the name itself, or the name plus digits and dots), or None."""
    for family in FAMILIES:
        for known in family.names:
            if name == known:
                return family
            if name.startswith(known):
                suffix = name[len(known):]
                if all(ch in DIGITS + "." for ch in suffix):
                    return family
    return None


def _command_index(words):
    """Return the index of the command word after assignments and wrappers,
    or None when the command is not judged."""
    i = 0
    n = len(words)
    while True:
        while i < n and _is_assignment(words[i]):
            i += 1
        if i >= n or words[i].dynamic:
            return None
        base = _basename(words[i].text)
        if base in WRAPPERS:
            i += 1
            if i < n and words[i].text.startswith("-"):
                return None
            continue
        if base == "timeout":
            i += 1
            if i < n and words[i].text.startswith("-"):
                return None
            i += 1
            continue
        return i


class _Options:
    """What the options of one launch say."""

    def __init__(self):
        self.interactive = False
        self.operand = False
        self.code = False
        self.informational = False
        self.code_string = None


def _read_options(family, args):
    """Read options left to right. Reading stops at the first operand and at
    the value of a code-passing option."""
    result = _Options()
    k = 0
    n = len(args)
    while k < n:
        word = args[k]
        text = word.text
        if word.dynamic or text == "-" or not text.startswith("-"):
            result.operand = True
            return result
        if text == "--":
            result.operand = k + 1 < n
            return result
        if text.startswith("--"):
            name, eq, _ = text.partition("=")
            if name in family.interactive_long:
                result.interactive = True
            if name in INFO_LONG or name in family.info_long:
                result.informational = True
            if name in family.code_long:
                result.code = True
                return result
            if name in family.value_long and not eq:
                k += 1
            k += 1
            continue
        letters = text[1:]
        for j, letter in enumerate(letters):
            rest = letters[j + 1:]
            if letter in family.code_letters:
                result.code = True
                if family.is_shell and not rest and k + 1 < n and not args[k + 1].dynamic:
                    result.code_string = args[k + 1].text
                return result
            if letter == "i" and family.deny_i:
                result.interactive = True
            elif letter in family.value_letters:
                if not rest:
                    k += 1
                break
            elif letter in family.attached_letters:
                break
            elif letter in INFO_LETTERS or letter in family.info_letters:
                result.informational = True
        k += 1
    return result


def _judge(words, connected):
    """Judge one simple command. Return (kind, inner): kind is "interactive",
    "noprogram" or None; inner is a shell `-c` literal to judge, or None."""
    index = _command_index(words)
    if index is None:
        return None, None
    name = _basename(words[index].text)
    family = _family_of(name)
    if family is None:
        return None, None
    options = _read_options(family, words[index + 1:])
    if options.interactive:
        return ("interactive", name), None
    if options.code or options.operand or options.informational or connected:
        return None, options.code_string
    return ("noprogram", name), None


def _scan(commands, inherited, depth):
    for command in commands:
        connected = inherited or command.stdin or command.after_pipe
        verdict, inner = _judge(command.words, connected)
        if verdict:
            return verdict
        if inner is not None and depth == 0:
            try:
                inner_commands = parse(inner)
            except _Undecidable:
                continue
            verdict = _scan(inner_commands, connected, depth + 1)
            if verdict:
                return verdict
    return None


def find_deny(command):
    """Return (kind, name) for the first launch to deny, or None."""
    return _scan(parse(command), False, 0)


def deny_reason(kind, name):
    if kind == "interactive":
        lead = f"`{name}` を対話モード（-i）で起動する操作は、ここでは使えない。"
    else:
        lead = f"`{name}` をプログラムを渡さずに起動する操作は、対話モードになるため、ここでは使えない。"
    return (
        "[codex-hook-interactive-guard] "
        + lead
        + "端末が閉じても入力待ちのまま残り続ける孤児プロセスになる。"
        "非対話の実行に切り替えること: `python3 -c '...'` で式を渡す、"
        "スクリプトファイルを作って実行する、"
        "または `python3 - <<EOF` でヒアドキュメントから渡す。"
    )


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read())
        if not isinstance(payload, dict):
            return
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return
        command = tool_input.get("command")
        if not isinstance(command, str):
            return
        hit = find_deny(command)
        if hit is None:
            return
        text = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": HOOK_EVENT_NAME,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": deny_reason(*hit),
                }
            },
            ensure_ascii=False,
        )
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        return


if __name__ == "__main__":
    main()
    sys.exit(0)

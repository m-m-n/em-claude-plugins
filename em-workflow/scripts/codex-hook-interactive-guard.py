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
     no output. The reader takes a command substitution inside double quotes
     (`$( ... )`, `$(( ... ))` or a backtick span) as one chunk up to its
     matching close: quotes, backslashes and substitutions inside it close
     nothing outside, the word holding it is dynamic, and its contents are
     not judged. A chunk that is not closed, or whose close cannot be located
     with certainty -> no output. After the closing quote ordinary reading
     resumes, so a launch outside the quotes is still judged.
  4. A subshell `( ... )` and a brace group `{ ...; }` are groups. `{` and
     `}` delimit a group only as a standalone word at command position; a
     brace inside a larger word (`{a,b}`) does not. A group is connected when
     it is the right side of `|` or `|&`, or when a stdin redirect follows
     its close (`<` `<<` `<<<` `<&` `0<`). Other redirects (`2>` `>`) and a
     pipe on the right of the group do not connect it. A connected group
     passes the connection to every command inside it, nested groups
     included, so the commands of a group are judged once the redirects after
     its close are known. A group that is not closed -> no output. The body
     of a function definition (`name() { ...; }`) is not judged. `while`
     `for` `until` `if` and `case` are not read as groups.
  5. After `|` or `|&` the right side is awaited: a pending pipe survives
     newlines, blank lines, comment-only lines and heredoc bodies, and the
     next non-empty command is the right side. A newline after `&&` or `||`
     never creates a connection.
  6. For each simple command: drop redirections, skip leading variable
     assignments and the option-less wrappers (`env` `nohup` `nice` `exec`
     `command` `time` `sudo` `timeout DURATION`), and match the basename of
     the command word against the interpreter families below. A wrapper
     that carries an option (`env -i`, `nice -n 5`) -> the command is not
     judged.
  7. A shell (bash sh zsh dash ksh) reads `-c` as a flag: `-c` takes no
     value. The rest of its option bundle and the option words after it are
     read as options, letter by letter: an `i` anywhere is a launch with
     `-i`, and each `o` / `O` takes the next word as its value (so do
     `--rcfile` and `--init-file`). `--` or a lone `-` ends the options. With
     `-c`, the first operand is judged once, the same way, as a command
     string and inherits the standard input connection of the command that
     holds it; the words after it are positional parameters, never options.
     `-c` without an operand -> no output. A literal inside the command
     string is not judged. Other interpreters keep their reading of
     `-c` `-m` `-e`.
  8. Deny a launch that carries `-i` before the first operand (python, node,
     the shells and lua), and a launch that gives the interpreter no program
     to run: no operand, no code option, standard input neither redirected
     nor connected, and no informational option. The informational short
     options belong to each interpreter: `-V` `-h` for python, lua, ruby,
     deno, irb and ipython, and `-V` `-h` `-v` for node and perl. The shells
     have no information short options, so a shell `-h` or `-V` is an
     ordinary flag. `--version` and `--help` are informational for all, and
     so are the long options an interpreter defines for itself.
  9. Anything undecidable or unexpected -> no output.

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

# Long informational options that never open a REPL. Every family shares
# these; the short informational options belong to each family (info_letters).
INFO_LONG = ("--version", "--help")


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
                       bundle, or the next word when last). The shells read
                       a bundle one letter at a time instead: each of these
                       letters takes the next word
    attached_letters   short options whose rest of the bundle is a value, and
                       which never take the next word
    value_long         long options that take the next word as their value
    info_letters       informational short options of this interpreter; they
                       never open a REPL. The shells have none, so a shell
                       `-h` or `-V` is an ordinary flag
    info_long          extra informational long options (`--version` and
                       `--help` are shared by every family)
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
            value_long=("--check-hash-based-pycs",), info_letters="Vh"),
    _Family("node", ("node",), deny_i=True, interactive_long=("--interactive",),
            code_letters="ep", code_long=("--eval", "--print"), value_letters="rC",
            value_long=("--require", "--import", "--loader", "--experimental-loader", "--conditions"),
            info_letters="Vhv", info_long=("--test", "--check", "--run")),
    _Family("shell", ("bash", "sh", "zsh", "dash", "ksh"), deny_i=True, code_letters="c",
            value_letters="oO", value_long=("--rcfile", "--init-file"), info_letters="",
            is_shell=True),
    _Family("lua", ("lua",), deny_i=True, code_letters="cme", value_letters="l", info_letters="Vh"),
    _Family("ruby", ("ruby",), code_letters="e", value_letters="Ir", attached_letters="i0xKFW",
            info_letters="Vh"),
    _Family("perl", ("perl",), code_letters="eE", value_letters="IMm", attached_letters="i0xFCdD",
            info_letters="Vhv"),
    _Family("deno", ("deno",), code_letters="cme", info_letters="Vh"),
    _Family("irb", ("irb",), code_letters="cme", info_letters="Vh"),
    _Family("ipython", ("ipython",), code_letters="cme", info_letters="Vh"),
)

DIGITS = "0123456789"


class _Word:
    __slots__ = ("text", "dynamic")

    def __init__(self, text, dynamic):
        self.text = text
        # True when the word holds an expansion, so its value is unknown.
        self.dynamic = dynamic


class _Command:
    __slots__ = ("words", "stdin", "after_pipe", "group")

    def __init__(self, words, stdin, after_pipe, group):
        self.words = words
        # Standard input is redirected with `<`, `<<`, `<<<` or `<&`.
        self.stdin = stdin
        # The command sits on the right side of a pipe.
        self.after_pipe = after_pipe
        # The innermost group that holds the command, or None.
        self.group = group


class _Group:
    """A subshell `( ... )` or a brace group `{ ...; }`.

    kind       "(" or "{"
    parent     the group that holds this one, or None
    pipe       the group is the right side of a pipe
    stdin      a stdin redirect follows the close of the group
    skip       the group is a function body: defined here, run elsewhere
    head       a command word stood right before the `(`: `name(`
    size       (commands, groups) counted when the group opened, itself included
    connected  settled once the whole command is read: the group, or a group
               that holds it, has its standard input connected
    skipped    settled likewise: the group, or a group that holds it, is a
               function body
    """

    __slots__ = ("kind", "parent", "pipe", "stdin", "skip", "head", "size", "connected", "skipped")

    def __init__(self, kind, parent, pipe, skip, head, size):
        self.kind = kind
        self.parent = parent
        self.pipe = pipe
        self.stdin = False
        self.skip = skip
        self.head = head
        self.size = size
        self.connected = False
        self.skipped = False


class _Parser:
    """Split a command string into simple commands.

    Quotes, backslashes, comments, redirections and heredocs are read the way
    a shell reads them. Expansions are not evaluated: a word that holds one
    is marked dynamic. Groups (subshells and brace groups) are tracked on a
    stack, never by recursion, so any nesting depth is read in linear time.
    Raises _Undecidable on an unbalanced quote or group, an unclosed command
    substitution inside double quotes, or an unterminated heredoc.
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
        # A redirection was met in the simple command in progress.
        self.redirected = False
        # Open groups, innermost last, and every group in the order it opened.
        self.frames = []
        self.groups = []
        # The group closed last, while only redirections have followed it.
        self.after_group = None
        # A `name()` was just read: the next group is the body of a function.
        self.fn_head = False
        self._reset_word()

    def _reset_word(self):
        self.buf = []
        self.started = False
        self.dynamic = False
        # Every character so far is an unquoted digit (a file descriptor).
        self.digits = True
        # No quote, escape or expansion so far: `{` and `}` can be group words.
        self.bare = True

    def _put(self, text, quoted=False, dynamic=False):
        self.buf.append(text)
        self.started = True
        if dynamic:
            self.dynamic = True
        if quoted or dynamic:
            self.bare = False
        if quoted or not all(ch in DIGITS for ch in text):
            self.digits = False

    def _finish_word(self):
        if not self.started:
            return
        text = "".join(self.buf)
        dynamic = self.dynamic
        bare = self.bare
        self._reset_word()
        if self.redirect is not None:
            is_heredoc, strips_tabs = self.redirect
            self.redirect = None
            if is_heredoc:
                if not text:
                    raise _Undecidable("heredoc delimiter")
                self.heredocs.append((text, strips_tabs))
            return
        # `{` and `}` delimit a brace group only as a standalone word at
        # command position. A `}` that matches no open brace group is an
        # ordinary word, as it was before groups were read.
        if bare and not self.words:
            if text == "{":
                self._open_group("{")
                return
            if text == "}" and self.frames and self.frames[-1].kind == "{":
                self._close_group()
                return
        if self.after_group is not None and self.after_group.kind == "{":
            # Only a redirection, a separator or a comment may follow the `}`.
            raise _Undecidable("word after a brace group")
        self.fn_head = False
        self.after_group = None
        self.words.append(_Word(text, dynamic))

    def _flush(self):
        """End the simple command in progress. Return (made, redirected):
        whether it held words, and whether it held a redirection."""
        self._finish_word()
        self.redirect = None
        made = bool(self.words)
        redirected = self.redirected
        if made:
            group = self.frames[-1] if self.frames else None
            self.commands.append(_Command(self.words, self.stdin, self.pipe_pending, group))
            self.pipe_pending = False
        self.words = []
        self.stdin = False
        self.redirected = False
        self.after_group = None
        return made, redirected

    def _separator(self, sep):
        _, redirected = self._flush()
        if sep != "\n":
            self.fn_head = False
        if sep in ("|", "|&"):
            self.pipe_pending = True
        elif sep != "\n" or redirected:
            # A newline that ends an empty command keeps a pending pipe: the
            # empty lines, comments and heredoc bodies after `|` are not its
            # right side.
            self.pipe_pending = False

    def _open_group(self, kind):
        made, _ = self._flush()
        parent = self.frames[-1] if self.frames else None
        # The sizes as they stand once this group is in the list: an empty
        # group is closed with the same sizes.
        size = (len(self.commands), len(self.groups) + 1)
        group = _Group(kind, parent, self.pipe_pending, self.fn_head, made, size)
        self.pipe_pending = False
        self.fn_head = False
        self.frames.append(group)
        self.groups.append(group)

    def _close_group(self):
        """Close the innermost group. A stdin redirect read next connects it."""
        group = self.frames.pop()
        self.pipe_pending = False
        self.after_group = group
        if group.kind == "(" and group.head and group.size == (len(self.commands), len(self.groups)):
            # `name()` with nothing inside: the group that follows is the body.
            self.fn_head = True

    def _close_paren(self):
        self._finish_word()
        if self.frames and self.frames[-1].kind == "(":
            self._flush()
            self._close_group()
        else:
            # No subshell is open (a `case` pattern, for one): a separator.
            self._separator(")")

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
            if ch == "`" or s.startswith("$(", j):
                end = self._skip_substitution(j)
                out.append(s[j:end])
                dynamic = True
                j = end
                continue
            if ch in "$`":
                dynamic = True
            out.append(ch)
            j += 1
        raise _Undecidable("quote")

    def _skip_substitution(self, start):
        """Return the index just after the command substitution that begins
        at `start` (`$(`, `$((` or a backtick) inside double quotes.

        Quotes, backslash escapes, `${ ... }` and nested substitutions inside
        the chunk are followed, so a `"` or a `)` that belongs to them closes
        neither the chunk nor the double quote around it. Nesting is kept on
        an explicit stack, so depth costs no recursion. Raises _Undecidable
        when the chunk is not closed, or when its close cannot be located
        with certainty: a heredoc or a `case` inside it.

        Contexts on the stack: p command list (`$(`, `(`), a arithmetic
        (`$((`), d double quotes, b backticks, k and K `${ ... }` outside and
        inside double quotes.
        """
        s, n = self.s, self.n
        if s[start] == "`":
            stack = ["b"]
            j = start + 1
        elif s.startswith("$((", start):
            stack = ["p", "a"]
            j = start + 3
        else:
            stack = ["p"]
            j = start + 2
        while j < n:
            top = stack[-1]
            ch = s[j]
            if ch == "\\":
                j += 2
            elif top == "b":
                j += 1
                if ch == "`":
                    stack.pop()
                    if not stack:
                        return j
            elif ch == "`":
                stack.append("b")
                j += 1
            elif ch == '"':
                if top == "d":
                    stack.pop()
                else:
                    stack.append("d")
                j += 1
            elif s.startswith("$((", j):
                stack.extend(("p", "a"))
                j += 3
            elif s.startswith("$(", j):
                stack.append("p")
                j += 2
            elif s.startswith("${", j):
                stack.append("K" if top in "dK" else "k")
                j += 2
            elif top == "d":
                j += 1
            elif ch == "}" and top in "kK":
                stack.pop()
                j += 1
            elif top == "K":
                j += 1
            elif ch == "'":
                j = s.find("'", j + 1)
                if j == -1:
                    raise _Undecidable("quote")
                j += 1
            elif s.startswith("$'", j):
                j += 2
                while j < n and s[j] != "'":
                    j += 2 if s[j] == "\\" else 1
                j += 1
            elif top == "k":
                j += 1
            elif ch == "(":
                stack.append(top)
                j += 1
            elif ch == ")":
                stack.pop()
                j += 1
                if not stack:
                    return j
            elif top == "a":
                j += 1
            elif ch == "#" and s[j - 1] in " \t\n;&|(":
                # A comment runs to the end of the line.
                j = s.find("\n", j)
                if j == -1:
                    raise _Undecidable("substitution")
            elif s.startswith("<<<", j):
                j += 3
            elif s.startswith("<<", j):
                raise _Undecidable("heredoc in a substitution")
            elif ch == "c" and self._is_case_keyword(j):
                raise _Undecidable("case in a substitution")
            else:
                j += 1
        raise _Undecidable("substitution")

    def _is_case_keyword(self, j):
        """Whether the `case` at `j` is the keyword that opens a `case`
        command: its patterns end in a `)` that closes no substitution."""
        s = self.s
        if not s.startswith("case", j) or (j + 4 < self.n and s[j + 4] not in " \t\n"):
            return False
        k = j - 1
        while k >= 0 and s[k] in " \t":
            k -= 1
        if k < 0 or s[k] in ";&|(\n{!":
            return True
        end = k + 1
        while k >= 0 and s[k].isalpha():
            k -= 1
        return s[k + 1:end] in ("then", "do", "else", "elif", "if", "while", "until", "time")

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
        self.redirected = True
        if fd == 0 or (fd is None and ch == "<"):
            self.stdin = True
            if self.after_group is not None:
                self.after_group.stdin = True
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
                    self.redirected = True
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
                self._open_group("(")
            elif ch == ")":
                self.i += 1
                self._close_paren()
            elif ch in "<>":
                self._redirection()
            else:
                self._put(ch)
                self.i += 1
        self._separator("\n")
        if self.heredocs:
            raise _Undecidable("heredoc")
        if self.frames:
            raise _Undecidable("group")
        # A group opens after the group that holds it, so one pass settles
        # every group.
        for group in self.groups:
            parent = group.parent
            group.connected = group.pipe or group.stdin or (parent is not None and parent.connected)
            group.skipped = group.skip or (parent is not None and parent.skipped)
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
        # The first operand of a shell started with `-c`, when it is a literal.
        self.code_string = None


def _read_shell_options(family, args):
    """Read the options of a shell launch left to right.

    `-c` is a flag that takes no value: it turns on command-string mode and
    reading goes on through the rest of its bundle and the option words after
    it. A bundle is read one letter at a time: `i` makes the launch
    interactive, and each `o` / `O` takes the next word as its value, as do
    `--rcfile` and `--init-file`. `--` ends the options, and so does a lone
    `-` in command-string mode. Reading stops at the first operand: with `-c`
    it is the command string, and the words after it are positional
    parameters, never options. A dynamic word is an operand whose value is
    unknown. The shells have no informational short options.
    """
    result = _Options()
    command_string = False
    operand = None
    k = 0
    n = len(args)
    while k < n:
        word = args[k]
        text = word.text
        if word.dynamic or not text.startswith("-") or (text == "-" and not command_string):
            operand = k
            break
        if text == "--" or text == "-":
            operand = k + 1 if k + 1 < n else None
            break
        if text.startswith("--"):
            name, eq, _ = text.partition("=")
            if name in INFO_LONG or name in family.info_long:
                result.informational = True
            if name in family.value_long and not eq:
                k += 1
            k += 1
            continue
        values = 0
        for letter in text[1:]:
            if letter in family.code_letters:
                command_string = True
                result.code = True
            elif letter == "i":
                result.interactive = True
            elif letter in family.value_letters:
                values += 1
        k += 1 + values
    if operand is not None:
        result.operand = True
        if command_string and not args[operand].dynamic:
            result.code_string = args[operand].text
    return result


def _read_options(family, args):
    """Read options left to right. Reading stops at the first operand and at
    the value of a code-passing option. The shells have a reader of their own."""
    if family.is_shell:
        return _read_shell_options(family, args)
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
                return result
            if letter == "i" and family.deny_i:
                result.interactive = True
            elif letter in family.value_letters:
                if not rest:
                    k += 1
                break
            elif letter in family.attached_letters:
                break
            elif letter in family.info_letters:
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
        group = command.group
        if group is not None and group.skipped:
            continue
        connected = inherited or command.stdin or command.after_pipe
        if group is not None and group.connected:
            connected = True
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

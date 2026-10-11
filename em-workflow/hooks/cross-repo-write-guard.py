#!/usr/bin/env python3
"""PreToolUse guard for file writes whose destination lies outside the git
repository of the session's working directory.

The comparison base is solely `git rev-parse --show-toplevel` run in the
payload `cwd`. A write whose resolved destination is neither equal to nor
below that toplevel is sent to confirmation (`ask`); under claude-batch, where
nobody can answer a prompt, it is denied instead and the reason says so. The
hook is a confirmation aid for a cooperating agent, not a sandbox: whatever it
cannot settle statically passes without output.

Judged destinations:

  - Write / Edit / MultiEdit: `tool_input.file_path`, taken as one literal path.
  - Bash: the statically resolvable destinations of output redirections
    (`>` `>>` `>|` `&>` `&>>`, also with a descriptor number), the file
    operands of `tee`, the targets of GNU `sed -i` / `--in-place`, and the
    destination of `cp` / `mv` (`-t DIR` / `--target-directory` or the last of
    two or more operands). They are read from top-level commands, `( )`
    subshells, `{ }` brace groups, and after the wrappers sudo / env / nohup /
    time / command / nice and leading `NAME=value` assignments. `bash -c`
    strings, `$( )` / backquote / process-substitution bodies, heredoc bodies,
    quoted text and comments are never read as commands, but redirections of
    the statement that contains them are judged.

Never judged: destinations under /tmp or `$HOME/.claude`, the sinks
/dev/null /dev/stdout /dev/stderr /dev/tty and /dev/fd/..., destinations that
contain a parameter expansion, command substitution, unquoted glob character
or `$'...'` / `$"..."` quoting, and relative destinations after `cd` /
`pushd` / `popd` (a `cd` inside a subshell does not leak out of it) or inside
a statement that uses `env -C` / `sudo --chdir`.

Decision flow:

  1. Parse stdin as one JSON object and validate it; anything else -> no output.
  2. Collect, normalize and resolve the destinations (real-path semantics along
     the longest existing prefix), dropping the excluded ones.
  3. Only when a destination remains, start git exactly once (argument vector,
     no shell, payload cwd as working directory, fixed time limit shorter than
     the 15-second hook timeout). Missing git, failure, empty output or a
     timeout -> no output.
  4. A destination that is not equal to or below the resolved toplevel (at a
     path-component boundary) -> one `ask`, or `deny` under CLAUDE_BATCH.
  5. Any unexpected exception -> no output.

The hook only ever asks, denies or says nothing -- it never returns `allow` --
and the exit status is 0 on every path. It writes no files and starts no
process other than the single git lookup.

Standard library only; no other module of this repository is imported.
"""

import json
import os
import re
import subprocess
import sys

HOOK_EVENT_NAME = "PreToolUse"
TAG = "[cross-repo-write-guard]"

# Shorter than the 15-second hook timeout registered in hooks.json.
GIT_TIME_LIMIT_SECONDS = 5

# Set by claude-batch on the claude process it launches; hooks inherit it.
BATCH_ENV = "CLAUDE_BATCH"
# Values that mean "not set" even when the variable exists.
BATCH_OFF = ("", "0", "false", "no")

FILE_TOOLS = ("Write", "Edit", "MultiEdit")
TOOLS = FILE_TOOLS + ("Bash",)

DEV_SINKS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")
DEV_FD_PREFIX = "/dev/fd/"

CD_COMMANDS = ("cd", "pushd", "popd")


class ParseError(Exception):
    """The command text cannot be parsed as a whole."""


# ---------------------------------------------------------------------------
# Lexing
# ---------------------------------------------------------------------------


class Word:
    """One shell word: its characters after quote removal, each with a flag
    saying whether it was quoted, and whether the word is unresolvable
    (parameter expansion, substitution, unquoted glob, ANSI-C quoting)."""

    __slots__ = ("segs", "unres", "raw")

    def __init__(self):
        self.segs = []
        self.unres = False
        self.raw = ""

    @property
    def value(self):
        return "".join(c for c, _ in self.segs)

    def literal(self):
        return None if self.unres else self.value

    def is_plain(self, text):
        """True when the word is exactly `text`, written without quoting."""
        return (
            not self.unres
            and len(self.segs) == len(text)
            and all(not q for _, q in self.segs)
            and self.value == text
        )

    def sub(self, start):
        """The word made of the characters from `start` on (the part after an
        attached `=` or option letter)."""
        part = Word()
        part.segs = self.segs[start:]
        part.unres = self.unres
        return part


_DIGITS = "0123456789"
_DOLLAR_SPECIAL = "@*#?-$!" + _DIGITS
_NAME_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_NAME_CHARS = _NAME_START + "0123456789"
_ARRAY_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=$")


def skip_squote(text, i, n):
    """`i` is just after an opening `'`; return the index after the closing."""
    j = text.find("'", i)
    if j < 0:
        raise ParseError("unterminated single quote")
    return j + 1


def skip_backtick(text, i, n):
    """`i` is just after an opening backquote; return the index after the
    closing one."""
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            return i + 1
        i += 1
    raise ParseError("unterminated backquote")


def skip_ansi_c(text, i, n):
    """`i` is just after `$'`; return the index after the closing quote."""
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            return i + 1
        i += 1
    raise ParseError("unterminated $'...'")


def skip_dquote(text, i, n):
    """`i` is just after an opening `"`; return the index after the closing."""
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if c == "`":
            i = skip_backtick(text, i + 1, n)
            continue
        if c == "$" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "(":
                i = skip_paren(text, i + 2, n)
                continue
            if nxt == "{":
                i = skip_brace(text, i + 2, n)
                continue
        i += 1
    raise ParseError("unterminated double quote")


def skip_brace(text, i, n):
    """`i` is just after `${`; return the index after the matching `}`."""
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            i = skip_squote(text, i + 1, n)
            continue
        if c == '"':
            i = skip_dquote(text, i + 1, n)
            continue
        if c == "`":
            i = skip_backtick(text, i + 1, n)
            continue
        if c == "$" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "(":
                i = skip_paren(text, i + 2, n)
                continue
            if nxt == "{":
                i = skip_brace(text, i + 2, n)
                continue
        if c == "}":
            return i + 1
        i += 1
    raise ParseError("unterminated ${...}")


def skip_paren(text, i, n):
    """`i` is just after an opening `(` of `$(`, `$((`, `<(`, `>(` or an array
    assignment; return the index after the matching `)`. Quotes, nested
    substitutions, heredoc bodies and comments are honored only to find the
    end -- the body is never analyzed."""
    depth = 1
    start = i
    pending = []
    while i < n:
        c = text[i]
        if c == "\n" and pending:
            i = skip_heredoc_bodies(text, i + 1, n, pending)
            pending = []
            continue
        if c == "<" and text.startswith("<<", i) and not text.startswith("<<<", i):
            j = i + 2
            strip_tabs = j < n and text[j] == "-"
            if strip_tabs:
                j += 1
            while j < n and text[j] in " \t":
                j += 1
            delimiter, k = scan_word(text, j, n)
            if k > j:
                pending.append((strip_quotes(delimiter.raw), strip_tabs))
                i = k
                continue
            i += 2
            continue
        if c == "\\":
            i += 2
            continue
        if c == "'":
            i = skip_squote(text, i + 1, n)
            continue
        if c == '"':
            i = skip_dquote(text, i + 1, n)
            continue
        if c == "`":
            i = skip_backtick(text, i + 1, n)
            continue
        if c == "$" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "(":
                i = skip_paren(text, i + 2, n)
                continue
            if nxt == "{":
                i = skip_brace(text, i + 2, n)
                continue
            if nxt == "'":
                i = skip_ansi_c(text, i + 2, n)
                continue
        if c == "#" and (i == start or text[i - 1] in " \t\n;&|("):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ParseError("unterminated substitution")


def scan_dollar(text, i, n, word, in_dquote):
    """`text[i]` is `$`; consume the expansion that starts there into `word`
    and return the index after it."""
    nxt = text[i + 1] if i + 1 < n else ""
    if nxt == "(":
        word.unres = True
        return skip_paren(text, i + 2, n)
    if nxt == "{":
        word.unres = True
        return skip_brace(text, i + 2, n)
    if nxt == "'" and not in_dquote:
        word.unres = True
        return skip_ansi_c(text, i + 2, n)
    if nxt == '"' and not in_dquote:
        word.unres = True
        return scan_dquote(text, i + 2, n, Word())
    if nxt and nxt in _NAME_START:
        j = i + 1
        while j < n and text[j] in _NAME_CHARS:
            j += 1
        word.unres = True
        return j
    if nxt and nxt in _DOLLAR_SPECIAL:
        word.unres = True
        return i + 2
    word.segs.append(("$", in_dquote))
    return i + 1


def scan_dquote(text, i, n, word):
    """`i` is just after an opening `"`; append the string's characters to
    `word` and return the index after the closing quote."""
    while i < n:
        c = text[i]
        if c == '"':
            return i + 1
        if c == "\\":
            if i + 1 >= n:
                break
            nxt = text[i + 1]
            if nxt == "\n":
                i += 2
                continue
            if nxt in '$`"\\':
                word.segs.append((nxt, True))
                i += 2
                continue
            word.segs.append(("\\", True))
            i += 1
            continue
        if c == "`":
            word.unres = True
            i = skip_backtick(text, i + 1, n)
            continue
        if c == "$":
            i = scan_dollar(text, i, n, word, True)
            continue
        word.segs.append((c, True))
        i += 1
    raise ParseError("unterminated double quote")


def scan_word(text, i, n):
    """Scan one word starting at `i`; return (word, index after the word)."""
    word = Word()
    start = i
    while i < n:
        c = text[i]
        if c in " \t\n;&|)<>":
            break
        if c == "(":
            # `NAME=( ... )` array assignment; any other `(` ends the word.
            if _ARRAY_ASSIGN_RE.match(word.value) and all(not q for _, q in word.segs):
                word.unres = True
                i = skip_paren(text, i + 1, n)
                continue
            break
        if c == "\\":
            if i + 1 >= n:
                word.segs.append(("\\", True))
                i += 1
                continue
            if text[i + 1] == "\n":
                i += 2
                continue
            word.segs.append((text[i + 1], True))
            i += 2
            continue
        if c == "'":
            j = skip_squote(text, i + 1, n)
            for ch in text[i + 1 : j - 1]:
                word.segs.append((ch, True))
            i = j
            continue
        if c == '"':
            i = scan_dquote(text, i + 1, n, word)
            continue
        if c == "$":
            i = scan_dollar(text, i, n, word, False)
            continue
        if c == "`":
            word.unres = True
            i = skip_backtick(text, i + 1, n)
            continue
        if c in "*?[":
            word.unres = True
        word.segs.append((c, False))
        i += 1
    word.raw = text[start:i]
    return word, i


def strip_quotes(raw):
    """The heredoc delimiter: the word with quote removal and no expansion."""
    out = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n:
            out.append(raw[i + 1])
            i += 2
        elif c == "'":
            j = raw.find("'", i + 1)
            j = n if j < 0 else j
            out.append(raw[i + 1 : j])
            i = j + 1
        elif c == '"':
            j = i + 1
            while j < n and raw[j] != '"':
                if raw[j] == "\\" and j + 1 < n and raw[j + 1] in '$`"\\':
                    j += 1
                out.append(raw[j])
                j += 1
            i = j + 1
        elif c == "$" and i + 1 < n and raw[i + 1] in "'\"":
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def skip_heredoc_bodies(text, i, n, pending):
    """`i` is the start of the line after a newline that ends a command line
    carrying heredoc operators; skip each body up to its delimiter line."""
    for delimiter, strip_tabs in pending:
        while True:
            if i >= n:
                raise ParseError("heredoc delimiter line not found")
            j = text.find("\n", i)
            line = text[i:] if j < 0 else text[i:j]
            i = n if j < 0 else j + 1
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                break
    return i


_REDIRECT_OPS_FROM_LT = ("<<<", "<<-", "<<", "<&", "<>", "<")
_REDIRECT_OPS_FROM_GT = (">>", ">|", ">&", ">")


def tokenize(text):
    """Split the command text into tokens.

    ("word", Word) | ("redir", operator, fd-or-None) | ("op", operator) with
    operator one of `;` `&` `&&` `||` `|` `|&` newline `(` `)`.
    Heredoc bodies are skipped; comments are dropped."""
    n = len(text)
    i = 0
    tokens = []
    pending = []
    expect_delimiter = None  # None, or the strip-tabs flag of the open `<<`
    fd = None
    while i < n:
        c = text[i]
        if c in " \t":
            i += 1
            continue
        if c == "\\" and i + 1 < n and text[i + 1] == "\n":
            i += 2
            continue
        if c == "\n":
            if expect_delimiter is not None:
                raise ParseError("heredoc without a delimiter word")
            tokens.append(("op", "\n"))
            i += 1
            if pending:
                i = skip_heredoc_bodies(text, i, n, pending)
                pending = []
            continue
        if c == "#" and expect_delimiter is None:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in ";&|()<>":
            if expect_delimiter is not None:
                raise ParseError("heredoc without a delimiter word")
            if c == ";":
                tokens.append(("op", ";"))
                i += 1
            elif c == "&":
                if text.startswith("&>>", i):
                    tokens.append(("redir", "&>>", fd))
                    i += 3
                elif text.startswith("&>", i):
                    tokens.append(("redir", "&>", fd))
                    i += 2
                elif text.startswith("&&", i):
                    tokens.append(("op", "&&"))
                    i += 2
                else:
                    tokens.append(("op", "&"))
                    i += 1
                fd = None
            elif c == "|":
                if text.startswith("||", i):
                    tokens.append(("op", "||"))
                    i += 2
                elif text.startswith("|&", i):
                    tokens.append(("op", "|&"))
                    i += 2
                else:
                    tokens.append(("op", "|"))
                    i += 1
            elif c in "()":
                tokens.append(("op", c))
                i += 1
            elif text.startswith("(", i + 1):
                # process substitution: a word that is unresolvable
                word = Word()
                word.unres = True
                j = skip_paren(text, i + 2, n)
                word.raw = text[i:j]
                tokens.append(("word", word))
                i = j
            else:
                operators = _REDIRECT_OPS_FROM_LT if c == "<" else _REDIRECT_OPS_FROM_GT
                for operator in operators:
                    if text.startswith(operator, i):
                        break
                tokens.append(("redir", operator, fd))
                i += len(operator)
                fd = None
                if operator in ("<<", "<<-"):
                    expect_delimiter = operator == "<<-"
            continue
        if c in _DIGITS and expect_delimiter is None:
            j = i
            while j < n and text[j] in _DIGITS:
                j += 1
            if j < n and text[j] in "<>" and not text.startswith("(", j + 1):
                fd = text[i:j]
                i = j
                continue
        word, i = scan_word(text, i, n)
        tokens.append(("word", word))
        if expect_delimiter is not None:
            pending.append((strip_quotes(word.raw), expect_delimiter))
            expect_delimiter = None
    if expect_delimiter is not None:
        raise ParseError("heredoc without a delimiter word")
    if pending:
        raise ParseError("heredoc body not found")
    return tokens


# ---------------------------------------------------------------------------
# Command analysis
# ---------------------------------------------------------------------------

WRAPPERS = ("sudo", "env", "nohup", "time", "command", "nice")

# Per wrapper: short options that take an argument, long options that take an
# argument, and the options that change the working directory.
_WRAPPER_SHORT_ARG = {
    "sudo": "ugprtCDRTU",
    "env": "uCSa",
    "nohup": "",
    "time": "fo",
    "command": "",
    "nice": "n",
}
_WRAPPER_LONG_ARG = {
    "sudo": (
        "user", "group", "host", "prompt", "role", "type", "close-from",
        "chdir", "chroot", "command-timeout", "other-user",
    ),
    "env": ("unset", "chdir", "split-string", "argv0"),
    "nohup": (),
    "time": ("format", "output"),
    "command": (),
    "nice": ("adjustment",),
}
_WRAPPER_CHDIR_SHORT = {"sudo": "D", "env": "C"}
_WRAPPER_CHDIR_LONG = {"sudo": "chdir", "env": "chdir"}

_SED_LONG = (
    "binary", "debug", "expression", "file", "follow-symlinks", "help",
    "in-place", "line-length", "null-data", "zero-terminated", "posix",
    "quiet", "regexp-extended", "sandbox", "separate", "silent",
    "unbuffered", "version",
)
_CPMV_LONG = {
    "cp": (
        "archive", "attributes-only", "backup", "copy-contents", "debug",
        "dereference", "force", "interactive", "link", "no-clobber",
        "no-dereference", "no-preserve", "no-target-directory",
        "one-file-system", "parents", "preserve", "recursive", "reflink",
        "remove-destination", "sparse", "strip-trailing-slashes", "suffix",
        "symbolic-link", "target-directory", "update", "verbose", "context",
        "help", "version", "keep-directory-symlink",
    ),
    "mv": (
        "backup", "debug", "exchange", "force", "interactive", "no-clobber",
        "no-copy", "no-target-directory", "strip-trailing-slashes", "suffix",
        "target-directory", "update", "verbose", "context", "help", "version",
    ),
}
_CPMV_LONG_ARG = {
    "cp": ("suffix", "target-directory", "sparse", "no-preserve"),
    "mv": ("suffix", "target-directory"),
}


def unique_prefix(name, table):
    """GNU getopt_long matching: an exact name or a unique abbreviation."""
    if name in table:
        return name
    if not name:
        return None
    found = [t for t in table if t.startswith(name)]
    return found[0] if len(found) == 1 else None


def is_assignment(word):
    """`NAME=value` / `NAME+=value` with an unquoted name."""
    segs = word.segs
    for k, (ch, quoted) in enumerate(segs):
        if quoted:
            return False
        if ch == "=":
            return k > 0
        if ch == "+" and k > 0 and k + 1 < len(segs) and segs[k + 1] == ("=", False):
            return True
        if not (ch.isascii() and (ch.isalnum() or ch == "_")):
            return False
        if k == 0 and ch.isdigit():
            return False
    return False


def skip_wrapper_options(name, words, i):
    """Skip the options of wrapper `name` that start at words[i]. Return
    (next index, changes the working directory, command is not executed)."""
    chdir = False
    no_exec = False
    short_arg = _WRAPPER_SHORT_ARG[name]
    long_arg = _WRAPPER_LONG_ARG[name]
    chdir_short = _WRAPPER_CHDIR_SHORT.get(name, "")
    chdir_long = _WRAPPER_CHDIR_LONG.get(name)
    n = len(words)
    while i < n:
        text = words[i].literal()
        if text is None:
            break
        if text == "--":
            i += 1
            break
        if text == "-" and name == "env":
            i += 1
            continue
        if text.startswith("--") and len(text) > 2:
            option, equals, _ = text[2:].partition("=")
            if chdir_long is not None and option == chdir_long:
                chdir = True
            i += 1
            if option in long_arg and not equals:
                i += 1
            continue
        if text.startswith("-") and len(text) > 1:
            takes_next = False
            for k in range(1, len(text)):
                ch = text[k]
                if chdir_short and ch == chdir_short:
                    chdir = True
                if name == "command" and ch in "vV":
                    no_exec = True
                if ch in short_arg:
                    takes_next = k + 1 >= len(text)
                    break
            i += 2 if takes_next else 1
            continue
        break
    return min(i, n), chdir, no_exec


def resolve_command(words):
    """Return (command name or None, its argument words, wrapper changes the
    working directory) after skipping leading assignments and wrappers."""
    chdir = False
    i = 0
    n = len(words)
    while True:
        while i < n and is_assignment(words[i]):
            i += 1
        if i >= n:
            return None, [], chdir
        name = words[i].literal()
        if name not in WRAPPERS:
            return name, words[i + 1 :], chdir
        i, changed, no_exec = skip_wrapper_options(name, words, i + 1)
        chdir = chdir or changed
        if no_exec:
            return None, [], chdir


def tee_destinations(args):
    out = []
    past_options = False
    for word in args:
        text = word.literal()
        if not past_options and text is not None:
            if text == "--":
                past_options = True
                continue
            if text.startswith("-") and len(text) > 1:
                continue
        out.append(word)
    return out


def sed_destinations(args):
    in_place = False
    script_option = False
    operands = []
    past_options = False
    i = 0
    n = len(args)
    while i < n:
        word = args[i]
        text = word.literal()
        i += 1
        if past_options or text is None or not text.startswith("-") or text == "-":
            operands.append(word)
            continue
        if text == "--":
            past_options = True
            continue
        if text.startswith("--"):
            option, equals, _ = text[2:].partition("=")
            full = unique_prefix(option, _SED_LONG)
            if full == "in-place":
                in_place = True
            elif full in ("expression", "file", "line-length"):
                if full != "line-length":
                    script_option = True
                if not equals:
                    i += 1
            continue
        for k in range(1, len(text)):
            ch = text[k]
            if ch == "i":
                in_place = True
                break
            if ch in "efl":
                if ch != "l":
                    script_option = True
                if k + 1 >= len(text):
                    i += 1
                break
    if not in_place:
        return []
    return operands if script_option else operands[1:]


def cpmv_destinations(name, args):
    target = None
    operands = []
    past_options = False
    long_names = _CPMV_LONG[name]
    long_with_arg = _CPMV_LONG_ARG[name]
    i = 0
    n = len(args)
    while i < n:
        word = args[i]
        text = word.literal()
        i += 1
        if past_options or text is None or not text.startswith("-") or text == "-":
            operands.append(word)
            continue
        if text == "--":
            past_options = True
            continue
        if text.startswith("--"):
            option, equals, _ = text[2:].partition("=")
            full = unique_prefix(option, long_names)
            if full == "target-directory":
                if equals:
                    target = word.sub(2 + len(option) + 1)
                elif i < n:
                    target = args[i]
                    i += 1
            elif full in long_with_arg and not equals:
                i += 1
            continue
        for k in range(1, len(text)):
            ch = text[k]
            if ch == "t":
                if k + 1 < len(text):
                    target = word.sub(k + 1)
                elif i < n:
                    target = args[i]
                    i += 1
                break
            if ch == "S":
                if k + 1 >= len(text):
                    i += 1
                break
    if target is not None:
        return [target]
    if len(operands) >= 2:
        return [operands[-1]]
    return []


def command_destinations(name, args):
    if name == "tee":
        return tee_destinations(args)
    if name == "sed":
        return sed_destinations(args)
    if name in ("cp", "mv"):
        return cpmv_destinations(name, args)
    return []


_WRITE_REDIRECTS = (">", ">>", ">|", "&>", "&>>")
_SEPARATORS = (";", "&", "&&", "||", "|", "|&", "\n")


class Analyzer:
    """Walks the token list and collects (Word, relative-suppressed) pairs."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.destinations = []

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def parse_sequence(self, closer, suppressed):
        """Statements until the end of input (closer None), a `)` or a `}`
        at command position. Return the suppression flag after them."""
        while True:
            token = self.peek()
            if token is None:
                if closer is not None:
                    raise ParseError("unterminated group")
                return suppressed
            if token[0] == "op":
                operator = token[1]
                if operator in _SEPARATORS:
                    self.pos += 1
                    continue
                if operator == ")":
                    if closer == ")":
                        self.pos += 1
                        return suppressed
                    raise ParseError("unbalanced )")
            elif token[0] == "word" and token[1].is_plain("}"):
                if closer == "}":
                    self.pos += 1
                    return suppressed
                raise ParseError("unbalanced }")
            suppressed = self.parse_command(suppressed)

    def parse_command(self, suppressed):
        token = self.peek()
        if token == ("op", "("):
            self.pos += 1
            self.parse_sequence(")", suppressed)
            self.parse_group_redirects(suppressed)
            return suppressed
        if token[0] == "word" and token[1].is_plain("{"):
            self.pos += 1
            inner = self.parse_sequence("}", suppressed)
            self.parse_group_redirects(suppressed)
            return suppressed or inner
        return self.parse_simple(suppressed)

    def take_redirect(self, found):
        """Consume one redirection (operator and target word); record the
        target word in `found` when the operator writes a file."""
        _, operator, _ = self.tokens[self.pos]
        self.pos += 1
        target = self.peek()
        if target is None or target[0] != "word":
            raise ParseError("redirection without a target")
        self.pos += 1
        if operator in _WRITE_REDIRECTS:
            found.append(target[1])

    def parse_group_redirects(self, suppressed):
        found = []
        while True:
            token = self.peek()
            if token is None or token[0] != "redir":
                break
            self.take_redirect(found)
        self.destinations.extend((word, suppressed) for word in found)

    def parse_simple(self, suppressed):
        words = []
        found = []
        while True:
            token = self.peek()
            if token is None or token[0] == "op":
                break
            if token[0] == "redir":
                self.take_redirect(found)
            else:
                words.append(token[1])
                self.pos += 1
        name, args, chdir = resolve_command(words)
        flag = suppressed or chdir
        found.extend(command_destinations(name, args))
        self.destinations.extend((word, flag) for word in found)
        return suppressed or name in CD_COMMANDS


def word_to_path(word, home):
    """The literal path a destination word names, or None when it cannot be
    settled (unresolvable, empty, or a tilde with no HOME)."""
    if word.unres or not word.segs:
        return None
    value = word.value
    if word.segs[0] == ("~", False) and (len(word.segs) == 1 or word.segs[1] == ("/", False)):
        if not home:
            return None
        value = home + value[1:]
    return value


def bash_destinations(command, home):
    """The ordered (path, relative-suppressed) destinations of a Bash command,
    or None when the command cannot be parsed as a whole."""
    try:
        analyzer = Analyzer(tokenize(command))
        analyzer.parse_sequence(None, False)
    except ParseError:
        return None
    out = []
    for word, suppressed in analyzer.destinations:
        path = word_to_path(word, home)
        if path is not None:
            out.append((path, suppressed))
    return out


# ---------------------------------------------------------------------------
# Judgment
# ---------------------------------------------------------------------------


def normalize(path):
    path = os.path.normpath(path)
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    return path


def is_dev_sink(path):
    return path in DEV_SINKS or path.startswith(DEV_FD_PREFIX)


def within(path, root):
    """Equal to or below `root`, compared at path-component boundaries."""
    if path == root:
        return True
    return path.startswith(root if root.endswith("/") else root + "/")


def resolve_path(path, parents):
    """`os.path.realpath(path)` -- symbolic links resolved along the longest
    existing prefix, the non-existent remainder appended -- with the real path
    of each parent directory computed once (`parents` is the cache): a command
    naming thousands of files in one directory would otherwise resolve the
    same prefix again and again. A path with a NUL byte cannot name a file:
    ValueError, as `os.path.realpath` raises it."""
    if "\0" in path:
        raise ValueError("embedded null byte")
    parent, leaf = os.path.split(path)
    if not leaf or os.path.islink(path):
        return os.path.realpath(path)
    real_parent = parents.get(parent)
    if real_parent is None:
        real_parent = parents[parent] = os.path.realpath(parent)
    return os.path.join(real_parent, leaf)


def git_toplevel(cwd):
    """The output of `git rev-parse --show-toplevel` in `cwd`, or None."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIME_LIMIT_SECONDS,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    top = os.fsdecode(proc.stdout)
    if top.endswith("\n"):
        top = top[:-1]
    return top or None


def unattended():
    return os.environ.get(BATCH_ENV, "").strip().lower() not in BATCH_OFF


def build_decision(outside, toplevel):
    reason = (
        f"{TAG} 書き込み先が現在の git リポジトリ（{toplevel}）の外にある:\n"
        + "\n".join(f"  - {path}" for path in outside)
        + "\n意図した書き込み先か確認する。"
    )
    decision = "ask"
    if unattended():
        decision = "deny"
        reason += (
            "\n無人実行（claude-batch）のため確認を取れないので、`ask` を `deny` に降格した。"
            "書き込み先をリポジトリの中に変えて続行する。"
            "リポジトリの外へ書き込む必要が本当にあるなら、ユーザーに報告して指示を仰ぐ。"
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def tilde_literal(path, home):
    """Expand a leading `~` alone or `~/` with HOME; None when HOME is unset."""
    if path == "~" or path.startswith("~/"):
        return home + path[1:] if home else None
    return path


def judge(raw):
    """Return the decision document for one payload, or None for no output."""
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        return None
    tool = payload.get("tool_name")
    cwd = payload.get("cwd")
    tool_input = payload.get("tool_input")
    if not isinstance(tool, str) or tool not in TOOLS:
        return None
    if not isinstance(cwd, str) or not cwd:
        return None
    if not isinstance(tool_input, dict):
        return None
    home = os.environ.get("HOME", "")

    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command:
            return None
        candidates = bash_destinations(command, home)
        if candidates is None:
            return None
    else:
        file_path = tool_input.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            return None
        path = tilde_literal(file_path, home)
        candidates = [] if path is None else [(path, False)]

    absolute = []
    for path, suppressed in candidates:
        is_absolute = path.startswith("/")
        if suppressed and not is_absolute:
            continue
        path = normalize(path if is_absolute else os.path.join(cwd, path))
        if is_dev_sink(path):
            continue
        absolute.append(path)

    roots = [os.path.realpath("/tmp")]
    if home and os.path.isabs(home):
        roots.append(os.path.realpath(os.path.join(home, ".claude")))
    resolved = {}  # insertion-ordered set: each destination listed once
    parents = {}
    for path in absolute:
        try:
            real = resolve_path(path, parents)
        except (OSError, ValueError):
            continue
        if any(within(real, root) for root in roots):
            continue
        resolved[real] = None
    if not resolved:
        return None

    top = git_toplevel(cwd)
    if top is None:
        return None
    top = os.path.realpath(top)
    outside = [path for path in resolved if not within(path, top)]
    if not outside:
        return None
    return build_decision(outside, top)


def main():
    try:
        decision = judge(sys.stdin.buffer.read())
        if decision is not None:
            sys.stdout.write(json.dumps(decision))
            sys.stdout.flush()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()

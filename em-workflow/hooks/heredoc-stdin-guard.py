#!/usr/bin/env python3
"""PreToolUse(Bash) guard that closes standard input for a heredoc command
or a command with a bare `cat`/`tee` stdin reader.

The Bash tool connects a command's standard input to the Claude Code
socket. A command that contains a heredoc still works, because bash reads
the heredoc body from the script text itself rather than from real stdin --
but if that same command also runs something that tries to READ real
stdin (a CLI waiting for a prompt, say), that read blocks on the socket
forever, because nothing on the other end will ever write to it or close
it. The reproduction that motivated this guard: a heredoc used to build a
prompt file, followed by a CLI invocation that read from stdin when no
prompt argument was given -- the CLI sat at `00:00:00` CPU time
indefinitely.

This guard rewrites such a command by prepending a stdin cut-off
(`exec < /dev/null`), so anything later in the same script that reads
stdin gets an immediate EOF instead of hanging. It NEVER denies, blocks or
delays a tool call: its only two outcomes are "one updated-input object"
and "nothing" (IMPLEMENTATION.md D4). This is what makes an imperfect,
purely static reading of the command text an acceptable basis for the
decision -- the worst case of a false positive is a command that runs with
its standard input closed.

Decision flow:

  1. Read stdin, parse as one JSON object. Any failure -> no output.
  2. tool_name must be exactly "Bash". Otherwise -> no output.
  3. tool_input.command must be a non-empty string. Otherwise -> no output.
  4. Decide, by static reading of the command text alone, whether it
     contains a heredoc operator (`<<` or `<<-`, never a here-string
     `<<<`) outside quotes and outside any heredoc body already opened
     earlier in the command -- or a `cat`/`tee` that would read the
     script's own standard input: not on the receiving side of a pipe,
     with no stdin redirect of its own, and (for `cat`) with no file
     operand other than `-`. The reproduction for this second trigger: a
     stray `cat > file` line with no input, left at the head of a prompt-
     building command, blocked on the socket for good.
  5. Decide whether the FIRST command of the script already redirects
     standard input at its head -- a plain `<` (never a heredoc or
     here-string) with no explicit file-descriptor prefix, or an explicit
     `0<`. This is what makes a second application of this guard, or a
     command the caller already wrote with its stdin closed, a no-op
     (IMPLEMENTATION.md D5): the exact token this guard inserts,
     `exec < /dev/null`, is one instance of that case.
  6. Rewrite only when step 4 is true and step 5 is false.
  7. The rewrite copies the whole `tool_input` mapping and replaces only
     `command` with the cut-off token, a newline, then the original
     command text unchanged. Every other field keeps its original value
     and type.
  8. Anything unexpected anywhere above is caught and ends the run exactly
     like step 1 -- no output, exit status 0. No file is written, no
     process is started, no network connection is opened, and nothing is
     written to standard error (NFR2).

The reading in step 4/5 does not need to be a complete shell parser
(Precision boundary): when the command's structure cannot be settled --
an unterminated quote, an unterminated heredoc body -- it is treated as
undecidable and the run ends with no output, the same as a plain
non-match. Over-detection is acceptable and under-detection is safe,
because the only effect of a rewrite is a closed standard input.
"""

import json
import sys

BASH_TOOL_NAME = "Bash"

# The PreToolUse event name, carried on every emitted output's hook-specific
# output as `hookEventName` (IMPLEMENTATION.md D10). The runtime's
# hook-output validator rejects a hook-specific output missing this member,
# and its sanitizer discards the whole hook-specific output when the
# member's value is not the event name of the event being handled -- so
# omitting it, or misnaming its value, silently turns every rewrite below
# into a no-op even though the guard's own tests still see the JSON it
# printed.
HOOK_EVENT_NAME = "PreToolUse"

# The exact token this guard inserts. Also the recognition signal for
# idempotency (IMPLEMENTATION.md D5): a command that already begins with a
# plain stdin redirect -- including this one, fed back in -- is never
# rewritten again.
STDIN_CUTOFF = "exec < /dev/null"

# Words that may precede a command name in the same simple command without
# being the command itself (reserved words and `{`).
_COMMAND_PREFIX_WORDS = frozenset(
    {"!", "{", "then", "do", "else", "elif", "if", "while", "until", "time"}
)


class _Undecidable(Exception):
    """The command's shell structure cannot be read with confidence (an
    unterminated quote, or a heredoc whose delimiter or body cannot be
    resolved). Callers treat this exactly like "do not rewrite"."""


def _parse_heredoc_word(command, k):
    """Parse the delimiter word following a `<<`/`<<-` operator, starting
    at index `k` (already past any optional `-` and leading whitespace).

    Returns (word, next_index), or (None, k) if the word cannot be read
    (e.g. an unterminated quote around it) -- the caller raises
    `_Undecidable` in that case.
    """
    n = len(command)
    if k >= n:
        return None, k
    ch = command[k]
    if ch == "'":
        end = command.find("'", k + 1)
        if end == -1:
            return None, k
        return command[k + 1 : end], end + 1
    if ch == '"':
        j = k + 1
        buf = []
        while j < n and command[j] != '"':
            if command[j] == "\\" and j + 1 < n:
                buf.append(command[j + 1])
                j += 2
                continue
            buf.append(command[j])
            j += 1
        if j >= n:
            return None, k
        return "".join(buf), j + 1
    j = k
    buf = []
    while j < n and command[j] not in " \t\n":
        if command[j] == "\\" and j + 1 < n:
            buf.append(command[j + 1])
            j += 2
            continue
        buf.append(command[j])
        j += 1
    if not buf:
        return None, k
    return "".join(buf), j


def _skip_heredoc_body(command, i, delim, dashed):
    """Return the index right after the heredoc body starting at `i`,
    i.e. right after the line consisting of exactly `delim` (leading tabs
    stripped first when `dashed`). Raises `_Undecidable` if that
    terminator line is never found before the command ends."""
    n = len(command)
    while True:
        newline = command.find("\n", i)
        end = newline if newline != -1 else n
        line = command[i:end]
        candidate = line.lstrip("\t") if dashed else line
        if candidate == delim:
            return end + 1 if newline != -1 else n
        if newline == -1:
            raise _Undecidable("heredoc terminator not found before end of command")
        i = end + 1


class _SimpleCommand:
    """The words and stdin facts of one simple command, collected while
    `_analyze` walks the text. Only what the bare-stdin-reader decision
    needs is kept: the words that are not redirect targets, whether the
    command redirects its own stdin, and whether it receives a pipe."""

    def __init__(self, pipe_receiver):
        self.words = []
        self.stdin_redirected = False
        self.pipe_receiver = pipe_receiver


def _is_assignment(word):
    name, sep, _ = word.partition("=")
    return bool(sep) and bool(name) and (name[0].isalpha() or name[0] == "_") and all(
        c.isalnum() or c == "_" for c in name
    )


def _reads_stdin_bare(cmd):
    """True iff `cmd` is a `cat` or `tee` that reads the script's own
    standard input: it receives no pipe, redirects no stdin of its own, and
    (for `cat`) names no file operand other than `-`."""
    if cmd.pipe_receiver or cmd.stdin_redirected:
        return False
    words = list(cmd.words)
    while words and (words[0] in _COMMAND_PREFIX_WORDS or _is_assignment(words[0])):
        words.pop(0)
    if not words:
        return False
    name = words[0].rsplit("/", 1)[-1]
    if name == "tee":
        return True
    if name != "cat":
        return False
    operands = [w for w in words[1:] if w == "-" or not w.startswith("-")]
    return all(w == "-" for w in operands)


def _analyze(command):
    """One static-reading pass over `command`.

    Returns (has_heredoc, has_bare_stdin_reader, head_has_stdin_redirect):

      has_heredoc             -- a heredoc operator (`<<`/`<<-`, never a
                                  here-string `<<<`) exists outside quotes
                                  and outside any heredoc body already
                                  opened earlier in the command.
      has_bare_stdin_reader   -- some simple command is a `cat` or `tee`
                                  that would read the script's own standard
                                  input (see `_reads_stdin_bare`). The
                                  reading of command boundaries is
                                  approximate; over-detection only costs a
                                  closed standard input.
      head_has_stdin_redirect -- the first command of the script (the span
                                  up to the first top-level statement
                                  separator: newline, `;`, `&`, `|`)
                                  itself carries a plain stdin redirect
                                  (no fd prefix, or an explicit `0`) --
                                  never a heredoc or here-string, which
                                  redirect only the ONE command that opens
                                  them and say nothing about the rest of
                                  the script.

    Raises `_Undecidable` when the structure cannot be read with
    confidence (an unterminated quote or heredoc).
    """
    n = len(command)
    i = 0
    in_squote = False
    in_dquote = False
    has_heredoc = False
    has_bare_reader = False
    head_has_redirect = False
    in_head = True
    pending = []  # [(delim, dashed), ...] awaiting their body at the next newline

    cmd = _SimpleCommand(pipe_receiver=False)
    word = []  # characters of the word being read; quotes are dropped
    in_word = False
    skip_next_word = False  # the next word is a redirect target, not an operand
    in_backtick = False  # inside a `...` command substitution

    def end_word():
        nonlocal word, in_word, skip_next_word
        if in_word:
            if skip_next_word:
                skip_next_word = False
            else:
                cmd.words.append("".join(word))
        word = []
        in_word = False

    def end_command(next_is_pipe_receiver):
        nonlocal cmd, has_bare_reader
        end_word()
        if _reads_stdin_bare(cmd):
            has_bare_reader = True
        cmd = _SimpleCommand(pipe_receiver=next_is_pipe_receiver)

    def take_fd_prefix():
        """A word made only of digits right before `<`/`>` is the fd
        number of that redirect, not an operand. Returns those digits."""
        nonlocal word, in_word
        if in_word and word and all(c.isdigit() for c in word):
            digits = "".join(word)
            word = []
            in_word = False
            return digits
        end_word()
        return ""

    while i < n:
        ch = command[i]

        if in_squote:
            if ch == "'":
                in_squote = False
            else:
                word.append(ch)
            i += 1
            continue

        if in_dquote:
            if ch == "\\" and i + 1 < n:
                word.append(command[i + 1])
                i += 2
                continue
            if ch == '"':
                in_dquote = False
            else:
                word.append(ch)
            i += 1
            continue

        if ch == "\\" and i + 1 < n:
            if command[i + 1] != "\n":
                word.append(command[i + 1])
                in_word = True
            i += 2
            continue
        if ch == "'":
            in_squote = True
            in_word = True
            i += 1
            continue
        if ch == '"':
            in_dquote = True
            in_word = True
            i += 1
            continue

        if ch == "#" and not in_word:
            newline = command.find("\n", i)
            i = n if newline == -1 else newline
            continue

        if ch in "<>" and i + 1 < n and command[i + 1] == "(":
            # Process substitution `<(...)` / `>(...)`: an operand, and its
            # inner command runs separately.
            end_word()
            cmd.words.append(ch + "(")
            end_command(next_is_pipe_receiver=False)
            in_head = False
            i += 2
            continue

        if ch == "<":
            j = i
            while j < n and command[j] == "<":
                j += 1
            run_len = j - i
            digits = take_fd_prefix()

            if run_len == 1:
                if digits in ("", "0"):
                    cmd.stdin_redirected = True
                    if in_head:
                        head_has_redirect = True
                if j < n and command[j] == "&":
                    j += 1
                skip_next_word = True
                i = j
                continue

            if run_len == 3:
                # Here-string: never a heredoc, never a plain redirect of
                # the whole script, but it does feed this one command --
                # only when it targets fd 0.
                if digits in ("", "0"):
                    cmd.stdin_redirected = True
                skip_next_word = True
                i = j
                continue

            if run_len == 2:
                has_heredoc = True
                if digits in ("", "0"):
                    cmd.stdin_redirected = True
                k = j
                dashed = False
                if k < n and command[k] == "-":
                    dashed = True
                    k += 1
                while k < n and command[k] in " \t":
                    k += 1
                delim, k = _parse_heredoc_word(command, k)
                if delim is None:
                    raise _Undecidable("heredoc delimiter could not be read")
                pending.append((delim, dashed))
                i = k
                continue

            # A run of 4+ is not a construct this reader models; treat it
            # as opaque and move past it rather than guessing.
            i = j
            continue

        if ch == ">" or (ch == "&" and i + 1 < n and command[i + 1] == ">"):
            take_fd_prefix()
            j = i + 1
            while j < n and command[j] in ">|&":
                j += 1
            skip_next_word = True
            i = j
            continue

        if ch == "\n":
            if cmd.pipe_receiver and not cmd.words and not in_word:
                # `a |` <newline> `b`: the pipe continues onto the next line.
                end_word()
            else:
                end_command(next_is_pipe_receiver=False)
            i += 1
            if pending:
                for delim, dashed in pending:
                    i = _skip_heredoc_body(command, i, delim, dashed)
                pending = []
            in_head = False
            continue

        if ch == "|":
            is_or = i + 1 < n and command[i + 1] == "|"
            end_command(next_is_pipe_receiver=not is_or)
            in_head = False
            i += 2 if is_or or (i + 1 < n and command[i + 1] == "&") else 1
            continue

        if (ch == "$" and i + 1 < n and command[i + 1] == "(") or (
            ch == "`" and not in_backtick
        ):
            # Opening a command substitution: it is an operand of the outer
            # command (like `<(...)` above), and its inner command runs
            # separately.
            end_word()
            cmd.words.append("$(" if ch == "$" else "`")
            end_command(next_is_pipe_receiver=False)
            in_head = False
            if ch == "`":
                in_backtick = True
                i += 1
            else:
                i += 2
            continue

        if ch in ";&()`":
            if ch == "`":
                in_backtick = False
            end_command(next_is_pipe_receiver=False)
            in_head = False
            i += 1
            continue

        if ch in " \t":
            end_word()
            i += 1
            continue

        word.append(ch)
        in_word = True
        i += 1

    if in_squote or in_dquote:
        raise _Undecidable("unterminated quote")
    if pending:
        raise _Undecidable("unterminated heredoc: no body found")

    end_command(next_is_pipe_receiver=False)
    return has_heredoc, has_bare_reader, head_has_redirect


def _should_rewrite(command):
    """True iff `command` contains a heredoc outside quotes/bodies, or a
    `cat`/`tee` that would read the script's own standard input, and its
    first command does not already redirect standard input. An undecidable
    shell structure is treated as "do not rewrite" (Precision boundary)."""
    try:
        has_heredoc, has_bare_reader, head_has_redirect = _analyze(command)
    except _Undecidable:
        return False
    return (has_heredoc or has_bare_reader) and not head_has_redirect


def _emit_rewrite(tool_input):
    updated = dict(tool_input)
    updated["command"] = f"{STDIN_CUTOFF}\n{tool_input['command']}"
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT_NAME,
                "updatedInput": updated,
            }
        },
        sys.stdout,
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # fail-open: unreadable/malformed input is not decidable

    if not isinstance(payload, dict):
        return
    if payload.get("tool_name") != BASH_TOOL_NAME:
        return

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    command = tool_input.get("command")
    if not isinstance(command, str) or command == "":
        return

    try:
        if not _should_rewrite(command):
            return
        _emit_rewrite(tool_input)
    except Exception:
        return  # fail-open: never let an unexpected failure block the call


if __name__ == "__main__":
    main()
    sys.exit(0)

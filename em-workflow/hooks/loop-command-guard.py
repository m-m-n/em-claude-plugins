#!/usr/bin/env python3
"""PreToolUse(Bash) guard against while / until loops at a command position.

A `while` / `until` loop that never terminates can hang an unattended run
indefinitely. This guard denies any Bash command whose command text (or a
shell text reachable from it -- a `-c` string, an `eval` argument, a command
substitution, a heredoc body or herestring fed to bash/sh/zsh) contains a
`while` or `until` keyword at a command position, per the position rules in
feature-docs/loop-command-guard/tasks/task0001.md ("Command position").

Decision flow:

  1. Read stdin, parse as one JSON object; tool_name must be exactly "Bash"
     and tool_input.command a non-empty string. Otherwise -> no output.
  2. Read the command as a shell text at depth 0 (`read_shell_text`).
  3. A loop found in the text itself, or in a nested shell text this guard
     re-reads (command substitution / backtick content; the `-c` string of
     bash, sh or zsh; an `eval` argument; a heredoc body or herestring fed to
     bash, sh or zsh) -> deny. Otherwise, including every input this guard
     cannot settle (an unterminated quote/heredoc/substitution at the text's
     own depth, or nesting beyond the maximum depth) -> no output.
  4. Any unexpected failure anywhere above -> no output, exit status 0.

The guard only ever denies or says nothing -- it never returns allow or ask,
and every undecidable case falls through silently so the other Bash guards
still get to see the command.

Standard library only (json, re, sys); no other module, no other hook.
Output: a PreToolUse permission decision on stdout on deny; exit 0 either
way; stderr is always empty.
"""

import json
import re
import sys

HOOK_EVENT_NAME = "PreToolUse"

# feature-docs/loop-command-guard/tasks/task0001.md Design, "Undecidability
# and depth": "a named constant of no less than 8."
MAX_NESTING_DEPTH = 8

SHELLS = {"bash", "sh", "zsh"}
A6_PREFIXES = {
    "timeout", "nohup", "env", "nice", "setsid", "stdbuf", "command", "exec", "time",
}
# Reserved words that, standing at a command position themselves, keep the
# NEXT word at a command position too (task0001.md Design, "Command
# position"). `!` behaves the same way and is checked alongside these.
RESERVED_CHAIN = {"if", "then", "elif", "else", "do"}

_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

def _scan_dquote(text, i, out_nested):
    """`i` is the index right after an opening `"`. Return
    (index_after_closing_quote, ok). Command substitutions and backticks
    inside are matched for balance; when `out_nested` is a list, their
    content is appended to it (one entry per occurrence, read at depth + 1
    by the caller) -- when it is None, only the boundary is found (used
    while balance-matching an enclosing construct, so a nested occurrence is
    never extracted twice at the wrong depth)."""
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            return i + 1, True
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "`":
            content, j, ok = _scan_backtick_end(text, i + 1)
            if not ok:
                return n, False
            if out_nested is not None:
                out_nested.append(content)
            i = j
            continue
        if text.startswith("$((", i):
            i = _scan_arith_end(text, i + 3)
            continue
        if text.startswith("$(", i):
            content, j, ok = _scan_cmdsub_end(text, i + 2)
            if not ok:
                return n, False
            if out_nested is not None:
                out_nested.append(content)
            i = j
            continue
        i += 1
    return n, False


def _scan_cmdsub_end(text, i):
    """`i` is the index right after `$(`. Return (content, index_after_close,
    ok) where content is the text up to (excluding) the matching `)`. Quotes,
    nested command substitutions and backticks inside are tracked purely for
    balance -- their own content is never extracted here, only when the
    returned `content` is itself later read at depth + 1."""
    n = len(text)
    start = i
    depth = 1
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "'":
            end = text.find("'", i + 1)
            if end == -1:
                return None, n, False
            i = end + 1
            continue
        if ch == '"':
            j, ok = _scan_dquote(text, i + 1, None)
            if not ok:
                return None, n, False
            i = j
            continue
        if ch == "`":
            _, j, ok = _scan_backtick_end(text, i + 1)
            if not ok:
                return None, n, False
            i = j
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth -= 1
            i += 1
            if depth == 0:
                return text[start : i - 1], i, True
            continue
        i += 1
    return None, n, False


def _scan_backtick_end(text, i):
    """`i` is the index right after an opening backtick. Return (content,
    index_after_close, ok)."""
    n = len(text)
    start = i
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "`":
            return text[start:i], i + 1, True
        if ch == "'":
            end = text.find("'", i + 1)
            if end == -1:
                return None, n, False
            i = end + 1
            continue
        if ch == '"':
            j, ok = _scan_dquote(text, i + 1, None)
            if not ok:
                return None, n, False
            i = j
            continue
        i += 1
    return None, n, False


def _scan_arith_end(text, i):
    """`i` is the index right after `$((`. Arithmetic expansion is data, not
    a command substitution (task0001.md Design, "Reading one shell text").
    Return the index right after the matching `))`, or the text length when
    it never closes -- an unterminated arithmetic expansion is not one of
    the named undecidability triggers, so this never reports failure."""
    n = len(text)
    depth = 2
    while i < n:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n

_WORD_STOP_CHARS = set(" \t\n;&|(){}<>")


def _read_word_raw(text, i, out_nested):
    """Read one shell word starting at `i` (already known not to be
    whitespace, a comment start or an operator character). Return
    (raw_word, index_after_word, ok). `out_nested` collects the content of
    every command substitution / backtick encountered while reading, in
    unquoted or double-quoted context (never inside single quotes) -- FR3
    applies "whatever the command word is", so this happens for every word,
    not only ones at a command position."""
    n = len(text)
    start = i
    while i < n:
        ch = text[i]
        if ch in _WORD_STOP_CHARS:
            break
        if ch == "\\":
            if i + 1 < n:
                i += 2
                continue
            i += 1
            break
        if ch == "'":
            end = text.find("'", i + 1)
            if end == -1:
                return text[start:n], n, False
            i = end + 1
            continue
        if ch == '"':
            j, ok = _scan_dquote(text, i + 1, out_nested)
            if not ok:
                return text[start:n], n, False
            i = j
            continue
        if ch == "`":
            content, j, ok = _scan_backtick_end(text, i + 1)
            if not ok:
                return text[start:n], n, False
            out_nested.append(content)
            i = j
            continue
        if text.startswith("$((", i):
            i = _scan_arith_end(text, i + 3)
            continue
        if text.startswith("$(", i):
            content, j, ok = _scan_cmdsub_end(text, i + 2)
            if not ok:
                return text[start:n], n, False
            out_nested.append(content)
            i = j
            continue
        i += 1
    return text[start:i], i, True


_THREE_CHAR_OPS = ("<<-", "<<<")
_TWO_CHAR_OPS = ("&&", "||", "|&", "<<", ">>", ">&", "&>", ">|")

# Separators (task0001.md Design, "Command position"): a word right after
# one of these is at a command position. Redirection operators that merely
# contain `&` or `|` (`2>&1`, `&>`, `>|`) are deliberately excluded.
SEPARATOR_OPS = {";", "&", "&&", "||", "|", "|&"}


def _match_operator(text, i):
    """`text[i]` is one of `;&|(){}<>`. Return (op, length) for the longest
    operator starting there."""
    for op in _THREE_CHAR_OPS:
        if text.startswith(op, i):
            return op, len(op)
    for op in _TWO_CHAR_OPS:
        if text.startswith(op, i):
            return op, len(op)
    return text[i], 1

def _read_heredoc_delim(text, i):
    """`i` is the index right after a `<<` or `<<-` operator. Return
    (delimiter, index_after_delimiter, ok). The delimiter may be quoted or
    unquoted (task0001.md Design, "Reading one shell text", Heredocs)."""
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    if i >= n or text[i] in "\n;&|(){}<>":
        return None, i, False
    if text[i] in "'\"":
        q = text[i]
        end = text.find(q, i + 1)
        if end == -1:
            return None, n, False
        return text[i + 1 : end], end + 1, True
    start = i
    while i < n and text[i] not in " \t\n;&|(){}<>":
        i += 1
    delim = text[start:i].replace("\\", "")
    if not delim:
        return None, i, False
    return delim, i, True


def _read_heredoc_body(text, i, delim, dashed):
    """`i` is the index right after the newline that starts the body. Return
    (body, index_after_body, ok). `<<-` ignores leading tabs only when
    matching the delimiter line, per task0001.md Design; the extracted body
    itself is left exactly as written."""
    n = len(text)
    body_start = i
    while True:
        nl = text.find("\n", i)
        line_end = nl if nl != -1 else n
        line = text[i:line_end]
        cmp_line = line.lstrip("\t") if dashed else line
        if cmp_line == delim:
            body = text[body_start:i]
            new_i = line_end + 1 if nl != -1 else n
            return body, new_i, True
        if nl == -1:
            return text[body_start:n], n, False
        i = line_end + 1

def _literal_value(raw):
    """Return `raw` unchanged when it is a plain, unquoted, unescaped word
    (no quote, backslash, `$` or backtick anywhere in it), else None. Used
    for the while/until/reserved-word/`!` check (A7): a quoted or escaped
    spelling never counts, even when it would unescape to the same text."""
    if any(c in raw for c in "'\"\\$`"):
        return None
    return raw


def _literal_command_word(word):
    """Return the literal value of a word that may be fully single- or
    double-quoted (e.g. `'bash'`), or plain -- used for identity checks
    (shell name, A6 prefix name) where a whole-word quoting still resolves.
    None when the word is empty, partially quoted, or holds an expansion
    this reader does not model."""
    if not word:
        return None
    if len(word) >= 2 and word[0] == word[-1] and word[0] in "'\"":
        inner = word[1:-1]
        if word[0] == "'" and "'" not in inner:
            return inner
        if word[0] == '"' and not set(inner) & set('"\\$`'):
            return inner
        return None
    if set(word) & set("'\"\\$`"):
        return None
    return word


def _command_identity(word):
    """The basename used to compare a resolved word against SHELLS / eval /
    A6_PREFIXES (the shell-word comparison is explicitly "by last path
    segment" per task0001.md Design; applied uniformly here). None when the
    word's literal value cannot be determined."""
    literal = _literal_command_word(word)
    if literal is None:
        return None
    return literal.rsplit("/", 1)[-1]


def _is_assignment(word):
    return bool(_ASSIGN_RE.match(word))


def _verbatim_span(word, i):
    """`word[i:]` starts a command substitution or backtick. Return
    (verbatim_text, index_after) -- the span exactly as written, used by
    `_unquote_for_nested_text` to leave it untouched rather than resolve
    it (it is separately extracted, at the correct depth, wherever it was
    actually read as a word)."""
    n = len(word)
    if word.startswith("$(", i):
        _, j, ok = _scan_cmdsub_end(word, i + 2)
        if not ok:
            j = n
        return word[i:j], j
    _, j, ok = _scan_backtick_end(word, i + 1)
    if not ok:
        j = n
    return word[i:j], j


def _unquote_for_nested_text(word):
    """Strip quoting from a raw word to the literal text the destination
    shell would receive: single-quoted content verbatim, double-quoted
    content with its escapes resolved, backslash escapes outside quotes
    resolved -- while `$...` expansions (parameter, command substitution,
    arithmetic, backticks) are left exactly as written, since they cannot be
    resolved statically (task0001.md Design, "-c string"). None when a quote
    never closes."""
    out = []
    i = 0
    n = len(word)
    while i < n:
        ch = word[i]
        if ch == "'":
            end = word.find("'", i + 1)
            if end == -1:
                return None
            out.append(word[i + 1 : end])
            i = end + 1
            continue
        if ch == '"':
            i += 1
            closed = False
            while i < n:
                c = word[i]
                if c == '"':
                    i += 1
                    closed = True
                    break
                if c == "\\" and i + 1 < n:
                    out.append(word[i + 1])
                    i += 2
                    continue
                if c == "`" or word.startswith("$(", i):
                    span, i = _verbatim_span(word, i)
                    out.append(span)
                    continue
                out.append(c)
                i += 1
            if not closed:
                return None
            continue
        if ch == "\\" and i + 1 < n:
            out.append(word[i + 1])
            i += 2
            continue
        if ch == "`" or word.startswith("$(", i):
            span, i = _verbatim_span(word, i)
            out.append(span)
            continue
        out.append(ch)
        i += 1
    return "".join(out)

def _handle_shell_invocation(rest, heredocs, herestrings, out_nested):
    """`rest` is the word list right after a resolved bash/sh/zsh command
    word. Append the `-c` string (when present), every heredoc body and
    every herestring word attached to this simple command to `out_nested`
    (task0001.md Design, "Nested texts", "Shell commands")."""
    j = 0
    n = len(rest)
    c_operand_index = None
    while j < n:
        w = rest[j]
        if w == "--":
            j += 1
            break
        if w in ("--rcfile", "--init-file"):
            j += 2
            continue
        if not (w.startswith("-") or w.startswith("+")) or len(w) < 2:
            break
        if w.startswith("--"):
            j += 1
            continue
        letters = w[1:]
        if "c" in letters:
            c_operand_index = j + 1
            break
        j += 1
        if letters[-1:] in ("o", "O"):
            j += 1
    if c_operand_index is not None and c_operand_index < len(rest):
        operand = _unquote_for_nested_text(rest[c_operand_index])
        if operand is not None:
            out_nested.append(operand)
    for body in heredocs:
        out_nested.append(body)
    for hs in herestrings:
        unquoted = _unquote_for_nested_text(hs)
        if unquoted is not None:
            out_nested.append(unquoted)


# task0002.md "Prefix option table": the options, per A6 prefix, that take a
# value. A prefix absent here (nohup, setsid, command, time) has no
# value-taking option -- every `-x` word of theirs is skipped whole, as
# before this task.
PREFIX_VALUE_OPTIONS = {
    "env": (frozenset("uCS"), frozenset({"unset", "chdir", "split-string"})),
    "nice": (frozenset("n"), frozenset({"adjustment"})),
    "timeout": (frozenset("sk"), frozenset({"signal", "kill-after"})),
    "exec": (frozenset("a"), frozenset()),
    "stdbuf": (frozenset("ioe"), frozenset({"input", "output", "error"})),
}


def _skip_prefix_options(prefix, words, i):
    """Advance `i` past this one A6 prefix command's own options
    (task0002.md, "Skipping one prefix command"). A value-taking option --
    per `PREFIX_VALUE_OPTIONS` -- consumes its value: the rest of an attached
    word (`-uX`, `-n5`) when non-empty, else the following word whole,
    whatever it looks like (never re-examined as another option, prefix or
    the command word; `env -u bash`, `nice -n -5`). `--name=value` is one
    complete option; a bare `--name` in the table's long column consumes the
    next word; `--` ends this prefix's options and is itself consumed. Any
    other `-`-led word takes no value. Returns the index of the first word
    this prefix does not claim (== len(words) when the words run out while a
    value is still owed, leaving no executed command word for this simple
    command)."""
    n = len(words)
    short_opts, long_opts = PREFIX_VALUE_OPTIONS.get(prefix, (frozenset(), frozenset()))
    while i < n:
        w = words[i]
        if w == "--":
            return i + 1
        if not w.startswith("-"):
            break
        if w.startswith("--"):
            name = w[2:]
            i += 1
            if "=" not in name and name in long_opts and i < n:
                i += 1
            continue
        letters = w[1:]
        i += 1
        for idx, ch in enumerate(letters):
            if ch in short_opts:
                if not letters[idx + 1 :] and i < n:
                    i += 1
                break
        continue
    return i


def _analyze_simple_command(words, heredocs, herestrings, out_nested):
    """`words` is the raw word list of one simple command (command word plus
    arguments, in order). Skip leading NAME=value assignments and any chain
    of A6_PREFIXES with their options (task0001.md Design, "Nested texts";
    task0002.md, "Skipping one prefix command"), then dispatch on the
    resolved command word."""
    i = 0
    n = len(words)
    while i < n and _is_assignment(words[i]):
        i += 1
    while i < n:
        base = _command_identity(words[i])
        if base not in A6_PREFIXES:
            break
        prefix = base
        i += 1
        if prefix == "env":
            # env's NAME=value operands may be interleaved with its options
            # in any order (unchanged from before this task); each cycle
            # skips one assignment, then everything `_skip_prefix_options`
            # can claim.
            while i < n:
                if _is_assignment(words[i]):
                    i += 1
                    continue
                new_i = _skip_prefix_options(prefix, words, i)
                if new_i == i:
                    break
                i = new_i
        elif prefix == "timeout":
            i = _skip_prefix_options(prefix, words, i)
            if i < n:
                i += 1
        else:
            i = _skip_prefix_options(prefix, words, i)
        while i < n and _is_assignment(words[i]):
            i += 1
    if i >= n:
        return
    base = _command_identity(words[i])
    rest = words[i + 1 :]
    if base in SHELLS:
        _handle_shell_invocation(rest, heredocs, herestrings, out_nested)
    elif base == "eval":
        parts = []
        for w in rest:
            unquoted = _unquote_for_nested_text(w)
            if unquoted is not None:
                parts.append(unquoted)
        if parts:
            out_nested.append(" ".join(parts))

def _scan(text, out_nested):
    """Read `text` once at its own depth. Return (found, undecidable).
    `found` is True when a `while` / `until` literal stands at a command
    position anywhere in `text` itself (not counting nested texts, which the
    caller reads separately at depth + 1 via `out_nested`). `undecidable` is
    True on an unterminated quote, heredoc, command substitution or
    backtick, or a heredoc operator with no delimiter -- the caller ignores
    `found` entirely when this is True (task0001.md Design, FR8)."""
    n = len(text)
    i = 0
    found = False
    cmd_pos = True
    cur_words = []
    cur_heredocs = []
    cur_herestrings = []
    pending = []  # [(delim, dashed, owner_heredocs_list), ...]
    # Simple commands are recorded here, not analyzed immediately: a heredoc
    # registered against a command is only resolved at the FOLLOWING
    # newline, which can come after this command has already been finalized
    # by a mid-line separator (`cmd <<EOF; next`). `heredocs`/`herestrings`
    # are the actual list objects `cur_heredocs`/`cur_herestrings` were
    # bound to at finalize time, so later appends to them (once bodies
    # resolve) are still visible when every record is analyzed at the end.
    pending_records = []

    def finalize():
        if cur_words:
            pending_records.append((cur_words, cur_heredocs, cur_herestrings))

    while i < n:
        ch = text[i]

        if ch in " \t":
            i += 1
            continue

        if ch == "\\" and i + 1 < n and text[i + 1] == "\n":
            i += 2
            continue

        if ch == "\n":
            finalize()
            cur_words = []
            cur_heredocs = []
            cur_herestrings = []
            i += 1
            if pending:
                for delim, dashed, owner in pending:
                    body, i, ok = _read_heredoc_body(text, i, delim, dashed)
                    if not ok:
                        return False, True
                    owner.append(body)
                pending = []
            cmd_pos = True
            continue

        if ch == "#":
            nl = text.find("\n", i)
            i = nl if nl != -1 else n
            continue

        if ch in ";&|(){}<>":
            op, oplen = _match_operator(text, i)
            if op in SEPARATOR_OPS or op in ("(", "{", ")", "}"):
                finalize()
                cur_words = []
                cur_heredocs = []
                cur_herestrings = []
            if op in SEPARATOR_OPS or op in ("(", "{"):
                cmd_pos = True
            elif op in (")", "}"):
                cmd_pos = False
            elif op in ("<<", "<<-"):
                dashed = op == "<<-"
                delim, j, ok = _read_heredoc_delim(text, i + oplen)
                if not ok:
                    return False, True
                pending.append((delim, dashed, cur_heredocs))
                i = j
                continue
            elif op == "<<<":
                k = i + oplen
                while k < n and text[k] in " \t":
                    k += 1
                word, j, ok = _read_word_raw(text, k, out_nested)
                if not ok:
                    return False, True
                cur_herestrings.append(word)
                i = j
                continue
            i += oplen
            continue

        word_raw, j, ok = _read_word_raw(text, i, out_nested)
        if not ok:
            return False, True
        if cmd_pos:
            literal = _literal_value(word_raw)
            if literal in RESERVED_CHAIN or literal == "!":
                i = j
                continue
            if literal in ("while", "until"):
                found = True
            cur_words = [word_raw]
            cmd_pos = False
        else:
            cur_words.append(word_raw)
        i = j

    finalize()
    if pending:
        return False, True
    for words, heredocs, herestrings in pending_records:
        _analyze_simple_command(words, heredocs, herestrings, out_nested)
    return found, False


def read_shell_text(text, depth):
    """Decide whether `text`, read as a shell text at `depth`, contains a
    while / until loop at a command position -- in the text itself, or in
    any shell text it hands to another shell (nested texts are read at
    depth + 1, recursively, up to MAX_NESTING_DEPTH). Always returns a
    plain bool: an undecidable text, or one beyond the maximum depth,
    contributes no finding (task0001.md Design)."""
    if depth > MAX_NESTING_DEPTH:
        return False
    out_nested = []
    found, undecidable = _scan(text, out_nested)
    if undecidable:
        return False
    if found:
        return True
    for nested in out_nested:
        if read_shell_text(nested, depth + 1):
            return True
    return False

def deny():
    reason = (
        "[loop-command-guard] while / until ループを含むコマンドは実行できない。"
        "終わらないループは無人実行のハングにつながる。"
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT_NAME,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return
    try:
        hit = read_shell_text(command, 0)
    except Exception:
        return
    if hit:
        deny()


if __name__ == "__main__":
    main()
    sys.exit(0)

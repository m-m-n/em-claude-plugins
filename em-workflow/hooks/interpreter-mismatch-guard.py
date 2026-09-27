#!/usr/bin/env python3
"""PreToolUse(Bash) guard against running a non-shell script through a shell.

`bash foo.py` makes bash read the Python file line by line as shell
commands. Most lines fail harmlessly with "command not found", but a line
that happens to name a real program runs that program. The reproduction
that motivated this guard: `bash validate-worker-output.py --help` reached
`import argparse`, which started ImageMagick's `import` -- a screen-capture
tool that waits for a mouse click. The Bash call went to the background on
timeout, and claude-batch then waited on that background shell for hours.

Decision flow:

  1. Read stdin, parse as one JSON object. Any failure -> no output.
  2. tool_name must be exactly "Bash" and tool_input.command a non-empty
     string. Otherwise -> no output.
  3. Drop heredoc bodies, split the command into simple commands, and find
     each one whose command word (after env assignments and wrappers) is a
     shell (`bash` / `sh` / `zsh` / `dash` / `ksh`) or `source` / `.`.
  4. Take the script operand. Nothing is decided when there is none
     (`bash -c ...`, `bash -s`, stdin, `--version`), when it contains an
     expansion or glob, or when it does not name a readable regular file.
  5. Read the file's first line. A shebang naming a non-shell interpreter
     -> deny. No shebang, but an extension of a known non-shell language
     -> deny. Anything else -> no output.
  6. Anything unexpected anywhere above -> no output, exit status 0.

The guard only ever denies, and only when it has read the target file and
found evidence that it is not a shell script. Every undecidable case falls
through to the other hooks, so a misreading costs at most a missed
detection, never a stalled run.

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import json
import os
import shlex
import sys

HOOK_EVENT_NAME = "PreToolUse"

SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "ash", "mksh"}
SOURCE_WORDS = {"source", "."}

# Prefix words that run the next word as the command. Only flag-free use is
# followed; a wrapper with options ends the search (undecidable).
WRAPPERS = {"env", "sudo", "nohup", "time", "command", "nice", "exec", "doas"}

# Shell options that consume the following word as their value.
VALUE_OPTIONS = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}

# Non-shell interpreters, keyed by the name a shebang resolves to. Versioned
# names (python3.12, node22) are matched by prefix.
INTERPRETER_PREFIXES = {
    "python": "python3",
    "node": "node",
    "deno": "deno run",
    "bun": "bun",
    "ruby": "ruby",
    "perl": "perl",
    "php": "php",
    "lua": "lua",
    "Rscript": "Rscript",
    "tsx": "tsx",
    "ts-node": "ts-node",
    "uv": "uv run",
}

# Extensions used only when the file has no shebang.
EXTENSION_RUNNERS = {
    ".py": "python3",
    ".js": "node",
    ".mjs": "node",
    ".cjs": "node",
    ".ts": "tsx",
    ".rb": "ruby",
    ".pl": "perl",
    ".php": "php",
    ".lua": "lua",
}

# Characters the lexer splits out as operators. A run made only of these,
# without `<` or `>`, ends a simple command.
PUNCTUATION = ";&|()<>\n"


class _Undecidable(Exception):
    pass


def strip_heredoc_bodies(command):
    """Return `command` with every heredoc body removed, so text inside a
    body is never read as a command. Raises _Undecidable on an unterminated
    quote or heredoc."""
    out = []
    i = 0
    n = len(command)
    in_squote = in_dquote = False
    pending = []
    while i < n:
        ch = command[i]
        if in_squote:
            out.append(ch)
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if in_dquote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(command[i + 1])
                i += 2
                continue
            if ch == '"':
                in_dquote = False
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            out.append(command[i : i + 2])
            i += 2
            continue
        if ch == "'":
            in_squote = True
        elif ch == '"':
            in_dquote = True
        elif ch == "<" and command.startswith("<<", i) and not command.startswith("<<<", i):
            k = i + 2
            dashed = k < n and command[k] == "-"
            if dashed:
                k += 1
            while k < n and command[k] in " \t":
                k += 1
            start = k
            if k < n and command[k] in "'\"":
                end = command.find(command[k], k + 1)
                if end == -1:
                    raise _Undecidable("heredoc delimiter")
                delim = command[k + 1 : end]
                k = end + 1
            else:
                while k < n and command[k] not in " \t\n;&|<>()":
                    k += 1
                delim = command[start:k].replace("\\", "")
            if not delim:
                raise _Undecidable("heredoc delimiter")
            pending.append((delim, dashed))
            out.append(command[i:k])
            i = k
            continue
        elif ch == "\n" and pending:
            out.append(ch)
            i += 1
            for delim, dashed in pending:
                while True:
                    nl = command.find("\n", i)
                    end = nl if nl != -1 else n
                    line = command[i:end]
                    if (line.lstrip("\t") if dashed else line) == delim:
                        i = end + 1 if nl != -1 else n
                        break
                    if nl == -1:
                        raise _Undecidable("heredoc body")
                    i = end + 1
            pending = []
            continue
        out.append(ch)
        i += 1
    if in_squote or in_dquote or pending:
        raise _Undecidable("unterminated")
    return "".join(out)


def simple_commands(command):
    """Yield each simple command as a list of raw words. Quotes are kept so
    an expansion inside a quoted word stays visible to unquote()."""
    lexer = shlex.shlex(command, posix=False, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t"
    lexer.whitespace_split = True
    lexer.commenters = ""
    current = []
    in_comment = False
    try:
        for tok in lexer:
            is_punct = set(tok) <= set(PUNCTUATION)
            if in_comment:
                if is_punct and "\n" in tok:
                    in_comment = False
                continue
            if tok.startswith("#"):
                in_comment = True
            if in_comment or (is_punct and not set(tok) & set("<>")):
                if current:
                    yield current
                current = []
                continue
            current.append(tok)
    except ValueError as exc:
        raise _Undecidable(str(exc))
    if current:
        yield current


def drop_redirects(words):
    """Remove redirection operators and their targets. `2>&1` lexes as
    `2`, `>&`, `1`; the leftover digits are harmless because only the first
    operand after the options is read."""
    kept = []
    skip = False
    for w in words:
        if skip:
            skip = False
            continue
        if set(w) <= set("<>&"):
            skip = True
            continue
        kept.append(w)
    return kept


def unquote(word):
    """Return the literal value of `word`, or None when it holds an
    expansion, a glob, or quoting this reader does not model."""
    if len(word) >= 2 and word[0] == word[-1] and word[0] in "'\"":
        inner = word[1:-1]
        if word[0] == "'" and "'" not in inner:
            return inner
        if word[0] == '"' and not set(inner) & set('"\\$`'):
            return inner
        return None
    if set(word) & set("'\"\\$`*?["):
        return None
    if word.startswith("~"):
        return os.path.expanduser(word) if word.startswith("~/") else None
    return word


def script_operand(words):
    """Return (shell_word, script_path) for a shell / source invocation that
    reads a script file, or None when there is none or it cannot be settled."""
    i = 0
    while i < len(words) and "=" in words[i] and words[i].split("=", 1)[0].isidentifier():
        i += 1
    while i < len(words) and os.path.basename(words[i]) in WRAPPERS:
        if i + 1 < len(words) and words[i + 1].startswith("-"):
            return None
        i += 1
        while i < len(words) and "=" in words[i] and words[i].split("=", 1)[0].isidentifier():
            i += 1
    if i >= len(words):
        return None
    word = os.path.basename(unquote(words[i]) or "")
    args = words[i + 1 :]
    if word in SOURCE_WORDS:
        return (word, unquote(args[0])) if args else None
    if word not in SHELLS:
        return None
    j = 0
    while j < len(args):
        a = args[j]
        if a == "--":
            j += 1
            break
        if a in VALUE_OPTIONS:
            j += 2
            continue
        if a.startswith("--"):
            j += 1
            continue
        if a.startswith(("-", "+")) and len(a) > 1:
            # -c takes the script from the argument, -s from stdin.
            if "c" in a[1:] or "s" in a[1:]:
                return None
            j += 1
            continue
        break
    if j >= len(args):
        return None
    return word, unquote(args[j])


def resolve(path, cwd):
    if not os.path.isabs(path):
        path = os.path.join(cwd or os.getcwd(), path)
    if not os.path.isfile(path):
        return None
    return path


def interpreter_of(path):
    """Return (kind, runner) where kind names the evidence, or None when the
    file looks like a shell script or cannot be judged."""
    try:
        with open(path, "rb") as f:
            head = f.read(256)
    except OSError:
        return None
    if head.startswith(b"#!"):
        line = head[2:].split(b"\n", 1)[0].decode("utf-8", "replace").split()
        if not line:
            return None
        name = os.path.basename(line[0])
        if name == "env":
            rest = [p for p in line[1:] if not p.startswith("-") and "=" not in p]
            if not rest:
                return None
            name = os.path.basename(rest[0])
        if name in SHELLS:
            return None
        for prefix, runner in INTERPRETER_PREFIXES.items():
            if name.startswith(prefix):
                return f"shebang が `{name}`", name if runner == "python3" else runner
        return None
    ext = os.path.splitext(path)[1].lower()
    runner = EXTENSION_RUNNERS.get(ext)
    if runner:
        return f"拡張子が `{ext}`", runner
    return None


def find_mismatch(command, cwd):
    for words in simple_commands(strip_heredoc_bodies(command)):
        found = script_operand(drop_redirects(words))
        if not found or not found[1]:
            continue
        shell, target = found
        path = resolve(target, cwd)
        if not path:
            continue
        evidence = interpreter_of(path)
        if evidence:
            return (shell, target) + evidence
    return None


def deny(shell, target, evidence, runner):
    reason = (
        f"[interpreter-mismatch-guard] `{target}` はシェルスクリプトではない（{evidence}）。"
        f"`{shell}` で実行すると各行がシェルのコマンドとして解釈され、"
        f"たまたま実在するコマンド名の行（例: Python の `import` は ImageMagick の画面取り込み）"
        f"が起動してハングする。`{runner} {target}` のように本来のインタプリタで実行する。"
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
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    try:
        hit = find_mismatch(command, cwd)
    except Exception:
        return
    if hit:
        deny(*hit)


if __name__ == "__main__":
    main()
    sys.exit(0)

#!/usr/bin/env python3
"""PreToolUse(Bash) guard for destructive commands.

Two jobs, in this order:

1. **Block what is genuinely destructive.** A static blocklist over the
   command string — git history/worktree destruction, recursive deletes,
   safety-guard removal, irreversible external operations, and writes to
   Claude Code's own config. Decisions are deterministic: the same command
   always gets the same answer.

2. **Allow everything else outright.** Emitting `permissionDecision: "allow"`
   makes Claude Code skip the auto mode classifier entirely for that command
   (the binary logs `Skipping auto mode classifier for Bash` on this path).
   That is the point of this hook: the classifier is an LLM judged fresh on
   every call, with a measured false-positive rate around 0.2-0.8%, and each
   false positive stalls an unattended run. One `commit-docs.sh` invocation
   was allowed 251 times and denied twice in the same repository; a denial
   pair once froze a claude-batch run for eleven hours.

**The trade-off is real and deliberate.** Turning the classifier off for Bash
trades an adaptive judge for a fixed list. A destructive pattern this file
does not know about now sails through where the classifier might have caught
it — that already happened once in this account's history, when the
classifier stopped a `gcloud projects add-iam-policy-binding` that no
hand-written list here anticipated. The cloud/IaC section below exists to
narrow that gap, not to close it. Set ALLOW_NON_DESTRUCTIVE to False to keep
the blocking half and hand undecided commands back to the classifier.

A hook decision also outranks `permissions.deny` rules in settings.json, so
a deny rule added later will not fire for a command this hook allows.

Decision tiers:

  deny  — destructive and statically certain
  ask   — destructive shape whose blast radius cannot be resolved statically
          (demoted to deny in an unattended run, same as kill-guard)
  allow — everything else, when ALLOW_NON_DESTRUCTIVE is on

Process termination (kill / pkill / killall) is NOT handled here — that is
kill-guard.py's job, and it runs as a separate PreToolUse hook.

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import itertools
import json
import os
import re
import shlex
import shutil
import sys

# When True, a command that matches no rule below is allowed outright, which
# skips the auto mode classifier. See the module docstring for the trade-off.
ALLOW_NON_DESTRUCTIVE = True

# Set by claude-batch on the claude process it launches; hooks inherit it.
BATCH_ENV = "CLAUDE_BATCH"
BATCH_OFF = ("", "0", "false", "no")

# Statement separators after which a new command word can begin. Command
# substitutions are deliberately NOT split here — their bodies are scanned
# separately so a destructive call hidden inside one is still seen.
# The regex is the fallback path only; see lex_segments().
SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|&\n])")
SEGMENT_CHARS = frozenset(";|&\n")
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")

# What a command substitution is flattened to before lexing (statements()),
# in place of a bare space. A bare space erases all evidence that the
# flattened text ever held a substitution, so an assignment whose value was
# `$(mktemp -d)` looked exactly like a literal empty string once lexed — the
# false-positive half of task0003's item D. This placeholder keeps that
# evidence alive: it fuses onto adjacent text as one shlex word (no
# whitespace of its own, so `X=$(mktemp -d)` still lexes as the single token
# `X=${DYNAMIC-SUBSTITUTION}` that a bare NAME=VALUE assignment needs to be
# collected at all) and it already matches the DYNAMIC pattern the
# resolution and judgment layers use everywhere else, so a value carrying it
# can never be mistaken for a literal. The hyphen keeps it from ALSO
# matching VAR_REF (which requires an identifier with no hyphen), so it is
# never mistaken for a reference to a real variable named DYNAMIC.
DYNAMIC_PLACEHOLDER = "${DYNAMIC-SUBSTITUTION}"

# Characters shlex should emit as operator tokens of their own. The default
# set plus `\n`, which has to be removed from the whitespace set to survive
# as a separator — a newline ends a statement just as `;` does.
PUNCTUATION = "();<>|&\n"

# Redirection operators, matched against a whole token. A redirect and its
# target are not arguments to the command and must be lifted out before the
# checks run, or `>` and `/dev/null` read as two more paths to delete.
REDIRECT = re.compile(r"\d*(?:>>?\|?|<<?<?|<>|>&|<&|&>>?)\d*")

# `<>` opens its target for both reading and writing (unlike `<`, `<<`,
# `<<<`, which are read-only) and must join the write-target set.
READWRITE_REDIRECT = re.compile(r"\d*<>\d*")

# A here-document and its body, up to the line bearing the delimiter.
HEREDOC = re.compile(
    r"<<-?(?!<)[ \t]*(['\"]?)(\w+)\1[^\n]*\n(.*?)^[ \t]*\2[ \t]*$",
    re.S | re.M,
)
# Commands that run what arrives on stdin, so a here-doc body aimed at one is
# not data but code, and has to be scanned like any other statement.
SHELL_SINK = re.compile(r"\b(sh|bash|zsh|dash|ksh|python\d?|perl|ruby|node)\b")

# Shell words whose `-c` argument, or a here-string (`<<<`) redirected into
# them, is a script the shell executes rather than ordinary data. `eval` gets
# the same treatment separately in extract_shell_payload() — it takes no
# `-c`, its own arguments ARE the script.
SHELL_WORDS = {"sh", "bash", "zsh", "dash", "ksh"}

# Hard cap on how many `-c`/`eval`/here-string payloads statements() will
# unpack and re-scan for one command, so a deliberately or accidentally
# nested chain (`bash -c 'bash -c "bash -c ..."'`) cannot make this loop run
# unbounded.
MAX_SHELL_PAYLOAD_EXPANSIONS = 25

# Wrapper commands that prefix the real one. `mise exec -- gcloud …` and
# `sudo rm -rf …` must be judged on the wrapped command, not the wrapper.
WRAPPERS = {"sudo", "env", "nohup", "time", "command", "nice", "ionice", "doas"}

# Wrapper options that take a value of their own (a separate token), keyed by
# wrapper name. Without consuming these, the value token is mistaken for the
# wrapped command word (`env -u NAME cp …` would read `NAME` as the command).
# `--flag=value` spellings are attached and need no extra consumption.
WRAPPER_VALUE_FLAGS = {
    "sudo": {
        "-u", "-g", "-p", "-C", "-h", "-R", "-T", "-U", "-D", "-r", "-t",
        "--user", "--group", "--prompt", "--close-from", "--host",
        "--chroot", "--type", "--other-user", "--role", "--chdir",
    },
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata", "--pid"},
    "time": {"-o", "--output"},
    "doas": {"-u", "-C"},
    "command": set(),
    "nohup": set(),
}

# A token whose value cannot be resolved by reading the command alone.
DYNAMIC = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]|\*|\?|\[")

# Env-var and flag names whose spelling is the author's own warning label.
BYPASS_TOKEN = re.compile(
    r"(?i)(^|[^A-Z0-9_])(DANGEROUSLY_\w+|BREAKGLASS\w*|\w*_BYPASS_\w*|\w*_UNSAFE\w*"
    r"|I_KNOW_WHAT_IM_DOING)($|[^A-Z0-9_])"
)
BYPASS_FLAGS = {
    "--dangerously-skip-permissions",
    "--insecure",
    "--allow-unsafe",
    "--allow-unsafe-eval",
    "--no-sandbox",
    "--disable-web-security",
}

# Deletion targets safe enough to wave through even under `rm -rf`: the
# scratch roots and build output that get recreated as a matter of course.
SAFE_DELETE = re.compile(
    r"^(?:\./)?(?:/tmp/|/var/tmp/|node_modules|dist|build|target|\.next|coverage|"
    r"tmp/|\.cache/)"
)

# Claude Code's own configuration. A write here changes how the agent itself
# is permitted to act, so it needs the user in the loop.
SELF_CONFIG = re.compile(
    r"(?:^|[\"'\s=])(?:~|\$HOME|/home/[^/\s]+)/\.claude/"
    r"(?:settings[^/\s]*\.json|(?:hooks|rules|agents|skills|commands|"
    r"output-styles|workflows|routines)(?:/|$)|scheduled_tasks\.json)"
)
# Session transcripts. Reading them is routine; writing them is not.
TRANSCRIPT = re.compile(r"\.claude/projects/[^\s\"']*\.jsonl")
# Commands that write to a path given as an argument rather than via `>`.
INPLACE_WRITERS = {"tee", "truncate", "shred", "install", "patch"}

# The target-directory flag `cp`/`mv`/`ln`/`install` accept, in both spellings
# GNU coreutils allows: a separate token (`-t DIR`) and the attached-`=` form
# (`--target-directory=DIR`). Its value is a destination even though it is
# not the last positional argument.
TARGET_DIR_FLAGS = ("-t", "--target-directory")

# Flags through which a command receives its write destination instead of a
# bare positional argument. Keys are command words; values are the flag
# spellings (separate token or, where the command supports it, `=`-attached)
# whose value is the destination.
FLAG_DEST_FLAGS = {
    "tar": ("-C", "--directory"),
    "unzip": ("-d",),
    "curl": ("-o", "--output"),
    "wget": ("-O", "--output-document"),
}

# Short options of cp/ln that take a value token of their own. Their value
# must not be mistaken for the trailing positional destination when scanning
# non-flag arguments (`cp /tmp/foo ~/.claude/settings.json -S .bak` — `.bak`
# is `-S`'s value, not the destination).
VALUE_TAKING_FLAGS = {
    "cp": ("-S", "--suffix", "-t", "--target-directory"),
    "ln": ("-S", "--suffix"),
    "install": (
        "-m", "--mode", "-o", "--owner", "-g", "--group",
        "-S", "--suffix", "-t", "--target-directory",
    ),
    "rsync": ("--exclude", "--include", "--filter", "-e", "--rsh"),
}

# Process-termination command words. These belong to kill-guard.py, which
# runs as its own PreToolUse hook and reaches a deny/ask/allow decision from
# the live process tree. This hook must not answer for them at all: its
# blanket `allow` at the end of main() would otherwise override kill-guard's
# deny for a command like `pkill -f emterm`, reinstating exactly the incident
# kill-guard exists to prevent.
KILL_WORDS = ("kill", "pkill", "killall")

# em-workflow's exit-4 recovery resyncs an integration worktree to its own
# branch tip (references/phase-state.md). It is a `reset --hard`, but the
# target is the branch the worktree already tracks, so nothing is lost.
EM_WORKFLOW_REF = re.compile(r"^em-workflow/[a-z0-9][a-z0-9-]*/integration$")


def unattended():
    """True when this session runs under claude-batch with nobody watching."""
    return os.environ.get(BATCH_ENV, "").strip().lower() not in BATCH_OFF


def decide(decision, rule, reason):
    """Emit a PreToolUse permission decision and stop."""
    if decision == "ask" and unattended():
        decision = "deny"
        reason = (
            f"{reason}\n"
            f"無人実行（claude-batch）のため確認を取れないので、`ask` を `deny` に降格した。"
            f"対象を静的に確定できる形に書き換えて続行する。"
        )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": (
                    f"[destructive-guard] {reason}"
                    if rule is None
                    else f"[destructive-guard/{rule}] {reason}"
                ),
            }
        },
        sys.stdout,
    )
    sys.exit(0)


class Tok(str):
    """A token string that also remembers whether shlex read it from bare,
    unquoted operator syntax (`>`, `2>&1`, …) rather than from a word or
    quoted span. Every consumer besides split_redirects() treats it as an
    ordinary str; the attribute defaults to False so a plain str used where
    a Tok is expected (there is no such caller today) fails closed.
    """

    is_operator = False

    def __new__(cls, value, is_operator=False):
        obj = str.__new__(cls, value)
        obj.is_operator = is_operator
        return obj


class _TrackingLexer(shlex.shlex):
    """shlex.shlex that also records whether the token `get_token()` just
    returned began in the base class's punctuation state ('c') — i.e. bare,
    unquoted operator syntax — as opposed to a word or quoted span.

    shlex resolves quoting before the token text ever reaches a caller, so a
    quoted `"2>&1"` and a real, unquoted `2>&1` come out as the identical
    string. `state` is overridden as a property purely to observe every
    assignment the base class's `read_token()` already makes; no parsing
    behaviour changes.
    """

    def __init__(self, *args, **kwargs):
        self.last_was_operator = False
        super().__init__(*args, **kwargs)

    @property
    def state(self):
        return self.__dict__.get("_state", " ")

    @state.setter
    def state(self, value):
        self.__dict__["_state"] = value
        if value == "c":
            self.last_was_operator = True

    def read_token(self):
        self.last_was_operator = False
        return super().read_token()


def lex_segments(chunk, base_scope, next_scope):
    """Split a chunk into statements, each returned as
    (tokens, lexed, scope, conditional).

    Separators only count when they sit OUTSIDE quotes, and telling those
    apart is the whole reason shlex does the splitting rather than a regex.
    `echo 'a; rm -rf /x'` is one statement headed by `echo`; a quote-blind
    split reads it as two and finds a recursive delete in the second, which
    denied a command that deletes nothing. Literal command text like that
    shows up constantly in generated docs, tests, and commit messages.

    LEXED is True on this path: each returned token is a Tok, carrying (as
    `.is_operator`) whether shlex read it from bare operator syntax or from
    a word/quoted span — the signal split_redirects() needs to tell a real
    `>` apart from a quoted string that merely looks like one.

    SCOPE is the resolution layer's identity for the statement (see
    collect_assignments()/resolve_target()): BASE_SCOPE for everything at
    this chunk's own nesting level, a fresh id from NEXT_SCOPE() for a
    subshell group (delimited by a bare `(` ... `)` pair — the parentheses
    themselves are delimiters, never statement tokens, so their boundary is
    tracked by counting occurrences across the token stream rather than by
    testing whether a statement's first or last token happens to BE a
    parenthesis; a closing paren fused with a redirect operator still closes
    the group), and a fresh id for EVERY element of a pipeline (`|`, never
    the sequential `||` — the element before the first `|` included) and for
    a statement terminated as a background job (`&`, never `&&`). This never
    changes which statements are produced or their order (NFR6) — it only
    tags each one.

    CONDITIONAL is True when the statement was introduced by a conditional
    separator (`&&` or `||`) — item A.2 of the resolution layer's design: an
    assignment reached only through a short-circuit that may not run is
    never applicable. A statement introduced by a sequential separator
    (`;`, newline, `|`, `&`) or by the start of its own scope is
    unconditional (False).

    Falls back to the regex split when the chunk will not parse — an
    unbalanced quote, usually. That path keeps the old false positives and
    returns LEXED False, since per-token provenance is unavailable there; a
    parse failure is rare, and waving the chunk through unexamined would be
    a hole rather than a nuisance. Per the resolution layer's fail-closed
    rule, every statement on this path gets its OWN fresh scope — not even
    shared with siblings in the same fallback batch — so nothing resolves
    across, or within, it. CONDITIONAL is irrelevant there (LEXED False
    already excludes these statements from collection).
    """
    try:
        lex = _TrackingLexer(chunk, posix=True, punctuation_chars=PUNCTUATION)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        toks = []
        while True:
            raw = lex.get_token()
            if raw is None or raw == lex.eof:
                break
            toks.append(Tok(raw, lex.last_was_operator))
    except ValueError:
        return [
            (tokens(seg), False, next_scope(), False)
            for seg in SEGMENT_SPLIT.split(chunk) if seg.strip()
        ]

    out, current = [], []
    scope_stack = [base_scope]
    current_scope = base_scope
    pending_conditional = False

    def flush(sep_text):
        nonlocal current, current_scope, pending_conditional
        scope = current_scope
        if sep_text in ("|", "&"):
            # This statement precedes a pipe, or is itself backgrounded: it
            # runs in a shell of its own (item C), so it gets an identity
            # distinct from whatever it shares current_scope with today.
            scope = next_scope()
        out.append((current, True, scope, pending_conditional))
        # A lone `|` is a real pipe — each side runs in its own subshell in
        # the shell this hook is modeling, so the statement after it starts
        # a fresh scope too. `||` is sequential control flow (like `&&`/`;`)
        # and must NOT trigger this. A background job (`&`) isolates only
        # the statement it terminates; execution continues in the SAME
        # enclosing scope afterward, so current_scope is left untouched.
        current_scope = next_scope() if sep_text == "|" else scope_stack[-1]
        pending_conditional = sep_text in ("&&", "||")
        current = []

    def open_paren():
        nonlocal current, current_scope, pending_conditional
        if current:
            out.append((current, True, current_scope, pending_conditional))
            current = []
        new_id = next_scope()
        scope_stack.append(new_id)
        current_scope = new_id
        pending_conditional = False

    def close_paren():
        nonlocal current, current_scope, pending_conditional
        if current:
            out.append((current, True, current_scope, pending_conditional))
            current = []
        if len(scope_stack) > 1:
            scope_stack.pop()
        current_scope = scope_stack[-1]
        pending_conditional = False

    for t in toks:
        # punctuation_chars makes shlex fuse adjacent punctuation into one
        # token, so a separator with no space before the next operator
        # (';>', '\n(') arrives as a single token that is neither a clean
        # separator nor a clean operator. Split such fused tokens back into
        # their runs — each all-SEGMENT_CHARS or all-non-SEGMENT_CHARS —
        # before the separator test below, carrying is_operator forward onto
        # every piece so split_redirects() still recognizes the operator half.
        # `(` and `)` are always carved out as their own single-character
        # piece first, regardless of what they are fused with, so a closing
        # paren fused with a redirect operator (`)>`) still closes the group
        # instead of being swallowed into the redirect's own token. This
        # whole carve-out is gated on t.is_operator (item A of task0004):
        # without it, a quoted or escaped run that happens to consist
        # entirely of punctuation characters (a quoted `"();"`) would be
        # split into fake operator pieces even though the lexer never read
        # it as operator syntax at all.
        if t.is_operator and t and all(c in PUNCTUATION for c in t) and not all(
            c in SEGMENT_CHARS for c in t
        ):
            pieces, i = [], 0
            while i < len(t):
                if t[i] in "()":
                    pieces.append(t[i])
                    i += 1
                    continue
                # `>|` `>&` `&>>` は 1 個のリダイレクト演算子。`|` / `&` が
                # SEGMENT_CHARS でも、演算子全体は割らずに 1 片として残す。
                # 割ると区切りと解釈され、リダイレクト先が次の文へ流出する。
                if REDIRECT.fullmatch(t[i:]):
                    pieces.append(t[i:])
                    break
                j = i + 1
                while j < len(t) and (t[j] in SEGMENT_CHARS) == (
                    t[i] in SEGMENT_CHARS
                ) and t[j] not in "()":
                    j += 1
                pieces.append(t[i:j])
                i = j
            segs = [Tok(p, t.is_operator) for p in pieces]
        else:
            segs = [t]
        for seg in segs:
            # Item A: a parenthesis is a scope delimiter only when the
            # lexer's own operator-provenance marker confirms it came from
            # real, unquoted operator syntax — the same contract
            # split_redirects() already honours for redirect operators.
            # Without this, a quoted or escaped `(`/`)` (a find `\(`, a
            # quoted `"("`) opened or closed a scope exactly as an operator
            # would, splitting a command that deletes nothing into a
            # foreign scope, or letting `find \( ... \) -delete` and
            # `git push "(" --force` escape their own rules entirely.
            if seg == "(" and getattr(seg, "is_operator", False):
                open_paren()
            elif seg == ")" and getattr(seg, "is_operator", False):
                close_paren()
            elif seg and all(c in SEGMENT_CHARS for c in seg):
                flush(seg)
            else:
                current.append(seg)
    flush(None)
    return out


def split_redirects(toks, lexed=True):
    """Return (the statement's own words, its redirection tokens).

    `rm -rf /tmp/x > /dev/null` has to be judged on `rm -rf /tmp/x`. With the
    redirect left in, `>` and `/dev/null` looked like two more delete targets
    and the command was denied for writing to the bit bucket. A leading file
    descriptor (`2` in `2>&1`) is part of the redirect too.

    A token counts as a redirect operator only when its text matches the
    operator shape AND — when LEXED, i.e. token provenance is available —
    its own `.is_operator` marking confirms it came from real, unquoted
    operator syntax rather than a word or quoted span. Without that second
    test, a quoted data word whose text happens to look like an operator
    (`echo "2>&1" > ~/.claude/settings.json`) paired with the token after it
    as if it were the operator, and the real `>` that followed lost its
    target. When LEXED is False (the parse-failure fallback, where tokens
    carry no provenance), the text-shape test alone applies, unchanged from
    before this marking existed.
    """
    words, redirects = [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        if REDIRECT.fullmatch(t) and (not lexed or getattr(t, "is_operator", False)):
            if words and words[-1].isdigit():
                redirects.append(words.pop())
            redirects.extend(toks[i : i + 2])
            i += 2
            continue
        words.append(toks[i])
        i += 1
    return words, redirects


def extract_shell_payload(toks, lexed):
    """Return the literal script a shell-invocation segment (TOKS) will
    execute via `-c`, `eval`, or a here-string (`<<<`) redirect aimed at a
    shell word — or None when the segment is not such an invocation, or its
    payload is not a single literal token statements() can push back onto
    its own queue and re-scan like any other statement.

    Only lexed (LEXED True) segments are examined: token provenance is what
    tells split_redirects() a real `<<<` apart from a quoted word that merely
    looks like one, and head()/split_redirects() both expect that provenance
    to be present. On the parse-failure fallback (LEXED False) this returns
    None, same as any other feature here that depends on tokenization; the
    fallback's own whole-segment matching still sees the raw text.
    """
    if not lexed:
        return None
    words, redirects = split_redirects(toks, lexed)
    word, args = head(words)
    if word == "eval":
        return " ".join(args) if args else None
    if word in SHELL_WORDS:
        if "-c" in args:
            idx = args.index("-c")
            if idx + 1 < len(args):
                return args[idx + 1]
        i = 0
        while i < len(redirects):
            t = redirects[i]
            if REDIRECT.fullmatch(t):
                if t == "<<<" and i + 1 < len(redirects):
                    return redirects[i + 1]
                i += 2
            else:
                i += 1
    return None


def strip_heredocs(chunk):
    """Return (chunk without here-doc bodies, the bodies removed).

    A here-doc body is data, not commands: `cat <<EOF` followed by a line
    reading `rm -rf ~` deletes nothing. Leaving it in place meant the newline
    split treated every line of the body as its own statement, so writing a
    shell example into a file was refused as though it were being run.
    """
    bodies = []

    def take(m):
        bodies.append(m.group(3))
        return m.group(0)[: m.start(3) - m.start(0)]

    return HEREDOC.sub(take, chunk), bodies


def statements(command):
    """Yield (text, tokens, lexed, scope, conditional, ordinal, collect_tokens)
    per command segment, substitution bodies included.

    TEXT/TOKENS are what every check reads and every reason quotes (item B of
    task0004's plan): built with the SAME substitution treatment base used —
    a bare space in place of each command substitution
    (`SUBSTITUTION.sub(" ", chunk)`) — so a command carrying no assignment
    the collector records is judged identically to base whether or not it
    contains a substitution at all. LEXED is lex_segments()'s per-segment
    parse-success flag — False only on the parse-failure fallback, where
    token provenance is unavailable.

    COLLECT_TOKENS is a SEPARATE lexing of the very same statement, with each
    command substitution flattened to DYNAMIC_PLACEHOLDER instead of a bare
    space, so a value that captured one (`X=$(mktemp -d)`) still lexes as a
    single, dynamic-marked token instead of an indistinguishable literal
    (task0003 item D). collect_assignments() is the ONLY reader of this
    field; every check and every reason use TOKENS instead. The two lexings
    always agree on how many statements a chunk contains: a command
    substitution's replacement text — a space, or the placeholder — holds no
    statement separator and no bare, operator-provenance parenthesis either
    way, so where a statement starts and ends never depends on which
    replacement is used. Only intra-statement word boundaries can differ,
    and that difference is exactly what TOKENS and COLLECT_TOKENS are meant
    to disagree on.

    SCOPE is the resolution layer's identity for the statement (item C of
    the task0003 plan): a fresh id from a process-local counter every time a
    chunk is pushed onto PENDING — a shell `-c`/`eval`/here-string payload,
    a command-substitution body, or a here-doc body re-queued as script —
    so each such re-queued payload starts in a scope of its own, distinct
    from whatever statement pushed it. Within one chunk, lex_segments()
    further distinguishes a subshell group, each pipeline element (the first
    included) and a statement terminated as a background job the same way.
    Sequential composition (`;`, `&&`, `||`, newline) shares the enclosing
    scope. This changes nothing about which statements are yielded or their
    order (NFR6); the scope travels alongside them. It is assigned from the
    COLLECT_TOKENS lexing (the canonical structural pass); the TOKENS lexing
    runs against a throwaway scope counter of its own and its scope/
    conditional output is discarded.

    CONDITIONAL is lex_segments()'s per-statement flag (item A.2): True when
    the statement is reached only through a preceding `&&`/`||` and may not
    run at all.

    ORDINAL is this statement's position in the whole stream, assigned right
    here — the single place a statement's scope identity is also assigned
    (item F of task0004's plan) — so collect_assignments() and the main
    judgment loop both read this SAME number instead of each re-deriving it
    with their own enumerate() over the materialized list, which could
    silently drift apart the day either loop gains a filter or reordering of
    its own.
    """
    next_scope = itertools.count(1).__next__
    next_ordinal = itertools.count().__next__
    pending = [(command, next_scope())]
    budget = [MAX_SHELL_PAYLOAD_EXPANSIONS]
    while pending:
        chunk, base_scope = pending.pop()
        chunk, bodies = strip_heredocs(chunk)
        if bodies and SHELL_SINK.search(chunk):
            # `bash <<EOF` does execute its body, so put it back in the queue.
            pending.extend((b, next_scope()) for b in bodies if b.strip())
        for m in SUBSTITUTION.finditer(chunk):
            body = m.group(1) or m.group(2) or ""
            if body.strip():
                pending.append((body, next_scope()))

        collect_segments = lex_segments(
            SUBSTITUTION.sub(DYNAMIC_PLACEHOLDER, chunk), base_scope, next_scope
        )
        check_segments = lex_segments(
            SUBSTITUTION.sub(" ", chunk), base_scope, itertools.count(1).__next__
        )
        if len(check_segments) != len(collect_segments):
            # Should not happen — see the docstring's argument for why the
            # two lexings always agree on statement count — but fail safe
            # rather than guess an alignment between two differently-sized
            # lists: fall back to the collection pass's own tokens for the
            # check-facing role too (today's pre-task0004 behaviour for this
            # one chunk), which never loses a statement.
            check_segments = collect_segments

        for (ctoks, lexed, scope, conditional), (qtoks, _qlex, _qscope, _qcond) in zip(
            collect_segments, check_segments
        ):
            if not qtoks:
                continue
            ordinal = next_ordinal()
            yield " ".join(qtoks), qtoks, lexed, scope, conditional, ordinal, ctoks
            if budget[0] > 0:
                payload = extract_shell_payload(qtoks, lexed)
                if payload and payload.strip():
                    budget[0] -= 1
                    pending.append((payload, next_scope()))


def tokens(segment):
    """Best-effort tokenization. Falls back to whitespace on a parse error."""
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def head(toks):
    """Return (command word, remaining args), skipping assignments/wrappers."""
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.match(r"^[A-Za-z_]\w*=", t):  # VAR=value prefix
            i += 1
            continue
        if t in WRAPPERS:
            i += 1
            value_flags = WRAPPER_VALUE_FLAGS.get(t, set())
            while i < len(toks):
                a = toks[i]
                if a == "--":
                    i += 1
                    break
                if a == "-" or not a.startswith("-"):
                    break
                i += 1
                if a in value_flags:
                    i += 1  # consume the option's value token
            continue
        if t in ("mise", "asdf") and i + 1 < len(toks) and toks[i + 1] == "exec":
            i += 2
            while i < len(toks) and toks[i] != "--":
                i += 1
            i += 1  # step past the `--`
            continue
        break
    if i >= len(toks):
        return None, []
    return os.path.basename(toks[i]), toks[i + 1 :]


# --- Resolution (layer 3): plain literal VAR=value assignments -------------
#
# Collects standalone `VAR=value` assignments from the statement stream
# statements() already produces, and substitutes them into a target token
# before check_rm()/check_self_modification() read it, so a delete or write
# reached through such a variable is judged exactly as the literal path
# would be. See feature-docs/destructive-guard-var-resolution/tasks/task0001.md
# and task0003.md for the full design; this section implements items A-F.

# A statement's entire content, once a single lexed token: NAME=VALUE. VALUE
# may be empty or contain anything (re.S), including embedded newlines from
# a quoted multi-line value shlex already resolved.
ASSIGNMENT_STATEMENT = re.compile(r"([A-Za-z_]\w*)=(.*)", re.S)

# A reference to another shell variable, either spelling. Used both to
# exclude a value that chains to another variable (single-stage resolution
# only) and to substitute a reference in a target token.
VAR_REF = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)")

# A process substitution in either direction. Unlike a command substitution
# (flattened via DYNAMIC_PLACEHOLDER before lexing, so it already reaches
# here dynamic-marked) or an arithmetic expansion (`$((...))`, already
# matched by DYNAMIC's own `\$\(` alternative regardless of the extra
# paren), a process substitution carries no `$` at all and so is invisible
# to every check downstream of collection unless excluded here (item D).
PROCESS_SUB = re.compile(r"[<>]\(")

# Item G's bound on resolved text: substituting a value of length V at R
# reference sites builds V×R characters with no ceiling otherwise, and this
# hook is a synchronous PreToolUse check on every Bash call under a
# 10-second timeout — past roughly 110KB of command the hook is killed and
# no verdict is emitted at all, the one failure mode that is neither allow,
# ask nor deny. A resolved token longer than this is simply not resolved
# (resolve_target() below); the pre-resolution verdict stands (NFR2). Chosen
# generously above any real path length so it never fires for ordinary use.
RESOLVED_TEXT_MAX = 4096

# Appended to the rm-unresolvable reason when the reference that stayed
# unresolved named a variable assigned more than once (item F).
REASSIGN_HINT = (
    "同じ名前に2回代入されているのが原因で未解決になっている。"
    "値ごとに別の変数名へ分けて代入し直すと解決できる。"
)

# item B's widened invalidation set: command words whose own arguments can
# bind a name WITHOUT that binding ever being a single lexed NAME=VALUE
# token — so the narrow ASSIGNMENT_STATEMENT shape test never sees them,
# and a stale earlier bare assignment would otherwise survive unnoticed.
NAME_BINDING_WORDS = {"export", "declare", "typeset", "local", "readonly"}
LINE_READING_WORDS = {"read", "mapfile", "readarray"}

# item E's additions: the loop/selection constructs bind the identifier that
# follows them, `getopts` binds its name argument (its second, after the
# option string), and `unset` removes a name — which this hook treats as
# just another way a statement can bind/touch a name (item E: "unset joins
# the binding words"), since either one makes a prior recorded value stale.
LOOP_BINDING_WORDS = {"for", "select"}
OPTION_PARSE_WORD = "getopts"
UNSET_WORD = "unset"

# Statements that can bind ANY name at all, not just ones spelled out in
# their own text — a string-evaluating builtin or a sourced file. What they
# bind is not statically knowable, so instead of naming a variable they
# invalidate every currently-known value in their own scope from their own
# position onward (item B), via WILDCARD below.
WILDCARD_BINDING_WORDS = {"eval", "source"}

BARE_NAME = re.compile(r"^[A-Za-z_]\w*$")
APPEND_STATEMENT = re.compile(r"([A-Za-z_]\w*)\+=(.*)", re.S)

# Sentinel returned by invalidated_names() for a statement that can bind any
# name at all (eval / source / `.`), as opposed to a (possibly empty) set of
# specific names.
WILDCARD = object()


def invalidated_names(toks):
    """Return the variable name(s) TOKS's statement could bind through one of
    the name-binding WORDS below (item B/E) — a set of names, or the
    WILDCARD sentinel when the statement could bind any name at all. Returns
    an empty set for a statement that binds nothing this way.

    Every binding word is recognised WHEREVER it sits in the token list, not
    only as the statement's first token (item E): a command-prefix
    assignment ahead of it (`A=1 export X=v`), or a leading shell keyword
    this hook does not model as its own statement shape (`then`, `do`, a
    brace-group opener), must not hide it. This is deliberately independent
    of collect_assignments()'s own per-token scan for a bare `NAME=VALUE` or
    `NAME+=VALUE` shape (item E) — that scan runs on every token of every
    statement regardless of which word, if any, precedes it, and the two
    together are what make invalidation "per token" rather than "per first
    token" the way recording (FR5) stays.
    """
    if not toks:
        return set()
    names = set()
    for i, t in enumerate(toks):
        if t in WILDCARD_BINDING_WORDS or (t == "." and i + 1 < len(toks)):
            return WILDCARD
        if t in NAME_BINDING_WORDS:
            for u in toks[i + 1 :]:
                if u.startswith("-"):
                    continue
                m = re.match(r"^([A-Za-z_]\w*)(?:=.*)?$", u, re.S)
                if m:
                    names.add(m.group(1))
        elif t in LINE_READING_WORDS:
            names.update(
                u for u in toks[i + 1 :] if not u.startswith("-") and BARE_NAME.match(u)
            )
        elif t == "printf":
            rest = toks[i + 1 :]
            if "-v" in rest:
                j = rest.index("-v")
                if j + 1 < len(rest) and BARE_NAME.match(rest[j + 1]):
                    names.add(rest[j + 1])
        elif t == OPTION_PARSE_WORD:
            # getopts OPTSTRING NAME [args...] — NAME is its second argument.
            if i + 2 < len(toks) and BARE_NAME.match(toks[i + 2]):
                names.add(toks[i + 2])
        elif t in LOOP_BINDING_WORDS:
            if i + 1 < len(toks) and BARE_NAME.match(toks[i + 1]):
                names.add(toks[i + 1])
        elif t == UNSET_WORD:
            names.update(
                u for u in toks[i + 1 :] if not u.startswith("-") and BARE_NAME.match(u)
            )
    return names


def collect_assignments(all_statements):
    """Collect plain literal `VAR=value` assignments from ALL_STATEMENTS —
    the (text, tokens, lexed, scope, conditional, ordinal, collect_tokens)
    tuples statements() already produced for one command string, in one
    linear pass (NFR4). ORDINAL travels with each statement from statements()
    itself (item F) rather than being re-derived here with enumerate(); it is
    compared only between statements the caller has already confirmed share
    a scope. COLLECT_TOKENS — not TOKENS — is what this function scans: the
    lexing where a command substitution survives as a dynamic-marked
    placeholder instead of vanishing like a bare space would (item B/D), so
    `X=$(mktemp -d)` is still visible here as one assignment-shaped token
    even though the check-facing TOKENS for the very same statement no
    longer contain any trace of the substitution at all.

    Returns (values, reassigned):
      values     -- dict name -> (literal value, defining scope, defining
                    ordinal, whether the defining statement was conditional,
                    the ordinal of the first eval/source in that scope after
                    the assignment, or None). One entry per name assigned
                    exactly once anywhere in the command via a recordable
                    bare assignment.
      reassigned -- set of names bound two or more times anywhere in the
                    command string, whether or not every binding was itself
                    recordable (FR6, item B/E). Such a name is absent from
                    VALUES even though every occurrence was seen, so every
                    reference to it stays unresolved and resolve_target()
                    can report that it was the reassigned name, for the
                    rewrite hint in the unresolvable reason (item F).

    Only a statement whose entire content is a single lexed token shaped
    like NAME=VALUE is a candidate for VALUES (FR5's qualifying shape): a
    command-prefix assignment (`X=v rm ...`) or one introduced by a command
    word (`export X=v`) always yields more than one token in its own
    statement and is excluded by that alone. A value referencing another
    variable is excluded too (single-stage resolution, no chaining), as is
    one carrying a process substitution (item D; a command substitution or
    arithmetic expansion already arrives dynamic-marked via
    DYNAMIC_PLACEHOLDER/DYNAMIC and needs no separate exclusion here — it is
    recorded, and resolve_target()'s existing DYNAMIC check on the
    substituted text catches it downstream). The parse-failure fallback
    (LEXED False) never contributes — per-token provenance is unavailable
    there, so a statement on that path cannot be trusted to be a bare
    assignment, or any of the widened forms, at all.

    INVALIDATION (item E) is wider than recording, and decided per token
    rather than per first token: every token of every lexed statement is
    checked for a bare `NAME=VALUE` or `NAME+=VALUE` shape, regardless of
    whether the statement AS A WHOLE also qualifies for recording — a
    reassignment fused into a compound statement (after a conditional
    keyword this hook does not model as its own shape, inside a loop body,
    behind an assignment prefix on another command word) is counted here
    even though it can never be recorded. A second assignment counts even
    when its value is unrecordable (a variable reference, a substitution, an
    arithmetic expansion): the counting in this loop never declines, only
    the separate recording step below does — this is what keeps a
    self-referential or chained-value reassignment (`X=$X/sub`) from being
    mistaken for a single, still-good assignment.
    """
    counts = {}
    candidates = {}
    poison = {}
    for _text, _toks, lexed, scope, conditional, ordinal, ctoks in all_statements:
        if not lexed:
            continue
        names = invalidated_names(ctoks)
        if names is WILDCARD:
            poison.setdefault(scope, []).append(ordinal)
            continue
        for name in names:
            counts[name] = counts.get(name, 0) + 1

        for t in ctoks:
            m = ASSIGNMENT_STATEMENT.fullmatch(t)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
                continue
            m = APPEND_STATEMENT.fullmatch(t)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1

        if len(ctoks) != 1:
            continue
        m = ASSIGNMENT_STATEMENT.fullmatch(ctoks[0])
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        if VAR_REF.search(value) or PROCESS_SUB.search(value):
            continue
        candidates[name] = (value, scope, ordinal, conditional)

    reassigned = {name for name, n in counts.items() if n > 1}
    values = {}
    for name, (value, scope, ordinal, conditional) in candidates.items():
        if name in reassigned:
            continue
        later_poisons = [p for p in poison.get(scope, ()) if p > ordinal]
        invalid_from = min(later_poisons) if later_poisons else None
        values[name] = (value, scope, ordinal, conditional, invalid_from)
    return values, reassigned


def resolve_target(token, values, reassigned, scope, ordinal):
    """Attempt to resolve TOKEN using VALUES/REASSIGNED (collect_assignments()'
    output) for a use site identified by SCOPE and ORDINAL — the resolution
    layer's identity and position for the statement TOKEN came from.

    An entry in VALUES applies to this use site only when every one of
    item A's conditions holds:
      1. its defining ordinal is lower than ORDINAL (it precedes the use);
      2. its defining statement was not conditional (item A.2);
      3. its defining scope equals SCOPE (item C — includes item A.3, since
         a statement handed to another shell already carries a different
         scope by construction);
      4. no eval/source statement in the same scope sits between the
         assignment and this use (its recorded `invalid_from`, if any, is
         not exceeded by ORDINAL — item B's "from its own position onward").
    Any uncertainty here resolves to "not applicable" (fail-closed, NFR2).

    Returns (text, resolved, substituted, hit_reassigned):
      text           -- the substituted text when fully resolved; otherwise
                        TOKEN unchanged, so the caller's existing judgment
                        runs on the original text exactly as before (NFR2).
      resolved       -- whether TEXT is usable as one fully-resolved literal
                        target: no dynamic construct at all (the same
                        DYNAMIC regex the pre-existing checks already use —
                        no glob metacharacter, no command/arithmetic
                        substitution, no remaining variable reference), not
                        empty or whitespace-only (item E.2 — an empty
                        substitution is not a resolution), not carrying IFS
                        whitespace (item E.1 — a multi-word result is never
                        treated as one target on the strength of its first
                        word; it stays unresolved instead, which the
                        caller's pre-resolution judgment already handles
                        safely), and not longer than RESOLVED_TEXT_MAX (item
                        G of task0004's plan).
      substituted    -- whether TOKEN referenced a name at all (item D of
                        task0004's plan): the provenance test that decides
                        which scratch-area treatment a caller's containment
                        decision applies. False for a token nothing in it
                        ever referenced — a plain literal — regardless of
                        RESOLVED (a plain literal is trivially "resolved":
                        there was nothing to resolve). A caller that has
                        already passed the DYNAMIC gate on TEXT before
                        consulting this flag never observes SUBSTITUTED True
                        together with RESOLVED False: a referenced name that
                        failed to apply leaves the literal `$NAME`/`${NAME}`
                        text behind, which DYNAMIC already matches.
      hit_reassigned -- names referenced in TOKEN that were dropped from
                        VALUES for being bound twice (item F).

    Every reference of a mapped, currently-applicable name, bare or braced,
    is replaced; a reference to an unmapped name, or to a mapped name that
    fails any condition above, is left exactly as written (item C).
    """
    hit = set()

    def replace(m):
        name = m.group(1) or m.group(2)
        if name in reassigned:
            hit.add(name)
            return m.group(0)
        entry = values.get(name)
        if entry is None:
            return m.group(0)
        value, def_scope, def_ordinal, def_conditional, invalid_from = entry
        if def_scope != scope or def_conditional or not (def_ordinal < ordinal):
            return m.group(0)
        if invalid_from is not None and ordinal > invalid_from:
            return m.group(0)
        if len(value) > RESOLVED_TEXT_MAX:
            # item G: refuse the substitution before it happens, not after —
            # building the substituted string is itself the O(value length)
            # cost a large value repeated at R reference sites multiplies
            # into O(V×R). Leaving the literal `$NAME`/`${NAME}` text behind
            # means the DYNAMIC check below still catches it, so the result
            # is the same "not resolved" outcome the post-hoc length check
            # further down would reach anyway, at a fraction of the cost.
            return m.group(0)
        return value

    substituted = VAR_REF.search(token) is not None
    result = VAR_REF.sub(replace, token)
    if DYNAMIC.search(result):
        return token, False, substituted, hit
    if not result.strip():
        return token, False, substituted, hit
    if re.search(r"[ \t\n]", result):
        return token, False, substituted, hit
    if len(result) > RESOLVED_TEXT_MAX:
        # item G: a value of length V substituted at R reference sites
        # builds V×R characters with no ceiling otherwise, and this hook is
        # a synchronous PreToolUse check on every Bash call with a 10-second
        # timeout — past roughly 110KB of command the hook is killed and no
        # verdict is emitted at all, the one failure mode that is neither
        # allow, ask nor deny. Exceeding the ceiling is not an error and not
        # a denial: the token is simply not resolved, so the pre-resolution
        # judgment path runs on it and the pre-resolution verdict stands
        # (NFR2).
        return token, False, substituted, hit
    return result, True, substituted, hit


def make_resolver(values, reassigned, scope, ordinal):
    """Bind VALUES/REASSIGNED/SCOPE/ORDINAL into a one-argument resolver a
    caller can apply to any target token via resolve_target()."""
    return lambda token: resolve_target(token, values, reassigned, scope, ordinal)


def git_subcommand(args):
    """Strip git's global options and return (subcommand, its args)."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if a.startswith("--git-dir=") or a.startswith("--work-tree="):
            i += 1
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a, args[i + 1 :]
    return None, []


def has(args, *flags):
    return any(a in flags for a in args)


def short_flags(args):
    """Letters of clustered short flags, e.g. `-rf` -> {'r','f'}."""
    out = set()
    for a in args:
        if a.startswith("-") and not a.startswith("--"):
            out.update(a[1:])
    return out


def check_git(args, segment):
    sub, rest = git_subcommand(args)
    if sub is None:
        return

    if sub == "push":
        if has(rest, "--force", "-f") or any(
            a.startswith("--force-with-lease") for a in rest
        ):
            decide("deny", "git-force-push", "force push はリモート履歴を巻き戻す。")
        if has(rest, "--delete", "-d") or any(
            a.startswith(":") and len(a) > 1 for a in rest
        ):
            decide("deny", "git-remote-delete", "リモートブランチ/タグの削除。")
        if has(rest, "--mirror"):
            decide(
                "deny", "git-force-push", "`--mirror` はリモートの ref を丸ごと置き換える。"
            )

    if sub == "tag" and has(rest, "-d", "--delete"):
        decide("deny", "git-tag-delete", "タグの削除。")

    if sub == "branch" and (
        has(rest, "-D") or (has(rest, "-d", "--delete") and has(rest, "--force"))
    ):
        decide(
            "deny",
            "git-branch-force-delete",
            "未マージのブランチを強制削除する（`-D`）。到達不能なコミットが残る。",
        )

    if sub == "reset" and has(rest, "--hard"):
        target = [a for a in rest if not a.startswith("-")]
        if len(target) == 1 and EM_WORKFLOW_REF.match(target[0]):
            return  # em-workflow exit-4 recovery — worktree resync, nothing lost
        decide(
            "deny",
            "git-reset-hard",
            "`reset --hard` は未コミットの変更を復元不能に捨てる。"
            "個別ファイルなら `git checkout -- <path>` を使う。",
        )

    if sub == "clean" and (short_flags(rest) & {"f", "x"} or has(rest, "--force")):
        decide(
            "deny",
            "git-clean",
            "`git clean` は untracked ファイルを削除する。stash では復元できない。",
        )

    if sub in ("checkout", "restore"):
        targets = [a for a in rest if not a.startswith("-")]
        if "." in targets or (sub == "restore" and not targets):
            decide(
                "deny",
                "git-discard-tree",
                f"`git {sub} .` は作業ツリー全体の変更を捨てる。パスを個別に指定する。",
            )

    if sub == "stash" and rest[:1] and rest[0] in ("drop", "clear"):
        decide(
            "deny",
            "git-stash-drop",
            "stash の破棄。linked worktree は stash を共有するので影響範囲が広い。",
        )

    if sub == "worktree" and rest[:1] == ["remove"] and has(rest, "--force", "-f"):
        decide(
            "deny",
            "git-worktree-force-remove",
            "`--force` 付きの worktree 削除は未コミットの変更ごと消す。",
        )

    if sub == "commit":
        if has(rest, "--no-verify", "-n"):
            decide(
                "deny",
                "git-no-verify",
                "`--no-verify` は pre-commit フックを飛ばす。"
                "このマシンでは gitleaks のシークレット検査がそこに載っている。",
            )
        if has(rest, "--amend"):
            decide(
                "ask",
                "git-amend",
                "`--amend` は既存コミットを書き換える。push 済みかどうかは"
                "コマンドだけでは判定できない。",
            )

    if sub in ("filter-branch", "filter-repo"):
        decide("deny", "git-history-rewrite", "履歴の一括書き換え。")

    if (sub == "reflog" and has(rest, "--expire=now")) or (
        sub == "gc" and has(rest, "--prune=now")
    ):
        decide(
            "deny",
            "git-reflog-expire",
            "reflog/到達不能オブジェクトの即時破棄。復旧手段がなくなる。",
        )


_GIO = None


def gio_available():
    """Whether `gio` is on PATH. Probed once, and only on a deny path."""
    global _GIO
    if _GIO is None:
        _GIO = shutil.which("gio") is not None
    return _GIO


def deletion_alternative(target):
    """A concrete command to offer in place of the delete being refused.

    `gio trash` is the good outcome: it records the original path and the
    deletion time under ~/.local/share/Trash, so the file can be restored from
    the desktop trash. The trash cannot span filesystems, though, so it only
    works below $HOME — outside that, and when gio is not installed at all,
    the honest suggestion is a move to somewhere the file survives.

    The point is that the agent can read this, rewrite the command itself and
    keep going. `gio trash` and `mv` are not `rm`, so neither comes back here.
    """
    path = os.path.abspath(os.path.expanduser(target))
    home = os.path.expanduser("~")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in path):
        return "パスに制御文字が含まれているため、安全な代替コマンドを提示できない。手動で確認する。"
    quoted = shlex.quote(path)
    if not gio_available():
        return f"`mv -- {quoted} /tmp/` で退避する（gio が無いのでゴミ箱は使えない）。"
    if path == home or path.startswith(home + os.sep):
        return f"`gio trash -- {quoted}` に書き換える（復元情報が残り、ゴミ箱から戻せる）。"
    return (
        f"`mv -- {quoted} /tmp/` で退避する"
        f"（$HOME の外はゴミ箱がファイルシステムをまたげないので `gio trash` は失敗する）。"
    )


def is_safe_delete_raw(text):
    """Whether TEXT is inside SAFE_DELETE's scratch area by the
    PRE-RESOLUTION decision (item D of task0004's plan): SAFE_DELETE's own
    prefix match alone, on TEXT exactly as written — no normalization, no
    path-component boundary. This is the same test the hook at
    `workflow.implement.base_commit` ran, and it is the only scratch-area
    test a target nothing was substituted into ever receives; a target a
    resolved value WAS substituted into gets is_safe_delete() below instead
    (round 1's stricter, component-boundary treatment, which task0003
    required and this task does not undo).
    """
    return SAFE_DELETE.match(text) is not None


def is_safe_delete(text):
    """Whether TEXT is inside SAFE_DELETE's scratch area, decided at path
    COMPONENT boundaries (item E.3) rather than by SAFE_DELETE's own prefix
    match alone. SAFE_DELETE's own pattern text is unchanged (NFR6); only
    where a match must END changes. An alternative whose own literal already
    ends in `/` (`/tmp/`, `tmp/`, `.cache/`, ...) already carries its own
    boundary there. A bare-name alternative (`dist`, `node_modules`, `build`,
    `target`, `.next`, `coverage`) additionally needs the text right after
    the match to be absent or `/`, so a leading path component that merely
    STARTS WITH a scratch-area name as a string prefix (`distfiles/secret`)
    is not treated as inside it.

    Used only on a NORMALIZED target that a resolved value was substituted
    into (item D of task0004's plan) — a target nothing was substituted into
    is judged by is_safe_delete_raw() above instead, on its raw, unnormalized
    text, exactly as base decided it.
    """
    m = SAFE_DELETE.match(text)
    if not m:
        return False
    if m.group(0).endswith("/"):
        return True
    return m.end() == len(text) or text[m.end()] == "/"


def check_rm(args, resolve):
    """RESOLVE is resolve_target() bound to this statement (make_resolver()) —
    every argument is resolved BEFORE it is separated into flags and targets
    (item E.4 — a recursive flag supplied through a variable is seen as a
    flag, not lost as an unresolved-looking positional word), so a delete
    reached through a plain literal `VAR=value` is judged on the resolved
    path exactly as the literal path would be (task0001 item D).
    """
    resolved_args = [resolve(a) for a in args]
    texts = [text for text, _resolved, _sub, _hit in resolved_args]
    flags = short_flags(texts)
    recursive = "r" in flags or "R" in flags or has(texts, "--recursive")
    target_idx = [i for i, text in enumerate(texts) if not text.startswith("-")]

    if not target_idx:
        return
    resolved = [resolved_args[i] for i in target_idx]
    for text, _resolved, _sub, _hit in resolved:
        if re.fullmatch(r"/+|/\*|~|~/|\$HOME/?", text):
            decide("deny", "rm-root", f"削除対象が `{text}` — ホーム/ルート全体に届く。")
    if not recursive:
        return
    for text, _resolved, substituted, hit in resolved:
        # item C: the unresolvable gate is decided BEFORE any containment
        # decision, on TEXT exactly as it stands (never normalized first).
        # Lexical normalization collapses `.`/`..` without knowing what an
        # unexpanded component would have expanded to, so deciding
        # containment first could normalize a dynamic target (an unexpanded
        # reference, a glob component, a substitution) straight into the
        # scratch area and this gate would never see it at all.
        if DYNAMIC.search(text):
            hint = f" {REASSIGN_HINT}" if hit else ""
            decide(
                "ask",
                "rm-unresolvable",
                f"再帰削除の対象 `{text}` が変数/グロブで、影響範囲を静的に確定できない。"
                f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。{hint}",
            )
        # item D: which scratch-area test applies depends on provenance —
        # SUBSTITUTED (resolve_target()'s 3rd element), not whether TEXT
        # happens to look clean. A target nothing was substituted into
        # (SUBSTITUTED is False — including a plain literal that never
        # contained a reference at all) gets the pre-resolution decision:
        # SAFE_DELETE's own raw prefix match on TEXT as written, exactly as
        # base decided it — no normalization, no path-component boundary —
        # so the scratch roots written in directory form and a build-output
        # name that merely begins with a scratch-area name both keep their
        # base allow. A target a resolved value WAS substituted into
        # (SUBSTITUTED is True) keeps round 1's stricter treatment:
        # normalized first (so a value climbing out of the scratch area
        # with parent references is judged on the path the shell would
        # actually act on), then decided at path-component boundaries —
        # this is the one place resolution may be STRICTER than the
        # identical literal (NFR2's one-directional exception, recorded in
        # the task plan's item D).
        if substituted:
            candidate = normalize_candidate(text)
            if is_safe_delete(candidate):
                continue
            alternative_for = candidate
        else:
            if is_safe_delete_raw(text):
                continue
            alternative_for = text
        decide(
            "deny",
            "rm-recursive",
            f"`rm -r` の対象 `{text}` はスクラッチ領域の外。"
            f"{deletion_alternative(alternative_for)}",
        )


def check_file_destruction(word, args, segment):
    if word == "shred":
        decide("deny", "shred", "`shred` は上書き消去で復元できない。")
    if word == "dd" and any(a.startswith("of=") for a in args):
        decide("deny", "dd-write", "`dd of=` は対象を直接上書きする。")
    if word == "truncate" and has(args, "-s", "--size"):
        decide("deny", "truncate", "`truncate` は既存ファイルを切り詰める。")
    if word == "mkfs" or word.startswith("mkfs."):
        decide("deny", "mkfs", "ファイルシステムの作成はデバイス上の全データを消す。")
    if word == "find" and (has(args, "-delete") or "rm" in args):
        decide(
            "deny",
            "find-delete",
            "`find` による一括削除は対象一覧を事前に確認できない。"
            "`find` で列挙してから個別に消す。",
        )
    if word == "rsync" and has(args, "--delete", "--delete-after", "--delete-before"):
        decide("deny", "rsync-delete", "`rsync --delete` は宛先にしかないファイルを消す。")
    if word in ("tar", "unzip") and has(args, "-o", "--overwrite"):
        decide(
            "ask", "archive-overwrite", "アーカイブ展開が既存ファイルを無条件で上書きする。"
        )


def redirect_write_targets(redirects):
    """Return the target-side token of each write-shaped redirect in REDIRECTS.

    REDIRECTS is split_redirects()'s flat token list: an optional leading fd
    digit, then an operator token, then its target, repeated in order. An
    operator starting with `<` is normally an input form (plain redirect,
    here-doc, here-string, fd-dup-input) and contributes nothing — that data
    is read, not written, and must stay out of the write-target set. The one
    exception is `<>`, which opens its target for both reading and writing;
    its target does enter the result. Every other operator's target enters
    the result too, including the bare descriptor number that is the
    "target" of a descriptor-duplicating redirect (`2>&1`); it is not a
    path, but neither detection pattern below will match it.
    """
    out = []
    i = 0
    while i < len(redirects):
        t = redirects[i]
        if REDIRECT.fullmatch(t):
            is_readwrite = READWRITE_REDIRECT.fullmatch(t) is not None
            if (not t.startswith("<") or is_readwrite) and i + 1 < len(redirects):
                out.append(redirects[i + 1])
            i += 2
        else:
            i += 1  # a leading fd digit belonging to the next operator
    return out


def flag_destinations(args):
    """Return the values of target-directory flags (TARGET_DIR_FLAGS) among
    ARGS, covering every GNU getopt spelling: a separate token (`-t DIR`),
    the value-attached short form (`-tDIR`), a short-option cluster
    (`-rt DIR` / `-rtDIR`), the attached `=` form
    (`--target-directory=DIR`), and unambiguous long-option abbreviations
    (`--target-dir DIR`). The flag's own token never enters the result —
    only its value does.
    """
    out = []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            name, sep, val = a.partition("=")
            if len(name) > 2 and "--target-directory".startswith(name):
                if sep:
                    out.append(val)
                    i += 1
                    continue
                if i + 1 < len(args):
                    out.append(args[i + 1])
                i += 2
                continue
            i += 1
            continue
        if a.startswith("-") and len(a) > 1 and "t" in a[1:]:
            idx = a.index("t", 1)
            rest = a[idx + 1 :]
            if rest:
                out.append(rest)
                i += 1
                continue
            if i + 1 < len(args):
                out.append(args[i + 1])
            i += 2
            continue
        i += 1
    return out


def flag_value_destinations(word, args):
    """Return the values of WORD's flag-carried destination flags (per
    FLAG_DEST_FLAGS) among ARGS, covering every spelling GNU-style tools
    accept: a separate token (`-C DIR`), the value-attached short form
    (`-CDIR`, possibly at the tail of a short-option cluster like `-xCDIR`),
    and the attached `=` long form (`--directory=DIR`). Mirrors
    flag_destinations()'s handling of `-t`/`--target-directory`, restricted
    to the flag spellings WORD actually accepts.
    """
    flags = FLAG_DEST_FLAGS.get(word)
    if not flags:
        return []
    short_chars = {
        f[1] for f in flags if len(f) == 2 and f.startswith("-") and not f.startswith("--")
    }
    out = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            if i + 1 < len(args):
                out.append(args[i + 1])
            i += 2
            continue
        matched = False
        for f in flags:
            if f.startswith("--") and a.startswith(f + "="):
                out.append(a.split("=", 1)[1])
                matched = True
                break
        if matched:
            i += 1
            continue
        if short_chars and a.startswith("-") and not a.startswith("--") and len(a) > 1:
            hit = next((c for c in a[1:] if c in short_chars), None)
            if hit is not None:
                idx = a.index(hit, 1)
                rest = a[idx + 1 :]
                if rest:
                    out.append(rest)
                    i += 1
                    continue
                if i + 1 < len(args):
                    out.append(args[i + 1])
                i += 2
                continue
        i += 1
    return out


def strip_value_tokens(word, args):
    """Return WORD's positional arguments from ARGS, dropping any token that
    is actually the value of one of WORD's VALUE_TAKING_FLAGS rather than a
    positional argument — so the last remaining entry is the real
    destination for `cp`/`ln`/`rsync`.

    "Positional argument" is decided in exactly one place (here): a token
    that does not start with `-`, is not itself a value-taking flag, and
    does not immediately follow one. This covers a value-taking flag given
    as its own token (`-S .bak`, `--exclude foo`) and as the trailing letter
    of a short-option cluster (`-vS .bak` — `S` is the last letter, so the
    next token is its value per getopt rules). Anything after a literal `--`
    is positional even if it looks like a flag.
    """
    value_flags = VALUE_TAKING_FLAGS.get(word)
    if not value_flags:
        return [a for a in args if not a.startswith("-")]
    short_value_chars = {
        f[1] for f in value_flags if len(f) == 2 and f.startswith("-") and not f.startswith("--")
    }
    result = []
    consumed_next = False
    seen_dashdash = False
    for a in args:
        if consumed_next:
            consumed_next = False
            continue
        if not seen_dashdash and a == "--":
            seen_dashdash = True
            continue
        if seen_dashdash:
            result.append(a)
            continue
        if a in value_flags:
            consumed_next = True
            continue
        if (
            a.startswith("-")
            and not a.startswith("--")
            and len(a) > 2
            and a[-1] in short_value_chars
        ):
            consumed_next = True
            continue
        if not a.startswith("-"):
            result.append(a)
    return result


def write_targets(word, args, redirects):
    """Assemble the set of paths this segment writes to.

    Sources, unioned (task plan Part 1 and Part 2):

    - the target side of every write-shaped redirect (append and plain
      output alike; input forms are already excluded upstream)
    - every non-flag argument of an in-place writer (`tee`, `truncate`,
      `shred`, `install`, `patch`), or of `sed` invoked with an in-place
      flag — the flag itself, including its attached-value and
      empty-suffix forms (`-i.bak`, `-i''`), always starts with `-` and is
      excluded by the same non-flag filter
    - the destination of a file-manipulating command: the LAST non-flag
      argument only for `cp`/`ln` (their destination is positional and
      their source is genuinely only read), every non-flag argument for
      `mv`/`rm`/`chmod`/`chown` — a move unlinks each source it names, so a
      source is written to exactly as much as the destination is
    - for `cp`/`mv`/`ln`/`install`, the value of a target-directory flag
      (`-t DIR` / `--target-directory=DIR`). For `cp`/`ln`/`install`, this
      flag and the positional-last destination are mutually exclusive per
      GNU's own grammar: once `-t`/`--target-directory` is given, every
      non-flag argument is a source, not a destination, so the
      positional-last rule is skipped entirely in that case. `mv` still
      unlinks every source it names regardless of `-t`, so its non-flag
      arguments remain targets either way.
    - the last non-flag argument for `rsync`, and for `git` only the last
      positional argument of `git clone` (covers `git clone URL DEST`;
      other git subcommands are not treated as write-target-bearing here)
    - the value of a command-specific destination flag (`tar -C`/`--directory`,
      `unzip -d`, `curl -o`/`--output`, `wget -O`/`--output-document`)

    Before taking the last non-flag argument as the destination for `cp`/
    `ln`/`rsync`, value-taking options of theirs (`-S`/`--suffix`, `-t`/
    `--target-directory` for `cp`/`ln`; `--exclude`/`--include`/`--filter`/
    `-e`/`--rsh` for `rsync`) have their value token removed from the
    candidate list — including when the flag is the trailing letter of a
    short-option cluster (`-vS .bak`) — so that value is never mistaken for
    the destination.

    A member need not be a path — a bare descriptor number or `/dev/null`
    passes through untouched; only the two detection patterns decide
    whether a member matters.
    """
    targets = redirect_write_targets(redirects)
    non_flags = [a for a in args if not a.startswith("-")]

    flag_dests = (
        flag_destinations(args) if word in ("cp", "mv", "ln", "install") else []
    )

    if word == "install":
        # install は INPLACE_WRITERS の一員だが、cp/ln 同様 -t/--target-directory
        # が与えられた時点で宛先は既に決まっており、非フラグ引数は全てソース。
        # フラグが無ければ従来どおり最後の非フラグ引数だけが宛先で、先行する
        # 引数（コピー元）は読むだけ。
        # 値取りフラグ（-m 644 等）の値は位置引数ではない。除いてから
        # 末尾を取らないと、フラグ後置形で宛先を取り違える。
        positional = strip_value_tokens(word, args)
        if not flag_dests and positional:
            targets = targets + [positional[-1]]
    elif word in INPLACE_WRITERS or (
        word == "sed"
        and any(a.startswith("-i") or a.startswith("--in-place") for a in args)
    ):
        targets = targets + non_flags
    elif word in ("cp", "ln"):
        if flag_dests:
            # -t DIR / --target-directory=DIR は「宛先は既に決まっている」
            # という文法を表す。この場合すべての非フラグ引数はソースであり、
            # positional-last 規則を重ねて宛先扱いしてはいけない。
            pass
        else:
            positional = strip_value_tokens(word, args)
            if positional:
                targets = targets + [positional[-1]]
    elif word in ("mv", "rm", "chmod", "chown"):
        targets = targets + non_flags
    elif word == "rsync":
        positional = strip_value_tokens(word, args)
        if positional:
            targets = targets + [positional[-1]]
    elif word == "git":
        # git の文法は git_subcommand() が既に持っている。宛先が位置引数に
        # 現れるサブコマンドだけを write target として扱う。全サブコマンドの
        # 末尾引数を宛先扱いすると、`git log -- <path>` や `-m` のメッセージ
        # 本文まで書き込み先として照合される。
        sub, rest = git_subcommand(args)
        if sub == "clone":
            positional = [a for a in rest if not a.startswith("-")]
            if len(positional) >= 2:
                targets = targets + [positional[-1]]

    if word in ("cp", "mv", "ln", "install"):
        targets = targets + flag_dests

    targets = targets + flag_value_destinations(word, args)

    return targets


HOME_VAR = re.compile(r"^(?:\$\{HOME\}|\$HOME)")


def normalize_candidate(target):
    """Expand deterministic home forms and lexically normalize TARGET.

    Only static, filesystem-free transformations: `~`, `$HOME`, and
    `${HOME}` are replaced with the real HOME (known at hook-start, not
    resolved via the filesystem), then the result is run through
    os.path.normpath to collapse `..`/`.`/duplicate slashes lexically —
    no os.path.realpath, no stat, no subprocess.

    A trailing separator in TARGET's own spelling is restored afterward if
    normpath dropped it (item D of task0004's plan): normpath("/tmp/") is
    "/tmp", which no longer matches SAFE_DELETE's `/tmp/`-spelled
    alternative, so a resolved value naming a scratch root in directory
    form would otherwise be denied instead of allowed. TARGET is still a
    directory when the containment decision reads it; only its lexical
    spelling changed.
    """
    home = os.path.expanduser("~")
    expanded = target
    if expanded == "~" or expanded.startswith("~/"):
        expanded = home + expanded[1:]
    elif HOME_VAR.match(expanded):
        expanded = HOME_VAR.sub(home, expanded, count=1)
    normalized = os.path.normpath(expanded)
    # os.path.normpath is POSIX-compliant and preserves a leading `//`.
    # `/home/...` and `//home/...` are the same location, so this spelling
    # difference must not slip past the SELF_CONFIG boundary.
    normalized = re.sub(r"^//(?=[^/])", "/", normalized)
    if target.endswith("/") and not normalized.endswith("/"):
        normalized += "/"
    return normalized


def check_self_modification(word, args, redirects, segment, lexed, resolve):
    """Ask/deny only when an assembled write TARGET matches a protected path.

    Matching used to run over the whole segment text, so a command that
    merely READ a protected path — `grep -rn foo ~/.claude/skills/
    2>/dev/null`, say — was asked about as though it wrote there: the
    `2>/dev/null` made the old `writes` boolean true, and the segment text
    still contained `~/.claude/skills/` for SELF_CONFIG to match against.
    Testing the write-target set instead of the whole segment fixes that
    without touching either pattern's own definition.

    When LEXED is False (the parse-failure fallback), token provenance is
    unavailable, so the assembled target set cannot be trusted — falls back
    to matching the two patterns against the whole segment text instead,
    but only when a `writes` boolean (write-form redirect / INPLACE_WRITERS /
    `sed -i` / rm・mv・cp・ln・chmod・chown) is true, the same gate this
    judgment always had on this fallback path before the write-target set
    existed.

    Each raw candidate is resolved (RESOLVE — resolve_target() bound to this
    statement, task0001 item D) before either pattern is tested, so a write
    reached through a plain literal `VAR=value` is judged exactly as the
    literal path would be; a candidate that does not resolve is tested
    exactly as before (NFR2). Each candidate is also checked in its
    normalized form (`~`/`$HOME`/`${HOME}` expanded, `..` segments collapsed
    lexically) so equivalent spellings of a protected path are not missed.
    """
    if lexed:
        candidates = write_targets(word, args, redirects)
    else:
        writes = (
            any(REDIRECT.fullmatch(t) and not t.startswith("<") for t in redirects)
            or word in INPLACE_WRITERS
            or (word == "sed" and any(a.startswith("-i") for a in args))
            or word in ("rm", "mv", "cp", "ln", "chmod", "chown")
        )
        candidates = [segment] if writes else []
    for raw in candidates:
        target, _resolved, _sub, _hit = resolve(raw)
        normalized = normalize_candidate(target)
        if SELF_CONFIG.search(target) or SELF_CONFIG.search(normalized):
            decide(
                "ask",
                "self-modification",
                "Claude Code 自身の設定（settings / hooks / rules / agents / skills）への書き込み。"
                "権限やガードの挙動が変わるので、ユーザーの意図を確認する。",
            )
        if TRANSCRIPT.search(target) or TRANSCRIPT.search(normalized):
            decide(
                "deny",
                "transcript-write",
                "セッション transcript（~/.claude/projects/**/*.jsonl）への書き込み。"
                "これはハーネスが管理する状態で、書き換えると以降の判定すべてに影響する。"
                "読み取りは通常運用なので制限しない。",
            )


def check_external(word, args, segment):
    if word == "gh":
        sub = " ".join(a for a in args if not a.startswith("-"))[:40]
        if re.match(r"^(repo|release|secret|ssh-key|gpg-key)\s+delete", sub):
            decide("deny", "gh-delete", f"`gh {sub}` はリモート側で不可逆。")
        if re.match(r"^secret\s+set", sub):
            decide("deny", "gh-secret-set", "リポジトリ secret の書き換え。")
        if re.match(r"^pr\s+merge", sub):
            decide("ask", "gh-pr-merge", "PR のマージは他者から見える不可逆な操作。")
    if word in ("npm", "pnpm", "yarn") and "publish" in args:
        decide("deny", "package-publish", "パッケージの公開は取り消せない。")
    if word == "cargo" and "publish" in args:
        decide("deny", "package-publish", "crates.io への公開は取り消せない。")
    if word in ("docker", "podman"):
        joined = " ".join(args)
        if re.search(r"\b(system\s+prune|volume\s+rm|volume\s+prune)\b", joined):
            decide(
                "deny",
                "container-prune",
                "ボリューム/未使用リソースの一括削除は他プロジェクトにも及ぶ。",
            )
    if word == "systemctl" and not has(args, "--user"):
        if any(a in ("stop", "disable", "mask") for a in args):
            decide(
                "ask",
                "systemctl-system",
                "system スコープの unit を止める/無効化する操作。"
                "`--user` を付け忘れていないか確認する。",
            )
    if word == "gcloud":
        joined = " ".join(args)
        if re.search(
            r"\b(delete|remove-iam-policy-binding|add-iam-policy-binding)\b", joined
        ):
            decide(
                "ask",
                "cloud-iam",
                "クラウド側のリソース削除または IAM 変更。ローカルでは取り消せない。",
            )
    if word == "kubectl" and any(a in ("delete", "drain", "cordon") for a in args):
        decide("ask", "kubectl-destructive", "クラスタ上のリソースに対する破壊的操作。")
    if word == "terraform" and any(a in ("destroy", "apply") for a in args):
        decide("ask", "terraform", "インフラへの適用/破棄。")
    if word == "aws":
        joined = " ".join(args)
        if re.search(r"\b(rm|rb|delete-\w+|terminate-\w+)\b", joined):
            decide("ask", "cloud-delete", "AWS リソースの削除。")
    if word == "ssh":
        # `ssh host` alone is interactive; `ssh host '<cmd>'` runs remotely.
        remote = [a for a in args if not a.startswith("-")]
        if len(remote) >= 2:
            decide(
                "ask",
                "remote-exec",
                "リモートホスト上でのコマンド実行。手元のガードはリモート側には届かない。",
            )


def check_pipe_to_shell(segment):
    if re.search(
        r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(sh|bash|zsh|python\d?)\b", segment
    ):
        decide(
            "deny",
            "curl-pipe-shell",
            "ダウンロードしたスクリプトを検証せずに実行する形。"
            "一度ファイルに落として内容を確認してから実行する。",
        )


def check_bypass(segment, toks):
    for t in toks:
        if t in BYPASS_FLAGS:
            decide("deny", "safety-bypass", f"`{t}` は安全機構を明示的に外すフラグ。")
    if BYPASS_TOKEN.search(segment):
        decide(
            "deny",
            "safety-bypass",
            "名前自体が安全装置の解除を示す環境変数/フラグが含まれている。",
        )


def check_permissions(word, args):
    if word == "chmod":
        if any(a in ("777", "-R777", "a+rwx") for a in args) or (
            has(args, "-R", "--recursive")
            and any(re.fullmatch(r"[0-7]{3,4}", a) for a in args)
        ):
            decide("ask", "chmod-broad", "広い、または再帰的なパーミッション変更。")
    if word == "chown" and has(args, "-R", "--recursive"):
        decide("ask", "chown-recursive", "再帰的な所有者変更。")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail-open: a malformed payload is not our problem

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command.strip():
        sys.exit(0)

    # Whether kill-guard.py owns the verdict for this command. The destructive
    # checks below still run — a compound such as
    # `pkill -f x; rm -rf /home/sakura/y` must still be denied for its `rm`
    # half — but the blanket `allow` at the end is withheld, so kill-guard's
    # own deny/ask is never overridden. See KILL_WORDS above.
    defer_to_kill_guard = any(
        re.search(rf"(^|[^\w./-]){w}([^\w./-]|$)", command) for w in KILL_WORDS
    )

    # Judged on the whole command string, not per segment: `statements()`
    # splits on `|`, so a `curl … | sh` pipeline is never one unit inside the
    # loop below and the check would never fire.
    check_pipe_to_shell(command)

    # Materialized once: collect_assignments() needs the whole stream to
    # build its name-to-value map (item A), and the judgment loop below
    # walks the same list again. Neither pass re-lexes the command (NFR4) —
    # statements() itself still runs exactly once. Each statement's ORDINAL
    # travels with it from statements() itself (item F); collect_assignments()
    # and resolve_target() both read that same number rather than either one
    # re-deriving it with its own enumerate() over this list.
    all_statements = list(statements(command))
    values, reassigned = collect_assignments(all_statements)

    # item F's single declaration: RESOLVE (make_resolver()'s bound
    # resolve_target()) is handed to exactly two checks below —
    # check_self_modification() and check_rm() — matching FR3's fixed set
    # (the write-target judgment and the recursive-delete judgment). Every
    # other check in this loop (check_bypass, check_git,
    # check_file_destruction, check_external, check_permissions) reads TOKS/
    # SEGMENT/ARGS as statements() produced them, unresolved: a command that
    # supplies one of THEIR arguments through a variable keeps its base
    # verdict (task0004's "P"), and that is a decision recorded here once
    # rather than an oversight discovered by re-reading the whole loop.
    for segment, toks, lexed, scope, _conditional, ordinal, _ctoks in all_statements:
        check_bypass(segment, toks)

        words, redirects = split_redirects(toks, lexed)
        word, args = head(words)
        resolve = make_resolver(values, reassigned, scope, ordinal)
        # `> ~/.claude/settings.json` のようにコマンド語を持たない純リダイレクト
        # 文も対象を切り詰める。word が無くても redirects だけで判定する。
        check_self_modification(word or "", args, redirects, segment, lexed, resolve)
        if word is None:
            continue

        if word == "git":
            check_git(args, segment)
        elif word == "rm":
            check_rm(args, resolve)
        else:
            check_file_destruction(word, args, segment)
            check_external(word, args, segment)
            check_permissions(word, args)

    if ALLOW_NON_DESTRUCTIVE and not defer_to_kill_guard:
        decide("allow", None, "破壊的なパターンに一致しない。")
    sys.exit(0)


if __name__ == "__main__":
    main()

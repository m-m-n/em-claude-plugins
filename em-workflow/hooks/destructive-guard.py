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
kill-guard.py's job, and it runs as a separate PreToolUse hook. The same
withholding applies to `git worktree remove`, a non-force `git branch`
deletion, and `gh pr create` — those belong to failed-run-cleanup-guard.py;
see matches_target_shape().

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import bisect
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


# Characters shlex should emit as operator tokens of their own. The default
# set plus `\n`, which has to be removed from the whitespace set to survive
# as a separator — a newline ends a statement just as `;` does.
PUNCTUATION = "();<>|&\n"

# A transient, filesystem-free sentinel that stands in for a command
# substitution removed adjacent to other text in the same word (D7). It is
# introduced by _mark_substitutions() and consumed by _strip_unresolved_
# marks() before any token reaches a check — no downstream code ever sees
# it. NUL is chosen because it is not shlex whitespace, not a PUNCTUATION
# operator character, and not a quote, so it survives tokenization as
# ordinary word content without splitting or merging anything.
UNRESOLVED_MARK = "\x00"

# UNRESOLVED_MARK is followed by the decimal index of the CHUNK_SUBS entry
# the marker was produced from, then this terminator — e.g. `\x00 12 \x02`
# (spaces added only for legibility) for the 13th substitution in the
# current chunk. All three characters are, like UNRESOLVED_MARK itself, not
# shlex whitespace, not a PUNCTUATION operator, and not a quote, so the
# whole marker survives tokenization as ordinary word content. Carrying the
# index INSIDE the marker (destructive-guard-command-name-substitution) lets
# _strip_unresolved_marks() recover which CHUNK_SUBS entry produced a given
# surviving token by direct lookup, rather than by counting markers
# left-to-right across the token stream — a count that a lexer-dropped
# comment (`# $(cmd)`, consumed whole by shlex's `comments=True` and never
# reaching the token stream) silently desynchronizes from CHUNK_SUBS's own
# enumeration.
_MARK_TERMINATOR = "\x02"
_MARK_RE = re.compile(re.escape(UNRESOLVED_MARK) + r"(\d+)" + re.escape(_MARK_TERMINATOR))

# A second, distinct marker character used ONLY by extract_shell_payload()'s
# own quote-detection pass (_mark_quoted_substitutions(), task0001 FR4) — it
# never reaches head()/git_subcommand()/check_rm() or any other consumer of
# the main UNRESOLVED_MARK/SUBSTITUTION_STANDIN/Tok pipeline, so the marker
# structure those stages rely on is unchanged. Same properties as
# UNRESOLVED_MARK (not shlex whitespace, not a PUNCTUATION operator
# character, not a quote) so it survives tokenization as ordinary word
# content, and the same LENGTH (one character) so replacing a substitution
# match with this instead of UNRESOLVED_MARK never shifts any other
# character's position in the chunk — the two marked strings
# _mark_substitutions()/_mark_quoted_substitutions() produce from the same
# CHUNK lex into token sequences of identical shape (same segment/token
# boundaries), differing only in which of the two characters sits at a
# substitution's position, so extract_shell_payload() can read this marker
# at the SAME index it already uses in the ordinary marked sequence.
QUOTED_MARK = "\x01"

# Stand-in text for a token whose ENTIRE value was one or more command
# substitutions with nothing else in the word — the whole-word case
# (destructive-guard-command-substitution task0001 Design Part 1/2). Once
# _strip_unresolved_marks() finds nothing but marker residue left in a
# token, this is what it renders in place of the value that was never
# present, and what the reason text names as the offending delete target.
#
# Deliberately shaped like a command substitution so a reader recognizes it
# as one, and inert everywhere else a word can occupy: no leading `-` (never
# read as a flag), no match against REDIRECT's operator shape, no equal-to
# or leading match against any name in SAFE_DELETE_BUILD_ARTIFACTS/
# SAFE_DELETE_SCRATCH_ROOTS_*, no match against SELF_CONFIG or TRANSCRIPT,
# and no control character. check_rm() also judges the `.substitution_only`
# flag itself before this text is ever pattern-matched, so the token cannot
# reach the safe-root exception even if this text's own shape changed later.
SUBSTITUTION_STANDIN = "$(...)"

# Redirection operators, matched against a whole token. A redirect and its
# target are not arguments to the command and must be lifted out before the
# checks run, or `>` and `/dev/null` read as two more paths to delete.
REDIRECT = re.compile(r"\d*(?:>>?\|?|<<?<?|<>|>&|<&|&>>?)\d*")

# `<>` opens its target for both reading and writing (unlike `<`, `<<`,
# `<<<`, which are read-only) and must join the write-target set.
READWRITE_REDIRECT = re.compile(r"\d*<>\d*")

# A here-document operator on its own -- the opening `<<`/`<<-` plus its
# delimiter word, quoted or not -- matched per line rather than swallowing
# the body in one regex: several operators can share a line (task0001 FR3),
# and each operator's own body/delimiter-line search is now a separate,
# index-assisted lookup (see strip_heredocs()) rather than backtracking
# regex match. `<<<` (a here-string, not a here-document) stays excluded by
# the negative lookahead, unchanged from before this task.
HEREDOC_OP = re.compile(r"<<-?(?!<)[ \t]*(['\"]?)(\w+)\1")
# Commands that run what arrives on stdin, so a here-doc body aimed at one is
# not data but code, and has to be scanned like any other statement.
SHELL_SINK = re.compile(r"\b(sh|bash|zsh|dash|ksh|python\d?|perl|ruby|node)\b")
# The word-anchored form of SHELL_SINK (task0001 Component 2's "sink word"):
# matches only when the sink vocabulary BEGINS the word under test, for
# judging a heredoc's own host/enclosing command word directly instead of
# searching for a sink anywhere in a larger string. Kept as its own pattern
# rather than reusing SHELL_SINK via re.match() so an edit to one can never
# silently drift from the other -- the task plan requires them to stay the
# same vocabulary.
SINK_WORD_RE = re.compile(r"^(sh|bash|zsh|dash|ksh|python\d?|perl|ruby|node)\b")

# task0003 Change 2 (SC2's widened fallback match): the three characters a
# sink name can be split across without changing what the shell itself
# executes -- `b"a"s"h"` and `bash` run the identical program once quoting
# is resolved, and `\` before/between letters is likewise inert to a real
# shell in that position. Removing exactly these three characters from the
# heredoc-stripped chunk before re-running SHELL_SINK against it is enough
# to catch that spelling; nothing is evaluated (NFR1), and every character
# outside this set is left untouched.
_QUOTE_CHARS_TABLE = str.maketrans("", "", "'\"\\")


def _strip_quote_chars(text):
    """TEXT with every `'`, `"` and `\\` character removed -- see
    _QUOTE_CHARS_TABLE."""
    return text.translate(_QUOTE_CHARS_TABLE)


# Command words that treat stdin and their own arguments as data and never
# run them as a program (task0001 Component 2's "data command"). `sed`,
# `awk`, `sort`, and `rg` are deliberately absent -- each can take a program
# from its input or run one named in an option (task plan Terms). Reviewed
# change: any edit to this list is part of this task's contract.
DATA_COMMANDS = frozenset(
    {
        ":", "cat", "tee", "head", "tail", "wc", "uniq", "cut", "tr", "grep",
        "diff", "jq", "read", "echo", "printf", "git", "gh",
    }
)

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
# Mirrored in failed-run-cleanup-guard.py's own WRAPPERS — keep both in sync.
WRAPPERS = {"sudo", "env", "nohup", "time", "command", "nice", "ionice", "doas"}

# Wrapper options that take a value of their own (a separate token), keyed by
# wrapper name. Without consuming these, the value token is mistaken for the
# wrapped command word (`env -u NAME cp …` would read `NAME` as the command).
# `--flag=value` spellings are attached and need no extra consumption.
# Mirrored in failed-run-cleanup-guard.py's own WRAPPER_VALUE_FLAGS — keep
# both in sync.
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

# Glob wildcard characters, on their own. Kept separate from
# UNRESOLVED_EXPANSION below: a pure glob still reaches the safe-root
# exception in check_rm() (no variable/substitution involved), so its
# presence alone must not short-circuit the check the way an unresolved
# expansion does.
GLOB_CHARS = re.compile(r"[*?\[]")

# Variable expansion / command substitution — the subset of DYNAMIC above
# that makes a target's real destination unknowable no matter how it looks
# lexically. Glob characters are deliberately excluded; see GLOB_CHARS.
UNRESOLVED_EXPANSION = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]")

# Positional (`$1`-`$9`, bare — the `${10}`-style multi-digit spelling is
# already covered by UNRESOLVED_EXPANSION's `\$\{` alternative) and special
# (`$@ $* $# $? $$ $- $! $0`) parameter forms. Neither is a named variable
# (`[A-Za-z_]`), so UNRESOLVED_EXPANSION does not see them; their value is
# exactly as unknowable to a static reader as `$HOME` or `$(cmd)`.
UNRESOLVED_PARAM = re.compile(r"\$(?:[1-9]|[@*#$?!0-])")

# A leading `~` whose next character is neither `/` nor the end of the
# token — `~+`, `~-`, `~user`. normalize_candidate() only expands a bare
# `~` and a leading `~/`; every other tilde form passes through it
# unresolved, so folding a parent reference against the rest of the token
# is not trustworthy for these spellings either.
UNRESOLVED_TILDE = re.compile(r"^~(?!/|$)")

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

# Deletion targets safe enough to wave through even under `rm -rf`, split
# into the two classes check_rm()'s containment predicate (safe_delete_
# target(), defined next to check_rm()) judges against:
#
#   - build artifacts (relative targets only): safe when the target's
#     LEADING path component equals one of these exactly, either as the
#     whole target or with further components below it. An absolute path
#     spelled with the same name, or a component that merely starts with
#     the name (`build-debug`), is never safe — matching is on whole path
#     components only, never a text prefix.
#   - scratch roots: safe only for a proper descendant of the root; the
#     root itself, in any spelling that normalizes to it (`/tmp`, `/tmp/`),
#     is never safe. `/tmp`/`/var/tmp` match as absolute paths, `tmp`/
#     `.cache` as the leading relative path component.
#
# Matching runs on the target AFTER normalize_candidate() has folded it —
# home forms expanded, `.`/`..`/duplicate separators collapsed lexically —
# so a target that merely LOOKS like it starts with a safe root, but
# actually escapes it through a parent reference (`/tmp/../home/x`), is
# judged on where it lexically lands, not on its raw spelling. A path
# component below a matching root that both starts with `.` and carries a
# glob wildcard is excluded from the exception even then, because such a
# component can itself expand to `..` (a bare `*` cannot — shell globbing
# skips dotfiles, so it can never match `.` or `..`).
#
# Residual gap, left in place rather than silently accepted (D5, out of
# scope for this module): a symlink can make the REAL filesystem location
# of a normalized target differ from its lexical one. Closing that would
# require os.path.realpath, which both breaks the determinism this module
# promises and would touch the filesystem on every decision — this module
# never does either.
SAFE_DELETE_BUILD_ARTIFACTS = frozenset(
    {"node_modules", "dist", "build", "target", ".next", "coverage"}
)
SAFE_DELETE_SCRATCH_ROOTS_ABS = ("/tmp", "/var/tmp")
SAFE_DELETE_SCRATCH_ROOTS_REL = frozenset({"tmp", ".cache"})

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
    quoted span; whether the lexing layer removed a command substitution
    adjacent to this token's own text (D7); whether this token's own
    text is fabricated because the word it stands in for was built solely
    from one or more command substitutions with nothing else in it
    (`.substitution_only`, task0001 Design Part 1); whether, only for a
    `.substitution_only` token, the raw text of the single substitution it
    came from (`.raw_substitution_body`, task0002 FR11) — set after
    construction by _strip_unresolved_marks() via its occurrence-order
    mapping (see that function's docstring), never via this constructor;
    and whether the token's text passed through a quote state at any point
    while shlex built it (`.quoted`, task0004 postcondition 3/7) — a WORD
    token equal to a reserved word or `case`/`esac` by text alone (`"case"`,
    `'if'`) is not, itself, that keyword, and `.is_operator` cannot tell the
    two apart the way it does for `(`/`)` (neither a bare nor a quoted
    letter-word ever goes through the punctuation-sticky state); `.quoted`
    is the signal `_shape_leading()` uses instead for those checks.
    Every consumer besides split_redirects()/check_rm()/
    read_command_name_evidence()/_shape_leading() treats it as an ordinary
    str; every attribute defaults to a closed-fail value (False / None) so
    a plain str used where a Tok is expected fails closed.
    """

    is_operator = False
    unresolved = False
    substitution_only = False
    raw_substitution_body = None
    quoted = False

    def __new__(
        cls, value, is_operator=False, unresolved=False, substitution_only=False,
        quoted=False,
    ):
        obj = str.__new__(cls, value)
        obj.is_operator = is_operator
        obj.unresolved = unresolved
        obj.substitution_only = substitution_only
        obj.quoted = quoted
        return obj


class _TrackingLexer(shlex.shlex):
    """shlex.shlex that also records whether the token `get_token()` just
    returned began in the base class's punctuation state ('c') — i.e. bare,
    unquoted operator syntax — as opposed to a word or quoted span; and
    whether building that token ever passed through a quote state (task0004
    postcondition 3/7 — `last_was_quoted`), regardless of whether the quoted
    span was the whole token or only part of it.

    shlex resolves quoting before the token text ever reaches a caller, so a
    quoted `"2>&1"` and a real, unquoted `2>&1` come out as the identical
    string — and likewise a quoted `"case"` and a real, bare `case` both come
    out as the plain word `case`, with `.is_operator` False for both (neither
    ever enters the punctuation-sticky state 'c', since letters are never
    punctuation_chars). `last_was_quoted` is the analogous signal for that
    case: it is set the moment `state` is assigned one of shlex's own quote
    characters (`self.quotes`, default `'"`), and — like `last_was_operator`
    — is NOT cleared when the state later returns to plain word-building, so
    it stays true for the rest of that one token even if unquoted text
    follows the closing quote within the same word. `state` is overridden as
    a property purely to observe every assignment the base class's
    `read_token()` already makes; no parsing behaviour changes.
    """

    def __init__(self, *args, **kwargs):
        self.last_was_operator = False
        self.last_was_quoted = False
        super().__init__(*args, **kwargs)

    @property
    def state(self):
        return self.__dict__.get("_state", " ")

    @state.setter
    def state(self, value):
        self.__dict__["_state"] = value
        if value == "c":
            self.last_was_operator = True
        elif isinstance(value, str) and value in self.quotes:
            self.last_was_quoted = True

    def read_token(self):
        self.last_was_operator = False
        self.last_was_quoted = False
        return super().read_token()


_COMMENT_WORD_BOUNDARY = " \t\r\n;|&()<>"


def _blank_comments(text):
    """TEXT with every `#`-comment -- a `#` outside quotes, at the start of
    a word -- replaced by spaces from the `#` up to but NOT including its
    terminating newline. Quote tracking mirrors scan_structure()'s own
    shell-mode rule (a `#` inside a quoted span is literal, never a
    comment); a backslash-escaped character, in or out of quotes, is
    skipped whole so an escaped quote/`#` is never misread as one starting
    or ending. Kept as its own light, self-contained pass rather than a
    scan_structure() call because every lex_segments() caller already hands
    it a MARKED chunk (substitutions already replaced by marker residue),
    so no substitution/case tracking is needed to find a comment's own
    boundary here -- only where it starts and where its line ends.

    This exists because Python's shlex, given `commenters` containing `#`
    (its own default), swallows the comment's OWN terminating newline
    along with the comment text -- it never emits a separator token for
    that specific newline, so two statements split only by a trailing
    comment (`echo hi # x\nrm -rf y`) lex as ONE merged statement, with
    `rm -rf y` read as mere arguments to `echo` rather than as its own
    statement. Blanking the comment text here, while leaving the newline
    itself in place, removes every `#` character before the lexer ever
    sees one (lex_segments() below turns its OWN `commenters` off to
    match) -- so the newline the comment used to swallow now reaches the
    lexer as ordinary text and is tokenized as a real, counted separator,
    same as any other newline. This does not change the WORDS surrounding
    a comment -- comment text was already discarded, never yielded as a
    token, on the old commenters path too -- only whether the newline that
    follows still separates them.
    """
    out = list(text)
    n = len(text)
    q = None
    i = 0
    while i < n:
        c = text[i]
        if q:
            if c == q:
                q = None
            elif c == "\\" and q == '"' and i + 1 < n:
                i += 1
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c in ("'", '"'):
            q = c
            i += 1
            continue
        if c == "#" and (i == 0 or text[i - 1] in _COMMENT_WORD_BOUNDARY):
            j = text.find("\n", i)
            end = j if j != -1 else n
            for k in range(i, end):
                out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def lex_segments(chunk):
    """Split a chunk into statements, each returned as (tokens, lexed, sep).

    Separators only count when they sit OUTSIDE quotes, and telling those
    apart is the whole reason shlex does the splitting rather than a regex.
    `echo 'a; rm -rf /x'` is one statement headed by `echo`; a quote-blind
    split reads it as two and finds a recursive delete in the second, which
    denied a command that deletes nothing. Literal command text like that
    shows up constantly in generated docs, tests, and commit messages.

    LEXED is True on this path: each returned token is a Tok, carrying (as
    `.is_operator`) whether shlex read it from bare operator syntax or from
    a word/quoted span — the signal split_redirects() needs to tell a real
    `>` apart from a quoted string that merely looks like one — and (as
    `.quoted`, task0004) whether building the token passed through a quote
    state at all, the analogous signal `_shape_leading()` needs to tell a
    bare `case`/reserved word apart from a quoted string that merely
    matches its text (`.is_operator` cannot do this for a word: neither a
    bare nor a quoted letter-word ever enters the punctuation-sticky state).

    SEP (task0001, case-pattern tracking) is the raw separator text that
    ended this statement (possibly fused with an adjacent separator, e.g.
    `;;\n` when a newline directly follows a double-semicolon with no
    space — punctuation_chars fuses contiguous punctuation regardless of
    which characters they are), or None for the trailing statement, which
    has nothing following it in this chunk. statements() reads whether
    `";;"` occurs in SEP to know a case item just ended; nothing else in
    this file consults it.

    Falls back to the regex split when the chunk will not parse — an
    unbalanced quote, usually. That path keeps the old false positives and
    returns LEXED False (and SEP always None, since separator provenance is
    unavailable there too); a parse failure is rare, and waving the chunk
    through unexamined would be a hole rather than a nuisance. The fallback
    reads the ORIGINAL, un-blanked CHUNK — _blank_comments() only changes
    which characters a `#` comment's own newline separates, never which
    quote pairing balances, so nothing about when this path is taken
    changes; keeping it on the original text avoids any risk, however
    small, of the blanking pass itself disagreeing with shlex about where
    an unbalanced quote sits.
    """
    try:
        lex = _TrackingLexer(
            _blank_comments(chunk), posix=True, punctuation_chars=PUNCTUATION
        )
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        lex.commenters = ""
        toks = []
        while True:
            raw = lex.get_token()
            if raw is None or raw == lex.eof:
                break
            toks.append(Tok(raw, lex.last_was_operator, quoted=lex.last_was_quoted))
    except ValueError:
        return [
            (tokens(seg), False, None)
            for seg in SEGMENT_SPLIT.split(chunk)
            if seg.strip()
        ]

    out, current = [], []
    for t in toks:
        # punctuation_chars makes shlex fuse adjacent punctuation into one
        # token, so a separator with no space before the next operator
        # (';>', '\n(') arrives as a single token that is neither a clean
        # separator nor a clean operator. Split such fused tokens back into
        # their runs — each all-SEGMENT_CHARS or all-non-SEGMENT_CHARS —
        # before the separator test below, carrying is_operator forward onto
        # every piece so split_redirects() still recognizes the operator half.
        if t and all(c in PUNCTUATION for c in t) and not all(
            c in SEGMENT_CHARS for c in t
        ):
            pieces, i = [], 0
            while i < len(t):
                # `>|` `>&` `&>>` は 1 個のリダイレクト演算子。`|` / `&` が
                # SEGMENT_CHARS でも、演算子全体は割らずに 1 片として残す。
                # 割ると区切りと解釈され、リダイレクト先が次の文へ流出する。
                if REDIRECT.fullmatch(t[i:]):
                    pieces.append(t[i:])
                    break
                j = i + 1
                while j < len(t) and (t[j] in SEGMENT_CHARS) == (
                    t[i] in SEGMENT_CHARS
                ):
                    j += 1
                pieces.append(t[i:j])
                i = j
            segs = [Tok(p, t.is_operator) for p in pieces]
        else:
            segs = [t]
        for seg in segs:
            if (
                seg
                and all(c in SEGMENT_CHARS for c in seg)
                and getattr(seg, "is_operator", False)
            ):
                out.append((current, True, seg))
                current = []
            else:
                current.append(seg)
    out.append((current, True, None))
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


def _payload_index(seq, start):
    """Return the index in SEQ of the first token at/after START that is not
    a `.substitution_only` placeholder — an unquoted, unresolved expansion
    that resolves to nothing disappears along with its whole word in a real
    shell, so the word after it is what actually carries a payload. Falls
    back to START itself when nothing past it qualifies (or START is already
    out of range), so a caller can always index SEQ with the result when
    START itself was in range.
    """
    j = start
    while j < len(seq) and getattr(seq[j], "substitution_only", False):
        j += 1
    return j if j < len(seq) else start


def extract_shell_payload(toks, lexed, quoted_toks=None):
    """Return the literal script a shell-invocation segment (TOKS) will
    execute via `-c`, `eval`, or a here-string (`<<<`) redirect aimed at a
    shell word — or None when the segment is not such an invocation, its
    payload is not a single literal token statements() can push back onto
    its own queue and re-scan like any other statement, or (task0001 FR4/
    FR7) the payload argument position is a substitution enclosed in
    quotes.

    Out-of-scope declaration (FR7, task0002; stated identically in the case
    labels for the two forms it covers and here — a divergence in scope
    between the two is a defect): this hook's static analysis deliberately
    does not decide two forms, both left `allow` by design rather than by
    oversight. First, the form returning None here — a substitution enclosed
    in quotes at the payload position — because deciding it would require
    evaluating the substitution's own expanded output as the script body,
    and this module never evaluates anything (NFR1). Second, unrelated to
    this function — read_command_name_evidence()'s "unreadable" result — a
    substitution-headed statement whose command name cannot be read
    statically out of the substitution's own text.

    Only lexed (LEXED True) segments are examined: token provenance is what
    tells split_redirects() a real `<<<` apart from a quoted word that merely
    looks like one, and head()/split_redirects() both expect that provenance
    to be present. On the parse-failure fallback (LEXED False) this returns
    None, same as any other feature here that depends on tokenization; the
    fallback's own whole-segment matching still sees the raw text.

    Structural decisions (which word is the command, which args are `-c`/
    redirects) are made on marker-stripped spellings, so residual
    UNRESOLVED_MARK characters in TOKS cannot desync those comparisons; the
    payload text itself is still pulled from the corresponding marked token,
    so its substitution evidence survives into the re-scanned statement.

    QUOTED_TOKS (task0001 FR4) is statements()'s parallel lexing of the SAME
    chunk through _mark_quoted_substitutions() instead of
    _mark_substitutions() — identical token shape, differing only in
    whether a payload-position substitution's marker is QUOTED_MARK (it sat
    inside a pair of double quotes in the raw text) or UNRESOLVED_MARK
    (everywhere else, including no quotes at all, single quotes — a real
    shell would not expand a substitution there either, but this module has
    never distinguished that — or quotes mixed with other text). None (the
    caller could not supply a same-shaped parallel) is treated as "never
    quoted", which reproduces this function's pre-FR4 behaviour exactly
    rather than guessing.

    When the argument sitting right after `-c` (or a bare here-string
    target) is itself a whole-word substitution (`.substitution_only`):

    - Unquoted (FR5, unchanged): an unresolved expansion that resolves to
      nothing disappears along with its entire word in a real shell, so the
      word AFTER it is what `-c`/the here-string actually runs — this walks
      past any run of such placeholders to find that word (_payload_index()),
      falling back to the placeholder itself when nothing follows it.
    - Quoted (FR4): the word survives even an empty expansion (a quoted
      empty string is still one argument), so THIS position — not the next
      word — is the real payload boundary; the following argument is the
      shell's own `$0`, not script text, and is left alone (no promotion).
      The substitution's own expanded output is what a real shell would
      actually run there, but resolving that requires evaluating the
      substitution, which this module never does (NFR1) — out of scope, by
      design (FR7, same declared range as read_command_name_evidence()'s
      "unreadable": a form whose substitution's expanded output itself
      becomes the script body is outside this hook's static analysis). This
      function returns None for that position rather than guess at it.

    Both bullets above apply ONLY when the payload-position word is a
    substitution IN ITS ENTIRETY (`.substitution_only`) — checked first, on
    both the `-c` side and the here-string side alike (task0002 FR4/FR5/
    FR12: the two are now symmetric). Anything else at that position —
    including a word that merely CONTAINS a quoted substitution somewhere
    inside it, mixed with other text — always falls to the plain, always-
    re-scan return below, regardless of quoting. Before task0002 the `-c`
    side tested containment (`QUOTED_MARK` present ANYWHERE in the word)
    without checking whole-word-ness first, which silently cancelled the
    rescan of an ordinary mixed body — `bash -c 'cd "$(dirname /a/b)" &&
    rm -rf ~'` interpolates a directory name next to a destructive command,
    and the quoted substitution nested inside that word was enough to stop
    the rescan of the whole argument. The here-string side already tested
    whole-word-ness first; the `-c` side now matches it.

    Only stage 3 (this function and its helpers) ever reads quote
    information; the marker structure (UNRESOLVED_MARK / SUBSTITUTION_STANDIN
    / Tok's three attributes) is unchanged, and no quote knowledge leaks
    into head() / git_subcommand() / check_rm(), which keep working from
    tokens alone.
    """
    if not lexed:
        return None

    # Structural decisions use marker-stripped spellings. The parallel
    # marked lists retain the evidence that must be copied into a payload
    # before statements() scans it again.
    comparison_toks = _strip_unresolved_marks(toks)
    words, redirects = split_redirects(comparison_toks, lexed)
    marked_words, marked_redirects = split_redirects(toks, lexed)
    if len(words) != len(marked_words) or len(redirects) != len(marked_redirects):
        # A mismatch means the marker's presence made split_redirects() draw
        # the word/redirect boundary differently between the two passes.
        # Falling back to `return None` here would skip re-scanning the
        # payload entirely (fail-open); instead fall back to judging and
        # extracting from the marked side alone, same as before this mismatch
        # check existed.
        words, redirects = marked_words, marked_redirects

    # task0001 FR4: QUOTED_TOKS mirrors TOKS's own shape (see docstring). A
    # length mismatch against marked_words/marked_redirects — the same
    # failure mode the block above already guards against for the ordinary
    # marked side — falls back to "never quoted" rather than guessing.
    if quoted_toks is not None:
        quoted_words, quoted_redirects = split_redirects(quoted_toks, lexed)
        if len(quoted_words) != len(marked_words) or len(
            quoted_redirects
        ) != len(marked_redirects):
            quoted_words, quoted_redirects = marked_words, marked_redirects
    else:
        quoted_words, quoted_redirects = marked_words, marked_redirects

    word, args = head(words)
    marked_args = marked_words[-len(args):] if args else []
    quoted_args = quoted_words[-len(args):] if args else []

    if word == "eval":
        return " ".join(marked_args) if marked_args else None
    if word in SHELL_WORDS:
        if "-c" in args:
            idx = args.index("-c")
            if idx + 1 < len(args):
                # task0002 FR4/FR5: symmetric with the here-string branch
                # below — whole-word-ness is checked FIRST. A word that is
                # not a substitution in its entirety always falls straight
                # through to the plain return, regardless of quoting; only
                # a whole-word substitution's OWN quoting decides between
                # "this is the payload boundary" (quoted) and "promote to
                # the next word" (unquoted).
                if not getattr(args[idx + 1], "substitution_only", False):
                    return marked_args[idx + 1]
                if idx + 1 < len(quoted_args) and QUOTED_MARK in quoted_args[idx + 1]:
                    return None
                return marked_args[_payload_index(args, idx + 1)]
        i = 0
        while i < len(redirects):
            t = redirects[i]
            if REDIRECT.fullmatch(t):
                if t == "<<<" and i + 1 < len(redirects):
                    # split_redirects() puts only the `<<<` operator and the
                    # ONE token right after it into `redirects`; every other
                    # word of the statement lands in `words`. So when that
                    # one token is a `.substitution_only` placeholder, the
                    # next candidate is not further along in `redirects` —
                    # it is the first non-placeholder word in `words[1:]`,
                    # the actual here-string body a real shell would run.
                    if not getattr(redirects[i + 1], "substitution_only", False):
                        return marked_redirects[i + 1]
                    if i + 1 < len(quoted_redirects) and QUOTED_MARK in quoted_redirects[i + 1]:
                        return None
                    j = _payload_index(words, 1)
                    if j > 0 and not getattr(words[j], "substitution_only", False):
                        return marked_words[j]
                    return marked_redirects[i + 1]
                i += 2
            else:
                i += 1
    return None


class HeredocRecord:
    """One here-document found by strip_heredocs(): BODY is the raw text
    removed for it, and OP_START/OP_END are the character offsets, in the
    STRIPPED chunk strip_heredocs() returns, of this heredoc's own operator
    (`<<`/`<<-` through its delimiter word) -- enough to find, by re-lexing
    around that span, which statement the operator sits in (Component 2's
    "host statement"), without strip_heredocs() itself needing to know
    anything about statements, substitutions, or pipelines.

    QUOTED is whether the delimiter word itself was written quoted
    (`<<'EOF'`/`<<"EOF"`/`<<\\EOF`) -- when it is, the shell never expands
    anything inside the body (it is taken completely literally), but when
    it is NOT, the shell expands `$(...)`/`` `...` `` inside the body before
    the body ever reaches the destination command -- true regardless of
    whether that destination is a data command or a sink. A `data`
    destination therefore still needs its body's own substitutions scanned
    whenever QUOTED is False; only a quoted delimiter makes the body inert.
    """

    __slots__ = ("body", "op_start", "op_end", "quoted")

    def __init__(self, body, op_start, op_end, quoted=False):
        self.body = body
        self.op_start = op_start
        self.op_end = op_end
        self.quoted = quoted


def _delimiter_line_word(line):
    r"""The bare word LINE closes a heredoc with, if LINE -- its own
    trailing newline, if any, ignored -- is nothing but optional leading/
    trailing spaces/tabs around a run of word characters; None otherwise.
    Matches the closing-line shape the single-pattern strip this replaces
    always accepted (`^[ \t]*WORD[ \t]*$`), for both `<<` and `<<-` alike --
    this task does not change that (task plan Design, "current handling
    stays" for delimiter lines).
    """
    text = line[:-1] if line.endswith("\n") else line
    m = re.match(r"^[ \t]*(\w+)[ \t]*$", text)
    return m.group(1) if m else None


def _line_comment_start(line):
    """The offset of a `#`-comment's start in LINE (one operator line from
    strip_heredocs(), never a heredoc body line), or None. Mirrors Component
    1's own word-start/quote rules (scan_structure()'s `_at_word_start()`
    and its quote handling) but scoped to one line, since an operator line
    is examined here before any statement/substitution structure has been
    resolved: a `#` outside quotes and at the start of a word starts a
    comment that runs to the end of LINE, and an operator inside that
    comment (`# <<X`) is not a real heredoc operator at all -- see this
    function's call site.
    """
    quote = None
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"' and i + 1 < n:
                i += 1
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c in ("'", '"'):
            quote = c
            i += 1
            continue
        if c == "#" and (i == 0 or line[i - 1] in " \t\r\n;|&()<>"):
            return i
        i += 1
    return None


def strip_heredocs(chunk):
    """Return (CHUNK with every heredoc body removed, an ordered list of
    HeredocRecord). See the task plan's Component 1 for the exact
    postconditions this implements; in short:

    - A line with one heredoc operator strips exactly as the old single-
      pattern version did: the operator line stays, the body and the
      delimiter line go.
    - Several operators on one line consume body lines in left-to-right
      order, each up to its own delimiter line, the next starting right
      after that delimiter line.
    - An operator whose delimiter never appears in the rest of the input
      consumes nothing (its would-be body stays in the chunk, exactly as
      before this task), and does not stop a LATER operator on the same
      line from finding its own delimiter independently.
    - An operator inside a `#`-comment on its own line (_line_comment_start()
      above) is never collected, at any position on the line: the text
      after `#` is never real syntax, so a `<<DELIM` written there opens no
      heredoc and consumes no body -- it stays in the chunk as ordinary
      (comment) text, exactly as a real shell would leave it.

    Delimiter-line CANDIDATES (every line that is nothing but a bare word,
    per _delimiter_line_word()) are indexed once, up front, into
    WORD_TO_LINES. Finding (or ruling out) a given operator's own closing
    line is then a bisect lookup into that word's own candidate list --
    O(log m), m being how many lines share that one word -- rather than a
    linear scan of everything after the operator. This is what keeps an
    unterminated operator from costing a fresh scan of the remaining input
    (NFR3, TM-5): the line-by-line pass below still visits every line
    exactly once, in order, and a delimiter that never appears anywhere
    later is discovered by an empty/exhausted bisect range, never by
    reading all the way to the end of the chunk.
    """
    lines = chunk.splitlines(keepends=True)
    n = len(lines)
    word_to_lines = {}
    for idx, line in enumerate(lines):
        word = _delimiter_line_word(line)
        if word is not None:
            word_to_lines.setdefault(word, []).append(idx)

    out = []
    records = []
    out_len = 0
    i = 0
    while i < n:
        line = lines[i]
        matches = list(HEREDOC_OP.finditer(line))
        comment_start = _line_comment_start(line)
        if comment_start is not None:
            matches = [m for m in matches if m.start() < comment_start]
        if not matches:
            out.append(line)
            out_len += len(line)
            i += 1
            continue
        # The operator line is kept verbatim; each operator's own offset in
        # the STRIPPED output is fixed before it, since appending LINE
        # unchanged does not move where its own text starts.
        op_positions = [
            (out_len + m.start(), out_len + m.end(), m.group(2), bool(m.group(1)))
            for m in matches
        ]
        out.append(line)
        out_len += len(line)
        start = i + 1
        for op_start, op_end, delimiter, quoted in op_positions:
            candidates = word_to_lines.get(delimiter, ())
            pos = bisect.bisect_left(candidates, start)
            if pos < len(candidates):
                found = candidates[pos]
                records.append(
                    HeredocRecord(
                        "".join(lines[start:found]), op_start, op_end, quoted
                    )
                )
                start = found + 1
            # No candidate at/after START for THIS operator: it consumes
            # nothing, and START stays put, so a LATER operator on this
            # same line still searches from the same point (Component 1
            # postcondition 3).
        i = start
    return "".join(out), records


# --- Component 2: per-heredoc destination decision -------------------------
#
# A heredoc's body is data, sink-bound, or of undeterminable destination,
# judged from the statement its own operator sits in (the "host statement")
# and, when that statement is itself inside a command substitution, every
# statement enclosing that substitution in turn -- see the task plan's
# Component 2 for the exact rules. The functions below implement that
# decision; _heredoc_destinations() is the single entry point statements()
# calls, once per popped chunk, with every heredoc found in it.

# Process-substitution operators (`<(`/`>(`), matched either as one fused
# token (adjacent in the source, e.g. `>(bash)`) or as two adjacent operator
# tokens (a space in between, e.g. `> (bash)`) -- see _has_process_
# substitution().
PROCESS_SUB_TOKENS = ("<(", ">(")

# VAR=value assignment shape, the same test _skip_assignments_and_wrappers()
# applies inline -- kept as its own named pattern here rather than reusing a
# private detail of that function, since _is_assignment_only() below checks
# it against an ALREADY-shaped statement's remaining words, a different
# question ("is EVERY word one of these") from that function's own ("skip a
# run of these at the front").
ASSIGNMENT_PREFIX = re.compile(r"^[A-Za-z_]\w*=")

class _StmtInfo:
    """One statement's contribution to a heredoc destination decision: its
    own command WORD (None when it has none of its own, or lexing failed --
    see PARSE_FAILED), whether a LATER statement in its own pipeline has a
    sink command word (PIPELINE_SINK), whether it contains a process
    substitution (HAS_PROCESS_SUB), and whether every one of its own words
    is a VAR=value assignment (IS_ASSIGNMENT_ONLY -- the exemption
    Component 2 gives an enclosing statement that only stores a
    substitution's output).
    """

    __slots__ = (
        "word", "pipeline_sink", "pipeline_undetermined", "has_process_sub",
        "is_assignment_only", "parse_failed",
    )

    def __init__(
        self, word=None, pipeline_sink=False, pipeline_undetermined=False,
        has_process_sub=False, is_assignment_only=False, parse_failed=False,
    ):
        self.word = word
        self.pipeline_sink = pipeline_sink
        self.pipeline_undetermined = pipeline_undetermined
        self.has_process_sub = has_process_sub
        self.is_assignment_only = is_assignment_only
        self.parse_failed = parse_failed


# `git`/`gh` are in DATA_COMMANDS on the premise that their stdin/arguments
# are never executed. `-c <name>=<value>` breaks that premise: it can define
# a shell alias (`-c alias.x=!bash`) that a following subcommand invocation
# then runs, turning what looks like a data command into code execution.
# `--config-env=<name>=<envvar>` reads the value out of an environment
# variable instead of the command line, but defines the exact same kind of
# config entry — same risk, same treatment. Any `-c`/`--config`/
# `--config-env`/`--git-dir`-style option value cannot be read statically
# for this, so a gh invocation carrying a bare `-c` (or `-C`, which git also
# treats as a global option position, though it only changes cwd) is judged
# conservatively: not a data command at all.
#
# `git` itself no longer uses this condition (task0003, IMPLEMENTATION.md
# D3/SC1): its own data/undeterminable split is _git_is_data() below, a
# closed list of built-in subcommands rather than a flag blocklist, because
# an alias route through `git` is not confined to `-c`/`--config`/
# `--config-env`/GIT_CONFIG_* — any subcommand not on that closed list can
# itself BE an alias defined by a configuration source this module never
# reads (a `.gitconfig` file, say), and a flag-shaped test can only ever
# catch the routes that happen to look like a flag. `gh` keeps this
# condition unchanged; task0003 changes what SC1 decides for `git` only.
GIT_LIKE_DATA_COMMANDS = frozenset({"gh"})
GIT_UNSAFE_GLOBAL_FLAGS = {"-c", "--config", "--config-env"}

# GIT_CONFIG_COUNT/GIT_CONFIG_KEY_<n>/GIT_CONFIG_VALUE_<n>/
# GIT_CONFIG_PARAMETERS, set as VAR=value assignments leading a gh
# invocation, configure it exactly as `-c`/`--config`/`--config-env` do —
# including defining an alias — with no `-c`-shaped flag anywhere on the
# command line for the checks above to see. (`git` no longer reads this;
# see GIT_LIKE_DATA_COMMANDS above.)
GIT_CONFIG_ENV_RE = re.compile(r"^GIT_CONFIG_(COUNT|KEY_\d+|VALUE_\d+|PARAMETERS)=")


def _git_alias_risk(word, shaped, leading=()):
    """True when WORD is `gh` and either SHAPED (its own shaped argument
    list, command word included) carries a `-c`/`--config`/`--config-env`
    global option, or LEADING (the VAR=value assignment tokens stripped
    from in front of the command word before SHAPED was built) carries a
    GIT_CONFIG_-prefixed assignment — see GIT_LIKE_DATA_COMMANDS's own
    comment for why either disqualifies it from being treated as a data
    command. `git` is judged by _git_is_data() instead, not by this
    function (task0003)."""
    if word not in GIT_LIKE_DATA_COMMANDS:
        return False
    if any(GIT_CONFIG_ENV_RE.match(a) for a in leading):
        return True
    for a in shaped[1:]:
        if a in GIT_UNSAFE_GLOBAL_FLAGS or any(
            a.startswith(f"{flag}=") for flag in GIT_UNSAFE_GLOBAL_FLAGS
        ):
            return True
    return False


# `git`'s own global options that take a value, either as a separate token
# or attached with `=` — task0003 Change 1, task plan step 1. Skipped left
# to right before the subcommand word is read, so `git -c user.name=x
# commit` and `git -C /tmp/r commit` still reach their subcommand.
GIT_GLOBAL_VALUE_FLAGS = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
)
# `git`'s own global options that take no value — skipped the same way, but
# consuming only their own token.
GIT_GLOBAL_BOOLEAN_FLAGS = frozenset(
    {
        "-p", "-P", "--paginate", "--no-pager", "--bare", "--no-replace-objects",
        "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
        "--icase-pathspecs", "--no-optional-locks",
    }
)

# The closed list of `git` built-in subcommands SC1 treats as data (task
# plan step 3) — stdin/arguments a real shell never hands to a configured
# or option-named program. `credential` and `hook` are deliberately absent
# (each hands stdin to a configured program); so are `bisect`,
# `filter-branch`, `submodule`, `difftool`, `mergetool` and `rebase` (each
# runs a program named in its own options or configuration). Any subcommand
# NOT on this list — including an alias defined by any configuration
# source, an external `git-*` program, or an unlisted built-in — is
# undeterminable (task plan step 4): a built-in cannot be shadowed by an
# alias, so this closed list is the only route through which an alias can
# be reached.
GIT_DATA_SUBCOMMANDS = frozenset(
    {
        "add", "am", "apply", "blame", "branch", "cat-file", "check-attr",
        "check-ignore", "check-mailmap", "commit", "commit-tree", "diff",
        "diff-tree", "fast-import", "hash-object", "interpret-trailers",
        "log", "ls-files", "ls-tree", "mailinfo", "mailsplit", "mktag",
        "mktree", "notes", "rev-list", "rev-parse", "show", "status", "tag",
        "update-index", "update-ref",
    }
)


def _statically_unknown_word(word):
    """Whether WORD -- a shaped token -- cannot be read statically: built
    entirely from a command substitution (`.substitution_only`), or
    carrying an unresolved variable/positional/special-parameter expansion
    anywhere in its own text (UNRESOLVED_EXPANSION/UNRESOLVED_PARAM — the
    same two tests check_rm() already uses for an unresolvable rm target).
    """
    return bool(
        getattr(word, "substitution_only", False)
        or UNRESOLVED_EXPANSION.search(word)
        or UNRESOLVED_PARAM.search(word)
    )


def _git_is_data(args):
    """Whether a `git` statement counts as a data command (task0003 Change
    1 / task plan "Change 1: the git condition in statement classification
    (SC1)"). ARGS is everything after the `git` command word itself (as
    head() returns it) -- global options, the subcommand, and whatever
    follows.

    Global options are skipped left to right first (GIT_GLOBAL_VALUE_FLAGS/
    GIT_GLOBAL_BOOLEAN_FLAGS, task plan step 1). The statement is
    undeterminable (returns False) when, after that skip: another
    `-`-leading word remains before a subcommand is reached (this includes
    `--exec-path`, which is not on either recognized-option list, so it
    falls straight into this case); no subcommand word remains; or the
    subcommand word cannot be read statically (_statically_unknown_word()).
    Only a subcommand on the closed GIT_DATA_SUBCOMMANDS list makes the
    statement data; any other subcommand is undeterminable (task plan step
    4) -- including one that is itself an alias defined by any
    configuration source (`.gitconfig`, `-c`, `--config-env`,
    GIT_CONFIG_*, …): a built-in cannot be shadowed by an alias, so an
    alias can only be reached through a subcommand this list does not
    contain, and that route is already undeterminable by construction.
    Assignments in front of the statement (GIT_CONFIG_COUNT=… and similar)
    therefore need no special-case handling here — unlike gh's own
    condition (_git_alias_risk()), which still reads them.
    """
    i = 0
    n = len(args)
    while i < n:
        a = args[i]
        if a in GIT_GLOBAL_VALUE_FLAGS:
            i += 2
            continue
        if any(a.startswith(f"{flag}=") for flag in GIT_GLOBAL_VALUE_FLAGS):
            i += 1
            continue
        if a in GIT_GLOBAL_BOOLEAN_FLAGS:
            i += 1
            continue
        break
    if i >= n or args[i].startswith("-"):
        return False
    sub = args[i]
    if _statically_unknown_word(sub):
        return False
    return sub in GIT_DATA_SUBCOMMANDS


# Compound-statement keywords that can start a pipeline continuation stage
# (`cmd | if ...; then bash; fi`, `cmd | while read x; do bash; done`,
# `cmd | for x in ...; do bash; done`, `cmd | case $x in ...) bash;; esac`,
# `cmd | select x in ...; do bash; done`). Component 3's own per-statement
# shaping strips one of these via _shape_leading() (RESERVED_SKIP_WORDS)
# exactly as statements()'s own per-segment scan does, which is right for
# THAT scan (it later sees every one of the compound's own inner segments
# as its own, separately-lexed statement) but wrong for pipeline lookahead
# (_pipeline_downstream()): that function only ever looks at ONE lexer
# segment per pipeline stage (the text up to the compound's own first
# `;`/newline), so stripping the keyword and reading the word behind it
# (`if :` -> `:`, a DATA_COMMANDS entry) misses every later branch of the
# SAME compound statement (`then bash; fi`) that a real shell would also
# feed this stage's stdin -- and, through it, the piped-in heredoc body.
# Recognised on the RAW, unshaped token so the stage is judged
# conservatively as "other" rather than by the now-hidden word behind the
# keyword.
COMPOUND_STATEMENT_KEYWORDS = frozenset(
    {"if", "while", "until", "for", "case", "select"}
)


def _is_pipe_sep(sep):
    """Whether SEP -- the raw separator lex_segments() returned for a
    statement -- is a Pipeline separator per the task plan's Terms: `|` or
    `|&`, allowing a fused trailing newline (a pipe directly followed by a
    line break; punctuation_chars fuses the two into one separator token).
    """
    if not sep:
        return False
    return sep.replace("\n", "") in ("|", "|&")


def _has_process_substitution(toks):
    """Whether TOKS -- one statement's own raw (unshaped) tokens -- contains
    a process substitution opener. `>(`/`<(` survive lex_segments() as one
    fused token when adjacent in the source (both characters are
    PUNCTUATION and neither is a SEGMENT_CHARS separator, so lex_segments()'s
    own fused-token re-split keeps them together); the two-token check below
    covers the same construct written with a space before the `(`.
    """
    for idx, t in enumerate(toks):
        if t in PROCESS_SUB_TOKENS:
            return True
        if (
            t in ("<", ">")
            and getattr(t, "is_operator", False)
            and idx + 1 < len(toks)
            and toks[idx + 1] == "("
            and getattr(toks[idx + 1], "is_operator", False)
        ):
            return True
    return False


def _is_assignment_only(words_only):
    """Whether every one of WORDS_ONLY (a statement's own words BEFORE
    _shape_leading()'s command-position skip -- redirects already pulled
    out, but nothing else) is a VAR=value assignment, and there is at
    least one -- the exemption Component 2 gives an enclosing statement
    whose only job is to store a substitution's output (`x="$(cat <<'EOF'
    ... EOF)"`). Deliberately NOT the shaped remainder _shape_leading()
    itself would produce: a statement that is nothing BUT assignments has
    _shape_leading() consume every one of them as leading VAR=value
    tokens, leaving an EMPTY remainder -- `bool([])` is False, so checking
    the remainder can never recognise the exact shape this function's own
    docstring example names as its purpose. Checking the PRE-skip words
    instead means a real command word surviving the skip (`FOO=bar cat`)
    still fails this test on its own account (`cat` itself does not match
    ASSIGNMENT_PREFIX), so the result is identical to checking the
    remainder in every case except the one the remainder can never catch."""
    return bool(words_only) and all(
        ASSIGNMENT_PREFIX.match(t) for t in words_only
    )


# --- Component 1: lexical structure scan -----------------------------------
#
# One scanner, shared by every caller that needs to find comment spans,
# quoted spans, or command-substitution spans: chunk processing (statements()
# itself), heredoc operator collection (strip_heredocs()) and body-
# substitution extraction (_extract_heredoc_body_substitutions()). It is the
# only routine in the file that decides where a substitution starts and
# ends, so a heredoc's destination, and every other caller, agree by
# construction rather than by two independent re-lexes drawing the same line
# differently.

_SUB_WORD_STOP = frozenset(' \t\r\n;|&()<>"\'`$')


def _word_at(text, i):
    """The maximal run of characters starting at I that are not whitespace,
    a statement separator/operator, a quote, `$`, or a backtick -- used only
    to recognise `case`/`esac` as WHOLE words, never as a substring of a
    longer identifier (`case-sensitive` is one word, not the keyword)."""
    j = i
    n = len(text)
    while j < n and text[j] not in _SUB_WORD_STOP:
        j += 1
    return text[i:j], j


def _at_word_start(text, i):
    """Whether TEXT[I] could begin a new word: start of text, or the
    previous character is whitespace or one of the operator characters a
    word never continues across."""
    if i == 0:
        return True
    return text[i - 1] in ' \t\r\n;|&()<>'


_SQ_PAREN_TOKEN = re.compile(r"\$\(|[()]")


def _single_quoted_sub_closes(text, start, limit):
    """Closing parenthesis of every `$(` in TEXT[START:LIMIT], found in ONE
    forward pass -- the rest of one single-quoted span for the
    honor_single_quotes=False scan in scan_structure(), LIMIT being its
    closing quote (or the end of TEXT when the quote is never closed).
    Returns {offset of the `$`: offset of its `)`}; a `$(` absent from the
    result stays unmatched. Each character in the range is examined a
    bounded number of times however many `$(` it holds, so the total cost
    is linear in the range.

    Each `$(` gets what a search started at that `$(` alone would find.
    Every `(` and `)` after it up to LIMIT counts alike (no quote, escape
    or nested-`$(` rule), and
    1. the `)` that balances the `$(`'s own `(` is its close; failing that,
    2. the first `)` after the `$(` is its close; with none in the range,
    3. the `$(` is unmatched.
    A `$(` the caller skips over (inside an earlier span) is resolved too and
    simply never asked for.
    """
    closes = {}
    first_close = {}
    # One entry per `(` still waiting for its `)`: the offset of the `$` for
    # a `$(`'s own `(`, -1 for a plain `(`.
    open_stack = []
    # `$(` offsets that have not seen any `)` after them yet; the next `)`
    # is the first one for all of them, and each is settled exactly once.
    waiting = []
    for m in _SQ_PAREN_TOKEN.finditer(text, start, limit):
        tok = m.group()
        if tok == ")":
            k = m.start()
            for d in waiting:
                first_close[d] = k
            waiting.clear()
            if open_stack:
                d = open_stack.pop()
                if d >= 0:
                    closes[d] = k
        elif tok == "(":
            open_stack.append(-1)
        else:
            d = m.start()
            open_stack.append(d)
            waiting.append(d)
    for d, k in first_close.items():
        closes.setdefault(d, k)
    return closes


def scan_structure(text, mode="shell", checkpoints=None, honor_single_quotes=True):
    """Component 1. One pass over TEXT (a text and an outer MODE, `shell`
    or `heredoc-body`). Returns (spans, parent_of, unmatched, opaque,
    containing_span):

    - SPANS: every `$( … )`/`` ` … ` `` span found, at every nesting level.
    - PARENT_OF: {span: its immediate enclosing span, or None} -- a span
      strictly containing it with nothing tighter in between.
    - UNMATCHED: start offsets of an opener never closed by end of text.
    - OPAQUE: TOP-LEVEL ranges inert for statement-separator counting: a
      quoted span, a comment span, or a top-level substitution span (mode
      `shell` only -- `heredoc-body` mode returns `[]` here, since quotes
      and comments are literal at that mode's own top level and no caller
      needs separator counting over heredoc-body text).
    - CONTAINING_SPAN: {checkpoint position: the innermost span enclosing
      it, or None} for every position in CHECKPOINTS, found for free while
      the scan passes each one -- the position-only way a heredoc operator
      is matched to the substitution (if any) that holds it, with no
      marker text ever written into TEXT (Component 3: "no marker
      characters are inserted... a control character in the input has no
      special meaning").

    Postconditions:
    1. Inside a substitution body, shell rules apply in BOTH modes: a `)`
       inside quotes, inside a comment, or ending a case pattern never
       closes the span, and nested substitutions are reported at every
       level.
    2. In `shell` mode, a `#` at the start of a word outside quotes starts
       a comment that runs to the end of the line. Text inside a comment
       or inside single quotes opens no substitution.
    3. In `heredoc-body` mode, quote characters and `#` outside any
       substitution are literal text. A backslash-escaped `$` or backtick
       opens no span, in either mode.
    4. An unterminated span is reported as unterminated (in UNMATCHED) and
       extends to the end of the text; it is never truncated silently.

    HONOR_SINGLE_QUOTES defaults to True, which is postcondition 2 exactly
    (real shell semantics: single quotes suppress expansion, so a `$(`/
    backtick inside them opens no span) -- used by every heredoc-facing
    caller (chunk-wide `chunk_scan`, `_statement_info_at()`,
    `_extract_heredoc_body_substitutions()`), since Component 3/4's
    statement/case-state analysis needs the position of a REAL shell
    separator, which a single-quoted `$(`/backtick can never introduce.
    Passing False keeps every other rule identical but stops single quotes
    from suppressing `$(`/backtick recognition -- used ONLY by
    `statements()`'s own general, non-heredoc substitution discovery (the
    span list `_mark_substitutions()`/`_mark_quoted_substitutions()` mark
    and that `pending` recurses into), which predates this task and must
    keep its own pre-existing, quote-agnostic reach: check_rm() and the
    other per-token checks read `.unresolved` as "this token's value was
    never fully present, regardless of how the substitution sitting in it
    was written" -- a static, conservative reading that intentionally does
    not depend on whether a real shell would actually expand that spot,
    the same way UNRESOLVED_EXPANSION's own raw-text search (check_rm()
    step 3) never did either. Since the only code path this flag touches
    is the `q == "'"` branch, every other input -- and this same function's
    heredoc-facing callers, which never pass it -- is completely unaffected.
    """
    spans = []
    parent_open_of = {}
    unmatched = []
    opaque = []
    containing_open = {}

    checkpoints = sorted(set(checkpoints or ()))
    ci = 0

    # Stack of frames: [open_pos_or_None, is_sub, quote_char_or_None,
    # case_stack]. stack[0] is the implicit top-level frame (never itself a
    # span). CASE_STACK is per FRAME -- a case construct cannot span a
    # subshell/substitution boundary, so each pushed frame starts fresh,
    # mirroring statements()'s own per-chunk reset.
    stack = [[None, False, None, []]]
    sub_open_stack = []
    top_opaque_start = [None]
    # Closes of the `$(` in the single-quoted span being scanned (only for
    # honor_single_quotes=False): None until the span's first `$(`, then
    # {offset of `$`: offset of `)`}. Reset at every single-quote opener.
    sq_closes = None

    def close_top_opaque(end):
        if top_opaque_start[0] is not None:
            opaque.append((top_opaque_start[0], end))
            top_opaque_start[0] = None

    n = len(text)
    i = 0
    while i < n:
        while ci < len(checkpoints) and checkpoints[ci] <= i:
            containing_open[checkpoints[ci]] = (
                sub_open_stack[-1] if sub_open_stack else None
            )
            ci += 1

        frame = stack[-1]
        depth = len(stack) - 1
        literal = depth == 0 and mode == "heredoc-body"
        q = frame[2]
        c = text[i]

        if q == "'":
            if c == "'":
                frame[2] = None
                if depth == 0:
                    close_top_opaque(i + 1)
                i += 1
                continue
            if not honor_single_quotes and c == "$" and i + 1 < n and text[i + 1] == "(":
                if sq_closes is None:
                    # First `$(` of this single-quoted span: resolve every
                    # `$(` left in the span in one pass instead of searching
                    # from each one (that was quadratic). The close is inside
                    # the single-quoted range only (it holds no `'`, so the
                    # span can never leak past the quote).
                    quote_end = text.find("'", i + 1)
                    sq_closes = _single_quoted_sub_closes(
                        text, i, quote_end if quote_end != -1 else n
                    )
                close_pos = sq_closes.get(i, -1)
                if close_pos != -1:
                    spans.append((i, close_pos + 1))
                    parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
                    i = close_pos + 1
                    continue
                i += 1
                continue
            if not honor_single_quotes and c == "`":
                quote_end = text.find("'", i + 1)
                j = text.find("`", i + 1)
                if j == -1 or (quote_end != -1 and j > quote_end):
                    i += 1
                    continue
                spans.append((i, j + 1))
                parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
                if depth == 0:
                    if top_opaque_start[0] is None:
                        top_opaque_start[0] = i
                    close_top_opaque(j + 1)
                i = j + 1
                continue
            i += 1
            continue

        if c == "\\" and i + 1 < n:
            i += 2
            continue

        if q == '"':
            if c == '"':
                frame[2] = None
                if depth == 0:
                    close_top_opaque(i + 1)
                i += 1
                continue
            if c == "$" and i + 1 < n and text[i + 1] == "(":
                stack.append([i, True, None, []])
                parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
                sub_open_stack.append(i)
                i += 2
                continue
            if c == "`":
                j = text.find("`", i + 1)
                if j == -1:
                    unmatched.append(i)
                    i = n
                    break
                spans.append((i, j + 1))
                parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
                sub_open_stack.append(i)
                while ci < len(checkpoints) and checkpoints[ci] <= j:
                    containing_open[checkpoints[ci]] = sub_open_stack[-1]
                    ci += 1
                sub_open_stack.pop()
                i = j + 1
                continue
            i += 1
            continue

        # Unquoted within this frame.
        if not literal and c == "#" and _at_word_start(text, i):
            j = text.find("\n", i)
            end = j if j != -1 else n
            if depth == 0:
                if top_opaque_start[0] is None:
                    top_opaque_start[0] = i
                close_top_opaque(end)
            i = end
            continue

        if not literal and c == "'":
            frame[2] = "'"
            sq_closes = None
            if depth == 0 and top_opaque_start[0] is None:
                top_opaque_start[0] = i
            i += 1
            continue
        if not literal and c == '"':
            frame[2] = '"'
            if depth == 0 and top_opaque_start[0] is None:
                top_opaque_start[0] = i
            i += 1
            continue

        if c == "$" and i + 1 < n and text[i + 1] == "(":
            stack.append([i, True, None, []])
            parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
            sub_open_stack.append(i)
            if depth == 0 and top_opaque_start[0] is None:
                top_opaque_start[0] = i
            i += 2
            continue

        if c == "`":
            j = text.find("`", i + 1)
            if j == -1:
                unmatched.append(i)
                i = n
                break
            spans.append((i, j + 1))
            parent_open_of[i] = sub_open_stack[-1] if sub_open_stack else None
            sub_open_stack.append(i)
            while ci < len(checkpoints) and checkpoints[ci] <= j:
                containing_open[checkpoints[ci]] = sub_open_stack[-1]
                ci += 1
            sub_open_stack.pop()
            if depth == 0:
                if top_opaque_start[0] is None:
                    top_opaque_start[0] = i
                close_top_opaque(j + 1)
            i = j + 1
            continue

        if c == "(":
            stack.append([i, False, None, []])
            i += 1
            continue

        case_stack = frame[3]
        top = case_stack[-1] if case_stack else None
        if c == ")":
            if top in ("pattern_first", "pattern_rest"):
                # A case pattern's own closer -- never the frame's closer,
                # regardless of nesting depth (postcondition 1).
                case_stack[-1] = "body"
                i += 1
                continue
            if len(stack) > 1:
                open_pos, is_sub, _q, _cs = stack.pop()
                if is_sub:
                    spans.append((open_pos, i + 1))
                    if sub_open_stack and sub_open_stack[-1] == open_pos:
                        sub_open_stack.pop()
                if len(stack) == 1:
                    close_top_opaque(i + 1)
            i += 1
            continue

        if (c.isalnum() or c == "_") and _at_word_start(text, i):
            word, end = _word_at(text, i)
            if top == "await_subject":
                case_stack[-1] = "await_in"
            elif top == "await_in":
                case_stack[-1] = "pattern_first"
            elif top == "pattern_first":
                rest = end
                while rest < n and text[rest] in " \t":
                    rest += 1
                followed_by_closer = rest < n and text[rest] == ")"
                if word == "esac" and not followed_by_closer:
                    case_stack.pop()
                else:
                    case_stack[-1] = "pattern_rest"
            elif top == "pattern_rest":
                pass
            else:
                if word == "esac" and case_stack:
                    case_stack.pop()
                elif word == "case":
                    case_stack.append("await_subject")
            i = end
            continue

        i += 1

    while ci < len(checkpoints):
        containing_open[checkpoints[ci]] = (
            sub_open_stack[-1] if sub_open_stack else None
        )
        ci += 1

    for frame in stack[1:]:
        if frame[1]:
            unmatched.append(frame[0])
    if top_opaque_start[0] is not None:
        opaque.append((top_opaque_start[0], n))

    open_to_span = {s: (s, e) for s, e in spans}
    parent_of = {}
    for s, e in spans:
        p_open = parent_open_of.get(s)
        parent_of[(s, e)] = open_to_span.get(p_open) if p_open is not None else None

    opaque.sort()
    containing_span = {
        pos: (open_to_span.get(open_pos) if open_pos is not None else None)
        for pos, open_pos in containing_open.items()
    }
    return spans, parent_of, unmatched, opaque, containing_span


def _top_level_spans(spans, parent_of):
    """SPANS with no enclosing parent, sorted left to right -- the ones a
    caller marks/queues at THIS level; a nested one is found again once its
    parent's own body is queued and re-scanned as its own chunk."""
    return sorted(s for s in spans if parent_of.get(s) is None)


def _span_inner(text, span):
    """(inner text, its own start offset in TEXT) for SPAN, a (start, end)
    pair from scan_structure()."""
    start, end = span
    if text[start] == "`":
        return text[start + 1 : end - 1], start + 1
    return text[start + 2 : end - 1], start + 2


def _segment_boundaries(text, opaque):
    """The START offset of every real (non-comment, non-quoted, non-
    substitution) statement-separator run in TEXT, in ascending order,
    using OPAQUE (scan_structure()'s top-level ranges) to skip inert
    regions -- ONE forward pass over the whole of TEXT, built once per
    TEXT/OPAQUE pair and shared by every _segment_index_at() query against
    it (see that function), rather than each query re-scanning from
    position 0 on its own. A chunk with K heredocs would otherwise cost
    O(K) scans, each up to that heredoc's own (growing) offset -- O(n^2)
    total on a chunk whose heredoc count grows with its own length
    (NFR3/TM-5) -- where this one pass, plus a bisect per query, costs
    O(n) once and O(log n) per query."""
    boundaries = []
    i = 0
    n = len(text)
    oi = 0
    m = len(opaque)
    while i < n:
        while oi < m and opaque[oi][1] <= i:
            oi += 1
        if oi < m and opaque[oi][0] <= i < opaque[oi][1]:
            i = min(opaque[oi][1], n)
            continue
        c = text[i]
        if c in SEGMENT_CHARS:
            boundaries.append(i)
            j = i
            while j < n and text[j] in SEGMENT_CHARS:
                j += 1
            i = j
            continue
        i += 1
    return boundaries


def _segment_index_at(pos, boundaries):
    """Which lex_segments(marked_text) statement index contains character
    POS in TEXT -- the count of separator runs in BOUNDARIES (see
    _segment_boundaries()) that START strictly before POS, found by
    bisecting the precomputed, sorted list rather than re-scanning TEXT
    from position 0 (Component 3: position only, no marker ever inserted
    into TEXT)."""
    return bisect.bisect_left(boundaries, pos)


# --- Component 5: substitutions in an unquoted-delimiter heredoc body ------


def _extract_heredoc_body_substitutions(text):
    """Every OUTERMOST `$( … )`/`` ` … ` `` in TEXT (an unquoted-delimiter
    heredoc body), found by Component 1's own scanner in `heredoc-body`
    mode rather than a separate ad hoc parse -- so a `)` that closes a case
    pattern or sits inside a quoted string, however deep the nesting, never
    ends the span early. Returns (bodies, needs_whole_body); NEEDS_WHOLE_BODY
    is True when an opener is never closed, so the caller falls back to
    scanning the whole text rather than silently dropping the unresolved
    tail. Each returned body is queued as its own chunk by the caller;
    nested levels are found in turn when THAT chunk is scanned next."""
    spans, parent_of, unmatched, _opaque, _containing = scan_structure(
        text, mode="heredoc-body"
    )
    if unmatched:
        return [], True
    top_spans = _top_level_spans(spans, parent_of)
    return [_span_inner(text, span)[0] for span in top_spans], False


# --- Component 3: chunk statement analysis, built once per chunk -----------


class _Stmt:
    """One statement's contribution to Component 3's per-chunk table --
    everything Component 4's destination decision (and, for its own
    purposes, _mark_substitutions()'s callers) reads about ONE lex_segments()
    statement, computed once and shared by every heredoc in the chunk."""

    __slots__ = (
        "toks", "lexed", "sep", "shaped_words", "redirects", "word",
        "has_process_sub", "is_assignment_only", "opens_group",
        "closes_group", "is_compound_keyword",
    )

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))


def _leading_group_opener_char(toks):
    """Whether TOKS' own command position, after skipping any VAR=value/
    WRAPPERS prefix, lands on an unquoted grouping opener, and which
    bracket/keyword-pair it opens ('{', '(', 'if', 'loop' for the
    for/while/until/select family, or 'case') -- the type Component 3's
    group tracking needs to match against the correct closer -- or None.
    Recognising the compound-statement keyword pairs closes the gap where
    `if ...; then cat <<'EOF' ...\\nEOF\\nfi | bash`,
    `for ...; do cat <<'EOF' ...\\nEOF\\ndone | bash`, and
    `case ... in ...) cat <<'EOF' ...\\nEOF\\n;; esac | bash` (and their
    `while`/`until`/`select` counterparts) piped the closer's own line to a
    shell sink and were not tracked as a group the way `{`/`(` already are."""
    i = 0
    n = len(toks)
    while i < n:
        advance = _skip_assignments_and_wrappers(toks[i:])
        if not advance:
            break
        i += advance
    if i >= n:
        return None
    t = toks[i]
    quoted = getattr(t, "quoted", False)
    if t == "(" and getattr(t, "is_operator", False):
        return "("
    if t == "{" and not quoted:
        return "{"
    if t == "if" and not quoted:
        return "if"
    if t in ("for", "while", "until", "select") and not quoted:
        return "loop"
    if t == "case" and not quoted:
        return "case"
    return None


def _leading_group_closer(toks, case_stack=None):
    """The closer counterpart to _leading_group_opener_char(): which
    bracket/keyword-pair TOKS' own leading position closes ('{' for a bare
    `}`, '(' for a `)` operator, 'if' for `fi`, 'loop' for `done`, 'case'
    for `esac`), or None.

    CASE_STACK (the same per-chunk case-pattern/body stack
    _build_statement_table() carries into _shape_leading(), snapshotted
    BEFORE that call mutates it) decides whether a leading `esac` closes a
    case construct here: it does when the case-tracking state at the start
    of this statement is empty/"body" (ordinary command position) or
    "pattern_first" (the empty-case-body shape `case x in esac`) -- the
    same positions _shape_leading() itself treats `esac` as a closer.
    "await_subject"/"await_in" (the subject/`in` word position) and
    "pattern_rest" (opaque pattern content past its first word) never treat
    `esac` as a closer, mirroring _shape_leading() exactly."""
    i = 0
    n = len(toks)
    while i < n:
        advance = _skip_assignments_and_wrappers(toks[i:])
        if not advance:
            break
        i += advance
    if i >= n:
        return None
    t = toks[i]
    quoted = getattr(t, "quoted", False)
    if t == "}" and not quoted:
        return "{"
    if t == ")" and getattr(t, "is_operator", False):
        return "("
    if t == "fi" and not quoted:
        return "if"
    if t == "done" and not quoted:
        return "loop"
    if t == "esac" and not quoted:
        top = case_stack[-1] if case_stack else None
        if top in ("await_subject", "await_in", "pattern_rest"):
            return None
        if top == "pattern_first":
            followed_by_closer = (
                i + 1 < n
                and toks[i + 1] == ")"
                and getattr(toks[i + 1], "is_operator", False)
            )
            if followed_by_closer:
                return None
        return "case"
    return None


def _build_statement_table(chunk, marked_chunk):
    """Component 3. ONE lexing pass of MARKED_CHUNK (CHUNK with every
    top-level substitution already blanked by _mark_substitutions()),
    yielding the same per-statement shaping statements() itself computes
    (case state carried statement-by-statement via _shape_leading(), the
    same fused-closer/redirect/wrapper handling, and -- SC1's git/gh
    condition -- _git_is_data() for a `git` command word, _git_alias_risk()
    for a `gh` one, task0003) -- built once per chunk and read by every
    heredoc's destination decision instead of each heredoc re-lexing the
    chunk on its own."""
    segments = lex_segments(marked_chunk)
    case_stack = []
    table = []
    for toks, lexed, sep in segments:
        stripped = _strip_unresolved_marks(toks)
        if lexed:
            fused = _split_fused_closer_redirects(stripped)
            words_only, redirects = split_redirects(fused, lexed)
            # Snapshotted BEFORE _shape_leading() mutates case_stack, so a
            # leading `esac` on THIS statement is judged against the
            # case-tracking state this statement actually started in (see
            # _leading_group_closer()'s own docstring).
            case_stack_before = list(case_stack)
            lead = _shape_leading(words_only, case_stack)
            shaped_words = _shaped_remainder(words_only, lead)
            ends_case_item = bool(
                sep and any(term in sep for term in (";;", ";&", ";|"))
            )
            if ends_case_item and case_stack and case_stack[-1] == "body":
                case_stack[-1] = "pattern_first"
            word, args = head(shaped_words)
            if word == "git":
                if not _git_is_data(args):
                    word = None
            elif _git_alias_risk(word, shaped_words, words_only[:lead]):
                word = None
            raw_index = _skip_assignments_and_wrappers(stripped)
            is_compound_keyword = (
                raw_index < len(stripped)
                and stripped[raw_index] in COMPOUND_STATEMENT_KEYWORDS
            )
            table.append(_Stmt(
                toks=stripped, lexed=True, sep=sep, shaped_words=shaped_words,
                redirects=redirects, word=word,
                has_process_sub=_has_process_substitution(stripped),
                is_assignment_only=_is_assignment_only(words_only),
                opens_group=_leading_group_opener_char(stripped),
                closes_group=_leading_group_closer(stripped, case_stack_before),
                is_compound_keyword=is_compound_keyword,
            ))
        else:
            fallback_words, redirects = split_redirects(stripped, lexed)
            shaped_words = _shape_fallback(fallback_words)
            table.append(_Stmt(
                toks=stripped, lexed=False, sep=sep, shaped_words=shaped_words,
                redirects=redirects, word=None, has_process_sub=False,
                is_assignment_only=False, opens_group=None, closes_group=None,
                is_compound_keyword=False,
            ))
    return table


def _track_groups(table):
    """One forward pass over TABLE building GROUP_CLOSER_OF ({statement
    index that OPENS a group: the statement index that CLOSES it}),
    OPEN_GROUPS_AT (per statement index, a reference to the persistent
    linked-stack node -- (bracket, open index, parent node), or None when
    nothing is open -- describing every group open AT that statement,
    including one it opens itself and any opened by an earlier statement
    or on an earlier line -- Component 3's own definition), and MISMATCHED
    (True when a closer was seen that does not match the top of the group
    stack -- including a closer seen with an empty stack). A vocabulary gap
    in _leading_group_opener_char() (a compound-statement keyword this pass
    does not yet recognise as an opener, e.g. one only reachable after
    `then`/`do`/`else`/`elif`/`!`) produces exactly this shape: its paired
    closer arrives with no matching opener on the stack. Rather than
    silently ignoring that closer -- which would leave the heredocs it was
    meant to re-enclose looking like top-level, undetermined-free
    statements -- MISMATCHED tells the caller this table's own group
    tracking is unreliable, so it can fall back to treating every heredoc
    resolved against this table as undetermined instead of guessing.

    The stack is a persistent singly-linked list rather than a Python list
    copied per statement: pushing/popping only ever rebinds the current
    top node, so OPEN_GROUPS_AT holds one O(1) reference per statement
    instead of an O(open groups) copy, keeping this pass and its memory
    linear in the number of statements even when groups never close
    (NFR3)."""
    group_top = None
    group_closer_of = {}
    open_groups_at = []
    mismatched = False
    for idx, stmt in enumerate(table):
        if stmt.lexed:
            closer = stmt.closes_group
            if closer is not None:
                if group_top is not None and group_top[0] == closer:
                    _bracket, open_idx, parent = group_top
                    group_closer_of[open_idx] = idx
                    group_top = parent
                else:
                    mismatched = True
            opener = stmt.opens_group
            if opener is not None:
                group_top = (opener, idx, group_top)
        open_groups_at.append(group_top)
    return group_closer_of, open_groups_at, mismatched


_PIPELINE_MEMO_KEY = "_pipeline_memo"


def _pipeline_downstream(table, index, memo):
    """(has_sink, has_other) for the run of statements later than
    TABLE[INDEX], joined to it by an unbroken run of Pipeline separators --
    same semantics the first pass's _pipeline_has_sink() had, but reading
    each lookahead statement's WORD/flags from the shared, case-aware
    TABLE instead of re-lexing it with a fresh case_stack, and memoized so
    a group closer or enclosing level queried by more than one heredoc in
    the same chunk costs one lookup, not one re-walk (NFR3).

    A statement holding no tokens at all (Component 3: "Segments that hold
    only whitespace or newlines are skipped. They never end the downstream
    search.") is skipped over, regardless of its OWN separator -- a bare
    trailing space/tab after a pipe (`cmd | \n...`, `cmd |\t\n...`) lexes as
    an empty statement whose own SEP is a plain `\n`, not `|`, since nothing
    else shares its line; without this skip, that empty statement's
    non-pipe SEP would end the walk right there, one stage short of the
    statement the pipe actually feeds."""
    if index in memo:
        return memo[index]
    n = len(table)
    if index >= n or not _is_pipe_sep(table[index].sep):
        memo[index] = (False, False)
        return memo[index]
    has_other = False
    i = index + 1
    while True:
        while i < n and table[i].lexed and not table[i].toks:
            i += 1
        if i >= n:
            result = (False, has_other)
            break
        stmt = table[i]
        if not stmt.lexed:
            result = (True, has_other)
            break
        if stmt.is_compound_keyword:
            has_other = True
        else:
            word = stmt.word
            if word is not None and SINK_WORD_RE.match(word):
                result = (True, has_other)
                break
            if (
                word is None
                or word not in DATA_COMMANDS
                or stmt.has_process_sub
                or stmt.opens_group is not None
            ):
                has_other = True
        if not _is_pipe_sep(stmt.sep):
            result = (False, has_other)
            break
        i += 1
    memo[index] = result
    return result


def _group_chain_pipeline(table, node, group_closer_of, memo):
    """(has_sink, has_other) aggregated over NODE's own group's downstream
    pipeline OR'd with its parent node's own aggregate, memoized per node
    (keyed by identity, since nodes are shared linked-stack cells) so a
    node reachable from more than one heredoc's OPEN_GROUPS_AT costs one
    lookup instead of one re-walk of the whole enclosing chain (NFR3)."""
    pending = []
    cur = node
    while cur is not None and ("group", id(cur)) not in memo:
        pending.append(cur)
        cur = cur[2]
    sink, other = memo[("group", id(cur))] if cur is not None else (False, False)
    for nd in reversed(pending):
        close_idx = group_closer_of.get(nd[1])
        if close_idx is None:
            s2, o2 = False, True
        else:
            s2, o2 = _pipeline_downstream(table, close_idx, memo)
        sink = sink or s2
        other = other or o2
        memo[("group", id(nd))] = (sink, other)
    return sink, other


def _statement_pipeline_info(table, idx, group_closer_of, open_groups_at, memo):
    """Component 4 levels 2-3 combined for TABLE[IDX]: its own downstream
    pipeline, OR the downstream pipeline after the closer of any compound
    group open at it. A group whose closer cannot be found anywhere in the
    chunk makes this undeterminable (Component 4 rule 2), not silently
    'no sink here'."""
    sink, other = _pipeline_downstream(table, idx, memo)
    node = open_groups_at[idx]
    if node is not None:
        s2, o2 = _group_chain_pipeline(table, node, group_closer_of, memo)
        sink = sink or s2
        other = other or o2
    return sink, other


def _stmt_destination_info(table, idx, group_closer_of, open_groups_at, memo):
    """The _StmtInfo Component 4 reads for TABLE[IDX] as either a host or
    an enclosing statement."""
    stmt = table[idx]
    if not stmt.lexed:
        return _StmtInfo(parse_failed=True)
    pipeline_sink, pipeline_undetermined = _statement_pipeline_info(
        table, idx, group_closer_of, open_groups_at, memo
    )
    return _StmtInfo(
        word=stmt.word,
        pipeline_sink=pipeline_sink,
        pipeline_undetermined=pipeline_undetermined,
        has_process_sub=stmt.has_process_sub,
        is_assignment_only=stmt.is_assignment_only,
    )


# --- Component 4: destination decision --------------------------------------


def _decide_destination(chain):
    """The task plan's Component 4 decision, given CHAIN[0] (the host
    statement, its own pipeline/group levels already folded in) and
    CHAIN[1:] (its enclosing statements, innermost first, each with its
    own pipeline/group levels folded in the same way): 'sink',
    'undetermined', or 'data'.

    A sink at ANY level wins outright, even when another level in the same
    chain is unlexable or undeterminable (checked first, in its own pass,
    before any parse-failure/undetermined check runs)."""
    for level in chain:
        if level.parse_failed:
            continue
        if level.word is not None and SINK_WORD_RE.match(level.word):
            return "sink"
        if level.pipeline_sink:
            return "sink"

    for level in chain:
        if level.parse_failed or level.pipeline_undetermined or level.has_process_sub:
            return "undetermined"

    host = chain[0]
    if host.word is None or host.word not in DATA_COMMANDS:
        return "undetermined"
    for level in chain[1:]:
        if level.is_assignment_only:
            continue
        if level.word is None or level.word not in DATA_COMMANDS:
            return "undetermined"

    return "data"


def _statement_info_at(text, pos, memo_key, tables_cache):
    """The Component 3 table (built once per TEXT, cached in TABLES_CACHE
    keyed by MEMO_KEY) plus the statement index at POS in TEXT, plus that
    table's own group-tracking and pipeline memo -- shared by every level
    of every heredoc's chain that resolves against this same TEXT."""
    cached = tables_cache.get(memo_key)
    if cached is None:
        spans, parent_of, unmatched, opaque, _containing = scan_structure(
            text, mode="shell"
        )
        top_spans = _top_level_spans(spans, parent_of)
        marked = _mark_substitutions(text, top_spans, 0)
        table = _build_statement_table(text, marked)
        group_closer_of, open_groups_at, mismatched = _track_groups(table)
        # _segment_boundaries() is the one full-text pass every heredoc's
        # own _segment_index_at() query against THIS text shares (NFR3) --
        # see that function's own docstring.
        boundaries = _segment_boundaries(text, opaque)
        cached = (
            table, group_closer_of, open_groups_at, {}, unmatched, boundaries,
            mismatched,
        )
        tables_cache[memo_key] = cached
    (
        table, group_closer_of, open_groups_at, pipe_memo, unmatched, boundaries,
        mismatched,
    ) = cached
    if any(p < pos for p in unmatched):
        return None
    idx = _segment_index_at(pos, boundaries)
    if idx >= len(table):
        return None
    if mismatched:
        # This table's own group tracking saw a closer that did not match
        # its stack (see _track_groups()'s own docstring) -- undetermined
        # here rather than a possibly-wrong sink/data guess; a sink found
        # at another level of the same chain still wins (_decide_destination()).
        return _StmtInfo(parse_failed=True)
    return _stmt_destination_info(table, idx, group_closer_of, open_groups_at, pipe_memo)


def _walk_enclosing_chain(chunk, cur_span, parent_of, tables_cache):
    """The chain of enclosing statements around CUR_SPAN -- a (start, end)
    span for the substitution directly holding a heredoc's host statement
    -- innermost first, up to the outermost. Each level is resolved
    against whichever text actually holds it (CHUNK itself for the
    outermost level, or the immediate parent substitution's own inner text
    otherwise), using PARENT_OF (built once per chunk) for O(1) lookups
    rather than re-scanning the whole chunk per heredoc (NFR3)."""
    chain = []
    cur = cur_span
    for _ in range(10):
        parent = parent_of.get(cur)
        if parent is None:
            info = _statement_info_at(chunk, cur[0], "chunk", tables_cache)
            chain.append(info if info is not None else _StmtInfo(parse_failed=True))
            break
        inner_text, inner_base = _span_inner(chunk, parent)
        local_pos = cur[0] - inner_base
        info = _statement_info_at(inner_text, local_pos, parent, tables_cache)
        chain.append(info if info is not None else _StmtInfo(parse_failed=True))
        cur = parent
    else:
        chain.append(_StmtInfo(parse_failed=True))
    return chain


def _heredoc_destinations(chunk, records, chunk_scan):
    """{index into RECORDS: 'sink'/'data'/'undetermined'} for every heredoc
    strip_heredocs() found in CHUNK -- the single entry point statements()
    calls, once per popped chunk, before that chunk's own substitution
    bodies are queued. CHUNK_SCAN is CHUNK's own Component 1 scan result
    (scan_structure(chunk, mode="shell", checkpoints=[r.op_start for r in
    RECORDS])), computed once by the caller and shared with this chunk's
    substitution marking -- never a separate re-lex of CHUNK."""
    if not records:
        return {}

    spans, parent_of, unmatched, opaque, containing_span = chunk_scan
    tables_cache = {}

    destinations = {}
    for index, record in enumerate(records):
        if any(pos < record.op_start for pos in unmatched):
            destinations[index] = "undetermined"
            continue
        containing = containing_span.get(record.op_start)
        if containing is None:
            info = _statement_info_at(chunk, record.op_start, "chunk", tables_cache)
            chain = [info if info is not None else _StmtInfo(parse_failed=True)]
        else:
            inner_text, inner_base = _span_inner(chunk, containing)
            local_start = record.op_start - inner_base
            host = _statement_info_at(inner_text, local_start, containing, tables_cache)
            chain = [host if host is not None else _StmtInfo(parse_failed=True)]
            chain.extend(
                _walk_enclosing_chain(chunk, containing, parent_of, tables_cache)
            )
        destinations[index] = _decide_destination(chain)
    return destinations


def _mark_substitutions(chunk, top_spans, offset_=0):
    """Blank every span in TOP_SPANS -- CHUNK's own top-level `$( … )`/
    `` ` … ` `` spans, Component 1's scan_structure() result narrowed by
    _top_level_spans() -- by replacing it with UNRESOLVED_MARK, so the word
    it sat in survives lexing as a token no matter whether the span filled
    the whole word or sat beside real text (destructive-guard-command-
    substitution task0001 Design Part 1, "evidence survives the lexing
    boundary"). Unlike SUBSTITUTION's own single-level, paren-free regex,
    TOP_SPANS already reflects true nesting (Component 1), so a chunk whose
    only substitution is several levels deep is still marked correctly here
    -- the nested levels are found in turn once this span's own inner text
    is queued and re-scanned as its own chunk (see call site).

    Unlike before this task, there is no boundary test here and no separate
    "blank to a space" branch: every match becomes marker residue, and
    _strip_unresolved_marks() is what tells the two shapes apart, by whether
    any real text is left once the residue is peeled back out —

    - A word whose ENTIRE text was one or more command substitutions and
      nothing else collapses, once every match in it is replaced, into a
      token made purely of marker characters. _strip_unresolved_marks()
      turns that into exactly one token carrying SUBSTITUTION_STANDIN and
      `.substitution_only` — never zero tokens, which was the hole this
      closes: a bare `rm -rf $(mktemp -d)` used to blank straight to
      whitespace here, vanish at tokenization, and reach the recursive-delete
      check with no target at all.
    - A match beside real text keeps that text once the marker is peeled
      back out; `.unresolved` is set on it exactly as before.

    A substitution sitting inside an otherwise-empty pair of quotes
    (`"$(cmd)"`) reaches the same one-token-of-marker-only result as the
    unquoted form, because quoting is resolved by the lexer before this
    function's output is ever tokenized — no special case is needed for it
    here.

    Each span is replaced with a marker carrying that span's own ordinal
    position among TOP_SPANS, OFFSET by OFFSET_ — statements() passes the
    number of entries already accumulated in its run-global ALL_SUBS list
    before this chunk's own spans are appended, so the index baked into
    each marker names a position in that run-global list rather than in
    this chunk's own local enumeration (destructive-guard-command-name-
    substitution). A marker's index therefore stays meaningful even if the
    marked token text later leaks into a re-scanned chunk (e.g. via a
    `bash -c '...'` payload pushed back onto PENDING), where a fresh,
    differently-numbered local list would otherwise either miss the entry
    (index out of range) or, worse, resolve to an unrelated entry that
    merely happens to be in range. This lets _strip_unresolved_marks()
    recover the right ALL_SUBS entry for a surviving marker by direct index
    lookup even when some other span in the same chunk never reaches the
    token stream at all (dropped whole by a lexer-level comment).
    """
    out = []
    cursor = 0
    for i, (start, end) in enumerate(top_spans):
        out.append(chunk[cursor:start])
        index = offset_ + i
        out.append(f"{UNRESOLVED_MARK}{index}{_MARK_TERMINATOR}")
        cursor = end
    out.append(chunk[cursor:])
    return "".join(out)


def _mark_quoted_substitutions(chunk, top_spans):
    """Like _mark_substitutions(), but a span in TOP_SPANS that sits
    immediately between a pair of double-quote characters in CHUNK's raw
    text — `"$(...)"` / `` "`...`" ``, with nothing else between the quote
    and the substitution boundary on either side — is replaced with
    QUOTED_MARK instead of UNRESOLVED_MARK. Every other occurrence (bare,
    single-quoted — a real shell would not expand that, but this module has
    never distinguished it either — or mixed with other text inside the
    quotes) gets the ordinary UNRESOLVED_MARK, byte for byte as
    _mark_substitutions() itself would produce (a single marker character,
    no index, no terminator — the two functions' outputs are compared only
    by segment/token shape, never by absolute offset, so this narrower
    replacement is enough; see this function's own second docstring
    paragraph below).

    Used ONLY by extract_shell_payload() (task0001 FR4), which lexes this
    output as a second, parallel token sequence to _mark_substitutions()'s
    own — same shape, same boundaries, differing only in which marker
    character sits at a substitution's position (see QUOTED_MARK) — so it
    can read, at the payload argument position and nowhere else, whether
    that specific substitution was written enclosed in quotes. No other
    stage calls this function.
    """
    out = []
    cursor = 0
    for start, end in top_spans:
        out.append(chunk[cursor:start])
        if 0 < start and end < len(chunk) and chunk[start - 1] == '"' and chunk[end] == '"':
            out.append(QUOTED_MARK)
        else:
            out.append(UNRESOLVED_MARK)
        cursor = end
    out.append(chunk[cursor:])
    return "".join(out)


def _strip_unresolved_marks(toks, chunk_subs=None):
    """Peel UNRESOLVED_MARK back out of TOKS (task0001 Design Part 1).

    A token made ENTIRELY of marker characters — one command substitution
    that filled the whole word, or several with nothing else between them —
    contributed no real text at all; it is replaced by SUBSTITUTION_STANDIN
    and carries `.substitution_only`, so check_rm() can judge it as a target
    whose value was never present, rather than dropping it (the hole this
    feature closes — AC-1). A token mixing marker characters with real text
    keeps that text, with `.unresolved` set so check_rm() can tell this
    target's value was never fully present — unchanged from before this
    task. Tokens without the marker pass through untouched — a command with
    no substitution in it is unaffected, byte for byte (AC-6).

    CHUNK_SUBS (task0002 FR11, R1/D5; positional lookup added by
    destructive-guard-command-name-substitution) lets this pass additionally
    recover, for a token that collapses entirely into marker residue, the
    RAW text of the substitution it came from — attached as
    `.raw_substitution_body` on the resulting `.substitution_only` Tok, for
    read_command_name_evidence() to read later. Despite its name (kept for
    continuity with earlier tasks), CHUNK_SUBS is, as of destructive-guard-
    command-name-substitution's index-leak fix, the RUN-GLOBAL list
    (`all_subs` in statements()) accumulated across every chunk processed
    so far in the current statements() call, not just the current chunk —
    each surviving marker's encoded index names its position in that
    run-global list. Each surviving marker already carries, encoded in its
    own text, the index into CHUNK_SUBS it was produced from (see
    _mark_substitutions()'s OFFSET_ parameter); this pass reads that index
    back out and looks CHUNK_SUBS up directly, rather than counting markers
    left-to-right across the token stream. A left-to-right ordinal count
    would desync the moment any match in the chunk never reaches the token
    stream at all — which happens when shlex's own `comments=True` consumes
    a `#` comment, and any `$(...)`/`` `...` `` written inside it, whole,
    before lexing ever produces a marker token for it; CHUNK_SUBS still
    counts that match, but no token carries its marker, so a plain
    left-to-right count silently attributes every later marker to the WRONG
    entry. Reading the index out of the marker itself is immune to that: a
    dropped match's marker is dropped along with it, and every surviving
    marker still names its own, correct CHUNK_SUBS entry regardless of what
    else in the chunk was dropped. Using a run-global index instead of a
    chunk-local one additionally makes this immune to a marked token's TEXT
    leaking into a re-scanned chunk (a `bash -c '...'` payload pushed back
    onto PENDING carries its marker's text verbatim into a fresh
    statements() iteration with its OWN chunk-local matches); a chunk-local
    index would either fall out of range there (evidence silently lost) or,
    worse, collide with an unrelated entry that happens to be in range
    (wrong evidence). A token whose marker count is not exactly one —
    several substitutions concatenated into the same whole word, so there
    is no single raw occurrence to attribute the token to — gets no
    evidence (`.raw_substitution_body` stays None, the constructor
    default): deliberately left unreadable rather than guessing which body
    applies (task0002 Design "Command-name evidence", "the token position
    cannot be mapped back to a raw occurrence"). The same applies, as a
    defence-in-depth backstop, when a marker's encoded index is out of
    range for CHUNK_SUBS or otherwise fails to parse: rather than guess, or
    raise, the token is left unreadable and read_command_name_evidence()
    falls back to `allow`. CHUNK_SUBS defaults to None, which reproduces
    this function's pre-FR11 behaviour exactly (no attribute set) — the
    extract_shell_payload() comparison call elsewhere in this file omits
    it, since it never needs this evidence.
    """
    out = []
    for t in toks:
        if UNRESOLVED_MARK not in t:
            out.append(t)
            continue
        matches = list(_MARK_RE.finditer(t))
        marker_count = len(matches)
        raw_body = None
        if chunk_subs is not None and marker_count == 1:
            try:
                index = int(matches[0].group(1))
            except ValueError:
                index = None
            if index is not None and 0 <= index < len(chunk_subs):
                raw_body = chunk_subs[index]
        cleaned = _MARK_RE.sub("", t)
        # A marker character that survived the well-formed-sequence
        # substitution above (UNRESOLVED_MARK/QUOTED_MARK/_MARK_TERMINATOR
        # not part of a full `UNRESOLVED_MARK + digits + _MARK_TERMINATOR`
        # run) came from the user's own command string, not from this
        # module's marking pass — strip it too, so head()'s basename() read
        # of the command word cannot land on residue mixed into the token
        # (destructive-guard-command-name-substitution: a NUL byte inside
        # e.g. `rm` would otherwise make the token match neither `rm` nor
        # anything else, and the destructive check would silently never run).
        cleaned = cleaned.replace(UNRESOLVED_MARK, "").replace(QUOTED_MARK, "").replace(
            _MARK_TERMINATOR, ""
        )
        if cleaned == "":
            new_tok = Tok(
                SUBSTITUTION_STANDIN,
                getattr(t, "is_operator", False),
                substitution_only=True,
                quoted=getattr(t, "quoted", False),
            )
            new_tok.raw_substitution_body = raw_body
            out.append(new_tok)
            continue
        out.append(
            Tok(
                cleaned,
                getattr(t, "is_operator", False),
                unresolved=True,
                quoted=getattr(t, "quoted", False),
            )
        )
    return out


def _shaped_remainder(words, lead):
    """WORDS[LEAD:] with every bare `)` closer dropped (task0001 FR3): a
    closer is never counted among a shaped statement's arguments. `[]` when
    LEAD has reached or passed the end of WORDS (task0001 FR2: a statement
    consisting entirely of syntax has no command of its own).
    """
    if lead >= len(words):
        return []
    return [
        a for a in words[lead:] if not (a == ")" and getattr(a, "is_operator", False))
    ]


def _shape_parallel(source_toks, canonical_word_count, lead):
    """Apply the SAME fused-closer split, redirect separation, and LEAD
    slice that produced the canonical shaped statement to SOURCE_TOKS — a
    marker-bearing parallel of the canonical tokens (statements()'s own
    MARKED or QUOTED_MARKED sequence for this statement) with identical
    segment/token shape (task0004 postcondition 1: "The substitution-marked
    and quoted-marked parallel token lists ... must be shaped the same
    way, so that all three stay aligned token for token"). Returns
    (shaped_words, redirects) for extract_shell_payload() to read the
    grouping-stripped statement from, instead of the unshaped one.

    A marker character never occurs inside an operator token — markers are
    word content, and a PUNCTUATION/REDIRECT operator token is built
    purely from shlex punctuation_chars — so _split_fused_closer_redirects()
    and split_redirects() make IDENTICAL closer/redirect/word-boundary
    decisions on SOURCE_TOKS as they did on the canonical, marker-stripped
    tokens: the two word-only lists this produces are the same length and
    shape, differing only in the TEXT of non-operator tokens. LEAD
    (computed once, from the canonical pass, via _shape_leading() —
    calling that scan a second time here would double-mutate CASE_STACK)
    therefore slices SOURCE_TOKS's own word list at the same real
    boundary. When that invariant does not hold — SOURCE_TOKS's own
    word-only list comes out a different length than
    CANONICAL_WORD_COUNT — LEAD is not trusted against a list it was not
    computed from (an index computed on one list must not be applied to a
    list that was split differently): the word/redirect split is still
    returned, but unsliced, matching the same fail-safe shape
    extract_shell_payload() itself already falls back to on a length
    mismatch.
    """
    fused = _split_fused_closer_redirects(source_toks)
    words, redirects = split_redirects(fused, True)
    if len(words) != canonical_word_count:
        return words, redirects
    return _shaped_remainder(words, lead), redirects


# Characters a parse-failure fallback token can start/end with while still
# being grouping syntax fused to a real word (`(rm`, `/home/sakura/x)`) —
# _shape_fallback()'s only vocabulary, since it has no operator/quote
# provenance to test against.
_FALLBACK_OPENERS = "({"
_FALLBACK_CLOSERS = ")}"


def _shape_fallback(words):
    """Strip grouping/reserved-word syntax at the front, and a fused
    closer at the tail, from a parse-failure fallback segment's plain-text
    WORDS (task0004 postcondition 7: "grouping and compound syntax at
    command position is still removed before the command word is
    located... That syntax includes an opener fused to the first word
    (`(rm`) and a closer fused to the last argument (`/home/sakura/x)`)").

    No `.is_operator`/`.quoted` provenance is available on this path
    (tokens() falls back to shlex.split()/str.split(), neither of which
    carries lexer state), so quoting cannot be told apart here at all —
    the stricter reading applies (IMPLEMENTATION.md Conventions): a word
    that looks like this syntax is read as it, whether or not it was
    actually quoted in the raw text.

    Handles a standalone token (`(`, `if`) and an opener/closer fused to
    the first/last real word with no space, the two shapes this fallback
    tokenizer actually produces for our grouping vocabulary (it never runs
    a real operator/word boundary scan). No case-pattern tracking is
    attempted here — this fallback path is rare (an unbalanced quote,
    usually) and untracked case constructs on it are out of scope; see
    lex_segments()'s own docstring for why the fallback exists at all.
    WRAPPERS/VAR=value are left alone: head()'s own existing skip
    (_skip_to_command_word(), unchanged by this task) still applies to
    whatever this returns, exactly as it already does for every fallback
    statement.
    """
    words = list(words)
    changed = True
    while words and changed:
        changed = False
        w = words[0]
        if w in RESERVED_SKIP_WORDS or w in ("case", "esac"):
            words.pop(0)
            changed = True
            continue
        if w and w[0] in _FALLBACK_OPENERS:
            stripped = w.lstrip(_FALLBACK_OPENERS)
            if stripped:
                words[0] = stripped
            else:
                words.pop(0)
            changed = True
            continue
    changed = True
    while words and changed:
        changed = False
        w = words[-1]
        if w in ("fi", "done"):
            words.pop()
            changed = True
            continue
        if w and w[-1] in _FALLBACK_CLOSERS:
            stripped = w.rstrip(_FALLBACK_CLOSERS)
            if stripped:
                words[-1] = stripped
            else:
                words.pop()
            changed = True
            continue
    return words


def statements(command):
    """Yield (text, tokens, lexed, shaped_words, redirects) per command
    segment, substitution bodies included.

    The text is the tokens rejoined, so quoting is already resolved by the
    time the regex-based checks see it. LEXED is lex_segments()'s per-segment
    parse-success flag — False only on the parse-failure fallback, where
    token provenance is unavailable.

    SHAPED_WORDS (task0001 D1, reshaped by task0004 postcondition 6) is
    TOKENS with every redirect operator/target (and any leading fd digit)
    pulled out FIRST, then every grouping/compound-construct token at
    command position removed from what is left — see _shape_leading()'s
    docstring for the full vocabulary and CASE_STACK's semantics — and any
    remaining bare `)` operator token dropped (task0001 FR3: a closer is
    never counted among a command's arguments). REDIRECTS is the flat
    [digit?, operator, target, ...] list split_redirects() pulled out;
    every per-statement check reads it for write-target extraction instead
    of re-deriving it from SHAPED_WORDS. Pulling redirects out BEFORE the
    grouping/wrapper scan runs — rather than after, on the scan's own
    output, as before this task — is what lets a redirect sitting between
    a wrapper and that wrapper's own options or command word (`sudo
    2>/dev/null -u root rm -rf ...`) stop neither: with the redirect still
    inline, the wrapper's own option-skip loop met the redirect's leading
    fd digit immediately after the wrapper name, read it as looking like a
    command word, and stopped there — misreading the wrapper's OWN flag
    (`-u`) as the command. SHAPED_WORDS is `[]` for a statement that
    consists entirely of grouping syntax (no command here).

    TOKENS itself (the second yielded value) is UNCHANGED by this: it is
    still exactly what lexing/mark-stripping produced, so main()'s
    deferral computation (strip_grouping_prefix()/_deferral_head()/
    matches_target_shape()) keeps working from it precisely as before —
    only the destructive checks (check_rm(), check_git(), check_file_
    destruction(), check_external(), check_permissions(), check_self_
    modification(), and the substitution-headed route) read SHAPED_WORDS/
    REDIRECTS. CASE_STACK is reset to `[]` at the start of each chunk below
    (never carried across a substitution body, here-doc body, or
    `-c`/eval/here-string payload boundary — task0001 "the same command
    string or payload"), and a statement's own trailing separator flips a
    "body" frame to "pattern_first" when it contains `;;`, `;&`, or `;|`
    (`ends_case_item` below, task0004 postcondition 2 — `;;&` already
    contains `;;` as a substring, so it needs no separate test), so a case
    construct's pattern/body alternation survives across the terminator-
    separated statements of one chunk. This flip is evaluated for EVERY
    statement lex_segments() yields, including one with zero tokens
    (task0004 postcondition 2: "A statement with no tokens of its own
    still has its separator evaluated for case state") — a standalone
    `;;`/`;&`/`;|` line, with nothing else on it, is exactly such a
    statement, and skipping the flip for it left the NEXT statement's case
    state one step behind. Shaping (and this flip) is only ever applied
    when LEXED is True — grouping/closer recognition needs the
    `.is_operator`/`.quoted` provenance the parse-failure fallback does not
    have; on that path, SHAPED_WORDS/REDIRECTS instead come from
    _shape_fallback() (task0004 postcondition 7), a text-only, provenance-
    free approximation of the same stripping.

    The shell-payload extraction below runs on the SHAPED marked/quoted-
    marked parallels — statements()'s own MARKED/QUOTED_MARKED token
    sequences (still carrying raw UNRESOLVED_MARK/QUOTED_MARK residue),
    put through the SAME fused-closer-split/redirect-separation/LEAD-slice
    as the canonical SHAPED_WORDS above (_shape_parallel(), task0004
    postcondition 1) — rather than on the raw, unshaped sequences (as
    before this task). Extracting from the unshaped sequence meant a
    `-c`/eval/here-string invocation sitting behind grouping (`(bash -c
    'rm -rf ...')`) was never recognised: head()'s own skip has no grouping
    awareness, so the word it found there was the grouping token itself
    (`(`), never `bash`. Extracting from the marked-but-unstripped-of-
    markers tokens (rather than the flag-converted ones) is unchanged from
    before this task — converting residue into the per-token
    `.unresolved`/`.substitution_only` flags erases the substitution's
    textual trace from the token TEXT (the whole point of
    _strip_unresolved_marks()); extracting a `-c`/`eval`/here-string
    payload AFTER that conversion means the string pushed back onto
    PENDING for re-scanning no longer contains any trace of the
    substitution that used to sit in it, so the re-scanned statement's own
    marking pass has nothing left to find — a bare `bash -c 'rm -rf
    $(mktemp -d)'` used to re-scan as a targetless `rm -rf`, the exact
    zero-target hole this closes. Extracting from the marked-but-unstripped
    tokens instead means the marker character itself survives into the
    payload string, so the re-scan's OWN _mark_substitutions()/
    _strip_unresolved_marks() pass (run fresh, once, when that string is
    popped off PENDING) reproduces the same flag it would for the
    identical text written directly — the marker is plain, inert token
    content until then, so this cannot double-convert or nest
    (idempotent: each pass converts what it introduces, not what a previous
    pass already resolved). The tokens handed to the checks below (via
    `yield`) are still the flag-converted ones, unchanged from before this
    task.

    task0001 FR4: alongside the ordinary marked segments, this also lexes
    the SAME chunk through _mark_quoted_substitutions() — identical
    segment/token shape, differing only in which marker character sits at
    a substitution's position (see QUOTED_MARK) — and hands the
    corresponding quoted-marked segment to extract_shell_payload() so it
    can tell a quoted payload-position substitution from an unquoted one.
    Segment counts are expected to match (both lexings split the same
    underlying text on the same non-marker characters); a caller-side
    length check in extract_shell_payload() itself covers the case where
    they do not.

    task0002 FR11: CHUNK_SUBS below is the ordered list of every
    substitution match's raw body text seen so far across THIS statements()
    call — ALL_SUBS, appended to (never rebuilt) once per chunk from the
    same finditer() pass that already feeds PENDING, its results kept
    instead of discarded. _mark_substitutions() is given that chunk's
    OFFSET into ALL_SUBS so the index it bakes into each marker names a
    position in ALL_SUBS rather than in a per-chunk list (destructive-
    guard-command-name-substitution index-leak fix — see that function's
    docstring for why a chunk-local list is unsafe once marked text can
    leak into a re-scanned chunk). _strip_unresolved_marks() maps each
    `.substitution_only` token back to the one raw body it came from by
    that index encoded into its own surviving marker, not by a shared
    position counter — so this is not a new read of the raw command string
    beyond what this loop already performs, just string processing over
    CHUNK alone plus one running list.
    """
    pending = [command]
    budget = [MAX_SHELL_PAYLOAD_EXPANSIONS]
    # Relative scan-cost cap (TM-5): each chunk popped off PENDING below is
    # scanned a constant number of times (scan_structure() runs twice, plus
    # the lexing passes), so the running total of chunk lengths processed is
    # a fair proxy for total work done. A deeply nested substitution chain
    # requeues a slightly shorter copy of the same text at every level
    # (_span_inner()/CHUNK_SUBS above), so that total grows with the SQUARE
    # of nesting depth even though COMMAND itself only grows linearly — the
    # O(d x length) blowup this guards against. The cap is deliberately
    # relative to len(command) (8x, plus a floor so a short command with a
    # few legitimate levels of nesting is never cut short) rather than an
    # absolute character count: an absolute cap previously tried here made a
    # single large, flat command (a 60KB heredoc, a 50KB echo) trip the same
    # limit a small nested one would, which is wrong — cost must scale with
    # input length, not sit at a fixed ceiling regardless of it.
    scanned_chars = 0
    scan_budget = 8 * len(command) + 4096
    # Run-global: one list for the whole statements() call, appended to as
    # each chunk is processed, never rebuilt per chunk. A marker's encoded
    # index (see _mark_substitutions()) names a position in THIS list, so
    # it stays valid even if the marked token text leaks into a re-scanned
    # chunk pushed back onto PENDING (destructive-guard-command-name-
    # substitution index-leak fix) — a chunk-local list would desync there.
    all_subs = []
    while pending:
        chunk = pending.pop()
        scanned_chars += len(chunk)
        if scanned_chars > scan_budget:
            decide(
                "ask",
                "scan-budget-exceeded",
                "入れ子/積み上げの構造が深く、静的解析の走査量が入力長に対して"
                "過大になったため打ち切った。安全側で確認を挟む。",
            )
        chunk, heredocs = strip_heredocs(chunk)
        # Component 1: ONE structural scan of CHUNK, shared by every caller
        # below that needs to know where CHUNK's own top-level substitutions
        # sit -- the heredoc destination decision, and this chunk's own
        # CHUNK_SUBS/marking -- rather than each re-lexing or re-scanning
        # CHUNK on its own (NFR3; also what lets a heredoc's destination and
        # this chunk's own substitution marking agree by construction).
        chunk_scan = scan_structure(
            chunk, mode="shell", checkpoints=[r.op_start for r in heredocs]
        )
        # This chunk's own general, non-heredoc substitution discovery --
        # what CHUNK_SUBS (recursion) and this loop's own _mark_
        # substitutions()/_mark_quoted_substitutions() calls below read --
        # predates this task and must keep its own, wider, quote-agnostic
        # reach (scan_structure()'s HONOR_SINGLE_QUOTES docstring): every
        # per-token check downstream (check_rm() among them) reads
        # `.unresolved`/`.substitution_only` as "this token's value was
        # never fully present", a static reading that has never depended on
        # whether the `$(`/backtick sat inside a pair of single quotes. The
        # heredoc destination decision (CHUNK_SCAN above, passed to
        # _heredoc_destinations() untouched) stays on the quote-aware
        # default it needs for correct statement/case-state structure; only
        # TOP_SPANS below reads the wider scan.
        legacy_spans, legacy_parent_of, _l_unmatched, _l_opaque, _l_containing = (
            scan_structure(chunk, mode="shell", honor_single_quotes=False)
        )
        top_spans = _top_level_spans(legacy_spans, legacy_parent_of)
        if heredocs:
            # Component 2/3 (task0001): each heredoc is judged on its own
            # destination, not on whether a sink word appears ANYWHERE in
            # the chunk -- see _heredoc_destinations().
            destinations = _heredoc_destinations(chunk, heredocs, chunk_scan)
            # task0003 Change 2 (SC2): the fallback for an undeterminable
            # heredoc matches when SHELL_SINK finds a sink word in the
            # heredoc-stripped chunk as written (today's behaviour, kept
            # exactly) OR in that same chunk with every `'`/`"`/`\` removed
            # (task plan Change 2) -- so a sink name split across quote
            # characters (`b"a"s"h"`) is still caught. Computed once per
            # chunk, not once per heredoc, since every undeterminable
            # heredoc in this chunk asks the identical chunk-wide question.
            chunk_sink_fallback = bool(
                SHELL_SINK.search(chunk) or SHELL_SINK.search(_strip_quote_chars(chunk))
            )
            for index, record in enumerate(heredocs):
                if not record.body.strip():
                    continue  # a blank body is never queued, as before this task
                destination = destinations.get(index, "undetermined")
                if destination == "sink" or (
                    destination == "undetermined" and chunk_sink_fallback
                ):
                    pending.append(record.body)
                elif not record.quoted:
                    # An unquoted delimiter (`<<EOF`, not `<<'EOF'`/
                    # `<<"EOF"`) means the shell itself expands
                    # `$(...)`/`` `...` `` inside the body before the body
                    # ever reaches the destination command -- true even
                    # when that destination is a plain data command (`cat
                    # <<EOF\n$(git reset --hard $(echo HEAD))\nEOF`). The
                    # body itself is not re-scanned as a statement here (it
                    # is still just data once expanded), but each OUTERMOST
                    # substitution inside it is queued for the same
                    # scanning every other substitution gets.
                    # _extract_heredoc_body_substitutions() uses Component
                    # 1's own scan_structure() (`heredoc-body` mode) to find
                    # each outermost `$( … )`/`` ` … ` `` whole, however
                    # deeply nested, rather than a single-level regex that
                    # would find just the inner `echo HEAD` and silently
                    # drop the outer, actually-executed `git reset --hard
                    # ...`; queuing that whole body (rather than trying to
                    # recurse here) is enough, because the queued text goes
                    # through the ordinary chunk path next iteration, whose
                    # own top-level-span scan then finds the nested
                    # substitution in turn. A backslash-escaped `$(` is
                    # literal text the shell never expands, so it is not a
                    # substitution boundary here either.
                    bodies, needs_whole_body = _extract_heredoc_body_substitutions(
                        record.body
                    )
                    if needs_whole_body:
                        # An unbalanced/unclosed `$(`/`` ` `` could not be
                        # extracted as a discrete substitution; treat the
                        # whole body as the scan target rather than silently
                        # dropping it.
                        pending.append(record.body)
                    else:
                        for body in bodies:
                            if body.strip():
                                pending.append(body)
        # TOP_SPANS (Component 1, computed once above) already reflects true
        # nesting, unlike SUBSTITUTION's own single-level, paren-free regex:
        # a chunk-local substitution several levels deep no longer needs a
        # second regex pass here to be marked at all. Each span's own inner
        # text is queued; a nested level inside it is found in turn once
        # that text is popped off PENDING and scanned as its own chunk.
        chunk_subs = [_span_inner(chunk, span)[0] for span in top_spans]
        for body in chunk_subs:
            if body.strip():
                pending.append(body)
        offset = len(all_subs)
        all_subs.extend(chunk_subs)
        quoted_segments = lex_segments(_mark_quoted_substitutions(chunk, top_spans))
        # task0001: case-pattern/body state, scoped to this one chunk only.
        case_stack = []
        for seg_index, (marked, lexed, sep) in enumerate(
            lex_segments(_mark_substitutions(chunk, top_spans, offset))
        ):
            toks = _strip_unresolved_marks(marked, all_subs)
            if lexed:
                fused = _split_fused_closer_redirects(toks)
                words_only, redirects = split_redirects(fused, lexed)
                lead = _shape_leading(words_only, case_stack)
                shaped_words = _shaped_remainder(words_only, lead)
                # task0004 postcondition 2: evaluated for every statement,
                # including one with zero tokens (an standalone
                # `;;`/`;&`/`;|` line) — see this function's docstring.
                # `;;&` already contains `;;`, so no separate test for it.
                ends_case_item = bool(
                    sep and any(term in sep for term in (";;", ";&", ";|"))
                )
                if ends_case_item and case_stack and case_stack[-1] == "body":
                    case_stack[-1] = "pattern_first"
            else:
                fallback_words, redirects = split_redirects(toks, lexed)
                shaped_words = _shape_fallback(fallback_words)

            if toks:
                yield " ".join(toks), toks, lexed, shaped_words, redirects
                if budget[0] > 0 and lexed:
                    quoted_marked = (
                        quoted_segments[seg_index][0]
                        if seg_index < len(quoted_segments)
                        else None
                    )
                    shaped_marked_words, marked_redirects = _shape_parallel(
                        marked, len(words_only), lead
                    )
                    payload_toks = shaped_marked_words + marked_redirects
                    if quoted_marked is not None:
                        shaped_quoted_words, quoted_redirects = _shape_parallel(
                            quoted_marked, len(words_only), lead
                        )
                        quoted_payload_toks = shaped_quoted_words + quoted_redirects
                    else:
                        quoted_payload_toks = None
                    payload = extract_shell_payload(
                        payload_toks, lexed, quoted_payload_toks
                    )
                    if payload and payload.strip():
                        budget[0] -= 1
                        pending.append(payload)


def tokens(segment):
    """Best-effort tokenization. Falls back to whitespace on a parse error."""
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def _skip_assignments_and_wrappers(toks):
    """Advance past VAR=value assignments, WRAPPERS (and their value-taking
    options), and mise/asdf `exec` prefixes — the skip loop head() has
    always applied, minus its `.substitution_only` handling.

    Factored out of _skip_to_command_word() (task0001) so that the
    grouping/case-aware scan in statements() (_shape_leading()) can
    interleave this same skip with its own — a subshell wrapping a WRAPPER
    (`( sudo rm -rf /home/sakura/x )`), or a reserved word introducing a
    VAR=value prefix (`then HOME=/home/sakura/y`) — WITHOUT also consuming
    a `.substitution_only` token: that token must survive intact at the
    front of the shaped remainder statements() produces, so main()'s
    separate, unchanged call to _skip_to_command_word() on the shaped
    tokens still finds it and still drives route_substitution_headed_
    statement() exactly as it does for an unwrapped statement (see
    _shape_leading()'s docstring).

    Returns the index in TOKS where this stops — 0 when TOKS[0] itself
    doesn't match anything here (including when it is `.substitution_only`,
    which this function does not look at all).
    """
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if re.match(r"^[A-Za-z_]\w*=", t):  # VAR=value prefix
            i += 1
            continue
        if t in WRAPPERS:
            i += 1
            value_flags = WRAPPER_VALUE_FLAGS.get(t, set())
            while i < n:
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
        if t in ("mise", "asdf") and i + 1 < n and toks[i + 1] == "exec":
            i += 2
            while i < n and toks[i] != "--":
                i += 1
            i += 1  # step past the `--`
            continue
        break
    return i


def _skip_to_command_word(toks):
    """Advance past VAR=value assignments, WRAPPERS (and their value-taking
    options), and mise/asdf `exec` prefixes (_skip_assignments_and_
    wrappers()) — exactly the skip loop head() has always applied —
    additionally tracking whether a `.substitution_only` token (an argument
    built entirely from a command substitution) was skipped along the way
    (task0001 FR1/FR2/FR3, AS-2).

    Any grouping/case/reserved-word syntax at command position (task0001
    FR1/FR2) has already been stripped upstream, in statement shaping
    (statements(), via _shape_leading()) — see that function's docstring —
    before this function ever sees the tokens; it does not look for such
    syntax itself, exactly as before this task.

    Returns (index, saw_substitution, last_substitution_tok). INDEX is where
    the scan stops: either a real candidate token, or len(TOKS) when none
    remains — head() turns this into its own (word, args) return unchanged.
    SAW_SUBSTITUTION and LAST_SUBSTITUTION_TOK feed the "statically unknown
    command word" classification in main() (task0002 FR11:
    LAST_SUBSTITUTION_TOK is the `.substitution_only` token closest to the
    stop index, whose `.raw_substitution_body` route_substitution_headed_
    statement() reads as evidence; None when no such token was skipped).
    head() itself ignores both, so its own return shape and behaviour are
    unchanged by this refactor.
    """
    i = 0
    n = len(toks)
    saw_substitution = False
    last_substitution_tok = None
    while i < n:
        t = toks[i]
        if getattr(t, "substitution_only", False):
            saw_substitution = True
            last_substitution_tok = t
            i += 1
            continue
        advance = _skip_assignments_and_wrappers(toks[i:])
        if advance:
            i += advance
            continue
        break
    return i, saw_substitution, last_substitution_tok


def head(toks):
    """Return (command word, remaining args), skipping assignments/wrappers.

    Mirrored in failed-run-cleanup-guard.py's own head() — keep both in sync.
    That mirror does not know about `Tok.substitution_only`; the skip added
    here for it, AND the "statically unknown command word" classification
    and its route into route_substitution_headed_statement() built on top
    of it in main() (task0001 FR1/FR2/FR3; task0002 FR11/FR13 rebuilt that
    routing around read command-name evidence rather than remainder shape),
    are local to this file and do not change the shape of this function's
    return value, which stays the 2-tuple both files already agree on. The
    grouping/case-aware skip that now runs upstream of this function, in
    statement shaping (statements(), via _shape_leading()) — subshells,
    brace groups, reserved words, case patterns, function definitions
    (task0001 FR1/FR2/FR3) — is, the same as `.substitution_only`, local to
    this file: that mirror's own head() has no grouping awareness at all,
    and stays that way. This function itself needs no change for that
    upstream stripping: main()'s own call passes SHAPED_WORDS, which
    statement shaping (statements(), via _shape_leading()) has already
    stripped of that vocabulary. _deferral_head()'s call passes words
    narrowed by strip_grouping_prefix() instead — deliberately, per that
    function's own docstring, a strictly narrower strip than
    _shape_leading()'s — so a leading case pattern or reserved word can
    still reach this function unstripped on that path; this function
    itself does not look for such syntax either way.

    A token flagged `.substitution_only` (an argument built entirely from a
    command substitution, task0001 Design Part 1) sits where a command name
    or wrapper token would be, but its real text is unknown statically — it
    can expand to nothing. Skipping it here lets a real command word that
    follows it still be found and checked.
    """
    i, _, _ = _skip_to_command_word(toks)
    if i >= len(toks):
        return None, []
    return os.path.basename(toks[i]), toks[i + 1 :]


# Reserved words that carry no command of their own wherever they sit at
# command position (task0001 FR2): the `if`/`while`/`until` family and its
# body-introducing counterparts, `!`, and the two bare closers/terminators
# that never need CASE_STACK to be recognised (unlike `)`, `esac`, and a
# case pattern, which do — see _shape_leading()). `case`, `esac`, `for`,
# and `select` are handled separately in _shape_leading() itself, since
# each needs more than a single-token skip.
RESERVED_SKIP_WORDS = frozenset(
    {"if", "then", "elif", "else", "while", "until", "do", "!", "fi", "done"}
)


def _split_fused_closer_redirects(toks):
    """Split an unquoted operator token that STARTS with a run of one or
    more `)` into one closer token per `)`, then classify whatever text
    remains after that run (task0001 FR3, generalised by task0004
    postcondition 5 to a run of any length, not just one): a leading `(`
    in the remainder becomes its own subshell-opener token (also split one
    per `(`, in case more than one follows), and — once every leading
    closer/opener character has been peeled off — anything still left
    (typically a real redirect operator: `)>`, `)>>`, `)2>`, `))>`, `)(`
    and similar) is kept as a single token, unchanged, so split_redirects()
    can still match it against REDIRECT as a whole.

    shlex's punctuation_chars fuses ANY run of contiguous punctuation
    characters into one raw token regardless of which characters they are,
    and lex_segments()'s own fused-token splitter only re-splits a run
    whose characters fall in two different SEGMENT_CHARS/non-SEGMENT_CHARS
    buckets (needed so a `;`-adjacent operator like `;>` still separates
    correctly) — `)`, `(`, and a redirect's own characters (`>`, `<`, `&`)
    all land in the SAME bucket (none is a SEGMENT_CHARS separator), so
    they survive lex_segments() as one token, and split_redirects() — which
    matches REDIRECT against a token's WHOLE text — never recognises `)>`
    or `))>` as a redirect at all, and `_shape_leading()` never recognises
    a run like `))` or `)(` as more than one closer/opener. Without this
    split, `(cp /tmp/x ~/.claude/settings.json)>/dev/null` reads `)>/dev/
    null` as one ordinary (non-redirect) word, and `( (rm -rf /tmp/x))`
    reads its trailing `))` as one ordinary (non-closer) word too.

    Applied to a statement's full token list before redirects are pulled
    out and before _shape_leading() scans it, so a fused closer/opener run
    is already clean by the time redirect-separation and closer-recognition
    (leading or case-pattern-closing) run.
    """
    out = []
    for t in toks:
        if not (getattr(t, "is_operator", False) and len(t) > 1 and t[0] == ")"):
            out.append(t)
            continue
        rest = t
        while rest and rest[0] == ")":
            out.append(Tok(")", True))
            rest = rest[1:]
        while rest and rest[0] == "(":
            out.append(Tok("(", True))
            rest = rest[1:]
        if rest:
            out.append(Tok(rest, True))
    return out


def _shape_leading(toks, case_stack):
    """Advance past every construct that can sit at command position:
    grouping and compound-construct syntax (task0001 FR1/FR2 — the
    subshell opener `(` as an unquoted operator token only, the
    brace-group opener `{`, the reserved words in RESERVED_SKIP_WORDS, a
    case pattern, and a function-definition prefix), interleaved with the
    existing VAR=value/WRAPPERS/mise-asdf skip
    (_skip_assignments_and_wrappers()) so a combination like `then
    HOME=/home/sakura/y` or `( sudo rm -rf /home/sakura/x )` unwraps fully
    (task0001 "Nested and combined forms unwrap fully").

    Deliberately does NOT call _skip_to_command_word() and does NOT look at
    `.substitution_only` itself: a `.substitution_only` token never matches
    any check here (its text is SUBSTITUTION_STANDIN, `$(...)`, matching
    neither a reserved word nor `(`/`{`/`)`/`}` nor IDENT), so it always
    stops this scan and survives, untouched, as the first token of the
    shaped remainder — exactly where main()'s own, separate call to
    _skip_to_command_word() (on that shaped remainder, unchanged from
    before this task) expects to find it, so route_substitution_headed_
    statement() keeps working for a command name hidden behind grouping
    exactly as it does for an unwrapped statement.

    A WORD token equal by text alone to `case`/`esac`/a RESERVED_SKIP_WORDS
    entry/`for`/`select`/`function` is treated as that keyword only when
    `.quoted` is False (task0004 postcondition 3, 7): `.is_operator` cannot
    tell a bare `case` apart from a quoted `"case"` the way it does for `(`/
    `)`, since neither ever enters the punctuation-sticky lexer state — see
    Tok's own docstring. `{`/`}` get the same guard for the same reason,
    even though nothing pins a quoted-brace case today.

    `case`/`esac` recognition at command position (top is `None`/"body"
    below) is additionally FAIL-CLOSED on a preceding command wrapper or
    VAR=value prefix (task0004 postcondition 3): `command case x in ...`,
    `sudo case x in ...`, and `FOO=bar case x in ...` never open a case
    construct — in each, `case` is the wrapped/assigned command's own NAME,
    not the keyword — because a real shell only recognises `case` as a
    reserved word when it is literally the first word of the command, and
    `command`/`sudo`/`env`/the rest of WRAPPERS (unlike a real shell
    keyword) do not change what the NEXT word means the way `time`/`!` do.
    `time` and `!` are shell keywords in their own right and MAY precede a
    real `case` (`time case x in ...` opens one, same as bare `case`).
    CASE_BLOCKED tracks this: set True whenever the wrapper/assignment skip
    below consumes at least one VAR=value token or one WRAPPERS entry other
    than `time`, consumed (and reset) by the very next token's `case`/`esac`
    check; entering a case-pattern state (`top` no longer `None`/"body")
    always clears it, since a stale block from tokens before the construct
    started must never leak into pattern content.

    CASE_STACK (task0001 "Case patterns") is a list of per-case-construct
    stage strings, carried by the caller across every statement of one
    chunk (reset per chunk — case context does not cross a substitution
    body, here-doc body, or `-c`/eval/here-string payload boundary, each of
    which is its own chunk): "await_subject" (just saw `case`, next token
    is the subject word), "await_in" (subject consumed, next token is
    expected to be `in`), "pattern_first" (the FIRST word of a pattern
    position — right after `in`, or right after an item terminator via the
    caller's `;;`/`;&`/`;|` flip below), "pattern_rest" (reading pattern
    text past that first word — task0004 postcondition 4, distinguished
    from "pattern_first" because `esac` closes the case ONLY at the first-
    word position, never here), and "body" (past a pattern's closing `)`;
    ordinary command-position scanning resumes, including recognising a
    NESTED `case`).

    In "pattern_first", `esac` closes the whole construct (pop) UNLESS it
    is immediately followed by the pattern closer `)` (a real operator
    token) — that shape (`esac)`) means the pattern's literal text IS the
    string `esac`, so it is read as opaque pattern content instead
    (transition to "pattern_rest") and the following `)` still closes the
    pattern normally on the next token — OR unless the token is quoted
    (`.quoted`, task0002 Component 3: "A quoted esac... never closes it"),
    which reads as pattern text on that footing alone, regardless of what
    follows it — the FIRST alternative of a `|`-split pattern (`'esac'|x)
    ...`) has nothing of its own immediately after it (the `|` ends this
    statement, same as any pipe-split pattern; see below), so only the
    quoting test, not the closer-adjacency one, keeps it from closing
    there. `esac` reached in "pattern_rest" — a LATER alternative after a
    pipe-split, or any word past the first — is always opaque content,
    never a closer regardless of quoting (task0004 postcondition 4). A
    case statement with no items at all,
    `case x in esac`, is still valid: "pattern_first" with nothing after
    `esac`, which is not "followed by `)`" and so pops. The caller
    (statements()) additionally flips a "body" frame to "pattern_first"
    (a genuine new first-word position) when the statement's own trailing
    separator contains `;;`, `;&`, or `;|` (task0004 postcondition 2) — a
    pattern can itself be split across statements by `|` (segment-split,
    like a pipe) or by a newline, in which case the "pattern_first"/
    "pattern_rest" distinction the FIRST such statement reached simply
    carries over unchanged into the next one (see this function's
    per-statement scope: a pattern that continues into the NEXT statement
    leaves CASE_STACK's top at whichever pattern state this scan reached
    when it hit the end of TOKS without finding the closing `)`).

    Returns the index in TOKS where the scan stops: either the token that
    starts the shaped remainder, or len(TOKS) when every token in this
    statement was consumed as pure syntax (no command here — task0001 FR2
    "closers... carry no command of their own", and the `for`/`select`
    header, whose WORDS are never a command either).
    """
    i, n = 0, len(toks)
    case_blocked = False
    while i < n:
        top = case_stack[-1] if case_stack else None
        t = toks[i]

        if top in ("await_subject", "await_in", "pattern_first", "pattern_rest"):
            case_blocked = False  # a stale block never leaks into a pattern
            if top == "await_subject":
                case_stack[-1] = "await_in"
                i += 1
                continue
            if top == "await_in":
                case_stack[-1] = "pattern_first"
                i += 1  # the subject WORD does not need its own text read
                continue
            if top == "pattern_first":
                followed_by_closer = (
                    i + 1 < n
                    and toks[i + 1] == ")"
                    and getattr(toks[i + 1], "is_operator", False)
                )
                if (
                    t == "esac"
                    and not getattr(t, "quoted", False)
                    and not followed_by_closer
                ):
                    case_stack.pop()
                    i += 1
                    continue
                if t == ")" and getattr(t, "is_operator", False):
                    case_stack[-1] = "body"
                    i += 1
                    continue
                case_stack[-1] = "pattern_rest"  # first word read; esac now inert
                i += 1
                continue
            # top == "pattern_rest": opaque content until a real `)` closes
            # it. `esac` here is always pattern text (task0004 FR4).
            if t == ")" and getattr(t, "is_operator", False):
                case_stack[-1] = "body"
                i += 1
                continue
            i += 1
            continue

        # top is "body" or CASE_STACK is empty: ordinary command-position
        # scanning, interleaved with the existing assignment/wrapper skip.
        advance = _skip_assignments_and_wrappers(toks[i:])
        if advance:
            consumed = toks[i : i + advance]
            if any(
                re.match(r"^[A-Za-z_]\w*=", c) or (c in WRAPPERS and c != "time")
                for c in consumed
            ):
                case_blocked = True
            else:
                case_blocked = False
            i += advance
            continue

        blocked, case_blocked = case_blocked, False
        quoted = getattr(t, "quoted", False)
        if t == "esac" and case_stack and not blocked and not quoted:
            case_stack.pop()
            i += 1
            continue
        if t == "case" and not blocked and not quoted:
            case_stack.append("await_subject")
            i += 1
            continue
        if t in RESERVED_SKIP_WORDS and not quoted:
            i += 1
            continue
        if t == "}" and not quoted:
            i += 1
            continue
        if t == ")" and getattr(t, "is_operator", False):
            i += 1  # a bare closer with nothing (recognised) open — FR3
            continue
        if (
            t in ("for", "select")
            and not quoted
            and i + 2 < n
            and toks[i + 2] == "in"
        ):
            i = n  # the header's WORDS are never a command (FR2)
            continue
        if t == "(" and getattr(t, "is_operator", False):
            i += 1
            continue
        if t == "{" and not quoted:
            i += 1
            continue
        if (
            i + 2 < n
            and not quoted
            and IDENT.match(t)
            and toks[i + 1] == FUNC_SIGNATURE
            and toks[i + 2] == "{"
        ):
            i += 2  # `NAME() {` — the `{` itself is picked up next round
            continue
        if (
            t == "function"
            and not quoted
            and i + 1 < n
            and IDENT.match(toks[i + 1])
        ):
            if i + 3 < n and toks[i + 2] == FUNC_SIGNATURE and toks[i + 3] == "{":
                i += 3  # `function NAME() {`
                continue
            if i + 2 < n and toks[i + 2] == "{":
                i += 2  # `function NAME {`
                continue
        break
    return i


def _deferral_head(words):
    """Like head(), but a wrapper token spelled with an absolute/relative
    path (`/usr/bin/sudo`) is normalized to its basename before the wrapper
    check, matching failed-run-cleanup-guard.py's own basename-based wrapper
    detection. Only feeds the deferral computation in main() — head() itself,
    and every other caller of it, still compares raw tokens, so no existing
    deny/ask verdict changes because of this.
    """
    normalized = list(words)
    i = 0
    n = len(normalized)
    while i < n:
        t = normalized[i]
        if re.match(r"^[A-Za-z_]\w*=", t):
            i += 1
            continue
        basename = os.path.basename(t) if os.path.sep in t else t
        if basename in WRAPPERS:
            normalized[i] = basename
            i += 1
            value_flags = WRAPPER_VALUE_FLAGS.get(basename, set())
            while i < n:
                a = normalized[i]
                if a == "--":
                    i += 1
                    break
                if a == "-" or not a.startswith("-"):
                    break
                i += 1
                if a in value_flags:
                    i += 1  # consume the option's value token
            continue
        if t in ("mise", "asdf") and i + 1 < n and normalized[i + 1] == "exec":
            i += 2
            while i < n and normalized[i] != "--":
                i += 1
            i += 1  # step past the `--`
            continue
        break
    return head(normalized)


def _expand_short_clusters(args):
    """Split a clustered short-option token (`-dr`) into its individual
    letters (`-d`, `-r`), the same expansion failed-run-cleanup-guard.py's
    own classify() applies, so a flag bundled into a cluster is still found
    by has(). `--` stops expansion (options after it are operands, not
    flags) and `--long` spellings are left untouched. Only used by
    matches_target_shape()'s S2 shape match; check_git()'s own has()/
    short_flags() calls are untouched, so no existing verdict changes.
    """
    out = []
    stop = False
    for a in args:
        if stop or not re.fullmatch(r"-[A-Za-z]+", a):
            out.append(a)
        else:
            out.extend(f"-{c}" for c in a[1:])
        if a == "--":
            stop = True
    return out


def git_subcommand(args):
    """Strip git's global options and return (subcommand, its args).

    Mirrored in failed-run-cleanup-guard.py's own git_subcommand() (used
    inside its classify()) — keep both in sync. That mirror does not know
    about `Tok.substitution_only`; the skip added here for it is local to
    this file and does not change the shape of the return value, which
    stays the 2-tuple both files already agree on. The same holds for the
    git route (FR2, main(), route_substitution_headed_statement()): offering
    an ARGS list that starts beyond a statically-unknown command word —
    rather than always starting right after a literal `git` token — is a
    caller-side change in main(), not a change to this function's own
    signature or behaviour. task0001 first built that route on the
    remainder's own shape; task0002 rebuilt it around statically read
    command-name evidence (read_command_name_evidence(),
    route_substitution_headed_statement()) and folded the dispatch into one
    function. Both the routing logic and the evidence reader it calls are
    equally local to this file — the mirror carries neither.

    A token flagged `.substitution_only` sitting where a global option or
    the subcommand itself would be is skipped, the same reasoning head()
    applies to a command-position substitution.
    """
    i = 0
    while i < len(args):
        a = args[i]
        if getattr(a, "substitution_only", False):
            i += 1
            continue
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


def read_command_name_evidence(raw_body):
    """Read a command name out of RAW_BODY, or return None ("unreadable")
    when it cannot be read (task0002 FR11).

    RAW_BODY is the raw text of the substitution that sat at a statement's
    command-word position — recovered by _strip_unresolved_marks()'s
    occurrence-order mapping (see that function's docstring) and carried on
    the skipped token as `.raw_substitution_body` — or None when that
    mapping could not attribute a single raw occurrence to the token (no
    substitution reachable, several concatenated into one whole word, or
    nesting left the raw extent indeterminable; see that docstring for each
    case).

    String processing only: no substitution is evaluated, no subprocess is
    launched, no path is resolved or stat-ed, nothing is read from the
    filesystem (R1, NFR1). Evidence is never taken from any word of the
    body other than the last one — a body in which an rm/git word appears
    as some other command's own argument must not produce a route entry.

    Reading, in order:
    1. RAW_BODY is None, or empty/whitespace-only once stripped: unreadable.
    2. Split on whitespace; take the LAST word.
    3. That word begins with `-`: unreadable — a real shell could never use
       an option spelling as a command name.
    4. Otherwise, the basename of that last word (`os.path.basename`) — an
       absolute or relative path (`/usr/bin/rm`) reads the same as the bare
       name, matching how a real shell would resolve it. A basename that
       comes out empty (the word was a bare trailing path separator, naming
       no file) is unreadable too.
    """
    if raw_body is None:
        return None
    body = raw_body.strip()
    if not body:
        return None
    last = body.split()[-1]
    if last.startswith("-"):
        return None
    name = os.path.basename(last)
    return name or None


def route_substitution_headed_statement(remainder, raw_body, segment, next_rm_invocation):
    """The single entry point for a statement whose command-word position
    held a substitution token that _skip_to_command_word() skipped
    (task0002 FR1/FR2/FR3/FR11/FR13 — supersedes task0001's shape-based
    pre-gates, both removed: the dash-leading pre-gate and the recursion-
    AND-force-AND-operand pre-screen _rm_route_candidate() used to apply).

    NEXT_RM_INVOCATION is main()'s counter callback (task0001 FR4): called
    exactly once, only on the branch that actually reaches check_rm(), so a
    substitution-headed statement that evidences "git" or nothing readable
    never consumes an invocation ordinal.

    REMAINDER is the statement's own tokens from that skip point onward —
    exactly what would be `args` for the plain spelling of the read command
    name (task0001 FR1/FR2, AS-3). RAW_BODY is the raw text of the
    substitution that sat there (see read_command_name_evidence()). SEGMENT
    is passed through to check_git() unchanged, matching its existing
    signature.

    Returns the rm shape matcher's own list of (tier, rule, target,
    message) decisions for main() to pool (D6) when evidence reads as
    "rm"; calls check_git() (which decide()s and exits directly, or returns
    None) when evidence reads as "git"; returns [] — no route entered, no
    decision — when evidence reads as anything else, or is unreadable (R4:
    falls open, never `ask`; a fallback `ask` would demote to `deny`
    unattended and halt normal operation, NFR3). Two forms are therefore
    left `allow` by design and declared as this hook's out-of-scope range
    rather than treated as an oversight (FR7): a substitution-headed form
    whose command name cannot be read this way, and (unrelated to this
    function — see extract_shell_payload()) a form whose substitution
    *result* becomes the script body.

    R2/R3: the command name read here is the ONLY entry condition — the
    remaining tokens' flag shape is never consulted to decide whether to
    enter a route. Once entered, REMAINDER is handed to the existing shape
    matcher completely unfiltered; no route-side floor is added, so the
    matcher's own threshold and its own safe-route exceptions decide
    exactly as they do for the plain spelling of the same command (R6,
    NFR7) — this is what makes the substitution-headed spelling never
    stricter than the plain one hold by construction rather than by
    inspection. R5: no new tier, no new reason id — whatever the matcher
    returns is what is returned or decided.
    """
    name = read_command_name_evidence(raw_body)
    if name == "rm":
        return check_rm(remainder, next_rm_invocation())
    if name == "git":
        check_git(remainder, segment)
    return []


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


DELETION_PLACEHOLDER = "<対象>"

# The gio-versus-mv branch selection below (gio on PATH, target under HOME,
# control characters in the target) is unchanged by task0001; only the
# rendering of the chosen alternative changed — a fixed placeholder stands in
# for the target instead of the target's own text (FR4).


def deletion_alternative(target):
    """A concrete command TEMPLATE to offer in place of the delete being
    refused — never the target's own text (task0001 FR4): the caller already
    designates the target by position (rm_target_designation()), so this
    function only needs to pick WHICH template applies.

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
    if not gio_available():
        return f"`mv -- {DELETION_PLACEHOLDER} /tmp/` で退避する（gio が無いのでゴミ箱は使えない）。"
    if path == home or path.startswith(home + os.sep):
        return f"`gio trash -- {DELETION_PLACEHOLDER}` に書き換える（復元情報が残り、ゴミ箱から戻せる）。"
    return (
        f"`mv -- {DELETION_PLACEHOLDER} /tmp/` で退避する"
        f"（$HOME の外はゴミ箱がファイルシステムをまたげないので `gio trash` は失敗する）。"
    )


def _is_dotglob_component(component):
    """Whether COMPONENT both starts with `.` and carries a glob wildcard —
    the one shape a glob component can use to reach a parent reference
    (`.*` matches `..`; a bare `*` cannot, since shell globbing skips
    dotfiles). Excluded from the safe-root exception wherever it appears
    below a matching root — see safe_delete_target().
    """
    return component.startswith(".") and bool(GLOB_CHARS.search(component))


def _has_parent_ref_component(token):
    """Whether TOKEN's path, split on `/`, contains a literal `..` segment.

    Checked on the RAW token, before normalize_candidate() folds `..` away —
    folding a parent reference past an unresolved glob component is not
    trustworthy (the glob's actual match is unknown at check time), so
    check_rm() judges this combination unresolvable instead of trusting the
    fold.
    """
    return ".." in token.split("/")


def safe_delete_target(normalized):
    """Whether NORMALIZED — already home-expanded and lexically folded by
    normalize_candidate() — is contained in a safe root, per the two-class
    vocabulary in SAFE_DELETE_BUILD_ARTIFACTS / SAFE_DELETE_SCRATCH_ROOTS_*.
    Pure string comparison; the filesystem is never consulted.
    """
    if normalized.startswith("/"):
        for root in SAFE_DELETE_SCRATCH_ROOTS_ABS:
            if normalized == root:
                return False  # the root itself is never safe
            if normalized.startswith(root + "/"):
                rest = normalized[len(root) + 1 :].split("/")
                return not any(_is_dotglob_component(c) for c in rest)
        return False
    parts = normalized.split("/")
    head, rest = parts[0], parts[1:]
    if head in SAFE_DELETE_BUILD_ARTIFACTS:
        return not any(_is_dotglob_component(c) for c in rest)
    if head in SAFE_DELETE_SCRATCH_ROOTS_REL:
        if not rest:
            return False  # the root itself is never safe
        return not any(_is_dotglob_component(c) for c in rest)
    return False


# Tier ranking for D6's cross-target/cross-segment selection: `deny` outranks
# `ask`, `ask` outranks the implicit `allow` of no decision at all.
DECISION_RANK = {"allow": 0, "ask": 1, "deny": 2}

# The root/home shape check_rm() denies outright, matched against the RAW
# token before anything else — see check_rm()'s docstring, step 2.
RM_ROOT_SHAPE = re.compile(r"/+|/\*|~|~/|\$HOME/?")


def rm_target_designation(invocation_index, target_index, target):
    """A hook-authored designation for TARGET, naming its POSITION instead of
    its text (task0001 FR4, "Target designation" contract): the
    INVOCATION_INDEXth `rm` invocation the hook encountered while analysing
    this command (1-based, in the order main() reaches it — including one
    found inside a command-substitution body via
    route_substitution_headed_statement()), and the TARGET_INDEXth operand of
    that invocation (1-based among TARGETS in check_rm(), options not
    counted).

    Two different targets never receive the same designation: every target
    check_rm() judges reaches this function with a distinct
    (invocation_index, target_index) pair, because target_index is assigned
    by enumerate() over that one invocation's own TARGETS list and
    invocation_index is unique per check_rm() call (main() hands out a fresh
    one per `rm` invocation, direct or substitution-headed). The pair is a
    pure function of the command text — the same command always drives
    main()'s loop the same way — so the same command always yields the same
    designation for the same target (NFR2).

    Contains no character taken from TARGET, with one exception: a TARGET
    built entirely from command substitution (`.substitution_only`) may show
    the fixed stand-in the hook already writes for that case
    (SUBSTITUTION_STANDIN, SPEC.md a3) next to the position — that text is
    hook-authored and constant, never copied from the target. That suffix
    uses ASCII square brackets rather than the full-width parentheses every
    caller below wraps the whole designation in, so the two never nest into
    an unreadable "（…（…）…）" when both apply to the same target.
    """
    designation = f"{invocation_index}番目のrmの{target_index}番目の対象"
    if getattr(target, "substitution_only", False):
        designation += f"[`{SUBSTITUTION_STANDIN}`]"
    return designation


def check_rm(args, invocation_index):
    """Return the decision every target of one `rm` invocation warrants, as
    a list of (tier, rule, designation, message) tuples — never emits and
    never exits. A check that emitted the first decision it reached let an
    `ask` on an early target end the scan, so a later target — or, once the
    caller folds multiple calls together, a later segment — that warranted
    `deny` was approved along with it (D6). Collecting every target's
    decision here, uncollapsed, is what lets the caller (main()) evaluate
    every target of every segment before picking the strongest one and
    emitting once.

    INVOCATION_INDEX is this `rm` invocation's own 1-based ordinal among
    every `rm` invocation main() hands to check_rm() for the command under
    analysis (task0001 FR4) — passed straight through to
    rm_target_designation() for every target below whose reason names a
    position instead of its text. It plays no part in steps 1-2: the
    `rm-root` decision keeps naming its RAW token verbatim (SPEC.md a2, fixed
    RM_ROOT_SHAPE vocabulary only, never free text), unaffected by this
    task.

    Per target, in this order (IMPLEMENTATION.md "Recursive-delete check"),
    unchanged from before D6 except that each step now APPENDS instead of
    deciding:

    1. Zero targets — empty list, unchanged.
    2. Root/home target (RM_ROOT_SHAPE) — judged on the RAW token, before
       anything below; reused unchanged so its `rm-root` reason id
       survives. A target already decided here is skipped by the
       remaining steps, matching the priority a single early decide() call
       used to give it.
    3. Unresolved — a variable expansion or command substitution still
       present in the token (UNRESOLVED_EXPANSION), a positional/special
       parameter form (UNRESOLVED_PARAM), a tilde form the normalizer does
       not expand (UNRESOLVED_TILDE), or a token whose value is entirely
       fabricated because the word it stands in for was built solely from
       one or more command substitutions with nothing else in it
       (`.substitution_only`, task0001 Design Part 1/3) — is unresolvable
       regardless of how it looks, and never reaches the safe exception.
       There is no path text to normalize for a `.substitution_only` target,
       so it is judged here, before step 4, on the same footing as the
       other three shapes; it shares their sentence because the sentence
       already covers both a variable expansion and a command substitution.
       A glob mixed with a literal `..` component is unresolvable for the
       same reason folding cannot be trusted there
       (_has_parent_ref_component()) — a PURE glob is not caught here; see
       step 6.
    4. Lexical normalization (normalize_candidate()) — filesystem-free.
    5. A relative target still starting with `..` after normalization has
       nowhere left to fold and is not safe; it falls straight through to
       step 7 exactly as containment failure would, so no separate branch
       is needed for it.
    6. Component-wise containment (safe_delete_target()) against the
       normalized target — SKIPPED when the lexing layer marked this
       token's text as evidence it lost to a substitution adjacent to other
       text in the same word (`.unresolved`, D7): folding a parent
       reference past that residue is not trustworthy, so it must not be
       allowed to land in the safe exception. A pure glob (no expansion, no
       parent reference, no lost evidence) still reaches this step and can
       still land in the safe exception (e.g. `dist/*`).
    7. Otherwise: a glob remaining in the RAW token is still unresolved
       (ask); anything else is a genuine recursive delete (deny) — the same
       tier a `.unresolved` target with no glob has always reached here,
       including the pre-existing pinned `deny` for a substitution-adjacent
       shape (task0001's `$(pwd)/build`); task0003 leaves this tier alone.
       The REASON differs for a `.unresolved` target, though (task0003
       Design Part 2): step 6 already established that its safe-root
       exception was suppressed because evidence was LOST, not because its
       real text actually sits outside every safe root, so the message
       states the substitution fact — part of the target comes from a
       command substitution and its range cannot be confirmed statically —
       instead of an assertion about position that may not hold for this
       input. A target with no lost evidence keeps the original wording,
       verbatim.
    """
    flags = short_flags(args)
    recursive = "r" in flags or "R" in flags or has(args, "--recursive")
    # A bare, unquoted grouping token (a subshell's trailing `)`, say, in
    # `(rm -rf $X)` with nothing after it) tokenizes as its own word and
    # lands in ARGS with no leading `-`, same shape as a real target —
    # `.is_operator` (Tok, set by the tracking lexer) is what tells the two
    # apart; a quoted `")"` is a real word and never carries it. Evaluating
    # every target now that D6 no longer exits on the first decision would
    # otherwise let this artifact outvote a real target under it.
    targets = [
        a
        for a in args
        if not a.startswith("-") and not getattr(a, "is_operator", False)
    ]

    if not targets:
        return []

    decisions = []
    root_hit = set()
    for t in targets:
        if RM_ROOT_SHAPE.fullmatch(t):
            decisions.append(
                ("deny", "rm-root", t, f"削除対象が `{t}` — ホーム/ルート全体に届く。")
            )
            root_hit.add(t)
    if not recursive:
        return decisions

    for target_index, t in enumerate(targets, start=1):
        if t in root_hit:
            continue
        designation = rm_target_designation(invocation_index, target_index, t)
        unresolved = getattr(t, "unresolved", False)
        if (
            getattr(t, "substitution_only", False)
            or UNRESOLVED_EXPANSION.search(t)
            or UNRESOLVED_PARAM.search(t)
            or UNRESOLVED_TILDE.search(t)
        ):
            decisions.append(
                (
                    "ask",
                    "rm-unresolvable",
                    designation,
                    f"再帰削除の対象（{designation}）が変数/コマンド置換で、影響範囲を静的に確定できない。"
                    f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。",
                )
            )
            continue
        if GLOB_CHARS.search(t) and _has_parent_ref_component(t):
            decisions.append(
                (
                    "ask",
                    "rm-unresolvable",
                    designation,
                    f"再帰削除の対象（{designation}）はグロブと親参照(`..`)が混在し、"
                    f"グロブの展開結果によって実際の削除範囲が変わるため静的に確定できない。"
                    f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。",
                )
            )
            continue
        normalized = normalize_candidate(t)
        if not unresolved and safe_delete_target(normalized):
            continue
        if GLOB_CHARS.search(t):
            decisions.append(
                (
                    "ask",
                    "rm-unresolvable",
                    designation,
                    f"再帰削除の対象（{designation}）がグロブで、影響範囲を静的に確定できない。"
                    f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。",
                )
            )
            continue
        if unresolved:
            # task0003 Design Part 2: this target reached `deny` because its
            # safe-root exception was suppressed by lost evidence (step 6),
            # not because its real text is actually outside every safe root
            # — that may or may not be true, and the old wording below
            # asserted it regardless. State the fact that IS true instead.
            message = (
                f"`rm -r` の対象（{designation}）は一部がコマンド置換によるもので、"
                f"実際の削除範囲を静的に確定できない。置換を展開した実パスを"
                f"コマンドに直接書いて撃ち直す。"
            )
        else:
            message = f"`rm -r` の対象（{designation}）はスクラッチ領域の外。{deletion_alternative(t)}"
        decisions.append(("deny", "rm-recursive", designation, message))
    return decisions


def strongest_rm_decision(decisions):
    """Pick the strongest decision across every (tier, rule, designation,
    message) tuple check_rm() returned — possibly pooled across several
    `rm` invocations in different segments of one compound command — and
    return (tier, rule, message) for main() to emit, or None when nothing
    was collected (D6). Every target that reached the winning tier is named,
    by its designation, in the combined reason text (task0001 FR4: the
    joined reason, like each individual one, contains no target-derived
    text — DESIGNATION is rm_target_designation()'s output for every winner
    except an `rm-root` one, which keeps its fixed RM_ROOT_SHAPE token
    verbatim, SPEC.md a2). Designations are already unique per
    (invocation, operand) pair, so no two winners collapse into one entry
    here — unlike the raw target strings before this task, which could
    repeat when the same literal text appeared at two positions. When more
    than one reason id shares the winning tier (`rm-root` alongside
    `rm-recursive`, both `deny`), `rm-root` is reported — the same priority a
    single target used to get from being checked first, before D6 separated
    evaluation from emission.
    """
    if not decisions:
        return None
    top_rank = max(DECISION_RANK[tier] for tier, _, _, _ in decisions)
    winners = [d for d in decisions if DECISION_RANK[d[0]] == top_rank]
    tier = winners[0][0]
    rule = next((r for _, r, _, _ in winners if r == "rm-root"), winners[0][1])
    if len(winners) == 1:
        return tier, rule, winners[0][3]
    names = []
    for _, _, designation, _ in winners:
        if designation not in names:
            names.append(designation)
    joined = "、".join(names)
    return (
        tier,
        rule,
        f"再帰削除の複数対象が同じ強さの判定に達した: {joined}。"
        f"それぞれ個別に安全な経路へ書き換えて撃ち直すと確認不要になる。",
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


# tar's own value-taking short flag for `-C`/`--directory` (FLAG_DEST_FLAGS).
# tar_extract_mode() stops scanning a short-option cluster at this character
# so a directory value attached to `-C` (`-Cxtra`) is never misread as the
# `-x` extract flag merely because the VALUE text starts with the letter x —
# mirrors flag_value_destinations()'s own cluster handling of `-C`.
_TAR_DIR_SHORT_FLAG = "C"


def tar_extract_mode(args):
    """Whether ARGS put a tar statement in extract mode (IMPLEMENTATION.md
    "tar extract-mode rule", task0002 FR6).

    True when ARGS contain any of: `-x`; `--extract`; `--get`; a single-dash
    short-option cluster containing `x` (e.g. `-xzf`); or, only as the FIRST
    argument after the command word and not itself starting with a dash, a
    word containing `x` (the traditional dashless form, e.g. `xzf`).

    A long option other than `--extract`/`--get` never indicates extract
    mode, even when its own name contains the letter x (`--exclude`) —
    ARGS is only ever tested against the exact long-option spellings above,
    never substring-matched. Scanning a short-option cluster stops at the
    `C` character (see _TAR_DIR_SHORT_FLAG): `-C`'s own value is the REST of
    that cluster, not further option letters, so a directory name starting
    with `x` there is never read as `-x`. A value that belongs to another
    option and arrives as its own token (the archive name after `-f`) is
    never scanned at all — only tokens starting with a single dash, or the
    statement's own first argument, are examined.

    Each tar statement is judged from its own ARGS only (D2); a caller
    passing one side of a pipeline gets that side's own answer.
    """
    for a in args:
        if a in ("-x", "--extract", "--get"):
            return True
        if a.startswith("-") and not a.startswith("--") and len(a) > 1:
            for c in a[1:]:
                if c == "x":
                    return True
                if c == _TAR_DIR_SHORT_FLAG:
                    break
    if args and not args[0].startswith("-") and "x" in args[0]:
        return True
    return False


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
    - the value of a command-specific destination flag: for `tar`, `-C`/
      `--directory` only when the statement is in extract mode (task0002
      FR6, tar_extract_mode() / IMPLEMENTATION.md "tar extract-mode rule");
      unconditionally for `unzip -d`, `curl -o`/`--output`, `wget -O`/
      `--output-document`

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

    # tar's -C/--directory value is a write target only in extract mode
    # (task0002 FR6); every other FLAG_DEST_FLAGS command's destination flag
    # is unconditional, as before.
    if word == "tar":
        if tar_extract_mode(args):
            targets = targets + flag_value_destinations(word, args)
    else:
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
    return re.sub(r"^//(?=[^/])", "/", normalized)


def check_self_modification(word, args, redirects, segment, lexed):
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

    Each candidate is also checked in its normalized form (`~`/`$HOME`/
    `${HOME}` expanded, `..` segments collapsed lexically) so equivalent
    spellings of a protected path are not missed.
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
    for target in candidates:
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


# A bare function-signature token: shlex's punctuation_chars fuses adjacent
# punctuation into one token, so `f()` arrives as two tokens (the name, then
# this) rather than three.
FUNC_SIGNATURE = "()"
IDENT = re.compile(r"^[A-Za-z_]\w*$")


def strip_grouping_prefix(toks):
    """Strip leading grouping-construct tokens so the statement's REAL head —
    the invocation nested one level in — is what matches_target_shape()
    judges (IMPLEMENTATION.md "Guard parity vocabulary" / task0004's D7
    grouping-construct list): a subshell's bare `(`, a brace group's bare
    `{`, or a function signature (`NAME` then the fused `()` then `{`) that
    defines and, in the same command, invokes its body.

    Repeated so nested combinations (a function defined inside a subshell,
    etc.) unwrap fully. Trailing closers (`)`, `}`) are left exactly where
    they are — every extraction this feeds (S1/S2/S3's operand search) takes
    the FIRST matching token from what follows, so a closer sitting after
    the real operand never changes the result, and stripping it here would
    only add code with no observable effect.

    Only ever feeds the deferral check in main(): it strips its own smaller
    grouping-construct vocabulary (no reserved words, no case patterns) from
    the UNSHAPED tokens statements() yields, so this function's own
    behaviour and the deferral verdicts it drives are unchanged by task0001.
    check_git()/check_rm()/the other destructive checks no longer keep
    calling head() on those unstripped tokens, though — since task0001,
    they read the SEPARATELY grouping/case-aware SHAPED tokens statements()
    also yields (see that function's docstring and _shape_leading()), so a
    subshell- or brace-wrapped destructive command IS now examined by those
    checks, unlike before this task.
    """
    toks = list(toks)
    changed = True
    while toks and changed:
        changed = False
        if toks[0] in ("(", "{"):
            toks = toks[1:]
            changed = True
        elif (
            len(toks) >= 3
            and IDENT.match(toks[0])
            and toks[1] == FUNC_SIGNATURE
            and toks[2] == "{"
        ):
            toks = toks[3:]
            changed = True
    return toks


def _seg_matches(seg, literal):
    """Whether a branch-name path segment matches LITERAL exactly, or is
    dynamic (see DYNAMIC above) — used by matches_target_shape()'s S2 branch
    segment check.
    """
    return seg == literal or bool(DYNAMIC.search(seg))


def matches_target_shape(word, args, cwd):
    """Whether (WORD, ARGS) is a real invocation of failed-run-cleanup-guard's
    target shapes S1/S2/S3 (IMPLEMENTATION.md "Target invocation shapes
    (S1/S2/S3)", decision D2): a `git worktree remove`, a `git branch`
    deletion carrying a non-force flag (`-d`/`--delete`), or a `gh pr
    create`. That other hook owns the verdict for these; this hook's own
    checks below still run against them, but its trailing blanket `allow`
    must be withheld or it would override the other hook's deny — the same
    reason KILL_WORDS above is excluded from that allow.

    WORD/ARGS are already the product of head()/split_redirects() over one
    lexed statement from statements(), the same quote-aware decomposition
    check_git()/check_external() judge on — never a raw substring scan of
    the command text. A mention inside quotes, a here-doc body not aimed at
    a shell sink, or a commit message never surfaces as a `git`/`gh`
    invocation of its own, so it is not matched here either, exactly as the
    other hook's own classifier stays silent for those same mentions.

    The caller (main()) passes WORD/ARGS already unwrapped by
    strip_grouping_prefix(): a statement whose real head sits one level
    inside a subshell, a brace group, or a function signature defined and
    invoked in the same command is matched on that real head, not on the
    grouping token — matching the new guard's own recursion into those same
    constructs (D7's grouping-construct vocabulary).

    S1 does not exclude the `--force` spelling: a forced worktree removal is
    already denied outright by check_git() before main()'s loop can reach
    the trailing allow, so the distinction has no observable effect, and
    S1's own definition draws none either. S2 DOES exclude `-D`/`--force`,
    matching its definition exactly — harmless for the same reason (also
    denied earlier), but this keeps the shape match an honest statement of
    S2 as specified rather than relying on that other rule firing first.

    Narrowed to only the shapes failed-run-cleanup-guard.py can actually
    judge, so unrelated worktree removals / branch deletions do not lose
    their blanket allow and fall through to the auto mode classifier every
    time. A trailing dynamic token (`$`, backtick, `${`, a variable-name
    sigil, `*`, `?`, `[`) is treated as matching, since its resolved value
    is unknown here and the other hook is the one that judges it at run
    time — the same unresolvable-marker character set failed-run-cleanup-
    guard.py's own DYNAMIC regex uses, bracket-glob spelling included (D7).
    S1: only when the operand's last path segment (after stripping a
    trailing `/`) is literally `integration`, or is dynamic.
    S2: only when the branch name's first segment is `em-workflow` (or
    dynamic) AND its last segment is `integration` (or dynamic).
    S3: only when CWD's path segments contain the consecutive run
    `.claude/worktrees/em-workflow/<feature>/integration`, matching the
    window failed-run-cleanup-guard.py's own resolve_pr_create() judges.

    When the operand/branch-name token is missing entirely (S1's `rest[1:]`
    or S2's filtered `rest` has nothing left), that is treated as matching
    too, not as out of scope: a real `git worktree remove`/`git branch -d`
    is never genuinely pathless, so an empty tail here only happens when
    statements()'s command-substitution hoisting already lifted the whole
    operand out of this statement's own token list before this function
    ever saw it (its body is re-scanned separately, as its own statement).
    Treating the gap itself as unresolved mirrors the trailing-dynamic-token
    rule above rather than adding a new one.
    """

    if word == "git":
        sub, rest = git_subcommand(args)
        if sub == "worktree" and rest[:1] == ["remove"]:
            operand = next((a for a in rest[1:] if not a.startswith("-")), None)
            if operand is None:
                return True
            last = operand.rstrip("/").rsplit("/", 1)[-1]
            return last == "integration" or bool(DYNAMIC.search(operand))
        if sub == "branch":
            expanded_rest = _expand_short_clusters(rest)
            if has(expanded_rest, "-d", "--delete") and not (
                has(expanded_rest, "-D") or has(expanded_rest, "--force")
            ):
                operands = [a for a in rest if not a.startswith("-")]
                if not operands:
                    return True
                for name in operands:
                    if DYNAMIC.search(name):
                        return True
                    parts = name.split("/")
                    if len(parts) == 3 and _seg_matches(
                        parts[0], "em-workflow"
                    ) and _seg_matches(parts[-1], "integration"):
                        return True
        return False
    if word == "gh":
        # `-R`/`--repo` take a value token of their own (`gh -R owner/repo pr
        # create`); without skipping it, the repo spelling is mistaken for
        # the first positional and `pr create` is missed.
        # This positional-argument extraction mirrors the one in
        # failed-run-cleanup-guard.py's own classify() (its `gh pr create`
        # detection, S3) — keep both in sync.
        positional = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a in ("-R", "--repo"):
                skip_next = True
                continue
            if a.startswith("--repo="):
                continue
            if a.startswith("-"):
                continue
            positional.append(a)
        if positional[:2] != ["pr", "create"]:
            return False
        segs = [s for s in cwd.split("/") if s]
        window = [".claude", "worktrees", "em-workflow"]
        for i in range(len(segs) - 4):
            if (
                segs[i : i + 3] == window
                and segs[i + 4] == "integration"
            ):
                return True
        return False
    return False


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
    cwd = payload.get("cwd") or ""

    # Whether kill-guard.py owns the verdict for this command. The destructive
    # checks below still run — a compound such as
    # `pkill -f x; rm -rf /home/sakura/y` must still be denied for its `rm`
    # half — but the blanket `allow` at the end is withheld, so kill-guard's
    # own deny/ask is never overridden. See KILL_WORDS above.
    defer_to_kill_guard = any(
        re.search(rf"(^|[^\w./-]){w}([^\w./-]|$)", command) for w in KILL_WORDS
    )

    # Whether failed-run-cleanup-guard.py owns the verdict for this command
    # (decision D2). Unlike defer_to_kill_guard above, this is NOT a raw
    # substring scan of COMMAND — the D2 narrowness requirement means a
    # mention inside quotes or a here-doc body must keep its blanket allow,
    # so this is set from matches_target_shape() inside the loop below, over
    # each statement's already quote-resolved WORD/ARGS. See
    # matches_target_shape() for the full rationale.
    defer_to_new_guard = False

    # Judged on the whole command string, not per segment: `statements()`
    # splits on `|`, so a `curl … | sh` pipeline is never one unit inside the
    # loop below and the check would never fire.
    check_pipe_to_shell(command)

    # Every rm target of every segment, pooled across possibly several `rm`
    # invocations in one compound command (D6). check_rm() no longer decides
    # for itself — an `ask` on an early target must not end the scan before a
    # later target, or a later segment's own `rm`, gets to contribute a
    # `deny` — so this loop only collects, and the strongest decision found
    # is emitted once, after every segment has been examined.
    rm_decisions = []

    # task0001 FR4: hands out a fresh, 1-based ordinal each time an `rm`
    # invocation is actually about to be analysed — direct spelling or
    # substitution-headed — so rm_target_designation() can name which
    # invocation a target belongs to. A mutable single-element list stands
    # in for a nonlocal int (no counter object needed): both call sites
    # below increment it exactly once per real `rm` invocation, in the same
    # left-to-right order statements() yields segments, so the same command
    # text always drives the same sequence of calls and the same ordinals
    # (NFR2).
    _rm_invocation_seq = [0]

    def next_rm_invocation():
        _rm_invocation_seq[0] += 1
        return _rm_invocation_seq[0]

    for segment, toks, lexed, shaped_words, shaped_redirects in statements(command):
        check_bypass(segment, toks)

        # task0001 D1: every check below reads SHAPED_WORDS/SHAPED_REDIRECTS
        # — statements()'s grouping/case-aware unwrap of TOKS (see that
        # function's docstring and _shape_leading()) — so a command sitting
        # behind a subshell, a brace group, a reserved word, a case pattern,
        # or a function definition is judged exactly as the same command
        # written alone. The deferral computation below deliberately keeps
        # using the UNSHAPED words instead; see its own comment.
        word, args = head(shaped_words)
        # `> ~/.claude/settings.json` のようにコマンド語を持たない純リダイレクト
        # 文も対象を切り詰める。word が無くても redirects だけで判定する。
        check_self_modification(word or "", args, shaped_redirects, segment, lexed)

        # task0001 FR1/FR2/FR3 (AS-2), rebuilt by task0002 FR1/FR2/FR3/FR11/
        # FR13: a statement whose command word is a `.substitution_only`
        # token — skipped by head() above to reach WORD/ARGS — has a
        # command name that is statically unknown. WORD/ARGS themselves are
        # untouched by this classification — a statement whose command word
        # was found directly (no substitution skip at all) never reaches
        # route_substitution_headed_statement(), leaving the WORD == "git" /
        # "rm" dispatch below, and every substitution-free command's
        # verdict, unchanged (AC-12). The single entry point below reads a
        # command name statically out of the skipped substitution's own raw
        # text and hands the remaining tokens to the EXISTING rm/git shape
        # matchers on that evidence alone — never on the remainder's flag
        # shape (D2, superseding task0001's dash pre-gate and recursion-AND-
        # force-AND-operand pre-screen, both removed) — reusing the
        # matchers' own verdict tier and reason id verbatim (R5: no new
        # stage, no new reason id, no verdict produced by the
        # classification itself).
        skip_index, saw_substitution, substitution_tok = _skip_to_command_word(
            shaped_words
        )
        if saw_substitution:
            rm_decisions.extend(
                route_substitution_headed_statement(
                    shaped_words[skip_index:],
                    getattr(substitution_tok, "raw_substitution_body", None),
                    segment,
                    next_rm_invocation,
                )
            )

        # The deferral is judged on the statement's REAL head — leading
        # grouping tokens (subshell `(`, brace group `{`, a function
        # signature) stripped first (D7) — over the UNSHAPED words TOKS
        # itself produces (task0001: deliberately not SHAPED_WORDS above;
        # the deferral's own, narrower grouping-construct vocabulary —
        # strip_grouping_prefix(), unchanged by this task — and its pinned
        # verdicts stay exactly as they were; see that function's
        # docstring). A subshell's `(` is itself WORD when ungrouped
        # ("(" != "git"), so this must run even when WORD is None or not
        # "git"/"gh"; it is placed before the `continue` below for that
        # reason.
        words, _ = split_redirects(toks, lexed)
        gword, gargs = _deferral_head(strip_grouping_prefix(words))
        if matches_target_shape(gword, gargs, cwd):
            defer_to_new_guard = True

        if word is None:
            continue

        if word == "git":
            check_git(args, segment)
        elif word == "rm":
            rm_decisions.extend(check_rm(args, next_rm_invocation()))
        else:
            check_file_destruction(word, args, segment)
            check_external(word, args, segment)
            check_permissions(word, args)

    # Emission happens once, after every segment's rm targets have been
    # collected (D6) — an earlier deny from check_git()/check_file_
    # destruction()/etc. already exited the process before this line, so
    # reaching it means no OTHER check decided first.
    top = strongest_rm_decision(rm_decisions)
    if top is not None:
        tier, rule, message = top
        decide(tier, rule, message)

    if ALLOW_NON_DESTRUCTIVE and not defer_to_kill_guard and not defer_to_new_guard:
        decide("allow", None, "破壊的なパターンに一致しない。")
    sys.exit(0)


if __name__ == "__main__":
    main()

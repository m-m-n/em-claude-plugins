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
import collections
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
# comment (`# $(cmd)`, blanked out of the view shlex reads and so never
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


class _Decided(BaseException):
    """decide() raises this, carrying the output it would have printed, while
    _judge_under() judges a command under one lexer reading (P14). A
    BaseException, so that no handler of the verdict logic can swallow it, as
    none can swallow the SystemExit it stands in for."""

    def __init__(self, output):
        super().__init__()
        self.output = output


# True while _judge_under() runs: decide() hands its decision over instead of
# printing it.
_capture_decisions = False


def decide(decision, rule, reason):
    """Emit a PreToolUse permission decision and stop."""
    if decision == "ask" and unattended():
        decision = "deny"
        reason = (
            f"{reason}\n"
            f"無人実行（claude-batch）のため確認を取れないので、`ask` を `deny` に降格した。"
            f"対象を静的に確定できる形に書き換えて続行する。"
        )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": (
                f"[destructive-guard] {reason}"
                if rule is None
                else f"[destructive-guard/{rule}] {reason}"
            ),
        }
    }
    if _capture_decisions:
        raise _Decided(output)
    json.dump(output, sys.stdout)
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
        self.last_end = 0
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
        token = super().read_token()
        # How many characters of the input the lexer has taken in once this
        # token is complete -- the token's own end, or one past it when the
        # character that ended the token (whitespace, or the next character,
        # pushed back for the following token) was read as well.
        # _lex_layout() turns this into offsets; nothing else reads it.
        self.last_end = self.instream.tell()
        return token


# --- Unified lexer (destructive-guard-unified-lexer, FR1-FR9) ---------------
#
# lex_shell() is the ONE place in this file that decides where a quote, a
# comment, a parameter / arithmetic expansion, a command / backtick / process
# substitution, a here-string operator and a real here-document operator
# begin and end. strip_heredocs(), scan_structure(), the text _TrackingLexer
# reads and tokens() all take those judgments from its map; none of them
# classifies a character on its own. See IMPLEMENTATION.md ("Unified lexer
# contract", postconditions P1-P12).
#
# Rework round 1 (task0002) -- three readings the lexer takes the way bash
# does, so a destructive statement after them is never dropped as a heredoc
# body or a comment (review findings 42180fe3cd060309, 6ad3de37b64392ec,
# acf9e8aa8bb287ea):
#
#   P10 (FR3)  a reserved word is recognized directly after a closer (the `)`
#              of a subshell group, the `}` of a brace group, the `))` of an
#              arithmetic command, the `]]` of a conditional command, and
#              `fi` / `done` / `esac`), and a recognized one sets command
#              position exactly as at a command position; the `do` after
#              `for NAME` / `select NAME` is one too; the position after
#              `coproc NAME`, `function NAME` and `function NAME ()` is a
#              command position. Grammar state: _LexFrame.rw, .kw, .cond.
#   P11 (FR8)  a pending heredoc body begins after the first newline read
#              while no region opened after its operator is still open; a
#              backslash-newline never begins one. Each operator remembers
#              the region sequence number it was registered at.
#   P12 (FR6)  a process substitution stays part of its word: after its
#              closing `)` the word continues, so a `#` right after it is no
#              comment.
#
# destructive-guard-heredoc-syntax-error adds one more reading:
#
#   P13        a `<<` written directly inside an array compound assignment
#              (`x=( <<EOF`) is a syntax error in bash, which drops that
#              physical line and runs the next one. It is no operator here,
#              and the line it is on takes no body (_lex_pass(), "Discarded
#              line"); the lines after it are command lines. Grammar state:
#              _LexFrame.asg, .decl, .arr_end and the frame kind `array`.
#   P14        the array contexts P13 knows are completed, and what a valid
#              array holds no longer discards the line: `eval`, `let` and
#              `alias` take assignment arguments like the declaration
#              builtins; a `NAME[` word at an assignment position, and a word
#              inside an array that starts with `[`, have their subscript read
#              to the matching `]` the way bash does (the frame kind
#              `subscript`; blanks, `<<` and the other operator characters are
#              part of it, and a `]` that never comes is LexUnmatchedSubscript);
#              an extended-glob parenthesis directly inside an array is read
#              under a lexer reading (lex_shell()'s EXTGLOB): with extglob on it
#              is a pattern group (the frame kind `extglob`), with it off it is
#              the syntax error P13 discards the line for. The hook cannot know
#              which one bash will take, so run() judges the command under both
#              readings -- when the lexer met such a parenthesis -- and keeps
#              the stricter verdict.
#
# Round 2 residuals (destructive-guard-lexer-round2-residuals, task0002,
# FR3; review finding 9381769d7116fab2, first half) meets P14.
#
#   Array subscript (FR3)  the subscript P14 reads to its matching `]` is an
#              `array-subscript` region: it is masked from shlex and no `<<`
#              operator, comment or command position opens inside it. In the
#              arguments of a declaration builtin bash reads the word with the
#              ordinary word rules, so there the subscript ends the word at an
#              unquoted blank or metacharacter (a `bound` subscript frame,
#              without a region): `declare a[1<<2]=x` registers the `<<` as
#              bash does, and `declare -a x[0]=(` still opens an array.
#
# Rework round 1 (destructive-guard-lexer-round2-residuals, task0005, FR4;
# review findings 1baa909f9b288847 and 19edf404b5cbeb2b).
#
#   Unreadable delimiter word (FR4)  a `<<` whose delimiter word cannot be read
#              (_read_heredoc_delimiter()) registers no operator and is a tail
#              source: from it on no comment, no quote region (`'`, `"`, `$'`,
#              `$"`) and no further `<<` operator is opened, so every line
#              after it stays subject to inspection. The quote characters left
#              literal are reported in the map's UNOPENED (the masked view
#              hides them from shlex) and the map's TAIL_START is the earlier
#              of this `<<` and the settle channel's. The pass state is
#              _LexPassState.tail_source / .tail_start, restored by a resume.
#   Close line (FR4)  a line ends a body only where bash 5.3 ends it: under
#              `<<` it equals the delimiter value (its line end removed),
#              under `<<-` it does once its leading tabs are removed.
#              _LexLines.close_lines() is that index, one pass per kind.
#
# Round 2 deferred (destructive-guard-lexer-round2-deferred, task0001, FR2 and
# FR8; review finding 52bfa0f59d1ea852 and the tail-gate part of
# c8c16caba82d6238).
#
#   Tail gate (FR8)  every question the pass asks about its tail -- may this
#              opener open here -- is answered by one function of the pass,
#              tail_gate(), for an opener kind and its offset. A tail-start
#              opener (a comment, a here-document operator, a subscript, an
#              array's discarded-line trigger) is refused from the tail start
#              on; a tail-source opener (a quote, `$'`, `$"`, the parameter
#              form of `${`, `$((`, `$[`, a `((` at a command position, a case
#              construct) once a `<<` whose delimiter word cannot be read has
#              been met. `$(`, a backtick, a process substitution and the
#              command form of `${` are never asked about. The tail start's own
#              bookkeeping is not a question and stays out of the gate.
#   After a tail source (FR2)  no parameter-form `${`, `$((`, `$[` or `((` at
#              a command position opens: the characters stay literal text, the
#              offset is listed in UNOPENED, and reading goes on after them as
#              after a settled opener. A `case` word opens no case construct --
#              in the pass, and in statement shaping for a statement that begins
#              at or after the chunk's tail start (_shape_leading()'s TAIL): it
#              is the statement's command word.
#
# Work bound (P7, D4). A pass reads the text once, left to right, with an
# explicit stack (no recursion). An opener that never closes cannot be known
# to be one until the end of the text, so the text is read again with every
# such opener settled as "not opened". Every opener settled this way is
# remembered, so a pass never rescans because of an opener it has already
# settled, and all unclosed openers found by one pass are settled together --
# `${` repeated twenty thousand times costs two passes, not twenty thousand.
#
# A `((` / `$((` whose first close is not an adjacent `))` is read as two
# parentheses (review round 2, finding 29bbf9032dd762a0), and that is found out
# only at its close. The pass does not start over for it: nothing before the
# opener, and no frame below it, changes while it is open, so the pass takes a
# _LexResumeSnapshot of its state (a _LexPassState) when it pushes the opener,
# restores it at the close and resumes at the opener, now read as two
# parentheses. The openers it reads that way are part of what the pass
# returns; the set it was given is not changed.
# That is the very reading a whole-text restart with the opener added gives,
# for the cost of the opener's span alone (read as arithmetic, then as two
# parentheses): any number of openers one after another, or inside one span,
# cost a constant number of reads of their spans. Only a chain of openers each
# nested in the next, every one closing without an adjacent `))`, reads the
# inner spans once more per level of the chain. The total number of loop
# iterations over all passes and re-reads is counted; past
# LEX_WORK_FACTOR times the text length (plus a floor) the lexer raises
# LexBudgetExceeded and the hook issues its scan-budget "ask" decision, never
# an "allow".

LEX_WORK_FACTOR = 8
_LEX_WORK_FLOOR = 1024


class LexBudgetExceeded(Exception):
    """lex_shell() could not settle a text within its linear work bound.
    run() turns it into the existing scan-budget "ask" decision
    (destructive-guard-unified-lexer D4, NFR3)."""


class LexUnmatchedSubscript(LexBudgetExceeded):
    """lex_shell() met an array subscript whose matching `]` is not found
    before the end of the text (P14). bash keeps reading for the `]` across
    lines, so the line boundaries the lexer would hand the later stages cannot
    be placed. It is a LexBudgetExceeded -- the text cannot be settled -- that
    the hook answers with its own `ask` (ask_unmatched_subscript()), never an
    `allow`."""


LexRegion = collections.namedtuple(
    "LexRegion", ["kind", "start", "end", "parent", "closed"]
)
LexHeredoc = collections.namedtuple(
    "LexHeredoc",
    ["start", "end", "delimiter", "quoted", "body_start", "body_end", "close_end"],
)
LexCandidate = collections.namedtuple(
    "LexCandidate", ["quote", "start", "end", "enclosing"]
)

LEX_SUBSTITUTION_KINDS = frozenset(
    {"command-substitution", "backtick-substitution", "process-substitution"}
)
LEX_QUOTE_KINDS = frozenset(
    {"single-quote", "double-quote", "ansi-c-quote", "locale-quote"}
)
# The two region kinds of a discarded line (destructive-guard-heredoc-syntax-
# error): a direct-position `<<` in an array compound assignment makes bash
# drop the rest of that physical line and read the next one as a fresh command
# line (see _lex_pass(), "Discarded line"). What the map keeps of the dropped
# line is read as ordinary commands, except what shlex would read across the
# line end, which is hidden from it as the two kinds below say; both are in
# LEX_MASKED_KINDS and cover nothing but the hidden characters:
#   discarded-quote         the opening quote character (`"`, `'`, or `$"`) of
#                           a quote still open at the line end -- the quote is
#                           no region any more, and the text after the opener
#                           stays command text;
#   discarded-continuation  a backslash that ends the line, which is no line
#                           continuation for shlex either.
LEX_DISCARDED_QUOTE = "discarded-quote"
LEX_DISCARDED_CONTINUATION = "discarded-continuation"
# Regions that are inert for statement-separator counting at the top level.
LEX_OPAQUE_KINDS = LEX_QUOTE_KINDS | LEX_SUBSTITUTION_KINDS | frozenset(
    {
        "comment",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
        "array-subscript",
    }
)
# Regions whose content shlex would read differently from bash: the masked
# view hides every character inside one of these (comments are blanked).
LEX_MASKED_KINDS = frozenset(
    {
        "ansi-c-quote",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
        "array-subscript",
        LEX_DISCARDED_QUOTE,
        LEX_DISCARDED_CONTINUATION,
    }
)


class LexMap:
    """The lexical map lex_shell() returns (IMPLEMENTATION.md, "Output").

    - REGIONS: LexRegion(kind, start, end, parent, closed) in order of start;
      END is exclusive, PARENT the index of the immediately enclosing region
      (None at the top level), CLOSED False for a quote or substitution that
      runs to the end of the text unterminated -- or to the end of a
      discarded line (P13), where an open quote is only a `discarded-quote`
      region over its opening character, and a backslash that ends the line a
      `discarded-continuation` region (both hidden from shlex).
    - HEREDOCS: LexHeredoc for every real here-document operator in text
      order: START/END span the `<<` / `<<-` through its delimiter word;
      DELIMITER is that word with its quotes removed (_read_heredoc_delimiter())
      and QUOTED whether it held a quote character (`'`, `"` or `\\`);
      BODY_START/BODY_END the body lines and CLOSE_END the end of the
      delimiter line (all None when the delimiter line never appears, when
      the operator sits on a discarded line (P13), or when the map was made
      without body skipping). An operator whose delimiter word cannot be read
      is not reported at all and takes no body; it is a tail source instead
      (TAIL_START, and no quote region opens from it on).
    - CANDIDATES: LexCandidate(quote, start, end, enclosing) -- P8: the
      substitutions the broad search reads inside the single-quote or
      ansi-c-quote region with index QUOTE; ENCLOSING is the index of the
      substitution region around that quote, or None.
    - UNOPENED: offsets of the openers settled as not opened (P4), of the
      `'` / `"` characters a tail source leaves literal (no quote region opens
      from a `<<` whose delimiter word cannot be read on), and of the
      expansion openers the tail gate refuses after one (the parameter form of
      `${`, `$((`, `$[`, a `((` at a command position; round 2 deferred,
      task0001); TAIL_START the earliest settled opener or such a `<<` (the
      re-read tail starts there), None without either.
    - WORK / ROUNDS: loop iterations and passes it cost (P7)."""

    __slots__ = (
        "regions", "heredocs", "candidates", "unopened", "tail_start", "work",
        "rounds", "ext_lines",
    )

    def __init__(self, regions, heredocs, candidates, unopened, tail_start, work, rounds):
        # EXT_LINES: ((line start, text of that line before its first
        # extended-glob parenthesis inside an array), ...) -- the lines on
        # which the lexer met one (P14); run() counts them.
        self.ext_lines = ()
        self.regions = regions
        self.heredocs = heredocs
        self.candidates = candidates
        self.unopened = unopened
        self.tail_start = tail_start
        self.work = work
        self.rounds = rounds

    def as_tuple(self):
        return (
            tuple(self.regions), tuple(self.heredocs), tuple(self.candidates),
            tuple(self.unopened), self.tail_start, self.work, self.rounds,
        )


class _LexFrame:
    """One open context on the lexer's stack. KIND is `top`, `btop` (the
    literal top level of a heredoc body), `cmdsub`, `backtick`, `procsub`,
    `group` (shell rules); `dq`, `locale`, `sq`, `ansi`, `param`, `arith`,
    `bracket`. REGION is the region the frame owns and REG the region a child
    of this frame hangs under. The grammar state of the shell-rule kinds is
    CMD (the next word is at a command position), RW (P10: the next word
    comes directly after a closer or a `for` / `select` name, so a reserved
    word is recognized there although it is not a command position), CS (the
    case-construct stack), COND (a `[[` opened at a command position awaits
    its `]]`) and the little markers TIME_P (0; 1 directly after `time`, where
    `-p` and `--` are options; 2 directly after `time -p`, where only `--`
    is), KW (the keyword the previous
    word was: `for`, `select` or `coproc`), function-name and function-head
    tracking. ASG (every word since the command position was an assignment
    word, so the next one is still in assignment position), DECL (the command
    word was a declaration builtin, so its words are in declaration-argument
    position) and ARR_END (the offset of the `(` that would open an array
    compound assignment: the end of the `NAME=` / `NAME+=` word just read in
    one of those positions) are the grammar state that tells an array
    compound assignment's `(` from every other parenthesis. RD_CMD says a
    redirection was read at the command position of the simple command being
    read: bash 5.3 recognizes no reserved word after it (`>/dev/null time`
    runs a command named `time`), though it still takes assignment words.
    NOSUB says a redirection was read after an assignment word: bash takes no
    more assignment words then, so a `NAME[` word opens no subscript (its
    `<<` is an operator); the array compound assignment of P13 is still read
    there, which only keeps more lines inspected. The kind `array`
    is the array context (shell rules, but its words are elements, never
    commands): it opens at that `(` and closes at its matching `)`. SUB_AT
    (the offset of the `[` of a `NAME[` word at an assignment position, which
    opens a subscript right after the word's first run, or when the pass
    reaches it past the line continuations the name holds), and the kinds
    `subscript` (a bracketed subscript read to its matching `]`; NAMED says it
    follows `NAME`, so the `=(` after it can open an array) owns an
    `array-subscript` region, unless it is BOUND: a subscript in an argument
    of a declaration builtin, read with the word rules bash applies there --
    an unquoted blank or metacharacter ends it with the word -- and without a
    region. `extglob` (the pattern group of an extended-glob parenthesis
    inside an array, read to its matching `)`) is a frame without a region of
    its own, as `array` is; regions opened inside it hang under REG."""

    __slots__ = (
        "kind", "start", "region", "reg", "cmd", "cs", "in_word", "depth",
        "prev_plain", "time_p", "kw", "fn_p", "rw", "cond", "asg", "decl",
        "arr_end", "redir", "rd_cmd", "nosub", "sub_at", "sub_bound", "named", "bound", "snap",
    )

    def __init__(self, kind, start, region, reg, cmd=False, depth=0):
        self.kind = kind
        self.start = start
        self.region = region
        self.reg = reg
        self.cmd = cmd
        self.cs = []
        self.in_word = False
        self.depth = depth
        self.prev_plain = False
        self.time_p = False
        self.kw = ""
        self.fn_p = False
        self.rw = False
        self.cond = False
        self.asg = False
        self.decl = False
        self.arr_end = -1
        self.redir = False
        self.rd_cmd = False
        self.nosub = False
        self.sub_at = -1
        self.sub_bound = False
        self.named = False
        self.bound = False
        # An `arith` frame: a _LexResumeSnapshot of what the pass held when
        # the frame was pushed, to resume from there when its first close is
        # not an adjacent `))`.
        self.snap = None


class _LexLines:
    """Line index of a text for here-document body lookup: START offsets of
    every line (str.splitlines() rules, as strip_heredocs() always used) and,
    built on first use of each kind, the close-line index (NFR3):
    close_lines(DASH) maps a delimiter value to the lines that close a body
    with it, one pass over the lines per kind. A line closes the body of a
    `<<` operator when the line, its line end removed, equals the delimiter
    value; of a `<<-` operator when it does once its leading tabs are removed
    too (bash 5.3). The key of a line is therefore the line itself (DASH
    false) or the line without its leading tabs (DASH true), so a value that
    holds blanks is looked up like any other."""

    __slots__ = ("text", "starts", "_close_lines")

    def __init__(self, text):
        starts = []
        total = 0
        for line in text.splitlines(keepends=True):
            starts.append(total)
            total += len(line)
        self.text = text
        self.starts = starts
        self._close_lines = [None, None]

    def close_lines(self, dash):
        """{key: [indexes of the lines with that key, in order]} for a `<<-`
        operator (DASH true) or a `<<` operator (DASH false)."""
        kind = 1 if dash else 0
        mapping = self._close_lines[kind]
        if mapping is None:
            mapping = {}
            starts = self.starts
            text = self.text
            last = len(starts) - 1
            for idx, s in enumerate(starts):
                e = starts[idx + 1] if idx < last else len(text)
                if e > s and text[e - 1] == "\n":
                    e -= 1
                key = text[s:e]
                if dash:
                    key = key.lstrip("\t")
                mapping.setdefault(key, []).append(idx)
            self._close_lines[kind] = mapping
        return mapping


_LEX_WS = re.compile(r"[ \t\r]+")
_LEX_WORD_RUN = re.compile(r"[^ \t\r\n;|&()<>\"'`$\\]+")
_LEX_DQ_SPECIAL = re.compile(r"[\\\"$`]")
_LEX_PARAM_SPECIAL = re.compile(r"[\\'\"$`}]")
_LEX_ARITH_SPECIAL = re.compile(r"[\\'\"$`()]")
_LEX_EXTGLOB_SPECIAL = re.compile(r"[\\'\"$`()<>]")
_LEX_BRACKET_SPECIAL = re.compile(r"[\\'\"$`\[\]]")
_LEX_SUBSCRIPT_SPECIAL = re.compile(r"[\\'\"$`\[\]<>]")
# A BOUND subscript (a declaration-builtin argument) ends with its word at an
# unquoted blank or metacharacter as well.
_LEX_SUBSCRIPT_BOUND_SPECIAL = re.compile(r"[\\'\"$`\[\] \t\r\n;|&()<>]")
# The line breaks str.splitlines() splits a text at -- the lines _LexLines
# indexes. A here-document delimiter word never spans one.
_LEX_LINE_BREAKS = frozenset("\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")
_LEX_LINE_BREAK = re.compile(r"[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")
_LEX_DELIM_BLANKS = re.compile(r"[ \t]*")
# A run of delimiter word characters read without a decision: everything but
# a metacharacter (blank, line break, `;|&()<>`) and the characters that open
# an escape, a quote, an expansion or a substitution.
_LEX_DELIM_RUN = re.compile(
    r"[^ \t\r\n\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029;|&()<>\\'\"`$]+"
)
# Inside double quotes: the characters that need a decision.
_LEX_DELIM_DQ_SPECIAL = re.compile(
    r"[\\\"$`\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]"
)
_LEX_ANSI_SPECIAL = re.compile(r"[\\']")
_LEX_BODY_SPECIAL = re.compile(r"[\\$`]")
_LEX_FUNCTION_HEAD = re.compile(r"\([ \t]*\)")
_LEX_CANDIDATE_OPEN = re.compile(r"\$\(|`")
_LEX_WORD_END = frozenset(" \t\r\n;|&()<>")
_LEX_SHELL_KINDS = frozenset(
    {"top", "cmdsub", "group", "procsub", "backtick", "array"}
)
# The start of an assignment word (`NAME=`, `NAME+=`); a word that is nothing
# more is the one a compound-assignment parenthesis follows.
_LEX_ASSIGN_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
# The start of a subscripted assignment word: `NAME[`. Its subscript is read to
# the matching `]` by a `subscript` frame, and the `=` or `+=` after that `]`
# makes the word an assignment word.
_LEX_SUBSCRIPTED_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\[")
# The two parts of that test when the name holds line continuations: a whole
# name, and the name characters that follow a continuation.
_LEX_NAME_ONLY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LEX_NAME_CHARS = re.compile(r"[A-Za-z0-9_]*")


def _lex_subscript_open(text, start, end, first):
    """The offset in TEXT of the `[` that opens the subscript of a `NAME[`
    word, or -1 when the word is no such word. FIRST is the plain run the word
    starts with, TEXT[START:END]; the word's leading characters are tested
    with every backslash-newline pair removed, as bash removes them before it
    reads the word (round 2 deferred, FR4), and the `[` is reported at its
    offset in TEXT, the pairs included. A run that is a whole name followed
    by a continuation is read on through the pairs and the name characters
    between them: every character is read once, so the work is proportional
    to the length of the name."""
    m = _LEX_SUBSCRIPTED_NAME.match(first)
    if m is not None:
        return start + m.end() - 1
    if not text.startswith("\\\n", end) or _LEX_NAME_ONLY.fullmatch(first) is None:
        return -1
    at = end
    while text.startswith("\\\n", at):
        at = _LEX_NAME_CHARS.match(text, at + 2).end()
    return at if at < len(text) and text[at] == "[" else -1
# The builtins bash parses assignment arguments for: after one of them a
# `NAME=(` word opens an array compound assignment. `eval` and `let` are
# assignment-argument builtins in the parser, `alias` is an assignment builtin.
_LEX_DECLARATION_BUILTINS = frozenset(
    {"declare", "typeset", "local", "export", "readonly", "eval", "let", "alias"}
)
# What an extended-glob parenthesis follows directly, inside one word.
_LEX_EXTGLOB_PREFIXES = "?*+@!"
# Case-construct states while a pattern is being read: PATTERN_FIRST right
# after `in`, PATTERN_NEXT right after a `;;` (where a bare `esac` always ends
# the construct, so `$(case x in x) :;; esac)` closes at its last `)`), and
# PATTERN_REST once the pattern's first word is past.
_LEX_CASE_PATTERN_STATES = ("pattern_first", "pattern_next", "pattern_rest")
# The tail gate (round 2 deferred, task0001, FR8): the one question the lexer
# pass asks about its tail -- may an opener of this kind, at this offset, open
# -- in the two classes its answer comes in. A TAIL-START opener is refused
# from the tail start on: the earliest settled opener, or the first `<<` whose
# delimiter word cannot be read. A TAIL-SOURCE opener is refused once a `<<`
# whose delimiter word cannot be read (a tail source) has been met. `$(`, a
# backtick, a process substitution and the command form `${ ` / `${|` are
# never asked about: they run their content as commands, so refusing one would
# turn commands bash runs into arguments of the command before it.
_LEX_TAIL_START_OPENERS = frozenset(
    {
        "comment",
        "heredoc-operator",
        "assignment-subscript",
        "array-subscript",
        "discarded-line",
    }
)
_LEX_TAIL_SOURCE_OPENERS = frozenset(
    {
        "single-quote",
        "double-quote",
        "ansi-c-quote",
        "locale-quote",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
        "case-construct",
    }
)
# Words after which the next word is still at a command position (P3).
_LEX_COMMAND_KEEPERS = frozenset(
    {"if", "then", "elif", "else", "do", "while", "until", "time", "coproc", "!", "{"}
)
# The reserved words recognized directly after a closer (P10). Each is
# handled afterwards exactly as at a command position. `{` is one of them for
# the group a `for ((...)) {` header opens; after any other closer it is read
# the same way, which can only remove a here-document operator, never add one.
_LEX_AFTER_CLOSER_WORDS = frozenset(
    {"then", "do", "else", "elif", "fi", "done", "esac", "}", "{"}
)
# After `coproc`, a word that begins a compound command is not the coprocess
# NAME; any other word is, and the position after it is a command position.
_LEX_COPROC_COMPOUND = frozenset(
    {"{", "if", "while", "until", "case", "for", "select", "function", "time",
     "!", "[[", "coproc"}
)
_LEX_SPECIAL_PARAMETERS = "$?#!-@*0123456789"

_LEX_CACHE = {}
_LEX_CACHE_LIMIT = 16


def _lex_quote_candidates(text, lo, hi, quote_index, enclosing, out):
    """P8: the candidate substitutions inside the quote content TEXT[LO:HI],
    appended to OUT as LexCandidate. Left to right: a `$(` closes at the `)`
    that balances its own `(` when every `(` and `)` up to HI counts alike,
    failing that at the first `)` after it, with none it is no candidate; a
    backtick closes at the next backtick before HI, with none it is no
    candidate; scanning resumes after a candidate's end. One forward pass
    for all the `$(` (_single_quoted_sub_closes()), one `find` per backtick
    that is either paired or the last one: linear in HI - LO."""
    closes = None
    p = lo
    while True:
        m = _LEX_CANDIDATE_OPEN.search(text, p, hi)
        if m is None:
            return
        j = m.start()
        if m.group() == "`":
            k = text.find("`", j + 1, hi)
            if k == -1:
                p = j + 1
                continue
            out.append(LexCandidate(quote_index, j, k + 1, enclosing))
            p = k + 1
        else:
            if closes is None:
                closes = _single_quoted_sub_closes(text, j, hi)
            c = closes.get(j, -1)
            if c == -1:
                p = j + 1
                continue
            out.append(LexCandidate(quote_index, j, c + 1, enclosing))
            p = c + 1


def _heredoc_word_start(text, i):
    """The offset at which the delimiter word of the `<<` / `<<-` at I
    begins: after the operator and the blanks (spaces and tabs) following it."""
    p = i + 2
    if text.startswith("-", p):
        p += 1
    return _LEX_DELIM_BLANKS.match(text, p).end()


def _read_heredoc_delimiter(text, i):
    """The delimiter word of the here-document operator at I (`<<` / `<<-`,
    never `<<<`), as (END, DELIMITER, QUOTED), or None when the word cannot be
    read -- then the `<<` is no operator and takes no body (NFR6, SPEC A3).

    The word runs from after the operator and its blanks to the next unquoted
    metacharacter (blank, line break, `;`, `|`, `&`, `(`, `)`, `<`, `>`);
    quoted segments and backslash escapes are part of it. DELIMITER is the
    word with its quotes removed (`END-X` -> `END-X`, `E\\X` -> `EX`, `E"X"` ->
    `EX`, `'E-X'` -> `E-X`, `\\EOF` -> `EOF`); a `$` that starts no expansion
    stays a character of it (`E$X` -> `E$X`: nothing is expanded). QUOTED is
    True exactly when the word holds a `'`, `"` or `\\`: the body is then
    literal. Inside double quotes a backslash removes itself only before
    `$`, a backtick, `"` and `\\`.

    Unreadable: no word before a metacharacter or the end of the text; a
    quote that does not close on the operator's line (nor does a backslash
    before a line break); a command substitution, a backtick, `${`, `$((`,
    `$[`, `$'` or `$"` in the word. The `<<` is then no operator and a tail
    source: _lex_pass() opens no comment, quote region or operator from it on,
    so every following line stays subject to inspection."""
    n = len(text)
    start = _heredoc_word_start(text, i)
    parts = []
    quoted = False
    q = start
    while q < n:
        m = _LEX_DELIM_RUN.match(text, q)
        if m is not None:
            parts.append(m.group())
            q = m.end()
            continue
        c = text[q]
        if c == "\\":
            nxt = text[q + 1 : q + 2]
            if nxt == "" or nxt in _LEX_LINE_BREAKS:
                return None
            parts.append(nxt)
            quoted = True
            q += 2
        elif c == "'":
            close = text.find("'", q + 1)
            if close == -1:
                return None
            if _LEX_LINE_BREAK.search(text, q + 1, close) is not None:
                return None
            parts.append(text[q + 1 : close])
            quoted = True
            q = close + 1
        elif c == '"':
            r = q + 1
            while True:
                m = _LEX_DELIM_DQ_SPECIAL.search(text, r)
                if m is None:
                    return None
                j = m.start()
                d = text[j]
                parts.append(text[r:j])
                if d == '"':
                    q = j + 1
                    break
                if d == "\\":
                    nxt = text[j + 1 : j + 2]
                    if nxt == "" or nxt in _LEX_LINE_BREAKS:
                        return None
                    parts.append(nxt if nxt in '$`"\\' else "\\" + nxt)
                    r = j + 2
                elif d == "$":
                    if text[j + 1 : j + 2] in ("(", "{", "["):
                        return None
                    parts.append("$")
                    r = j + 1
                else:
                    # A backtick, or a line break: the quote does not close
                    # on the operator's line.
                    return None
            quoted = True
        elif c == "$":
            if text[q + 1 : q + 2] in ("(", "{", "[", "'", '"'):
                return None
            parts.append("$")
            q += 1
        elif c == "`":
            return None
        else:
            break
    if q == start:
        return None
    return q, "".join(parts), quoted


class _LexPassState:
    """The state ONE pass of _lex_pass() builds up and moves as it reads. The
    pass keeps all of it in this one record, under these names, so the fields
    can be enumerated (`__slots__`) and every one of them is classified by
    _LexResumeSnapshot: restored by a resume, or named as not restored.

    Collections that grow: REGIONS (the lexical map under construction, one
    `[kind, start, end, parent, closed, nearest substitution ancestor]` list
    per region), CANDIDATES (single-quote substitution candidates), ENCOUNTERED
    (the settled openers the pass read as literal text), OPS (the here-document
    operators, each `[start, end, delimiter, quoted, body_start, body_end,
    close_end]`), STACK (the open contexts, bottom first), RSEQ (the sequence
    numbers of the regions open now), HD_PENDING (the operators waiting for a
    body, in registration order) and HD_SEQS (the region sequence number each
    pending operator was registered at). The pass holds each of these lists
    under its own name as well: they are only ever changed in place.

    Scalars: HD_TRIGGER (the offset of the line start at which the pending
    operators are looked at again, None without any), LIMIT (the offset no scan
    reads past: the trigger, or the end of the text), CONT_AT (the offset after
    the last backslash-newline continuation, -1 for none), SEQ (the last
    region sequence number given out), TAIL_START (the offset from which no
    comment, no `<<` operator and no array subscript is opened: the earliest
    settled opener, or the tail source below when that comes first, None for
    neither) and TAIL_SOURCE (the offset of the first `<<` whose delimiter word
    could not be read, None until one is met: from it on no quote region is
    opened either), DISCARD_END (the offset of the newline that ends the
    discarded line being read (P13), None outside one) and EXTGLOB_MET
    (whether an extended-glob parenthesis was met directly inside an array,
    P14). DISCARD_UNCLOSED (the openers of the expansions a discarded line
    left open, settled with the rest at the end of the pass) and EXT_LINES
    (`(line start, text of that line before the parenthesis)` for every such
    parenthesis met, in order) are collections that grow too.

    ITERATIONS counts the loop iterations of the pass, and REPAREN_FOUND the
    `((` / `$((` openers the pass found to close without an adjacent `))`.

    The scan position of the loop is not a field: it is the loop's own cursor,
    and a resume sets it to the opener's offset."""

    __slots__ = (
        "regions", "candidates", "encountered", "ops", "stack", "rseq",
        "hd_pending", "hd_seqs", "hd_trigger", "limit", "cont_at", "seq",
        "tail_start", "tail_source", "iterations", "reparen_found",
        "discard_end", "discard_unclosed", "extglob_met", "ext_lines",
    )

    def __init__(self, root, n):
        self.regions = []
        self.candidates = []
        self.encountered = []
        self.ops = []
        self.stack = [root]
        self.rseq = []
        self.hd_pending = []
        self.hd_seqs = []
        self.hd_trigger = None
        self.limit = n
        self.cont_at = -1
        self.seq = 0
        self.tail_start = None
        self.tail_source = None
        self.iterations = 0
        self.reparen_found = set()
        self.discard_end = None
        self.discard_unclosed = []
        self.extglob_met = False
        self.ext_lines = []


class _LexResumeSnapshot:
    """What the pass takes back when a `((` / `$((` opener, pushed as
    arithmetic, turns out to close without an adjacent `))` (see "Work bound"
    above): captured when the opener is pushed, restored at its first close.
    Capture and restore are the only code that reads these fields of a
    _LexPassState for a resume, and the three lists below are the only place
    that says which field is restored how -- a field of _LexPassState that is
    in none of them (or in two) fails the completeness test.

    COLLECTIONS are cut back, in place, each to the length it had when the
    snapshot was captured; every one has its own recorded length, so two
    collections never rest on the assumption that they grow together. The
    entries before that length are not changed while the opener is open: every
    operator pending at the opener stays pending (a region opened after it is
    open), and the frames below it are not touched. SCALARS are set back to
    their captured values. NOT_RESTORED are the fields a resume deliberately
    keeps as they are: ITERATIONS, because the work of reading a span twice is
    counted, and REPAREN_FOUND, because it is what the resume itself learned."""

    COLLECTIONS = (
        "regions", "candidates", "encountered", "ops", "stack", "rseq",
        "hd_pending", "hd_seqs", "discard_unclosed", "ext_lines",
    )
    SCALARS = (
        "hd_trigger", "limit", "cont_at", "seq", "tail_start", "tail_source",
        "discard_end", "extglob_met",
    )
    NOT_RESTORED = ("iterations", "reparen_found")

    __slots__ = ("_extents", "_values")

    def __init__(self, extents, values):
        self._extents = extents
        self._values = values

    @classmethod
    def capture(cls, state):
        return cls(
            tuple(len(getattr(state, name)) for name in cls.COLLECTIONS),
            tuple(getattr(state, name) for name in cls.SCALARS),
        )

    def restore(self, state):
        for name, extent in zip(self.COLLECTIONS, self._extents):
            del getattr(state, name)[extent:]
        for name, value in zip(self.SCALARS, self._values):
            setattr(state, name, value)


# What one pass returns: STATUS is "done" (the map parts are set) or "restart"
# (they are None: the pass ended to have the openers in SETTLE settled as not
# opened); REPAREN lists the openers the pass newly read as two parentheses;
# TAIL_SOURCE (a "done" pass) is the offset of the first `<<` whose delimiter
# word could not be read, None without one; AMBIGUOUS (a "done" pass) says an
# extended-glob parenthesis was met directly inside an array, so the other
# reading could differ (P14).
# The pass never changes the opener sets it was given; the caller adds SETTLE
# and REPAREN to them for the next pass.
_LexPassResult = collections.namedtuple(
    "_LexPassResult",
    [
        "status", "regions", "ops", "candidates", "encountered", "settle",
        "reparen", "iterations", "tail_source", "ambiguous",
    ],
)


def _lex_pass(
    text, mode, settled, reparen, lines, budget, extglob=False, whole_restart=False
):
    """ONE left-to-right pass of lex_shell(). SETTLED are the openers earlier
    passes settled as not opened (P4) and REPAREN the `((` / `$((` openers
    earlier passes found to close without an adjacent `))`, which are read as
    two parentheses; neither set is changed. LINES is the line index when
    here-document bodies are to be skipped (None otherwise); EXTGLOB is the
    reading of an extended-glob parenthesis inside an array (P14). Returns a
    _LexPassResult: status "done" with the map parts, or status "restart" when
    this pass learned of openers to settle (SETTLE); either way its REPAREN
    holds the openers this pass newly found to close without an adjacent `))`.
    Raises LexBudgetExceeded past BUDGET iterations and LexUnmatchedSubscript
    when a subscript's `]` never comes.

    An opener that closes without an adjacent `))` is added to the pass's own
    set of found openers and the pass resumes at it, read as two parentheses
    (see "Work bound" above, and _LexResumeSnapshot for what the resume takes
    back); it never ends the pass. WHOLE_RESTART turns that off for the
    reference reading the agreement test compares with: the pass then ends
    with status "restart" and that opener as its REPAREN at the first such
    close, and the caller reads the whole text again.

    The grammar state a shell-rule frame carries (CMD, RW, CS and the small
    markers on _LexFrame) is advanced one word at a time by word_transition():
    it is what decides, by P3 and P10, whether a bare `((` is arithmetic.

    Here-document bodies (P6, P11). A real operator is queued in HD_PENDING
    with the region sequence number it was registered at (HD_SEQS; every
    pushed region gets the next number, RSEQ holds the numbers of the regions
    open now). While operators are pending, HD_TRIGGER is the offset of the
    next line start and no scan reads past it (LIMIT). When the lexer arrives
    there, an operator takes its body from that line on exactly when no
    region opened after it is still open -- the topmost open region's number
    is not above its own -- and the newline just read was no backslash-newline
    line continuation; otherwise the operator stays pending and the next line
    start becomes the trigger. A region that encloses the operator was open
    when it registered and so never defers it.

    Discarded line (P13). A `<<` / `<<-` whose innermost open context is an
    array compound assignment (kind `array`: the `(` of `NAME=(` / `NAME+=(`
    at an assignment position, or of the same word as an argument of
    `declare` / `typeset` / `local` / `export` / `readonly`) is a syntax
    error in bash. Bash drops the rest of that physical line and reads the
    next line as a fresh command line, so the `<<` is no operator and the
    line it is on -- through the first newline after it, whatever a quote,
    substitution, comment or backslash-newline opened on it would do -- is
    DISCARDED (DISCARD_END is that newline's offset): no operator on it takes
    a body (the ones registered before the `<<` stay in the map without one --
    the pending record is emptied, never re-read -- and the later ones are not
    registered at all), and at the newline every open context is cleared by
    end_discard() -- a quote or substitution still open there ends at the
    newline with CLOSED False, an open expansion that has no such end is
    settled as not opened like an unterminated one at the end of the text --
    and the next line is read at the top level, command position. A `<<` in a
    context nested in the array (a substitution, a quote) is not at that
    position and is read as before.

    Subscripts and extended-glob parentheses (P14). A word at an assignment
    position that starts with `NAME[`, and a word inside an array that starts
    with `[`, have the bracketed part read to the matching `]` the way bash
    reads it (a `subscript` frame: quotes, `$(`, `${`, `$((`, backquotes and
    nested brackets are matched; blanks, `<<` and the other operator
    characters are part of the subscript, and a `<<` in it is never an
    operator and never starts a discarded line). The `=(` / `+=(` after the
    `]` of a `NAME[...]` word opens an array like `NAME=(` does. A `(` directly
    after one of `?*+@!` inside one word of an array is an extended-glob
    parenthesis: with EXTGLOB true it is a pattern group (an `extglob` frame,
    read to its matching `)`), with it false it is the syntax error a bare `(`
    is. A subscript still open at the end of the text raises
    LexUnmatchedSubscript."""
    n = len(text)
    state = _LexPassState(
        _LexFrame("btop" if mode == "heredoc-body" else "top", 0, None, None, True), n
    )
    # From this offset on no comment, no `<<` operator and no array subscript
    # is opened: the earliest settled opener, until a `<<` whose delimiter word
    # cannot be read is met (a tail source, which moves it to its own offset).
    state.tail_start = min(settled) if settled else None
    # The collections of the state, held under their own names (a resume cuts
    # them back in place, never rebinds them).
    regions = state.regions
    ops = state.ops
    candidates = state.candidates
    encountered = state.encountered
    stack = state.stack
    rseq = state.rseq
    hd_pending = state.hd_pending
    hd_seqs = state.hd_seqs
    discard_unclosed = state.discard_unclosed
    new_reparen = state.reparen_found
    i = 0

    def as_two_parentheses(opener):
        return opener in reparen or opener in new_reparen

    def ending(settle):
        return _LexPassResult(
            "restart", None, None, None, None, tuple(settle), frozenset(new_reparen),
            state.iterations, None, False,
        )

    def tail_gate(opener, offset):
        """The tail gate: whether an opener of kind OPENER (one of
        _LEX_TAIL_START_OPENERS or _LEX_TAIL_SOURCE_OPENERS) at OFFSET may open
        in the pass state as it stands. A tail-start opener may not from the
        tail start on (OFFSET is where the opener begins; for an assignment-
        word subscript, where its word begins); a tail-source opener may not
        once a tail source has been met, wherever it lies. This is the only
        place of the pass that compares an offset with the tail start or tests
        the tail source for an opener's sake; what keeps the two up to date
        (the initial tail start, a tail source being met, the end of a
        discarded line) is the pass's own bookkeeping and stays where it is.
        A refused opener is literal text, and the caller lists it in
        UNOPENED."""
        if opener in _LEX_TAIL_SOURCE_OPENERS:
            return state.tail_source is None
        if opener in _LEX_TAIL_START_OPENERS:
            return state.tail_start is None or offset < state.tail_start
        raise ValueError("unknown opener kind: %r" % (opener,))

    def new_region(kind, start, f):
        parent = f.reg
        if parent is None:
            anc = None
        else:
            anc = parent if regions[parent][0] in LEX_SUBSTITUTION_KINDS else regions[parent][5]
        regions.append([kind, start, None, parent, True, anc])
        return len(regions) - 1

    def push(f, kind, region_kind, start, cmd=False, depth=0):
        # What resuming from an arithmetic opener takes back is captured
        # before anything of the opener is pushed.
        snap = _LexResumeSnapshot.capture(state) if kind == "arith" else None
        idx = new_region(region_kind, start, f)
        frame = _LexFrame(kind, start, idx, idx, cmd, depth)
        frame.snap = snap
        stack.append(frame)
        state.seq += 1
        rseq.append(state.seq)

    def close(f, end):
        regions[f.region][2] = end
        stack.pop()
        rseq.pop()
        if f.kind == "sq":
            _lex_quote_candidates(
                text, f.start + 1, end - 1, f.region, regions[f.region][5], candidates
            )
        elif f.kind == "ansi":
            _lex_quote_candidates(
                text, f.start + 2, end - 1, f.region, regions[f.region][5], candidates
            )

    def open_bare(f, kind, start, named=False, bound=False):
        """P14: a `subscript` (at its `[`) or `extglob` (at its `(`) frame on
        top of F. An `extglob` frame, and a BOUND subscript (a declaration-
        builtin argument), have no region of their own -- regions opened
        inside them hang under F's; any other subscript owns an
        `array-subscript` region from its `[`. Either way the frame counts as
        an open context for the here-document bodies pending before it, as a
        region does, so it takes a region sequence number."""
        if kind == "subscript" and not bound:
            idx = new_region("array-subscript", start, f)
            child = _LexFrame(kind, start, idx, idx, depth=1)
        else:
            child = _LexFrame(kind, start, None, f.reg, depth=1)
        child.named = named
        child.bound = bound
        stack.append(child)
        state.seq += 1
        rseq.append(state.seq)

    def close_bare(f, end=None):
        """The frame F opened by open_bare() ends (at END, its region's end):
        the word of the frame below goes on after it."""
        if f.region is not None:
            regions[f.region][2] = end
        stack.pop()
        rseq.pop()
        stack[-1].in_word = True

    def close_subscript(f, after):
        """F's subscript ends with the `]` just before AFTER. After the `]` of
        a `NAME[...]` word, `=(` / `+=(` open an array compound assignment (the
        `(` sets ARR_END); any other `=` / `+=` makes it an assignment word,
        and anything else makes it no assignment word at all."""
        close_bare(f, after)
        if f.named:
            parent = stack[-1]
            op_at = after
            while text.startswith("\\\n", op_at):
                op_at += 2
            if text.startswith("+=", op_at):
                op_at += 2
            elif text.startswith("=", op_at):
                op_at += 1
            else:
                op_at = -1
            paren = op_at
            while op_at >= 0 and text.startswith("\\\n", paren):
                paren += 2
            if op_at >= 0 and paren < n and text[paren] == "(":
                parent.arr_end = paren
            elif op_at < 0:
                parent.asg = False

    def word_transition(f, w, end, first=None):
        """F's grammar state advances over one word: W is its text when it
        is a plain, complete word, else None; END the offset after it; FIRST
        the plain run the word starts with (None for a word that starts with
        a quote, an expansion or an escape).

        P10 (FR3). RW says the word comes directly after a closer (or after
        the NAME of a `for` / `select`): a reserved word of
        _LEX_AFTER_CLOSER_WORDS is recognized there and handled as at a
        command position, any other word is an argument. `]]` closes a
        conditional command opened at a command position (COND); `fi`,
        `done`, `esac` and `}` at a command position are closers themselves
        and set RW for the word after them; the word after `coproc` is the
        coprocess NAME unless it begins a compound command, and the position
        after the NAME -- like the one after `function NAME` -- is a command
        position. Directly after `time` a `-p` is an option (the command
        position stays and the marker records that it was seen) and a `--`
        ends the options; directly after `time -p` only `--` is an option, so
        any other word -- a second `-p` included -- is the command word and
        ends the command position like every other command word. In every
        case a `--` keeps the command position and clears the marker.

        P13. A word at a command position or after assignment words only
        (ASG) is in assignment position; one after a declaration builtin, or
        `eval`, `let` or `alias` (DECL) is in declaration-argument position.
        A `NAME=` / `NAME+=` word in either position that a `(` follows
        directly sets ARR_END to its end: that `(` opens an array compound
        assignment. P14: a `NAME[` word in either position sets SUB_AT to the
        offset of its `[`, where a subscript frame opens; its `]` followed by
        `=(` / `+=(` sets ARR_END. The `NAME[` test reads the word's leading
        characters with every backslash-newline pair removed
        (_lex_subscript_open(), round 2 deferred FR4), so a name that holds
        continuations opens its subscript at the original offset of the `[`."""
        if f.redir:
            # The target word of a redirection: it is no command or
            # assignment word and leaves the grammar state as it was.
            f.redir = False
            f.prev_plain = False
            return
        time_p = f.time_p
        kw = f.kw
        rw = f.rw
        rd_cmd = f.rd_cmd
        nosub = f.nosub and not f.cmd
        f.time_p = False
        f.kw = ""
        f.rw = False
        f.prev_plain = False
        cs = f.cs
        top = cs[-1] if cs else None
        if rw and not f.cmd and w in _LEX_AFTER_CLOSER_WORDS:
            f.cmd = True
        assign_pos = f.cmd or f.asg
        decl_pos = f.decl and not f.cmd
        if f.cmd:
            f.asg = False
            f.decl = False
            f.nosub = False
        if f.cond and w == "]]":
            f.cond = False
            f.cmd = False
            f.rw = True
        elif top == "await_subject":
            cs[-1] = "await_in"
            f.cmd = False
        elif top == "await_in":
            cs[-1] = "pattern_first"
            f.cmd = False
        elif top == "pattern_first" or top == "pattern_next":
            if w == "esac":
                rest = end
                while rest < n and text[rest] in " \t":
                    rest += 1
                if top == "pattern_first" and rest < n and text[rest] == ")":
                    cs[-1] = "pattern_rest"
                else:
                    cs.pop()
                    f.cmd = False
                    f.rw = True
            else:
                cs[-1] = "pattern_rest"
        elif top == "pattern_rest":
            pass
        elif f.fn_p:
            f.fn_p = False
            f.cmd = True
            f.prev_plain = True
        elif time_p == 1 and w == "-p":
            # The one `-p` `time` takes: the command position is kept and
            # F.TIME_P records it, so only a `--` can follow as an option.
            f.time_p = 2
        elif time_p and w == "--":
            # The end of `time`'s options: the command position is kept and
            # F.TIME_P, cleared above, stays cleared, so no later `-p` or `--`
            # is an option.
            pass
        elif kw == "for" or kw == "select":
            f.cmd = False
            f.rw = True
        elif kw == "coproc" and (w is None or w not in _LEX_COPROC_COMPOUND):
            f.cmd = True
        elif f.cmd and w is not None and not rd_cmd:
            if w == "esac":
                if cs:
                    cs.pop()
                f.cmd = False
                f.rw = True
            elif w == "case" and tail_gate("case-construct", end - len(w)):
                # After a tail source the gate refuses the construct: the
                # word is read as the ordinary command word it falls through
                # to below, and the words after it are arguments.
                cs.append("await_subject")
                f.cmd = False
            elif w in _LEX_COMMAND_KEEPERS:
                f.time_p = 1 if w == "time" else 0
                if w == "coproc":
                    f.kw = "coproc"
            elif w == "function":
                f.fn_p = True
                f.cmd = False
            elif w == "for" or w == "select":
                f.kw = w
                f.cmd = False
            elif w == "fi" or w == "done" or w == "}":
                f.cmd = False
                f.rw = True
            elif w == "[[":
                f.cond = True
                f.cmd = False
            else:
                f.cmd = False
                f.prev_plain = True
        else:
            f.cmd = False
        array_word = False
        sub_open = -1
        if (
            first is not None
            and state.discard_end is None
            and not nosub
            and tail_gate("assignment-subscript", end - len(first))
        ):
            # No subscript is read from the tail start on (round 2 residuals,
            # FR3): its `[` stays literal there, as every opener does. The
            # word's own start offset is the one compared with it, whatever
            # line continuations the name holds (round 2 deferred, FR4).
            sub_open = _lex_subscript_open(text, end - len(first), end, first)
        if assign_pos:
            if first is not None and _LEX_ASSIGN_WORD.match(first):
                f.asg = True
                f.decl = False
                array_word = first is not None and _LEX_ASSIGN_WORD.fullmatch(first)
            elif sub_open >= 0:
                # `NAME[`: an assignment word when the `=` / `+=` follows the
                # subscript's `]`, which close_subscript() finds out; until
                # then it is taken for one, and the subscript opens at its `[`.
                f.asg = True
                f.decl = False
                f.sub_at = sub_open
                f.sub_bound = False
            else:
                f.asg = False
                f.decl = w in _LEX_DECLARATION_BUILTINS
        elif decl_pos:
            if sub_open >= 0:
                # In a declaration-builtin argument bash reads the word with
                # the ordinary word rules: the subscript is BOUND, ending with
                # the word at an unquoted blank or metacharacter.
                f.sub_at = sub_open
                f.sub_bound = True
            else:
                array_word = first is not None and _LEX_ASSIGN_WORD.fullmatch(first)
        if not f.asg:
            f.rd_cmd = False
            f.nosub = False
        if array_word:
            # Line continuations between the `=` and the `(` are removed by
            # bash before it reads the word: skip them, keeping the offset
            # of the `(` in the original text.
            paren = end
            while text.startswith("\\\n", paren):
                paren += 2
            if paren < n and text[paren] == "(":
                f.arr_end = paren

    def mark_redirect(f):
        """A redirection operator was read: the next word is its target. One
        read at the command position turns off reserved words for the rest of
        the simple command (RD_CMD); one read after an assignment word ends
        the positions where a `NAME[` word opens a subscript (NOSUB; bash
        5.3)."""
        f.redir = True
        if f.cmd:
            f.rd_cmd = True
        elif f.asg:
            f.nosub = True

    def start_word(f, i):
        if not f.in_word:
            word_transition(f, None, i)
            f.in_word = True

    def dollar(i, f, in_quotes, body_literal):
        """The `$` at I: open the expansion it starts, or consume the special
        parameter it names; returns the offset to continue at (P1-P3)."""
        c2 = text[i + 1] if i + 1 < n else ""
        if c2 == "(":
            if text.startswith("(", i + 2):
                if i in settled or not tail_gate("arithmetic-expansion", i):
                    # Settled as unclosed, or refused after a tail source:
                    # literal text either way, read on after it.
                    encountered.append(i)
                    return i + 3
                if not as_two_parentheses(i):
                    push(f, "arith", "arithmetic-expansion", i, depth=2)
                    return i + 3
            push(f, "cmdsub", "command-substitution", i, cmd=True)
            return i + 2
        if c2 == "{":
            # The parameter form: the command form `${ ` / `${|` is decided
            # before this point (task0005) and is never refused.
            if i in settled or not tail_gate("parameter-expansion", i):
                encountered.append(i)
                return i + 2
            push(f, "param", "parameter-expansion", i)
            return i + 2
        if c2 == "[":
            if i in settled or not tail_gate("bracket-arithmetic", i):
                encountered.append(i)
                return i + 2
            push(f, "bracket", "bracket-arithmetic", i, depth=1)
            return i + 2
        if c2 == "'" and not in_quotes and not body_literal:
            if i in settled:
                encountered.append(i)
                return i + 2
            if tail_gate("ansi-c-quote", i):
                push(f, "ansi", "ansi-c-quote", i)
                return i + 2
        if (
            c2 == '"' and not in_quotes and not body_literal
            and tail_gate("locale-quote", i)
        ):
            push(f, "locale", "locale-quote", i)
            return i + 2
        if c2 and c2 in _LEX_SPECIAL_PARAMETERS:
            return i + 2
        return i + 1

    def register_operator(i, word):
        """A real here-document operator at I, its delimiter word read as
        WORD = (end, delimiter, quoted): queue it for a body (P11). Its body
        is not looked up here -- where it begins depends on the newlines read
        after it."""
        op = [i, word[0], word[1], word[2], None, None, None]
        ops.append(op)
        if lines is None:
            return
        if not hd_pending:
            starts = lines.starts
            k = bisect.bisect_right(starts, i)
            state.hd_trigger = starts[k] if k < len(starts) else None
            state.limit = state.hd_trigger if state.hd_trigger is not None else n
        hd_pending.append(op)
        hd_seqs.append(state.seq)

    def begin_discard(i):
        """The `<<` at I is at direct position in an array: the line it is on
        becomes the discarded line. No scan reads past its newline (LIMIT).
        The operators still pending -- the line's own before the `<<`, and
        any an earlier line left waiting -- are dropped without a body, now:
        the pending record is emptied, nothing is re-read, and no line start
        before the newline can hand out a body."""
        newline = text.find("\n", i)
        state.discard_end = n if newline == -1 else newline
        del hd_pending[:]
        del hd_seqs[:]
        state.hd_trigger = None
        state.limit = state.discard_end

    def end_discard():
        """The discarded line ends (at DISCARD_END): every open context is
        cleared and the next line is read at the top level, command position.
        The openers of the expansions that cannot end at the newline are
        collected in DISCARD_UNCLOSED: the pass goes on, and at its end they
        are settled together with the rest, so many discarded lines cost no
        more passes than one."""
        end = state.discard_end
        if state.tail_start is not None and state.tail_start < end:
            # An opener left unclosed on this discarded line reaches no
            # further than its newline: the lines after it are read with
            # only the later unclosed openers in force. A tail source (a
            # `<<` whose delimiter word cannot be read) stays in force.
            later = [s for s in settled if s >= end]
            if state.tail_source is not None:
                later.append(state.tail_source)
            state.tail_start = min(later) if later else None
        if text[end - 1] == "\\" and not (
            regions and regions[-1][0] == "comment" and regions[-1][2] == end
        ):
            # A backslash ends the line (inside a quote it consumed the
            # newline, in a word it never began a continuation): the view
            # must not read it as an escape of the newline.
            idx = new_region(LEX_DISCARDED_CONTINUATION, end - 1, stack[-1])
            regions[idx][2] = end
        cut_quotes = []
        for f in stack[1:]:
            if f.kind in ("param", "arith", "bracket", "ansi"):
                discard_unclosed.append(f.start)
            if f.region is None:
                continue
            region = regions[f.region]
            region[2] = end
            region[4] = False
            if f.kind == "sq":
                _lex_quote_candidates(text, f.start + 1, end, f.region, region[5], candidates)
            if f.kind in ("sq", "dq", "locale"):
                cut_quotes.append(f.region)
        if cut_quotes:
            # A quote still open at the newline is no quote: its region
            # shrinks to the opening character (hidden from shlex) and what
            # it held belongs to the region around it, so the text after the
            # opener is read as the commands it is. The stack is ordered, so
            # one pass over the regions after the first quote does it.
            hoist = {}
            for q in cut_quotes:
                parent = regions[q][3]
                hoist[q] = hoist.get(parent, parent)
            for k in range(cut_quotes[0] + 1, len(regions)):
                parent = regions[k][3]
                if parent in hoist:
                    regions[k][3] = hoist[parent]
            for q in cut_quotes:
                region = regions[q]
                region[0] = LEX_DISCARDED_QUOTE
                region[2] = region[1] + (2 if text.startswith('$"', region[1]) else 1)
        del stack[1:]
        del rseq[:]
        base = stack[0]
        base.cmd = True
        base.cs = []
        base.in_word = False
        base.prev_plain = base.time_p = False
        base.kw = ""
        base.fn_p = False
        base.rw = False
        base.cond = False
        base.asg = base.decl = False
        base.arr_end = -1
        base.redir = False
        base.rd_cmd = False
        base.nosub = False
        base.sub_at = -1
        state.limit = n
        state.discard_end = None

    while i < n:
        state.iterations += 1
        if state.iterations > budget:
            raise LexBudgetExceeded()
        if state.discard_end is not None and i >= state.discard_end:
            # The newline that ends the discarded line (a backslash or a quote
            # may have consumed it already): everything open is cleared and
            # the next line starts at the top level.
            newline = state.discard_end
            end_discard()
            i = max(i, newline + 1)
            continue
        if state.hd_trigger is not None and i >= state.hd_trigger:
            # A line start with here-document operators pending (P11). The
            # operators whose registration-time regions are all that is
            # open now (the pending list is in registration order, so they
            # are a suffix of it) take their bodies from this line on, in
            # operator order; the others -- and all of them after a
            # backslash-newline -- wait for the next line start.
            boundary = state.hd_trigger
            starts = lines.starts
            if boundary == state.cont_at:
                cut = len(hd_pending)
            else:
                cut = bisect.bisect_left(hd_seqs, rseq[-1] if rseq else 0)
            if cut < len(hd_pending):
                hd_next = bisect.bisect_right(starts, boundary) - 1
                jump = None
                for op in hd_pending[cut:]:
                    # `<<-` removes leading tabs from a line before it is
                    # compared with the delimiter, `<<` compares the line.
                    found_lines = lines.close_lines(
                        text.startswith("-", op[0] + 2)
                    ).get(op[2], ())
                    pos = bisect.bisect_left(found_lines, hd_next)
                    if pos < len(found_lines):
                        found = found_lines[pos]
                        op[4] = starts[hd_next]
                        op[5] = starts[found]
                        op[6] = starts[found + 1] if found + 1 < len(starts) else n
                        hd_next = found + 1
                        jump = op[6]
                del hd_pending[cut:]
                del hd_seqs[cut:]
                if jump is not None and jump > i:
                    i = jump
                stack[-1].in_word = False
            if hd_pending:
                k = bisect.bisect_right(starts, max(i, boundary))
                state.hd_trigger = starts[k] if k < len(starts) else None
                state.limit = state.hd_trigger if state.hd_trigger is not None else n
            else:
                state.hd_trigger = None
                state.limit = n
            continue
        f = stack[-1]
        kind = f.kind

        if kind in _LEX_SHELL_KINDS:
            c = text[i]
            if c in " \t\r":
                i = _LEX_WS.match(text, i, state.limit).end()
                f.in_word = False
                continue
            if c == "\n":
                f.cmd = kind != "array"
                f.in_word = False
                f.redir = False
                f.rd_cmd = False
                f.prev_plain = f.time_p = False
                f.kw = ""
                i += 1
                continue
            if c == "\\":
                if text.startswith("\n", i + 1):
                    if i + 1 == state.discard_end:
                        # The discarded line's own newline: no continuation;
                        # the line ends here (see the end of the line below).
                        i += 1
                        continue
                    # A line continuation: it never starts a here-document body (P11).
                    i += 2
                    state.cont_at = i
                    continue
                start_word(f, i)
                i += 2
                continue
            if c == "#" and not f.in_word and tail_gate("comment", i):
                end = text.find("\n", i, state.limit)
                if end == -1:
                    end = state.limit
                idx = new_region("comment", i, f)
                regions[idx][2] = end
                i = end
                continue
            if c == ";":
                if text.startswith(";;&", i):
                    step = 3
                elif text.startswith(";;", i) or text.startswith(";&", i) or text.startswith(";|", i):
                    step = 2
                else:
                    step = 1
                if kind == "array" and state.discard_end is None and tail_gate("discarded-line", i):
                    # `;` directly in an array compound assignment: a syntax
                    # error; this line is the discarded line (P13).
                    begin_discard(i)
                cs = f.cs
                if step > 1 and cs and cs[-1] == "body":
                    cs[-1] = "pattern_next"
                f.cmd = kind != "array"
                f.in_word = False
                f.redir = False
                f.rd_cmd = False
                f.prev_plain = f.time_p = False
                f.kw = ""
                i += step
                continue
            if c == "&" or c == "|":
                if kind == "array" and state.discard_end is None and tail_gate("discarded-line", i):
                    # `&` / `|` directly in an array compound assignment: a
                    # syntax error; this line is the discarded line (P13).
                    begin_discard(i)
                f.in_word = False
                f.redir = False
                f.rd_cmd = False
                if c == "&" and text.startswith("&>", i):
                    mark_redirect(f)
                    i += 3 if text.startswith("&>>", i) else 2
                    continue
                if c == "|" and f.cs and f.cs[-1] in _LEX_CASE_PATTERN_STATES:
                    i += 1
                    continue
                if text.startswith("&&", i) or text.startswith("||", i) or text.startswith("|&", i):
                    i += 2
                else:
                    i += 1
                f.cmd = kind != "array"
                f.prev_plain = f.time_p = False
                f.kw = ""
                continue
            if c == "(":
                top_cs = f.cs[-1] if f.cs else None
                in_word = f.in_word
                f.in_word = False
                if top_cs == "pattern_first" or top_cs == "pattern_next":
                    i += 1
                    continue
                if kind == "array":
                    # The logical previous character: backslash-newline line
                    # continuations are removed before bash reads the word.
                    prev_j = i - 1
                    while prev_j >= 1 and text[prev_j] == "\n" and text[prev_j - 1] == "\\":
                        k = prev_j - 1
                        while k >= 0 and text[k] == "\\":
                            k -= 1
                        if (prev_j - 1 - k) % 2 == 0:
                            break
                        prev_j -= 2
                    if (
                        in_word
                        and state.discard_end is None
                        and prev_j >= 0
                        and text[prev_j] in _LEX_EXTGLOB_PREFIXES
                    ):
                        # An extended-glob parenthesis (P14): valid with
                        # extglob on, a syntax error with it off. The reading
                        # decides; either way the other one could differ.
                        state.extglob_met = True
                        line_start = text.rfind("\n", 0, i) + 1
                        state.ext_lines.append((line_start, text[line_start:i]))
                        if extglob:
                            open_bare(f, "extglob", i)
                            i += 1
                            continue
                    # A parenthesis inside an array compound assignment is a
                    # syntax error in bash as well: this line is the
                    # discarded line, and no operator on it gets a body (P13).
                    if state.discard_end is None and tail_gate("discarded-line", i):
                        begin_discard(i)
                    i += 1
                    continue
                if f.prev_plain:
                    m = _LEX_FUNCTION_HEAD.match(text, i, state.limit)
                    if m is not None:
                        i = m.end()
                        f.cmd = True
                        f.prev_plain = f.time_p = False
                        f.kw = ""
                        continue
                if f.arr_end == i:
                    # The `(` right after a `NAME=` / `NAME+=` word at an
                    # assignment or declaration-argument position (P13).
                    f.kw = ""
                    f.prev_plain = f.time_p = False
                    stack.append(_LexFrame("array", i, None, f.reg))
                    i += 1
                    continue
                if (
                    in_word
                    and f.decl
                    and not f.cmd
                    and text[i - 1] == "="
                    and state.discard_end is None
                    and tail_gate("discarded-line", i)
                ):
                    # A `(` right after the `=` of a declaration-builtin
                    # argument that is no `NAME=` / `NAME[...]=` word (a BOUND
                    # subscript ended it early: `declare x[a b]=(`): a syntax
                    # error in bash. Read like the array error (P13): this line
                    # is the discarded line, so no operator on it gets a body.
                    begin_discard(i)
                    i += 1
                    continue
                if (
                    (f.cmd or f.kw == "for")
                    and text.startswith("((", i)
                    and top_cs not in _LEX_CASE_PATTERN_STATES
                ):
                    if i in settled or not tail_gate("arithmetic-command", i):
                        # Settled as unclosed, or refused after a tail
                        # source: the two characters are literal text that
                        # starts a word and ends the command position.
                        encountered.append(i)
                        f.in_word = True
                        f.cmd = False
                        f.kw = ""
                        f.prev_plain = f.time_p = False
                        i += 2
                        continue
                    if not as_two_parentheses(i):
                        f.kw = ""
                        f.redir = False
                        f.rd_cmd = False
                        f.prev_plain = f.time_p = False
                        push(f, "arith", "arithmetic-command", i, depth=2)
                        i += 2
                        continue
                f.kw = ""
                f.redir = False
                f.rd_cmd = False
                f.prev_plain = f.time_p = False
                stack.append(_LexFrame("group", i, None, f.reg, True))
                i += 1
                continue
            if c == ")":
                f.in_word = False
                f.redir = False
                f.rd_cmd = False
                f.prev_plain = f.time_p = False
                f.kw = ""
                top_cs = f.cs[-1] if f.cs else None
                if top_cs in _LEX_CASE_PATTERN_STATES:
                    f.cs[-1] = "body"
                    f.cmd = True
                elif kind == "group":
                    stack.pop()
                    parent = stack[-1]
                    parent.cmd = False
                    parent.in_word = False
                    parent.rw = True
                elif kind == "array":
                    # The array compound assignment ends; its word is whole,
                    # and the assignment position it was read in stays.
                    stack.pop()
                    stack[-1].in_word = False
                elif kind == "cmdsub":
                    close(f, i + 1)
                elif kind == "procsub":
                    # P12: the process substitution is part of its word, as a
                    # command substitution is; the word stays in progress.
                    close(f, i + 1)
                i += 1
                continue
            if c == "<" or c == ">":
                in_word = f.in_word
                f.in_word = False
                f.prev_plain = f.time_p = False
                f.kw = ""
                if c == "<":
                    if text.startswith("<<<", i):
                        if kind == "array" and state.discard_end is None and tail_gate("discarded-line", i):
                            begin_discard(i)
                        mark_redirect(f)
                        idx = new_region("here-string-operator", i, f)
                        regions[idx][2] = i + 3
                        i += 3
                        continue
                    if text.startswith("<<", i):
                        if state.discard_end is not None:
                            # On the discarded line: no operator (P13).
                            i += 2
                            continue
                        if kind == "array":
                            # Direct position in an array compound assignment:
                            # a syntax error, no operator; this line is the
                            # discarded line (P13).
                            begin_discard(i)
                            i += 2
                            continue
                        word = None
                        if tail_gate("heredoc-operator", i):
                            word = _read_heredoc_delimiter(text, i)
                            if word is None:
                                # A delimiter word that cannot be read: no
                                # operator, and the text from here on is read
                                # as a tail (no comment, quote region or
                                # operator opens), so a line bash 5.3 would
                                # run as a command is never hidden by one.
                                state.tail_source = state.tail_start = i
                        # A here-document operator is a redirection as well; its
                        # delimiter word is part of it, so no target follows.
                        mark_redirect(f)
                        f.redir = False
                        if word is not None:
                            register_operator(i, word)
                            i = word[0]
                        else:
                            i += 2
                        continue
                    if text.startswith("<(", i) and (i == 0 or text[i - 1] not in "<>"):
                        f.in_word = in_word
                        start_word(f, i)
                        push(f, "procsub", "process-substitution", i, cmd=True)
                        i += 2
                        continue
                    if kind == "array" and state.discard_end is None and tail_gate("discarded-line", i):
                        begin_discard(i)
                    mark_redirect(f)
                    i += 2 if (text.startswith("<&", i) or text.startswith("<>", i)) else 1
                    continue
                if text.startswith(">(", i) and (i == 0 or text[i - 1] not in "<>"):
                    f.in_word = in_word
                    start_word(f, i)
                    push(f, "procsub", "process-substitution", i, cmd=True)
                    i += 2
                    continue
                if kind == "array" and state.discard_end is None and tail_gate("discarded-line", i):
                    begin_discard(i)
                mark_redirect(f)
                i += 2 if (
                    text.startswith(">>", i) or text.startswith(">&", i) or text.startswith(">|", i)
                ) else 1
                continue
            if c == "'":
                start_word(f, i)
                if tail_gate("single-quote", i):
                    push(f, "sq", "single-quote", i)
                else:
                    encountered.append(i)
                i += 1
                continue
            if c == '"':
                start_word(f, i)
                if tail_gate("double-quote", i):
                    push(f, "dq", "double-quote", i)
                else:
                    encountered.append(i)
                i += 1
                continue
            if c == "$":
                start_word(f, i)
                i = dollar(i, f, False, False)
                continue
            if c == "`":
                if kind == "backtick":
                    close(f, i + 1)
                    i += 1
                    continue
                start_word(f, i)
                push(f, "backtick", "backtick-substitution", i, cmd=True)
                i += 1
                continue
            run = _LEX_WORD_RUN.match(text, i, state.limit)
            end = run.end()
            if f.in_word:
                if i <= f.sub_at < end:
                    # The `[` of a `NAME[` word whose name held line
                    # continuations (FR4): word_transition() found it past the
                    # pairs, and this run, read after the last of them, holds
                    # it. The subscript opens at the `[` in the original text.
                    at = f.sub_at
                    f.sub_at = -1
                    open_bare(f, "subscript", at, True, f.sub_bound)
                    i = at + 1
                    continue
                i = end
                continue
            if (
                end < n
                and text[end] in "<>"
                and (
                    text[i:end].isdigit()
                    or re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", text[i:end]) is not None
                )
                and not text.startswith("(", end + 1)
            ):
                # The fd number of a redirection: it leaves the grammar state
                # as it was; the operator that follows sets REDIR.
                f.in_word = True
                i = end
                continue
            complete = end >= n or text[end] in _LEX_WORD_END
            f.sub_at = -1
            word_transition(f, text[i:end] if complete else None, end, text[i:end])
            f.in_word = True
            if 0 <= f.sub_at < end:
                # A `NAME[` word at an assignment position: its subscript
                # opens at the `[` (P14). A `[` past this run, after line
                # continuations in the name, opens when the pass reaches it.
                at = f.sub_at
                f.sub_at = -1
                open_bare(f, "subscript", at, True, f.sub_bound)
                i = at + 1
                continue
            if (
                kind == "array"
                and text[i] == "["
                and state.discard_end is None
                and tail_gate("array-subscript", i)
            ):
                # An element of an array that starts with `[`: a subscript.
                open_bare(f, "subscript", i)
                i += 1
                continue
            i = end
            continue

        if kind == "dq" or kind == "locale":
            m = _LEX_DQ_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif c == '"':
                close(f, j + 1)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, True, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        if kind == "sq":
            j = text.find("'", i, state.limit)
            if j == -1:
                i = state.limit
            else:
                close(f, j + 1)
                i = j + 1
            continue

        if kind == "ansi":
            m = _LEX_ANSI_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            if text[j] == "\\":
                i = j + 2
            else:
                close(f, j + 1)
                i = j + 1
            continue

        if kind == "param":
            m = _LEX_PARAM_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif c == "}":
                close(f, j + 1)
                i = j + 1
            elif c == "'":
                if tail_gate("single-quote", j):
                    push(f, "sq", "single-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == '"':
                if tail_gate("double-quote", j):
                    push(f, "dq", "double-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, False, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        if kind == "arith":
            m = _LEX_ARITH_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif c == "(":
                f.depth += 1
                i = j + 1
            elif c == ")":
                f.depth -= 1
                if f.depth != 1:
                    i = j + 1
                elif text.startswith(")", j + 1):
                    close(f, j + 2)
                    if regions[f.region][0] == "arithmetic-command":
                        parent = stack[-1]
                        parent.cmd = False
                        parent.in_word = False
                        parent.rw = True
                    i = j + 2
                elif whole_restart:
                    new_reparen.add(f.start)
                    return ending(())
                else:
                    # The first close is not an adjacent `))`: read the opener
                    # as two parentheses (P4). Take back what the pass held
                    # at the opener, the opener's own frame included, and
                    # resume there: nothing before the opener, and nothing in
                    # the frames below it, has changed.
                    new_reparen.add(f.start)
                    is_command = regions[f.region][0] == "arithmetic-command"
                    f.snap.restore(state)
                    parent = stack[-1]
                    if is_command:
                        # `((`: two nested groups.
                        stack.append(_LexFrame("group", f.start, None, parent.reg, True))
                        i = f.start + 1
                    else:
                        # `$((`: a command substitution whose body starts
                        # with a group.
                        push(parent, "cmdsub", "command-substitution", f.start, cmd=True)
                        i = f.start + 2
            elif c == "'":
                if tail_gate("single-quote", j):
                    push(f, "sq", "single-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == '"':
                if tail_gate("double-quote", j):
                    push(f, "dq", "double-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, False, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        if kind == "bracket":
            m = _LEX_BRACKET_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif c == "[":
                f.depth += 1
                i = j + 1
            elif c == "]":
                f.depth -= 1
                if f.depth == 0:
                    close(f, j + 1)
                i = j + 1
            elif c == "'":
                if tail_gate("single-quote", j):
                    push(f, "sq", "single-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == '"':
                if tail_gate("double-quote", j):
                    push(f, "dq", "double-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, False, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        if kind == "subscript":
            # A subscript (P14), read the way bash matches `[` ... `]`: only
            # quotes, expansions, backquotes, backslash escapes and nested
            # brackets mean anything; a blank, `<<` or `;` is part of it.
            # A BOUND subscript ends with its word at an unquoted blank or
            # metacharacter instead: the frame below reads that character.
            m = (
                _LEX_SUBSCRIPT_BOUND_SPECIAL if f.bound else _LEX_SUBSCRIPT_SPECIAL
            ).search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif f.bound and c in _LEX_WORD_END:
                stack.pop()
                rseq.pop()
                i = j
            elif c == "<" or c == ">":
                if text.startswith("(", j + 1) and (j == 0 or text[j - 1] not in "<>"):
                    # A process substitution runs inside a subscript too.
                    push(f, "procsub", "process-substitution", j, cmd=True)
                    i = j + 2
                else:
                    i = j + 1
            elif c == "[":
                f.depth += 1
                i = j + 1
            elif c == "]":
                f.depth -= 1
                i = j + 1
                if f.depth == 0:
                    close_subscript(f, i)
            elif c == "'":
                if tail_gate("single-quote", j):
                    push(f, "sq", "single-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == '"':
                if tail_gate("double-quote", j):
                    push(f, "dq", "double-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, False, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        if kind == "extglob":
            # The pattern group of an extended-glob parenthesis inside an
            # array (P14), read to its matching `)`: parentheses nest, and a
            # `<<` or `;` in it is pattern text.
            m = _LEX_EXTGLOB_SPECIAL.search(text, i, state.limit)
            if m is None:
                i = state.limit
                continue
            j = m.start()
            c = text[j]
            if c == "\\":
                i = j + 2
            elif c == "<" or c == ">":
                if text.startswith("(", j + 1) and (j == 0 or text[j - 1] not in "<>"):
                    # A process substitution runs inside a pattern too.
                    push(f, "procsub", "process-substitution", j, cmd=True)
                    i = j + 2
                else:
                    i = j + 1
            elif c == "(":
                f.depth += 1
                i = j + 1
            elif c == ")":
                f.depth -= 1
                i = j + 1
                if f.depth == 0:
                    close_bare(f)
            elif c == "'":
                if tail_gate("single-quote", j):
                    push(f, "sq", "single-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == '"':
                if tail_gate("double-quote", j):
                    push(f, "dq", "double-quote", j)
                else:
                    encountered.append(j)
                i = j + 1
            elif c == "$":
                i = dollar(j, f, False, False)
            else:
                push(f, "backtick", "backtick-substitution", j, cmd=True)
                i = j + 1
            continue

        # `btop`: the literal top level of a heredoc body -- only the `$`
        # expansions, backticks and backslash escapes mean anything.
        m = _LEX_BODY_SPECIAL.search(text, i, state.limit)
        if m is None:
            i = state.limit
            continue
        j = m.start()
        c = text[j]
        if c == "\\":
            i = j + 2
        elif c == "$":
            i = dollar(j, f, False, True)
        else:
            push(f, "backtick", "backtick-substitution", j, cmd=True)
            i = j + 1

    if state.discard_end is not None:
        # The text ends inside the discarded line.
        end_discard()
    unclosed = discard_unclosed + [
        f.start for f in stack[1:] if f.kind in ("param", "arith", "bracket", "ansi")
    ]
    if unclosed:
        return ending(unclosed)
    if any(f.kind == "subscript" and not f.bound for f in stack):
        # A subscript whose `]` never comes (P14): bash keeps reading for it.
        # (A BOUND one simply ends with its word at the end of the text.)
        raise LexUnmatchedSubscript()
    for f in stack[1:]:
        if f.region is not None:
            regions[f.region][2] = n
            regions[f.region][4] = False
            if f.kind == "sq":
                _lex_quote_candidates(
                    text, f.start + 1, n, f.region, regions[f.region][5], candidates
                )
    _lex_pass_ext_lines.clear()
    for line_start, prefix in state.ext_lines:
        _lex_pass_ext_lines.setdefault(line_start, prefix)
    return _LexPassResult(
        "done", regions, ops, candidates, encountered, (), frozenset(new_reparen),
        state.iterations, state.tail_source, state.extglob_met,
    )


# The reading of an extended-glob parenthesis inside an array (P14) that
# lex_shell() takes when its caller names none, and whether any lexing met such
# a parenthesis. run() judges a command under extglob off and, when the lexer
# met one, under extglob on as well (_judge_under()); the stages in between
# call lex_shell() without a reading, so the reading in force is set here, once,
# by the one function that combines the verdicts. The cache below is keyed on it.
_lex_extglob = False
_lex_extglob_met = False
# The lines _lex_pass() last met an extended-glob parenthesis on (line start ->
# text before it), handed to lex_shell(); and the (text, line start, prefix)
# of every such line any lexing of the judgment under way met, which run()
# turns into a count of parse units (_count_extglob_units()).
_lex_pass_ext_lines = {}
_lex_ext_seen = set()


def _note_extglob_lines(text, lex_map):
    for line_start, prefix in lex_map.ext_lines:
        _lex_ext_seen.add((text, line_start, prefix))


def _count_extglob_units():
    """How many parse units the lexing met an extended-glob parenthesis in
    during one judgment: the most lines of one text, or the number of distinct
    lines (compared by what precedes the parenthesis, marker residue left out)
    over all the texts lexed -- the top-level text, the stripped text, an
    `eval` / `-c` payload."""
    if not _lex_ext_seen:
        return 0
    per_text = {}
    keys = set()
    for text, _line_start, prefix in _lex_ext_seen:
        per_text[text] = per_text.get(text, 0) + 1
        keys.add(
            _MARK_RE.sub("", prefix).replace(QUOTED_MARK, "").replace(UNRESOLVED_MARK, "")
        )
    return max(max(per_text.values()), len(keys))


def lex_shell(text, mode="shell", bodies=True, extglob=None):
    """The unified lexer (FR1-FR9, and FR3 / FR6 / FR8 as reworked by P10-P12;
    IMPLEMENTATION.md "Unified lexer contract", P1-P13): ONE forward reading
    of TEXT that decides every quote, comment, expansion and substitution
    range, every real here-document operator, and the single-quote
    substitution candidates. Returns a LexMap.

    MODE is `shell` (the default) or `heredoc-body`: in `heredoc-body` mode,
    outside any substitution, quote characters, `$'`, `$"`, `#`, `<(` / `>(`
    and a bare `((` are literal text, while the `$` expansions are
    recognized; inside a substitution the shell rules apply.

    BODIES (shell mode) says TEXT still holds its here-document bodies: the
    body lines of a real operator, through its delimiter line, are then
    skipped (they change no lexer state) and reported on the operator. The
    body begins on the line after the first newline read while no region
    opened after the operator is still open, never after a backslash-newline
    (P11). Pass
    False for a text whose bodies were already removed (strip_heredocs()'s
    output): its operators are still reported, but consume nothing, so the
    text after them is lexed as it stands.

    TEXT is any string, including one with unbalanced quotes or unclosed
    openers (P4: an opener among `${`, `$((`, `$[`, `((` and `$'` that never
    closes is not a region, its characters are literal, and the text from the
    earliest such opener on is read without any `<<` operator and without
    any comment). A `<<` whose delimiter word cannot be read is a tail source
    too: from it on no comment, no quote region, no operator, no parameter-form
    `${`, `$((`, `$[`, no `((` at a command position and no case construct
    opens (`$(` and backticks still do), and the quote characters and the
    expansion openers left literal are listed in UNOPENED. The same TEXT, MODE
    and BODIES always give the same map;
    nothing is read from disk and nothing is evaluated (P7). Raises
    LexBudgetExceeded when the work bound is exceeded.

    EXTGLOB (P14) is the reading of an extended-glob parenthesis directly
    inside an array compound assignment: True reads it as the pattern group
    bash accepts with `shopt -s extglob`, False as the syntax error it is
    without it. None -- what every stage but the one that combines the two
    readings passes -- takes the reading in force (_lex_extglob). The module
    flag _lex_extglob_met is raised whenever a lexing met such a parenthesis,
    that is, whenever the other reading could give another map. Raises
    LexUnmatchedSubscript (a LexBudgetExceeded) for a subscript whose `]`
    never comes.

    The result is cached on (TEXT, MODE, BODIES, EXTGLOB): the maps are never
    modified, and every stage that needs the lexer's reading of one chunk
    shares one lexing."""
    global _lex_extglob_met
    if mode not in ("shell", "heredoc-body"):
        raise ValueError("unknown lexer mode: %r" % (mode,))
    if bodies and (mode != "shell" or "<<" not in text):
        bodies = False
    if extglob is None:
        extglob = _lex_extglob
    key = (text, mode, bodies, extglob)
    cached = _LEX_CACHE.get(key)
    if cached is not None:
        if cached.ext_lines:
            _note_extglob_lines(text, cached)
        return cached
    n = len(text)
    budget = LEX_WORK_FACTOR * n + _LEX_WORK_FLOOR
    lines = _LexLines(text) if bodies else None
    settled = set()
    reparen = set()
    used = 0
    rounds = 0
    while True:
        rounds += 1
        # A pass ends early only to settle unclosed openers (RESULT.SETTLE);
        # it resumes by itself at each opener that closes without an adjacent
        # `))`, and returns those (RESULT.REPAREN) for the passes after it.
        result = _lex_pass(text, mode, settled, reparen, lines, budget - used, extglob)
        if result.status == "done":
            break
        used += result.iterations
        settled.update(result.settle)
        reparen.update(result.reparen)
    regions, ops, candidates, encountered = (
        result.regions, result.ops, result.candidates, result.encountered
    )
    used += result.iterations
    ambiguous = result.ambiguous
    if ambiguous:
        _lex_extglob_met = True
    # The re-read tail starts at the earliest opener settled as not opened or
    # at the `<<` whose delimiter word could not be read, whichever comes
    # first: it is the very rule the final pass applied (no `<<` operator, no
    # comment from there on).
    unopened = sorted(encountered)
    tail_start = min(settled) if settled else None
    if result.tail_source is not None and (
        tail_start is None or result.tail_source < tail_start
    ):
        tail_start = result.tail_source
    lex_map = LexMap(
        [LexRegion(kind, s, e, parent, closed) for kind, s, e, parent, closed, _anc in regions],
        [LexHeredoc(*op) for op in ops],
        sorted(candidates, key=lambda c: (c.start, c.end)),
        unopened,
        tail_start,
        used,
        rounds,
    )
    if ambiguous:
        lex_map.ext_lines = tuple(sorted(_lex_pass_ext_lines.items()))
        _note_extglob_lines(text, lex_map)
    if len(_LEX_CACHE) >= _LEX_CACHE_LIMIT:
        del _LEX_CACHE[next(iter(_LEX_CACHE))]
    _LEX_CACHE[key] = lex_map
    if bodies and all(op.body_start is None for op in lex_map.heredocs):
        _LEX_CACHE[(text, mode, False, extglob)] = lex_map
    return lex_map


# --- Position map, masked view and value restoration (FR7) -----------------
#
# The text _TrackingLexer reads is not the text the lexer read: a substitution
# became marker residue, and the content of an ANSI-C quote, a parameter or
# arithmetic expansion is hidden from shlex, which would read it differently
# from bash. Three coordinate systems therefore meet here: O (the command
# chunk), S (O without real heredoc bodies) and M (S with top-level
# substitutions replaced by marker residue). A _PositionMap translates between
# two neighbours; a _MarkedText carries M, its map back to S, and the masked
# view of M that shlex reads.


class _PositionMap:
    """Position translation between two texts, OLD and NEW, as an ordered
    list of SEGMENTS `(kind, old_start, old_end, new_start, new_end, ref)`
    covering both texts end to end without a gap.

    A `copy` segment is a run of characters carried verbatim: both ranges have
    one length and a position inside it moves by a constant shift, so a
    round trip returns the same position and the same character. A `replace`
    segment is a range that has no character-level counterpart -- a removed
    heredoc body (its NEW range is empty, REF the HeredocRecord) or a marked
    substitution (its NEW range the marker residue, whatever length that has,
    REF the span): every position inside either range maps to the whole of the
    other, never to a single position in it. Nothing is promised across
    replaced segments beyond the order being kept.

    to_new(pos) is ("copy", new_pos) or ("replace", new_start, new_end, ref);
    to_old(pos) is ("copy", old_pos) or ("replace", old_start, old_end, ref).
    A position at or past the end of the text maps to the other text's end.
    Building the map is linear in the number of segments, a lookup one
    bisect (destructive-guard-unified-lexer, position map contract)."""

    __slots__ = ("segments", "old_len", "new_len", "_old_starts", "_new_starts")

    def __init__(self, segments, old_len, new_len):
        self.segments = segments
        self.old_len = old_len
        self.new_len = new_len
        self._old_starts = [seg[1] for seg in segments]
        self._new_starts = [seg[3] for seg in segments]

    def to_new(self, pos):
        if pos >= self.old_len:
            return ("copy", self.new_len)
        kind, old_start, _old_end, new_start, new_end, ref = self.segments[
            bisect.bisect_right(self._old_starts, pos) - 1
        ]
        if kind == "copy":
            return ("copy", new_start + pos - old_start)
        return ("replace", new_start, new_end, ref)

    def to_old(self, pos):
        if pos >= self.new_len:
            return ("copy", self.old_len)
        # Of several segments sharing a start (an empty replaced range in
        # NEW), the last one is the one that holds POS.
        kind, old_start, old_end, new_start, _new_end, ref = self.segments[
            bisect.bisect_right(self._new_starts, pos) - 1
        ]
        if kind == "copy":
            return ("copy", old_start + pos - new_start)
        return ("replace", old_start, old_end, ref)


def _identity_map(length):
    """The map of a text onto itself."""
    segments = [("copy", 0, length, 0, length, None)] if length else []
    return _PositionMap(segments, length, length)


_PRIVATE_USE = re.compile("[-\U000f0000-\U000ffffd\U00100000-\U0010fffd]")


def _mask_char_for(*texts):
    """A private-use character that occurs in none of TEXTS: the mask the
    masked view writes over hidden content. shlex reads it as an ordinary
    word character (not whitespace, a quote, an escape, a punctuation
    character or a commenter), and it differs from every marker character this
    module uses. Chosen per text so a command that itself holds private-use
    characters cannot collide with it; restoration is by position and never
    searches the text for the mask."""
    present = set()
    for text in texts:
        present.update(_PRIVATE_USE.findall(text))
    for first, last in ((0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD)):
        for code in range(first, last + 1):
            ch = chr(code)
            if ch not in present:
                return ch
    raise LexBudgetExceeded()


def _merge_ranges(ranges):
    """RANGES -- (start, end) pairs -- sorted, with overlapping ones joined."""
    merged = []
    for start, end in sorted(ranges):
        if merged and start < merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _map_copy_ranges(posmap, ranges):
    """The parts of RANGES (sorted, disjoint ranges of OLD) that lie in copy
    segments, as ranges of NEW. A part inside a replaced segment has no
    counterpart and is dropped: marker residue is never masked."""
    segments = posmap.segments
    out = []
    for lo, hi in ranges:
        k = max(bisect.bisect_right(posmap._old_starts, lo) - 1, 0)
        while k < len(segments):
            kind, old_start, old_end, new_start, _new_end, _ref = segments[k]
            if old_start >= hi:
                break
            if kind == "copy":
                a = max(lo, old_start)
                b = min(hi, old_end)
                if a < b:
                    out.append((new_start + a - old_start, new_start + b - old_start))
            k += 1
    return out


class _MarkedText:
    """The text _TrackingLexer reads, with everything needed to read it
    back (FR7; IMPLEMENTATION.md "Masked view and value restoration").

    - SOURCE: the text the lexer read (S). TEXT: SOURCE with substitutions
      replaced by marker residue (M). POSMAP: the S-to-M _PositionMap.
    - VIEW: TEXT's masked view, as long as TEXT. Every character inside a
      region whose content shlex would read differently from bash
      (ansi-c-quote, parameter-expansion, the three arithmetic kinds) is
      MASK_CHAR, and so is the quote character of a `$'` settled as not
      opened (P4); comment text is blank up to, not including, its newline.
      Marker residue is never masked, so the existing marker mechanism still
      yields the same unresolved / substitution_only flags.
    - MASK_RANGES: the (start, end) ranges of TEXT that VIEW masks, sorted.
      Values are restored from them by position, never by searching a text
      for the mask character.
    - SUBSCRIPT_RANGES: the (start, end) ranges of TEXT that are the array
      subscripts the lexer read (the `array-subscript` regions), sorted. A
      subscript read across a newline is one word: the parse-failure path of
      _lex_layout() splits a chunk outside them only.
    - TAIL_START: the lexer's tail start for SOURCE (LexMap.tail_start) as an
      offset of TEXT -- a tail inside a replaced substitution lands on that
      substitution's marker -- or None without one. Statement shaping compares
      it with where each statement of TEXT begins (round 2 deferred, task0001).

    Built from the lexer's map of SOURCE alone: no stage that reads VIEW
    classifies a character itself."""

    __slots__ = (
        "source", "text", "posmap", "view", "mask_char", "mask_ranges",
        "subscript_ranges", "tail_start", "_mask_starts", "_quote_starts",
        "_quote_ends",
    )

    def __init__(self, source, text, posmap):
        lexmap = lex_shell(source, "shell", False)
        self.tail_start = (
            None if lexmap.tail_start is None else posmap.to_new(lexmap.tail_start)[1]
        )
        masked = []
        blanked = []
        quoted = []
        subscripts = []
        for region in lexmap.regions:
            kind = region.kind
            if kind in LEX_MASKED_KINDS:
                masked.append((region.start, region.end))
                if kind == "array-subscript":
                    subscripts.append((region.start, region.end))
            elif kind == "comment":
                blanked.append((region.start, region.end))
            if kind in LEX_QUOTE_KINDS:
                quoted.append((region.start, region.end))
        for pos in lexmap.unopened:
            if source.startswith("$'", pos):
                masked.append((pos + 1, pos + 2))
            elif source[pos] in "'\"":
                # A quote character left literal by a tail source (rework
                # round 1, task0005): shlex must not open a quote at it.
                masked.append((pos, pos + 1))
        for op in lexmap.heredocs:
            if op.quoted:
                # The quote characters of `<<'EOF'` are quote delimiters of
                # the delimiter word, though not a region of their own.
                quoted.append((_heredoc_word_start(source, op.start), op.end))
        mask_ranges = _map_copy_ranges(posmap, _merge_ranges(masked))
        blank_ranges = _map_copy_ranges(posmap, _merge_ranges(blanked))
        subscript_ranges = _map_copy_ranges(posmap, _merge_ranges(subscripts))
        quote_ranges = []
        for lo, hi in _merge_ranges(quoted):
            start = posmap.to_new(lo)
            if start[0] != "copy":
                continue  # inside a marked substitution: that is its own chunk
            end = posmap.to_new(hi - 1)
            quote_ranges.append((start[1], end[1] + 1 if end[0] == "copy" else end[2]))
        mask_char = _mask_char_for(source, text)
        chars = list(text)
        for lo, hi in blank_ranges:
            chars[lo:hi] = " " * (hi - lo)
        for lo, hi in mask_ranges:
            chars[lo:hi] = mask_char * (hi - lo)
        self.source = source
        self.text = text
        self.posmap = posmap
        self.view = "".join(chars)
        self.mask_char = mask_char
        self.mask_ranges = mask_ranges
        self.subscript_ranges = subscript_ranges
        self._mask_starts = [lo for lo, _hi in mask_ranges]
        self._quote_starts = [lo for lo, _hi in quote_ranges]
        self._quote_ends = [hi for _lo, hi in quote_ranges]

    @classmethod
    def plain(cls, text):
        """TEXT as it stands: nothing marked, nothing removed."""
        return cls(text, text, _identity_map(len(text)))

    def masked_parts(self, start, end):
        """The parts of TEXT[START:END] that VIEW masks, in order."""
        ranges = self.mask_ranges
        out = []
        k = max(bisect.bisect_right(self._mask_starts, start) - 1, 0)
        while k < len(ranges):
            lo, hi = ranges[k]
            if lo >= end:
                break
            if hi > start:
                out.append((max(lo, start), min(hi, end)))
            k += 1
        return out

    def touches_quote(self, start, end):
        """Whether TEXT[START:END] holds a quote region or a quote
        delimiter of any kind (single, double, ANSI-C, locale), one nested
        in an expansion included."""
        k = bisect.bisect_right(self._quote_starts, end - 1) - 1
        return k >= 0 and self._quote_ends[k] > start

    def restore(self, raw, start, end):
        """The inspection value of the token shlex read as RAW from
        TEXT[START:END] of VIEW: RAW with its mask characters -- one for each
        masked position of the span, in order -- given back their original
        characters. A span without masked positions keeps RAW exactly. No
        value leaves here holding the mask character."""
        parts = self.masked_parts(start, end)
        if not parts:
            return raw
        fill = "".join(self.text[lo:hi] for lo, hi in parts)
        pieces = raw.split(self.mask_char)
        if len(pieces) - 1 != len(fill):
            # shlex did not carry every hidden character into the token; the
            # span's own text is the value that is never wrong.
            return self.text[start:end]
        out = [pieces[0]]
        for ch, piece in zip(fill, pieces[1:]):
            out.append(ch)
            out.append(piece)
        return "".join(out)


def _tokenize_marked(marked, layout=True):
    """Tokenize MARKED's masked view with _TrackingLexer and return
    [(Tok, start, end)], START and END being the token's span in
    MARKED.text.

    LAYOUT (the default) is the lexing pass of _lex_layout(): newline and
    the operator characters are punctuation, so statements stay separated.
    Without it the view is split into plain words, the way tokens() reads a
    segment. Comments never reach the tokenizer (shlex's own commenters are
    off): the view has them blank.

    Each Tok's value is restored from MARKED (restore()), is_operator comes
    from the lexer's own state, and quoted is True when the token's span holds
    a quote region or quote delimiter of any kind. Raises ValueError when the
    view does not tokenize (an unclosed quote, a trailing backslash)."""
    view = marked.view
    if layout:
        lex = _TrackingLexer(view, posix=True, punctuation_chars=PUNCTUATION)
        lex.whitespace = " \t\r"
    else:
        lex = _TrackingLexer(view, posix=True)
    lex.whitespace_split = True
    lex.commenters = ""
    whitespace = lex.whitespace
    size = len(view)
    out = []
    previous_end = 0
    while True:
        raw = lex.get_token()
        if raw is None or raw == lex.eof:
            break
        # last_end is where the lexer's input stands once the token is whole:
        # past the character that ended it (whitespace, consumed; or the next
        # character, pushed back for the following token), unless the input
        # ended with the token (state None).
        end = lex.last_end if lex.state is None else lex.last_end - 1
        start = previous_end
        while start < size and view[start] in whitespace:
            start += 1
        previous_end = end
        value = marked.restore(raw, start, end)
        quoted = lex.last_was_quoted or marked.touches_quote(start, end)
        out.append((Tok(value, lex.last_was_operator, quoted=quoted), start, end))
    return out


def lex_segments(chunk):
    """Split a chunk into statements, each returned as (tokens, lexed, sep).

    Separators only count when they sit OUTSIDE quotes, and telling those
    apart is the whole reason shlex does the splitting rather than a regex.
    `echo 'a; rm -rf /x'` is one statement headed by `echo`; a quote-blind
    split reads it as two and finds a recursive delete in the second, which
    denied a command that deletes nothing. Literal command text like that
    shows up constantly in generated docs, tests, and commit messages.

    CHUNK is a str or a _MarkedText (a chunk whose substitutions are already
    marker residue, with the masked view built from the lexer's map of it).
    shlex reads only the masked view, so a separator, a `<<` or a quote
    inside an ANSI-C quote, a parameter or arithmetic expansion, or a
    comment never reaches it as syntax (destructive-guard-unified-lexer
    FR1-FR3, FR5, FR7).

    LEXED is True on this path: each returned token is a Tok, carrying (as
    `.is_operator`) whether shlex read it from bare operator syntax or from
    a word/quoted span — the signal split_redirects() needs to tell a real
    `>` apart from a quoted string that merely looks like one — and (as
    `.quoted`, task0004) whether the token's span holds a quote of any kind,
    the analogous signal `_shape_leading()` needs to tell a bare
    `case`/reserved word apart from a quoted string that merely matches its
    text (`.is_operator` cannot do this for a word: neither a bare nor a
    quoted letter-word ever enters the punctuation-sticky state). A Tok's
    value is the text of its span: characters hidden from shlex are given
    back, so no value holds the mask character.

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
    through unexamined would be a hole rather than a nuisance. The words of
    each fallback statement come from tokens(), which reads them through the
    lexer too: a comment is never part of a word there either.

    The lexing itself lives in _lex_layout(), which can also report where
    each statement sits in CHUNK; this function is its segments only.
    """
    return _lex_layout(chunk, False)[0]


def _lex_segments_with_ends(chunk):
    """lex_segments()'s result plus SEG_ENDS, the character offset in the
    lexed text (CHUNK itself when it is a str, its marked TEXT when it is a
    _MarkedText) at which each statement's own separator starts — the offset
    where the statement ends — and the length of that text for the trailing
    statement. A statement's number is its index in the result, so an offset
    maps to "how many statements end at or before it" by bisecting SEG_ENDS
    (statements() uses that to place a heredoc body between statements).
    SEG_ENDS is None on the parse-failure fallback, whose statements carry
    no offsets, and whenever _lex_layout() reports no LAYOUT. It is read off
    LAYOUT: a statement's separator is the bare operator text that ends just
    where the next statement begins. Everything lex_segments() documents
    applies here unchanged; reading offsets does not change which statements
    or tokens come out."""
    segments, starts, _operators = _lex_layout(chunk, True)
    if starts is None:
        return segments, None
    seg_ends = [
        starts[k + 1] - len(sep) for k, (_, _, sep) in enumerate(segments[:-1])
    ]
    seg_ends.append(len(chunk.text if isinstance(chunk, _MarkedText) else chunk))
    return segments, seg_ends


def _split_outside_subscripts(text, ranges):
    """SEGMENT_SPLIT.split(TEXT), except that a separator inside one of RANGES
    -- sorted, disjoint (start, end) ranges of TEXT, the array subscripts the
    lexer read (_MarkedText.subscript_ranges) -- does not split. The
    parse-failure path of _lex_layout() splits by this: a subscript that
    closes on a later line is one word (`a[1` + newline + `]=x`), and
    each half read alone is a subscript the lexer cannot settle, which would
    turn the lines after it into an `ask` instead of the verdict they have
    (round 2 deferred, FR1). With no RANGES it is SEGMENT_SPLIT.split(TEXT)."""
    if not ranges:
        return SEGMENT_SPLIT.split(text)
    out = []
    start = 0
    k = 0
    for m in SEGMENT_SPLIT.finditer(text):
        pos = m.start()
        while k < len(ranges) and ranges[k][1] <= pos:
            k += 1
        if k < len(ranges) and ranges[k][0] <= pos:
            continue
        out.append(text[start:pos])
        start = m.end()
    out.append(text[start:])
    return out


def _lex_layout(chunk, track):
    """lex_segments()'s one lexing pass: (segments, layout, operators).
    SEGMENTS is lex_segments()'s own return value, unchanged.

    CHUNK is a str or a _MarkedText; the offsets below are offsets in the
    text shlex's view was made from (a _MarkedText's TEXT), which is exactly
    as long as that view.

    With TRACK, LAYOUT says where the statements sit in that text as a list:
    LAYOUT[k] is the offset where statement k begins, which is the end of the
    separator before it (0 for the first). Statement k is everything from
    LAYOUT[k] up to LAYOUT[k + 1], its own terminating separator included, or
    to the end of the text for the last one. LAYOUT is None when the chunk
    does not lex, or when a separator's offset could not be confirmed against
    the text.

    OPERATORS, with TRACK, is the record of heredoc operator starts: {k: the
    offsets, ascending, of every `<<` that statement k holds as bare,
    unquoted operator syntax}. Only a token the lexer read from operator
    syntax is searched, so a `<<` inside a quoted word, a comment, an
    expansion or an arithmetic region never enters the record; and a token
    fused with neighbouring punctuation (`;<<`, `(<<`) is searched piece by
    piece, each piece attributed to the statement it falls in. A statement
    holding no such `<<` has no entry. OPERATORS is None exactly when LAYOUT
    is.

    Separators are recognised once, here. Whatever places a heredoc's host
    statement reads these offsets rather than counting separator characters
    on its own, so a redirection (`2>&1`, `&>`, `>|`) or an escape (an
    escaped `;` or `&`, a backslash before a newline) that this pass does
    not count as a separator can never be counted as one by a second
    rule."""
    marked = chunk if isinstance(chunk, _MarkedText) else _MarkedText.plain(chunk)
    text = marked.text
    try:
        toks = _tokenize_marked(marked)
    except ValueError:
        return [
            (tokens(seg), False, None)
            for seg in _split_outside_subscripts(text, marked.subscript_ranges)
            if seg.strip()
        ], None, None

    out, current = [], []
    starts = [0]
    operators = {}
    confirmed = track
    for t, tok_start, tok_end in toks:
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
        # Only a bare operator token is the characters it was read from, so
        # only its offsets can be taken from the lexer's position -- and a
        # separator, like a heredoc operator's `<<`, is always inside one.
        base = None
        if (
            confirmed
            and t.is_operator
            and (any(c in SEGMENT_CHARS for c in t) or "<<" in t)
        ):
            if text[tok_start:tok_end] == t:
                base = tok_start
            else:
                confirmed = False
        offset = 0
        for seg in segs:
            seg_start = None if base is None else base + offset
            offset += len(seg)
            if (
                seg
                and all(c in SEGMENT_CHARS for c in seg)
                and getattr(seg, "is_operator", False)
            ):
                out.append((current, True, seg))
                current = []
                if seg_start is not None:
                    starts.append(seg_start + len(seg))
            else:
                current.append(seg)
                # The statement under construction is the next one to be
                # appended to OUT. Every `<<` of the piece is recorded,
                # overlapping ones included: each is `<<` in bare operator
                # text, which is all the record says.
                if seg_start is not None and getattr(seg, "is_operator", False):
                    k = seg.find("<<")
                    while k != -1:
                        operators.setdefault(len(out), []).append(seg_start + k)
                        k = seg.find("<<", k + 1)
    out.append((current, True, None))
    if not confirmed or len(starts) != len(out):
        return out, None, None
    return out, starts, operators


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
    """The literal script a shell-invocation segment (TOKS) will execute —
    extract_shell_payload_anchored()'s first value, None when there is no
    such script. See that function for the contract."""
    return extract_shell_payload_anchored(toks, lexed, quoted_toks)[0]


def extract_shell_payload_anchored(toks, lexed, quoted_toks=None):
    """Return (payload, anchor): the literal script a shell-invocation
    segment (TOKS) will execute via `-c`, `eval`, or a here-string (`<<<`)
    redirect aimed at a shell word, and the token of TOKS that script was
    taken from — the payload word (for `eval`, its first argument) whose
    position in the original command string is where the payload's own
    statements are anchored (statements() origin positions). Returns
    (None, None) when the segment is not such an invocation, its
    payload is not a single literal token statements() can push back onto
    its own queue and re-scan like any other statement, or (task0001 FR4/
    FR7) the payload argument position is a substitution enclosed in
    quotes. ANCHOR is always one of the very objects in TOKS (never a
    rebuilt copy), so statements() finds it again by identity.

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
        return None, None

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
        if marked_args:
            return " ".join(marked_args), marked_args[0]
        return None, None
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
                    return marked_args[idx + 1], marked_args[idx + 1]
                if idx + 1 < len(quoted_args) and QUOTED_MARK in quoted_args[idx + 1]:
                    return None, None
                promoted = marked_args[_payload_index(args, idx + 1)]
                return promoted, promoted
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
                        return marked_redirects[i + 1], marked_redirects[i + 1]
                    if i + 1 < len(quoted_redirects) and QUOTED_MARK in quoted_redirects[i + 1]:
                        return None, None
                    j = _payload_index(words, 1)
                    if (
                        j > 0
                        and j < len(words)
                        and not getattr(words[j], "substitution_only", False)
                    ):
                        return marked_words[j], marked_words[j]
                    return marked_redirects[i + 1], marked_redirects[i + 1]
                i += 2
            else:
                i += 1
    return None, None


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


def _strip_heredocs_mapped(chunk):
    """(CHUNK with every real heredoc body removed, the ordered list of
    HeredocRecord, the original-to-stripped _PositionMap). Which `<<` is a
    real operator, and which lines are its body, is lex_shell()'s judgment
    (P6, FR8): this function only cuts the lines the lexer reported.

    Each removed body -- the body lines and the delimiter line, through its
    line end -- is one `replace` segment of the map (its stripped range
    empty, its REF the body's HeredocRecord); the text between bodies is
    copied verbatim. Construction is linear in the chunk."""
    lexmap = lex_shell(chunk, "shell")
    ops = [op for op in lexmap.heredocs if op.body_start is not None]
    if not ops:
        return chunk, [], _identity_map(len(chunk))
    close_ends = [op.close_end for op in ops]
    removed_before = [0]
    for op in ops:
        removed_before.append(removed_before[-1] + op.close_end - op.body_start)

    def stripped_pos(pos):
        # Bodies removed from before POS: the ones that end at or before it.
        return pos - removed_before[bisect.bisect_right(close_ends, pos)]

    out = []
    records = []
    segments = []
    cursor = 0
    new_cursor = 0
    for op in ops:
        record = HeredocRecord(
            chunk[op.body_start : op.body_end],
            stripped_pos(op.start),
            stripped_pos(op.end),
            op.quoted,
        )
        records.append(record)
        if op.body_start > cursor:
            out.append(chunk[cursor : op.body_start])
            length = op.body_start - cursor
            segments.append(
                ("copy", cursor, op.body_start, new_cursor, new_cursor + length, None)
            )
            new_cursor += length
        segments.append(
            ("replace", op.body_start, op.close_end, new_cursor, new_cursor, record)
        )
        cursor = op.close_end
    if cursor < len(chunk):
        out.append(chunk[cursor:])
        length = len(chunk) - cursor
        segments.append(
            ("copy", cursor, len(chunk), new_cursor, new_cursor + length, None)
        )
        new_cursor += length
    return "".join(out), records, _PositionMap(segments, len(chunk), new_cursor)


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
    - Only a REAL operator is collected: a `<<WORD` inside single quotes,
      double quotes, a `#`-comment, a parameter expansion or an arithmetic
      region is not syntax at all, so it opens no heredoc and consumes no
      body -- it stays in the chunk as ordinary text and the lines after it
      stay where they are, to be read by their actual syntax. A real
      operator inside a command substitution stays one, even when the
      substitution sits in a double-quoted string. The body lines of a real
      operator change no lexer state, so a quote character or `#` inside one
      opens nothing in the command text after its delimiter line.

    Which operators are real, and which lines are their bodies, is decided
    by lex_shell() (destructive-guard-unified-lexer FR8); nothing here
    classifies a character. The delimiter-line lookup is the lexer's indexed
    one: finding (or ruling out) an operator's own closing line is a bisect
    into the candidate lines of that one word, never a scan of everything
    after the operator, so an unterminated operator does not cost a fresh
    pass over the remaining input (NFR3, TM-5).

    _strip_heredocs_mapped() is the same result plus the position map from
    the original chunk to the stripped one."""
    stripped, records, _omap = _strip_heredocs_mapped(chunk)
    return stripped, records


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


def _git_global_options_end(args):
    """The index in ARGS -- everything after the `git` command word -- where
    `git`'s own global options end: `-C`/`-c`/`--git-dir`/`--work-tree`/
    `--namespace`/`--config-env` with their value (a separate token, or
    attached with `=`) and the value-less options in GIT_GLOBAL_BOOLEAN_FLAGS
    are passed over left to right. Shared by _git_is_data(), which reads the
    word at that index as the subcommand, and by the FR6 skipped-word sink
    check, which reads ARGS[:index] as the words the resolution skipped.
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
    return i


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
    i = _git_global_options_end(args)
    n = len(args)
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
# scan_structure() is the structural reading every caller that needs to find
# comment spans, quoted spans, or substitution spans shares: chunk processing
# (statements() itself), heredoc operator collection (strip_heredocs()) and
# body-substitution extraction (_extract_heredoc_body_substitutions()). Where
# a substitution starts and ends is lex_shell()'s judgment (the unified lexer
# above), so a heredoc's destination, and every other caller, agree by
# construction rather than by two independent re-lexes drawing the same line
# differently.

_SQ_PAREN_TOKEN = re.compile(r"\$\(|[()]")


def _single_quoted_sub_closes(text, start, limit):
    """Closing parenthesis of every `$(` in TEXT[START:LIMIT], found in ONE
    forward pass -- the rest of one single-quote or ANSI-C-quote region, for
    the single-quote substitution candidates of lex_shell() (P8, FR9), LIMIT
    being its closing quote (or the end of TEXT when the quote is never
    closed). This is the candidate rule's own helper: only
    _lex_quote_candidates() calls it.
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
    """Component 1. The structural reading of TEXT (a text and an outer MODE,
    `shell` or `heredoc-body`), taken from lex_shell(): this function keeps
    the span bookkeeping and the choice of which lexer output each search
    policy reads, and classifies no character itself
    (destructive-guard-unified-lexer layer 3). Returns (spans, parent_of,
    unmatched, opaque, containing_span):

    - SPANS: every `$( … )`/`` ` … ` ``/`<( … )`/`>( … )` span found, at every
      nesting level -- inside a parameter expansion, an arithmetic expansion
      or a double-quoted string included (FR4). A process substitution is a
      substitution (D5): its span starts at the `<` or `>`, and its body is
      its own chunk.
    - PARENT_OF: {span: its immediate enclosing span, or None} -- a span
      strictly containing it with nothing tighter in between.
    - UNMATCHED: start offsets of an opener never closed by end of text.
    - OPAQUE: TOP-LEVEL ranges inert for statement-separator counting: a
      quoted span, a comment span, a parameter-expansion or arithmetic
      region, or a top-level substitution span (mode `shell` only --
      `heredoc-body` mode returns `[]` here, since quotes and comments are
      literal at that mode's own top level and no caller needs separator
      counting over heredoc-body text). No caller counts separators from
      these ranges any more: which statement a position belongs to is read
      from lex_segments() itself (_lex_layout()), so there is one separator
      rule, not two.
    - CONTAINING_SPAN: {checkpoint position: the innermost span enclosing
      it, or None} for every position in CHECKPOINTS -- the position-only way
      a heredoc operator is matched to the substitution (if any) that holds
      it, with no marker text ever written into TEXT (Component 3: "no
      marker characters are inserted... a control character in the input has
      no special meaning").

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
    4. An unterminated span is reported as unterminated (in UNMATCHED); it is
       not among SPANS and extends to the end of the text; it is never
       truncated silently.
    5. Outside quotes, a backslash-escaped `'` or `"` is a literal
       character, never a quote start (C2).

    HONOR_SINGLE_QUOTES defaults to True, which is postcondition 2 exactly
    (real shell semantics: single quotes suppress expansion, so a `$(`/
    backtick inside them opens no span) -- used by every heredoc-facing
    caller (chunk-wide `chunk_scan`, `_statement_info_at()`,
    `_extract_heredoc_body_substitutions()`), since Component 3/4's
    statement/case-state analysis needs the position of a REAL shell
    separator, which a single-quoted `$(`/backtick can never introduce.
    Passing False keeps every other rule identical but also reports the
    lexer's single-quote substitution candidates (P8, FR9: the `$(`/backtick
    ranges the pre-change broad search found inside every single-quote and
    ANSI-C-quote region) -- used ONLY by `statements()`'s own general,
    non-heredoc substitution discovery (the span list
    `_mark_substitutions()`/`_mark_quoted_substitutions()` mark and that
    `pending` recurses into), which predates this task and must keep its own
    pre-existing, quote-agnostic reach: check_rm() and the other per-token
    checks read `.unresolved` as "this token's value was never fully
    present, regardless of how the substitution sitting in it was written"
    -- a static, conservative reading that intentionally does not depend on
    whether a real shell would actually expand that spot, the same way
    UNRESOLVED_EXPANSION's own raw-text search (check_rm() step 3) never did
    either.
    """
    lexmap = lex_shell(text, mode, False)
    regions = lexmap.regions
    # Per region, the index of the nearest CLOSED substitution around it:
    # only a closed substitution is a span, so an unterminated one is no
    # parent (its content is reported as if it sat at the level outside).
    around = [None] * len(regions)
    span_of = {}
    spans = []
    unmatched = []
    for index, region in enumerate(regions):
        parent = region.parent
        if parent is not None:
            parent_region = regions[parent]
            around[index] = (
                parent
                if parent_region.kind in LEX_SUBSTITUTION_KINDS and parent_region.closed
                else around[parent]
            )
        if region.kind in LEX_SUBSTITUTION_KINDS:
            if region.closed:
                span = (region.start, region.end)
                span_of[index] = span
                spans.append(span)
            else:
                unmatched.append(region.start)
    parent_of = {}
    for index, span in span_of.items():
        enclosing = around[index]
        parent_of[span] = span_of[enclosing] if enclosing is not None else None

    if not honor_single_quotes:
        for candidate in lexmap.candidates:
            span = (candidate.start, candidate.end)
            spans.append(span)
            enclosing = candidate.enclosing
            if enclosing is not None and not regions[enclosing].closed:
                enclosing = around[enclosing]
            parent_of[span] = span_of[enclosing] if enclosing is not None else None

    opaque = []
    if mode == "shell":
        opaque = [
            (region.start, region.end)
            for region in regions
            if region.parent is None and region.kind in LEX_OPAQUE_KINDS
        ]

    containing_span = {}
    if checkpoints:
        # The innermost substitution (open or not) strictly around each
        # checkpoint; one sweep over the regions, which are ordered by start.
        subs = [
            (index, region)
            for index, region in enumerate(regions)
            if region.kind in LEX_SUBSTITUTION_KINDS
        ]
        stack = []
        cursor = 0
        for pos in sorted(set(checkpoints)):
            while cursor < len(subs) and subs[cursor][1].start < pos:
                stack.append(subs[cursor])
                cursor += 1
            while stack and stack[-1][1].end <= pos:
                stack.pop()
            containing_span[pos] = span_of.get(stack[-1][0]) if stack else None
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
    nested levels are found in turn when THAT chunk is scanned next.

    BODIES is a list of (inner text, start offset in TEXT of the whole
    substitution — its `$(` or backtick), in ascending offset order: the
    caller anchors each queued chunk at that offset inside the heredoc body
    (statements() origin positions)."""
    spans, parent_of, unmatched, _opaque, _containing = scan_structure(
        text, mode="heredoc-body"
    )
    if unmatched:
        return [], True
    top_spans = _top_level_spans(spans, parent_of)
    return [(_span_inner(text, span)[0], span[0]) for span in top_spans], False


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


# --- FR6: a sink among the words the command-word resolution skipped ------
#
# A statement's command word is found by passing over VAR=value assignments,
# WRAPPERS with their options and option values, and `git`'s global options
# with theirs. `GIT_EDITOR=bash git commit -e -F - <<'EOF'` therefore reads as
# `git` -- a data command -- while the shell it hands the body to is named in
# a word that was passed over. These helpers collect those words once per
# statement and decide whether any of them names a sink.


def _collect_skipped_words(words, end, skipped):
    """Add to SKIPPED (a _SkippedWords) every assignment / wrapper word that
    _skip_assignments_and_wrappers() passes over in WORDS[:END], walking the
    prefix once left to right. Anything else in the prefix (a grouping
    token, a reserved word, a case pattern) is stepped over without being
    collected: only the three kinds of word FR6 names count as skipped.
    """
    i = 0
    while i < end:
        j = _skip_assignments_and_wrappers(words, i, end, skipped)
        i = j if j > i else i + 1


def _skipped_word_has_sink(word):
    """Whether SHELL_SINK, applied exactly as it is applied to a chunk, finds
    a sink in WORD as written, in the part after its first `=`, or in the
    leading word of that part -- and in each of those with every quote and
    backslash character removed (`core.editor=b'a'sh` is `bash` once the
    shell that git hands it to has resolved the quoting)."""
    forms = [word]
    if "=" in word:
        value = word.split("=", 1)[1]
        forms.append(value)
        leading = value.split(None, 1)
        if leading:
            forms.append(leading[0])
    for form in forms:
        if SHELL_SINK.search(form) or SHELL_SINK.search(_strip_quote_chars(form)):
            return True
    return False


def _skipped_words_make_undetermined(words_only, lead, shaped_words, word, args):
    """FR6: whether the words skipped before this statement's command WORD
    make its destination undetermined -- an `env` -S/--split-string option
    in any spelling, or a sink in any skipped word. WORDS_ONLY[:LEAD] is
    what statement shaping passed over; SHAPED_WORDS may still start with
    assignments/wrappers that head() skips; and for `git`, ARGS' leading
    global options and their values count as skipped too."""
    skipped = _SkippedWords()
    _collect_skipped_words(words_only, lead, skipped)
    skip_index, _, _ = _skip_to_command_word(shaped_words)
    _collect_skipped_words(shaped_words, skip_index, skipped)
    if word == "git":
        skipped.words.extend(args[: _git_global_options_end(args)])
    return skipped.env_split or any(_skipped_word_has_sink(w) for w in skipped.words)


def _statements_in_tail(marked, starts, count):
    """For each of the COUNT statements of MARKED's lexing, whether it begins
    at or after the chunk's tail start (round 2 deferred, task0001, FR2): the
    lexer's tail start for the chunk's text (_MarkedText.TAIL_START, an offset
    of the marked text) against STARTS, where each statement begins in that
    same marked text (_lex_layout()'s layout; None when there is none). A
    statement in the tail opens no case construct with `case`
    (_shape_leading()'s TAIL), the way the lexer opens none after a tail
    source. Without a layout nothing says where a statement begins, so every
    statement is taken to lie in a tail the chunk has -- the reading that
    keeps more of it inspected."""
    tail = marked.tail_start
    if tail is None:
        return [False] * count
    if starts is None:
        return [True] * count
    return [start >= tail for start in starts]


def _build_statement_table(chunk, marked_chunk):
    """Component 3. ONE lexing pass of MARKED_CHUNK (CHUNK with every
    top-level substitution already blanked by _mark_substitutions()),
    yielding the same per-statement shaping statements() itself computes
    (case state carried statement-by-statement via _shape_leading(), the
    same fused-closer/redirect/wrapper handling, and -- SC1's git/gh
    condition -- _git_is_data() for a `git` command word, _git_alias_risk()
    for a `gh` one, task0003) -- built once per chunk and read by every
    heredoc's destination decision instead of each heredoc re-lexing the
    chunk on its own.

    Returns (TABLE, STARTS, OPERATORS): STARTS is _lex_layout()'s statement
    start offsets for the same lexing pass and OPERATORS its record of the
    heredoc operator starts each statement holds (both None when they are
    unavailable), in MARKED_CHUNK's own coordinates."""
    segments, starts, operators = _lex_layout(marked_chunk, True)
    in_tail = _statements_in_tail(marked_chunk, starts, len(segments))
    case_stack = []
    table = []
    for index, (toks, lexed, sep) in enumerate(segments):
        stripped = _strip_unresolved_marks(toks)
        if lexed:
            fused = _split_fused_closer_redirects(stripped)
            words_only, redirects = split_redirects(fused, lexed)
            # Snapshotted BEFORE _shape_leading() mutates case_stack, so a
            # leading `esac` on THIS statement is judged against the
            # case-tracking state this statement actually started in (see
            # _leading_group_closer()'s own docstring).
            case_stack_before = list(case_stack)
            lead = _shape_leading(words_only, case_stack, in_tail[index])
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
            # FR6: a sink among the skipped words (or an `env` split-string)
            # makes a would-be data word undetermined. A word that is itself
            # a sink stays a sink -- only a non-sink command word is
            # downgraded here.
            if (
                word is not None
                and not SINK_WORD_RE.match(word)
                and _skipped_words_make_undetermined(
                    words_only, lead, shaped_words, word, args
                )
            ):
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
    return table, starts, operators


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


def _statement_holds_operator(operators, idx, marked_pos):
    """Whether the lex_segments() statement IDX holds the heredoc operator
    whose `<<` starts at MARKED_POS (FR2), MARKED_POS being the operator's
    position in the text the lexer saw. It does only when OPERATORS -- the
    record _lex_layout() builds in the same lexing pass -- lists that
    position for the statement: a `<<` the lexer read from bare, unquoted
    operator syntax. Anything else is False, which the caller reads as an
    undetermined destination (never data): no recorded start matches, the
    statement has no record, or the position is not one the record can
    hold. One lookup per heredoc against one statement's record (NFR3)."""
    held = operators.get(idx)
    return held is not None and marked_pos in held


def _statement_info_at(text, pos, memo_key, tables_cache, operator=False):
    """The Component 3 table (built once per TEXT, cached in TABLES_CACHE
    keyed by MEMO_KEY) plus the statement index at POS in TEXT, plus that
    table's own group-tracking and pipeline memo -- shared by every level
    of every heredoc's chain that resolves against this same TEXT.

    The statement at POS is the one lex_segments() yields for that position
    (FR1): the table is built from that very lexing pass, and the offsets of
    its statements come from the same pass (_lex_layout()), so a separator
    is a separator here exactly where it is one to lex_segments().

    OPERATOR says POS is the start of a heredoc's own `<<` operator, which
    the statement selected for it has to hold as bare operator syntax (FR2,
    _statement_holds_operator()). When it does not, or when the text does
    not lex so no statement offsets exist, None comes back, which the
    callers read as an undetermined destination -- never data."""
    cached = tables_cache.get(memo_key)
    if cached is None:
        spans, parent_of, unmatched, _opaque, _containing = scan_structure(
            text, mode="shell"
        )
        top_spans = _top_level_spans(spans, parent_of)
        marked = _mark_substitutions(text, top_spans, 0)
        table, starts, operators = _build_statement_table(text, marked)
        group_closer_of, open_groups_at, mismatched = _track_groups(table)
        cached = (
            table, group_closer_of, open_groups_at, {}, unmatched, starts,
            operators, marked.posmap, mismatched,
        )
        tables_cache[memo_key] = cached
    (
        table, group_closer_of, open_groups_at, pipe_memo, unmatched, starts,
        operators, posmap, mismatched,
    ) = cached
    if any(p < pos for p in unmatched):
        return None
    if starts is None:
        return None
    # POS in the text the lexer actually saw (substitutions replaced by their
    # markers), through the position map -- a position inside a marked
    # substitution lands on its marker -- then a bisect over the statement
    # starts: O(log n) per query against one O(n) pass shared by every
    # heredoc in TEXT (NFR3).
    marked_pos = posmap.to_new(pos)[1]
    idx = bisect.bisect_right(starts, marked_pos) - 1
    if idx >= len(table):
        return None
    if operator and not _statement_holds_operator(operators, idx, marked_pos):
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
            info = _statement_info_at(
                chunk, record.op_start, "chunk", tables_cache, operator=True
            )
            chain = [info if info is not None else _StmtInfo(parse_failed=True)]
        else:
            inner_text, inner_base = _span_inner(chunk, containing)
            local_start = record.op_start - inner_base
            host = _statement_info_at(
                inner_text, local_start, containing, tables_cache, operator=True
            )
            chain = [host if host is not None else _StmtInfo(parse_failed=True)]
            chain.extend(
                _walk_enclosing_chain(chunk, containing, parent_of, tables_cache)
            )
        destinations[index] = _decide_destination(chain)
    return destinations


def _substitution_body_range(chunk, span):
    """The part of SPAN -- a (start, end) pair from scan_structure() -- that
    marking replaces by marker residue. A command or backtick substitution is
    replaced whole. A process substitution `<( … )` / `>( … )` is replaced by
    its BODY only: the two opener characters and the closing `)` stay in the
    text, so the statement holding it still shows the opener (and the closer)
    as bare operator tokens, which is what _has_process_substitution() reads
    and what keeps `tee >(bash) <<'EOF'` a sink-bound heredoc (D5). The body
    is queued as its own chunk, like the body of a `$( … )`."""
    start, end = span
    if chunk[start] in "<>":
        return start + 2, end - 1
    return start, end


def _mark_with(chunk, top_spans, marker_for):
    """CHUNK with the body of every span in TOP_SPANS replaced by
    MARKER_FOR(span index, span), as a _MarkedText (the position map from
    CHUNK to the marked text is built here, each replaced body one `replace`
    segment whose marker may be shorter or longer than it)."""
    out = []
    segments = []
    cursor = 0
    new_cursor = 0
    for i, span in enumerate(top_spans):
        lo, hi = _substitution_body_range(chunk, span)
        if lo >= hi:
            continue  # an empty process substitution body: nothing to mark
        if lo > cursor:
            out.append(chunk[cursor:lo])
            segments.append(("copy", cursor, lo, new_cursor, new_cursor + lo - cursor, None))
            new_cursor += lo - cursor
        marker = marker_for(i, span)
        out.append(marker)
        segments.append(("replace", lo, hi, new_cursor, new_cursor + len(marker), span))
        new_cursor += len(marker)
        cursor = hi
    if cursor < len(chunk):
        out.append(chunk[cursor:])
        segments.append(
            ("copy", cursor, len(chunk), new_cursor, new_cursor + len(chunk) - cursor, None)
        )
        new_cursor += len(chunk) - cursor
    return _MarkedText(
        chunk, "".join(out), _PositionMap(segments, len(chunk), new_cursor)
    )


def _mark_substitutions(chunk, top_spans, offset_=0):
    """Blank every span in TOP_SPANS -- CHUNK's own top-level `$( … )`/
    `` ` … ` ``/`<( … )`/`>( … )` spans, Component 1's scan_structure()
    result narrowed by _top_level_spans() -- by replacing it with
    UNRESOLVED_MARK, so the word it sat in survives lexing as a token no
    matter whether the span filled the whole word or sat beside real text
    (destructive-guard-command-substitution task0001 Design Part 1, "evidence
    survives the lexing boundary"). Unlike SUBSTITUTION's own single-level,
    paren-free regex, TOP_SPANS already reflects true nesting (Component 1),
    so a chunk whose only substitution is several levels deep is still marked
    correctly here -- the nested levels are found in turn once this span's
    own inner text is queued and re-scanned as its own chunk (see call site).

    The result is a _MarkedText: the marked text, the position map from CHUNK
    to it (each marked substitution one replaced segment, whose marker may be
    longer or shorter than the substitution), and the masked view shlex reads
    (destructive-guard-unified-lexer FR7).

    A process substitution is marked by its BODY only: `<(` / `>(` and the
    closing `)` stay in the text as operator tokens, the body becomes marker
    residue. The statement holding it therefore keeps the opener evidence
    _has_process_substitution() reads (D5), while the body -- queued as its
    own chunk -- is scanned like the body of a `$(...)`.

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
    merely happens to be in range. This lets _strip_unresolved_marks() recover
    the right ALL_SUBS entry for a surviving marker by direct index lookup
    even when some other span in the same chunk never reaches the token
    stream at all (dropped whole by a comment).
    """
    return _mark_with(
        chunk,
        top_spans,
        lambda i, span: f"{UNRESOLVED_MARK}{offset_ + i}{_MARK_TERMINATOR}",
    )


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
    paragraph below). A process substitution is marked by its body only, as
    in _mark_substitutions().

    Used ONLY by extract_shell_payload() (task0001 FR4), which lexes this
    output as a second, parallel token sequence to _mark_substitutions()'s
    own — same shape, same boundaries, differing only in which marker
    character sits at a substitution's position (see QUOTED_MARK) — so it
    can read, at the payload argument position and nowhere else, whether
    that specific substitution was written enclosed in quotes. No other
    stage calls this function.
    """

    def marker_for(_i, span):
        start, end = span
        if 0 < start and end < len(chunk) and chunk[start - 1] == '"' and chunk[end] == '"':
            return QUOTED_MARK
        return UNRESOLVED_MARK

    return _mark_with(chunk, top_spans, marker_for)


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
    stream at all — which happens when a `#` comment, and any `$(...)`/
    `` `...` `` written inside it, is blanked out of the masked view before
    lexing ever produces a marker token for it; CHUNK_SUBS still
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


# --- Origin positions (destructive-guard-rm-reason-positions) ---------------
#
# statements() walks the command's own text first and then every chunk derived
# from it (substitution bodies, `-c` / eval / here-string payloads, heredoc
# bodies), in an order that has nothing to do with where those chunks were
# written. An ORIGIN POSITION is what lets a later stage put two tokens from
# different chunks back into the order they have in the original command
# string: a tuple of steps, each step a (statement index, token index, within)
# triple of ints, compared as ordinary tuples.
#
# - A chunk carries an ANCHOR: the steps that lead from the original command
#   to the place the chunk was derived from. The original command's anchor is
#   `()`.
# - A token's position is its chunk's anchor followed by one step for the
#   token itself: its statement index in the chunk, its index among that
#   statement's tokens as written (before shaping — wrappers, assignments and
#   grouping tokens included), and 0.
# - A derived chunk's anchor is the anchor of the chunk it came from followed
#   by the step of the place it was derived from (see statements()):
#   `within` is 1 + the occurrence number of a substitution inside its token
#   (after the token's own start, 0), -1 for a heredoc body (before the first
#   token of the statement that follows the operator's line), and the offset
#   inside a heredoc body for a substitution extracted from it.
#
# A shorter tuple that is a prefix of a longer one sorts first, so a token
# sorts before everything derived from inside it.

# Greater than any statement or token index a chunk can hold.
_AFTER_EVERYTHING = 1 << 30


def _token_index(toks, tok):
    """Index of TOK in TOKS: by identity first (shaping and payload
    extraction hand back the very token objects lexing produced), then by
    text, then 0 — a token a fallback shaping step rewrote cannot be found by
    identity, and any stable index serves there."""
    for i, t in enumerate(toks):
        if t is tok:
            return i
    for i, t in enumerate(toks):
        if t == tok:
            return i
    return 0


def token_position(origin, toks, tok):
    """Origin position of TOK, a token of the statement whose TOKS and
    ORIGIN statements() yielded together."""
    anchor, statement_index = origin
    return anchor + ((statement_index, _token_index(toks, tok), 0),)


def _segment_boundaries(text, opaque):
    """The START offset of every real (non-comment, non-quoted, non-
    substitution) statement-separator run in TEXT, in ascending order,
    using OPAQUE (scan_structure()'s top-level ranges) to skip inert
    regions -- ONE forward pass over the whole of TEXT. Only
    _statements_ended_by() reads it, for a chunk whose lexing fell back to
    the regex split and so has no lexer offsets."""
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


def _statements_ended_by(chunk, marked, seg_ends, opaque):
    """A function mapping a character position in CHUNK to the number of
    statements of the lexed chunk that END at or before it (their separator
    starts at or before it) — so the statement with that index is the first
    one that starts after the position.

    The statements are those statements() lexes: the chunk with its top-level
    substitutions replaced by markers, MARKED (a _MarkedText), and SEG_ENDS
    their separator offsets in its marked text (_lex_segments_with_ends()). A
    position is first moved from CHUNK to the marked text through MARKED's
    position map (a position inside a marked substitution lands on that
    substitution's marker); the count is a bisect over SEG_ENDS. When the
    chunk fell back to the regex split (SEG_ENDS None) there are no lexer
    offsets, and the count comes from _segment_boundaries() over OPAQUE (the
    chunk scan's opaque ranges) instead — best effort, and stable."""
    if seg_ends is None:
        boundaries = _segment_boundaries(chunk, opaque)
        return lambda pos: bisect.bisect_right(boundaries, pos)
    separators = seg_ends[:-1]
    posmap = marked.posmap

    def ended_by(pos):
        return bisect.bisect_right(separators, posmap.to_new(pos)[1])

    return ended_by


def _heredoc_body_step(chunk, ended_by, record, index):
    """The step a heredoc body queued whole is anchored at: the start of the
    body, which sits after everything on its operator's line and before
    anything that follows the delimiter line — before the first token of the
    first statement that starts after that line. CHUNK is the heredoc-
    stripped chunk, ENDED_BY its _statements_ended_by() function, RECORD the
    heredoc and INDEX its number among the chunk's heredocs (two operators on
    one line keep their written order)."""
    newline = chunk.find("\n", record.op_end)
    if newline == -1:
        newline = len(chunk)
    return (ended_by(newline), -1, index)


def _register_marker_positions(marker_pos, marked, anchor, statement_index):
    """Record, for every substitution marker in MARKED (one statement's
    tokens before marks are stripped), the origin position of the place the
    marker sits in this chunk. A payload chunk repeats its parent's marker
    text, so its registration — made later — refines the parent's: the
    substitution body is then anchored where the substitution sits inside
    the payload, not merely inside the payload word.

    A token can hold any byte sequence, including one that looks like a
    marker but was never produced by this module (NUL, digits, STX written
    in the command itself). When such a marker's digit run is longer than
    the interpreter's integer-from-string limit, its index cannot be
    converted: that marker is skipped, not registered, exactly as
    _strip_unresolved_marks() skips it. Registration therefore never raises
    on any token content, and the skipped marker's text is left to the
    downstream steps as it always was."""
    for token_index, tok in enumerate(marked):
        if UNRESOLVED_MARK not in tok:
            continue
        for occurrence, m in enumerate(_MARK_RE.finditer(tok)):
            try:
                index = int(m.group(1))
            except ValueError:
                continue
            marker_pos[index] = anchor + (
                (statement_index, token_index, occurrence + 1),
            )


# --- FR7: constructs that replace what a command name runs -----------------
#
# A function definition, an alias, `hash`, `enable` or a PATH assignment makes
# a data command name (`cat`, `git`) run something else -- possibly a shell
# that reads the heredoc body. No heredoc judged data in a command holding
# one of these can be trusted, so statements() turns every data judgment in
# that command into undetermined as soon as one is seen (once per hook
# invocation, in the single traversal it already makes).

# Builtins that change what a command name resolves to when they sit at
# command position.
OVERRIDE_BUILTINS = frozenset({"alias", "hash", "enable"})

# An assignment to PATH, `PATH=` or `PATH+=`. (The latter is not an
# ASSIGNMENT_PREFIX match, so it surfaces as the command word itself.)
PATH_ASSIGNMENT = re.compile(r"^PATH\+?=")


def _defines_function(words, lead):
    """Whether WORDS -- a statement's non-redirect words -- define a shell
    function at command position, in any spelling: `NAME()` and `NAME ()`
    (the lexer gives a `()` token, or `(` then `)`), `function NAME` with or
    without `()`, with any body form (`{ ... }`, `( ... )`, ...).

    Statement shaping has already stepped LEAD words past command position,
    and consumes the brace-bodied prefixes (`NAME() {`, `function NAME {`)
    as part of that; the others leave NAME at WORDS[LEAD]. Windows are
    therefore read from index 0 through LEAD, so every spelling shows up
    exactly once. A name ending in `=` is an assignment (`arr=()`), not a
    function name.
    """
    n = len(words)
    for i in range(min(lead, n - 1) + 1):
        t = words[i]
        if t == "function" and not getattr(t, "quoted", False):
            return True
        if i + 1 < n and not getattr(t, "is_operator", False) and not t.endswith("="):
            nxt = words[i + 1]
            if getattr(nxt, "is_operator", False):
                if nxt.startswith("()"):
                    return True
                if (
                    nxt == "("
                    and i + 2 < n
                    and words[i + 2] == ")"
                    and getattr(words[i + 2], "is_operator", False)
                ):
                    return True
    return False


def _overrides_command_name(words, lead, shaped_words):
    """Whether one lexed statement holds a command-name override construct
    (FR7): a function definition, `alias`/`hash`/`enable` as the command
    word (also behind `builtin`), a PATH assignment -- as a prefix of a
    command, as a statement of its own, or as an argument of `export`. WORDS
    is the statement's non-redirect words, LEAD where command position
    starts in them, SHAPED_WORDS what remains from there.

    Reads only the statement's own words, so a quoted `alias` or `f()`, a
    comment, or an argument-position `PATH=...` is not a match, and bodies
    of data heredocs never reach it.
    """
    if _defines_function(words, lead):
        return True
    if any(PATH_ASSIGNMENT.match(w) for w in words[:lead]):
        return True
    if shaped_words and PATH_ASSIGNMENT.match(shaped_words[0]):
        return True
    word, args = head(shaped_words)
    if word in OVERRIDE_BUILTINS:
        return True
    if word == "builtin" and args and args[0] in OVERRIDE_BUILTINS:
        return True
    if word == "export" and any(PATH_ASSIGNMENT.match(a) for a in args):
        return True
    return False


def _overrides_command_name_unlexed(toks, shaped_words):
    """_overrides_command_name() for a statement of a chunk that would not
    lex (an unbalanced quote): no operator/quote provenance exists, so the
    same constructs are read from plain words, and a PATH assignment
    anywhere in the statement counts (the stricter reading)."""
    word, args = head(shaped_words)
    if word in OVERRIDE_BUILTINS:
        return True
    if word == "builtin" and args and args[0] in OVERRIDE_BUILTINS:
        return True
    if toks and toks[0] == "function":
        return True
    if any("()" in t for t in toks[:2]) or toks[1:3] == ["(", ")"]:
        return True
    return any(PATH_ASSIGNMENT.match(t) for t in toks)


def ask_scan_budget_exceeded():
    """Emit the scan-budget `ask` decision and stop: the static analysis
    would cost far more than the input is long, either because statements()
    queued too much text (its own relative cap) or because lex_shell() could
    not settle the text within its linear work bound (LexBudgetExceeded,
    destructive-guard-unified-lexer D4). Never an `allow`: under claude-batch
    the `ask` is demoted to `deny` by decide()."""
    decide(
        "ask",
        "scan-budget-exceeded",
        "入れ子/積み上げの構造が深く、静的解析の走査量が入力長に対して"
        "過大になったため打ち切った。安全側で確認を挟む。",
    )


def ask_unmatched_subscript():
    """Emit the `ask` decision for an array subscript whose matching `]` is
    not found before the end of the input (LexUnmatchedSubscript, P14): bash
    keeps reading for the `]`, so the line boundaries it would use cannot be
    placed statically. Never an `allow`; under claude-batch decide() demotes
    the `ask` to `deny`."""
    decide(
        "ask",
        "unmatched-subscript",
        "配列の添字の `]` が入力の終わりまでに見つからない。bash は `]` が来るまで"
        "続きの行を読み続けるため、行の境界を静的に決められない。安全側で確認を挟む。",
    )


def ask_lex_unsettled(exc):
    """The `ask` decision for a text lex_shell() could not settle: its own
    for an unmatched subscript, the scan-budget one for everything else."""
    if isinstance(exc, LexUnmatchedSubscript):
        ask_unmatched_subscript()
    ask_scan_budget_exceeded()


def statements(command):
    """Yield (text, tokens, lexed, shaped_words, redirects, origin) per
    command segment, substitution bodies included.

    The text is the tokens rejoined, so quoting is already resolved by the
    time the regex-based checks see it. LEXED is lex_segments()'s per-segment
    parse-success flag — False only on the parse-failure fallback, where
    token provenance is unavailable.

    ORIGIN (destructive-guard-rm-reason-positions) is the statement's origin
    position information: an (anchor, statement index) pair, which
    token_position() turns into the origin position of any token of the
    statement — a tuple whose order, across statements of every chunk, is
    the order the tokens have when the original command string is read left
    to right. Chunks are scanned in a stack order unrelated to that, so the
    caller sorts by origin position rather than by arrival. The anchor of a
    derived chunk is the position it was derived from in the chunk it came
    out of: a substitution body, at the substitution's own opening (refined
    to where the substitution sits inside the payload when it was written
    inside a `-c` / eval / here-string payload); a payload, at the payload
    word; a heredoc body queued whole, at the start of the body (after
    everything on the operator's line, before anything after the delimiter
    line — not at the operator); a substitution extracted from an unquoted
    heredoc body, at its offset inside that body's start. A chunk lexed
    through the parse-failure fallback gets positions from the fallback's
    own statement and token order.

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
    # Each entry is (chunk text, anchor, substitution index): the anchor is
    # the chunk's origin-position prefix (see "Origin positions" above); the
    # substitution index is the run-global ALL_SUBS index of the substitution
    # a body chunk was queued for (None for every other chunk), which lets
    # the anchor be refined at pop time from MARKER_POS.
    pending = [(command, (), None)]
    # {ALL_SUBS index: origin position of that substitution's marker}, kept
    # by _register_marker_positions(); a later (deeper) registration
    # replaces an earlier one.
    marker_pos = {}
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
    # FR7: set the first time any statement of any chunk holds a command-name
    # override construct (_overrides_command_name()). From then on every
    # heredoc judged data is treated as undetermined. A data heredoc seen
    # BEFORE the first construct has already been passed over, so its body
    # is parked in DEFERRED_DATA_BODIES -- only when its chunk holds a sink
    # word, the one condition on which the fallback would scan it -- and
    # queued the moment the flag turns on. The flag is raised at most once,
    # so each parked body is queued at most once.
    override_seen = False
    deferred_data_bodies = []
    while pending:
        chunk, anchor, sub_index = pending.pop()
        if sub_index is not None:
            anchor = marker_pos.get(sub_index, anchor)
        scanned_chars += len(chunk)
        if scanned_chars > scan_budget:
            ask_scan_budget_exceeded()
        chunk, heredocs, _omap = _strip_heredocs_mapped(chunk)
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
        chunk_subs = [_span_inner(chunk, span)[0] for span in top_spans]
        offset = len(all_subs)
        # The chunk's one lexing: its statements are walked further down, and
        # SEG_ENDS (where each statement's separator starts) lets a heredoc
        # body queued below be anchored between the right two statements.
        marked_chunk = _mark_substitutions(chunk, top_spans, offset)
        segments, seg_ends = _lex_segments_with_ends(marked_chunk)
        # Where each statement begins in the marked text: the end of the
        # separator before it (the same offsets _lex_layout() reports).
        seg_starts = (
            None if seg_ends is None
            else [0] + [end + len(seg[2]) for end, seg in zip(seg_ends, segments[:-1])]
        )
        in_tail = _statements_in_tail(marked_chunk, seg_starts, len(segments))
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
            # Where each queued body sits among the chunk's statements, built
            # once and only when some body is queued: every queued body is
            # anchored by which statement starts after its operator's line.
            heredoc_ended_by = None
            for index, record in enumerate(heredocs):
                if not record.body.strip():
                    continue  # a blank body is never queued, as before this task
                destination = destinations.get(index, "undetermined")
                defer_data = False
                if destination == "data":
                    if override_seen:
                        destination = "undetermined"
                    elif chunk_sink_fallback:
                        defer_data = True
                queued_whole = destination == "sink" or (
                    destination == "undetermined" and chunk_sink_fallback
                )
                if queued_whole or defer_data or not record.quoted:
                    if heredoc_ended_by is None:
                        heredoc_ended_by = _statements_ended_by(
                            chunk, marked_chunk, seg_ends, chunk_scan[3]
                        )
                    body_anchor = anchor + (
                        _heredoc_body_step(chunk, heredoc_ended_by, record, index),
                    )
                if defer_data:
                    deferred_data_bodies.append((record.body, body_anchor, None))
                if queued_whole:
                    pending.append((record.body, body_anchor, None))
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
                    # BODIES holds (inner text, offset of the substitution
                    # in the heredoc body), each anchored below at the
                    # body's start plus that offset.
                    if needs_whole_body:
                        # An unbalanced/unclosed `$(`/`` ` `` could not be
                        # extracted as a discrete substitution; treat the
                        # whole body as the scan target rather than silently
                        # dropping it.
                        pending.append((record.body, body_anchor, None))
                    else:
                        for body, offset_in_body in bodies:
                            if body.strip():
                                pending.append(
                                    (
                                        body,
                                        body_anchor + ((offset_in_body, 0, 0),),
                                        None,
                                    )
                                )
        # TOP_SPANS (Component 1, computed once above) already reflects true
        # nesting, unlike SUBSTITUTION's own single-level, paren-free regex:
        # a chunk-local substitution several levels deep no longer needs a
        # second regex pass here to be marked at all. Each span's own inner
        # text is queued; a nested level inside it is found in turn once
        # that text is popped off PENDING and scanned as its own chunk.
        for i, body in enumerate(chunk_subs):
            if body.strip():
                # Anchored at its marker's position once the statements below
                # (and any payload chunk derived from them) have registered
                # it; the "after everything" step is only the answer for a
                # marker that never reaches a token.
                pending.append(
                    (
                        body,
                        anchor + ((_AFTER_EVERYTHING, _AFTER_EVERYTHING, i),),
                        offset + i,
                    )
                )
        all_subs.extend(chunk_subs)
        quoted_segments = lex_segments(_mark_quoted_substitutions(chunk, top_spans))
        # task0001: case-pattern/body state, scoped to this one chunk only.
        case_stack = []
        for seg_index, (marked, lexed, sep) in enumerate(segments):
            toks = _strip_unresolved_marks(marked, all_subs)
            _register_marker_positions(marker_pos, marked, anchor, seg_index)
            if lexed:
                fused = _split_fused_closer_redirects(toks)
                words_only, redirects = split_redirects(fused, lexed)
                lead = _shape_leading(words_only, case_stack, in_tail[seg_index])
                shaped_words = _shaped_remainder(words_only, lead)
                statement_overrides = not override_seen and _overrides_command_name(
                    words_only, lead, shaped_words
                )
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
                statement_overrides = (
                    not override_seen
                    and _overrides_command_name_unlexed(toks, shaped_words)
                )
            if statement_overrides:
                override_seen = True
                pending.extend(deferred_data_bodies)
                deferred_data_bodies = []

            if toks:
                yield (
                    " ".join(toks), toks, lexed, shaped_words, redirects,
                    (anchor, seg_index),
                )
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
                    payload, payload_word = extract_shell_payload_anchored(
                        payload_toks, lexed, quoted_payload_toks
                    )
                    if payload and payload.strip():
                        budget[0] -= 1
                        pending.append(
                            (
                                payload,
                                anchor
                                + ((seg_index, _token_index(marked, payload_word), 0),),
                                None,
                            )
                        )


def tokens(segment):
    """Best-effort tokenization of SEGMENT into words, the parse-failure
    path of _lex_layout() and nothing else. The words come from the same
    masked view the layout pass reads (destructive-guard-unified-lexer FR1-FR3,
    FR5, FR7): a `#` comment is dropped only where the lexer sees one, text
    hidden inside an ANSI-C quote, a parameter or arithmetic expansion is
    given back unchanged, and the raw text never reaches a comment-stripping
    tokenizer. Falls back to whitespace only when the view does not tokenize
    either (an unclosed quote, a trailing backslash)."""
    try:
        return [str(tok) for tok, _start, _end in _tokenize_marked(
            _MarkedText.plain(segment), layout=False
        )]
    except ValueError:
        return segment.split()


class _SkippedWords:
    """What the command-word resolution passed over before a statement's
    command word, as _skip_assignments_and_wrappers() collects it for the
    heredoc destination decision (destructive-guard-heredoc-sink-gaps FR6).

    WORDS holds the VAR=value assignments, the WRAPPERS' own names, their
    options and the options' values -- in the order they were read. ENV_SPLIT
    is True when an `env` option among them is -S/--split-string in any
    spelling. mise/asdf `exec` words are not collected: they name tool
    specs, not a program the heredoc could be handed to.
    """

    __slots__ = ("words", "env_split")

    def __init__(self):
        self.words = []
        self.env_split = False


def _env_split_option(opt):
    """Whether OPT -- one option word read after `env` -- is `env`'s
    -S/--split-string in any spelling (FR6): `-S`, `-Sbash`, `-S'sh -s'`,
    `-iS` and `-iSbash` (a short-option cluster), `--split-string`,
    `--split-string=...`, and an abbreviation of the long option (GNU env
    accepts any unambiguous prefix). Inside a short-option cluster, `u` and
    `C` take the rest of the word as their value, so a `S` after either is
    that value, not the option.
    """
    if opt.startswith("--"):
        name = opt[2:].split("=", 1)[0]
        return bool(name) and "split-string".startswith(name)
    for ch in opt[1:]:
        if ch == "S":
            return True
        if ch in "uC":
            return False
    return False


def _skip_assignments_and_wrappers(toks, start=0, end=None, skipped=None):
    """Advance past VAR=value assignments, WRAPPERS (and their value-taking
    options), and mise/asdf `exec` prefixes — the skip loop head() has
    always applied, minus its `.substitution_only` handling.

    START and END bound the scan to TOKS[START:END] and the returned index
    is then an index into TOKS itself (the default, START=0 / END=None,
    scans all of TOKS exactly as before). SKIPPED, when given, is a
    _SkippedWords this scan adds the words it passes over to (the
    assignments, the wrapper names, their options and option values) --
    the FR6 skipped-word sink check reads it. Collecting changes nothing
    about where the scan stops.

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

    Returns the index in TOKS where this stops — START (0 by default) when
    TOKS[START] itself doesn't match anything here (including when it is
    `.substitution_only`, which this function does not look at all).
    """
    i = start
    n = len(toks) if end is None else min(end, len(toks))
    while i < n:
        t = toks[i]
        if re.match(r"^[A-Za-z_]\w*=", t):  # VAR=value prefix
            if skipped is not None:
                skipped.words.append(t)
            i += 1
            continue
        if t in WRAPPERS:
            if skipped is not None:
                skipped.words.append(t)
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
                if skipped is not None:
                    skipped.words.append(a)
                    if t == "env" and _env_split_option(a):
                        skipped.env_split = True
                if a in value_flags:
                    i += 1  # consume the option's value token
                    if skipped is not None and i - 1 < n:
                        skipped.words.append(toks[i - 1])
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


def _shape_leading(toks, case_stack, tail=False):
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

    TAIL (round 2 deferred, task0001, FR2) says the statement begins at or
    after the chunk's tail start (see _statements_in_tail()): a `case` word is
    then no keyword and opens no case construct -- it is the statement's
    command word, as the lexer reads it after a tail source -- so a line bash
    runs is never taken for a case pattern. A construct opened before the tail
    is read, and closed by its `esac`, as ever: nothing here changes how
    CASE_STACK is read.

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
        if t == "case" and not blocked and not quoted and not tail:
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


def route_substitution_headed_statement(
    remainder, raw_body, segment, anchor, note_rm_invocation
):
    """The single entry point for a statement whose command-word position
    held a substitution token that _skip_to_command_word() skipped
    (task0002 FR1/FR2/FR3/FR11/FR13 — supersedes task0001's shape-based
    pre-gates, both removed: the dash-leading pre-gate and the recursion-
    AND-force-AND-operand pre-screen _rm_route_candidate() used to apply).

    ANCHOR is the origin position of that substitution token — the token
    whose body was read as command-name evidence — which is where this rm
    invocation sits in the original command string (token_position()).
    NOTE_RM_INVOCATION is main()'s registration callback: called once with
    ANCHOR, only on the branch that actually reaches check_rm(), so a
    substitution-headed statement that evidences "git" or nothing readable
    is never an rm invocation. The callback only RECORDS the invocation:
    this function never assigns or consumes an ordinal, because ordinals are
    assigned only after the whole command is scanned (main()). The rm
    invocation this route establishes is the statement's one rm invocation:
    when the statement's written command word is also `rm` (`$(printf rm)
    rm -rf x`), main() does not run the plain route for it, so the statement
    gets one ordinal across both routes. The written `rm` word, when there
    is one, is the first operand of REMAINDER and is numbered and judged as
    such.

    REMAINDER is the statement's own tokens from that skip point onward —
    exactly what would be `args` for the plain spelling of the read command
    name (task0001 FR1/FR2, AS-3), written command word included. RAW_BODY
    is the raw text of the substitution that sat there (see
    read_command_name_evidence()). SEGMENT is passed through to check_git()
    unchanged, matching its existing signature.

    Returns check_rm()'s own list of records for main() to pool (D6) when
    evidence reads as "rm"; calls check_git() (which decide()s and exits
    directly, or returns None) when evidence reads as "git"; returns [] — no
    route entered, no decision — when evidence reads as anything else, or is
    unreadable (R4:
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
        note_rm_invocation(anchor)
        return check_rm(remainder, anchor)
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


def rm_target_designation(invocation_ordinal, target_number, substitution_only=False):
    """A hook-authored designation naming a target's POSITION instead of its
    text (task0001 FR4, "Target designation" contract): the
    INVOCATION_ORDINALth `rm` invocation of the command (1-based) and the
    TARGET_NUMBERth operand of that invocation (1-based). Both are positions
    in the ORIGINAL command string read left to right, not the order the
    hook happened to reach them:

    - The ordinal of an rm invocation is assigned only after the whole
      command is scanned, by sorting every invocation's anchor token by its
      origin position in the original command string (statements()): the
      written `rm` command word for a plain invocation, the substitution
      token for a substitution-headed one (route_substitution_headed_
      statement()). A statement is one invocation however many routes judge
      it — a statement reaching both the substitution route and the plain
      route gets one ordinal — and an rm inside a substitution body, a
      `-c` / eval / here-string payload or a heredoc body is ordered by
      where that text was written. render_rm_decisions() calls this function
      once the ordinals exist.
    - The number of a target is its operand position in that invocation's
      own operand list (check_rm()): before the first `--`, a word starting
      with `-` is an option and is not counted; the first `--` itself is not
      counted; after it every word is counted, `-`-leading words and further
      `--` included. A dash-leading operand after `--` is numbered but never
      judged. A word that is operator syntax is never counted.

    Two different targets never receive the same designation: a target is
    identified by (invocation, operand position), and each invocation has its
    own ordinal. Both are pure functions of the command text, so the same
    command always yields the same designation for the same target (NFR2).

    Contains no character taken from the target, with one exception: a
    target built entirely from command substitution (SUBSTITUTION_ONLY, the
    token's `.substitution_only`) may show the fixed stand-in the hook
    already writes for that case
    (SUBSTITUTION_STANDIN, SPEC.md a3) next to the position — that text is
    hook-authored and constant, never copied from the target. That suffix
    uses ASCII square brackets rather than the full-width parentheses every
    caller below wraps the whole designation in, so the two never nest into
    an unreadable "（…（…）…）" when both apply to the same target.
    """
    designation = f"{invocation_ordinal}番目のrmの{target_number}番目の対象"
    if substitution_only:
        designation += f"[`{SUBSTITUTION_STANDIN}`]"
    return designation


# Message forms of one judged rm target (_RmRecord.form).
RM_FORM_ROOT = "root"
RM_FORM_EXPANSION = "expansion"
RM_FORM_GLOB_PARENT = "glob-parent"
RM_FORM_GLOB = "glob"
RM_FORM_LOST_EVIDENCE = "lost-evidence"
RM_FORM_OUTSIDE_SCRATCH = "outside-scratch"


class _RmRecord:
    """One judged rm target's decision, before any numbering or rendering:
    its TIER and RULE, the ANCHOR (origin position) of the rm invocation it
    belongs to, its operand NUMBER within that invocation, and exactly what
    its single-target message needs — FORM (which message applies), ROOT_
    TOKEN (the raw token, `rm-root` only), SUBSTITUTION_ONLY (whether the
    designation shows the fixed stand-in) and TEMPLATE (the deletion
    alternative text of a plain rm-recursive target, else None). It holds no
    ordinal and no rendered text: both exist only after the whole command is
    scanned (render_rm_decisions())."""

    __slots__ = (
        "tier", "rule", "anchor", "number", "form", "root_token",
        "substitution_only", "template",
    )

    def __init__(
        self, tier, rule, anchor, number, form, root_token=None,
        substitution_only=False, template=None,
    ):
        self.tier = tier
        self.rule = rule
        self.anchor = anchor
        self.number = number
        self.form = form
        self.root_token = root_token
        self.substitution_only = substitution_only
        self.template = template


def _number_rm_operands(args):
    """[(operand number, token)] for ARGS, the operand basis of one rm
    invocation, numbered left to right with the `--` rule: before the first
    `--` a word starting with `-` is an option and is not counted (a lone `-`
    included); the first `--` itself is not counted; after it every word is
    counted — words starting with `-` and further `--` included. A word that
    is operator syntax (`.is_operator`) is never counted, anywhere."""
    numbered = []
    count = 0
    options_ended = False
    for a in args:
        if getattr(a, "is_operator", False):
            continue
        if not options_ended:
            if a == "--":
                options_ended = True
                continue
            if a.startswith("-"):
                continue
        count += 1
        numbered.append((count, a))
    return numbered


def _rm_single_target_message(record, designation):
    """The single-target reason text of RECORD, byte-for-byte what the hook
    wrote for the same target when it named a position (A5)."""
    form = record.form
    if form == RM_FORM_ROOT:
        return f"削除対象が `{record.root_token}` — ホーム/ルート全体に届く。"
    if form == RM_FORM_EXPANSION:
        return (
            f"再帰削除の対象（{designation}）が変数/コマンド置換で、影響範囲を静的に確定できない。"
            f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。"
        )
    if form == RM_FORM_GLOB_PARENT:
        return (
            f"再帰削除の対象（{designation}）はグロブと親参照(`..`)が混在し、"
            f"グロブの展開結果によって実際の削除範囲が変わるため静的に確定できない。"
            f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。"
        )
    if form == RM_FORM_GLOB:
        return (
            f"再帰削除の対象（{designation}）がグロブで、影響範囲を静的に確定できない。"
            f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。"
        )
    if form == RM_FORM_LOST_EVIDENCE:
        return (
            f"`rm -r` の対象（{designation}）は一部がコマンド置換によるもので、"
            f"実際の削除範囲を静的に確定できない。置換を展開した実パスを"
            f"コマンドに直接書いて撃ち直す。"
        )
    return f"`rm -r` の対象（{designation}）はスクラッチ領域の外。{record.template}"


def render_rm_decisions(invocations, records):
    """Number and render the rm decisions of a fully scanned command: the
    point where ordinals exist at all.

    INVOCATIONS is the anchor (origin position) of every rm invocation main()
    established — including one that produced no record — and RECORDS every
    _RmRecord check_rm() collected. Every invocation gets an ordinal, 1..n in
    ascending anchor order, i.e. in the order the anchor tokens stand in the
    original command string. Records with the same (invocation, operand
    number) are the same token judged the same way and collapse into one.
    Returns [(tier, rule, name, message, template)], ascending by (ordinal,
    operand number), for strongest_rm_decision(): NAME is the designation
    (rm_target_designation()) — or the raw token for an `rm-root` record —
    MESSAGE the single-target reason text, and TEMPLATE the deletion
    alternative for a plain rm-recursive target (None for every other form).
    """
    ordinal_of = {
        anchor: ordinal
        for ordinal, anchor in enumerate(sorted(set(invocations)), start=1)
    }
    unique = {}
    for record in records:
        unique.setdefault((record.anchor, record.number), record)
    rendered = []
    for record in sorted(
        unique.values(), key=lambda r: (ordinal_of[r.anchor], r.number)
    ):
        designation = rm_target_designation(
            ordinal_of[record.anchor], record.number, record.substitution_only
        )
        name = record.root_token if record.form == RM_FORM_ROOT else designation
        template = record.template if record.form == RM_FORM_OUTSIDE_SCRATCH else None
        rendered.append(
            (
                record.tier,
                record.rule,
                name,
                _rm_single_target_message(record, designation),
                template,
            )
        )
    return rendered


def check_rm(args, anchor):
    """Return the decision every target of one `rm` invocation warrants, as
    a list of _RmRecord — never emits, never exits, never assigns an
    ordinal. A check that emitted the first decision it reached let an
    `ask` on an early target end the scan, so a later target — or, once the
    caller folds multiple calls together, a later segment — that warranted
    `deny` was approved along with it (D6). Collecting every target's
    decision here, uncollapsed, is what lets the caller (main()) evaluate
    every target of every segment before picking the strongest one and
    emitting once.

    ARGS is the invocation's operand basis: the REMAINDER of a
    substitution-headed statement (its written `rm` word, when present, is
    its first operand), or the ARGS of a plain `rm` command word. ANCHOR is
    the invocation's origin position (token_position() of the written `rm`
    word, or of the substitution token on the substitution route) and goes
    into every record: it, not an ordinal, is what ties a target to its
    invocation, because ordinals exist only after the whole command is
    scanned (render_rm_decisions(), which also renders the designations and
    messages). Each record carries its target's operand number, counted by
    _number_rm_operands(): before the first `--` a word starting with `-` is
    an option and is not counted, the first `--` is not counted, and after it
    every word is counted, `-`-leading words and further `--` included. The
    set of targets JUDGED is unchanged by the numbering — a target is judged
    when it does not start with `-` and is not operator syntax — so a
    dash-leading operand after `--` is numbered and never judged. The
    `rm-root` decision keeps naming its RAW token verbatim (SPEC.md a2,
    fixed RM_ROOT_SHAPE vocabulary only, never free text).

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
    # apart; a quoted `")"` is a real word and never carries it, and
    # _number_rm_operands() never counts it. Evaluating every target now that
    # D6 no longer exits on the first decision would otherwise let this
    # artifact outvote a real target under it. A target is a counted operand
    # that does not start with `-`: a dash-leading operand after `--` is
    # numbered (it still takes an operand position) but never judged.
    targets = [
        (number, a)
        for number, a in _number_rm_operands(args)
        if not a.startswith("-")
    ]

    if not targets:
        return []

    records = []
    root_hit = set()
    for number, t in targets:
        if RM_ROOT_SHAPE.fullmatch(t):
            records.append(
                _RmRecord(
                    "deny", "rm-root", anchor, number, RM_FORM_ROOT,
                    root_token=str(t),
                )
            )
            root_hit.add(t)
    if not recursive:
        return records

    for number, t in targets:
        if t in root_hit:
            continue
        substitution_only = getattr(t, "substitution_only", False)
        unresolved = getattr(t, "unresolved", False)
        if (
            substitution_only
            or UNRESOLVED_EXPANSION.search(t)
            or UNRESOLVED_PARAM.search(t)
            or UNRESOLVED_TILDE.search(t)
        ):
            records.append(
                _RmRecord(
                    "ask", "rm-unresolvable", anchor, number, RM_FORM_EXPANSION,
                    substitution_only=substitution_only,
                )
            )
            continue
        if GLOB_CHARS.search(t) and _has_parent_ref_component(t):
            records.append(
                _RmRecord(
                    "ask", "rm-unresolvable", anchor, number, RM_FORM_GLOB_PARENT
                )
            )
            continue
        normalized = normalize_candidate(t)
        if not unresolved and safe_delete_target(normalized):
            continue
        if GLOB_CHARS.search(t):
            records.append(
                _RmRecord("ask", "rm-unresolvable", anchor, number, RM_FORM_GLOB)
            )
            continue
        if unresolved:
            # task0003 Design Part 2: this target reached `deny` because its
            # safe-root exception was suppressed by lost evidence (step 6),
            # not because its real text is actually outside every safe root
            # — that may or may not be true, and the old wording below
            # asserted it regardless. State the fact that IS true instead.
            records.append(
                _RmRecord(
                    "deny", "rm-recursive", anchor, number, RM_FORM_LOST_EVIDENCE
                )
            )
        else:
            records.append(
                _RmRecord(
                    "deny", "rm-recursive", anchor, number, RM_FORM_OUTSIDE_SCRATCH,
                    template=deletion_alternative(t),
                )
            )
    return records


def strongest_rm_decision(decisions):
    """Pick the strongest decision across every (tier, rule, name, message,
    template) tuple render_rm_decisions() produced — possibly pooled across
    several `rm` invocations in different segments of one compound command,
    already ascending by (ordinal, operand number) — and return (tier, rule,
    message) for main() to emit, or None when nothing was collected (D6).
    The winning tier is the highest rank; the rule is `rm-root` when any
    winner is `rm-root` (the same priority a single target used to get from
    being checked first, before D6 separated evaluation from emission), else
    the winners' common rule.

    One winner: its single-target message is the reason, unchanged (A5). Two
    or more: the combined reason is a lead statement that several targets
    reached the same decision strength, one entry per winner in the winners'
    order, and a closing instruction to rewrite each target into a safe form
    and retry. An entry starts with the winner's NAME — its designation
    (rm_target_designation()), or the raw RM_ROOT_SHAPE token for `rm-root`
    (SPEC.md a2), not repeated when an earlier entry already has that name —
    and, for a plain rm-recursive winner (the one whose single-target message
    carries a deletion template), is followed immediately by that same
    template, so every plain rm-recursive designation is paired with its
    template and the next entry's name follows it. `rm-root`,
    `rm-unresolvable` and rm-recursive-with-lost-evidence winners have no
    template and get none. Each designation appears exactly once (the
    records were already collapsed per invocation and operand number), and no
    character of any target's text reaches the reason (task0001 FR4):
    templates carry the fixed placeholder, never the target.
    """
    if not decisions:
        return None
    top_rank = max(DECISION_RANK[d[0]] for d in decisions)
    winners = [d for d in decisions if DECISION_RANK[d[0]] == top_rank]
    tier = winners[0][0]
    rule = next((d[1] for d in winners if d[1] == "rm-root"), winners[0][1])
    if len(winners) == 1:
        return tier, rule, winners[0][3]
    entries = []
    named = set()
    for _, _, name, _, template in winners:
        if name in named:
            continue
        named.add(name)
        entries.append(f"{name} — {template}" if template else f"{name}。")
    listing = " ".join(entries)
    return (
        tier,
        rule,
        f"再帰削除の複数対象が同じ強さの判定に達した: {listing} "
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


def main(payload):
    """The hook's judgment of one PreToolUse payload under the lexer reading
    in force (_lex_extglob). It always ends in decide() or in sys.exit(0) (the
    hook has no decision to give). run() reads the payload and combines the
    judgments under the two readings."""
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
    rm_records = []

    # destructive-guard-rm-reason-positions: the anchor of every rm
    # invocation the loop below establishes — the origin position (see
    # statements()) of the invocation's anchor token: the written `rm`
    # command word for a plain invocation, the substitution token for a
    # substitution-headed one. No ordinal is handed out while the loop runs:
    # statements() reaches chunks in a stack order unrelated to where they
    # were written, so an ordinal given on arrival would not name the
    # invocation's place in the original command string. Ordinals are
    # assigned after the whole command is scanned, in ascending anchor order
    # (render_rm_decisions()), which is the left-to-right order of the
    # original command string; the same command text always yields the same
    # anchors and so the same ordinals (NFR2). A statement is ONE invocation:
    # a statement whose substitution evidence reads `rm` and whose written
    # command word is also `rm` is judged once, on the substitution route,
    # and gets one ordinal across both routes.
    rm_invocations = []

    for (
        segment, toks, lexed, shaped_words, shaped_redirects, origin
    ) in statements(command):
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
        # Whether the substitution route established this statement's rm
        # invocation (the evidence read `rm`): then the plain route below
        # must not judge it a second time, whatever its written command
        # word is.
        substitution_headed_rm = False
        if saw_substitution:
            invocations_before = len(rm_invocations)
            rm_records.extend(
                route_substitution_headed_statement(
                    shaped_words[skip_index:],
                    getattr(substitution_tok, "raw_substitution_body", None),
                    segment,
                    token_position(origin, toks, substitution_tok),
                    rm_invocations.append,
                )
            )
            substitution_headed_rm = len(rm_invocations) > invocations_before

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
            if not substitution_headed_rm:
                rm_anchor = token_position(origin, toks, shaped_words[skip_index])
                rm_invocations.append(rm_anchor)
                rm_records.extend(check_rm(args, rm_anchor))
        else:
            check_file_destruction(word, args, segment)
            check_external(word, args, segment)
            check_permissions(word, args)

    # Emission happens once, after every segment's rm targets have been
    # collected (D6) — an earlier deny from check_git()/check_file_
    # destruction()/etc. already exited the process before this line, so
    # reaching it means no OTHER check decided first.
    top = strongest_rm_decision(render_rm_decisions(rm_invocations, rm_records))
    if top is not None:
        tier, rule, message = top
        decide(tier, rule, message)

    if ALLOW_NON_DESTRUCTIVE and not defer_to_kill_guard and not defer_to_new_guard:
        decide("allow", None, "破壊的なパターンに一致しない。")
    sys.exit(0)


# How strict a judgment is, for keeping the stricter of two (_stricter()): the
# hook staying silent leaves the verdict to the guards that decide, which an
# `allow` would not.
_OUTCOME_RANK = {"allow": 0, "ask": 2, "deny": 3}


def _outcome_rank(output):
    if output is None:
        return 1
    return _OUTCOME_RANK[output["hookSpecificOutput"]["permissionDecision"]]


def _judge_under(payload, extglob):
    """main() under the lexer reading EXTGLOB (P14), its decision held back:
    returns the output decide() would have printed, or None when main() ended
    without one. A text lex_shell() could not settle -- within its linear work
    bound, or for lack of a subscript's `]` -- gets an `ask` (the scan-budget
    one, or ask_unmatched_subscript()), never an `allow`
    (destructive-guard-unified-lexer D4, NFR3)."""
    global _capture_decisions, _lex_extglob
    _capture_decisions = True
    _lex_extglob = extglob
    _lex_ext_seen.clear()
    try:
        try:
            main(payload)
        except LexBudgetExceeded as exc:
            ask_lex_unsettled(exc)
    except _Decided as decided:
        return decided.output
    except SystemExit:
        return None
    finally:
        _capture_decisions = False
        _lex_extglob = False
        _lex_ext_units.append(_count_extglob_units())
    return None


# The parse-unit counts (_count_extglob_units()) of the readings run() judged.
_lex_ext_units = []


def run():
    """The hook's entry point: reads the payload and judges it with main()."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail-open: a malformed payload is not our problem

    # Whether bash accepts an extended-glob parenthesis inside an array
    # depends on `shopt -s extglob`, which the hook cannot know (P14). The
    # command is judged with the option off; when the lexer met such a
    # parenthesis (_lex_extglob_met) it is judged with the option on as well,
    # and the stricter of the two verdicts stands, so every line bash would run
    # as a command under either reading is judged as one. Only the verdicts are
    # compared here: which `<<` is a here-document operator stays the lexer's
    # call, under each reading.
    del _lex_ext_units[:]
    outcome = _judge_under(payload, False)
    if _lex_extglob_met:
        other = _judge_under(payload, True)
        if _outcome_rank(other) > _outcome_rank(outcome):
            outcome = other
        # The option may be switched mid-command, so neither fixed reading is
        # reliable when extended-glob parentheses were met in more than one
        # parse unit (in either reading): settle it with an `ask`, never an
        # `allow`. Decided structurally, not by looking for the words
        # `shopt` / `extglob`, which quoting can split. The `ask` goes through
        # decide(), so an unattended run downgrades it to `deny`.
        if max(_lex_ext_units) > 1 and _outcome_rank(outcome) < _OUTCOME_RANK["ask"]:
            global _capture_decisions
            _capture_decisions = True
            try:
                decide(
                    "ask",
                    "extglob-switch",
                    "extglob を途中で切り替えており、拡張パターンの括弧の"
                    "解釈を確定できない。",
                )
            except _Decided as decided:
                outcome = decided.output
            finally:
                _capture_decisions = False
    if outcome is not None:
        json.dump(outcome, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    run()

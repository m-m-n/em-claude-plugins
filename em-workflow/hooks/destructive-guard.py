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
    (`.substitution_only`, task0001 Design Part 1); and, only for a
    `.substitution_only` token, the raw text of the single substitution it
    came from (`.raw_substitution_body`, task0002 FR11) — set after
    construction by _strip_unresolved_marks() via its occurrence-order
    mapping (see that function's docstring), never via this constructor.
    Every consumer besides split_redirects()/check_rm()/
    read_command_name_evidence() treats it as an ordinary str; all four
    attributes default to a closed-fail value (False / None) so a plain str
    used where a Tok is expected fails closed.
    """

    is_operator = False
    unresolved = False
    substitution_only = False
    raw_substitution_body = None

    def __new__(cls, value, is_operator=False, unresolved=False, substitution_only=False):
        obj = str.__new__(cls, value)
        obj.is_operator = is_operator
        obj.unresolved = unresolved
        obj.substitution_only = substitution_only
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


def lex_segments(chunk):
    """Split a chunk into statements, each returned as (tokens, lexed).

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

    Falls back to the regex split when the chunk will not parse — an
    unbalanced quote, usually. That path keeps the old false positives and
    returns LEXED False, since per-token provenance is unavailable there; a
    parse failure is rare, and waving the chunk through unexamined would be
    a hole rather than a nuisance.
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
            (tokens(seg), False) for seg in SEGMENT_SPLIT.split(chunk) if seg.strip()
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
            if seg and all(c in SEGMENT_CHARS for c in seg):
                out.append((current, True))
                current = []
            else:
                current.append(seg)
    out.append((current, True))
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


def _mark_substitutions(chunk):
    """Blank every command-substitution match in CHUNK by replacing it with
    UNRESOLVED_MARK, so the word it sat in survives lexing as a token no
    matter whether the match filled the whole word or sat beside real text
    (destructive-guard-command-substitution task0001 Design Part 1, "evidence
    survives the lexing boundary").

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
    """
    return SUBSTITUTION.sub(UNRESOLVED_MARK, chunk)


def _mark_quoted_substitutions(chunk):
    """Like _mark_substitutions(), but a substitution match that sits
    immediately between a pair of double-quote characters in CHUNK's raw
    text — `"$(...)"` / `` "`...`" ``, with nothing else between the quote
    and the substitution boundary on either side — is replaced with
    QUOTED_MARK instead of UNRESOLVED_MARK. Every other occurrence (bare,
    single-quoted — a real shell would not expand that, but this module has
    never distinguished it either — or mixed with other text inside the
    quotes) gets the ordinary UNRESOLVED_MARK, byte for byte as
    _mark_substitutions() itself would produce.

    Used ONLY by extract_shell_payload() (task0001 FR4), which lexes this
    output as a second, parallel token sequence to _mark_substitutions()'s
    own — same shape, same boundaries, differing only in which marker
    character sits at a substitution's position (see QUOTED_MARK) — so it
    can read, at the payload argument position and nowhere else, whether
    that specific substitution was written enclosed in quotes. No other
    stage calls this function.
    """

    def replace(match):
        start, end = match.span()
        if 0 < start and end < len(chunk) and chunk[start - 1] == '"' and chunk[end] == '"':
            return QUOTED_MARK
        return UNRESOLVED_MARK

    return SUBSTITUTION.sub(replace, chunk)


def _strip_unresolved_marks(toks, chunk_subs=None, cursor=None):
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

    CHUNK_SUBS and CURSOR (task0002 FR11, R1/D5) let this pass additionally
    recover, for a token that collapses entirely into marker residue, the
    RAW text of the substitution it came from — attached as
    `.raw_substitution_body` on the resulting `.substitution_only` Tok, for
    read_command_name_evidence() to read later. CHUNK_SUBS is the ordered
    list of every substitution match's body text in the CURRENT chunk
    (statements()'s own enumeration via SUBSTITUTION.finditer(chunk),
    reused rather than re-scanned); CURSOR is a one-element list shared
    across every segment of that SAME chunk, so the Nth marker character
    encountered — in left-to-right token order across all of a chunk's
    segments, the same order statements() yields them in — is matched to
    the Nth entry of CHUNK_SUBS. This holds regardless of where statement
    boundaries fall: _mark_substitutions() replaces each match with exactly
    one marker character at the match's own position, and neither that
    substitution pass nor lexing ever reorders characters, so the order
    correspondence is exact. A token whose marker count is not exactly
    one — several substitutions concatenated into the same whole word, so
    there is no single raw occurrence to attribute the token to — gets no
    evidence (`.raw_substitution_body` stays None, the constructor default):
    deliberately left unreadable rather than guessing which body applies
    (task0002 Design "Command-name evidence", "the token position cannot be
    mapped back to a raw occurrence"). The cursor still advances by the
    full marker count either way, so later tokens in the same chunk keep
    reading the correct entries of CHUNK_SUBS. Both arguments default to
    None, which reproduces this function's pre-FR11 behaviour exactly (no
    attribute set) — the extract_shell_payload() comparison call elsewhere
    in this file passes neither, since it never needs this evidence.
    """
    out = []
    for t in toks:
        if UNRESOLVED_MARK not in t:
            out.append(t)
            continue
        marker_count = t.count(UNRESOLVED_MARK)
        raw_body = None
        if chunk_subs is not None and cursor is not None:
            start = cursor[0]
            end = start + marker_count
            cursor[0] = end
            if marker_count == 1 and end <= len(chunk_subs):
                raw_body = chunk_subs[start]
        cleaned = t.replace(UNRESOLVED_MARK, "")
        if cleaned == "":
            new_tok = Tok(
                SUBSTITUTION_STANDIN,
                getattr(t, "is_operator", False),
                substitution_only=True,
            )
            new_tok.raw_substitution_body = raw_body
            out.append(new_tok)
            continue
        out.append(Tok(cleaned, getattr(t, "is_operator", False), unresolved=True))
    return out


def statements(command):
    """Yield (text, tokens, lexed) per command segment, substitution bodies
    included.

    The text is the tokens rejoined, so quoting is already resolved by the
    time the regex-based checks see it. LEXED is lex_segments()'s per-segment
    parse-success flag — False only on the parse-failure fallback, where
    token provenance is unavailable.

    The shell-payload extraction below runs on MARKED tokens — the direct
    output of lex_segments(), still carrying raw UNRESOLVED_MARK residue —
    rather than on the flag-converted ones (destructive-guard-command-
    substitution task0003 Design Part 1). Converting residue into the
    per-token `.unresolved`/`.substitution_only` flags erases the
    substitution's textual trace from the token TEXT (the whole point of
    _strip_unresolved_marks()); extracting a `-c`/`eval`/here-string payload
    AFTER that conversion means the string pushed back onto PENDING for
    re-scanning no longer contains any trace of the substitution that used
    to sit in it, so the re-scanned statement's own marking pass has nothing
    left to find — a bare `bash -c 'rm -rf $(mktemp -d)'` used to re-scan as
    a targetless `rm -rf`, the exact zero-target hole this closes. Extracting
    from the marked-but-unstripped tokens instead means the marker character
    itself survives into the payload string, so the re-scan's OWN
    _mark_substitutions()/_strip_unresolved_marks() pass (run fresh, once,
    when that string is popped off PENDING) reproduces the same flag it
    would for the identical text written directly — the marker is plain,
    inert token content until then, so this cannot double-convert or nest
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
    substitution match's raw body text in this CHUNK — the same
    finditer() pass that already feeds PENDING, its results kept instead of
    discarded. CURSOR is shared across every segment of this chunk (reset
    per chunk, at the top of this loop body) so _strip_unresolved_marks()
    can map each `.substitution_only` token back to the one raw body it
    came from, in occurrence order (see that function's docstring). Neither
    is a new read of the raw command string beyond what this loop already
    performs; both are string processing over CHUNK alone.
    """
    pending = [command]
    budget = [MAX_SHELL_PAYLOAD_EXPANSIONS]
    while pending:
        chunk = pending.pop()
        chunk, bodies = strip_heredocs(chunk)
        if bodies and SHELL_SINK.search(chunk):
            # `bash <<EOF` does execute its body, so put it back in the queue.
            pending.extend(b for b in bodies if b.strip())
        chunk_subs = [m.group(1) or m.group(2) or "" for m in SUBSTITUTION.finditer(chunk)]
        for body in chunk_subs:
            if body.strip():
                pending.append(body)
        quoted_segments = lex_segments(_mark_quoted_substitutions(chunk))
        cursor = [0]
        for seg_index, (marked, lexed) in enumerate(
            lex_segments(_mark_substitutions(chunk))
        ):
            toks = _strip_unresolved_marks(marked, chunk_subs, cursor)
            if toks:
                yield " ".join(toks), toks, lexed
                if budget[0] > 0:
                    quoted_marked = (
                        quoted_segments[seg_index][0]
                        if seg_index < len(quoted_segments)
                        else None
                    )
                    payload = extract_shell_payload(marked, lexed, quoted_marked)
                    if payload and payload.strip():
                        budget[0] -= 1
                        pending.append(payload)


def tokens(segment):
    """Best-effort tokenization. Falls back to whitespace on a parse error."""
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def _skip_to_command_word(toks):
    """Advance past VAR=value assignments, WRAPPERS (and their value-taking
    options), and mise/asdf `exec` prefixes — exactly the skip loop head()
    has always applied — additionally tracking whether a `.substitution_only`
    token (an argument built entirely from a command substitution) was
    skipped along the way (task0001 FR1/FR2/FR3, AS-2).

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
    return value, which stays the 2-tuple both files already agree on.

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


def route_substitution_headed_statement(remainder, raw_body, segment):
    """The single entry point for a statement whose command-word position
    held a substitution token that _skip_to_command_word() skipped
    (task0002 FR1/FR2/FR3/FR11/FR13 — supersedes task0001's shape-based
    pre-gates, both removed: the dash-leading pre-gate and the recursion-
    AND-force-AND-operand pre-screen _rm_route_candidate() used to apply).

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
        return check_rm(remainder)
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


def check_rm(args):
    """Return the decision every target of one `rm` invocation warrants, as
    a list of (tier, rule, target, message) tuples — never emits and never
    exits. A check that emitted the first decision it reached let an `ask`
    on an early target end the scan, so a later target — or, once the
    caller folds multiple calls together, a later segment — that warranted
    `deny` was approved along with it (D6). Collecting every target's
    decision here, uncollapsed, is what lets the caller (main()) evaluate
    every target of every segment before picking the strongest one and
    emitting once.

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

    for t in targets:
        if t in root_hit:
            continue
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
                    t,
                    f"再帰削除の対象 `{t}` が変数/コマンド置換で、影響範囲を静的に確定できない。"
                    f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。",
                )
            )
            continue
        if GLOB_CHARS.search(t) and _has_parent_ref_component(t):
            decisions.append(
                (
                    "ask",
                    "rm-unresolvable",
                    t,
                    f"再帰削除の対象 `{t}` はグロブと親参照(`..`)が混在し、"
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
                    t,
                    f"再帰削除の対象 `{t}` がグロブで、影響範囲を静的に確定できない。"
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
                f"`rm -r` の対象 `{t}` は一部がコマンド置換によるもので、"
                f"実際の削除範囲を静的に確定できない。置換を展開した実パスを"
                f"コマンドに直接書いて撃ち直す。"
            )
        else:
            message = f"`rm -r` の対象 `{t}` はスクラッチ領域の外。{deletion_alternative(t)}"
        decisions.append(("deny", "rm-recursive", t, message))
    return decisions


def strongest_rm_decision(decisions):
    """Pick the strongest decision across every (tier, rule, target,
    message) tuple check_rm() returned — possibly pooled across several
    `rm` invocations in different segments of one compound command — and
    return (tier, rule, message) for main() to emit, or None when nothing
    was collected (D6). Every target that reached the winning tier is named
    in the combined reason text. When more than one reason id shares that
    tier (`rm-root` alongside `rm-recursive`, both `deny`), `rm-root` is
    reported — the same priority a single target used to get from being
    checked first, before D6 separated evaluation from emission.
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
    for _, _, target, _ in winners:
        if target not in names:
            names.append(target)
    joined = "、".join(f"`{n}`" for n in names)
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

    Only ever feeds the deferral check in main(): check_git()/check_rm()/the
    other destructive checks keep calling head() on the UNSTRIPPED tokens,
    so no existing verdict changes because of this function — a subshell- or
    brace-wrapped destructive command is exactly as unexamined by those
    checks after this change as before it (out of scope for this task; see
    the task plan's "Which side moves").
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

    for segment, toks, lexed in statements(command):
        check_bypass(segment, toks)

        words, redirects = split_redirects(toks, lexed)
        word, args = head(words)
        # `> ~/.claude/settings.json` のようにコマンド語を持たない純リダイレクト
        # 文も対象を切り詰める。word が無くても redirects だけで判定する。
        check_self_modification(word or "", args, redirects, segment, lexed)

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
        skip_index, saw_substitution, substitution_tok = _skip_to_command_word(words)
        if saw_substitution:
            rm_decisions.extend(
                route_substitution_headed_statement(
                    words[skip_index:],
                    getattr(substitution_tok, "raw_substitution_body", None),
                    segment,
                )
            )

        # The deferral is judged on the statement's REAL head — leading
        # grouping tokens (subshell `(`, brace group `{`, a function
        # signature) stripped first (D7) — never on the unstripped WORD/ARGS
        # check_git()/check_rm()/the rest of this loop use below. A
        # subshell's `(` is itself WORD when ungrouped ("(" != "git"), so
        # this must run even when WORD is None or not "git"/"gh"; it is
        # placed before the `continue` below for that reason.
        gword, gargs = _deferral_head(strip_grouping_prefix(words))
        if matches_target_shape(gword, gargs, cwd):
            defer_to_new_guard = True

        if word is None:
            continue

        if word == "git":
            check_git(args, segment)
        elif word == "rm":
            rm_decisions.extend(check_rm(args))
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

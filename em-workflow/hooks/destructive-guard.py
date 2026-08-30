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

# Wrapper commands that prefix the real one. `mise exec -- gcloud …` and
# `sudo rm -rf …` must be judged on the wrapped command, not the wrapper.
WRAPPERS = {"sudo", "env", "nohup", "time", "command", "nice", "ionice", "doas"}

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
    r"(?:settings[^/\s]*\.json|hooks/|rules/|agents/|skills/|commands/|"
    r"output-styles/|workflows/|routines/|scheduled_tasks\.json)"
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
        if t and all(c in SEGMENT_CHARS for c in t):
            out.append((current, True))
            current = []
        else:
            current.append(t)
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
    """Yield (text, tokens, lexed) per command segment, substitution bodies
    included.

    The text is the tokens rejoined, so quoting is already resolved by the
    time the regex-based checks see it. LEXED is lex_segments()'s per-segment
    parse-success flag — False only on the parse-failure fallback, where
    token provenance is unavailable.
    """
    pending = [command]
    while pending:
        chunk = pending.pop()
        chunk, bodies = strip_heredocs(chunk)
        if bodies and SHELL_SINK.search(chunk):
            # `bash <<EOF` does execute its body, so put it back in the queue.
            pending.extend(b for b in bodies if b.strip())
        for m in SUBSTITUTION.finditer(chunk):
            body = m.group(1) or m.group(2) or ""
            if body.strip():
                pending.append(body)
        for toks, lexed in lex_segments(SUBSTITUTION.sub(" ", chunk)):
            if toks:
                yield " ".join(toks), toks, lexed


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


def check_rm(args):
    flags = short_flags(args)
    recursive = "r" in flags or "R" in flags or has(args, "--recursive")
    targets = [a for a in args if not a.startswith("-")]

    if not targets:
        return
    for t in targets:
        if re.fullmatch(r"/+|/\*|~|~/|\$HOME/?", t):
            decide("deny", "rm-root", f"削除対象が `{t}` — ホーム/ルート全体に届く。")
    if not recursive:
        return
    for t in targets:
        if SAFE_DELETE.match(t):
            continue
        if DYNAMIC.search(t):
            decide(
                "ask",
                "rm-unresolvable",
                f"再帰削除の対象 `{t}` が変数/グロブで、影響範囲を静的に確定できない。"
                f"展開後の実パスをコマンドに直接書いて撃ち直すと確認不要になる。",
            )
        decide(
            "deny",
            "rm-recursive",
            f"`rm -r` の対象 `{t}` はスクラッチ領域の外。{deletion_alternative(t)}",
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
    FLAG_DEST_FLAGS) among ARGS, in either spelling: a separate token
    (`-C DIR`) or the attached `=` form (`--directory=DIR`).
    """
    flags = FLAG_DEST_FLAGS.get(word)
    if not flags:
        return []
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
        i += 1
    return out


def strip_value_tokens(word, args, non_flags):
    """Remove, from NON_FLAGS, any token that is actually the value of one
    of WORD's VALUE_TAKING_FLAGS rather than a positional argument — so the
    last remaining entry is the real destination for `cp`/`ln`.
    """
    value_flags = VALUE_TAKING_FLAGS.get(word)
    if not value_flags:
        return non_flags
    # Walk ARGS in order (not non_flags) so the token immediately following
    # a value-taking flag is dropped by position, even if its text does not
    # start with `-`.
    result = []
    consumed_next = False
    for a in args:
        if consumed_next:
            consumed_next = False
            continue
        if a in value_flags:
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
      (`-t DIR` / `--target-directory=DIR`), additive to the positional
      destination above, never a replacement for it
    - the last non-flag argument for `rsync` and `git` (covers `git clone
      URL DEST`)
    - the value of a command-specific destination flag (`tar -C`/`--directory`,
      `unzip -d`, `curl -o`/`--output`, `wget -O`/`--output-document`)

    Before taking the last non-flag argument as the destination for `cp`/
    `ln`, value-taking short options of theirs (`-S`/`--suffix`, `-t`/
    `--target-directory`) have their value token removed from the
    candidate list, so that value is never mistaken for the destination.

    A member need not be a path — a bare descriptor number or `/dev/null`
    passes through untouched; only the two detection patterns decide
    whether a member matters.
    """
    targets = redirect_write_targets(redirects)
    non_flags = [a for a in args if not a.startswith("-")]

    if word in INPLACE_WRITERS or (
        word == "sed"
        and any(a.startswith("-i") or a.startswith("--in-place") for a in args)
    ):
        targets = targets + non_flags
    elif word in ("cp", "ln"):
        positional = strip_value_tokens(word, args, non_flags)
        if positional:
            targets = targets + [positional[-1]]
    elif word in ("mv", "rm", "chmod", "chown"):
        targets = targets + non_flags
    elif word in ("rsync", "git"):
        if non_flags:
            targets = targets + [non_flags[-1]]

    if word in ("cp", "mv", "ln", "install"):
        targets = targets + flag_destinations(args)

    targets = targets + flag_value_destinations(word, args)

    return targets


HOME_VAR = re.compile(r"^(?:\$\{HOME\}|\$HOME)")
DYNAMIC_CHARS = re.compile(r"[$`]")


def normalize_candidate(target):
    """Expand deterministic home forms and lexically normalize TARGET.

    Only static, filesystem-free transformations: `~`, `$HOME`, and
    `${HOME}` are replaced with the real HOME (known at hook-start, not
    resolved via the filesystem), then the result is run through
    os.path.normpath to collapse `..`/`.`/duplicate slashes lexically —
    no os.path.realpath, no stat, no subprocess.

    If TARGET still contains an unresolved `$` or a backtick after this
    expansion (an unrecognized variable or a live command substitution),
    the caller must not treat a non-match as safe: such a target's real
    destination cannot be determined statically.
    """
    home = os.path.expanduser("~")
    expanded = target
    if expanded == "~" or expanded.startswith("~/"):
        expanded = home + expanded[1:]
    elif HOME_VAR.match(expanded):
        expanded = HOME_VAR.sub(home, expanded, count=1)
    return os.path.normpath(expanded)


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
    the behaviour this judgment had before the write-target set existed.

    Each candidate is also checked in its normalized form (`~`/`$HOME`/
    `${HOME}` expanded, `..` segments collapsed lexically) so equivalent
    spellings of a protected path are not missed. A candidate that still
    carries an unresolved `$`/backtick after that expansion is a dynamic
    write target whose real destination cannot be determined statically;
    such a candidate is asked about rather than silently allowed.
    """
    candidates = write_targets(word, args, redirects) if lexed else [segment]
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
        if DYNAMIC_CHARS.search(normalized) and lexed:
            decide(
                "ask",
                "dynamic-write-target",
                "書き込み先に未解決の変数展開/コマンド置換が残っている。"
                "静的解析では実際の書き込み先を確定できない。",
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

    for segment, toks, lexed in statements(command):
        check_bypass(segment, toks)

        words, redirects = split_redirects(toks, lexed)
        word, args = head(words)
        if word is None:
            continue

        check_self_modification(word, args, redirects, segment, lexed)

        if word == "git":
            check_git(args, segment)
        elif word == "rm":
            check_rm(args)
        else:
            check_file_destruction(word, args, segment)
            check_external(word, args, segment)
            check_permissions(word, args)

    if ALLOW_NON_DESTRUCTIVE and not defer_to_kill_guard:
        decide("allow", None, "破壊的なパターンに一致しない。")
    sys.exit(0)


if __name__ == "__main__":
    main()

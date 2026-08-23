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
REDIRECT = re.compile(r"\d*(?:>>?\|?|<<?<?|>&|<&|&>>?)\d*")

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


def lex_segments(chunk):
    """Split a chunk into statements, each returned as its token list.

    Separators only count when they sit OUTSIDE quotes, and telling those
    apart is the whole reason shlex does the splitting rather than a regex.
    `echo 'a; rm -rf /x'` is one statement headed by `echo`; a quote-blind
    split reads it as two and finds a recursive delete in the second, which
    denied a command that deletes nothing. Literal command text like that
    shows up constantly in generated docs, tests, and commit messages.

    Falls back to the regex split when the chunk will not parse — an
    unbalanced quote, usually. That path keeps the old false positives, but a
    parse failure is rare, and waving the chunk through unexamined would be a
    hole rather than a nuisance.
    """
    try:
        lex = shlex.shlex(chunk, posix=True, punctuation_chars=PUNCTUATION)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return [tokens(seg) for seg in SEGMENT_SPLIT.split(chunk) if seg.strip()]

    out, current = [], []
    for t in toks:
        if t and all(c in SEGMENT_CHARS for c in t):
            out.append(current)
            current = []
        else:
            current.append(t)
    out.append(current)
    return out


def split_redirects(toks):
    """Return (the statement's own words, its redirection tokens).

    `rm -rf /tmp/x > /dev/null` has to be judged on `rm -rf /tmp/x`. With the
    redirect left in, `>` and `/dev/null` looked like two more delete targets
    and the command was denied for writing to the bit bucket. A leading file
    descriptor (`2` in `2>&1`) is part of the redirect too.
    """
    words, redirects = [], []
    i = 0
    while i < len(toks):
        if REDIRECT.fullmatch(toks[i]):
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
    """Yield (text, tokens) per command segment, substitution bodies included.

    The text is the tokens rejoined, so quoting is already resolved by the
    time the regex-based checks see it.
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
        for toks in lex_segments(SUBSTITUTION.sub(" ", chunk)):
            if toks:
                yield " ".join(toks), toks


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
    if not gio_available():
        return f"`mv {path} /tmp/` で退避する（gio が無いのでゴミ箱は使えない）。"
    if path == home or path.startswith(home + os.sep):
        return f"`gio trash {path}` に書き換える（復元情報が残り、ゴミ箱から戻せる）。"
    return (
        f"`mv {path} /tmp/` で退避する"
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


def check_self_modification(segment, word, args, redirects):
    # An output redirect is only a write when it is a real operator token.
    # Testing `">" in segment` also caught a `>` sitting inside a quoted
    # string, so writing the text of a command into a file was mistaken for
    # running it. `<` and `<<` read rather than write, so they do not count.
    writes = (
        any(REDIRECT.fullmatch(t) and not t.startswith("<") for t in redirects)
        or word in INPLACE_WRITERS
        or (word == "sed" and any(a.startswith("-i") for a in args))
        or word in ("rm", "mv", "cp", "ln", "chmod", "chown")
    )
    if not writes:
        return
    if SELF_CONFIG.search(segment):
        decide(
            "ask",
            "self-modification",
            "Claude Code 自身の設定（settings / hooks / rules / agents / skills）への書き込み。"
            "権限やガードの挙動が変わるので、ユーザーの意図を確認する。",
        )
    if TRANSCRIPT.search(segment):
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

    for segment, toks in statements(command):
        check_bypass(segment, toks)

        words, redirects = split_redirects(toks)
        word, args = head(words)
        if word is None:
            continue

        check_self_modification(segment, word, args, redirects)

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

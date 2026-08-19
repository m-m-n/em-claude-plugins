#!/usr/bin/env bash
# Claude Code PreToolUse hook: git commit の前に gitleaks で変更をスキャンする
# - staged / unstaged の両方の diff をスキャン（git add && git commit の複合コマンド対策）
# - リーク検出時は exit 2 でコミットをブロックし、検出内容（redact済み）をClaudeに返す
set -u

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# git commit を含むコマンドだけ対象（cd x && git commit、git -C path commit 等も拾う）
printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_./-])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)' || exit 0

# gitleaks バイナリの解決: PATH → mise の shims の順。どちらにも無ければ
# スキャンせずに通す（fail-open）。gitleaks 未インストール環境で全コミットが
# ブロックされるのを避けるため。develop の Step 0（git-setup ゲート）は逆に
# gitleaks 不在で workflow ごと中断するが、この hook は develop 外でも動く。
if command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS=$(command -v gitleaks)
elif [ -x "$HOME/.local/share/mise/shims/gitleaks" ]; then
    GITLEAKS="$HOME/.local/share/mise/shims/gitleaks"
else
    exit 0
fi

cwd=$(printf '%s' "$input" | jq -r '.cwd // "."')

# スキャン先の解決: コマンド先頭の `cd <path>` や `git -C <path>` があればそちらを優先する
# （フック入力の cwd はセッションのcwdであり、コマンド内の cd は反映されないため）
dir="$cwd"
re_cd="^cd[[:space:]]+(\"([^\"]+)\"|'([^']+)'|([^[:space:];&|]+))"
re_c="git[[:space:]]+-C[[:space:]]+(\"([^\"]+)\"|'([^']+)'|([^[:space:];&|]+))"
if [[ $cmd =~ $re_cd ]] || [[ $cmd =~ $re_c ]]; then
    t="${BASH_REMATCH[2]}${BASH_REMATCH[3]}${BASH_REMATCH[4]}"
    t="${t/#\~/$HOME}"
    [[ $t = /* ]] && dir="$t" || dir="$cwd/$t"
fi

cd "$dir" 2>/dev/null || exit 0
# リポジトリルートに移動してスキャン（ルートの .gitleaks.toml / .gitleaksignore を確実に拾うため）
top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$top" || exit 0
cfg=()
[ -f .gitleaks.toml ] && cfg=(--config .gitleaks.toml)

# --exit-code 9: リーク検出を gitleaks 自体のエラー(exit 1)と区別する
leak=0
"$GITLEAKS" git --pre-commit --staged --verbose --redact --no-banner --no-color --exit-code 9 "${cfg[@]}" 1>&2
[ $? -eq 9 ] && leak=1
"$GITLEAKS" git --pre-commit --verbose --redact --no-banner --no-color --exit-code 9 "${cfg[@]}" 1>&2
[ $? -eq 9 ] && leak=1
# 未追跡ファイルは git diff に映らないため個別にスキャン（新規 .env 等の対策）
while IFS= read -r -d '' f; do
    "$GITLEAKS" dir "$f" --verbose --redact --no-banner --no-color --exit-code 9 "${cfg[@]}" 1>&2
    [ $? -eq 9 ] && leak=1
done < <(git ls-files --others --exclude-standard -z)

if [ "$leak" -eq 1 ]; then
    echo "gitleaks: シークレットを検出したためコミットをブロックしました。検出箇所を修正してから再度コミットしてください。" >&2
    exit 2
fi
exit 0

#!/usr/bin/env bash
# Claude Code PreToolUse hook: git commit の前に gitleaks で変更をスキャンする
# - staged / unstaged の両方の diff をスキャン（git add && git commit の複合コマンド対策）
# - リーク検出時は exit 2 でコミットをブロックし、検出内容（redact済み）をClaudeに返す
# - スキャンはリポジトリの .gitleaks.toml（無ければ標準ルール）で 1 回、続けて
#   ~/.config/gitleaks/*.toml を 1 つずつ --config で渡して実行する
set -u

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# git commit を含むコマンドだけ対象（cd x && git commit、git -C path commit 等も拾う）
printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_./-])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)' || exit 0

# 警告を systemMessage としてユーザーに表示する（exit 0 のときだけ有効）
warn() {
    jq -cn --arg m "$1" '{systemMessage: $m}'
}

# gitleaks バイナリの解決: PATH → mise の shims の順。どちらにも無ければ
# 警告を出してスキャンせずに通す（fail-open）。gitleaks 未インストール環境で全コミットが
# ブロックされるのを避けるため。develop の Step 0（git-setup ゲート）は逆に
# gitleaks 不在で workflow ごと中断するが、この hook は develop 外でも動く。
if command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS=$(command -v gitleaks)
elif [ -x "$HOME/.local/share/mise/shims/gitleaks" ]; then
    GITLEAKS="$HOME/.local/share/mise/shims/gitleaks"
else
    warn "gitleaks: 見つからないため、コミット前のスキャンをスキップしました"
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
repo_cfg=()
[ -f .gitleaks.toml ] && repo_cfg=(--config .gitleaks.toml)

leak=0
errors=()

# 1 つの設定で 3 種類をスキャンする。引数は gitleaks に渡す設定オプション。
# --exit-code 9: リーク検出を gitleaks 自体のエラー(exit 1)と区別する
scan() {
    local rc
    "$GITLEAKS" git --pre-commit --staged --verbose --redact --no-banner --no-color --exit-code 9 "$@" 1>&2
    rc=$?
    "$GITLEAKS" git --pre-commit --verbose --redact --no-banner --no-color --exit-code 9 "$@" 1>&2
    [ $? -eq 9 ] && rc=9
    # 未追跡ファイルは git diff に映らないため個別にスキャン（新規 .env 等の対策）
    while IFS= read -r -d '' f; do
        "$GITLEAKS" dir "$f" --verbose --redact --no-banner --no-color --exit-code 9 "$@" 1>&2
        [ $? -eq 9 ] && rc=9
    done < <(git ls-files --others --exclude-standard -z)
    case $rc in
        0) ;;
        9) leak=1 ;;
        *) [ $# -gt 0 ] && [ "$2" != .gitleaks.toml ] && errors+=("$2") ;;
    esac
}

scan "${repo_cfg[@]}"
for cfg in "$HOME"/.config/gitleaks/*.toml; do
    [ -f "$cfg" ] && scan --config "$cfg"
done

if [ "$leak" -eq 1 ]; then
    echo "gitleaks: シークレットを検出したためコミットをブロックしました。検出箇所を修正してから再度コミットしてください。" >&2
    exit 2
fi
if [ ${#errors[@]} -gt 0 ]; then
    warn "gitleaks: 次の設定でのスキャンがエラーになったため、その設定を飛ばしました: ${errors[*]}"
fi
exit 0

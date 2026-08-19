#!/usr/bin/env bash
# Claude Code PreToolUse hook: Write/Edit/MultiEdit の前に書き込み内容を gitleaks でスキャンする
# - シークレット検出時は exit 2 で書き込みをブロックし、検出内容（redact済み）をClaudeに返す
set -u

input=$(cat)

# 書き込まれる新しい内容を抽出（Write: content / Edit: new_string / MultiEdit: edits[].new_string）
content=$(printf '%s' "$input" | jq -r '
    if .tool_input.content != null then .tool_input.content
    elif .tool_input.edits != null then [.tool_input.edits[].new_string // ""] | join("\n")
    elif .tool_input.new_string != null then .tool_input.new_string
    else "" end')
[ -z "$content" ] && exit 0

# gitleaks バイナリの解決: PATH → mise の shims の順。どちらにも無ければ
# スキャンせずに通す（fail-open）。gitleaks 未インストール環境で全書き込みが
# ブロックされるのを避けるため。
if command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS=$(command -v gitleaks)
elif [ -x "$HOME/.local/share/mise/shims/gitleaks" ]; then
    GITLEAKS="$HOME/.local/share/mise/shims/gitleaks"
else
    exit 0
fi

# --exit-code 9: リーク検出を gitleaks 自体のエラー(exit 1)と区別する
printf '%s' "$content" | "$GITLEAKS" stdin --verbose --redact --no-banner --no-color --exit-code 9 1>&2
if [ $? -eq 9 ]; then
    file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // "(不明)"')
    echo "gitleaks: 書き込み内容にシークレットを検出したため ${file} への書き込みをブロックしました。シークレットを含めない形に修正してください。" >&2
    exit 2
fi
exit 0

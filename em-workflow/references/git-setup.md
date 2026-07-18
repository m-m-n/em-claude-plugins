# Git Setup Procedure (SSOT)

プロジェクトの git ローカル設定を冪等にセットアップする手順。「設定項目」の各項目を順に確認し、未設定のものだけを設定する。すべて設定済みなら何も変更しない。

このドキュメントは以下の 2 箇所から参照される:

- `skills/git-setup/SKILL.md`（ユーザー起動の `/em-workflow:git-setup`）
- `agents/git-setup-guard.md`（develop の Step 0 workflow 開始ゲート）

## 前提チェック

1. `git rev-parse --git-dir` で git リポジトリかを確認する。リポジトリでなければ「git リポジトリではないため中止した」と報告して終了する
2. hooks ディレクトリのパスは `git rev-parse --git-path hooks` で解決する（`core.hooksPath` が設定されている環境や worktree でも正しいパスになる）

## 設定項目

### 1. gitleaks pre-commit hook

`{hooks}/pre-commit` に gitleaks によるシークレットスキャンを設定する。

**判定と処理:**

- pre-commit ファイルが**存在しない** → 「新規作成用スクリプト」で作成し、`chmod +x` する
- pre-commit ファイルが**存在する** → 内容を Read で確認する
  - `gitleaks` の記述が**ある** → 設定済み。何もしない
  - `gitleaks` の記述が**ない** → 既存の内容を壊さないよう「追記用スニペット」を追記する
    - 既存スクリプトの末尾が `exec` や `exit` で終わっている場合は、その手前に挿入する
    - 処理後に実行権限を確認し、なければ `chmod +x` する

**新規作成用スクリプト:**

```sh
#!/bin/sh
# pre-commit: gitleaks でステージ済みの変更からシークレットを検出する

if ! command -v gitleaks >/dev/null 2>&1; then
    # mise の shims が PATH に入っていない環境向けのフォールバック
    if [ -x "$HOME/.local/share/mise/shims/gitleaks" ]; then
        PATH="$HOME/.local/share/mise/shims:$PATH"
    else
        echo "pre-commit: gitleaks が見つからないためコミットを中止した" >&2
        echo "  インストールするか、緊急時は git commit --no-verify で回避できる" >&2
        exit 1
    fi
fi

exec gitleaks git --pre-commit --staged --redact --no-banner --verbose
```

**追記用スニペット:**

```sh

# gitleaks: ステージ済みの変更からシークレットを検出する
if ! command -v gitleaks >/dev/null 2>&1; then
    # mise の shims が PATH に入っていない環境向けのフォールバック
    if [ -x "$HOME/.local/share/mise/shims/gitleaks" ]; then
        PATH="$HOME/.local/share/mise/shims:$PATH"
    else
        echo "pre-commit: gitleaks が見つからないためコミットを中止した" >&2
        echo "  インストールするか、緊急時は git commit --no-verify で回避できる" >&2
        exit 1
    fi
fi
gitleaks git --pre-commit --staged --redact --no-banner --verbose || exit 1
```

## 報告

すべての設定項目の処理が終わったら、項目ごとに結果を報告する:

- 新規設定した / すでに設定済みだった / 既存 hook に追記した
- 問題があった場合（権限エラー等）はその内容

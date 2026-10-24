# Git Setup Procedure (SSOT)

プロジェクトの git ローカル設定を冪等にセットアップする手順。「設定項目」の各項目を順に確認し、未設定のものだけを設定する。すべて設定済みなら何も変更しない。

このドキュメントは以下の 2 箇所から参照される:

- `skills/git-setup/SKILL.md`（ユーザー起動の `/em-workflow:git-setup`）
- `agents/git-setup-guard.md`（develop の Step 0 workflow 開始ゲート）

## 前提チェック

1. `git rev-parse --git-dir` で git リポジトリかを確認する。リポジトリでなければ「git リポジトリではないため中止した」と報告して終了する
2. hooks ディレクトリのパスは `git rev-parse --git-path hooks` で解決する（`core.hooksPath` が設定されている環境や worktree でも正しいパスになる）
    - 出力が相対パスのとき、基準は git を実行したディレクトリ（`-C` で指定した場所）であって git-dir ではない。通常のリポジトリ直下では `.git/hooks` が返る
3. hooks ディレクトリは作成しない（`mkdir` を使わない）。git リポジトリなら必ず存在する。存在しなければパス解決を誤っているので、作成せず「hooks ディレクトリが見つからない」と失敗を報告して終了する

## 設定項目

### 1. gitleaks pre-commit hook

`{hooks}/pre-commit` に gitleaks によるシークレットスキャンを設定する。

**判定と処理:**

- pre-commit ファイルが**存在しない** → 「新規作成用スクリプト」で作成し、`chmod +x` する
- pre-commit ファイルが**存在する** → 内容を Read で確認する
  - `em-workflow:gitleaks-v2` の記述が**ある** → 設定済み。何もしない
  - 「旧版の新規作成用スクリプト」と内容が一致する → 「新規作成用スクリプト」で置き換える
  - 「旧版の追記用スニペット」が含まれる → その部分を「追記用スニペット」で置き換える。ほかの部分は変えない
  - 上のどれでもなく `gitleaks` の記述が**ある** → 設定済み。何もしない
  - `gitleaks` の記述が**ない** → 既存の内容を壊さないよう「追記用スニペット」を追記する
    - 既存スクリプトの末尾が `exec` や `exit` で終わっている場合は、その手前に挿入する
- 作成・置き換え・追記の後に実行権限を確認し、なければ `chmod +x` する

**スキャンの順序:**

1. `--config` 無しで 1 回。リポジトリに `.gitleaks.toml` があればそれ、無ければ標準ルールで検査する
2. `~/.config/gitleaks/*.toml` を名前順に 1 つずつ `--config` で渡して検査する
3. どれか 1 回でも検出したらコミットを中止する
    - 1 が gitleaks のエラーで終わったときもコミットを中止する
    - 2 が gitleaks のエラーで終わったときは、警告を出してその設定を飛ばす

**新規作成用スクリプト:**

```sh
#!/bin/sh
# pre-commit: gitleaks でステージ済みの変更からシークレットを検出する
# em-workflow:gitleaks-v2

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

# --exit-code 9: 検出を gitleaks 自体のエラー(exit 1)と区別する
leak=0
gitleaks git --pre-commit --staged --redact --no-banner --verbose --exit-code 9 || leak=1
for cfg in "$HOME"/.config/gitleaks/*.toml; do
    [ -f "$cfg" ] || continue
    gitleaks git --pre-commit --staged --redact --no-banner --verbose --exit-code 9 --config "$cfg"
    case $? in
        0) ;;
        9) leak=1 ;;
        *) echo "pre-commit: $cfg でのスキャンがエラーになったため飛ばした" >&2 ;;
    esac
done
exit $leak
```

**追記用スニペット:**

```sh

# gitleaks: ステージ済みの変更からシークレットを検出する
# em-workflow:gitleaks-v2
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
gitleaks git --pre-commit --staged --redact --no-banner --verbose --exit-code 9 || exit 1
for gitleaks_cfg in "$HOME"/.config/gitleaks/*.toml; do
    [ -f "$gitleaks_cfg" ] || continue
    gitleaks git --pre-commit --staged --redact --no-banner --verbose --exit-code 9 --config "$gitleaks_cfg"
    case $? in
        0) ;;
        9) exit 1 ;;
        *) echo "pre-commit: $gitleaks_cfg でのスキャンがエラーになったため飛ばした" >&2 ;;
    esac
done
```

**旧版の新規作成用スクリプト:**

置き換えの判定にだけ使う。新しく書き込まない。

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

**旧版の追記用スニペット:**

置き換えの判定にだけ使う。新しく書き込まない。

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

- 新規設定した / すでに設定済みだった / 既存 hook に追記した / 旧版を置き換えた
- 問題があった場合（権限エラー等）はその内容

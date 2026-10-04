---
title: "codex-interactive-guard-hook"
created_date: 2026-10-05
status: draft
---

# codex-interactive-guard-hook - 要件定義書

## 1. 概要

### 1.1 背景
Codex レビュアーと、同じラッパーを使う Codex 相談は、疑似端末付きで対話モードの処理系（`python3 -i` など）を起動できる。端末が閉じた後も、その処理系が孤児プロセスとして空回りし続けることがある。

### 1.2 目的
Codex レビュアーと、同じラッパーを使う Codex 相談が、疑似端末付きで対話モードの処理系（`python3 -i` など）を起動できないようにし、端末が閉じた後も空回りし続ける孤児プロセスを生まないようにする。

### 1.3 スコープ

対象:
- `em-workflow/scripts/run_codex_exec.sh`（既定経路と `--litellm` 経路）
- `em-review/scripts/run_codex_exec.sh`
- `em-workflow/scripts/codex-hook-interactive-guard.py`（新規）
- `em-review/scripts/codex-hook-interactive-guard.py`（新規）
- `em-workflow/agents/codex-reviewer.md`
- `em-review/agents/codex-reviewer.md`
- `tests/test_codex_hook_interactive_guard.py`（新規）
- `.claude/rules/hook-tests.md`

対象外:
- `em-workflow/hooks/hooks.json` への登録（A2）
- `write_stdin` 経由の対話、`code.interact()` のようにコードの中から開く対話モード、`deno repl` のようにサブコマンドで開く REPL の検知（A7）
- プラグインの version の手での変更（A1）
- `--ignore-user-config` の付け外し、ラッパーの usage 文言と受け付けるフラグの変更（A3、A4）

## 2. ビジネス要件

### 2.1 ビジネス目標
Codex レビュアーと、同じラッパーを使う Codex 相談が、疑似端末付きで対話モードの処理系（`python3 -i` など）を起動できないようにし、端末が閉じた後も空回りし続ける孤児プロセスを生まないようにする。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| Codex レビュアー | em-workflow と em-review の `codex-reviewer` が `run_codex_exec.sh` 経由で起動する Codex |
| Codex 相談 | 同じ `run_codex_exec.sh` を使って起動する Codex |

### 2.3 期待される効果
- 対話モードの処理系の起動が、Codex の PreToolUse hook で拒否される。
- 端末が閉じた後も空回りし続ける孤児プロセスが生まれない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター |
|----|----------------|----------|
| UC01 | Bash ツールでのコマンド実行を hook が判定する | Codex（Bash ツール） |

### 3.2 ユースケース詳細

#### UC01: Bash ツールでのコマンド実行を hook が判定する

**アクター**: Codex（Bash ツール）

**事前条件**:
- ラッパーが `codex exec` に hook の `-c` 値と `--dangerously-bypass-hook-trust` を渡している（FR1〜FR4）。

**基本フロー**:
1. Codex が Bash ツールでコマンドを実行しようとする。
2. PreToolUse hook が `tool_input.command` の文字列を解析する（FR9）。
3. 対話モードの処理系の起動（FR6、FR7、FR8）と判定したら、拒否の JSON を stdout に出して exit 0 で抜ける（FR12）。

**代替フロー**:
- 対話モードでない起動: 何も出力せず exit 0 で抜ける（FR10）。
- 判定できない入力: 何も出力せず exit 0 で抜ける（FR11）。
- hook 自体が起動できない・失敗した: Codex の既定の挙動（コマンドを実行する）に任せる（FR11）。

**事後条件**:
- 拒否と判定されたコマンドは、拒否の理由文とともに Codex に返る。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 |
|----|--------|
| FR1 | em-workflow 既定経路で hook を渡す |
| FR2 | em-workflow --litellm 経路で hook を渡す |
| FR3 | em-review で hook を渡す |
| FR4 | 全起動に適用 |
| FR5 | hook スクリプトの配置と同一性 |
| FR6 | -i 付き起動の拒否 |
| FR7 | 引数なし起動の拒否 |
| FR8 | 処理系名の判定 |
| FR9 | コマンドの解析範囲 |
| FR10 | 対話モードでない起動は通す |
| FR11 | fail-open |
| FR12 | 拒否の出力形式 |
| FR13 | レビュアーへの指示 |
| FR14 | テストとルール |

### 4.2 機能詳細

#### FR1: em-workflow 既定経路で hook を渡す

**説明**: `em-workflow/scripts/run_codex_exec.sh` の既定経路の `codex exec` 起動に、`-c "hooks.PreToolUse=[...]"`（matcher は `"Bash"`、command は同じプラグインの `scripts/codex-hook-interactive-guard.py` を絶対パスで実行する）と `--dangerously-bypass-hook-trust` を足す。既存の `-c` 上書き（推論 effort、otel）と `--ignore-user-config` は消さない。

**補足**:
- `-c` の値は TOML 配列 `[{matcher="Bash", hooks=[{type="command", command="python3 '<SCRIPT_DIR>/codex-hook-interactive-guard.py'"}]}]` の形とする。正確なキー名と、command がシェル経由で実行されるかどうかは、実装時に Codex 0.160.0 で確かめる。パスに含まれる引用符や空白は TOML とシェルの両方でエスケープする（A6）。
- ラッパーは hook スクリプトの有無を確かめずに渡す。ファイルが無い場合は Codex の fail-open に任せる（A5）。

#### FR2: em-workflow --litellm 経路で hook を渡す

**説明**: `--litellm` 経路の起動にも FR1 と同じ 2 つを足す。`-p litellm -m MODEL` が argv の中で連続する並びは崩さない。この経路は従来どおり `--ignore-user-config` を付けない。

#### FR3: em-review で hook を渡す

**説明**: `em-review/scripts/run_codex_exec.sh` の起動にも、em-review の `scripts/codex-hook-interactive-guard.py` を指す同じ 2 つを足す。

#### FR4: 全起動に適用

**説明**: hook は readonly と readwrite の両モード、em-workflow の既定経路と `--litellm` 経路、em-review のすべての起動に渡す。

#### FR5: hook スクリプトの配置と同一性

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を置く。Python 3、標準ライブラリだけを使う。2 つのファイルはバイト単位で同一にする。

#### FR6: -i 付き起動の拒否

**説明**: 次の処理系が `-i` を伴って起動されたら拒否する: python 系、node、bash / sh / zsh / dash / ksh、lua。`-i` は束ねた短いオプション（`-Bi`、`-ic`）の中にあっても検知する。node は `--interactive` も同じ扱い。オプションの読み取りは、最初のオペランド、または `-c` / `-m` / `-e` の値で止める。それより後ろの `-i` は対象の引数なので拒否しない。`perl -i`、`ruby -i`、`php -i`、`sed -i` は拒否しない。

#### FR7: 引数なし起動の拒否

**説明**: FR6 の処理系と ruby、perl、deno、irb、ipython について、次の条件をすべて満たす起動を拒否する: スクリプトのオペランドが無い、コードを渡すオプション（`-c` / `-m` / `-e` と、その処理系での同等のもの）が無い、`-` が無い、標準入力が `<` / `<<` / `<<<` でリダイレクトされていない、パイプの右側でもない。`python3 -B` のようにオプションだけの起動も拒否する。`--version` / `-V` / `-h` / `--help` は拒否しない。

**補足**（A9）: コードを渡すオプションは次のとおりとする。
- python 系: `-c` / `-m`
- node: `-e` / `-p` / `--eval` / `--print`
- perl: `-e` / `-E`
- ruby: `-e`
- シェル: `-c`。シェルの `-s` は、標準入力がつながれていなければオプションだけの起動として扱う。

#### FR8: 処理系名の判定

**説明**: コマンド語の basename が既知の名前そのもの、または既知の名前に数字と点だけの接尾が付いたもの（`python3.14`、`python3.N`、`ipython3`、`node22` など）のとき、同じ処理系とみなす。それ以外の接尾（`python3-config`、`bashcov` など）は対象外。

#### FR9: コマンドの解析範囲

**説明**: `tool_input.command` の文字列を解析して判定する（入力に tty の情報は無い）。手順は次のとおり。
1. heredoc 本文を除く。
2. `;` `&&` `||` `|` 改行で単純コマンドに分ける。
3. リダイレクトを除く。
4. 先頭の環境変数の代入、オプションの無いラッパー（`env` / `nohup` / `nice` / `exec` / `command` / `time` / `sudo`）、`timeout DURATION` を読み飛ばす。
5. `bash -c` / `bash -lc` / `sh -c` にリテラル文字列が渡されていたら、その文字列を 1 段だけ同じ手順で判定する。

クォートの中、コメント、heredoc 本文は判定しない。

**補足**（A8）: 判定ロジックは `interpreter-mismatch-guard.py` の解析手順（heredoc 除去、単純コマンドへの分割、リダイレクト除去、ラッパー読み飛ばし）を写して使う。`em-workflow/hooks/` のファイルは import しない。

#### FR10: 対話モードでない起動は通す

**説明**: `python3 -c '...'`、`python3 script.py`、`python3 - <<EOF` は拒否しない（何も出力せず exit 0）。

#### FR11: fail-open

**説明**: 判定できない場合は、何も出力せず exit 0 で抜ける。hook 自体が起動できない・失敗した場合は Codex の既定の挙動（コマンドを実行する）に任せる。

**エラーケース**:
| エラー | 対応 |
|--------|------|
| 入力 JSON が壊れている | 何も出力せず exit 0 |
| `tool_input.command` が無いか文字列でない | 何も出力せず exit 0 |
| 閉じていないクォートや heredoc がある | 何も出力せず exit 0 |
| 例外が起きた | 何も出力せず exit 0 |
| オプション付きのラッパー（`env -i` など）でくるまれている | 何も出力せず exit 0 |
| hook 自体が起動できない・失敗した | Codex の既定の挙動（コマンドを実行する）に任せる |

#### FR12: 拒否の出力形式

**説明**: 拒否するときは stdout に次の JSON を出して exit 0 で抜ける。

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```

理由文は日本語で書き、`python3 -c`、スクリプトファイル、`python3 - <<EOF` への切り替えを示す。

#### FR13: レビュアーへの指示

**説明**: `em-workflow/agents/codex-reviewer.md` と `em-review/agents/codex-reviewer.md` の Step 4 の `<grounding_rules>` に入れる内容として、対話モードの処理系を起動せず、`python3 -c` などで確かめることを書き足す。Step 5 の起動行、各見出し、`'timeout of 600000 milliseconds'` の記述は変えない。

#### FR14: テストとルール

**説明**:
- `tests/test_codex_hook_interactive_guard.py` を足す。`(期待する判定 deny|silent, ラベル, コマンド)` の CASES 表を両方のコピーに対して流し、両コピーのバイト一致も確かめる。
- stub の codex を使うラッパーテストで、3 つの起動経路の argv に hook の `-c` 値（matcher `Bash`、そのプラグインのスクリプトの絶対パス）と `--dangerously-bypass-hook-trust` があることを確かめる。
- `.claude/rules/hook-tests.md` に、この hook のテストコマンドとケース表の形式を書いた節を足す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし。

### 5.2 セキュリティ要件
- NFR1: hook は標準ライブラリだけを使う。ネットワーク、ファイル書き込み、サブプロセスには触れない。
- NFR5: `--ignore-user-config` と `--ignore-rules` を外さない。

### 5.3 可用性要件
- NFR2: 誤爆（対話モードでないコマンドの拒否）を避けることを優先する。判定できないものは通す。

### 5.4 保守性要件
- NFR4: テストは stub の codex を PATH の先頭に置き、HOME を隔離して実行する。本物の Codex には触れない。`python3 -m unittest discover -s tests` がすべて通る。

### 5.5 互換性要件
- NFR3: 既存テストの固定を壊さない。
    - em-workflow ラッパーの起動は 1 回
    - テキストに `2>&1` を含めない
    - usage 文言
    - 既定経路は `--ignore-user-config` ありで `-p` / `-m` なし
    - `--litellm` 経路は `-p litellm -m MODEL` が連続し `--ignore-user-config` なし
    - em-review ラッパーの非コメント行で `'codex exec'` が 1 回
    - `codex-reviewer.md` の起動行と見出し

## 6. UI/UX要件

### 6.1 画面設計要件
該当なし。画面や見た目の変更は無い。

### 6.2 画面遷移
該当なし。

### 6.3 レスポンシブ対応
該当なし。

## 7. データ要件

### 7.1 データモデル概要
該当なし。永続化するデータは無い。

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| hook の入力（PreToolUse JSON） | `tool_input.command` | 文字列 | × | 判定するコマンド文字列。無いか文字列でない場合は fail-open（FR11） |
| hook の出力（拒否時） | `hookSpecificOutput.hookEventName` | 文字列 | ○ | `"PreToolUse"` |
| hook の出力（拒否時） | `hookSpecificOutput.permissionDecision` | 文字列 | ○ | `"deny"` |
| hook の出力（拒否時） | `hookSpecificOutput.permissionDecisionReason` | 文字列 | ○ | 日本語の理由文（FR12） |

### 7.3 データ保持期間
該当なし。

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Codex（`codex exec`） | `-c "hooks.PreToolUse=[...]"` と `--dangerously-bypass-hook-trust` を起動引数で渡す | PreToolUse hook の設定 |
| Codex の PreToolUse hook | hook スクリプトの stdin / stdout | PreToolUse JSON、拒否の JSON |

### 8.2 API仕様要件
- `-c` の値の形は FR1 の補足（A6）のとおり。正確なキー名と、command がシェル経由で実行されるかどうかは、実装時に Codex 0.160.0 で確かめる。

## 9. 制約条件

### 9.1 技術的制約
- hook は Python 3 の標準ライブラリだけを使う（FR5、NFR1）。
- 2 つの hook ファイルはバイト単位で同一にする（FR5）。
- `em-workflow/hooks/` のファイルは import しない（A8）。
- `--ignore-user-config` と `--ignore-rules` を外さない（NFR5）。
- この hook は Codex 専用で、`em-workflow/hooks/hooks.json` には登録しない（A2）。

### 9.2 ビジネス上の制約
- version は手で変更しない。main への push 時に Actions が patch を上げる（A1）。
- `--ignore-user-config` の付け外しは変えない（A3）。
- ラッパーの usage 文言と受け付けるフラグは変えない（A4）。

### 9.3 スケジュール制約
該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-interactive-guard-hook/**`
- `test-docs/codex-interactive-guard-hook/**`

`feature-docs/codex-interactive-guard-hook/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-interactive-guard-hook/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-interactive-guard-hook/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-interactive-guard-hook/` ディレクトリを生成しないが、宣言された `test-docs/codex-interactive-guard-hook/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| hook の `-c` 値の正確なキー名と、command がシェル経由で実行されるかどうかが未確認（A6） | 中 | 実装時に Codex 0.160.0 で確かめる。パスに含まれる引用符や空白は TOML とシェルの両方でエスケープする |
| `write_stdin` 経由の対話、`code.interact()` のようにコードの中から開く対話モード、`deno repl` のようにサブコマンドで開く REPL は検知しない（A7） | 低 | 対象外とする |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: em-workflow 既定経路・`--litellm` 経路・em-review の各起動 argv に、`hooks.PreToolUse` を設定する `-c` 値が含まれる。matcher は `"Bash"` で、command はそのプラグインの `scripts/codex-hook-interactive-guard.py` を絶対パスで指す。
- [ ] AC2: 同じ 3 つの起動 argv に `--dangerously-bypass-hook-trust` が含まれる。readonly と readwrite の両モードで成り立つ。
- [ ] AC3: `em-workflow/scripts/` と `em-review/scripts/` に `codex-hook-interactive-guard.py` があり、2 つはバイト単位で同一である。
- [ ] AC4: `python3 -i`、`python3 -B -i -c ...`、`bash -i`、`python3 -Bi`、`node -i`、`lua -i`、`python3.14 -i`、`cd x && python3 -i`、`bash -lc 'python3 -i'` は拒否の JSON を出す。
- [ ] AC5: `python3`、`node`、`python3 -B`、`ruby`、`perl`、`deno`、`irb`、`ipython` を単独で起動すると拒否の JSON を出す。
- [ ] AC6: `python3 -c '...'`、`python3 script.py`、`python3 - <<EOF`、`python3 <<EOF`、`cmd | python3`、`python3 < f`、`python3 --version`、`python3 script.py -i`、`perl -i -pe ...`、`ruby -i`、`sed -i`、`echo 'python3 -i'`、`python3-config` は何も出力しない。
- [ ] AC7: 不正な JSON、command 欠落、閉じていないクォートでは、何も出力せず exit 0 になる。
- [ ] AC8: 両プラグインの `codex-reviewer.md` の Step 4 に、対話モードを使わず `python3 -c` などで確かめる旨が書かれ、Step 5 の起動行と見出しは変わっていない。
- [ ] AC9: `--ignore-user-config` の付け外しと usage 文言が変わらず、`python3 -m unittest discover -s tests` がすべて通る。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（hook、deny）: AC4 と AC5 の各コマンドを PreToolUse JSON（tool_name `"Bash"`）で渡すと、`hookSpecificOutput.permissionDecision` が `deny` になる。両方のコピーで確かめる。
- [ ] TS2（hook、silent）: AC6 の各コマンドと、クォート・コメント・heredoc 本文の中の `python3 -i` では、stdout が空で exit 0 になる。両方のコピーで確かめる。
- [ ] TS3（hook、fail-open）: 壊れた JSON、`tool_input` 欠落、command が文字列でない、閉じていないクォート、`env -i python3` では、stdout が空で exit 0 になる。
- [ ] TS4（hook、non-vacuity）: CASES 表に deny と silent の両方が含まれる。
- [ ] TS5（copies）: 2 つの hook ファイルのバイト列が一致する。
- [ ] TS6（wrapper argv）: stub の codex で、em-workflow readonly 既定経路、readwrite、readonly `--litellm MODEL`、em-review readonly の各起動を記録する。argv に hook の `-c` 値（Bash matcher、スクリプトの絶対パス）と `--dangerously-bypass-hook-trust` が含まれること、既存の固定（`--ignore-user-config`、`-p litellm -m MODEL` の連続、起動 1 回）が保たれることを確かめる。
- [ ] TS7（docs）: 両方の `codex-reviewer.md` の Step 4 の節に、対話モードの禁止と `python3 -c` への言及がある。
- [ ] TS8（regression）: `python3 -m unittest discover -s tests` の既存テストがすべて通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 対話モードの処理系 | `python3 -i` のように対話的に入力を待つ状態で起動された処理系 |
| 引数なし起動 | FR7 の条件をすべて満たす起動 |
| 誤爆 | 対話モードでないコマンドの拒否 |
| fail-open | 判定できない場合に、何も出力せず exit 0 で抜けてコマンドを通すこと |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 対象の処理系: `-i` で拒否するのは python 系、node、bash / sh / zsh / dash / ksh、lua。引数なし起動の拒否はこれに ruby、perl、deno、irb、ipython を加える。`perl -i`、`ruby -i`、`php -i`、`sed -i` は拒否しない（FR6、FR7）。
- [x] 引数なし起動の定義: スクリプトのオペランド、`-c` / `-m` / `-e`、`-` のいずれも無く、標準入力がリダイレクトされておらずパイプの右側でもない起動。`python3 -B` のようなオプションだけの起動も拒否し、`--version` / `-V` / `-h` / `--help` は通す（FR7）。
- [x] コマンドの解析の深さ: 単純コマンドへの分割とラッパーの読み飛ばしに加え、`bash -c` / `bash -lc` / `sh -c` のリテラル文字列を 1 段だけ判定する。解析できないものは通す（FR9、FR11）。
- [x] レビュアーへの指示の置き場所: 両プラグインの `codex-reviewer.md` の Step 4 で組み立てる `<grounding_rules>`。Step 5 の起動行と見出しは変えない（FR13）。
- [x] 2 つの hook のコピー: バイト単位で同一にし、テストで一致を確かめ、1 つの CASES 表を両方に流す（FR5、FR14）。
- [x] 拒否の出力形式: `hookSpecificOutput` の deny。理由文に `python3 -c`、スクリプトファイル、`python3 - <<EOF` への切り替えを書く（FR12）。
- [x] ラッパーの引数: 既存の `-c` 上書きと `--litellm` の `-p` / `-m` は消さず、hook の `-c` と `--dangerously-bypass-hook-trust` を足すだけにする。既存テストが固定する並びは崩さない（FR1、FR2、NFR3）。
- [x] 版付きの名前: 既知の名前に数字と点だけの接尾が付いたものを同じ処理系とみなす（FR8）。
- [x] 適用範囲: readonly / readwrite、既定経路 / `--litellm` 経路、em-review の全起動に渡す（FR4）。
- [x] デザインステップ: 省略する。

### 14.2 未確認・保留事項
- [ ] hook の `-c` 値の正確なキー名と、command がシェル経由で実行されるかどうか。実装時に Codex 0.160.0 で確かめる（A6）。

### 14.3 前提とした事項
- A1: version は手で変更しない。main への push 時に Actions が patch を上げる。
- A2: この hook は Codex 専用で、`em-workflow/hooks/hooks.json` には登録しない。
- A3: `--ignore-user-config` の付け外しは変えない。
- A4: ラッパーの usage 文言と受け付けるフラグは変えない。
- A5: ラッパーは hook スクリプトの有無を確かめずに渡す。ファイルが無い場合は Codex の fail-open に任せる。
- A6: `-c` の値は TOML 配列 `[{matcher="Bash", hooks=[{type="command", command="python3 '<SCRIPT_DIR>/codex-hook-interactive-guard.py'"}]}]` の形とする。正確なキー名と、command がシェル経由で実行されるかどうかは、実装時に Codex 0.160.0 で確かめる。パスに含まれる引用符や空白は TOML とシェルの両方でエスケープする。
- A7: `write_stdin` 経由の対話、`code.interact()` のようにコードの中から開く対話モード、`deno repl` のようにサブコマンドで開く REPL は検知しない。
- A8: hook の判定ロジックは `interpreter-mismatch-guard.py` の解析手順（heredoc 除去、単純コマンドへの分割、リダイレクト除去、ラッパー読み飛ばし）を写して使う。`em-workflow/hooks/` のファイルは import しない（em-review からは参照できないため）。
- A9: 引数なし判定でのコードを渡すオプションは、python 系は `-c` / `-m`、node は `-e` / `-p` / `--eval` / `--print`、perl は `-e` / `-E`、ruby は `-e`、シェルは `-c` とする。シェルの `-s` は、標準入力がつながれていなければオプションだけの起動として扱う。

## 15. 参考資料

- `.claude/rules/hook-tests.md`: フックのテストのルール
- `em-workflow/hooks/interpreter-mismatch-guard.py`: 解析手順の写し元（A8）

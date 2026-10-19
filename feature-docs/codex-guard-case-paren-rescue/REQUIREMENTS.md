---
title: "codex-guard-case-paren-rescue"
created_date: 2026-10-20
status: draft
---

# codex-guard-case-paren-rescue - 要件定義書

## 1. 概要

### 1.1 背景
codex-guard-subshell-anon-arg-semicolon で追加した `)` の救済は、case のパターンを終える `)` を、仮グループの連なりのすぐ外側にあるサブシェルの `(` グループの閉じとして読む。その `)` の後に標準入力のリダイレクトがあると、それより前に書いた対話起動がつながったものとして扱われる（レビュー指摘 5e71ff00fdbe5aff）。

### 1.2 目的
`codex-hook-interactive-guard.py`（em-workflow と em-review のコピー）で、deny が silent に変わる退行を取り除く。

### 1.3 スコープ
- 対象: コマンド位置の `case` を読んだ仮グループと、その仮グループの連なりに対する `)` の救済。
- 対象ファイル: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`、`tests/test_codex_hook_interactive_guard.py`。
- 対象外: メインの読み取りが case のパターン終端を一般に追う広い修正（別フィーチャー）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard.py の 2 つのコピーで、deny から silent への退行を取り除く。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 |
|----|--------|
| FR1 | コマンド位置の case で仮グループに印を付ける |
| FR2 | 仮グループの連なりに沿って case 印を継承する |
| FR3 | 印のある連なりには `)` の救済を行わない |
| FR4 | その他の読み方は変えない |
| FR5 | docstring を追従させる |
| FR6 | 2 つのコピーを同じ変更で直す |
| FR7 | CASES に退行防止の行を足す |

### 4.2 機能詳細

#### FR1: コマンド位置の case で仮グループに印を付ける
メインの読み取りが単純コマンドに語を追加するとき、次のすべてを満たせば、そのグループに case 印（`_Group` の新しいフィールド）を付ける。
- その語が、先頭の予約語の並び（RESERVED_WORDS: `!`、`time`、`then`、`do` ほか。`time` の後の動的でない `-p` を含む）の後で `_append_word` が保持する最初の語である
- テキストが `case` である
- クォート・エスケープ・展開を含まない
- 最も内側の開いているグループが仮グループである

`! case` と `time case` も対象に含む。クォート・エスケープ・展開を含む `case`、またはこの位置にない `case` は印を付けない。印はそのグループについて永続する。

#### FR2: 仮グループの連なりに沿って case 印を継承する
`_mark_provisional` が、親が仮グループである仮グループを開くとき、親だけから決まる別の値を子に定数時間で固定する。値は、親の case 印、または親自身の継承値とする。この値は `outer_blocked` とは別に保持する。`}` の救済（`_closes_after_rescue` / `_close_after_rescue`）はこの値を読まない。

#### FR3: 印のある連なりには `)` の救済を行わない
`_closes_paren_after_rescue` は、グループ自身が case 印か継承値を持つとき False を返す。その `)` は `_close_paren` の既存の読み方に従う。最も内側の開いているグループが `(` グループ（ここでは仮グループ自身）ならそれを閉じ、そうでなければ区切りとして扱う。

#### FR4: その他の読み方は変えない
次はそのまま変えない。
- `}` の救済
- 入力末尾の救済（`_rescue_argument_groups`）
- 印も継承値も持たないグループへの `)` の救済
- 仮グループが最も内側にある間にコマンド位置の `case` を読まない、すべての入力の読み方

メインの読み取りは、引き続き case のパターン終端を一般には追わない。

#### FR5: docstring を追従させる
次の docstring に、case 印・その継承・`)` の救済の例外を記述する。
- モジュール docstring の手順 4（`)` の救済の段落）
- `_Parser` クラスの docstring
- `_Group` のフィールド一覧
- `_mark_provisional`
- `_append_word`（または印を付ける箇所）
- `_close_paren`
- `_closes_paren_after_rescue`

テストが確認する既存の docstring マーカーはすべて残す。

#### FR6: 2 つのコピーを同じ変更で直す
`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を同じ変更の中で入れ、バイト単位で同一に保つ。

#### FR7: CASES に退行防止の行を足す
12 章の TS-1 から TS-9 の行を、`tests/test_codex_hook_interactive_guard.py` の CASES に `(expected, label, command)` の形で足す。この表は 2 つのコピーの両方に流す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読み取りは入力長に対して線形のままで、再帰を使わない。印の設定は追加する語ごとに定数時間、継承値の固定は開くグループごとに定数時間、`)` での判定は定数時間とする。

### 5.4 保守性要件
- NFR2: 2 つのガードのコピーはバイト単位で同一のまま保つ。

## 9. 制約条件

### 9.1 技術的制約
- 狭い修正に限る。メインの読み取りが case のパターン終端を追う広い修正は別フィーチャーとし、TS-9 は silent のまま（A1）。
- 継承値は `outer_blocked` とは別に持ち、`}` の救済は読まない。`}` の救済の振る舞いは変えない（A2）。
- コマンド位置は、先頭の予約語の並びの後で `_append_word` が保持する最初の語とする。語はむき出しで動的でないこと（A3）。
- プラグインの version は変更しない。main への push 時に GitHub Actions が patch を上げる（A4）。
- 既存の deny / silent の CASES 行は変えずに残す（A5）。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-case-paren-rescue/**`
- `test-docs/codex-guard-case-paren-rescue/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 両方のガードが、stdin `{"tool_input":{"command":"zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'"}}` に deny を返す（TS-1）。
- [ ] AC2: 両方のガードが、同じ形の `! case` 版と `time case` 版に deny を返す（TS-2、TS-3）。
- [ ] AC3: 両方のガードが、入れ子の連なりの形（外側の仮グループで `case` を読み、内側の仮グループが最も内側にある間にパターンの `)` が来る）に deny を返す（TS-4）。
- [ ] AC4: 標準入力が実際につながる形（外側のサブシェルの後のリダイレクト、サブシェルへのパイプ）と、`case` がコマンド位置のキーワードでない形（引数位置、クォート付き）は silent のまま（TS-5〜TS-8）。
- [ ] AC5: 既存の限界 `( python3; case x in x) < /dev/null :;; esac; )` は仮グループが無く対象外。結果（silent）は変わらない（TS-9）。
- [ ] AC6: `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。既存の CASES 行（`)` の救済の行と `}` の救済の行）、`test_the_two_copies_are_byte_identical`、docstring マーカーのテスト、深さ／線形性のテストをすべて含む（TS-10）。

## 12. テストシナリオ

- TS-1（deny）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'`
    - レビュー 5e71ff00fdbe5aff の再現例。パターンの `)` は外側のサブシェルではなく、印のある仮グループを閉じる。
- TS-2（deny）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'`
    - 予約語 `!` の後の `case`。
- TS-3（deny）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'`
    - 予約語 `time` の後の `case`。
- TS-4（deny）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'`
    - 連なりの継承。ガードは `${v:-${x:-}` を最初の `}` で閉じる 1 つの動的な語として読む。`case` が仮グループ P に印を付ける。`bar(b; ...` が仮の子 P2（chain_base は G1、継承値あり）を開く。`x)` は G1 ではなく P2 を閉じるので、リダイレクトは P2 にだけつながる。`y)` が印のある P を閉じ、`esac; )` が G1 を閉じる。G1 はつながらない。実際の zsh は `${...}` 全体を case の対象として読む。
- TS-5（silent）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'`
    - リダイレクトが外側のサブシェルの後にあり、本体は実際につながる。
- TS-6（silent）: `zsh -c 'setopt nobadpattern; echo x | ( function { python3; } foo(a; case x in x) :;; esac; )'`
    - 外側のサブシェルへのパイプが本体をつなぐ。
- TS-7（silent）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'`
    - 引数位置の `case` は印を付けない。`)` の救済は現状どおりサブシェルを閉じ、リダイレクトがつながる。zsh と一致する。
- TS-8（silent）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'`
    - クォート付きの `case` はキーワードではなく印を付けない。救済は現状どおり。
- TS-9（silent）: `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'`
    - 既存の限界で対象外、変更なし。仮グループが無く、メインの読み取りは case のパターン終端を追わない。既知の見逃しとしてラベルを付ける。
- TS-10（pass）: `python3 -m unittest tests.test_codex_hook_interactive_guard`
    - リポジトリのルートから実行する、両コピー対象のガードのテスト一式。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| case 印 | FR1 の条件で仮グループに付ける `_Group` の新しいフィールド |
| 継承値 | FR2 で `_mark_provisional` が子の仮グループに固定する、親の case 印または親の継承値 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 継承の扱い（requirement.case-mark-chain）: 連なりで継承する（inherit_in_chain）。継承値は `outer_blocked` とは別に持ち、`}` の救済は読まない。
- [x] コマンド位置の定義（requirement.case-command-position）: 先頭の予約語の並びの後（after_reserved_run）。語はむき出しで動的でないこと。
- [x] TS-2、TS-3: HEAD では silent、base 0e4426d6 では deny、実際の zsh では MARKER が出力される（オーケストレーター確認済み）。
- [x] TS-4: HEAD では silent、base 0e4426d6 では deny、実際の zsh では MARKER が出力される（オーケストレーター確認済み）。
- [x] TS-5: HEAD では deny（救済が `x)` で外側のサブシェルを閉じ、末尾のリダイレクトが届かなくなる）、base 0e4426d6 では silent。修正で silent に戻る（オーケストレーター確認済み）。

### 14.2 未確認・保留事項
- なし

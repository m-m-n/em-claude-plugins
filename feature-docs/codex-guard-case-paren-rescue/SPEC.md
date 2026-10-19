# Feature: codex-guard-case-paren-rescue

## 概要

`codex-hook-interactive-guard.py`（em-workflow と em-review のコピー）の `)` の救済が、case のパターンを終える `)` を仮グループの連なりのすぐ外側にあるサブシェルの `(` グループの閉じとして読み、その後の標準入力リダイレクトが前に書いた対話起動につながってしまう退行（レビュー指摘 5e71ff00fdbe5aff）を取り除く。要件は `REQUIREMENTS.md` を参照。

## 目的

- 2 つのガードのコピーで、deny から silent への退行を取り除く。

## 技術要件

### 機能要件
- **FR1:** コマンド位置の case で仮グループに印を付ける。メインの読み取りが単純コマンドに語を追加するとき、(a) その語が先頭の予約語の並び（RESERVED_WORDS: `!`、`time`、`then`、`do` ほか。`time` の後の動的でない `-p` を含む）の後で `_append_word` が保持する最初の語で、(b) テキストが `case` で、(c) クォート・エスケープ・展開を含まず、(d) 最も内側の開いているグループが仮グループであれば、そのグループに case 印（`_Group` の新しいフィールド）を付ける。`! case` と `time case` を含む。クォート・エスケープ・展開を含む `case`、この位置にない `case` は印を付けない。印はそのグループについて永続する。
- **FR2:** 仮グループの連なりに沿って case 印を継承する。`_mark_provisional` が親も仮グループである仮グループを開くとき、親だけから決まる値（親の case 印、または親自身の継承値）を子に定数時間で固定する。この値は `outer_blocked` とは別に持つ。`}` の救済（`_closes_after_rescue` / `_close_after_rescue`）はこの値を読まない。
- **FR3:** 印のある連なりには `)` の救済を行わない。`_closes_paren_after_rescue` は、グループ自身が case 印か継承値を持つとき False を返す。その `)` は `_close_paren` の既存の読み方に従い、最も内側の開いているグループが `(` グループ（ここでは仮グループ自身）ならそれを閉じ、そうでなければ区切りとして扱う。
- **FR4:** その他の読み方は変えない。`}` の救済、入力末尾の救済（`_rescue_argument_groups`）、印も継承値も持たないグループへの `)` の救済、仮グループが最も内側にある間にコマンド位置の `case` を読まないすべての入力の読み方は、そのまま保つ。メインの読み取りは引き続き case のパターン終端を一般には追わない。
- **FR5:** docstring を追従させる。モジュール docstring の手順 4（`)` の救済の段落）、`_Parser` クラスの docstring、`_Group` のフィールド一覧、`_mark_provisional`、`_append_word`（または印を付ける箇所）、`_close_paren`、`_closes_paren_after_rescue` に、case 印・その継承・`)` の救済の例外を記述する。テストが確認する既存の docstring マーカーはすべて残す。
- **FR6:** 2 つのコピーを同じ変更で直す。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を入れ、バイト単位で同一に保つ。
- **FR7:** CASES に退行防止の行を足す。TS-1 から TS-9 の行を `tests/test_codex_hook_interactive_guard.py` の CASES に `(expected, label, command)` の形で足す。この表は 2 つのコピーの両方に流す。

### 非機能要件
- **NFR1:** 読み取りは入力長に対して線形のままで、再帰を使わない。印の設定は追加する語ごとに定数時間、継承値の固定は開くグループごとに定数時間、`)` での判定は定数時間とする。
- **NFR2:** 2 つのガードのコピーはバイト単位で同一のまま保つ。

## 実装方針

### 変更対象
- `em-workflow/scripts/codex-hook-interactive-guard.py`（FR1〜FR5）
- `em-review/scripts/codex-hook-interactive-guard.py`（FR6 で上と同一にする）
- `tests/test_codex_hook_interactive_guard.py`（FR7）

### 制約
- 狭い修正に限る。メインの読み取りが case のパターン終端を追う広い修正は別フィーチャーとし、TS-9 は silent のまま（A1）。
- 継承値は `outer_blocked` とは別に持ち、`}` の救済は読まない。`}` の救済の振る舞いは変えない（A2）。
- コマンド位置は、先頭の予約語の並びの後で `_append_word` が保持する最初の語。語はむき出しで動的でないこと（A3）。
- プラグインの version は変更しない。main への push 時に GitHub Actions が patch を上げる（A4）。
- 既存の deny / silent の CASES 行は変えずに残す（A5）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-case-paren-rescue/**`
- `test-docs/codex-guard-case-paren-rescue/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## テストシナリオ

### ユニットテスト（CASES の行、FR7）
- [ ] TS-1（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'` — レビュー 5e71ff00fdbe5aff の再現例。パターンの `)` は外側のサブシェルではなく、印のある仮グループを閉じる。
- [ ] TS-2（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'` — 予約語 `!` の後の `case`。
- [ ] TS-3（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'` — 予約語 `time` の後の `case`。
- [ ] TS-4（deny、FR2・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'` — 連なりの継承。`case` が仮グループ P に印を付け、`bar(b; ...` が仮の子 P2（chain_base は G1、継承値あり）を開く。`x)` は G1 ではなく P2 を閉じ、リダイレクトは P2 にだけつながる。`y)` が P を、`esac; )` が G1 を閉じる。G1 はつながらない。
- [ ] TS-5（silent、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'` — リダイレクトが外側のサブシェルの後にあり、本体は実際につながる。HEAD では deny、修正で silent に戻る。
- [ ] TS-6（silent、FR1・FR3）: `zsh -c 'setopt nobadpattern; echo x | ( function { python3; } foo(a; case x in x) :;; esac; )'` — 外側のサブシェルへのパイプが本体をつなぐ。
- [ ] TS-7（silent、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'` — 引数位置の `case` は印を付けず、`)` の救済は現状どおり。
- [ ] TS-8（silent、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'` — クォート付きの `case` は印を付けず、救済は現状どおり。
- [ ] TS-9（silent、FR4）: `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'` — 既存の限界で対象外、変更なし。既知の見逃しとしてラベルを付ける。

### テスト一式
- [ ] TS-10（pass、FR5・FR6・NFR1・NFR2）: リポジトリのルートから `python3 -m unittest tests.test_codex_hook_interactive_guard` を実行する。既存の CASES 行（`)` の救済の行と `}` の救済の行）、`test_the_two_copies_are_byte_identical`、docstring マーカーのテスト、深さ／線形性のテストをすべて含む。

## 成功基準

- [ ] AC1: 両方のガードが TS-1 に deny を返す。
- [ ] AC2: 両方のガードが TS-2、TS-3 に deny を返す。
- [ ] AC3: 両方のガードが TS-4 に deny を返す。
- [ ] AC4: TS-5〜TS-8 は silent のまま。
- [ ] AC5: TS-9 の結果（silent）は変わらない。
- [ ] AC6: TS-10 が通る。

## 未解決事項

- なし

## 参照

- 要件定義書: `feature-docs/codex-guard-case-paren-rescue/REQUIREMENTS.md`

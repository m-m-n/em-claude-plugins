---
title: "codex-guard-case-paren-rescue"
created_date: 2026-10-20
status: draft
---

# codex-guard-case-paren-rescue - 要件定義書

## 1. 概要

### 1.1 背景
`codex-hook-interactive-guard.py` の 2 つのコピー（em-workflow / em-review）で、`)` の救済に deny から silent への退行がある。対象はレビュー指摘 5e71ff00fdbe5aff と、round 1 の指摘 285d9bc33784bb3d・df4afa83e782d56a・b374e6b3c3d4b471。

- 5e71ff00fdbe5aff: case のパターンを終える `)` の後に標準入力のリダイレクトがある形（TS-1）。
- 285d9bc33784bb3d、df4afa83e782d56a: esac で case 印を外す（TS-11〜TS-13）。
- b374e6b3c3d4b471: クォートやエスケープを含む予約語を、先頭の予約語の並びに数えない（TS-14、TS-15）。

### 1.2 目的
codex-hook-interactive-guard.py の 2 つのコピーで、deny から silent への退行を取り除く。

### 1.3 スコープ
- 対象: 仮グループの上で数える case 印と継承値、それに基づく `)` の救済の例外。
- 対象ファイル: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`、`tests/test_codex_hook_interactive_guard.py`。
- 対象外: 仮グループの外で case のパターン終端を追う広い修正（別フィーチャー）。TS-9 は silent のまま残す。

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard.py の 2 つのコピー（em-workflow / em-review）で、deny から silent への退行を取り除く。対象はレビュー指摘 5e71ff00fdbe5aff と、round 1 の指摘 285d9bc33784bb3d・df4afa83e782d56a・b374e6b3c3d4b471。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 |
|----|--------|
| FR1 | コマンド位置の case と esac で仮グループの case 印を増減する |
| FR2 | 仮グループの連なりに沿って case 印を継承する |
| FR3 | 印のある仮グループでは `)` の救済を行わない |
| FR4 | その他の読み方は変えない |
| FR5 | docstring を追従させる |
| FR6 | 2 つのコピーを同じ変更で直す |
| FR7 | テストを追従させる |

### 4.2 機能詳細

#### FR1: コマンド位置の case と esac で仮グループの case 印を増減する
case 印（`_Group.case_mark`）を、そのグループで読んだ case のうち、まだ esac で閉じていないものの数として持つ。フィールド名は変えない。

メインの読み取りが単純コマンドに語を追加するとき、最も内側の開いているグループが仮グループなら、次のとおり増減する。

1. 増やす: 語がコマンド位置にあり、テキストが `case` で、クォート・エスケープ・展開を含まない。このとき 1 増やす。
2. 減らす: 語のテキストが `esac` で、クォート・エスケープ・展開を含まず、次のどちらかを満たす。
    - (a) コマンド位置にある。
    - (b) 同じ単純コマンドの中で、(1) で数えた `case`・任意の 1 語・むき出しの `in` の 3 語の直後にある。

    このとき、グループ自身の case 印が 1 以上ならそれを 1 減らす。0 なら、継承値（FR2）が 1 以上のときそれを 1 減らす。両方 0 なら何もしない。

- コマンド位置とは、先頭にあるむき出しの予約語の並びの後で、`_append_word` が残す最初の語を指す。
- むき出しの予約語とは、RESERVED_WORDS の語でクォート・エスケープ・展開を含まないものを指す。むき出しの `time` の直後のむき出しの `-p` も並びに含める。
- クォートやエスケープを含む予約語（`"time"`、`\!`）は並びに数えず、並びはその語で終わる。
- このむき出しの並びの状態と、(2)(b) を判定する状態は、`_names_function` と `_names_anonymous_function` が使う状態（`run_open`・`after_time`・`lone_function`）とは別に持つ。
- 印はパターンを終える `)` を待っている間だけ効く。esac で 0 に戻ったグループは、印の無いグループと同じに読む。
- `! case` と `time case` も対象に含む。

#### FR2: 仮グループの連なりに沿って case 印を継承する
`_mark_provisional` が、親も仮グループである仮グループを開くとき、親の case 印と親の継承値の和を、子の継承値（`_Group.case_inherited`、フィールド名は変えない）として定数時間で固定する。親が仮グループでなければ 0 にする。

- 子の継承値は、その後 FR1 (2) の esac による減算でだけ変わる。開いた後に親の値が変わっても追従しない。
- 継承値は `outer_blocked` とは別に持つ。
- `}` の救済（`_closes_after_rescue` / `_close_after_rescue`）はこの値を読まない。

#### FR3: 印のある仮グループでは `)` の救済を行わない
`_closes_paren_after_rescue` は、グループ自身の case 印か継承値が 1 以上のとき False を返す。その `)` は `_close_paren` の既存の読み方に従う。最も内側の開いているグループが `(` グループ（ここでは仮グループ自身）ならそれを閉じ、そうでなければ区切りとして扱う。判定に使うのは最も内側のグループの値だけとする。

#### FR4: その他の読み方は変えない
次はそのまま変えない。
- `}` の救済
- 入力末尾の救済（`_rescue_argument_groups`）
- case 印も継承値も 0 のグループへの `)` の救済
- `_names_function` と `_names_anonymous_function` の判定
- 仮グループが最も内側にある間に、FR1 の位置でむき出しの `case` も `esac` も読まない入力の読み方

FR1 の位置にない `esac`（引数の位置にあるもの、クォート・エスケープ・展開を含むもの）は印を減らさない。メインの読み取りは、仮グループの外では case のパターン終端を追わない（TS-9）。

#### FR5: docstring を追従させる
次の箇所で、case 印が未完の case の数であること、FR1 の位置の esac で減ること、継承値の固定と減算、むき出しの予約語の並び、`)` の救済の例外を記述する。
- モジュール docstring の手順 4（`)` の救済の段落）
- `_Parser` クラスの docstring
- `_Group` のフィールド一覧
- `_mark_provisional`
- `_append_word`
- `_close_paren`
- `_closes_paren_after_rescue`
- 並びの状態を `_start_words` に置く場合は、その docstring

「The mark is never cleared」「It is never cleared」「for the rest of its life」といった、印が永続するという記述は取り除く。テストが確認する既存の docstring マーカー（`case mark`、`inherited value`、`case_mark`、`case_inherited` を含む）はすべて残す。

#### FR6: 2 つのコピーを同じ変更で直す
`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を同じ変更の中で入れ、バイト単位で同一に保つ。

#### FR7: テストを追従させる
- `tests/test_codex_hook_interactive_guard.py` の CASES に、TS-11 から TS-19 の行を `(expected, label, command)` の形で足す。この表は 2 つのコピーの両方に流す。
- 既存の TS-1〜TS-9、TS-7b、TS-8b の行はそのまま残す。
- CASES の case 印の説明コメントは、esac で印が減ることに合わせて改める。
- `TestGuardDocumentation` の case 印の docstring テストには、モジュール docstring・`_Parser`・`_Group`・`_append_word` に語 `esac` があることを確認する項目を足す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読み取りは入力長に対して線形のままにし、再帰を使わない。case 印の増減、むき出しの予約語の並びの状態、`in` の直後の esac を判定する状態の更新は、追加する語ごとに定数時間とする。継承値の固定は開くグループごとに定数時間、`)` での判定も定数時間とする。

### 5.4 保守性要件
- NFR2: 2 つのガードのコピーはバイト単位で同一のまま保つ。

## 9. 制約条件

### 9.1 技術的制約
- A1: 狭い修正に限る。case と esac は仮グループの上でだけ数える。仮グループの外で case のパターン終端を追う広い修正は別フィーチャーとし、TS-9 は silent のまま残す。
- A2: 継承値は `outer_blocked` とは別に持ち、`}` の救済はこれを読まない。`}` の救済の振る舞いは変えない。
- A3: コマンド位置とは、先頭にあるむき出しの予約語の並びの後で `_append_word` が残す最初の語とする。並びに数えるのは、クォート・エスケープ・展開を含まない予約語と、むき出しの time の直後のむき出しの -p だけとする。case と esac 自身もむき出しであることを条件にする。
- A4: プラグインの version は変更しない。main への push 時に GitHub Actions が patch を上げる。
- A5: 既存の deny / silent の CASES 行（TS-1〜TS-9、TS-7b、TS-8b を含む）は変えずに残す。
- A6: case 印は真偽値ではなく、未完の case の数として持つ。
- A7: esac はまず自分の case 印を減らし、それが 0 のときだけ継承値を減らす。
- A8: フィールド名 `case_mark` と `case_inherited` は変えない。

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
- [ ] AC1: 両方のガードが TS-1 に deny を返す。
- [ ] AC2: 両方のガードが TS-2、TS-3 に deny を返す。
- [ ] AC3: 両方のガードが TS-4 に deny を返す。
- [ ] AC4: TS-5〜TS-8 は silent のまま、既存の TS-7b、TS-8b は deny のままである。
- [ ] AC5: TS-9 の結果（silent）は変わらない。
- [ ] AC6: TS-10 が通る。
- [ ] AC7: 両方のガードが TS-11、TS-12、TS-13 に deny を返す（esac で印が外れる。指摘 285d9bc33784bb3d、df4afa83e782d56a）。
- [ ] AC8: 両方のガードが TS-14、TS-15 に deny を返す（クォートやエスケープを含む予約語は並びに数えない。指摘 b374e6b3c3d4b471）。
- [ ] AC9: 両方のガードが TS-16、TS-17 に deny を返す（入れ子の case を数で持つ。継承値も esac で減る）。
- [ ] AC10: 両方のガードが TS-18、TS-19 に deny を返す（引数の位置の esac と、クォート付きの esac は印を減らさない）。

## 12. テストシナリオ

### 12.1 既存の行（変更なし）
- TS-1（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'`
    - レビュー 5e71ff00fdbe5aff の再現例。
- TS-2（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'`
    - むき出しの `!` の後の case。
- TS-3（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'`
    - むき出しの `time` の後の case。
- TS-4（deny、FR2・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'`
    - 連なりの継承。`x)` は継承値を持つ P2 を閉じ、`y)` は P を閉じる。`esac` は G1 の中で読むので印に関係しない。
- TS-5（silent、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'`
- TS-6（silent、FR1・FR3）: `zsh -c 'setopt nobadpattern; echo x | ( function { python3; } foo(a; case x in x) :;; esac; )'`
- TS-7（silent、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'`
    - TS-7b も残す。
- TS-8（silent、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'`
    - TS-8b も残す。
- TS-9（silent、FR4）: `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'`
    - 既知の見逃しで対象外。変更なし。

### 12.2 テスト一式
- TS-10（pass、FR5・FR6・FR7・NFR1・NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard`
    - リポジトリのルートから実行する。既存の CASES 行、`test_the_two_copies_are_byte_identical`、docstring マーカーのテスト、深さと線形性のテストをすべて含む。

### 12.3 追加する行（FR7）
- TS-11（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x in esac; )'`
    - 指摘 285d9bc33784bb3d の再現例。`in` の直後の esac で印が 0 に戻り、最後の `)` が連なりを救済して G1 を閉じる。
- TS-12（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in esac; python3 -i; )'`
    - 指摘 df4afa83e782d56a。空の case の後の起動。
- TS-13（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in (x) :;; esac; python3 -i; )'`
    - 指摘 df4afa83e782d56a。`(x)` は普通の `(` グループとして開いて閉じる。`;;` の後のコマンド位置の esac で印が 0 に戻る。
- TS-14（deny、FR1）: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; "time" case; python3 -i; )'`
    - 指摘 b374e6b3c3d4b471。クォート付きの `time` は並びに数えないので、case に印は付かない。
- TS-15（deny、FR1）: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; \! case; python3 -i; )'`
    - 指摘 b374e6b3c3d4b471。エスケープした `!` は並びに数えない。
- TS-16（deny、FR1・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (x) case y in (y) :;; esac;; z) < /dev/null :;; esac; )'`
    - 入れ子の case。内側の esac の後も印は 1 残り、`z)` は P を閉じる。印を真偽値で持つと、ここで救済が働いて silent になる。
- TS-17（deny、FR1・FR2・FR3）: `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in (x) :;; esac; )'`
    - 継承値の減算。P2 の中のコマンド位置の esac が P2 の継承値を 0 にし、最後の `)` が連なり（P2・P）を救済して G1 を閉じる。
- TS-18（deny、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) echo esac;; x) < /dev/null :;; esac; )'`
    - 引数の位置の esac は印を減らさず、`x)` は P を閉じる。
- TS-19（deny、FR1・FR4）: `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) "esac";; x) < /dev/null :;; esac; )'`
    - クォート付きの esac は印を減らさない。

### 12.4 境界の扱い
- A9: 次の位置の esac は印を減らさない。`case x` の後に改行があり、`in esac` が次の行に来る形。zsh の `case x { ... }` の形。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| case 印 | `_Group.case_mark`。そのグループで読んだ case のうち、まだ esac で閉じていないものの数 |
| 継承値 | `_Group.case_inherited`。`_mark_provisional` が子の仮グループを開くときに固定する、親の case 印と親の継承値の和。その後は FR1 (2) の esac による減算でだけ変わる |
| コマンド位置 | 先頭にあるむき出しの予約語の並びの後で、`_append_word` が残す最初の語 |
| むき出しの予約語 | RESERVED_WORDS の語でクォート・エスケープ・展開を含まないもの。むき出しの `time` の直後のむき出しの `-p` も並びに含める |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 継承の扱い（requirement.case-mark-chain）: 連なりで継承する（inherit_in_chain）。
- [x] コマンド位置の定義（requirement.case-command-position）: 先頭の予約語の並びの後（after_reserved_run）。
- [x] case 印と esac（rework.spec-change.case-mark-esac）: TS-9/AC5 の境界を保つ。予約語の並びはむき出しの予約語だけとする。印はパターン終端の `)` を待つ間だけ効く。
- [x] デザインステップ（design-step.decision）: decide_autonomously → skip。

### 14.2 未確認・保留事項
- なし

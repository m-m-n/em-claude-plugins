---
title: "codex-guard-brace-anon-arg-rescue"
created_date: 2026-10-18
status: draft
---

# codex-guard-brace-anon-arg-rescue - 要件定義書

## 1. 概要

### 1.1 背景
`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）は、波括弧群 `{ ... }` や匿名関数の本体の中に、匿名関数の引数から仮に開いて閉じない `(` があり、その中の最初の区切りが `;` の形を判定不能（出力なし）にする。

- 仮に開いた `foo(` の群の中で、末尾の `}` が普通の語として読まれる。
- 救済（`_rescue_argument_groups`）は仮の群を外すだけで、`}` を外側の `{` 群で読み直さない。
- 外側の群が未閉鎖のまま残って `_Undecidable("group")` になり、`;` の後の `python3 -i` を見逃す。
- zsh ではこの `{` 群は閉じており、`;` の後のコマンドが実行される。

feature `codex-guard-anon-arg-paren-comment` のレビュー round 1 で medium として deferred にした残件（stable_id `db007e0ea42e58d2`）。

### 1.2 目的
引数の `(` の救済（前回の TM-1 対策）は、`{ ...; }` や匿名関数の本体で包むだけですり抜けられる。この抜け道を塞ぎ、`;` の後の対話起動を deny にする。

### 1.3 スコープ
- 対象: `{` 群（匿名関数の本体と関数定義の本体を含む）の中で救済した仮の群の後の `}` の読み。
- 対象ファイル: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`、`tests/test_codex_hook_interactive_guard.py`。
- 範囲外: サブシェル版 `( function { :; } foo(a; python3 -i; )`（F07）。

## 2. ビジネス要件

### 2.1 ビジネス目標
`{ ...; }` や匿名関数の本体で包んだ引数の `(` による救済のすり抜けを塞ぎ、`;` の後の対話起動を deny にする。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| 該当なし | UI の無いフックスクリプトの解析ロジックの修正 |

### 2.3 期待される効果
- 再現の2形が deny になる。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 波括弧群で包んだ救済形を判定する | codex-hook-interactive-guard | 高 |

### 3.2 ユースケース詳細

#### UC01: 波括弧群で包んだ救済形を判定する

**アクター**: codex-hook-interactive-guard

**事前条件**:
- `zsh -c` に渡す文字列の中で、`{` 群の中に匿名関数の引数から仮に開いた `(` がある。

**基本フロー**:
1. 単独の素の `}` を読む。
2. 開いている仮の群の列が救済の条件を満たすか調べる。
3. 条件を満たし、列のすぐ外側が `{` 群なら、仮の群を救済して `{` 群を閉じる。
4. 閉じた後の読みを続け、`;` の後の対話起動を deny にする。

**代替フロー**:
- 救済の条件を満たさない場合、`}` は普通の語として読み、判定不能のまま（出力なし）にする（F03）。
- 関数定義の本体の中は skipped の規則で silent のままにする（F04）。

**事後条件**:
- 救済した `{` 群は `; }` で閉じた `{` 群と同じに扱われる。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 | 救済した仮の群の後の `}` が外側の `{` 群を閉じる | 単独の素の `}` で仮の群を救済し、外側の `{` 群を閉じる | 高 |
| F02 | 閉じた後の読み | 閉じた `{` 群を `; }` で閉じた群と同じに扱う | 高 |
| F03 | 救済できない形は従来どおり | 条件を満たさない `}` は普通の語のまま | 高 |
| F04 | 再現の2形を deny、関数定義の本体は silent | 再現形の判定結果 | 高 |
| F05 | docstring の更新と目印テスト | 規則の記述と目印の文の検査 | 中 |
| F06 | 回帰テスト | CASES と性能テストの追加 | 高 |
| F07 | サブシェル版は範囲外 | `(` 群の扱いは変えない | 中 |

F01〜F07 は SPEC.md の FR1〜FR7 に対応する。

### 4.2 機能詳細

#### F01: 救済した仮の群の後の `}` が外側の `{` 群を閉じる

**説明**: 単独の素の `}` を読んだときの規則。

**ビジネスルール**:
- 一番内側から外側へ連続して開いている仮の群の列が、救済の条件を満たすか調べる。
- 条件は既存の `_rescue_argument_groups` と同じで、最初の直接の区切りが `;` か単独の `&` であること。
- 内側の区切りは外側に受け継ぐ。
- 区切りは本体の読み手が実際に読んだもの（`_Group.first_sep`）で判定し、先読み（`_scan_parens`）の結果は使わない。
- 条件を満たし、列のすぐ外側が `{` 群（匿名関数の本体と関数定義の本体を含む）なら、`}` を読んだ時点で列の仮の群を救済する（その `(` は引数語の文字として読む）。そのうえで、その `{` 群を閉じる。
- 後に `)` が来たら、他の場所と同じく区切りとして読む（外側にサブシェルがあればそれを閉じる）。
- 語が残っていない `}` は、どの `{` 群も閉じる。
- 語が残っている `}` で閉じるのは、閉じる `{` 群が匿名関数の本体の中にある（in_anon）ときだけ。このとき、残っている語を群のコマンドとして確定してから閉じる。それ以外の `{` 群では、`}` を普通の語のままにする。
- 次の `}` は対象外で、閉じる契機にならない。
    - 引用符で囲んだもの
    - 展開の一部
    - 他の文字と続いて語の一部になっているもの
    - リダイレクトの対象

#### F02: 閉じた後の読み

**説明**: F01 で閉じた `{` 群は、`; }` で閉じた `{` 群と同じに扱う。

**ビジネスルール**:
- 閉じた後の入力リダイレクトとパイプはその群を接続する。その接続は、中の救済した区切りの後のコマンドにも届く。
- 閉じた群が匿名関数の本体なら、後の語は引数になる。
- それ以外の波括弧群の後の語は判定不能になる。
- 関数定義の本体なら、中のコマンドは判定しない（skipped）。本体の後に区切りを挟んで続く起動は判定する。

#### F03: 救済できない形は従来どおり

**説明**: 次の場合、`}` は従来どおり普通の語として読み、判定不能のまま（出力なし）にする。

**ビジネスルール**:
- 列の最初の直接の区切りが改行・`&&`・`||`・`|`・`|&` の場合。
- 区切りが無い場合。
- 列のすぐ外側が `{` 群でない（`(` 群、またはトップレベル）場合。
- 救済に失敗した `}` は、開いている群の状態を変えない。

#### F04: 再現の2形を deny、関数定義の本体は silent

**ビジネスルール**:
- `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` を deny にする。
- `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` を deny にする。
- 関数定義の本体の中で救済した形（例: `f() { function { :; } foo(a; python3 -i; }`）は、skipped の規則で silent のままにする。

#### F05: docstring の更新と目印テスト

**ビジネスルール**:
- F01〜F03 の規則を次の箇所に書く。
    - モジュール docstring の手順4
    - `_Parser`・`_Group.provisional`・`_rescue_argument_groups` の docstring
    - `_finish_word` の `}` まわりのコメント
- 仮の群を「入力の終わりまで閉じない場合だけ救済する」とする既存の記述は、`}` の時点の救済を反映して書き直す。対象は次の2つ。
    - モジュール docstring の「When a provisional group is never closed (its `)` sits in a comment, or there is none)」
    - `_Group.provisional` の「may be rescued when input ends, and no other group ever is」
- 既存の目印の文（RESCUE_PROVISIONAL_MARKER と RESCUE_MARKERS）は残す。
- STALE_DOCSTRING_SENTENCES に当たる文は戻さない。
- モジュール docstring と `_Parser` の docstring に「救済した区切りの後の `}` が外側の `{` 群を閉じる」趣旨の文を書く。その文を目印として TestGuardDocumentation に加え、両方のコピーで検査する。

#### F06: 回帰テスト

**ビジネスルール**:
- CASES に足すもの: 再現の2形（deny）、F01〜F03 の境界ケース（12 章の各形）。
- ケース 604 はラベルを skipped の趣旨に改め、判定は silent のままにする。
- 性能テストを足す。深い仮の群の列（救済できない列を含む）と大量の `}` を組み合わせた入力で、両方のコピーが制限時間内に答えを返すことを確かめる。

#### F07: サブシェル版は範囲外

**ビジネスルール**:
- 今回扱うのは `{` 群（匿名関数の本体と関数定義の本体を含む）だけ。
- `( function { :; } foo(a; python3 -i; )` の扱いは変えない。この形では `)` が仮の群を閉じ、外側の `(` が開いたまま残るので silent のまま。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 解析は入力の長さに対して線形時間に保ち、再帰を使わない（TestNoRecursion）。
- `}` ごとの救済判定で、開いている群をさかのぼって走査しない。群が開いた時点で決まる値を持たせるなどして、`}` 1個あたり償却定数時間にする。
- 各仮の群が外されるのは1回だけ。
- 救済に失敗する `}` が続く場合も線形を保つ。

### 5.2 セキュリティ要件
- 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（TestStaticConstraints）。

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- em-workflow と em-review の2つのコピーを同じ変更の中で直し、バイト単位で同一に保つ（TestCopies）。
- plugin の version は変更しない。

### 5.5 互換性要件
- 既存の CASES の判定は変えない。変わるのはケース 604 のラベルだけ。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 線形時間・再帰なし（5.1）。
- 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない（5.2）。
- 2つのコピーをバイト単位で同一に保つ（5.4）。

### 9.2 ビジネス上の制約
- 該当なし

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-brace-anon-arg-rescue/**`
- `test-docs/codex-guard-brace-anon-arg-rescue/**`

`feature-docs/codex-guard-brace-anon-arg-rescue/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-brace-anon-arg-rescue/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-brace-anon-arg-rescue/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `{ function { :; } foo(a; python3 -i; } )` のように末尾に余分な `)` がある形は、zsh では構文エラーで実行されないが deny になりうる | 低 | 誤拒否を許容する |
| 匿名関数の外の通常の `{` 群で語が残っている `}`（例: `{ function { :; } foo(a; printf REACHED }`）の見逃し | 低 | 既存の規則どおり普通の語のままとし、見逃しは残す |
| サブシェル版 `( function { :; } foo(a; python3 -i; )` の見逃し | 低 | 残し、別の課題とする |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 再現1 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` が、両方のコピーで deny を返す。
- [ ] AC2: 再現2 `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` が、両方のコピーで deny を返す。
- [ ] AC3: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'` は silent、`zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'` は deny を返す。
- [ ] AC4: 救済できない形は silent のまま。最初の区切りが改行・`&&` の形、閉じる `}` が無い既存ケース 601、`}` が引用符の中・語の一部・リダイレクトの対象の形、サブシェル版が該当する。
- [ ] AC5: 既存の CASES の判定がすべて変わらない（ケース 604 はラベルだけ変わり、判定は silent）。`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る。
- [ ] AC6: 深い仮の群の列（救済できない列を含む）の後に `}` を大量に並べた入力で、両方のコピーが TestMalformedAndDeepInput の TIMEOUT 内に答えを返す。
- [ ] AC7: 2つのコピーがバイト単位で同一である。
- [ ] AC8: 「救済した区切りの後の `}` が外側の `{` 群を閉じる」趣旨の目印の文が、両方のコピーのモジュール docstring と `_Parser` の docstring にある。TestGuardDocumentation がそれを検査する。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点

各コマンドは両方のコピーで期待する判定を返す。`\n` は改行を表す。

- [ ] 正常系（deny）:
    - TS1 再現1: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'`
    - TS2 再現2: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'`
    - TS3 単独の `&` が区切り: `zsh -c 'setopt nobadpattern; { function { :; } foo(a & python3 -i; }'`
    - TS4 コメントの中の `)` は救済を妨げない（`}` の時点で確定）: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; } #)'`
    - TS5 プログラムを渡さない起動: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; }'`
    - TS8 入れ子の仮の群を内側から救済: `zsh -c 'setopt nobadpattern; { function { :; } foo(function { :; } bar(a; python3 -i; }'`
    - TS9 仮の群の中で入れ子の `{` 群が普通に閉じる: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; { python3 -i; }; }'`
    - TS10 語が残っている `}` で、閉じる `{` 群が in_anon なので語を確定して閉じる: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i }'`
    - TS12 閉じた匿名本体の後は引数、区切りの先の起動を判定: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; :; } arg; python3 -i'`
    - TS15 関数定義の本体の後の起動は判定: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'`
- [ ] 正常系（silent）:
    - TS6 閉じた `{` 群の入力リダイレクトが救済後のコマンドに届く: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; } < /dev/null'`
    - TS7 閉じた `{` 群のパイプ接続が救済後のコマンドに届く: `zsh -c 'setopt nobadpattern; echo x | { function { :; } foo(a; python3; }'`
    - TS11 匿名でない `{` 群で語が残っている `}` は普通の語: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; echo }'`
    - TS13 匿名でない波括弧群の後の語は判定不能: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; :; } arg'`
    - TS14 関数定義の本体は skipped: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'`
- [ ] 異常系（救済できない形、silent）:
    - TS16 最初の区切りが改行: `zsh -c 'setopt nobadpattern; { function { :; } foo(a\npython3 -i; }'`
    - TS17 最初の区切りが `&&`: `zsh -c 'setopt nobadpattern; { function { :; } foo(a && python3 -i; }'`
    - TS18 引用符の中の `}` は閉じない: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; "}"'`
    - TS19 語の一部の `}` は閉じない: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }x'`
    - TS20 リダイレクトの対象の `}` は閉じない: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; echo > }'`
    - TS21 サブシェル版は範囲外で従来どおり: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'`
- [ ] 境界値: TS8〜TS13、TS16〜TS20
- [ ] セキュリティ: TS26 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（TestStaticConstraints）
- [ ] パフォーマンス:
    - TS22 救済できない深い列に `}` を大量に並べる。入力は `"{ function { :; } x(a && " + "function { :; } x(" * D + "; }" * M`。TestMalformedAndDeepInput の TIMEOUT 内に答えを返す。素直にさかのぼる実装だと O(D·M) になる。
    - TS26 再帰を使わない（TestNoRecursion）
- [ ] 回帰:
    - TS23 既存の CASES の判定がすべて変わらない（ケース 604 はラベルだけ変わり、判定は silent）
    - TS24 2つのコピーがバイト単位で同一（TestCopies）
    - TS25 目印の文が両方のコピーのモジュール docstring と `_Parser` の docstring にある（TestGuardDocumentation）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 仮の群 | 匿名関数の引数から仮に開いた `(` の群（`_Group.provisional`） |
| 救済 | 仮の群を外し、その `(` を引数語の文字として読むこと（`_rescue_argument_groups`） |
| 直接の区切り | 本体の読み手が実際に読んだ区切り（`_Group.first_sep`） |
| in_anon | 閉じる `{` 群が匿名関数の本体の中にあること |
| skipped | 関数定義の本体の中のコマンドを判定しない規則 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 末尾に余分な `)` がある形（`{ function { :; } foo(a; python3 -i; } )`）: zsh では構文エラーで実行されない。それでも deny になりうる誤拒否を許容する。
- [x] 匿名関数の外の通常の `{` 群で語が残っている `}`（例: `{ function { :; } foo(a; printf REACHED }`）: 既存の規則どおり普通の語のままとする。この見逃しは残す。
- [x] サブシェル版 `( function { :; } foo(a; python3 -i; )`: 見逃しは残し、別の課題とする。
- [x] 既存の CASES: 判定は変えない。変わるのはケース 604 のラベルだけ。
- [x] plugin の version: Actions が上げるため、実装では変更しない。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `feature-docs/codex-guard-anon-arg-paren-comment/reviews/round1.yaml`: 残件の記録（stable_id `db007e0ea42e58d2`）
- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

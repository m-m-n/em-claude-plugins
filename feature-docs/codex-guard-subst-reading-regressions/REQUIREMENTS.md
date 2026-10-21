---
title: "codex-guard-subst-reading-regressions"
created_date: 2026-10-21
status: draft
---

# codex-guard-subst-reading-regressions - 要件定義書

## 1. 概要

### 1.1 背景

codex-guard-case-reading-fixes で、codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` に 3 種類の後退（拒否漏れ）が生じた。3 種類とも、基準コミットでは deny だった入力が、置換の読み違いで `_Undecidable` になる。

### 1.2 目的

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` から、codex-guard-case-reading-fixes で生じた 3 種類の後退（拒否漏れ）をなくす。
- 3 種類とも、基準コミットでは deny だった入力が、置換の読み違いで `_Undecidable` になる。これらの入力で、後ろの `python3 -i` を再び deny にする。
- 直した後の読み方で、新たな誤拒否を生まない。

### 1.3 スコープ

対象:
- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

対象外:
- zsh の `for name (words)` の読み方、select、function、算術の for のシェルごとの読み分け（A2）
- 前のフィーチャー（codex-guard-case-reading-fixes）の SPEC の編集（A5）
- プラグインの version（A6）

## 2. ビジネス要件

### 2.1 ビジネス目標

1.2 目的のとおり。

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

- 1.2 目的のとおり。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | for の語一覧は専用の文脈で読む | confirmed |
| FR2 | 空の () の判定で行継続の対を読み飛ばす | confirmed |
| FR3 | シェルの種類を読み取りに渡す | confirmed |
| FR4 | coproc をシェルごとに読む | confirmed |
| FR5 | repeat をシェルごとに読む | confirmed |
| FR6 | シェルが分からない文字列は、読めなければ 1 回だけ読み直す | confirmed |
| FR7 | 両コピーを同時に直す | confirmed |
| FR8 | docstring を更新する | confirmed |
| FR9 | CASES に再現と派生の行を足す | confirmed |

### 4.2 機能詳細

#### FR1: for の語一覧は専用の文脈で読む

zsh の `for name (words)` の語一覧は、算術展開の文脈 `a` を流用せず、語一覧用の文脈として積む。語一覧の中の語は、今と同じくコマンドの位置で読まない。`#` のコメントは `p` と同じ条件で始まる（直前の文字が空白・タブ・改行・`;` `&` `|` `(` のいずれか）。始まったコメントは改行まで読み飛ばす。コメントの中の引用符・`)`・置換は、何も開かず何も閉じない。改行は語を区切るが、次の語をコマンドの位置にはしない。語一覧の中でさらに開く `(`（`*(N)` のような glob 修飾子）も、中の語をコマンドの位置で読まない。その `)` の後は語の続きとして読む。語一覧を閉じる `)` の後は、今と同じくコマンドの位置にする。`$((` の算術展開の読み方は変えない。

#### FR2: 空の () の判定で行継続の対を読み飛ばす

`_empty_parens_end` は、括弧の間にある空白とタブに加えて、バックスラッシュと改行の対も読み飛ばす。中がそれらだけのときに空の `()` とする。対象は `name()`、`function name()`、`function ()` のすべて（例: `f(\<NL>)`、`f (\<NL>)`、`f( \<NL>\<NL> )`）。入力が対のバックスラッシュで終わり、`)` が来ないものは空の `()` ではない。

#### FR3: シェルの種類を読み取りに渡す

シェルの `-c` 文字列は、それを直接保持するシェルコマンドのベース名から決めたシェルの種類で読む。種類は bash / zsh / 不明 の 3 つ。照合は `_family_of` と同じで、名前そのものか、名前の後ろに数字と `.` が続くものを一致とみなす。`env` などのラッパーやパス（`/usr/bin/zsh`）を経由しても、照合はベース名で行う。sh / dash / ksh の `-c` 文字列と、フックが受け取ったコマンドそのものは、種類を『不明』とする。文字列の中の `$( )` も、その文字列と同じ種類で読む。より深い段の文字列は、自分を直接保持するシェルで決める。

#### FR4: coproc をシェルごとに読む

bash では今の読み方（前のフィーチャー codex-guard-case-reading-fixes の SPEC の要件 11）のとおりに読む。coproc の直後の語をコマンドの位置にし、それが普通の語（NAME）なら、その次の語もコマンドの位置にする（`coproc c {`）。zsh の coproc は NAME を取らない。直後の語はコマンドの位置にする（`coproc {`、`coproc while`）。それが普通の語なら、その語は単純コマンドの最初の語として読み、後ろの語は引数とする（`coproc echo case x in x` の case は文を開かない）。

#### FR5: repeat をシェルごとに読む

zsh では今の読み方（前のフィーチャー codex-guard-case-reading-fixes の SPEC の要件 11）のとおりに読む。repeat の直後の 1 語（回数）は普通の語で、その次の語をコマンドの位置にする（`repeat 1 {`）。bash では repeat は予約語ではなく、普通のコマンド名として読む。後ろの語は引数とする（`repeat x case y in y` の case は文を開かない）。

#### FR6: シェルが分からない文字列は、読めなければ 1 回だけ読み直す

種類が『不明』の文字列は、まず今の読み方で読む。今の読み方とは、bash の coproc NAME の規則と zsh の repeat の規則の両方を使う読み方。それで最後まで読めたら、その結果を使う（codex-guard-case-reading-fixes の TS47 / TS50 は今のまま deny）。判定不能（`_Undecidable`）になったときだけ、どちらの規則も使わない読み方で 1 回だけ読み直す。どちらの規則も使わない読み方では、coproc の直後の語をコマンドの位置にし、それが普通の語なら後ろの語を引数とする（FR4 の zsh の読み方と同じ）。repeat は普通のコマンド名として読む（FR5 の bash の読み方と同じ）。読み直しで最後まで読めたときだけ、その結果を採用する。読み直しも失敗したら、例外の種類にかかわらず、初回の `_Undecidable` とそれが持つ確定済みのコマンド（最後のチェックポイントまで）を使う。bash / zsh と分かっている文字列は読み直さない。読み直しは `parse` の中で扱う。`find_deny(command)` の引数と、`_scan` の中で `parse` を囲む 1 つの try は保つ。

#### FR7: 両コピーを同時に直す

`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR8: docstring を更新する

次の docstring とコメントを、FR1〜FR6 に合わせて書き直す。

- `_skip_substitution` の docstring（rule 6 の、空の `()` の判定・coproc・repeat の文と、Contexts on the stack の `a` の説明）
- `_empty_parens_end` の docstring
- `HEAD_*` と `HEAD_AFTER_WORD` のコメント
- シェルの種類と読み直しにかかわる関数（`parse` / `_Parser` / `_judge` / `_scan`）の docstring
- モジュールの docstring の手順 7 と手順 9

`TestSubstitutionSkipDocumentation` と `TestGuardDocumentation` が固定している文言のうち、本フィーチャーで意味が変わるもの（`RULE_MARKERS` の `loop and coproc head rule` など）は、docstring と同じ変更の中で書き換えてよい。それ以外の固定された文言は残す。

#### FR9: CASES に再現と派生の行を足す

`tests/test_codex_hook_interactive_guard.py` の `CASES` に、TS1〜TS24 を `(期待する判定, ラベル, コマンド)` の形で足し、両コピーに流す。線形時間のシナリオ（TS25〜TS27）は `TestCaseStatementsInASubstitution` に置く。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1 線形時間: 読み取りは、入力の長さに対して線形の時間で終わる。1 つの文字列を読む回数は最大 2 回。空の `()` の判定で、行継続の対を含めて読み直す回数は定数に収める。語一覧の文脈とシェルの種類は、定数サイズの状態として持つ。

### 5.2 セキュリティ要件

該当なし

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR2 再帰を使わない: `TestNoRecursion` と `TestSubstitutionSkipCallStructure` を通す。`_skip_substitution` から到達できるメソッドに、`_skip_substitution` / `_read_quoted_unit` / `parse` / `_remove_range_quotes` を含めない。
- NFR3 標準ライブラリだけを使う: `TestStaticConstraints` を通す。
- NFR5 構造の制約を保つ: `find_deny(command)` の引数を変えない。`_scan` は `_judge` と `parse` を呼ぶ。`_scan` の中で `parse` の呼び出しを囲む try はちょうど 1 つで、`_Undecidable` と `Exception` を捕まえる。`Exception` の節では return も raise もしない。

### 5.5 互換性要件

- NFR4 version を変えない: プラグインの version は変えない。

## 6. UI/UX要件

該当なし（デザインステップは省略。UI が無い）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 5.4 保守性要件の NFR2・NFR3・NFR5 のとおり。

### 9.2 ビジネス上の制約

- NFR4 のとおり。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-subst-reading-regressions/**`
- `test-docs/codex-guard-subst-reading-regressions/**`

`feature-docs/codex-guard-subst-reading-regressions/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-subst-reading-regressions/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-subst-reading-regressions/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: 再現手順の 3 入力（TS1〜TS3）と、bash の repeat の形（TS4）が、両コピーで deny になる。
- [ ] AC2: 最上位（シェルが分からない場合）の欠陥 3 の 2 つの形（TS19 / TS20）と、sh -c の形（TS21）が、両コピーで deny になる。
- [ ] AC3: 派生の行（TS5〜TS18、TS22〜TS24）が CASES に入り、両コピーで期待どおりの判定になる。
- [ ] AC4: 既存の CASES の行が、すべて元の判定のまま通る。codex-guard-case-reading-fixes の TS44〜TS59 のうち TS47 / TS50 も含む。
- [ ] AC5: `TestCopies` により、両コピーがバイト単位で同一であることが確かめられる。
- [ ] AC6: TS25〜TS27 が、`TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` の中で答えを返し、deny になる（NFR1）。
- [ ] AC7: `TestNoRecursion`・`TestSubstitutionSkipCallStructure`・`TestNestedParseErrorContainment`・`TestStaticConstraints`・`TestSubstitutionSkipDocumentation` が通る。
- [ ] AC8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。

### 11.2 KPI

該当なし

## 12. テストシナリオ

表記は 13. 用語定義のとおり。

### 12.1 単体（CASES の行）

| ID | 期待 | 内容 | 要件 |
|----|------|------|------|
| TS1 | deny | 欠陥 1 の再現 | FR1, FR9 |
| TS2 | deny | 欠陥 2 の再現（内側の文字列はタスクの再現手順 3 のとおり） | FR2, FR9 |
| TS3 | deny | 欠陥 3 の再現（zsh の coproc） | FR3, FR4, FR9 |
| TS4 | deny | 欠陥 3（bash の repeat） | FR3, FR5, FR9 |
| TS5 | deny | 語一覧のコメントの中の `)` は語一覧を閉じない | FR1, FR9 |
| TS6 | silent | コメントを含む語一覧の後の case 文の本体の、引用符の中の `python3 -i` を拒否しない | FR1, FR9 |
| TS7 | deny | 語一覧の改行の後の case は文を開かない | FR1, FR9 |
| TS8 | deny | 語一覧の `(` の直後のコメント | FR1, FR9 |
| TS9 | deny | 空白を挟んだ `(` の後の対 | FR2, FR9 |
| TS10 | deny | `function name(` の後の対 | FR2, FR9 |
| TS11 | deny | 空白と複数の対が混ざった空の `()` | FR2, FR9 |
| TS12 | silent | 対を挟んだ関数の本体の、引用符の中の `python3 -i` を拒否しない | FR2, FR9 |
| TS13 | deny | bash の coproc NAME の後の `{` | FR3, FR4, FR9 |
| TS14 | deny | bash では coproc WORD の後の case が文を開く | FR3, FR4, FR9 |
| TS15 | deny | zsh の repeat word の後の `{` | FR3, FR5, FR9 |
| TS16 | deny | zsh の coproc の後の `{` | FR3, FR4, FR9 |
| TS17 | silent | zsh の `coproc {` の case 文の本体の、引用符の中の `python3 -i` を拒否しない | FR3, FR4, FR9 |
| TS18 | deny | bash の repeat は普通のコマンドで、`{` と case は引数 | FR3, FR5, FR9 |
| TS19 | deny | 最上位（シェルが分からない場合）の coproc の形。初回は判定不能で、読み直しで deny になる | FR6, FR9 |
| TS20 | deny | 最上位（シェルが分からない場合）の repeat の形。初回は判定不能で、読み直しで deny になる | FR6, FR9 |
| TS21 | deny | sh の `-c` 文字列はシェルが分からない場合として読み直す | FR3, FR6, FR9 |
| TS22 | deny | 読み直しも失敗したら、初回の確定済みのコマンド（チェックポイントまで）を判定する | FR6, FR9 |
| TS23 | silent | bash と分かっている文字列は読み直さない（bash では case が文を開き、閉じない） | FR3, FR4, FR6, FR9 |
| TS24 | deny | 外側が bash でも、内側の zsh -c の文字列は zsh として読む（直接保持するシェルで決める） | FR3, FR9 |

各シナリオのコマンド:

- TS1: `echo "$(for x (a # "<NL>) { :; })"; python3 -i`
- TS2: `wrap_bash('echo "$(f(\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')`
- TS3: `zsh -c 'echo "$(coproc echo case x in x)"; python3 -i'`
- TS4: `bash -c 'echo "$(repeat x case y in y)"; python3 -i'`
- TS5: `echo "$(for x (a # )<NL>) { case x in x) printf '%s' '"';; esac; })"; python3 -i`
- TS6: `echo "$(for x (a # '<NL>) { case x in x) echo "; python3 -i;";; esac; })"`
- TS7: `echo "$(for x (a<NL>case) { :; }; echo case x in x)"; python3 -i`
- TS8: `echo "$(for x (# c<NL>a) { case x in x) printf '%s' '"';; esac; })"; python3 -i`
- TS9: `wrap_bash('echo "$(f (\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')`
- TS10: `wrap_bash('echo "$(function f(\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')`
- TS11: `wrap_bash('echo "$(f( \\<NL>\\<NL> ) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')`
- TS12: `wrap_bash('echo "$(f(\\<NL>) { case x in x) echo "; python3 -i;";; esac; }; f)"')`
- TS13: `wrap_bash(TS47 のコマンド)`（codex-guard-case-reading-fixes の TS47）
- TS14: `wrap_bash('echo "$(coproc echo case x in x) printf \'%s\' \'"\';; esac)"; python3 -i')`
- TS15: `wrap_zsh(TS50 のコマンド)`（codex-guard-case-reading-fixes の TS50）
- TS16: `wrap_zsh(TS46 のコマンド)`（codex-guard-case-reading-fixes の TS46）
- TS17: `wrap_zsh(TS53 のコマンド)`（codex-guard-case-reading-fixes の TS53）
- TS18: `bash -c 'echo "$(repeat 1 { case x in x)"; python3 -i'`
- TS19: `echo "$(coproc echo case x in x)"; python3 -i`
- TS20: `echo "$(repeat x case y in y)"; python3 -i`
- TS21: `sh -c 'echo "$(coproc echo case x in x)"; python3 -i'`
- TS22: `python3 -i<NL>echo "$(repeat x case y in y`
- TS23: `bash -c 'echo "$(coproc echo case x in x)"; python3 -i'`
- TS24: `wrap_bash(TS3 のコマンド)`（本フィーチャーの TS3）

### 12.2 線形時間（TestCaseStatementsInASubstitution）

| ID | 期待 | 要件 |
|----|------|------|
| TS25 | deny | NFR1, FR2 |
| TS26 | deny | NFR1, FR1 |
| TS27 | deny | NFR1, FR6 |

- TS25: `wrap_bash('echo "$(f(' + '\\<NL>' * DEPTH + ') { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')`
- TS26: `'echo "$(for x (a' + ' # "<NL>' * DEPTH + ') { :; })"; python3 -i'`
- TS27: `'echo "$(coproc echo case x in x)' + ' :' * DEPTH + '"; python3 -i'`（最上位。初回は長い本体を読み切ってから判定不能になり、読み直しで deny になる）

### 12.3 結合

- [ ] 既存の CASES の行が、すべて元の判定のまま通る（AC4）。
- [ ] `TestCopies`・`TestNoRecursion`・`TestSubstitutionSkipCallStructure`・`TestNestedParseErrorContainment`・`TestStaticConstraints`・`TestSubstitutionSkipDocumentation` が通る（AC5、AC7）。
- [ ] `python3 -m unittest discover -s tests` が通る（AC8）。

### 12.4 E2E

- 既存の E2E テスト: なし
- 実行コマンド: 検出なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `<NL>` | 改行 |
| `\<NL>` | バックスラッシュの直後に改行が続く対 |
| `wrap_bash(s)` | `'bash -c ' + shlex.quote(s)` |
| `wrap_zsh(s)` | `'zsh -c ' + shlex.quote(s)` |
| TS44〜TS59（TS46 / TS47 / TS50 / TS53 を含む） | 前のフィーチャー（codex-guard-case-reading-fixes）の CASES の行のコマンド |

## 14. 確認事項

### 14.1 確認済み事項

- [x] デザインステップ: 省略（UI が無い。変更はフックの解析処理とテストだけで、デザインシステムの候補も無い）

### 14.2 前提として置いた事項

- [ ] A1: sh / dash / ksh の `-c` 文字列は、フックのコマンドそのものと同じく、種類を『不明』として扱う（FR6 の読み直しの対象になる）。
- [ ] A2: zsh の `for name (words)` の読み方、select、function、算術の for は、シェルの種類で変えない。シェルによって読み分けるのは、coproc の NAME と repeat だけ。
- [ ] A3: `NESTED_READ_LIMIT` は、読み直しがあっても 1 つの文字列をその長さで 1 回だけ数える。
- [ ] A4: 既存の CASES の行は、削除も判定の変更もしない（codex-guard-case-reading-fixes の TS44〜TS59 を含む）。
- [ ] A5: 前のフィーチャーの SPEC（要件 10 の『中は空白だけ』と、要件 11 の coproc / repeat の文）は履歴として残し、編集しない。本フィーチャーの SPEC で置き換える。
- [ ] A6: プラグインの version は変えない。

## 15. 参考資料

- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`

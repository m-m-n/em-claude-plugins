# Feature: codex-guard-procsub-in-wordlist

## Overview

codex-hook-interactive-guard の `_skip_substitution` で、zsh の `for name (words)` の語一覧（文脈 w）の最も外側の項目の語の先頭にあるプロセス置換 `<(`・`>(`・`=(` を、入れ子の w ではなくコマンド列 p として読む。それ以外の `(` は今の読みを保つ。要件は `feature-docs/codex-guard-procsub-in-wordlist/REQUIREMENTS.md` を参照する。

## Objectives

- codex-hook-interactive-guard の両コピーで、zsh の `for name (words)` の語一覧の中にあるプロセス置換 `<(`・`>(`・`=(` の中身を、zsh と同じくコマンド列として読む
- プロセス置換の中のコメントが原因の拒否漏れ（fail-open）と誤拒否をなくす

## Technical Requirements

### Functional Requirements

- **FR1:** 語一覧の最も外側の項目で、語の先頭にあるプロセス置換はコマンド列 p として積む
    - `_skip_substitution` で、文脈 w の最も外側の項目（`stack[-2] != "w"`）の語の先頭に、引用・エスケープの無い `<(`・`>(`・`=(` があるときだけ、入れ子の w ではなくコマンド列 p として積む。
    - 語の先頭は字句状態で判定する。最も外側の項目を開いた `(` の直後、または引用・エスケープされていない区切り（空白、タブ、改行、`;`、`&`、`|`）の後で、その語の文字・引用・置換をまだ読んでいない位置を語の先頭とする。
    - エスケープした文字（`a\ =(` のエスケープした空白を含む）、引用（`'...'`、`$'...'`、`"..."`）、置換（`$(`、`$((`、`${`、バッククォート）、入れ子の項目、その他の語の文字は語を始める。
    - 継続行（バックスラッシュ + 改行）は語を始めも区切りもせず、直前の状態を保つ（`a\<改行>=(` は語の途中、`a \<改行><(` は語の先頭）。
    - 積んだ p はコマンドの位置で始まり、コメント・引用符・置換・case 文などをコマンド列として読む。
    - p の `)` は語の中の閉じ（close_command False）として扱う。読みは w に戻り、その後の文字は同じ語の続きになる。
    - 判定は後ろの文字を見返さず、読みながら持つ状態で行う。
- **FR2:** それ以外の ( は今の読みを保つ
    - 文脈 w の中のその他の `(` は今のまま入れ子の w を開く。
    - 対象は、入れ子の項目（glob 修飾子 `*(#qN)` やグループ）の中の `(`・`<(`・`>(`・`=(`（例: `a(=(: #c))`、`a(<(b #c))`）、語の途中の `<(`・`>(`・`=(`（例: `a=(`、`a<(x)`、`<(a)<(b)` の 2 つ目、`<->(`、`a\ =(`、`a\<改行>=(`）、エスケープや引用符で囲まれた `<`・`>`・`=` の後の `(`（例: `\<(`、`"<"(`）。
    - 入れ子の w では今のまま、すべての `#` を語の文字として読む。
    - 既知の制限を Known Limitations に記録する。
- **FR3:** 2 つのコピーをバイト単位で同一に保つ
    - `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で一緒に直し、バイト単位で同一に保つ。
- **FR4:** docstring とコメントを新しい読みに合わせる
    - `_skip_substitution` の docstring の語一覧 w の段落（「A `(` read in w opens a nested entry of w (a glob qualifier as in `*(N)`) ...」の文）と、`(` 分岐・w 分岐のコメントに、最も外側の項目の語の先頭にある引用・エスケープの無い `<(`・`>(`・`=(` が p を開き、その `)` が語の中の閉じであること、語の先頭の決め方（エスケープした空白は語の文字、継続行は語を区切らない）を書く。
    - 既存のテストが検査している文（`TestSubstitutionSkipDocumentation` の RULE_MARKERS と WORD_LIST_HASH_MARKERS）は残す。
- **FR5:** 再現入力と検証行を CASES に追加する
    - `tests/test_codex_hook_interactive_guard.py` の `CASES` に、Test Scenarios の TS-1〜TS-14 を `(期待する判定, ラベル, コマンド)` の行として追加する。
    - 拒否漏れの入力 `zsh -c 'echo "$(for x (<(: # "<改行>)) { :; })"; python3 -i'` は deny、誤拒否の入力 `zsh -c 'echo "$(for x (<(printf x # )))"; python3 -i; echo "<改行>)) { :; })"'` は silent。
    - 表は両コピーに流す。

### Non-Functional Requirements

- **NFR1:** 読みは線形のまま、再帰を使わない（`TestNoRecursion` と `TestSubstitutionSkipCallStructure` を壊さない）。語の先頭の判定は読みながら持つ定数サイズの状態で行い、後ろの文字を見返さない
- **NFR2:** テストは Python 標準ライブラリの `unittest` だけを使う
- **NFR3:** プラグインの version は変えない（Actions が patch を上げる）
- **NFR4:** 既存の CASES の deny / silent 行と、その他の既存テストをすべて通す

## Implementation Approach

### 読みの規則

| 位置 | `(` の前 | 積む文脈 | `#` の読み |
|------|----------|----------|------------|
| 最も外側の項目（`stack[-2] != "w"`）の語の先頭 | 引用・エスケープの無い `<`・`>`・`=` | コマンド列 p（`)` は語の中の閉じ、close_command False） | p の規則でコメントを始める |
| 最も外側の項目の語の途中 | 任意 | 入れ子の w | 語の文字 |
| 入れ子の項目の中 | 任意 | 入れ子の w | 語の文字 |
| 任意 | エスケープ・引用符で囲まれた `<`・`>`・`=` | 入れ子の w | 語の文字 |

### 保つ既存の読み

- `codex-guard-for-wordlist-glob-qualifier` で入れた条件 `stack[-2] != "w"` と、入れ子の w の中の `#` を語の文字とする読みは保つ。
- 最も外側の項目で `#` がコメントを始める条件（直前 1 文字が空白、タブ、改行、`;`、`&`、`|`、`(`）は変えない。

### Known Limitations

- zsh は語の途中や入れ子の中の `<(`・`>(` もプロセス置換として読む。この機能ではそれらを入れ子の w のまま読むので、そこに空白の後の `#` コメントがあると読みのずれが残る。

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # _skip_substitution とその docstring・コメント
em-review/scripts/codex-hook-interactive-guard.py     # 上とバイト単位で同一
tests/test_codex_hook_interactive_guard.py            # CASES に TS-1〜TS-14 を追加
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/codex-guard-procsub-in-wordlist/**`
- `test-docs/codex-guard-procsub-in-wordlist/**`

`feature-docs/codex-guard-procsub-in-wordlist/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-procsub-in-wordlist/**` に含まれるもの: `test-docs/codex-guard-procsub-in-wordlist/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-procsub-in-wordlist/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-procsub-in-wordlist/**` は依然として正しい。

## Test Scenarios

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の `CASES` に追加し、両コピーに流す。コマンドは Python 文字列リテラル表記（`\n` は改行、`\\` は 1 つのバックスラッシュ）。

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS-1 | deny | `zsh -c 'echo "$(for x (<(: # "\n)) { :; })"; python3 -i'` | 再現手順 2（拒否漏れ） | FR1, FR5 |
| TS-2 | silent | `zsh -c 'echo "$(for x (<(printf x # )))"; python3 -i; echo "\n)) { :; })"'` | 再現手順 3（誤拒否） | FR1, FR5 |
| TS-3 | deny | `echo "$(for x (>(: # "\n)) { :; })"; python3 -i` | `>(` の同型 | FR1, FR5 |
| TS-4 | deny | `echo "$(for x (=(: # "\n)) { :; })"; python3 -i` | `=(` の同型 | FR1, FR5 |
| TS-5 | deny | `echo "$(for x (a <(: # "\n)) { :; })"; python3 -i` | 空白の後の語の先頭 | FR1, FR5 |
| TS-6 | deny | `echo "$(for x (\\<(b #c)) { :; })"; python3 -i` | エスケープした `<` の後の `(` は入れ子の w。p と誤読すると末尾まで改行の無いコメントになり判定不能で silent になる | FR2, FR5 |
| TS-7 | deny | `echo "$(for x (a=(b #c)) { :; })"; python3 -i` | 語の途中の `=(` は入れ子の w | FR2, FR5 |
| TS-8 | deny | `echo "$(for x (<->(#qN)) { :; })"; python3 -i` | 数値範囲 glob `<->` の後の `(` は glob 修飾子で、`>(` は語の途中 | FR2, FR5 |
| TS-9 | deny | `echo "$(for x (a(<(b #c))) { :; })"; python3 -i` | 入れ子の項目の中の `<(` は入れ子の w のまま | FR2, FR5 |
| TS-10 | deny | `echo "$(for x ("<"(b #c)) { :; })"; python3 -i` | 引用符で囲んだ `<` の後の `(` は入れ子の w | FR2, FR5 |
| TS-11 | deny | `echo "$(for x (a(=(: #c))) { :; })"; python3 -i` | 入れ子の項目の中の `=(` は入れ子の w のままで、`#` は語の文字。p と誤読すると `#c` から末尾まで改行の無いコメントになり判定不能で silent になる | FR2, FR5 |
| TS-12 | deny | `echo "$(for x (a\\ =(b #c)) { :; })"; python3 -i` | エスケープした空白は語の文字なので `=(` は語の途中で入れ子の w。直前 1 文字（空白）で判定すると p と誤読し、判定不能で silent になる | FR1, FR2, FR5 |
| TS-13 | deny | `echo "$(for x (a\\\n=(b #c)) { :; })"; python3 -i` | 語の途中の継続行（バックスラッシュ + 改行）は語を区切らないので `=(` は語の途中で入れ子の w。直前 1 文字（改行）で判定すると p と誤読し、判定不能で silent になる | FR1, FR2, FR5 |
| TS-14 | deny | `echo "$(for x (a \\\n<(: # "\n)) { :; })"; python3 -i` | 空白の後の継続行は語の先頭の状態を保つので `<(` は p。今の読み（入れ子の w）では `"` が引用を開いて判定不能になり silent になる | FR1, FR5 |

### Regression Tests

- [ ] 既存の `CASES` の deny / silent 行がすべて通る（既存の「置換読み TS-1」「TS-2」「TS-7」を含む）
- [ ] `TestNoRecursion` と `TestSubstitutionSkipCallStructure` が通る
- [ ] `TestSubstitutionSkipDocumentation` の RULE_MARKERS と WORD_LIST_HASH_MARKERS が通る
- [ ] `TestCopies.test_the_two_copies_are_byte_identical` が通る

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### 実行コマンド

```
python3 -m unittest tests.test_codex_hook_interactive_guard
python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests
```

## Success Criteria

- [ ] AC1: 拒否漏れの再現入力が両コピーで deny になる（FR1, FR5）
- [ ] AC2: 誤拒否の再現入力が両コピーで silent になる（FR1, FR5）
- [ ] AC3: 語一覧の最も外側の項目で、項目を開く `(` の直後、空白の後、空白と継続行の後にある `<(`・`>(`・`=(` が p として読まれ、その中の空白の後の `#` がコメントを始める（FR1）
- [ ] AC4: 入れ子の項目（`a(=(: #c))`、`a(<(b #c))`）、語の途中（`a=(`、`<->(`）、エスケープ・引用符の後（`\<(`、`"<"(`）の `<(`・`>(`・`=(` は入れ子の w のままで、その中の `#` は語の文字として読まれる（既存 CASES の「置換読み TS-1」「TS-2」「TS-7」を含む）（FR2）
- [ ] AC5: 2 つのコピーがバイト単位で同一（`TestCopies.test_the_two_copies_are_byte_identical`）（FR3）
- [ ] AC6: docstring に新しい読みが書かれ、既存の検査対象の文が残っている（FR4）
- [ ] AC7: `python3 -m unittest tests.test_codex_hook_interactive_guard` と、`python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る（FR3, FR5, NFR4）
- [ ] AC8: エスケープした空白の後（`a\ =(`）と、語の途中の継続行の後（`a\<改行>=(`）の `=(` は語の先頭として読まれず、入れ子の w のままになる（FR1, FR2）

## Open Questions

なし。

## References

- 要件定義書: `feature-docs/codex-guard-procsub-in-wordlist/REQUIREMENTS.md`

# Feature: codex-guard-backquote-comment-undecidable

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）で、文字列の解析が `_Undecidable` で止まったとき、最後のチェックポイントまでに確定したコマンドだけを判定する。判定不能になった箇所より前に読み終えた行の起動が deny になる。要件は [REQUIREMENTS.md](REQUIREMENTS.md) にある。

再現手順（Python の式。値を `tool_input.command` に渡す）:

```python
"bash -c " + shlex.quote("python3 -B -S -i\nfunction { :; } foo(`case x in x) echo x;; esac` # '\n)")
```

行番号は `tests/test_codex_hook_interactive_guard.py` のもの。

## Objectives

- 両コピーで、文字列が判定不能になった箇所より前に読み終えた行の起動を deny にする。再現手順の先頭の `python3 -i` も含む。
- 再発を CASES で検出できるようにする。

## User Stories

### US1: 判定不能になる前に読み終えた行の起動を deny にする
em-workflow / em-review の利用者として、文字列が判定不能になった箇所より前に読み終えた行の起動を deny にしてほしい。

**Acceptance Criteria:**
- [ ] AC1: 再現手順の JSON で、両コピーとも deny を出力する。
- [ ] AC2: FR4 で足す行が、両コピーですべて期待どおりの値になる。

### US2: 既存の読みと結果を変えない
em-workflow / em-review の利用者として、既存の行の結果とコピーの同一性は変わらないでほしい。

**Acceptance Criteria:**
- [ ] AC3: 既存の CASES の行と TestNestedReadLimit がそのまま通る。test_a_string_that_proves_undecidable_still_counts も含む。
- [ ] AC4: TestCopies.test_the_two_copies_are_byte_identical が通る。
- [ ] AC5: 足した文言を含め、docstring テストが通る。

### US3: 性能と制約を保つ
em-workflow / em-review の利用者として、解析の性能と既存の制約が保たれてほしい。

**Acceptance Criteria:**
- [ ] AC6: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。

## Technical Requirements

### Functional Requirements
- **FR1:** 再現手順を deny — 上の再現手順の値を `tool_input.command` に渡すと、両コピーとも permissionDecision が deny になる。
- **FR2:** 判定不能のときは最後のチェックポイントまでを判定する — 文字列の解析が `_Undecidable` で止まったら、最後のチェックポイントまでに確定したコマンドだけを判定する。
    - チェックポイントは、reader 自身が最上位で読む改行のうち、次がすべて成り立つもの: 開いている群が無い、待っているパイプ（`|` / `|&`）が無い、末尾の `&&` / `||` でリストが続いていない、その行の heredoc の本文を読み終えている。
    - `|`・`|&`・`&&`・`||` の後の空行、コメントだけの行、heredoc の本文は、次のコマンドが確定するまでチェックポイントを作らない。
    - チェックポイントより前のコマンドは、接続と skip（関数定義の本体）を、チェックポイントより前に開いた群から取る。文字列全体を読んだときと同じ取り方にする。
    - フックのコマンドそのものと、入れ子のリテラルなシェルの `-c` 文字列のすべてに当てはめる。
    - こうして判定するコマンドは通常の順序でたどる。その中の `-c` 文字列と NESTED_READ_LIMIT も含む。判定不能と分かった文字列も、NESTED_READ_LIMIT には全長で数える。
- **FR3:** 変えないもの — 文字列の解析中に `_Undecidable` 以外の例外が起きた場合は従来どおりで、入れ子ならその文字列を飛ばし、最上位ならフックは何も出力せずに終わる。コメントの例外の範囲、`_scan_parens`、`_read_argument_parens`、救済の規則、区切り・群・heredoc の読みは変えない。判定不能な箇所より前にチェックポイントの無い文字列は、従来どおり何も出力しない。既存の CASES の行はすべてそのまま通り、行を消さず期待値も変えない（例: 行 111-114、576-577、603-631、656-703 は silent のまま）。
- **FR4:** 再発を検出する CASES の行 — `tests/test_codex_hook_interactive_guard.py` の CASES に、Test Scenarios の TS1〜TS4 に挙げる行を足し、表を両コピーに流す。
- **FR5:** 2 つのコピー — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR6:** docstring — モジュール docstring の「判定不能なら出力しない」旨の記述を FR2 に合わせて書き直す。対象は手順 3（閉じない引用符・終わらない heredoc → 出力しない）、手順 4（閉じない群 → 出力しない）、手順 7（reader が読めない文字列は飛ばして通す）、手順 9（判定不能・想定外のものは出力しない）、「Everything the guard cannot positively identify passes」。`_scan` の docstring と `_Parser` の docstring（「Raises _Undecidable ...」）も同じ規則に直す。既存の文言はすべて残し、特に "a string for which an unexpected error occurred while it was being read" と "the `}` is an ordinary word and the string stays undecidable" を残す。STALE_DOCSTRING_SENTENCES と STALE_GROUP_SENTENCES の文は書き戻さない。チェックポイントの規則を確かめる docstring テストの文言を足し、両コピーに流す。

### Non-Functional Requirements
- **NFR1 - 性能:** 解析は文字列の長さに対して線形のまま保つ。チェックポイントの記録は改行ごとに定数時間、チェックポイントより前の群を確定させる処理は群ごとに 1 回たどる。再帰は使わない。再帰と循環の検査、既存の性能テストが両コピーで通る。
- **NFR2 - 安全性:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない。判定はコマンド文字列だけで決まる（TestStaticConstraints）。入れ子の解析の例外処理の検査（nested_parse_handler_findings）が通る。`_Undecidable` と `Exception` の両方を捕まえ、`Exception` の処理は return も raise もしない。既存の deny は silent にならない。
- **NFR3 - 互換性:** plugin.json と marketplace.json の version は変えない。deny の理由の文言は変えない。

## Implementation Approach

### Architecture

対象のコンポーネント:

```
codex-hook-interactive-guard.py（em-workflow / em-review の 2 コピー、バイト単位で同一）
├── モジュール docstring   手順 3・4・7・9 と「Everything the guard ...」を FR2 に合わせる（FR6）
├── _scan                 docstring を FR2 に合わせる（FR6）
└── _Parser               最上位の改行でチェックポイントを記録する。docstring を FR2 に合わせる（FR2・FR6）
```

チェックポイントのコマンドを解析器から渡す形（例外の属性、返す組、ほかの形）は計画で決める。シンボルの削除・改名はしない（A3）。

### Data Flow

1 つの文字列（フックのコマンドそのもの、または入れ子のリテラルなシェルの `-c` 文字列）の判定:

```
文字列を解析する
  → reader 自身が最上位で読む改行がチェックポイントの条件を満たせば記録する（FR2）
  → 最後まで読めた:
       → 従来どおり全体を判定する
  → _Undecidable で止まった:
       → チェックポイントがある:
            → 最後のチェックポイントまでに確定したコマンドだけを判定する
              （接続と skip はチェックポイントより前に開いた群から取る）
            → 通常の順序でたどる。その中の -c 文字列と NESTED_READ_LIMIT も含む
       → チェックポイントが無い:
            → 従来どおり何も出力しない（FR3）
       → どちらでも、NESTED_READ_LIMIT にはその文字列を全長で数える
  → _Undecidable 以外の例外:
       → 従来どおり。入れ子ならその文字列を飛ばし、最上位なら何も出力せずに終わる（FR3）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- コメントの例外の範囲、`_scan_parens`、`_read_argument_parens`、救済の規則、区切り・群・heredoc の読み: 変えずに使う（FR3）。
- NESTED_READ_LIMIT: チェックポイントまでのコマンドの中の `-c` 文字列にも適用し、判定不能と分かった文字列も全長で数える（FR2）。

**External Dependencies:**
- 標準ライブラリだけ（NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py
tests/test_codex_hook_interactive_guard.py
```

## Declared Change Set

このセクションは手で列挙した一覧の代わりに create-plan での導出を述べる。このフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する:

- `feature-docs/codex-guard-backquote-comment-undecidable/**`
- `test-docs/codex-guard-backquote-comment-undecidable/**`

`feature-docs/codex-guard-backquote-comment-undecidable/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-backquote-comment-undecidable/**` に含まれるもの: タスクごとのテスト記録 `test-docs/codex-guard-backquote-comment-undecidable/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

既定の 2 つは、SPEC作成者が明示的に除外しない限り宣言に含まれる。記載が無いことで除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセット（superset）の主張であり、verify 時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-backquote-comment-undecidable/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-backquote-comment-undecidable/**` は依然として正しい。実際には生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で並べ、同じ表を 2 つのコピーの両方に流す。コマンドは Python の文字列リテラル。

### Unit Tests
- [ ] TS1（AC1）: 再現手順の行 - deny（FR1・FR4）
    ```python
    ("deny", "判定不能で止まる前に読み終えた行の起動を拒否する (再現手順)", "bash -c 'python3 -B -S -i\nfunction { :; } foo(`case x in x) echo x;; esac` # '\"'\"'\n)'"),
    ```
- [ ] TS2（AC2）: FR4 の deny の行。最上位の `-i`・プログラムなしの起動、入れ子の `-c`、閉じた群、チェックポイントより前の行の `-c`、読み終えた heredoc の後 - deny（FR2・FR4）
    ```python
    ("deny", "最上位で閉じない引用符より前の行の -i を拒否する", "python3 -i\necho '"),
    ("deny", "最上位で閉じない引用符より前の行のプログラムなしの起動を拒否する", "python3\necho '"),
    ("deny", "入れ子の -c 文字列で閉じない引用符より前の行の -i を拒否する", "bash -c 'python3 -i\necho '\"'\"''"),
    ("deny", "チェックポイントより前の閉じた群の中の起動を拒否する", "( python3 -i )\necho '"),
    ("deny", "チェックポイントより前の行の -c 文字列も判定する", "bash -c 'python3 -i'\necho '"),
    ("deny", "読み終えた heredoc の後の行の起動を拒否する", "python3 - <<EOF\nprint(1)\nEOF\npython3 -i\necho '"),
    ```
- [ ] TS3（AC2）: FR4 の既知の誤拒否の行（後ろに構文エラーのある zsh -c、if の中の行）- deny。ラベルに既知の誤拒否と書く（FR2・FR4・A2）
    ```python
    ("deny", "既知の誤拒否: zsh は後ろの構文エラーで何も実行しない", "zsh -c 'python3 -i\nfunction { :; } foo(`case x in x) echo x;; esac` # '\"'\"'\n)'"),
    ("deny", "既知の誤拒否: 改行がシェルの実行単位の境界でない if の中の行", "if false; then\npython3 -i\necho '"),
    ```
- [ ] TS4（AC2）: FR4 の silent の行（同じ行、`|`・`|&`・`&&`・`||` の継続、`&&` の後の空行、開いた群、終わらない heredoc、接続された群、関数定義の本体、パイプの右側）- silent（FR2・FR4）
    ```python
    ("silent", "同じ行の判定不能な箇所より前の起動は判定しない", "python3 -i; echo '"),
    ("silent", "| で続く行はチェックポイントにならない", "python3 -i |\necho '"),
    ("silent", "|& で続く行はチェックポイントにならない", "python3 -i |&\necho '"),
    ("silent", "&& で続く行はチェックポイントにならない", "python3 -i &&\necho '"),
    ("silent", "|| で続く行はチェックポイントにならない", "python3 -i ||\necho '"),
    ("silent", "&& の後の空行を越えても継続のまま", "python3 -i &&\n\necho '"),
    ("silent", "開いた群の中の行はチェックポイントにならない", "{ python3 -i\necho '"),
    ("silent", "heredoc の本文が終わらない行はチェックポイントにならない", "python3 -i <<EOF\nprint(1)"),
    ("silent", "チェックポイントより前の接続された群は接続の読みのまま", "( python3 ) < /dev/null\necho '"),
    ("silent", "チェックポイントより前の関数定義の本体は判定しない", "f() { python3 -i; }\necho '"),
    ("silent", "チェックポイントより前のパイプの右側は接続されている", "echo x | python3\necho '"),
    ```
- [ ] TS5（AC3）: 既存の CASES の行 - 変わらない（FR3）
- [ ] TS6（AC4・AC5）: TestCopies、TestGuardDocumentation（足した文言）、入れ子の解析の例外処理の検査 - 通る（FR5・FR6・NFR2）

### Integration Tests
- [ ] IT1（AC6）: `python3 -m unittest tests.test_codex_hook_interactive_guard && python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` - 通る（NFR1・NFR2・NFR3）

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] 該当なし

### Edge Cases
- [ ] ``function { python3 -i; } foo(`echo )` #)``（バッククォートの中の `)` で走査が早く終わり、本当の `)` は `#` の後にある）: コメントの例外の範囲を変えないので deny のまま。
- [ ] 起動行で終わらない heredoc（`python3 -i <<EOF\nprint(1)`）: チェックポイントが無いので silent。bash は実行するが、FR2 の定義で受け入れる見逃し。
- [ ] 行 113 の `cat <<EOF\npython3 -i`: 本文の行はコマンドにならないので silent のまま。
- [ ] `_Undecidable` 以外の例外: 従来どおりその文字列を飛ばす。

### Performance Tests
- [ ] TS7（NFR1）: 既存の性能テストと再帰の検査が、両コピーで制限内に通る。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 判定はコマンド文字列だけで決まる（NFR2）。既存の deny は silent にならない（NFR2）。
- **Data Protection:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR2）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

- `_Undecidable`: 最後のチェックポイントまでに確定したコマンドを判定する。チェックポイントが無ければ従来どおり何も出力しない（FR2・FR3）。
- `_Undecidable` 以外の例外: 従来どおり。入れ子ならその文字列を飛ばし、最上位ならフックは何も出力せずに終わる（FR3）。
- 入れ子の解析の例外処理は `_Undecidable` と `Exception` の両方を捕まえ、`Exception` の処理は return も raise もしない（NFR2）。

## Performance Optimization

### Performance Goals
- 解析は文字列の長さに対して線形（NFR1）。

### Optimization Strategies
- チェックポイントの記録: 改行ごとに定数時間（NFR1）。
- チェックポイントより前の群を確定させる処理: 群ごとに 1 回たどる（NFR1）。
- 再帰は使わない（NFR1）。

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] 2 つのコピーがバイト単位で同一（FR5）

## Assumptions

- A1: bash -c は後ろの構文エラーを検出する前に 1 行目を実行する。zsh -c は文字列に parse error があると何も実行しない。
- A2: 既知の誤拒否として受け入れるもの: 後ろに構文エラーのある zsh -c 文字列と、改行がシェルの実行単位の境界でない行（ガードが群として追わない `if` / `while` / `for` / `case` の中）。
- A3: チェックポイントのコマンドを解析器から渡す形（例外の属性、返す組、ほかの形）は計画で決める。シンボルの削除・改名はしない。
- A4: plugin.json と marketplace.json の version は変えない。
- A5: LICENSE ファイルが無いので、ライセンスは検出なしとして扱う。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
- 既存のテスト: `tests/test_codex_hook_interactive_guard.py`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`

# Feature: destructive-guard-multi-substitution-reason

## Overview

1 つの再帰削除に、コマンド置換だけでできた削除対象が 2 つ以上あるとき、destructive-guard の理由文で各対象を位置による指定で区別できることを、回帰テストで固定する。
テストが現在のフックで通る場合、`em-workflow/hooks/destructive-guard.py` は変更しない。

## Objectives

- 1 つの再帰削除に、コマンド置換だけでできた削除対象が 2 つ以上あるとき、destructive-guard の理由文を読んだ人間やエージェントが、どの対象が引っかかったのかを判別できる
- この判別できる状態が後の変更で崩れたら、テストで検出できる
- goal の完了の定義どおり、`python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` がどちらも全件通る

## User Stories

### US1: 引っかかった置換対象を理由文で判別する
As a destructive-guard の理由文を読む人間やエージェント, I want to 置換だけでできた削除対象が 2 つ以上あるときに、どの対象が引っかかったのかを理由文で判別したい, so that 引っかかった対象を特定できる.

**Acceptance Criteria:**
- [ ] AC-1: `rm -rf $(cat a) $(cat b)` の判定が ask / rm-unresolvable で、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの2番目の対象[`$(...)`] `` と完全一致し、`cat a` も `cat b` も理由文に含まれないことをテストが確かめ、そのテストが通る。（FR1, FR6）
- [ ] AC-2: `rm -rf $(cat a); rm -rf $(cat b)` の理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 2番目のrmの1番目の対象[`$(...)`] `` と完全一致することをテストが確かめ、そのテストが通る。（FR2）
- [ ] AC-3: CLAUDE_BATCH を立てたとき、AC-1 のコマンドの判定が deny / rm-unresolvable で、理由文の指定の並びが AC-1 と完全一致することをテストが確かめ、そのテストが通る。（FR3）
- [ ] AC-5: `` rm -rf `cat a` `cat b` `` の判定が ask / rm-unresolvable で、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの2番目の対象[`$(...)`] `` と完全一致することをテストが確かめ、そのテストが通る。（FR7, FR6）
- [ ] AC-6: `` rm -rf $(cat a) `cat b` `` の判定が ask / rm-unresolvable で、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの2番目の対象[`$(...)`] `` と完全一致することをテストが確かめ、そのテストが通る。（FR8, FR6）
- [ ] AC-7: `rm -rf <(cat a) <(cat b)` の判定が ask / rm-unresolvable で、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの2番目の対象[`$(...)`] `` と完全一致することをテストが確かめ、そのテストが通る。（FR9, FR6）
- [ ] AC-8: `rm -rf $(cat a) /tmp/scratch $(cat b)` の判定が ask / rm-unresolvable で、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの3番目の対象[`$(...)`] `` と完全一致し、「1番目のrmの2番目の対象」を含まないことをテストが確かめ、そのテストが通る。（FR10, FR6）
- [ ] AC-9: 置換の本文に固有の文字列を入れた 2 対象のコマンドの判定が ask / rm-unresolvable で、どちらの固有文字列も理由文に含まれず、理由文の指定の並びが `` 1番目のrmの1番目の対象[`$(...)`] `` 、 `` 1番目のrmの2番目の対象[`$(...)`] `` と完全一致することをテストが確かめ、そのテストが通る。（FR11, FR6）

### US2: 判別できる状態が崩れたらテストで検出する
As a destructive-guard を変更する人間やエージェント, I want to 理由文で置換対象を判別できる状態が崩れたらテストで検出したい, so that この状態を後の変更で失わない.

**Acceptance Criteria:**
- [ ] AC-4: tests/test_destructive_guard_mixed_rm_precedence.py（FR12 の範囲の変更）を除く既存テストを変更せずに、`python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` が全件通る。（FR4, FR5, FR12）
- [ ] AC-10: `python3 -m unittest tests.test_destructive_guard_mixed_rm_precedence` が failures 0 / errors 0 で通る。そのファイルは自分の feature のケースを `[PRE_EXISTING_CASE_COUNT:]` で取り出さず、ラベルが `destructive-guard-mixed-rm-precedence ` で始まるケース（現在のケース表で 33 件）を取り出し、それらが PRE_EXISTING_CASE_COUNT 番目から連続していることを確かめる。PRE_EXISTING_CASE_COUNT / PRE_EXISTING_CASES_DIGEST の値と各シナリオの期待件数は変わっていない。em-workflow/hooks/tests/destructive-guard-cases.json は変更されていない。（FR12, FR4）

## Technical Requirements

### Functional Requirements
- **FR1:** 1 つの rm に置換だけの対象が 2 つある場合の回帰テスト。`rm -rf $(cat a) $(cat b)` を PreToolUse JSON でフックに渡すテストを追加する。判定は ask、理由 ID は rm-unresolvable、理由文から取り出した対象の指定がこの順で [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] であり、2 つが互いに異なり、それぞれ 1 回だけ出ることを固定する。理由文に置換の本文（`cat a` / `cat b`）が含まれないことも固定する。
- **FR2:** 置換だけの対象が別々の rm 呼び出しにある場合の回帰テスト。`rm -rf $(cat a); rm -rf $(cat b)` について、理由文の対象の指定が [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 2番目のrmの1番目の対象[`$(...)`] ``] で、それぞれ 1 回だけ出ることを固定するテストを追加する。
- **FR3:** 無人実行で降格したときも指定が区別できる。FR1 のコマンドを CLAUDE_BATCH を立てて実行したとき、判定は deny、理由 ID は rm-unresolvable のままで、理由文に FR1 と同じ 2 つの異なる指定がそれぞれ 1 回だけ含まれることを固定するテストを追加する。
- **FR4:** 単一対象の理由文は変えない。置換だけの対象が 1 つのときの理由文（例: `rm -rf $(printf /x)` の全文）は変更しない。既存テストは変更せずに通す。例外は FR12 の tests/test_destructive_guard_mixed_rm_precedence.py の 1 ファイルだけで、FR12 の範囲に限って変更する。
- **FR5:** SUBSTITUTION_STANDIN を変えない。`SUBSTITUTION_STANDIN` の値 `$(...)` と、そのコメントに挙げた不活性条件（先頭が `-` でない、REDIRECT の形に一致しない、安全なルート名と一致しない、制御文字を含まない）は変えない。
- **FR6:** フック本体の変更は、テストが失敗した場合に限る。現在のフックはすでに位置による指定で対象を区別している（Assumptions A1）。FR1〜FR3 と FR7〜FR11 のテストが現在のフックで通るなら、`em-workflow/hooks/destructive-guard.py` は変更しない。通らない場合に限り、FR1〜FR5 と FR7〜FR11 を満たすようにフックを直す。
- **FR7:** バッククォート置換が 2 つの場合の回帰テスト。`` rm -rf `cat a` `cat b` `` について、判定が ask / rm-unresolvable で、理由文の指定がこの順で [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] であり、互いに異なり、それぞれ 1 回だけ出ることを固定するテストを追加する（バッククォートの対象にも固定の標準テキスト `$(...)` が付く）。
- **FR8:** $() とバッククォートが混在する場合の回帰テスト。`` rm -rf $(cat a) `cat b` `` について、判定が ask / rm-unresolvable で、理由文の指定がこの順で [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] であり、互いに異なり、それぞれ 1 回だけ出ることを固定するテストを追加する。
- **FR9:** プロセス置換が 2 つの場合の回帰テスト。`rm -rf <(cat a) <(cat b)` について、判定が ask / rm-unresolvable で、理由文の指定がこの順で [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] であり、互いに異なり、それぞれ 1 回だけ出ることを固定するテストを追加する（`<(` と `)` は対象として数えない）。
- **FR10:** 置換の対象の間に静的に決まる対象を挟んだ場合の回帰テスト。`rm -rf $(cat a) /tmp/scratch $(cat b)` について、判定が ask / rm-unresolvable で、理由文の指定がこの順で [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの3番目の対象[`$(...)`] ``] であり（番号は元のコマンドでの対象の位置）、互いに異なり、それぞれ 1 回だけ出ること、「1番目のrmの2番目の対象」が理由文に出ないことを固定するテストを追加する。
- **FR11:** 置換の本文に固有の文字列を入れても理由文に出ない。2 つの置換の本文に、ほかでは使わない固有の文字列を入れたコマンド（例: `rm -rf $(printf MULTISUBBODYALPHA) $(printf MULTISUBBODYBETA)`）について、判定が ask / rm-unresolvable で、どちらの固有文字列も理由文に含まれず、理由文の指定が [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] でそれぞれ 1 回だけ出ることを固定するテストを追加する。
- **FR12:** mixed-rm-precedence のテストが自分の feature のケースを位置ではなくラベルで見分ける。tests/test_destructive_guard_mixed_rm_precedence.py の TestCaseTable.setUpClass と TestScenarioCasesPassAgainstTheHook.setUpClass は、自分の feature のケースを `[PRE_EXISTING_CASE_COUNT:]`（1208 番目以降すべて）という固定の位置で取り出している。これを、ラベル（各ケースの 2 番目の要素）が `destructive-guard-mixed-rm-precedence `（feature 名と空白 1 つ）で始まるケースを取り出す方法に変える。あわせて、取り出したケースがケース表の中で連続しており、その先頭がケース表の PRE_EXISTING_CASE_COUNT 番目の位置（0 始まり）にあることを確かめる検査を TestCaseTable に足す。このファイルで変えるのはこの取り出し方とこの検査の追加だけで、ほかの検査と期待値（PRE_EXISTING_CASE_COUNT と PRE_EXISTING_CASES_DIGEST による既存ケースの検査、各シナリオの件数を含む）は変えない。em-workflow/hooks/tests/destructive-guard-cases.json と、ほかの既存テストは変更しない。

### Non-Functional Requirements
- **NFR1 - テストの書き方:** テストは標準ライブラリの unittest だけを使い、フックをサブプロセスとして起動し、標準入力に PreToolUse JSON を渡す。HOME と PATH はテストが明示的に渡し、実行するマシンに左右されない（test/README.md と既存の tests/test_destructive_guard_rm_reason*.py の書き方に合わせる）。
- **NFR2 - 決定性:** 同じコマンドからは毎回同じ理由文が出る（既存の決定性の保証を崩さない）。
- **NFR3 - version:** plugin の version は変更しない（.claude/rules/core-plugin-version-bump.md）。
- **NFR4 - 指定の取り出しと比較:** 理由文からの指定の取り出しは、既存の tests/test_destructive_guard_rm_reason_positions.py の DESIGNATION_PATTERN と同じ形（`` \d+番目のrmの\d+番目の対象(?:\[`[^`]*`\])? ``）で全件を順に取り出し、期待する並びと完全一致で比べる。これで「互いに異なる」「それぞれ 1 回だけ」「順序」を同時に確かめる。

## Implementation Approach

### Architecture

**System Architecture:**
```
tests/test_destructive_guard_multi_substitution_reason.py   (新規、unittest)
        │  サブプロセス起動 / 標準入力に PreToolUse JSON
        ▼
em-workflow/hooks/destructive-guard.py                      (FR6 の条件を満たすときだけ変更)
        │  標準出力に判定 JSON（判定 / 理由文）
        ▼
テストが理由文から指定を DESIGNATION_PATTERN の形で取り出し、期待する並びと完全一致で比べる
```

**Component Diagram:**
```
destructive-guard.py
  ├── _mark_substitutions / _strip_unresolved_marks   置換を印に置き換え、置換だけの語を SUBSTITUTION_STANDIN `$(...)` にする
  ├── _substitution_body_range / _tokenize_marked / split_redirects / _shaped_remainder
  ├── _number_rm_operands                              演算子トークンを数えずに対象に番号を振る
  ├── safe_delete_target                               安全な対象は記録を作らない（番号は占める）
  ├── rm_target_designation                            「N番目のrmのM番目の対象」（置換だけの対象には [`$(...)`] が付く）
  └── strongest_rm_decision                            名前による重複除去
```

### Data Flow

```
テスト → (stdin: PreToolUse JSON, env: HOME / PATH / CLAUDE_BATCH) → destructive-guard.py
       ← (stdout: 判定 ask|deny、理由 ID rm-unresolvable、理由文)
テスト → 理由文から指定を順に取り出す → 期待する並びと完全一致で比較
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: テスト対象のフック
- `tests/test_destructive_guard_rm_reason_positions.py`: DESIGNATION_PATTERN と同じ形で指定を取り出す（NFR4）

**External Dependencies:**
- Python 標準ライブラリ unittest（NFR1）

### File Structure

```
tests/
├── test_destructive_guard_multi_substitution_reason.py   # 新規。FR1〜FR3、FR7〜FR11 の回帰テスト
└── test_destructive_guard_mixed_rm_precedence.py         # FR12 の範囲だけ変更
em-workflow/hooks/
└── destructive-guard.py                                  # FR6 の条件を満たすときだけ変更
```

## Declared Change Set

この節は手書きの一覧ではなく create-plan での導出を述べる。上の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上の機能固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/destructive-guard-multi-substitution-reason/**`
- `test-docs/destructive-guard-multi-substitution-reason/**`

`feature-docs/destructive-guard-multi-substitution-reason/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップが生成する設計成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、その規則を再掲しない。

`test-docs/destructive-guard-multi-substitution-reason/**` はタスクごとのテスト記録 `test-docs/destructive-guard-multi-substitution-reason/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、その規則を再掲しない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。書かれていないことをもって外したとはみなさない。外すことは意図した明示的な絞り込みである。

この宣言は上位集合としての宣言である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、等しい必要はない。実装タスクを生まない feature は `test-docs/destructive-guard-multi-substitution-reason/` ディレクトリを生成しないが、その場合も宣言した `test-docs/destructive-guard-multi-substitution-reason/**` は正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

### Unit Tests
該当なし。各テストはフックをサブプロセスとして起動する（NFR1）。

### Integration Tests
- [ ] TS-1: `rm -rf $(cat a) $(cat b)`（HOME と PATH をテストで固定、CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]、`cat a` と `cat b` が理由文に無い（AC-1）
- [ ] TS-2: `rm -rf $(cat a); rm -rf $(cat b)`（CLAUDE_BATCH なし） - 指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 2番目のrmの1番目の対象[`$(...)`] ``]（AC-2）
- [ ] TS-3: `rm -rf $(cat a) $(cat b)`（CLAUDE_BATCH=1） - deny / rm-unresolvable、指定の並びは TS-1 と同じ（AC-3）
- [ ] TS-4: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` - 全件成功（AC-4）
- [ ] TS-5: `` rm -rf `cat a` `cat b` ``（CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]（AC-5）
- [ ] TS-6: `` rm -rf $(cat a) `cat b` ``（CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]（AC-6）
- [ ] TS-7: `rm -rf <(cat a) <(cat b)`（CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]（AC-7）
- [ ] TS-8: `rm -rf $(cat a) /tmp/scratch $(cat b)`（CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの3番目の対象[`$(...)`] ``]、「1番目のrmの2番目の対象」が無い（AC-8）
- [ ] TS-9: `rm -rf $(printf MULTISUBBODYALPHA) $(printf MULTISUBBODYBETA)`（CLAUDE_BATCH なし） - ask / rm-unresolvable、指定の並び [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]、MULTISUBBODYALPHA と MULTISUBBODYBETA が理由文に無い（AC-9）
- [ ] TS-12: `python3 -m unittest tests.test_destructive_guard_mixed_rm_precedence` - failures 0 / errors 0。自分の feature のケースの取り出しがラベルによる（33 件）こと、それらが PRE_EXISTING_CASE_COUNT 番目から連続していること、`[PRE_EXISTING_CASE_COUNT:]` による取り出しが残っていないこと、PRE_EXISTING_CASE_COUNT / PRE_EXISTING_CASES_DIGEST と各シナリオの期待件数が変わっていないこと、destructive-guard-cases.json に差分が無いこと（AC-10）

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] Existing E2E tests pass without regression

### Edge Cases
該当なし（上の Integration Tests に含む）。

### Performance Tests
該当なし。

## Security Considerations

- **Data Protection:** 置換の本文は理由文に出さない（FR1、FR11）。
- その他の項目（Authentication / Authorization / Input Validation / XSS / SQL Injection / CSRF）は該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

該当なし。

## Performance Optimization

該当なし。

## Assumptions

- **A1:** 報告された現象（2 つの置換対象が同じ `$(...)` に潰れ、1 つしか挙がらない）は現在のコードでは起きない。feature destructive-guard-rm-reason-positions で、合成理由文の各項目の名前が rm_target_designation() による位置の指定（「N番目のrmのM番目の対象」、置換だけの対象には `` [`$(...)`] `` が付く）に変わった。strongest_rm_decision() の名前による重複除去は残っているが、名前が (呼び出し, 対象番号) ごとに一意なので、異なる置換対象は畳まれない。チケットに書かれた行番号（1144〜1147）は古く、該当箇所は現在 9532〜9538 行付近にある。
- **A2:** タスクが例に挙げた「出現順の識別子」の形は、既存の位置による指定で満たす。`$(...)#1` のような新しい表記や、置換本文の一部を理由文に出す方式は採らない。回答（batch-codex-consultation, Q1）で同意済み。
- **A3:** 回帰テストは新しいファイル tests/test_destructive_guard_multi_substitution_reason.py に置く。回答（Q2）で同意済み。
- **A4:** em-workflow/hooks/tests/destructive-guard-cases.json のランナーは判定と理由 ID しか比べず、理由文は比べないので、この回帰はそこでは固定できない。ケースの追加は必須にしない。回答（Q2）で同意済み。
- **A5:** 回答（Q3）により、回帰テストにバッククォート 2 つ、$() とバッククォートの混在、プロセス置換 2 つ、静的対象を挟んだ場合の位置番号、本文が出ないことの 5 ケースを加え、各ケースで 2 つの指定が互いに異なりそれぞれ 1 回だけ出ることを確かめる（FR7〜FR11）。
- **A6:** FR7〜FR11 の期待する指定はコードを読んで導き、オーケストレーターがフックを実行して一致を確かめた。バッククォートは `$( … )` と同じく置換全体が印に置き換わり、置換だけの語は SUBSTITUTION_STANDIN `$(...)` の substitution_only トークンになる（_mark_substitutions, _strip_unresolved_marks）。プロセス置換は本文だけが印になり、`<(` と `)` は演算子トークンとして残る。`<(` は REDIRECT に完全一致しないので引数に残るが、_number_rm_operands は演算子トークンを数えず、`)` は _shaped_remainder が落とす（_substitution_body_range, _tokenize_marked, split_redirects）。`/tmp/scratch` は safe_delete_target() で安全とされ記録を作らないが、対象番号 2 を占める（既存テスト test_single_winner_text_is_exactly_the_single_target_text と同じ扱い）。
- **A7:** verify round 1 の TS-4 の失敗（unittest discover で failures=96 errors=7）は、すべて tests/test_destructive_guard_mixed_rm_precedence.py から出ており、merge-base 78c6db0ed の main でも同じく再現する既存の失敗である。原因は、そのテストが自分の feature のケースを `cases[1208:]` で取り出していることにある。ケース表では destructive-guard-mixed-rm-precedence の 33 件の後ろに、後の feature（destructive-guard-heredoc-literal、3 要素のケースを含む）の 96 件が足されている。
- **A8:** test_every_existing_case_is_present_unchanged_and_first（cases[:1208] の件数とダイジェスト）は現在も通っている（オーケストレーターが実行して確認した）。このため FR12 ではこの検査を変えない。
- **A9:** ケースに含まれる情報のうち、feature ごとに一意な目印はラベルの先頭の feature 名だけなので、見分け方はラベルの先頭一致（`destructive-guard-mixed-rm-precedence ` に空白まで含める）にする。
- **A10:** ラベルの先頭一致だけでは「既存ケースの直後に連続して置かれている」ことを確かめなくなるため、連続性と開始位置の検査を足す（Codex 相談で、位置の固定窓や先頭一致のみより比較的よいと判断）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1〜AC-10 を満たす
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- destructive-guard フック: `em-workflow/hooks/destructive-guard.py`
- 既存の理由文の位置テスト: `tests/test_destructive_guard_rm_reason_positions.py`
- version のルール: `.claude/rules/core-plugin-version-bump.md`

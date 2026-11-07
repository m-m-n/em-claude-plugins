# Feature: scenario-id-fence-scope

## Overview

シナリオ ID 形式検査 `find_hyphenless_scenario_ids` が除外するコード範囲を、行頭の囲みブロックと HTML コメントに変更する。これにより、3 つの文書（planner-contract.md、create-plan-phase.md、plan-writing の SKILL.md）の記述「fenced code blocks を除く」と検査の範囲を一致させる。文書の記述と読み取り側の処理は変えない。

## Objectives

- シナリオ ID 形式検査 `find_hyphenless_scenario_ids` が除外するコード範囲を、3 つの文書の記述「fenced code blocks を除く」と一致させる。

## Technical Requirements

### Functional Requirements
- **FR1:** 検査が除外する範囲: `find_hyphenless_scenario_ids` は、行頭の三連バッククォートまたは `~~~` で囲んだブロックと HTML コメントを除外した残りを検査する。`_strip_noise` は呼ばない。この範囲は feature `scenario-id-ts-hyphen` の SPEC A2（`_strip_noise` と同じ）とは異なる。
- **FR2:** 開始行の判定: 行の先頭の空白（スペースとタブ）に続いて同じ文字が 3 個以上並ぶ行を開始行とする。文字はバッククォートかチルダ（`~`）とする。バッククォートの開始行では、並びより後ろにバッククォートを含まない。
- **FR3:** 終了行の判定: 行の先頭の空白に続いて、開始行と同じ文字が開始行の個数以上並び、その後ろがスペースとタブだけの行を終了行とする。
- **FR4:** 閉じていないブロック: 終了行が無い開始行は、開始行から文書末尾までを除外する。
- **FR5:** 行内の三連バッククォート: 行内の三連バッククォートはブロックとして扱わず、検査する。行頭にある「```<ID>``` for details.」も同じく検査する。
- **FR6:** 変えないもの: `_strip_noise`、`_FENCE_RE`、`_TS_ID_RE`、`extract_verification_scenario_ids`、ID の直前の文字による判定、planner-contract.md・create-plan-phase.md・plan-writing の SKILL.md の記述は変えない。
- **FR7:** 回帰テスト: `~~~` ブロックと行内の三連バッククォートの回帰テストを `tests/test_validate_worker_output.py` に追加する。
- **FR8:** sha256 ピンの更新: `tests/test_gate_option_vocabulary.py` の `VALIDATE_WORKER_OUTPUT_SHA256` と `TEST_VALIDATE_WORKER_OUTPUT_SHA256` を更新し、既存の並びに従って更新理由のコメントを追記する。

### Non-Functional Requirements
- **NFR1 - 純粋関数の維持:** `find_hyphenless_scenario_ids` はファイルにアクセスせず、どの文字列入力でも例外を出さない。

## Implementation Approach

### Data Flow

`find_hyphenless_scenario_ids` の処理順は次のとおり。

1. 文書を改行文字 `\n` で行に区切る。`str.splitlines` は使わない。行末の `\r` は、開始行と終了行の判定で行末の一部として無視する。
2. FR2 から FR4 の判定で、開始行から終了行までの行全体を除外する。開始行の残りの文字列も除外に含める。除外した前後は改行で区切られたまま残す。
3. 残りから HTML コメントを除く。
4. 残りを検査する。ID の直前の文字による判定は変えない。

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は既定で、feature 固有のパスに加えて、ワークフローが生成する次の 2 つのエントリを宣言する。

- `feature-docs/scenario-id-fence-scope/**`
- `test-docs/scenario-id-fence-scope/**`

`feature-docs/scenario-id-fence-scope/**` は、`REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design step が生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成し所有する。この節はそれらを参照するだけで、その規則を再掲しない。

`test-docs/scenario-id-fence-scope/**` は、タスクごとのテスト記録 `test-docs/scenario-id-fence-scope/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成し所有する。この節はそれを参照するだけで、その規則を再掲しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に取り除かない限り宣言に含まれる。記載が無いことを取り除いたとはみなさない。取り除くことは、意図して明示的に範囲を狭める操作である。

この宣言は SUPERSET の表明である。検証時に観測される実際の変更集合は、宣言した集合に含まれていなければならない（CONTAINED IN）。一致している必要は無い。implement タスクを持たない feature は `test-docs/scenario-id-fence-scope/` を生成しないが、その場合も宣言した `test-docs/scenario-id-fence-scope/**` は正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

### Unit Tests
- [ ] TS-1: 行頭の三連バッククォートのブロック内と、開始行の文字列の後ろにある ID - 報告されない（FR1, FR2）
- [ ] TS-2: 行頭の `~~~` ブロック内の ID - 報告されない（FR1, FR2）
- [ ] TS-3: 文の途中の「See ```<ID>``` for details.」 - 報告される（FR5）
- [ ] TS-4: 行頭の「```<ID>``` for details.」 - 報告される（FR2, FR5）
- [ ] TS-5: 先頭にスペースまたはタブがある開始行と終了行で囲んだ ID - 報告されない（FR2, FR3）
- [ ] TS-6: 開始行より長い終了行、後ろにスペースとタブが続く終了行の次の行にある ID - 報告される（FR3）
- [ ] TS-7: 開始行より短い行、別の文字の行、後ろに文字が続く行の次の行にある ID - ブロックが閉じておらず報告されない（FR3, FR4）
- [ ] TS-8: 閉じていない三連バッククォートまたは `~~~` の開始行の前後にある ID - 前の ID だけ報告される（FR4）
- [ ] TS-9: HTML コメント内の ID と、ブロック内の HTML コメント開始記号の後ろでブロックの外にある ID - コメント内の ID は報告されず、ブロックの外の ID は報告される（FR1）
- [ ] TS-10: ブロックの直前の行と直後の行の ID、および文書先頭のブロックの直後の行の ID - すべて報告される（FR1, FR6）
- [ ] TS-11: 行末が CRLF の文書のブロックと、その直後の行の ID - ブロック内は報告されず、直後の行は報告される（FR3）
- [ ] TS-12: `_strip_noise` と `extract_verification_scenario_ids` に `~~~` ブロックと行内の三連バッククォートを渡す - 変更前と同じ結果（`~~~` は残り、行内の三連バッククォートは除去される）（FR6）

### Integration Tests
- [ ] TS-13: VERIFICATION.md とタスク計画に `~~~` ブロック内の ID を書いた planner 結果と、行内の三連バッククォートの ID を書いた planner 結果を検証する - 前者はエラーなし、後者は `scenario-id-form` エラー（FR1, FR5）
- [ ] TS-14: テストスイート全体を実行する - sha256 ピンのテストを含めて通る（FR7, FR8）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] すべての機能要件が実装され、テストされている
- [ ] すべてのテストシナリオが通る
- [ ] AC-1: 行頭の `~~~` ブロック内のハイフン無し ID が検査で報告されない。（FR1, FR2, FR3）
- [ ] AC-2: 行内の三連バッククォートで囲んだハイフン無し ID が検査で報告される。（FR1, FR5）
- [ ] AC-3: 開始行と終了行の判定が FR2 と FR3 のとおりで、閉じていない開始行は文書末尾まで除外する。（FR2, FR3, FR4）
- [ ] AC-4: HTML コメント内のハイフン無し ID が報告されない。（FR1）
- [ ] AC-5: `_strip_noise` と読み取り側の結果が変わらず、3 つの文書の記述に差分が無い。（FR6）
- [ ] AC-6: `~~~` ブロックと行内の三連バッククォートの回帰テストがある。（FR7）
- [ ] AC-7: `python3 -m unittest discover -s tests` が通る。sha256 ピンのテストを含む。（FR8, NFR1）

## Assumptions

- **A1:** 閉じていない行頭の囲みは文書末尾まで除外するため、閉じ忘れが 1 つあると、それ以降の ID がすべて検査を抜ける。読み取り側の `_strip_noise` は閉じていない囲みを除去しないので、抜けた ID は VERIFICATION.md のシナリオとして読まれる。この残存リスクを受け入れる。
- **A2:** 先頭の空白はスペースとタブで、個数の上限は無く、開始行と終了行の両方で認める。
- **A3:** 開始行は同じ文字 3 個以上、バッククォートの開始行の残りにバッククォートを含まない、終了行は同じ文字で開始行の個数以上、後ろはスペースとタブだけとする。行頭の「```<ID>``` for details.」はブロックではなく行内として検査する。
- **A4:** `~` の開始行の残りには制限が無い。行頭の「`~~~<ID>~~~ for details.`」はブロックの開始行になり、ID は検査されず、終了行が無ければ A1 のとおり文書末尾まで除外される。
- **A5:** HTML コメントは引き続き除外する。処理順は `_strip_noise` と同じで、ブロックを先に除外し、残りから HTML コメントを除く。このため、コメント内にある開始行の形の行もブロックを開き、閉じていなければ文書末尾まで除外される。
- **A6:** 新しい範囲は feature `scenario-id-ts-hyphen` の SPEC A2 と異なるため、この feature の SPEC に範囲を明記する。同 feature の SPEC は書き換えない。
- **A7:** 読み取り側と書き込み側の範囲は意図して異なる。`~~~` ブロック内の ID は読み取り側では読まれるが検査では報告されず、行内の三連バッククォート内の ID は読み取り側では読まれないが検査では報告される。
- **A8:** 行内の三連バッククォートで囲んだ ID は、検査対象の文書で再計画時に新たに拒否される場合がある。既存文書の書き換えはスコープ外とする。
- **A9:** 行は改行文字 `\n` で区切り、行末の `\r` は開始行と終了行の判定で行末の一部として無視する。`str.splitlines` は使わない。
- **A10:** 「`- `」「`> `」のような記号が三連バッククォートの前に付く行は開始行ではない。これらのブロック内の ID は新たに検査対象になる。記号「`- `」の形では、字下げされた閉じの行が開始行になり、以降が文書末尾まで除外される場合がある。
- **A11:** 除外は開始行から終了行までの行全体で、開始行の残りの文字列も含む。除外した前後は改行で区切られたまま残り、直前の文字の判定は変わらない。
- **A12:** `tests/test_scenario_id_planner_docs.py` の `hyphenless_ids` は 3 つの文書を調べるローカルの写しで、検査本体を呼ばない。変更しない。写しの範囲は変更前のままになる。

## Open Questions

なし

## References

- feature `scenario-id-ts-hyphen` の SPEC: A2

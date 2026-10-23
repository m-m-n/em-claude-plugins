# Feature: artifact-digest-empty-targets

## Overview

em-workflow/references/artifact-digest.md の `Pre-dispatch verification` と `Layer 5 recording` に、対象が 0 件の場合の扱いを書き足す。expect_digest を要する target が 0 件の dispatch と、written_artifacts が 0 件の completed 結果では Calculation を呼ばない。

## Objectives

- expect_digest の照合対象が 0 件の dispatch（新しい feature の初回 create-spec で REQUIREMENTS.md と SPEC.md がどちらも create になる場合など）で、照合が不一致と判定されて stale 判定が繰り返されることが無くなる
- written_artifacts が 0 件の completed 結果が、Layer 5 recording で artifact-validation failure にならない

## Acceptance Criteria

- [ ] AC-1（FR1）: artifact-digest.md の `Pre-dispatch verification` 節に、expect_digest を要する target が 0 件のときは Calculation を呼ばず、照合を成功とすることが書かれている。
- [ ] AC-2（FR2）: artifact-digest.md の `Layer 5 recording` 節に、written_artifacts が 0 件のときは Calculation を呼ばず、何も記録しないことが書かれている。空の completed 結果の可否は別の層の規則に任せることも書かれている。
- [ ] AC-3（FR3）: em-workflow/scripts/artifact-digest.py に変更が無い。artifact-digest.md の `Calculation` 節では、引き続き終了コード `2` が「no argument was given」を含む。
- [ ] AC-4（FR4）: tests/test_artifact_digest_docs.py に 2 つの 0 件の場合を確かめるテストがあり、`python3 -m unittest discover -s tests` が通る。
- [ ] AC-5（FR1）: 再現手順（REQUIREMENTS.md と SPEC.md がどちらも create の初回 create-spec）を artifact-digest.md の手順どおりにたどると、Calculation を引数なしで呼ぶ手順が出てこず、照合が成功して dispatch に進む。
- [ ] AC-6（NFR2）: `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` の dispatch_digest_wiring が通る。

## Technical Requirements

### Functional Requirements

- **FR1:** Pre-dispatch verification の対象 0 件 — em-workflow/references/artifact-digest.md の `Pre-dispatch verification` に、expect_digest を要する write_policy.targets が 0 件なら Calculation を呼ばずに照合を成功とすることを書く。
- **FR2:** Layer 5 recording の対象 0 件 — em-workflow/references/artifact-digest.md の `Layer 5 recording` に、written_artifacts が 0 件なら Calculation を呼ばずに何も記録しないことを書く。空の completed 結果を拒否するかどうかは、その結果を扱う別の層の規則に任せる。
- **FR3:** スクリプトの無引数時の終了コード維持 — em-workflow/scripts/artifact-digest.py は変更しない。無引数で呼ばれたときは従来どおり終了コード 2 を返し、標準出力に配列を出さない。
- **FR4:** 0 件の場合を固定するテスト — tests/test_artifact_digest_docs.py に、FR1 と FR2 の両方の 0 件の場合が artifact-digest.md の該当節に書かれていることを確かめるテストを追加する。

### Non-Functional Requirements

- **NFR1:** 既存の固定文言を壊さない — tests/test_artifact_digest_docs.py の既存テストが引き続き通る。artifact-digest.md の level-2 見出しは 6 節のまま（`Digest definition`、`Calculation`、`Pre-dispatch verification`、`Layer 5 recording`、`Legacy records`、`Dispatch sites`）にする。既存テストが固定している文言（`one `Calculation` call`、`every `written_artifacts` path`、Calculation の `2` 項目の `no argument was given` / `standard output carries no array`、mismatch 判定や layer-5 失敗に関わる `error` の文言など）も残す。
- **NFR2:** 所有文書だけを変える — 0 件の扱いは artifact-digest.md だけに書く。dispatch site の各節（create-spec-phase.md の 9 / 10 節、develop SKILL.md の design ステップ分岐、create-plan-phase.md の 4 / 8 節、rework-task-synthesis.md の 10 節）には言い直しを足さない。em-workflow/scripts/check-plugin-invariants.py の dispatch_digest_wiring と、既存テストの言い直し検出（restatement markers）がそのまま通る。
- **NFR3:** テストは標準ライブラリのみ — 追加するテストは Python 標準ライブラリの unittest だけを使う。既存テストと同じく、見出しで切り出して空白を正規化し、トークンや句の有無で確かめる。文書全体の一致や改行位置には依存しない。存在しないことを確かめるアサーションには、偽の文面でマッチャーが反応することを示すケースを対にする。

## Implementation Approach

### File Structure

変更するファイル:

```
em-workflow/references/artifact-digest.md   # FR1, FR2
tests/test_artifact_digest_docs.py          # FR4（既存のテストメソッドは変えずに追加）
```

変更しないファイル:

```
em-workflow/scripts/artifact-digest.py                     # FR3
create-spec-phase.md                                       # NFR2（9 / 10 節）
develop SKILL.md                                           # NFR2（design ステップ分岐）
create-plan-phase.md                                       # NFR2（4 / 8 節）
rework-task-synthesis.md                                   # NFR2（10 節）
em-workflow/references/contracts/spec-writer-contract.md   # 「Who verifies `expect_digest`」
```

## Declared Change Set

この節は手で列挙する代わりに create-plan での導出を記す。上記の feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

feature 固有のパスに加え、既定で次の 2 つの workflow 生成エントリを宣言する。

- `feature-docs/artifact-digest-empty-targets/**`
- `test-docs/artifact-digest-empty-targets/**`

`feature-docs/artifact-digest-empty-targets/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、規則を言い直さない。

`test-docs/artifact-digest-empty-targets/**` はタスクごとのテスト記録 `test-docs/artifact-digest-empty-targets/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、規則を言い直さない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。書かれていないことを理由に外れたとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合の主張である。verification 時に観測される実際の変更集合は、宣言された集合に含まれていればよく、一致する必要はない。implement タスクを生まない feature では `test-docs/artifact-digest-empty-targets/` ディレクトリは作られないが、宣言した `test-docs/artifact-digest-empty-targets/**` はその場合も正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS1（AC-1, AC-5）: `Pre-dispatch verification` 節を見出しで切り出して空白を正規化し、0 件（no target / zero targets など）のときに Calculation を呼ばないことと、照合が成功（mismatch ではない）することが書かれていることを確かめる。
- [ ] TS2（AC-2）: `Layer 5 recording` 節を見出しで切り出して空白を正規化し、written_artifacts が 0 件のときに Calculation を呼ばないことと、何も記録しないことが書かれていることを確かめる。
- [ ] TS3（AC-3, AC-4, NFR1）: 既存の tests/test_artifact_digest_docs.py（6 つの level-2 見出し、Calculation の終了コード `2` の文言、Layer 5 の one `Calculation` call、error 要素の不一致・失敗の文言）が変更後も通る。
- [ ] TS4（AC-6, NFR2）: 既存の言い直し検出テスト（TestEverySiteCitesTheOwner）と check-plugin-invariants.py の dispatch_digest_wiring が通る。
- [ ] TS5（NFR3）: 新しいマッチャーが存在しないことの判定に使われる場合は、偽の文面で反応することを示すケースを対にする。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] write_policy.targets が全部 create（expect_digest が常に null）の場合も、targets 自体が空の場合も、どちらも「expect_digest を要する target が 0 件」として扱う。

## Assumptions

- 0 件の扱いは artifact-digest.md の規則として書き、create-spec / design / create-plan / rework の全 dispatch site に一律に適用される。各 site の節は所有文書を引用しているので、site 側の文書は変えない。
- expect_digest を要する target が 1 件以上ある場合の手順は変えない。不一致の条件（sha256 の相違、error 要素、引用規則でコマンドに入れられないパス、終了コード 2）もそのまま残す。
- write_policy.targets が全部 create（expect_digest が常に null）の場合も、targets 自体が空の場合も、どちらも「expect_digest を要する target が 0 件」として扱う。
- written_artifacts が 0 件のとき、Layer 5 recording は phase-state の artifacts に何も足さない。phase-state ファイルの作成や他フィールドの扱いは references/phase-state.md の既存規則のままとし、この feature では変えない。
- written_artifacts が 1 件以上ある場合の Layer 5 recording（1 回の Calculation 呼び出し、error 要素・終了コード 2・引用規則で除外されるパスでの artifact-validation failure）は変えない。
- spec-writer-contract.md の「Who verifies `expect_digest`」はすでに「expect_digest を要する targets のパスを持つ dispatch の直前」に照合すると書いており、0 件の規則と矛盾しない。そのためこの文書は変えない。
- tests/test_artifact_digest_docs.py の既存のテストメソッドは変えずに、テストを追加する形で 0 件の場合を固定する。
- plugin の version は変えない（main への push 時に Actions が patch を上げる）。

## Success Criteria

- [ ] FR1〜FR4 と NFR1〜NFR3 を満たす
- [ ] AC-1〜AC-6 を満たす
- [ ] `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- artifact-digest.md: em-workflow/references/artifact-digest.md
- artifact-digest.py: em-workflow/scripts/artifact-digest.py
- test_artifact_digest_docs.py: tests/test_artifact_digest_docs.py
- check-plugin-invariants.py: em-workflow/scripts/check-plugin-invariants.py
- spec-writer-contract.md: em-workflow/references/contracts/spec-writer-contract.md
- phase-state.md: references/phase-state.md

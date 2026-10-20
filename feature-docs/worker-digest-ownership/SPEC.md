# Feature: worker-digest-ownership

## Overview

write_policy を持つ worker のうち Bash を持たないもの（spec-writer / designer / implementation-planner / rework-planner）は digest を扱わない。expect_digest の照合と layer 5 の digest 計算・記録は、オーケストレーターが 1 本の共通スクリプトで、write_policy を持つ worker のすべての dispatch 箇所で行う。

要件の詳細は `feature-docs/worker-digest-ownership/REQUIREMENTS.md` を参照する。

## Objectives

- Bash を持たない worker（spec-writer / designer / implementation-planner / rework-planner）が、digest を計算できないことを理由に blocked を返して run が止まらないようにする（create-spec 再入: rework の仕様変更、tier 昇格）。
- write_policy の expect_digest 照合と written_artifacts の digest 記録を、オーケストレーターが 1 つの計算手段で行う手順として、write_policy を持つ worker を dispatch するすべての箇所で一貫させる。

## User Stories

### US1: create-spec 再入での spec-writer の dispatch

オーケストレーターとして、create-spec 再入で spec-writer を replace_own 付きで dispatch したい。spec-writer が digest を理由に止まらないようにするため。

**Acceptance Criteria:**
- [ ] AC1（FR1, FR3）: create-spec 再入で spec-writer を replace_own 付きで dispatch したとき、spec-writer は digest を計算できないことを理由に blocked を返さず、REQUIREMENTS.md と SPEC.md を書いて、written_artifacts を path だけで返す。
- [ ] AC3（FR3, FR4）: どの dispatch 箇所でも、expect_digest が現在の digest と食い違う target があるとき、オーケストレーターは worker を dispatch しない。

### US2: 既存の成果物がある状態での designer の dispatch

オーケストレーターとして、既存の design 成果物がある状態で designer を dispatch したい。designer が digest を理由に止まらないようにするため。

**Acceptance Criteria:**
- [ ] AC2（FR1, FR4, FR5）: 既存の成果物（extend_only の tokens.yaml、regenerate の tokens.html、replace_own の mockup）がある状態で designer を dispatch したとき、designer は digest を理由に blocked を返さない。dispatch 前の照合、戻った後の scope verification と artifact validation、phase-state/design.yaml への digest 記録はオーケストレーターが行う。
- [ ] AC8（FR4, FR5）: phase-state/design.yaml が無い既存 feature で design ステップを実行したときの扱いが、develop SKILL.md の「design ステップ分岐」に書かれている。

### US3: digest の定義と計算手段の統一

オーケストレーターとして、すべての digest を同じ定義・同じスクリプトで計算したい。

**Acceptance Criteria:**
- [ ] AC4（FR2, FR7）: expect_digest、phase-state の artifacts[].sha256、layer 5 の digest は、どれも同じ定義（生バイト列の sha256、`sha256:` + 小文字 16 進 64 桁）で、FR7 のスクリプトで計算される、と文書に書かれている。create-spec-phase.md は、この 2 つの用途に git hash-object を指定していない。scope verification の git blob id、workflow_blob、base_workflow_blob、input_digest の定義は変わっていない。
- [ ] AC6（FR7）: FR7 のスクリプトは、既知の内容のファイルに対して既知の digest を出す。複数パスの出力と入力の対応、先頭がハイフンのパス、空白や日本語を含むパス、存在しないファイル、読み取り失敗のそれぞれで、定義した出力と終了コードを返す。

### US4: 旧方式で記録された feature の再開

オーケストレーターとして、旧方式で記録された artifacts を持つ feature を再開したい。

**Acceptance Criteria:**
- [ ] AC7（FR8）: 旧方式で記録された artifacts を持つ feature を再開したとき、旧方式での一致を確認できた target は一致として扱われ、確認できない target は {phase}.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送られる、と文書に書かれている。

### US5: 再発の検出

オーケストレーターとして、上の不変条件が崩れたらテストで検出したい。

**Acceptance Criteria:**
- [ ] AC5（FR6, NFR1, NFR3）: check-plugin-invariants.py の新しい検査が実リポジトリで通り、否定例（FR1〜FR5 のどれかが崩れた合成の木、対象 worker が 0 件の木）で失敗する。validator を実行するテストと FR7 のスクリプトのテストがあり、`python3 -m unittest discover -s tests` で全件通る。

## Technical Requirements

### Functional Requirements

- **FR1:** worker 側は digest を扱わない。envelope の対象 worker のうち、書き込みを持ち tools に Bash を持たないもの（spec-writer / designer / implementation-planner / rework-planner）は、digest を計算せず、expect_digest を照合し直さない。written_artifacts には path だけを書く（sha256 は null か省略）。digest を計算できないことを理由に blocked を返さない。この 4 worker の agent prompt と contract は、worker 側に digest の計算や照合を求める記述を持たない。main 7468e0b7 で spec-writer.md / spec-writer-contract.md / worker-envelope.md / designer.md は対応済み。implementation-planner.md と rework-planner.md には digest の扱いを明示する記述が無く、planner-contract.md と worker-envelope.md の記述に頼っている。
- **FR2:** digest の定義を 1 つに揃える。expect_digest、phase-state の artifacts[].sha256、layer 5（artifact validation）の digest は、どれも「ファイルの生バイト列の sha256 を `sha256:` + 小文字 16 進 64 桁で表したもの」とする。create-spec-phase.md で `git hash-object --` を使っている 2 か所（Pre-dispatch snapshot 表の `write_policy.targets` digests の行、§10 の Artifact digests の項）を、この定義と FR7 の計算手段に合わせて書き換える。次のものは現行のまま変えない: scope verification の事後比較で使う git blob id（`git hash-object`）、workflow_blob、base_workflow_blob、input_digest（Rule R1 の正規化 JSON の sha256）。文書は、sha256 の digest と git blob id が別のものであることを明記する。
- **FR3:** 照合と記録を全 dispatch 箇所で行う。dispatch 前の expect_digest 照合と、layer 5 の digest 計算・記録は、write_policy を持つ worker を dispatch するすべての箇所でオーケストレーターが FR7 のスクリプトで行う: create-spec（spec-writer）、design ステップ（designer）、create-plan（implementation-planner）、rework（rework-planner）。手順の本文は 1 つのドキュメントが持ち、ほかの箇所は path で参照する。spec-writer-contract.md の「Who verifies `expect_digest`」は現在 create-spec-phase.md だけを参照しているため、ほかの dispatch 箇所も手順の対象だと読めるように揃える。create-plan-phase.md の §4（Planner dispatch）と §8（Validation）には、現在このどちらの記述も無い（scope verification は create-spec-phase.md の「Scope verification」を参照している）。rework-planner の dispatch 箇所は rework-task-synthesis.md §10 の「Dispatch input (step 2, all four routes)」で、ここにも記述が無い。変更は共通の計算手段と、dispatch 前後の照合・記録の接続に限る。計画パッチの権限、再計画の認可などは変えない。
- **FR4:** design ステップの照合・検証・記録。skills/develop/SKILL.md の「design ステップ分岐」に次を書く。(1) designer の dispatch 直前に、expect_digest が必要な各 write_policy.targets を照合する。不一致なら dispatch せず、入力を stale として扱い、action を決め直す。(2) designer が戻ったら、scope verification（layer 4）と artifact validation（layer 5）を行い、written_artifacts の各 path の digest を phase-state/design.yaml の artifacts に記録する。(3) phase-state/design.yaml が無い既存 feature の扱い。既存 mockup の更新を replace_own にするかの判定は、design.yaml に記録された「直前の同じ phase の出力」の digest と比べて行う。
- **FR5:** design phase の値と記録場所。phase-state/design.yaml を既存のスキーマで新設する。phase-state.md のファイル構成と `phase` の値、worker-envelope.md の入力 `phase` の値、validate-worker-output.py の PHASE_VALUES に `design` を加える。designer は workflow patch を返さないため、phase-state.md の Resume decision table のうちパッチを前提にした行（`applying_patch` の 2 行）は design.yaml に適用しない。
- **FR6:** 再発を検出するテスト。em-workflow/scripts/check-plugin-invariants.py に不変条件の検査を加え、tests/ から実リポジトリと否定例（合成した木）の両方で実行する。対象 worker は worker-envelope.md の Applicability 表と agents/*.md の frontmatter の tools から導き、書き込みを持ち Bash を持たない worker を対象にする（読み取り専用の requirements-analyst は除く）。加えて次のテストを置く: validator を実行するテスト（4 worker の completed 結果で written_artifacts の sha256 の省略と null を受け付ける、phase-state の phase: design を受け付け、未知の phase を拒否する）、FR7 のスクリプトの既知の期待値と失敗時の動作のテスト。テストは、全文一致、特定の改行位置への依存、worker 名の固定列挙を使わない。対象の集合が空のときに通ってしまう作りにしない。
- **FR7:** digest を計算する共通スクリプト。標準ライブラリだけを使う Python スクリプトを em-workflow/scripts/ に 1 本加え、FR2 の digest を計算する。呼び出しは python3 + 引用符で囲んだスクリプトのパス + 対象パスの形とする。FR3 のすべての dispatch 箇所は、この呼び出しを参照する。スクリプトは次の動作を定義する: 複数のパスを渡したときの出力と入力の対応、先頭がハイフンのパス、空白や日本語を含むパス、存在しないファイル、読み取りに失敗したときの終了コード。文書は、このスクリプトの digest と input_digest の計算を別のものとして区別する。
- **FR8:** 旧方式で記録された artifacts の扱い。phase-state の artifacts に旧方式（git blob id）で記録された既存の値は、旧方式での一致（記録値が、現在のファイルを旧方式で計算した値と一致すること）を確認できたものだけを新方式の digest に読み替える。確認できないものは、既存の digest 不一致の処理（{phase}.artifact-overwrite ゲート。batch では batch-policies.yaml の決定）に送る。

### Non-Functional Requirements

- **NFR1 - 既存テストの維持:** `python3 -m unittest discover -s tests` が全件通る。既存の文言テストが固定している次の内容を保つ: spec-writer.md の digest の扱いを書いた 3 つの文言（tests/test_new_worker_agents.py）、spec-writer-contract.md の「### Who verifies `expect_digest`」の節と、その中の 2 文（tests/test_worker_contracts_create_spec.py）、create-spec-phase.md の事後比較の文言「Content hashing with `git hash-object --` is applied only to the」と、create-plan-phase.md に `git hash-object` を書かない制約（tests/test_phase_protocols.py）、worker-envelope.md に `expect_digest` という語を書かない制約（tests/test_worker_contract_docs.py）、phase-state.md の Resume decision table の各 status の行と 2 つの `dispatching` 行、Legacy feature compatibility の節（tests/test_phase_state_doc.py）。tests/test_check_plugin_invariants.py の既存の検査（合成した木での exit 0、run_all_checks での iter_repo_files の 1 回だけの走査、実リポジトリでの exit 0）も通る。
- **NFR2 - SSOT の維持:** 手順や定義の本文は所有ドキュメント 1 か所に置き、ほかのドキュメントは path で参照する。言い換えて書き直さない。
- **NFR3 - 標準ライブラリだけ:** テストコードは Python 標準ライブラリの unittest だけを使い、サードパーティのパッケージを import しない。FR7 のスクリプトも標準ライブラリだけを使い、sha256sum などの外部コマンドを呼ばない。

## Implementation Approach

### Architecture

**役割の分担:**

```
オーケストレーター
  ├─ dispatch 前: expect_digest が必要な各 write_policy.targets を FR7 のスクリプトで計算し、照合する（FR3）
  │    └─ 不一致: dispatch しない。入力を stale として扱い、action を決め直す
  ├─ dispatch: worker（spec-writer / designer / implementation-planner / rework-planner）
  │    └─ worker: digest を計算しない。written_artifacts は path だけ（FR1）
  └─ 戻った後: layer 4（scope verification）、layer 5（artifact validation）
       └─ written_artifacts の各 path を FR7 のスクリプトで計算し、phase-state の artifacts に記録する
```

**dispatch 箇所と変更対象（FR3）:**

| dispatch 箇所 | worker | 文書 | 変更内容 |
|---------------|--------|------|----------|
| create-spec | spec-writer | `em-workflow/references/phases/create-spec-phase.md` | Pre-dispatch snapshot 表の `write_policy.targets` digests の行、§10 の Artifact digests の項を、FR2 の定義と FR7 の計算手段に合わせる |
| design ステップ | designer | `em-workflow/skills/develop/SKILL.md` の「design ステップ分岐」 | FR4 の (1)〜(3) を書く |
| create-plan | implementation-planner | `em-workflow/references/phases/create-plan-phase.md` の §4（Planner dispatch）と §8（Validation） | dispatch 前の照合と layer 5 の記録を、所有ドキュメントの参照で接続する。`git hash-object` は書かない（NFR1） |
| rework | rework-planner | rework-task-synthesis.md §10 の「Dispatch input (step 2, all four routes)」 | dispatch 前の照合と layer 5 の記録を、所有ドキュメントの参照で接続する |

- 手順の本文は 1 つのドキュメントが持ち、ほかの箇所は path で参照する（FR3、NFR2）。
- `em-workflow/references/contracts/spec-writer-contract.md` の「Who verifies `expect_digest`」は、ほかの dispatch 箇所も手順の対象だと読めるように揃える（FR3）。NFR1 が固定する節見出しと 2 文は保つ。
- `em-workflow/references/contracts/worker-envelope.md` には `expect_digest` という語を書かない（NFR1）。

**worker 側の記述（FR1）:**

- 対象: spec-writer / designer / implementation-planner / rework-planner の agent prompt と contract。
- main 7468e0b7 の worker 側の修正（spec-writer.md、spec-writer-contract.md の「Who verifies `expect_digest`」、worker-envelope.md の「`written_artifacts` reporting」、designer.md の Output）は維持する（A1）。
- implementation-planner.md と rework-planner.md は、現在 digest の扱いを明示する記述が無い。

### Data Flow

```
write_policy.targets ──FR7 のスクリプト──▶ 現在の digest ──照合──▶ expect_digest
                                                         │
                                         一致 ──▶ dispatch ──▶ worker が書く ──▶ written_artifacts（path のみ）
                                         不一致 ──▶ dispatch しない（stale）       │
                                                                                    ▼
                                                         FR7 のスクリプト ──▶ phase-state の artifacts[].sha256
```

### digest の定義（FR2）

| 値 | 定義 | この feature での扱い |
|----|------|----------------------|
| expect_digest | ファイルの生バイト列の sha256（`sha256:` + 小文字 16 進 64 桁） | FR7 のスクリプトで計算する |
| phase-state の artifacts[].sha256 | 同上 | FR7 のスクリプトで計算する |
| layer 5 の digest | 同上 | FR7 のスクリプトで計算する |
| scope verification の事後比較の git blob id | `git hash-object` | 変えない |
| workflow_blob / base_workflow_blob | 現行の定義 | 変えない |
| input_digest | Rule R1 の正規化 JSON の sha256 | 変えない。FR7 のスクリプトの digest とは別のものとして文書で区別する |

文書は、sha256 の digest と git blob id が別のものであることを明記する。

### FR7 のスクリプト

- 置き場所: `em-workflow/scripts/` に 1 本。
- 依存: Python 標準ライブラリだけ。sha256sum などの外部コマンドを呼ばない（NFR3）。
- 呼び出し: python3 + 引用符で囲んだスクリプトのパス + 対象パス。
- 出力: 各対象パスの digest（`sha256:` + 小文字 16 進 64 桁）。
- 定義する動作:
    - 複数のパスを渡したときの出力と入力の対応
    - 先頭がハイフンのパス
    - 空白や日本語を含むパス
    - 存在しないファイル
    - 読み取りに失敗したときの終了コード
- ファイル名、出力の形式、終了コードの具体的な値は requirements_analysis で決まっていない（A7。Open Questions を参照）。
- この呼び出しは workflow.yaml 由来のコマンドではないため、hooks/bash_guard.py は判定を返さず、通常の permission の流れになる。

### design phase（FR4、FR5）

- `phase-state/design.yaml` を既存の phase-state のスキーマで新設する（A3）。
- `design` を加える箇所:
    - `em-workflow/references/phase-state.md` のファイル構成と `phase` の値
    - `em-workflow/references/contracts/worker-envelope.md` の入力 `phase` の値
    - `validate-worker-output.py` の PHASE_VALUES
- phase-state.md の Resume decision table の `applying_patch` の 2 行は design.yaml に適用しない。design.yaml の status は applying_patch にならない。
- design ステップが skipped のときは designer を dispatch せず、phase-state/design.yaml も作らない。
- tokens.yaml（extend_only）と tokens.html（regenerate）は written_artifacts に両方そろって現れ、どちらも digest の記録対象になる。
- phase-state/design.yaml が無い既存 feature で既存の design 成果物があるとき、その成果物は FR8 の「一致を確認できない記録」と同じく扱い、design.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る。phase-state.md の Legacy feature compatibility 表で、phase-state が無いときに既存文書を digest 不一致として扱う規則と同じ扱いになる（A6）。

### 旧方式の記録（FR8）

- 旧方式の記録値は、現在のファイルを旧方式（git blob id）で計算した値と一致することを確認できたものだけを、新方式の digest に読み替える。
- 確認できないものは {phase}.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る。
- 旧方式の記録値は `sha256:` 接頭辞付きの git blob id の形で残っている可能性がある。git の object format が SHA-256 のリポジトリでは git blob id も 64 桁になるので、桁数では新旧を見分けない。判定は一致確認で行う。

### 不変条件の検査（FR6）

- 追加先: `em-workflow/scripts/check-plugin-invariants.py`。
- 対象 worker の導出: `worker-envelope.md` の Applicability 表と `agents/*.md` の frontmatter の tools から、書き込みを持ち Bash を持たない worker を導く。読み取り専用の requirements-analyst は除く。Applicability 表の worker 名に付く `(new)` / `(revised)` の注記は名前に含めない。
- 対象の集合が空のときは失敗する。
- 全文一致、特定の改行位置への依存、worker 名の固定列挙を使わない。
- tests/ から実リポジトリと否定例（合成した木）の両方で実行する。
- tests/ に新しく書くテストに、`subagent_type=` の後に引用符で囲んだ「`em-workflow:` + agent 名」が続く形の文字列を入れない。実リポジトリでの agent_dispatch_parity の検査に拾われる（除外されているのは tests/test_check_plugin_invariants.py と check-plugin-invariants.py だけ）。

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/contracts/worker-envelope.md`: Applicability 表、`written_artifacts` reporting、入力 `phase` の値
- `em-workflow/references/contracts/spec-writer-contract.md`: 「Who verifies `expect_digest`」、artifact-overwrite ゲート
- `em-workflow/references/phase-state.md`: ファイル構成、`phase` の値、Resume decision table、Legacy feature compatibility
- `validate-worker-output.py`: PHASE_VALUES、`--kind worker-result`、`--kind phase-state`
- `batch-policies.yaml`: {phase}.artifact-overwrite ゲートの batch での決定

**External Dependencies:**
- なし（Python 標準ライブラリだけ。NFR3）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/worker-digest-ownership/**`
- `test-docs/worker-digest-ownership/**`

`feature-docs/worker-digest-ownership/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/worker-digest-ownership/**` covers
`test-docs/worker-digest-ownership/{T}.tests.yaml`, the per-task test record.
It is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/worker-digest-ownership/` directory at all; the declared
`test-docs/worker-digest-ownership/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1（FR1, FR6）: check-plugin-invariants.py の新しい検査が、worker-envelope.md の Applicability 表と agents/*.md の frontmatter の tools から「envelope の対象で、書き込みを持ち、Bash を持たない worker」を導き、その各 agent prompt と contract が worker 側の digest 計算や expect_digest 照合を指示しておらず、digest を計算できないことを理由に blocked を返さない旨と written_artifacts は path だけでよい旨を（本文または参照で）持つことを調べる。実リポジトリで通り、どれかの worker の記述を崩した合成の木で失敗することを確かめる。
- [ ] TS2（FR3, FR4, FR7）: write_policy を持つ worker の各 dispatch 箇所（create-spec-phase.md、develop SKILL.md の「design ステップ分岐」、create-plan-phase.md、rework-task-synthesis.md §10 の dispatch 入力）が、dispatch 前の expect_digest 照合と layer 5 の digest 記録を、本文に書くか所有ドキュメントを参照していること、計算手段として FR7 のスクリプトに行き着くことを、新しい検査で調べる。create-plan-phase.md に `git hash-object` が現れないことも確かめる。どれかの箇所から参照を外した合成の木で失敗することを確かめる。
- [ ] TS3（FR2, FR8）: create-spec-phase.md の expect_digest 照合（Pre-dispatch snapshot 表の行）と §10 の Artifact digests が `git hash-object` を指定しておらず、FR2 の定義（またはその所有ドキュメント）を参照していることを調べる。事後比較の blob id の文言が残っていること、旧方式の記録の扱い（FR8）が所有ドキュメントに書かれていることも確かめる。
- [ ] TS4（FR5）: `validate-worker-output.py --kind phase-state` を実行し、phase: design の phase-state を受け付け、未知の phase を拒否することを確かめる。worker-envelope.md と phase-state.md の phase の値に design が含まれることも調べる。
- [ ] TS5（FR1, FR6）: `validate-worker-output.py --kind worker-result` を実行し、spec-writer / designer / implementation-planner / rework-planner の completed 結果のうち、written_artifacts の各エントリが sha256: null のものと sha256 を省略したものが、どちらも受け付けられることを確かめる。
- [ ] TS6（FR7）: FR7 のスクリプトを実行し、既知の内容（空のファイルなど）に対して既知の sha256 を `sha256:` + 小文字 16 進 64 桁で出すこと、複数パスで出力と入力が対応すること、先頭がハイフンのパスと、空白や日本語を含むパスを正しく扱うことを確かめる。
- [ ] TS7（FR7）: FR7 のスクリプトに存在しないファイルと読み取れないファイルを渡し、定義した終了コードと出力になることを確かめる。
- [ ] TS8（FR6）: 対象 worker が 0 件になる合成の木（Applicability 表が無い、または該当する agent が無い）で、新しい検査が通らずに失敗することを確かめる。

### Integration Tests

- [ ] `python3 -m unittest discover -s tests` が全件通る（NFR1）。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

agent の実行時の挙動は unit test から直接は実行しない（A5）。

### Edge Cases

- [ ] worker が written_artifacts に sha256 を書いてきた場合、その値は検証に使わない（worker-envelope.md の既存規則）。
- [ ] preserve の target に worker は書かない。layer 5 で記録する対象にもならない。
- [ ] action が create の target が既にある場合、worker は blocked を返す（存在の確認は Read でできる）。
- [ ] tokens.yaml（extend_only）と tokens.html（regenerate）は written_artifacts に両方そろって現れ、どちらも digest の記録対象になる。
- [ ] design ステップが skipped のときは designer を dispatch せず、phase-state/design.yaml も作らない。
- [ ] tier 昇格による create-spec 再入も、rework の仕様変更による再入と同じ dispatch 経路を通る。
- [ ] 旧方式の記録値は `sha256:` 接頭辞付きの git blob id の形で残っている可能性がある。git の object format が SHA-256 のリポジトリでは git blob id も 64 桁になるので、桁数では新旧を見分けられない。判定は FR8 の一致確認で行う。
- [ ] phase-state/design.yaml の status は applying_patch にならない。Resume decision table の applying_patch の行は design.yaml に適用しない（FR5）。
- [ ] rework-planner の replace_own の target（VERIFICATION.md / IMPLEMENTATION.md）の直前の出力は create-plan のもので、create-plan.yaml に記録されている場合がある。spec-writer-contract.md の artifact-overwrite ゲートは create-spec / design / create-plan の 3 つだけ。rework での action の決め方は、この feature では変えない（FR3 の範囲の限定）。
- [ ] FR7 のスクリプトの呼び出しは workflow.yaml 由来のコマンドではないため、hooks/bash_guard.py は判定を返さず、通常の permission の流れになる。
- [ ] worker-envelope.md の Applicability 表の worker 名には `(new)` / `(revised)` の注記が付いている。対象 worker を導くときはこの注記を名前に含めない。
- [ ] tests/ に新しく書くテストに、`subagent_type=` の後に引用符で囲んだ「`em-workflow:` + agent 名」が続く形の文字列を入れると、実リポジトリでの agent_dispatch_parity の検査に拾われる。除外されているのは tests/test_check_plugin_invariants.py と check-plugin-invariants.py だけ。

### Performance Tests

該当なし

## Security Considerations

該当なし

## Error Handling

| 条件 | 対応 |
|------|------|
| expect_digest が現在の digest と食い違う target がある | worker を dispatch しない。入力を stale として扱い、action を決め直す（FR3、FR4） |
| 旧方式の記録で一致を確認できない | {phase}.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る（FR8） |
| phase-state/design.yaml が無い既存 feature で既存の design 成果物がある | design.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る（A6） |
| FR7 のスクリプトに存在しないファイル、読み取れないファイルを渡した | 定義した出力と終了コードを返す（FR7） |

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` が全件通る（NFR1）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- `status: tbd` の要件は無い。
- FR7 のスクリプトのファイル名、出力の形式、終了コードの具体的な値は、A7 により SPEC で決めることになっているが、requirements_analysis に具体的な値が無いため、この SPEC には書いていない。

## References

- 要件定義書: `feature-docs/worker-digest-ownership/REQUIREMENTS.md`
- `em-workflow/references/contracts/worker-envelope.md`
- `em-workflow/references/contracts/spec-writer-contract.md`
- `em-workflow/references/phases/create-spec-phase.md`
- `em-workflow/references/phases/create-plan-phase.md`
- `em-workflow/references/phase-state.md`
- `em-workflow/skills/develop/SKILL.md`
- rework-task-synthesis.md §10

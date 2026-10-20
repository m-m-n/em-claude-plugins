---
title: "worker-digest-ownership"
created_date: 2026-10-21
status: draft
---

# worker-digest-ownership - 要件定義書

## 1. 概要

### 1.1 背景

Bash を持たない worker（spec-writer / designer / implementation-planner / rework-planner）が、digest を計算できないことを理由に blocked を返し、run が止まる。対象となる経路は create-spec 再入（rework の仕様変更、tier 昇格）。

main 7468e0b7 で spec-writer.md / spec-writer-contract.md / worker-envelope.md / designer.md は対応済み。implementation-planner.md と rework-planner.md には digest の扱いを明示する記述が無く、planner-contract.md と worker-envelope.md の記述に頼っている。

### 1.2 目的

- Bash を持たない worker が、digest を計算できないことを理由に blocked を返して run が止まらないようにする。
- write_policy の expect_digest 照合と written_artifacts の digest 記録を、オーケストレーターが 1 つの計算手段で行う手順として、write_policy を持つ worker を dispatch するすべての箇所で一貫させる。

### 1.3 スコープ

対象:

- worker 側の digest の扱い（FR1）
- digest の定義の統一（FR2）
- write_policy を持つ worker の全 dispatch 箇所での照合と記録（FR3）: create-spec（spec-writer）、design ステップ（designer）、create-plan（implementation-planner）、rework（rework-planner）
- design ステップの照合・検証・記録と phase-state/design.yaml（FR4、FR5）
- 再発を検出するテスト（FR6）
- digest を計算する共通スクリプト（FR7）
- 旧方式で記録された artifacts の扱い（FR8）

対象外:

- 計画パッチの権限、再計画の認可（FR3）
- rework での action の決め方（FR3 の範囲の限定）
- scope verification の事後比較で使う git blob id、workflow_blob、base_workflow_blob、input_digest の定義（FR2）

## 2. ビジネス要件

### 2.1 ビジネス目標

- Bash を持たない worker（spec-writer / designer / implementation-planner / rework-planner）が、digest を計算できないことを理由に blocked を返して run が止まらないようにする（create-spec 再入: rework の仕様変更、tier 昇格）。
- write_policy の expect_digest 照合と written_artifacts の digest 記録を、オーケストレーターが 1 つの計算手段で行う手順として、write_policy を持つ worker を dispatch するすべての箇所で一貫させる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | dispatch 前の expect_digest 照合と、layer 5 の digest 計算・記録を行う |
| 書き込みを持ち Bash を持たない worker | spec-writer / designer / implementation-planner / rework-planner。digest を扱わない |

### 2.3 期待される効果

- create-spec 再入と design ステップで、worker が digest を理由に blocked を返さない。
- expect_digest、phase-state の artifacts[].sha256、layer 5 の digest が同じ定義・同じ計算手段になる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | create-spec 再入で spec-writer を replace_own 付きで dispatch する | オーケストレーター | 高 |
| UC02 | 既存の成果物がある状態で designer を dispatch する | オーケストレーター | 高 |
| UC03 | 旧方式で記録された artifacts を持つ feature を再開する | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: create-spec 再入で spec-writer を replace_own 付きで dispatch する

**アクター**: オーケストレーター

**事前条件**:
- REQUIREMENTS.md と SPEC.md が既にある（rework の仕様変更、または tier 昇格による create-spec 再入）

**基本フロー**:
1. オーケストレーターが、expect_digest が必要な各 write_policy.targets の digest を FR7 のスクリプトで計算し、expect_digest と照合する。
2. オーケストレーターが spec-writer を dispatch する。
3. spec-writer が REQUIREMENTS.md と SPEC.md を書き、written_artifacts を path だけで返す。
4. オーケストレーターが layer 5 で written_artifacts の各 path の digest を FR7 のスクリプトで計算し、記録する。

**代替フロー**:
- expect_digest が現在の digest と食い違う target があるとき、オーケストレーターは dispatch しない。

**事後条件**:
- spec-writer は digest を計算できないことを理由に blocked を返していない。

#### UC02: 既存の成果物がある状態で designer を dispatch する

**アクター**: オーケストレーター

**事前条件**:
- extend_only の tokens.yaml、regenerate の tokens.html、replace_own の mockup がある

**基本フロー**:
1. オーケストレーターが、designer の dispatch 直前に、expect_digest が必要な各 write_policy.targets を照合する。
2. オーケストレーターが designer を dispatch する。
3. designer が戻ったら、オーケストレーターが scope verification（layer 4）と artifact validation（layer 5）を行う。
4. オーケストレーターが written_artifacts の各 path の digest を phase-state/design.yaml の artifacts に記録する。

**代替フロー**:
- 照合が不一致なら dispatch せず、入力を stale として扱い、action を決め直す。
- phase-state/design.yaml が無い既存 feature で既存の design 成果物があるときは、design.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る。

**事後条件**:
- designer は digest を理由に blocked を返していない。

#### UC03: 旧方式で記録された artifacts を持つ feature を再開する

**アクター**: オーケストレーター

**事前条件**:
- phase-state の artifacts に旧方式（git blob id）で記録された値がある

**基本フロー**:
1. 記録値が、現在のファイルを旧方式で計算した値と一致するかを確認する。
2. 一致を確認できたものを新方式の digest に読み替える。

**代替フロー**:
- 一致を確認できないものは {phase}.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る。

**事後条件**:
- 旧方式の記録はすべて、読み替えられたか、ゲートに送られている。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | worker 側は digest を扱わない | 書き込みを持ち Bash を持たない worker は digest を計算・照合しない | 高 |
| FR2 | digest の定義を 1 つに揃える | 生バイト列の sha256（`sha256:` + 小文字 16 進 64 桁） | 高 |
| FR3 | 照合と記録を全 dispatch 箇所で行う | write_policy を持つ worker のすべての dispatch 箇所でオーケストレーターが行う | 高 |
| FR4 | design ステップの照合・検証・記録 | develop SKILL.md の「design ステップ分岐」に記述する | 高 |
| FR5 | design phase の値と記録場所 | phase-state/design.yaml の新設と `design` の phase 値 | 高 |
| FR6 | 再発を検出するテスト | check-plugin-invariants.py の不変条件検査と関連テスト | 高 |
| FR7 | digest を計算する共通スクリプト | 標準ライブラリだけの Python スクリプトを em-workflow/scripts/ に 1 本加える | 高 |
| FR8 | 旧方式で記録された artifacts の扱い | 旧方式での一致を確認できたものだけを読み替える | 高 |

### 4.2 機能詳細

#### FR1: worker 側は digest を扱わない

**説明**: envelope の対象 worker のうち、書き込みを持ち tools に Bash を持たないもの（spec-writer / designer / implementation-planner / rework-planner）は、digest を計算せず、expect_digest を照合し直さない。written_artifacts には path だけを書く（sha256 は null か省略）。digest を計算できないことを理由に blocked を返さない。この 4 worker の agent prompt と contract は、worker 側に digest の計算や照合を求める記述を持たない。

main 7468e0b7 で spec-writer.md / spec-writer-contract.md / worker-envelope.md / designer.md は対応済み。implementation-planner.md と rework-planner.md には digest の扱いを明示する記述が無く、planner-contract.md と worker-envelope.md の記述に頼っている。

**ビジネスルール**:
- worker が written_artifacts に sha256 を書いてきた場合、その値は検証に使わない（worker-envelope.md の既存規則）。
- preserve の target に worker は書かない。layer 5 で記録する対象にもならない。
- action が create の target が既にある場合、worker は blocked を返す（存在の確認は Read でできる）。

#### FR2: digest の定義を 1 つに揃える

**説明**: expect_digest、phase-state の artifacts[].sha256、layer 5（artifact validation）の digest は、どれも「ファイルの生バイト列の sha256 を `sha256:` + 小文字 16 進 64 桁で表したもの」とする。

create-spec-phase.md で `git hash-object --` を使っている 2 か所を、この定義と FR7 の計算手段に合わせて書き換える。

- Pre-dispatch snapshot 表の `write_policy.targets` digests の行
- §10 の Artifact digests の項

**ビジネスルール**:
- 次のものは現行のまま変えない: scope verification の事後比較で使う git blob id（`git hash-object`）、workflow_blob、base_workflow_blob、input_digest（Rule R1 の正規化 JSON の sha256）。
- 文書は、sha256 の digest と git blob id が別のものであることを明記する。

#### FR3: 照合と記録を全 dispatch 箇所で行う

**説明**: dispatch 前の expect_digest 照合と、layer 5 の digest 計算・記録は、write_policy を持つ worker を dispatch するすべての箇所でオーケストレーターが FR7 のスクリプトで行う。

| dispatch 箇所 | worker | 記述箇所と現状 |
|---------------|--------|----------------|
| create-spec | spec-writer | create-spec-phase.md |
| design ステップ | designer | skills/develop/SKILL.md の「design ステップ分岐」 |
| create-plan | implementation-planner | create-plan-phase.md の §4（Planner dispatch）と §8（Validation）。現在、照合・記録のどちらの記述も無い（scope verification は create-spec-phase.md の「Scope verification」を参照している） |
| rework | rework-planner | rework-task-synthesis.md §10 の「Dispatch input (step 2, all four routes)」。現在、記述が無い |

**ビジネスルール**:
- 手順の本文は 1 つのドキュメントが持ち、ほかの箇所は path で参照する。
- spec-writer-contract.md の「Who verifies `expect_digest`」は現在 create-spec-phase.md だけを参照しているため、ほかの dispatch 箇所も手順の対象だと読めるように揃える。
- 変更は共通の計算手段と、dispatch 前後の照合・記録の接続に限る。計画パッチの権限、再計画の認可などは変えない。
- tier 昇格による create-spec 再入も、rework の仕様変更による再入と同じ dispatch 経路を通る。
- rework-planner の replace_own の target（VERIFICATION.md / IMPLEMENTATION.md）の直前の出力は create-plan のもので、create-plan.yaml に記録されている場合がある。spec-writer-contract.md の artifact-overwrite ゲートは create-spec / design / create-plan の 3 つだけ。rework での action の決め方は、この feature では変えない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| expect_digest 不一致 | expect_digest が現在の digest と食い違う target がある | worker を dispatch しない |

#### FR4: design ステップの照合・検証・記録

**説明**: skills/develop/SKILL.md の「design ステップ分岐」に次を書く。

1. designer の dispatch 直前に、expect_digest が必要な各 write_policy.targets を照合する。不一致なら dispatch せず、入力を stale として扱い、action を決め直す。
2. designer が戻ったら、scope verification（layer 4）と artifact validation（layer 5）を行い、written_artifacts の各 path の digest を phase-state/design.yaml の artifacts に記録する。
3. phase-state/design.yaml が無い既存 feature の扱い。既存 mockup の更新を replace_own にするかの判定は、design.yaml に記録された「直前の同じ phase の出力」の digest と比べて行う。

**ビジネスルール**:
- tokens.yaml（extend_only）と tokens.html（regenerate）は written_artifacts に両方そろって現れ、どちらも digest の記録対象になる。
- design ステップが skipped のときは designer を dispatch せず、phase-state/design.yaml も作らない。

#### FR5: design phase の値と記録場所

**説明**: phase-state/design.yaml を既存のスキーマで新設する。次に `design` を加える。

- phase-state.md のファイル構成と `phase` の値
- worker-envelope.md の入力 `phase` の値
- validate-worker-output.py の PHASE_VALUES

**ビジネスルール**:
- designer は workflow patch を返さないため、phase-state.md の Resume decision table のうちパッチを前提にした行（`applying_patch` の 2 行）は design.yaml に適用しない。
- phase-state/design.yaml の status は applying_patch にならない。

#### FR6: 再発を検出するテスト

**説明**: em-workflow/scripts/check-plugin-invariants.py に不変条件の検査を加え、tests/ から実リポジトリと否定例（合成した木）の両方で実行する。

対象 worker は worker-envelope.md の Applicability 表と agents/*.md の frontmatter の tools から導き、書き込みを持ち Bash を持たない worker を対象にする（読み取り専用の requirements-analyst は除く）。

加えて次のテストを置く。

- validator を実行するテスト: 4 worker の completed 結果で written_artifacts の sha256 の省略と null を受け付ける。phase-state の phase: design を受け付け、未知の phase を拒否する。
- FR7 のスクリプトの既知の期待値と失敗時の動作のテスト

**ビジネスルール**:
- テストは、全文一致、特定の改行位置への依存、worker 名の固定列挙を使わない。
- 対象の集合が空のときに通ってしまう作りにしない。
- worker-envelope.md の Applicability 表の worker 名には `(new)` / `(revised)` の注記が付いている。対象 worker を導くときはこの注記を名前に含めない。
- tests/ に新しく書くテストに、`subagent_type=` の後に引用符で囲んだ「`em-workflow:` + agent 名」が続く形の文字列を入れると、実リポジトリでの agent_dispatch_parity の検査に拾われる。除外されているのは tests/test_check_plugin_invariants.py と check-plugin-invariants.py だけ。

#### FR7: digest を計算する共通スクリプト

**説明**: 標準ライブラリだけを使う Python スクリプトを em-workflow/scripts/ に 1 本加え、FR2 の digest を計算する。呼び出しは python3 + 引用符で囲んだスクリプトのパス + 対象パスの形とする。FR3 のすべての dispatch 箇所は、この呼び出しを参照する。

**入力**:
- 対象パス: 1 つ以上のファイルパス

**出力**:
- 各対象パスの digest（`sha256:` + 小文字 16 進 64 桁）

**ビジネスルール**:
- スクリプトは次の動作を定義する: 複数のパスを渡したときの出力と入力の対応、先頭がハイフンのパス、空白や日本語を含むパス、存在しないファイル、読み取りに失敗したときの終了コード。
- 文書は、このスクリプトの digest と input_digest の計算を別のものとして区別する。
- FR7 のスクリプトの呼び出しは workflow.yaml 由来のコマンドではないため、hooks/bash_guard.py は判定を返さず、通常の permission の流れになる。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 存在しないファイル | 対象パスにファイルが無い | 定義した出力と終了コードを返す |
| 読み取り失敗 | 対象ファイルを読み取れない | 定義した出力と終了コードを返す |

#### FR8: 旧方式で記録された artifacts の扱い

**説明**: phase-state の artifacts に旧方式（git blob id）で記録された既存の値は、旧方式での一致（記録値が、現在のファイルを旧方式で計算した値と一致すること）を確認できたものだけを新方式の digest に読み替える。確認できないものは、既存の digest 不一致の処理（{phase}.artifact-overwrite ゲート。batch では batch-policies.yaml の決定）に送る。

**ビジネスルール**:
- 旧方式の記録値は `sha256:` 接頭辞付きの git blob id の形で残っている可能性がある（create-spec-phase.md §10 が git hash-object の結果を artifacts に記録すると書いているため）。git の object format が SHA-256 のリポジトリでは git blob id も 64 桁になるので、桁数では新旧を見分けられない。判定は FR8 の一致確認で行う。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし

### 5.2 セキュリティ要件

該当なし

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR1 既存テストの維持: `python3 -m unittest discover -s tests` が全件通る。既存の文言テストが固定している次の内容を保つ。
    - spec-writer.md の digest の扱いを書いた 3 つの文言（tests/test_new_worker_agents.py）
    - spec-writer-contract.md の「### Who verifies `expect_digest`」の節と、その中の 2 文（tests/test_worker_contracts_create_spec.py）
    - create-spec-phase.md の事後比較の文言「Content hashing with `git hash-object --` is applied only to the」と、create-plan-phase.md に `git hash-object` を書かない制約（tests/test_phase_protocols.py）
    - worker-envelope.md に `expect_digest` という語を書かない制約（tests/test_worker_contract_docs.py）
    - phase-state.md の Resume decision table の各 status の行と 2 つの `dispatching` 行、Legacy feature compatibility の節（tests/test_phase_state_doc.py）
    - tests/test_check_plugin_invariants.py の既存の検査（合成した木での exit 0、run_all_checks での iter_repo_files の 1 回だけの走査、実リポジトリでの exit 0）
- NFR2 SSOT の維持: 手順や定義の本文は所有ドキュメント 1 か所に置き、ほかのドキュメントは path で参照する。言い換えて書き直さない。
- NFR3 標準ライブラリだけ: テストコードは Python 標準ライブラリの unittest だけを使い、サードパーティのパッケージを import しない。FR7 のスクリプトも標準ライブラリだけを使い、sha256sum などの外部コマンドを呼ばない。

### 5.5 互換性要件

- 旧方式（git blob id）で記録された phase-state の artifacts は FR8 に従って扱う。

## 6. UI/UX要件

該当なし（design ステップ: skipped。UI を持たない変更（プラグインの文書・スクリプト・テスト））

## 7. データ要件

### 7.1 データモデル概要

phase-state/design.yaml を既存の phase-state のスキーマで新設する（FR5）。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| phase-state | phase | 文字列 | ○ | 値に `design` を加える |
| phase-state | artifacts[].sha256 | 文字列 | ○ | ファイルの生バイト列の sha256（`sha256:` + 小文字 16 進 64 桁） |

### 7.3 データ保持期間

該当なし

## 8. 外部連携

### 8.1 連携システム

該当なし

### 8.2 API仕様要件

該当なし

## 9. 制約条件

### 9.1 技術的制約

- FR7 のスクリプトとテストコードは Python 標準ライブラリだけを使う（NFR3）。
- scope verification の事後比較で使う git blob id、workflow_blob、base_workflow_blob、input_digest の定義は変えない（FR2）。
- 手順の本文は所有ドキュメント 1 か所に置く（NFR2）。

### 9.2 ビジネス上の制約

- 計画パッチの権限、再計画の認可、rework での action の決め方は変えない（FR3）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/worker-digest-ownership/**`
- `test-docs/worker-digest-ownership/**`

`feature-docs/worker-digest-ownership/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/worker-digest-ownership/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/worker-digest-ownership/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/worker-digest-ownership/` ディレクトリを生成しないが、宣言された `test-docs/worker-digest-ownership/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 旧方式の記録値は桁数では新旧を見分けられない | 高 | FR8 の一致確認で判定する |
| tests/ の新しいテストの文字列が agent_dispatch_parity の検査に拾われる | 中 | FR6 のビジネスルールに書いた形の文字列を tests/ の新しいテストに入れない |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1（FR1, FR3）: create-spec 再入で spec-writer を replace_own 付きで dispatch したとき、spec-writer は digest を計算できないことを理由に blocked を返さず、REQUIREMENTS.md と SPEC.md を書いて、written_artifacts を path だけで返す。
- [ ] AC2（FR1, FR4, FR5）: 既存の成果物（extend_only の tokens.yaml、regenerate の tokens.html、replace_own の mockup）がある状態で designer を dispatch したとき、designer は digest を理由に blocked を返さない。dispatch 前の照合、戻った後の scope verification と artifact validation、phase-state/design.yaml への digest 記録はオーケストレーターが行う。
- [ ] AC3（FR3, FR4）: どの dispatch 箇所でも、expect_digest が現在の digest と食い違う target があるとき、オーケストレーターは worker を dispatch しない。
- [ ] AC4（FR2, FR7）: expect_digest、phase-state の artifacts[].sha256、layer 5 の digest は、どれも同じ定義（生バイト列の sha256、`sha256:` + 小文字 16 進 64 桁）で、FR7 のスクリプトで計算される、と文書に書かれている。create-spec-phase.md は、この 2 つの用途に git hash-object を指定していない。scope verification の git blob id、workflow_blob、base_workflow_blob、input_digest の定義は変わっていない。
- [ ] AC5（FR6, NFR1, NFR3）: check-plugin-invariants.py の新しい検査が実リポジトリで通り、否定例（FR1〜FR5 のどれかが崩れた合成の木、対象 worker が 0 件の木）で失敗する。validator を実行するテストと FR7 のスクリプトのテストがあり、`python3 -m unittest discover -s tests` で全件通る。
- [ ] AC6（FR7）: FR7 のスクリプトは、既知の内容のファイルに対して既知の digest を出す。複数パスの出力と入力の対応、先頭がハイフンのパス、空白や日本語を含むパス、存在しないファイル、読み取り失敗のそれぞれで、定義した出力と終了コードを返す。
- [ ] AC7（FR8）: 旧方式で記録された artifacts を持つ feature を再開したとき、旧方式での一致を確認できた target は一致として扱われ、確認できない target は {phase}.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送られる、と文書に書かれている。
- [ ] AC8（FR4, FR5）: phase-state/design.yaml が無い既存 feature で design ステップを実行したときの扱いが、develop SKILL.md の「design ステップ分岐」に書かれている。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（FR1, FR6）: check-plugin-invariants.py の新しい検査が、worker-envelope.md の Applicability 表と agents/*.md の frontmatter の tools から「envelope の対象で、書き込みを持ち、Bash を持たない worker」を導き、その各 agent prompt と contract が worker 側の digest 計算や expect_digest 照合を指示しておらず、digest を計算できないことを理由に blocked を返さない旨と written_artifacts は path だけでよい旨を（本文または参照で）持つことを調べる。実リポジトリで通り、どれかの worker の記述を崩した合成の木で失敗することを確かめる。
- [ ] TS2（FR3, FR4, FR7）: write_policy を持つ worker の各 dispatch 箇所（create-spec-phase.md、develop SKILL.md の「design ステップ分岐」、create-plan-phase.md、rework-task-synthesis.md §10 の dispatch 入力）が、dispatch 前の expect_digest 照合と layer 5 の digest 記録を、本文に書くか所有ドキュメントを参照していること、計算手段として FR7 のスクリプトに行き着くことを、新しい検査で調べる。create-plan-phase.md に `git hash-object` が現れないことも確かめる。どれかの箇所から参照を外した合成の木で失敗することを確かめる。
- [ ] TS3（FR2, FR8）: create-spec-phase.md の expect_digest 照合（Pre-dispatch snapshot 表の行）と §10 の Artifact digests が `git hash-object` を指定しておらず、FR2 の定義（またはその所有ドキュメント）を参照していることを調べる。事後比較の blob id の文言が残っていること、旧方式の記録の扱い（FR8）が所有ドキュメントに書かれていることも確かめる。
- [ ] TS4（FR5）: `validate-worker-output.py --kind phase-state` を実行し、phase: design の phase-state を受け付け、未知の phase を拒否することを確かめる。worker-envelope.md と phase-state.md の phase の値に design が含まれることも調べる。
- [ ] TS5（FR1, FR6）: `validate-worker-output.py --kind worker-result` を実行し、spec-writer / designer / implementation-planner / rework-planner の completed 結果のうち、written_artifacts の各エントリが sha256: null のものと sha256 を省略したものが、どちらも受け付けられることを確かめる。
- [ ] TS6（FR7）: FR7 のスクリプトを実行し、既知の内容（空のファイルなど）に対して既知の sha256 を `sha256:` + 小文字 16 進 64 桁で出すこと、複数パスで出力と入力が対応すること、先頭がハイフンのパスと、空白や日本語を含むパスを正しく扱うことを確かめる。
- [ ] TS7（FR7）: FR7 のスクリプトに存在しないファイルと読み取れないファイルを渡し、定義した終了コードと出力になることを確かめる。
- [ ] TS8（FR6）: 対象 worker が 0 件になる合成の木（Applicability 表が無い、または該当する agent が無い）で、新しい検査が通らずに失敗することを確かめる。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| digest | ファイルの生バイト列の sha256 を `sha256:` + 小文字 16 進 64 桁で表したもの（FR2）。expect_digest、phase-state の artifacts[].sha256、layer 5 の digest に使う |
| git blob id | `git hash-object` の結果。scope verification の事後比較で使う。digest とは別のもの |
| input_digest | Rule R1 の正規化 JSON の sha256。FR7 のスクリプトの digest とは別のもの |
| 旧方式 | phase-state の artifacts に git blob id で記録する方式 |
| 対象 worker | envelope の対象で、書き込みを持ち、tools に Bash を持たない worker（spec-writer / designer / implementation-planner / rework-planner） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: main 7468e0b7 の worker 側の修正（spec-writer.md、spec-writer-contract.md の「Who verifies `expect_digest`」、worker-envelope.md の「`written_artifacts` reporting」、designer.md の Output）は維持する。この feature では、残っているオーケストレーター側の不整合とテストを扱う。
- [x] A2: digest の定義は回答 requirement.digest-definition のとおり、生バイト列の sha256（`sha256:` + 小文字 16 進 64 桁）とする。dispatch 前の照合と layer 5 は同じ計算（FR7）を使う。
- [x] A3: design phase の digest は、新しく作る phase-state/design.yaml の artifacts に、既存と同じスキーマで記録する（回答 requirement.design-phase-state）。
- [x] A4: create-plan（implementation-planner）と rework（rework-planner）も対象に含める。変更は計算手段と照合・記録の接続に限る（回答 requirement.dispatch-scope）。
- [x] A5: agent の実行時の挙動は unit test から直接は実行しない。再発の検出は、check-plugin-invariants.py の不変条件の検査、validator を実行するテスト、FR7 のスクリプトのテストで行う（回答 requirement.regression-test-form）。
- [x] A6: phase-state/design.yaml が無い既存 feature で既存の design 成果物があるとき、その成果物は FR8 の「一致を確認できない記録」と同じく扱い、design.artifact-overwrite ゲート（batch では batch-policies.yaml の決定）に送る。phase-state.md の Legacy feature compatibility 表で、phase-state が無いときに既存文書を digest 不一致として扱う規則と同じ扱いになる。
- [x] A7: FR7 のスクリプトのファイル名、出力の形式、終了コードの具体的な値は SPEC で決める。回答は、定義すべき項目だけを決めている。

### 14.2 未確認・保留事項

- [ ] FR7 のスクリプトのファイル名、出力の形式、終了コードの具体的な値（A7）。requirements_analysis には具体的な値が無い。

## 15. 参考資料

- `em-workflow/references/contracts/worker-envelope.md`
- `em-workflow/references/contracts/spec-writer-contract.md`
- `em-workflow/references/phases/create-spec-phase.md`
- `em-workflow/references/phases/create-plan-phase.md`
- `em-workflow/references/phase-state.md`
- `em-workflow/skills/develop/SKILL.md`
- rework-task-synthesis.md §10

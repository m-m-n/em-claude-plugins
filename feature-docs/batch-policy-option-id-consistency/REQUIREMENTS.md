---
title: "batch-policy-option-id-consistency"
created_date: 2026-08-17
status: draft
---

# batch-policy-option-id-consistency - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/batch-policies.yaml` の `action: select` エントリは、そのゲートが実際に提示する option_id を名指しする前提で書かれている。しかし policy が名指しする option_id を、そのゲートの発行元（issuing site）が提示していないケースが存在する。この不一致があると、バッチ実行はブロッキングでない選好ゲートで `question-resolution.md` step 6 の protocol-error abort に落ちる。

具体的に確認されている不一致は 2 件ある。

- `create-spec.design-step`: policy の option_id `decide_autonomously` を requirements-analyst の発行元が提示していない。
- `create-spec.design-system`: policy の option_id `top_candidate_or_none` を発行元である `create-spec-phase.md` step 11a が提示しておらず、そこには `project_native` / `em_workflow` / `none` の語彙しか記載がない。

さらに、`derive_from_task_description`、`top_candidate_or_none`、`compatible_alternative`、`merge`、`assume`、`create-spec.stalled` の `record_tbd` は、現状 `batch-policies.yaml` の外に一切現れない option_id である。

### 1.2 目的

- `batch-policies.yaml` のすべての `action: select` エントリを、そのゲートが実際に提示する option_id に対して解決可能にし、バッチ実行が非ブロッキングな選好ゲートで protocol-error abort に落ちないようにする。
- 該当するすべてのゲートについて、policy が名指しする option_id を含む option_id 群を提示する発行元を特定し、`batch-policies.yaml` を対応関係の正（authoritative）の側とする。
- その対応関係を機械的に検査可能にし、同じドリフトが黙って再発しないようにする。機械検査できないゲートについては、検査できない理由と代わりの保証をドキュメント化する。

### 1.3 スコープ

対象は YAML の policy ファイル、Markdown の reference / contract / protocol ドキュメント、Python の unittest スイート、および JSON マニフェスト 2 箇所の version フィールドに限られる。

**対象外（凍結ファイル）**:

- `em-workflow/references/workflow-patch.md`
- `em-workflow/scripts/validate-worker-output.py`
- `tests/test_validate_worker_output.py:1269` および `valid-design-step-correct-binding` フィクスチャ（変更前とバイト一致であること）

## 2. ビジネス要件

### 2.1 ビジネス目標

1. `batch-policies.yaml` のすべての `action: select` エントリが、そのゲートが実際に提示する option_id に対して解決できること。バッチ実行が非ブロッキングな選好ゲートで `question-resolution.md` step 6 の protocol-error abort に到達しないこと。
2. 該当する各ゲートについて、policy が名指しする option_id を提示する発行元が特定されていること。`batch-policies.yaml` がその対応関係の正の側であること。
3. その対応関係が機械検査されること。あるいは、検査できないゲートについては、検査できない理由とその代わりの保証が記録されていること。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| バッチ実行（`--batch`） | `batch-policies.yaml` を参照して select ゲートを無人で解決する実行主体 |
| em-workflow プラグインのメンテナ | policy ファイルとゲート発行元を編集し、両者の対応を保つ担当 |

### 2.3 期待される効果

- 非ブロッキングな選好ゲートに起因するバッチ実行の中断がなくなる。
- policy とゲート発行元の間のドリフトが、テストスイートによって検出される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | バッチ実行が select ゲートを policy に従って解決する | バッチ実行 | 高 |
| UC02 | メンテナが policy と発行元の対応をテストで検証する | メンテナ | 高 |

### 3.2 ユースケース詳細

#### UC01: バッチ実行が select ゲートを policy に従って解決する

**アクター**: バッチ実行（`--batch`）

**事前条件**:

- 対象ゲートが `batch-policies.yaml` に `action: select` + `option_id` で登録されている

**基本フロー**:

1. ゲートが提示され、そのゲートの発行元が定義する option 語彙が確定する
2. バッチ実行が `batch-policies.yaml` の該当エントリを引く
3. policy の `option_id` が、そのゲートの提示する option_id に含まれるため解決に成功する
4. 実行が継続する

**代替フロー**:

- policy の `option_id` が提示された option_id に含まれない場合、`question-resolution.md` step 6 の protocol-error abort になる（本要件が解消する状態）

**事後条件**:

- 非ブロッキングな選好ゲートで実行が中断しない

#### UC02: メンテナが policy と発行元の対応をテストで検証する

**アクター**: em-workflow プラグインのメンテナ

**事前条件**:

- リポジトリルートの unittest スイートが実行可能である

**基本フロー**:

1. メンテナが `python3 -m unittest discover -s tests` を実行する
2. チェックが各 `action: select` エントリの発行元を解決し、提示 option_id を読み取る
3. policy の `option_id` が提示 option_id に含まれることを検査する

**代替フロー**:

- いずれかの対応が壊れている場合、テストが失敗する
- 機械検査できないゲートについては、記録された理由と代替保証の存在を検査する

**事後条件**:

- policy と発行元のドリフトが黙って通過しない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | create-spec.design-step の対応解決 | policy の `decide_autonomously` を発行元が提示する | 高 |
| FR2 | select ゲートごとの発行元特定 | 11 エントリすべてに発行元と成立した対応を持たせる | 高 |
| FR3 | create-spec.design-system の潜在不一致 | `top_candidate_or_none` を step 11a に追加宣言する | 高 |
| FR4 | policy にしか存在しない option 語彙 | 該当 option_id を発行元に宣言・文書化する | 高 |
| FR5 | 機械的な整合チェック | 対応が壊れたときに落ちるテストを追加する | 高 |
| FR6 | 検査不能ゲートの文書化フォールバック | 理由と代替保証をプラグイン文書に記録する | 高 |
| FR7 | 既存の構造テストの同時更新 | `tests/test_batch_policies.py` 等を同一変更で更新する | 高 |
| FR8 | プラグイン version の bump | plugin.json と marketplace.json を同値にする | 高 |

### 4.2 機能詳細

#### FR1: create-spec.design-step resolves against the policy's option_id

**説明**: `batch-policies.yaml` の `create-spec.design-step` エントリは option_id `decide_autonomously` を変更せずに保つ。requirements-analyst の発行元（`em-workflow/references/contracts/analyst-contract.md` と requirements-analyst のエージェントプロンプト）が、`create-spec.design-step` ゲートの option として `decide_autonomously` を宣言・提示し、その option の意味論を発行元に記載する。`tests/test_validate_worker_output.py:1269` と `valid-design-step-correct-binding` フィクスチャは変更しない。

**ビジネスルール**:

- policy 側の option_id は書き換えない。発行元を policy に合わせる。

#### FR2: Identified issuing site per select gate

**説明**: `batch-policies.yaml` の `action: select` + `option_id` を持つ 11 エントリそれぞれについて、その option 語彙を発行するサイトを特定し、そのサイトの提示 option_id が policy の名指しする option_id を含むようにする。

対象ゲート:

| # | gate_id |
|---|---------|
| 1 | create-spec.feature-identity |
| 2 | create-spec.design-step |
| 3 | create-spec.design-system |
| 4 | design-system.reclassify |
| 5-7 | `*.artifact-overwrite` 3 ゲート |
| 8 | create-spec.stalled |
| 9 | create-plan.tbd-resolution |
| 10 | create-plan.license-conflict |
| 11 | create-plan.existing-files |

#### FR3: create-spec.design-system's second latent mismatch

**説明**: `create-spec.design-system` の policy option_id `top_candidate_or_none` は記載どおりに保つ。発行元である `create-spec-phase.md` step 11a（現状 `project_native` / `em_workflow` / `none` の語彙のみを記載）を拡張し、`top_candidate_or_none` を意味論つきで宣言・提示する。

#### FR4: Option vocabularies that exist only in the policy file

**説明**: 現状 `batch-policies.yaml` の外に現れない option_id、すなわち `derive_from_task_description`、`top_candidate_or_none`、`compatible_alternative`、`merge`、`assume`、および `create-spec.stalled` の `record_tbd` について、それぞれのゲートの発行元に、宣言され文書化された語彙エントリを追加する。

**ビジネスルール**:

- これらの option_id を、発行元の既存語彙に合わせて改名してはならない。

#### FR5: Mechanical consistency check

**説明**: リポジトリルートの unittest スイートに、`batch-policies.yaml` の `action: select` エントリが、そのゲートの発行元が提示していない option_id を名指ししているときに失敗するチェックを追加する。対象は `create-spec.design-step` 単独ではなく、該当する全エントリ。

#### FR6: Documented fallback for uncheckable gates

**説明**: 対応関係を機械的に検査できない select ゲートがある場合、その理由と代償となる保証を、暗黙にせずプラグイン自身のドキュメントに記録する。

#### FR7: Existing structural tests updated in the same change

**説明**: policy ファイルの構造と gate-ID 集合を固定している `tests/test_batch_policies.py`、および変更対象の値をアサートしている他のテストを、同一変更内で更新し、新しく文書化された語彙をスイートが反映するようにする。

#### FR8: Plugin version bump

**説明**: `em-workflow/.claude-plugin/plugin.json` の `version` を 0.1.41 から bump し、リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリを同じ値にする。

## 5. 非機能要件

本変更の対象は policy ファイル・ドキュメント・テスト・マニフェストであるため、テンプレート標準項目のうち 5.1 パフォーマンス要件 / 5.2 セキュリティ要件 / 5.3 可用性要件 / 5.5 互換性要件に該当する要件は requirements-analyst から示されていない。確定した非機能要件は以下のとおり。

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | Frozen files | `em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` を本変更で変更しない |
| NFR2 | No third-party imports in test code | 新しいチェックはサードパーティパッケージ（PyYAML を含む）を import しない。`tests/test_batch_policies.py` に既にある制限サブセット YAML パーサを再利用または再実装する（`test/README.md` のテストスコープの外部依存禁止ルールに従う） |
| NFR3 | Whole suite stays green | `python3 -m unittest discover -s tests` が、変更したテストモジュールだけでなくスイート全体で成功する |
| NFR4 | SSOT preserved | `batch-policies.yaml` が gate_id を持つゲートの単一の正であり続ける。第 2 の policy テーブルを導入せず、`batch-mode.md` の Non-packet gates テーブルへゲートを移動しない |
| NFR5 | Direction of reconciliation is uniform | 本変更のすべての整合作業は発行元を policy ファイルに寄せる方向で行う。ドリフトした worker / protocol の語彙に合わせて `batch-policies.yaml` の option_id を書き換えない |

### 5.4 保守性要件

- NFR4（SSOT の維持）と NFR5（整合方向の統一）が保守性要件に相当する。

## 6. UI/UX要件

該当なし。本変更にはユーザーインターフェースも視覚的な表出面も存在せず、デザインステップは skipped と判定されている。

## 7. データ要件

該当なし。永続化されるデータモデルを導入しない。

## 8. 外部連携

該当なし。外部システム連携を導入しない。

## 9. 制約条件

### 9.1 技術的制約

- `em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` は変更しない（NFR1）。
- `tests/test_validate_worker_output.py:1269` と `valid-design-step-correct-binding` フィクスチャは変更前とバイト一致であること（FR1）。
- テストコードでサードパーティパッケージを import しない（NFR2）。
- `batch-policies.yaml` を単一の正として維持し、第 2 の policy テーブルを作らない（NFR4）。
- policy 側の option_id を書き換えず、発行元側を policy に合わせる（NFR5、FR4）。

### 9.2 ビジネス上の制約

- リポジトリルートに LICENSE ファイルがないため、本フィーチャーは SPDX 上の義務を継承しない。

### 9.3 スケジュール制約

- requirements-analyst から示された制約はない。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:

- `em-workflow/references/batch-policies.yaml`
- `em-workflow/references/contracts/analyst-contract.md`
- `em-workflow/references/create-spec-phase.md`
- `em-workflow/references/**`（FR2 が特定する残りの select ゲート発行元：contract / phase protocol ドキュメント、および FR6 の文書化先）
- `em-workflow/agents/**`（ゲートの option 語彙を発行するエージェントプロンプト）
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/**`（FR5 の新規チェックモジュールと FR7 が更新する `tests/test_batch_policies.py`）

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。
- この宣言はスーパーセットの主張であり、実際の変更集合は宣言に含まれる必要がある。実際には生成されないパスが宣言されていても違反にはならない。

**宣言に含まれるが変更してはならないパス**: `tests/**` は宣言に含まれるが、`tests/test_validate_worker_output.py:1269` と `valid-design-step-correct-binding` フィクスチャは変更前とバイト一致であること（FR1）。同様に `em-workflow/references/**` は宣言に含まれるが、`em-workflow/references/workflow-patch.md` は変更しない（NFR1）。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 一部の select ゲートは発行元の option 語彙を機械的に解析できない可能性がある | 中 | FR6 に従い、検査できない理由と代償となる保証をプラグイン文書に記録する |
| `record_tbd` が `on_unanswered` フィールドにも現れるため、対応検査が誤って成立と判定しうる | 中 | 検査は当該ゲートの提示 option のみを対象とし、`on_unanswered` 単独の出現を対応成立と見なさない |
| 制限サブセット YAML パーサが、選択した語彙表現を解析できない可能性がある | 中 | 選択した表現を用いたフィクスチャが例外なく解析できることをテストで固定する |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| policy と発行元のドリフトが再発し、バッチ実行が非ブロッキングゲートで中断する | 中 | 高 | FR5 の機械チェックで検出する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] `batch-policies.yaml` の `create-spec.design-step` policy を適用すると、requirements-analyst が実際に提示する option が選択される（analyst の発行元が `decide_autonomously` を宣言しているため）。policy ファイルの option_id は変更されていない。
- [ ] `create-spec.design-system` の `top_candidate_or_none` が、`project_native` / `em_workflow` / `none` の語彙と並んで発行元に宣言されており、design-system ゲートがバッチモードで解決する。
- [ ] `action: select` + `option_id` を持つ 11 エントリすべてに、特定された発行元と成立した対応がある。
- [ ] `tests/` 配下のテストが、それらの対応のいずれかが壊れたときに失敗する。機械検査できないゲートについては、理由と代替保証がプラグインのドキュメントに記載されている。
- [ ] `tests/test_validate_worker_output.py:1269` と `valid-design-step-correct-binding` フィクスチャが変更前とバイト一致である。
- [ ] `em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` が変更されていない。
- [ ] `python3 -m unittest discover -s tests` が成功する。
- [ ] em-workflow の version が `em-workflow/.claude-plugin/plugin.json` で bump され、`.claude-plugin/marketplace.json` に同じ値が設定されている。

### 11.2 KPI

requirements-analyst から示された KPI はない。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] カバレッジ: `action: select` の全エントリが `option_id` を持つこと、およびその gate_id 集合が明示的に固定された 11 件の期待集合と一致することを検査する。新規追加された select ゲートは、意図的に登録されるまでテストを失敗させる。
- [ ] 対応関係: 各 select ゲートについて発行元（パスと当該ゲートの option 語彙を宣言するセクション）を解決し、提示 option_id を解析して policy の option_id が含まれることを検査する。一時コピー上で policy の option_id を意図的に変異させるとアサーションが失敗する。
- [ ] design-step 回帰: `create-spec.design-step` の policy option_id がちょうど `decide_autonomously` であり、`analyst-contract.md` の design-step option 語彙が `decide_autonomously` を含むことを検査する。
- [ ] design-system 回帰: `create-spec.design-system` の policy option_id がちょうど `top_candidate_or_none` であり、`create-spec-phase.md` step 11a の語彙が `project_native` / `em_workflow` / `none` に加えてそれを含むことを検査する。
- [ ] `on_unanswered` の区別: `create-spec.stalled` の option_id `record_tbd` が当該ゲートの提示 option のみに対して検証され、`on_unanswered` フィールド中の `record_tbd` の出現だけでは対応検査を満たさないことを検査する。
- [ ] 不在系: `rework.spec-change` が `batch-policies.yaml` に存在しないままであり、カバレッジ検査がそれを欠落エントリとして報告しないことを検査する。
- [ ] 非 select 系: `create-spec.requirement-clarification` と `create-spec.command-approval` が `option_id` を持たず、対応検査の対象外であることを検査する。
- [ ] 検査不能ゲートの文書化: 機械検査できないゲートについて、記録されたドキュメントパスに理由と代償となる保証が存在することを検査する。文書化されていない適用除外は失敗する。
- [ ] 凍結ファイル: `em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` が本変更で変更されていないことを検査する。
- [ ] version 同期: `em-workflow/.claude-plugin/plugin.json` の version が `.claude-plugin/marketplace.json` の em-workflow エントリの version と等しく、0.1.41 より厳密に大きいことを検査する。
- [ ] パーサ堅牢性: チェックが用いる制限サブセット YAML パーサが、実際の表現の option 語彙を扱えること。選択した表現を用いたフィクスチャが例外を送出せず解析できることを検査する。
- [ ] スイート: `python3 -m unittest discover -s tests` が failure 0・error 0 で完了することを検査する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 発行元（issuing site） | あるゲートの option 語彙を発行するサイト。worker contract、エージェントプロンプト、または phase protocol のいずれか |
| select ゲート | `batch-policies.yaml` で `action: select` と `option_id` を持つエントリに対応するゲート |
| 凍結ファイル | 本変更で変更してはならないファイル |

## 14. 確認事項

### 14.1 確認済み事項

- [x] ライセンス: リポジトリルートに LICENSE ファイルがないため、本フィーチャーは SPDX 上の義務を継承しない。ライセンス検出結果は `none`（confidence: high）。
- [x] ビルド・整形・E2E: リポジトリにビルドステップ、設定されたフォーマッタ、E2E インフラのいずれも存在しない。対応するコマンドフィールドは未検出値ではなく意図的な空文字列である。

### 14.2 未確認・保留事項

以下は requirements-analyst が記録した前提であり、ユーザーによる確認を得ていない。

- [ ] 整合方向の前提（バッチポリシー `record_as_assumption: true` により記録）: 整合方向は `pin_worker_vocabulary` である。すなわち `em-workflow/references/batch-policies.yaml` がすべての `action: select` ゲートの option_id について正であり、各ゲートの発行元（worker contract、エージェントプロンプト、または phase protocol）が policy の名指しする option_id を宣言・提示しなければならない。worker のドリフトした語彙に合わせて policy の option_id を書き換えることはしない。これはバッチ実行中に gate_id `create-spec.requirement-clarification`（action: codex_consultation）のもとで Codex 相談により解決されたものであり、ユーザーによる決定ではない。ユーザーはこれを確認していない。
- [ ] 上記前提の帰結（同様にユーザー未確認）: いずれかの policy エントリを改名するのではなく、requirements-analyst が `create-spec.design-step` の option 語彙に `decide_autonomously` を獲得し、`create-spec-phase.md` step 11a が `create-spec.design-system` の語彙に `top_candidate_or_none` を獲得する。
- [ ] 件数の前提: `action: select` + `option_id` エントリが 11 件という数は、base revision bb33560 時点の `batch-policies.yaml` を反映したものである。実装前に当該エントリが増減した場合、FR2 の列挙はここに記した数値ではなくファイルに従う。

## 15. 参考資料

- `em-workflow/references/batch-policies.yaml`: バッチポリシーの単一の正
- `em-workflow/references/question-resolution.md`: step 6 の protocol-error abort
- `em-workflow/references/contracts/analyst-contract.md`: create-spec.design-step ゲートの発行元
- `em-workflow/references/create-spec-phase.md`: step 11a、create-spec.design-system ゲートの発行元
- `em-workflow/references/batch-mode.md`: Non-packet gates テーブル
- `tests/test_batch_policies.py`: policy ファイルの構造と gate-ID 集合を固定する既存テスト
- `test/README.md`: テストスコープの外部依存禁止ルール

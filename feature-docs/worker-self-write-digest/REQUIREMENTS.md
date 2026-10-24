---
title: "worker-self-write-digest"
created_date: 2026-10-24
status: draft
---

# worker-self-write-digest - 要件定義書

## 1. 概要

### 1.1 背景
2.1 のビジネス目標を参照。

### 1.2 目的
- worker の帰着時に行う Rule R1 の `input_digest` 再確認で、worker 自身が `write_policy` に基づいて正当に書き込んだパスを、stale な入力として扱わない。
- dispatch 期間中に、worker に許可された自己書き込み以外で起きた実際の変更は、引き続き stale として検出する。

### 1.3 スコープ
- 対象: `references/contracts/worker-envelope.md` Rule R1、designer / implementation-planner / rework-planner の各契約、`workflow-patch.md` の適用規則 1、`scripts/validate-worker-output.py --dry-run-apply`、create-plan の resume 比較、phase-state への永続化、`em-workflow/scripts/` 配下のスクリプト関数、各 dispatch 箇所のオーケストレーター手順、unittest。
- 対象外: TASK.md（planner の `digest_inputs` に含まれないため。追加は別の変更とする）。
- デザインステップ: スキップ（UI は無い。変更はプロトコルの Markdown、Python スクリプト、テストに限られる）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- worker の帰着時に行う Rule R1 の `input_digest` 再確認で、worker 自身が `write_policy` に基づいて正当に書き込んだパスを、stale な入力として扱わない。
- dispatch 期間中に、worker に許可された自己書き込み以外で起きた実際の変更は、引き続き stale として検出する。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | `input_digest` の再計算・比較、自己書き込み集合の特定、phase-state への永続化を行う主体 |

### 2.3 期待される効果
- designer の `extend_only`、implementation-planner の再計画、rework-planner の自己書き込みが stale と判定されない。
- 自己書き込み以外の変更は stale と判定される。

## 3. ユースケース

ユースケースは 11.1 の受け入れ基準（AC1〜AC10）で表す。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | 自己書き込みパスへの dispatch 時ダイジェストの代入 | confirmed |
| FR2 | 自己書き込み集合の特定 | confirmed |
| FR3 | action ごとの許可 | confirmed |
| FR4 | 自己書き込み以外の変更は stale のまま | confirmed |
| FR5 | パッチ適用規則 1 | confirmed |
| FR6 | resume 時の比較 | confirmed |
| FR7 | 永続化 | confirmed |
| FR8 | 順序 | confirmed |
| FR9 | envelope 共通のルール | confirmed |
| FR10 | スクリプト関数 | confirmed |
| FR11 | 回帰テスト | confirmed |

### 4.2 機能詳細

#### FR1: 自己書き込みパスへの dispatch 時ダイジェストの代入
オーケストレーターは、worker の帰着時に `input_digest` を再計算するとき、自己書き込み集合に含まれるすべてのパスについて、dispatch 時の `digest_inputs` の値を使う。dispatch 時に存在しなかったパスは、キーを欠いたままにする。それ以外の `digest_inputs` のパス、および `value_inputs` / `answers_digest` / `write_policy_digest` / `workflow_blob` は、従来どおり現在の状態から再計算する。ダイジェスト全体での比較は維持する。

#### FR2: 自己書き込み集合の特定
パスが自己書き込み集合に入るのは、次の両方を満たすときに限る。
- (a) オーケストレーターが観測した dispatch 期間の変更集合（layer 4 の dispatch 前後比較）に含まれる。
- (b) その変更が、そのパスを覆う `write_policy` エントリの action で許可されている。

worker の `written_artifacts` だけでは所属を決めない。パスと `write_policy` の単純な共通部分でも決めない。

#### FR3: action ごとの許可
- `allowed_write_roots` は、dispatch 時に存在しなかったファイルの作成だけを許可し、既存ファイルの変更は許可しない。`targets` に列挙されていない、`allowed_write_roots` 配下の既存ファイルが変更された場合、それは自己書き込みではない。
- `preserve` のターゲットは自己書き込みにならない。
- `regenerate` のターゲットは、同じ dispatch でその `source` も自己書き込みである場合に限り自己書き込みになる。
- `create` のターゲットは、dispatch 時にそのパスが存在しなかった場合に限り自己書き込みになる。

#### FR4: 自己書き込み以外の変更は stale のまま
自己書き込み集合の外にある `digest_inputs` の変更、および `value_inputs` / `answers_digest` / `write_policy_digest` / `workflow_blob` のいずれかの変更は、引き続き不一致を生じ、結果は stale として扱われる。

#### FR5: パッチ適用規則 1
`workflow-patch.md` の適用規則 1 と `validate-worker-output.py --dry-run-apply` で使う `digest_source` は、FR1 と同じ自己書き込みの代入を行って構築する。これにより、planner と rework-planner の正当な自己書き込みでパッチが拒否されない。

#### FR6: resume 時の比較
create-plan の resume 時に、再計算した `input_digest` を phase-state の `last_input_digest` と比較する処理にも、同じ自己書き込みの代入を適用する。resume 時の記録済み成果物ダイジェストとの比較は維持し、自己書き込みした成果物がダイジェスト記録後に変更された場合は引き続き検出する。

#### FR7: 永続化
オーケストレーターは、dispatch 時のパスごとの `digest_inputs` マップと、帰着後にはその実行の自己書き込み集合を phase-state に永続化する。これにより、中断後も FR1・FR5・FR6 の比較を再現できる。スキーマ上の配置は `references/phase-state.md` に照らして決める。

#### FR8: 順序
帰着時の再計算は、dispatch 期間の変更集合を観測した後（layer 4 のスコープ比較の後）に行う。FR2 がその結果に依存するため。

#### FR9: envelope 共通のルール
このルールは `worker-envelope.md` Rule R1 の「Recomputation and comparison timing」に、条件付きのルールとして 1 回だけ記述する。`digest_inputs` が `write_policy` と重なるすべての envelope worker に適用する。`designer-contract.md`、`planner-contract.md`、`rework-planner-contract.md` はこれを引用し、重なるパスを列挙する。
- designer: `design-system/tokens.yaml` と `tokens.html`
- implementation-planner: `IMPLEMENTATION.md`、`VERIFICATION.md`、`THREAT-MODEL.md`、`tasks/`
- rework-planner: `IMPLEMENTATION.md`、`VERIFICATION.md`、`tasks/`

#### FR10: スクリプト関数
`em-workflow/scripts/` 配下のスクリプトに関数を置く。入力は、パスごとのマップを持つ dispatch 時の `digest_source`、現在のパスごとのダイジェスト、観測した変更集合、`write_policy`。出力は、自己書き込み集合と、代入済みの帰着時 `digest_source`。ハッシュ計算はオーケストレーター側に残す（`references/artifact-digest.md` の Calculation、R1 の正規化）。各 dispatch 箇所のオーケストレーター手順がこの関数を呼ぶ。
- `skills/develop/SKILL.md` のデザインステップの分岐
- `create-plan-phase.md`
- `rework-task-synthesis.md` の 10 節

#### FR11: 回帰テスト
unittest で、FR10 の関数を通して次を再現する。
- designer の `extend_only`、implementation-planner の再計画、rework-planner の自己書き込みが stale にならない。
- 自己書き込み以外の変更が stale になる。

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | R1 の正規化手順と、`digest_source` の構造キー（`worker`、`mode`、`workflow_blob`、`digest_inputs`、`value_inputs`、`answers_digest`、`write_policy_digest`）は変更しない。 |
| NFR2 | `check-plugin-invariants.py` の `worker_digest_stance` が通る。`worker-envelope.md` の「`written_artifacts` reporting」節は「The worker does not compute digests」を保持し、Bash を持たない書き込み worker が引用する契約には、worker に向けたダイジェスト計算の指示を含めない。新しいルールはオーケストレーターを主語として記述する。 |
| NFR3 | `check-plugin-invariants.py` の `dispatch_digest_wiring` が通る。`artifact-digest.md` の「Dispatch sites」に登録された各 dispatch 箇所の節は、引き続き `references/artifact-digest.md` を Covers の名前とともに引用し、`git hash-object` を含まない。 |
| NFR4 | `python3 -m unittest discover -s tests` がすべて通る。 |
| NFR5 | プラグインの version は変更しない。 |
| NFR6 | 各ルールは 1 回だけ記述し、他の箇所からはパスと節で引用する。契約は R1 を再掲しない。 |

## 6. UI/UX要件

該当なし。

## 7. データ要件

phase-state に、dispatch 時のパスごとの `digest_inputs` マップと、帰着後の自己書き込み集合を永続化する（FR7）。配置は `references/phase-state.md` に照らして決める。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- R1 の正規化手順と `digest_source` の構造キーは変更しない（NFR1）。
- ハッシュ計算はオーケストレーター側に残し、worker はダイジェストを計算しない（NFR2）。

### 9.2 ビジネス上の制約
- プラグインの version は変更しない（NFR5）。

### 9.3 スケジュール制約
該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/worker-self-write-digest/**`
- `test-docs/worker-self-write-digest/**`

`feature-docs/worker-self-write-digest/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/worker-self-write-digest/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/worker-self-write-digest/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| worker と外部の主体が、許可された同じパスを変更した場合、オーケストレーターは両者の変更を区別できない（A6） | 中 | dispatch の排他性の前提（design-input.md 5.11.3）に依拠する。この前提はロックで強制されていない。 |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR2, FR3, FR11）: 既存の `design-system/tokens.yaml` がある状態で、`extend_only` で dispatch された designer が `tokens.yaml` にキーを追加し、`tokens.html` を再生成する。帰着時の再確認は結果を stale と判定しない。
- [ ] AC2（FR1, FR3, FR5, FR11）: implementation-planner が既存の `IMPLEMENTATION.md` と `VERIFICATION.md` を `replace_own` で書き換え、`tasks/` 配下に新しいファイルを作る。R1 の再確認も `validate-worker-output.py --dry-run-apply` も stale を報告しない。
- [ ] AC3（FR1, FR5, FR11）: rework-planner が `IMPLEMENTATION.md` と `VERIFICATION.md` を `replace_own` で書き、`tasks/` 配下に新しいファイルを作る。R1 の再確認も `--dry-run-apply` も stale を報告しない。
- [ ] AC4（FR4, FR11）: dispatch 期間中に、どの `write_policy` エントリも許可していない `digest_inputs` のパス（例: `SPEC.md`）が変更された場合、引き続き stale と判定される。
- [ ] AC5（FR2）: `written_artifacts` に列挙されていても、オーケストレーターが変更を観測しなかったパスは、自己書き込み集合に入らない。
- [ ] AC6（FR3）: `allowed_write_roots` だけに覆われた既存ファイルが変更された場合、それは自己書き込み集合に入らず、結果は stale と判定されるか、スコープ検証で失敗する。変更された `preserve` ターゲット、および `source` が書かれていない `regenerate` ターゲットも同様。
- [ ] AC7（FR1, FR3）: dispatch 時に存在せず、worker が書き込んだ `create` ターゲットは、キーを欠いた状態として代入され、再計算したダイジェストが dispatch 時のダイジェストと一致する。
- [ ] AC8（FR6, FR7）: planner の自己書き込みの後に中断が起きても、resume 時に誤った `input_digest` の不一致を報告しない。自己書き込みした成果物がダイジェスト記録後に変更された場合は、記録済み成果物ダイジェストの検査で引き続き検出される。
- [ ] AC9（FR9）: `worker-envelope.md` の R1 が条件付きの自己書き込みルールを記述している。designer・planner・rework-planner の各契約がそれを引用し、重なるパスを列挙している。
- [ ] AC10（FR11, NFR4）: 新しいテストは修正前の挙動に対して失敗し、修正後はテストスイート全体が通る。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC1）: designer の `extend_only`。`tokens.yaml`（キー追加）と `tokens.html`（再生成）が変わる。再計算したダイジェストが dispatch 時のダイジェストと等しい。
- [ ] TS-2（AC2）: planner の再計画。`IMPLEMENTATION.md` / `VERIFICATION.md` の `replace_own` に加え、新しい `tasks/task000N.md` を作る。R1 と `--dry-run-apply` が通る。
- [ ] TS-3（AC3）: rework-planner。`VERIFICATION.md` の `replace_own` に加え、新しい `tasks/` 配下のファイルを作る。stale にならない。
- [ ] TS-4（AC4）: 正当な自己書き込みと並行して、期間中に `SPEC.md` が変わる。結果は stale。
- [ ] TS-5（AC5）: `written_artifacts` に `SPEC.md` が列挙されているが、観測した変更集合には含まれない。`SPEC.md` は代入されない。
- [ ] TS-6（AC6）: `allowed_write_roots` だけの下で既存の `tasks/` 配下のファイルが変更される。`preserve` ターゲットが変更される。`tokens.yaml` を変えずに `tokens.html` が変わる。いずれも自己書き込みではない。
- [ ] TS-7（AC7）: `create` ターゲットが dispatch 時に存在せず、帰着後に存在する。代入済みの `digest_source` ではそのキーが省かれる。
- [ ] TS-8（AC8）: 永続化したマップと自己書き込み集合を使い、自己書き込みの後に resume する。誤った不一致は出ない。その後に記録済み成果物を編集すると検出される。
- [ ] TS-9（AC9）: `worker-envelope.md` の R1、および 3 つの契約の引用と重なるパスの列挙に対する、ドキュメントのアサーション。
- [ ] TS-10（AC10, NFR2, NFR3, NFR4）: `python3 -m unittest discover -s tests` が、`check-plugin-invariants` の `worker_digest_stance` と `dispatch_digest_wiring` を含めて通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 自己書き込み集合 | dispatch 期間にオーケストレーターが観測した変更集合に含まれ、かつその変更が、パスを覆う `write_policy` エントリの action で許可されているパスの集合（FR2, FR3） |
| 観測した変更集合 | layer 4 の dispatch 前後比較で、オーケストレーターが観測した dispatch 期間中の変更 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1（影響: 高、可逆、mechanism.self-write、回答元: batch-codex-consultation）: 方式は、自己書き込みしたパスに dispatch 時のダイジェストを代入する。これによりダイジェスト全体での比較が保たれる。`exclude_write_targets` では再計画時のずれの検出が失われる。
- [x] A2（影響: 中、可逆、testing.regression-form、回答元: batch-codex-consultation）: 回帰の検出は、実際の呼び出し経路に組み込んだスクリプト関数と、その unittest で行う。
- [x] A3（影響: 中、可逆、scope.resume-reconcile、回答元: batch-codex-consultation）: resume 時の比較はスコープに含め、記録済み成果物ダイジェストの検査は維持する。
- [x] A4（影響: 中、可逆、scope.workers、回答元: batch-codex-consultation）: ルールは `worker-envelope.md` の R1 に、すべての envelope worker に対する条件付きのルールとして 1 回だけ記述し、3 つの契約がそれを引用する。
- [x] A5（影響: 低、可逆、scope.task-md、回答元: batch-codex-consultation）: TASK.md は planner の `digest_inputs` に含まれないため、スコープ外とする。追加は別の変更とする。
- [x] A6（影響: 中、可逆、mechanism.self-write、根拠: Codex 相談時の注記、`worker-envelope.md` の排他性の前提）: 既知の限界。worker と外部の主体が許可された同じパスを変更した場合、オーケストレーターは両者の変更を区別できない。このケースは dispatch の排他性の前提（design-input.md 5.11.3）に依拠し、この前提はロックで強制されていない。
- [x] A7（影響: 中、可逆、根拠: `tests/test_worker_contract_docs.py` と `check-plugin-invariants.py` の `digest_reproducibility` が固定している）: R1 の正規化手順と `digest_source` の構造キーは変更しない。
- [x] A8（影響: 中、可逆、根拠: `worker-envelope.md` の「`written_artifacts` reporting」、`check-plugin-invariants` の `worker_digest_stance`）: ハッシュ計算はオーケストレーター側に残し、worker はダイジェストを計算しない。
- [x] A9（影響: 低、可逆、根拠: `.claude/rules/core-plugin-version-bump.md`）: プラグインの version は変更しない。

### 14.2 未確認・保留事項
なし。

## 15. 参考資料

- `em-workflow/references/contracts/worker-envelope.md`: Rule R1、「`written_artifacts` reporting」、排他性の前提
- `em-workflow/references/artifact-digest.md`: Calculation、Dispatch sites
- `em-workflow/references/phase-state.md`
- `em-workflow/references/workflow-patch.md`: 適用規則 1

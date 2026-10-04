---
title: "codex-fallback-review-residuals"
created_date: 2026-10-04
status: draft
---

# codex-fallback-review-residuals - 要件定義書

## 1. 概要

### 1.1 背景
タスク記述は、`em-workflow/scripts/run_codex_exec.sh` のプロバイダフォールバック連鎖が前の試行の出力を切り捨て、`rate_limited` 判定が失われる不具合（b915524ad5c7ed09）を挙げている。併せて、`feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml` に残る未解決の medium 指摘 5 件（21fcec3b529ebbd1、7e1c5176f1992a47、ad385249e099e34b、f16ba900e23a5497、43504ede8ee2f609）を挙げている。

現行ツリーでは、見出しの不具合（b915524ad5c7ed09）と 7e1c5176f1992a47、43504ede8ee2f609 は解消済みである。21fcec3b529ebbd1、ad385249e099e34b、f16ba900e23a5497 は未解決のまま残っている。

### 1.2 目的
- `feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml` の medium 指摘のうち、現行ツリーで未解決のもの（21fcec3b529ebbd1、ad385249e099e34b、f16ba900e23a5497）を閉じる。変更後は、利用者向けの README、Opus escalation の定義、batch 監査記録の `source` マッピングが、互いに、かつ batch-codex-autonomous-decisions の SPEC と一致する。
- タスクの見出しの不具合（b915524ad5c7ed09）と指摘 7e1c5176f1992a47、43504ede8ee2f609 が現行ツリーに存在しないことを明示的に記録し、再発しないよう回帰チェックを加える。そのうち 1 つは `--litellm MODEL` をそのまま渡すことのチェックで、現状どのテストもこれを見ていない。

### 1.3 スコープ

**対象**:
- FR1: `em-workflow/README.md` の `--batch` 項目の記述修正（21fcec3b529ebbd1）
- FR2〜FR4: `em-workflow/references/question-resolution.md` の `### Opus escalation` 節と、専用エージェント定義・契約ドキュメントの追加（ad385249e099e34b）
- FR5: `em-workflow/references/phase-state.md` の batch 監査記録の `source` マッピング（f16ba900e23a5497）
- FR6: FR1〜FR5 を固定するテスト
- FR7: `--litellm MODEL` をそのまま渡すことの回帰テスト（7e1c5176f1992a47）

**対象外**:
| ID | 指摘 | 理由 |
|----|------|------|
| X1 | b915524ad5c7ed09（タスクの見出し: フォールバック連鎖が前の試行の出力を切り捨てる） | 解消済み。`em-workflow/scripts/run_codex_exec.sh` は現在 `codex exec` を 1 回だけ起動する（ヘッダ 26〜30 行、起動は 175 行）。フォールバック連鎖も `run_attempt` も entry ごとの切り捨てもない。stdout と stderr は 1 回だけ連結される（194 行）ため、entry 1 の usage-limit 診断は必ず `codex-reviewer.md` Step 6 に届く。`tests/test_codex_wrapper_single_invocation.py` の AC-1 が、1 回の起動で usage-limit の stderr テキストがそのまま caller に届くことを固定している。 |
| X2 | タスクの完了の定義: `tests/test_codex_wrapper_provider_fallback.py` の stdout 完全一致 assert 3 件の更新と、ヘッダコメントへの合成規則の追記 | 適用対象がない。そのテストモジュールは削除済みで、`tests/test_codex_wrapper_single_invocation.py::TestSupersededModuleRemoved` が存在しないことを assert している。起動が 1 回なので、文書化すべき複数 entry の合成規則もない。 |
| X3 | 7e1c5176f1992a47（wrapper に litellm のモデル名がハードコードされている） | wrapper 側は解消済み。`ENTRY_ARGS_*` も `PROVIDER_NAME_*` もない。モデルは caller の `--litellm MODEL` 引数からのみ渡され、そのまま渡される（102〜112 行）。`muse-spark` は 9 行目の使用例コメントにしか現れない。wrapper の変更は不要。欠けている回帰チェックを FR7 で加える。 |
| X4 | 43504ede8ee2f609（switch 判定が未検証の stderr の前提に依存している） | 解消済み。wrapper には `is_usage_limit_response` / `is_provider_error_response` も、応答の形を判定する仕組みも一切ない（ヘッダ 29〜30 行）。`tests/test_codex_wrapper_single_invocation.py` の AC-3 が、switch の形をしたテキストで 2 回目の起動が起きないことを固定している。 |

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 目的と同じ。

### 2.2 対象ユーザー
該当なし。

### 2.3 期待される効果
- 利用者向けの README、Opus escalation の定義、batch 監査記録の `source` マッピングが、互いに、かつ batch-codex-autonomous-decisions の SPEC と一致する。
- 解消済みの不具合（b915524ad5c7ed09、7e1c5176f1992a47、43504ede8ee2f609）の再発を回帰テストが検出する。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 由来の指摘 |
|----|--------|------------|
| FR1 | README の batch 記述で interactive / batch の扱いの違いを述べる | 21fcec3b529ebbd1 |
| FR2 | Opus escalation が dispatch 経路・契約・モデルの束縛を指定する | ad385249e099e34b |
| FR3 | Opus escalation のエージェント定義と契約ドキュメント | ad385249e099e34b |
| FR4 | 非パケットゲートの呼び出し元に対する Opus escalation の適用範囲と選択肢の示し方 | ad385249e099e34b |
| FR5 | escalation が決めた非パケットゲートの batch 監査記録の `source` | f16ba900e23a5497 |
| FR6 | FR1〜FR5 を固定するテスト | 21fcec3b529ebbd1、ad385249e099e34b、f16ba900e23a5497 |
| FR7 | 回帰チェック: `--litellm MODEL` をそのまま渡す | 7e1c5176f1992a47 |

### 4.2 機能詳細

#### FR1: README の batch 記述で interactive / batch の扱いの違いを述べる

**説明**: `em-workflow/README.md` の `--batch` 項目にある「仕様変更・セキュリティ・ライセンス・不可逆判断のゲートは未収載なら安全側で中断する（fail-closed）」の記述を書き直す。

**ビジネスルール**:
- 新しい記述は、モードごとの扱いの違いを述べる。
    - interactive モードでは中断する。
    - batch モードでは、セキュリティ・ライセンス・不可逆操作の質問は緩和経路（Codex 相談 → Opus escalation → 最小副作用の選択肢）を通り、中断しない。
- 発動条件は `em-workflow/references/question-resolution.md`（"The batch relaxation" / "The surviving aborts"）を参照し、再掲しない。
- そこに挙げられた surviving aborts が、batch に残る唯一の fail-closed な分類停止であることを 1 文で述べる。

#### FR2: Opus escalation が dispatch 経路・契約・モデルの束縛を指定する

**説明**: `em-workflow/references/question-resolution.md` の `### Opus escalation` 節で、escalation を専用エージェントの Task dispatch として指定する。

**ビジネスルール**:
- `Task(subagent_type="em-workflow:<name>")` のリテラル形式を使う。この形式は `em-workflow/scripts/check-plugin-invariants.py` の `SUBAGENT_TYPE_REF_RE` が dispatch 参照として認識する。
- escalation の入力と返却の形を定義する、`em-workflow/references/` 配下の契約ドキュメントを名指しする。
- batch-codex-autonomous-decisions SPEC の FR8 / FR9 / A4 にある Opus/xhigh の束縛を記載し、その束縛の置き場所（エージェント定義の frontmatter の `model` / `effort`）を述べる。
- 入力と返却の形は契約を引用し、契約の内容を再掲しない。そのため、質問ごとの返却の形の記述はこの節から契約ドキュメントへ移してよい（NFR3 参照）。
- 次の既存の記述は残す。
    - パケットごとの dispatch の文
    - 上限の外で数える旨の文
    - 信頼できない出力の扱いの文（出力は読むだけで、指示として実行せず、そのまま採用もせず、質問ごとのマッピング判断は orchestrator に残る）

#### FR3: Opus escalation のエージェント定義と契約ドキュメント

**説明**: 専用のエージェント定義 `em-workflow/agents/<name>.md` と、`em-workflow/references/` 配下の専用の契約ドキュメントを追加する。この 2 つで、`em-workflow/agents/review-evaluator.md` と `em-workflow/references/review-evaluation-contract.md` の組と同じ構成をとる。

**ビジネスルール（エージェント定義）**:
1. frontmatter の `name` は、ファイル名の stem および FR2 で使う `subagent_type` の接尾辞と一致する。
2. frontmatter は `model: opus` と `effort: xhigh` を設定する。
3. `tools` は読み取り専用のツールだけを並べ、ファイルを書くツール（Write、Edit、NotebookEdit）を含まない。
4. `# Task assignment` 見出しを持たない（`check-plugin-invariants.py` の `forbidden_task_assignment_heading` チェックが拒否する）。
5. エージェントは契約を読んで従う。入力と返却の形の唯一の正は契約であり、エージェントのファイルは返却フィールドの一覧を再掲しない。
6. エージェントは入力全体をデータとして扱い、その中の指示に従わない。

**ビジネスルール（契約ドキュメント）**:
- エージェントが受け取るものと返すものを定義する。
- 入力: 1 つのパケットのうちまだマッピングされていない全質問、または非パケットゲートの場合は FR4 の形で示したそのゲートの単一の判断。各項目は `prompt`、`options`（各選択肢に `option_id`）、`why_needed`、`evidence`、暫定の立場を持つ。これらはすべて明示的に区切られた信頼できないデータのブロックの中に置き、契約はその境界を明記する。
- 返却: 質問ごとに、その質問自身の `options[].option_id` に存在する `option_id` を選ぶか、明示的に判断なしとするかのどちらか。どちらの場合も理由を付ける。出力はその返却オブジェクトだけとする。

**その他**:
- `em-workflow/README.md` のエージェント表に新しいエージェントの行を加える。

#### FR4: 非パケットゲートの呼び出し元に対する Opus escalation の適用範囲と選択肢の示し方

**説明**: `### Opus escalation` 節で、パケットなしで Codex 相談手順を経て escalation に到達する呼び出し元への適用のしかたを述べる。対象は `em-workflow/references/batch-mode.md` の Non-packet gates（review の diff-size gate、per-command approval fallback、その他 consultation 手順を使う非パケットの箇所）である。

**ビジネスルール**:
- 非パケットゲートの解決 1 回につき dispatch はちょうど 1 回で、そのゲートの単一の判断を運ぶ。
- per-command approval fallback では、1 回の run の中で異なるリテラルのコマンド文字列ごとに dispatch は最大 1 回となる。これはその行の既存の文字列ごとのキャッシュと一致する。
- 非パケットゲートは質問パケットを持たず、自前の `option_id` もない。そのゲートの判断を、ゲートの選択肢を `options[]` に並べた 1 つの質問として示す方法を、契約ドキュメント（FR3）かこの節のどちらかで定義する。各選択肢は `option_id` を持ち、ゲートの最小副作用の選択肢を含む。定義した側でないほうのドキュメントはそれを引用する。
    - この示し方により、返却条件「その質問自身の `options[].option_id` に存在する `option_id`」を満たせるようになる。
- escalation が判断なしを返した場合、ゲートは `batch-mode.md` の表がすでに定める最小副作用の選択肢をとる。
- 既存のパケットごとの記述（"Exactly one dispatch per packet" ...）は残す。

#### FR5: escalation が決めた非パケットゲートの batch 監査記録の `source`

**説明**: `em-workflow/references/phase-state.md` の Batch audit record file 節にある、Non-packet gates の writer を規定する一般的な `source` マッピングを変更する。

**ビジネスルール**:
- Opus escalation が決めた非パケットゲートの値を定義する。availability probe がハーネスを見つけられず、Codex 相談のターンが走らなかった場合も含む。
- 値は `batch-codex-consultation` とする。これは相談の経路を指すものとして読み、Codex 自体に相談したという主張とは読まない。relaxed-route の項目がすでに使っている読み方と同じである。
- 値は `question-packet-schema.md` の既存の閉じた語彙から取り、新しい値は作らない。
- 最小副作用の選択肢をとった場合の値は引き続き `batch-safe-default` とする。
- Non-packet gates の writer の `resolution_note` には、Opus escalation が走ったかどうかとその理由も記録する。
- escalation が解決し、Codex 相談も safe-default の選択もなかった非パケットゲートの記録例を節に加える。例は次を持つ。
    - そのゲートの `question_id`（`review.diff-size-gate` または `command-execution.per-command-approval-fallback`）
    - `packet_id: null`
    - `source: batch-codex-consultation`
    - Codex に相談しなかったこと、Opus escalation が走ったこと、その理由を述べた `resolution_note`

#### FR6: FR1〜FR5 を固定するテスト

**説明**: `tests/` 配下のテスト（Python 標準ライブラリの unittest）で次を assert する。

**ビジネスルール**:
- (a) `README.md` に batch の fail-closed 中断の記述がもうなく、緩和の条件について `references/question-resolution.md` を引用している。
- (b) Opus escalation 節が、リテラル `Task(subagent_type="em-workflow:<name>")`、契約のパス、Opus/xhigh の束縛を含む。名指しされたエージェントのファイルが存在する。その frontmatter は、ファイル名の stem と等しい `name`、`model: opus`、`effort: xhigh` を持つ。`tools` にファイルを書くツール（Write、Edit、NotebookEdit のいずれも）がない。`# Task assignment` 見出しがない。名指しされた契約ファイルが存在する。
- (c) 契約ドキュメントが、区切られた信頼できない入力の境界と、質問ごとの返却契約（その質問自身の `options[].option_id` からの `option_id` か明示的な判断なし、どちらも理由付き）を述べている。
- (d) `tests/test_question_resolution_doc.py` の既存の返却の形の固定（`test_opus_escalation_return_shape`）を、網羅を失わずに更新する。節が契約ドキュメントを参照していることと、契約ドキュメントが返却の形の記述を含むことを assert する。他の既存の Opus escalation の固定は変えない。
- (e) Opus escalation 節または契約が、非パケットゲートの適用範囲と、非パケットの選択肢 / `option_id` の示し方の規則を述べている。
- (f) `phase-state.md` の一般マッピングが escalation で決まった非パケットのケースを扱い、記録例を含む。これらの assert は、指摘の求めどおり `tests/test_batch_quiet_output_audit_record_contract.py` に置く。
- 新しい否定の assert にはそれぞれ、これらのモジュールの既存のパターンに倣って、空振りでないことの証明を付ける。

#### FR7: 回帰チェック: `--litellm MODEL` をそのまま渡す

**説明**: `tests/test_codex_wrapper_single_invocation.py` に、`em-workflow/scripts/run_codex_exec.sh` を `--litellm` と、wrapper にも `references/reviewers.yaml` にもないモデル名の任意の値で呼ぶケースを加える。

**ビジネスルール**:
- 起動が 1 回で、その argv が `-p`、`litellm`、`-m`、MODEL を連続した要素として含み、MODEL が変わっていないことを assert する。
- 既存の argv チェック（`test_accepted_flag_set_on_the_launch_is_unchanged`）は `--litellm` を渡していない。
- 空振りでないことの証明を付ける。そのマッチャーは、モデルの値が置き換えられた argv や落とされた argv を拒否する。
- wrapper 自体は変更しない。

## 5. 非機能要件

### 5.1 非機能要件一覧
| ID | 要件 |
|----|------|
| NFR1 | 新しい `gate_id`、`references/batch-policies.yaml` の新しいエントリ、回答の `source` 語彙（`references/question-packet-schema.md`）の新しい値を、どれも加えない。 |
| NFR2 | `em-workflow/scripts/run_codex_exec.sh` は変更しない。`tests/test_codex_wrapper_provider_fallback.py` は作り直さない。`tests/test_codex_wrapper_single_invocation.py` がそれが存在しないことを assert している。 |
| NFR3 | 既存のテストが固定している語句はそのまま残す。例外は 1 つで、`tests/test_question_resolution_doc.py::test_opus_escalation_return_shape` が固定している Opus escalation の返却の形の文である。この文は契約ドキュメントへ移してよい。ただし、そのテストを更新して、節が契約を参照していることと契約が返却の形を持つことを assert し、網羅を保つ。`### Opus escalation` 節では次の固定を変えない: "Exactly one dispatch per packet"、"carrying every question of that packet still unmapped when the consultation ended"、上限の外で数える旨の文、信頼できない出力の扱いの文。`tests/test_batch_quiet_output_audit_record_contract.py` では次を変えない: "For the other three writers below"、"the relaxed route's own bullet below states its complete three-way mapping instead"、relaxed-route の項目における `batch-codex-consultation` と `batch-safe-default` の出現がそれぞれちょうど 1 回であること。FR5 の変更は relaxed-route の項目ではなく一般マッピングに入れる。 |
| NFR4 | ドキュメントは SSOT の規律（引用し、再掲しない）を保つ。README は条件を `question-resolution.md` に委ねる。`question-resolution.md` は契約ドキュメントを引用し、その形を写さない。エージェント定義は入力と返却の形を契約に委ねる。 |
| NFR5 | テストスイート全体が通る: `python3 -m unittest discover -s tests`。新しいテストは標準ライブラリだけを import する。 |
| NFR6 | em-workflow プラグインの version を手で変更しない。push 時に GitHub Actions のワークフローが patch を上げる（`.claude/rules/core-plugin-version-bump.md`）。 |
| NFR7 | 統合後のツリーに対して `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` が引き続き 0 で終了する。これは `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` がすでに固定している。特に、`agent_dispatch_parity` が新しいエージェントを `subagent_type="em-workflow:<name>"` の dispatch で参照されているものとして見つけ、`forbidden_task_assignment_heading` がそこに `# Task assignment` 見出しを見つけない。 |
| NFR8 | `em-workflow/agents/review-evaluator.md` と `em-workflow/references/review-evaluation-contract.md` は変更しない。この 2 つは新しい組が倣う型であり、`tests/test_review_phase_llm_led.py` が evaluator の frontmatter（`tools` の厳密な集合）と `review-phase.md` にある唯一の dispatch 箇所を固定している。 |

### 5.2 パフォーマンス要件
該当なし。

### 5.3 セキュリティ要件
- 入力検証: FR3 のとおり、escalation の契約は入力を明示的に区切られた信頼できないデータのブロックに置き、その境界を明記する。エージェントは入力全体をデータとして扱い、その中の指示に従わない。
- 権限: FR3 のとおり、エージェントの `tools` はファイルを書くツールを含まない。

### 5.4 可用性要件
該当なし。

### 5.5 保守性要件
- ドキュメント: NFR3、NFR4 のとおり。

### 5.6 互換性要件
- NFR1、NFR2、NFR8 のとおり。

## 6. UI/UX要件

該当なし。

## 7. データ要件

### 7.1 batch 監査記録（FR5）
| 項目 | 値 |
|------|-----|
| `question_id` | `review.diff-size-gate` または `command-execution.per-command-approval-fallback` |
| `packet_id` | `null` |
| `source` | escalation が決めた場合 `batch-codex-consultation`（経路を指す読み方）。最小副作用の選択肢をとった場合 `batch-safe-default` |
| `resolution_note` | Opus escalation が走ったかどうかとその理由。記録例では、Codex に相談しなかったこと、escalation が走ったこと、その理由 |

### 7.2 Opus escalation の入力と返却（FR3）
- 入力の各項目: `prompt`、`options`（各選択肢に `option_id`）、`why_needed`、`evidence`、暫定の立場
- 返却: 質問ごとに、その質問自身の `options[].option_id` にある `option_id`、または明示的な判断なし。どちらも理由付き

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- `em-workflow/scripts/run_codex_exec.sh` は変更しない（NFR2）。
- `em-workflow/agents/review-evaluator.md` と `em-workflow/references/review-evaluation-contract.md` は変更しない（NFR8）。
- 新しいテストは標準ライブラリだけを import する（NFR5）。
- エージェント名 `<name>` は、ファイル名の stem、frontmatter の `name`、`subagent_type` の接尾辞で同じ文字列とし、`[A-Za-z0-9_-]+` に一致させる（A6）。

### 9.2 ビジネス上の制約
- em-workflow プラグインの version を手で変更しない（NFR6）。

### 9.3 スケジュール制約
該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-fallback-review-residuals/**`
- `test-docs/codex-fallback-review-residuals/**`

`feature-docs/codex-fallback-review-residuals/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-fallback-review-residuals/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-fallback-review-residuals/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1、FR6）: `em-workflow/README.md` が、未収載のセキュリティ・ライセンス・不可逆のゲートは batch で fail-closed 中断するとはもう述べていない。interactive の中断と batch の緩和経路の違いを述べ、条件と surviving aborts について `references/question-resolution.md` を指している。テストがこれを固定し、古い記述に対する否定の証明を持つ。
- [ ] AC2（FR2、FR3、FR6、NFR7）: `question-resolution.md` の `### Opus escalation` 節が、`Task(subagent_type="em-workflow:<name>")`、契約ドキュメントのパス、そのエージェントの frontmatter に置かれた Opus/xhigh の束縛を含む。名指しされたエージェントのファイルが存在する。その frontmatter はファイル名の stem と等しい `name`、`model: opus`、`effort: xhigh` を持つ。tools にファイルを書くツールがなく、`# Task assignment` 見出しもない。名指しされた契約ファイルが存在する。README のエージェント表がそのエージェントを載せている。リポジトリルートに対して `check-plugin-invariants.py` が 0 で終了する。各点をテストが固定する。
- [ ] AC3（FR3、FR6）: 契約ドキュメントが、区切られた信頼できない入力の境界と、質問ごとの返却契約（その質問自身の `options[].option_id` にある `option_id` を選ぶか明示的な判断なし、どちらも理由付き）を述べている。テストが契約を読み、両方を固定する。
- [ ] AC4（FR4、FR6）: Opus escalation 節が非パケットゲートの適用範囲を述べている: 非パケットゲートの解決 1 回につき dispatch 1 回（per-command approval fallback では異なるリテラルのコマンド文字列ごと）、判断なしの結果は `batch-mode.md` の最小副作用の選択肢に落ちる。節または契約が、非パケットゲートの選択肢を 1 つの質問の `option_id` 付きの `options[]` として示す方法を定義し、もう一方のドキュメントがその定義を引用する。既存のパケットごとの文は変わっていない。テストがこれを固定する。
- [ ] AC5（FR5、FR6）: `phase-state.md` の一般的な `source` マッピングが、Opus escalation が決めた非パケットゲートに `batch-codex-consultation`（経路を指す読み方）を与える。Codex のターンが走らなかった場合も含む。Non-packet gates の writer の `resolution_note` が、escalation が走ったかどうかとその理由を記録する。節に、`packet_id: null` と、Codex に相談しなかったこと・escalation が走ったこと・その理由を述べた `resolution_note` を持つ、このケースの記録例がある。`tests/test_batch_quiet_output_audit_record_contract.py` がこれらすべてを扱う。
- [ ] AC6（FR6、NFR3）: `tests/test_question_resolution_doc.py::test_opus_escalation_return_shape`（またはその置き換え）が、Opus escalation 節が契約ドキュメントを参照していることと、契約ドキュメントが返却の形の記述を含むことを assert する。既存の Opus escalation の固定は弱められておらず、NFR3 に挙げた他の固定語句もすべて残っている。
- [ ] AC7（FR7、NFR2）: テストが `run_codex_exec.sh` を `--litellm` と任意のモデルの値で呼ぶ。起動がちょうど 1 回で、その argv が `-p litellm -m MODEL` を連続して持ち、MODEL が変わっていないことを assert し、空振りでないことの証明を持つ。
- [ ] AC8（NFR2）: 解消済みの見出しの不具合に対する回帰の防護: `run_codex_exec.sh` は呼び出し 1 回につき `codex exec` をちょうど 1 回起動し、stderr の usage-limit 診断はそのまま caller に届く。`tests/test_codex_wrapper_single_invocation.py` の既存のケース（そのモジュールの AC-1、AC-3、AC-7）がすでにこれを固定しており、通り続けなければならない。`tests/test_codex_wrapper_provider_fallback.py` は存在しない。
- [ ] AC9（NFR3、NFR5、NFR8）: `python3 -m unittest discover -s tests` が通る。AC6 が網羅ごと移す返却の形の文を除き、固定された語句は削除されていない。`tests/test_review_phase_llm_led.py` は変更なしで通る。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: `em-workflow/README.md` を読む。古い fail-closed の記述の文字列がないこと、batch の項目がセキュリティ・ライセンス・不可逆の質問について緩和経路を名指ししていること、`references/question-resolution.md` を引用していることを assert する。否定の証明のフィクスチャ: 古い記述のテキストをマッチャーが捕まえる。
- [ ] TS2（AC2）: `question-resolution.md` の `### Opus escalation` 節を切り出す。`Task(subagent_type="em-workflow:<name>")` のリテラルと契約のパスを取り出す。`em-workflow/agents/<name>.md` と契約ファイルが存在することを assert する。エージェントの frontmatter を、`tests/test_review_phase_llm_led.py` が review-evaluator に対して行うのと同じ方法で解析する。`name` が `<name>` と等しいこと、frontmatter が `model: opus` と `effort: xhigh` を持つこと、`tools` の集合が {Write, Edit, NotebookEdit} と交わらないことを assert する。`# Task assignment` 見出しがないこと、README のエージェント表が `<name>` を載せていることを assert する。空振りでないことの証明: `Write` を持つフィクスチャの frontmatter を tools のマッチャーが拒否する。
- [ ] TS3（AC3、AC6）: 契約ドキュメントを読む。入力について区切られた信頼できないデータのブロックと、質問ごとの返却契約（その質問自身の `options[].option_id` からの `option_id`、または明示的な判断なし、どちらも理由付き）を述べていることを assert する。`test_opus_escalation_return_shape` を更新し、節が契約のパスを引用していることと、契約が返却の形の記述を含むことを assert する。他の Opus escalation の固定が節に対して引き続き通ることを assert する。
- [ ] TS4（AC4）: Opus escalation 節が非パケットゲートの適用範囲の記述（非パケットゲートの解決 1 回につき dispatch 1 回、approval fallback についてのコマンド文字列ごとの読み方、判断なしが最小副作用の選択肢に落ちること）を含むことを assert する。節または契約が、非パケットゲートの選択肢が 1 つの質問の `option_id` 付きの `options[]` になる方法を述べ、もう一方のドキュメントがそれを引用していることを assert する。既存のパケットごとの文が残っていることを assert する。
- [ ] TS5（AC5）: `phase-state.md` の Batch audit record file 節を切り出す。一般マッピングが escalation で決まった非パケットのケースを経路を指す読み方で `batch-codex-consultation` に対応させていることを assert する。Non-packet gates の writer の `resolution_note` が escalation が走ったかどうかとその理由を名指ししていることを assert する。節に、非パケットの `question_id`（`review.diff-size-gate` または `command-execution.per-command-approval-fallback`）、`packet_id: null`、`source: batch-codex-consultation`、escalation が走り Codex に相談しなかったことを述べる `resolution_note` を持つ YAML の記録例があることを assert する。relaxed-route の項目が各 source リテラルをちょうど 1 回ずつ持ち続けていることを assert する。
- [ ] TS6（AC7）: `tests/test_codex_wrapper_single_invocation.py` の既存の codex スタブの仕組みを使い、`run_codex_exec.sh readonly --litellm <arbitrary-model> "prompt"` を実行する。起動がちょうど 1 回であること、その起動の argv が `-p`、`litellm`、`-m`、`<arbitrary-model>` を連続した要素として含むことを assert する。空振りでないことの証明: 連続列のマッチャーが、別のモデルの値を持つ偽の argv を拒否する。
- [ ] TS7（AC2、AC8、AC9）: スイート全体を実行する。新しいエージェントがある状態で `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` が通る。`tests/test_codex_wrapper_single_invocation.py`（usage-limit がそのまま届くこと、起動 1 回、provider-fallback のモジュールがないこと）と `tests/test_review_phase_llm_led.py` が変更なしで通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| Opus escalation | `em-workflow/references/question-resolution.md` の `### Opus escalation` 節が定める、batch の緩和経路で Codex 相談の後に置かれる段階。本フィーチャーで専用エージェントの Task dispatch として指定する（FR2、FR3）。 |
| 緩和経路（relaxed route） | batch モードでセキュリティ・ライセンス・不可逆操作の質問がとる経路。Codex 相談 → Opus escalation → 最小副作用の選択肢。 |
| 非パケットゲート | `em-workflow/references/batch-mode.md` の Non-packet gates。review の diff-size gate、per-command approval fallback、その他 consultation 手順を使う非パケットの箇所。 |
| 空振りでないことの証明（non-vacuity proof） | 否定の assert のマッチャーが、捕まえるべき入力（フィクスチャ）を実際に捕まえることを示す確認。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] Opus escalation を届ける手段（requirement.opus-escalation-vehicle）: 専用のエージェント `em-workflow/agents/<name>.md` と、`em-workflow/references/` 配下の専用の契約ドキュメントとする（A1）。他の候補は、既存のエージェント種別にモデルの上書きを付ける方法と、契約をインラインに書く方法だった。orchestrator が決定した（source: batch-codex-consultation）。batch-codex-autonomous-decisions SPEC の A4（SPEC.md:49-50）は手段を planning に委ねていたため、インラインの候補も SPEC に反してはいなかった。review-evaluator の役割と契約を分けたままにするため、`review-evaluator.md` + `review-evaluation-contract.md` と同じ構成の専用の組を選んだ。`check-plugin-invariants.py` の `agent_dispatch_parity` は、エージェントが `subagent_type="em-workflow:<name>"` の形で参照されることを要求する。
- [x] escalation が決めた非パケットゲートの `source`（requirement.escalation-nonpacket-source）: 経路を指す読み方で `source: batch-codex-consultation` を記録し、語彙に新しい値は加えない（A2）。orchestrator が確認した。`question-packet-schema.md` の `source` 語彙は閉じている。`phase-state.md` の relaxed-route の項目（470〜475 行）は、すでにその読み方で escalation の判断を `batch-codex-consultation` に対応させている。`batch-safe-default`、`batch-decision-table`、`batch-classification-gate` はこのケースに合わない。

### 14.2 前提事項

- A3: この変更は minor / major の version を上げないので、version は Actions の patch の引き上げに任せる。根拠: この変更は、出荷済みのフィーチャーの欠けを埋めるもの（ドキュメントの整合と、そのフィーチャーの SPEC がすでに求めていた escalation の手段）である。`core-plugin-version-bump.md` は手での引き上げを機能追加と互換性を壊す変更に限っている。
- A4: 現在、専用の Opus escalation エージェントは存在しない。新しいエージェントに必要な登録は、(1) `em-workflow/`、`feature-docs/`、`test-docs/`、`tests/` のどこかで `subagent_type="em-workflow:<name>"` の形で参照されること、(2) `# Task assignment` 見出しを持たないこと、の 2 つだけである。根拠: `check-plugin-invariants.py` はエージェントの集合を `em-workflow/agents/*.md` から作り（231〜237 行）、`SCAN_ROOTS` に `SUBAGENT_TYPE_REF_RE` の一致がない定義を失敗にする（99、172〜174、265〜270 行）。`tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` はそれをリポジトリルートに対して実行する。`question-resolution.md` には `subagent_type` の参照がなく、README のエージェント表にも escalation のエージェントはない。別の登録簿はない（`gate_id_coverage` チェックは batch-policies の id だけを扱い、新しいエージェントはそれを加えない）。
- A5: 新しいエージェントの `tools` は Read、Glob、Grep とし、Bash は与えない。根拠: escalation は渡された質問から判断し、コマンドを実行する必要がない。review-evaluator が Bash を持つのは変更ファイルを読み取り専用の `git diff` / `git log` で調べるためで、escalation はそれを行わない。テストの要件（FR6 (b)）はファイルを書くツールがないことだけを求めるので、この選択は planning で変えてもテストに影響しない。
- A6: エージェントの `<name>` は planning で決める。ファイル名の stem、frontmatter の `name`、`subagent_type` の接尾辞は同じ文字列で、`[A-Za-z0-9_-]+` に一致する。根拠: `SUBAGENT_TYPE_REF_RE` は `em-workflow:([A-Za-z0-9_-]+)` を捕まえ、`agent_dispatch_parity` はその捕まえた文字列をファイル名の stem と比べる。

### 14.3 未確認・保留事項
- [ ] エージェント名 `<name>` は create-plan で決める（A6）。
- [ ] 非パケットゲートの選択肢の示し方を定義する側（契約ドキュメントか `### Opus escalation` 節か）は FR4 がどちらも許している。

## 15. 参考資料

- `feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml`: 指摘 21fcec3b529ebbd1、7e1c5176f1992a47、ad385249e099e34b、f16ba900e23a5497、43504ede8ee2f609 の全文
- `feature-docs/batch-codex-autonomous-decisions/SPEC.md`: FR8、FR9、A4（Opus/xhigh の束縛）
- `em-workflow/references/question-resolution.md`
- `em-workflow/references/phase-state.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/question-packet-schema.md`
- `em-workflow/agents/review-evaluator.md`、`em-workflow/references/review-evaluation-contract.md`
- `em-workflow/scripts/check-plugin-invariants.py`
- `em-workflow/scripts/run_codex_exec.sh`

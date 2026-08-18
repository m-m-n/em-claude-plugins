---
title: "exit4-tip-argument"
created_date: 2026-08-18
status: draft
---

# exit4-tip-argument - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/scripts/commit-docs.sh` は第3引数として任意の `expected_base_tip` を受け取る。スクリプト自身のヘッダは、この引数を「呼び出し側の refresh+edit とスクリプト内部の BEFORE_TIP 読み取りの間に開く窓を閉じる、権威ある staleness チェック」と記述し、呼び出し側は SHOULD で渡すべきと述べている。

`em-workflow/references/implement-phase.md` の中では、Step I.1（BASE_COMMIT）、Step I.2.b（RECONCILE_TIP）、Step I.2.c の route-back（ROUTEBACK_TIP）、Step I.2.c の terminal（TERMINAL_TIP）がそれぞれ tip を捕捉して渡している。一方、同じドキュメントの exit-4 recovery の箇条書きが「この recovery に拘束される」と列挙している呼び出し箇所のうち 2 つ — Step I.2.a の launch 時の task status / task branch 書き込みと、Step I.3 の implement-completed / completed-commit 書き込み — は、refresh も tip の捕捉も `commit-docs.sh` の呼び出し自体も一切記述していない。

### 1.2 目的

上記 2 箇所がスクリプト側の弱い start-vs-under-lock チェックにフォールバックし、並行する `merge-task.sh` が既に進めた tip の上に構築されたドキュメント書き込みをコミットしうるギャップを閉じる。exit-4 recovery の箇条書きが名指しする implement フェーズの全 `commit-docs.sh` 呼び出し箇所が、捕捉した `expected_base_tip` を渡すようにする。

### 1.3 スコープ

**対象**:
- `em-workflow/references/implement-phase.md` のプロトコル記述（Step I.2.a、Step I.3、および refill 境界）
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` のバージョン bump
- `tests/` 配下への新規契約テストの追加

**対象外**:
- `em-workflow/scripts/commit-docs.sh`（`expected_base_tip` 第3引数、exit code のセマンティクス、RECOVERY CONTRACT は現状のままで本変更を支える）
- `tests/test_rework_synthesis_contract.py`（本フィーチャーでは編集しない）
- hook / script / agent 定義の挙動変更

## 2. ビジネス要件

### 2.1 ビジネス目標

exit-4 recovery の箇条書きが列挙する implement フェーズの `commit-docs.sh` 呼び出し箇所すべてが、その箇所自身の refresh の後に捕捉した tip を第3引数として渡す状態にする。これにより、列挙されたどの箇所もスクリプトの二次的な start-vs-under-lock チェックのみに依存しなくなる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の orchestrator | `implement-phase.md` の手順に従って workflow.yaml の書き込みとコミットを実行する主体 |
| em-workflow の保守者 | プロトコル文書と exit-4 recovery の列挙の整合性を維持する主体 |

### 2.3 期待される効果

- 並行する `merge-task.sh` が tip を進めた後に、古い tip の上に構築された doc 書き込みをコミットする経路が閉じる
- 6 つの呼び出し箇所が単一の一貫したメカニズムとして読める
- exit-4 recovery の箇条書きと各ステップ本文が一対一で対応する

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | Launch 時の task status / task branch 書き込みを tip 付きでコミットする | orchestrator | 高 |
| UC02 | Phase completion 時の implement-completed / completed-commit 書き込みを tip 付きでコミットする | orchestrator | 高 |
| UC03 | Refill 経路から Step I.2.a に再入した際に新しい tip を捕捉する | orchestrator | 高 |

### 3.2 ユースケース詳細

#### UC01: Launch 時の task status / task branch 書き込みを tip 付きでコミットする

**アクター**: orchestrator（Step I.2.a Launch phase）

**事前条件**:
- integration worktree が存在する
- launch 対象タスク `{T}` が決定している

**基本フロー**:
1. integration worktree を refresh する — `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
2. tip を捕捉する — `LAUNCH_TIP=$(git -C {integration_worktree} rev-parse HEAD)`
3. refresh 済みの worktree 上で workflow.yaml に `tasks.{T}.status = in_progress` と `tasks.{T}.branch` を書き込む
4. 捕捉した tip を第3引数としてコミットする — `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$LAUNCH_TIP"`

**代替フロー**:
- `commit-docs.sh` が exit 4 を返した場合は Branch & Worktree Model の exit-4 recovery に従う

**事後条件**:
- 書き込みが、捕捉した tip を基準として検証された状態でコミットされている

#### UC02: Phase completion 時の implement-completed / completed-commit 書き込みを tip 付きでコミットする

**アクター**: orchestrator（Step I.3 Phase completion）

**事前条件**:
- implement フェーズの完了条件が満たされている

**基本フロー**:
1. `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
2. `COMPLETION_TIP=$(git -C {integration_worktree} rev-parse HEAD)`
3. workflow.yaml の `implement` ステップに `status = completed` と `completed_at_commit` を書き込む
4. `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$COMPLETION_TIP"`

**代替フロー**:
- exit 4 の場合は exit-4 recovery の箇条書きを参照する

**事後条件**:
- `test_completed_at_commit_wording_is_unchanged` が pin している文が byte 単位で不変のまま、上記の手順が記述されている

#### UC03: Refill 経路から Step I.2.a に再入した際に新しい tip を捕捉する

**アクター**: orchestrator（Step I.2.b step 5 の refill 経路）

**事前条件**:
- Step I.2.b step 2 で `RECONCILE_TIP` が捕捉済み
- Step I.2.b step 3 の `commit-docs.sh` によりブランチ tip が既に進んでいる

**基本フロー**:
1. 同一ターン内で Step I.2.a に再入する
2. Step I.2.a 自身の refresh を行い、新しい tip を捕捉する
3. その新しい tip を `commit-docs.sh` の第3引数として渡す

**代替フロー**:
- なし（`$RECONCILE_TIP` の再利用は禁止）

**事後条件**:
- `$RECONCILE_TIP`（および他の既捕捉 tip）が第3引数として使われていない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 列挙された全呼び出し箇所が捕捉済み `expected_base_tip` を渡す | exit-4 recovery が列挙する 6 箇所すべてに明示的な三引数呼び出しを記述する | 高 |
| FR2 | Step I.2.a に refresh / capture / write / commit-with-tip の順序を記述する | Launch phase の順序付きシーケンスを本文に明記する | 高 |
| FR3 | Step I.3 に refresh / capture / write / commit-with-tip の順序を記述する | Phase completion の順序付きシーケンスを本文に明記する | 高 |
| FR4 | Step I.3 の pin された文を byte 単位で不変に保つ | pin 文を一切変更せず、テストファイルも編集しない | 高 |
| FR5 | Refill 再入時に fresh tip を捕捉し `$RECONCILE_TIP` を再利用しない | refill 境界で明示する | 高 |
| FR6 | プラグインのバージョン bump | 2 箇所を同一値の patch bump にする | 高 |

### 4.2 機能詳細

#### FR1: 列挙された全呼び出し箇所が捕捉済み `expected_base_tip` を渡す

**説明**: `em-workflow/references/implement-phase.md` は、その "exit-4 recovery" の箇条書きが列挙する全 `commit-docs.sh` 呼び出し箇所（Step I.1 の baseline commit、Step I.2.a の launch 時 task status / task branch 書き込み、Step I.2.b の wake-phase commit、Step I.2.c の rejected-path terminal status commit、Step I.2.c の abort-phase terminal status commit、Step I.3 の implement-completed / completed-commit 書き込み）について、その箇所自身の refresh の後に捕捉した tip を `commit-docs.sh` の第3引数として渡す明示的な呼び出しを記述しなければならない。

**入力**:
- `implement-phase.md` の exit-4 recovery 箇条書きの列挙: 6 つの呼び出し箇所

**出力**:
- 各ステップ本文: 三引数形式の `commit-docs.sh` 呼び出し記述

**ビジネスルール**:
- 本変更後、列挙されたどの箇所もスクリプトの二次的な start-vs-under-lock チェックのみに依存しない
- Step I.2.c の route-back の carve-out は唯一の文書化された例外として残る

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 列挙と本文の不一致 | 箇条書きが名指しする箇所に対応する呼び出し記述が無い | NFR4 の整合性要件に従い記述を追加する |

#### FR2: Step I.2.a に refresh / capture / write / commit-with-tip の順序を記述する

**説明**: Step I.2.a（Launch phase）は、そのステップ自身の本文に、明示的な順序付きシーケンスとして orchestrator が以下を行うことを記述しなければならない。

1. integration worktree を refresh する — `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
2. tip を捕捉する — `LAUNCH_TIP=$(git -C {integration_worktree} rev-parse HEAD)`
3. 直前に refresh した worktree 上で workflow.yaml に `tasks.{T}.status = in_progress` と `tasks.{T}.branch` を書き込む
4. 捕捉した tip を第3引数としてその書き込みをコミットする — `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$LAUNCH_TIP"`（メッセージはドキュメント既存の `docs({feature}): {summary}` 規約に従う）

加えて、exit-4 のケースについて Branch & Worktree Model の exit-4 recovery を相互参照する。

**ビジネスルール**:
- 順序は規範的である: refresh が capture に先行し、capture が write に先行し、write が commit に先行する
- 表現は Step I.2.b の steps 2-3 が既に用いているパターンに倣う

#### FR3: Step I.3 に refresh / capture / write / commit-with-tip の順序を記述する

**説明**: Step I.3（Phase completion）は、implement-completed / completed-commit 書き込みについて、同一の 4 部構成メカニズムを明示的な順序付きシーケンスとして記述しなければならない。

1. `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
2. `COMPLETION_TIP=$(git -C {integration_worktree} rev-parse HEAD)`
3. workflow.yaml への `implement` ステップの `status = completed` および `completed_at_commit` の書き込み
4. `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$COMPLETION_TIP"`

加えて exit-4 recovery 箇条書きへの相互参照を含める。

**ビジネスルール**:
- 表現は Step I.2.b の既存パターンに合わせる
- FR4 の配置制約に従う

#### FR4: Step I.3 の pin された文を byte 単位で不変に保つ

**説明**: `tests/test_rework_synthesis_contract.py` の `test_completed_at_commit_wording_is_unchanged` が pin している Step I.3 の文は、その内部の改行を含めて byte 単位で不変でなければならない。

**ビジネスルール**:
- FR3 が追加する全メカニズムは、その文の厳密に前か厳密に後に配置する
- その文の内部の文字、および assertion がマッチする部分文字列の文字は、一切変更・再折り返し・再インデントしない
- `tests/test_rework_synthesis_contract.py` は本フィーチャーで編集しない

#### FR5: Refill 再入時に fresh tip を捕捉し `$RECONCILE_TIP` を再利用しない

**説明**: Step I.2.b step 5 の refill 経路は同一ターン内で Step I.2.a に再入するが、その時点で `RECONCILE_TIP`（Step I.2.b step 2 で捕捉）は既に stale である。これは Step I.2.b step 3 自身の `commit-docs.sh` によるコミット（ブランチ tip を進める）より前に捕捉されているためである。

**ビジネスルール**:
- Step I.2.a のシーケンスは、refill 再入を含むすべての入口で、自身の refresh を行い新しい tip を捕捉しなければならない
- `$RECONCILE_TIP`（および他の既捕捉 tip）を第3引数として再利用してはならない
- Step I.2.b step 5 から到達した読者が「既に捕捉済みの tip は再利用可能」と結論できないよう、refill 境界でこれを明示する

#### FR6: プラグインのバージョン bump

**説明**: `em-workflow/` 配下のファイルを変更するため、次の 2 箇所のバージョンを同一値に bump する。

- `em-workflow/.claude-plugin/plugin.json` の `version`（現在 `0.1.44`）
- `.claude-plugin/marketplace.json` の `em-workflow` エントリの `version`

**ビジネスルール**:
- ドキュメント / プロトコルの修正であるため patch レベルの bump とする

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし（ドキュメントのみの変更）。

### 5.2 セキュリティ要件

該当なし。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

#### NFR1: 既存 tip 引き渡し箇所との記述の一貫性

FR2 と FR3 が追加するシーケンスは、Step I.1（`BASE_COMMIT`）および Step I.2.b steps 2-3（`RECONCILE_TIP`）が既に用いているのと同じ形・同じ変数捕捉のイディオム・同じ相互参照の言い回しを使う。これにより、列挙された 6 つの呼び出し箇所がステップごとの変種ではなく単一の一貫したメカニズムとして読める。

#### NFR2: ドキュメントのみの変更

`em-workflow/scripts/commit-docs.sh` は変更しない。その `expected_base_tip` 第3引数、exit code のセマンティクス、RECOVERY CONTRACT は現状のまま本変更を支える。hook / script / agent 定義のいずれも挙動を変えない。変更はプロトコル散文と FR6 のバージョン bump に限定される。

#### NFR4: exit-4 recovery 列挙の内部整合性

変更後、Branch & Worktree Model の exit-4 recovery 箇条書きと各ステップ本文が一致する。箇条書きが名指しする全呼び出し箇所が、そのステップ自身に対応する明示的な呼び出しを持ち、Step I.2.c の route-back の carve-out が唯一の文書化された例外として残る。

### 5.5 互換性要件

#### NFR3: 既存テストスイートが無編集で green のまま

`python3 -m unittest discover -s tests` が、いずれのテストファイルも変更せずに pass する。特に `tests/test_rework_synthesis_contract.py` の `test_completed_at_commit_wording_is_unchanged` と `test_regression_precondition_stated_before_launch_selection` は、いずれも `implement-phase.md` の部分文字列と順序に対して assert しており、本変更はそれらを乱してはならない。

## 6. UI/UX要件

該当なし。UI、ユーザー向けの視覚的な面、新規コンポーネント・画面のいずれも存在しない。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- Step I.3 の pin された文は byte 単位で不変（FR4）
- `tests/test_rework_synthesis_contract.py` は編集しない（FR4）
- `em-workflow/scripts/commit-docs.sh` は変更しない（NFR2）
- `test_regression_precondition_stated_before_launch_selection` の順序制約を維持する（NFR3）

### 9.2 ビジネス上の制約

- `em-workflow/` 配下の変更に伴い、バージョンを 2 箇所同一値で bump する（FR6）

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/**`（TS3・TS4・TS5 の新規契約テスト。既存の `tests/test_rework_synthesis_contract.py` は変更しない）

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/exit4-tip-argument/**`
- `test-docs/exit4-tip-argument/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| FR3 の挿入が Step I.3 の pin 文を壊す | 高 | 新規メカニズムを pin 文の厳密に前後へ配置する（FR4）。pin は assertIn の部分文字列チェックなので達成可能（A2） |
| FR2 の挿入が I.2.a の launch-selection 記述との相対順序を変える | 中 | pending-task precondition が launch-selection 記述に先行する順序を維持する（AC10） |
| refill 再入で stale な `RECONCILE_TIP` が再利用される | 高 | refill 境界に fresh capture を明示する（FR5） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| バージョン bump 漏れによりキャッシュが更新されない | 中 | 中 | 2 箇所を同一値で patch bump する（FR6、AC9） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: Step I.2.a の本文が、順に `reset --hard em-workflow/{feature}/integration` の refresh、`rev-parse HEAD` の tip 捕捉、`tasks.{T}.status = in_progress` / `tasks.{T}.branch` の workflow.yaml 書き込み、第3引数がその捕捉 tip である `commit-docs.sh` 呼び出しを含む
- [ ] AC2: Step I.3 の本文が、implement-completed / completed-commit 書き込みについて同じ 4 要素を同じ順序で含む
- [ ] AC3: `test_completed_at_commit_wording_is_unchanged` が assert する厳密な pin 文字列が `implement-phase.md` に byte 単位で存在し、`tests/test_rework_synthesis_contract.py` が diff 上で変更されていない
- [ ] AC4: Step I.2.a（または refill 境界）の本文が、refill 再入を含む全入口で fresh tip を捕捉すること、および `$RECONCILE_TIP` を再利用しないことを述べている
- [ ] AC5: `$RECONCILE_TIP` が Step I.2.a の本文中に `commit-docs.sh` へ渡す値としてどこにも現れない
- [ ] AC6: exit-4 recovery 箇条書きの列挙が名指しする全呼び出し箇所が、そのステップ自身の本文に三引数形式の `commit-docs.sh` 呼び出しを持つ
- [ ] AC7: `python3 -m unittest discover -s tests` が exit 0 で終了する
- [ ] AC8: `em-workflow/scripts/commit-docs.sh` が diff に含まれない
- [ ] AC9: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` が同一の新しい patch bump 済みバージョンを持つ
- [ ] AC10: `test_regression_precondition_stated_before_launch_selection` が引き続き pass する — 挿入後も pending-task precondition が I.2.a の launch-selection 記述に先行する

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（既存・無変更）: `test_completed_at_commit_wording_is_unchanged` — 既存スイートを実行し、FR3 の挿入後も Step I.3 の pin が引き続きマッチすることを確認する（FR4、NFR3）
- [ ] TS2（既存・無変更）: `test_regression_precondition_stated_before_launch_selection` — FR2 の I.2.a への挿入が precondition と launch-selection 記述の順序を入れ替えていないことを確認する（FR2、NFR3）
- [ ] TS3（新規・契約スタイル、`tests/` の既存 assertIn パターンに倣う）: Step I.2.a の本文が refresh、tip 捕捉、および第3引数が捕捉 tip 変数である `commit-docs.sh` 呼び出しを含むことを assert する（FR1、FR2）
- [ ] TS4（新規）: Step I.3 の本文が同じ 3 要素を含むことを assert し、別途 pin 文の byte 単位の同一性を再 assert する（FR1、FR3、FR4）
- [ ] TS5（新規）: fresh-capture-on-refill の記述が存在すること — 例えば refill / I.2.a のテキストが `RECONCILE_TIP` を「再利用しない」文脈でのみ名指ししていること — を assert する（FR5）
- [ ] TS6（手動 / レビュー）: exit-4 recovery 箇条書きの 6 箇所の列挙を各ステップ本文と突き合わせ、一対一の対応を確認する（FR1、NFR4）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `expected_base_tip` | `commit-docs.sh` の第3引数。呼び出し側の refresh+edit とスクリプト内部の BEFORE_TIP 読み取りの間の窓を閉じる、権威ある staleness チェック |
| exit-4 recovery | `implement-phase.md` の Branch & Worktree Model にある箇条書き。`commit-docs.sh` が exit 4 を返した場合の復旧手順と、その手順に拘束される呼び出し箇所の列挙を持つ |
| start-vs-under-lock チェック | `commit-docs.sh` の二次的な staleness チェック。`expected_base_tip` が渡されない場合のフォールバック |
| refill 経路 | Step I.2.b step 5 が同一ターン内で Step I.2.a に再入する経路 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1（`requirement.approach` / create-spec-run-q0002 の回答、batch codex consultation、record_as_assumption: true）: 是正手段は、共有・抽出されたヘルパー手順でも Branch & Worktree Model の箇条書きだけに置かれた汎用ルールでもなく、Step I.2.a と Step I.3 に書き込まれる明示的なステップシーケンス（Step I.2.b の既存の表現に倣う）とする
- [x] A2（`testing.i3-pin-handling` / create-spec-run-q0002 の回答、batch codex consultation）: Step I.3 の pin は、新しいメカニズムを pin 文の外側に配置することで尊重し、`tests/test_rework_synthesis_contract.py` は編集しない。pin は assertIn の部分文字列チェック（`tests/test_rework_synthesis_contract.py:209-217`）であるため達成可能
- [x] A3（Codex second-opinion レビューによる確立）: `RECONCILE_TIP` は Step I.2.b step 2 で、Step I.2.b step 3 自身のコミットより前に捕捉されるため、refill 経路が Step I.2.a に再入する時点では stale である。FR5 はこれに従う
- [x] A4: tip 変数名 `LAUNCH_TIP`（Step I.2.a）と `COMPLETION_TIP`（Step I.3）は、既存の `BASE_COMMIT` / `RECONCILE_TIP` / `ROUTEBACK_TIP` / `TERMINAL_TIP` の命名に合わせた提案である。名前自体は load-bearing ではなく、その系列と整合する任意の名前が FR2 / FR3 を満たす
- [x] A5: 2 つの新規呼び出しのコミットメッセージは、ドキュメント既存の `docs({feature}): {summary}` 規約に従う。summary の正確な文言は本要件では制約しない
- [x] A6: プロジェクトルートに LICENSE ファイルが存在しないため、SPDX 識別子は記録されず、create-plan の license-consistency チェックは新規依存を照合する対象を持たない。本フィーチャーは依存を導入しないため、このギャップはここでは無害である

### 14.2 未確認・保留事項

なし（`status: tbd` の要件は存在しない）。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: 本変更の対象となるプロトコル文書
- `em-workflow/scripts/commit-docs.sh`: `expected_base_tip` 第3引数と RECOVERY CONTRACT の定義元（変更しない）
- `tests/test_rework_synthesis_contract.py`: `test_completed_at_commit_wording_is_unchanged`（209-217 行）および `test_regression_precondition_stated_before_launch_selection`（変更しない）

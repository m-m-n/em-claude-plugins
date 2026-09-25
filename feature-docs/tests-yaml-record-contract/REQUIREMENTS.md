---
title: "tests-yaml-record-contract"
created_date: 2026-09-25
status: draft
---

# tests-yaml-record-contract - 要件定義書

## 1. 概要

### 1.1 背景
implementer が書く `test-docs/{feature}/{task}.tests.yaml` で、`final_failures` と `red_confirmed` の記録が `em-workflow/agents/implementer.md` Step 4c の契約から外れていた。

- `final_failures` のコメントに、`baseline_failures` と同一の実行結果（件数・経過時間まで一致）が記録されていた。
- `notes` で `red_confirmed` の意味をローカルに再定義し、実行可能な red を観測していない criterion をすべて `tests: []` かつ `red_confirmed: true` にしていた。

### 1.2 目的
- implementer が書く `test-docs/{feature}/{task}.tests.yaml` を、後続タスク・verify・`unconfirmed_reds` 集計が機械的に読んでも失敗の帰属を誤らない証跡にする。
- 実行可能な red が存在しないタスク（ドキュメント型タスク等）での tests.yaml の書き方を、implementer が自分で解釈を作らずに済むよう契約側（`em-workflow/agents/implementer.md` Step 4c）に明記する。
- `final_failures` が実際に観測した実行結果か、再実行せず baseline を継承したものかを記録から区別できるようにする。

### 1.3 スコープ
- `em-workflow/agents/implementer.md` Step 4c / Step 6 の記述変更
- 上記の規定を固定する document-contract テストの追加（`tests/` 配下）
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version 更新

スコープ外は「14.1 確認済み事項」の前提（ASM-3〜ASM-5）を参照。

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 目的と同じ。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| implementer エージェント | tests.yaml を書く |
| 後続タスク・verify フェーズ・`unconfirmed_reds` 集計 | tests.yaml を読む |

### 2.3 期待される効果
- tests.yaml の `red_confirmed` / `final_failures` が、実際に観測した事実だけを表す。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 実行可能な red が存在しない criterion の記録形式 | Step 4c に `tests: []` / `red_confirmed: false` / `red_reason` / `unconfirmed_reds` の記録形式を明記する | 高 |
| FR2 | `red_confirmed: true` の意味の固定とローカル再定義の禁止 | Step 4c に `red_confirmed: true` の意味と、フィールド意味のローカル再定義禁止を明記する | 高 |
| FR3 | `red_confirmed: false` の報告先を `unconfirmed_reds` に揃える | Step 4c の報告先記述を Step 7 の `unconfirmed_reds` に揃える | 高 |
| FR4 | `final_failures` の記録規律（コメント形式） | Step 4c に `final_failures` の記録規律を定める | 高 |
| FR5 | 親側採用後の再実行の必須化 | Step 6 の親側採用後は必ず再実行すると明記する | 高 |
| FR6 | document-contract テスト | FR1〜FR5 の規定を固定するテストを追加する | 高 |
| FR7 | プラグイン version の更新 | plugin.json と marketplace.json の version を patch 単位で上げる | 高 |

### 4.2 機能詳細

#### FR1: 実行可能な red が存在しない criterion の記録形式

**説明**: `em-workflow/agents/implementer.md` Step 4c は、失敗させられる実行可能な検査（テスト・ビルド・lint 等）が存在しない Acceptance Criterion について、`tests: []`、`red_confirmed: false`、`red_reason` に実行可能な red が存在しない理由を書き、報告の `unconfirmed_reds` に載せる、と明記する。ドキュメントのみを成果物とするタスクはこの規定の対象として名指しする。

#### FR2: `red_confirmed: true` の意味の固定とローカル再定義の禁止

**説明**: Step 4c は、`red_confirmed: true` が「実装が存在しない状態で、実行した検査が失敗するのを実際に観測した」ことだけを意味すると明記する。文書やアンカーを読んだこと・探したことは red の観測に当たらないと明記する。`tests` / `red_confirmed` / `red_reason` の意味を `notes` その他の記述でローカルに再定義することを禁止する。

#### FR3: `red_confirmed: false` の報告先を `unconfirmed_reds` に揃える

**説明**: Step 4c の `red_confirmed: false` の criterion を「report の notes に載せる」とする現行の記述を、Step 7 の報告フィールド `unconfirmed_reds` に載せる記述に揃える。

#### FR4: `final_failures` の記録規律（コメント形式）

**説明**: Step 4c は `final_failures` の記録規律を定める。tests.yaml にキーは追加せず、`final_failures` のコメントに書く。

**ビジネスルール**:
- (a) コメントには実装後に実際に再実行した回の出力を書く。
- (b) 再実行を省けるのは、スイートが読むファイル（ソース・テスト・テストが読むドキュメント）を一切変更していない場合だけとする。その場合は「再実行せず baseline を継承」と理由付きでコメントに書き、報告にも再実行していないことを明記する。
- (c) 省略条件を満たすことを確認できなければ再実行する。
- (d) 同一の実行結果を 2 つの独立した観測であるかのように `baseline_failures` と `final_failures` の両方に書かない。

#### FR5: 親側採用後の再実行の必須化

**説明**: Step 6 の親側採用（parent-side adoption）後は、FR4 (b) の省略条件を適用せず、必ずスイートを再実行して `baseline_failures` と `final_failures` を更新する、と明記する。

#### FR6: document-contract テスト

**説明**: FR1〜FR5 で Step 4c / Step 6 に書いた規定を固定する document-contract テストを `tests/` 配下に追加する。テストは `em-workflow/agents/implementer.md` を読み、各規定の存在を検査する。

#### FR7: プラグイン version の更新

**説明**: `em-workflow/.claude-plugin/plugin.json` の version と `.claude-plugin/marketplace.json` の em-workflow エントリの version を、同じ変更の中で同じ値に patch 単位で上げる。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし。

### 5.2 セキュリティ要件
該当なし。

### 5.3 可用性要件
該当なし。

### 5.4 保守性要件
- NFR1: tests.yaml のスキーマ（キー構成）は変更しない。`final_failures` の再実行有無はコメントで表す。
- NFR2: tests.yaml を機械検証する仕組み（バリデータ・フック）は追加しない。
- NFR3: tests.yaml 契約の所有者は `em-workflow/agents/implementer.md` Step 4c のままとし、他の文書に同じ規定を重複させない。
- NFR4: テストは Python 標準ライブラリ unittest のみを使い、`tests/test_*.py` に置く（`test/README.md` の規約）。
- NFR5: 既存テストスイート（`python3 -m unittest discover -s tests`）にリグレッションを出さない。

### 5.5 互換性要件
- NFR1 を参照。

## 6. UI/UX要件

該当なし。

## 7. データ要件

該当なし（tests.yaml のキー構成は変更しない。NFR1）。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- NFR1〜NFR4 を参照。

### 9.2 ビジネス上の制約
- なし。

### 9.3 スケジュール制約
- なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/tests-yaml-record-contract/**`
- `test-docs/tests-yaml-record-contract/**`

`feature-docs/tests-yaml-record-contract/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/tests-yaml-record-contract/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/tests-yaml-record-contract/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし。

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1）: `implementer.md` Step 4c に、実行可能な検査が存在しない criterion は `tests: []`、`red_confirmed: false`、`red_reason` に理由、報告の `unconfirmed_reds` に記載、と書かれており、ドキュメントのみを成果物とするタスクがその対象として名指しされている
- [ ] AC-2（FR2）: Step 4c に、`red_confirmed: true` は実行した検査の失敗を実装前に観測したことだけを意味すること、文書を読んだことは red の観測に当たらないこと、`tests` / `red_confirmed` / `red_reason` の意味を `notes` 等でローカルに再定義してはならないことが書かれている
- [ ] AC-3（FR3）: Step 4c が `red_confirmed: false` の criterion の報告先として `unconfirmed_reds` を指しており、`notes` を指す記述が残っていない
- [ ] AC-4（FR4）: Step 4c に、`final_failures` のコメントに実際に再実行した回の出力を書くこと、再実行を省けるのはスイートが読むファイル（ソース・テスト・テストが読むドキュメント）を一切変更していない場合だけであること、省く場合は「再実行せず baseline を継承」と理由付きで書き報告にも明記すること、省略条件を確認できなければ再実行することが書かれている
- [ ] AC-5（FR4）: Step 4c に、同一の実行結果を `baseline_failures` と `final_failures` の 2 つの独立した観測として提示してはならないことが書かれている
- [ ] AC-6（FR5）: Step 6 に、親側採用後は再実行の省略条件を適用せず必ず再実行することが書かれている
- [ ] AC-7（FR6）: `tests/` 配下の document-contract テストが AC-1〜AC-6 の規定を検査し、変更前の `implementer.md` に対して失敗し、変更後に成功する
- [ ] AC-8（FR7）: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version が同じ値で、変更前より patch 単位で上がっている
- [ ] AC-9（NFR5）: `python3 -m unittest discover -s tests` がリグレッションなしで通る

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC-1）: `implementer.md` の Step 4c 節を抽出し、実行可能な検査が存在しない場合の `tests: []` / `red_confirmed: false` / `red_reason` / `unconfirmed_reds` の規定と、ドキュメントのみのタスクへの言及が含まれることを検査する
- [ ] TS-2（AC-2）: Step 4c 節に `red_confirmed: true` の意味（実行した検査の失敗の観測）、文書を読むことは観測に当たらないこと、フィールド意味のローカル再定義禁止が含まれることを検査する
- [ ] TS-3（AC-3）: Step 4c 節で `red_confirmed: false` の報告先が `unconfirmed_reds` であり、「notes に載せる」旨の記述が無いことを検査する
- [ ] TS-4（AC-4, AC-5）: Step 4c 節に `final_failures` の再実行出力の記録、省略条件（スイートが読むファイルの未変更）、省略時の「baseline を継承」表記と報告への明記、確認不能時の再実行、同一実行結果の二重提示禁止が含まれることを検査する
- [ ] TS-5（AC-6）: Step 6 節に親側採用後の再実行が省略条件の対象外であることが含まれることを検査する
- [ ] TS-6（AC-7）: document-contract テストを `implementer.md` の変更前に実行して失敗を観測し、変更後に成功することを確認する
- [ ] TS-7（AC-8）: plugin.json と marketplace.json の em-workflow version が一致し、変更前の値より patch 単位で大きいことを確認する
- [ ] TS-8（AC-9）: `python3 -m unittest discover -s tests` をリポジトリルートで実行し、リグレッションが無いことを確認する

### 12.2 エッジケース
- 1 タスクの中で、実行可能なテストがある criterion と無い criterion が混在する場合は、criterion ごとに FR1 / 通常の規定を適用する。
- ビルドや lint の結果を検証手段とする criterion は、実装前にその検査の失敗を実際に観測した場合に限り `red_confirmed: true` とする。
- ドキュメントだけを変更するタスクでも、そのドキュメントを読む document-contract テストを書ける場合は実行可能な red があるので通常の規定に従う。
- テストが読むドキュメントを変更したタスクは、`final_failures` の再実行を省けない。
- 変更したファイルがスイートに読まれるかを確認できない場合は再実行する。
- Step 6 のコンフリクトループでは、毎回の親側採用後に再実行する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 実行可能な red | 実装が存在しない状態で、実行した検査（テスト・ビルド・lint 等）が失敗すること |
| 親側採用（parent-side adoption） | `implementer.md` Step 6 が定める処理 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] `final_failures` の記録形式: キーは増やさずコメント形式。`final_failures` のコメントには再実行した回の実出力を書く。再実行を省けるのはスイートが読むファイル（ソース・テスト・テストが読むドキュメント）を一切変えていない場合だけで、その場合は「再実行せず baseline を継承」と理由付きで書き、report にも未実行を明記する。Step 6 の親側採用後は必ず再実行する。省略条件を確認できなければ再実行する。
- [x] design ステップ: skipped（UI や視覚的な成果物を含まない。エージェント定義文書・テスト・マニフェストの変更のみ）。

前提事項:

- [x] ASM-1: `final_failures` の記録形式は create-spec-q0001 の回答（comment_rerun_required_unless_untouched）に従い、キーを増やさずコメント形式とする。
- [x] ASM-2: 再実行を省いたことを報告に明記する先は、Step 7 報告の既存フィールド `notes` とする（報告スキーマにフィールドは追加しない）。
- [x] ASM-3: 既存の実例 `test-docs/i2c-routeback-reconciliation/task0001.tests.yaml` は修正しない。完了の定義が `implementer.md` の契約と document-contract テストに限られているため。
- [x] ASM-4: `em-workflow/skills/tdd-testing/SKILL.md` と `em-workflow/skills/worktree-task-workflow/SKILL.md` は変更しない。tests.yaml 契約の SSOT は `implementer.md` Step 4c である。
- [x] ASM-5: `em-workflow/references/implement-phase.md` の `tests_yaml_path` の説明（`baseline_failures` / `final_failures` と、criterion ごとに観測した red の AC → test 対応）は変更後の契約と矛盾しないため、変更しない。
- [x] ASM-6: version の上げ幅は patch とする（基準時点では 0.2.8 → 0.2.9。実装時点でほかの変更により値が進んでいれば、その値から patch で上げる）。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `em-workflow/agents/implementer.md` Step 4c / Step 6 / Step 7
- `em-workflow/references/implement-phase.md`

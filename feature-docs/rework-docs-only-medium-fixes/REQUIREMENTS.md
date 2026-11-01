---
title: "rework-docs-only-medium-fixes"
created_date: 2026-11-01
status: draft
---

# rework-docs-only-medium-fixes - 要件定義書

## 1. 概要

### 1.1 背景
rework-docs-only-task-routing の review round 1 で、medium 指摘 4 件（c588505add1da8c7 / 33f072c3b90c3aea / 6ed87da72e3f5de3 / a3ac237a09af8436）が残っている。

### 1.2 目的
`em-workflow/scripts/validate-worker-output.py` の文書のみの回・シナリオ ID 改名・tests 参照置換の検査を SSOT の規則に揃え、上記 4 件の medium 指摘を解消する。

### 1.3 スコープ
- `em-workflow/scripts/validate-worker-output.py` の検査（FR1〜FR4、NFR1）
- SSOT 文書の記述（FR5）
    - `em-workflow/references/rework-task-synthesis.md` Section 12
    - `em-workflow/references/contracts/rework-planner-contract.md` の check 2
    - `em-workflow/references/workflow-patch.md` の Tests replacement 節
- `em-workflow/references/fixtures/` 配下の fixture と、それを検査するテスト（FR6、FR7）

対象外:
- 完了済み feature の文書（`feature-docs/rework-docs-only-task-routing/` の THREAT-MODEL の TM-5、SPEC.md、reviews/round1.yaml）は変更しない。

## 2. ビジネス要件

### 2.1 ビジネス目標
- `em-workflow/scripts/validate-worker-output.py` の文書のみの回・シナリオ ID 改名・tests 参照置換の検査を SSOT の規則に揃え、rework-docs-only-task-routing の review round 1 で残った medium 指摘 4 件（c588505add1da8c7 / 33f072c3b90c3aea / 6ed87da72e3f5de3 / a3ac237a09af8436）を解消する。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 上記 medium 指摘 4 件が解消される。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 改名による受理は文書の差分で裏付ける（c588505add1da8c7） | 改名 pair による covered_by_existing の受理を、変更後と baseline の VERIFICATION.md の差分で確かめる | - |
| FR2 | 改名で消えた旧 ID を受理しない（33f072c3b90c3aea） | 改名 pair の from、および変更後 VERIFICATION.md に無い ID を covered_by_existing として受理しない | - |
| FR3 | 文書のみの回の step_patches を SSOT の規則どおりに検査する（6ed87da72e3f5de3） | entries が空の append_rework の step_patches を、起点ステップ 1 件・status pending に限る | - |
| FR4 | from と to が重なる tests_replace を拒否する（a3ac237a09af8436） | tests_replace の from 集合と to 集合の重なりを拒否する | - |
| FR5 | SSOT を検査規則に揃える | FR1〜FR4 の規則を SSOT 3 文書に書く | - |
| FR6 | 拒否例の fixture とテスト | FR1〜FR4 の invalid- fixture とテストを足す | - |
| FR7 | 既存の成功例 fixture を受理し続ける | 既存の valid- fixture をすべて受理し続ける | - |

### 4.2 機能詳細

#### FR1: 改名による受理は文書の差分で裏付ける（c588505add1da8c7）

**説明**: rework_index の covered_by_existing のうち verification_index のキーでない ID を、payload.doc_corrections[].scenario_renames の申告済み pair で受理するのは、次の条件がすべて成り立つときに限る。

- pair の from が verification_index のキーである
- `--feature-dir` と `--baseline-dir` の両方が与えられ、feature-dir に VERIFICATION.md がある
- to が変更後 VERIFICATION.md の ID 集合にある
- from が baseline VERIFICATION.md の ID 集合にある
- from が変更後 VERIFICATION.md の ID 集合にない

**ビジネスルール**:
- どちらかのディレクトリが無いとき、または feature-dir に VERIFICATION.md が無いときは、改名による受理をせず rework-index で拒否する（fail-closed）。
- このときのメッセージは、文書の差分が取れないために改名を確かめられないことを示し、改名の申告が無い場合のメッセージと区別できる。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| rework-index | 上記条件のいずれかが成り立たない | 拒否する |
| rework-index | ディレクトリが無い、または feature-dir に VERIFICATION.md が無い | 改名による受理をせず拒否し、差分が取れない旨のメッセージを出す |

#### FR2: 改名で消えた旧 ID を受理しない（33f072c3b90c3aea）

**説明**: 申告済みの改名 pair の from である ID は、verification_index のキーであっても covered_by_existing として受理せず、rework-index で拒否する。

**ビジネスルール**:
- `--feature-dir` と `--baseline-dir` の両方が与えられ feature-dir に VERIFICATION.md があるときは、covered_by_existing の各 ID が変更後 VERIFICATION.md の ID 集合にあることを求め、無い ID を rework-index で拒否する。改名に関係しない ID にも適用する。
- どちらのディレクトリも無い場合に、改名に関係しない verification_index のキーの ID を受理する既存の動作は変えない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| rework-index | covered_by_existing に申告済み改名 pair の from がある | 拒否する |
| rework-index | 差分が取れるとき、covered_by_existing の ID が変更後 VERIFICATION.md に無い | 拒否する |

#### FR3: 文書のみの回の step_patches を SSOT の規則どおりに検査する（6ed87da72e3f5de3）

**説明**: operation が append_rework で tasks_patch.entries が無いか空の patch は、step_patches がちょうど 1 件で、その step_id が起点ステップで、set.status が pending であるときだけ受理する。

**ビジネスルール**:
- 起点ステップは、入力 envelope に rework_source.type があるときはその値と一致しなければならない。
- 起点ステップが得られないとき（`--kind workflow-patch` 単体、または envelope に rework_source.type が無いとき）は、verify か review のどちらかでなければならない。新しい envelope フィールドは足さない。
- envelope の rework_source が mapping でない、または type があって review / verify 以外の値のときは、起点ステップの照合を満たせないものとして拒否する（fail-closed）。
- implement を対象にする entry は、set.status の値によらず拒否する。
- step_patches が 0 件、2 件以上、起点以外の step を含む、set.status が pending 以外、のいずれも拒否する。
- 検査は `--dry-run-apply` の有無によらず構造検査として行い、`--kind worker-result` と `--kind workflow-patch` の両方の経路で効く。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| docs-only-implement-reset | implement を対象にする entry がある | 拒否する |
| docs-only-implement-reset と区別できるコード | step_patches の件数・起点・status の違反 | 拒否する |

#### FR4: from と to が重なる tests_replace を拒否する（a3ac237a09af8436）

**説明**: requirements_patch の 1 つの entry の set.tests_replace で、from の集合と to の集合に共通する ID があるときは、構造検査で requirements_patch として拒否する。

**ビジネスルール**:
- 連鎖（TS-1→TS-2 と TS-2→TS-3）と入れ替え（TS-1→TS-2 と TS-2→TS-1）がどちらも対象になる。
- `--dry-run-apply` の有無によらず拒否する。
- 複数の pair が同じ to を持つ tests_replace（TS1→X, TS2→X）は FR4 の対象外とし、既存の「to が既にあれば from を消す」適用規則のままにする。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| requirements_patch | 1 つの entry の tests_replace で from 集合と to 集合が重なる | 拒否する |

#### FR5: SSOT を検査規則に揃える

**説明**: FR1〜FR4 の規則を次の SSOT に書く。

- `em-workflow/references/rework-task-synthesis.md` Section 12 の Rename-aware coverage の項
- 同 Section 12 の、tasks_patch.entries が空の append_rework patch の項（step_patches は起点ステップ 1 件で set.status は pending、起点の照合元）
- `em-workflow/references/contracts/rework-planner-contract.md` の check 2
- `em-workflow/references/workflow-patch.md` の Tests replacement 節（from と to の重なりの禁止）

#### FR6: 拒否例の fixture とテスト

**説明**: FR1〜FR4 のそれぞれについて、不正な出力を拒否する invalid- fixture と、それを検査するテストを足す。

- FR1: 架空の to（変更後 VERIFICATION.md に無い ID）を申告した改名と、差分を取れない（`--feature-dir` / `--baseline-dir` が無い）改名申告
- FR2: 申告した改名の from を covered_by_existing に挙げた出力
- FR3: implement を pending 以外の status にする entry、step_patches が空、起点以外の step が混ざる、起点の set.status が pending 以外、envelope の rework_source.type と step_id が食い違う、の各ケース
- FR4: 連鎖と入れ替え

**ビジネスルール**:
- tests_replace を含む fixture は、rework-planner の 6 件（test_ac6_no_fixture_uses_tests_replace が対象にするもの）以外に置く。
- 報告コードが増える既存の invalid- fixture（例: invalid-docs-only-round-resets-implement、step_patches が implement と review の 2 件）は、tests 側の期待コードを更新してよい。

#### FR7: 既存の成功例 fixture を受理し続ける

**説明**: `em-workflow/references/fixtures/` 配下の既存の valid- fixture はすべて受理され続ける。

**ビジネスルール**:
- valid-mixed-round-renamed-scenario-declared には feature-dir/VERIFICATION.md（TS-3 を含み TS3 を含まない）と baseline-dir/VERIFICATION.md（TS3 を含む）を足し、FR1 の条件を満たすようにする。
- `tests/test_rework_docs_only_validator_rules.py` の TestFixtures._run は、fixture に feature-dir / baseline-dir があればそれを `--feature-dir` / `--baseline-dir` として渡す。
- 既存の valid-docs-only-round の envelope は rework_source を持たないため、FR3 の起点ステップは verify か review を求める扱いで受理される。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- 入力検証（NFR1 不正な入力で例外を出さない）: FR1〜FR4 で足す検査は、形の崩れた入力（rework_source が mapping でない、type が文字列でない、step_patches の要素が mapping でない、tests_replace の pair が崩れている、VERIFICATION.md が読めない形など）に対しても例外を出さず、エラーとして報告する。CLI は終了コード 1 と JSON のエラー詳細を返し、2 にならない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2 テストは標準ライブラリだけを使う: 追加・変更するテストは Python 標準ライブラリの unittest だけを使い、サードパーティのパッケージを import しない。
- NFR3 テストスイート全体が通る: `python3 -m unittest discover -s tests` がリポジトリルートから通る。

### 5.5 互換性要件
- FR2: どちらのディレクトリも無い場合に、改名に関係しない verification_index のキーの ID を受理する既存の動作は変えない。
- FR7: 既存の valid- fixture はすべて受理され続ける。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR2: テストは Python 標準ライブラリの unittest だけを使う。
- 新しい envelope フィールドは足さない。

### 9.2 ビジネス上の制約
- 完了済み feature の文書（`feature-docs/rework-docs-only-task-routing/` の THREAT-MODEL の TM-5、SPEC.md、reviews/round1.yaml）は変更しない。
- em-workflow の version は手で上げない。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/rework-docs-only-medium-fixes/**`
- `test-docs/rework-docs-only-medium-fixes/**`

`feature-docs/rework-docs-only-medium-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/rework-docs-only-medium-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/rework-docs-only-medium-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/rework-docs-only-medium-fixes/` ディレクトリを生成しないが、宣言された `test-docs/rework-docs-only-medium-fixes/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: FR1〜FR4 の 4 件それぞれについて、不正な出力を拒否する invalid- fixture とテストがあり、validator がそれを終了コード 1 で拒否する（FR1, FR2, FR3, FR4, FR6）
- [ ] AC-2: 既存の valid- fixture がすべて引き続き終了コード 0 で受理される（valid-mixed-round-renamed-scenario-declared は feature-dir / baseline-dir を足した状態で）（FR7）
- [ ] AC-3: rework-task-synthesis.md Section 12、rework-planner-contract.md の check 2、workflow-patch.md の Tests replacement 節が FR1〜FR4 の規則を述べている（FR5）
- [ ] AC-4: `python3 -m unittest discover -s tests` が通る（NFR1, NFR2, NFR3）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: TS-6 3 条件を満たす改名申告（baseline に TS3、変更後に TS-3 があり TS3 が無い）は受理される（FR1, FR7）
- [ ] 正常系: TS-9 ディレクトリが無いとき、改名に関係しない verification_index のキーの ID は従来どおり受理される（FR2）
- [ ] 正常系: TS-15 envelope が無いとき、step_id が verify または review の 1 件で set.status が pending なら受理され、それ以外の step_id は拒否される（FR3）
- [ ] 正常系: TS-19 from と to が重ならない複数 pair（valid-docs-only-round の TS1→TS-1, TS2→TS-2）は受理される（FR4, FR7）
- [ ] 正常系: TS-20 既存の valid- fixture がすべて終了コード 0 で受理される（FR7）
- [ ] 正常系: TS-22 SSOT 3 文書が FR1〜FR4 の規則を述べている（FR5）
- [ ] 異常系: TS-1 改名申告の to が変更後 VERIFICATION.md に無いと拒否される（架空の to、例 TS3→TS-9999）（FR1）
- [ ] 異常系: TS-2 改名申告の from が変更後 VERIFICATION.md に残っていると拒否される（FR1）
- [ ] 異常系: TS-3 改名申告の from が baseline VERIFICATION.md に無いと拒否される（FR1）
- [ ] 異常系: TS-4 `--feature-dir` か `--baseline-dir` が無いと改名による受理をせず拒否し、差分が取れない旨のメッセージを出す（FR1）
- [ ] 異常系: TS-5 feature-dir に VERIFICATION.md が無いと改名による受理をせず拒否する（FR1）
- [ ] 異常系: TS-7 申告した改名の from（TS3）を covered_by_existing に挙げると、verification_index のキーであっても拒否される（FR2）
- [ ] 異常系: TS-8 差分が取れるとき、変更後 VERIFICATION.md に無い covered_by_existing の ID は拒否される（FR2）
- [ ] 異常系: TS-10 entries が空の append_rework で implement を completed にする entry が拒否される（FR3）
- [ ] 異常系: TS-11 entries が空の append_rework で step_patches が空だと拒否される（FR3）
- [ ] 異常系: TS-12 entries が空の append_rework で step_patches が 2 件以上（起点以外の step が混ざる）だと拒否される（FR3）
- [ ] 異常系: TS-13 entries が空の append_rework で起点ステップの set.status が pending 以外（例 completed）だと拒否される（FR3）
- [ ] 異常系: TS-14 envelope の rework_source.type が verify なのに step_id が review（またはその逆）だと拒否される（FR3）
- [ ] 異常系: TS-16 FR3 の拒否が `--dry-run-apply` の有無、`--kind worker-result` / `workflow-patch` のどちらでも起きる（FR3）
- [ ] 異常系: TS-17 tests_replace の連鎖（TS-1→TS-2, TS-2→TS-3）が requirements_patch で拒否される（FR4）
- [ ] 異常系: TS-18 tests_replace の入れ替え（TS-1→TS-2, TS-2→TS-1）が requirements_patch で拒否される（FR4）
- [ ] 異常系: TS-21 形の崩れた rework_source / step_patches / tests_replace / VERIFICATION.md が例外にならず終了コード 1 で報告される（NFR1）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 文書のみの回 | operation が append_rework で tasks_patch.entries が無いか空の patch |
| 起点ステップ | 文書のみの回の step_patches が対象にする step。envelope に rework_source.type があればその値、無ければ verify か review |
| 差分が取れる | `--feature-dir` と `--baseline-dir` の両方が与えられ、feature-dir に VERIFICATION.md があること |
| fail-closed | 判定に必要な情報が得られないときに拒否すること |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 改名による受理で文書の差分が取れないとき（requirement.rename-coverage.no-diff）: fail-closed で拒否する（fail_closed）
- [x] 文書のみの回の起点ステップ（requirement.docs-only-step-patches.origin-step）: 入力 envelope に rework_source.type があるときはそれと一致させ、無いとき（`--kind workflow-patch` 単体、または envelope が rework_source.type を持たないとき）は verify か review を求める。新しい envelope フィールドは足さない（match_origin）。既存の valid-docs-only-round の envelope は rework_source を持たないため、後者の扱いで受理される
- [x] 完了済み feature の文書の扱い（requirement.scope.past-feature-docs）: `feature-docs/rework-docs-only-task-routing/` の THREAT-MODEL の TM-5、SPEC.md、reviews/round1.yaml は変更しない。TM-5 の更新は残件として扱う（references_only）

### 14.2 前提

- [x] A3: envelope の rework_source が mapping でない、または type があって review / verify 以外の値のときは、起点ステップの照合を満たせないものとして拒否する（fail-closed）
- [x] A5: FR2 の「差分が取れるときは covered_by_existing の各 ID が変更後 VERIFICATION.md にあることを求める」は、review の提案（round1.yaml 33f072c3b90c3aea の suggestion）に従って、改名に関係しない ID にも適用する
- [x] A6: エラーコードは、改名・カバレッジの拒否が rework-index、tests_replace の重なりが requirements_patch。文書のみの回で implement を対象にする entry は既存の docs-only-implement-reset を使い、件数・起点・status の違反はそれと区別できるコードで報告する。報告コードが増える既存の invalid- fixture（invalid-docs-only-round-resets-implement など）は、tests 側の期待コードを更新してよい（AC-2 が守るのは valid- fixture だけ）
- [x] A7: PR #50（rework-docs-only-task-routing）はマージ済みで、この integration ブランチの基点に含まれている
- [x] A8: em-workflow の version は手で上げない（minor / major に当たらない）
- [x] A9: 複数の pair が同じ to を持つ tests_replace（TS1→X, TS2→X）は from と to の重なりに当たらないため FR4 の対象外とし、既存の「to が既にあれば from を消す」適用規則のままにする

### 14.3 未確認・保留事項
- [ ] `feature-docs/rework-docs-only-task-routing/` の THREAT-MODEL の TM-5 の更新（残件）

## 15. 参考資料

- `em-workflow/references/rework-task-synthesis.md`: Section 12
- `em-workflow/references/contracts/rework-planner-contract.md`: check 2
- `em-workflow/references/workflow-patch.md`: Tests replacement 節
- `feature-docs/rework-docs-only-task-routing/reviews/round1.yaml`: medium 指摘 4 件の出典

---
title: "spec-change-rework-reentry"
created_date: 2026-11-11
status: draft
---

# spec-change-rework-reentry - 要件定義書

## 1. 概要

### 1.1 背景
rework の SPEC変更遷移を経たフィーチャーは、無人の `--batch` 実行において、自動リトライでは解消できない 2 つの停止に当たる。

- implement の Step I.0 による ABORT
- 古い `verify: failed` に対して停止条件 3 が発火すること

### 1.2 目的
- rework の SPEC変更遷移を経たフィーチャーが、`--batch` 実行と対話実行のどちらでも、`workflow.yaml` を誰も手で編集せずに review → verify → retrospect まで進む。
- 無人の `--batch` 実行で自動リトライでは解消できない 2 つの停止（implement Step I.0 の ABORT と、古い `verify: failed` に対する停止条件 3 の発火）を取り除く。

### 1.3 スコープ
- 対象: SPEC変更遷移の手順 2（3 文書）、implement-phase.md Step I.0 の Re-entry precondition、rework-task-synthesis.md Section 11 の Invariant 1、develop/SKILL.md「verify フェーズ」の項目 6、tests/ 配下のテスト。
- 対象外: tier-upgrade の手順（A7）、停止条件 3 そのもの（A8）、batch の verify カウンター `batch.verify_rework.*`（A6）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- rework の SPEC変更遷移を経たフィーチャーが、`--batch` 実行と対話実行のどちらでも、`workflow.yaml` を誰も手で編集せずに review → verify → retrospect まで進む。
- 無人の `--batch` 実行で自動リトライでは解消できない 2 つの停止を取り除く。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の実行者 | `--batch` 実行または対話実行でフィーチャーを進める |

### 2.3 期待される効果
- SPEC変更遷移の後、implement Step I.0 の ABORT で止まらない。
- SPEC変更遷移の後、古い `verify: failed` に対して停止条件 3 が発火しない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | SPEC変更遷移の後、手編集なしで retrospect まで進む | em-workflow の実行者（`--batch` / 対話） | 高 |

### 3.2 ユースケース詳細

#### UC01: SPEC変更遷移の後、手編集なしで retrospect まで進む

**アクター**: em-workflow の実行者（`--batch` / 対話）

**事前条件**:
- rework-planner が `gate_id` `rework.spec-change` を返し、SPEC変更遷移が選ばれている。

**基本フロー**:
1. SPEC変更遷移が create-plan / implement / review / verify を pending に戻す（FR1）。
2. create-spec → create-plan が再実行される。
3. implement が pending のまま進入し、Step I.0 が SPEC変更再進入として認識する（FR2）。
4. pending タスクが 0 件の場合、implementer を起動せず、Step I.3 で implement を completed にする（FR3）。
5. review → verify → retrospect へ進む。

**代替フロー**:
- 再計画で新しいタスクが 1 件以上登録された場合は、通常どおり Step I.2 を実行する（FR3）。
- SPEC変更再進入ではない非初回進入で、pending タスクも failed タスクも無い場合は、現行どおり即座に ABORT する（FR4）。

**事後条件**:
- `workflow.yaml` を手で編集せずに、フィーチャーが review → verify → retrospect まで進んでいる。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | SPEC変更遷移で verify も pending に戻す | 遷移の手順 2 に verify を加える | 高 |
| FR2 | Step I.0 が SPEC変更再進入を正当な進入経路として認識する | Re-entry precondition に経路を追加する | 高 |
| FR3 | タスク 0 件の SPEC変更再進入はフェーズ完了へ直行する | Step I.2 を飛ばして Step I.3 へ進む | 高 |
| FR4 | それ以外の状態では ABORT を維持する | 現行の即時 ABORT を残す | 高 |
| FR5 | Invariant 1 の対象範囲を明記する | SPEC変更遷移を対象外とする | 高 |
| FR6 | develop スキルからの相互参照 | verify も pending に戻ることを引用する | 中 |
| FR7 | 再発を検知するテスト | 2 つの停止の再発を検知する unittest を追加する | 高 |
| FR8 | 影響を受ける既存の固定テストを更新する | 文言・ダイジェスト・件数の固定を新しい文言に合わせる | 高 |

### 4.2 機能詳細

#### FR1: SPEC変更遷移で verify も pending に戻す

**説明**: SPEC変更遷移の手順 2（rework-task-synthesis.md Section 10 の `When rework needs a SPEC.md change` ブロック）を、create-plan / implement / review → pending から、create-plan / implement / review / verify → pending に変更する。rework-planner-contract.md の `## Specification-change transition` にある 5 手順の手順 2、および agents/rework-planner.md の `## Specification-change transition` にある 5 手順の要約にも、同じ変更を入れる。手順数 5 と番号付け（1〜5）は維持する。

**ビジネスルール**:
- verify を pending に戻すのは、orchestrator の遷移書き込みで行う（worker のパッチではない）。設定するのは status だけで、verify の result / failed_items は verify の再実行時に上書きされる（A4）。
- review 起点の SPEC変更では verify は通常すでに pending のため、FR1 の書き込みは効果を持たない。修正は対話実行と batch 実行に同じように適用される（A5）。

#### FR2: Step I.0 が SPEC変更再進入を正当な進入経路として認識する

**説明**: implement-phase.md Step I.0（step 5）の Re-entry precondition の進入経路に、SPEC変更再進入を追加する。これは、SPEC変更遷移（rework-task-synthesis.md Section 10）と、それに続く create-spec → create-plan の再実行の後に、`implement: pending` へ進入する経路である。この経路では、status == pending のタスクが 0 件かつ reconciled state が failed のタスクが 0 件（全タスクが merged）の状態で進入しても、プロトコルエラーではなく、フェーズを ABORT しない。

**ビジネスルール**:
- SPEC変更再進入は、コミット済みの事実だけから識別し、次のすべてが成り立つことを条件とする（A2）。
  1. create-spec と create-plan が completed であり、implement が base_commit と以前の completed_at_commit を持つ。
  2. phase-state/rework.yaml に、`consumed: true` かつ `replan_authorized: false` の spec_change 記録がある。
  3. 以前の implement の completed_at_commit が記録の recorded_at_commit の真の祖先であり、recorded_at_commit が現在の integration の先端の祖先である（タイムスタンプは比較しない）。
  4. その記録を伴う SPEC変更遷移が implement を pending に戻したことを、コミット履歴が示している（tier-upgrade の手順も同じ記録を書くが implement を pending に戻さないため、フラグだけでは足りない）。
  5. タスク集合が空ではなく、全タスクが merged である。
- 同じ再進入の Step I.1 が書いた in_progress からの再開も受け付ける（A2）。

#### FR3: タスク 0 件の SPEC変更再進入はフェーズ完了へ直行する

**説明**: FR2 の経路で pending タスクが無い状態で進入した場合、implementer を起動しない。Step I.2 のタスクループを飛ばし、Step I.3 のフェーズ完了手順（capture → refresh → write → commit）で implement を completed にする。空のキューを待ってターンを終えない。再計画で新しいタスクが 1 件以上登録された場合は、通常どおり Step I.2 を実行する。

**ビジネスルール**:
- タスク 0 件の SPEC変更再進入でも、Step I.1（gitignore guard、base_commit の保持、implement → in_progress のコミット）は通常どおり実行する。飛ばすのは Step I.2 だけで、フェーズは Step I.3 へ進む（A3）。
- Step I.3 は作業が 0 件でも completed_at_commit を更新し、同じ記録が後の再進入に持ち越されないようにする（A3）。

#### FR4: それ以外の状態では ABORT を維持する

**説明**: FR2 の SPEC変更再進入ではない非初回進入で、pending タスクが無く、reconciled state が failed のタスクも無い場合は、現行どおり即座にプロトコルエラーとして ABORT する。SPEC変更再進入の識別は、コミット済みの事実（workflow.yaml と phase-state/rework.yaml の spec_change 記録、および git のコミット祖先関係）だけから行い、セッションの記憶や worker の自然言語出力は使わない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| プロトコルエラー | 非初回進入、SPEC変更再進入ではない、pending タスクが無い、failed タスクが無い | 即座に ABORT する |

#### FR5: Invariant 1 の対象範囲を明記する

**説明**: rework-task-synthesis.md Section 11 の Invariant 1（implement が pending に戻る前に少なくとも 1 件のタスクが登録される）は、SPEC変更遷移を対象としないことを明記する。この遷移はタスクを登録しない（Invariant 9）が、implement を pending に戻す。その再進入の前提条件は implement-phase.md Step I.0 が所有する（引用のみで再掲しない）。新しい不変条件は追加せず、件数は 11 のまま保つ。

#### FR6: develop スキルからの相互参照

**説明**: develop/SKILL.md「verify フェーズ」の項目 6 に、rework-planner が `gate_id` `rework.spec-change` を返し SPEC変更遷移が選ばれた場合、rework-task-synthesis.md Section 10 によって verify も pending に戻ることを、引用として追記する（遷移の内容は再掲しない）。停止条件 3 の発火条件は変えない。

#### FR7: 再発を検知するテスト

**説明**: どちらの停止の再発も検知する unittest のテスト（標準ライブラリのみ）を tests/ 配下に追加する。

- (a) 3 文書すべてで、SPEC変更遷移の手順 2 が verify を含む。
- (b) Step I.0 が、SPEC変更再進入の経路、その経路では pending タスク 0 件でも ABORT しないこと、Step I.3 へ進むことを記載している。
- (c) SPEC変更再進入以外の状態に対する ABORT が残っている。
- (d) Invariant 1 が SPEC変更遷移を対象外として明記している。

このスイートの慣例に従い、各マッチャーには、その記述を欠く合成テキストに対する否定の証明を付ける。

#### FR8: 影響を受ける既存の固定テストを更新する

**説明**: FR1〜FR5 によって固定文字列・ダイジェスト・件数が変わる既存テストを、同じ変更の中で新しい文言に更新する（該当する範囲で tests/test_failed_kind_resume_reentry.py、tests/test_rework_synthesis_contract.py、tests/test_rework_docs_only_route_doc.py、tests/test_worker_contracts_planning.py）。引き続き成り立つアサーションは意味を保つ。これには、不変条件 11 件の件数、5 手順の番号付け、前提条件が起動選択より前に現れることを含む。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1: 既存の所有の分担を保つ。各文書は相手のルールを引用し、再掲しない（Invariant 1 ↔ Step I.0、Section 10 ↔ rework-planner-contract / agents/rework-planner.md、SKILL.md ↔ Section 10）。
- NFR2: em-workflow の version を変更しない（main への push 時に Actions が patch を上げる）。
- NFR3: テストは Python 標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る。
- NFR4: 各文書は既存の言語で書く（implement-phase.md、rework-task-synthesis.md、契約・エージェントのファイルは英語、SKILL.md は日本語）。変更した文書は Notion の URL とホームディレクトリ配下の絶対パスを含まない。

### 5.5 互換性要件
- NFR5: 他の進入経路の既存の振る舞いを変えない。対象は、初回の通過、既存の rework 再進入、batch の infra 自動再開、Step A.6 の failed 進入の復元。

## 6. UI/UX要件

該当なし（Markdown のプロトコル文書と unittest のテストだけで、ユーザーインターフェースを持たない）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 5 章の NFR1〜NFR5 を参照。

### 9.2 ビジネス上の制約
- tier-upgrade の手順は対象外とし、変更しない（A7）。
- 停止条件 3 そのものは変更しない（A8）。
- batch の verify カウンター（`batch.verify_rework.*`）は変更しない（A6）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/spec-change-rework-reentry/**`
- `test-docs/spec-change-rework-reentry/**`

`feature-docs/spec-change-rework-reentry/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/spec-change-rework-reentry/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/spec-change-rework-reentry/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/spec-change-rework-reentry/` ディレクトリを生成しないが、宣言された `test-docs/spec-change-rework-reentry/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 3 文書すべてで、SPEC変更遷移の手順 2 が verify を含み、5 手順の番号付けが保たれている。
- [ ] AC2: implement-phase.md Step I.0 が SPEC変更再進入を進入経路として挙げ、pending タスク 0 件かつ failed タスク 0 件でその経路に進入しても ABORT しないことを記載している。
- [ ] AC3: Step I.0 が、タスク 0 件の SPEC変更再進入では implementer を起動せず、Step I.3 でフェーズを完了することを記載している。
- [ ] AC4: SPEC変更再進入ではなく、pending タスクも failed タスクも無い非初回進入に対しては、即時の ABORT が引き続き成り立つ。SPEC変更再進入を識別する基準は、コミット済みの事実だけで記述されている。
- [ ] AC5: rework-task-synthesis.md の Invariant 1 が SPEC変更遷移を対象外として挙げ、Step I.0 を引用している。不変条件は引き続き 11 件である。
- [ ] AC6: develop/SKILL.md「verify フェーズ」の 6 が、SPEC変更遷移によって verify が pending に戻ることを引用している。
- [ ] AC7: この変更より前の文言に対して実行すると、新しいテストが FR7 の (a)〜(d) のそれぞれで失敗する。
- [ ] AC8: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: 3 文書から SPEC変更遷移の手順 2 を抜き出し、verify を含むことを確認する（空白は正規化する）（TS-1）。
- [ ] 正常系: implement-phase.md の Step I.0 の節を抜き出し、SPEC変更再進入の経路、pending タスク 0 件で ABORT しないこと、Step I.3 へ進むことの記載を確認する（TS-2）。
- [ ] 正常系: Step I.0 の節に、SPEC変更再進入以外の状態に対する即時の ABORT が残っていることを確認する（TS-3）。
- [ ] 正常系: Section 11 の不変条件が 11 件であり、Invariant 1 が SPEC変更遷移を対象外として挙げ、Step I.0 を引用していることを確認する（TS-4）。
- [ ] 正常系: develop/SKILL.md「verify フェーズ」の項目 6 が、SPEC変更遷移によって verify が pending に戻ることを引用していることを確認する（TS-5）。
- [ ] 正常系: 既存の固定を更新した後、スイート全体と check-plugin-invariants.py が通る（TS-6）。
- [ ] 異常系: 旧来の 3 フェーズの文言が TS-1 のマッチャーで失敗する。現行の 3 経路の文言が TS-2 のマッチャーで失敗する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| SPEC変更遷移 | rework-task-synthesis.md Section 10 の `When rework needs a SPEC.md change` ブロックが定める遷移 |
| SPEC変更再進入 | SPEC変更遷移と、それに続く create-spec → create-plan の再実行の後に、`implement: pending` へ進入する経路 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 修正方針: Step I.0 に SPEC変更再進入の経路を加え（FR2/FR3）、Invariant 1 の対象範囲を明記する（FR5）。再計画でタスクが 0 件のとき create-plan の直後に implement を completed に戻す案は採らない。この案は新しい書き込み主体を要し、2 つの書き込みの間で中断すると同じ停止が残る（A1、Codex 相談で決定）。
- [x] SPEC変更再進入の識別（`create-spec.reentry-identification`）: コミット済みの事実だけから識別し、4.2 FR2 のビジネスルールに挙げた 5 条件すべてを要する。同じ再進入の Step I.1 が書いた in_progress からの再開も受け付ける（A2、Codex 相談で決定）。
- [x] タスク 0 件の SPEC変更再進入でも Step I.1 は通常どおり実行し、飛ばすのは Step I.2 だけとする。Step I.3 は作業 0 件でも completed_at_commit を更新する（A3）。
- [x] verify を pending に戻すのは orchestrator の遷移書き込みで行い、status だけを設定する（A4）。
- [x] review 起点の SPEC変更では verify は通常すでに pending のため、FR1 の書き込みは効果を持たない。修正は対話実行と batch 実行に同じように適用される（A5）。
- [x] batch の verify カウンター（`batch.verify_rework.*`）は変更しない（A6）。
- [x] tier-upgrade の手順は対象外とし、変更しない（A7）。
- [x] 停止条件 3 そのものは変更しない（A8）。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

なし

---
title: "divergence-fail-open-wording"
created_date: 2026-09-25
status: draft
---

# divergence-fail-open-wording - 要件定義書

## 1. 概要

### 1.1 背景
`em-workflow/references/implement-phase.md` の I.2.a にある unlaunched 判定の divergence 段落は、この挙動を 'the hooks are fail-open nets, not authorities' と説明している。同じ文書の Supporting cast にある fail-open 定義（想定外の状態では exit 0 で黙って通す）と、この説明が食い違っている。

タスク: [https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89](https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89)

### 1.2 目的
- em-workflow/references/implement-phase.md の I.2.a にある unlaunched 判定の divergence 段落を、同じ文書の Supporting cast にある fail-open 定義（想定外の状態では exit 0 で黙って通す）と食い違わない表現に直す
- divergence 段落と I.2.b step 1 の reconcile ルールの関係を、どちらを単独で読んでも誤読しない形にする
- tests/test_recycled_task_id_consistency.py で固定している文言を新しい表現に合わせ、対になる negative proof も更新する

### 1.3 スコープ
- `em-workflow/references/implement-phase.md` の I.2.a divergence 段落と I.2.b step 1
- `tests/test_recycled_task_id_consistency.py`
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 の目的と同じ。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| implement-phase.md の読者 | divergence 段落と I.2.b step 1 のどちらか一方だけを読む場合も含む |

### 2.3 期待される効果
- divergence 段落の説明が、Supporting cast の fail-open 定義と食い違わない
- divergence 段落と I.2.b step 1 のどちらを単独で読んでも、`status != merged` がどこで効くかを誤読しない

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | divergence の正当化を fail-open 以外の語で書き直す | divergence 段落から fail-open の説明を取り除き、根拠と有界化を明示する | 高 |
| FR2 | divergence 段落で I.2.b step 1 との関係を述べる | reconcile の status 無参照の分類と、`status != merged` が効く場所を書く | 高 |
| FR3 | I.2.b step 1 に注記を足す | 『no event → unlaunched』に status 無参照と除外の適用箇所の注記を足す | 高 |
| FR4 | 固定文言とテストを更新する | 固定句・正の assertion・テストメソッド名・negative proof を更新する | 高 |
| FR5 | em-workflow の version を上げる | 0.2.7 から 0.2.8 に上げる | 高 |

### 4.2 機能詳細

#### FR1: divergence の正当化を fail-open 以外の語で書き直す

**説明**: I.2.a の divergence 段落（統合 worktree の em-workflow/references/implement-phase.md の 298-308 行、'The other three queue hooks detect a task as **unlaunched** solely from ...' で始まる段落）から、'the hooks are fail-open nets, not authorities' という句と、この挙動を 'fail-open' と呼ぶ記述をすべて取り除く。書き直した段落では次の 2 点を明示する。

- (a) 意図された根拠：journal にイベントが 1 件も無いタスクを unlaunched として扱うことで、初回 launch の取りこぼしを検出する。
- (b) 結果として queue_stop_guard.py は workflow.yaml の status が merged のタスク名を挙げて turn の終了を BLOCK（exit 2）することがあるが、この誤 BLOCK は consecutive-block cap（3）で有界化されており、上限を超えると警告を出して turn を終わらせる。この挙動に 'fail-open' という語を当てない。

**ビジネスルール**:
- 書き換えの対象は、実際にある 'the hooks are fail-open nets, not authorities'（implement-phase.md の 305-306 行）とする（A2）。

#### FR2: divergence 段落で I.2.b step 1 との関係を述べる

**説明**: divergence 段落には次の 2 点も書く。

- (1) I.2.b step 1 の reconcile も、status を参照せずに『no event → unlaunched』と分類する。
- (2) `status != merged` による除外は I.2.a の選択時フィルタとして効く（I.2.b は I.2.a に再突入する）。

このため、『orchestrator は分類の時点で常に `status != merged` を併用する』とは読めない形にする。

**ビジネスルール**:
- 『status を参照しない』と書く範囲は、journal にイベントが無い場合の分類に限定する。failed かつ pending の例外（recycled-task-id carve-out）と混同させる書き方をしない（A7）。

#### FR3: I.2.b step 1 に注記を足す

**説明**: I.2.b step 1（465-471 行）の『no event → unlaunched』に短い注記を足す。内容は、この分類が workflow.yaml の status を参照しないこと、そして `status != merged` による除外は I.2.a の選択条件で適用されること（divergence 段落を参照先として示す）。既存の句 'the recycled-task-id rule in I.2.a above' はそのまま残す。

**ビジネスルール**:
- 『status を参照しない』と書く範囲は、journal にイベントが無い場合の分類に限定する（A7）。

#### FR4: 固定文言とテストを更新する

**説明**: tests/test_recycled_task_id_consistency.py の `DIVERGENCE_REASON_PHRASE`（439 行。ticket に書かれた `DIVERGENCE_DELIBERATE_PHRASE` は HEAD に存在しない）を、FR1 の新しい根拠の文言に合わせて更新する。986 行の正の assertion も同じく更新し、fail-open を名指ししているテストメソッド名 `test_reason_states_fail_open_nets_not_authorities` も内容に合う名前に変える。1349 行の negative proof（`test_unlaunched_divergence_matchers_flag_absence_in_pre_change_wording`）は、今の b28a716 時点のサンプルに対してだと自明にしか通らないので、次の形で対になる negative proof を足す。このモジュールの既存パターンに倣い、base 4999893 時点の divergence 段落を一字一句そのまま写した pre-change サンプル定数を置き、そのサンプルには新しい phrase が無く、旧い 'the hooks are fail-open nets, not authorities' が有ることを assert する。FR2・FR3 で足す新しい文言にも、正の pin とこのサンプルに対する negative proof を付ける。

**ビジネスルール**:
- `DIVERGENCE_REASON_PHRASE` は定数名を変えずに値だけ更新する（A1）。
- テストメソッド `test_reason_states_fail_open_nets_not_authorities` は改名する。同じテストモジュール内で旧メソッド名を参照している箇所（対応一覧など）は新しい名前に揃える。test-docs/recycled-task-id-contract/task0001.tests.yaml は書き換えない（A5）。
- 新しく足す pre-change サンプル定数には、サンプルに期待する旧句が含まれていることの assert も置く。本文側で旧句が無いことの検査は divergence 段落の範囲に限定する（A8）。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 改名による参照の不整合 | 全体テストが test-docs/recycled-task-id-contract/task0001.tests.yaml の旧メソッド名参照との不整合を理由に落ちた | 改名をやめて旧い名前を残す（A5） |

#### FR5: em-workflow の version を上げる

**説明**: em-workflow/.claude-plugin/plugin.json の version と、.claude-plugin/marketplace.json の em-workflow エントリの version を、どちらも 0.2.7 から 0.2.8 に上げる。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし。

### 5.2 セキュリティ要件
該当なし。

### 5.3 可用性要件
該当なし。

### 5.4 保守性要件
- NFR1: 次の箇所は変更しない。em-workflow/hooks/queue_stop_guard.py のコード、Supporting cast の fail-open 定義（1167-1171 行）、hook classification table とその anchor、I.2.a の Select 行の改行位置に依存する生リテラル（'`tasks.*.status`. Select\nunlaunched tasks (no journal event yet and `status != merged`, ascending'）。
- NFR2: divergence 段落に既に固定されている句は、空白を正規化した状態で本文に残す。対象は UNLAUNCHED_SOLELY_FROM_ABSENCE_PHRASE、NARROWER_THAN_ORCHESTRATOR_PHRASE、NO_EQUIVALENT_EXCLUSION_PHRASE、AUTHORITATIVE_SOURCE_PHRASE。

### 5.5 互換性要件
- NFR3: テストが import してよいのは Python 標準ライブラリの unittest と、同じディレクトリにある既存モジュールだけ（test/README.md）。

## 6. UI/UX要件

該当なし。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- NFR1・NFR2・NFR3 のとおり。

### 9.2 ビジネス上の制約
- 該当なし。

### 9.3 スケジュール制約
- 該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/divergence-fail-open-wording/**`
- `test-docs/divergence-fail-open-wording/**`

`feature-docs/divergence-fail-open-wording/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/divergence-fail-open-wording/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/divergence-fail-open-wording/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 改名したテストメソッド名が test-docs/recycled-task-id-contract/task0001.tests.yaml（35 行）の旧名参照と食い違う | 低 | 全体テストがこの不整合を理由に落ちた場合は改名をやめて旧い名前を残す（A5） |
| pre-change サンプルが空や別文面になると negative proof が自明に通る | 低 | サンプルに期待する旧句が含まれていることを assert する（A8） |
| Supporting cast に 'All of the hooks above are fail-open nets, not authorities' が残る | 低 | 本文側で旧句が無いことの検査は divergence 段落の範囲に限定する（A8） |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: I.2.a の divergence 段落に 'fail-open' という文字列が含まれていない。（FR1）
- [ ] AC-2: divergence 段落に、初回 launch の取りこぼしを検出するという根拠と、誤 BLOCK が consecutive-block cap（3）で有界化されている事実の両方が書かれている。（FR1）
- [ ] AC-3: divergence 段落が、I.2.b step 1 の reconcile も status を参照せずに分類することと、`status != merged` が I.2.a の選択時フィルタとして効くことを述べている。（FR2）
- [ ] AC-4: I.2.b step 1 に、no-event の分類が status を参照しないことと、merged の除外が I.2.a の選択で適用されることを示す注記がある。'the recycled-task-id rule in I.2.a above' も残っている。（FR3）
- [ ] AC-5: DIVERGENCE_REASON_PHRASE が新しい文言になっている。正の assertion が現行文書で通り、新しく足した negative proof が base 4999893 時点の divergence 段落サンプルに対して『新しい phrase が無く、旧い phrase が有る』ことを assert している。（FR4）
- [ ] AC-6: plugin.json と marketplace.json の em-workflow の version が、どちらも 0.2.8 で一致している。（FR5）
- [ ] AC-7: リポジトリのルートで `python3 -m unittest discover -s tests` が通る。（FR1〜FR5、NFR1〜NFR3）

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC-1）: 現行文書の I.2.a 節を取り出し、空白を正規化する。divergence 段落（UNLAUNCHED_SOLELY_FROM_ABSENCE_PHRASE から AUTHORITATIVE_SOURCE_PHRASE の終わりまで）に 'fail-open' が無いことを assert する。
- [ ] TS-2（AC-2、AC-5）: I.2.a 節に、新しい DIVERGENCE_REASON_PHRASE（初回 launch 取りこぼし検出の根拠）と、consecutive-block cap（3）で有界化されていることを述べる句が含まれることを assert する。
- [ ] TS-3（AC-3）: I.2.a 節に、I.2.b step 1 の status 無参照の分類と、I.2.a の選択時フィルタとしての `status != merged` を述べる句が含まれることを assert する。
- [ ] TS-4（AC-4）: I.2.b 節に FR3 の注記の句と 'the recycled-task-id rule in I.2.a above' が含まれることを assert する。
- [ ] TS-5（AC-5）: negative proof：base 4999893 時点の divergence 段落を一字一句写したサンプルでは、新しい phrase（TS-2・TS-3 の句）がすべて無く、'the hooks are fail-open nets, not authorities' が有ることを assert する。I.2.b step 1 の pre-change サンプルでは FR3 の注記の句が無いことを assert する。
- [ ] TS-6（AC-6）: 既存の test_plugin_version_parity が 0.2.8 で通る。
- [ ] TS-7（AC-7）: `python3 -m unittest discover -s tests` の全体が通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| divergence 段落 | I.2.a の 'The other three queue hooks detect a task as **unlaunched** solely from ...' で始まる段落 |
| fail-open | Supporting cast の定義。想定外の状態では exit 0 で黙って通す |
| negative proof | pre-change サンプルに新しい phrase が無いことを assert し、固定句の検査が変更前の文面を見分けられることを示すテスト |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: ticket にある `DIVERGENCE_DELIBERATE_PHRASE` は、HEAD の `DIVERGENCE_REASON_PHRASE`（tests/test_recycled_task_id_consistency.py:439）を指しているものとして扱う。定数名は変えずに値だけ更新する。
- [x] A2: ticket が引用する 'deliberate, intended fail-open behavior' と 'the hook is a fail-open net' は HEAD の文書に無い。書き換えの対象は、実際にある 'the hooks are fail-open nets, not authorities'（implement-phase.md の 305-306 行）とする。
- [x] A3: 完了の定義にある『どちらか一方を読んだだけで誤読しない』を満たすため、divergence 段落（FR2）と I.2.b step 1 への注記（FR3）の両方を入れる。
- [x] A4: Supporting cast の fail-open 定義（1167-1171 行）と queue_stop_guard.py のコードは変えない。
- [x] A5: テストメソッド `test_reason_states_fail_open_nets_not_authorities` は改名する。過去の feature の記録である test-docs/recycled-task-id-contract/task0001.tests.yaml（35 行でこの名前を参照）は書き換えない。全体テストがこの参照の不整合を理由に落ちた場合は、改名をやめて旧い名前を残す。同じテストモジュール内で旧メソッド名を参照している箇所（対応一覧など）は新しい名前に揃える。
- [x] A6: version の上げ幅は patch（0.2.7 → 0.2.8）とする。
- [x] A7: divergence 段落と I.2.b step 1 の注記で『status を参照しない』と書く範囲は、journal にイベントが無い場合の分類に限定する。failed かつ pending の例外（recycled-task-id carve-out）と混同させる書き方をしない。
- [x] A8: 新しく足す pre-change サンプル定数には、このモジュールの既存方式に倣ってサンプル自体の欠落を検出する検査（サンプルに期待する旧句が含まれていることの assert）も置く。本文側で旧句が無いことの検査は divergence 段落の範囲に限定する（Supporting cast の 'All of the hooks above are fail-open nets, not authorities' は残るため）。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- タスク: [https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89](https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89)

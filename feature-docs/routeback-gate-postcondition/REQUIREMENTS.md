---
title: "routeback-gate-postcondition"
created_date: 2026-08-15
status: draft
---

# routeback-gate-postcondition - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow 自身のプロトコル文書のバグ修正である。`implement-phase.md` Step I.2.c の
route-back ゲートは、自身が宣言している事後条件を強制していない。また Branch & Worktree
Model の exit-4 リカバリ列挙は、ゲートによって到達不能となるケースを掲載している。

### 1.2 目的

- Step I.2.c の route-back ゲートが、宣言どおりの事後条件を実際に成立させるようにする。
- ゲートが route back を拒否した経路に、単一の定義済み終端状態を与える。
- exit-4 リカバリ列挙から到達不能なエントリを取り除き、到達不能である理由を明記する。

### 1.3 スコープ

対象は phase / model のプロトコル文書の記述と、プラグインの version ファイルである。

- 対象: `implement-phase.md` Step I.2.c、Branch & Worktree Model 文書の exit-4 リカバリ列挙、
  編集された記述を固定している既存テスト、`em-workflow/.claude-plugin/plugin.json`
- 対象外: `scripts/validate-worker-output.py`、`references/workflow-patch.md`、
  `references/contracts/` 配下の worker contract、ルートの `.claude-plugin/marketplace.json`
- 新規の機械的チェッカー・バリデータルール・スクリプトは追加しない。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| OBJ1 | `implement-phase.md` Step I.2.c の route-back ゲートが宣言する事後条件を強制し、route back が進行するときは常に `workflow-patch.md` の `replace_all` 操作の受理前提条件（既存の全タスクが `pending`）が実際に成立している状態にする。 |
| OBJ2 | ゲートが route back を拒否する経路に単一の定義済み終端状態を与え、合法に route back できない実行が、部分的に適用された route back のまま継続するのではなく、人手の介入のために停止するようにする。 |
| OBJ3 | 拡張されたゲートによって到達不能になるエントリを Branch & Worktree Model の exit-4 リカバリ列挙から取り除き、到達不能である理由を記述して、列挙を真実に保つ。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow のオーケストレーター | `implement-phase.md` Step I.2.c の記述に従って route back の可否を判断する |
| em-workflow のプロトコル文書の読者 | Branch & Worktree Model の exit-4 リカバリ列挙を参照して復旧手順を判断する |

### 2.3 期待される効果

- route back が進行した時点で `replace_all` の受理前提条件が成立している。
- route back できない実行が単一の終端状態で停止する。
- exit-4 リカバリ列挙が到達可能なケースのみを掲載する。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | route back の受理判定 | オーケストレーター | 高 |
| UC02 | route back 拒否時の停止 | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: route back の受理判定

**アクター**: オーケストレーター（implement フェーズ Step I.2.c）

**事前条件**:
- workflow.yaml が存在し、タスクの status を保持している

**基本フロー**:
1. workflow.yaml のタスク status を読む
2. status が `merged` のタスクが存在せず、かつ status が `in_progress` のタスクも存在しないことを確認する
3. 条件を満たすので route back を受理する
4. status が `failed` のタスクを `pending` にリセットする

**代替フロー**:
- 条件を満たさない場合は UC02 に遷移する

**事後条件**:
- 既存の全タスクが `pending` であり、`replace_all` の受理前提条件が成立している

#### UC02: route back 拒否時の停止

**アクター**: オーケストレーター（implement フェーズ Step I.2.c）

**事前条件**:
- Step I.2.c のゲート条件が満たされていない

**基本フロー**:
1. ゲートが route back を拒否する
2. `implement` ステップの status を `failed` にする
3. develop Step B の停止条件 3（status が `failed` / `needs_update` のステップは利用者の介入を要する）で実行を停止する

**代替フロー**:
- なし。代替の復旧経路・リトライループ・縮退した route back は提供しない。

**事後条件**:
- 何もコミットされておらず、route back のクリーンアップも開始されていない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | status |
|----|--------|------|--------|
| FR1 | Step I.2.c の route-back 受理ゲートの拡張 | 受理条件に `in_progress` の不在を加える | resolved |
| FR2 | ゲート拒否時の終端状態 | `implement: failed` + develop Step B 停止条件 3 | resolved |
| FR3 | ゲート判定を全ての副作用より先行させる | commit-docs.sh 呼び出しとクリーンアップの前に判定する | resolved |
| FR4 | exit-4 リカバリ列挙のエントリを到達不能として削除 | 削除と理由の明記 | resolved |
| FR5 | 文書のみの変更、機械的チェッカーは追加しない | テストは同一変更内で更新する | resolved |
| FR6 | version bump のスコープ | plugin.json のみ 0.1.36 → 0.1.37 | resolved |

### 4.2 機能詳細

#### FR1: Step I.2.c の route-back 受理ゲートの拡張

**説明**: `implement-phase.md` Step I.2.c は、workflow.yaml のどのタスクも status が `merged`
ではなく、**かつ** どのタスクも status が `in_progress` ではない場合にのみ route back を受理する。
既存の write set は変更しない（status が `failed` のタスクを `pending` にリセットする）。拡張された
条件と変更されない write set を組み合わせることで、`workflow-patch.md` の `replace_all` の受理条件が
要求する「全て `pending`」の状態を、まだ実行中かもしれない作業のラベルを付け替えることなく成立させる。

**入力**:
- workflow.yaml のタスク status 一覧

**出力**:
- route back の受理可否
- 受理時: `failed` → `pending` にリセットされたタスク status

**ビジネスルール**:
- 受理条件は `merged` の不在と `in_progress` の不在の連言である。
- write set は変更しない。

#### FR2: ゲート拒否時の終端状態

**説明**: 拡張されたゲートの条件が満たされない場合、Step I.2.c は `implement` ステップを `failed`
にし、実行は develop Step B の停止条件 3（status が `failed` / `needs_update` のステップは利用者の
介入を要する）で停止する。代替の復旧経路・リトライループ・縮退した route back は提供しない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| route back 不可 | `merged` または `in_progress` のタスクが存在する | `implement` を `failed` にし、develop Step B 停止条件 3 で停止する |

#### FR3: ゲート判定を全ての副作用より先行させる

**説明**: Step I.2.c のゲート判定は、いかなる commit-docs.sh 呼び出しよりも前、かつ route back の
クリーンアップが始まるよりも前に、厳密に先行して行われる。これにより拒否された経路は何もコミットせず、
何も変更しない。

#### FR4: exit-4 リカバリ列挙のエントリを到達不能として削除

**説明**: Branch & Worktree Model 文書の exit-4 リカバリ列挙から I.2.c の route-back コミットを
削除し、同文書に到達不能である理由を記述する。理由は次のとおり: 拡張されたゲートは `in_progress`
のタスクが存在しない場合にのみ route back を進行させるため、この feature の implementer が実行中で
あることはあり得ず、implementer はこの integration ブランチに対して merge-task.sh を呼ぶ唯一の
呼び出し元である。drain の主張は正しいものとして扱う。

#### FR5: 文書のみの変更、機械的チェッカーは追加しない

**説明**: 本変更は文書上の変更である。新規の機械的チェッカー・バリデータルール・スクリプトは追加
しない。編集された記述を固定している既存テストは同一変更内で更新し、
`python3 -m unittest discover -s tests` が green のままであるようにする。

#### FR6: version bump のスコープ

**説明**: `em-workflow/.claude-plugin/plugin.json` を 0.1.36 から 0.1.37 に bump する。ルートの
`.claude-plugin/marketplace.json` の em-workflow エントリは `version` フィールドを持たないため編集
せず、同期すべきものもない。

## 5. 非機能要件

| ID | 名称 | 内容 | status |
|----|------|------|--------|
| NFR1 | 凍結ファイルの凍結維持 | `scripts/validate-worker-output.py`、`references/workflow-patch.md`、`references/contracts/` 配下の worker contract は本変更で修正しない。修正は phase / model の記述とプラグインの version ファイルに閉じる。 | resolved |
| NFR2 | 独立した安全網の回復 | route back の受理可否は workflow.yaml のタスク status のみから判定するため、ゲートは「先行する drain ステップが正しく振る舞った」という仮定の言い換えではなく独立したチェックとなる。古い、あるいは回収されなかった `in_progress` エントリはゲート自身が捕捉する。 | resolved |
| NFR3 | テストスイートの green 維持 | 変更後に `python3 -m unittest discover -s tests` が pass する。green にするためにテストを skip したり削除したりしない。 | resolved |

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
NFR1 / NFR2 のとおり。

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし（UI サーフェスを持たない変更のため design ステップはスキップされた）。

## 7. データ要件

該当なし（データモデルを持たない変更のため design ステップはスキップされた）。

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- `scripts/validate-worker-output.py`、`references/workflow-patch.md`、
  `references/contracts/*` は変更しない（NFR1）。
- 新規の機械的チェッカー・バリデータルール・スクリプトは追加しない（FR5）。
- ルートの `.claude-plugin/marketplace.json` は変更しない（FR6）。

### 9.2 ビジネス上の制約

該当なし

### 9.3 スケジュール制約

該当なし

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 対応策 |
|------|--------|
| 編集した記述を固定している既存テストが red になる | 同一変更内でテストを更新する（FR5 / NFR3） |
| 2 つの文書が「どの条件が exit-4 の排他を保証するか」で食い違う | 到達不能の理由を drain ステップ単独ではなく拡張されたゲートに結び付けて記述する（FR4） |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `implement-phase.md` Step I.2.c が受理条件を「どのタスクも status が `merged` ではなく、かつどのタスクも status が `in_progress` ではない」と記述し、その write set が引き続き `failed` のタスクを `pending` にリセットする。（FR1 / OBJ1）
- [ ] AC2: Step I.2.c が、条件を満たさない場合に `implement` を `failed` にし、develop Step B 停止条件 3 で実行が停止すると記述している。（FR2 / OBJ2）
- [ ] AC3: Step I.2.c がゲート判定をいかなる commit-docs.sh 呼び出しよりも前、かつ route back のクリーンアップよりも前に置き、拒否された経路では何もコミットされないと記述している。（FR3）
- [ ] AC4: Branch & Worktree Model 文書が exit-4 リカバリのケースとして I.2.c の route-back コミットを掲載しておらず、その代わりに到達不能性の根拠を記述している。（FR4 / OBJ3）
- [ ] AC5: 新規のチェッカー・バリデータルール・スクリプトが導入されておらず、`scripts/validate-worker-output.py`、`references/workflow-patch.md`、`references/contracts/*` が変更前の内容とバイト単位で同一である。（FR5 / NFR1）
- [ ] AC6: `em-workflow/.claude-plugin/plugin.json` の version が 0.1.37 であり、ルートの `.claude-plugin/marketplace.json` が未変更である。（FR6）
- [ ] AC7: `python3 -m unittest discover -s tests` が exit 0 で終了する（編集された記述を固定する reference-sweep 系のテストを含む）。（FR5 / NFR3）

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 対象 AC | 種別 | シナリオ |
|----|---------|------|----------|
| TS1 | AC1 | document-assertion | `implement-phase.md` Step I.2.c を読み、2 つの status 名（`merged`、`in_progress`）が route back の連言的なブロッカーとして現れること、および `failed` → `pending` が write set に残っていることを確認する。 |
| TS2 | AC1 | edge-case | 一部のタスクが `failed` で、`merged` も `in_progress` も存在しない workflow.yaml について推論する: 記述されたゲートは route back を受理し、write set は `failed` タスクを `pending` にして `replace_all` の受理条件を満たす。 |
| TS3 | AC1 | edge-case | クラッシュした implementer が残した古い `in_progress` タスクを持つ workflow.yaml について推論する: 記述されたゲートは、drain ステップだけを根拠に受理するのではなく route back を拒否する。 |
| TS4 | AC1 | edge-case | 全タスクが既に `pending`（あるいはタスクが存在しない）workflow.yaml について推論する: ゲートは route back を受理し、write set は no-op となる。 |
| TS5 | AC2 | document-assertion | Step I.2.c が拒否経路の終端をちょうど 1 つ（`implement: failed` と develop Step B 停止条件 3）だけ挙げ、リトライや縮退した代替を提示していないことを確認する。 |
| TS6 | AC3 | edge-case | 編集後の記述で拒否経路を辿り、ゲートが拒否した後に commit-docs.sh 呼び出しにもクリーンアップステップにも到達し得ないこと、すなわち拒否された実行が worktree と git 履歴に触れないことを確認する。 |
| TS7 | AC4 | document-assertion | Branch & Worktree Model 文書の exit-4 リカバリ節を I.2.c の route-back コミットのケースで grep する: 当該ケースが存在せず、到達不能性の根拠（`in_progress` タスクの不在 → 実行中の implementer の不在 → 並行する merge-task.sh 呼び出し元の不在）が存在する。 |
| TS8 | AC4 | edge-case | 根拠のテキストが、drain ステップ単独ではなく拡張されたゲートに到達不能性を結び付けており、2 つの文書がどの条件で排他が保証されるかについて食い違わないことを確認する。 |
| TS9 | AC5, AC6 | diff-scope | 変更のファイル一覧を確認する: phase の記述、Branch & Worktree Model 文書、編集された記述を固定するテスト、`em-workflow/.claude-plugin/plugin.json` のみに触れている。凍結ファイルも `marketplace.json` のエントリも現れない。 |
| TS10 | AC7, AC5 | command | リポジトリルートから `python3 -m unittest discover -s tests` を実行し、skip も削除もされたテストがない状態で exit 0 となることを確認する。 |
| TS11 | AC7 | edge-case | 旧 I.2.c あるいは旧 exit-4 の文言を assert していた既存テストがすべて同一変更内で更新され、編集された文がスイートを red にしないことを確認する。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| route back | implement フェーズ Step I.2.c で前フェーズに戻る操作 |
| `replace_all` | `references/workflow-patch.md` の操作。既存の全タスクが `pending` であることを受理前提条件とする |
| exit-4 | merge-task.sh の終了コード 4。Branch & Worktree Model 文書がリカバリ手段を列挙している |
| drain | route back に先立って実行中の implementer を回収するステップ |
| develop Step B 停止条件 3 | status が `failed` / `needs_update` のステップは利用者の介入を要する、という停止条件 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] ASM1（gate: create-spec.requirement-clarification / question: routeback.enforcement-mechanism / option: widen-gate、source: batch-codex-consultation）: route back の受理条件を「`merged` なし かつ `in_progress` なし」に拡張し、write set は変更しない。`workflow-patch.md` の `replace_all` の受理条件が既存の全タスクの `pending` を要求しており、この組み合わせがまだ実行中かもしれない作業のラベルを付け替えずにその状態へ到達するため。
- [x] ASM2（gate: create-spec.requirement-clarification / question: routeback.unmet-terminal-state / option: blocked-halt、source: batch-codex-consultation）: 拒否経路は `implement` を `failed` にして develop Step B 停止条件 3 で停止する。ゲート判定はいかなる commit-docs.sh 呼び出しよりも前、かつ route back のクリーンアップよりも前に行う。
- [x] ASM3（gate: create-spec.requirement-clarification / question: routeback.exit4-recovery / option: unreachable、source: batch-codex-consultation）: drain の主張は正しいものとして扱う。I.2.c の route-back コミットは到達不能として exit-4 リカバリ列挙から削除し、理由を文書に記述する。
- [x] ASM4（gate: create-spec.requirement-clarification / question: routeback.mechanical-enforcement / option: prose-only、source: batch-codex-consultation）: 強制は文書上に留める。新規の機械的チェッカーは追加せず、受け入れの基準は `python3 -m unittest discover -s tests` が green であること。
- [x] ASM5（gate: create-spec.requirement-clarification / question: routeback.version-bump-scope / option: plugin-json-only、source: batch-codex-consultation）: bump するのは `em-workflow/.claude-plugin/plugin.json` のみ（0.1.36 → 0.1.37）。ルートの marketplace.json の em-workflow エントリには同期すべき `version` フィールドが存在しない（オーケストレーターが検証済み）。
- [x] ASM6（gate: create-spec.design-step / question: design-step.recommendation / option: skip、source: batch-decision-table）: design ステップはスキップする。UI サーフェス、データモデル、design-system 入力のいずれも持たない変更であるため。

### 14.2 未確認・保留事項

なし（すべての要件が `status: resolved`）。

## 15. 参考資料

- SPEC.md: `feature-docs/routeback-gate-postcondition/SPEC.md`

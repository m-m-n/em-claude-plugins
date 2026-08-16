---
title: "routeback-reset-scope-consistency"
created_date: 2026-08-16
status: draft
---

# routeback-reset-scope-consistency - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/implement-phase.md` の Step I.2.c（Failed handling）が持つ
route-back（route back to planning）は、次の 3 つをそれぞれ別の状態導出元に基づいて
決めている。

- route-back の可否（gate）
- workflow.yaml への書き込みセット（reset 対象）
- コミット後の worktree / branch のクリーンアップ対象

Step I.2.a / I.2.b は「タスクの状態は step 1 の reconciled state から導出する」という
単一の導出規則を確立しているが、I.2.c ではその規則が保たれていない。

なお、レビュー記録に残る当初の記述（「write set が pending でない全タスクに広がって
いる」）は、本 base revision のドキュメントの実際の記述とは一致しない。この base
revision で現に成立している乖離は、journal の last event が `merged`（ancestor 検証済み）
でありながら workflow.yaml の `status` が `failed` であるケース（EC-1）である。本要件は
現在のドキュメントの記述に対して定義する。

### 1.2 目的

- Step I.2.c の route-back において、可否判定・workflow.yaml 書き込みセット・
  worktree / branch クリーンアップのすべてを同一のタスク状態導出元から導く。
- 統合ブランチへマージ済みの作業を持つタスクが、route-back の副作用として
  ブランチを削除されたり、planner の `replace_all` による再採番で記録を消されたり
  しない状態にする。

### 1.3 スコープ

対象は `em-workflow/references/implement-phase.md`、新規テストモジュール、および
2 つのバージョンファイル（`em-workflow/.claude-plugin/plugin.json` と
`.claude-plugin/marketplace.json`）。他のドキュメントは FR5 が真であり続けるために
必要な範囲でのみ触れる（A-5）。ドキュメントのみの変更であり、ランタイムスクリプト・
hook・シェルの挙動は変更しない（NFR8）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- Step I.2.c の route-back が、可否判定・workflow.yaml 書き込みセット・worktree /
  branch クリーンアップを、まったく同一のタスク状態導出元から導くようにし、I.2.a /
  I.2.b が確立した単一の導出規則（「タスクの状態は step 1 の reconciled state から
  来る」）を回復する。
- 統合ブランチに既にマージ済みの作業を持つタスクが、route-back の副作用として
  ブランチを削除されること、および planner の `replace_all` 再採番によって記録を
  消されることが起きないようにする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow のオーケストレーター | implement フェーズ Step I.2.c を実行し、route-back の可否・書き込み・クリーンアップを判断する |
| em-workflow の利用者 | implement フェーズの失敗ハンドリングを通じて、マージ済み作業が失われないことに依存する |

### 2.3 期待される効果

- route-back の 3 つの判断（admissibility / write set / cleanup）が同一の導出元を
  名指しし、記述として整合する。
- journal の last event が `merged`（ancestor 検証済み）のタスクの worktree /
  branch が、route-back のクリーンアップ対象になることがなくなる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | route-back の可否判定と実行 | オーケストレーター | 高 |
| UC02 | gate 不成立時の終端処理 | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: route-back の可否判定と実行

**アクター**: オーケストレーター（implement フェーズ Step I.2.c）

**事前条件**:
- いずれかのタスクの reconciled status が `failed` である
- ユーザー（またはバッチポリシー）が "route back to planning" を選択している

**基本フロー**:
1. gate を評価する。`merged` の conjunct は 2 つの独立した source の union として
   評価する（workflow.yaml が `merged` を報告する、または Step I.2.b step 1 の
   reconciled state が `merged` を報告する）。`in_progress` の conjunct は既存の
   union のまま評価する。
2. gate が成立する場合、統合 worktree を refresh し `ROUTEBACK_TIP` を取得する。
3. 順序付き workflow.yaml 書き込みセットを作る。reset 対象は Step I.2.b step 1 の
   reconciled state が `failed` のすべてのタスク。書き込み指示 4 つとその順序は
   従来どおり（`create-plan` → `needs_update`、`implement` → `pending`、失敗理由を
   `tasks.{T}.notes` へ、`tasks.{T}.status` を `pending` へ戻す）。
4. その書き込みセットを、クリーンアップより前にコミットする。
5. コミット成功後にのみ、直前の手順で reset したタスク（= マージ済みでないことが
   確認されたタスク）の worktree と branch をクリーンアップする。
6. 明確なレポートでフェーズを終了する。create-plan が後で再入する。

**代替フロー**:
- gate が成立しない場合は UC02 へ。

**事後条件**:
- `merged` でも `in_progress` でも `failed` でもないタスク状態になり、planner の
  `replace_planning` 操作が再入時に許容される。
- マージ済みタスクの worktree / branch は削除されていない。

#### UC02: gate 不成立時の終端処理

**アクター**: オーケストレーター（implement フェーズ Step I.2.c）

**事前条件**:
- route-back gate が成立しない

**基本フロー**:
1. 不成立理由を列挙する。既存の `merged` / `in_progress` / in-flight の理由に加え、
   「workflow.yaml は報告していないが reconciled state が `merged` を報告する
   タスクがある」を列挙に含める。
2. `create-plan` は `needs_update` にしない。
3. 統合 worktree を refresh し、`TERMINAL_TIP` を取得し、`implement` ステップの
   `status` を `failed` にする（このパスの唯一の書き込み）。
4. その書き込みだけをコミットする。
5. develop の stop condition 3 経由で制御をユーザーへ返す。

**事後条件**:
- route-back の書き込みセット、worktree / branch クリーンアップ、route-back
  コミットのいずれもこのパスでは発生していない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | `merged` gate conjunct の 2-source union 化 | gate の `merged` 条件を 2 つの独立 source の union として記述する | 高 |
| FR2 | reset（書き込みセット）対象を reconciled state で定義 | 書き込みセットの対象を reconciled state `failed` に基づかせる | 高 |
| FR3 | クリーンアップ対象をマージ済みでないと確認されたタスクに限定 | クリーンアップ対象を FR2 で reset したタスクに一致させる | 高 |
| FR4 | rejected パスへの新規ブロッカー列挙 | gate 不成立の理由列挙に FR1 の source を追加する | 高 |
| FR5 | gate を記述する相互参照の整合維持 | gate を説明する他箇所を同一変更内で更新する | 高 |
| FR6 | route-back 自身の再帰不変条件の明示 | recycled id を通じた後続 route-back がデッドロックしない理由を記述する | 中 |
| FR7 | ドキュメント契約テスト | FR1..FR4 / FR6 を implement-phase.md に対して検証するテストを追加する | 高 |
| FR8 | プラグインバージョン bump | 2 つのバージョンファイルを同一の新パッチバージョンへ | 中 |

### 4.2 機能詳細

#### FR1: `merged` gate conjunct の 2-source union 化

**説明**: I.2.c において、route-back gate の `merged` conjunct を、いずれか一方でも
ブロックする 2 つの独立した source の union として記述し直す。これは既存の
`in_progress` conjunct の union と完全に並行する形とする。2 つの source は、
workflow.yaml がタスクを `merged` と報告すること、または Step I.2.b step 1 の
reconciled state がタスクを `merged` と報告すること（journal last event が `merged`
であり、当該ステップが既に要求しているとおり `git merge-base --is-ancestor` で
検証されたもの）。Step I.2.b は所有規則として引用するのみで、再記述はしない。
既存の literal「no task has status `merged`」は残し、union はそれを置き換えるのでは
なく、それを囲む形で追加する。

**ビジネスルール**:
- union はいずれか一方が成立すればブロックする（置換ではなく union 意味論）。
- Step I.2.b の規則は引用であり、再記述しない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| gate 不成立 | いずれかの source が `merged` を報告 | FR4 の rejected パスへ |

#### FR2: reset（書き込みセット）対象を reconciled state で定義

**説明**: 順序付き workflow.yaml 書き込みセットは、Step I.2.b step 1 の reconciled
state が `failed` であるすべてのタスクの status を reset する。これは現行の
workflow.yaml の `status: failed` を基準とする定義を置き換える。4 つの書き込み指示と
その順序（`create-plan` → `needs_update`、`implement` → `pending`、失敗理由を
`tasks.{T}.notes` へ、`tasks.{T}.status` を `pending` へ戻す）は変更しない。
`replace_planning` / `replace_all` の `references/workflow-patch.md` への引用は引用の
ままとする。

**ビジネスルール**:
- 書き込み指示の内容と順序は不変。
- `references/workflow-patch.md` は引用であり、条件セットを再記述しない。

#### FR3: クリーンアップ対象をマージ済みでないと確認されたタスクに限定

**説明**: コミット後のクリーンアップ（`git worktree remove --force`;
`git branch -D`）は、FR2 で reset した当のタスクにちょうど適用される。かつ、
それらがマージ済みでないと確認されたタスクであることを、ドキュメントが明言する。
reconciled state が `merged` のタスクは決してクリーンアップ対象にならない。
commit-before-cleanup の順序と leftover-state の文は保持する。

**ビジネスルール**:
- クリーンアップ対象 = FR2 の reset 対象、と厳密に一致する。
- reconciled state が `merged` のタスクはクリーンアップ対象外。
- コミットが先、クリーンアップが後、の順序は不変。

#### FR4: rejected パスへの新規ブロッカー列挙

**説明**: 「When the gate does not hold」の分岐に、FR1 の source（workflow.yaml は
報告していないのに reconciled state が `merged` を報告するタスク）を、既存の
`merged` / `in_progress` / in-flight の理由と並べて理由列挙に追加する。
終端は不変：`needs_update` にしない、`implement` を `failed` にして単一の書き込みと
してコミットする、develop の stop condition 3 経由で制御を戻す。

**ビジネスルール**:
- rejected パスの終端（単一書き込みとそのコミットのみ）は変更しない。

#### FR5: gate を記述する相互参照の整合維持

**説明**: I.2.c の gate を記述しているすべての箇所を同一変更内で更新し、正しく
読める状態を保つ。対象は I.2.a の unreachability の文（"Given I.2.c's route-back
precondition below, which admits only tasks with a terminal journal last event…"）と、
Branch & Worktree Model の exit-4 unreachability proof（"The widened I.2.c gate's
union rule — blocked when workflow.yaml reports a task `in_progress` OR …"）。

#### FR6: route-back 自身の再帰不変条件の明示

**説明**: FR1 が recycled id を通じた後続の route-back をデッドロックさせない理由を
ドキュメントに記述する。理由は、route-back はいずれの source でも `merged` のタスクが
存在しないときにのみ進むため、退役した id が `merged` の last event を残して再採番後の
タスクに継承させることがありえないこと。したがって I.2.a の recycled-task-id の
carve-out は `failed` のみに正しくスコープされたままとなる。

#### FR7: ドキュメント契約テスト

**説明**: 新規の `tests/test_*.py` モジュールが、`em-workflow/references/implement-phase.md`
に対して FR1..FR4 および FR6 を検証する（受け入れ基準が名指しする TS-3 / TS-4 相当）。
既存のスタイルに従う：散文には空白正規化したセクションスライス、バイト同一性には
raw text、新しい matcher ごとに変更前の文言を捕捉した negative proof を 1 つ、
加えてそのサンプルに対する non-vacuity guard。

#### FR8: プラグインバージョン bump

**説明**: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`
の双方を、この変更内で `0.1.38` から同一の新しいパッチバージョンへ移す。

## 5. 非機能要件

| ID | 内容 |
|----|------|
| NFR1 | `tests/test_implement_routeback_gate.py` と `tests/test_recycled_task_id_consistency.py` が既にアサートしているバイト同一性制約が不変で成立すること：I.2.c の heading、および I.2.c セクションのバイト同一な TAIL としての batch-mode 段落（新しい散文はすべてその前に挿入する）。 |
| NFR2 | I.2.c 外の行折り返し literal を reflow しないこと — Step I.0 の "in `tasks` whose\n   `status == pending`"、Step I.2.a の "`tasks.*.status`. Select\nunlaunched tasks (…) ascending"、Step I.2.b step 3 の `commit-docs.sh` 2 行 literal。 |
| NFR3 | 正規化した I.2.c セクションに対してアサートされている順序が保たれること：最初に出現する `tasks.{T}.status` の 60 文字以内に `pending` があること（新しい gate の文言がそれより前に言及を持ち込まないこと）、4 つの書き込みトークンが `git worktree remove --force` より前にあること、`commit-docs.sh` がクリーンアップより前、クリーンアップが "End the phase with a" より前にあること、literal "terminal journal last event (`merged` or `failed`)" が残り、かつ "`create-plan` to `needs_update`" より前にあること。 |
| NFR4 | rejected パスの包含制約が保たれること：正規化テキストで "When the gate does not hold" 以降に "make one ordered workflow.yaml write set"、"git worktree remove --force"、"ROUTEBACK_TIP" のいずれも含まれないこと。かつ文字列 "rework" と "append" が I.2.c セクションのどこにも現れないこと。 |
| NFR5 | 保持すべき gate literal："no task has status `merged`"、"no task has status `in_progress`"（1 文の中で結合されていること）、"re-read from workflow.yaml task statuses"、"not inferred from the drain above"、"a union of two independent sources"。 |
| NFR6 | implement-phase.md に裸の `git … commit` / `git … add -A` 行を導入しないこと。 |
| NFR7 | テストは Python 標準ライブラリ（`unittest`）のみを使用し、リポジトリルートの `tests/` に置き、プロジェクトルートから `python3 -m unittest discover -s tests` の全スイートが成功すること。 |
| NFR8 | ドキュメントのみの変更であること：ランタイムスクリプト・hook・シェルの挙動は一切変更しない。ファイルセットは implement-phase.md、新規テストモジュール、2 つのバージョンファイル（加えて FR5 により gate を再記述しているドキュメントがあればそれ）。 |

## 6. UI/UX要件

該当なし（ドキュメントおよびテストのみの変更）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 標準ライブラリ（`unittest`）のみを使用する（NFR7）。
- テストはリポジトリルートの `tests/` に置く（NFR7）。
- 既存の保護済みテストモジュール 2 本は編集しない（A-4）。
- ランタイムスクリプト・hook・シェルの挙動は変更しない（NFR8）。

### 9.2 ビジネス上の制約

- スコープは `em-workflow/references/implement-phase.md`、新規テストモジュール、
  2 つのバージョンファイルに限る。他ドキュメントは FR5 が要求する範囲のみ（A-5）。

## 10. 想定される課題とリスク

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| I.2.b step 3 の precedence の曖昧さ（「verified merged」節と「report is `failed`/malformed」節の双方に一致するタスク） | 中 | 本変更では現状維持とし、スコープ外とする（A-2） |
| 新しい gate 文言が I.2.c の既存の順序アサートを壊す | 高 | NFR3 の順序制約（特に 60 文字ウィンドウ）をテストで守る |
| 新しい散文が batch-mode 段落の TAIL バイト同一性を壊す | 高 | 新しい散文はすべて batch-mode 段落より前に挿入する（NFR1） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: I.2.c の route-back admissibility、write set、cleanup がすべて同一の
      状態導出元（Step I.2.b step 1 の reconciled state）を名指ししている。
- [ ] AC-2: タスクの journal last event が `merged`（ancestor 検証済み）のとき、
      その worktree と branch は route-back のクリーンアップ対象に決してならない
      — workflow.yaml の `status` が何であっても。
- [ ] AC-3: このパスの `git branch -D` が、マージ済みでないと確認されたタスクのみを
      対象とすることをドキュメントが明言している。
- [ ] AC-4: TS-3 / TS-4 相当のドキュメント契約テストが `tests/` 配下に存在し、
      新しい absence / new-wording matcher それぞれに negative proof と
      non-vacuity guard が対になっている。
- [ ] AC-5: `python3 -m unittest discover -s tests` が成功する。
- [ ] AC-6: `tests/test_implement_routeback_gate.py` と
      `tests/test_recycled_task_id_consistency.py` が無変更のまま成功する。
- [ ] AC-7: `em-workflow/.claude-plugin/plugin.json` と
      `.claude-plugin/marketplace.json` が同一の bump 済みバージョンを持つ。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1: I.2.c gate の `merged` conjunct が、workflow.yaml status と Step I.2.b の
      reconciled state の union として記述され、I.2.b を所有者として引用している。
      変更前の文言（workflow.yaml のみ）は存在しない。（FR1, AC-1）
- [ ] TS-2: 書き込みセットの reset 対象が reconciled state の用語で表現されている。
      workflow.yaml の `status: failed` のみに基づく表現は存在しない。（FR2, AC-1）
- [ ] TS-3: クリーンアップの文が、対象を「直前に reset したタスク」と名指しし、
      それらがマージ済みでないと確認されていることを述べている。`git branch -D` は
      そのスコープされた文の中にのみ現れる。（FR3, AC-2, AC-3）
- [ ] TS-4: rejected 分岐が reconciled-state-`merged` のブロッカーを列挙し、単一の
      終端（`implement` を `failed`、コミット、stop condition 3）を保つ。
      route-back の指示が漏れ込まない。（FR4, NFR4）
- [ ] TS-5: I.2.a の unreachability の文と Branch & Worktree Model の exit-4
      union-rule の文が、現在の gate の記述を正しく説明している。（FR5）
- [ ] TS-6: 再帰不変条件の文（退役 id が `merged` last event を持ち越せない）が存在し、
      I.2.a の carve-out が `failed` にスコープされたままである。（FR6）
- [ ] TS-7: リグレッションガード：heading と batch-mode 段落のバイト同一性、保護対象
      3 つの行折り返し literal、60 文字の `tasks.{T}.status` / `pending` ウィンドウを
      含む正規化 I.2.c の 4 つの順序、I.2.c における "rework" / "append" の不在、
      裸の git commit / add 行の不在。（NFR1, NFR2, NFR3, NFR4, NFR6）
- [ ] TS-8: TS-1..TS-6 の各 new-wording matcher が、変更前の逐語サンプルに対する
      negative proof を持ち、各サンプルが positive にアサートされた retained anchor を
      持つ。（FR7, AC-4）
- [ ] TS-9: 2 つのバージョンファイルが同一の bump 済みバージョン文字列を報告する。
      （FR8, AC-7）

### 12.2 エッジケース

- [ ] EC-1: journal last event が `merged`（ancestor 検証済み）＋ workflow.yaml
      `status: failed`。現状で到達可能：I.2.b step 3 は「whose report is
      `failed`/malformed」のタスクに `failed` を書き、この節は `merged` 節が一致する
      のと同じタスクに一致しうる。現行 gate の両 conjunct が通過し、そのタスクは
      `pending` に reset され、branch が `git branch -D` される。これが報告された
      バグの実インスタンスであり、FR1 が閉じなければならない。
- [ ] EC-2: journal last event が `merged` ＋ workflow.yaml `status: in_progress`
      （レビュー指摘が名指しするシナリオ）。既存の `in_progress` conjunct により
      既にブロックされる。FR1 の後は `merged` の理由でもブロックされ、rejected パスは
      それに対して真である理由を報告しなければならない。
- [ ] EC-3: `git merge-base --is-ancestor` に失敗する `merged` 主張はマージ済みでは
      ない（I.2.b step 1 が権威）。新しい conjunct を通じて route-back をブロックしては
      ならない。
- [ ] EC-4: journal イベントがまったくないタスクは継承するものがなく、route-back を
      決してブロックしない。`pending` のままでクリーンアップ対象にもならない。
      既にドキュメントに記述されており、編集後も残らなければならない。
- [ ] EC-5: 過去の route-back ＋ `replace_all` 後の recycled id：再採番されたタスクが
      退役 id の `merged` イベントを継承して 2 回目の route-back を恒久的にブロック
      してはならない。FR6 がこれが起こりえない理由を述べる。
- [ ] EC-6: workflow.yaml `status: merged` かつ `merged` の journal イベントなし
      （journal の消失・切り詰め）：FR1 の union の workflow.yaml 側 source が依然として
      ブロックする。置換ではなく union 意味論。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| reconciled state | Step I.2.b step 1 が journal の last-event-per-task 規則と git 実状態の突き合わせ（trust-but-verify）から導出するタスク状態 |
| route-back | Step I.2.c の "route back to planning"。`create-plan` を `needs_update` にし、`implement` を `pending` に戻して計画へ再入する経路 |
| gate | route-back の admissibility 判定条件 |
| rejected パス | gate が成立しない場合の分岐。`implement` を `failed` にする単一書き込みとそのコミットのみを行う |
| write set | route-back が行う順序付き workflow.yaml 書き込みセット |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A-1: レビュアーの選択肢 (a) を (b) に優先して採用する。reset / cleanup の
      スコープは Step I.2.b step 1 の reconciled state で定義し、gate の `merged`
      conjunct は `in_progress` conjunct が既に使っている 2-source union の形へ
      拡張する。
- [x] A-2: I.2.b step 3 自身の precedence の曖昧さ（「verified merged」節と
      「report is `failed`/malformed」節の双方に一致するタスク）は現状のままとし、
      スコープ外とする。
- [x] A-3: バージョン bump は `0.1.38` → `0.1.39`（パッチ）。
- [x] A-4: 新規テストモジュールは `tests/` 配下の単一の新規ファイルとする。保護対象の
      2 モジュールはいずれも編集しない。
- [x] A-5: スコープは `em-workflow/references/implement-phase.md`、新規テスト
      モジュール、2 つのバージョンファイルに限る。他のドキュメントは FR5 が真であり
      続けるために必要な箇所のみ触れる。
- [x] レビュー記録の当初の記述（「write set が pending でない全タスクに広がって
      いる」）は、この base revision のドキュメントの記述とは一致しない。現に成立して
      いる乖離は journal-`merged` ＋ workflow.yaml-`failed`（EC-1）であり、本要件は
      現在の記述に対して定義されている。

### 14.2 未確認・保留事項

なし（すべての要件は `status: resolved`）。

### 14.3 design ステップ

- skipped。理由：UI もレンダリング出力もない、ドキュメント + Python unittest の
  リポジトリであり、design-system の入力が存在しない。design-system の候補探索は
  候補ゼロを返した。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: Branch & Worktree Model、Step I.2.a /
  I.2.b / I.2.c
- `em-workflow/references/workflow-patch.md`: `replace_planning` / `replace_all` の
  許可条件
- `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`:
  無変更で成立し続けるべき既存の契約テスト
- `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`:
  バージョンファイル

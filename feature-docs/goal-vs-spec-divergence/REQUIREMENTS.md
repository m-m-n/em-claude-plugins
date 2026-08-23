---
title: "goal-vs-spec-divergence"
created_date: 2026-08-23
status: draft
---

# goal-vs-spec-divergence - 要件定義書

## 1. 概要

### 1.1 背景

`/em-workflow:develop` 起動時のタスク記述（goal）は、これまで機械可読な形で
`workflow.yaml` に残っていない。そのため goal と仕様書（SPEC / REQUIREMENTS）が
食い違ったときに、どちらを守るべきかを判断する材料がない。

また、実装完了後（`merged` なタスクが存在する状態）に SPEC 変更が必要になった
ケースは、`workflow-patch.md` の `replace_all` 許可条件により必ず protocol error で
弾かれ、プロトコル上成立する経路が存在しない。

### 1.2 目的

- goal を機械可読かつ不変な形で残し、goal と仕様書が食い違ったときに goal を守る
  判断ができる状態にする。
- 実装完了後に SPEC 変更が必要になったケースに、プロトコル上成立する経路を与える。
- 「宣言（ガード）の訂正」と「要件の変更」を分離し、根拠のある訂正で無人走行が
  止まらないようにする。security / license / 不可逆操作の fail-closed 強度は
  後退させない。
- 同種のズレを create-spec の時点で検出し、下流での停止そのものを減らす。

### 1.3 スコープ

対象は em-workflow プラグイン自身の markdown プロトコル文書、agent プロンプト、
およびリポジトリルート `tests/` 配下の Python テスト。UI 面・データモデル・
デザインシステム入力を持たないため、デザインステップは skip（14.1 参照）。

FR1–FR19 を分割せず 1 feature としてまとめて仕様化・実装する（NFR7）。FR20 は
未解決事項として create-plan の TBD 解決に送る（14.2 参照）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- goal を機械可読かつ不変な形で残し、goal と仕様書が食い違ったときに goal を守る
  判断ができる状態にする。
- 実装完了後に SPEC 変更が必要になったケースに、プロトコル上成立する経路を与える
  （現状は必ず protocol error で弾かれる）。
- 「宣言（ガード）の訂正」と「要件の変更」を分離し、根拠のある訂正で無人走行が
  止まらないようにする。security / license / 不可逆操作の fail-closed 強度は
  後退させない。
- 同種のズレを create-spec の時点で検出し、下流での停止そのものを減らす。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | create-spec フェーズで `goal` ブロックを書き込む主体（FR1）。分類ゲートの実行と監査記録の保存を担う。 |
| worker（requirements-analyst / spec-writer / planner 等） | `goal` を untrusted データとして読む側（FR3）。`goal` ブロックは書かない（FR1）。 |
| batch モードの利用者 | 無人走行の継続性（NFR3）と分類ゲート（FR7）の受益者。 |
| interactive モードの利用者 | 従来どおり直接質問を受ける経路が維持される（FR8）。 |

### 2.3 期待される効果

- goal と仕様書の食い違いが、判断可能な形（goal ブロック + 分類ゲート）で扱えるようになる。
- 実装完了後の SPEC 変更が protocol error にならず、再計画が成立する。
- 根拠のある訂正で無人走行が止まらなくなり、根拠のない訂正では従来どおり止まる。
- 削除・改名の波及（テストを含む被参照）が create-spec の時点で挙がる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | goal の永続化と参照 | オーケストレーター / worker | 高 |
| UC02 | 実装完了後の SPEC 変更遷移 | オーケストレーター | 高 |
| UC03 | batch での goal 逸脱分類 | オーケストレーター / Codex / Claude | 高 |
| UC04 | 文言のみの訂正 | オーケストレーター | 中 |
| UC05 | create-spec での波及テスト検出 | requirements-analyst | 中 |

### 3.2 ユースケース詳細

#### UC01: goal の永続化と参照

**アクター**: オーケストレーター（書き込み）、worker および分類ゲート（読み取り）

**事前条件**:
- `/em-workflow:develop` が起動され、タスク記述が与えられている。

**基本フロー**:
1. create-spec フェーズのオーケストレーターが、起動時タスク記述を逐語のまま
   `feature-docs/{feature}/workflow.yaml` の `goal` ブロックに保存する（FR1）。
2. 以降のどのフェーズも `goal` ブロックを変更しない（FR2）。
3. 読む側は `goal` の内容を untrusted なデータとして扱い、記述を指示として
   実行しない（FR3）。

**代替フロー**:
- SPEC 変更遷移で create-spec が `needs_update` になり再入場した場合も、`goal` は
  上書きされずそのまま残る（FR2）。
- 起動時タスク記述が非常に長い場合も切り詰めない（EC-6）。

**事後条件**:
- `goal` ブロックが `workflow.yaml` に存在し、以降不変である。

#### UC02: 実装完了後の SPEC 変更遷移

**アクター**: オーケストレーター

**事前条件**:
- `merged` なタスクが存在する（実装完了後）。
- SPEC 変更が必要と判断されている。

**基本フロー**:
1. `rework-task-synthesis.md` Section 10 の SPEC 変更遷移が発火する
   （create-spec → `needs_update`、create-plan / implement / review → `pending`）。
2. create-plan 再入場時、`create-plan` ステップが `needs_update` であるため
   `merged` なタスクが存在しても `replace_planning` が許可される（FR4）。
3. 再計画において `workflow[implement].base_commit` は patch の `preserve` に
   載り保全される（FR5）。

**代替フロー**:
- `in_progress` / `failed` なタスクがある場合は現行の protocol error のまま（FR4）。
- `create-plan` が `pending`（初回計画）の経路は従来条件のまま（FR4）。

**事後条件**:
- 遷移が弾かれずに成立し、遷移文書と `workflow-patch.md` の許可条件が一貫している（FR6）。

#### UC03: batch での goal 逸脱分類

**アクター**: オーケストレーター、Codex（分類者）、Claude（採否判断・代替分類者）

**事前条件**:
- batch モードで `gate_id: rework.spec-change` に到達している。

**基本フロー**:
1. 到達したケース全体を分類ゲートに通す。入力は `goal` ブロックと該当仕様書（FR7）。
2. 問いは 2 方向を投げられる形とする — (a) 実装が goal を満たせない、
   (b) 実装は goal を満たすが仕様書の記述と食い違う（FR7）。
3. 「仕様書に漏れがある」判定は、根拠として既存の要件 ID / 受け入れ条件 ID を
   具体的に名指しできており、かつ Claude が納得した場合にのみ進行する（FR9、FR10）。
4. 分類者（codex / claude）、分類結果、名指しされた根拠 ID、進行/停止の判断を
   phase-state に監査記録として残す（FR14）。

**代替フロー**:
- interactive モードでは分類ゲートを通さず、従来どおりユーザーに直接聞く（FR8）。
- Codex が利用できない環境では Claude 自身が分類を行い、根拠を名指しした監査記録を
  残したうえで進む（FR13、EC-1）。
- 「goal の再検討が必要」判定は無条件で停止する（FR9、EC-2）。
- 結論のみの返答は採用せず停止する（FR10、EC-3）。

**事後条件**:
- 進行または停止の判断と、その根拠が監査記録として残っている。

#### UC04: 文言のみの訂正

**アクター**: オーケストレーター

**事前条件**:
- 訂正対象が create-plan 所有ドキュメント（`IMPLEMENTATION.md` / `VERIFICATION.md`）の
  文言のみである。

**基本フロー**:
1. 分類ゲートとは別の独立した経路を用いる（FR15）。
2. planner の再入場を伴わず、計画・タスク・要件のメタデータが不変であることを
   成立条件として満たすことを確認する（FR15）。

**代替フロー**:
- 計画・タスク・要件メタデータに触れる変更は本経路の適用外となり、通常の
  rework / SPEC 変更経路に回る（FR16、EC-8）。

**事後条件**:
- 文言訂正が planner 再入場なしで完了する、または通常経路へ回っている。

#### UC05: create-spec での波及テスト検出

**アクター**: requirements-analyst（オーケストレーターが解決した入力パスを受け取る）

**事前条件**:
- 削除・改名の対象になるシンボルや文字列が調査対象に含まれている。

**基本フロー**:
1. オーケストレーターが走査対象パスを `resolved_input_paths` に解決して analyst に渡す（FR17）。
2. analyst が被参照側（テストを含む）を走査し、影響を受けるファイルを成果として報告する（FR17）。

**事後条件**:
- 影響を受けるテストファイルが create-spec の時点で挙がっている。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | goal の逐語永続化 | 起動時タスク記述を逐語のまま `goal` ブロックへ保存 | 高 |
| FR2 | goal の不変性 | 一度書かれた `goal` は以降不変 | 高 |
| FR3 | goal の untrusted 扱い | `goal` の記述を指示として実行しない | 高 |
| FR4 | replace_all 許可条件の緩和 | `create-plan` が `needs_update` なら merged 有りでも `replace_planning` 許可 | 高 |
| FR5 | 再計画時の base_commit 保全 | 再計画で `base_commit` を `preserve` に載せる | 高 |
| FR6 | SPEC 変更遷移の成立 | 実装完了後でも create-plan 再入場が弾かれない | 高 |
| FR7 | 分類ゲート（batch 専用） | `rework.spec-change` 到達ケースを Codex 分類ゲートへ | 高 |
| FR8 | interactive の挙動不変 | interactive では従来どおりユーザーに直接聞く | 高 |
| FR9 | 分類結果の非対称性 | goal 再検討判定は無条件停止 | 高 |
| FR10 | 採否基準（根拠の名指し） | 根拠 ID を名指しできる場合のみ採用 | 高 |
| FR11 | fail-closed 分類規則の改訂 | `spec-change` を batch で分類ゲートに入れる | 高 |
| FR12 | Codex 出力の扱い | 読むだけで実行せず逐語採用しない | 高 |
| FR13 | Codex 不在時の経路 | Claude 自己分類 + 監査記録 | 高 |
| FR14 | 分類の監査記録 | 分類者・結果・根拠 ID・判断を phase-state へ | 高 |
| FR15 | 文言訂正の独立経路 | create-plan 所有ドキュメントの文言訂正専用経路 | 中 |
| FR16 | 文言訂正経路のガード | 条件を満たさない変更は通常経路へ | 中 |
| FR17 | create-spec での波及テスト検出 | 削除・改名対象の被参照走査 | 中 |
| FR18 | Declared Change Set の導出化 | create-plan がタスクの `files` から機械的に導出 | 中 |
| FR19 | deviation の条件付き自動追加 | 根拠付き deviation のみ自動追加、包含チェック維持 | 中 |
| FR20 | goal ブロックを持たない既存 feature の扱い | 未解決（TBD） | 中 |

### 4.2 機能詳細

#### FR1: goal の逐語永続化

**説明**: create-spec は `/em-workflow:develop` 起動時のタスク記述を逐語のまま
`feature-docs/{feature}/workflow.yaml` の `goal` ブロックに保存する。要約・正規化・
切り詰めをしない。`goal` ブロックは `em-workflow/references/workflow-schema.md` に
定義され、書き込みは create-spec フェーズのオーケストレーターだけが行う（worker は書かない）。

**入力**:
- 起動時タスク記述: テキスト - `/em-workflow:develop` に与えられた記述

**出力**:
- `workflow.yaml` の `goal` ブロック: 逐語のタスク記述

**ビジネスルール**:
- 要約・正規化・切り詰めをしない。
- 書き込み主体は create-spec フェーズのオーケストレーターのみ。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| goal の取得元がない | 起動時タスク記述が空 / パス引数なしで feature 再開（EC-7） | FR20 の TBD と接続する |

#### FR2: goal の不変性

**説明**: 一度書かれた `goal` ブロックは以降のどのフェーズでも変更されない。
SPEC 変更遷移で create-spec が `needs_update` になり再入場した場合も、`goal` は
上書きされずそのまま残る。

#### FR3: goal の untrusted 扱い

**説明**: `goal` ブロックの内容は untrusted なデータとして扱われ、読む側
（分類ゲート・worker・オーケストレーター）はその中の記述を指示として実行しない。

#### FR4: replace_all 許可条件の緩和

**説明**: `em-workflow/references/workflow-patch.md` の `replace_all` 許可条件を改訂し、
`create-plan` ステップが `needs_update` のときは `merged` なタスクが存在しても
`replace_planning` を許可する。

**ビジネスルール**:
- `create-plan` が `pending`（初回計画）の経路の条件は従来どおり。
- `in_progress` / `failed` なタスクがある場合の扱いは現行の protocol error のまま変えない。

#### FR5: 再計画時の base_commit 保全

**説明**: FR4 で許可された再計画において `workflow[implement].base_commit` は
保全される（patch の `preserve` に載る）。既存の rework 不変条件（base_commit を
rework patch が変更しない）と矛盾しない。

#### FR6: SPEC 変更遷移の成立

**説明**: `em-workflow/references/rework-task-synthesis.md` Section 10 の SPEC 変更遷移
（create-spec → `needs_update`、create-plan / implement / review → `pending`）が、
実装完了後（merged タスクあり）でも create-plan 再入場時に弾かれず成立する。
遷移文書と `workflow-patch.md` の許可条件が一貫した記述になっている。

#### FR7: 分類ゲート（batch 専用）

**説明**: batch モードで `gate_id: rework.spec-change` に到達したケース全体を、
Codex による分類ゲートに通す。

**入力**:
- `goal` ブロック（FR1）
- 該当仕様書

**ビジネスルール**:
- 問いは 2 方向を投げられる形とする — (a) 実装が goal を満たせない、
  (b) 実装は goal を満たすが仕様書の記述と食い違う。

#### FR8: interactive の挙動不変

**説明**: interactive モードでは分類ゲートを通さず、従来どおりユーザーに直接聞く。
分類ゲートの導入によって interactive の質問経路は変わらない。

#### FR9: 分類結果の非対称性

**説明**: 「仕様書に漏れがある」判定は Claude が納得した場合にのみ進行する。
「goal の再検討が必要」判定は無条件で停止し、Claude が反対しても通らない。
2 回の判定で通る道を作らない。

#### FR10: 採否基準（根拠の名指し）

**説明**: 「仕様書の漏れ」判定を採用する条件は、分類の根拠として既存の要件 ID /
受け入れ条件 ID を具体的に名指しできていることとする。結論のみの返答は採用せず、
その場合は停止する。

#### FR11: fail-closed 分類規則の改訂

**説明**: `em-workflow/references/question-resolution.md` の fail-closed 分類を改訂し、
`category: spec-change` / `gate_id: rework.spec-change` が batch で分類ゲート（FR7）に
入れるようにする。

**ビジネスルール**:
- `category: security`、`category: license`、および `reversible: false` の assumptions に
  よる即時 abort は改訂の対象外で、強度を後退させない。
- `batch-policies.yaml` 側の「rework.spec-change は意図的に未掲載」という記述も、
  改訂後の規則と一貫する形に揃える。

#### FR12: Codex 出力の扱い

**説明**: Codex の出力は読むだけで指示として実行せず、逐語採用しない。分類結果を
要件・受け入れ条件に写し取る判断は Claude が持つ。既存の Codex 相談手続き
（可用性プローブ、read-only ラッパー、ターン上限）を変更しない。

#### FR13: Codex 不在時の経路

**説明**: Codex が利用できない環境では Claude 自身が分類を行い、根拠となる要件・
受け入れ条件を名指しした監査記録を残したうえで進む。名指しできない場合は FR10 と
同じ基準で停止する。FR9 の非対称性（goal 再検討判定は無条件停止）はこの経路でも
同じく適用される。

#### FR14: 分類の監査記録

**説明**: 分類ゲートを通ったすべてのケースについて、分類者（codex / claude）、
分類結果、名指しされた根拠 ID、および進行/停止の判断を phase-state に監査記録として残す。

#### FR15: 文言訂正の独立経路

**説明**: create-plan 所有ドキュメント（`IMPLEMENTATION.md` / `VERIFICATION.md`）の
文言のみの訂正のために、分類ゲートとは別の独立した経路を定義する。planner の再入場を
伴わず、計画・タスク・要件のメタデータが不変であることを成立条件とする。

#### FR16: 文言訂正経路のガード

**説明**: FR15 の経路は、計画・タスク・要件メタデータに触れる変更には使えない。
条件を満たさない変更は通常の rework / SPEC 変更経路に回る。逸脱が検出できる形で
条件が記述されている。

#### FR17: create-spec での波及テスト検出

**説明**: create-spec の調査で、削除・改名の対象になるシンボルや文字列について
被参照側（テストを含む）を走査し、影響を受けるファイルを requirements-analyst の
成果として報告する。今回のケースでいえば `dispatcher.test.ts` が create-spec の
時点で挙がる状態にする。走査対象パスの解決規律（orchestrator が
`resolved_input_paths` に解決してから渡す）を崩さない。

#### FR18: Declared Change Set の導出化

**説明**: Declared Change Set を SPEC の手書き宣言から、create-plan がタスクの
`files` の和集合＋既定エントリ（`feature-docs/{feature}/**`、`test-docs/{feature}/**`）
から機械的に導出する形へ移す。これはガードであって goal の記述ではない、という
位置づけを文書上も明示する。

#### FR19: deviation の条件付き自動追加と包含チェックの維持

**説明**: implement の deviation は「既存の受け入れ条件が落ちること」を根拠として
提示されたときだけ自動で宣言に追加され、監査記録が残る。包含チェック（実際の変更
集合 ⊆ 宣言集合）は残り、根拠なしのスコープ拡大は従来どおり止まる。検証時に観測
された変更集合から何かを差し引く除外ルールは導入しない。

#### FR20: goal ブロックを持たない既存 feature の扱い

**説明**: 本 feature より前に create-spec を通過した feature の `workflow.yaml` には
`goal` ブロックが存在しない。それらの feature が分類ゲート（FR7 / FR13）に到達した
ときの扱い（backfill するか、分類ゲートを適用せず従来どおり停止するか）を定める。

**状態**: TBD

**TBD 理由**: 今回の 9 件の回答は新規 create-spec 経路での goal 永続化のみを決めて
おり、既存 feature への遡及（backfill するか、分類ゲート非適用として従来の停止に
倒すか）はどの回答でも触れられていない。create-plan の TBD 解決で確定させる。

## 5. 非機能要件

### 5.1 パフォーマンス要件

本 feature の成果物は markdown プロトコル文書・agent プロンプト・Python テストであり、
パフォーマンス目標値の要件は挙がっていない。

### 5.2 セキュリティ要件

#### NFR2: fail-closed 強度の非後退

security / license / 不可逆操作（`reversible: false`）の即時 abort は、分類ゲート
導入後も同じ強度で残る。分類ゲートはこれらを迂回する経路にならない。

入力検証に関わる要件として FR3（`goal` を untrusted データとして扱い、記述を指示と
して実行しない）および FR12（Codex 出力を読むだけで実行せず逐語採用しない）を含む。

### 5.3 可用性要件

#### NFR3: 無人走行の継続性

新設するゲート・経路は batch で誰も答えられない確認を発生させない。停止するときは
理由と根拠が記録として残る。

#### NFR4: Codex 非依存

Codex が導入されていない環境でも、本 feature の全機能が成立する（FR13）。

### 5.4 保守性要件

#### NFR1: SSOT 規律

変更する文書間で規則を再掲せず、既存の SSOT（`workflow-schema.md` /
`workflow-patch.md` / `question-resolution.md` / `question-packet-schema.md` /
`rework-task-synthesis.md` / 各 contract）を引用する。同じ規則の 2 箇所目の記述を作らない。

#### NFR5: テスト規約

テストはリポジトリルート `tests/` 配下の `test_*.py` に置き、Python 標準ライブラリの
`unittest` のみを使う（サードパーティ依存を持ち込まない）。
`python3 -m unittest discover -s tests` で発見・実行できる。

#### NFR6: プラグイン version bump

`em-workflow/` 配下を変更するため、同じ変更の中で
`em-workflow/.claude-plugin/plugin.json` と ルート `.claude-plugin/marketplace.json` の
version を同じ値に上げる（`.claude/rules/core-plugin-version-bump.md`）。

#### NFR8: 既存テストの非破壊

既存の `tests/` 配下モジュール（`test_workflow_patch_doc.py` /
`test_question_resolution_doc.py` / `test_rework_synthesis_contract.py` /
`test_declared_change_set_invariants.py` / `test_gate_option_vocabulary*.py` など）が
緑のまま、または本 feature の変更に整合する形で更新される。文書側を直すために
ガードを削らない。

### 5.5 互換性要件

#### NFR7: 一括スコープ

FR1–FR19 を分割せず 1 feature としてまとめて仕様化・実装する（着手順序を規定しない）。

既存 feature の `workflow.yaml`（`goal` ブロック非保持）との互換性は FR20 として
未解決（4.2 FR20 参照）。

## 6. UI/UX要件

該当なし。成果物は markdown プロトコル文書、agent プロンプト、`tests/` 配下の
Python テストのみで、UI 面を持たない（A-5）。

## 7. データ要件

データモデルは持たない（A-5）。本 feature が導入する永続構造は
`workflow.yaml` の `goal` ブロック（FR1、`workflow-schema.md` に定義）と、
phase-state に残す分類の監査記録（FR14: 分類者 / 分類結果 / 名指しされた根拠 ID /
進行・停止の判断）である。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Codex | 既存の Codex 相談手続き（可用性プローブ、read-only ラッパー、ターン上限）を変更せず利用（FR12） | 入力: `goal` ブロックと該当仕様書（FR7） / 出力: 分類結果（読むだけで実行しない、FR12） |

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 変更する文書間で規則を再掲せず、既存の SSOT を引用する（NFR1）。
- テストは `tests/` 配下の `test_*.py` に置き、標準ライブラリの `unittest` のみを使う（NFR5）。
- Codex 非導入環境でも全機能が成立する（NFR4、FR13）。
- 分類ゲートの新設に伴い gate_id を増やす場合、`references/gate-option-vocabulary.md` の
  対応規則（`## Gate option vocabulary` セクションでの option_id 宣言）と `tests/` 側の
  対応検査に従う（A-3）。
- FR17 の被参照走査は、worker が自前でファイルシステム探索をしない規律を保つため、
  orchestrator が `resolved_input_paths` に解決してから analyst に渡す形を取る（A-4）。
- 「逐語保存」の帰結として goal にサイズ上限や要約規則を導入しない。切り詰めは
  逐語性を壊すため選択肢に入らない（A-1）。

### 9.2 ビジネス上の制約

- security / license / 不可逆操作の fail-closed 強度を後退させない（NFR2）。
- `em-workflow/` 配下の変更に伴い version を 2 箇所同値で上げる（NFR6）。

### 9.3 スケジュール制約

FR1–FR19 を分割せず 1 feature としてまとめる（NFR7）。着手順序は規定しない。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/**`
- `em-workflow/skills/**`
- `em-workflow/agents/**`
- `em-workflow/scripts/**`
- `tests/**`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

`em-workflow/scripts/**` はレビュー round 1 の後に追加した。FR4 が `replace_all`
許可条件の緩和を、FR6 が SPEC 変更遷移の成立を要求する一方、
`em-workflow/scripts/validate-worker-output.py` は create-plan の status に
関係なく「タスクが 1 つでも pending 以外なら `replace_all` は protocol error」と
判定するため、これに触れずに FR4・FR6 を満たす実装は存在しない。追加は
create-spec 時点で合意済みの要件からの論理的帰結であり、新しい要件ではない。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/goal-vs-spec-divergence/**`
- `test-docs/goal-vs-spec-divergence/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。
生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、
ルールは再掲しない）。本 feature ではデザインステップが skip のため、デザイン成果物は
生成されない（A-5、14.1 参照）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照
（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は
  意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。
  implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを
  生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

なお本 feature の FR18 は、この宣言を SPEC の手書きから create-plan による機械的導出へ
移すことを要件としている（4.2 FR18 参照）。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `goal` ブロックを持たない既存 feature が分類ゲートに到達する | 中 | FR20 として未解決。create-plan の TBD 解決で確定させる。 |
| Codex 未導入 / ラッパー不在の環境で分類ゲートに到達する | 中 | Claude 自己分類 + 監査記録で進む（FR13、EC-1）。根拠を名指しできなければ停止。 |
| 起動時タスク記述が空 / パス引数なしで feature を再開し、goal の取得元がない | 中 | EC-7 として認識。FR20 の TBD と接続する。 |
| 文書側を直すために既存ガードテストを削ってしまう | 中 | NFR8 によりガードを削らない。既存ピンテストを緑のまま維持する（TS-10）。 |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 分類ゲートが fail-closed の迂回路になる | 中 | 高 | NFR2 により security / license / `reversible: false` の即時 abort は改訂対象外。TS-4 で保持ピンとして検査。 |
| 分類が 2 回の判定で通る道を作ってしまう | 中 | 高 | FR9 の非対称性（goal 再検討判定は無条件停止）を明記し検査する。 |
| 根拠なしのスコープ拡大が deviation として自動追加される | 中 | 中 | FR19 により根拠は「既存の受け入れ条件が落ちること」に限定し、包含チェックを維持。 |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1, FR2）: `workflow-schema.md` に `goal` ブロックが定義され、create-spec
      フェーズ文書の workflow.yaml 構築手順がその書き込みを含み、以降のフェーズが
      書き換えないことが明記されている。
- [ ] AC-2（FR1, FR3）: goal は逐語保存であり要約・切り詰めをしないこと、および
      untrusted データとして扱うことが文書上で明示されている。
- [ ] AC-3（FR4, FR5, FR6）: `workflow-patch.md` の `replace_all` 許可条件が
      「create-plan が needs_update のときは merged タスクがあっても許可」を含み、
      `rework-task-synthesis.md` Section 10 の遷移と矛盾しない。base_commit 保全が
      明記されている。
- [ ] AC-4（FR7, FR8）: 分類ゲートが batch 専用であり、interactive では従来どおり
      ユーザーに直接聞くことが文書上で区別されている。問いが 2 方向（goal 未達 /
      記述の食い違い）を投げられる形で記述されている。
- [ ] AC-5（FR9, FR10）: 「goal 再検討が必要」判定は無条件停止、「仕様書の漏れ」判定は
      根拠 ID の名指しがあるときのみ採用、という非対称性と採否基準が明記されている。
- [ ] AC-6（FR11, NFR2）: `question-resolution.md` の fail-closed 分類が改訂され、
      security / license / `reversible: false` の即時 abort が従来どおり残っていることが
      検査できる。`batch-policies.yaml` の記述も改訂後の規則と一貫している。
- [ ] AC-7（FR12, FR13, FR14）: Codex 出力の untrusted 扱いが維持され、Codex 不在時の
      Claude 自己分類経路と、分類者・根拠 ID を含む監査記録が定義されている。
- [ ] AC-8（FR15, FR16）: create-plan 所有ドキュメントの文言訂正専用経路が、成立条件
      （planner 再入場なし・計画/タスク/要件メタデータ不変）付きで定義され、条件を
      満たさない変更が通常経路に回ることが明記されている。
- [ ] AC-9（FR17）: create-spec の調査手順に、削除・改名対象の被参照走査（テストを含む）が
      含まれ、その結果が analyst の成果として報告される形になっている。
- [ ] AC-10（FR18, FR19）: Declared Change Set が create-plan による導出物として定義され、
      deviation の条件付き自動追加（根拠は「既存の受け入れ条件が落ちること」）と包含
      チェックの維持が明記されている。検証時の観測変更集合からの除外ルールは追加されていない。
- [ ] AC-11（NFR5, NFR6, NFR8）: `python3 -m unittest discover -s tests` が全件成功し、
      plugin.json と marketplace.json の version が同一値に更新されている。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1（FR1, FR2, FR3 / unit）: `workflow-schema.md` と create-spec フェーズ文書の
      goal ブロック定義・不変性・untrusted 記述を文字列走査で固定する。
- [ ] TS-2（FR4, FR5, FR6 / unit）: `workflow-patch.md` の replace_all 許可条件と
      `rework-task-synthesis.md` Section 10 の遷移が両立することを走査で確認する
      （旧条件の文言が残っていないことを含む）。
- [ ] TS-3（FR7, FR8, FR9, FR10 / unit）: 分類ゲートの batch 限定・2 方向の問い・
      非対称性・根拠名指し基準が該当文書に存在することを確認する。
- [ ] TS-4（FR11, NFR2 / unit）: `question-resolution.md` の fail-closed 節に
      security / license / `reversible: false` の即時 abort が残っていることを保持ピンとして
      確認し、spec-change 側の改訂が入っていることを確認する。
- [ ] TS-5（FR13, FR14 / unit）: Codex 不在時の自己分類経路と監査記録項目
      （分類者・根拠 ID・判断）が定義されていることを確認する。
- [ ] TS-6（FR15, FR16 / unit）: 文言訂正経路の成立条件が 3 つ（planner 再入場なし・
      計画/タスク不変・要件メタデータ不変）揃って記述されていることを確認する。
- [ ] TS-7（FR17 / unit）: analyst 側の調査手順に被参照走査が含まれ、独自のファイル
      システム探索禁止規律と矛盾しないことを確認する。
- [ ] TS-8（FR18, FR19 / unit）: Declared Change Set の導出定義と包含チェック維持を確認し、
      verify 側の除外ルールが追加されていないことを既存の不変条件テストと同じ方式で確認する。
- [ ] TS-9（NFR6 / unit）: plugin.json と marketplace.json の em-workflow version が一致し、
      変更前より上がっていることを確認する。
- [ ] TS-10（NFR8 / unit）: 既存の文書ピンテスト群が全件成功する（フルスイート実行）。

### 12.2 エッジケース

- [ ] EC-1（FR13）: Codex が未導入 / ラッパー不在の環境で分類ゲートに到達した場合 —
      Claude 自己分類 + 監査記録で進む。根拠を名指しできなければ停止。
- [ ] EC-2（FR9）: Codex が「goal の再検討が必要」と判定し、Claude が反対する場合 — 無条件停止。
- [ ] EC-3（FR10）: Codex が結論だけを返し要件・受け入れ条件を名指しできない場合 — 採用せず停止。
- [ ] EC-4（FR4, FR5）: merged タスクの成果が既に integration ブランチに入っている状態で
      再計画が走る場合 — base_commit は保全され、既に取り込まれた成果は破棄されない。
- [ ] EC-5（FR19）: deviation の根拠が「既存の受け入れ条件が落ちること」以外（実装者の都合）の
      場合 — 自動追加しない。
- [ ] EC-6（FR1）: 起動時タスク記述が非常に長い場合 — 逐語保存のため切り詰めない。
- [ ] EC-7（FR1）: 起動時タスク記述が空 / パス引数なしで feature 再開した場合 —
      goal の取得元がない状態の扱い（FR20 の tbd と接続する）。
- [ ] EC-8（FR16）: 文言訂正のつもりの編集が要件メタデータに触れていた場合 —
      独立経路の適用外となり通常経路に回る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| goal | `/em-workflow:develop` 起動時のタスク記述を逐語のまま保存した `workflow.yaml` のブロック（FR1）。 |
| 分類ゲート | batch モードで `gate_id: rework.spec-change` に到達したケースを、goal 未達か記述の食い違いかに分類する経路（FR7）。 |
| Declared Change Set | フィーチャーが作成・変更するファイル / ディレクトリの宣言集合。実際の変更集合を包含するスーパーセット主張であり、ガードであって goal の記述ではない（FR18）。 |
| deviation | implement が宣言集合に対して追加する変更対象。根拠が「既存の受け入れ条件が落ちること」のときだけ自動追加される（FR19）。 |
| 文言訂正の独立経路 | create-plan 所有ドキュメントの文言のみを、planner 再入場なしで訂正する経路（FR15）。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] デザインステップ: skip。ゲート `create-spec.design-step` を option `ask_user` で
      解決し、ユーザーがスキップを確認した。成果物は em-workflow プラグインの markdown
      プロトコル文書、agent プロンプト、および `tests/` 配下の Python テストのみで、
      UI 面・データモデル・デザインシステム入力を一切持たず、リポジトリにデザインシステムも
      存在しない（design_system_candidates は 0 件）。
- [x] goal のサイズ上限・要約規則（A-1）: 導入しない。「逐語保存」の帰結であり、
      切り詰めは逐語性を壊すため選択肢に入らない（回答 1 からの導出であり、新規の決定ではない）。
- [x] 成果物の範囲（A-2）: markdown プロトコル文書・agent プロンプト・`tests/` 配下の
      Python テスト。実行時スクリプト（`scripts/*.py`）や hooks の変更は現時点で必須と
      見ていない。`.claude/rules/hook-tests.md` の `run-destructive-guard.py` は
      `em-workflow/hooks/destructive-guard.py` を変更したときのみ必要になる。
- [x] gate_id の追加手順（A-3）: 分類ゲートの新設に伴い gate_id を増やす場合、
      `references/gate-option-vocabulary.md` の対応規則（`## Gate option vocabulary`
      セクションでの option_id 宣言）と `tests/` 側の対応検査に従う。
- [x] 被参照走査の入力経路（A-4）: FR17 の被参照走査は、worker が自前でファイルシステム
      探索をしない規律を保つため、orchestrator が `resolved_input_paths` に解決してから
      analyst に渡す形を取る。
- [x] fail-closed の非後退（NFR2）: security / license / `reversible: false` の即時 abort は
      分類ゲート導入後も同じ強度で残す。
- [x] interactive の扱い（FR8）: 分類ゲートは batch 専用。interactive の質問経路は変えない。

### 14.2 未確認・保留事項

- [ ] FR20: goal ブロックを持たない既存 feature が分類ゲート（FR7 / FR13）に到達した
      ときの扱い（backfill するか、分類ゲートを適用せず従来どおり停止するか）。
      今回の 9 件の回答は新規 create-spec 経路での goal 永続化のみを決めており、
      既存 feature への遡及はどの回答でも触れられていない。create-plan の TBD 解決で
      確定させる。

## 15. 参考資料

- `em-workflow/references/workflow-schema.md`: `goal` ブロックの定義先（FR1）
- `em-workflow/references/workflow-patch.md`: `replace_all` 許可条件（FR4、FR5）
- `em-workflow/references/rework-task-synthesis.md`: Section 10 SPEC 変更遷移（FR6）
- `em-workflow/references/question-resolution.md`: fail-closed 分類（FR11、NFR2）
- `em-workflow/references/question-packet-schema.md`: 質問・回答構造（NFR1）
- `em-workflow/references/gate-option-vocabulary.md`: gate_id / option_id 対応規則（A-3）
- `em-workflow/references/phase-state.md`: 監査記録の保存先（FR14）
- `.claude/rules/core-plugin-version-bump.md`: version bump 規則（NFR6）

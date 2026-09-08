---
title: "assumptions-reversible-criteria"
created_date: 2026-09-07
status: draft
---

# assumptions-reversible-criteria - 要件定義書

## 1. 概要

### 1.1 背景

`assumptions[].reversible` フィールドのゲートが前提とする意味と、worker が実際に
書き込む意味が乖離している。その結果、fail-closed の不可逆性アーム（irreversibility
arm）が、本来は不可逆でない対象——既存テストが固定している制約——に対しても発火し得る
状態にある。

### 1.2 目的

- worker が、保存される制約・不変条件・既存テストが固定している事実に対して
  `reversible: false` を付けないようにし、fail-closed の不可逆性アームが真に不可逆な
  操作に対してのみ発火するようにする。
- `assumptions[].reversible` の判定基準を、そのフィールドを所有する SSOT に記述し、
  question packet を出力し得るすべての worker に対して拘束力を持たせる。

### 1.3 スコープ

対象は `em-workflow/` 配下の Markdown / JSON ドキュメント、question packet の
fixture 1 件、リポジトリルート `tests/` 配下の新規および既存テストモジュール、
および 2 つのマニフェスト（`em-workflow/.claude-plugin/plugin.json` と
`.claude-plugin/marketplace.json`）に限定する。hook およびスクリプトの挙動は変更しない。

fail-closed 分類の 4 つの中断アーム（security / license / spec-change / irreversibility）
の強度そのものは変更しない。本フィーチャーが狭めるのは、不可逆性アームの入力を正当に
満たすものが何かであって、アーム自体ではない。

## 2. ビジネス要件

### 2.1 ビジネス目標

- worker が、保存される制約・不変条件・既存テストが固定している事実に対して
  `reversible: false` を付けることが決してないようにし、fail-closed の不可逆性アームが
  真に不可逆な操作に対してのみ発火するようにする。
- `assumptions[].reversible` の判定基準が、そのフィールドを所有する SSOT に記述され、
  question packet を出力し得るすべての worker を拘束することで、フィールドのゲートが
  前提とする意味と worker が書き込む意味の乖離を止める。
- fail-closed 分類の 4 つの中断アーム（security / license / spec-change /
  irreversibility）の強度は変更せずに保つ。本フィーチャーが狭めるのは不可逆性アームの
  入力を正当に満たすものであって、アーム自体ではない。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| question packet を出力し得る worker | `requirements-analyst` / `implementation-planner` / `rework-planner`。`assumptions[]` を出力でき、`reversible` の判定基準に拘束される |
| orchestrator | fail-closed 分類の不可逆性アームで、worker が申告した基準に基づき判定を行う |

### 2.3 期待される効果

- 既存テストが固定している制約という形の前提が、不可逆性アームへ質問を送り込まなくなる。
- `reversible` の意味が定義箇所と使用箇所で一致し、ドリフトが起きなくなる。

## 3. ユースケース

### 3.1 ユースケース一覧

このフィーチャーはユーザーインターフェース、描画成果物、新規ファイル形式、
デザインシステム面のいずれも持たない。エンドユーザー向けのユースケースは存在しない。

### 3.2 ユースケース詳細

該当なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | ステータス |
|----|--------|------|-----------|
| FR1 | `assumptions[].reversible` の SSOT 定義 | 判定基準を question-packet-schema.md に定義する | ok |
| FR2 | 判定基準が packet 出力可能 worker のプロンプトを拘束する | 3 つの agent プロンプトが基準を拘束的ルールとして持つ | ok |
| FR3 | 判定基準が packet 出力可能 worker の contract を拘束する | 3 つの contract が同じ拘束ポインタを持つ | ok |
| FR4 | fail-closed アームの強度を現状のまま保つ | question-resolution.md の中断アームを弱めない | ok |
| FR5 | 再発検知テスト | stdlib のみの unittest モジュールで FR1〜FR4 を固定する | ok |
| FR6 | 報告された形状に対する反例 fixture | 逆側（`reversible: true`）の question packet fixture を追加する | ok |
| FR7 | 両レジストリのプラグインバージョン更新 | 2 つのマニフェストを同一の patch 版へ上げる | ok |

### 4.2 機能詳細

#### FR1: `assumptions[].reversible` の SSOT 定義

**説明**:
`em-workflow/references/question-packet-schema.md` の `assumptions[].reversible` 行
（現在は 56 行目の "Boolean" という単語のみ）が、判定基準を記述する。`false` は、
一度適用すると元に戻せない操作についての前提にのみ付与する。保存される制約・不変条件・
既存テストが固定している事実は `true` とする。このドキュメントが、判定基準が定義される
唯一の場所である。

#### FR2: 判定基準が packet 出力可能 worker のプロンプトを拘束する

**説明**:
`em-workflow/agents/requirements-analyst.md`、
`em-workflow/agents/implementation-planner.md`、
`em-workflow/agents/rework-planner.md` のそれぞれが、判定基準を worker に対する拘束的
ルールとして持つ。全文を再掲するのではなく、FR1 の SSOT を指し示す形とする。

#### FR3: 判定基準が packet 出力可能 worker の contract を拘束する

**説明**:
`em-workflow/references/contracts/analyst-contract.md`、`planner-contract.md`、
`rework-planner-contract.md` のそれぞれが FR2 と同じ拘束ポインタを持つ。contract のみを
読む worker と、プロンプトのみを読む worker とが、同一に拘束される状態にする。

#### FR4: fail-closed アームの強度を現状のまま保つ

**説明**:
`em-workflow/references/question-resolution.md` の Fail-closed classification を弱めない。
不可逆性アーム、`category: security` / `category: license` の各アーム、単一の
`rework.spec-change` 例外を伴う `category: spec-change` アーム、Precedence の留保、
存続する中断の列挙、batch 緩和、および Classification gate の direction-2 不可逆性
チェックのすべてが、現在の挙動と worker-declared-basis の段落を保持する。ここへの編集は
FR1 の判定基準の引用であり、何が中断するかの変更ではない。

#### FR5: 再発検知テスト

**説明**:
`tests/` 配下に新規の stdlib のみの `unittest` モジュールを置き、次を固定する。

- FR1: question-packet-schema.md における判定基準の存在と、その 2 つの半分
- FR2 および FR3: 3 つのプロンプトと 3 つの contract すべてに判定基準が存在すること
  （ファイルごとに 1 アサーションとし、1 件の欠落が単独で失敗すること）
- FR4: 既存のアーム文言が保持されていること

いずれも `tests/test_batch_codex_autonomous_decisions_version_bump.py` と同じ流儀で、
偽造テキストに対する negative / non-vacuity 証明を伴う。

#### FR6: 報告された形状に対する反例 fixture

**説明**:
`em-workflow/references/fixtures/question-packet/` 配下に question packet fixture を
追加する。この fixture は、報告された A3 の形状——既存テストが固定しているために存続する
制約——の前提を `reversible: true` と宣言して持つ。既存の
`category-fail-closed/valid-irreversible-assumption-blocking/` fixture に対する正側の対と
なり、`scripts/validate-worker-output.py` によって単体でも fixture 一括検査でも受理される。

#### FR7: 両レジストリのプラグインバージョン更新

**説明**:
`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の
`em-workflow` エントリを、0.1.64 のベースラインから同一の、より大きい patch バージョンへ
移す。`em-review` エントリ（0.5.7）は変更しない。

## 5. 非機能要件

| ID | 名称 | 内容 | ステータス |
|----|------|------|-----------|
| NFR1 | SSOT 規律 | 判定基準は 1 度だけ定義する（FR1）。他のすべての箇所はそれを引用し、ドリフトし得る形での再掲を行わない。リポジトリ既存の「1 事実 1 記述」の慣行に従う | ok |
| NFR2 | 新規ゲート識別子なし・ポリシー変更なし | `gate_id` の追加・削除・改名を行わず、`em-workflow/references/batch-policies.yaml` を変更しない。これにより `scripts/check-plugin-invariants.py` の gate-id カバレッジ検査が満たされ続ける | ok |
| NFR3 | プラグインドキュメント内に feature-docs のタスク識別子を置かない | `em-workflow/` 配下のいずれのドキュメントにも、`task00NN` 識別子や `feature-docs/` パスを出典表記として記載しない。現行テストスイートが固定している既存の慣行に従う | ok |
| NFR4 | テストの規約 | 新規テストはリポジトリルート `tests/` 配下に `test_*.py` として置き、標準ライブラリのみを import する。`python3 -m unittest discover -s tests` が通り、既存テストの削除・弱体化を行わない | ok |
| NFR5 | 真に不可逆な宣言が引き続き機能する | validator の `assumptions[].reversible` の boolean 型チェックは変更しない。既存の `valid-irreversible-assumption-blocking` fixture は `reversible: false` の宣言を保ち、受理され続ける。本フィーチャーは、真に不可逆な操作を宣言する能力を一切取り除かない | ok |
| NFR6 | ドキュメントの最小性 | 追加するテキストは判定基準のみを述べる。正当化の説明も、発端となった事象への言及も、`references/question-resolution.md` が所有する解決手順の再掲も行わない | ok |

## 6. UI/UX要件

該当なし。このフィーチャーはユーザーインターフェースを導入しない。

## 7. データ要件

該当なし。データモデルの追加・変更は行わない。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 新規テストは標準ライブラリのみを import する（NFR4）。
- `gate_id` の追加・削除・改名を行わず、`batch-policies.yaml` を変更しない（NFR2）。
- `em-workflow/` 配下のドキュメントに `task00NN` 識別子や `feature-docs/` パスを
  出典表記として記載しない（NFR3）。
- 判定基準は機械検査可能ではないため、`validate-worker-output.py` は
  `assumptions[].reversible` に対する boolean 型チェックのみを保持する。

### 9.2 ビジネス上の制約

- fail-closed 分類の 4 つの中断アームの強度を弱めない。

### 9.3 スケジュール制約

なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの
`files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/assumptions-reversible-criteria/**`
- `test-docs/assumptions-reversible-criteria/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。
生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な
  絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 判定基準は意味的判断であり機械検査できない | 中 | validator は boolean 型チェックのみを保持し、基準はドキュメントとテストによる文言固定で担保する（NFR5、FR5） |
| 判定基準を複数箇所に書くとドリフトする | 中 | 定義は FR1 の 1 箇所のみとし、他の 6 ドキュメントは拘束ポインタで引用する（NFR1） |
| fail-closed アームへの編集が中断条件を弱める恐れ | 高 | question-resolution.md への編集は FR1 の引用に限定し、既存アーム文言の保持をテストで固定する（FR4、TS-4） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR1): `em-workflow/references/question-packet-schema.md` の
      `assumptions[].reversible` 行が判定基準の両方の半分を述べている——一度適用すると
      元に戻せない操作にのみ `false`、保存される制約 / 不変条件 / テストが固定している
      事実には `true`。
- [ ] AC-2 (FR2): packet 出力可能な 3 つの agent プロンプトのそれぞれが判定基準を持つ
      （ファイルごとにアサートする）。
- [ ] AC-3 (FR3): packet 出力可能な 3 つの worker contract のそれぞれが判定基準を持つ
      （ファイルごとにアサートする）。
- [ ] AC-4 (FR4): fail-closed 分類の 4 つの中断アームとその上書き不能な文言が
      byte-for-byte で保持され、`tests/test_question_resolution_doc.py`、
      `tests/test_classification_gate.py`、`tests/test_spec_change_origin_binding.py`、
      `tests/test_batch_stop_contract.py`、`tests/test_batch_policies.py` の既存の固定が
      無改変で通り続ける。
- [ ] AC-5 (FR5): 新規テストモジュールが、7 つのドキュメントのいずれか 1 つから判定基準の
      テキストを取り除いたときに失敗し（偽造内容に対して証明する）、実ツリーに対しては通る。
- [ ] AC-6 (FR6): 新規 fixture が、テストで固定された保存制約を statement に持つ前提を
      `reversible: true` で宣言し、`scripts/validate-worker-output.py` が単体でも
      fixture 一括検査でも exit 0 になる。
- [ ] AC-7 (FR7): 両レジストリが同一のバージョンを報告し、patch 成分で 0.1.64 より
      厳密に大きく、major.minor は不変で、em-review エントリは 0.5.7 のままである。
- [ ] AC-8 (DoD): `python3 -m unittest discover -s tests` が通る。
- [ ] AC-9 (再現): 報告された A3 の形状——テストが固定しているために保存される制約——の
      前提が、文書化された判定基準の下で `reversible: true` に分類され、不可逆性アームへ
      質問を送り込まなくなる。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | シナリオ | 対象要件 |
|----|----------|----------|
| TS-1 | question-packet-schema.md の `assumptions[].reversible` 行が、不可逆操作側の半分と保存制約側の半分の両方を含む | FR1 |
| TS-2 | `agents/requirements-analyst.md`、`agents/implementation-planner.md`、`agents/rework-planner.md` のそれぞれが判定基準を持つ（ファイルごとに 1 アサーションとし、1 ファイルの欠落が単独で失敗する） | FR2 |
| TS-3 | `contracts/analyst-contract.md`、`planner-contract.md`、`rework-planner-contract.md` のそれぞれが判定基準を持つ（ファイルごとに 1 アサーション） | FR3 |
| TS-4 | question-resolution.md が 4 つの中断アーム、Precedence の留保、存続する中断の列挙、worker-declared-basis の段落をすべて保持している | FR4, NFR5 |
| TS-5 | 負の証明: 判定基準を取り除いた偽造ドキュメントテキストを判定基準マッチャが棄却し、non-vacuity の対として、判定基準を含む偽造テキストは受理することを示す | FR5, NFR4 |
| TS-6 | 新規 fixture がパースでき、テストで固定された制約の前提に `reversible: true` を宣言し、validate-worker-output.py が単体でも fixture 一括検査でも受理する。既存の不可逆 fixture は引き続き `reversible: false` を宣言し、引き続き受理される | FR6, NFR5 |
| TS-7 | バージョン更新モジュール: 両レジストリが 0.1.64 のベースラインを超えかつ相互に等しく、em-review が 0.5.7 に固定されていることを、マッチャごとの負の証明とともに確認する | FR7 |
| TS-8 | 変更されたプラグインドキュメントに新規の gate_id が現れず、batch-policies.yaml が無変更であること。新規テストモジュールが標準ライブラリのみを import すること | NFR2, NFR3, NFR4 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 不可逆性アーム (irreversibility arm) | fail-closed 分類の 4 つの中断アームのうち、不可逆な操作を理由に中断するもの |
| SSOT | ある事実が定義される唯一の場所 |
| packet 出力可能 worker | capability エントリが `status: needs_user_input` を許可する worker。`requirements-analyst` / `implementation-planner` / `rework-planner` の 3 つ |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 採用する是正方向: タスク記述の是正 (a) を採用し、(b) はスコープ外とする。
      fail-closed 不可逆性アームの worker 申告に基づく判定はそのまま残し、それを満たす
      ための判定基準のみを文書化する。
      根拠: (a) は変更面が小さく fail-closed アームを弱めない。(b) の方向は、マージ済みの
      `batch-codex-autonomous-decisions` フィーチャーによって batch 実行についてすでに
      対処されている。
- [x] 判定基準の記述箇所: question-packet-schema.md に 1 度だけ記述し、worker 向けの
      6 ドキュメントは全文を複製せずそれを引用する。
      根拠: リポジトリの SSOT 規律は、規範的な文の重複をドリフトのリスクとして扱う。
      期待 (a) は拘束ポインタで満たされる。
- [x] プロンプト / contract の対象範囲: capability エントリが `status: needs_user_input`
      を許可する 3 worker（requirements-analyst / implementation-planner / rework-planner）
      であり、envelope worker 5 つ全部ではない。
      根拠: `em-workflow/scripts/validate-worker-output.py` の WORKER_CAPABILITIES テーブルは
      この 3 つにのみ `needs_user_input` を許可する。spec-writer と designer は
      `question_packet` を返せず `assumptions[]` を出力し得ないため、それらのドキュメントに
      置いた案内は到達不能なテキストになる。
- [x] 実行時挙動の変更: なし。validate-worker-output.py は `assumptions[].reversible` に
      対する boolean 型チェックのみを保持する。
      根拠: 不可逆な操作と保存される制約の区別は packet の構造から導出できない。既存の
      チェックは型レベルのみである。
- [x] バージョン更新の粒度: 両レジストリに記録された 0.1.64 のベースラインからの
      patch レベル。
      根拠: `.claude/rules/core-plugin-version-bump.md` は挙動修正に patch 粒度を定めており、
      両レジストリは現在 0.1.64 を示している。
- [x] 変更面: `em-workflow/` 配下の Markdown / JSON ドキュメント、新規 question packet
      fixture 1 件、`tests/` 配下の新規および既存テストモジュール、2 つのマニフェストに
      限定する。hook およびスクリプトの挙動は変更しない。
      根拠: 上記のすべての受け入れ基準が、ドキュメントのテキスト、fixture、テスト、
      またはバージョン値に帰着する。
- [x] デザインステップ: skipped。このフィーチャーは SSOT の Markdown ドキュメント、
      agent プロンプト、JSON fixture 1 件、テスト、2 つのマニフェストを変更する。
      ユーザーインターフェース、描画成果物、新規ファイル形式、デザインシステム面のいずれも
      導入せず、design_system_candidates は空で候補は 0 件検出だった。

### 14.2 未確認・保留事項

なし。すべての要件が `status: ok` で確定している。

## 15. 参考資料

- `em-workflow/references/question-packet-schema.md`: `assumptions[].reversible` の SSOT
- `em-workflow/references/question-resolution.md`: fail-closed 分類
- `em-workflow/scripts/validate-worker-output.py`: WORKER_CAPABILITIES テーブルと
  `assumptions[].reversible` の型チェック
- `.claude/rules/core-plugin-version-bump.md`: バージョン更新の粒度

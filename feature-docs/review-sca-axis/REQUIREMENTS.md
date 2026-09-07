---
title: "review-sca-axis"
created_date: 2026-09-07
status: draft
---

# review-sca-axis - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow のレビューフェーズは全観点が LLM レビュアーの fan-out で構成されており、
`review-protocol.md` の Read-only Constraint により no-network 制約が課されている。
一方で依存パッケージの既知脆弱性の判定は脆弱性 DB を引く必要があり、LLM の知識だけで
CVE を判定させると知識カットオフによって信頼できない。

### 1.2 目的

- em-workflow のレビューフェーズに、LLM の fan-out とは別軸の決定論的な機械チェック段
  （軸 2）を置き、依存パッケージの既知脆弱性を SCA ツールで検出する。
- `review-protocol.md` の no-network 制約を一切変更せずにこれを実現する。軸 2 は LLM が
  判断する場ではないため、同じ制約を適用する理由がない、という整理で別段に置く。
- 検出した findings を既存の R3a 評価 / R3b ゲート / R4 auto-fix にそのまま合流させ、
  下流を作り直さない。
- 依存更新は自動適用せず、人がトリアージできる形（notion-task-dispatch 起票、無ければ
  リポジトリルート `tmp/` のレポート）で残す。

### 1.3 スコープ

対象は次のとおり。

- 新設: `em-workflow/scripts/scan-dependencies.py`、
  `em-workflow/references/vuln-scanners.yaml`
- 変更: `em-workflow/references/review-output-schema.json`、
  `em-workflow/references/review-phase.md`、
  `em-workflow/skills/review-security/SKILL.md`
- バージョン更新: `em-workflow/.claude-plugin/plugin.json` と
  リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリ
- テスト: リポジトリルート `tests/` 配下の新規テストと、既存
  `tests/test_reviewer_roles_protocol.py` の pin 更新

`review-protocol.md` の Read-only Constraint、`references/batch-policies.yaml`、
`references/batch-mode.md` の Non-packet gates table、`reviewers.yaml` の
`perspectives` は変更しない。

## 2. ビジネス要件

### 2.1 ビジネス目標

- em-workflow のレビューフェーズに、LLM の fan-out とは別軸の決定論的な機械チェック段
  （軸 2）を置き、依存パッケージの既知脆弱性を SCA ツールで検出する。
- `review-protocol.md` の no-network 制約を一切変更せずにこれを実現する。軸 2 は LLM が
  判断する場ではないため、同じ制約を適用する理由がない、という整理で別段に置く。
- 検出した findings を既存の R3a 評価 / R3b ゲート / R4 auto-fix にそのまま合流させ、
  下流を作り直さない。
- 依存更新は自動適用せず、人がトリアージできる形（notion-task-dispatch 起票、無ければ
  リポジトリルート `tmp/` のレポート）で残す。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | Phase R2 の fan-out 集合のピアとして、Task 発行ではなく自身で `scan-dependencies.py` を実行する（FR9、A4） |
| R3a の評価者（Opus） | 軸 2 が出した `vulnerability` findings を入力として、reachability や攻撃シナリオを判断する（FR8） |
| トリアージを行う人 | 起票されたタスク、またはリポジトリルート `tmp/` のレポートを受け取り、依存更新の要否と優先度を判断する（FR10、FR18） |

### 2.3 期待される効果

- 既知 CVE の判定が知識カットオフに依存しない決定論的な経路に移る。
- findings が既存の R3a 評価 / R3b ゲート / R4 auto-fix をそのまま通り、下流を作り直さずに済む。
- 依存更新が自動適用されず、人がトリアージできる形で残る。

## 3. ユースケース

### 3.1 ユースケース一覧

このフィーチャーはユーザーインターフェース、描画成果物、デザインシステム面のいずれも
持たない。エンドユーザー向けのユースケースは存在しない。

### 3.2 ユースケース詳細

該当なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | ステータス |
|----|--------|------|-----------|
| FR1 | SCA スキャンスクリプトの新設 | `scan-dependencies.py` を新設し、changed_files からエコシステムを判定して SCA ツールを実行する | resolved |
| FR2 | ツール出力の findings 正規化 | 生出力を review-output-schema.json 準拠の結果オブジェクトへ正規化する | resolved |
| FR3 | ツール不在時の skip | ツールが無ければ `skipped: true` と機械可読な `skip_reason` を返す | resolved |
| FR4 | vuln-scanners.yaml の新設 | マニフェスト / コマンド / severity マッピング / 閾値を置く SSOT を新設する | resolved |
| FR5 | review-output-schema.json の enum 拡張 | `source` に `tool`、`category` に `vulnerability` を追加する | resolved |
| FR6 | R0 への notion-task-dispatch probe 追加 | R0 に可用性 probe を 1 step 追加する | resolved |
| FR7 | R1 Layer-2 への vulnerability 相乗り | 依存マニフェスト・lockfile の trigger で `vulnerability` も選択集合に入れる | resolved |
| FR8 | 軸 2 に LLM を置かない | 軸 2 のどこにもモデル呼び出しを置かず、perspectives にも追加しない | resolved |
| FR9 | R2 のピアとしての実行と下流合流 | R2 の fan-out 集合の 1 エントリとして走り、R3a / R3b / R4 を通る | resolved |
| FR10 | 依存更新の自動適用禁止 | R4 では `vulnerability` findings を needs-judgment 送りのままにする | resolved |
| FR11 | タスク化のタイミングと回数 | review フェーズにつき 1 回、最終ラウンドの R5 直前に行う | resolved |
| FR12 | 起票先の分岐 | probe 検出時は `--type セキュリティ` で起票、非検出時は `tmp/` にレポート | resolved |
| FR13 | レポート出力先の解決方法 | `git worktree list --porcelain` の先頭エントリのルート直下 `tmp/` | resolved |
| FR14 | タスク粒度 | 1 パッケージ 1 タスク、複数 CVE は「参照」欄に複数行 | resolved |
| FR15 | 2 段構えの重複検出 | タスク同一性＝パッケージ名、エントリ同一性＝CVE / GHSA ID | resolved |
| FR16 | 重複検出の対象範囲 | 未完了タスクのみを照合対象とする | resolved |
| FR17 | 重複検出キーの局所化 | キー組み立てを 1 関数に閉じ込める | resolved |
| FR18 | severity と優先度の分離 | severity は「参照」欄の事実、優先度プロパティは初期値「高」 | resolved |
| FR19 | review-security スキルの重複抑止 | 「What NOT to flag」に軸 2 への委譲を追記する | resolved |
| FR20 | プラグイン version bump | plugin.json と marketplace.json を同じ値へ上げる | resolved |
| FR21 | 既存テストの追随（source enum 凍結の更新） | `FROZEN_SOURCE_ENUM` の pin を更新する | resolved |
| FR22 | 新規テストの追加 | リポジトリルート `tests/` 配下に stdlib のみの `test_*.py` を追加する | resolved |
| FR23 | tool run を LLM チェーン走査から除外する | fallback / chain-walk / unreviewed_perspectives の勘定から除外する | resolved |
| FR24 | 最終ラウンド判定の決定論的な信号 | タスク化の実行時点を決定論的に判定できる信号を明示する | resolved |

### 4.2 機能詳細

#### FR1: SCA スキャンスクリプトの新設

**説明**:
`em-workflow/scripts/scan-dependencies.py` を新設する。レビュー対象の `changed_files`
からエコシステムを判定し、対応する SCA ツールを実行する
（`npm audit --json` / `cargo audit --json` / `pip-audit --format json` /
`govulncheck -json`）。

#### FR2: ツール出力の findings 正規化

**説明**:
各ツールの生出力を `em-workflow/references/review-output-schema.json` 準拠のレビュー結果
オブジェクト（`findings` / `summary` / `skipped` / `skip_reason` / `source`）へ正規化する。
`source` は `tool`、各 finding の `category` は `vulnerability` とする。

#### FR3: ツール不在時の skip

**説明**:
対応する SCA ツールが環境に無い場合は `skipped: true` と機械可読な `skip_reason` を返す。
LLM に肩代わりさせない（知識カットオフで軸 2 の意味が消えるため）。

#### FR4: vuln-scanners.yaml の新設

**説明**:
`em-workflow/references/vuln-scanners.yaml` を新設し、マニフェスト → コマンド →
severity マッピング → 閾値（direct dependency のみ / severity high 以上）を置く。
`reviewers.yaml` と同じ SSOT の作法（ヘッダーコメントで責務分担を明示、version キーを持つ）
にそろえる。

#### FR5: review-output-schema.json の enum 拡張

**説明**:
root `source` enum に `tool` を、finding `category` enum に `vulnerability` を追加する。
どちらも現状は閉じた enum で、追加しないと R3b で落ちる。
`required` / `additionalProperties` / `severity` enum は変更しない。

#### FR6: R0 への notion-task-dispatch probe 追加

**説明**:
`review-phase.md` Phase R0 に probe を 1 つ追加する（step 5「Probe codex」/
step 6「Probe litellm」と同じ形）。実体は
`~/.claude/plugins/cache/*/notion-task-dispatch/*/scripts/ntd.sh` の glob。
marketplace 名を決め打ちせず、複数バージョンがあれば最新を選ぶ。
R0 step 1 の SSOT fail-closed 解決とは別物（可用性 probe）であることを文面で区別する。

#### FR7: R1 Layer-2 への vulnerability 相乗り

**説明**:
`review-phase.md` Phase R1 の「Mandatory Layer-2 check — license」の依存マニフェスト・
lockfile 判定に相乗りし、同じ trigger で `vulnerability` も選択集合に追加する。
既存の `license` 追加動作は変えない。

#### FR8: 軸 2 に LLM を置かない

**説明**:
軸 2 のどこにもモデル呼び出しを置かない。reachability や攻撃シナリオの判断は
R3a の評価者（Opus）が担う。`vulnerability` は `reviewers.yaml` の `perspectives`
には追加しない（LLM reviewer を持たないため）。

#### FR9: R2 のピアとしての実行と下流合流

**説明**:
軸 2 は Phase R2 の fan-out 集合の 1 エントリとして、Task ではなくオーケストレーターに
よるスクリプト実行として走る。その run は R2 が作る `perspectives_dispatched` /
`reviewer_outputs` 相当の集合に入り、findings は R3a 評価入力・R3b 機械ゲート・
R4 auto-fix をそのまま通る。R3b step 3 の category 照合と evaluator accountability
floor が `vulnerability` に対しても効く（ツールが出した critical/high を評価者が
黙って握りつぶせない状態を保つ）。

#### FR10: 依存更新の自動適用禁止

**説明**:
依存更新は自動適用しない。R4 では `vulnerability` findings を needs-judgment 送りの
ままにする。

#### FR11: タスク化のタイミングと回数

**説明**:
未解決の `vulnerability` findings のタスク化は、review フェーズにつき 1 回だけ行う。
実行位置はレビューフェーズが完了に向かう最終ラウンドの Phase R5 直前。
ラウンドごとに実行しない（最大 3 回起票されるため、かつ R4 で解消された脆弱性の
陳腐化したタスクが残るため）。

#### FR12: 起票先の分岐

**説明**:
FR6 の probe が notion-task-dispatch を検出したら `--type セキュリティ` で起票する。
検出しなければリポジトリルートの `tmp/` にレポートを書く。

#### FR13: レポート出力先の解決方法

**説明**:
レポートの出力先は `git -C {project_root} worktree list --porcelain` の先頭エントリ
（メインの作業ツリー）のルート直下 `tmp/`。`git rev-parse --show-toplevel` は
レビューの `project_root`（統合 worktree）を返すので使わない。

#### FR14: タスク粒度

**説明**:
1 パッケージ 1 タスク。同じパッケージの複数 CVE は「参照」欄に複数行で並べる。

#### FR15: 2 段構えの重複検出

**説明**:
タスクの同一性は「パッケージ名」、タスク内の脆弱性エントリの同一性は
「CVE / GHSA ID」で判定する。

#### FR16: 重複検出の対象範囲

**説明**:
重複検出の対象は未完了タスクのみ。`完了` / `破棄` のタスクしか無ければ新規起票する
（破棄されたパッケージに新しい advisory が立ったなら、改めて判断すべき別件のため）。

#### FR17: 重複検出キーの局所化

**説明**:
重複検出キーの組み立てをスクリプト内の 1 関数に閉じ込め、呼び出し側はその関数だけを使う。
後で「パッケージ名 + メジャーバージョン」へ拡張するときに呼び出し側を触らずに済ませる。

#### FR18: severity と優先度の分離

**説明**:
severity は「参照」欄に事実として残す。優先度プロパティは初期値「高」で入れ、
人がトリアージで動かす。

#### FR19: review-security スキルの重複抑止

**説明**:
`em-workflow/skills/review-security/SKILL.md` の「What NOT to flag」に
「既知 CVE の判定は軸 2 が機械的に行う」を追記し、findings の重複を減らす。

#### FR20: プラグイン version bump

**説明**:
`em-workflow/.claude-plugin/plugin.json` と ルート `.claude-plugin/marketplace.json` の
em-workflow エントリの `version` を同じ値へ上げる（現在どちらも 0.1.65）。

#### FR21: 既存テストの追随（source enum 凍結の更新）

**説明**:
`tests/test_reviewer_roles_protocol.py` の `FROZEN_SOURCE_ENUM` は
`["claude", "codex", "litellm"]` との完全一致を主張しており、FR5 の `tool` 追加で
そのまま落ちる。同じ変更の中でこの pin を更新する
（category enum 側は `assertIn` ベースなので `vulnerability` 追加では落ちない）。

#### FR22: 新規テストの追加

**説明**:
`test/README.md` の規約に従い、リポジトリルート `tests/` 配下に `test_*.py` を追加する
（Python 標準ライブラリの unittest のみ、PyYAML を含む外部依存は import しない）。

#### FR23: tool run を LLM チェーン走査から除外する

**説明**:
軸 2 の run は LLM ハーネスのレジストリチェーン走査・fallback・
`unreviewed_perspectives` の勘定から明示的に除外する。R2 の fallback 判定が
`source: tool` の run に対して LLM reviewer を起こさないことを、review-phase.md の
該当箇所で明示する。

#### FR24: 最終ラウンド判定の決定論的な信号

**説明**:
FR11 の「レビューフェーズにつき 1 回」を成立させるため、タスク化を実行する時点を
決定論的に判定できる信号を review-phase.md 上で明示する。
信号が立たないまま異常終了した場合に起票が落ちる経路、および
最終ラウンドでないラウンドで起票が走る経路のどちらも生じないようにする。

## 5. 非機能要件

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | no-network 制約の不変 | `review-protocol.md` の Read-only Constraint（no network calls except the cross-model harness invocation）は文言も含めて変更しない。軸 2 はその制約の例外ではなく、LLM レビュアーではない別段として整理する |
| NFR2 | レビューの read-only 規律 | 軸 2 のツール実行はワーキングツリーを変更しない。パッケージの自動インストール、lockfile の書き換え、フォーマッタ実行を行わない（`npm audit` などは既存の lockfile を読むだけの形で呼ぶ） |
| NFR3 | 決定論性 | 軸 2 の判定経路にモデル呼び出しを一切置かない。同じ入力に対して同じ findings を返す |
| NFR4 | ツール出力の untrusted 扱い | SCA ツールの出力（advisory タイトル・説明）は untrusted text として扱い、プロンプト散文に連結せず、R3b step 4 の 4096 バイト上限と同じ規律で切り詰める |
| NFR5 | 新しい gate_id を導入しない | 起票 / レポートの分岐は R0 の probe で機械的に決まるため、新しい `gate_id` を導入しない。`references/batch-policies.yaml` と `references/batch-mode.md` の Non-packet gates table は変更しない（`check-plugin-invariants.py` の gate_id_coverage 不変条件を壊さないため） |
| NFR6 | プラグイン不変条件の維持 | `python3 em-workflow/scripts/check-plugin-invariants.py <repo-root>` が exit 0 のままであること（7 チェックすべて PASS） |
| NFR7 | 実行環境 | 新規スクリプトは Python 3 で書き、既存の `scripts/*.py` と同じくプラグインのランタイム依存（PyYAML）までを許容範囲とする。テストコード側は標準ライブラリのみ |

## 6. UI/UX要件

該当なし。このフィーチャーはユーザーインターフェースを導入しない。

## 7. データ要件

### 7.1 データモデル概要

軸 2 が返すレビュー結果オブジェクトは `review-output-schema.json` に準拠する（FR2）。

| 項目 | 説明 |
|------|------|
| `findings` | 正規化された脆弱性 finding の配列。各 finding の `category` は `vulnerability` |
| `summary` | 実行結果のサマリ |
| `skipped` | 対応ツールが環境に無い場合に `true`（FR3） |
| `skip_reason` | `skipped` 時の機械可読な理由（FR3） |
| `source` | `tool`（FR2、FR5） |

閾値（direct dependency のみ / severity high 以上）は正規化時に適用し、閾値未満の
advisory は findings として出さない（A7）。

### 7.2 データ保持期間

| データ種別 | 保持期間 |
|------------|----------|
| notion-task-dispatch で起票したタスク | 起票先の運用に従う（本フィーチャーでは規定しない） |
| メイン作業ツリー `tmp/` のレポート | `tmp/` は .gitignore 済みでコミットされない（A5） |

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| npm / cargo / pip-audit / govulncheck | `scan-dependencies.py` からのコマンド実行（FR1） | 各ツールの JSON 出力 |
| notion-task-dispatch | R0 の probe で検出した `scripts/ntd.sh` を `--type セキュリティ` で実行（FR6、FR12） | 未解決の `vulnerability` findings |

### 8.2 API仕様要件

該当なし。HTTP API の追加・変更は行わない。

## 9. 制約条件

### 9.1 技術的制約

- `review-protocol.md` の Read-only Constraint は文言も含めて変更しない（NFR1）。
- 軸 2 のツール実行はワーキングツリーを変更しない（NFR2）。
- 軸 2 の判定経路にモデル呼び出しを一切置かない（NFR3、FR8）。
- 新しい `gate_id` を導入せず、`batch-policies.yaml` と `batch-mode.md` の
  Non-packet gates table を変更しない（NFR5）。
- 新規スクリプトは Python 3、ランタイム依存は PyYAML まで。テストは標準ライブラリのみ（NFR7、FR22）。
- `git rev-parse --show-toplevel` は使わない（FR13）。

### 9.2 ビジネス上の制約

- 依存更新を自動適用しない（FR10）。
- 下流（R3a / R3b / R4）を作り直さず、findings をそのまま合流させる。

### 9.3 スケジュール制約

なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの
`files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/review-sca-axis/**`
- `test-docs/review-sca-axis/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。
生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/review-sca-axis/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な
  絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `vulnerability` を `reviewers.yaml` の perspectives に足すと R2 が LLM を fan-out してしまう | 高 | perspectives には追加せず、category enum にのみ追加する（FR8、A1） |
| `source` enum の拡張で既存テストの完全一致 pin が落ちる | 高 | 同じ変更の中で `FROZEN_SOURCE_ENUM` を更新する（FR21、A2） |
| ラウンドごとにタスク化すると最大 3 回起票され、R4 で解消された脆弱性の陳腐化したタスクが残る | 高 | review フェーズにつき 1 回、最終ラウンドの R5 直前に限定し、判定信号を決定論的に定義する（FR11、FR24） |
| `review-output-schema.json` の severity enum は critical/high/medium しか持たず、閾値未満を表現できない | 中 | 閾値を正規化時に適用し、閾値未満の advisory を findings に出さない（A7） |
| `rev-parse --show-toplevel` はレビューの `project_root`（統合 worktree）を返す | 中 | `git worktree list --porcelain` の先頭エントリから解決する（FR13） |
| 重複検出キーの構成が呼び出し側へ漏れると後の拡張で広範囲を触ることになる | 中 | キー組み立てを 1 関数に閉じ込める（FR17） |
| SCA ツールの advisory テキストが untrusted である | 中 | プロンプト散文に連結せず、R3b step 4 と同じ 4096 バイト規律で切り詰める（NFR4） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] `em-workflow/scripts/scan-dependencies.py` が存在し、changed_files から npm / cargo / pip / go の各エコシステムを判定して対応コマンドを組み立てる。
- [ ] 各ツールの JSON 出力が review-output-schema.json に対して schema-valid な結果オブジェクトへ正規化される（source: tool / category: vulnerability）。
- [ ] 対応ツールが PATH に無い場合、findings 空・`skipped: true`・machine-stable な `skip_reason` を返し、LLM へのフォールバックが発生しない。
- [ ] `em-workflow/references/vuln-scanners.yaml` が存在し、マニフェスト / コマンド / severity マッピング / 閾値（direct dependency のみ・severity high 以上）を持つ。
- [ ] review-output-schema.json の `source` enum が `tool` を含み、finding `category` enum が `vulnerability` を含む。`required` / `additionalProperties` / `severity` enum は従来どおり。
- [ ] review-phase.md Phase R0 に notion-task-dispatch の probe が step として存在し、marketplace 名を決め打ちせず複数バージョンから最新を選ぶことが明記されている。
- [ ] review-phase.md Phase R1 の Mandatory Layer-2 check が、依存マニフェスト・lockfile に触れた diff で `license` に加えて `vulnerability` も追加すると述べている。
- [ ] 軸 2 の記述のどこにも Task 発行 / モデル呼び出しが無く、reachability 判断は R3a の評価者が担うと明記されている。`reviewers.yaml` の perspectives は 6 件のまま。
- [ ] 軸 2 が R2 のピアとして走り、その run が R3a 入力・R3b ゲート・R4 auto-fix を通る経路が review-phase.md 上で追える（R3b step 3 の category 照合と accountability floor が `vulnerability` に効く）。
- [ ] R2 の fallback / chain-walk / unreviewed_perspectives の勘定が `source: tool` の run を明示的に除外すると review-phase.md に書かれている。
- [ ] R4 の分類で `vulnerability` findings が auto-applicable にならず needs-judgment 側に落ちることが明記されている。
- [ ] タスク化が review フェーズにつき 1 回、最終ラウンドの R5 直前に実行されると明記され、その「最終ラウンド」を決定論的に判定する信号が示されている。
- [ ] notion-task-dispatch 検出時は `--type セキュリティ` で起票、非検出時はリポジトリルート `tmp/` にレポートを書く分岐が実装されている。
- [ ] レポート出力先が `git -C {project_root} worktree list --porcelain` の先頭エントリから解決され、`rev-parse --show-toplevel` を使っていない。
- [ ] 1 パッケージ 1 タスクで、同一パッケージの複数 CVE が「参照」欄に複数行として並ぶ。
- [ ] 重複検出がタスク同一性＝パッケージ名、エントリ同一性＝CVE/GHSA ID の 2 段で行われる。
- [ ] 重複検出の照合対象が未完了タスクのみで、完了 / 破棄しか無いときは新規起票される。
- [ ] 重複検出キーの組み立てが 1 関数に閉じており、呼び出し側にキー構成の知識が漏れていない。
- [ ] 起票内容で severity が「参照」欄の事実として記録され、優先度プロパティが初期値「高」で入る。
- [ ] review-security/SKILL.md の「What NOT to flag」に既知 CVE 判定は軸 2 が機械的に行う旨がある。
- [ ] plugin.json と marketplace.json の em-workflow エントリの version が同じ値で、0.1.65 より大きい。
- [ ] `python3 -m unittest discover -s tests` が exit 0（`tests/test_reviewer_roles_protocol.py` の source enum pin 更新を含む）。
- [ ] `python3 em-workflow/scripts/check-plugin-invariants.py <repo-root>` が exit 0。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | シナリオ | 対象要件 |
|----|----------|----------|
| TS-1 | スクリプト単体: package.json / Cargo.toml / pyproject.toml / requirements.txt / go.mod を含む changed_files に対して、期待どおりのエコシステムとコマンドが選ばれる | FR1, FR4 |
| TS-2 | スクリプト単体: 各ツールの代表的な JSON 出力サンプル（fixture）を与え、正規化結果が review-output-schema.json に対して schema-valid になる | FR2, FR5 |
| TS-3 | スクリプト単体: 閾値（direct dependency のみ / severity high 以上）が正規化時に適用され、transitive 依存や moderate/low の advisory が findings に出ない | FR2, FR4 |
| TS-4 | スクリプト単体: ツール不在（PATH を空にした環境）で `skipped: true` + `skip_reason` が返り、findings が空になる | FR3 |
| TS-5 | スクリプト単体: 重複検出キー関数へパッケージ名 / CVE を与えたときのキーが期待どおりで、キー構成の変更がその関数だけで完結する | FR15, FR17 |
| TS-6 | スクリプト単体: `git worktree list --porcelain` の出力サンプル（統合 worktree が先頭でない場合を含む）から先頭エントリのパスを取り出し、`tmp/` 配下の出力先を組み立てる。使い捨て git リポジトリを tempfile 上に作って実地に確認する | FR13 |
| TS-7 | 重複検出: 同一パッケージの未完了タスクが既にあれば新規起票せずエントリ追記、完了 / 破棄しか無ければ新規起票する | FR14, FR15, FR16 |
| TS-8 | ドキュメント pin: review-phase.md の R0 に probe が、R1 の Mandatory Layer-2 check に `vulnerability` が、R2 の fallback 記述に tool run 除外が含まれる | FR6, FR7, FR23 |
| TS-9 | ドキュメント pin: review-phase.md にタスク化の実行位置と最終ラウンド判定信号が明記されている | FR11, FR24 |
| TS-10 | スキーマ pin: review-output-schema.json の source enum が `tool` を、category enum が `vulnerability` を含み、severity enum と required は不変 | FR5, FR21 |
| TS-11 | レジストリ pin: reviewers.yaml の perspectives が 6 件のままで `vulnerability` を含まない | FR8 |
| TS-12 | スキル pin: review-security/SKILL.md の「What NOT to flag」に軸 2 への委譲文がある | FR19 |
| TS-13 | version bump: plugin.json と marketplace.json が一致し、0.1.65 より大きい | FR20 |
| TS-14 | E2E: 該当なし（このリポジトリに E2E 基盤は無い） | — |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 軸 2 | LLM レビュアーの fan-out（軸 1）とは別の、決定論的な機械チェック段。本フィーチャーが新設する |
| SCA | 依存パッケージの既知脆弱性を検出するツール群。ここでは npm audit / cargo audit / pip-audit / govulncheck |
| accountability floor | R3b の、ツールが出した critical/high を評価者が黙って握りつぶせないようにする機構 |
| direct dependency | プロジェクトのマニフェストが直接宣言している依存。閾値の対象範囲 |
| 未完了タスク | `完了` でも `破棄` でもない状態のタスク。重複検出の照合対象（FR16） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] `vulnerability` の追加先: review-output-schema.json の category enum にだけ追加し、
      `reviewers.yaml` の perspectives には追加しない。軸 2 に LLM reviewer は無く、
      追加すると R2 が LLM を fan-out してしまう。
      根拠: `tests/test_reviewers_primary_chains.py` が perspectives をちょうど 6 件に
      pin している既存事実と、指示メモの「軸 2 に LLM を置かない」から。Codex 相談（Q2）でも同結論。
- [x] 既存テストの pin 更新: `tests/test_reviewer_roles_protocol.py` の
      `FROZEN_SOURCE_ENUM` を `["claude", "codex", "litellm", "tool"]` に更新する。
      根拠: 既存テストが完全一致で pin しており、更新しないと source enum 拡張が即座に赤くなる。
- [x] 軸 2 の記録形式: 実行結果は round record の `perspective_runs` に `source: tool` の
      1 行として記録し、R3b step 3 の category 照合と accountability floor がその run を
      参照できるようにする。run_id の具体形は設計 / 実装時に決める。
      根拠: 制約「軸 2 を perspective として扱うと accountability floor が効く」を既存の
      R3b / R5 の仕組みに写すと、dispatched run として記録する以外の経路が無い。
      Codex 相談（Q2）で追認。
- [x] 軸 2 の実行位置: Phase R2 の fan-out 集合のピアとして、オーケストレーター自身が
      `scan-dependencies.py` を実行する決定論ステップとして走る（Task 発行はしない）。
      根拠: Codex 相談（Q1）で「R1 と R3a の間に独立段を足す」案と比較した結果、R2 のピアに
      置く方が R3a が消費する `perspectives_dispatched` / `reviewer_outputs` にそのまま入る
      ため優れると判断した。
- [x] レポートの配置: メイン作業ツリーの `tmp/` 配下に、フィーチャー名と時刻を含む
      ファイル名で書く。`tmp/` は .gitignore 済みなのでコミットされない。
      根拠: リポジトリの .gitignore に `tmp/` があり、一時ファイル配置方針とも一致。
- [x] version の刻み: patch を 1 つ上げて 0.1.65 → 0.1.66 とする。
      根拠: `core-plugin-version-bump.md` は semver を掲げつつ「実際にはほとんどが挙動の
      修正なので patch 単位が基本」とし、リポジトリの実績も一貫して patch。
- [x] 閾値の適用位置: 閾値（direct dependency のみ / severity high 以上）は正規化時に適用し、
      閾値未満の advisory は findings として出さない。ツール severity の critical →
      `critical`、high → `high` に写し、moderate / low は閾値で落ちる。
      根拠: review-output-schema.json の severity enum は critical/high/medium しか持たず、
      閾値未満を表現できない。R3b は medium も受け入れるため下流フィルタも効かない。
      Codex 相談（Q4）で追認。
- [x] 実行文脈: 軸 2 は develop 駆動と standalone（`/em-workflow:review`）の両方で走る
      （R0/R1 は両文脈共通の同じ節のため）。standalone でもタスク化 / レポートの分岐は
      同じ probe に従う。
      根拠: review-phase.md は 1 プロトコルで 2 実行文脈を扱う構造になっており、R0/R1 に
      文脈分岐を足す指示は無い。
- [x] ゲートの扱い: 新しい `gate_id` は導入しない。起票 / レポートの分岐は probe による
      機械判定で、ユーザーへの問いを増やさない。
      根拠: 指示に新規ゲートの記載が無く、`check-plugin-invariants.py` の gate_id_coverage が
      両方向で失敗するため、安易な追加は不変条件違反になる。
- [x] デザインステップ: skipped。UI / 視覚的成果物が一切無い変更のため。対象は Python
      スクリプト 1 本、YAML レジストリ 1 本、既存の JSON スキーマ・Markdown プロトコル・
      スキルのテキスト編集、およびプラグイン version bump。design_system_candidates も空で、
      デザインシステムの候補は存在しない。

### 14.2 未確認・保留事項

なし。すべての機能要件が `status: resolved` で確定している。

## 15. 参考資料

- `em-workflow/references/review-phase.md`: レビューフェーズのプロトコル（R0〜R5）
- `em-workflow/references/review-protocol.md`: Read-only Constraint（no-network 制約）
- `em-workflow/references/review-output-schema.json`: レビュー結果のスキーマ
- `em-workflow/references/reviewers.yaml`: レビュアーレジストリ（SSOT の作法の参照元）
- `em-workflow/skills/review-security/SKILL.md`: security 観点のスキル
- `em-workflow/scripts/check-plugin-invariants.py`: プラグイン不変条件の検査
- `.claude/rules/core-plugin-version-bump.md`: バージョン更新の粒度
- `test/README.md`: テストの配置と依存の規約

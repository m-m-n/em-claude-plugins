---
title: "develop-once-option"
created_date: 2026-08-25
status: draft
---

# develop-once-option - 要件定義書

## 1. 概要

### 1.1 背景

`--once` が無い場合、develop は `workflow[]` の全ステップが `completed`（`design` のみ
`skipped` もあり得る）になるまで自走する。フェーズ境界でもターンが終わらないため、
1 起動あたりのコンテキスト消費がフェーズをまたいで積み上がる。

### 1.2 目的

- `--once` が与えられたとき、1 フェーズ実行してターンを終えることで、develop
  オーケストレータのフェーズ境界におけるコンテキスト消費を削減する。
- 外側のドライバが Claude Code の起動 1 回につき 1 フェーズだけフィーチャーを進め、
  フェーズごとに同じフィーチャーを再起動できるようにする。

### 1.3 スコープ

対象は Markdown のプロンプト／リファレンス文書と、それらを検証するテストモジュール、
および 2 つの JSON の `version` フィールド。ランタイムスクリプトの挙動は変更しない。
この変更にはユーザーインターフェースも視覚的な表示面も無く、本プロジェクトには
デザインシステムも存在しない（design-system 候補は 0 パス）ため、デザインステップは
`skipped` とする。

## 2. ビジネス要件

### 2.1 ビジネス目標

- `--once` が与えられたとき 1 フェーズでターンを終えることで、develop オーケストレータの
  フェーズ境界でのコンテキスト消費を削減する。
- 外側のドライバが Claude Code の起動ごとに 1 フェーズ進め、各フェーズの後に同じ
  フィーチャーを再起動できるようにする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| develop を起動する利用者 | `--once` を付けて 1 フェーズだけ進める |
| 外側のドライバ | Claude Code の起動 1 回につき 1 フェーズ進め、終端行を見て同じフィーチャーを再起動する |

### 2.3 期待される効果

- フェーズ境界でターンが終わることによる、1 起動あたりのコンテキスト消費の削減
- 1 起動 = 1 フェーズという単位での外部駆動が可能になる

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | `--batch --once` で 1 フェーズだけ進める | 外側のドライバ | — |
| UC02 | 対話モードで `--once` を使い、次の起動方法の案内を受け取る | develop を起動する利用者 | — |

優先度は要件分析に指定が無いため `—` とする。

### 3.2 ユースケース詳細

#### UC01: `--batch --once` で 1 フェーズだけ進める

**アクター**: 外側のドライバ

**事前条件**:
- 対象フィーチャーの `workflow.yaml` が存在し、未完了のステップが残っている

**基本フロー**:
1. ドライバが develop を `--batch --once` 付きで起動する
2. develop が次に実行すべき `workflow[]` ステップを 1 つ実行する
3. そのステップの `status` が `completed`（`design` のみ `skipped`）に確定し、状態が
   コミットされる
4. develop はバッチ終端行を出力してターンを終える。`state` は `--once` のフェーズ境界用に
   追加された第 3 の値で、`reason=none`、`detail` は非空の 1 行。`step` はそのターンで
   実行されたステップ名
5. ドライバは終端行を見て、同じフィーチャーを再起動する

**代替フロー**:
- `verify` が `fail` を記録した場合: rework パッチが適用され、`implement` と `verify` が
  `pending` に戻り、その変更がコミットされた時点で 1 フェーズ完了。終端行の `step` は
  `verify`。次の起動は `implement` から再開する
- `retrospect` が `completed` に達した場合: そこでターンが終わり、Step C（完了処理）は
  次の起動で 1 つの独立したフェーズとして実行される
- implement I.2.c の planning への route back（`create-plan` → `needs_update`）および
  rework の spec-change 遷移（`create-spec` → `needs_update`）: routing パッチの適用と
  コミットが済んだ時点でターンを終える
- implement フェーズの内部ではターンを終えない。停止条件 5 の wait ターンと implement の
  launch / wake ターンは非終端であり、終端行も出さない

**事後条件**:
- `workflow.yaml` が 1 フェーズ分進み、その状態がコミットされている

#### UC02: 対話モードで `--once` を使い、次の起動方法の案内を受け取る

**アクター**: develop を起動する利用者

**事前条件**:
- 対象フィーチャーの `workflow.yaml` が存在し、未完了のステップが残っている

**基本フロー**:
1. 利用者が develop を `--once` 付きで対話モード起動する
2. develop が 1 フェーズ実行してターンを終える
3. 終了報告に次の 1 行が加わる:
   `{step} が完了したよ。続きは /clear してから /em-workflow:develop {feature} を実行してね`

**代替フロー**:
- UC01 の代替フローと同じフェーズ境界の扱いが適用される

**事後条件**:
- `workflow.yaml` が 1 フェーズ分進み、利用者が次の起動方法を把握できている

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | `--once` 引数の処理 | develop の 引数処理 に `--once` を追加する | — |
| FR2 | 1 フェーズの定義（`completed` 境界） | 1 ステップの実行・状態確定・コミットを 1 フェーズとする | — |
| FR3 | Step C は独立した 1 フェーズ | `retrospect` の `completed` でターンを終え、Step C は次の起動で実行する | — |
| FR4 | verify 失敗時の rework 境界 | rework パッチ適用・`pending` 復帰・コミットで 1 フェーズ完了とする | — |
| FR5 | `completed` 以外のフェーズ境界 | 自動再入の 2 遷移も `--once` のフェーズ境界とする | — |
| FR6 | 停止条件 7 | ターンを終わらせていい唯一の条件に 7 番目を追加する | — |
| FR7 | バッチ終端行の第 3 の `state` 値 | 終端行 SSOT に `--once` フェーズ境界用の `state` 値を追加する | — |
| FR8 | `--once` 境界での `step` の値 | `step` はそのターンで実行されたステップを指す | — |
| FR9 | SSOT 分割: SKILL.md に値リテラルを書かない | SKILL.md と batch-mode.md は「いつ出すか」だけを述べる | — |
| FR10 | literal guard を `state` 値まで拡張 | FR9 を機械的に強制する | — |
| FR11 | 終端状態の個数に関する記述の整合 | 「2 つ」を固定した記述を FR7 の追加後も真に保つ | — |
| FR12 | 対話モードの終了行 | `--once` の終了報告に 1 行だけ追加する | — |
| FR13 | プラグイン version の bump | plugin.json と marketplace.json の `version` を同じ値に上げる | — |
| FR14 | implement の途中では終了しない | `--once` は implement フェーズ内でターンを終えない | — |

優先度は要件分析に指定が無いため `—` とする。

### 4.2 機能詳細

#### FR1: `--once` 引数の処理

**説明**: `em-workflow/skills/develop/SKILL.md` の 「引数処理」 に `--once` を追加する。
指定された起動では 1 フェーズだけ実行し、次のステップに進まずターンを終える。これは
起動ごとの設定に限られ、`workflow.yaml` にも `phase-state/` にも一切書かれない。
`--batch` と併用できる。フラグが無い場合の挙動は現状と完全に同じ（`workflow[]` の
全ステップが `completed` になるまで自走する。`design` は `skipped` もあり得る）。
スキルの frontmatter の `argument-hint` にこのフラグを列挙する。

**入力**:
- `--once`: 起動引数のフラグ - 指定時、1 フェーズでターンを終える

**出力**:
- 起動ごとの動作切り替え（永続化されるデータは無い）

**ビジネスルール**:
- `--once` は永続化しない（`workflow.yaml` にも `phase-state/` にも書かない）
- `--batch` と併用できる
- フラグが無い起動の挙動は現状から変わらない

#### FR2: 1 フェーズの定義（`completed` 境界）

**説明**: 1 フェーズとは、`workflow[]` のステップが 1 つ実行され、その `status` が
`completed`（`design` のみ `skipped`）に確定し、その状態がコミットされることを指す。
ターンはその時点で終わる。

#### FR3: Step C は独立した 1 フェーズ

**説明**: Step C（完了処理）は 1 つの独立したフェーズとして数える。`--once` では
`retrospect` が `completed` に達した時点でターンが終わり、Step C は次の起動で実行される。

#### FR4: verify 失敗時の rework 境界

**説明**: `verify` が `fail` を記録した場合、rework パッチが適用され、`implement` と
`verify` が `pending` に戻り、その変更がコミットされた時点で 1 フェーズが完了する。
次の起動は `implement` から再開する。

#### FR5: `completed` 以外のフェーズ境界

**説明**: SKILL.md Step B の 「停止条件 3 との優先関係」 に列挙されている 2 つの
自動再入遷移も `--once` のフェーズ境界とする。implement I.2.c の planning への route back
（`create-plan` → `needs_update`）と、rework の spec-change 遷移
（`create-spec` → `needs_update`）である。いずれも routing パッチが適用されコミットされた
時点でターンを終える。`--once` が約束するのは 1 フェーズであって、1 回の `completed`
状態遷移ではない。

#### FR6: 停止条件 7

**説明**: SKILL.md の 「ターンを終わらせていい唯一の条件」 のリストに 7 番目の項目を
追加する。`--once` において 1 フェーズが完了したとき。既存の 6 条件とその文言は変更しない。

#### FR7: バッチ終端行の第 3 の `state` 値

**説明**: 終端行の値域の唯一の所有者である `em-workflow/references/batch-terminal-line.md`
に、`--once` のフェーズ境界を表す第 3 の `state` 値を追加する。この値は `reason=none` と、
非空で 1 行の `detail` とともに出力され、プレフィックスも 4 フィールドとその順序も既存と
同じものを使う。`state=completed` と `state=stopped` の意味は現状のまま、11 個の停止理由
コードと停止点カバレッジ表も変更しない。同文書には、外側のドライバがこの新しい state を
見たら同じフィーチャーを再起動することを記述する。

#### FR8: `--once` 境界での終端行の `step`

**説明**: 終端行の `step` には、そのターンで実行されたステップ名を書く。次の起動が再開する
ステップではない。verify 失敗時の rework 境界では値は `verify` になる。終端行はその起動を
終わらせたフェーズを表すものであり、再開カーソルではない。

#### FR9: SSOT 分割 — SKILL.md に `state` 値リテラルを書かない

**説明**: SKILL.md の 「バッチ終端行」 サブセクションには、`--once` のフェーズ境界で終端行を
「いつ出すか」だけを書き、`state` の値リテラルは書かない。出力の直前に
`${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` を Read し、そこで定義された
プレフィックス・フィールド文法・値集合を使うという既存の指示を維持する。
`references/batch-mode.md` も同様に値リテラルを再掲しない。

#### FR10: literal guard を `state` 値まで拡張

**説明**: `tests/test_batch_stop_contract_skill_wiring.py` の既存の contract-literal guard
（`_find_contract_literal_violations`。SKILL.md と batch-mode.md の双方に適用される）と、
`tests/test_batch_stop_contract.py` の対応する不在チェック
（`TestBatchModePointer.test_restates_no_contract_literal`）を、`state` の値集合まで
カバーするよう拡張する。これにより FR9 を慣習ではなく機械的に強制する。拡張は
`completed` / `skipped` / `stopped` に対して誤検知してはならない。これらは両文書が
`workflow.yaml` のステップ status の語彙として既に日常的に使っているためで、guard は
既存の 4 つのフィールド名と同じ流儀で、素の単語ではなく契約固有の形として検査する。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 誤検知 | ポインタ文書中の `completed` / `skipped` / `stopped` を step status として使っている | 契約固有の形としてスコープし、違反としない |
| 見逃し | ポインタ文書が新しい `state` 値を再掲している | guard が違反として検出する |

#### FR11: 終端状態の個数に関する記述の整合

**説明**: 終端状態の個数を固定している文言は、FR7 の追加後も真であり続けなければならない。
対象は batch-terminal-line.md の `state` の箇条書き（"closed set of two values"）と
「No line on a wait turn」 の一文（"either of the contract's two terminal states"）、および
SKILL.md の 「同 SSOT が定める 2 つの終端状態のいずれか」。SKILL.md 側は個数を固定せず、
かつどの state 値も名指ししない形で規則を表現する（FR9）。

#### FR12: 対話モードの終了行

**説明**: 対話モードにおける `--once` の終了報告に、次の 1 行だけを追加する。

```
{step} が完了したよ。続きは /clear してから /em-workflow:develop {feature} を実行してね
```

#### FR13: プラグイン version の bump

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、同じ変更の中で
`em-workflow/.claude-plugin/plugin.json` とリポジトリルートの
`.claude-plugin/marketplace.json` の `version` を同じ値に上げる。目標値は 0.1.50 → 0.1.51。

#### FR14: implement の途中では終了しない

**説明**: `--once` は implement フェーズの内部でターンを終えることはない。実行中の
バックグラウンド implementer はプロセス終了で失われるため、ターンはフェーズ境界でのみ
終わる。停止条件 5 の wait ターン、および implement の launch ターンと wake ターンは
非終端のままで、終端行も出さない。

## 5. 非機能要件

### 5.1 NFR1: SSOT 分割の維持

`references/batch-terminal-line.md` がプレフィックス・フィールド文法・全ての値域の唯一の
所有者であり続ける。ポインタ文書は同文書を名指しするだけで、リテラルを再掲しない。
プレフィックスは `em-workflow/` 配下の全ファイルの中で、同文書のフェンス付きコードブロック内
だけに出現し続ける。

### 5.2 NFR2: 変更面はドキュメントに限定

変更対象は Markdown のプロンプト／リファレンス文書と、2 つの JSON の `version` フィールド。
ランタイムスクリプトの挙動は変わらないため、検証はファイルに対する構造的／テキスト的な
アサーションで行う。これは既存の 3 つのテストモジュールが既に採っている流儀と一致する。

### 5.3 NFR3: テストの規約

新しいテストはリポジトリルートの `tests/` ディレクトリに `test_*.py` として置き、
`python3 -m unittest discover -s tests` で発見される。import は Python 標準ライブラリのみ
（`test/README.md`。モジュール内で `TestOwnModuleStdlibOnly` により強制される）。新しい
matcher にはそれぞれ negative proof と非空虚性（non-vacuity）ガードを付ける。既存文言の
維持を確認するだけの純粋な回帰ガードは、既存モジュールに記録された慣習に従い対象外とする。

### 5.4 NFR4: 後方互換性

`--once` を付けない起動は、現状とバイト単位で同一の挙動になる。既存の固定された構造も
そのまま保つ。batch-terminal-line.md の 7 つの level-2 見出しとその順序、11 個の理由コードと
11 行のカバレッジ表、batch-mode.md の 10 行の Non-packet gates 表とその catch-all /
diff-size / per-command の文言。

### 5.5 NFR5: バッチにおける報告の完全性

`--once` のバッチターンでも、最終アシスタントメッセージの最後の行として終端行を出力する。
`detail` は 1 物理行に正規化され、パス以上の機密情報を含まない。

### 5.6 その他の非機能カテゴリ

パフォーマンス、セキュリティ、可用性、UI の互換性については、要件分析に該当する要件が無い。

## 6. UI/UX要件

### 6.1 画面設計要件

画面は無い。ユーザーに見える出力は、対話モードの終了報告に加わる 1 行（FR12）と、
バッチモードの終端行（FR7、NFR5）のみ。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

永続データの追加は無い。`--once` は起動ごとの設定であり、`workflow.yaml` にも
`phase-state/` にも書かれない（FR1）。

### 7.2 データ項目

該当なし。

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| 外側のドライバ | バッチ終端行を読み、同じフィーチャーを再起動する | 終端行の `state` / `step` / `reason` / `detail`（FR7、FR8） |

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- `references/batch-terminal-line.md` が値域の唯一の所有者であり、ポインタ文書は
  リテラルを再掲しない（NFR1、FR9）
- 変更面は Markdown 文書と 2 つの JSON `version` フィールドに限られ、ランタイム
  スクリプトの挙動は変えない（NFR2）
- テストは `tests/` 配下の `test_*.py` で、標準ライブラリのみを import する（NFR3）
- 実行中のバックグラウンド implementer はプロセス終了で失われるため、implement の
  途中でターンを終えられない（FR14）
- プラグイン配下を変更したら同じ変更で version を上げる（FR13、
  `.claude/rules/core-plugin-version-bump.md`）

### 9.2 ビジネス上の制約

- `--once` を付けない起動は現状とバイト単位で同一の挙動でなければならない（NFR4）

### 9.3 スケジュール制約

要件分析に記載なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの
`files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/develop-once-option/**`
- `test-docs/develop-once-option/**`

`feature-docs/develop-once-option/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。
生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、
ルールは再掲しない）。

`test-docs/develop-once-option/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/develop-once-option/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照
（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は
  意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。
  implementタスクを1つも生成しないフィーチャーは `test-docs/develop-once-option/`
  ディレクトリを生成しないが、宣言された `test-docs/develop-once-option/**` は依然として
  正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| ポインタ文書に `state` 値リテラルが混入し SSOT 分割が崩れる | — | literal guard を `state` 値まで拡張して機械的に強制する（FR10） |
| guard の拡張が `completed` / `skipped` / `stopped` の step status 用法に誤検知する | — | 既存の 4 フィールド名と同じく契約固有の形としてスコープする（FR10、AC7） |
| 終端状態の個数を「2 つ」と固定した記述が第 3 の値の追加で偽になる | — | 個数を固定した文言を洗い出して整合させる（FR11） |
| implement 実行中にターンを終えるとバックグラウンド implementer が失われる | — | ターンはフェーズ境界でのみ終える（FR14） |

影響度は要件分析に指定が無いため `—` とする。

### 10.2 ビジネスリスク

要件分析に記載なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: SKILL.md の 引数処理 が `--once` を起動ごとの設定・`--batch` と併用可能・
      どこにも永続化しない、と記述している。frontmatter の `argument-hint` にも含まれる。
- [ ] AC2: SKILL.md の 「ターンを終わらせていい唯一の条件」 に `--once` のフェーズ境界を
      扱う 7 番目の項目があり、1〜6 は変更されていない。
- [ ] AC3: SKILL.md が 4 種類すべての境界を含むフェーズ境界の定義を述べている。ステップが
      `completed` / `skipped` に達する場合、retrospect の `completed`（Step C は次の起動へ）、
      verify 失敗時の rework パッチのコミット、2 つの自動再入 routing コミット
      （implement I.2.c の route back、rework の spec-change）。
- [ ] AC4: batch-terminal-line.md が第 3 の `state` 値を `reason=none` と非空の `detail`
      とともに定義し、`step` フィールドが実行されたステップを持つこと（verify 失敗時の
      rework 境界では `verify`）を述べ、`completed` / `stopped` の意味・11 個の理由コード・
      カバレッジ表を変更していない。
- [ ] AC5: batch-terminal-line.md の level-2 見出しがちょうど 7 つで順序どおりであり、
      終端状態の個数に関するあらゆる記述が追加後も真である。
- [ ] AC6: SKILL.md と batch-mode.md のいずれにも、`state` 値リテラル、プレフィックス
      リテラル、4 つのフィールド名の全部そろい、理由コード、sentinel が含まれない。
- [ ] AC7: 拡張された literal guard が、新しい `state` 値を再掲した SKILL.md /
      batch-mode.md の偽造抜粋に対して失敗し、実ファイルに対しては通る。実ファイル中の
      既存の `completed` / `skipped` / `stopped` の記述に誤検知しない。
- [ ] AC8: SKILL.md の 「バッチ終端行」 サブセクションが 「停止時の報告」 の直後にあり、
      その間に他の level-2 見出しが無く、出力直前に契約文書を Read する指示を保ち、
      停止条件 5 と implement の launch / wake ターンを名指しした一般化 no-line 規則を
      述べ続けている。
- [ ] AC9: 対話モードの `--once` 終了行が、`{step}` と `{feature}` を置換した上で指定の
      文言と完全一致する。
- [ ] AC10: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の
      `version` が同一で、変更前より大きい。
- [ ] AC11: `python3 -m unittest discover -s tests` が通る。reference_scan_targets の
      既存 3 モジュールを含む。

### 11.2 KPI

要件分析に記載なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 全スイート: リポジトリルートで `python3 -m unittest discover -s tests`。
- [ ] TS2 プラグイン不変条件: `python3 em-workflow/scripts/check-plugin-invariants.py` を
      リポジトリルートに対して実行し exit 0（根拠: `tests/test_batch_stop_contract_skill_wiring.py`
      の AC-5）。
- [ ] TS3 契約文書の構造: 見出しの数と順序、`## Field values` の値域に新しい `state` 値が
      あること、`reason=none` との対応、`step` の executed-step 規則。
- [ ] TS4 ポインタ文書のリテラル不在: 拡張した `_find_contract_literal_violations` を
      SKILL.md の 「バッチ終端行」 サブセクションと batch-mode.md の `## Terminal line` に
      適用し、加えてファイル全体のプレフィックス不在チェック。
- [ ] TS5 guard の negative proof: 新しい `state` 値を再掲した偽造サブセクションが
      拒否される。偽造テキストがそれ以外は well-formed で正しくスライスされていることを
      非空虚性ガードで示す。
- [ ] TS6 guard の誤検知検証: 実際の SKILL.md（step status として `completed` / `skipped` を
      多用している）で違反 0 件。
- [ ] TS7 停止条件リスト: 項目 7 が存在し、1〜6 が変更されておらず、bullet-3 のスライス
      （`3. ` … `4. `）が依然として機能する。
- [ ] TS8 配置の回帰: 「## 停止時の報告」 と 「## バッチ終端行」 の間に level-2 見出しが無い。
- [ ] TS9 プレフィックスの一意性掃引: `em-workflow/` 配下の全ファイルを走査して、
      プレフィックスが batch-terminal-line.md のフェンス付きブロック内にのみ見つかる。
- [ ] TS10 非回帰: batch-mode.md の Non-packet gates 表のデータ行が 10 行のまま、
      batch-terminal-line.md の理由コード表から 11 コード、カバレッジ表から固定された
      11 組の key→code が抽出できる。

セキュリティ観点とパフォーマンス観点は、要件分析に該当するシナリオが無い。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `--once` | 1 フェーズ実行してターンを終える、起動ごとの引数フラグ（FR1） |
| フェーズ | `workflow[]` のステップが 1 つ実行され、`status` が確定し、その状態がコミットされるまで（FR2） |
| バッチ終端行 | `references/batch-terminal-line.md` が定義する、バッチターンの最終行 |
| 外側のドライバ | Claude Code の起動ごとに 1 フェーズ進め、同じフィーチャーを再起動する外部の実行主体 |
| Step C | develop の完了処理。`--once` では独立した 1 フェーズとして数える（FR3） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] `completed` 以外のフェーズ境界の扱い: implement I.2.c の planning への route back と
      rework の spec-change 遷移も `--once` のフェーズ境界とし、routing パッチの適用と
      コミットが済んだ時点でターンを終える（A1）。
- [x] `--once` 境界での終端行 `step` の値: そのターンで実行されたステップ名を書く
      （verify 失敗時の rework 境界では `verify`）。再開位置ではない（A2）。
- [x] SKILL.md における `state` 値リテラルの扱い: SKILL.md には値リテラルを書かず、既存の
      literal guard を `state` 値まで拡張して機械的に強制する（A3）。
- [x] デザインステップ: requirements-analyst の推奨どおり `skipped` とする。個別のユーザー
      確認は行わない（A4）。
- [x] プラグイン version: 現行値は 0.1.50、目標は 0.1.51。現行値はオーケストレータが
      `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の双方で
      確認済み（A5）。

### 14.2 未確認・保留事項

なし。`status: tbd` の要件は無い。

## 15. 参考資料

- SPEC.md: `feature-docs/develop-once-option/SPEC.md`
- develop スキル: `em-workflow/skills/develop/SKILL.md`
- 終端行 SSOT: `em-workflow/references/batch-terminal-line.md`
- バッチモード: `em-workflow/references/batch-mode.md`
- 既存テスト: `tests/test_batch_stop_contract_skill_wiring.py`、`tests/test_batch_stop_contract.py`
- テスト規約: `test/README.md`
- version bump ルール: `.claude/rules/core-plugin-version-bump.md`
- create-plan での変更集合導出: `references/phases/create-plan-phase.md`

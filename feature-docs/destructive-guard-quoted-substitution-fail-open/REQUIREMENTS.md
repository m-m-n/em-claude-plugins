---
title: "destructive-guard-quoted-substitution-fail-open"
created_date: 2026-09-14
status: draft
---

# destructive-guard-quoted-substitution-fail-open - 要件定義書

## 1. 概要

### 1.1 背景

destructive-guard の「引用符付きコマンド置換 + 親参照 + safe ルート着地」形が fail-open（allow）になるとの報告があった。この形は main HEAD fba3d7e の `em-workflow/hooks/destructive-guard.py` では再現せず、攻撃シナリオ 5 形を含む 9 形の実測結果はすべて deny である。

既存のケース表には引用符付きコマンド置換の deny ケースが数件存在する（`em-workflow/hooks/tests/destructive-guard-cases.json` 186 行「prefix$(cat list)」、194-195 行「"/tmp/sub/"$(cat list)」系）。欠けているのは 165-168 行の親参照 + safe ルート着地形の引用符付き双子である。

### 1.2 目的

- 当該形が fail-closed（deny）であることを期待値スイートで固定し、同じ穴が再び開いたときに検知できる状態にする。
- em-workflow 配下のファイルを変更するため、同一変更内でプラグイン version を上げ、インストール済みキャッシュが更新される状態を保つ。

### 1.3 スコープ

回帰テスト追加のみ。`em-workflow/hooks/destructive-guard.py` の挙動は変更しない。変更対象は次の 2 種類のファイルに限る。

- `em-workflow/hooks/tests/destructive-guard-cases.json`
- プラグイン version 2 箇所（`em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`）

## 2. ビジネス要件

### 2.1 ビジネス目標

- destructive-guard の「引用符付きコマンド置換 + 親参照 + safe ルート着地」形が fail-closed（deny）であることを期待値スイートで固定し、同じ穴が再び開いたときに検知できる状態にする。
- 報告された fail-open は main（fba3d7e）では再現しない（オーケストレーター実測、9 形すべて deny）ため、挙動修正ではなく回帰テスト整備で完了とする。
- em-workflow 配下のファイルを変更するため、同一変更内でプラグイン version を上げ、インストール済みキャッシュが更新される状態を保つ。

### 2.2 対象ユーザー

要件に記載なし。

### 2.3 期待される効果

- 同じ形の fail-open が再発したとき、スイートの失敗として検知できる。

## 3. ユースケース

要件に記載なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | ステータス |
|----|--------|-----------|
| FR1 | 引用符付きコマンド置換の deny ケース追加 | resolved |
| FR2 | 期待値は実測値であること | resolved |
| FR3 | 既存ケースの完全保持 | resolved |
| FR4 | フック本体を変更しない | resolved |
| FR5 | ケース表の記法準拠 | resolved |
| FR6 | プラグイン version の同時更新 | resolved |
| FR7 | スイート全件グリーン | resolved |

### 4.2 機能詳細

#### FR1: 引用符付きコマンド置換の deny ケース追加

`em-workflow/hooks/tests/destructive-guard-cases.json` に、チケットが allow と報告した 5 形（二重引用符で囲んだ形 / 単一引用符で囲んだ形 / バッククォート置換を二重引用符で囲んだ形 / 着地先を dist・node_modules・.cache に変えた形 / 置換の前後に文字を密着させた形）を、既存の裸形の双子（現行 165-168 行）に対応する形で追加する。

#### FR2: 期待値は実測値であること

追加する各ケースの期待判定は、現行 `em-workflow/hooks/destructive-guard.py` に同一コマンド文字列を通した実測結果と一致させる。実測が deny 以外（ask 等）になった形は、その実測値をそのまま期待値として記録し、ラベルにその理由を書く。期待値を推測で書かない。

#### FR3: 既存ケースの完全保持

`.claude/rules/hook-tests.md` の「既存の deny / ask ケースは消さない」に従い、`destructive-guard-cases.json` の既存エントリを 1 件も削除・改変しない。追加のみを行う。

#### FR4: フック本体を変更しない

`em-workflow/hooks/destructive-guard.py` の判定挙動を変更しない。今回の変更対象はケース表とプラグイン version の 2 種類のファイルに限る。

#### FR5: ケース表の記法準拠

追加ケースは既存と同じ 3 要素配列 `[期待する判定, ラベル, コマンド]` で書き、ラベルは既存の日本語 + カテゴリ接頭辞の様式（例: 「評価境界(rm-recursive): ...」「スクラッチ外(rm-recursive): ...」）に揃える。ラベルには「引用符付きでも裸形と同じ判定になること」を検証している旨が読み取れる記述を含める。

#### FR6: プラグイン version の同時更新

`.claude/rules/core-plugin-version-bump.md` に従い、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version を、同じ変更の中で同一の値に patch 単位で上げる（現在いずれも 0.1.79）。

#### FR7: スイート全件グリーン

`python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（終了コード 0、FAIL 行なし）。

## 5. 非機能要件

| ID | 内容 |
|----|------|
| NFR1 | 追加ケースは外部依存を持たない。ネットワーク・実ファイルシステム上の存在するパス・カレントディレクトリの内容に判定が依存しないコマンド文字列だけを使う（フックは静的解析であり、コマンドは実行されない）。 |
| NFR2 | テストの実行時間は 1 ケースあたりサブプロセス 1 本の線形増加に収まる。ケース数の追加以外にランナーの構造を変えない。 |
| NFR3 | `destructive-guard-cases.json` は JSON として妥当であり続ける（`json.load` が通る）。 |
| NFR4 | Python 標準ライブラリのみで動作する状態を維持し、新規依存を追加しない。 |

## 6. UI/UX要件

該当なし。UI を持たない変更であり、対象は JSON のテストケース表とプラグイン version の 2 種類のファイルのみで、画面・コンポーネント・スタイルのいずれにも触れない。

## 7. データ要件

要件に記載なし。

## 8. 外部連携

要件に記載なし。

## 9. 制約条件

### 9.1 技術的制約

- `em-workflow/hooks/destructive-guard.py` の判定挙動を変更しない（FR4）。
- `destructive-guard-cases.json` の既存エントリを削除・改変しない（FR3）。
- Python 標準ライブラリのみで動作する状態を維持する（NFR4）。

### 9.2 ビジネス上の制約

要件に記載なし。

### 9.3 スケジュール制約

要件に記載なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。

## 10. 想定される課題とリスク

| 課題 | 対応策 |
|------|--------|
| 単一引用符形は実シェルでは置換が展開されないため、フックの deny はコマンド文字列の静的解析上の fail-closed 判定であって、シェル意味論上の再現ではない。 | 期待値は実測に合わせる（FR2）。 |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: チケットの攻撃シナリオ 5 形すべてについて、対応するケースが `destructive-guard-cases.json` に存在し、期待判定が fail-closed 側（deny）である。
- [ ] AC2: 引用符の種別（二重引用符 / 単一引用符 / バッククォート置換 + 二重引用符）ごとに、少なくとも 1 件の deny ケースが存在する。
- [ ] AC3: safe ルート着地先の別バリエーション（dist / node_modules / .cache）について、それぞれ引用符付きの deny ケースが存在する。
- [ ] AC4: 置換の前に文字が密着する形と、後ろに文字が密着する形の双方について、引用符付きの deny ケースが存在する。
- [ ] AC5: 追加した各ケースの期待判定が、現行 `destructive-guard.py` の実測判定と一致する。
- [ ] AC6: 変更前に存在した全ケースが、変更後も同じ期待判定・同じコマンド文字列で残っている（削除・改変ゼロ）。
- [ ] AC7: `em-workflow/hooks/destructive-guard.py` に差分が無い。
- [ ] AC8: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が終了コード 0 で、全件 ok と表示される。
- [ ] AC9: `python3 -m unittest discover -s tests` が変更前と同じく成功する（新規の失敗が無い）。
- [ ] AC10: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version が、0.1.79 から同一の新しい patch バージョンに更新されている。

### 11.2 KPI

要件に記載なし。

## 12. テストシナリオ

| ID | シナリオ | 期待 | 対応要件 |
|----|----------|------|----------|
| TS1 | 二重引用符で囲んだ置換 + 親参照 + safe ルート着地 | deny | FR1, FR2 |
| TS2 | 単一引用符で囲んだ形。実シェルでは置換が展開されず literal パス削除になるが、フックの静的解析としては fail-closed 側に倒れることを固定する | deny | FR1, FR2 |
| TS3 | バッククォート置換を二重引用符で囲んだ形（両スペル対称性のバッククォート側） | deny | FR1, FR2 |
| TS4 | 着地先を dist に変えた引用符付き形 | deny | FR1, FR2 |
| TS5 | 着地先を node_modules に変えた引用符付き形 | deny | FR1, FR2 |
| TS6 | 着地先を .cache に変えた引用符付き形 | deny | FR1, FR2 |
| TS7 | 引用符内で置換の前に実テキストが密着する形 | deny | FR1, FR2 |
| TS8 | 引用符内で置換の後ろに実テキストが密着する形 | deny | FR1, FR2 |
| TS9 | 対照として既存の裸形ケース（165-168 行）が変更後も同じ期待判定で残っていること | deny（既存のまま） | FR3 |
| TS10 | スイート全体の実行: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 ok | exit 0 | FR7 |
| TS11 | フック本体に差分が無いこと、および version が両ファイルで同一の新しい patch 値に上がっていること | 差分ゼロ / version 一致 | FR4, FR6 |

## 13. 用語定義

要件に記載なし。

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 報告された fail-open は main HEAD fba3d7e の `destructive-guard.py` では再現しない。攻撃シナリオ 5 形を含む 9 形の実測結果が全て deny であることは、オーケストレーターが提供した確定事実である。
- [x] A2: チケットが指す `WORD_BOUNDARY_CHARS` は現行実装に存在せず、`_mark_substitutions()` は `SUBSTITUTION.sub(UNRESOLVED_MARK, chunk)` のみ（`destructive-guard.py` 633 行）。チケットの該当箇所記述は CLOSED の PR 30 のブランチ実装に対するもので、main には適用されない。
- [x] A3: スコープは回帰テスト追加のみ。`destructive-guard.py` の挙動は変更しない。
- [x] A4: 既存ケース表には引用符付きコマンド置換の deny ケースが既に数件存在する（186 行「prefix$(cat list)」、194-195 行「"/tmp/sub/"$(cat list)」系）。欠けているのは 165-168 行の親参照 + safe ルート着地形の引用符付き双子であり、本変更はそこを埋める。
- [x] A5: version の刻みは patch（0.1.79 → 0.1.80）。挙動変更が無くファイル内容が変わるだけのため semver 上 patch が妥当。
- [x] A6: リポジトリルートに LICENSE ファイルが存在しないため、プロジェクトライセンスは未確定（SPDX id なし）として扱う。
- [x] A7: 単一引用符形は実シェルでは置換が展開されないため、フックの deny はコマンド文字列の静的解析上の fail-closed 判定であって、シェル意味論上の再現ではない。期待値は実測に合わせる。

### 14.2 未確認・保留事項

なし。全要件が解決済み（status: resolved）。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 判定対象のフック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース表
- `em-workflow/hooks/tests/run-destructive-guard.py`: スイートのランナー
- `.claude/rules/hook-tests.md`: ケース表の記法と既存ケース保持のルール
- `.claude/rules/core-plugin-version-bump.md`: version 更新のルール

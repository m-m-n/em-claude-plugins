# Feature: destructive-guard-quoted-substitution-fail-open

要件の出典: `feature-docs/destructive-guard-quoted-substitution-fail-open/REQUIREMENTS.md`

## Overview

destructive-guard の「引用符付きコマンド置換 + 親参照 + safe ルート着地」形について、fail-closed（deny）であることを期待値スイートに固定する。報告された fail-open は main（fba3d7e）では再現しない（9 形すべて deny の実測済み）ため、挙動修正ではなく回帰テスト整備を行う。変更対象は `em-workflow/hooks/tests/destructive-guard-cases.json` とプラグイン version 2 箇所のみで、フック本体は変更しない。

## Objectives

- destructive-guard の「引用符付きコマンド置換 + 親参照 + safe ルート着地」形が fail-closed（deny）であることを期待値スイートで固定し、同じ穴が再び開いたときに検知できる状態にする。
- 報告された fail-open は main（fba3d7e）では再現しない（オーケストレーター実測、9 形すべて deny）ため、挙動修正ではなく回帰テスト整備で完了とする。
- em-workflow 配下のファイルを変更するため、同一変更内でプラグイン version を上げ、インストール済みキャッシュが更新される状態を保つ。

## User Stories

要件に記載なし。

## Technical Requirements

### Functional Requirements

- **FR1 - 引用符付きコマンド置換の deny ケース追加:** `em-workflow/hooks/tests/destructive-guard-cases.json` に、チケットが allow と報告した 5 形（二重引用符で囲んだ形 / 単一引用符で囲んだ形 / バッククォート置換を二重引用符で囲んだ形 / 着地先を dist・node_modules・.cache に変えた形 / 置換の前後に文字を密着させた形）を、既存の裸形の双子（現行 165-168 行）に対応する形で追加する。
- **FR2 - 期待値は実測値であること:** 追加する各ケースの期待判定は、現行 `em-workflow/hooks/destructive-guard.py` に同一コマンド文字列を通した実測結果と一致させる。実測が deny 以外（ask 等）になった形は、その実測値をそのまま期待値として記録し、ラベルにその理由を書く。期待値を推測で書かない。
- **FR3 - 既存ケースの完全保持:** `.claude/rules/hook-tests.md` の「既存の deny / ask ケースは消さない」に従い、`destructive-guard-cases.json` の既存エントリを 1 件も削除・改変しない。追加のみを行う。
- **FR4 - フック本体を変更しない:** `em-workflow/hooks/destructive-guard.py` の判定挙動を変更しない。今回の変更対象はケース表とプラグイン version の 2 種類のファイルに限る。
- **FR5 - ケース表の記法準拠:** 追加ケースは既存と同じ 3 要素配列 `[期待する判定, ラベル, コマンド]` で書き、ラベルは既存の日本語 + カテゴリ接頭辞の様式（例:「評価境界(rm-recursive): ...」「スクラッチ外(rm-recursive): ...」）に揃える。ラベルには「引用符付きでも裸形と同じ判定になること」を検証している旨が読み取れる記述を含める。
- **FR6 - プラグイン version の同時更新:** `.claude/rules/core-plugin-version-bump.md` に従い、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version を、同じ変更の中で同一の値に patch 単位で上げる（現在いずれも 0.1.79）。
- **FR7 - スイート全件グリーン:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（終了コード 0、FAIL 行なし）。

### Non-Functional Requirements

- **NFR1 - 外部依存を持たない:** 追加ケースは外部依存を持たない。ネットワーク・実ファイルシステム上の存在するパス・カレントディレクトリの内容に判定が依存しないコマンド文字列だけを使う（フックは静的解析であり、コマンドは実行されない）。
- **NFR2 - 実行時間の線形性:** テストの実行時間は 1 ケースあたりサブプロセス 1 本の線形増加に収まる。ケース数の追加以外にランナーの構造を変えない。
- **NFR3 - JSON 妥当性の維持:** `destructive-guard-cases.json` は JSON として妥当であり続ける（`json.load` が通る）。
- **NFR4 - 標準ライブラリのみ:** Python 標準ライブラリのみで動作する状態を維持し、新規依存を追加しない。

## Implementation Approach

### Architecture

判定ロジックは変更しない（FR4）。変更は期待値表とプラグイン version に閉じる。

```
destructive-guard-cases.json  [期待する判定, ラベル, コマンド]
            │  読み込み
            ▼
run-destructive-guard.py  ── 1 ケース = サブプロセス 1 本 ──▶ destructive-guard.py（変更なし）
            │
            ▼
        ok / FAIL（全件 ok で exit 0）
```

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py              # 変更しない（FR4 / AC7）
│   └── tests/
│       ├── destructive-guard-cases.json  # ケース追加のみ（FR1 / FR3 / FR5）
│       └── run-destructive-guard.py      # 変更しない（NFR2）
└── .claude-plugin/
    └── plugin.json                       # version を patch 単位で更新（FR6）
.claude-plugin/
└── marketplace.json                      # em-workflow の version を同一値に更新（FR6）
```

### Dependencies

**External Dependencies:** なし。Python 標準ライブラリのみ（NFR4）。

## Declared Change Set

このセクションは手書きの一覧ではなく create-plan での導出を宣言する: フィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出される（`references/phases/create-plan-phase.md`）。

上記に加えて、次の 2 つのワークフロー生成エントリを既定で宣言に含める。

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップの成果物を含む。生成主体は各フェーズドキュメントと `references/phase-state.md` にあり、ここでは引用のみを行う。

`test-docs/{feature}/**` は `test-docs/{feature}/{T}.tests.yaml`（タスクごとのテスト記録）を含む。生成主体は `implement-phase.md` にあり、ここでは引用のみを行う。

この 2 つの既定エントリは、SPEC 作成者が明示的に除外しない限り宣言の一部である。この宣言はスーパーセットの主張であり、検証時に観測される実際の変更集合はこの宣言に含まれる（CONTAINED IN）必要がある。

## Test Scenarios

### Unit Tests

- [ ] TS1 (FR1, FR2): 二重引用符で囲んだ置換 + 親参照 + safe ルート着地 — deny
- [ ] TS2 (FR1, FR2): 単一引用符で囲んだ形。実シェルでは置換が展開されず literal パス削除になるが、フックの静的解析としては fail-closed 側に倒れることを固定する — deny
- [ ] TS3 (FR1, FR2): バッククォート置換を二重引用符で囲んだ形（両スペル対称性のバッククォート側） — deny
- [ ] TS4 (FR1, FR2): 着地先を dist に変えた引用符付き形 — deny
- [ ] TS5 (FR1, FR2): 着地先を node_modules に変えた引用符付き形 — deny
- [ ] TS6 (FR1, FR2): 着地先を .cache に変えた引用符付き形 — deny
- [ ] TS7 (FR1, FR2): 引用符内で置換の前に実テキストが密着する形 — deny
- [ ] TS8 (FR1, FR2): 引用符内で置換の後ろに実テキストが密着する形 — deny
- [ ] TS9 (FR3): 対照として既存の裸形ケース（165-168 行）が変更後も同じ期待判定で残っていること — deny（既存のまま）

### Integration Tests

- [ ] TS10 (FR7): スイート全体の実行 — `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 ok、exit 0
- [ ] TS11 (FR4, FR6): フック本体に差分が無いこと、および version が両ファイルで同一の新しい patch 値に上がっていること — 差分ゼロ / version 一致

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 単一引用符形（TS2）: 実シェルでは置換が展開されないため、deny は静的解析上の fail-closed 判定であって、シェル意味論上の再現ではない。期待値は実測に合わせる（FR2）。
- [ ] 実測が deny 以外（ask 等）になった形: その実測値をそのまま期待値として記録し、ラベルに理由を書く（FR2）。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。

なし。FR1-FR7、NFR1-NFR4 はすべて解決済み。

## Success Criteria

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

## Assumptions

- A1: 報告された fail-open は main HEAD fba3d7e の `destructive-guard.py` では再現しない。攻撃シナリオ 5 形を含む 9 形の実測結果が全て deny であることは、オーケストレーターが提供した確定事実である。
- A2: チケットが指す `WORD_BOUNDARY_CHARS` は現行実装に存在せず、`_mark_substitutions()` は `SUBSTITUTION.sub(UNRESOLVED_MARK, chunk)` のみ（`destructive-guard.py` 633 行）。チケットの該当箇所記述は CLOSED の PR 30 のブランチ実装に対するもので、main には適用されない。
- A3: スコープは回帰テスト追加のみ。`destructive-guard.py` の挙動は変更しない。
- A4: 既存ケース表には引用符付きコマンド置換の deny ケースが既に数件存在する（186 行「prefix$(cat list)」、194-195 行「"/tmp/sub/"$(cat list)」系）。欠けているのは 165-168 行の親参照 + safe ルート着地形の引用符付き双子であり、本変更はそこを埋める。
- A5: version の刻みは patch（0.1.79 → 0.1.80）。挙動変更が無くファイル内容が変わるだけのため semver 上 patch が妥当。
- A6: リポジトリルートに LICENSE ファイルが存在しないため、プロジェクトライセンスは未確定（SPDX id なし）として扱う。
- A7: 単一引用符形は実シェルでは置換が展開されないため、フックの deny はコマンド文字列の静的解析上の fail-closed 判定であって、シェル意味論上の再現ではない。期待値は実測に合わせる。

## References

- 要件定義書: `feature-docs/destructive-guard-quoted-substitution-fail-open/REQUIREMENTS.md`
- フック本体: `em-workflow/hooks/destructive-guard.py`
- ケース表: `em-workflow/hooks/tests/destructive-guard-cases.json`
- ランナー: `em-workflow/hooks/tests/run-destructive-guard.py`
- ケース表のルール: `.claude/rules/hook-tests.md`
- version 更新のルール: `.claude/rules/core-plugin-version-bump.md`

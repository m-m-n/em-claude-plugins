---
title: "destructive-guard-quoted-substitution"
created_date: 2026-09-13
status: draft
---

# destructive-guard-quoted-substitution - 要件定義書

## 1. 概要

### 1.1 背景

`destructive-guard.py` がクォート付きコマンド置換を含む再帰削除を止めるとき、理由文に表示されるターゲットが空白1文字になり、提示される `gio trash` のパスも実在しないものになる、というチケットが起票された。

同一原因の姉妹チケット（クォート無しのコマンド置換でターゲットが消えて allow になる問題）の修正が main にマージ済みであり、チケットの再現コマンドは既に `rm-unresolvable` で止まる。

### 1.2 目的

- クォート付きコマンド置換を含む再帰削除の理由文が「対象を静的に確定できない」と読み取れる表現になっている状態を、回帰テストで恒久的に固定する。
- 同一原因の再発を、チケットの再現形そのものとその綴り違いを含むテストケースで検出できるようにする。
- 変更を利用者環境のプラグインキャッシュへ確実に届ける。

### 1.3 スコープ

対象:

- `em-workflow/hooks/tests/destructive-guard-cases.json` への回帰ケース追加（2件）
- `em-workflow/.claude-plugin/plugin.json` とリポジトリルート `.claude-plugin/marketplace.json` の em-workflow version 引き上げ

対象外:

- `em-workflow/hooks/destructive-guard.py` の変更（FR5）

## 2. ビジネス要件

### 2.1 ビジネス目標

- destructive-guard がクォート付きコマンド置換を含む再帰削除を止めるとき、理由文が「対象を静的に確定できない」と読み取れる表現になっている状態を、回帰テストで恒久的に固定する。
- 同一原因の再発を、チケットの再現形そのものとその綴り違いを含むテストケースで検出できるようにする。
- 変更を利用者環境のプラグインキャッシュへ確実に届ける。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow プラグイン利用者 | destructive-guard の判定と理由文を受け取る Claude Code 利用者 |

### 2.3 期待される効果

- 同一原因の再発がテストスイートで検出される。
- 変更が利用者環境のプラグインキャッシュへ反映される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | クォート付きコマンド置換を含む再帰削除の判定 | em-workflow プラグイン利用者 | 中 |

### 3.2 ユースケース詳細

#### UC01: クォート付きコマンド置換を含む再帰削除の判定

**アクター**: em-workflow プラグイン利用者

**事前条件**:
- 統合ワークツリーの `em-workflow/hooks/destructive-guard.py` が配置されている

**基本フロー**:
1. 削除対象がクォートで囲まれたコマンド置換である `rm` コマンドが PreToolUse で検査される。
2. destructive-guard が `rm-unresolvable` として判定する。
3. 理由文に「対象が変数/コマンド置換で影響範囲を静的に確定できない」旨が出る。

**事後条件**:
- 理由文のターゲットが空白1文字にならない。
- 実在しない `gio trash` パスが提示されない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 再現形の回帰ケース追加 | チケット再現コマンドのケースを追加する | 高 |
| FR2 | バッククォート綴りの回帰ケース追加 | 再現形のバッククォート綴り版のケースを追加する | 高 |
| FR3 | 既存ケースの保全 | 既存ケースを削除も改変もしない | 高 |
| FR4 | プラグイン version の引き上げ | 2箇所の version を同一の patch 単位で上げる | 高 |
| FR5 | フック本体を変更しない | `destructive-guard.py` に変更を加えない | 高 |
| FR6 | 追加ケースの期待判定値 | 追加2件の期待判定を `ask` にする | 高 |
| FR7 | ケースのラベル | 経路と綴りの違いが読み取れるラベルにする | 中 |

### 4.2 機能詳細

#### FR1: 再現形の回帰ケース追加

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、チケットの再現コマンドと文字単位で一致するコマンド文字列を持つケースを、`[期待する判定, ラベル, コマンド]` の3要素形式で追加する。

対象のコマンド文字列:

```
rm -rf "$(printf /home/sakura/valuable)"
```

#### FR2: バッククォート綴りの回帰ケース追加

**説明**: 同じファイルに、再現形のバッククォート綴り版のケースも同じ3要素形式で追加する。`$(...)` 綴りとバッククォート綴りが同じ経路で同じ判定になることを固定する。

対象のコマンド文字列:

```
rm -rf "`printf /home/sakura/valuable`"
```

#### FR3: 既存ケースの保全

**説明**: 既存の deny / ask / allow ケースは削除も改変もしない。追加のみ行う。既存 226 件は件数・内容とも変化しない。

#### FR4: プラグイン version の引き上げ

**説明**: `em-workflow/` 配下を変更するため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` の `version` とリポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を、同一の patch 単位で引き上げた値にする。

#### FR5: フック本体を変更しない

**説明**: `em-workflow/hooks/destructive-guard.py` には一切変更を加えない。チケットの症状は同一原因の姉妹チケット修正で既に解消しており、本チケットの作業は回帰ケース追加と version 引き上げに限る。

#### FR6: 追加ケースの期待判定値

**説明**: FR1 / FR2 で追加する両ケースの第1要素（期待する判定）は `ask` とする。同じ rm-unresolvable 経路の既存ケースに揃える。再現手順の実行で観測される `deny` は無人実行（CLAUDE_BATCH）下の ask→deny 降格による表示差であり、別判定ではない。

#### FR7: ケースのラベル

**説明**: 追加する2件のラベルは、rm-unresolvable 経路であることと、クォート付きコマンド置換の綴り（`$()` / バッククォート）の違いが読み取れる日本語文言にする。

## 5. 非機能要件

### 5.1 NFR1: 標準ライブラリのみ

テストコードは Python 標準ライブラリのみを使い、第三者パッケージを import しない（test/README.md）。

### 5.2 NFR2: ケース形式の遵守

追加ケースは `[期待する判定, ラベル, コマンド]` の3要素形式に従う（.claude/rules/hook-tests.md）。

### 5.3 NFR3: 新規ファイルを増やさない

新規ファイルを増やさず、既存の `em-workflow/hooks/tests/destructive-guard-cases.json` への追記で完結させる。

### 5.4 NFR4: 配布物としての妥当性

`em-workflow/` 配下の全ファイルは利用者環境のキャッシュへ配布されるため、追加するテストケースも配布物として妥当な内容にする（.claude/rules/core-plugin-structure.md）。

### 5.5 NFR5: 誤爆を招かない

追加ケースが既存の allow ケースを巻き込んで誤爆させない。誤爆は無人実行をその場で止めるため、見逃しと同じ重さで扱う（.claude/rules/hook-tests.md）。

## 6. UI/UX要件

該当なし。UI・視覚要素を持たないため、デザインステップは skip とする。

## 7. データ要件

該当なし。変更対象は JSON のテストケース配列への追記とプラグインの version 文字列のみ。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テストコードは Python 標準ライブラリのみを使う（NFR1）。
- 追加ケースは3要素形式に従う（NFR2）。
- 新規ファイルを増やさない（NFR3）。

### 9.2 ビジネス上の制約

- `em-workflow/` 配下の全ファイルは利用者環境のキャッシュへ配布される（NFR4）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-quoted-substitution/**`
- `test-docs/destructive-guard-quoted-substitution/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`。生成主体は `implement-phase.md` を参照。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。
- この宣言はスーパーセットの主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 追加ケースが既存の allow ケースを巻き込んで誤爆させる | 中 | 既存226件の判定が変化しないことを確認する（NFR5 / TS-4） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| version 据え置きにより変更が利用者環境のキャッシュへ届かない | 中 | 中 | 2箇所の version を同一値で引き上げる（FR4 / TS-5） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が追加ケース込みで全件通る（226 + 2 = 228 件）。
- [ ] 追加ケース2件のコマンド文字列が、チケット再現手順のコマンドおよびそのバッククォート綴り版と文字単位で一致する。
- [ ] 追加ケース2件の期待判定がいずれも `ask` である。
- [ ] 既存ケースの件数と内容が、追加分を除いて変化していない。
- [ ] `em-workflow/hooks/destructive-guard.py` に差分が無い。
- [ ] チケットの再現手順を実行したとき、理由文のターゲットが空白1文字にならず、`[destructive-guard/rm-unresolvable]` の文言が出る。
- [ ] `em-workflow/.claude-plugin/plugin.json` とルート `.claude-plugin/marketplace.json` の em-workflow version が、互いに等しくかつ変更前より新しい値になっている。

## 12. テストシナリオ

### TS-1: 再現手順でターゲットが空白1文字にならない

- **前提**: 現在の統合ワークツリーの `em-workflow/hooks/destructive-guard.py`
- **操作**: チケットの再現手順（再現コマンドを `tool_input.command` として stdin に渡して実行）を走らせる
- **期待**: `permissionDecisionReason` のターゲットが空白1文字にならず、`[destructive-guard/rm-unresolvable]` として「対象が変数/コマンド置換で影響範囲を静的に確定できない」旨が出る。実在しない `gio trash` パスは提示されない。

### TS-2: 再現形のケースが期待判定 ask で存在する

- **前提**: `em-workflow/hooks/tests/destructive-guard-cases.json`
- **操作**: コマンド文字列が再現形（`$()` 綴り）に一致するエントリを探す
- **期待**: 該当エントリがちょうど1件存在し、第1要素が `ask` である。

### TS-3: バッククォート綴りのケースが期待判定 ask で存在する

- **前提**: `em-workflow/hooks/tests/destructive-guard-cases.json`
- **操作**: コマンド文字列がバッククォート綴り版に一致するエントリを探す
- **期待**: 該当エントリがちょうど1件存在し、第1要素が `ask` である。

### TS-4: ガードスイートが全件通る

- **前提**: 追加ケースを含む destructive-guard-cases.json
- **操作**: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行する
- **期待**: 228/228 が通り、失敗が0件である。既存226件の判定は変化しない。

### TS-5: version が2箇所で一致し、かつ新しい

- **前提**: 変更前後の `em-workflow/.claude-plugin/plugin.json` とルート `.claude-plugin/marketplace.json`
- **操作**: em-workflow の version 文字列を両ファイルから読み出して比較する
- **期待**: 2つの値が等しく、かつ変更前の値より patch が1つ以上進んでいる。他プラグインの version は変化していない。

### TS-6: フック本体に差分が無い

- **前提**: 統合ブランチの差分
- **操作**: `em-workflow/hooks/destructive-guard.py` の差分を確認する
- **期待**: 差分が無い。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| rm-unresolvable | destructive-guard が、再帰削除の対象を静的に確定できないと判定する経路 |
| ask→deny 降格 | 無人実行（CLAUDE_BATCH）下で `ask` 判定が `deny` として返る挙動 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 本チケットで `destructive-guard.py` 本体の変更は不要で、作業は回帰ケース追加と version bump に限られる（a1 / scope.remaining-work）: 同一原因の姉妹チケット修正が main にマージ済みで、再現コマンドは既に rm-unresolvable で止まるため。影響度 中 / 可逆。
- [x] 追加する回帰ケースの期待判定は `ask` であり、再現手順で観測された `deny` は無人実行時の降格による表示差である（a2 / testing.expected-verdict）: 同じ経路の既存2ケースが ask を期待値として通っているため。影響度 中 / 可逆。
- [x] `em-workflow/hooks/tests/` 配下のみの変更でも version bump の対象になる（a3 / scope.remaining-work）: core-plugin-structure.md により plugin 配下の全ファイルが利用者環境のキャッシュへ配布されるため。影響度 低 / 可逆。
- [x] この機能は UI・視覚要素を持たず、設計ステップは不要（a4 / design-step.decision）: 変更対象は JSON のテストケース配列への追記とプラグインの version 文字列のみであるため。影響度 低 / 可逆。

### 14.2 未確認・保留事項

なし（`status: tbd` の要件は無い）。

## 15. 参考資料

- `.claude/rules/hook-tests.md`: ケース形式と誤爆・見逃しの扱い
- `.claude/rules/core-plugin-structure.md`: プラグイン配下の配布範囲
- `.claude/rules/core-plugin-version-bump.md`: version 引き上げの2箇所
- Notion チケット: [https://www.notion.so/3d63509ec8ee815d8337cc340757a824](https://www.notion.so/3d63509ec8ee815d8337cc340757a824)

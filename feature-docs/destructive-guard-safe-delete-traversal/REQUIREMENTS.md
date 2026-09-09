---
title: "destructive-guard-safe-delete-traversal"
created_date: 2026-09-09
status: draft
---

# destructive-guard-safe-delete-traversal - 要件定義書

## 1. 概要

### 1.1 背景

`destructive-guard.py` の `SAFE_DELETE` 例外は、正規化前のターゲット文字列に対する正規表現の前方一致で適用される。このため、安全ディレクトリ名を接頭辞に持つだけの別パスや、親参照 `..` を含むパスが安全と判定され、削除ガードが allow を返す。`destructive-guard-cases.json` は現在この挙動を既知の穴として allow 期待で固定している。

### 1.2 目的

`SAFE_DELETE` の判定を、正規化後のパスコンポーネント単位の包含判定に置き換え、上記の穴を塞ぐ。あわせてケース表を修正後の実挙動に合わせ、既存の allow ケースを退行させない。

### 1.3 スコープ

対象:

- `em-workflow/hooks/destructive-guard.py` の `SAFE_DELETE` と、それを適用する `check_rm()`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version

対象外:

- シンボリックリンク経由の脱出の排除（14.1 の仮定 A-04）

## 2. ビジネス要件

### 2.1 ビジネス目標

- `destructive-guard.py` の `SAFE_DELETE` 例外を、正規化前の文字列前方一致から、正規化後のパスコンポーネント単位の包含判定に置き換え、安全ディレクトリ名を接頭辞に持つだけの別パスや親参照を含むパスが allow で通る穴を塞ぐ。
- 既知の穴として allow で固定されていたケース表のエントリを、修正後の実挙動に合わせて deny 側へ移し、ケース表が実挙動の記述であり続ける状態を保つ。
- 誤爆を増やさない。既存の allow ケース（スクラッチ領域配下の削除、クォート内言及、ヒアドキュメント本文）を退行させない。

### 2.2 対象ユーザー

該当なし（要件分析はユーザータイプを区別していない）。

### 2.3 期待される効果

該当なし（2.1 の目標以外の効果は要件分析に記載なし）。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 再帰削除コマンドの安全判定 | PreToolUse フック（destructive-guard.py） | 高 |

### 3.2 ユースケース詳細

#### UC01: 再帰削除コマンドの安全判定

**アクター**: PreToolUse フック（`check_rm()`）

**事前条件**:

- Bash ツールの実行前で、コマンドに再帰削除が含まれる。

**基本フロー**:

1. 削除対象に変数展開・コマンド置換が含まれる場合、安全例外に通さず ask(rm-unresolvable) にする（FR6）。
2. 削除対象を字句的に正規化する（FR1）。
3. 正規化後も先頭に `..` が残る相対対象は安全例外に通さない（FR2）。
4. 安全ルートとの比較をパス成分単位の包含判定で行う（FR3）。
5. 絶対スクラッチルートは真の子孫のみ安全とする（FR4）。相対安全名は先頭コンポーネントで 2 クラスに分けて判定する（FR5）。
6. 安全と判定されなければ、既存の rm-recursive deny に落とす。

**代替フロー**:

- 安全ルート配下の純グロブは allow を維持する。ただしドット始まりのグロブ成分は安全例外に通さない（FR7）。

**事後条件**:

- 同じコマンドに対して常に同じ判定が返る（NFR1）。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 安全例外の前に対象を正規化する | 安全例外の適用前に削除対象を字句的に正規化する | resolved |
| FR2 | 正規化後も残る親参照を安全としない | 先頭に `..` が残る相対対象を安全例外に通さない | resolved |
| FR3 | コンポーネント境界で包含を判定する | 前方一致をパス成分単位の包含判定に変える | resolved |
| FR4 | 絶対スクラッチルートは真の子孫のみ安全 | `/tmp` / `/var/tmp` は配下のみ安全、ルート自身は deny | resolved |
| FR5 | 相対安全名の 2 クラスを維持する | ビルド生成物名とスクラッチ名で安全範囲を分ける | resolved |
| FR6 | 未解決の展開は安全例外より先に判定する | 変数展開・コマンド置換を含む対象を ask に落とす | resolved |
| FR7 | 安全ルート配下の純グロブは allow を維持する | `dist/*` の allow を維持し、ドット始まりのグロブ成分は除く | resolved |
| FR8 | ケース表を実挙動に合わせる | SAFE_DELETE ラベル 14 件を deny に反転し、deny ケースを追加する | resolved |
| FR9 | プラグインの version を上げる | plugin.json と marketplace.json の version を同じ値に上げる | resolved |
| FR10 | スイートが全件通る | `run-destructive-guard.py` が全件通る | resolved |

### 4.2 機能詳細

#### FR1: 安全例外の前に対象を正規化する

**説明**: `check_rm()` は `SAFE_DELETE` 例外を適用する前に削除対象を字句的に正規化する。展開は `~` / `$HOME` / `${HOME}`、畳み込みは `.` / `..` / 連続スラッシュ / 先頭 `//`。既存の `normalize_candidate()`（`destructive-guard.py:1093`）と同じ、ファイルシステムに触れない変換に限る。

#### FR2: 正規化後も残る親参照を安全としない

**説明**: 正規化しても先頭に `..` が残る相対対象は安全例外に通さず、既存の rm-recursive deny に落とす。

#### FR3: コンポーネント境界で包含を判定する

**説明**: 安全ルートとの比較を正規表現の前方一致からパス成分単位の包含判定に変える。`targets` が `target` に、`build-debug` が `build` に、`node_modules_bak` が `node_modules` に一致してはならない。一致は成分の完全一致か、セパレータが続く形に限る。

#### FR4: 絶対スクラッチルートは真の子孫のみ安全

**説明**: `/tmp` と `/var/tmp` は、その配下（真の子孫）だけを安全とする。ルート自身は deny を維持する。正規化で末尾スラッシュが落ちるため、`/tmp/` を対象とする再帰削除は `/tmp` と同じ deny になる。

#### FR5: 相対安全名の 2 クラスを維持する

**説明**: 相対対象に限り、先頭コンポーネントで判定する。ビルド生成物名（`node_modules` / `dist` / `build` / `target` / `.next` / `coverage`）は完全一致とその配下を安全とし、`node_modules` 単体の allow を維持する。スクラッチ名（`tmp` / `.cache`）は配下のみ安全とし、名前そのものは deny を維持する。絶対パスはこのクラスでは安全にならない（`/build` は deny のまま）。

#### FR6: 未解決の展開は安全例外より先に判定する

**説明**: 変数展開・コマンド置換を含む対象は、安全ルート配下に見えても安全例外に通さず、既存の ask(rm-unresolvable) に落とす。現在は `SAFE_DELETE` の一致が DYNAMIC の判定より先に効くため、安全ルート配下の未解決展開が allow になっている。

#### FR7: 安全ルート配下の純グロブは allow を維持する

**説明**: `dist/*` のような、安全ルート配下のグロブ削除は allow を維持する（ケース表 132 行）。ただし `..` に一致しうるドット始まりのグロブ成分（`/tmp/.*` 等）は安全例外に通さない。

#### FR8: ケース表を実挙動に合わせる

**説明**: `destructive-guard-cases.json` のうちラベルに SAFE_DELETE を含む 14 件（98-109, 138, 139 行）の期待値を allow から deny に反転し、ラベルの「既知の穴(未修正)」表記を外して修正後の理由に書き換える。加えて `/tmp/../home/sakura/valuable` を対象とする再帰削除の deny ケースを新規追加する。既存の deny / ask ケースは 1 件も削除しない。

#### FR9: プラグインの version を上げる

**説明**: `em-workflow` 配下を変更するため、`em-workflow/.claude-plugin/plugin.json` とリポジトリルート `.claude-plugin/marketplace.json` の version を 0.1.72 から同じ値（patch 繰り上げ）に上げる。

#### FR10: スイートが全件通る

**説明**: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。

## 5. 非機能要件

| ID | 内容 |
|----|------|
| NFR1 | 判定はファイルシステムに触れない。`os.path.realpath` / `stat` / `subprocess` を使わず、同じコマンドは常に同じ判定になる（`destructive-guard.py` モジュール docstring の決定性、`normalize_candidate()` の docstring の制約）。 |
| NFR2 | 誤爆コストは見逃しコストと同じ桁に扱う（`.claude/rules/hook-tests.md`）。ask は claude-batch 下で deny に降格されるため、allow ケースの退行は無人実行をその場で止める。 |
| NFR3 | PreToolUse フックは Bash 実行のたびに同期で走るため、正規化は文字列処理のみに留める。 |
| NFR4 | シンボリックリンク経由の脱出は字句正規化では排除できない。ケース表 9 行が `/tmp/x` を対象とする再帰削除の allow を固定しており、実体解決を導入すると決定性とこの allow の両方を壊すため、残存する制約としてコード内に明記する。 |
| NFR5 | `SAFE_DELETE` の意味を変えるため、定数のコメント（`destructive-guard.py:151`）を新しい判定規則の記述に更新する。 |

## 6. UI/UX要件

該当なし。変更対象は PreToolUse フックの Python 関数 1 つと JSON のケース表で、ユーザーに見える画面・視覚要素・デザイントークンを一切持たない。design-system 候補も 0 件のため、デザインステップは skipped。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 判定はファイルシステムに触れない（NFR1）。
- 正規化は文字列処理のみに留める（NFR3）。
- シンボリックリンク経由の脱出は字句正規化では排除できない（NFR4）。

### 9.2 ビジネス上の制約

該当なし。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| シンボリックリンク経由の脱出は字句正規化で排除できない | 中 | 実体解決は導入せず、残存する制約としてコード内に明記する（NFR4、仮定 A-04） |
| allow ケースの退行が無人実行をその場で止める | 高 | 既存の allow ケース（`node_modules` 完全一致、`/tmp/x` 配下、`./build`、`dist/*`）を退行防止シナリオとして検証する（NFR2） |

### 10.2 ビジネスリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] `/tmp/../home/sakura/valuable` を対象とする再帰削除が deny または ask になる（現状 allow）。
- [ ] `build/../src` を対象とする再帰削除が deny または ask になる（現状 allow、ケース表 139 行）。
- [ ] `targets` を対象とする再帰削除が deny または ask になる（現状 allow、ケース表 138 行）。
- [ ] 対照の `/home/sakura/valuable` を対象とする再帰削除が deny のまま変わらない。
- [ ] 末尾スラッシュ無しの `/tmp` / `tmp` / `.cache` / `/var/tmp` を対象とする再帰削除が deny のまま維持される（ケース表 134-137 行）。
- [ ] `node_modules` を対象とし出力を捨てる形の再帰削除が allow のまま維持される（ケース表 8 行）。
- [ ] `/tmp/x` を対象とする再帰削除が、リダイレクト有無いずれの形でも allow のまま維持される（ケース表 7, 9 行）。
- [ ] `dist/*` を対象とする再帰削除が allow のまま維持される（ケース表 132 行）。
- [ ] コマンド置換のみを対象に持つ既存 2 ケースが allow のまま維持される（対象ゼロで早期 return する経路、ケース表 96, 129 行）。
- [ ] ラベルに SAFE_DELETE を含む 14 件が deny 期待に反転し、ラベルから「既知の穴(未修正)」が消えている。
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同じ値に上がっている。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 セキュリティ: パストラバーサル — `/tmp/../home/sakura/valuable` を対象とする再帰削除が deny になり、理由が対照の `/home/sakura/valuable` と同じ rm-recursive であること。
- [ ] TS2 セキュリティ: 相対パストラバーサル — `build/../src` が正規化で `src` になり deny になること。
- [ ] TS3 境界値: 成分境界 — `targets` / `build-debug` / `dist-ssr` / `target-old` / `coverage.old` / `build-artifacts` / `dist-newstyle` / `coverage-old` / `node_modules_bak` が全て deny になること。
- [ ] TS4 境界値: スクラッチルート自身 — `/tmp/` / `tmp/` / `.cache/` / `/var/tmp/` が、対になる末尾スラッシュ無しの形と同じ deny になること（非対称の解消）。
- [ ] TS5 正常系: 退行防止（allow 側） — `node_modules` 完全一致、`/tmp/x` 配下、`./build`、`dist/*` が allow のまま。
- [ ] TS6 異常系: 退行防止（deny/ask 側） — 既存の rm-root / rm-unresolvable / 親参照混じりの動的目標（110-112 行）が判定を変えないこと。
- [ ] TS7 異常系: 未解決展開 — 安全ルート配下に変数を置いた形が安全例外に通らず ask になること。
- [ ] TS8 セキュリティ: 無人実行の降格ケース（`run-destructive-guard.py` 内の追加アサーション）が引き続き deny を返すこと。

## 13. 用語定義

該当なし。

## 14. 確認事項

### 14.1 確認済み事項

要件分析が置いた仮定（いずれも差し戻し可能）:

- [x] A-01: ラベルに SAFE_DELETE を含む 14 件全てを deny に反転する。完了の定義は 3 パターンしか挙げていないが、正規化とコンポーネント比較を入れた時点で残り 11 件も必然的に判定が変わるため、ケース表を実挙動に合わせる。
  - 根拠: `destructive-guard-cases.json` 98-109, 138, 139 行の既存 allow 期待値。ケース表の期待値変更は差し戻せる。
- [x] A-02: スクラッチルート自身の再帰削除は deny 側に倒す。allow 側に倒すと完了の定義 4 番（末尾スラッシュ無しの `/tmp` / `.cache` / `/var/tmp` の deny 維持）と矛盾する。
  - 根拠: 完了の定義 4 番と、ケース表 134-137 行が固定する既存の deny。
- [x] A-03: 安全ルート配下の純グロブ（`dist/*`）は allow を維持し、未解決として ask に倒すのは変数展開・コマンド置換に限る。グロブは `..` を生成しないため安全ルートから脱出しない。ただしドット始まりのグロブ成分は除く。
  - 根拠: ケース表 132 行が `dist/*` の allow を固定している。`.claude/rules/hook-tests.md` が誤爆コストを見逃しコストと同じ桁に置いている。
- [x] A-04: シンボリックリンク経由の脱出は排除しない。字句正規化のみを行い、実体解決はしない。残存する制約としてコード内に明記する。
  - 根拠: `normalize_candidate()` の docstring が realpath / stat / subprocess の不使用を明示。ケース表 9 行が `/tmp/x` の allow を固定しており、実体解決を入れると判定が実行環境に依存する。
- [x] A-05: 相対の安全名判定は先頭コンポーネントに限る。`foo/build` は今と同じく安全にならない。
  - 根拠: 現行 `SAFE_DELETE` が `^` アンカー付きで、この挙動が既存の deny 側の前提になっている。
- [x] A-06: version の刻みは patch（0.1.72 → 0.1.73）とする。挙動の修正であり互換性を壊す API 変更ではない。
  - 根拠: `.claude/rules/core-plugin-version-bump.md` が挙動の修正を patch と定めている。

### 14.2 未確認・保留事項

なし（`status: tbd` の要件は無い）。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: `SAFE_DELETE`（151-152 行）、`check_rm()`、`normalize_candidate()`（1093 行）
- `em-workflow/hooks/tests/destructive-guard-cases.json`: 判定ケース表
- `em-workflow/hooks/tests/run-destructive-guard.py`: テストランナー
- `.claude/rules/hook-tests.md`: フックのテスト方針
- `.claude/rules/core-plugin-version-bump.md`: version の刻み方

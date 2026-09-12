---
title: "destructive-guard-command-substitution"
created_date: 2026-09-13
status: draft
---

# destructive-guard-command-substitution - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/hooks/destructive-guard.py` は PreToolUse(Bash) で再帰削除を静的に判定する。
削除対象が単語全体としてコマンド置換（`$( )` 形式・バッククォート形式）だけで構成されている場合、
`_mark_substitutions()` が置換を空白 1 文字に潰し、その語がトークンとして消滅する。結果として
`check_rm()` は対象ゼロで早期 return し、判定は `allow` になる。

`em-workflow/hooks/tests/destructive-guard-cases.json` には、この経路が
「既知の穴(未修正)」として `allow` 固定で 2 件記録されている（現行 96 行目の `rm -rf $(mktemp -d)`、
129 行目の `rm -rf $(cat list)`）。

同時に、`rm-unresolvable` の理由文は「再帰削除の対象 `{t}` が変数/コマンド置換で、影響範囲を静的に
確定できない。」と書かれているが、コマンド置換は実際にはこの経路に届いていない。

### 1.2 目的

コマンド置換のみで構成された再帰削除対象を判定に届かせ、`rm-unresolvable`（`ask`）へ合流させる。
併せて理由文とフックの実際の処理範囲を一致させる。

### 1.3 スコープ

**対象**:
- `em-workflow/hooks/destructive-guard.py` の置換マーキング／トークン復元／再帰削除判定の経路
- `rm-unresolvable` の理由文
- `em-workflow/hooks/tests/destructive-guard-cases.json` のケース表
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version

**対象外**:
- コマンド置換が「削除対象」ではなく「コマンド語そのもの」を作る形
- 再帰フラグの無い削除の挙動

## 2. ビジネス要件

### 2.1 ビジネス目標

- 再帰削除の対象がコマンド置換（`$(...)` / バッククォート）だけで構成されている場合に
  destructive-guard.py が `allow` を返す穴を塞ぎ、無人実行中に復元不能な削除が素通りしないようにする。
- `rm-unresolvable` の理由文とフックの実際の処理範囲を一致させ、フック出力を読む人間・エージェントが
  誤った安心を得ないようにする。
- 既存の allow ケース（誤爆防止側）と既存の deny / ask ケース（検知力側）を両方とも維持したまま修正する。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow を使う Claude Code 利用者 | PreToolUse でこのフックの判定を受ける |
| 無人実行（claude-batch）中のエージェント | `ask` が `deny` へ降格された結果を読み、安全な形に書き換えて続行する |

### 2.3 期待される効果

- コマンド置換だけで書かれた再帰削除が無人実行中に素通りしなくなる。
- フック出力の理由文が、実際に扱っている処理内容と一致する。
- 誤爆防止側の allow ケースを 1 件も落とさずに検知力を上げる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 置換のみの削除対象を判定に載せる | destructive-guard.py | 高 |
| UC02 | 理由文から安全な書き換え先を得る | 無人実行中のエージェント | 高 |

### 3.2 ユースケース詳細

#### UC01: 置換のみの削除対象を判定に載せる

**アクター**: destructive-guard.py

**事前条件**:
- Bash ツール呼び出しのコマンド文字列に再帰削除フラグ（`-r` / `-R` / `--recursive`）が含まれる
- 削除対象が単語全体としてコマンド置換で構成されている

**基本フロー**:
1. フックがコマンド文字列を受け取る
2. 置換のマーキングとトークン復元を経て、置換のみの削除対象が対象リストに残る
3. `check_rm()` が `rm-unresolvable` の判定（`ask`）を返す
4. 無人実行時は既存の降格ロジックにより `deny` になる

**代替フロー**:
- 置換の隣に実テキストが続く形は既存の `rm-recursive`（deny）のまま

**事後条件**:
- 判定が `allow` ではなくなり、理由文に問題の削除対象が表示される

#### UC02: 理由文から安全な書き換え先を得る

**アクター**: 無人実行中のエージェント

**事前条件**:
- UC01 の結果として `deny` が返っている

**基本フロー**:
1. エージェントが理由文を読む
2. どの削除対象が問題なのかを理由文の表示から特定する
3. 展開後の実パスを直接書いた形に書き換えて撃ち直す

**事後条件**:
- 書き換え後のコマンドが静的に確定でき、確認なしで続行できる

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 単語全体がコマンド置換の削除対象を検出対象に載せる | 置換のみの削除対象がトークン消滅で早期 return する経路を塞ぐ | 高 |
| FR2 | 判定は既存の rm-unresolvable（ask）へ合流させる | 変数展開と同じ扱いに揃える | 高 |
| FR3 | 理由文が実際の処理範囲と一致する | `rm-unresolvable` の理由文と処理内容を一致させる | 高 |
| FR4 | クォート付きコマンド置換の理由文の対象も空白にしない | `rm -rf "$(cat list)"` の対象表示を空白のみにしない | 中 |
| FR5 | 既存の deny / ask 判定を変えない | 検知力側・誤爆防止側の既存判定を維持する | 高 |
| FR6 | コマンド置換を含む非 rm コマンドを誤爆させない | 全コマンドのトークン列への影響を封じ込める | 高 |
| FR7 | ケース表の更新 | 既知の穴 2 件の書き換えと両形式の新規ケース追加 | 高 |
| FR8 | プラグイン version の同時更新 | plugin.json と marketplace.json の version を同じ値へ上げる | 高 |

### 4.2 機能詳細

#### FR1: 単語全体がコマンド置換の削除対象を検出対象に載せる

**説明**: 再帰削除フラグ（`-r` / `-R` / `--recursive`）付きの削除で、削除対象が単語全体として
コマンド置換で構成されている場合（`$( )` 形式・バッククォート形式の両方。実測例:
`rm -rf $(printf /home/sakura/valuable)` と、その printf をバッククォートで囲んだ等価形）、
置換除去の結果としてトークンが消滅し `check_rm()` が対象ゼロで早期 return する現在の経路を塞ぎ、
その対象が判定に届くようにする。両形式を同じ扱いにする。

**ビジネスルール**:
- `$( )` 形式とバッククォート形式は同じ扱いにする。

#### FR2: 判定は既存の rm-unresolvable（ask）へ合流させる

**説明**: FR1 の対象は、変数展開が既に落ちている `rm-unresolvable` の経路へ合流させ、判定 `ask` を
返す（`CLAUDE_BATCH` 下では既存の降格ロジックにより `deny` になる）。仕様上は `deny` でも完了条件を
満たすが、同じ「静的に確定できない削除対象」である変数展開と扱いを揃えることを優先する。

#### FR3: 理由文が実際の処理範囲と一致する

**説明**: `rm-unresolvable` の理由文（現行の「再帰削除の対象 `{t}` が変数/コマンド置換で、影響範囲を
静的に確定できない。」）が、コマンド置換を実際にその経路で扱っている状態と一致するようにする。

**バリデーション**:
| 項目 | ルール |
|------|--------|
| 理由文に表示される対象 | 空文字・空白のみにならない |
| 理由文に表示される対象 | どの削除対象が問題なのかが読んで分かる表記にする |

#### FR4: クォート付きコマンド置換の理由文の対象も空白にしない

**説明**: 二重引用符で囲んだコマンド置換だけを対象にした再帰削除（`rm -rf "$(cat list)"`）は現在
`rm-recursive` で deny になるが、理由文の対象が空白 1 文字として表示される。FR1/FR3 の修正後も
この形式は `deny` または `ask` のままとし、理由文の対象表示が空白のみにならないようにする。

#### FR5: 既存の deny / ask 判定を変えない

**説明**: 以下の既存判定を維持する。

| 形式 | 維持する判定 |
|------|--------------|
| 置換の隣に実テキストが続く形（`rm -rf $(pwd)/build`、`rm -rf $(pwd)/../tmp/scratch`、`rm -rf tmp/scratch$(pwd)`、およびバッククォート等価形） | deny |
| 置換本体の再走査（`echo $(rm -rf /home/sakura/x)`） | deny |
| 変数展開（`X=$(mktemp -d); rm -rf $X`） | ask |
| safe ルート例外（`rm -rf /tmp/x`、`rm -rf node_modules`、`rm -rf ./build`、`rm -rf dist/*`） | allow |

#### FR6: コマンド置換を含む非 rm コマンドを誤爆させない

**説明**: `_mark_substitutions()` / `_strip_unresolved_marks()` の変更は全コマンドのトークン列に
影響するため、置換を含む無害なコマンド（ビルド実行、コミットメッセージ、`python3 -c`、ヒアドキュメント
本文、リダイレクトのみの文）が引き続き `allow` になること。`head()` が返すコマンド語、
`split_redirects()` のリダイレクト判定、`cp`/`ln`/`rsync` の宛先抽出が、置換を含む語の扱い変更で
崩れないこと。

#### FR7: ケース表の更新

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` の既知の穴として `allow` で固定
されている 2 件（`rm -rf $(mktemp -d)` / `rm -rf $(cat list)`、現行 96 行目・129 行目）を新しい判定に
書き換え、ラベルから「既知の穴(未修正)」の記述を外す。加えて `$( )` 形式とバッククォート形式の両方に
ついて、削除対象が置換のみのケースを追加する。既存の deny / ask ケースは削除しない。

#### FR8: プラグイン version の同時更新

**説明**: `em-workflow/` 配下を変更するため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` の
version とリポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの version を
同じ値へ上げる（現行はどちらも 0.1.74、挙動修正なので patch 刻み）。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR3: フックは PreToolUse で毎回同期実行されるため、追加処理は文字列走査の範囲に収め、入力長に
  対して非線形に増えるループを作らない。`MAX_SHELL_PAYLOAD_EXPANSIONS` のような既存の上限機構を
  壊さない。

### 5.2 セキュリティ要件

- NFR4: 不正な payload に対する fail-open（exit 0）と、`ask` の無人実行時 `deny` 降格の挙動を変えない。
- NFR6: 内部センチネル（`UNRESOLVED_MARK` = NUL）が理由文・stdout のどこにも漏れない。

### 5.3 可用性要件

- NFR1: 判定は決定的であり、同じコマンド文字列には常に同じ判定を返す（destructive-guard.py モジュール
  docstring の約束）。

### 5.4 保守性要件

- NFR5: 理由文は既存と同じ日本語のスタイルで、エージェントが読んで安全な形に書き換えられる具体的な
  指示を含む。
- NFR7: 誤爆 1 件のコストは見逃し 1 件と同じ桁（`.claude/rules/hook-tests.md`）。allow 側ケースを
  1 件も落とさない。

### 5.5 互換性要件

- NFR2: 判定にファイルシステムを参照しない。`os.path.realpath` / `stat` / `subprocess` を新たに
  導入しない（`normalize_candidate()` の制約を維持）。

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし。PreToolUse フック内部の静的判定ロジックと理由文の修正であり、UI・画面・視覚要素を一切
持たない。デザインシステム候補も存在しない。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

該当なし。永続データを持たない。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| ケース表エントリ | 期待する判定 / ラベル / コマンド | 3 要素の配列 | ○ | `destructive-guard-cases.json` の 1 件 |

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Claude Code | PreToolUse フック契約（stdin に JSON、stdout に判定） | ツール呼び出しのコマンド文字列と permission decision |

### 8.2 API仕様要件

PreToolUse の permission decision を stdout に出し、exit 0 で終える既存の契約を変えない。

## 9. 制約条件

### 9.1 技術的制約

- 判定にファイルシステムを参照しない（`os.path.realpath` / `stat` / `subprocess` を新たに導入しない）。
- 判定は決定的である。
- 追加処理は文字列走査の範囲に収める。
- 内部センチネル（NUL）を外部出力に漏らさない。

### 9.2 ビジネス上の制約

- 既存の deny / ask ケースを削除しない（`.claude/rules/hook-tests.md`）。
- allow 側ケースを 1 件も落とさない。

### 9.3 スケジュール制約

記載なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-command-substitution/**`
- `test-docs/destructive-guard-command-substitution/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `_mark_substitutions()` / `_strip_unresolved_marks()` の変更が全コマンドのトークン列に影響する | 高 | FR6 の誤爆条件と、ケース表の allow 半分の回帰で担保する |
| `SUBSTITUTION` 正規表現は最内側しか一致しないため、入れ子の置換は現行 deny | 中 | 境界ケースとして allow へ退行しないことを確認する |
| 内部センチネル（NUL）の外部漏れ | 中 | 理由文・stdout のどこにも漏れないことを確認する |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 誤爆が増えて無人実行がその場で止まる | 中 | 高 | allow 側ケースを 1 件も落とさない（NFR7） |
| 検知力側の既存判定が退行する | 中 | 高 | 既存の deny / ask ケースを削除せず維持する（FR5） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `rm -rf $(printf /home/sakura/valuable)` の判定が allow ではなく ask（`CLAUDE_BATCH` 設定時は deny）になる。
- [ ] AC-2: 同じ内容をバッククォート形式で書いた場合の判定が AC-1 と同じになる。
- [ ] AC-3: `rm -rf $(mktemp -d)` と `rm -rf $(cat list)` が allow でなくなる。
- [ ] AC-4: `rm -rf "$(cat list)"` が deny または ask のままで、理由文に表示される削除対象が空白のみでない。
- [ ] AC-5: 既存の deny / ask ケース（FR5 に列挙した形式を含む）の判定が変わらない。
- [ ] AC-6: `rm-unresolvable` の理由文が、コマンド置換を実際に扱っている処理内容と一致している。
- [ ] AC-7: `em-workflow/hooks/tests/destructive-guard-cases.json` に `$( )` 形式とバッククォート形式の両方の新規ケースが入っている。
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（無人降格ケースを含む）。
- [ ] AC-9: `python3 -m unittest discover -s tests` が通る。
- [ ] AC-10: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version が同じ値に上がっている。

### 11.2 KPI

| 指標 | 目標値 | 測定方法 |
|------|--------|----------|
| ケース表の通過率 | 全件 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` |
| ユニットテストの通過率 | 全件 | `python3 -m unittest discover -s tests` |

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1 正常系: ケース表駆動 — `python3 em-workflow/hooks/tests/run-destructive-guard.py`（期待判定・ラベル・コマンドの 3 要素 JSON をフック本体へ subprocess 実行して突き合わせる）。
- [ ] TS-2 正常系: リポジトリルートのユニットテスト — `python3 -m unittest discover -s tests`（`test/README.md` 記載。フックは JSON を stdin に渡す subprocess 契約でテストする）。
- [ ] TS-3 境界値: 入れ子の置換を対象にした再帰削除（`SUBSTITUTION` 正規表現は最内側しか一致しないため、現行は deny。allow へ退行しないこと）。
- [ ] TS-4 境界値: 削除対象以外の位置（リダイレクト先）にある置換が削除対象として数えられないこと。
- [ ] TS-5 境界値: 複数対象（safe 対象と置換対象の混在、明確な危険パスと置換対象の混在）で最強判定選択が正しく働くこと。
- [ ] TS-6 境界値: 再帰フラグの無い削除の挙動を変えないこと。
- [ ] TS-7 境界値: 二重引用符内で実テキストに隣接する置換の既存 deny を維持すること。
- [ ] TS-8 境界値: `bash -c` / `eval` / ヒアストリングのペイロード内に置換を含む削除でも、`statements()` の再走査経路で同じ判定に届くこと。
- [ ] TS-9 異常系: パース失敗フォールバック（クォート不整合）経路で置換を含むコマンドが例外を投げないこと。
- [ ] TS-10 回帰: ケース表の allow 半分（引用符内の削除文字列、ヒアドキュメント本文、コミットメッセージ、`python3 -c`、`/dev/null` へのリダイレクト、安全先削除）が全件 allow のまま。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| コマンド置換 | `$( )` 形式およびバッククォート形式の置換 |
| 既知の穴 | ケース表に `allow` 固定で記録されていた、置換のみの削除対象 2 件 |
| 無人実行 | `CLAUDE_BATCH` が設定された claude-batch 下の実行。`ask` は `deny` に降格される |
| safe ルート例外 | `check_rm()` が再帰削除でも allow に落とすスクラッチ領域／ビルド生成物の包含判定 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 判定の段: `ask`（`rm-unresolvable` へ合流）とする。完了条件は `deny` でも満たせるが、変数展開と同じ扱いに揃える方針を採る。
- [x] 現行コードの `_mark_substitutions()` は「両側が語境界の置換は空白 1 文字に潰す」分岐を D7 shape (b) の SPEC 固定 allow として明示している。本フィーチャーはこの固定を意図的に更新する。
- [x] `destructive-guard-cases.json` の既存 allow 2 件（既知の穴として固定されたもの）は書き換え対象。`.claude/rules/hook-tests.md` が削除を禁じているのは deny / ask ケースであり、この 2 件はその対象外。
- [x] 再帰フラグの無い削除の挙動は変更しない。現行 `check_rm()` は非再帰ではルート形状のみ判定して返す。
- [x] コマンド置換が「削除対象」ではなく「コマンド語そのもの」を作る形は本フィーチャーの範囲外。影響範囲は削除対象側に限定されている。
- [x] version は 0.1.74 から 0.1.75 への patch 刻み（挙動の修正）。
- [x] リポジトリに LICENSE ファイルと package manifest は無い。

### 14.2 未確認・保留事項

なし。すべての機能要件が resolved。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 判定ロジック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース表
- `em-workflow/hooks/tests/run-destructive-guard.py`: ケース表の実行スクリプト
- `.claude/rules/hook-tests.md`: フックのテスト運用ルール
- `.claude/rules/core-plugin-version-bump.md`: version 更新ルール
- `test/README.md`: ユニットテストの実行方法とフックのテスト契約

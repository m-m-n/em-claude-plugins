---
title: "destructive-guard-write-target-scoping"
created_date: 2026-08-30
status: draft
---

# destructive-guard-write-target-scoping - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/hooks/destructive-guard.py` の `check_self_modification` が、読み取り専用のコマンドを誤検知して無人実行をその場で止めている。特に transcript-write の誤検知は deny（auto モード分類器を経由せず常に拒否）であり、session-log-recall スキルの手順そのものが `2>/dev/null` 付きで止まる。

### 1.2 目的

- `check_self_modification` が読み取り専用コマンドを誤検知して無人実行を止める事象をなくす。
- transcript-write の誤検知を最優先で解消する。
- 自己設定書き込み・transcript 書き込みの検知力は現状のまま維持する（誤爆修正が検知力を削らない）。

### 1.3 スコープ

**対象**:

- `em-workflow/hooks/destructive-guard.py` の `check_self_modification`（書き込み先パス集合方式への書き換え）
- `em-workflow/hooks/tests/destructive-guard-cases.json`（誤爆ケースの追加）
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version フィールド

**対象外**:

- `check_rm` および `SAFE_DELETE`（FR6）。rm 関連には既に誤爆がないため、今回の変更対象に含めない。

## 2. ビジネス要件

### 2.1 ビジネス目標

- `destructive-guard.py` の `check_self_modification` が読み取り専用コマンドを誤検知して無人実行を止める事象をなくす。
- 特に transcript-write の誤検知は deny（auto モード分類器を経由せず常に拒否）であり、session-log-recall スキルの手順そのものが `2>/dev/null` 付きで止まる。これを最優先で解消する。
- 自己設定書き込み・transcript 書き込みの検知力は現状のまま維持する（誤爆修正が検知力を削らない）。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| 無人実行（claude-batch）の走行者 | ask が deny に降格されるため、誤爆 1 件で走行がその場で終わる |
| session-log-recall スキルの利用者 | `2>/dev/null` 付きの手順が transcript-write の deny で止まる |

### 2.3 期待される効果

- 読み取り専用コマンドが誤爆せず通り、無人実行が誤爆で止まらなくなる。
- session-log-recall スキルの手順が deny されずに完走する。
- self-modification（ask）と transcript-write（deny）の検知力は維持される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 読み取り専用コマンドが誤爆せず allow になる | 無人実行の走行者 | 高 |
| UC02 | session-log-recall の transcript 読み取りが allow になる | session-log-recall スキルの利用者 | 高 |
| UC03 | 自己設定・transcript への書き込みが従来どおり検知される | 無人実行の走行者 | 高 |

### 3.2 ユースケース詳細

#### UC01: 読み取り専用コマンドが誤爆せず allow になる

**アクター**: 無人実行の走行者

**事前条件**:

- `destructive-guard.py` が PreToolUse(Bash) で呼ばれる。

**基本フロー**:

1. `grep -rn "x" ~/.claude/skills/ 2>/dev/null` のようなコマンドが実行される。
2. `check_self_modification` が書き込み先パス集合を組み立てる。
3. 集合の要素は `/dev/null` のみで、`SELF_CONFIG` / `TRANSCRIPT` のいずれにも一致しない。
4. 判定は allow となり、走行が継続する。

**代替フロー**:

- 書き込み先集合が空の場合、self-modification / transcript-write のいずれの判定も行わずに戻る（FR3）。

**事後条件**:

- 読み取り専用コマンドが ask / deny にならない。

#### UC02: session-log-recall の transcript 読み取りが allow になる

**アクター**: session-log-recall スキルの利用者

**事前条件**:

- transcript ファイル（`~/.claude/projects/.../*.jsonl`）を読むコマンドが実行される。

**基本フロー**:

1. `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null` が実行される。
2. 書き込み先集合の要素は `/dev/null` のみとなる。
3. `TRANSCRIPT` に一致せず allow となる。

**代替フロー**:

- `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null` も同様に allow となる。

**事後条件**:

- transcript の読み取り手順が deny されない。

#### UC03: 自己設定・transcript への書き込みが従来どおり検知される

**アクター**: 無人実行の走行者

**事前条件**:

- `~/.claude` 配下を書き込み先とするコマンドが実行される。

**基本フロー**:

1. `echo x > ~/.claude/projects/a/b.jsonl` が実行される。
2. 書き込み先集合にリダイレクトのターゲットが入る。
3. `TRANSCRIPT` に一致し deny となる。

**代替フロー**:

- `cat foo > ~/.claude/settings.json` / `sed -i s/a/b/ ~/.claude/rules/x.md` / `rm ~/.claude/hooks/foo.py` / `rm -rf ~/.claude/skills/foo` は ask となる。
- 無人実行下では `echo x > ~/.claude/settings.json` の ask が deny に降格される。

**事後条件**:

- 既存の検知力が維持される。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 誤爆ケースを先にテストスイートへ追加する | allow 期待の 5 ケースを追加し、追加時点で red を確認する | 高 |
| FR2 | 書き込み先パス集合を組み立て、その要素にだけ SELF_CONFIG / TRANSCRIPT を当てる | segment 全体への正規表現検索からパス集合照合へ書き換える | 高 |
| FR3 | 書き込み先が存在しない場合は判定しない | 集合が空のセグメントは判定せずに戻る | 高 |
| FR4 | 読み取り元が `~/.claude` にあるだけのコマンドは allow にする | source 側にあるだけでは発火させない | 高 |
| FR5 | 既存の検知力を維持する | ask / deny の既存判定を保つ | 高 |
| FR6 | rm 系の判定には手を入れない | `check_rm` と `SAFE_DELETE` は変更対象外 | 中 |
| FR7 | プラグイン version を 2 箇所同値で patch 上げする | 0.1.55 → 0.1.56 | 中 |

### 4.2 機能詳細

#### FR1: 誤爆ケースを先にテストスイートへ追加する

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、期待判定 allow で次の 5 ケースを追加する: `grep -rn "x" ~/.claude/skills/ 2>/dev/null` / `ls ~/.claude/skills/ 2>/dev/null | head -40` / `cat ~/.claude/settings.json > /tmp/copy.json` / `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null` / `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null`。既存の deny / ask ケースは 1 件も削除しない。この追加は FR2 の実装より先に行い、追加時点でスイートが red になることを確認する。

**状態**: resolved

**ビジネスルール**:

- 誤爆を見つけたら、直す前にケースを足す（`.claude/rules/hook-tests.md`）。
- 既存の deny / ask ケースは消さない。

**関連受け入れ基準**: AC-2、AC-3、AC-4

#### FR2: 書き込み先パス集合を組み立て、その要素にだけ SELF_CONFIG / TRANSCRIPT を当てる

**説明**: `check_self_modification` を、segment 全体への正規表現検索から「書き込み先パスの集合に対する照合」へ書き換える。集合の抽出元は 3 つ:

- (a) 出力リダイレクトのターゲット（`split_redirects()` は演算子とターゲットを両方 `redirects` に入れるため、演算子でない側を取る。入力リダイレクト `<` 系は含めない）
- (b) `INPLACE_WRITERS`（tee / truncate / shred / install / patch）と `sed -i` の対象引数
- (c) rm / mv / cp / ln / chmod / chown の対象引数（cp / mv / ln は宛先が最後の引数）

`SELF_CONFIG` と `TRANSCRIPT` はこの集合の要素にだけ適用する。

**状態**: resolved

**ビジネスルール**:

- 「対象引数」とはフラグでない引数を指す。cp / mv / ln は最後の 1 つを宛先として扱い、rm / chmod / chown はフラグでない引数すべてを対象として扱う。
- 入力リダイレクト（`<` / `<<` / `<<<`）由来のトークンは集合に入れない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 書き込み先集合が空 | リダイレクトも対象引数もない | 例外を出さずに判定せず戻る（FR3） |
| パス以外のトークンが混じる | `2>&1` のファイルディスクリプタ番号 | `SELF_CONFIG` / `TRANSCRIPT` に一致しないため無害 |

**関連受け入れ基準**: AC-1、AC-5

#### FR3: 書き込み先が存在しない場合は判定しない

**説明**: 組み立てた書き込み先集合が空のセグメントは、self-modification / transcript-write のいずれの判定も行わずに戻る。リダイレクト先が `/dev/null` のみのコマンド（`ls ... 2>/dev/null`、`rm -rf /tmp/x > /dev/null`）は、集合の要素が `/dev/null` と（`2>&1` の場合は）ファイルディスクリプタ番号だけになり、`SELF_CONFIG` / `TRANSCRIPT` のどちらにも一致しない。

**状態**: resolved

**関連受け入れ基準**: AC-1、AC-5

#### FR4: 読み取り元が `~/.claude` にあるだけのコマンドは allow にする

**説明**: 引数由来で writes が立つコマンドでも、`~/.claude` 配下が読み取り元（source）側にあるだけなら発火させない。`cat ~/.claude/settings.json > /tmp/copy.json` と `cp ~/.claude/settings.json /tmp/` はいずれも allow になる。

**状態**: resolved

**関連受け入れ基準**: AC-2

#### FR5: 既存の検知力を維持する

**説明**: 次は現状の判定を保つ。

| コマンド | 期待判定 |
|----------|----------|
| `cat foo > ~/.claude/settings.json` | ask（self-modification） |
| `sed -i s/a/b/ ~/.claude/rules/x.md` | ask |
| `rm ~/.claude/hooks/foo.py` | ask |
| `rm -rf ~/.claude/skills/foo` | ask |
| `echo x > ~/.claude/projects/a/b.jsonl` | deny（transcript-write） |
| 無人実行下で `echo x > ~/.claude/settings.json` | deny（ask の降格） |

`destructive-guard-cases.json` の既存 deny / ask ケースと `run-destructive-guard.py` 末尾の降格ケースが全て通ること。

**状態**: resolved

**関連受け入れ基準**: AC-4、AC-6、AC-7

#### FR6: rm 系の判定には手を入れない

**説明**: `SAFE_DELETE` と既存の誤爆修正により rm 関連には誤爆がない（`rm /tmp/foo` / `rm -rf node_modules` / `rm -rf /tmp/x 2>/dev/null` / `grep -rn "rm -rf /" ~/.claude/hooks/` はいずれも allow）。`check_rm` および `SAFE_DELETE` は今回の変更対象に含めない。

**状態**: resolved

**関連受け入れ基準**: AC-1

#### FR7: プラグイン version を 2 箇所同値で patch 上げする

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、`em-workflow/.claude-plugin/plugin.json` の version と `.claude-plugin/marketplace.json` の em-workflow エントリの version を同じ値に上げる。挙動の修正なので patch。現在値は両方 0.1.55、上げ先は 0.1.56。

**状態**: resolved

**関連受け入れ基準**: AC-8

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし

### 5.2 セキュリティ要件

- このフックは安全網であり、誤爆修正で検知力を落としてはならない。self-modification（ask）と transcript-write（deny）の検知は FR5 の全ケースで維持する。
- `ALLOW_NON_DESTRUCTIVE=True` のため、いずれのルールにも一致しないコマンドは allow となり auto モード分類器を丸ごとスキップする。書き込み先集合の抽出漏れは、そのまま検知漏れになる。
- ask の deny 降格は無人実行時のみ（`CLAUDE_BATCH`）。transcript-write は常時 deny であり人手で通せないため、誤爆の実害が最も大きい。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- 判定はコマンド文字列の静的解析だけで行い、コマンドを実行しない。同じコマンドには常に同じ判定を返す（NFR1）。
- フック本体もテストも第三者パッケージに依存しない。`destructive-guard.py` は json / os / re / shlex / shutil / sys のみを import しており、`test/README.md` はテストコードの外部依存禁止を定めている（NFR2）。
- `.claude/rules/hook-tests.md` の規則により、誤爆を見つけたら直す前にケースを足す。既存の deny / ask ケースは消さない（NFR3）。

### 5.5 互換性要件

該当なし

### 5.6 非機能要件一覧

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | 静的解析のみ・決定的判定 | 判定はコマンド文字列の静的解析だけで行い、コマンドを実行しない。同じコマンドには常に同じ判定を返す。 |
| NFR2 | 標準ライブラリのみ | フック本体もテストも第三者パッケージに依存しない。`destructive-guard.py` は json / os / re / shlex / shutil / sys のみを import しており、`test/README.md` はテストコードの外部依存禁止を定めている。 |
| NFR3 | テスト先行と既存ケース保持 | `.claude/rules/hook-tests.md` の規則により、誤爆を見つけたら直す前にケースを足す。既存の deny / ask ケースは消さない。 |
| NFR4 | 誤爆コストの非対称性 | 誤爆 1 件のコストは見逃し 1 件と同じ桁にある（ask は claude-batch 下で deny に降格され、無人走行がその場で終わる）。修正は誤爆を消しつつ検知力を落とさない形にする。 |

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし

### 6.2 画面遷移

該当なし

### 6.3 レスポンシブ対応

該当なし

## 7. データ要件

### 7.1 データモデル概要

該当なし

### 7.2 データ項目

該当なし

### 7.3 データ保持期間

該当なし

## 8. 外部連携

### 8.1 連携システム

該当なし

### 8.2 API仕様要件

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 判定はコマンド文字列の静的解析のみで行い、コマンドを実行しない（NFR1）。
- 第三者パッケージに依存しない。標準ライブラリのみを使う（NFR2）。
- `split_redirects()` は演算子とターゲットを両方 `redirects` に入れるため、演算子でない側を取る必要がある。
- パイプの各段は `statements()` で別セグメントになり、判定は各セグメント単位で行われる。

### 9.2 ビジネス上の制約

- 誤爆 1 件のコストは見逃し 1 件と同じ桁にある（NFR4）。
- 誤爆を見つけたら直す前にケースを足し、既存の deny / ask ケースは消さない（NFR3）。
- プラグインの内容を変更したら、同じ変更の中で version を 2 箇所同値で上げる（FR7）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-write-target-scoping/**`
- `test-docs/destructive-guard-write-target-scoping/**`

`feature-docs/destructive-guard-write-target-scoping/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-write-target-scoping/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-write-target-scoping/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/destructive-guard-write-target-scoping/` ディレクトリを生成しないが、宣言された `test-docs/destructive-guard-write-target-scoping/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 書き込み先集合の抽出漏れがそのまま検知漏れになる | 高 | 抽出元を (a) 出力リダイレクト、(b) `INPLACE_WRITERS` と `sed -i`、(c) rm / mv / cp / ln / chmod / chown の 3 つに揃える（FR2） |
| 書き込み先が変数・グロブで静的に確定できない（`rm -rf ~/.claude/skills/*` 等） | 中 | rm 系は既存の rm-unresolvable / rm-recursive が先に ask/deny を出す。self-modification 側の集合照合が新たな穴を作らないこと |
| フラグを対象引数と誤認する（`tee -a ~/.claude/settings.json`） | 中 | 対象引数はフラグでない引数に限る。ask を維持する |
| `sed -i.bak` / `sed -i ''` の変種でスクリプト引数が集合に混じる | 低 | 現行判定 `a.startswith("-i")` のまま。スクリプト引数は `SELF_CONFIG` に一致しないため判定は変わらない |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 誤爆修正が検知力を削る | 中 | 高 | FR5 の全ケースと既存 deny / ask ケースの通過を受け入れ条件にする |
| transcript-write の誤爆が残る | 中 | 高 | FR1 の 5 ケース（うち 2 件が transcript 読み取り）を allow 期待で先に追加する |
| version 据え置きでキャッシュが更新されない | 中 | 中 | plugin.json と marketplace.json を同値で 0.1.56 に上げる（FR7） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全ケース通過で終了コード 0 を返す。
- [ ] AC-2: FR1 の 5 ケースが `destructive-guard-cases.json` に allow 期待で存在し、いずれも allow と判定される。
- [ ] AC-3: FR1 のケースを追加しただけの状態（FR2 未適用）でスイートを走らせると red になる。
- [ ] AC-4: `destructive-guard-cases.json` の既存 34 ケースが 1 件も削除・改変されておらず、全て期待どおりの判定を返す。
- [ ] AC-5: `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null` と `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null` が deny ではなく allow になる。
- [ ] AC-6: `echo x > ~/.claude/projects/a/b.jsonl` が deny、`echo x > ~/.claude/settings.json` が ask、`rm -rf ~/.claude/skills/foo` が ask のままである。
- [ ] AC-7: `run-destructive-guard.py` 末尾の無人実行降格ケース（`CLAUDE_BATCH=1` で `echo x > ~/.claude/settings.json` → deny）が通る。
- [ ] AC-8: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version が同一値 0.1.56 である。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: `python3 em-workflow/hooks/tests/run-destructive-guard.py`（TS-1）— 誤爆修正と検知力維持の両方を 1 本で確認する。FR1 適用直後は red、FR2 適用後に green。
- [ ] 正常系: `python3 -m unittest discover -s tests`（TS-2）— リポジトリ全体のユニットテストに退行がないことの確認。
- [ ] 正常系: `python3 em-workflow/hooks/tests/run-destructive-guard.py <path-to-installed-guard-copy>`（TS-3）— version bump 後、インストール済みキャッシュ側に修正が反映されたかの確認（任意）。
- [ ] 異常系: 既存の deny / ask ケース（self-modification / transcript-write）が判定を変えないこと。
- [ ] 境界値: `2>&1` のターゲット側 fd 番号、書き込み先集合が空のセグメント、追記リダイレクト `>>` / `2>>`、入力リダイレクト `<` / `<<` / `<<<`。
- [ ] 境界値: `cp ~/.claude/settings.json /tmp/` → allow、`cp /tmp/x ~/.claude/settings.json` → ask、`mv a b c dir/` の宛先は最後の 1 つ、`ln -sf x ~/.claude/hooks/y` は最後の引数側が作られる。
- [ ] セキュリティ: 書き込み先集合の抽出漏れによる検知漏れがないこと（`ALLOW_NON_DESTRUCTIVE=True` のため未一致は allow になる）。
- [ ] パフォーマンス: 該当なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 誤爆 | 本来 allow のコマンドが ask / deny と判定されること |
| 降格 | 無人実行（`CLAUDE_BATCH`）下で ask が deny として扱われること |
| `SELF_CONFIG` | 自己設定書き込みを検出する正規表現 |
| `TRANSCRIPT` | transcript 書き込みを検出する正規表現 |
| `INPLACE_WRITERS` | tee / truncate / shred / install / patch |
| `SAFE_DELETE` | rm 判定側の既存の許容ルール |
| `split_redirects()` | セグメントからリダイレクトを分離する関数。演算子とターゲットを両方 `redirects` に入れる |
| `statements()` | コマンド文字列をセグメントへ分割する関数。パイプの各段は別セグメントになる |
| 書き込み先パス集合 | FR2 が定義する、(a) 出力リダイレクトのターゲット、(b) `INPLACE_WRITERS` と `sed -i` の対象引数、(c) rm / mv / cp / ln / chmod / chown の対象引数からなる集合 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] version bump の基準値: 現在のリポジトリ値 0.1.55（タスク記述の 0.1.51 ではない）。patch 1 つ分なので 0.1.56。
- [x] version bump 先: `plugin.json` と `marketplace.json` の 2 箇所。
- [x] FR2 の (b)(c) における「対象引数」: フラグでない引数を指す。cp / mv / ln は最後の 1 つを宛先として扱い、rm / chmod / chown はフラグでない引数すべてを対象として扱う。
- [x] 入力リダイレクト（`<` / `<<` / `<<<`）由来のトークン: 書き込み先集合に入れない。
- [x] `2>&1` のターゲット側トークン: ファイルディスクリプタ番号であり、`SELF_CONFIG` / `TRANSCRIPT` のどちらにも一致しないため集合に混じっても判定に影響しない。
- [x] `SELF_CONFIG` の先頭アンカー `(?:^|["'\s=])`: 集合の要素（単独トークン）に対して `^` 側の分岐で一致するため、正規表現自体の変更は不要。
- [x] `check_self_modification` のシグネチャ: 変更されうる。呼び出し元は `main()` の 1 箇所のみ。
- [x] 既存テスト基盤: 2 系統。(1) リポジトリルート `tests/` の unittest（`test/README.md` 記載、標準ライブラリのみ）。(2) `em-workflow/hooks/tests/` の destructive-guard 専用期待値スイート（JSON のケース表 + 独自ランナー）。今回の変更が直接対象とするのは (2)。
- [x] 既存 E2E 基盤: なし。
- [x] ライセンス: none（LICENSE ファイルなし）。
- [x] デザインステップ: skipped。UI もアーキテクチャ変更も伴わない。変更範囲は 1 関数（`destructive-guard.py` の `check_self_modification`）と、テストデータ 1 ファイル、version フィールド 2 箇所に閉じる。修正の形はタスク記述が既にパス集合方式として具体化しており、設計判断の余地が残っていない。

### 14.2 未確認・保留事項

なし（全機能要件が resolved）。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 変更対象のフック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: 期待判定のケース表
- `em-workflow/hooks/tests/run-destructive-guard.py`: 専用テストランナー
- `.claude/rules/hook-tests.md`: フックのテスト規則（テスト先行、既存ケース保持）
- `.claude/rules/core-plugin-version-bump.md`: version bump 規則（2 箇所同値）
- `test/README.md`: テストコードの外部依存禁止

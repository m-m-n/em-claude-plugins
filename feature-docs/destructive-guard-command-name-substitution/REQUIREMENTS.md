---
title: "destructive-guard-command-name-substitution"
created_date: 2026-09-14
status: draft
---

# destructive-guard-command-name-substitution - 要件定義書

## 1. 概要

### 1.1 背景

`destructive-guard.py` は、コマンド語そのものがコマンド置換で決まる形
（`$(which rm) -rf <path>`）を allow のまま素通りさせる。`head()` が
`.substitution_only` トークンをコマンド語位置で読み飛ばした結果、その文のコマンド語が
`-rf` になるためである。

あわせて `-c` / `eval` / `<<<` のペイロード引数位置では、置換がクォートで囲まれていたか
どうかを区別していない。引用付き `"$(...)"` を「次の語へ繰り上げる」現行挙動が
`destructive-guard-cases.json` の 230 行目のケースで誤爆を生んでいる。

### 1.2 目的

- コマンド語位置が置換で、残りのトークンが既存の破壊的形状に一致するものを検査対象に
  取り込み、`$(which rm) -rf <path>` の見逃しを塞ぐ。
- ペイロード引数位置でクォートの有無を区別し、引用付き `"$(...)"` の繰り上げが生む
  誤爆（cases.json:230）を取り除く。
- 置換の展開結果そのものがスクリプト本文になる形（cases.json:231）は静的に確定不能で
  あることを設計判断として明文化し、理由文・ラベル・docstring をその範囲と一致させる。
- 誤爆を増やさない。`$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` /
  `$(which node) script.js` / `eval "$(ssh-agent -s)"` / `bash -c "$(cat script.sh)"` は
  allow を保つ。

### 1.3 スコープ

**対象**:

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/.claude-plugin/plugin.json` の `version`
- `.claude-plugin/marketplace.json` の em-workflow エントリの `version`

**対象外**:

- 置換の展開結果（=置換本文の出力）がスクリプト本文になる形の解析。
- `failed-run-cleanup-guard.py` / `muse_guard.py` のコード変更。
- ビジュアルデザイン（design ステップは skipped）。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| OBJ-1 | コマンド語そのものがコマンド置換で決まる形のうち、残りのトークンが既存の破壊的形状に一致するものを検査対象に取り込み、`$(which rm) -rf <path>` が allow のまま素通りする見逃しを塞ぐ。 |
| OBJ-2 | `-c` / `eval` / `<<<` のペイロード引数位置でクォートの有無を区別し、引用付き `"$(...)"` を「次の語へ繰り上げる」現行挙動が生む誤爆 (cases.json:230) を取り除く。 |
| OBJ-3 | 置換の展開結果そのものがスクリプト本文になる形 (cases.json:231) は静的に確定不能であることを設計判断として明文化し、理由文・ラベル・docstring をその範囲と一致させる。 |
| OBJ-4 | 誤爆を増やさない。`$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `eval "$(ssh-agent -s)"` / `bash -c "$(cat script.sh)"` は allow を保つ。 |

### 2.2 対象ユーザー

本フィーチャーは PreToolUse フックの判定ロジックの変更であり、requirements_analysis に
対象ユーザーの定義はない。

### 2.3 期待される効果

- `$(which rm) -rf <path>` 形の見逃しが塞がる。
- 引用付きペイロード置換に起因する誤爆（cases.json:230）が解消する。
- 静的解析の対象外範囲が、ラベル・docstring の双方で同一の記述になる。
- 既存の allow 判定は維持される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | コマンド語が置換で決まる破壊的コマンドの遮断 | destructive-guard フック | 高 |
| UC02 | 引用付きペイロード置換を伴うコマンドの通過 | destructive-guard フック | 高 |

### 3.2 ユースケース詳細

#### UC01: コマンド語が置換で決まる破壊的コマンドの遮断

**アクター**: destructive-guard フック

**事前条件**:

- 判定対象のコマンド文字列のコマンド語位置が `.substitution_only` トークンである。

**基本フロー**:

1. `head()` が `.substitution_only` トークンをコマンド語位置で読み飛ばす。
2. 次のトークンが `-` で始まる場合、その文のコマンド名を静的に不明と判定する。
3. 残りのトークンが再帰フラグ（`-r` / `-R` / `--recursive`）と強制フラグ（`-f` /
   `--force`）の両方を持ち、非フラグのオペランドが 1 つ以上あるとき、残り引数を
   既存の `check_rm()` に流す。
4. 同じ文について、残りのトークンを `check_git()` の照合にも掛ける。
5. `check_rm()` / `check_git()` が返す判定段（deny / ask）と理由 id をそのまま採用する。

**代替フロー**:

- 残りが既存セーフルート例外に該当する場合（`$(which rm) -rf dist`、
  `$(which rm) -rf /tmp/scratch/x`）は例外を継承して allow になる。
- `check_git()` が何も一致させない残り（`echo safe`、`status`）は判定を出さない。

**事後条件**:

- `$(which rm) -rf /home/sakura/valuable` は `rm-recursive` で deny になる。
- `$(which git) reset --hard HEAD` は `git-reset-hard` で deny になる。

#### UC02: 引用付きペイロード置換を伴うコマンドの通過

**アクター**: destructive-guard フック

**事前条件**:

- `-c` / `eval` / `<<<` のペイロード引数位置に置換がある。

**基本フロー**:

1. 字句解析前のテキストから、その位置の置換がクォートで囲まれていたかを判定する。
2. 引用付き `"$(...)"` は空展開でも語が消えないため、`_payload_index()` による次の語への
   繰り上げを行わず、その置換自身をペイロードとして扱う。

**代替フロー**:

- 未引用 `$(...)` / バッククォートは現状どおり次の語へ繰り上げる。

**事後条件**:

- `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` は allow になる。
- `eval "$(ssh-agent -s)"` は allow のままである。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | コマンド語位置の置換 + rm 破壊形状の検査 | コマンド名が静的に不明な文の残りトークンを `check_rm()` に流す | 高 |
| FR2 | コマンド語位置の置換 + git 破壊形状の検査 | 同じ文の残りトークンを `check_git()` にも掛ける | 高 |
| FR3 | 無害な残りの allow 維持 | 実コマンド語になり得る次トークンは現行どおり扱う | 高 |
| FR4 | ペイロード引数位置のクォート判定 | 引用付き置換を繰り上げずペイロードとして扱う | 高 |
| FR5 | 未引用置換の繰り上げ挙動の保存 | 未引用置換の現行挙動を維持する | 高 |
| FR6 | cases.json:230 の期待値反転とラベル書き換え | deny を allow に変え、ラベルを書き換える | 中 |
| FR7 | cases.json:231 の対象外宣言の明文化 | ラベルと docstring を同一の範囲記述にする | 中 |
| FR8 | ケース追加 | TS-1〜TS-12 を 3 要素形式で追加する | 高 |
| FR9 | ミラー差分注記の更新 | docstring のミラー注記を新分岐まで拡張する | 中 |
| FR10 | プラグイン version の引き上げ | plugin.json と marketplace.json を同一 patch 値へ | 中 |

### 4.2 機能詳細

#### FR1: コマンド語位置の置換 + rm 破壊形状の検査

**説明**: `head()` が `.substitution_only` トークンをコマンド語位置で読み飛ばした結果、
次のトークンが `-` で始まる（実シェルではコマンド名になり得ない）場合、その文のコマンド名は
静的に不明と判定する。このとき残りのトークンを既存の rm 破壊形状に照合する: 再帰フラグ
（`-r` / `-R` / `--recursive`）と強制フラグ（`-f` / `--force`）の両方があり、かつ非フラグの
オペランドが 1 つ以上あるときに限り、残り引数を既存の `check_rm()` に流す。判定段
（deny / ask）と理由 id は `check_rm()` が現在返すものをそのまま使い、新しい段は作らない。

**ビジネスルール**:

- `$(which rm) -rf /home/sakura/valuable` は `rm-recursive` / deny。
- `$(which rm) -rf dist` / `$(which rm) -rf /tmp/x` は既存のセーフルート例外を継承して allow。

**エラーケース**:

| 条件 | 対応 |
|------|------|
| 再帰フラグのみで強制フラグが無い | 対象外（allow） |
| 非フラグのオペランドが 0 個 | 対象外（allow） |

#### FR2: コマンド語位置の置換 + git 破壊形状の検査

**説明**: 同じくコマンド語位置が `.substitution_only` だった文について、残りのトークンを
`check_git()` の照合にも掛ける（git のサブコマンドは裸の語なので FR1 のフラグ先頭判別では
捕まらない）。

**ビジネスルール**:

- `$(which git) reset --hard HEAD` は既存の `git-reset-hard` で deny。
- `$(which git) clean -fd` は既存の `git-clean` で deny。
- `check_git()` が何も一致させない残り（`echo safe`、`status`）は判定を出さない。

#### FR3: 無害な残りの allow 維持

**説明**: `.substitution_only` を読み飛ばした次のトークンが `-` で始まらない（=実コマンド語に
なり得る）場合は現行どおりそれをコマンド語として扱い、FR1 の経路に入れない。

**ビジネスルール**:

- `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` /
  `$(which node) script.js` は allow のまま。
- `$(which ls) -la` のようにフラグ先頭でも rm 形状に一致しない残りも allow。

#### FR4: ペイロード引数位置のクォート判定

**説明**: `-c` / `eval` / `<<<` のペイロード引数位置に限り、字句解析前のテキストから
その位置の置換がクォートで囲まれていたかを判定する。引用付き `"$(...)"` は空展開でも語が
消えないため `_payload_index()` による次の語への繰り上げを行わず、その置換自身をペイロード
として扱う。

**ビジネスルール**:

- マーカー構造（`UNRESOLVED_MARK` / `SUBSTITUTION_STANDIN` / `Tok` の 3 属性）は変更しない。
- 変更は `extract_shell_payload()` とその補助に閉じ、`head()` / `git_subcommand()` /
  `check_rm()` の読み飛ばしには波及させない。

#### FR5: 未引用置換の繰り上げ挙動の保存

**説明**: 未引用 `$(...)` / バッククォートの繰り上げ挙動は現状どおり維持する。
cases.json:203-205 と :227 の deny 期待値は不変。

#### FR6: cases.json:230 の期待値反転とラベル書き換え

**説明**: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` のケースは削除せず残し、
期待値を `deny` から `allow` に変える。ラベルは現行の「fail-closed の代償: …クォートの有無を
静的に区別できないため…」から、クォート判定により実シェル意味論（第 2 引数は `$0`）に
一致させた旨に書き換える。

**ビジネスルール**:

- `.claude/rules/hook-tests.md` の「既存の deny / ask ケースは消さない」に対しては、
  ケース自体を allow 側の誤爆防止ケースとして保持することで応じる。

#### FR7: cases.json:231 の対象外宣言の明文化

**説明**: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は allow のままとする。
ラベルを現行の「既知の限界(基準版と同じ)」から、置換の展開結果（=置換本文の出力）が
スクリプト本文になる形はこのフックの静的解析の対象外である、という設計判断の記述に
書き換える。

**ビジネスルール**:

- 同じ範囲記述を `extract_shell_payload()` の docstring にも置き、理由文・ラベル・docstring の
  3 者を一致させる。

#### FR8: ケース追加

**説明**: `destructive-guard-cases.json` に TS-1〜TS-12 のコマンドを
`[期待判定, ラベル, コマンド]` の 3 要素で追加する。deny/ask 側と allow 側の両方を入れる。

#### FR9: ミラー差分注記の更新

**説明**: `head()` / `git_subcommand()` の docstring にある「Mirrored in
failed-run-cleanup-guard.py … That mirror does not know about `Tok.substitution_only`;
the skip added here for it is local to this file」の注記を、FR1 / FR2 で増えた分岐も同じく
ローカル限定である旨に拡張する。`failed-run-cleanup-guard.py` と `muse_guard.py` のコードは
変更しない。

#### FR10: プラグイン version の引き上げ

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、同じ変更の中で
`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow
エントリの `version` を同じ次の patch 値へ引き上げる。挙動の修正なので patch 単位。

## 5. 非機能要件

### 5.1 判定の決定性（NFR1）

判定は決定的に保つ。ファイルシステム参照（`realpath` / `stat`）、サブプロセス起動、
置換の実行は一切行わない。判定材料はコマンド文字列のみ。

### 5.2 既存期待値の保存（NFR2, NFR4）

- 既存の期待値は FR6 の 1 件を除いて不変。特に cases.json:194-195 / 197-215 / 217-229 /
  233-234 は現行の判定を保つ。
- `ask` → `deny` の無人実行降格（`decide()` / `unattended()`）は変更しない。
  run-destructive-guard.py 末尾の降格ケースは通り続ける。

### 5.3 誤爆コスト（NFR3）

誤爆コストは見逃しコストと同じ桁（`.claude/rules/hook-tests.md`）。一律 `ask` へ倒す実装は
採らない。`ask` は無人実行で `deny` に降格するため、正常系を止める変更は allow 側ケースで
先に固定してから入れる。

### 5.4 変更範囲（NFR5）

変更範囲は `em-workflow/hooks/destructive-guard.py` と
`em-workflow/hooks/tests/destructive-guard-cases.json`、および FR10 の version 2 ファイルに
限る。他のフックスクリプトには手を入れない。

### 5.5 テストの独立性（NFR6）

テストは外部依存を持たない（`test/README.md`）。追加ケースは既存の 3 要素 JSON 形式に従い、
新しいランナーや依存を導入しない。

## 6. UI/UX要件

該当なし。本フィーチャーは PreToolUse フックの字句解析ロジックであり UI を一切持たない。
design ステップは skipped。

## 7. データ要件

該当なし。永続データを扱わない。

## 8. 外部連携

該当なし。外部依存を持たない（NFR6）。

## 9. 制約条件

### 9.1 技術的制約

- 判定材料はコマンド文字列のみ。ファイルシステム参照・サブプロセス起動・置換の実行を行わない。
- 変更範囲は 4 ファイル（NFR5 と FR10）。
- テストは外部依存を持たず、既存の 3 要素 JSON 形式に従う。
- プロジェクトに LICENSE、パッケージマニフェスト、ビルドコマンド、フォーマットコマンド、
  E2E 基盤はない。
- テストコマンドは `python3 em-workflow/hooks/tests/run-destructive-guard.py` と
  `python3 -m unittest discover -s tests` の 2 つ。

### 9.2 ビジネス上の制約

- `.claude/rules/hook-tests.md`: 既存の deny / ask ケースは消さない。
- `.claude/rules/core-plugin-version-bump.md`: プラグインの中身を変更したら同じ変更の中で
  version を 2 箇所同じ値へ上げる。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの
`files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/destructive-guard-command-name-substitution/**`
- `test-docs/destructive-guard-command-name-substitution/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。
生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/destructive-guard-command-name-substitution/{T}.tests.yaml`）。生成主体は
`implement-phase.md` を参照。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な
  絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 「コマンド名が静的に不明」の判別子が広すぎると誤爆が増える | 高 | 判別子を「`.substitution_only` を読み飛ばした次のトークンが `-` で始まる」ことと git サブコマンド形状への一致の 2 経路に絞る（AS-2） |
| rm 破壊形状の下限が緩いと `grep -r` 等の再帰フラグ単独形を巻き込む | 高 | 下限を「再帰フラグ AND 強制フラグ AND 非フラグオペランド 1 つ以上」とする（AS-3） |
| `ask` は無人実行で `deny` に降格するため、誤爆が正常系を止める | 高 | 一律 `ask` へ倒さず、allow 側ケースで正常系を先に固定する（NFR3） |
| ミラー実装（`failed-run-cleanup-guard.py` / `muse_guard.py`）との差分 | 中 | docstring のミラー注記を新分岐まで拡張し、コードは変更しない（FR9、AS-6） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` が `deny` になり、理由 id が `rm-recursive` である。
- [ ] AC-2: `$(which git) reset --hard HEAD` が `deny`、理由 id が `git-reset-hard` である。
- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` が `allow` である。
- [ ] AC-4: `$(which rm) -rf dist` と `$(which rm) -rf /tmp/scratch/x` が `allow` である（既存セーフルート例外の継承）。
- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` が `allow` であり、当該ケースが cases.json から削除されずラベル書き換えの上で残っている。
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` がいずれも `allow` である。
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / バッククォート形 / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` が `deny` のままである。
- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は `allow` であり、そのラベルと `extract_shell_payload()` の docstring が「置換の展開結果がスクリプト本文になる形は対象外」という同一の範囲を述べている。
- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] AC-10: `python3 -m unittest discover -s tests` が全件通る。
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow version が同一値で、変更前より patch が 1 つ以上進んでいる。
- [ ] AC-12: 変更後のフックが、置換を含まないコマンドに対して変更前と同じ判定・同じ理由文を返す。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 期待判定 | コマンド | 観点 |
|----|----------|----------|------|
| TS-1 | deny | `$(which rm) -rf /home/sakura/valuable` | チケット再現。コマンド名が置換で決まる rm 破壊形状。 |
| TS-2 | deny | `` `which rm` -rf /home/sakura/valuable `` | 両スペル対称性（バッククォート側）。 |
| TS-3 | deny | `$(which git) reset --hard HEAD` | git サブコマンド形状での同等形。 |
| TS-4 | deny | `$(which git) clean -fd` | git-clean 形状での同等形。 |
| TS-5 | allow | `$(which node) script.js` | 誤爆防止。残りが破壊形状に一致しない。 |
| TS-6 | allow | `$(which ls) -la` | 誤爆防止。フラグ先頭だが rm 形状（r+f+オペランド）に一致しない。 |
| TS-7 | allow | `$(which grep) -r pattern src` | 誤爆防止。再帰フラグのみで強制フラグが無い形は対象外。 |
| TS-8 | allow | `$(which rm) -rf dist` | 誤爆防止。セーフルート（build artifact）例外の継承。 |
| TS-9 | allow | `$(which rm) -rf /tmp/scratch/x` | 誤爆防止。スクラッチルート配下の例外の継承。 |
| TS-10 | allow | `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | FR6。既存 cases.json:230 の期待値反転。第 2 引数は実シェルでは `$0`。 |
| TS-11 | allow | `eval "$(ssh-agent -s)"` | 正常系固定。引用付き置換ペイロードを止めない。 |
| TS-12 | allow | `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` | FR7。対象外であることを明文化した上での allow（既存 cases.json:231）。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `.substitution_only` | コマンド置換のみからなるトークンを表す `Tok` の属性。 |
| コマンド語位置 | `head()` が文のコマンド名として読む位置。 |
| ペイロード引数位置 | `-c` / `eval` / `<<<` でスクリプト本文が来る引数位置。 |
| 繰り上げ | `_payload_index()` が置換の次の語をペイロードとして扱う現行挙動。 |
| セーフルート例外 | build artifact やスクラッチルート配下を allow とする既存の例外。 |
| 降格 | 無人実行（`claude-batch`）で `ask` が `deny` になる挙動。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] コマンド語位置の置換の扱い: コマンド語位置が置換のみのトークンで、かつ残りのトークンが
  既存の破壊的形状に一致するときだけ deny/ask に倒す。無害形は allow のまま。
- [x] クォート判定の範囲: マーカー全体の構造は変えず、`-c` / `eval` / `<<<` のペイロード引数位置に
  限って字句解析前テキストからクォートの有無を見る。変更は `extract_shell_payload()` に閉じる。
- [x] design ステップ: skipped。本フィーチャーは UI を持たず、`design_system_candidates` も 0 件。
  字句層コントラクトの設計判断と誤爆許容範囲は create-plan の IMPLEMENTATION.md が担う。

### 14.2 未確認・保留事項

なし。全機能要件の status は resolved。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 変更対象のフック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース定義
- `em-workflow/hooks/tests/run-destructive-guard.py`: テストランナー
- `.claude/rules/hook-tests.md`: フックのテスト運用ルール
- `.claude/rules/core-plugin-version-bump.md`: version 引き上げルール

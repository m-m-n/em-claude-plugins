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
`.substitution_only` トークンをコマンド語位置で読み飛ばすため、その文のコマンド語が
`-rf` になるためである。

この見逃しを「残りトークンのフラグ形状」だけで塞ごうとした形状のみによる推定は、
review round 1 の実測で誤 deny と見逃しを同時に生むことが示された。判別子をフラグの形から
「コマンド語位置の置換から静的に読み取れたコマンド名」へ置き換える必要がある。

あわせて `-c` / `eval` / `<<<` のペイロード引数位置では、語の中のどこかにクォート付き置換が
あるだけで繰り上げを止める部分一致判定（`QUOTED_MARK in quoted_args[idx + 1]`）になっており、
`-c` 本文に `"$(pwd)"` / `"$(date)"` / `"$(dirname ...)"` と破壊的コマンドが混在する形の
本文再走査を丸ごと無効化して deny を allow へ退行させている。

### 1.2 目的

- コマンド語そのものがコマンド置換で決まる形のうち、置換の生テキストからコマンド名が `rm` と
  静的に読み取れるものを検査対象に取り込み、`$(which rm) -rf <path>` が allow のまま素通りする
  見逃しを塞ぐ。フラグとオペランドの並び順（オペランド先行スペル）や強制フラグの有無で
  抜けられないこと（OBJ-1）。
- `-c` / `eval` / `<<<` のペイロード引数位置では、ペイロード語が丸ごと置換であるときに限り
  クォートの有無を区別し、引用付き `"$(...)"` の繰り上げが生む誤爆を取り除く。本文が置換と
  実コマンドの混在であるときは本文の再走査を止めない（OBJ-2）。
- 置換の展開結果そのものがスクリプト本文になる形は静的に確定不能であることを設計判断として
  明文化し、理由文・ラベル・docstring をその範囲と一致させる（OBJ-3）。
- 誤爆を増やさない。置換先頭スペルの判定が素のスペルより厳しくなることはない（OBJ-4）。
- 置換先頭スペルの判定段と理由 id を、静的に読み取れたコマンド名を素で書いたスペルの判定と
  同値にする。コマンド名が静的に読み取れない場合は現行どおり blanket allow を保ち、その限界を
  明文化する（OBJ-5）。

### 1.3 スコープ

**対象**:

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/.claude-plugin/plugin.json` の `version`
- `.claude-plugin/marketplace.json` の em-workflow エントリの `version`

**対象外**:

- 置換の展開結果（=置換本文の出力）がスクリプト本文になる形の解析。
- コマンド名を静的に読み取れない置換先頭形（例: `$(cat cmdfile) -rf /home/sakura/valuable`）の検知。
- `failed-run-cleanup-guard.py` / `muse_guard.py` のコード変更。
- base revision に既存する 6 件のテスト失敗の解消（別タスクとして起票する）。
- ビジュアルデザイン（design ステップは skipped）。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| OBJ-1 | コマンド語そのものがコマンド置換で決まる形のうち、置換の生テキストからコマンド名が `rm` と静的に読み取れるものを検査対象に取り込み、`$(which rm) -rf <path>` が allow のまま素通りする見逃しを塞ぐ。フラグとオペランドの並び順（オペランド先行スペル）や強制フラグの有無で抜けられないこと。 |
| OBJ-2 | `-c` / `eval` / `<<<` のペイロード引数位置では、ペイロード語が丸ごと置換であるときに限りクォートの有無を区別し、引用付き `"$(...)"` の繰り上げが生む誤爆を取り除く。本文が置換と実コマンドの混在であるときは本文の再走査を止めない。 |
| OBJ-3 | 置換の展開結果そのものがスクリプト本文になる形は静的に確定不能であることを設計判断として明文化し、理由文・ラベル・docstring をその範囲と一致させる。 |
| OBJ-4 | 誤爆を増やさない。置換先頭スペルの判定が素のスペルより厳しくなることはない。`$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` / `$(which cp) -rf src dst` / `$(which chmod) -Rf 755 build` / `$(which tar) -rf archive.tar file.txt` / `$(which make) clean -fd` / `eval "$(ssh-agent -s)"` / `bash -c "$(cat script.sh)"` は allow を保つ。 |
| OBJ-5 | 置換先頭スペルの判定段と理由 id を、静的に読み取れたコマンド名を素で書いたスペルの判定と同値にする。コマンド名が静的に読み取れない場合は現行どおり blanket allow を保ち、その限界を明文化する。 |

### 2.2 対象ユーザー

本フィーチャーは PreToolUse フックの判定ロジックの変更であり、requirements_analysis に
対象ユーザーの定義はない。

### 2.3 期待される効果

- `$(which rm) -rf <path>` 形の見逃しが塞がり、オペランド先行スペルや強制フラグなし再帰形でも
  抜けられなくなる。
- 非 rm/git のコマンドが再帰 + 強制フラグを取る形（`cp` / `chmod` / `chown` / `tar` / `grep` /
  `rsync` / `scp`）の誤 deny が生じない。
- `-c` 本文にクォート付き置換と破壊的コマンドが混在する形の本文再走査が復帰する。
- 静的解析の対象外範囲が、ケースのラベルと docstring の双方で同一の記述になる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | コマンド名の証拠に基づく置換先頭形の遮断 | destructive-guard フック | 高 |
| UC02 | 証拠が読み取れない置換先頭形の通過 | destructive-guard フック | 高 |
| UC03 | ペイロード引数位置のクォート判定 | destructive-guard フック | 高 |

### 3.2 ユースケース詳細

#### UC01: コマンド名の証拠に基づく置換先頭形の遮断

**アクター**: destructive-guard フック

**事前条件**:

- 判定対象のコマンド文字列のコマンド語位置が `.substitution_only` トークンである。

**基本フロー**:

1. `head()` がコマンド語位置で `.substitution_only` トークンを読み飛ばす。
2. 字句解析前のセグメント本文から、そのトークンに対応する生の置換テキストを取り出す（FR11）。
3. 置換本文を空白で分割した最後の語を取り、最後の `/` 以降（basename）を
   「静的に読み取れたコマンド名」とする。
4. コマンド名が `rm` であれば、読み飛ばし位置以降の残りトークンをそのまま `check_rm()` に渡す（FR1）。
5. コマンド名が `git` であれば、残りトークンを `check_git()` に渡す（FR2）。
6. `check_rm()` / `check_git()` が返す判定段（deny / ask）と理由 id をそのまま採用する。

**代替フロー**:

- 残りが既存セーフルート例外に該当する場合（`$(which rm) -rf dist`、
  `$(which rm) -rf /tmp/scratch/x`）は例外を継承して allow になる。
- `check_git()` が何も一致させない残り（`echo safe`、`status`）は判定を出さない。

**事後条件**:

- `$(which rm) -rf /home/sakura/valuable` は `rm-recursive` で deny になる。
- `$(which rm) /home/sakura/valuable -rf` / `$(which rm) -r /home/sakura/valuable` も
  同じ `rm-recursive` で deny になる。
- `$(which git) reset --hard HEAD` は `git-reset-hard`、`$(which git) clean -fd` は
  `git-clean` で deny になる。

#### UC02: 証拠が読み取れない置換先頭形の通過

**アクター**: destructive-guard フック

**事前条件**:

- コマンド語位置が `.substitution_only` トークンである。

**基本フロー**:

1. FR11 の読み取り結果が `rm` でも `git` でもない、または読み取り自体ができなかった。
2. どちらの経路にも入れず、現行の blanket allow を保つ（FR3）。

**代替フロー**:

- 置換本文が空、最後の語が `-` で始まる、生テキストとトークン位置の対応付けができない、
  ネストした置換で生テキストの範囲を確定できない場合は「読み取れなかった」として扱う。

**事後条件**:

- `$(which cp) -rf src dst` / `$(which chmod) -Rf 755 build` / `$(which tar) -rf archive.tar file.txt` /
  `$(which make) clean -fd` / `$(hatch env find) reset --hard` / `$(cat cmdfile) -rf /home/sakura/valuable`
  はいずれも allow。

#### UC03: ペイロード引数位置のクォート判定

**アクター**: destructive-guard フック

**事前条件**:

- `-c` / `eval` / `<<<` のペイロード引数位置に語がある。

**基本フロー**:

1. その位置の語が丸ごと置換である（`.substitution_only`）ことを前提条件として判定する。
2. ペイロード語が丸ごと引用付き置換のときだけ、空展開でも語が消えないため次の語へ繰り上げず、
   その位置自身をペイロード境界として扱う（後続引数は実シェルの `$0`）。

**代替フロー**:

- 未引用 `$(...)` / バッククォートは現状どおり次の語へ繰り上げる（FR5）。
- 本文が置換と実コマンドの混在であるときは、本文の再走査を止めない。

**事後条件**:

- `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` は allow になる。
- `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` は allow になる（deny からの反転）。
- `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` は deny になる。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | コマンド語位置の置換 + rm 経路（コマンド名証拠でゲートする） | 読み取ったコマンド名が `rm` のときだけ残りトークンを `check_rm()` に渡す | 高 |
| FR2 | コマンド語位置の置換 + git 経路（コマンド名証拠でゲートする） | 読み取ったコマンド名が `git` のときだけ残りトークンを `check_git()` に渡す | 高 |
| FR3 | 証拠が無い残りの allow 維持 | rm / git の証拠が無い形は経路に入れず allow のまま | 高 |
| FR4 | ペイロード引数位置のクォート判定（語全体が置換のときに限る） | 部分一致判定を撤廃し `.substitution_only` を前提条件にする | 高 |
| FR5 | 未引用置換の繰り上げ挙動の保存 | 未引用置換の現行挙動を維持する | 高 |
| FR6 | クォート付き `-c` ペイロードケースの期待値反転とラベル書き換え | deny を allow に変え、ラベルを書き換える | 中 |
| FR7 | 対象外宣言の明文化 | ラベルと docstring を同一の範囲記述にする | 中 |
| FR8 | ケース追加 | TS-1〜TS-33 を 3 要素形式で持たせる | 高 |
| FR9 | ミラー差分注記の更新 | docstring のミラー注記を新分岐・新関数まで拡張する | 中 |
| FR10 | プラグイン version の引き上げ | plugin.json と marketplace.json を同一 patch 値へ | 中 |
| FR11 | コマンド位置置換からのコマンド名の静的読み取り | 置換の生テキストから basename を読み取る | 高 |
| FR12 | クォート付き here-string 分岐の判定反転の明示 | deny → allow の反転を受け入れ条件とケースに固定する | 中 |
| FR13 | 置換先頭ルーティングの関数抽出 | `main()` のインライン分類を単一の名前付き関数へ切り出す | 中 |

### 4.2 機能詳細

#### FR1: コマンド語位置の置換 + rm 経路（コマンド名証拠でゲートする）

**説明**: `head()` がコマンド語位置で `.substitution_only` トークンを読み飛ばした文について、
FR11 が読み取ったコマンド名が `rm` であるときに限り、読み飛ばし位置以降の残りトークンを
そのまま既存の `check_rm()` に渡す。現行の 2 つの事前ゲート — 次トークンが `-` で始まることを
要求する dash 事前ゲートと、`_rm_route_candidate()` の「再帰 AND 強制 AND 非フラグオペランド
1 つ以上」という下限 — はいずれも撤廃し、閾値の決定は `check_rm()` 自身（再帰の有無と
RM_ROOT_SHAPE）に委ねる。判定段（deny / ask）と理由 id は `check_rm()` が返すものをそのまま
使い、新しい段も新しい理由 id も作らない。

**ビジネスルール**:

- フラグ先行形、オペランド先行形、強制フラグなし再帰形のいずれもが、同じ引数を素の `rm` に
  与えたときと同一の判定になる。
- セーフルート例外も素スペルと同様に継承される。

#### FR2: コマンド語位置の置換 + git 経路（コマンド名証拠でゲートする）

**説明**: 同じ文について、FR11 が読み取ったコマンド名が `git` であるときに限り、残りトークンを
既存の `check_git()` に渡す。現行の「置換を読み飛ばしたら無条件に `check_git()` を呼ぶ」挙動は
撤廃する。

**ビジネスルール**:

- `$(which git) reset --hard HEAD` / `$(which git) clean -fd` は既存の `git-reset-hard` /
  `git-clean` で deny になる。
- `$(which make) clean -fd` や `$(hatch env find) reset --hard` は git の証拠が無いため経路に
  入らず allow のまま残る。
- `check_git()` が何も一致させない残り（`echo safe`、`status`）は判定を出さない。

#### FR3: 証拠が無い残りの allow 維持

**説明**: FR11 の読み取り結果が `rm` でも `git` でもない場合、および読み取り自体ができなかった
場合は、どちらの経路にも入れず現行の blanket allow を保つ。

**ビジネスルール**:

- `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` /
  `$(which ls) -la` / `$(which cp) -rf src dst` / `$(which cp) -Rf src dst` /
  `$(which chmod) -Rf 755 build` / `$(which chown) -Rf user:group /srv/app` /
  `$(which tar) -rf archive.tar file.txt` / `$(which grep) -rf patterns.txt src` /
  `$(which grep) -r pattern src` / `$(which rsync) -rf src/ dst/` / `$(which scp) -rf host:/a /b`
  はいずれも allow。
- 判別子はフラグの形ではなくコマンド名の証拠であり、置換先頭スペルが素スペルより厳しくなる
  経路は存在しない。

#### FR4: ペイロード引数位置のクォート判定（語全体が置換のときに限る）

**説明**: `-c` / `eval` / `<<<` のペイロード引数位置でのクォート判定は、その位置の語が丸ごと
置換である（`.substitution_only`）ことを前提条件とする。語の中のどこかにクォート付き置換が
あるだけで繰り上げを止める現行の部分一致判定（`QUOTED_MARK in quoted_args[idx + 1]`）は誤りで、
`-c` 本文にクォート付き置換（`"$(pwd)"` / `"$(date)"` / `"$(dirname ...)"`）と破壊的コマンドが
混在する形の本文再走査を丸ごと無効化し、deny を allow へ退行させる。

**ビジネスルール**:

- `-c` 側を here-string 側（`.substitution_only` を先に判定する既存の順序）と対称にする。
- ペイロード語が丸ごと引用付き置換のときだけ、空展開でも語が消えないため次の語へ繰り上げず、
  その位置自身をペイロード境界として扱う（後続引数は実シェルの `$0`）。

#### FR5: 未引用置換の繰り上げ挙動の保存

**説明**: 未引用 `$(...)` / バッククォートの繰り上げ挙動は現状どおり維持する。
`bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / バッククォート形 /
`sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` の
deny 期待値は不変。

#### FR6: クォート付き `-c` ペイロードケースの期待値反転とラベル書き換え

**説明**: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` のケースは削除せず残し、
期待値を `deny` から `allow` に変える。ラベルは「fail-closed の代償: クォートの有無を静的に
区別できない」から、クォート判定により実シェル意味論（第 2 引数は `$0`）に一致させた旨へ
書き換える。

**ビジネスルール**:

- `.claude/rules/hook-tests.md` の「既存の deny / ask ケースは消さない」に対しては、ケース自体を
  allow 側の誤爆防止ケースとして保持することで応じる。

#### FR7: 対象外宣言の明文化

**説明**: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は allow のままとし、
ラベルを「置換の展開結果（=置換本文の出力）がスクリプト本文になる形はこのフックの静的解析の
対象外である」という設計判断の記述に書き換える。

**ビジネスルール**:

- 同じ範囲記述を `extract_shell_payload()` の docstring にも置き、理由文・ラベル・docstring の
  3 者を一致させる。
- FR11 が扱えない形（コマンド名を静的に読み取れない置換先頭形。例:
  `$(cat cmdfile) -rf /home/sakura/valuable`）も同じ対象外宣言の一部として同一の場所に明文化する。

#### FR8: ケース追加

**説明**: `destructive-guard-cases.json` に TS-1〜TS-33 のコマンドを
`[期待する判定, ラベル, コマンド]` の 3 要素で持たせる。既存エントリ（TS-1〜TS-12 に対応する
もの）は残し、新規の TS-13〜TS-33 を追加する。

**ビジネスルール**:

- deny 側（オペランド先行、強制なし再帰、混在 `-c` 本文）と allow 側（非 rm/git の再帰 + 強制
  フラグを取るコマンド群、置換先頭 + `clean -fd` / `reset --hard` 形、クォート付き here-string、
  読み取り不能形）の双方を入れる。
- 既存 TS-6 / TS-7 のラベルは、根拠が「rm 形状の下限に届かない」から「rm であるという証拠が
  読み取れない」へ変わるため書き換える（期待値 `allow` は不変）。

#### FR9: ミラー差分注記の更新

**説明**: `head()` / `git_subcommand()` の docstring にあるミラー注記
（`failed-run-cleanup-guard.py` は `Tok.substitution_only` を知らず、ここで足した読み飛ばしは
このファイル限定である旨）を、FR1 / FR2 / FR11 / FR13 で増えた分岐と新しい関数も同じく
ローカル限定である旨に拡張する。

**ビジネスルール**:

- `failed-run-cleanup-guard.py` と `muse_guard.py` のコードは変更しない（両ファイルは本 feature が
  触る記号を 1 つも参照していない）。

#### FR10: プラグイン version の引き上げ

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、同じ変更の中で
`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow
エントリの `version` を同じ次の patch 値へ引き上げる。挙動の修正なので patch 単位。

#### FR11: コマンド位置置換からのコマンド名の静的読み取り

**説明**: コマンド語位置で読み飛ばされた `.substitution_only` トークンに対応する生の置換テキスト
（`$(...)` またはバッククォート）を、字句解析前のセグメント本文から取り出す。その本文を空白で
分割した最後の語を取り、最後の `/` 以降（basename）を「静的に読み取れたコマンド名」とする。
`$(which rm)` → `rm`、`$(command -v rm)` → `rm`、`$(which cp)` → `cp`、`$(hatch env find)` → `find`。

**エラーケース**:

| 条件 | 対応 |
|------|------|
| 置換本文が空 | 読み取れなかったとし、FR1 / FR2 の経路に入れない |
| 最後の語が `-` で始まる | 同上 |
| 生テキストとトークン位置の対応付けができない | 同上 |
| ネストした置換で生テキストの範囲を確定できない | 同上 |

**ビジネスルール**:

- 読み取りは文字列処理だけで行い、置換の実行・サブプロセス起動・ファイルシステム参照は一切
  行わない（NFR1）。
- 本文中の任意の語が rm / git に一致することをもって証拠とはしない
  （`$(git config alias.x) -rf <path>` のような形で誤 deny を生むため）。

#### FR12: クォート付き here-string 分岐の判定反転の明示

**説明**: クォート付き here-string（`bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` の
ように、here-string の対象が丸ごと引用付き置換で、後続引数に破壊的コマンドが続く形）が deny から
allow に反転することを、受け入れ条件として明記し、`destructive-guard-cases.json` に allow ケース
として固定する。

**ビジネスルール**:

- 実シェル意味論（here-string 本文が実行され、後続引数は `$0`）に一致させた反転であることを
  ラベルに書く。
- 非クォート here-string（`bash <<<$(true) 'rm -rf /home/sakura/valuable'`）の deny は不変（FR5）。

#### FR13: 置換先頭ルーティングの関数抽出

**説明**: `main()` のループ内にインラインで置かれている置換先頭のトークン構造分類
（`_skip_to_command_word()` の結果判定、コマンド名証拠の読み取り、rm / git それぞれの経路への
受け渡し）を、`_rm_route_candidate()` があった位置の隣に置く単一の名前付き関数（例:
`_check_substitution_head(words, segment)`）へ切り出す。

**ビジネスルール**:

- 経路の入口条件が 1 箇所のテスト可能な場所にまとまることを条件とし、`main()` 側には
  呼び出しだけを残す。
- 役目を失う `_rm_route_candidate()` は削除する。

## 5. 非機能要件

### 5.1 判定の決定性（NFR1）

判定は決定的に保つ。ファイルシステム参照（`realpath` / `stat`）、サブプロセス起動、置換の実行は
一切行わない。判定材料はコマンド文字列のみ。置換の生テキストを静的に読むこと（FR11）は展開でも
評価でもないため、この制約の内側にある。

### 5.2 既存期待値の保存（NFR2）

既存ケースの期待値は、FR6 が反転させる 1 件と FR12 が明示する 1 件を除いて不変。特に非置換
コマンド、退行防止(A)/(B) 群、誤爆防止(A)/(B) 群、末尾の ask 群は現行の判定と理由 id を保つ。
既存の deny / ask ケースは削除しない。

### 5.3 誤爆コスト（NFR3）

誤爆コストは見逃しコストと同じ桁（`.claude/rules/hook-tests.md`）。一律 `ask` へ倒す実装は
採らない。`ask` は無人実行で `deny` に降格するため、正常系を止めうる変更は allow 側ケースで
先に固定してから入れる。

### 5.4 降格経路の不変（NFR4）

`ask` → `deny` の無人実行降格（`decide()` / `unattended()`）は変更しない。
run-destructive-guard.py 末尾の降格ケースは通り続ける。

### 5.5 変更範囲（NFR5）

変更範囲は `em-workflow/hooks/destructive-guard.py` と
`em-workflow/hooks/tests/destructive-guard-cases.json`、および FR10 の version 2 ファイルに限る。
`failed-run-cleanup-guard.py` / `muse_guard.py` には手を入れない。

### 5.6 テストの独立性（NFR6）

テストは外部依存を持たない。追加ケースは既存の 3 要素 JSON 形式に従い、新しいランナーや依存を
導入しない。

### 5.7 素スペルとの同値性（NFR7）

置換先頭スペルの判定段・理由 id は、FR11 が読み取ったコマンド名をそのまま素で書いたスペルに
同じ残り引数を与えたときの判定と一致する。素スペルが allow のものを置換先頭スペルで deny / ask に
しない（厳しくならない）。コマンド名が読み取れない場合は経路に入らないため、判定は変更前と
同一になる。

## 6. UI/UX要件

該当なし。本フィーチャーは PreToolUse フックの字句解析ロジックであり UI を一切持たない。
design ステップは skipped。

## 7. データ要件

該当なし。永続データを扱わない。

## 8. 外部連携

該当なし。外部依存を持たない（NFR6）。

## 9. 制約条件

### 9.1 技術的制約

- 判定材料はコマンド文字列のみ。ファイルシステム参照・サブプロセス起動・置換の実行を行わない
  （NFR1）。
- 変更範囲は 4 ファイル（NFR5 と FR10）。
- テストは外部依存を持たず、既存の 3 要素 JSON 形式に従う（NFR6）。
- マーカー構造（`UNRESOLVED_MARK` / `QUOTED_MARK` / `SUBSTITUTION_STANDIN` / `Tok` の属性）は
  変更しない。生テキストの読み取りはセグメント本文に対する文字列処理として行い、トークン側には
  情報を持たせない（AS-6）。
- 置換の生テキストとトークン位置の対応付けは、セグメント本文中の置換出現順とマーカー出現順が
  一致することに依拠する。対応付けが確定できない入力では経路に入れない（AS-7）。
- テストコマンドは `python3 em-workflow/hooks/tests/run-destructive-guard.py` と
  `python3 -m unittest discover -s tests` の 2 つ。

### 9.2 ビジネス上の制約

- `.claude/rules/hook-tests.md`: 既存の deny / ask ケースは消さない。
- `.claude/rules/core-plugin-version-bump.md`: プラグインの中身を変更したら同じ変更の中で
  version を 2 箇所同じ値へ上げる。
- base revision には本 feature と無関係な既存のテスト失敗が 6 件ある。既存の赤を解消することは
  変更範囲（NFR5）の外にあり、別タスクとして起票する（AS-10）。

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
| 経路の入口をフラグ形状で推定すると誤 deny と見逃しを同時に生む | 高 | 入口判別子を「置換から静的に読み取れたコマンド名が rm / git であること」に置き換える（AS-2） |
| 経路側で追加の下限を設けると素スペルとの判定がずれる | 高 | 閾値は `check_rm()` 自身（再帰の有無、RM_ROOT_SHAPE、セーフルート例外）に委ねる（AS-3） |
| 置換本文中の任意の語で証拠を取ると `$(git config alias.x) -rf <path>` 形で誤 deny が出る | 高 | 証拠は「本文の最後の語の basename」に限る（AS-4） |
| コマンド名を静的に読み取れない置換先頭形が検知できない | 中 | 経路に入れず allow のままとし、限界をラベルと docstring に対象外宣言として明文化する（AS-5） |
| 生テキストとトークン位置の対応付けが確定できない入力がある | 中 | 「読み取れなかった」として fail-open 側に倒す（AS-7） |
| `ask` は無人実行で `deny` に降格するため、誤爆が正常系を止める | 高 | 一律 `ask` へ倒さず、allow 側ケースで正常系を先に固定する（NFR3） |
| ミラー実装（`failed-run-cleanup-guard.py` / `muse_guard.py`）との差分 | 中 | docstring のミラー注記を新分岐・新関数まで拡張し、コードは変更しない（FR9、AS-9） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` が `deny` になり、理由 id が `rm-recursive` である。バッククォート形も同じ。
- [ ] AC-2: `$(which git) reset --hard HEAD` が `deny` / `git-reset-hard`、`$(which git) clean -fd` が `deny` / `git-clean` である。
- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` が `allow` である。
- [ ] AC-4: `$(which rm) -rf dist` と `$(which rm) -rf /tmp/scratch/x` が `allow` である（既存セーフルート例外の継承）。
- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` が `allow` であり、当該ケースが cases.json から削除されずラベル書き換えの上で残っている。
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` がいずれも `allow` である。
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / バッククォート形 / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` が `deny` のままである。
- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は `allow` であり、そのラベルと `extract_shell_payload()` の docstring が「置換の展開結果がスクリプト本文になる形は対象外」という同一の範囲を述べている。
- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] AC-10: `python3 -m unittest discover -s tests` の失敗テスト ID 集合が base revision のそれと完全に一致し、本変更による新規の失敗が 1 件も無い（base には本 feature と無関係な既存の失敗が 6 件ある。件数の一致だけでは足りず、テスト ID 単位で突き合わせる）。base に既存する失敗は別タスクとして起票し、本 feature の変更範囲 NFR5 の外に置く。
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow version が同一値で、変更前より patch が 1 つ以上進んでいる。
- [ ] AC-12: 変更後のフックが、置換を含まないコマンドに対して変更前と同じ判定・同じ理由文を返す。
- [ ] AC-13: オペランド先行スペル `$(which rm) /home/sakura/valuable -rf` が `deny` / `rm-recursive` になる。`$(which rm) /home/sakura -rf` も `deny` になる。
- [ ] AC-14: 強制フラグなし再帰 `$(which rm) -r /home/sakura/valuable` / `$(which rm) -R /home/sakura/valuable` / `$(which rm) --recursive /home/sakura/valuable` がいずれも `deny` / `rm-recursive` になる。
- [ ] AC-15: 非 rm/git の再帰 + 強制フラグを取るコマンドが `allow` である: `$(which cp) -rf src dst` / `$(which cp) -Rf src dst` / `$(which chmod) -Rf 755 build` / `$(which chown) -Rf user:group /srv/app` / `$(which tar) -rf archive.tar file.txt` / `$(which grep) -rf patterns.txt src` / `$(which rsync) -rf src/ dst/` / `$(which scp) -rf host:/a /b`。
- [ ] AC-16: 置換先頭 + git サブコマンド形の非 git コマンドが `allow` である: `$(which make) clean -fd` / `$(hatch env find) reset --hard`。
- [ ] AC-17: `$(which grep) -r pattern src` が `allow` のままであり、そのラベルが「rm であるという証拠が読み取れないため経路に入らない」という新しい根拠を述べている。
- [ ] AC-18: `-c` 本文にクォート付き置換と破壊的コマンドが混在する 3 形がいずれも `deny` になる: `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` / `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` / `bash -c 'echo "$(pwd)"; git reset --hard HEAD'`。
- [ ] AC-19: クォート付き here-string `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` が `allow` であり、その deny からの反転が受け入れ条件とケーステーブルの双方に記録されている。
- [ ] AC-20: 置換先頭ルーティングが `main()` から名前付きの単一関数へ切り出され、`main()` には呼び出しだけが残り、`_rm_route_candidate()` が削除されている。
- [ ] AC-21: コマンド名を静的に読み取れない置換先頭形（`$(cat cmdfile) -rf /home/sakura/valuable`）が `allow` のままであり、その限界がケースのラベルと docstring に対象外宣言として明文化されている。
- [ ] AC-22: FR11 の読み取りが文字列処理のみで行われ、置換の実行・サブプロセス起動・ファイルシステム参照を伴わない（NFR1）。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 期待判定 | コマンド | 観点 |
|----|----------|----------|------|
| TS-1 | deny | `$(which rm) -rf /home/sakura/valuable` | チケット再現。コマンド名が置換で決まる rm 破壊形状。 |
| TS-2 | deny | `` `which rm` -rf /home/sakura/valuable `` | 両スペル対称性（バッククォート側。実際のケースではバッククォート表記）。 |
| TS-3 | deny | `$(which git) reset --hard HEAD` | git サブコマンド形状での同等形。 |
| TS-4 | deny | `$(which git) clean -fd` | git-clean 形状での同等形。 |
| TS-5 | allow | `$(which node) script.js` | 誤爆防止。rm/git の証拠が無い。 |
| TS-6 | allow | `$(which ls) -la` | 誤爆防止。フラグ先頭だが rm の証拠が無い（ラベル書き換え対象）。 |
| TS-7 | allow | `$(which grep) -r pattern src` | 誤爆防止。再帰フラグを持つが grep には rm の証拠が無い（ラベル書き換え対象、pinned allow）。 |
| TS-8 | allow | `$(which rm) -rf dist` | セーフルート（build artifact）例外の継承。 |
| TS-9 | allow | `$(which rm) -rf /tmp/scratch/x` | スクラッチルート配下の例外の継承。 |
| TS-10 | allow | `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | 既存ケースの期待値反転。第 2 引数は実シェルでは `$0`。 |
| TS-11 | allow | `eval "$(ssh-agent -s)"` | 正常系固定。引用付き置換ペイロードを止めない。 |
| TS-12 | allow | `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` | 対象外であることを明文化した上での allow。 |
| TS-13 | deny | `$(which rm) /home/sakura/valuable -rf` | オペランド先行スペル。dash 事前ゲート撤廃の固定。 |
| TS-14 | deny | `$(which rm) /home/sakura -rf` | home ルート標的でのオペランド先行スペル。 |
| TS-15 | deny | `$(which rm) -r /home/sakura/valuable` | 強制フラグなし再帰。`check_rm()` 自身の閾値に揃える。 |
| TS-16 | deny | `$(which rm) -R /home/sakura/valuable` | 強制フラグなし再帰（大文字スペル）。 |
| TS-17 | deny | `$(which rm) --recursive /home/sakura/valuable` | 強制フラグなし再帰（長スペル）。 |
| TS-18 | allow | `$(which cp) -rf src dst` | 誤爆防止。素の cp 同形が allow なので同値。 |
| TS-19 | allow | `$(which cp) -Rf src dst` | 誤爆防止。大文字スペルでも同じ。 |
| TS-20 | allow | `$(which chmod) -Rf 755 build` | 誤爆防止。chmod は再帰と強制を正当に取る。 |
| TS-21 | allow | `$(which chown) -Rf user:group /srv/app` | 誤爆防止。chown も同型。 |
| TS-22 | allow | `$(which tar) -rf archive.tar file.txt` | 誤爆防止。tar の再帰フラグは追記、強制フラグはファイル指定。 |
| TS-23 | allow | `$(which grep) -rf patterns.txt src` | 誤爆防止。grep の強制フラグはパターンファイル。 |
| TS-24 | allow | `$(which rsync) -rf src/ dst/` | 誤爆防止。 |
| TS-25 | allow | `$(which scp) -rf host:/a /b` | 誤爆防止。 |
| TS-26 | allow | `$(which make) clean -fd` | 誤爆防止。git 経路の無条件呼び出し撤廃の固定。 |
| TS-27 | allow | `$(hatch env find) reset --hard` | 誤爆防止。置換先頭 + git サブコマンド形でも git の証拠が無い。 |
| TS-28 | deny | `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` | `-c` 本文にクォート付き置換と破壊的コマンドが混在する形。 |
| TS-29 | deny | `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` | 同上。混在形（日付置換）。 |
| TS-30 | deny | `bash -c 'echo "$(pwd)"; git reset --hard HEAD'` | 同上。混在本文の git 破壊コマンド。 |
| TS-31 | allow | `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | クォート付き here-string の判定反転を明示的に固定する。 |
| TS-32 | deny | `bash <<<$(true) 'rm -rf /home/sakura/valuable'` | 非クォート here-string の繰り上げ deny は不変（対照）。 |
| TS-33 | allow | `$(cat cmdfile) -rf /home/sakura/valuable` | コマンド名を静的に読み取れない置換先頭形は対象外として allow。限界の明文化を伴う。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `.substitution_only` | コマンド置換のみからなるトークンを表す `Tok` の属性。 |
| コマンド語位置 | `head()` が文のコマンド名として読む位置。 |
| ペイロード引数位置 | `-c` / `eval` / `<<<` でスクリプト本文が来る引数位置。 |
| 繰り上げ | ペイロード位置の置換の次の語をペイロードとして扱う現行挙動。 |
| コマンド名の証拠 | 置換本文の最後の語の basename として静的に読み取れたコマンド名。 |
| 素スペル | 読み取れたコマンド名をそのまま書いた、置換を含まないコマンド表記。 |
| セーフルート例外 | build artifact やスクラッチルート配下を allow とする既存の例外。 |
| 降格 | 無人実行（`claude-batch`）で `ask` が `deny` になる挙動。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 判定段の新設可否: 新設しない。FR1 / FR2 で既存 `check_rm()` / `check_git()` に残りトークンを
  流した結果の段と理由 id をそのまま採用する（AS-1）。
- [x] 経路の入口判別子: 「コマンド語位置の置換から静的に読み取れたコマンド名が rm / git である
  こと」。トークンのフラグ形状による推定は、誤 deny と見逃しを同時に生むため撤廃する（AS-2）。
- [x] rm 経路の閾値: `check_rm()` 自身（再帰の有無、RM_ROOT_SHAPE、セーフルート例外）に委ね、
  経路側で追加の下限を設けない（AS-3）。
- [x] コマンド名の読み取り方法: 置換本文の最後の語の basename。本文中の任意の語との一致は
  採らない（AS-4）。
- [x] 読み取れない形の扱い: 経路に入れず allow のままとする。一律 `ask` へ倒す選択肢は NFR3 に
  より採らない（AS-5）。
- [x] AC-10 の判定基準: 「全件通る」ではなく「失敗テスト ID 集合が base と完全一致し、新規失敗
  ゼロ」。base 既存の 6 件は別タスクとして起票する（AS-10）。
- [x] design ステップ: skipped。本フィーチャーは UI を持たず、`design_system_candidates` も 0 件で
  `kind: none`。design を走らせると UI を持たない本リポジトリに tokens.yaml / tokens.html が
  新規作成される。字句層コントラクトの設計判断と誤爆許容範囲は create-plan の IMPLEMENTATION.md が
  担う。

### 14.2 未確認・保留事項

なし。全機能要件・全非機能要件の status は resolved。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 変更対象のフック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース定義
- `em-workflow/hooks/tests/run-destructive-guard.py`: テストランナー
- `em-workflow/hooks/failed-run-cleanup-guard.py` / `em-workflow/hooks/muse_guard.py`: ミラー先（コード変更なし）
- `.claude/rules/hook-tests.md`: フックのテスト運用ルール
- `.claude/rules/core-plugin-version-bump.md`: version 引き上げルール

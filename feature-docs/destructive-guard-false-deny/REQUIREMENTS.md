---
title: "destructive-guard-false-deny"
created_date: 2026-11-09
status: draft
---

# destructive-guard-false-deny - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow の destructive-guard（`em-workflow/hooks/destructive-guard.py`）に、次の 2 つの現象がある。

- 現象 1: em-workflow のプロトコルが規定するコマンドを、em-workflow 自身の destructive-guard が止める。
- 現象 2: シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で、destructive-guard が deny する。

### 1.2 目的

- em-workflow のプロトコルが規定するコマンドを、em-workflow 自身の destructive-guard が止めない状態にする。
- シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で destructive-guard が deny しない状態にする。
- 単一引用符の中の文字列が後でシェルに実行される経路（bash -c / sh -c / eval / here-string / シェルへのパイプなど）の検知は維持する。
- 上記を `destructive-guard-cases.json` のケースで固定し、既存の deny / ask の検知力を落とさない。

### 1.3 スコープ

対象:

- `em-workflow/hooks/destructive-guard.py` の `statements()` における単一引用符内コマンド置換候補の再走査（FR2、FR3、FR4）
- `em-workflow/hooks/destructive-guard.py` のコード内の説明（FR7）
- `em-workflow/hooks/tests/destructive-guard-cases.json` へのケース追加（FR5）

対象外:

- `destructive-guard.py` の `check_git` にある git-branch-force-delete の判定（変えない。FR1）
- `em-workflow/references/implement-phase.md` の本文（変えない。FR1）
- `implement-phase.md` の Resume guard（Clean re-attempt）と route-back の後片付けが規定する `git worktree remove --force` / `git branch -D`（別タスクとして起票する。A5）
- em-review / plugin-dev（A2）
- em-workflow の `plugin.json` / `marketplace.json` の version（NFR3）

## 2. ビジネス要件

### 2.1 ビジネス目標

- em-workflow のプロトコルが規定するコマンドを、em-workflow 自身の destructive-guard が止めない状態にする。
- シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で destructive-guard が deny しない状態にする。
- 単一引用符の中の文字列が後でシェルに実行される経路（bash -c / sh -c / eval / here-string / シェルへのパイプなど）の検知は維持する。
- 上記を `destructive-guard-cases.json` のケースで固定し、既存の deny / ask の検知力を落とさない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | 現象 1 の方針: フックの強制削除 deny は維持し、プロトコルは非強制削除を使う |
| FR2 | データ引数の中の単一引用符内置換候補だけを再走査しない |
| FR3 | 単一引用符内候補の印付けは維持する |
| FR4 | 実際に実行される位置の置換は従来どおり検知する |
| FR5 | テストケースの追加 |
| FR6 | ケースの追加を修正より先に行う |
| FR7 | コード内の説明の更新 |

### 4.2 機能詳細

#### FR1: 現象 1 の方針: フックの強制削除 deny は維持し、プロトコルは非強制削除を使う

**状態**: resolved

**説明**: `destructive-guard.py` の `check_git` にある git-branch-force-delete の判定（`git branch -D`、および `-d` / `--delete` と `--force` の併用を deny）は変えない。マージ済みタスクブランチの後片付けは、`em-workflow/references/implement-phase.md` Step I.2.b step 4 の形 `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"`（integration worktree からの非強制削除。失敗時に `-D` / `--force` へ切り替えない）とする。この記述は現行の `implement-phase.md` にすでにあるため本文は変えず、フックがこの形を allow することをケースで固定する。

#### FR2: データ引数の中の単一引用符内置換候補だけを再走査しない

**状態**: resolved

**説明**: `statements()` が `scan_structure(..., honor_single_quotes=False)` で拾う単一引用符内（ANSI-C 引用 `$'...'` を含む）のコマンド置換候補のうち、次の条件をすべて満たすものに限り、その本文を pending に積まない（コマンドとして再走査しない）。

- (a) 候補が置かれたチャンクが元のコマンド文字列そのもの（最上位のチャンク）である。置換本文・プロセス置換本文・閉じないコマンド形式の本文・ヒアドキュメント本文・-c / eval / here-string のペイロードとして積まれたチャンクでは従来どおり再走査する。
- (b) そのチャンクの全文が字句解析に成功している（parse-failure fallback を通っていない）。
- (c) そのチャンクのどの文も、代入とラッパーを読み飛ばした後のコマンド語が実行系の語ではない。実行系の語は少なくとも `SINK_WORD_RE` の語彙（sh / bash / zsh / dash / ksh / python / perl / ruby / node）、eval、source、`.`、exec、xargs、find、su、ssh、および env の -S / --split-string を含む。語彙を足すのは deny 側に倒すだけなので実装で追加してよい。
- (d) そのチャンクのどの文もコマンド語を静的に決められる（置換や変数展開がコマンド語の位置に無い）。またコマンド名を上書きする構文（`_overrides_command_name()` が検出するもの）がチャンクに無い。

どれか 1 つでも満たさない、または判断できないときは、従来どおり再走査する。

#### FR3: 単一引用符内候補の印付けは維持する

**状態**: resolved

**説明**: FR2 で変えるのは pending への積み込みだけとする。`top_spans` の算出、`_mark_substitutions()` / `_mark_quoted_substitutions()` による印付け、`all_subs` への追加と目印の添字の対応、トークンの `.unresolved` / `.substitution_only` の付与は変えない。

**例**:

| コマンド | 判定 |
|----------|------|
| `rm -rf '$(pwd)/../tmp/scratch'` | deny のまま |
| `echo 'a $(' ; rm -rf /home/user/x ; f "(" ; echo ')'` | deny のまま |
| `X='foo$(bar'; rm -rf $X` | ask のまま |

#### FR4: 実際に実行される位置の置換は従来どおり検知する

**状態**: resolved

**説明**: 次の置換は従来どおり再走査し、git-branch-force-delete などで deny する。

- 引用符無しのバッククォート / `$( )`
- 二重引用符内のバッククォート / `$( )`
- 引用符無しの区切り語のヒアドキュメント本文内の置換
- 単一引用符の中の置換で、後からシェルに実行されるもの
    - `bash -c` / `sh -c` のペイロード
    - `eval` の引数
    - シェルへの here-string（`bash <<< '...'`）
    - シェルへパイプされる文字列（`printf '%s\n' '...' | bash`）
    - 同じコマンド文字列の中で実行系の語を持つ文があるもの（ファイルに書いてから `bash` で実行する形など）
    - プロセス置換やコマンド置換の本文の中にあるもの（`bash <(printf ...)`、`eval "$(printf ...)"`）

#### FR5: テストケースの追加

**状態**: resolved

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、12 章のテストシナリオ TS-1〜TS-17 をケースとして追加する。

- allow: TS-1、TS-3、TS-4、TS-5、TS-6
- deny: TS-2、TS-7〜TS-17

既存の deny / ask ケースは消さず、期待値も変えない。ケースにホームディレクトリやマシン固有のパスを書かない。integration worktree のパスは既存ケースと同じ `/home/user/.claude/worktrees/em-workflow/some-feature/integration` を使う。

#### FR6: ケースの追加を修正より先に行う

**状態**: resolved

**説明**: `.claude/rules/hook-tests.md` に従い、ケースは `destructive-guard.py` を直す前に追加する。修正前のフックで、deny 側の追加ケース（TS-2、TS-7〜TS-17）がすべて通ること、TS-3・TS-4・TS-6 が deny になる（現象 2 を再現する）ことを確かめてから修正する。

#### FR7: コード内の説明の更新

**状態**: resolved

**説明**: `scan_structure()` の docstring の HONOR_SINGLE_QUOTES の段落、`statements()` の `legacy_spans` 周辺のコメント（単一引用符内候補が pending の再走査対象になると書いている箇所）、`_mark_quoted_substitutions()` と `extract_shell_payload_anchored()` の docstring の単一引用符に触れた記述を、FR2 / FR3 の挙動に合わせて書き換える。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR2（性能）: 1 回の判定は `hooks.json` の timeout（10 秒）とランナーの `GUARD_TIMEOUT_SECONDS`（10 秒）以内に収まる。`statements()` の走査量の上限（`scan_budget`、`MAX_SHELL_PAYLOAD_EXPANSIONS`）は変えない。

### 5.4 保守性要件

- NFR1（既存スイートの全通過）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が追加ケースを含めて全件通る。既存ケースの期待値は変えない。
- NFR3（version を触らない）: em-workflow の `plugin.json` / `marketplace.json` の version は変更しない。
- NFR4（リポジトリ全体のテスト）: `python3 -m unittest discover -s tests` が変更前と同じ結果になる。

## 6. UI/UX要件

UI を持たないフックスクリプトとテストケースの変更のみのため、デザインステップは行わない。

## 9. 制約条件

### 9.1 技術的制約

- git-branch-force-delete の判定は変えない（FR1）。
- `top_spans` の算出、印付け、`all_subs` への追加と目印の添字の対応、トークンの `.unresolved` / `.substitution_only` の付与は変えない（FR3）。
- `scan_budget`、`MAX_SHELL_PAYLOAD_EXPANSIONS` は変えない（NFR2）。
- FR2 の条件を判断できないときは再走査（deny 側）に倒す（FR2、A6）。

### 9.2 ビジネス上の制約

- 既存の deny / ask ケースは消さない（`.claude/rules/hook-tests.md`、A4）。
- ケースは `destructive-guard.py` を直す前に追加する（FR6）。
- em-workflow の version は変更しない（NFR3）。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-false-deny/**`
- `test-docs/destructive-guard-false-deny/**`

`feature-docs/destructive-guard-false-deny/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-false-deny/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-false-deny/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `git -C /home/user/.claude/worktrees/em-workflow/some-feature/integration branch -d "em-workflow/some-feature/task0001"` が allow になる（FR1）。
- [ ] AC-2: `git branch -D em-workflow/some-feature/task0001` が git-branch-force-delete で deny のまま（FR1）。
- [ ] AC-3: `implement-phase.md` Step I.2.b step 4 が非強制削除を規定し、強制削除への切り替えを禁じる記述を保っている（FR1）。
- [ ] AC-4: 単一引用符の JSON 引数の中にバッククォート / `$( )` で `git branch -D example` を書いた mcp-bridge コマンド、および ANSI-C 引用の中に書いたデータ引数が allow になる（FR2）。
- [ ] AC-5: 引用符無し・二重引用符内の置換、bash -c / sh -c / eval / here-string / シェルへのパイプ / 同じコマンド中のシェル実行 / プロセス置換・コマンド置換の本文に置いた単一引用符内の置換の `git branch -D example` が deny のまま（FR4）。
- [ ] AC-6: 既存の deny / ask ケースが 1 件も削除・変更されず、`run-destructive-guard.py` が全件通る（FR3、FR5、NFR1）。
- [ ] AC-7: 修正前のフックで deny 側の追加ケースが通り、TS-3・TS-4・TS-6 が deny になることを確かめた記録がある（FR6）。

## 12. テストシナリオ

### 12.1 テスト観点

各シナリオのコマンドは SPEC.md の Test Scenarios に記載する。

- [ ] 正常系（allow）: TS-1（AC-1）、TS-3〜TS-6（AC-4）
- [ ] 検知の維持（deny）: TS-2（AC-2）、TS-7〜TS-17（AC-5）
- [ ] 回帰: TS-18 既存スイート全件通過（AC-6）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 現象 1 | em-workflow のプロトコルが規定するコマンドを、em-workflow 自身の destructive-guard が止める現象 |
| 現象 2 | シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で destructive-guard が deny する現象 |
| 最上位のチャンク | 元のコマンド文字列そのもの。置換本文・プロセス置換本文・閉じないコマンド形式の本文・ヒアドキュメント本文・-c / eval / here-string のペイロードとして積まれたチャンクは含まない（FR2 (a)） |
| 実行系の語 | FR2 (c) が挙げる語。`SINK_WORD_RE` の語彙（sh / bash / zsh / dash / ksh / python / perl / ruby / node）、eval、source、`.`、exec、xargs、find、su、ssh、および env の -S / --split-string を少なくとも含む |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 現象 1 の方針（phenomenon1-policy）: 案 B。フックの強制削除 deny を維持し、プロトコルは integration worktree からの非強制削除を使う。完了の定義の「再現手順で現象が起きない」は、現象 1 については「プロトコルが規定するコマンドがフックに止められない」ことと解釈する。再現手順 2 の強制削除そのものは deny のまま（A1）。
- [x] プロトコル内の強制削除形の扱い（protocol-force-forms-scope）: 案 X。`implement-phase.md` の Resume guard（Clean re-attempt）と route-back の後片付けが規定する `git worktree remove --force` / `git branch -D` は本機能の対象外とし、別タスクとして起票する（A5）。
- [x] 現象 2 の修正範囲（phenomenon2-fix-scope）: 案 Q。「実行されないデータ引数」は、静的に判断できる範囲に限る保守的な定義（FR2 の条件 (a)〜(d)）とする。判断できないときは再走査（deny 側）に倒す（A6）。

### 14.2 未確認・保留事項（前提）

- [ ] A2: 完了の定義の「両プラグインに同じ判断を反映する」について、本分析の読み取り範囲に em-review / plugin-dev は無く、写しの有無は未確認。写しが無い前提で em-workflow だけを変更対象とする。
- [ ] A3: ANSI-C 引用 `$'...'` の中でもシェルはコマンド置換を行わないため、単一引用符と同じ扱いにする。
- [ ] A4: 既存の deny / ask ケースは消さない（`.claude/rules/hook-tests.md`）。
- [ ] A7: TS-7〜TS-17 が修正前のフックで deny になることはコード読解で確かめた（要件分析のディスパッチではフックを実行できなかった）。FR6 で修正前に実行して確かめる。

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
- `em-workflow/references/implement-phase.md`（Step I.2.b step 4）
- `.claude/rules/hook-tests.md`

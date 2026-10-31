# Feature: unattended-merge

## Overview

develop --batch で完了した feature を、人が張り付かずに base ブランチへ取り込む batch 専用スキル `/em-workflow:merge` を追加する。loop-develop の dispatcher が claude-batch 経由で `/em-workflow:merge --batch <feature>` を起動し、構造化結果だけで成否を判定する。同じ起動を何度繰り返しても、マージ済みなら何もせず成功を返す。

要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- develop --batch で完了した feature を、人が張り付かずに base ブランチへ取り込める状態にする
- loop-develop の dispatcher が claude-batch 経由で `/em-workflow:merge --batch <feature>` を起動し、構造化結果だけで成否を判定できるようにする
- 同じ起動を何度繰り返しても、マージ済みなら何もせず成功を返す（再開可能・冪等）
- スコープ外: Notion など外部タスク管理サービスのステータス更新

## User Stories

### US1: 完了した feature を無人でマージする
loop-develop の dispatcher として、`/em-workflow:merge --batch <feature>` を起動して、完了した feature を人が張り付かずに base ブランチへ取り込みたい。

**Acceptance Criteria:**
- [ ] AC2: workflow.yaml に completed / skipped 以外の step がある feature では、マージせず、その step 名を理由に含む結果を返す
- [ ] AC3: 最新の review ラウンドに deferred の high finding があるとマージせず、その stable_id が結果に含まれる。declined の critical/high だけのときは止まらない
- [ ] AC4: remote が無いリポジトリでは base_branch に `--no-ff` のマージコミットができ、integration worktree は消え、ブランチは残る
- [ ] AC5: base の upstream が無く remote が複数ある場合と、remote が GitHub でない場合は、マージせずに返す
- [ ] AC7: PR が無いと push と `gh pr create` のあと PR ルートで進み、結果に pr_url が入る
- [ ] AC8: 仕様から帰属を判断できないコンフリクトでは、worktree をクリーンに戻してマージせず返す
- [ ] AC9: 未承認のコマンドがあると何も実行せずマージせず返し、承認ストアは変わらない
- [ ] AC10: test_command が失敗すると push せず、失敗したコマンドが結果に含まれる
- [ ] AC11: PR チェックが無い場合は待たずにマージする。チェックが失敗した場合、または 60 分で終わらない場合はマージしない
- [ ] AC12: マージ直前に base が動いていると取り込みからやり直し、4 回目が必要になったらマージせず返す
- [ ] AC13: integration worktree を cwd とする `gh pr merge <番号> --merge --match-head-commit <40桁SHA>` は destructive-guard で allow になる。`--admin` / `--auto` / `--squash` / `--rebase` / `--delete-branch` 付き、SHA 欠落、cwd が別の場所の場合は従来どおり ask になり、`CLAUDE_BATCH` 下では deny になる。後続セグメントの危険な操作は引き続き deny / ask になる
- [ ] AC15: ロックを他の feature が保持している間は、base の取り込みもマージも行わない

### US2: 構造化結果で成否を判定する
loop-develop の dispatcher として、最後の assistant メッセージの構造化結果だけで成否を判定したい。

**Acceptance Criteria:**
- [ ] AC1: `--batch` なしで起動すると使い方だけを表示し、git / gh の状態を一切変えない
- [ ] AC14: すべての終端で、最後の assistant メッセージが新しい契約文書の書式どおりの結果だけになる

### US3: 何度起動しても同じ結論に収束する
loop-develop の dispatcher として、同じ起動を繰り返しても、マージ済みなら何もせず成功を受け取りたい。

**Acceptance Criteria:**
- [ ] AC6: すでにマージ済みの feature に再実行すると、取り込み・push・マージをせず成功を返す

### US4: テストが通る状態を保つ
em-workflow の開発者として、スクリプトと hook のテストがともに通る状態を保ちたい。

**Acceptance Criteria:**
- [ ] AC16: `python3 -m unittest discover -s tests` と `python3 em-workflow/hooks/tests/run-destructive-guard.py` がともに通る

## Technical Requirements

### Functional Requirements
- **FR1:** スキルの配置 — 新スキルを `em-workflow/skills/merge/SKILL.md` に置き、`/em-workflow:merge` として起動できるようにする。`commands/` ディレクトリは使わない。
- **FR2:** 引数と batch 専用 — 引数は feature 名と `--batch` のみとする。`--batch` が無い起動では使い方を表示して何もしない（構造化結果も出さない）。feature 名は `^[a-z0-9][a-z0-9-]*$` に一致しなければ、シェルコマンドへ補間する前に「マージできなかった」を返す。
- **FR3:** 対象の解決 — feature 名から `em-workflow/{feature}/integration` ブランチを解決する。ブランチが無ければマージせず返す。base_branch と project.components は integration ブランチ先端の `feature-docs/{feature}/workflow.yaml` から読む。integration worktree が無い場合（develop の Step C が削除済み）は、develop Step A.2 と同じ `git worktree add` で再作成する。
- **FR4:** 事前条件 — workflow.yaml の全 step が completed または skipped のときだけ進む（verify が failed なら不成立）。満たさなければ、満たしていない step と status を理由に含めて「マージできなかった」を返す。
- **FR5:** 未解決の重大 review finding — 最新の review ラウンド記録 `feature-docs/{feature}/reviews/round{N}.yaml`（N 最大）に、severity が critical/high で resolution が fixed でも declined でもない finding（deferred / unresolved など）が 1 件でもあれば、マージせず返す。理由にはその stable_id をすべて含める。review ラウンド記録が 1 件も無い場合（review step が skipped）は、この判定を行わない。
- **FR6:** ルート判定と remote の選択 — remote が 1 つも無ければローカルルートに進む。remote があれば次の順で使う remote を決める: base_branch の upstream remote（`branch.<base>.remote`）、無ければ remote が 1 つだけのときのその remote。どちらでも決まらなければマージせず返す。gh がその remote の GitHub リポジトリを解決できない場合もマージせず返し、ローカルルートには切り替えない。
- **FR7:** マージ済みなら何もせず成功 — PR ルートでは head が integration ブランチの PR が MERGED なら、ローカルルートでは base_branch が integration ブランチの先端を含んでいれば、取り込み・検証・push・マージを行わずに成功（already merged）を返す。後片付け（FR19）は通常の成功時と同じく行う。
- **FR8:** PR の解決と作成 — head=`em-workflow/{feature}/integration`・base=base_branch の OPEN な PR があればそれを使う。無ければ integration ブランチを push し、`gh pr create` で base_branch への PR を作る（title: feature 名、body: 実行サマリ）。`gh pr create` はプロジェクトルートを cwd とし、`--head` と `--base` を明示する。
- **FR9:** PR の状態確認 — マージに進む前に、PR が OPEN であり、draft でなく、gh が示す mergeable が CONFLICTING でないことを確認する。満たさなければ、その状態を理由にしてマージせず返す。
- **FR10:** リポジトリ単位の排他ロック — base の取り込み（FR11）からマージ完了（FR17/FR18）までを、git common dir 上のロックでリポジトリ単位に直列化する。CI 待ちの間もロックを持ち続ける。ロックは `merge-task.sh` の `em-workflow-merge.lock` とは別のファイルにする。
- **FR11:** base の取り込み — どちらのルートでも、マージの前に integration worktree で base（PR ルートは選んだ remote の base_branch を fetch した先端、ローカルルートはローカルの base_branch）を integration ブランチへマージコミットで取り込む。rebase も force 更新も行わない。
- **FR12:** コンフリクトの解消 — 取り込みでコンフリクトしたら、この feature の `feature-docs/{feature}/` の仕様と、base 側の変更元 feature の仕様（base 側にある `feature-docs/{other}/`）の両方を読み、両方の意図を満たすように解消してコミットする。base 側の変更元 feature を特定できない場合や、対応する仕様書を確認できない場合は解消せず、取り込みを中止して worktree をクリーンに戻してから「マージできなかった」を返す。
- **FR13:** 取り込み後の検証コマンド — 取り込み後、workflow.yaml の project.components の build_command・test_command・e2e_test_command を integration worktree で実行する（空のものは飛ばす）。実行前に `bash_guard.py --list --project-dir` で承認済みかを確かめる。未承認のものがあれば承認を記録せずにマージせず返す。各コマンドは承認文字列をそのまま、単独の cd の後に直接の Bash 呼び出しとして実行する。失敗したら push せず、失敗したコマンドと出力の要点を理由にしてマージせず返す。
- **FR14:** push — PR ルートでは integration ブランチを選んだ remote へ force なしで push する。拒否されたらマージせず返す。
- **FR15:** CI 待ち — push した head の PR チェックを最大 60 分待つ。チェックが 1 件も無ければ待たずに進む。1 件でも失敗したらマージせず返す。60 分以内に終わらなければマージせず返す。待機は、Bash の timeout 上限（600 秒）内に終わるスクリプト呼び出しを最初に決めた期限まで繰り返して行う。コマンド文字列に while / until は書かない。
- **FR16:** base が動いた場合のやり直し — マージ直前に base の先端を取り込み時の値と比べる。動いていれば FR11 の取り込みからやり直す。やり直しは 3 回までで、それでも収まらなければマージせず返す。
- **FR17:** PR のマージ — 単独の cd で integration worktree に移ってから `gh pr merge <PR 番号> --merge --match-head-commit <検証した head の 40 桁 SHA>` を直接の Bash 呼び出しとして実行する。`--admin` / `--auto` / `--squash` / `--rebase` / `--delete-branch` は付けない。
- **FR18:** ローカルルートのマージ — メイン作業ツリーが base_branch を checkout していて、かつクリーンなときだけ、そこで `git merge --no-ff em-workflow/{feature}/integration` を実行する。それ以外はマージせず返す。
- **FR19:** 後片付け — マージ成功または already merged の後、プロジェクトルートへ単独の cd で戻る。そのうえで integration worktree の絶対パスをリテラルで書いた `git worktree remove` を `--force` なしで実行し、worktree だけを削除する。ローカル・リモートのブランチは残す。マージせず返す場合は worktree を残す。
- **FR20:** destructive-guard の限定許可 — `destructive-guard.py` に、決まった形の `gh pr merge` だけを allow する規則を足す。条件は、PR 番号・`--merge`・`--match-head-commit <40 桁 SHA>` がそろっていること、`--admin` / `--auto` / `--squash` / `--rebase` / `--delete-branch` が無いこと、payload の cwd が `.claude/worktrees/em-workflow/<feature>/integration` かその配下であること。例外に当たった後も同じコマンドの後続セグメントの危険な操作は判定し続ける。既存の deny / ask ケースは残し、`destructive-guard-cases.json` に allow と ask のケースを足す。`run-destructive-guard.py` は、ケースごとに cwd を渡せるようにし、cwd と `CLAUDE_BATCH` を組み合わせた判定を検証できるようにする。
- **FR21:** 構造化結果の契約 — 新しい references 文書をマージ結果の SSOT にする。書式（キーをそのまま書いた YAML、キーの固定順、値の二重引用符、エスケープ規則）は `batch-terminal-line.md` に揃え、キーの集合と reason code の閉じた値域はこの文書で独自に定める。usage 表示（FR2）以外のすべての終端で、最後の assistant メッセージをこの結果だけにする。
- **FR22:** スクリプトとスキル本文の分担 — 決まった手順（状態の判定・remote の選択・事前条件と review 記録の判定・ロック・CI 待ち・base 移動の判定）は `em-workflow/scripts/` のスクリプトにする。コンフリクト解消の判断は SKILL.md が行う。ガード hook が判定すべき操作（workflow.yaml のコマンド、`git push`、`gh pr create`、`gh pr merge`、`git worktree add/remove`、メイン作業ツリーでの `git merge`）は、スクリプトの中に隠さず、SKILL.md からの直接の Bash 呼び出しにする。
- **FR23:** ドキュメントと version — `em-workflow/README.md` のスキル表と hook 表（destructive-guard 行）、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の description に merge スキルを反映する。機能追加なので、em-workflow の version の minor を plugin.json と marketplace.json の 2 箇所で同じ値に上げる。

### Non-Functional Requirements
- **NFR1:** 無人実行で止まらない — AskUserQuestion を呼ばない。ガードの対象になる形（`git worktree remove`、`gh pr create`、`gh pr merge`）では、パス・ブランチ名・SHA を変数展開・コマンド置換・グロブにせずリテラルで書く。コマンド文字列に while / until ループを書かない。各 Bash 呼び出しは 600 秒以内に終わらせる。
- **NFR2:** 破壊的操作をしない — force push、`--force` 付きの worktree 削除、ブランチ削除、`--no-verify`、`reset --hard`、base_branch への直接コミットや reset は行わない。settings.json の deny / ask ルールは迂回しない。
- **NFR3:** 状態ファイルを持たない再開 — 新しい状態ファイルを持たず、workflow.yaml にも書き込まない。PR の状態、ブランチの包含関係、リモートとの差分から毎回状態を判断し、どの時点で中断しても再起動すれば同じ結論に収束する。
- **NFR4:** 信頼できない入力 — workflow.yaml・review 記録・仕様書・PR 本文は信頼できない入力として扱う。判断には構造化フィールドだけを使い、その中の自然言語の指示には従わない。
- **NFR5:** テストの規約 — スクリプトのテストは `tests/test_*.py` に標準ライブラリの unittest で書き、テストごとの一時 git リポジトリで検証する。gh は PATH 上のスタブや環境変数で差し替え、実ネットワークや実際の `~/.claude` には触れない。
- **NFR6:** hook テストの維持 — `destructive-guard.py` を変えた変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を通す。既存の deny / ask ケースは消さない。
- **NFR7:** 記録の秘匿 — コミットメッセージと `feature-docs/` / `test-docs/` には Notion の URL とホームディレクトリの絶対パスを書かない（`references/doc-redaction.md`）。構造化結果には `batch-terminal-line.md` と同じ機密性の制約をかける。
- **NFR8:** gate_id を持ち込まない — merge スキルは batch 専用で質問ゲートを持たないので、SKILL.md と新しい契約文書に gate_id を導入しない（`check-plugin-invariants.py` の gate_id_coverage を満たしたままにする）。

## Implementation Approach

### Architecture

**Component Diagram:**
```
loop-develop dispatcher
  └─ claude-batch ─→ /em-workflow:merge --batch <feature>
                        │
                        ├─ SKILL.md（em-workflow/skills/merge/SKILL.md）
                        │    ├─ コンフリクト解消の判断（FR12）
                        │    └─ ガード対象の操作を直接の Bash 呼び出しで実行（FR22）
                        │         workflow.yaml のコマンド / git push / gh pr create /
                        │         gh pr merge / git worktree add・remove /
                        │         メイン作業ツリーでの git merge
                        │
                        ├─ em-workflow/scripts/ のスクリプト（FR22）
                        │    状態の判定 / remote の選択 / 事前条件と review 記録の判定 /
                        │    ロック / CI 待ち / base 移動の判定
                        │
                        └─ 構造化結果（新しい references 文書が SSOT、FR21）

hooks/destructive-guard.py ─ 決まった形の gh pr merge だけを allow（FR20）
```

### Data Flow

```
起動（FR1, FR2）
 → 対象の解決（FR3）
 → 事前条件・review 記録の判定（FR4, FR5）
 → ルート判定と remote の選択（FR6）
 → マージ済み判定（FR7）── already merged ──────────────────────────┐
 → [PR ルート] PR の解決と作成・状態確認（FR8, FR9）                  │
 → ロック取得（FR10）                                                 │
 → base の取り込み・コンフリクト解消（FR11, FR12）←─┐                 │
 → 検証コマンド（FR13）                              │                 │
 → [PR ルート] push・CI 待ち（FR14, FR15）           │                 │
 → base 移動の判定（FR16）── 動いた（3 回まで）─────┘                 │
 → [PR ルート] PR のマージ（FR17） / [ローカルルート] マージ（FR18）  │
 → 後片付け（FR19）←──────────────────────────────────────────────────┘
 → 構造化結果（FR21）
```

各判定で条件を満たさない場合は、マージせず理由を含む構造化結果（FR21）を返し、worktree は残す（FR19）。

### API Design

該当なし（HTTP API は持たない）。外部コマンドの形は次のとおり。

- `gh pr create`: プロジェクトルートを cwd とし、`--head em-workflow/{feature}/integration` と `--base <base_branch>` を明示する。title は feature 名、body は実行サマリ（FR8）。
- `gh pr merge <PR 番号> --merge --match-head-commit <検証した head の 40 桁 SHA>`: 単独の cd で integration worktree に移ってから実行する。`--admin` / `--auto` / `--squash` / `--rebase` / `--delete-branch` は付けない（FR17）。
- `git merge --no-ff em-workflow/{feature}/integration`: メイン作業ツリーで実行する（FR18）。
- `git worktree remove <integration worktree の絶対パス>`: プロジェクトルートで、`--force` なしで実行する（FR19）。

### Database Schema

該当なし。新しい状態ファイルを持たず、workflow.yaml にも書き込まない（NFR3）。

読み取る既存データ:

| データ | 項目 | 用途 |
|--------|------|------|
| `feature-docs/{feature}/workflow.yaml`（integration ブランチ先端） | 各 step の status | 事前条件（FR4） |
| 同上 | base_branch | マージ先（FR3） |
| 同上 | project.components の build_command / test_command / e2e_test_command | 検証コマンド（FR13） |
| `feature-docs/{feature}/reviews/round{N}.yaml`（N 最大） | severity / resolution / stable_id | 未解決の重大 finding（FR5） |

### Dependencies

**Internal Dependencies:**
- `batch-terminal-line.md`: 構造化結果の書式の準拠先（FR21）
- `bash_guard.py --list --project-dir`: 検証コマンドの承認確認（FR13）
- `merge-task.sh`: 既存のロック `em-workflow-merge.lock`。新しいロックはこれと別のファイルにする（FR10）
- develop Step A.2: integration worktree の再作成で同じ `git worktree add` を使う（FR3）
- `em-workflow/hooks/destructive-guard.py`: 限定許可の追加先（FR20）
- `em-workflow/hooks/failed-run-cleanup-guard.py`: `git worktree remove` と `gh pr create` の判定（A29, A31）
- `check-plugin-invariants.py`: gate_id_coverage（NFR8）
- `references/doc-redaction.md`: 記録の秘匿（NFR7）

**External Dependencies:**
- git: ブランチ・worktree・マージ・fetch・push
- gh: PR の解決・作成・状態確認・チェック待ち・マージ

### File Structure

```
em-workflow/
├── skills/merge/SKILL.md              # 新スキル（FR1）
├── scripts/                           # 決まった手順のスクリプト（FR22）
├── references/                        # マージ結果の契約文書（新規、FR21）
├── hooks/destructive-guard.py         # gh pr merge の限定許可（FR20）
├── hooks/tests/destructive-guard-cases.json   # allow / ask ケースの追加（FR20）
├── hooks/tests/run-destructive-guard.py       # ケースごとの cwd 指定（FR20）
├── README.md                          # スキル表と hook 表（FR23）
└── .claude-plugin/plugin.json         # description と version の minor（FR23）
.claude-plugin/marketplace.json        # description と version の minor（FR23）
tests/test_*.py                        # スクリプトのテスト（NFR5）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/unattended-merge/**`
- `test-docs/unattended-merge/**`

`feature-docs/unattended-merge/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/unattended-merge/**` covers `test-docs/unattended-merge/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS2: already merged の判定 — integration の先端を含む base、および MERGED の PR を返す gh スタブで状態判定を実行する - already merged と判定され、更新系の操作が起きない（AC6）
- [ ] TS3: 事前条件の不成立 — verify: failed、implement: pending のそれぞれで事前条件の判定を実行する - 不成立になり、step 名が理由に入る（AC2）
- [ ] TS4: review 記録の判定 — round1 と round2 を置き、round2 に deferred の high / declined の critical / fixed の high を混ぜる - 最新ラウンドの deferred の high の stable_id だけで止まる（AC3）
- [ ] TS5: remote の選択 — upstream あり / upstream なしで remote 1 つ / upstream なしで remote 複数 / GitHub 以外の各ケース - upstream、単一 remote、停止、停止の順になる（AC5）
- [ ] TS6: CI 待ち — gh スタブがチェックなし / 失敗あり / 期限切れまで pending を返す - 進む、停止、停止の順になる（AC11）
- [ ] TS7: base 移動によるやり直し — 判定のたびに base を進めるフィクスチャで base 移動判定を繰り返す - 3 回まではやり直し、超えたら停止する（AC12）
- [ ] TS8: ロックの排他 — 別の feature がロックを保持している状態で取得を試みる - 取得できず、取り込みに進まない（AC15）
- [ ] TS9: destructive-guard の allow ケース — cwd を integration worktree にした規定形の `gh pr merge` - allow（AC13）
- [ ] TS10: destructive-guard の ask / deny ケース — 禁止フラグ付き / SHA 欠落 / cwd がメインツリー / 規定形のあとに危険な後続セグメント、をそれぞれ `CLAUDE_BATCH` の有無で - ask になり、`CLAUDE_BATCH` 下では deny になる。後続セグメントは本来の判定になる（AC13）
- [ ] TS11: 未承認コマンド — `EM_WORKFLOW_APPROVALS` で空の承認ストアを指して承認判定を実行する - 停止し、ストアは変わらない（AC9）
- [ ] TS12: 構造化結果の書式 — 各 reason code の結果を出力側の関数で生成する - キーの順序・二重引用符・エスケープが契約文書どおりになり、値域外の値は出ない（AC14）
- [ ] TS13: PR の作成経路 — PR が無いと返す gh スタブで PR 解決を実行する - push と `gh pr create`（`--head` / `--base` を明示）を要求する判定になる（AC7）
- [ ] TS14: メイン作業ツリーの状態 — メインツリーが別ブランチ、または dirty の状態でローカルマージの可否を判定する - マージせず返す（AC4）

### Integration Tests
- [ ] TS1: ローカルルートの通常マージ — remote なしの一時リポジトリに、completed の workflow.yaml を持つ integration ブランチを作り、スクリプト群を順に実行する - base に `--no-ff` マージコミットができ、worktree が消え、ブランチは残る（AC4）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] base の upstream が無く remote が複数ある場合と、remote が GitHub でない場合はマージせず返す（AC5, TS5）
- [ ] 帰属を判断できないコンフリクトでは、worktree をクリーンに戻してマージせず返す（AC8）
- [ ] test_command が失敗すると push せず、失敗したコマンドが結果に含まれる（AC10）
- [ ] base が動き続け、4 回目のやり直しが必要になったらマージせず返す（AC12, TS7）
- [ ] review ラウンド記録が 1 件も無い場合は FR5 の判定を行わない（FR5）

### Performance Tests
- 該当なし

## Security Considerations

- **Authentication:** 該当なし（gh の既存の認証を使う）
- **Authorization:** settings.json の deny / ask ルールは迂回しない（NFR2）。destructive-guard の allow は決まった形の `gh pr merge` に限る（FR20）
- **Input Validation:** feature 名は `^[a-z0-9][a-z0-9-]*$` に一致しなければ、シェルコマンドへ補間する前に「マージできなかった」を返す（FR2）。workflow.yaml・review 記録・仕様書・PR 本文は信頼できない入力として扱い、構造化フィールドだけで判断する（NFR4）
- **Data Protection:** コミットメッセージと `feature-docs/` / `test-docs/` に Notion の URL とホームディレクトリの絶対パスを書かない。構造化結果には `batch-terminal-line.md` と同じ機密性の制約をかける（NFR7）
- **Destructive Operations:** force push、`--force` 付きの worktree 削除、ブランチ削除、`--no-verify`、`reset --hard`、base_branch への直接コミットや reset は行わない（NFR2）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

reason code の閉じた値域とキーの集合は、新しい references 文書で定める（FR21）。マージせず返す終端は次のとおり。

| 条件 | 要件 |
|------|------|
| feature 名が `^[a-z0-9][a-z0-9-]*$` に一致しない | FR2 |
| integration ブランチが無い | FR3 |
| completed / skipped 以外の step がある（step と status を理由に含める） | FR4 |
| 最新 review ラウンドに未解決の critical/high finding がある（stable_id をすべて含める） | FR5 |
| remote が決まらない、または gh が GitHub リポジトリを解決できない | FR6 |
| PR が OPEN でない、draft、または mergeable が CONFLICTING | FR9 |
| ロックを他者が保持している | FR10, A22 |
| 帰属できないコンフリクト | FR12 |
| 未承認のコマンドがある、または検証コマンドが失敗した | FR13 |
| push が拒否された | FR14 |
| PR チェックが失敗した、または 60 分以内に終わらない | FR15 |
| 3 回やり直しても base の移動が収まらない | FR16 |
| メイン作業ツリーが base_branch を checkout していない、またはクリーンでない | FR18 |

### Error Flow

```
条件不成立 → マージせず返す → worktree を残す（FR19） → 構造化結果（FR21）を最後の assistant メッセージにする
```

## Performance Optimization

### Performance Goals
- 各 Bash 呼び出しは 600 秒以内に終わらせる（NFR1）
- CI 待ちは最大 60 分（FR15）

### Optimization Strategies
- CI 待ちは、600 秒以内に終わるスクリプト呼び出しを最初に決めた期限まで繰り返す（FR15）

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1〜AC16 を満たす

## Assumptions

- A1: スキル名は merge（`/em-workflow:merge`、`skills/merge/SKILL.md`）
- A2: 対象は feature 名だけで指定する
- A3: remote があって PR が無ければ、PR を作って続行する
- A4: 全 step が completed / skipped のときだけマージする
- A5: 帰属できないコンフリクトでは停止する
- A6: 検証は build・test・e2e を実行し、空のものは飛ばす
- A7: 未承認のコマンドがあれば停止し、承認は記録しない
- A8: テストが失敗したら停止し、修正は試みない
- A9: CI は最大 60 分待ち、チェックが無ければ待たずに進む。60 分で終わらなければ停止する
- A10: 後片付けは worktree だけで、ブランチは残す
- A11: ローカルマージはメイン作業ツリーで、base を checkout していてクリーンなときだけ行う
- A12: 結果の形式は専用の契約文書で定め、書式は `batch-terminal-line.md` に揃える
- A13: 再開時の状態は git と PR から導き、状態ファイルは持たない
- A14: batch 専用。`--batch` が無ければ使い方を表示する
- A15: リポジトリ単位の排他ロックをかける
- A16: base が動いたら最大 3 回やり直す
- A17: 決まった手順はスクリプト、コンフリクト解消の判断は SKILL.md で行う
- A18: design step は skip する
- A19: destructive-guard に `gh pr merge` の限定 allow を足す。例外の後も後続セグメントは判定し、既存ケースは残し、runner は cwd と無人フラグの組合せを検証できるようにする
- A20: 最新の review ラウンドに、fixed でも declined でもない critical/high があれば停止する
- A21: remote は base の upstream、無ければ単一の remote を使う。決まらない場合と GitHub でない場合は停止する
- A22: ロックは、run_in_background で起動したロック保持プロセス（git common dir 上のファイルへの flock）が持つ。すべての終端で TaskStop して解放し、セッションが終われば OS が解放する。他者が保持中なら待たずに停止して lock_busy を返し、再試行は dispatcher に任せる
- A23: ローカルルートでも、マージ前に integration worktree で base の取り込み・コンフリクト解消・検証を行い、メインツリーのマージではコンフリクトが起きないようにする
- A24: PR ルートではローカルの base_branch とメイン作業ツリーを更新しない
- A25: PR が CLOSED（未マージ）しか無い場合と draft の場合は、新しい PR を作らずに停止する
- A26: マージせず返す場合、再作成した integration worktree は調査用に残す
- A27: 60 分の CI 期限はこの起動の中で数える。プロセスが落ちて再起動した場合は期限を数え直す
- A28: 取り込みとコンフリクト解消のコミットは通常の git commit で行い、gitleaks の pre-commit hook を通す。merge スキル自身は git-setup ゲートを実行しない
- A29: 事前条件を満たす feature の workflow.yaml には failed step が無い。このためリテラル絶対パスの `git worktree remove`（S1）にも、`gh pr create`（S3）にも failed-run-cleanup-guard は判定を出さない。パスを変数にすると、到達できる他の feature のどれかが failed なら ask になり、無人では deny になる
- A30: integration パス（末尾が integration）への `git worktree remove` は、destructive-guard が allow を出さずに auto mode の分類器へ回す。develop Step C と同じ既存の露出として受け入れる
- A31: `gh pr create` はプロジェクトルートを cwd にすると、destructive-guard の S3 一致が起きずに allow になり、failed-run-cleanup-guard も判定を出さない。このため FR8 で cwd をプロジェクトルートに固定する

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/unattended-merge/REQUIREMENTS.md`
- 構造化結果の書式: `batch-terminal-line.md`
- 記録の秘匿: `references/doc-redaction.md`
- hook テストの規則: `.claude/rules/hook-tests.md`

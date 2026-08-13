---
title: "implement-routeback-gate"
created_date: 2026-08-14
status: draft
---

# implement-routeback-gate - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/implement-phase.md` Step I.2.c の「route back to planning」経路が、現状では実際には到達不能である。失敗タスクを `pending` に戻す指示が手順に含まれていないため、create-plan が再入した瞬間に、planner の唯一の操作（`replace_planning` / `replace_all`）が `references/workflow-patch.md` の権限条件によって拒否される。

加えて、同じ段落のゲート文言「applies only when every existing task is still `pending`」は、判断時点で失敗タスク自身がこの条件を偽にするため自己矛盾している。また、マージ済みタスクが存在する場合の分岐は、implement から rework へ至る定義済みトリガが存在しないにもかかわらず rework 経路を指しており、終端が未定義になっている。同じ段落の委譲先の記述も、実際に優先関係を所有している develop 側の節を指していない。

### 1.2 目的

- Step I.2.c の route-back 経路を実際に到達可能にする。
- 自己矛盾したゲート文言を、route-back 時点で観測可能な条件（マージ済みタスクが存在しないこと）で言い直す。
- マージ済みタスクが存在する場合に、未定義の rework トリガではなく定義済みの終端を与える。
- 同じ段落の委譲先の記述を、実際に優先関係を所有している develop 側の節に訂正する。

### 1.3 スコープ

対象は次の 2 ファイルのみ。

- `em-workflow/references/implement-phase.md`（プロトコル文書の編集）
- `em-workflow/.claude-plugin/plugin.json`（プラグイン version の patch bump）

対象外（変更しない）:

- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/references/rework-task-synthesis.md`
- `em-workflow/references/workflow-patch.md`
- `em-workflow/references/contracts/*`
- `tests/test_develop_skill_rewiring.py`

`tests/test_develop_skill_rewiring.py` 内の広げられたスライス（`cmp-exemption-slice-widened`）は、回答済みの `routeback.adjacent-findings-scope` により明示的にスコープ外であり、いずれの要件でも扱わない。

## 2. ビジネス要件

### 2.1 ビジネス目標

- `em-workflow/references/implement-phase.md` Step I.2.c の「route back to planning」経路を実際に到達可能にする。現状は失敗タスクを `pending` に戻さないため、create-plan が再入した瞬間に planner の唯一の操作（`replace_planning` / `replace_all`）が `references/workflow-patch.md` の権限条件で拒否される。
- 自己矛盾したゲート文言（「applies only when every existing task is still `pending`」）を取り除き、route-back 時点で実際に観測可能な条件、すなわち「マージ済みタスクが存在しないこと」でゲートを言い直す。
- マージ済みタスクが存在する場合に、未定義の rework トリガを指すのではなく定義済みの終端を与える。`implement` を `failed` のまま残し、develop の停止条件 3（「abort phase」と同じ終端）を通じてユーザーへ制御を戻す。
- 同じ段落内の委譲先の名称を訂正し、implement-phase.md が停止条件 3 の優先関係を実際に所有している develop 側の節を引用するようにする。
- 変更を 1 つのプロトコル文書と規定のプラグイン version bump に限定し、所有権のある SSOT（develop SKILL.md、workflow-patch.md、rework-task-synthesis.md）および既存の回帰テストを一切乱さない。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow のオーケストレータ | implement フェーズを実行し、Step I.2.c の失敗時ハンドリングに従って route-back / 終端の判断を行う |
| em-workflow の利用者 | マージ済みタスクがある失敗時に、停止条件 3 を通じて制御を返され、次の判断を行う |

### 2.3 期待される効果

- route-back 選択後の create-plan 再入が、planner の操作の権限条件を満たすようになる。
- ゲート条件が判断時点で評価可能になり、実行者ごとの解釈差がなくなる。
- マージ済みタスクが存在する場合の終端が定義済みのものになる。
- 委譲先の引用が、実際に規則を所有している節を指すようになる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | マージ済みタスクが無い状態での planning への route back | オーケストレータ | 高 |
| UC02 | マージ済みタスクが有る状態での失敗終端 | オーケストレータ | 高 |

### 3.2 ユースケース詳細

#### UC01: マージ済みタスクが無い状態での planning への route back

**アクター**: オーケストレータ

**事前条件**:
- タスク `{T}` が `failed` である
- `merged` 状態のタスクが 1 つも存在しない
- interactive モードで route-back が選択されている

**基本フロー**:
1. 失敗理由を `tasks.{T}.notes` に記録した状態を保つ
2. 同一の順序付き書き込み集合として、`create-plan` を `needs_update`、`implement` ステップを `pending`、`tasks.{T}.status` を `failed` から `pending` に設定する
3. 失敗タスクの worktree とブランチの後始末を、テキスト上で順序が一意に定まる位置で行う
4. 上記 workflow.yaml への書き込みを、integration worktree に対して `commit-docs.sh` でコミットする（third argument の expected tip は、同ファイルの他の呼び出し箇所と同じ書き方で指定する）
5. フェーズを終了し、create-plan が再入する

**代替フロー**:
- batch モードでは route-back-to-planning は自動的には選択されない（I.2.c に続く batch-mode 段落は変更しない）

**事後条件**:
- `tasks.{T}.status` が `pending`、`tasks.{T}.notes` に失敗理由が残っている
- `create-plan` が `needs_update`、`implement` が `pending`
- 上記の書き込みがコミット済みである

#### UC02: マージ済みタスクが有る状態での失敗終端

**アクター**: オーケストレータ

**事前条件**:
- タスク `{T}` が `failed` である
- `merged` 状態のタスクが 1 つ以上存在する

**基本フロー**:
1. 自動再入は適用しないと判定する
2. `create-plan` を `needs_update` に設定しない
3. `implement` を `failed` のままにする
4. 報告し、develop の停止条件 3 を通じてユーザーへ制御を返す（「abort phase」と同じ終端）

**事後条件**:
- `implement` が `failed` のまま
- rework 経路への引き渡しや `append` の指示は行われない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | Route-back が失敗タスクを `pending` に戻す | I.2.c の route-back 手順に失敗タスクのステータスリセットを明記 | 高 |
| FR2 | Route-back の書き戻しを create-plan 再入前にコミット | workflow.yaml 書き込みを `commit-docs.sh` でコミット | 高 |
| FR3 | exit-4 リカバリ列挙に新しい呼び出し箇所を追加 | I.2.c の route-back コミットを列挙に加える | 高 |
| FR4 | ゲートを「マージ済みタスクが存在しない」で再定義 | 自己矛盾した現行文言を置き換える | 高 |
| FR5 | マージ済みタスク分岐は `failed` + 停止条件 3 で終端 | rework 引き渡し指示を削除 | 高 |
| FR6 | 委譲の引用先を優先関係の所有節に訂正 | Step B の停止条件 3 優先関係節を引用 | 高 |
| FR7 | 変更の封じ込め | 編集対象ファイルを限定 | 高 |
| FR8 | batch-mode 段落の維持 | I.2.c に続く batch-mode 段落を無変更で残す | 高 |
| FR9 | プラグイン version の patch bump | 0.1.35 → 0.1.36 | 高 |

### 4.2 機能詳細

#### FR1: Route-back が失敗タスクを `pending` に戻す

**説明**: Step I.2.c の「route back to planning」手順が、失敗タスクの `tasks.{T}.status` を `failed` から `pending` に明示的に戻す。失敗理由は `tasks.{T}.notes` に記録されたまま残る。このリセットは、`create-plan` を `needs_update` に、`implement` ステップを `pending` に設定するのと同一の順序付き書き込み集合の一部として記述される。

**ビジネスルール**:
- 失敗理由の `tasks.{T}.notes` への記録は保持する。
- リセットは他のステータス書き込みと同一の書き込み集合として記述する。

#### FR2: Route-back の書き戻しを create-plan 再入前にコミット

**説明**: route-back に伴う workflow.yaml への書き込み全体（`create-plan` の `needs_update`、`implement` の `pending`、タスクの `pending`、失敗理由の notes）を、フェーズ終了および create-plan 再入の前に、integration worktree に対して `commit-docs.sh` でコミットする。これは「workflow.yaml への書き込みは同じステップ内で `commit-docs.sh` によるコミットを伴う」という同ファイルの既定の規律に一致する。指示は expected-tip の第 3 引数を、同ファイルの他の呼び出し箇所と同じ書き方で示す。

**ビジネスルール**:
- コミットはフェーズ終了 / create-plan 再入より前に順序付けられる。
- 失敗タスクの worktree とブランチの後始末との前後関係が本文で一意に読み取れること。

#### FR3: exit-4 リカバリ列挙に新しい呼び出し箇所を追加

**説明**: Branch & Worktree Model の exit-4 リカバリ箇条は、現状フェーズの `commit-docs.sh` 呼び出し箇所として「Step I.1 のベースラインコミットと Step I.2.b の wake-phase コミット」を列挙している。ここに新しい I.2.c の route-back コミットを加え、bounded recovery の規則がそれにも適用されることを明示する。

#### FR4: ゲートを「マージ済みタスクが存在しない」で再定義

**説明**: 自動再入を支配する条件を「applies only when no task has merged (there is no task with status `merged`)」と言い直す。判断時点で失敗タスク自身が偽にしてしまう現行の文言「applies only when every existing task is still `pending` (i.e. none has merged yet)」は削除する。

#### FR5: マージ済みタスク分岐は `failed` + 停止条件 3 で終端

**説明**: 少なくとも 1 つのタスクがマージ済みの場合、自動再入は適用されない。`create-plan` は `needs_update` に設定せず、`implement` は `failed` のままとし、フェーズは報告のうえ develop の停止条件 3 を通じてユーザーに制御を返す（「abort phase」と同じ終端）。既存の「追加スコープを rework 経路（`append`）に引き渡す」指示は、その `replace_all` 却下の根拠文とともに削除する。implement から rework へ至る定義済みトリガが存在しないためである。

#### FR6: 委譲の引用先を優先関係の所有節に訂正

**説明**: 同じ段落内で、現在「`skills/develop/SKILL.md` Step B's create-plan exemption owns that precedence」と書かれている文を、Step B の停止条件 3 の優先関係節を引用する形に訂正する。当該節の自動再入除外リストは、implement-phase.md が所有する create-plan route-back 遷移を明示的に列挙している。create-plan の `in_progress` exemption（Step B 内の別ブロック）は、以後この優先関係の所有者としては挙げない。implement-phase.md は develop の規則を再掲せず、引用にとどめる。

#### FR7: 変更の封じ込め

**説明**: プロトコルの編集はすべて `em-workflow/references/implement-phase.md` に限定する。`em-workflow/skills/develop/SKILL.md`、`em-workflow/references/rework-task-synthesis.md`、`em-workflow/references/workflow-patch.md`、`em-workflow/references/contracts/*`、`tests/test_develop_skill_rewiring.py` は変更しない。

#### FR8: batch-mode 段落の維持

**説明**: I.2.c に続く batch-mode 段落は変更しない。batch モードでは route-back-to-planning は依然として自動的には選択されないため、新しいリセットとコミットの手順は interactive の route-back 選択に限定され、新たな batch の挙動を生まない。

#### FR9: プラグイン version の patch bump

**説明**: 同じ変更の中で `em-workflow/.claude-plugin/plugin.json` の `version` を 0.1.35 から 0.1.36 に patch bump する。ルートの `.claude-plugin/marketplace.json` のエントリは `version` フィールドを持たないため、変更しない。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし（ドキュメントのみの変更）。

### 5.2 セキュリティ要件

該当なし。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

#### NFR1: 既存テスト契約の維持

見出しリテラル `### I.2.c: Failed handling` はバイト単位で同一のまま保つ（`tests/test_review_implement_develop_lock_contracts.py` のセクション切り出しアンカーであるため）。また implement-phase.md のいずれの行も、`git ` で始まりつつ `commit` または `add -A` を含んではならない。したがって新しいコミット指示は必ず `commit-docs.sh` を経由し、生の git 行にはしない。当該見出しの手前のスライスに対する wake-phase のアサーションも引き続き成立する。

#### NFR2: SSOT の非重複

implement-phase.md は所有者文書を再掲せず引用する。`replace_all` の権限条件については `references/workflow-patch.md` を、停止条件 3 の優先関係については `skills/develop/SKILL.md` Step B を引用する。他所が所有する規則を I.2.c にコピーしない。

#### NFR3: ドキュメントのみの変更

実行される挙動は変更しない。スクリプト、フック、エージェント、スキルプロンプトは編集しない。成果物はプロトコルの markdown と version bump のみ。

#### NFR4: ローカルなスタイル整合

編集した文章は周辺のファイルに合わせる。implement-phase.md では英語の記述とし、既存の箇条書き構造とバッククォートの慣習を保ち、要件が述べる以上の理由付けを追加しない。

### 5.5 互換性要件

該当なし。

## 6. UI/UX要件

該当なし。design ステップはスキップされている（理由: プロトコルの markdown とバージョン番号の変更のみであり、UI サーフェス・レンダリング出力・design-system 候補のいずれも存在しない）。

## 7. データ要件

該当なし（新規のデータモデルは導入しない）。route-back 時に書き換わる workflow.yaml のフィールドは `create-plan` のステータス、`implement` ステップのステータス、`tasks.{T}.status`、`tasks.{T}.notes` である。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 編集対象は `em-workflow/references/implement-phase.md` と `em-workflow/.claude-plugin/plugin.json` に限定される（FR7 / FR9）。
- 見出し `### I.2.c: Failed handling` はバイト同一に保つ（NFR1）。
- implement-phase.md に、`git ` で始まり `commit` または `add -A` を含む行を作らない（NFR1）。
- 他所が所有する規則を I.2.c に再掲しない（NFR2）。
- 実行される挙動は変更しない（NFR3）。

### 9.2 ビジネス上の制約

- I.2.c に続く batch-mode 段落は変更前のテキストとバイト同一に保つ（FR8）。

### 9.3 スケジュール制約

該当なし。

## 10. 想定される課題とリスク

確定要件に該当項目なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: I.2.c の route-back 箇条が、失敗タスクのステータスを `pending` に戻すこと、および失敗理由が `tasks.{T}.notes` に残ることを述べている（FR1）
- [ ] AC-2: route-back 手順が workflow.yaml 書き戻しの `commit-docs.sh` コミットで終わり、その順序がフェーズ終了 / create-plan 再入より前であり、失敗タスクの worktree・ブランチ後始末との前後関係が本文で一意である（FR2）
- [ ] AC-3: exit-4 リカバリ箇条の呼び出し箇所列挙が、Step I.1 と Step I.2.b のコミットに加えて I.2.c の route-back コミットを挙げている（FR3）
- [ ] AC-4: ゲート文が `merged` タスクの不在として条件を表現しており、文字列 "every existing task is still `pending`" が I.2.c に現れない（FR4）
- [ ] AC-5: マージ済みタスク分岐が、`implement` は `failed` のままで develop の停止条件 3 を通じてユーザーへ制御が戻ることを述べ、rework 経路への引き渡しや `append` の指示を含まない（FR5）
- [ ] AC-6: 委譲文が develop SKILL.md Step B の停止条件 3 優先関係節を挙げ、その優先関係を create-plan `in_progress` exemption に帰属させていない（FR6）
- [ ] AC-7: 変更の変更ファイル一覧（`--name-only` の差分）が、`em-workflow/references/implement-phase.md`、`em-workflow/.claude-plugin/plugin.json`、feature-docs 成果物、本機能のために追加・拡張したテストファイルのみである（FR7 / FR9）
- [ ] AC-8: I.2.c に続く batch-mode 段落が変更前のテキストとバイト同一である（FR8）
- [ ] AC-9: `python3 -m unittest discover -s tests` が通り、`tests/test_review_implement_develop_lock_contracts.py` と `tests/test_develop_skill_rewiring.py` が無変更のまま含まれる（FR7 / NFR1）
- [ ] AC-10: `em-workflow/.claude-plugin/plugin.json` が `"version": "0.1.36"` である（FR9）

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1（正常系 / unittest: document contract）: implement-phase.md の `### I.2.c: Failed handling` セクションを解析し、route-back 箇条に失敗タスクの `pending` リセットと notes 保持の節が含まれることを検証する（AC-1）
- [ ] TS-2（正常系 / unittest: document contract）: I.2.c セクションに `commit-docs.sh` の呼び出しが含まれ、その位置がステータス書き込みの指示より後、フェーズ終了報告の文より前であることを検証する（AC-2）
- [ ] TS-3（正常系 / unittest: document contract）: exit-4 リカバリ箇条の呼び出し箇所一覧が、I.1 と I.2.b に加えて I.2.c に言及することを検証する（AC-3）
- [ ] TS-4（境界値 / unittest: document contract）: I.2.c のゲート文が「no merged task」を表現し、旧文言 "every existing task is still `pending`" がセクションに存在しないことを検証する（AC-4）
- [ ] TS-5（異常系 / unittest: document contract）: マージ済みタスク分岐が `failed` の維持と develop の停止条件 3 に言及し、その分岐のテキストに "rework" も "`append`" も現れないことを検証する（AC-5）
- [ ] TS-6（正常系 / unittest: document contract）: 委譲文が Step B の停止条件 3 優先関係節を引用し、"create-plan exemption owns that precedence" と読めないことを検証する（AC-6）
- [ ] TS-7（回帰 / unittest: existing regression）: 既存の `tests/test_review_implement_develop_lock_contracts.py` を無変更で実行し、I.2.c 見出しアンカーが解決すること、implement-phase.md に生の git commit / git add -A 行が 0 件であることを確認する（AC-9）
- [ ] TS-8（回帰 / unittest: existing regression）: `tests/test_develop_skill_rewiring.py` を無変更で実行し、develop SKILL.md とその carve-out アサーションが乱されていないことを確認する（AC-7 / AC-9）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| route back to planning | implement フェーズの失敗ハンドリングから create-plan へ制御を戻し、再スコープさせる経路 |
| 停止条件 3 | develop SKILL.md Step B が定める停止条件のひとつ。「abort phase」と同じ終端としてユーザーに制御を返す |
| exit-4 リカバリ | Branch & Worktree Model が定める、`commit-docs.sh` の exit code 4 に対する bounded recovery 規則 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] `arch-implementphase-delegation` の訂正対象: develop SKILL.md を読んで確認済み。implement-phase.md の route-back 遷移を名指しする自動再入除外は Step B の「停止条件 3 との優先関係」ブロックにあり、現行 implement-phase.md の文が名指ししている create-plan `in_progress` exemption とは別ブロックである。
- [x] `routeback.adjacent-findings-scope`: `cmp-exemption-slice-widened`（`tests/test_develop_skill_rewiring.py` の広げられたスライス）は明示的にスコープ外であり、いずれの要件でも扱わない。
- [x] version bump の対象: 0.1.35 → 0.1.36（patch）。ルートの `.claude-plugin/marketplace.json` はエントリが `version` フィールドを持たないため編集不要。

### 14.2 未確認・保留事項

なし（`status: tbd` の要件はない）。

### 14.3 前提事項

- AS-1: 本要件セットは、記録された phase-state の回答と integration worktree 内の対象テキストから再構成されている。
- AS-2: `arch-implementphase-delegation` の訂正対象は develop SKILL.md を読んで検証済みである。implement-phase.md の route-back 遷移を名指しする自動再入除外は Step B の「停止条件 3 との優先関係」ブロックにあり、現行 implement-phase.md の文が名指ししている create-plan `in_progress` exemption とは別ブロックである。
- AS-3: implement-phase.md は英語で書かれている一方、develop 側の節の見出しは日本語であるため、訂正後の引用が日本語の見出しリテラルを引用してもよい。これは規則違反ではなく許容されるスタイルとして扱う。
- AS-4: version bump の対象は 0.1.35 から 0.1.36（patch）であり、ルートの `.claude-plugin/marketplace.json` はエントリが `version` フィールドを持たないため編集不要である。
- AS-5: 新しいアサーションは `tests/` 配下の Python `unittest` テストとして追加し、`python3 -m unittest discover -s tests` で実行する。本プロジェクトは build / format / e2e のコマンドを定義していない。
- AS-6: `cmp-exemption-slice-widened`（`tests/test_develop_skill_rewiring.py` の広げられたスライス）は、回答済みの `routeback.adjacent-findings-scope` により明示的にスコープ外であり、いずれの要件でも表現されない。
- AS-7: この worktree はオープン中の PR #3 のブランチ `em-workflow/create-plan-status-conflict/integration` から分岐しているため、対象テキストは PR #3 適用後の文言である。変更はその文言に対して表現される。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: 変更対象のプロトコル文書（Step I.2.c、Branch & Worktree Model）
- `em-workflow/skills/develop/SKILL.md`: Step B の停止条件 3 優先関係節（引用先、変更しない）
- `em-workflow/references/workflow-patch.md`: `replace_all` の権限条件（引用先、変更しない）
- `em-workflow/.claude-plugin/plugin.json`: version bump 対象
- `tests/test_review_implement_develop_lock_contracts.py`: I.2.c 見出しアンカーおよび git 行の回帰テスト
- `tests/test_develop_skill_rewiring.py`: develop SKILL.md の回帰テスト（変更しない）

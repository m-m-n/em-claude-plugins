---
title: "implement-guard-compatible-git-ops"
created_date: 2026-09-25
status: draft
---

# implement-guard-compatible-git-ops - 要件定義書

## 1. 概要

### 1.1 背景
destructive-guard が有効な環境で、em-workflow の implement フェーズが規定する git 操作が拒否されることがある。

### 1.2 目的
- destructive-guard が有効な環境で、implement フェーズが規定する git 操作のうち範囲内のもの（全 refresh 箇所と I.2.b step 4）が拒否されずに完走する。
- hook と両立させる方針をプロトコル側の修正に決め、hook の検知力は削らない。
- プロトコル本文と hook の判定がずれたことを、テストで検出できるようにする。

### 1.3 スコープ
対象:
- `em-workflow/references/implement-phase.md` の I.2.b step 4 のブランチ削除（FR1、FR2）
- 全 refresh 箇所の `reset --hard` の書き方の明記（FR3）
- workflow artifact の書き込みとヒアドキュメントの規定（FR4）
- `em-workflow/hooks/tests/destructive-guard-cases.json` へのケース追加（FR5）
- 文書抽出テストの新規追加（FR6）
- 延期した箇所の記録（FR7）
- version の更新（FR8）

対象外:
- I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup（`git worktree remove --force` と未マージブランチへの `git branch -D`）。後続タスクに回す（FR7）。
- `em-workflow/hooks/destructive-guard.py` と `/home/sakura/.claude/hooks/destructive-guard.py` の判定ロジック（NFR1）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- destructive-guard が有効な環境で、em-workflow の implement フェーズが規定する git 操作のうち範囲内のもの（全 refresh 箇所と I.2.b step 4）が拒否されずに完走する。
- hook と両立させる方針をプロトコル側の修正に決め、hook の検知力は削らない。
- プロトコル本文と hook の判定がずれたことを、テストで検出できるようにする。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | destructive-guard が有効な環境で em-workflow の implement フェーズを実行する |

### 2.3 期待される効果
- 範囲内の git 操作（全 refresh 箇所と I.2.b step 4）が destructive-guard に拒否されずに完走する。
- プロトコル本文と hook の判定のずれがテストで検出される。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | implement フェーズの範囲内の git 操作を完走する | em-workflow のオーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: implement フェーズの範囲内の git 操作を完走する

**アクター**: em-workflow のオーケストレーター

**事前条件**:
- destructive-guard が有効である。
- I.2.b step 4 の時点で、タスクブランチがマージ済みであることを `merge-base --is-ancestor` で確認済みである。

**基本フロー**:
1. refresh として `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration` を実行する。
2. I.2.b step 4 で `git worktree remove "$WT_ROOT/{T}"` を実行する。
3. 続けて `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` を実行する。

**代替フロー**:
- 3 の `branch -d` が失敗した場合、`-D` などの強制削除には切り替えない。ブランチは残し、wake phase の報告に対象のブランチ名を書く。

**事後条件**:
- 1〜3 のコマンドが destructive-guard に拒否されずに実行されている。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | マージ済み task ブランチを -d で削除する | I.2.b step 4 のブランチ削除を integration worktree 内の `git branch -d` に書き換える | confirmed |
| FR2 | -d が拒否されたときも強制削除しない | `branch -d` の失敗時はブランチを残し、報告する | confirmed |
| FR3 | refresh のリテラル形を維持し、対象の書き方を明記する | 全 refresh 箇所のリテラル形を維持し、対象の書き方を 1 回だけ明記する | confirmed |
| FR4 | ドキュメントの書き込みとヒアドキュメント | artifact を Write ツールで書き、`commit-docs.sh` の Bash 呼び出しにヒアドキュメントを含めない | confirmed |
| FR5 | hook ケース表にプロトコル形状を追加する | allow ケース 3 件と deny の対照ケースを追加する | confirmed |
| FR6 | 文書抽出テスト | プロトコル文書から git コマンドを抽出して hook に通すテストを追加する | confirmed |
| FR7 | 延期した箇所を記録する | 範囲外の既知の未対応を SPEC に記録し、後続タスクに起票する | confirmed |
| FR8 | version を上げる | em-workflow の version を 0.2.8 から 0.2.9 に上げる | confirmed |

### 4.2 機能詳細

#### FR1: マージ済み task ブランチを -d で削除する

**説明**: `em-workflow/references/implement-phase.md` I.2.b step 4 のブランチ削除を `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` に書き換える。

**ビジネスルール**:
- 直前の `git worktree remove "$WT_ROOT/{T}"` はそのまま残す。
- 順序は worktree 削除が先のまま変えない。
- `-D` を使う理由を述べた既存コメントは削除する。
- 代わりに -d で通る理由をコメントに書く。理由は次のとおり。integration worktree の HEAD は integration ブランチであり、そのブランチはマージ済みであることを `merge-base --is-ancestor` で確認済みのタスクブランチを含む。

#### FR2: -d が拒否されたときも強制削除しない

**説明**: I.2.b step 4 の `branch -d` が失敗した場合の扱いを規定する。

**ビジネスルール**:
- `-D` などの強制削除には切り替えない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `branch -d` の失敗 | I.2.b step 4 の `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` が失敗した | ブランチは残し、wake phase の報告に対象のブランチ名を書く |

#### FR3: refresh のリテラル形を維持し、対象の書き方を明記する

**説明**: 全 refresh 箇所の `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration` はリテラル形のまま変えない。

対象の refresh 箇所:
- implement-phase.md の Branch & Worktree Model / I.1 / I.2.a step 2 / I.2.b step 2 / I.2.c
- phase-state.md の Phase-state と Artifact-commit の exit-4 recovery
- skills/develop/SKILL.md の Step A と exit-4 リカバリ
- references/phases/create-spec-phase.md の stale handling

**ビジネスルール**:
- implement-phase.md の Branch & Worktree Model の refresh の項に、次を 1 回だけ明記する。reset の対象はリテラルのブランチ名 `em-workflow/{feature}/integration` で書く。シェル変数・キャプチャした SHA・HEAD・`refs/heads/` 接頭辞・対象の省略は使わない。

#### FR4: ドキュメントの書き込みとヒアドキュメント

**説明**: implement-phase.md の Branch & Worktree Model で workflow artifact の書き込みを定めている項（"Every workflow artifact ..."）に規定を加える。

**ビジネスルール**:
- artifact は Write ツールで書く。
- Bash のヒアドキュメントで書かない。
- `commit-docs.sh` を実行する Bash 呼び出しにヒアドキュメントを含めない。

#### FR5: hook ケース表にプロトコル形状を追加する

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に `[期待する判定, ラベル, コマンド]` の形でケースを追加する。

**ビジネスルール**:
- allow ケースは次の 3 つ。
    - `git -C /home/sakura/.claude/worktrees/em-workflow/some-feature/integration reset --hard em-workflow/some-feature/integration`
    - `git -C /home/sakura/.claude/worktrees/em-workflow/some-feature/integration branch -d em-workflow/some-feature/task0001`
    - `git worktree remove /home/sakura/.claude/worktrees/em-workflow/some-feature/task0001`
- 対照として、リテラル以外の対象が deny のままであることを示すケースを追加する（例: `refs/heads/` 付き、`"$BRANCH"`）。
- 既存ケースは削除も変更もしない。

#### FR6: 文書抽出テスト

**説明**: tests/ に unittest を新規に追加する。

**処理**:
1. 範囲内の各箇所（FR3 の全 refresh 箇所と、I.2.b step 4 の `git worktree remove` / `git branch -d`）から git コマンドのリテラルを抽出する。
2. プレースホルダ（`{integration_worktree}`、`$WT_ROOT`、`{feature}`、`{T}`）を具体値に展開する。
3. 展開したコマンドを `em-workflow/hooks/destructive-guard.py` に subprocess で渡す。
4. 判定が deny でも ask でもないことを確かめる。

**ビジネスルール**:
- 延期した箇所（I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup）は、テスト内の明示的な除外リストに箇所名つきで載せる。
- 範囲内の各箇所からコマンドが少なくとも 1 件抽出されることも確かめる。

#### FR7: 延期した箇所を記録する

**説明**: I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup は、`git worktree remove --force` と未マージブランチへの `git branch -D` を使う。

**ビジネスルール**:
- これらを今回の範囲外の既知の未対応として SPEC に記録する。
- 後続タスクに起票する。
- 完了扱いにはしない。

#### FR8: version を上げる

**説明**: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version を上げる。

**ビジネスルール**:
- 両方を同じ値のパッチ版（0.2.8 → 0.2.9）にする。
- 中身の変更と同じ変更に含める。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- NFR1: `em-workflow/hooks/destructive-guard.py` と `/home/sakura/.claude/hooks/destructive-guard.py` の判定ロジックは変更しない。変更はリポジトリ内に限る。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: `destructive-guard-cases.json` の既存ケースは削除も期待値の変更もしない。`tests/test_destructive_guard_command_substitution.py` の `TestCaseTableDiscipline` が引き続き通ること。
- NFR3: テストは Python 標準ライブラリの unittest だけを使う。実際の `~/.claude` の状態には触れない。`CLAUDE_BATCH` を外して hook を起動する。
- NFR4: FR3 で足す文と FR1 で書き換えるコメントに、既存テストが否定アンカーにしている綴りを含めない。対象は `reset --hard "$LAUNCH_TIP"`、`reset --hard "$COMPLETION_TIP"`、`reset --hard "${var}"` の各形。step ごとのセクション内に新たな `reset --hard` を足さない。`tests/test_tip_capture_idiom_uniformity.py` と `tests/test_exit4_tip_argument_consistency.py` が固定している出現位置と順序を崩さないため。
- NFR5: I.2.c セクション内の `git branch -D` の出現回数（1 回）と `git worktree remove --force` の文言は変えない（`tests/test_routeback_reset_scope_consistency.py`、`tests/test_implement_routeback_gate.py`、`tests/test_recycled_task_id_consistency.py`）。

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- hook の判定ロジックは変更しない（NFR1）。
- テストは Python 標準ライブラリの unittest だけを使う（NFR3）。
- 既存テストが固定している綴り・出現位置・出現回数を崩さない（NFR2、NFR4、NFR5）。

### 9.2 ビジネス上の制約
- 変更はリポジトリ内に限る。`~/.claude/hooks/destructive-guard.py` には触れない（NFR1）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/implement-guard-compatible-git-ops/**`
- `test-docs/implement-guard-compatible-git-ops/**`

`feature-docs/implement-guard-compatible-git-ops/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/implement-guard-compatible-git-ops/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/implement-guard-compatible-git-ops/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/implement-guard-compatible-git-ops/` ディレクトリを生成しないが、宣言された `test-docs/implement-guard-compatible-git-ops/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| PR #19 の run で refresh が拒否された原因は、入力からは特定できない（A3） | 中 | FR3 の明記と FR5/FR6 のテストで、対象を別の書き方にしたことによる再発を防ぐ |
| I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup は今回の範囲外（A-C2） | 中 | SPEC に既知の未対応として記録し、後続タスクに起票する（FR7） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: implement-phase.md の I.2.b step 4 に `git branch -D` が無い。`git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` があり、それが `git worktree remove "$WT_ROOT/{T}"` より後に置かれている。
- [ ] AC-2: I.2.b step 4 に、-d が拒否されたときは強制削除せずにブランチを残して報告する、という規定がある。
- [ ] AC-3: 範囲内の全 refresh 箇所の文言が `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`（または同じ形の `"$WT_ROOT/integration"`）のまま残っている。Branch & Worktree Model に、対象をリテラルのブランチ名で書く規定がある。
- [ ] AC-4: Branch & Worktree Model の artifact 書き込みの項に、Write ツールで書くこと、`commit-docs.sh` と同じ Bash 呼び出しにヒアドキュメントを含めないこと、の規定がある。
- [ ] AC-5: `destructive-guard-cases.json` に FR5 の allow ケースと deny の対照ケースがあり、`python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する。
- [ ] AC-6: 新しい文書抽出テストが、範囲内の各箇所から 1 件以上のコマンドを抽出し、そのどれもが deny/ask にならないことを確かめる。延期した 2 箇所は明示的な除外リストに載っている。
- [ ] AC-7: `python3 -m unittest discover -s tests` が全件 pass する。
- [ ] AC-8: plugin.json と marketplace.json の em-workflow の version が、同じ新しい値になっている。
- [ ] AC-9: 延期した箇所（I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup）が SPEC に範囲外の既知の未対応として記録されている。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系 TS-1: `git -C <integration wt> reset --hard em-workflow/some-feature/integration` → destructive-guard が allow。
- [ ] 異常系 TS-2: `git -C <integration wt> reset --hard refs/heads/em-workflow/some-feature/integration` と、対象が `"$BRANCH"` の形 → deny（対照）。
- [ ] 正常系 TS-3: `git -C <integration wt> branch -d em-workflow/some-feature/task0001` → allow。
- [ ] 正常系 TS-4: `git worktree remove <root>/.claude/worktrees/em-workflow/some-feature/task0001`（--force なし）→ allow。
- [ ] 異常系 TS-5: 既存ケース `git reset --hard HEAD~1` → deny のまま。
- [ ] 正常系 TS-6: 文書抽出テストで、implement-phase.md / phase-state.md / SKILL.md / create-spec-phase.md の refresh コマンドと I.2.b step 4 のコマンドを展開し、どれも deny/ask にならない。
- [ ] 境界値 TS-7: 文書抽出テストで、範囲内の各箇所の抽出件数が 0 のとき fail する。
- [ ] 境界値 TS-8: 除外リストの各箇所は抽出対象から外れ、テストの失敗理由にならない。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| refresh | `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration` による integration worktree の更新 |
| 範囲内の箇所 | FR3 の全 refresh 箇所と、I.2.b step 4 の `git worktree remove` / `git branch -d` |
| 延期した箇所 | I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup |
| 文書抽出テスト | プロトコル文書から git コマンドのリテラルを抽出し、destructive-guard に通す unittest（FR6） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A-C1 方針: プロトコル側の修正（protocol_side）。I.2.b step 4 を integration worktree 内の `git branch -d` に書き換え、hook の検知力は削らない。
- [x] A-C2 未マージの片付けの扱い: I.2.a の resume guard と I.2.c の route-back の `worktree remove --force` / `branch -D` は範囲外とし、後続タスクに回す。完了扱いにはしない。
- [x] A-C3 refresh の形: `reset --hard em-workflow/{feature}/integration` のリテラル形を維持し、対象はリテラルのブランチ名で書くと明記する。
- [x] A-C4 ヒアドキュメントの誤爆: hook を直さず、プロトコルの規定で避ける（Write ツールで書き、`commit-docs.sh` と同じ Bash 呼び出しにヒアドキュメントを混ぜない）。worker の推奨（fix_hook_repo）とは違う選択。
- [x] A-C5 再発の検出: ケース表への追加と、範囲を限定した文書抽出テスト（除外リストつき）の両方で行う。
- [x] A-C6 変更範囲: リポジトリ内に限る。`~/.claude/hooks/destructive-guard.py` には触れない。今回の方針では hook のロジックを変えないため、利用者側のコピーに要る手作業は無い。
- [x] A4: I.2.b step 4 で -d が拒否されたときも強制削除に切り替えない（FR2）。強制削除の拒否を維持するという A-C1 の方針に従う。

### 14.2 未確認・保留事項
- [ ] A1: `git worktree add -b` で作った task ブランチには upstream が無い。そのため integration worktree 内の `git branch -d` は、その worktree の HEAD（integration ブランチ。merge-task.sh が update-ref で進めた ref）に対してマージ済みかを判定し、index が古いままでも通る。
- [ ] A2: failed-run-cleanup-guard.py は、integration 形状でない対象（task ブランチ）への `git branch -d` を判定しない。hook 本体は入力に含まれていなかった。
- [ ] A3: PR #19 の run で refresh が拒否された原因は、入力からは特定できない。現在の両方の hook のコピーはプロトコルのリテラルを allow する。対象を別の書き方にしたか、当時の hook のコピーが古かった可能性がある。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`
- phase-state.md
- skills/develop/SKILL.md
- references/phases/create-spec-phase.md
- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`

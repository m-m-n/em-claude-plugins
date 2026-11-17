---
title: "final-path-plan-binding"
created_date: 2026-11-18
status: draft
---

# final-path-plan-binding - 要件定義書

## 1. 概要

### 1.1 背景

final-path の訂正エントリでは、validator が canonical text と照合する plan ドキュメントと、implementer が指示として受け取るドキュメントが一致していない。そのため、canonical text を囮の plan に置き、未登録の `tasks/{T}.md` に別の指示を置く攻撃シナリオが成立する。また、TM-11（フィーチャー final-path-correction-medium-fixes）の canonical text の要件が、implementer の実際の指示入力に届いていない。

### 1.2 目的

- final-path の訂正エントリにおいて、validator が canonical text と照合する plan ドキュメントを、implementer が指示として受け取るドキュメントと同一にし、上記の攻撃シナリオを成立させない。
- TM-11（フィーチャー final-path-correction-medium-fixes）の canonical text の要件を、implementer の実際の指示入力に届かせる。

### 1.3 スコープ

- 暫定対策: 訂正エントリで、未束縛の `tasks/{T}.md` が存在する場合に拒否する（FR1、FR4）。
- 根本対策: implementer の plan パスを `tasks.{T}.plan` から解決し、解決したパスを fail-closed で検査する（FR2、FR3、FR6）。
- 回帰テストの追加（FR5）。
- 対象ファイル:
    - `em-workflow/scripts/validate-worker-output.py`
    - `em-workflow/references/implement-phase.md`
    - `em-workflow/references/phases/create-plan-phase.md`
    - `em-workflow/references/workflow-patch.md`
    - `em-workflow/references/batch-terminal-line.md`
    - `tests/test_final_path_correction.py`
    - `tests/test_final_path_correction_docs.py`
- UI は持たない（デザインステップはスキップ）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- final-path の訂正エントリにおいて、validator が canonical text と照合する plan ドキュメントと、implementer が指示として受け取るドキュメントを同一にし、攻撃シナリオ（囮の plan に canonical text、未登録の `tasks/{T}.md` に別の指示）を成立させない。
- TM-11（フィーチャー final-path-correction-medium-fixes）の canonical text の要件を implementer の実際の指示入力に届かせる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | em-workflow で final-path の訂正を含むフィーチャー開発を回す Claude Code 利用者 |

### 2.3 期待される効果

- 囮の plan と未登録の `tasks/{T}.md` を組み合わせた攻撃シナリオが、訂正エントリの検証で拒否される。
- implementer が受け取る plan が `tasks.{T}.plan` に登録されたドキュメントと一致する。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 訂正エントリの検証 | validator（`validate-worker-output.py`） | 高 |
| UC02 | implementer の起動プロンプトの構築 | implement フェーズのオーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: 訂正エントリの検証

**アクター**: validator（`validate-worker-output.py` の `_correction_entries_errors`）

**事前条件**:
- 訂正エントリとして `tasks_patch.entries` を含む workflow patch が提出されている。

**基本フロー**:
1. validator が `tasks_patch.entries` の各項目について、フィーチャーディレクトリの作業ツリーに `tasks/{T}.md` のディレクトリエントリが存在するかを調べる。
2. 存在し、かつ項目の plan が `path_segments` 正規化後に `tasks/{T}.md` と一致しない場合、`path-correction-entries` で拒否する。
3. それ以外の場合、既存の検証を続ける。

**代替フロー**:
- `tasks/{T}.md` の状態が読めない、または判定できない場合は、存在するものとして扱う。
- Re-planning の経路と他の状態では、この検査は走らない。

**事後条件**:
- 拒否された項目のエラーには task_id とパス `tasks/{T}.md` が含まれる。

#### UC02: implementer の起動プロンプトの構築

**アクター**: implement フェーズのオーケストレーター（`implement-phase.md`）

**事前条件**:
- implement 対象のタスクが選択されている。

**基本フロー**:
1. 選択されたすべてのタスクの `tasks.{T}.plan` の値を検査する（FR3）。
2. すべて通過した場合、`task_plan_path` を integration worktree の `feature-docs/{feature}/{tasks.{T}.plan}` の絶対パスとして解決する。
3. implementer の起動プロンプトを構築する。

**代替フロー**:
- いずれかのタスクが検査に失敗した場合、フェーズを中止する（FR3 の中止処理）。

**事後条件**:
- implementer に渡る plan パスが `tasks.{T}.plan` の登録内容と一致する。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 訂正エントリにおける未束縛の `tasks/{T}.md` の拒否 | `tasks/{T}.md` が存在し、plan がそれと一致しない訂正エントリを `path-correction-entries` で拒否する | 高 |
| FR2 | implementer の plan パスを `tasks.{T}.plan` から解決 | `task_plan_path` を固定の `tasks/{T}.md` ではなく `tasks.{T}.plan` から解決する | 高 |
| FR3 | 解決した plan パスの fail-closed 検査 | implementer 起動プロンプトの構築前に、選択された全タスクの plan パスを検査し、失敗時は中止する | 高 |
| FR4 | 新しい拒否の契約文書への記載 | `workflow-patch.md` の path-correction-entries の項に FR1 の拒否を記載する | 高 |
| FR5 | 回帰テスト | 攻撃シナリオの再現テストと docs テストを追加する | 高 |
| FR6 | plan パス検査の停止に対する batch 停止の束縛 | `batch-terminal-line.md` の名指しの例外を FR3 の停止にも適用する | 高 |

### 4.2 機能詳細

#### FR1: 訂正エントリにおける未束縛の `tasks/{T}.md` の拒否

**説明**: `em-workflow/scripts/validate-worker-output.py` の `_correction_entries_errors` は、`tasks_patch.entries` の項目について、フィーチャーディレクトリ配下に `tasks/{T}.md` のディレクトリエントリが現在存在し、かつ項目の plan が `path_segments` 正規化後に `tasks/{T}.md` と一致しない場合、`path-correction-entries` で拒否する。

**ビジネスルール**:
- エラーには task_id とパス `tasks/{T}.md` を含める。
- 存在の判定では、エントリの種類を問わない（通常ファイル、ディレクトリ、ダングリングを含むシンボリックリンク）。
- 他の path-correction-entries の制限と同じく、訂正エントリでのみ適用する。Re-planning の経路と他の状態は変更しない。
- この制約は、`tasks/{T}.md` が別の plan と共存する訂正エントリにのみ適用する。それ以外の場所で、すべての plan に固定の `tasks/{T}.md` の名前を要求するものではない。

**バリデーション**:

| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| `tasks_patch.entries[].plan` | `tasks/{T}.md` が存在する場合、`path_segments` 正規化後に `tasks/{T}.md` と一致すること | `path-correction-entries`（task_id と `tasks/{T}.md` を含む） |

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| `path-correction-entries` | 訂正エントリで `tasks/{T}.md` が存在し、plan が一致しない | 項目を拒否する |
| `path-correction-entries` | `tasks/{T}.md` の状態が読めない、または判定できない | 存在するものとして扱い、plan が一致しなければ拒否する |

#### FR2: implementer の plan パスを `tasks.{T}.plan` から解決

**説明**: `em-workflow/references/implement-phase.md` のプロンプトペイロード（現在 518 行目）は、`task_plan_path` を固定の `feature-docs/{feature}/tasks/{T}.md` ではなく、integration worktree の `feature-docs/{feature}/{tasks.{T}.plan}` の絶対パスとして解決する。

**ビジネスルール**:
- `em-workflow/references/phases/create-plan-phase.md` の 2a 節（103-107 行目）と一致させる。minimal tier の `TASK.md` の plan も含む。
- 保存される `tasks.{T}.plan` の値は `feature-docs/{feature}` からの相対パスである（例: minimal tier では `TASK.md`、それ以外では `tasks/task0001.md`）。
- `create-plan-phase.md` の 2a 節の記述を、保存される値と解決後の絶対パスを分けて述べる形に明確化する。

#### FR3: 解決した plan パスの fail-closed 検査

**説明**: implementer の起動プロンプトを 1 つでも構築する前に、`implement-phase.md` は選択されたすべてのタスク（最初のタスクだけではない）の `tasks.{T}.plan` の値を検査する。

**バリデーション**:

| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| `tasks.{T}.plan` | 安全な相対パスであること（絶対パスでない、`..` セグメントを含まない、区切り文字・空セグメント・`.` の扱いは validator の safe-relative-path 検査と同じ） | 該当タスク ID を報告して中止 |
| `tasks.{T}.plan` | パスのどの構成要素（中間要素を含む）もシンボリックリンクでないこと | 該当タスク ID を報告して中止 |
| `tasks.{T}.plan` | realpath が `feature-docs/{feature}` の内側に留まること | 該当タスク ID を報告して中止 |
| 保存値と解決後の絶対パス | Unicode カテゴリ Cc の文字、U+2028、U+2029 を含まないこと | 該当タスク ID を報告して中止 |

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| plan パス検査の失敗 | 選択されたいずれかのタスクが検査に失敗 | 既存の worktree_path の制御文字検査と同じ終端処理で中止する |

中止時の処理:
- 失敗したタスク ID を報告する。
- 選択されたどのタスクについても implementer の起動プロンプトを構築しない。
- implementer を起動しない。
- implement を failed（failed_kind: decision）として 1 コミットで書く。
- 値のサニタイズはせず、`tasks/{T}.md` へのフォールバックもしない。
- 以前の refill で起動済みのタスクは、待たず、キャンセルせず、ロールバックもしない。

#### FR4: 新しい拒否の契約文書への記載

**説明**: `em-workflow/references/workflow-patch.md` の「Limits on entries」の path-correction-entries の項に、FR1 の拒否を記載する。

**ビジネスルール**:
- `tests/test_final_path_correction_docs.py` の既存の `LIMITS_NEEDLES` の文字列はすべて残す。
- limits の段落に番号付きの項目を追加しない。

#### FR5: 回帰テスト

**説明**: `tests/test_final_path_correction.py` に攻撃シナリオの再現テストを追加し、docs テストを追加する。

**ビジネスルール**:
- `canonical_correction_plan` の出力を持つ plan `tasks/{T}-safe.md` の新規エントリと、別のテキストを持つ `tasks/{T}.md` が存在する場合、`validate_workflow_patch(dry_run=True)` と `validate_worker_result` の両方で `path-correction-entries` になる。
- plan が `tasks/{T}.md` で canonical text を持ち、他のファイルが無い場合は引き続き通過する。
- `tasks/{T}.md` が存在する状態での `TASK.md` の plan は拒否される。
- docs テストで、`implement-phase.md` が `task_plan_path` を `tasks.{T}.plan` から解決し、固定の `tasks/{T}.md` のペイロード行を含まないことを固定する。

#### FR6: plan パス検査の停止に対する batch 停止の束縛

**説明**: `em-workflow/references/batch-terminal-line.md` の、Step I.2.a の制御文字検査による停止を stop-condition-3 の行と `step_needs_intervention` に束縛する名指しの例外を、FR3 の plan パス検査による停止にも適用する。

**ビジネスルール**:
- batch 実行は FR3 の停止を `unmapped_stop` ではなく `step_needs_intervention` として報告する。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

- 認証: 該当なし
- 認可: 該当なし
- データ保護: 該当なし
- 入力検証:
    - NFR1: `_correction_entries_errors` は git を `_read_base_document` 経由でのみ読む。新しい検査は `feature_dir` の作業ツリーに対する lstat / lexists を使い、`_run_git`、`subprocess`、`ls-tree`、`cat-file` のいずれも含まない（`TestEntryLimits.test_entry_files_reach_git_only_through_the_base_readers` で固定）。
    - NFR2: fail-closed。`tasks/{T}.md` の状態が読めない、または判定できない場合は存在するものとして扱う。疑わしい読み取り結果でエントリを通過させない。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

- ログ出力: 該当なし
- 監視: 該当なし
- ドキュメント: FR4、FR6 の契約文書の更新
- テスト:
    - NFR3: テストは Python 標準ライブラリ（unittest）のみを使う（`test/README.md` に従う）。
    - NFR5: `tests/test_final_path_correction.py` と `tests/test_final_path_correction_docs.py` の既存テストは変更なしで通り続ける。

### 5.5 互換性要件

- NFR4: プラグインの version フィールドは変更しない（`.claude/rules/core-plugin-version-bump.md`）。patch レベルの修正とする。

## 6. UI/UX要件

該当なし（UI を持たない）。

## 7. データ要件

### 7.1 データモデル概要

該当なし。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| workflow.yaml の tasks | `tasks.{T}.plan` | string | ○ | `feature-docs/{feature}` からの相対パス（例: `TASK.md`、`tasks/task0001.md`） |

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

該当なし。

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- FR1 の検査は訂正エントリでのみ適用する。Re-planning の経路と他の状態は変更しない。
- `_correction_entries_errors` は git を `_read_base_document` 経由でのみ読む（NFR1）。
- テストは Python 標準ライブラリ（unittest）のみを使う（NFR3）。
- 既存の `LIMITS_NEEDLES` の文字列はすべて残し、limits の段落に番号付きの項目を追加しない（FR4）。

### 9.2 ビジネス上の制約

- プラグインの version フィールドは変更しない（NFR4）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

該当なし。

### 10.2 ビジネスリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: plan `tasks/task0003-safe.md`（canonical text）と未登録の `tasks/task0003.md` が存在する状態で、訂正エントリの patch が、`validate_workflow_patch(dry_run=True)` と `validate_worker_result` の両方で、task0003 と `tasks/task0003.md` を挙げた `path-correction-entries` になる。（FR1）
- [ ] AC-2: plan `tasks/{T}.md` で canonical text を持ち、他のファイルが無いエントリはエラーにならない。自由な plan パスで `tasks/{T}.md` が存在しないエントリは新たなエラーにならない。（FR1）
- [ ] AC-3: `tasks/{T}.md` が存在する状態で plan が `TASK.md` のパスであるエントリは `path-correction-entries` で拒否される。`tasks/{T}.md` がディレクトリの場合、ダングリングのシンボリックリンクの場合も同じく拒否される。（FR1、NFR2）
- [ ] AC-4: `implement-phase.md` のプロンプトペイロードが `task_plan_path` を `tasks.{T}.plan` から与え、固定の `tasks/{T}.md` のペイロードの記述が無くなっている。（FR2）
- [ ] AC-5: `implement-phase.md` が、implementer の起動プロンプトを構築する前に、FR3 のパス検査（安全な相対パス、シンボリックリンクの構成要素なし、realpath の包含、保存値と解決後の値に対する Cc / U+2028 / U+2029、選択された全タスク）とその中止処理を記載している。（FR3）
- [ ] AC-6: `workflow-patch.md` の path-correction-entries の項が FR1 の拒否を記載し、既存の docs テストが通る。（FR4、NFR5）
- [ ] AC-7: `python3 -m unittest discover -s tests` が通る。（FR5、NFR1、NFR3、NFR5）
- [ ] AC-8: `batch-terminal-line.md` が FR3 の停止を stop-condition-3 の行と `step_needs_intervention` に束縛している。（FR6）

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: TS-2 束縛された plan（plan `tasks/{T}.md` で canonical text）はエラーにならない。
- [ ] 正常系: TS-3 自由な plan パスで `tasks/{T}.md` が存在しない場合は新たなエラーにならない（既存の TestCreatedDocuments / TestEntryLimits の挙動を維持）。
- [ ] 正常系: TS-5 正規化すると `tasks/{T}.md` になる plan パスの表記（例: `./tasks/{T}.md`）は束縛されたものとして扱う。
- [ ] 異常系: TS-4 `tasks/{T}.md` がディレクトリ、ダングリングのシンボリックリンク、`TASK.md` の plan と共存する場合は拒否される。
- [ ] 境界値: TS-6 Re-planning の経路と他の状態では新しい検査は走らない。
- [ ] セキュリティ: TS-1 攻撃の再現（canonical な囮の plan と未登録の `tasks/{T}.md`）が `path-correction-entries` になる（validator と worker-result の両経路）。
- [ ] セキュリティ: TS-8 コード読みのテストで、`_correction_entries_errors` が引き続き base readers 経由でのみ git に到達することを確かめる。
- [ ] ドキュメント: TS-7 docs テストで、`implement-phase.md` が `task_plan_path` を `tasks.{T}.plan` から解決し、FR3 の中止を記載していることを確かめる。
- [ ] ドキュメント: TS-9 docs テストで、`batch-terminal-line.md` が FR3 の停止を `step_needs_intervention` に束縛していることを確かめる。
- [ ] パフォーマンス: 該当なし。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 訂正エントリ | final-path の訂正で `tasks_patch.entries` を提出する経路 |
| canonical text | `canonical_correction_plan` が出力する訂正 plan の本文 |
| `tasks.{T}.plan` | workflow.yaml に保存されたタスク {T} の plan パス。`feature-docs/{feature}` からの相対パス |
| `task_plan_path` | implementer のプロンプトペイロードで渡す plan の絶対パス |

## 14. 確認事項

### 14.1 確認済み事項

requirements-analyst が置いた前提:

- [x] A1: 暫定対策（FR1）と根本対策（FR2、FR3）の両方をこのフィーチャーのスコープに含める。
- [x] A2: `tasks.{T}.plan` の値は `feature-docs/{feature}` からの相対パスである（例: `tasks/task0001.md`）。validator は `_read_current_document(feature_dir, plan)` で読み、テストのフィクスチャもその形で登録している。
- [x] A3: FR1 の存在検査は、base commit ではなくフィーチャーディレクトリの現在の作業ツリーを使う。
- [x] A4: path-correction-entries の挙動と TM-9 のコード読みの制約を固定している既存テストは、維持すべき不変条件である。
- [x] A5: FR3 の中止は、既存の worktree_path の制御文字検査の終端処理を再利用する（implement ステップを failed、failed_kind: decision、`commit-docs.sh` による 1 コミット）。
- [x] A6: Codex への相談（batch）の結果、スコープは暫定対策と根本対策の両方、`tasks.{T}.plan` はフィーチャーディレクトリからの相対パス、FR3 は制御文字検査の終端処理を再利用する。いずれも A1、A2、A5 と一致した。
- [x] A7: FR3 のパス検査は validator の既存の plan ドキュメント検査（どの構成要素のシンボリックリンクも拒否、realpath の包含）に倣い、文字検査は保存値と解決後の値の両方について Cc 全体と U+2028 / U+2029 を対象にする。
- [x] A8: `batch-terminal-line.md` は名指しの例外を制御文字検査のみに限定しているため、FR3 の停止に対する batch の停止理由の束縛を明示的に記載する（FR6）。

### 14.2 未確認・保留事項

なし。

## 15. 参考資料

- `em-workflow/references/workflow-patch.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/phases/create-plan-phase.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/scripts/validate-worker-output.py`

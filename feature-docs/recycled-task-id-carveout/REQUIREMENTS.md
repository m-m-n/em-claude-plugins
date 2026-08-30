---
title: "recycled-task-id-carveout"
created_date: 2026-08-18
status: draft
---

# recycled-task-id-carveout - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/implement-phase.md` の I.2.a（recycled-task-id 段落、現在の 226-236 行）に自己矛盾がある。「governs only the orchestrator's interpretation of the journal」というリテラルの直後に、`queue_stop_guard.py` を対象とする例外宣言が続いており、前文の「orchestrator のみ」という限定を後続節が打ち消している。

同時に、この設計上の不変条件を実際に固定しているはずのテスト `tests/test_recycled_task_id_consistency.py::TestRecycledTaskIdRuleScopedToOrchestrator` は、4 つのフック名が I.2.a セクション内のどこかに出現することしか検査していない。post-stopguard-retired-failed の文言は `queue_stop_guard.py` を例外として名指しすることでこの検査を満たしてしまうため、テストは意味が反転したままグリーンで通り続けている。

さらに carve-out は 3 箇所（I.2.a の本文、Supporting cast の Stop-hook 箇条書き、`queue_stop_guard.py` の実装）で独立に述べられており、相互に機械的な結び付きがない。

### 1.2 目的

- I.2.a の自己矛盾を除去する。
- 4 つのキューフックのうち 3 つ（`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`）が journal の最終イベントのみからタスク状態を導出し `tasks.{T}.status` を参照しない、`queue_stop_guard.py` のみが明示的な唯一の carve-out である、という設計不変条件に実効的なピンを取り戻す。
- テストが意味を反転させたままグリーンで通るギャップを閉じる。
- 3 箇所に散った carve-out の記述を、SSOT を文書化したうえでテストにより実装と機械的に接続した形に整理する。

### 1.3 スコープ

**対象**:

- `em-workflow/references/implement-phase.md` の I.2.a 段落および Supporting cast の Stop-hook 箇条書きの文言改訂
- `tests/test_recycled_task_id_consistency.py` の改訂、および必要に応じた新規テストモジュールの追加
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version bump

**対象外**:

- 4 つのフックいずれの実行時挙動の変更（`queue_stop_guard.py` の分類ロジックは byte 単位で不変）
- unlaunched 定義の乖離をフック側の変更で閉じること（文書化にとどめる）

## 2. ビジネス要件

### 2.1 ビジネス目標

- `em-workflow/references/implement-phase.md` I.2.a の自己矛盾（「governs only the orchestrator's interpretation of the journal」というリテラルの直後に `queue_stop_guard.py` の例外宣言が続く構造）を除去する。
- 4 つのキューフックのうち 3 つ（`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`）が journal の最終イベントのみからタスク状態を導出し `tasks.{T}.status` を決して参照しないこと、`queue_stop_guard.py` が唯一の明示的な carve-out であることという設計不変条件に、実効的に強制されるピンを取り戻す。
- `TestRecycledTaskIdRuleScopedToOrchestrator` が意味を反転させたままグリーンで通るギャップを閉じる。現状のアサーションは各フックのファイル名が I.2.a セクション内のどこかに出現することしか検査しておらず、post-stopguard-retired-failed の文言は `queue_stop_guard.py` を例外として名指しすることでこれを満たしてしまう。
- carve-out の三重記述（I.2.a の本文、Supporting cast の Stop-hook 箇条書き、`queue_stop_guard.py` の実装）を、相互に結び付いていない 3 箇所から、テストによって実装と機械的に接続された文書化済み SSOT へと縮約する。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| implement フェーズのオーケストレータ | I.2.a を recycled-task-id ルールの SSOT として参照する |
| em-workflow のメンテナ | 文書とフック実装の対応を改訂・検証する |

### 2.3 期待される効果

- I.2.a を読んだだけで recycled-task-id ルールの適用範囲が一意に決まる。
- 文書の文言が設計不変条件から乖離した場合にテストが赤くなる。
- carve-out の記述が SSOT 1 箇所に集約され、他の記述はそれを引用する形になる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | recycled-task-id ルールの適用範囲を I.2.a から判断する | implement フェーズのオーケストレータ | 高 |
| UC02 | 文書とフック実装の対応をテストで検証する | em-workflow のメンテナ | 高 |

### 3.2 ユースケース詳細

#### UC01: recycled-task-id ルールの適用範囲を I.2.a から判断する

**アクター**: implement フェーズのオーケストレータ

**事前条件**:

- `em-workflow/references/implement-phase.md` の I.2.a が改訂済みである。

**基本フロー**:

1. I.2.a の recycled-task-id 段落を読む。
2. ルールが orchestrator の journal 解釈と `queue_stop_guard.py` に適用されることを読み取る。
3. 他の 3 フックが journal の最終イベントのみから状態を導出することを読み取る。

**代替フロー**:

- unlaunched 定義の乖離に関する記述を読み、これが意図された乖離であることを読み取る。

**事後条件**:

- 適用範囲について矛盾のない単一の解釈が得られる。

#### UC02: 文書とフック実装の対応をテストで検証する

**アクター**: em-workflow のメンテナ

**事前条件**:

- リポジトリルートで `python3 -m unittest discover -s tests` が実行可能である。

**基本フロー**:

1. 静的スキャンにより 3 つの journal-only フックがタスク単位の workflow.yaml status 読み取りを行わないことを検証する。
2. `queue_stop_guard.py` をサブプロセスとして起動し、carve-out の挙動を検証する。
3. I.2.a と Supporting cast 箇条書きの文言アサーションを検証する。

**代替フロー**:

- 文言または実装が主張に反する場合、対応するアサーションが失敗する。

**事後条件**:

- スイート全体がグリーンである。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | I.2.a のスコープ文の内部整合化 | 矛盾したスコープ文を単一の非矛盾ルールに書き換える | 高 |
| FR2 | Supporting cast の Stop-hook 箇条書きを carve-out にスコープ限定 | 等価主張の範囲を carve-out 自体に限定する | 高 |
| FR3 | TestRecycledTaskIdRuleScopedToOrchestrator の 2 主張への分割 | ファイル名出現の連言を 2 つの分離した主張に置き換える | 高 |
| FR4 | 文書化された分類と実装を結ぶ二層ピン | 静的スキャンと挙動テストの両層を構築する | 高 |
| FR5 | 新規マッチャの非空虚性規律 | 各マッチャに定数共有・負証明・アンカー保証を課す | 高 |
| FR6 | unlaunched 定義の乖離を閉じずに文書化 | フックを変更せず I.2.a に意図的な乖離として明記する | 高 |
| FR7 | プラグインの version bump | plugin.json と marketplace.json を同一の新値に揃える | 高 |
| FR8 | スイート全体のグリーン | 既存モジュール・既存マッチャを含めて全件通過する | 高 |

### 4.2 機能詳細

#### FR1: I.2.a のスコープ文の内部整合化

**説明**: `em-workflow/references/implement-phase.md` の I.2.a recycled-task-id 段落（現在の 226-236 行）の末尾スコープ文を、単一の非矛盾なルールを述べる形に書き換える。すなわち、recycled-task-id ルールは orchestrator の journal 解釈**および** `queue_stop_guard.py` に適用され、他の 3 フック（`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`）は journal の最終イベントのみからタスク状態を導出し `tasks.{T}.status` を決して参照しない。リテラル「governs only the orchestrator's interpretation of the journal」は、後続節が矛盾させている当の対象であるため削除する。workflow.yaml 読み取りに関するより弱い真の主張は保持する。すなわち本文書のどこにも `never read workflow.yaml` および `never reads workflow.yaml` は出現してはならない。

**入力**:

- `em-workflow/references/implement-phase.md`: Markdown 文書 - 現行の I.2.a 段落

**出力**:

- `em-workflow/references/implement-phase.md`: Markdown 文書 - 改訂された I.2.a 段落

**ビジネスルール**:

- I.2.a が recycled-task-id ルールの唯一の規範的記述であり続ける。
- 削除対象のリテラルは「governs only the orchestrator's interpretation of the journal」である。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| スコープ矛盾の残存 | 改訂後も限定と例外が同一文で並ぶ | TS-1 のアサーションが失敗する |
| 過剰な主張の混入 | `never read workflow.yaml` / `never reads workflow.yaml` が出現する | 既存の回帰ガードが失敗する |

#### FR2: Supporting cast の Stop-hook 箇条書きを carve-out にスコープ限定

**説明**: `implement-phase.md` の「Supporting cast: journal, hooks, resume」配下にある Stop-hook 箇条書き（現在の 517-527 行）を改訂後の I.2.a と整合させる。その等価主張（`applying the same recycled-task-id carve-out as I.2.a above`）の範囲は carve-out 自体、すなわち failed-plus-pending の再分類に限定され、`queue_stop_guard.py` が I.2.a の unlaunched 定義のその他すべての側面を再現するとは主張しない。I.2.a が SSOT であり続け、当該箇条書きは引用する側の消費者であり続ける。両者が独立にドリフトしうる形でルールを再掲してはならない。

**入力**:

- `em-workflow/references/implement-phase.md`: Markdown 文書 - 現行の Stop-hook 箇条書き

**出力**:

- `em-workflow/references/implement-phase.md`: Markdown 文書 - 改訂された Stop-hook 箇条書き

**ビジネスルール**:

- 等価主張のスコープは carve-out（failed-plus-pending の再分類）に限定する。
- I.2.b step 1 の I.2.a 引用は変更しない。

#### FR3: TestRecycledTaskIdRuleScopedToOrchestrator の 2 主張への分割

**説明**: `tests/test_recycled_task_id_consistency.py::TestRecycledTaskIdRuleScopedToOrchestrator` を改訂し、4 フックすべてに対するファイル名出現の連言 1 つではなく、I.2.a セクションに対する 2 つの分離した主張を検証する形にする。(a) 3 つの journal-only フックが journal の最終イベントのみから状態を導出し `tasks.{T}.status` を決して参照しないものとして名指しされていること。(b) `queue_stop_guard.py` が carve-out を適用する明示的かつ唯一の例外として名指しされていること。4 つのファイル名がセクション内のどこかに出現するだけで満たされるテストはもはや許容しない。モジュール定数 `ORCHESTRATOR_ONLY_SCOPE_PHRASE` と対になる負証明（`test_orchestrator_only_scope_matcher_flags_absence_in_pre_change_wording`）は、正のマッチャと一体で更新または廃止する。モジュール docstring の AC-6 記述は新しい契約を述べるよう訂正する。

**入力**:

- `tests/test_recycled_task_id_consistency.py`: Python テストモジュール - 現行の当該クラスと定数

**出力**:

- `tests/test_recycled_task_id_consistency.py`: Python テストモジュール - 分割された 2 主張と更新された定数・docstring

**ビジネスルール**:

- 生き残るアサーションのうち、フックのファイル名がセクション内のどこかに出現するだけで満たされるものがあってはならない。
- 定数の改訂後、読み手が 1 つしかないモジュール定数を残してはならない。

#### FR4: 文書化された分類と実装を結ぶ二層ピン

**説明**: 文書と実装の対応を**両方の層**でピンする。

- Layer 1: `em-workflow/hooks/queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py` に対する静的ソーススキャン。いずれもタスク単位の workflow.yaml status 読み取りを行わないという否定的主張を証明する。スキャンは status 読み取りそのもの、すなわちそうした読み取りを構成する識別子（例: `queue_stop_guard.py` の `task_statuses_from_workflow` ヘルパおよびその `TASK_STATUS_RE` / `TASKS_SECTION_RE` 行スキャン正規表現）にマッチさせ、裸の部分文字列 `workflow.yaml` には決してマッチさせない（`queue_taskstop_net.py` のモジュール docstring は当該部分文字列を含むが何も読んでいない）。
- Layer 2: `queue_stop_guard.py` の carve-out の挙動テスト。`test/README.md` の hook-contract パターンに従い、stdin に JSON を与えてフックをサブプロセスとして起動し、一時 worktree レイアウト上で検証する。journal の最終イベントが `failed` かつ当該タスク自身の workflow.yaml が `status: pending` のとき、タスクは unlaunched に再分類され、それを名指しする BLOCK（exit 2）が生じる。同じ journal 状態でタスク status が `pending` 以外のときはブロックが生じない（exit 0）。

**入力**:

- 3 つの journal-only フックのソース: Python ソース - 静的スキャン対象
- `em-workflow/hooks/queue_stop_guard.py`: Python フック - サブプロセス起動対象
- 一時 worktree フィクスチャ: ディレクトリ構造 - journal と workflow.yaml を含む

**出力**:

- 静的スキャンの検証結果: テスト結果 - 違反があれば失敗
- サブプロセスの exit code と stderr: プロセス出力 - exit 2 / BLOCK 行、または exit 0

**ビジネスルール**:

- 静的スキャンは status 読み取りの識別子でキーする。
- 部分文字列 `workflow.yaml` 単独では決して失敗を引き起こさない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 3 フックのいずれかが status 読み取りを行う | 識別子がソースに出現する | Layer 1 のスキャンが失敗する |
| carve-out の挙動不一致 | failed + pending で exit 2 にならない | Layer 2 のテストが失敗する |

#### FR5: 新規マッチャの非空虚性規律

**説明**: FR3 と FR4 が導入するすべての新規アサーションは、モジュールの確立済み規律を引き継ぐ。各新規文言マッチャは、そのリテラルをモジュールレベル定数 1 つに保持し、正のテストと負証明テストで共有する（Contract 1）。各負証明は、言い換えではなくキャプチャ済みの変更前文言サンプルに対して実行する（Contract 2）。各サンプルは `TestPreChangeSampleGuards` の RETAINED アンカーアサーションによって非空虚性を保証する（Contract 4）。特に FR4 の静的スキャンは、タスク status を**実際に読む**フックソースであればフラグを立てることを示す負証明を持ち、任意の入力に対して通過するアサーションへ劣化しないようにする。

**ビジネスルール**:

- Contract 1（定数の単一保持と共有）、Contract 2（キャプチャ済みサンプルによる負証明）、Contract 4（RETAINED アンカーによる非空虚性保証）を新規アサーションすべてに適用する。

#### FR6: unlaunched 定義の乖離を閉じずに文書化

**説明**: `queue_stop_guard.py` の分類ロジックには手を触れず、乖離を I.2.a に意図的かつ文書化された乖離として明記する。記述すべき乖離: I.2.a は unlaunched を「journal イベントがまだ無く、かつ status != merged」と定義するのに対し、`queue_stop_guard.py` の `evaluate_feature` は journal イベントの無いタスクを workflow.yaml status を一切参照せずに unlaunched と分類する。したがって journal が欠損・切り詰められた場合、workflow.yaml status が `merged` と読めるタスクがフックの launch リストに名指しされうる。文書化されたテキストは、これを本フィーチャーが修正すべき欠陥ではなく、意図されたフック挙動（当該フックは権威ではなく fail-open のネットである）として記録する。

**ビジネスルール**:

- `queue_stop_guard.py` の分類ロジックは byte 単位で不変とする。
- 乖離は意図的であるとマークする。

#### FR7: プラグインの version bump

**説明**: `em-workflow/` 配下のファイルが変更されるため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` の `version` と `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を bump する。両者は現在 0.1.44 であり、同一の新しい値で終える。CLAUDE.md が定めるバージョニング規則に合致するのは patch レベルの bump（0.1.45）である。

**入力**:

- `em-workflow/.claude-plugin/plugin.json`: JSON - 現行 version 0.1.44
- `.claude-plugin/marketplace.json`: JSON - em-workflow エントリの現行 version 0.1.44

**出力**:

- 両ファイルの version: 文字列 - 同一の新しい値（0.1.45）

#### FR8: スイート全体のグリーン

**説明**: 変更後、リポジトリルートから `python3 -m unittest discover -s tests` が通過する。これには `tests/` の既存モジュールすべてと、本フィーチャーが意図的に改訂しない `test_recycled_task_id_consistency.py` の既存マッチャすべて（TS-7 raw-literal ガード、TS-8 commit リテラル、TS-9 byte-identity、TS-10 順序、AC-1..AC-5 グループ）を含む。

## 5. 非機能要件

### NFR1: テストコードの依存下限

新規および改訂されたテストは Python 標準ライブラリ（unittest、pathlib、re、json、subprocess、tempfile）のみを import する。`test/README.md` に従い、サードパーティパッケージは import せず、インストール済みであることも前提としない。

### NFR2: テストの配置と命名

すべてのテストコードはリポジトリルートの `tests/` ディレクトリに置く。改訂は `tests/test_recycled_task_id_consistency.py` に入る。新規モジュールは `test_<target>.py` と命名し、クラスは `Test<Behavior>`、メソッドは `test_<condition>_<expected_result>` とする。登録手順なしで `unittest discover` に拾われること。

### NFR3: 文書アサーションの行折り返し耐性

`implement-phase.md` の散文に対するアサーションは、該当セクションの空白正規化済みコピー（モジュール既存の `_normalize_ws` ヘルパ）と比較する。これにより再折り返しがアサーションを脆くしない。例外は byte-identity および raw-literal ガード（TS-7、TS-8、TS-9）であり、これらは生の未正規化テキストとの比較を維持しなければならない。

### NFR4: フック実行時挙動の不変

4 つのフックいずれにも挙動変更を加えない。`queue_stop_guard.py` の fail-open 規約（想定外の条件はすべて exit 0）、タスク status の遅延読み取り、連続ブロック上限 3、サイドカー処理はすべて保持する。FR4 の挙動テストはフックを観測するものであり、フックの変更を要求しない。

### NFR5: テストの独立性

挙動サブプロセステストはフィクスチャ一式を `tempfile.TemporaryDirectory()` 配下に構築する（worktrees ルート、integration worktree、`feature-docs/<feature>/workflow.yaml`、`journal.jsonl`、stop-guard サイドカー）。実際の `~/.claude` 状態やリポジトリ自身の `.claude/worktrees` ツリーは読み書きしない。

### NFR6: SSOT の単一性の保持

変更後も I.2.a は recycled-task-id ルールの唯一の規範的記述であり続ける。Supporting cast の箇条書きは独立に再掲するのではなく I.2.a を引用する。既存の I.2.b step 1 の引用（`the recycled-task-id rule in I.2.a above`）は変更しない。

## 6. UI/UX要件

該当なし。本フィーチャーにユーザー可視の面は無い。参照文書のセクション改訂、Python unittest アサーションの改訂・追加、2 つの JSON version フィールドの bump のみで構成される。

## 7. データ要件

該当なし。永続データモデルの追加・変更は無い。

## 8. 外部連携

該当なし。外部システムとの連携は無い。

## 9. 制約条件

### 9.1 技術的制約

- テストコードは Python 標準ライブラリのみに依存する（NFR1）。
- テストは `tests/` に配置し `unittest discover` で拾われる（NFR2）。
- フックの実行時挙動は変更しない（NFR4）。
- テストコマンドは `python3 -m unittest discover -s tests`（プロジェクト検出結果: main コンポーネント、言語 python）。

### 9.2 ビジネス上の制約

- `em-workflow/` 配下の変更には同一変更内での version bump が伴う（FR7）。
- ライセンス: none。

### 9.3 スケジュール制約

記載なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:

- `em-workflow/references/implement-phase.md`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_*.py`（本フィーチャーが追加しうる新規テストモジュール）
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/recycled-task-id-carveout/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/recycled-task-id-carveout/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/recycled-task-id-carveout/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 静的スキャンが意味ではなく識別子にマッチするため、まったく新しい機構（例: YAML ライブラリ）による status 読み取りを検出できない | 中 | ソーステキストによるピンの境界として受け入れる（前提事項に記録） |
| `workflow.yaml` の裸の部分文字列にマッチさせると `queue_taskstop_net.py` の docstring で誤検出する | 高 | スキャンを status 読み取りの識別子のみにキーする（FR4 Layer 1） |
| 新規マッチャが任意の入力で通過する空虚なアサーションに劣化する | 高 | 各マッチャに負証明と RETAINED アンカーを課す（FR5） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| version bump 漏れによりキャッシュが更新されない | 中 | 中 | plugin.json と marketplace.json を同一値に揃える（FR7、TS-9 で検証） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR1): I.2.a の recycled-task-id 段落に、ルールを orchestrator に限定したうえで直後にフックをその限定から除外する文が存在しないこと。リテラル「governs only the orchestrator's interpretation of the journal」が文書から消えていること。
- [ ] AC-2 (FR1): 改訂後の I.2.a の文言が、`queue_stop_guard.py` が recycled-task-id carve-out を適用すること、および `queue_launch_guard.py`・`queue_failure_net.py`・`queue_taskstop_net.py` が journal の最終イベントのみから判断し `tasks.{T}.status` を決して参照しないことを、単一のルールとして述べていること。
- [ ] AC-3 (FR1): `never read workflow.yaml` も `never reads workflow.yaml` も `implement-phase.md` のどこにも出現しないこと（既存の回帰ガードが依然として成立する）。
- [ ] AC-4 (FR2): Supporting cast の Stop-hook 箇条書きの等価主張が carve-out に限定され、改訂後の I.2.a と整合していること。I.2.b step 1 の I.2.a 引用が変更されていないこと。
- [ ] AC-5 (FR3): `TestRecycledTaskIdRuleScopedToOrchestrator` が 3 フックの journal-only 主張と `queue_stop_guard.py` の例外を 2 つの分離したアサーションとして検証すること。当該クラスに生き残るアサーションのうち、フックのファイル名が I.2.a セクション内のどこかに出現するだけで満たされるものが無いこと。
- [ ] AC-6 (FR3): モジュール docstring の当該クラスに関する記述が、クラスが実際に検証する内容と一致すること。`ORCHESTRATOR_ONLY_SCOPE_PHRASE` の改訂後、読み手が 1 つしかないモジュールレベル定数が残っていないこと。
- [ ] AC-7 (FR4, layer 1): 静的スキャンテストが `queue_launch_guard.py`・`queue_failure_net.py`・`queue_taskstop_net.py` のソースを読み、いずれかがタスク単位の workflow.yaml status 読み取りを行っていれば失敗すること。そのマッチャは status 読み取りの識別子でキーされ、文字列 `workflow.yaml` 単独では決して失敗を引き起こさないこと。
- [ ] AC-8 (FR4, layer 2): 挙動テストが `queue_stop_guard.py` をサブプロセスとして一時フィクスチャに対して実行し、journal の最終イベントが `failed` かつ当該タスクの workflow.yaml status が `pending` のとき exit 2 と BLOCK 行でのタスク名指しを観測し、同じ journal 状態で status が `pending` 以外のとき exit 0 を観測すること。
- [ ] AC-9 (FR5): 各新規マッチャが、主張に反する文言（またはフックソース）に対して失敗することを示す負証明を対で持つこと。各変更前サンプル／違反サンプルが、正のアサーションで保持されるアンカーを備え、いかなる証明もトートロジーに劣化しないこと。
- [ ] AC-10 (FR6): I.2.a が、自身の「journal イベントが無く status != merged」という文言と、フックの status 非参照な no-journal-event 扱いとの間の unlaunched 定義の乖離を、意図的なものとして明示的に記録すること。`queue_stop_guard.py` の分類ロジックが byte 単位で不変であること。
- [ ] AC-11 (FR7): `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリが同一の bump 後 version（0.1.45）を持ち、同一変更集合内で変更されていること。
- [ ] AC-12 (FR8): リポジトリルートから `python3 -m unittest discover -s tests` が exit 0 で終了すること。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1 (AC-1, AC-3): 正規化済み I.2.a セクションが矛盾したスコープリテラルを含まないこと。文書全体が `never read workflow.yaml` も `never reads workflow.yaml` も含まないこと。負証明: マッチャが現行（矛盾した）I.2.a 文言のキャプチャ済みサンプルをフラグすること。
- [ ] TS-2 (AC-2, AC-5): 正規化済み I.2.a が、3 つの journal-only フックを `tasks.{T}.status` を決して参照しないという主張の中で名指ししていること。負証明: `queue_stop_guard.py` が同じ 3 フックの主張に含まれているサンプルに対してマッチャが失敗すること。
- [ ] TS-3 (AC-2, AC-5): 正規化済み I.2.a が `queue_stop_guard.py` を carve-out を適用する明示的な例外として名指ししていること。負証明: `queue_stop_guard.py` が 4 フックの「never consults」リストにのみ現れる post-stopguard-retired-failed 文言に対してマッチャが失敗すること。
- [ ] TS-4 (AC-4): 正規化済み Supporting cast の Stop-hook 箇条書きが carve-out にスコープされた等価性を述べ、I.2.a を引用していること。I.2.b step 1 の引用リテラルが不変のまま残っていること。
- [ ] TS-5 (AC-7): 3 つの journal-only フックソースに対する静的スキャンがタスク単位の status 読み取りを検出しないこと。負証明: 同じスキャンをそうした読み取りを含むソースサンプルに適用すると違反を報告し、docstring に部分文字列 `workflow.yaml` のみを含むサンプルでは報告しないこと。
- [ ] TS-6 (AC-8): task0001 の journal 最終イベントが `failed` かつ workflow.yaml の `tasks.task0001.status` が `pending` であるフィクスチャに対する `queue_stop_guard.py` のサブプロセス実行 — exit 2、stderr の BLOCK 行が task0001 を名指しすること。
- [ ] TS-7 (AC-8): 同一フィクスチャで `tasks.task0001.status: in_progress`（または `pending` 以外の任意の値）の場合 — exit 0、BLOCK 無し。
- [ ] TS-8 (AC-10): 正規化済み I.2.a が、journal イベント欠損ケースを名指しし意図的とマークする乖離記述を含むこと。負証明: 変更前 I.2.a 段落サンプルには当該マッチャが存在しないこと。
- [ ] TS-9 (AC-11): 両 version ファイルが JSON としてパースでき、その em-workflow version 値が等しく 0.1.44 より大きいこと。
- [ ] TS-10 (AC-6, AC-9): `TestPreChangeSampleGuards` が本フィーチャーで導入されたすべての新規サンプルに対して RETAINED アンカーを検証すること。
- [ ] TS-11 (AC-12): 本モジュールの既存 TS-7/TS-8/TS-9/TS-10 ガードおよび `tests/` の他のすべてのモジュールを含むスイート全体がグリーンで実行されること。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| recycled-task-id ルール | `implement-phase.md` I.2.a が定める、再利用されたタスク ID の解釈規則 |
| carve-out | recycled-task-id ルールの適用対象に `queue_stop_guard.py` を含める明示的な例外。具体的には failed-plus-pending の再分類 |
| journal-only フック | `queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`。journal の最終イベントのみからタスク状態を導出する |
| unlaunched | I.2.a の定義では「journal イベントがまだ無く、かつ status != merged」。`queue_stop_guard.py` の `evaluate_feature` では journal イベントが無いことのみで判定される |
| SSOT | Single Source of Truth。本フィーチャーでは I.2.a が recycled-task-id ルールの SSOT |
| 負証明 | マッチャが主張に反するサンプルに対して失敗することを示すテスト |
| RETAINED アンカー | 変更前サンプルの非空虚性を保証するために正のアサーションで確認される要素 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] ピン機構の選択（batch codex consultation、question `recycled-carveout.pin-test-mechanism`）: 両方のピン層を構築する。3 つの journal-only フックに対する静的ソーススキャンと、`queue_stop_guard.py` の carve-out に対する挙動サブプロセステストの両方であり、いずれか一方のみではない。
- [x] unlaunched 定義の乖離の扱い（batch codex consultation、question `recycled-carveout.unlaunched-divergence`）: 乖離はフックを変更して閉じるのではなく、I.2.a に意図的なものとして文書化する。`queue_stop_guard.py` は手つかずのままとし、タスク記述が述べるスコープ除外に合致させる。
- [x] version bump の刻み: CLAUDE.md の patch レベル bump 規則に従い 0.1.45 への patch bump とする。version を保持するファイルは FR7 が挙げる 2 つのみ。
- [x] 静的スキャンの検出範囲: スキャンは意味ではなく識別子にマッチする。すなわち `queue_stop_guard.py` が用いる形（行ベースの workflow.yaml スキャンヘルパ／正規表現）の status 読み取りを検出する。まったく新しい機構（例: YAML ライブラリ）でタスク status を読むフックは捕捉されない。これはソーステキストによるピンの境界として受け入れる。
- [x] 変更範囲: `em-workflow/references/implement-phase.md`、`tests/`（本モジュールおよび新規テストモジュール）、`em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` 以外のファイルは変更されない見込みである。
- [x] デザインステップ: skipped。本フィーチャーにユーザー可視の面は無く、参照文書のセクション改訂・Python unittest アサーションの改訂と追加・2 つの JSON version フィールドの bump のみである。UI も画面も視覚的出力も設計対象のユーザー操作も無く、本リポジトリにデザインシステム入力も存在しない。batch ポリシーがゲート `create-spec.design-step` を option_id `decide_autonomously` で解決し、この推奨を受理した。

### 14.2 未確認・保留事項

なし。すべての要件が `status: resolved` である。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: I.2.a recycled-task-id 段落（現在の 226-236 行）および Supporting cast の Stop-hook 箇条書き（現在の 517-527 行）
- `tests/test_recycled_task_id_consistency.py`: 改訂対象のテストモジュール
- `test/README.md`: hook-contract パターンおよびテストコードの依存方針
- `em-workflow/hooks/queue_stop_guard.py`、`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`: ピン対象のフック実装
- `em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`: version 保持ファイル
- `CLAUDE.md`: バージョニング規則

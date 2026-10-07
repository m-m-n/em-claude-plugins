# Feature: routeback-record-quoted-continuation

## Overview

`em-workflow/hooks/queue_stop_guard.py` は workflow.yaml の `tasks:` を行単位で読む。
この機能では、引用文字列（ダブルクォート / シングルクォート）とフロー形式のコレクション（`[ ]` / `{ }`）の値の本文にある行を、タスクの境界・タスク ID・status・route-back 記録のどれとしても読まないようにする。
`tasks.{T}.notes` の中の値は、Stop hook の未起動 / 失敗の判定に影響しない。

## Objectives

- queue_stop_guard.py が workflow.yaml の `tasks:` を行単位で読むとき、引用文字列（ダブルクォート / シングルクォート）とフロー形式のコレクション（`[ ]` / `{ }`）の値の本文にある行を、タスクの境界・タスク ID・status・route-back 記録のどれとしても読まない。
- 継続行の字下げが直下キーと同じでも、それより浅くても読まない。
- `tasks.{T}.notes` の中の値は、Stop hook の未起動 / 失敗の判定に影響しない。

## User Stories

該当なし

## Acceptance Criteria

- [ ] AC1 (FR1, FR2): 再現手順のフィクスチャ（status: pending、notes の 3 行 `notes: "tried twice` / `routeback_failed_journal_line: 1` / `gave up"` がすべて 4 空白字下げ）で、`task_routeback_records_from_workflow` が `{}` を返す。
- [ ] AC2 (FR1, FR2, FR7): 偽造。ジャーナル 1 行目が task0001 の failed、task0001 は pending、notes の引用文字列の 4 空白の継続行に `routeback_failed_journal_line: 1`、直下キーの記録は無い。この場合、hook は exit 0 で終わり、stderr に BLOCK が出ない。
- [ ] AC3 (FR1, FR2, FR5, FR7): 隠蔽。同じ条件で、notes の 4 空白の継続行に `routeback_failed_journal_line: 3` があり、その後ろの直下キーに `routeback_failed_journal_line: 1` がある。この場合、hook は exit 2 で終わり、起動リストに task0001 が含まれる。
- [ ] AC4 (FR1, FR7): AC2 と AC3 が、単一引用符の複数行スカラーと、複数行のフロー形式のシーケンス・マッピングでも成り立つ。
- [ ] AC5 (FR1, FR2): task0001 の notes の引用文字列の中に `  task0002:` と、その下の 4 空白の `routeback_failed_journal_line: N` または `status: pending` の行がある。この場合、本物の task0002 ブロックの記録と status が採用され、偽の行で task0002 の分類は変わらない。引用文字列の中のタスクキーの形の行（例: `  task0099:`）は起動リストに現れない。
- [ ] AC6 (FR1): 引用文字列の継続行が 0 桁目にあっても、その後ろのタスクは引き続き列挙され、判定される。
- [ ] AC7 (FR3, FR4): エスケープした引用符（`\"` と `''`）では閉じないこと、ブロックスカラー本文とコメント行にある閉じない引用符・括弧が後続の本物の記録を隠さないこと（exit 2）、1 行で閉じる値が後続行に影響しないことを、テストで確かめる。
- [ ] AC8 (FR5, FR6, NFR2, NFR4, NFR6): 既存テストがアサーションを変えずにすべて通り、docstring とコメントに FR6 の記述がある。

## Technical Requirements

### Functional Requirements

- **FR1:** 引用文字列とフロー形式の本文を読み飛ばす — `em-workflow/hooks/queue_stop_guard.py` の `iter_task_block_lines` と `task_ids_from_workflow` は、ファイルの先頭から引用文字列とフロー形式の開閉を追う。値が二重引用符・単一引用符・フロー形式の開き括弧で始まり、その行で閉じない場合、閉じる行までの後続行は次のどれにも使わない: `tasks:` セクションの開始、セクションの終了、タスクキー（`taskNNNN:`）、タスクブロックの終了、ブロック内の行としての yield。後続行の字下げは問わない（直下キーと同じ 4 空白、それより浅い 2 空白、0 桁目を含む）。開いた行そのものは従来どおり扱う。
- **FR2:** 共有の読み取りを通じて status と記録にも効かせる — `task_statuses_from_workflow` と `task_routeback_records_from_workflow` は、FR1 の対象になった `iter_task_block_lines` の出力だけを読む。これにより、引用文字列とフロー形式の本文の行は、どのタスクの status にも記録にもならない。本文の中にあるタスクキーの形の行（例: `  task0002:`）は、後続行を別タスクに振り分けない。
- **FR3:** 閉じの判定とエスケープ — 二重引用符では、`\"` は閉じとみなさず、`\\` の後の `"` は閉じとみなす。行末の `\`（エスケープした改行）があっても本文は続く。単一引用符では `''` は閉じとみなさない。フロー形式では入れ子の括弧を数え、内側の引用文字列の中にある括弧と、コメントの中にある括弧は数えない。閉じた後の同じ行に続く空白とコメント（例: `title: "x" # "`）は開きとみなさない。
- **FR4:** 開きとみなす位置 — 値の開始位置にある引用符と括弧だけを開きとみなす。直下キーの値、値がキーの次の行から始まる場合、ネストしたキーの値、シーケンス項目の値が該当する。次は開きとみなさない: ブロックスカラー（`|` / `>` と各指示子）の本文の行、コメント行、プレーンスカラーの途中や継続行に現れる引用符・括弧。
- **FR5:** 1 行で閉じる値と既存の規則 — 1 行で閉じる引用文字列とフロー形式の値（`title: "task task0001"`、`files: []`、`skills: [infra-impl]` など）は、後続行の扱いを変えない。閉じた行より後の行は従来どおり読む。既存の規則は変えない: 直下キーの字下げ判定、直下キーの間で最初の出現を採用すること、正準値の規則、ブロック範囲の規則、hook の終了コードと stderr の形式。
- **FR6:** docstring とコメント — モジュール docstring、`iter_task_block_lines`・`task_ids_from_workflow`・`task_routeback_records_from_workflow` の docstring、`ROUTEBACK_RECORD_KEY` の直上のコメントに、引用文字列とフロー形式の値の本文の行を、タスクの境界・タスク ID・status・記録として読まないことを書く。`TestModuleDocstring` が固定する文言（'only when all three hold'、'`routeback_failed_journal_line` record'、'Any other task whose last event is `failed` is failed'、"the task's own id, returned from `failed` to `pending` by route-back"）と、`TestDirectKeyWording` が固定する文言（'direct keys'、'block scalar bodies'、'nested'）は残す。'a recycled task id left behind by a route-back re-plan' は含めない。
- **FR7:** 回帰テスト — `tests/test_queue_stop_guard_routeback_record.py` に次のテストを追加する。(a) 継続行を直下キーと同じ 4 空白で字下げした二重引用符の notes での偽造（直下キーの記録が無い → exit 0）と隠蔽（記録より前に一致しない値、一致する本物の記録 → exit 2、task0001 を名指し）。(b) 同じ 2 種の単一引用符版とフロー形式（シーケンス・マッピング）版。(c) 再現手順の関数呼び出しが `{}` を返すこと。(d) 引用文字列の中のタスクキーの形の行による、別タスクの記録・status・タスク ID の偽造が起きないこと。(e) 0 桁目の継続行の後ろのタスクが引き続き列挙されること。(f) エスケープとブロックスカラー本文の境界。フィクスチャ生成関数には、単一引用符とフロー形式の複数行の notes を出力する手段を足す（既存の `notes_double_quoted` の `continuation_indent` 引数は既存の呼び出しを変えずに使う）。

### Non-Functional Requirements

- **NFR1 - 依存:** `queue_stop_guard.py` は引き続き標準ライブラリだけを import し、workflow.yaml を行単位で読む（YAML ライブラリは使わない）。
- **NFR2 - fail-open:** 閉じない引用文字列や括弧（ファイル末尾まで閉じない場合を含む）、壊れたバイト列で hook はクラッシュしない。閉じを判定できないときは、後続行を読まない側（記録なし、ブロックしない側）に倒す。既存の `TestFailOpen` は通ったままにする。
- **NFR3 - テスト規約:** テストコードは標準ライブラリだけを import し、他のテストモジュールを import しない。hook は Stop hook の JSON を stdin に渡すサブプロセスとして実行する。単一の関数を確かめるときは、ファイルパスから hook モジュールを読み込んでよい（既存の `load_hook_module`）。
- **NFR4 - status 読み取りの識別子:** `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` を、`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py` に持ち込まない（`tests/test_queue_hook_status_read_pin.py` の静的スキャン）。読み飛ばしの処理を共通化する場合も、`queue_stop_guard.py` の中に置く。
- **NFR5 - バージョン:** プラグインの version は変えない。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` は触らない。
- **NFR6 - 回帰:** `python3 -m unittest discover -s tests` の全体が通ったままにする。`tests/test_queue_stop_guard.py`、`tests/test_queue_stop_guard_routeback_record.py`、`tests/test_queue_hook_status_read_pin.py`、`tests/test_routeback_record_carve_out.py` の既存アサーションは変えない。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし（変更は `em-workflow/hooks/queue_stop_guard.py` の行単位の読み取りに閉じる）

**Component Diagram:**

```
queue_stop_guard.py
├── iter_task_block_lines            # 引用文字列・フロー形式の開閉を追い、本文の行を境界・yield に使わない (FR1)
├── task_ids_from_workflow           # 同上 (FR1)
├── task_statuses_from_workflow      # iter_task_block_lines の出力だけを読む (FR2)
└── task_routeback_records_from_workflow  # iter_task_block_lines の出力だけを読む (FR2)
```

### Data Flow

```
workflow.yaml
  → iter_task_block_lines / task_ids_from_workflow（引用文字列・フロー形式の本文を読み飛ばす）
  → task_statuses_from_workflow / task_routeback_records_from_workflow
  → Stop hook の未起動 / 失敗の判定（exit 0 / exit 2）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**

- `iter_task_block_lines`: `task_statuses_from_workflow` と `task_routeback_records_from_workflow` の入力 (FR2)
- `queue_launch_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py`: `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` を持ち込まない (NFR4)

**External Dependencies:**

- 標準ライブラリのみ (NFR1, NFR3)

### File Structure

```
em-workflow/
└── hooks/
    └── queue_stop_guard.py                          # FR1–FR6
tests/
└── test_queue_stop_guard_routeback_record.py        # FR7
```

## Declared Change Set

この機能固有のパス:

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard_routeback_record.py`

この機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出される（`references/phases/create-plan-phase.md`）。

上の機能固有のパスに加え、ワークフローが生成する次の 2 つを既定で宣言する:

- `feature-docs/routeback-record-quoted-continuation/**`
- `test-docs/routeback-record-quoted-continuation/**`

`feature-docs/routeback-record-quoted-continuation/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、規則を再掲しない。

`test-docs/routeback-record-quoted-continuation/**` はタスクごとのテスト記録 `test-docs/routeback-record-quoted-continuation/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、規則を再掲しない。

この 2 つの既定の項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことを外したとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合としての宣言である。検証時に観測される実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない機能は `test-docs/routeback-record-quoted-continuation/` ディレクトリを作らないが、その場合も宣言した `test-docs/routeback-record-quoted-continuation/**` は正しい。宣言したパスが実在しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS1 (AC1; FR1, FR2): ファイルパスから hook モジュールを読み込み、再現フィクスチャで `task_routeback_records_from_workflow` が `{}` を返すことを確かめる。二重引用符・単一引用符・フロー形式で行う。

### Integration Tests

- [ ] TS2 (AC2, AC4; FR1, FR2, FR7): 偽造。4 空白の継続行の `routeback_failed_journal_line: 1`、直下キーの記録なし、ジャーナル 1 行目が task0001 の failed → exit 0、BLOCK なし。二重引用符・単一引用符・フロー形式のシーケンス・マッピングの subTest で行う。
- [ ] TS3 (AC3, AC4; FR1, FR2, FR5, FR7): 隠蔽。4 空白の継続行の `routeback_failed_journal_line: 3` の後に、直下キーの `routeback_failed_journal_line: 1` → exit 2、起動リストに task0001。TS2 と同じ 4 形式で行う。
- [ ] TS4 (AC5; FR1, FR2): 別タスクの偽造。task0001 の notes の引用文字列に `  task0002:` と 4 空白の `routeback_failed_journal_line: N`（N はジャーナル上の task0002 の failed 行）、本物の task0002 は pending で記録なし → exit 0。`status: pending` の偽造（本物の task0002 は `status: failed`、記録が一致）→ exit 0。`  task0099:` が起動リストに現れない。
- [ ] TS5 (AC6; FR1): 0 桁目の継続行で閉じる引用文字列の後の task0002・task0003 が起動リストに現れる。
- [ ] TS6 (AC7; FR3, FR4): `\"` と `''` を含む継続行、行末 `\` の継続、閉じた後のコメント内の引用符、ブロックスカラー（`|` / `>-` など）の本文の閉じない `"` と `[` の後の本物の記録 → exit 2。値がキーの次の行から始まる引用文字列の 4 空白の継続行 → 記録にならない。

### Regression Tests

- [ ] TS7 (AC8; FR5, FR6, NFR2, NFR4, NFR6): `python3 -m unittest tests.test_queue_stop_guard tests.test_queue_stop_guard_routeback_record tests.test_queue_hook_status_read_pin tests.test_routeback_record_carve_out` と `python3 -m unittest discover -s tests` がすべて通る。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 継続行の字下げが直下キーと同じ 4 空白、それより浅い 2 空白、0 桁目のいずれでも本文として読み飛ばす (FR1, TS2, TS3, TS5)
- [ ] エスケープした引用符（`\"`、`''`）と行末の `\` では閉じない (FR3, TS6)
- [ ] ブロックスカラー本文・コメント行にある閉じない引用符・括弧は開きとみなさない (FR4, TS6)
- [ ] ファイル末尾まで閉じない引用文字列・括弧、壊れたバイト列でクラッシュせず、記録なし・ブロックしない側に倒す (NFR2)

### Performance Tests

該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `tasks.{T}.notes` など引用文字列・フロー形式の値の本文の行を、タスクの境界・タスク ID・status・route-back 記録として読まない (FR1–FR4)
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし（hook の終了コードと stderr の形式は変えない (FR5)）

### Error Flow

```
閉じを判定できない（ファイル末尾まで閉じない / 壊れたバイト列）
  → 後続行を読まない → 記録なし・ブロックしない（exit 0） (NFR2)
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] FR1–FR7 がすべて実装され、テストされている
- [ ] TS1–TS7 がすべて通る
- [ ] NFR1–NFR6 を満たす
- [ ] FR6 の docstring とコメントが書かれている
- [ ] コードレビューが完了している

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Assumptions

- A1: 読み取り側で修正する。読み取り時に引用文字列とフロー形式の本文を読み飛ばす。文書だけを直す案は修正として採らない。
- A2: 読み飛ばしは共有のブロック走査（`iter_task_block_lines` と `task_ids_from_workflow`）に入れる。タスクの境界、タスク ID の列挙、status の読み取り、記録の読み取りのすべてが引用文字列とフロー形式の本文を無視する (FR1, FR2)。
- A3: `tasks.{T}.notes` に書き込み側の規則を追加しない。`em-workflow/references/implement-phase.md` と `em-workflow/references/workflow-schema.md` は変えない。
- A4: 引用文字列・フロー形式の値の閉じを判定できないとき（ファイル末尾まで閉じない、壊れたバイト列）は、後続行を読まない。結果は記録なし・ブロックしない（exit 0）側に倒れる。
- A5: `implement_in_progress`（ワークフローのステップの status の読み取り）は対象外で、変えない。
- A6: アンカー、タグ、引用符付きのキーは、値の開始位置の接頭辞として扱わない。
- A7: 既存テストが固定している挙動を保つ: 直下キーの字下げ規則、最初の出現を採用すること、正準値の規則、ブロック範囲の規則。
- A8: プラグインの version は変えない。

## Implementation Phases (if applicable)

該当なし

## References

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard.py`
- `tests/test_queue_stop_guard_routeback_record.py`
- `tests/test_queue_hook_status_read_pin.py`
- `tests/test_routeback_record_carve_out.py`

# Feature: routeback-record-quoted-open-residual

## Overview

`em-workflow/hooks/queue_stop_guard.py` の複数行の値の追跡（`_MultilineValueTracker`）には、引用された値を誤って開き、それ以降の行をすべて本文として扱ってしまう経路が 2 つ残っている。
どちらの経路も本物の `routeback_failed_journal_line` 記録と後続のタスクを隠し、Stop hook が exit 2 で終わるべきところを exit 0 で終わる（TM-2 の隠蔽）。
この機能では、この 2 つの経路を塞ぐ。

## Objectives

- `em-workflow/hooks/queue_stop_guard.py` の複数行の値の追跡で、引用された値を誤って開いて後続行をすべて本文として扱う残り 2 つの経路を塞ぐ。
- 本物の `routeback_failed_journal_line` 記録と後続のタスクが隠されず、Stop hook が exit 2 で終わるべきところで exit 2 で終わる。

## User Stories

該当なし

## Acceptance Criteria

- [ ] AC-1 (FR1): 準備: ジャーナル 1 行目は task0001 の `failed` イベント。task0001 は `pending` で、notes キーの後に直下キー `routeback_failed_journal_line: 1` がある。その後ろに、ジャーナルにイベントの無い pending の task0002 ブロックが続く。notes の次の各形式を subTest で実行する: 1 行の `    notes: [retry? 'failed]`、1 行の `    notes: {reason: retry? 'failed}`、末尾 `?` の形式 `    notes: [retry?` + `      'failed]` と `    notes: {reason: retry?` + `      'failed}`。それぞれで、hook のサブプロセスは BLOCK を出して exit 2 で終わり、起動リストに task0001 と task0002 が含まれる。
- [ ] AC-2 (FR1): AC-1 のフィクスチャで、ファイルパスから hook モジュールを読み込むと、`task_ids_from_workflow` は task0001 と task0002 を返し、`task_routeback_records_from_workflow` は task0001 を `"1"` に対応づける。
- [ ] AC-3 (FR2): 準備は AC-1 と同じで、notes を次のように書く: `    notes:`、次に 6 個の空白の後に U+3000 だけがある行、次に `      - 'unclosed`・`      "unclosed`・`      [unclosed` のいずれか。U+3000 を U+00A0 に置き換えた形でも同じことを行い、それぞれを subTest で実行する。hook は BLOCK を出して exit 2 で終わり、起動リストに task0001 と task0002 が含まれる。直接呼び出すと、`task_ids_from_workflow` は task0001 と task0002 を返し、task0001 の記録は `"1"` になる。
- [ ] AC-4 (FR3): 既存の `test_question_mark_indicator_followed_by_a_space_still_opens`（`{? 'tried }`）と、既存のテスト全体が変更なしで通る。
- [ ] AC-5 (NFR2): AC-1 と AC-3 のすべてのフィクスチャで直接呼び出したとき、タスク ID・タスクブロック走査・記録の各読み取り関数は例外を出さずに戻る。
- [ ] AC-6 (FR4): トラッカーのクラス docstring と `_scan_flow` のコメントに FR1 の `?` の条件が書かれ、トラッカーの docstring に FR2 の空行の定義が書かれている。

## Technical Requirements

### Functional Requirements

- **FR1:** `?` を flow マッピングの指示子とみなすのは flow エントリの先頭だけにする — `_MultilineValueTracker._scan_flow` で、内側の文字列の外にある `?` は、次の 2 つをともに満たすときだけマッピングの指示子とみなす。(a) その時点で `_at_start` が真である。(b) 直後が空白・タブ・行末のいずれかである。それ以外の `?` は通常のプレーンスカラーの文字として扱う。この `?` は `_at_start` と `_after_close` を偽にするので、その後ろの引用符は、同じ行でも後続行でも内側の文字列を開かない。`:` の規則は変えない。
- **FR2:** トラッカーの空行判定は空白とタブだけを使う — `_MultilineValueTracker` の 2 つの空行判定、`_read_line` の判定（現在の `stripped.strip() == ""`、240 行目）と `feed` のブロックスカラー分岐の判定（現在の `text.strip() == ""`、230 行目）は、行末の改行を除いた後に U+0020 の空白と U+0009 のタブだけからなる行だけを空行とみなす。それ以外の空白文字（例: U+3000、U+00A0）だけからなる行は空行ではなく、通常の規則で読む。値の開始位置では、その行はプレーンスカラーになり、それより深い後続行はプレーンスカラーの継続行になる。ブロックスカラーの状態では、その行の字下げで、本文の行か、ブロックスカラーの終わりかが決まる。
- **FR3:** 変えない挙動 — 次は従来どおり開く: flow エントリの先頭にあり、直後が空白・タブ・行末の `?`（例: `{? 'tried }`）と、既存の本物の指示子による開きのすべて。トラッカーの外にある読み取り関数の空行判定は変えない: `task_ids_from_workflow`（420 行目）、`iter_task_block_lines`（463 行目）、`task_routeback_records_from_workflow`。
- **FR4:** docstring とコメントの文言 — `_MultilineValueTracker` クラスの docstring（`?` についての文、現在の 208–210 行目）と、`_scan_flow` の `:`/`?` 分岐のコメント（375–379 行目）に、FR1 の条件を書く。トラッカーの docstring には、空行は空白とタブだけからなる行であること（FR2）も書く。

### Non-Functional Requirements

- **NFR1 - 依存:** hook は Python の標準ライブラリだけを import する。
- **NFR2 - fail-open:** トラッカーと読み取り関数は、新しいフィクスチャやファイル末尾まで閉じない値を含め、どんな行の内容でも例外を出さない（fail-open の規約）。
- **NFR3 - 変更範囲:** 変更は `em-workflow/hooks/queue_stop_guard.py`、`tests/test_queue_stop_guard_routeback_record.py`、`feature-docs/routeback-record-quoted-open-residual/` 配下のパスに限る。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` は変えない。
- **NFR4 - 回帰:** 既存テストのアサーションを変更・削除せず、`python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし（変更は `em-workflow/hooks/queue_stop_guard.py` の `_MultilineValueTracker` の行の読み取りに閉じる）

**Component Diagram:**

```
queue_stop_guard.py
├── _MultilineValueTracker
│   ├── _scan_flow                        # `?` を指示子とみなすのは flow エントリの先頭だけ (FR1, FR4)
│   ├── _read_line                        # 空行は空白とタブだけの行 (FR2)
│   └── feed（ブロックスカラー分岐）       # 空行は空白とタブだけの行 (FR2)
├── task_ids_from_workflow                # 自身の空行判定は変えない (FR3)
├── iter_task_block_lines                 # 自身の空行判定は変えない (FR3)
└── task_routeback_records_from_workflow  # 自身の空行判定は変えない (FR3)
```

### Data Flow

```
workflow.yaml
  → _MultilineValueTracker（引用された値・flow の開閉、空行の判定）
  → task_ids_from_workflow / iter_task_block_lines / task_routeback_records_from_workflow
  → Stop hook の判定（exit 0 / exit 2）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**

- `_MultilineValueTracker`: `task_ids_from_workflow`・`iter_task_block_lines`・`task_routeback_records_from_workflow` が値の本文の行を判定するために使う

**External Dependencies:**

- 標準ライブラリのみ (NFR1)

### File Structure

```
em-workflow/
└── hooks/
    └── queue_stop_guard.py                          # FR1–FR4
tests/
└── test_queue_stop_guard_routeback_record.py        # TS-1–TS-6
```

## Declared Change Set

この機能固有のパス:

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard_routeback_record.py`

この機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出される（`references/phases/create-plan-phase.md`）。

上の機能固有のパスに加え、ワークフローが生成する次の 2 つを既定で宣言する:

- `feature-docs/routeback-record-quoted-open-residual/**`
- `test-docs/routeback-record-quoted-open-residual/**`

`feature-docs/routeback-record-quoted-open-residual/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、規則を再掲しない。

`test-docs/routeback-record-quoted-open-residual/**` はタスクごとのテスト記録 `test-docs/routeback-record-quoted-open-residual/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、規則を再掲しない。

この 2 つの既定の項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことを外したとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合としての宣言である。検証時に観測される実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない機能は `test-docs/routeback-record-quoted-open-residual/` ディレクトリを作らないが、その場合も宣言した `test-docs/routeback-record-quoted-open-residual/**` は正しい。宣言したパスが実在しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-2 (AC-2, AC-3; FR1, FR2): importlib で hook モジュールを読み込み、AC-1 と AC-3 のフィクスチャで読み取り関数を直接呼ぶ。task_ids が `[task0001, task0002]`、`records[task0001] == "1"` になることを確かめる。基準リビジョンでは red を観測済み（records が `{}`、task_ids が `['task0001']`）。
- [ ] TS-6 (AC-5; NFR2): 新しいフィクスチャで、読み取り関数が例外を出さずに戻る。

### Integration Tests

- [ ] TS-1 (AC-1; FR1): Stop hook の JSON を stdin に渡す hook のサブプロセスを、AC-1 の notes の各形式で実行する（subTest）。exit 2 で終わり、起動リストに task0001 と task0002 が含まれることを確かめる。基準リビジョンでは red を観測済み（exit 0）。
- [ ] TS-3 (AC-3; FR2): hook のサブプロセスを、U+3000 と U+00A0 × （`- '…`、`"…`、`[…`）の組み合わせ（6 個の subTest）で実行する。exit 2 で終わり、起動リストに task0001 と task0002 が含まれることを確かめる。
- [ ] TS-4 (FR2): `feed` の変更の非回帰。`    notes: |`、本文の行、6 個の空白と U+3000 の行、`      - 'x` の後に直下キーの記録を置く。U+3000 の行がブロックスカラーの本文の行のままで、hook が exit 2 で終わり task0001 を名指しすることを確かめる。

### Regression Tests

- [ ] TS-5 (AC-4, NFR4; FR3): リポジトリのルートで `python3 -m unittest tests.test_queue_stop_guard_routeback_record` と `python3 -m unittest discover -s tests` を実行する。すべて通り、既存のアサーションが変更されていないことを確かめる。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] `[`・`{`・`,` の直後（間の空白の有無を問わない）にあり、直後が空白・タブ・行末の `?` は引き続き指示子であり、`[a, ? 'x]` は開く (FR1, FR3)
- [ ] スカラーの途中の行末にある `?`（`[retry?`）は通常の文字である。走査は `_at_start` が偽のまま次の本文の行に進むので、`'failed]` は開かず、`]` で値が閉じる (FR1)
- [ ] `[retry?'failed]`（空白なし）は既存の、開かない挙動のまま (FR1)
- [ ] 0 桁目の U+3000 / U+00A0 だけの行の後に `"…` か `[…` が続く場合も、FR2 の後は開かない。後に `- '…` が続く場合は引き続き開く（A1） (FR2)
- [ ] U+000B と U+000C だけの行も、FR2 で空行ではなくなる（YAML の空白は空白とタブだけ） (FR2)

### Performance Tests

該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** notes の値の中の flow エントリ先頭でない `?` や、U+3000 / U+00A0 だけの行で引用された値を誤って開かず、本物の `routeback_failed_journal_line` 記録と後続のタスクを隠さない (FR1, FR2)
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
どんな行の内容（新しいフィクスチャ、ファイル末尾まで閉じない値を含む）
  → トラッカーと読み取り関数は例外を出さない (NFR2)
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] FR1–FR4 がすべて実装され、テストされている
- [ ] TS-1–TS-6 がすべて通る
- [ ] NFR1–NFR4 を満たす
- [ ] FR4 の docstring とコメントが書かれている
- [ ] コードレビューが完了している

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Assumptions

- A1: AC-3 のフィクスチャでは、U+3000 または U+00A0 の行は `notes:` キーより深く字下げする（6 個の空白の後に、その非 ASCII の空白文字だけを置く）。
- A2: FR2 は `_read_line`（240 行目）だけでなく、`feed` のブロックスカラーの判定（230 行目）にも適用する。
- A3: トラッカーの外にある読み取り関数自身の空行判定（420 行目と 463 行目の `line.strip()`）は変えない。
- A4: プラグインの version は変えない。

## Implementation Phases (if applicable)

該当なし

## References

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard_routeback_record.py`

# Feature: sca-listing-undecodable-output

## 概要

`em-workflow/scripts/scan-dependencies.py` の file-tasks は、タスク一覧（`task list --type セキュリティ --format json`）の出力が UTF-8 としてデコードできないときも落ちずに終わり、stdout に JSON サマリを出す。
デコードできない一覧出力は、新しい理由トークン `listing_output_undecodable` を持つ 6 つ目の「一覧が使えない」条件として、既存の `ListingOutcome(available=False, reason=...)` から report 分岐への切り替え経路で扱う。

## 目的

- file-tasks は、タスク一覧の出力が UTF-8 としてデコードできないときも落ちずに終わり、stdout に JSON サマリを出す
- デコードできない一覧出力は、既存の「一覧が使えない」経路（`ListingOutcome(available=False, reason=...)` から report 分岐への切り替え）で扱う

## 受け入れ条件

- [ ] **AC-1**（FR3, FR5, FR8）: `task list` が終了コード 0 で UTF-8 として不正なバイト列を stdout に出す代役を `--entry-point` に渡して file-tasks を実行すると、traceback が出ず、終了コード 0 で stdout に JSON サマリが 1 つ出る。サマリは `branch="report"`、`degraded=true`、`degraded_reason="listing_output_undecodable"` で、report ファイルが書かれる。
- [ ] **AC-2**（FR1, FR3）: `list_security_tasks` を直接呼ぶと、終了コード 0 で stdout が不正な UTF-8 のとき `ListingOutcome(available=False, reason="listing_output_undecodable")` が返り、例外は出ない。
- [ ] **AC-3**（FR2）: 非ゼロ終了で stdout に不正なバイト列があるとき、理由は `listing_exit_nonzero` になる。
- [ ] **AC-4**（FR4）: 終了コード 0 で stdout が正しい UTF-8 の JSON 配列、stderr だけが不正なバイト列のとき、一覧は利用可能で `file_tasks` は filing 分岐（`branch="ntd"`）に進む。
- [ ] **AC-5**（FR7）: `TestListingUnavailableReasons` が 6 つの不能条件それぞれで report 分岐に入ることと、6 つの理由がすべて異なることを確かめ、通る。
- [ ] **AC-6**（FR6）: `ListingOutcome` の docstring が 6 つの不能条件と書かれていて、`list_security_tasks` の docstring と矛盾しない。
- [ ] **AC-7**（NFR2, NFR6）: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。

## 技術要件

### 機能要件

- **FR1: 一覧出力をバイト列で受け取る** — `em-workflow/scripts/scan-dependencies.py` の `list_security_tasks` は、`task list --type セキュリティ --format json` を起動するとき出力をバイト列で受け取る（`subprocess.run` に `text=True` を渡さない）。ロケールに依存しない。
- **FR2: 判定の順序** — `list_security_tasks` は次の順で判定する。
  1. `entry_point_invalid`
  2. `listing_launch_failed`（`OSError`）
  3. `listing_exit_nonzero`（非ゼロ終了。出力の中身は見ない）
  4. stdout を UTF-8 で厳密にデコード
  5. `listing_output_not_json`
  6. `listing_output_not_array`
- **FR3: デコード失敗の新しい理由トークン** — 終了コード 0 で、stdout が UTF-8 として厳密にデコードできないとき、`list_security_tasks` は `ListingOutcome(available=False, reason="listing_output_undecodable")` を返す。`UnicodeDecodeError` は `list_security_tasks` の外に出さない。
- **FR4: stderr はデコードしない** — `list_security_tasks` は stderr をデコードしない。stderr に UTF-8 として不正なバイト列があっても、終了コード 0 で stdout が正しい UTF-8 の JSON 配列なら、一覧は利用可能（`available=True`）として扱う。
- **FR5: report 分岐への切り替え** — `listing_output_undecodable` のとき、`file_tasks` は既存の degraded report 分岐に入る。サマリは `branch="report"`、`degraded=true`、`degraded_reason="listing_output_undecodable"` で、12 個のキーの形は変えない。CLI（file-tasks サブコマンド）は stdout に JSON サマリを 1 つ出して終了コード 0（`EXIT_OK`）で終わる。
- **FR6: docstring の条件数** — `ListingOutcome` の docstring にある「一覧が使えない条件」の件数を 5 から 6 に改める。`list_security_tasks` の docstring も 6 条件と整合させる。
- **FR7: 不能条件の区別性テストを 6 条件にする** — `tests/test_sca_task_filing.py` の `TestListingUnavailableReasons`（各不能条件が別々の理由になることの確認）を、`listing_output_undecodable` を含む 6 条件に広げ、6 つの理由がすべて異なることを確かめる。同じファイル内の「five」「other four」という記述も 6 条件に合わせる。
- **FR8: 再発を検出するテスト** — `task list` に UTF-8 として不正なバイト列を stdout へ出す代役の実行ファイルを用意し、file-tasks を実行して、traceback で落ちず stdout に JSON サマリが出ること、`degraded_reason` が `listing_output_undecodable` であることを確かめるテストを追加する。

### 非機能要件

- **NFR1: 変更範囲** — 変更は `list_security_tasks` の一覧取得と、その docstring・`ListingOutcome` の docstring・関係するテストに限る。`resolve_main_worktree_root` と、`task create` / `task update` を起動する `_run_entry_point_with_references` の `subprocess.run`（`text=True`）は変えない。
- **NFR2: 既存の理由トークンを変えない** — 既存の 5 つの理由トークン（`entry_point_invalid` / `listing_launch_failed` / `listing_exit_nonzero` / `listing_output_not_json` / `listing_output_not_array`）の名前と、それぞれが出る条件は変えない。
- **NFR3: サマリに不正なバイト列や出力の中身を載せない** — サマリの `degraded_reason` は固定のトークンだけで、一覧出力の中身やデコード例外の文言を含まない。
- **NFR4: テストは標準ライブラリだけ** — 追加・変更するテストは標準ライブラリの `unittest` だけを使い、外部のタスクシステムには接続しない。代役の実行ファイルは不正なバイト列を `sys.stdout.buffer` などでバイトのまま書き出す。
- **NFR5: version は変えない** — em-workflow の version は変えない（main への push 時に Actions が patch を上げる）。
- **NFR6: 既存テストと不変条件チェックが通る** — `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。`test-docs/**/*.tests.yaml` に記録されたテスト ID も引き続き解決できる。

## 実装方針

### 一覧が使えない条件（6 条件）

| 順 | 理由トークン | 条件 |
|----|--------------|------|
| 1 | `entry_point_invalid` | 既存の条件のまま（NFR2） |
| 2 | `listing_launch_failed` | 起動で `OSError` |
| 3 | `listing_exit_nonzero` | 非ゼロ終了（出力の中身は見ない） |
| 4 | `listing_output_undecodable` | 終了コード 0 で、stdout が UTF-8 として厳密にデコードできない（新規） |
| 5 | `listing_output_not_json` | 既存の条件のまま（NFR2） |
| 6 | `listing_output_not_array` | 既存の条件のまま（NFR2） |

### データの流れ

```
task list（バイト列で受け取る）
  → 終了コードを確かめる（非ゼロ → listing_exit_nonzero）
  → stdout だけを UTF-8 で厳密にデコード（失敗 → listing_output_undecodable）
  → JSON として読む（失敗 → listing_output_not_json）
  → 配列か確かめる（違う → listing_output_not_array）
  → ListingOutcome(available=True)
stderr はデコードしない
```

`available=False` のとき、`file_tasks` は既存の degraded report 分岐に入り、サマリの `degraded_reason` に理由トークンを入れる。

### 変更対象

- `em-workflow/scripts/scan-dependencies.py` — `list_security_tasks` の一覧取得、`list_security_tasks` と `ListingOutcome` の docstring
- `tests/test_sca_task_filing.py` — `TestListingUnavailableReasons` と、同じファイル内の「five」「other four」という記述
- FR8 の再発検出テスト

変更しないもの（NFR1）:

- `resolve_main_worktree_root`
- `_run_entry_point_with_references` の `subprocess.run`（`text=True`）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-listing-undecodable-output/**`
- `test-docs/sca-listing-undecodable-output/**`

`feature-docs/sca-listing-undecodable-output/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-listing-undecodable-output/**` covers
`test-docs/sca-listing-undecodable-output/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-listing-undecodable-output/` directory at all; the declared
`test-docs/sca-listing-undecodable-output/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## テストシナリオ

### 単体テスト

- [ ] **TS-2**（AC-2 / FR1, FR3）: 関数直呼び。`list_security_tasks` に TS-1 と同じ代役を渡し、`available=False` と `reason=listing_output_undecodable` を確かめる。
- [ ] **TS-3**（AC-3 / FR2）: 非ゼロ終了 + 不正バイトの stdout で `listing_exit_nonzero` になることを確かめる。
- [ ] **TS-5**（AC-2 / FR1, FR3）: UTF-8 として符号化されたサロゲート（例: `b'\xed\xa0\x80'`）を含む stdout が `listing_output_undecodable` になることを確かめる（厳密デコードの確認）。
- [ ] **TS-6**（AC-5 / FR7）: `TestListingUnavailableReasons` の区別性テストに 6 条件目（不正 UTF-8 の stdout、終了コード 0）を足し、理由の集合の大きさが 6 であることを確かめる。
- [ ] **TS-7**（AC-6 / FR6）: `ListingOutcome` の docstring に 6 条件が書かれていることを確かめる。

### 結合テスト

- [ ] **TS-1**（AC-1 / FR3, FR5, FR8）: CLI 再現。代役が `task list` で `b'\xff\xfe['` のような不正な UTF-8 を stdout に書き終了コード 0 で終わる。`scan-dependencies.py file-tasks` を subprocess で実行し、終了コード 0、stdout が JSON として読め、`degraded_reason=listing_output_undecodable`、stderr に `Traceback` が無いことを確かめる。
- [ ] **TS-4**（AC-4 / FR4）: 終了コード 0、stdout は `"[]"`、stderr に不正バイトのとき `branch=ntd` で `filed_packages` に対象パッケージが入ることを確かめる。

### 回帰確認

- [ ] **AC-7**（NFR2, NFR6）: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

### エッジケース

- [ ] 非ゼロ終了で stdout が不正なバイト列 → `listing_exit_nonzero`（TS-3）
- [ ] stderr だけが不正なバイト列で stdout は正しい JSON 配列 → 一覧は利用可能（TS-4）
- [ ] UTF-8 として符号化されたサロゲートを含む stdout → `listing_output_undecodable`（TS-5）

## セキュリティ上の考慮

- **入力の扱い:** サマリの `degraded_reason` は固定のトークンだけで、一覧出力の中身やデコード例外の文言を含まない（NFR3）。

## エラー処理

- `UnicodeDecodeError` は `list_security_tasks` の外に出さず、`ListingOutcome(available=False, reason="listing_output_undecodable")` に変える（FR3）。
- `listing_output_undecodable` のとき、CLI は stdout に JSON サマリを 1 つ出して終了コード 0（`EXIT_OK`）で終わる（FR5）。

## 前提

- **A1**（`listing.undecodable.reason-token`、batch-decision-table（Codex consultation）、可逆）: デコードできない一覧出力には新しい理由トークン `listing_output_undecodable` を割り当て、6 つ目の不能条件とする。`ListingOutcome` / `list_security_tasks` の docstring の件数と、不能条件の区別性テストを 6 条件に合わせる。
- **A2**（`listing.undecodable.decode-scope`、batch-decision-table（Codex consultation）、可逆）: 一覧はバイト列で受け取り、終了コードを確かめた後に stdout だけを UTF-8 で厳密にデコードする。stderr はデコードしない。非ゼロ終了は出力の中身に関係なく `listing_exit_nonzero`。stderr だけが不正でも stdout が正しければ一覧は利用可能。ロケールに依存しない。
- **A3**（既存テスト、可逆）: 既存の 5 つの理由トークンの名前と条件、`file_tasks` のサマリの 12 キーの形は既存テスト（`tests/test_sca_task_filing.py`、`tests/test_sca_file_tasks_oserror.py`、`tests/test_sca_file_tasks_unexpected_exceptions.py`）で固定されていて、変えない。

## 完了条件

- [ ] FR1〜FR8 が実装され、テストされている
- [ ] TS-1〜TS-7 が通る
- [ ] AC-1〜AC-7 を満たす

## 未解決事項

なし

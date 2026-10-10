# Feature: file-tasks-temp-unlink-oserror

## 概要

`em-workflow/scripts/scan-dependencies.py` の file-tasks で、一時参照ファイルの削除に失敗したときの扱いを変える。削除時の `OSError` は stderr に出すだけにし、entry point の起動結果と終了ステータスで決まる結果を上書きしない。

## 目的

- file-tasks の成否を、entry point の起動結果と終了ステータスだけで決める。一時参照ファイルの削除失敗で、起票・追記に成功したパッケージが失敗として記録され、残りのパッケージが打ち切られることをなくす。
- receipt・R6 の報告・batch の最終結果が、起票済みのパッケージを未起票と表示する食い違いをなくす。

## 受け入れ条件

- [ ] **AC-1**（FR1, FR3, FR7）: 一時ファイル削除が `OSError` を送出する状態で、成功する entry point に対して `file_tasks` を 3 パッケージで実行すると、create 経路では `filed_packages`、append 経路では `appended_packages` に 3 件すべてが入り、`failed_package` / `failure_reason` が `None`、`unattempted_packages` が `[]` になる。
- [ ] **AC-2**（FR1, FR2, FR3, FR6）: 一時ファイル削除が `OSError` を送出する状態で、`create_security_task` と `append_security_task_references`（exit 0 の entry point）は例外を送出せずに戻り、削除エラーの文言は stderr に出て stdout には出ない。
- [ ] **AC-3**（FR4）: `subprocess.run` が `OSError` を送出し、かつ削除も `OSError` を送出するとき、ヘルパは `EntryPointError` を送出し、その `__cause__` は起動時の `OSError`（削除時の `OSError` ではない）である。
- [ ] **AC-4**（FR4）: entry point が非ゼロで終了し、かつ削除が `OSError` を送出するとき、ヘルパは既存どおり非ゼロ終了の `EntryPointError`（entry point の stderr を含み、`__cause__` は `None`）を送出する。
- [ ] **AC-5**（FR5）: `_run_entry_point_with_references` と `create_security_task` の docstring に、削除の `OSError` が伝播する／`EntryPointError` になるという記述が残っていない。
- [ ] **AC-6**（NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` が全件通る。

## 技術要件

### 機能要件

- **FR1:** 一時参照ファイル削除の OSError を握る — `em-workflow/scripts/scan-dependencies.py` の `_run_entry_point_with_references` は、`finally` 内の一時参照ファイル削除（`Path(refs_path).unlink(missing_ok=True)`）を `try/except OSError` で囲む。削除で `OSError` が起きても、その `OSError` を呼び出し元へ送出しない。
- **FR2:** 削除エラーは stderr にだけ出す — FR1 で捕まえた削除エラーは、`OSError` の文言を含む形で stderr に出す。stdout（file-tasks の JSON サマリー）、サマリーの各キー、`EntryPointError` のメッセージには入れない。
- **FR3:** 完了した結果を上書きしない — `subprocess.run` が戻った後に削除が失敗した場合、`_run_entry_point_with_references` はその `CompletedProcess` を正常に返す。exit 0 なら `create_security_task` / `append_security_task_references` は例外を送出せずに戻り、`file_tasks` はそのパッケージを `filed_packages` / `appended_packages` に入れて次のパッケージへ進む。
- **FR4:** 先に起きたエラーを上書きしない — 起動時の `OSError`（`subprocess.run` が送出）の後に削除も失敗した場合、呼び出し元へ伝わるのは起動時の `OSError` のままで、`create_security_task` / `append_security_task_references` が送出する `EntryPointError` の `__cause__` はその起動時 `OSError` である。非ゼロ終了の後に削除が失敗した場合も、既存の非ゼロ終了の `EntryPointError`（メッセージに entry point の stderr を含み、`__cause__` は `None`）がそのまま送出される。
- **FR5:** docstring の修正 — `_run_entry_point_with_references` と `create_security_task` の docstring から、一時ファイル削除の `OSError` が伝播する／`EntryPointError` に変換されるという記述を外し、削除エラーは stderr に出すだけで結果を変えないことを示す記述にする。
- **FR6:** 既存テストの書き換え — `tests/test_sca_file_tasks_oserror.py` の `TestFilingHelpersConvertOsErrors.test_temp_file_removal_failure_becomes_entry_point_error` を書き換え、削除で `OSError` が起きても create / append の両ヘルパが例外を送出せずに戻ること、削除エラーの文言が stderr にだけ出ることを確かめる。
- **FR7:** file_tasks レベルの再発検出テスト — 一時ファイル削除が `OSError` を送出する状態で、成功する stand-in entry point に対して `file_tasks` を複数パッケージで実行するテストを追加する。create 経路と append 経路の両方で、全パッケージが `filed_packages` / `appended_packages` に入り、`failed_package` と `failure_reason` が `None`、`unattempted_packages` が空であることを確かめる。

### 非機能要件

- **NFR1:** 標準ライブラリのみ — `scan-dependencies.py` とテストは標準ライブラリだけを使う（`TestDocstringAndModuleDiscipline.test_only_standard_library_imports` を維持）。
- **NFR2:** stdout の形を変えない — file-tasks の stdout はこれまでどおり JSON サマリー 1 件だけで、12 キーの形を変えない。
- **NFR3:** 既存テストが通る — `python3 -m unittest discover -s tests` の既存テストがすべて通る。
- **NFR4:** version を変えない — em-workflow の version は変更しない（`.claude/rules/core-plugin-version-bump.md`）。

## 前提

- **A-1:** stderr に出す削除エラーの文言の書式（接頭辞など）は固定しない。1 回の削除失敗につき、`OSError` の文言を含む出力を stderr に出す。
- **A-2:** 削除の再試行はしない。削除に失敗した一時ファイルは残ることを許容する。
- **A-3:** `_write_references_tempfile` の書き込み失敗時の後始末（`contextlib.suppress(OSError)` で黙って握る）は変更しない。
- **A-4:** 削除の `try/except` で捕まえるのは `OSError` だけとし、それ以外の例外の扱いは変えない。`FileNotFoundError` はこれまでどおり `missing_ok=True` で吸収する。
- **A-5:** 書き換え対象のテストメソッドは、新しい挙動に合う名前へ改名してよい。改名する場合は、旧テスト ID（`tests.test_sca_file_tasks_oserror.TestFilingHelpersConvertOsErrors.test_temp_file_removal_failure_becomes_entry_point_error`）を参照している `test-docs/**/*.tests.yaml` の記録が、`tests/test_tests_yaml_id_resolution.py` で解決できない状態にならないようにする。
- **A-6:** テストモジュール `tests/test_sca_file_tasks_oserror.py` の module docstring と `TestFilingHelpersConvertOsErrors` の class docstring にある「削除エラーも `EntryPointError` になる」旨の記述も、新しい挙動に合わせて直す。
- **A-7:** `append_security_task_references` の docstring（「Same pre/postcondition as create_security_task ... launch, file or exit failure is EntryPointError」）は、削除を名指ししていないため必須の修正対象ではない。`create_security_task` の docstring 修正と矛盾する場合だけ合わせて直す。

## 実装方針

### 処理の流れ

```
file_tasks
  → create_security_task / append_security_task_references
    → _run_entry_point_with_references
        subprocess.run（entry point 起動）
        finally: 一時参照ファイル削除
                 OSError → stderr に出す（送出しない）
    ← CompletedProcess / 起動時 OSError
  ← exit 0: 正常に戻る
    非ゼロ終了: 非ゼロ終了の EntryPointError（__cause__ は None）
    起動時 OSError: EntryPointError（__cause__ は起動時 OSError）
```

### 対象ファイル

```
em-workflow/scripts/scan-dependencies.py   # FR1〜FR5
tests/test_sca_file_tasks_oserror.py       # FR6、A-5、A-6
```

### デザイン

design step は skipped（UI を持たない、スクリプト内の例外処理の修正とテスト追加のみのため）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/file-tasks-temp-unlink-oserror/**`
- `test-docs/file-tasks-temp-unlink-oserror/**`

`feature-docs/file-tasks-temp-unlink-oserror/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/file-tasks-temp-unlink-oserror/**` covers `test-docs/file-tasks-temp-unlink-oserror/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/file-tasks-temp-unlink-oserror/` directory at all; the declared
`test-docs/file-tasks-temp-unlink-oserror/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## テストシナリオ

### ユニットテスト

- [ ] **TS-2**（FR1, FR2, FR3, FR6）: 書き換えた `TestFilingHelpersConvertOsErrors` の削除失敗テストで、`os.unlink` を patch した状態で両ヘルパを stderr を捕捉して呼び、例外なしで戻ること・捕捉した stderr に `OSError` の文言が含まれることを確かめる（AC-2）。
- [ ] **TS-3**（FR4）: `subprocess.run` と `os.unlink` の両方を別々の `OSError` で patch し、`EntryPointError` の `__cause__` が `subprocess.run` 側の `OSError` であることを確かめる（AC-3）。
- [ ] **TS-4**（FR4）: stand-in を exit 1 に設定し `os.unlink` を patch して、既存の非ゼロ終了の `EntryPointError` が送出されることを確かめる（AC-4）。

### 結合テスト

- [ ] **TS-1**（FR1, FR3, FR7）: `os.unlink` を `OSError(EIO)` を送出するよう patch し、stand-in entry point で `file_tasks` を create 経路・append 経路の 3 パッケージで実行し、サマリーが全件成功の形になることを確かめる（AC-1）。後始末では本物の unlink で残った一時ファイルを消す。

### 回帰テスト

- [ ] **TS-5**（NFR1, NFR2, NFR3）: 全テストスイートを実行する（AC-6）。

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

## 未解決事項

なし（`status: tbd` の要件はない）。

## 参照

- 対象スクリプト: `em-workflow/scripts/scan-dependencies.py`
- 対象テスト: `tests/test_sca_file_tasks_oserror.py`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`

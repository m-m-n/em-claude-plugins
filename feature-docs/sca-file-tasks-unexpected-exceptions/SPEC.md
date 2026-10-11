# Feature: sca-file-tasks-unexpected-exceptions

## Overview

file-tasks の起票ヘルパが OSError 以外の例外（NUL を含む argv で `subprocess.run` が送出する ValueError、UnicodeEncodeError）を受けたとき、トレースバックで落ちずに既存の break-and-return 経路で終了し、JSON サマリを 1 つ出力するようにする。UTF-8 にエンコードできない package / advisory id / 文字列の severity を持つ finding は、起票ループの前で落とさずにスキップして記録し、他の finding は処理を続ける。どちらの再現入力についても回帰テストで再発を検出する。

## Objectives

- 起票ヘルパが OSError 以外の例外（`subprocess.run` が argv 中の NUL で送出する ValueError、UnicodeEncodeError）を送出したとき、file-tasks は既存の break-and-return 経路で終了し、トレースバックではなく JSON サマリを 1 つ出力する。
- package・advisory id・文字列の severity のいずれかを UTF-8 にエンコードできない finding があっても、file-tasks は起票ループの前で落ちない。その finding はスキップして記録し、他の finding はすべて処理する。
- 回帰テストで、どちらの再現入力（パッケージ名に NUL、advisory id に lone surrogate）の再発も検出する。

## User Stories

### US1: 起票ヘルパの想定外例外でも JSON サマリで終了する
file-tasks の利用者として、起票ヘルパが ValueError や UnicodeEncodeError を送出しても、トレースバックではなく JSON サマリ 1 つで実行が終わってほしい。

**Acceptance Criteria:**
- [ ] AC1: 実 CLI、create 経路、3 パッケージ `[pkg-a, <NUL を含むパッケージ>, pkg-c]`、空のリスティング。終了コードは 0、stderr に `Traceback` が無く、stdout はちょうど 1 つの JSON オブジェクトで 12 キーのサマリと一致する（`filed_packages=[pkg-a]`、`failed_package=<NUL パッケージ>`、`failure_reason=task_create_failed`、`unattempted_packages=[<NUL パッケージ>, pkg-c]`）。スタンドインが記録する create 呼び出しは 1 回（pkg-a）だけで、pkg-c は起動されない。stderr に `task_create_failed` が含まれる。（FR1, FR2, FR5）
- [ ] AC2: append 経路、3 パッケージそれぞれに未完了タスクがあり、リスティング上の pkg-b のタスク id に NUL が含まれる。結果は `appended_packages=[pkg-a]`、`failed_package=pkg-b`、`failure_reason=task_update_failed`、`unattempted_packages=[pkg-b, pkg-c]`。スタンドインに届く更新は pkg-a のものだけ。（FR1, FR2）
- [ ] AC3: 一時ファイル書き込み関数が 2 回目の呼び出しで UnicodeEncodeError を送出すると、create 経路・append 経路の両方で、既存の OSError 書き込み失敗ケースと同じサマリになる（`failed_package=pkg-b`、`unattempted_packages=[pkg-b, pkg-c]`、`failure_reason` は経路ごと）。（FR1, FR2）
- [ ] AC4: ヘルパ単体、両ヘルパについて。書き込み関数または `subprocess.run` が送出した ValueError と UnicodeEncodeError は、それぞれ `__cause__` がその例外オブジェクトそのものである EntryPointError としてヘルパから出る。同じ箇所で送出された TypeError は TypeError のまま伝播する。（FR1）
- [ ] AC5: lone surrogate を含む参照行で `_write_references_tempfile` を呼ぶと UnicodeEncodeError が送出され、一時ファイルは残らない。既存の OSError ケースは引き続き生の OSError を送出し、ファイルは残らない。（FR3）

### US2: エンコードできない finding をスキップして処理を続ける
file-tasks の利用者として、UTF-8 にエンコードできない文字列を含む finding があっても、その finding だけがスキップ・記録され、他の finding は処理されてほしい。

**Acceptance Criteria:**
- [ ] AC6: 実 CLI、複数パッケージのバッチで、1 つの finding の advisory id に lone surrogate を含む（再現入力）。終了コードは 0、`Traceback` が無く、stdout はちょうど 1 つの JSON オブジェクト。その finding は入力上の position と新しい固定の理由とともに `malformed_findings` に現れる。理由はタイトル契約の理由と異なり、finding のテキストを含まない。他のパッケージはすべて起票され、`failed_package` と `failure_reason` は null、`unattempted_packages` は空、stdout に surrogate は含まれない。（FR4）
- [ ] AC7: package 中の lone surrogate、文字列の severity 中の lone surrogate にも同じ除外が適用され、report 分岐（entry point が None）でも同様。レポートが書き出され、サマリが返り、その finding は `malformed_findings` に記録される。（FR4）

### US3: 回帰テストで再発を検出する
file-tasks の保守者として、2 つの再現入力の再発を回帰テストで検出したい。

**Acceptance Criteria:**
- [ ] AC8: `python3 -m unittest discover -s tests` が通る（`tests/test_sca_file_tasks_oserror.py` は無変更）。`python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。（FR6, NFR3, NFR4）

## Technical Requirements

### Functional Requirements
- **FR1:** 起票ヘルパの OSError / ValueError 変換 — `create_security_task` と `append_security_task_references` は、一時参照ファイルの書き込み中またはエントリポイントの起動中に OSError または ValueError（サブクラスの UnicodeEncodeError を含む）が送出されたとき、EntryPointError を送出する。元の例外オブジェクトは `__cause__` に保持する。それ以外の例外型（TypeError など）は変換せず、従来どおり伝播させる。非ゼロ終了による EntryPointError（cause なし）と、エントリポイントの妥当性の事前条件は変更しない。
- **FR2:** 変換されたヘルパ失敗の break-and-return 経路 — FR1 で変換されたヘルパ失敗は、既存の経路で起票ループを終了させる。`failed_package` は起票中のパッケージ。`failure_reason` は create 経路で `task_create_failed`、append 経路で `task_update_failed`。`unattempted_packages` は失敗したパッケージと、グループ順でそれ以降のすべてのパッケージ。失敗前に起票・追記されたパッケージは `filed_packages` / `appended_packages` に残る。例外テキストは既存ループと同じく stderr に出力する。file-tasks は stdout にちょうど 1 つの JSON オブジェクトを出力し、終了コード 0 で終わる。
- **FR3:** 一時ファイル削除の対象範囲を同じ範囲に広げる — `_write_references_tempfile` の書き込みが OSError または ValueError（UnicodeEncodeError を含む）で失敗したとき、例外を伝播させる前に書きかけの一時ファイルを削除する。書き込み関数自体は引き続き生の例外を送出し、EntryPointError は送出しない。起動後の一時ファイル削除の挙動は変更しない（削除エラーは stderr にのみ出し、結果は変えない。削除は 1 回だけ試みる。既に存在しないファイルは何も出さずに受け入れる）。
- **FR4:** エンコードできない finding テキストを malformed としてスキップする — `group_findings_by_package` は、復元した package、復元した advisory_id、または severity（文字列の場合）のいずれかを UTF-8 にエンコードできない finding をスキップする。その finding は `malformed_findings` に `{position, reason}` として記録する。reason は新しい固定文字列で、既存のタイトル契約の理由（`MALFORMED_FINDING_REASON`）とは別のものとし、finding の内容から生成しない。この判定は `truncate_untrusted` の前に行う。他の finding は通常どおりグループ化・処理する。グループ化は共通なので、ntd 分岐、report 分岐、degraded report 分岐のすべてに適用される。
- **FR5:** パッケージ名の NUL は break-and-return でバッチを終了させる — NUL を含むパッケージ名を事前に除外しない。create 経路で `subprocess.run` が ValueError を送出し、`create_security_task` がそれを EntryPointError に変換する（FR1）。実行は `failed_package` = そのパッケージ、`failure_reason` = `task_create_failed`、`unattempted_packages` = そのパッケージとそれ以降のすべてのパッケージ、で終了する。
- **FR6:** docstring を広げた挙動に合わせる — `_write_references_tempfile`、`_run_entry_point_with_references`、`create_security_task`、`append_security_task_references`、`group_findings_by_package`、`file_tasks` の docstring は FR1〜FR5 の挙動を記述する。`MALFORMED_FINDING_REASON` のコメントは、それが唯一の malformed 理由であるとは書かない。

### Non-Functional Requirements
- **NFR1 - サマリ契約と出力内容:** file-tasks のサマリはちょうど 12 キーを保つ。`failure_reason` は `task_create_failed` / `task_update_failed` のいずれかのまま。例外テキスト、advisory 由来・package 由来のテキストは `failure_reason` にも `malformed_findings[].reason` にも出さない。例外テキストは stderr にのみ出す。
- **NFR2 - 標準ライブラリのみ:** `scan-dependencies.py` と新しいテストモジュールは標準ライブラリのみを使う。
- **NFR3 - 既存テストの無変更での通過:** `tests/test_sca_file_tasks_oserror.py` と他のすべての既存テストモジュールが、変更なしで通る。
- **NFR4 - docstring の文言制約:** `_run_entry_point_with_references`、`create_security_task`、`append_security_task_references` の docstring で、`remov|delet|unlink`（大文字小文字を区別しない）にマッチする文に `EntryPointError` も `propagat` も含めない。前 2 つは、`stderr` と `unchanged` の両方を含む削除についての文を保つ。`file_tasks` の docstring は `Five keys are ADDED` とそれに続くバッククォート付きの 5 つのキー名を保つ。
- **NFR5 - バージョン据え置き:** この機能ではプラグインの version を変更しない。

## Implementation Approach

### Architecture

**System Architecture:**
```
file-tasks (CLI)
  └─ file_tasks
       ├─ group_findings_by_package   … FR4: エンコード不能な finding を malformed_findings へ
       └─ 起票ループ（パッケージのグループ順）
            ├─ create_security_task             … FR1: OSError / ValueError → EntryPointError
            └─ append_security_task_references  … FR1: OSError / ValueError → EntryPointError
                 └─ _run_entry_point_with_references
                      ├─ _write_references_tempfile  … FR3: 失敗時に一時ファイル削除、生の例外を送出
                      └─ subprocess.run
```

**Component Diagram:**
```
group_findings_by_package ──(グループ)──> 起票ループ ──> create / append ヘルパ
        │                                     │                │
        └─> malformed_findings                └─ EntryPointError を受けて break-and-return（FR2）
```

### Data Flow

```
findings → group_findings_by_package ─┬─ エンコード不能 → malformed_findings {position, reason}
                                      └─ 正常 → 起票ループ → ヘルパ → 一時ファイル書き込み → subprocess.run
ヘルパ内 OSError / ValueError → EntryPointError(__cause__=元の例外) → ループ終了
  → failed_package / failure_reason / unattempted_packages を設定 → stderr に例外テキスト
  → stdout に 12 キーの JSON サマリ 1 つ、終了コード 0
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `tests/test_sca_file_tasks_oserror.py`: 変更せずに通過させる既存の回帰テスト。
- `em-workflow/scripts/check-plugin-invariants.py`: AC8 で通過を確認する。

**External Dependencies:**
- なし（標準ライブラリのみ）。

### File Structure

```
scan-dependencies.py                                  # FR1〜FR6 の変更対象
tests/
├── test_sca_file_tasks_oserror.py                    # 変更しない
└── test_sca_file_tasks_unexpected_exceptions.py      # 新規: 回帰テスト
```

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を示す。上記の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は既定で、上記の機能固有のパスに加えて、ワークフローが生成する次の 2 エントリを宣言する。

- `feature-docs/sca-file-tasks-unexpected-exceptions/**`
- `test-docs/sca-file-tasks-unexpected-exceptions/**`

`feature-docs/sca-file-tasks-unexpected-exceptions/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する成果物を含む。これらは各フェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、規則は再掲しない。

`test-docs/sca-file-tasks-unexpected-exceptions/**` はタスクごとのテスト記録 `test-docs/sca-file-tasks-unexpected-exceptions/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、規則は再掲しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことをもって外したとはみなさない。外すことは意図的で明示的な絞り込みである。

この宣言は上位集合（SUPERSET）の宣言である。検証時に観測される実際の変更集合は、宣言集合と等しい必要はなく、宣言集合に含まれていればよい。implement タスクを生成しない機能では `test-docs/sca-file-tasks-unexpected-exceptions/` ディレクトリ自体が生成されないが、その場合も宣言した `test-docs/sca-file-tasks-unexpected-exceptions/**` エントリは正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

新しい回帰テストは `tests/test_sca_file_tasks_unexpected_exceptions.py` に置く。

### Unit Tests
- [ ] TS2（AC2 / FR1, FR2）: 3 件の未完了タスクのリスティング（pkg-b の id に NUL を含む）を与え、スタンドインに対して `file_tasks` をプロセス内で呼ぶ - サマリが AC2 のとおりで、記録された更新が pkg-a のものだけである。
- [ ] TS3（AC3 / FR1, FR2）: `_write_references_tempfile` を 2 回目の呼び出しで UnicodeEncodeError を送出するテストダブルに置き換え、create 経路と append 経路で `file_tasks` をプロセス内で呼ぶ - サマリが AC3 のとおりである。
- [ ] TS4（AC4 / FR1）: `_write_references_tempfile`、続いて別途 `subprocess.run` を、ValueError / UnicodeEncodeError / TypeError を送出するようにパッチする - 前 2 つでは両ヘルパが `__cause__` にその例外オブジェクトそのものを持つ EntryPointError を送出し、TypeError はそのまま伝播する。
- [ ] TS5（AC5 / FR3）: `NamedTemporaryFile` をラップして作成された一時ファイル名を記録しつつ、`['\ud800 (high)']` で `_write_references_tempfile` を直接呼ぶ - UnicodeEncodeError が送出され、呼び出し後にそのファイルが存在しない。
- [ ] TS7（AC7 / FR4）: package、advisory id、文字列の severity にそれぞれ lone surrogate を入れて `group_findings_by_package` を直接呼ぶ - それぞれが malformed として記録される。entry point を None（一時 git リポジトリ）とし surrogate を含む finding で `file_tasks` を呼ぶ - レポートのパスが返り、その finding が記録される。

### Integration Tests
- [ ] TS1（AC1 / FR1, FR2, FR5）: create 経路の finding 3 件（2 つ目のパッケージ名に `\u0000` を findings ファイル中で JSON エスケープして含む）で、スタンドインのエントリポイントに対して CLI をサブプロセスとして実行する - 終了コード、`Traceback` が無いこと、stdout が JSON 1 つであること、サマリの完全一致、スタンドインの呼び出しログを確認する。
- [ ] TS6（AC6 / FR4）: 2 つ目の finding の advisory id を JSON エスケープした `\ud800` とした 3 件の finding で CLI をサブプロセスとして実行する - 終了コード 0、stdout が JSON 1 つ、`filed_packages` が他の 2 パッケージ、`malformed_findings == [{position: 1, reason: <新しい固定の理由>}]`、その理由が `sd.MALFORMED_FINDING_REASON` と異なることを確認する。
- [ ] TS8（AC8 / FR6, NFR3, NFR4）: リポジトリルートで `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` を実行する - どちらも通る。

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 未検出
- [ ] 既存の E2E テストが退行なく通る

### Edge Cases
- [ ] ヘルパ内で送出された TypeError は EntryPointError に変換されず、そのまま伝播する（FR1）。
- [ ] 非ゼロ終了による EntryPointError（cause なし）は従来どおり（FR1）。
- [ ] 起動後の一時ファイル削除のエラーは stderr にのみ出て結果を変えない。削除は 1 回だけ試み、既に存在しないファイルは何も出さずに受け入れる（FR3）。
- [ ] NUL を含むパッケージ名は事前に除外せず、create 経路で break-and-return により終了する（FR5）。
- [ ] severity のエンコード可否判定は severity が文字列の場合に行う（FR4）。
- [ ] エンコード不能な finding の除外は ntd 分岐、report 分岐、degraded report 分岐のすべてに適用される（FR4）。

### Performance Tests

該当なし。

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 該当なし。
- **Input Validation:** 復元した package、復元した advisory_id、文字列の severity の UTF-8 エンコード可否を、`truncate_untrusted` の前に `group_findings_by_package` で判定する（FR4）。
- **Data Protection:** 例外テキスト、advisory 由来・package 由来のテキストは `failure_reason` と `malformed_findings[].reason` に出さない。例外テキストは stderr にのみ出す（NFR1）。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| `task_create_failed` | create 経路で起票ヘルパが EntryPointError を送出した（FR1 で変換された OSError / ValueError を含む） | 該当なし | `failure_reason` に設定。例外テキストは stderr のみ |
| `task_update_failed` | append 経路で起票ヘルパが EntryPointError を送出した（FR1 で変換された OSError / ValueError を含む） | 該当なし | `failure_reason` に設定。例外テキストは stderr のみ |
| 新しい固定の malformed 理由 | finding の package / advisory_id / 文字列の severity が UTF-8 にエンコードできない（FR4） | 該当なし | `malformed_findings[].reason` に設定。`MALFORMED_FINDING_REASON` とは別の固定文字列 |

### Error Flow

```
ヘルパ内で OSError / ValueError 発生 → EntryPointError(__cause__=元の例外) に変換
  → 起票ループで捕捉 → stderr に例外テキスト → failed_package / failure_reason / unattempted_packages を設定
  → stdout に JSON サマリ 1 つ、終了コード 0
TypeError など → 変換せず伝播
```

## Performance Optimization

### Performance Goals
- 該当なし。

### Optimization Strategies
- 該当なし。

### Caching Strategy
- 該当なし。

## Success Criteria

- [ ] すべての機能要件が実装され、テストされている
- [ ] すべてのテストシナリオが通る
- [ ] 非機能要件 NFR1〜NFR5 を満たしている
- [ ] `tests/test_sca_file_tasks_oserror.py` が変更なしで通る
- [ ] コードレビューが完了している

## Assumptions

- **as-1:** ヘルパの例外範囲 — ヘルパは一時ファイルの書き込み中またはエントリポイントの起動中に送出された OSError と ValueError（UnicodeEncodeError を含む）を、`__cause__` を保持したまま EntryPointError に変換する。TypeError などその他の型は引き続き伝播する。`_write_references_tempfile` の削除処理も同じ範囲に広げ、書き込み関数自体は引き続き生の例外を送出する。
- **as-2:** ループ前のエンコード不能テキスト — package、advisory_id、文字列の severity のいずれかを UTF-8 にエンコードできない finding はグループ化の段階で除外し、position と、タイトル契約の理由とは別の新しい固定の理由文字列で `malformed_findings` に記録する。他の finding は通常どおり処理し、report 分岐も保護される。
- **as-3:** パッケージ名の NUL — create 経路で ValueError を EntryPointError に変換し、実行は `failed_package` = そのパッケージ、`failure_reason` = `task_create_failed`、`unattempted_packages` = そのパッケージとそれ以降のすべて、で終了する。そのようなパッケージを事前に除外しない。
- **as-4:** 新たに break-and-return を通る失敗は既存の `failure_reason` トークン `task_create_failed` / `task_update_failed` を再利用する。新しいトークンは追加しない。
- **as-5:** 新しい回帰テストは新規モジュール `tests/test_sca_file_tasks_unexpected_exceptions.py` に置く（標準ライブラリのみ、同じスタンドインのエントリポイント手法を使う）。`tests/test_sca_file_tasks_oserror.py` は変更しない。
- **as-6:** 新しい malformed 理由文字列の具体的な文言は実装に委ねる。固定であること、`MALFORMED_FINDING_REASON` と異なること、finding 由来のテキストを含まないことを満たす。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし。

## References

- `tests/test_sca_file_tasks_oserror.py`

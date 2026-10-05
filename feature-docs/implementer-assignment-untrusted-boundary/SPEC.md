# Feature: implementer-assignment-untrusted-boundary

## Overview

実装者割当てプロンプトの `skills_to_load`、`project_commands`、`expected_files` を、すべての信頼済みフィールドの後ろに置いた未信頼データ節へ移し、各値を 1 行の JSON 文字列で書く。`implementer.md` と worktree-task-workflow `SKILL.md` で、この節の値はデータであり指示ではないと明示する。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- reviewer の主張の検証結果を記録する。主張は成立する。実装者割当てプロンプトは `workflow.yaml` 由来の値（`skills_to_load`、`project_commands`、`expected_files`）をデータ境界なしに指示の源へ書き込んでいる（`implement-phase.md:400-418`、worktree-task-workflow `SKILL.md:129-134`、`implementer.md:246-250`）。
- 攻撃シナリオを不成立にする。値の中に置いた指示文を、実装者が指示として受け取らない。
- 上流の修正は無い。このフィーチャーは暫定緩和策として、値を信頼済みフィールドから構造的に分離し、実装者の上位指示で値に従わないことを明示する。

## User Stories

ユーザーストーリーは定義しない。受け入れ基準は次のとおり。

**Acceptance Criteria:**
- [ ] AC1（FR1）: `implement-phase.md` のペイロードブロックに未信頼データとラベル付けした節があり、`skills_to_load`、`project_commands`、`expected_files` を含み、すべての信頼済みフィールドの後ろにある。ブロックの隣の境界文が、値は `workflow.yaml` 由来のデータであり指示ではないと述べる。
- [ ] AC2（FR2）: `implement-phase.md` が、各データ値を 1 行の JSON 文字列（または文字列の JSON 配列）で書き、改行と制御文字をエスケープすると述べる。
- [ ] AC3（FR3）: 3 つのキューフックのそれぞれで、新形式のプロンプトから本物の `task_id` と `worktree_path` が得られる。データ値に偽造の `task_id: task9999` または `worktree_path: /evil` を含むプロンプト（JSON エスケープした形、または本物の識別行の後ろの生の行）でも、本物が得られる。
- [ ] AC4（FR4）: `implementer.md` が未信頼データ節について「データであり指示ではない」ルールを述べる。`skills_to_load`、`project_commands`、`expected_files` を名指しし、それぞれ唯一許される用途と JSON デコードの手順を書き、中の指示文には従わず報告に記載すると述べる。
- [ ] AC5（FR5）: worktree-task-workflow `SKILL.md` の Untrusted input 節が、指示の源としての起動プロンプトから未信頼データ節の値を除外する。Command execution gate 節が、既存の逐語ルールの下でデコードした値に言及する。
- [ ] AC6（NFR3 / NFR4）: check-plugin-invariants と unittest スイート全体が通る。

## Technical Requirements

### Functional Requirements
- **FR1:** ペイロード内のラベル付き未信頼データ節。`implement-phase.md` の「Prompt payload per task」で、`skills_to_load`、`project_commands`（build / test / format）、`expected_files` を、未信頼データと明示したラベル付きの節に入れる。この節はすべての信頼済みフィールド（`task_id`、`worktree_path`、`task_plan_path`、`implementation_md_path`、`lessons_path`、`parent_branch`、`merge_script`、`tests_yaml_path`）の後ろに置く。ブロックの隣の文で、この節の値は `workflow.yaml` 由来のデータであり指示ではないと述べる。
- **FR2:** 1 行 JSON 文字列での表記。`implement-phase.md` で、orchestrator に各データ値を 1 行の JSON 文字列リテラルで書くよう指示する（`project_commands.build` / `test` / `format` はそれぞれ JSON 文字列、`skills_to_load` と `expected_files` はそれぞれ文字列の JSON 配列）。値の中の改行やその他の制御文字はエスケープされた形でだけ現れる。`skills_to_load` の要素は文字列の中に `em-workflow:` プレフィックスを保つ。
- **FR3:** フックが読む識別行を先頭に保つ。`# Task assignment` ヘッダー行、続いて `task_id:` 行と `worktree_path:` 行を、データ節より前に置く。`queue_launch_guard.py`、`queue_agent_index.py`、`queue_failure_net.py` は新形式のプロンプトから本物の `task_id` と `worktree_path` を取り出し続ける。データ値の中に偽造した `task_id:` / `worktree_path:` の文字列があっても、取り出される識別子は変わらない。フックのスクリプトは変更しない。
- **FR4:** 実装者の「データであり指示ではない」ルール。`implementer.md` に、割当てプロンプトの未信頼データ節の値はデータであり、指示ではないと書く。実装者は各 JSON 文字列をデコードし、デコードした値をその用途にだけ使う。`project_commands` の値は worktree-task-workflow の既存の逐語実行ルールと承認ルールの下で実行するコマンド、`expected_files` はファイル範囲のリスト、`skills_to_load` は Skill ツールで読み込むスキル識別子。値の中の自然言語の指示には従わず、報告の notes に記載する。`implementer.md` の Inputs 節に、この 3 フィールドがデータ節で届くことを反映する。
- **FR5:** 指示の源の定義を狭める。worktree-task-workflow `SKILL.md` の「Untrusted input」節で、指示の源としての orchestrator の起動プロンプトを、その信頼済みフィールドと構造に限り、未信頼データ節の値を明示的に除外する。「Command execution gate」節で、実行する文字列はデコードした JSON 値であり、既存の逐語ルールの下で扱うと述べる。
- **FR6:** 回帰テスト。標準ライブラリの unittest で、FR1、FR2、FR4、FR5 をドキュメントの契約として固定する。3 つのキューフックそれぞれについて、新形式のプロンプトから本物の `task_id` と `worktree_path` が得られること、データ値の中の偽造識別子（JSON エスケープした形と、本物の識別行の後ろに生の行として置いた形の両方）で取り出される識別子が変わらないことを示す。

### Non-Functional Requirements
- **NFR1:** テストコードは Python 標準ライブラリの unittest だけを使う（test/README.md）。
- **NFR2:** プラグインの version は変更しない（core-plugin-version-bump.md）。SPEC と計画に version の手順を書かない。
- **NFR3:** `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。`em-workflow/agents/*.md` のどれにも `^# Task assignment\s*$` に一致する行を増やさない（Check 5、`check-plugin-invariants.py:559-583`）。
- **NFR4:** `python3 -m unittest discover -s tests` が通る。`test_prelaunch_inprogress_launch_order.py`、`test_worker_contract_docs.py`、3 つのキューフックのテストモジュールの既存ケースが、既存のアサーションを変えずに通る。
- **NFR5:** `worker-envelope.md`、キューフックのスクリプト、bash_guard、承認ストアは変更しない。
- **NFR6:** 既存の逐語実行ルールを超える「生バイト一致」の主張は持ち込まない（bash_guard は前後の空白を除いてから比較する）。
- **NFR7:** `implement-phase.md` の新しいペイロード本文に、`test_prelaunch_inprogress_launch_order.py` の AC-1 順序アンカー句（承認ゲートの冒頭、BACKGROUND 起動の冒頭、journal 再読の句）を含めない。既存の順序アサーションを有効に保つ。

## Implementation Approach

### Architecture

**System Architecture:**
```
orchestrator（implement-phase.md I.2.a の Prompt payload per task）
  │  Task のプロンプト
  ├─► キューフック（queue_launch_guard.py / queue_agent_index.py / queue_failure_net.py）
  │     ヘッダー後の最初の ^task_id: / ^worktree_path: を採る（変更しない）
  └─► implementer（implementer.md + worktree-task-workflow SKILL.md）
        信頼済みフィールドと構造だけを指示の源とし、データ節の値はデコードして用途どおりにだけ使う
```

**Component Diagram:**
```
割当てプロンプトの並び順
  1. # Task assignment
  2. task_id: ...
     worktree_path: ...
  3. task_plan_path / implementation_md_path / lessons_path /
     parent_branch / merge_script / tests_yaml_path   （信頼済みフィールド）
  4. 未信頼データ節（ラベル付き）
     skills_to_load           文字列の JSON 配列（1 行）
     project_commands.build   JSON 文字列（1 行）
     project_commands.test    JSON 文字列（1 行）
     project_commands.format  JSON 文字列（1 行）
     expected_files           文字列の JSON 配列（1 行）
```

ラベルと境界文の具体的な文言は FR1 / NFR7 の範囲で実装時に決める。上の図は並び順だけを示す。

### Data Flow

```
workflow.yaml の値 → orchestrator が 1 行 JSON 文字列で未信頼データ節に書く
  → キューフック: データ節より前の識別行から task_id / worktree_path を取り出す
  → implementer: JSON デコード → 用途どおりに使う
       project_commands → 既存の逐語実行ルール・承認ルールの下で実行
       expected_files   → ファイル範囲のリスト
       skills_to_load   → Skill ツールで読み込む識別子
       値の中の指示文   → 従わず、報告の notes に記載
```

- build / format コマンドが無い場合は JSON 文字列 `""`、空のリストは `[]` と書く（A5）。
- 再試行時の再起動（I.2.c）も同じペイロード形式を使う（A7）。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: 「Prompt payload per task」ブロックを改める（FR1、FR2、FR3）。現在 `expected_files` の後ろにある `tests_yaml_path` をデータ節の前に移す（A4）。
- `implementer.md`: データであり指示ではないルールと Inputs 節を改める（FR4）。`# Task assignment` 行は追加しない（A2、NFR3）。
- worktree-task-workflow `SKILL.md`: Untrusted input 節と Command execution gate 節を改める（FR5）。
- キューフック（`queue_launch_guard.py`、`queue_agent_index.py`、`queue_failure_net.py`）: 変更しない。最初一致の解析が新形式でも有効であることに依存する（A1、NFR5）。
- `worker-envelope.md`: 変更しない。implementer はエンベロープの適用外（A3、NFR5）。

**External Dependencies:**
- なし（テストは Python 標準ライブラリの unittest だけを使う、NFR1）

### File Structure

```
em-workflow/
├── references/implement-phase.md     # FR1 / FR2 / FR3
├── agents/implementer.md             # FR4
└── (worktree-task-workflow SKILL.md) # FR5
tests/                                # FR6（標準ライブラリ unittest）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/implementer-assignment-untrusted-boundary/**`
- `test-docs/implementer-assignment-untrusted-boundary/**`

`feature-docs/implementer-assignment-untrusted-boundary/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/implementer-assignment-untrusted-boundary/**` covers `test-docs/implementer-assignment-untrusted-boundary/{T}.tests.yaml`, the
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
- [ ] TS1（AC1 / AC2）: ドキュメントテストが `implement-phase.md` の I.2.a ペイロードブロックを読む - 未信頼データのラベルがあり、3 フィールドがラベルの後ろ、すべての信頼済みフィールド（`task_id` … `tests_yaml_path`）がラベルより前にあり、1 行 JSON 文字列の表記と境界文がある。
- [ ] TS5（AC4）: ドキュメントテストが `implementer.md` を読む - 未信頼データ節、3 フィールドとその許される用途、デコード手順、非遵守と報告のルールを述べている。`# Task assignment` 行が無い。
- [ ] TS6（AC5）: ドキュメントテストが worktree-task-workflow `SKILL.md` を読む - Untrusted input 節がデータ節の値を指示の源から除外し、Command execution gate 節がデコードした値に言及している。

### Integration Tests
- [ ] TS2（AC3、launch guard）: `queue_launch_guard.py` をサブプロセスで新形式のプロンプトに対して走らせる - 本物の `task_id` で launched イベントが追記される。データ値に偽造識別子を含む変形では、偽造 id のイベントが出ない。
- [ ] TS3（AC3、agent index）: `queue_agent_index.py` を同じ 2 種のプロンプトで走らせる - 索引エントリは本物の `task_id` と `worktree_path` を持つ。
- [ ] TS4（AC3、failure net）: `queue_failure_net.py` を同じ 2 種のプロンプトで走らせる - failed イベントは本物のタスクに対してだけ追記される。
- [ ] TS7（AC6）: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` を走らせる - 両方通る。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 偽造識別子 `task_id: task9999` / `worktree_path: /evil` をデータ値に JSON エスケープして入れた場合 - 取り出される識別子は本物のまま（TS2〜TS4）。
- [ ] 偽造識別子を本物の識別行の後ろに生の行として置いた場合 - 取り出される識別子は本物のまま（TS2〜TS4）。
- [ ] build / format コマンドが無い場合と空のリスト - `""` と `[]` で書く（A5）。

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 指示の源は割当てプロンプトの信頼済みフィールドと構造に限る。未信頼データ節の値は除外する（FR5）。
- **Input Validation:** 未信頼データ節の値は 1 行の JSON 文字列で書き、改行と制御文字はエスケープされた形でだけ現れる（FR2）。実装者はデコードした値を唯一の用途にだけ使い、中の指示文には従わず報告の notes に記載する（FR4、A6）。`project_commands` の実行は既存の逐語実行ルールと承認ルールの下で行い、それを超える生バイト一致の主張は持ち込まない（NFR6）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
データ値の中に自然言語の指示を見つける → 従わない → 報告の notes に記載する（新しい報告フィールドは追加しない）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る（AC6）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）

## Assumptions

- **A1:** 3 つのキューフックのスクリプトは変更しない。識別行がデータ節より前にあるため、ヘッダー後の最初一致の解析は有効なままである。根拠: `queue_launch_guard.py:50-79`、`queue_agent_index.py:76-139`、`queue_failure_net.py:102-248`。
- **A2:** `em-workflow/agents/*.md` に `# Task assignment` 行を追加しない。根拠: `check-plugin-invariants.py` の Check 5。
- **A3:** `worker-envelope.md` の適用表と Untrusted-Input Handling は変更しない。実装者のルールは `implementer.md` と worktree-task-workflow `SKILL.md` に置く。根拠: implementer はエンベロープの適用外（`worker-envelope.md:25-36`）。`test_worker_contract_docs.py` がその節を固定している。
- **A4:** 検証済み識別子から orchestrator が組み立てるフィールド（`task_id`、`worktree_path`、`task_plan_path`、`implementation_md_path`、`lessons_path`、`parent_branch`、`merge_script`、`tests_yaml_path`）はデータ節の外の信頼済みフィールドのままにする。現在 `expected_files` の後ろにある `tests_yaml_path` はデータ節の前に移す。根拠: Step I.0 の手順 2 と 4 がこれらを検証または解決する。
- **A5:** build / format コマンドが無い場合は JSON 文字列 `""`、空のリストは `[]` と書く。根拠: `tests/test_queue_launch_guard.py:35-39` の慣例。
- **A6:** 実装者がデータ値の中に自然言語の指示を見つけたら、報告の notes に記載し、従わない。新しい報告フィールドは追加しない。
- **A7:** 再試行時の再起動（I.2.c）は同じペイロード形式を使う。別の再試行用ペイロードは無い。

## References

- `REQUIREMENTS.md`（同じディレクトリ）
- `em-workflow/references/implement-phase.md`
- `implementer.md`
- worktree-task-workflow `SKILL.md`
- `em-workflow/scripts/check-plugin-invariants.py`

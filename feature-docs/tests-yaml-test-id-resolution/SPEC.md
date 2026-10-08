# Feature: tests-yaml-test-id-resolution

## Overview

`test-docs/**/*.tests.yaml` の `acceptance_tests.*.tests` に書かれた全 ID を、unittest の標準ローダーで直接選択できる `tests.` 始まりのドット区切り ID に整理する。`tests/` に全記録の ID を検査するモジュールを新設し、通常のテスト実行で ID のずれを検出する。`em-workflow/agents/implementer.md` に記録の書き込み規則と書いた後の確認手順を追加する。

要件の詳細は `feature-docs/tests-yaml-test-id-resolution/REQUIREMENTS.md` を参照する。

## Objectives

- `test-docs/**/*.tests.yaml` の `acceptance_tests.*.tests` に書かれた全 ID を、unittest の標準ローダーで直接選択できる状態にする。
- テストの名前変更・削除で記録の ID がずれたとき、通常のテスト実行（`python3 -m unittest discover -s tests`）で検出できるようにする。
- 記録を書く側（implementer）に、プロジェクトのテスト実行コマンドで直接選択できる ID だけを書く規則を与え、再発を防ぐ。

## User Stories

該当なし（受け入れ基準は Success Criteria に記す）。

## Technical Requirements

### Functional Requirements
- **FR1:** ID 形式の統一 — このリポジトリの記録の `tests` 要素は、`tests.` で始まるドット区切りの ID に統一する。メソッド ID に加えて、unittest が直接選択できるモジュール ID（例: `tests.test_x`）とクラス ID（例: `tests.test_x.TestY`）も認める。`path::Class::method` 形式の既存 ID はドット区切り形式に書き換える。
- **FR2:** unittest 以外の記載の扱い — `tests` 要素のうち unittest の ID でないもの（別の実行器のスクリプト、説明文など）は `tests` から外す。対象を実際に検証している既存の unittest がある場合（例: destructive-guard の実行器を包む `tests/test_destructive_guard_command_substitution.py` のテスト）はその ID に置き換える。無い場合、その AC に残る ID が無ければ `tests: []` にする。外した説明は既存の `red_reason` の末尾へ追記し、既存の記述と `red_confirmed` は変えない。
- **FR3:** 古い ID の対応付けと削除 — 解決できない ID は次の順で扱う。略称はその記録内の定義から正式名を確定する（例: 記録内で定義された TBE）。名前変更・統合は git 履歴から対応先を確認する。対象を特定できるワイルドカードは実在する ID へ展開する。対応先が無い ID は削除する。変更・削除した ID ごとに、ファイル・AC・旧 ID・新 ID または削除・根拠を、`test-docs/tests-yaml-test-id-resolution/` 配下の文書として記録する。ID 整理の作業では既存の `red_confirmed` / `red_reason` を変えない（FR2 の追記を除く）。
- **FR4:** 対象フィールド — 書き換えと検査の対象は `acceptance_tests.*.tests` だけにする。`baseline_failures` / `final_failures` は書き換えない。
- **FR5:** 全件検査モジュールの新設 — `tests/` に新しいテストモジュールを追加する。`test-docs/**/*.tests.yaml` の全記録を列挙し、`acceptance_tests.*.tests` の全 ID を抽出して解決を判定する。抽出エラーと解決エラーは途中で止めず全件集め、ファイル・AC・ID・理由を付けて失敗メッセージに並べる。`tests/test_exit4_ac2_test_id_drift.py` は変更しない。
- **FR6:** 解決の判定基準 — ID が `tests.` で始まり、リポジトリルートを `sys.path` に置いた状態で、モジュール、`unittest.TestCase` の派生クラス、またはそのクラス（`TestCase` 自身を除く継承元を含む）で定義されたメソッドのどれかに解決できるとき、解決できたと判定する。そのうえで `unittest.TestLoader().loadTestsFromName` でも確認し、例外が出た場合だけでなく、`loader.errors` に記録が残った場合や `_FailedTest` が返った場合も失敗と判定する。判定の過程でテストを実行せず、解決したオブジェクトを呼び出さない。検査後に `sys.path` を元に戻す。
- **FR7:** 記録の読み取り範囲 — 抽出は対応する YAML 表記の範囲を明示したうえで行う。`tests` のブロック形式のリストと 1 行のフロー形式のリスト（`[]` を含む）、引用符付きスカラー、行末コメント、他キー（`red_reason` など）の複数行スカラー（`>` / `|`）に対応する。複数行スカラーの本文中に `tests:` や `-` で始まる行があっても ID として読まない。AC キーは `AC-n` 以外の名前（例: `D4-parser-unavailable`）も受け付ける。対応しない形式、AC キーや `tests` キーの重複、`tests` キーの欠落、`acceptance_tests` の欠落は、ファイルと AC を示して失敗させる。対応する表記の範囲は `test/README.md` に書く。
- **FR8:** 空リストと読み取り失敗の区別 — `tests: []` は正当な記録として受け入れ、全 AC が `tests: []` の記録も失敗にしない。読み取りに失敗した記録を空リストとして扱わない。検査対象の記録が 1 件も見つからない場合は失敗させる。
- **FR9:** 新しいずれの見え方 — 全件検査の失敗は記録ファイルごとに別のテスト名として現れるようにする。ある記録がすでに失敗している状態でも、別の記録に新しく不正な ID が入れば、失敗したテスト名の差分（implementer.md Step 4b の baseline との比較）に現れる。
- **FR10:** implementer.md の書き込み規則 — `em-workflow/agents/implementer.md` の Step 4c に、言語に依存しない規則を追加する。`tests` の各要素は、そのプロジェクトのテスト実行コマンドで直接選択できる ID とする。説明文・略称・ワイルドカード・実行器スクリプトのパスは書かず、説明は `red_reason` に書く。
- **FR11:** 記録を書いた後の確認 — `implementer.md` に、Step 4c で記録を書いた後に `project_commands.test` を実行し、baseline にない失敗が無いことを確認する手順を追加する。記録が原因の失敗は記録の側を直す。
- **FR12:** 他機能の記録を壊したときの扱い — `implementer.md` に次の規則を追加する。テストの名前変更・削除で他の機能やタスクの記録が全件検査に失敗するようになった場合は、その記録の ID も直す。予定の範囲外のファイル変更は `deviations` に報告する。変更範囲への追加を求める場合は、既存の AC、必要なパス、直さないと失敗する検査を示す。
- **FR13:** このリポジトリの ID 形式の記載 — `test/README.md` に、このリポジトリの記録で使う ID 形式（`tests.` で始まるドット区切り、モジュール・クラス・メソッドのどれでもよい）と、全件検査が読み取る YAML 表記の範囲（FR7）を書く。

### Non-Functional Requirements
- **NFR1:** 標準ライブラリのみ — 新しい検査モジュールは標準ライブラリだけを import する。YAML ライブラリや他のテストモジュールは import しない。
- **NFR2:** 通常のテスト実行に含める — 全件検査は `python3 -m unittest discover -s tests` で自動的に実行される。登録作業や別コマンドは要らない。
- **NFR3:** 既存テストの維持 — `tests/test_exit4_ac2_test_id_drift.py` を変更せず、通り続ける状態を保つ。この検査が固定している `test-docs/exit4-tip-argument/task0002.tests.yaml` の内容（AC ごとの ID 数、AC-2 の `red_reason` の 1 行引用符付き形式、`red_confirmed: true`）を変えない。
- **NFR4:** バージョン — em-workflow の version は変更しない。

## Implementation Approach

### Architecture

**System Architecture:**
```
python3 -m unittest discover -s tests            (NFR2)
        │
        ▼
tests/ 配下の全件検査モジュール                   (FR5)
├── 記録の列挙      test-docs/**/*.tests.yaml      (FR5, FR8)
├── ID の抽出       acceptance_tests.*.tests       (FR4, FR7, FR8)
├── 解決の判定      tests. 接頭辞 / sys.path /      (FR6)
│                   loadTestsFromName
└── 集約と報告      記録ファイルごとのテスト名      (FR5, FR9)
```

**Component Diagram:**
```
記録の列挙
  - test-docs/**/*.tests.yaml の全記録を列挙する（FR5）
  - 対象が 1 件も無ければ失敗させる（FR8）

ID の抽出
  - acceptance_tests.*.tests だけを読む（FR4）
  - FR7 の表記の範囲に対応する。範囲外の形式・重複キー・tests キー欠落・
    acceptance_tests 欠落はファイルと AC を示して失敗させる（FR7）
  - tests: [] は正当な記録として受け入れ、読み取り失敗は空リストにしない（FR8）

解決の判定
  - tests. で始まることを確認する（FR6）
  - リポジトリルートを sys.path に置き、モジュール / TestCase 派生クラス /
    そのクラス（TestCase 自身を除く継承元を含む）のメソッドへの解決を確認する（FR6）
  - loadTestsFromName でも確認し、例外・loader.errors・_FailedTest を失敗とする（FR6）
  - テストを実行せず、解決したオブジェクトを呼び出さない。検査後に sys.path を戻す（FR6）

集約と報告
  - 抽出エラーと解決エラーを途中で止めず全件集め、ファイル・AC・ID・理由を
    失敗メッセージに並べる（FR5）
  - 失敗は記録ファイルごとに別のテスト名として現れる（FR9）
```

### Data Flow

```
test-docs/**/*.tests.yaml → 記録の列挙 → ID の抽出 → 解決の判定 → 集約と報告 → unittest の結果
                                          │             │
                                          └─ 抽出エラー ─┴─ 解決エラー → ファイル・AC・ID・理由
```

### API Design

該当なし。

### Database Schema

該当なし。

記録ファイルで扱うフィールド:

| フィールド | 扱い |
|------------|------|
| `acceptance_tests` | 欠落は失敗（FR7） |
| `acceptance_tests.*.tests` | 書き換えと検査の対象（FR4）。`[]` は正当（FR8） |
| `acceptance_tests.*.red_reason` | FR2 による末尾への追記だけを行う（FR2、FR3） |
| `acceptance_tests.*.red_confirmed` | 変えない（FR2、FR3） |
| `baseline_failures` / `final_failures` | 書き換えない（FR4） |

ID の対応記録（`test-docs/tests-yaml-test-id-resolution/` 配下、FR3）の項目: ファイル・AC・旧 ID・新 ID または削除・根拠。

### Dependencies

**Internal Dependencies:**
- `test-docs/**/*.tests.yaml`: 全件検査の入力（FR5）
- `tests/` 配下のテストモジュール: ID の解決先（FR6）
- `tests/test_exit4_ac2_test_id_drift.py`: 変更せず通り続ける（FR5、NFR3）

**External Dependencies:**
- なし（新しい検査モジュールは標準ライブラリだけを import する。NFR1）

### File Structure

```
tests/
└── (新規) 全件検査モジュール            # FR5〜FR9
test/
└── README.md                            # FR7, FR13
em-workflow/agents/
└── implementer.md                       # FR10〜FR12
test-docs/
├── **/*.tests.yaml                      # FR1〜FR4（全記録）
└── tests-yaml-test-id-resolution/       # FR3 ID の対応記録
```

## Declared Change Set

フィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。そのうえで、この SPEC はデフォルトの 2 項目に加えて次のパスを変更対象として明示する。

**デフォルト外のパス:**
- `test-docs/**/*.tests.yaml` — 他の機能のものを含む全記録。書き換えるのは `acceptance_tests.*.tests` と、FR2 による `red_reason` 末尾への追記だけ。`test-docs/exit4-tip-argument/task0002.tests.yaml` は NFR3 が固定する内容を変えない。
- `em-workflow/agents/implementer.md` — FR10〜FR12
- `test/README.md` — FR7、FR13
- `tests/` 配下に新設する全件検査モジュール — FR5〜FR9

**明示するデフォルト内のパス:**
- `test-docs/tests-yaml-test-id-resolution/` — ID の対応記録（FR3）

**変更しないパス:**
- `tests/test_exit4_ac2_test_id_drift.py`（FR5、NFR3）

この SPEC は、デフォルトで次の 2 項目を宣言に含める。

- `feature-docs/tests-yaml-test-id-resolution/**`
- `test-docs/tests-yaml-test-id-resolution/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: タスクごとのテスト記録 `test-docs/{feature}/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 項目は、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセットの主張であり、verify 時点で観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。宣言されたパスが実際に生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS-4（AC-5）: 一時ディレクトリのフィクスチャ記録に、存在しないメソッド・クラス・モジュール、`tests.` 接頭辞なし、`path::` 形式、説明文を入れて検査する - メッセージにファイル・AC・全不正 ID が含まれる
- [ ] TS-5（AC-6）: 既存クラス上の存在しないメソッド ID で `loader.errors` / `_FailedTest` 経路を通す。テスト本体でマーカーファイルを作るフィクスチャのテストモジュールを解決させる - 失敗と判定され、マーカーが作られない。`TestCase` 以外の属性や呼び出し可能なモジュール属性は呼ばれずに拒否される
- [ ] TS-6（AC-7）: 表記ごとのフィクスチャで抽出結果を比較する - 期待どおりの ID だけが抽出され、未対応形式・AC キー重複・`tests` キー重複・`tests` キー欠落・`acceptance_tests` 欠落がそれぞれファイルと AC を示して失敗する
- [ ] TS-7（AC-8）: 全 AC が `tests: []` の記録、読み取れない記録、対象 0 件を検査する - `tests: []` の記録は通り、読み取れない記録と対象 0 件は失敗する
- [ ] TS-8（AC-9）: 2 つの記録フィクスチャで、片方を失敗させた状態にもう片方へ不正 ID を加える - 失敗テスト名の集合が増える

### Integration Tests
- [ ] TS-1（AC-1）: 実リポジトリの `test-docs/**/*.tests.yaml` を全件検査にかける - 記録ファイルごとのテストがすべて通る
- [ ] TS-9（AC-10）: `implementer.md` と `test/README.md` を読む文書契約テスト - FR10〜FR13 の規則の記述がある
- [ ] TS-10（AC-11）: 新モジュールの import を `ast` で列挙し、全スイートを実行する - import がすべて `sys.stdlib_module_names` に含まれ、全スイートが通る

### Verify Checks
- [ ] TS-2（AC-2）: 再現手順（各 ID を `loadTestsFromName` で解決）を実行する - 失敗 0 件（verify で実施）
- [ ] TS-3（AC-3、AC-4）: ベースとの git diff を確認する - 記録の変更が `tests` 要素と `red_reason` 末尾への追記だけで、変更 ID と対応記録の件数が一致する（verify で実施）

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] 該当なし

### Edge Cases
- [ ] 複数行スカラーの本文中の `tests:` や `-` で始まる行: ID として読まない（FR7）
- [ ] `AC-n` 以外の AC キー（例: `D4-parser-unavailable`）: 受け付ける（FR7）
- [ ] 全 AC が `tests: []` の記録: 失敗にしない（FR8）
- [ ] 読み取りに失敗した記録: 空リストとして扱わず失敗させる（FR8）
- [ ] 検査対象の記録が 0 件: 失敗させる（FR8）
- [ ] ある記録がすでに失敗している状態で別の記録に不正 ID が入る: 失敗したテスト名の差分に現れる（FR9）
- [ ] ID 整理で AC の ID がすべて削除され `tests: []` になる: `red_confirmed` / `red_reason` は変えない（A4）

### Performance Tests
- [ ] 該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** FR7 の表記の範囲外の記録は、ファイルと AC を示して失敗させる。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし
- **その他:** 判定の過程でテストを実行せず、解決したオブジェクトを呼び出さない（FR6）。

## Error Handling

### Error Codes

| 種別 | 条件 | 失敗メッセージに含める内容 |
|------|------|----------------------------|
| 抽出エラー | 対応しない形式、AC キーや `tests` キーの重複、`tests` キーの欠落、`acceptance_tests` の欠落（FR7）、読み取り失敗（FR8） | ファイル・AC・ID・理由（FR5、FR7） |
| 解決エラー | FR6 で解決できない ID（`tests.` で始まらない、解決先が無い、`loadTestsFromName` の例外・`loader.errors`・`_FailedTest`） | ファイル・AC・ID・理由（FR5） |
| 対象 0 件 | 検査対象の記録が 1 件も見つからない（FR8） | 失敗させる |

### Error Flow

```
エラー検出 → 途中で止めず全件集める → 記録ファイルごとのテストで失敗させる → ファイル・AC・ID・理由を失敗メッセージに並べる
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC-1: `test-docs/**/*.tests.yaml` の全記録で、`acceptance_tests.*.tests` の全 ID が全件検査で抽出エラー・解決エラーなしに解決する。（FR1、FR2、FR3、FR5、FR6）
- [ ] AC-2: タスク説明の再現手順（全記録の全 ID を `unittest.TestLoader().loadTestsFromName` で解決する）を実行すると、解決できない ID が 0 件になる。（FR1、FR2、FR3、FR6）
- [ ] AC-3: 変更・削除した全 ID について、ファイル・AC・旧 ID・新 ID または削除・根拠の記録があり、その件数が実際の差分と一致する。（FR3）
- [ ] AC-4: ベースからの差分で、記録の `red_confirmed`・`baseline_failures`・`final_failures` は変わっていない。`red_reason` の変更は FR2 による末尾への追記だけで、追記前の記述が先頭にそのまま残っている。（FR2、FR3、FR4）
- [ ] AC-5: 存在しないメソッド・クラス・モジュールを指す ID、`tests.` で始まらない ID、`path::Class::method` 形式の ID、説明文の要素を持つ記録のフィクスチャを全件検査にかけると、ファイル・AC・ID を示して失敗する。複数の不正 ID は 1 回の失敗メッセージにすべて並ぶ。（FR5、FR6）
- [ ] AC-6: `loadTestsFromName` が例外を出さずに `loader.errors` / `_FailedTest` で失敗を返す ID を、全件検査が失敗と判定する。テストを実行しないこと（解決した対象のテスト本体が持つ副作用が起きないこと）が確認できる。（FR6）
- [ ] AC-7: ブロック形式・フロー形式・引用符付き・コメント付きの `tests` と、本文に `tests:` や `-` 行を含む複数行の `red_reason` を持つフィクスチャから、期待どおりの ID だけが抽出される。対応しない形式・重複キー・`tests` キーの欠落・`acceptance_tests` の欠落はファイルと AC を示して失敗する。（FR7）
- [ ] AC-8: 全 AC が `tests: []` の記録は失敗しない。読み取りに失敗する記録は空リスト扱いにならず失敗する。対象記録 0 件では失敗する。（FR8）
- [ ] AC-9: ある記録がすでに失敗している状態で別の記録に不正 ID を加えると、新しい失敗テスト名が増える。（FR9）
- [ ] AC-10: `implementer.md` に FR10・FR11・FR12 の規則が、`test/README.md` に FR13 の記載がある。（FR10、FR11、FR12、FR13）
- [ ] AC-11: 新しい検査モジュールの import が標準ライブラリだけである。`python3 -m unittest discover -s tests` で新モジュールが実行され、`tests/test_exit4_ac2_test_id_drift.py` は無変更のまま通る。（NFR1、NFR2、NFR3）

## Assumptions

- A1: 解決判定はリポジトリルートを `sys.path` に置いた状態で行う。`python3 -m unittest discover -s tests` をリポジトリルートから実行したときは、`tests/` とリポジトリルートの両方が `sys.path` にあり、`tests.` 付きの ID がこの状態で解決する。
- A2: 件数（409 ファイル、失敗 ID 1,035 件 / 133 ファイル、ドット形式への変換で解決するもの 257 件、残り 778 件 / 123 ファイル、旧抽出器が拒否する 90 ファイル）は事前調査の値で、要件では件数を固定しない。タスク説明の「約 769 件」とは差がある。
- A3: ID の対応記録の置き場所は `test-docs/tests-yaml-test-id-resolution/` とする。
- A4: ID 整理で AC の ID がすべて削除され `tests: []` になっても、`red_confirmed` / `red_reason` は変えない。全件検査は `red_confirmed` との整合を判定しない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし。

## References

- 要件定義書: `feature-docs/tests-yaml-test-id-resolution/REQUIREMENTS.md`

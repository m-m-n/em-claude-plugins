# Feature: cleanup-guard-cap-sync-test

## Overview

develop の SKILL.md に書かれた batch 自動 rework の系譜 cap / hard cap の値と、
failed-run-cleanup-guard.py の定数 `LINEAGE_CAP_COUNT` / `HARD_CAP_ROUNDS` が
食い違ったときに失敗するテストを `tests/test_failed_run_cleanup_guard.py` に加える。
フックと SKILL.md は変更しない。

## Objectives

- develop SKILL.md の batch 自動 rework の cap 値と failed-run-cleanup-guard.py の cap しきい値の
  食い違いを、テストの失敗として検出する。
    - フックのコメントは両者が一致すると述べているが、それを確かめるテストは無い。
    - SKILL.md の cap が変わると、cap に達した run に対して S1（git worktree remove）と
      S3（gh pr create）が再び拒否され、Step C の completion_aborted が戻る。その状態でも
      既存のテストはすべて通る。

## Acceptance Criteria

- [ ] AC1: `tests/test_failed_run_cleanup_guard.py` に、実際の SKILL.md から系譜 cap と hard cap の
  ラベルの数値と到達条件の数値を読み、FR3 の規則で `LINEAGE_CAP_COUNT` / `HARD_CAP_ROUNDS` と
  照合するテストがある。現在のツリーでこのテストは通る。
- [ ] AC2: SKILL.md の本文をメモリ上で複製し、4 つの cap の数値のうち 1 つを変えたものは
  不整合として報告される。数値ごとに 1 つのテストケースがあり、実ファイルは編集しない。
- [ ] AC3: cap の箇条書きを見つけられない、または複数回一致する SKILL.md の本文は不整合として
  報告される。整合とも、スキップとも扱わない。

## Technical Requirements

### Functional Requirements

- **FR1:** SKILL.md から cap 値を読む。
  テストは `em-workflow/skills/develop/SKILL.md`
  （`REPO_ROOT / 'em-workflow' / 'skills' / 'develop' / 'SKILL.md'`）を読む。
  「**batch 自動 rework の系譜 cap**」の段落の下にある 2 つの箇条書きから、次の 4 つの数値を取り出す。
    - 系譜 cap のラベルの N: `系譜 cap（値 N）`
    - 系譜 cap の到達条件の N: `累積出現回数が N に達した`
    - hard cap のラベルの N: `hard cap（値 N）`
    - hard cap の到達条件の N: `` `batch.verify_rework.rounds`（...）が N に達した ``
- **FR2:** フックの定数を読む。
  `LINEAGE_CAP_COUNT` と `HARD_CAP_ROUNDS` は、既存の `load_hook_module()` が返すモジュールから読む。
  これらの値をリテラルとしてテストに書き写さない。
- **FR3:** 整合の規則。
    - 系譜 cap: 到達条件の数値 == `LINEAGE_CAP_COUNT`、かつ ラベルの数値 + 1 == `LINEAGE_CAP_COUNT`
    - hard cap: 到達条件の数値 == `HARD_CAP_ROUNDS`、かつ ラベルの数値 == `HARD_CAP_ROUNDS`
    - 破れた規則ごとに、SKILL.md 側の値と、比較したフックの定数を示して報告する。
- **FR4:** 頑健な読み取り。
    - 各箇条書きの本文の改行とインデントを 1 つの空白にまとめてから照合する
      （hard cap の到達条件は 889-890 行にまたがる）。
    - パターンには全角の括弧 `（` `）` を使う。
    - 4 つの数値はそれぞれちょうど 1 回見つかる必要がある。0 回または複数回の一致は、見つからない
      項目・曖昧な項目の名前を示した不整合として報告する。整合とは扱わず、テストをスキップしない。
    - 系譜 cap の箇条書きにある「2 回目」の数値と、SKILL.md の他の箇所にある数値を伴わない
      系譜 cap への言及は読まない。
- **FR5:** 本文を受け取る関数としての抽出。
  抽出と比較はテストモジュール内の 1 つの関数に置く。この関数は SKILL.md の本文と 2 つのフック定数を
  引数に取り、検出した不整合のリストを返す（空のリストは整合を意味する）。実ファイルのテストと
  変異のテストは、どちらもこの同じ関数を呼ぶ。
- **FR6:** 値を変えると失敗することをテスト内の変異で示す。
  各テストケースは実際の SKILL.md の本文をメモリ上で複製し、4 つの数値（系譜 cap のラベル、
  系譜 cap の到達条件、hard cap のラベル、hard cap の到達条件）のうちちょうど 1 つを変える。
  各ケースはまず置換がちょうど 1 回適用されたことを確かめ、次に関数が 1 件以上の不整合を報告する
  ことを確かめる。実際の SKILL.md は編集しない。

### Non-Functional Requirements

- **NFR1 - 標準ライブラリのみ:** test/README.md に従い、標準ライブラリ
  （`unittest`、`re`、`pathlib`、`importlib`）だけを使う。
- **NFR2 - 読み取り専用:** テストは SKILL.md、フック、その他リポジトリ内のどのファイルにも書き込まない。
- **NFR3 - 配置と実行:** テストは `tests/test_failed_run_cleanup_guard.py` に置く。
  `python3 -m unittest discover -s tests` で拾われ、
  `python3 -m unittest tests.test_failed_run_cleanup_guard` で単独でも実行できる。
- **NFR4 - 命名:** test/README.md に従い、クラスは `Test<Behavior>`、メソッドは
  `test_<condition>_<expected_result>` とする。
- **NFR5 - フックと SKILL.md の不変:** フック（判定ロジック、定数、docstring）と SKILL.md は何も変えない。

## Implementation Approach

### Architecture

```
SKILL.md の本文 ──┐
                 ├─> 抽出・比較関数（FR5） ──> 不整合のリスト（空 = 整合）
フックの定数 ──────┘
  (load_hook_module() から LINEAGE_CAP_COUNT / HARD_CAP_ROUNDS)
```

- 実ファイルのテスト: 実際の SKILL.md の本文とフックの定数を関数に渡し、不整合が無いことを確かめる。
- 変異のテスト: 実際の本文を複製して 1 か所だけ書き換えたものを同じ関数に渡し、不整合が報告される
  ことを確かめる。

### Data Flow

```
SKILL.md（読み取りのみ） → 本文 → 箇条書きの特定 → 改行・インデントを空白 1 つにまとめる
  → 4 つの数値の抽出（各 1 回ちょうど） → FR3 の規則で定数と比較 → 不整合のリスト
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/skills/develop/SKILL.md`: cap 値の読み取り元（読み取りのみ）
- failed-run-cleanup-guard.py: 既存の `load_hook_module()` で読み込み、`LINEAGE_CAP_COUNT` /
  `HARD_CAP_ROUNDS` を参照する（変更しない）

**External Dependencies:**
- なし（標準ライブラリのみ）

### File Structure

```
tests/
└── test_failed_run_cleanup_guard.py   # 整合テストを追加する（唯一の変更ファイル）
```

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。上の機能固有のパスは、create-plan の
時点で `workflow.yaml` の各タスクの `files` から導出する
（`references/phases/create-plan-phase.md`）。

上の機能固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/cleanup-guard-cap-sync-test/**`
- `test-docs/cleanup-guard-cap-sync-test/**`

`feature-docs/cleanup-guard-cap-sync-test/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、
`retrospect.yaml`、design step が生成する成果物を含む。これらは各フェーズ文書と
`references/phase-state.md` が生成・管理し、この節はそれらの規則を再掲しない。

`test-docs/cleanup-guard-cap-sync-test/**` はタスクごとのテスト記録
`test-docs/cleanup-guard-cap-sync-test/{T}.tests.yaml` を含む。これは `implement-phase.md` が
生成・管理し、この節はその規則を再掲しない。

この 2 つの既定のエントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、
一致する必要はない。宣言したパスが生成されないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS1（AC1 / FR1, FR2, FR3, FR5）: 実際の SKILL.md の本文とフックの定数では、不整合は報告されない。
- [ ] TS2（AC2 / FR1, FR3, FR5, FR6）: 系譜 cap のラベル（`系譜 cap（値 1）`）を別の整数に変える
  （置換はちょうど 1 回）。不整合が報告される。
- [ ] TS3（AC2 / FR1, FR3, FR5, FR6）: 系譜 cap の到達条件（`累積出現回数が 2 に達した`）を別の整数に
  変える（置換はちょうど 1 回）。不整合が報告される。
- [ ] TS4（AC2 / FR1, FR3, FR5, FR6）: hard cap のラベル（`hard cap（値 3）`）を別の整数に変える
  （置換はちょうど 1 回）。不整合が報告される。
- [ ] TS5（AC2 / FR1, FR3, FR4, FR5, FR6）: hard cap の到達条件（rounds のフィールドに続き、改行を
  またぐ `が 3 に達した`）を別の整数に変える（置換はちょうど 1 回）。不整合が報告される。
- [ ] TS6（AC3 / FR4, FR5）: 系譜 cap または hard cap の箇条書きを取り除いた複製、またはラベルの文言を
  変えてパターンが一致しなくなった複製は、不整合として報告される。
- [ ] TS7（AC3 / FR4, FR5）: cap の箇条書きを重複させた複製は、不整合（曖昧な一致）として報告される。

### Integration Tests

該当なし。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 4 つの数値のいずれかが 0 回または複数回一致する: 見つからない項目・曖昧な項目の名前を示した
  不整合として報告する（TS6, TS7）。
- [ ] hard cap の到達条件が行をまたぐ: 改行とインデントを空白 1 つにまとめてから照合する（TS5）。
- [ ] 系譜 cap の箇条書きにある「2 回目」の数値と、他の箇所の数値を伴わない系譜 cap への言及:
  読み取らない。

### Performance Tests

該当なし。

## Assumptions

- **A1:** フックの判定ロジック、定数の値、docstring は変えない。変わるのは
  `tests/test_failed_run_cleanup_guard.py` だけ。
- **A2:** SKILL.md は編集しない。テストは現在の SKILL.md の本文とフックの定数を互いに固定する。
- **A3:** `.claude/rules/hook-tests.md` に failed-run-cleanup-guard の節は追加しない。

## Security Considerations

該当なし。

## Error Handling

該当なし。不整合は FR3・FR4 のとおり、関数の戻り値のリストとして報告する。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] FR1-FR6 が実装され、テストされている
- [ ] TS1-TS7 が通る
- [ ] NFR1-NFR5 を満たしている

## Open Questions

なし。

## References

- develop スキル: `em-workflow/skills/develop/SKILL.md`
- テスト規約: test/README.md

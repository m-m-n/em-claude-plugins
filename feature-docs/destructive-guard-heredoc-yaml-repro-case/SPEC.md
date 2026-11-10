# Feature: destructive-guard-heredoc-yaml-repro-case

## Overview

区切り文字をクォートしたヒアドキュメントでファイルを書き、本文で文字列 `git reset --hard` を引用しているだけのコマンドを、`em-workflow/hooks/destructive-guard.py` が拒否しないようにする。
報告された再現コマンドを期待値スイートに allow ケースとして固定する。
本物の `git reset --hard` の実行は引き続き拒否する。

## Objectives

- 区切り文字をクォートしたヒアドキュメントでファイルを書き、本文で文字列 `git reset --hard` を引用しているだけのコマンドを、destructive-guard.py が deny しない。
- 報告の再現形を期待値スイートに allow ケースとして固定し、退行が再び入り込めないようにする。
- 本物の `git reset --hard` の実行は deny のまま保つ。

## Acceptance Criteria

- [ ] AC1（FR1, FR2）: `destructive-guard-cases.json` に、コマンドが再現コマンドと一致する allow ケースがあり、ランナーがそのケースを `ok` と報告する。
- [ ] AC2（FR3）: `destructive-guard-cases.json` に、再現コマンドの終端行の後に本物の `git reset --hard HEAD~1` の行を続けた deny ケースがあり、ランナーがそのケースを `ok` と報告する。
- [ ] AC3（FR4）: 既存の `["deny", "本物: git reset --hard", "git reset --hard HEAD~1"]` ケースが残っていて通過し、既存の deny / ask ケースの集合が変わっていない。
- [ ] AC4（NFR1）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が終了コード 0 で終わり、`N/N passed` を出力する。

## Technical Requirements

### Functional Requirements

- **FR1: 再現形の allow ケース**
  `em-workflow/hooks/tests/destructive-guard-cases.json` に allow ケースを 1 件追加する。コマンドは報告の再現コマンドをそのまま使う。構成は次のとおり。
    - 1 行目: `cat > /tmp/example.yaml <<'YAML'`
    - 本文: `description: |` の行と、それに続くインデントされた 2 行。2 行はそれぞれ、バッククォートで囲んだ `rm -rf tmp/$X` と、バッククォートで囲んだ `rm -rf tmp/$X; git reset --hard HEAD~1` を含む。
    - 終端行: `YAML`

  ケースは 3 要素形式 `["allow", ラベル, コマンド]` とし、4 要素目は付けない（`cwd` も `CLAUDE_BATCH` も指定しない）。

- **FR2: 再現形に対するガードの判定**
  `em-workflow/hooks/destructive-guard.py` は FR1 のコマンドに `allow` を返す。区切り文字がクォートされていて、出力先が `cat` のファイルへのリダイレクトであるヒアドキュメントの本文は、コマンドとして読まない。FR1 のケースが現在の destructive-guard.py で既に通る場合、destructive-guard.py は変更しない。

- **FR3: 対照の deny ケース（ヒアドキュメントの後の本物の reset）**
  `destructive-guard-cases.json` に deny ケースを 1 件追加する。コマンドは FR1 のコマンドの `YAML` 終端行の後に、本物の `git reset --hard HEAD~1` 文の行を続けたもの。期待する判定は `deny`。

- **FR4: 既存の deny / ask ケースを保つ**
  `destructive-guard-cases.json` の既存の deny / ask ケースは、1 件も削除せず、期待する判定も変えない。単独の `git reset --hard HEAD~1` の deny ケースと、ヒアドキュメントをインタプリタ（`| bash`、python3、sh）に渡して deny になるケースもこれに含む。

### Non-Functional Requirements

- **NFR1: 期待値スイートの全件通過**
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` が、無人実行時の降格の検査を含む全ケースを通過する。各評価はランナーの 10 秒の制限内に終わる。
- **NFR2: ケースのラベルとコマンドの書き方**
  新しいケースのラベルは既存の日本語ラベルの書き方に合わせる。コマンドにマシン固有のパスとホームディレクトリのパスを含めない。
- **NFR3: プラグインの version を変えない**
  version の欄（`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`）は変更しない。

## Assumptions

- **A1:** 現在のツリーは、再現コマンドに `allow` を、`git reset --hard HEAD~1` に `deny` を既に返す（オーケストレーターが確認済み）。報告された deny は、古いフックのコピー（例: インストール済みプラグインの古いキャッシュ）から出た可能性が高い。このため想定する範囲はテストケースの追加だけで、destructive-guard.py は変更しない。FR1 のケースが現在のフックで失敗する場合は、FR2 に基づき destructive-guard.py の修正が範囲に入る。（覆りうる）
- **A2:** インタプリタ（`| bash`、python3、sh）に渡すヒアドキュメントは、設計どおり deny のまま保つ。この不具合の対象ではなく、既存ケースで担保されている。（覆りうる）
- **A3:** 区切り文字をクォートしない形（`<<YAML`）は範囲外。この形では bash 自身が本文のバッククォートのコマンド置換を実行するため、誤検知ではなく本物の実行にあたる。（覆りうる）

## Implementation Approach

### 進め方

1. FR1 の allow ケースと FR3 の deny ケースを `destructive-guard-cases.json` に追加する。
2. `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる。
3. FR1 のケースが現在の destructive-guard.py で通る場合、destructive-guard.py は変更しない（FR2、A1）。
4. FR1 のケースが失敗する場合は、FR2 の判定になるよう destructive-guard.py を直す。その際も FR4 の既存の deny / ask ケースは変えない。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: 判定の対象
- `em-workflow/hooks/tests/run-destructive-guard.py`: 期待値スイートのランナー

**External Dependencies:**
- なし

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py              # FR1 のケースが失敗する場合だけ変更（FR2）
└── tests/
    ├── destructive-guard-cases.json  # FR1 / FR3 のケースを追加
    └── run-destructive-guard.py      # 変更しない
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-heredoc-yaml-repro-case/**`
- `test-docs/destructive-guard-heredoc-yaml-repro-case/**`

`feature-docs/destructive-guard-heredoc-yaml-repro-case/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-heredoc-yaml-repro-case/**` covers `test-docs/destructive-guard-heredoc-yaml-repro-case/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/destructive-guard-heredoc-yaml-repro-case/` directory at all; the declared
`test-docs/destructive-guard-heredoc-yaml-repro-case/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1: 期待値スイートを走らせる - FR1 の allow ケースが `allow` になる（AC1 / FR1, FR2）
- [ ] TS-2: 期待値スイートを走らせる - FR3 の対照ケースが理由タグ `git-reset-hard` 付きの `deny` になる（AC2 / FR3）
- [ ] TS-3: `python3 em-workflow/hooks/tests/run-destructive-guard.py` をスイート全体に対して走らせる - 終了コード 0 で終わり、既存の deny / ask ケースも通過する（AC3, AC4 / FR4, NFR1）

### E2E Tests

**Existing E2E tests**: なし
**Run command**: 検出なし

## Performance Optimization

### Performance Goals

- 各ケースの評価がランナーの 10 秒の制限内に終わる（NFR1）

## Success Criteria

- [ ] FR1〜FR4 を満たし、テストで確認できている
- [ ] TS-1〜TS-3 がすべて通過する
- [ ] NFR1〜NFR3 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 期待値スイート: `em-workflow/hooks/tests/destructive-guard-cases.json`
- ランナー: `em-workflow/hooks/tests/run-destructive-guard.py`
- 判定の対象: `em-workflow/hooks/destructive-guard.py`

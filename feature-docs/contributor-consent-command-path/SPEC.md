# Feature: contributor-consent-command-path

## Overview

contributor-consent スキルの手順 5 で、スキル自身が `--record` / `--remove` を実行する設計を維持する。`tests/test_contributor_consent_skill.py` の文言を固定するテストを、構造的なテストに置き換える。要件は `feature-docs/contributor-consent-command-path/REQUIREMENTS.md` を参照する。

## Objectives

- contributor-consent スキルによる muse-spark のコントリビューター同意の記録と取り消しが、実際の利用で機能する。スキル自身が `--record` / `--remove` を実行する。
- 特定の文言を固定するテストを構造的なテストに置き換え、再発（ユーザーに見せる行が未解決の環境変数参照を含むこと）と、記録・削除の経路の消失を検出する。

## User Stories

### US1: スキルによる同意の記録・取り消し
スキル利用者として、contributor-consent スキルで同意・取り消しを選んだとき、スキル自身に `--record` / `--remove` を実行してほしい。

**Acceptance Criteria:**
- [ ] AC-2: 両方のコピーについて、手順 5 の同意の分岐がスキルの実行するコマンドちょうど 1 つ（`hooks/muse_guard.py`、`--record`、`--project-dir`）に結びつき、取り消しの分岐が `--remove` 付きの同様のコマンドちょうど 1 つに結びついていることを、テストが確かめる
- [ ] AC-3: 両方のコピーについて、辞退と維持の分岐が何も実行しないこと、手順 6 が CLI を呼ばず書き込みなしの行を出力することを、テストが確かめる
- [ ] AC-5: 両方のコピーについて、手順 5 がスキル自身がコマンドを実行すると述べ、ユーザー自身の端末で貼り付けたり実行したりする指示を含まないことを、テストが確かめる

### US2: 文言に依存しない構造的なテスト
プラグイン開発者として、特定の文言に固定されないテストで、ユーザーに見せる行への未解決の環境変数参照の混入と、記録・削除の経路の消失を検出したい。

**Acceptance Criteria:**
- [ ] AC-1: `tests/test_contributor_consent_skill.py` が `PRESENTED_RECORD_CMD` / `PRESENTED_REMOVE_CMD` を含まず、コマンド文字列全体またはリテラル `"${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py` を文書と照合する assertion を含まない
- [ ] AC-4: 両方のコピーについて、テストが本文のすべてのフェンスブロックとユーザー向けリテラルを「スキルが実行するコマンド」か「ユーザーに見せるテキスト」に分類し、ユーザーに見せるテキストが `${NAME}` / `$NAME` 参照を含まないことを確かめる。スキルが実行するコマンド中の `${CLAUDE_PLUGIN_ROOT}` は検出しない
- [ ] AC-6: 非空性。合成入力で、テストが次を証明する。(a) 変数の検査は `${X}` または `$X` を含むユーザーに見せるテキストを検出し、`$(...)` のコマンド置換やただのテキストは検出しない。(b) 手順 5 の記録または削除のコマンドを取り除いた本文で、対応の検査が失敗する。(c) 分類されないフェンスブロックで、分類の検査が失敗する
- [ ] AC-7: task0009 のテスト名・コメント・モジュール docstring がスキルが実行する設計を述べ、コマンドを「presented to the user」「never executed」とする記述が残っていない
- [ ] AC-8: 既存の検査が引き続き成り立つ。文書ごとに AskUserQuestion がちょうど 1 つ、6 つの手順の順序、固定行、CLI のみの行、frontmatter、`commands/` 配下のファイルがないこと、2 つのコピーがプラグイン名と手順番号以外で同一であること、`tests/test_muse_consent_no_new_questions.py` の除外
- [ ] AC-9: `python3 -m unittest discover -s tests` が通り、変更したテストモジュールが標準ライブラリだけを import する

## Technical Requirements

### Functional Requirements
- **FR1:** スキルが実行する設計の維持 — contributor-consent の手順 5 は、スキル自身がガード CLI を実行する設計を維持する。ユーザーが同意したら `--record`、取り消したら `--remove` を実行する。`em-workflow/skills/contributor-consent/SKILL.md` と `em-review/skills/contributor-consent/SKILL.md` は、テストとの整合を保つのに必要な場合だけ変更し、変更するときは両方に同じ変更を入れる。
- **FR2:** 文言固定の削除 — `tests/test_contributor_consent_skill.py` から定数 `PRESENTED_RECORD_CMD` / `PRESENTED_REMOVE_CMD` を削除する。あわせて、コマンド文字列全体や特定のパス表記（`"${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py` など）を文書と照合する assertion をすべて削除する。
- **FR3:** 回答と実行内容の対応のテスト — テストは、各コピーについて構造的に次を確かめる。手順 5 の同意の分岐が、スキルが実行するコマンドちょうど 1 つに結びつき、そのコマンドが `hooks/muse_guard.py` を `--record` と `--project-dir` 付きで呼ぶこと。取り消しの分岐が、同様のコマンドちょうど 1 つに `--remove` 付きで結びつくこと。辞退と維持の分岐が何も実行しないこと。手順 6（却下または無回答）が CLI を呼ばず、書き込みなしの行 `同意ストアは変更していない。` を出力すること。確認は肯定形で行い、記録または削除の手順が消えたら失敗する。
- **FR4:** ユーザーに見せる行の未解決変数の検査 — テストは、スキル本文のフェンスブロックとインラインリテラルを 2 種類に分ける。スキルが実行するコマンド（手順 2 の `--list`、手順 5 の `--record` / `--remove`）と、スキルがユーザーにそのまま見せるテキスト（手順 1 の未インストールの行、手順 4 の質問と選択肢の文言、手順 6 の書き込みなしの行）。すべての要素はちょうど 1 種類に属し、分類されない要素があればテストは失敗する。ユーザーに見せるテキストは未解決の環境変数参照（`${NAME}` / `$NAME`）を含まない。スキルが実行するコマンド中の `${CLAUDE_PLUGIN_ROOT}` は、スキルの読み込み時に置換されるため検出対象にしない。
- **FR5:** ユーザー端末での実行指示がないことの検査 — テストは、各コピーの手順 5 が「スキル自身がコマンドを実行する」と述べていること、ユーザーに自分の端末でコマンドを貼り付けたり実行したりするよう指示していないことを確かめる。
- **FR6:** task0009 の記述の整合 — `tests/test_contributor_consent_skill.py` の task0009 のテスト名・コメント・モジュール docstring を、スキルが実行する設計の記述に更新する。コマンドを「presented to the user」「never executed by the skill」とする記述を残さない。
- **FR7:** 2 つのコピーの一致 — em-workflow と em-review の SKILL.md は、引き続きプラグイン名とレビューフェーズのプローブ手順の番号だけが異なる。

### Non-Functional Requirements
- **NFR1:** 標準ライブラリのみ — テストは標準ライブラリだけを使い、`python3 -m unittest discover -s tests` で通る。
- **NFR2:** 既存の不変条件の維持 — 文書ごとに AskUserQuestion がちょうど 1 つ、6 つの手順の順序、固定行（未インストールの行と書き込みなしの行）、CLI のみの行、正しい frontmatter、`commands/` 配下にファイルがないことを保つ。
- **NFR3:** 文言に依存しない検査 — 新しい検査は構造的であり、特定の文言に固定しない。意味を保つ文言の変更や折り返し桁の変更で壊れない。
- **NFR4:** 非空性の証明 — すべての検査は、合成入力による非空性の証明を持つ。何かが存在しないことだけを確かめる検査は、それだけでは足りない。
- **NFR5:** ドキュメントの秘匿 — Notion の URL とホームディレクトリ配下の絶対パスを書かない。

## Implementation Approach

### Architecture

**System Architecture:**
```
em-workflow/skills/contributor-consent/SKILL.md ─┐
                                                 ├─> tests/test_contributor_consent_skill.py
em-review/skills/contributor-consent/SKILL.md  ──┘
```

**Component Diagram:**
```
tests/test_contributor_consent_skill.py
  ├─ 回答と実行内容の対応の検査（FR3）
  ├─ 要素の分類と未解決変数の検査（FR4）
  ├─ 手順 5 の実行主体の検査（FR5）
  └─ 合成入力による非空性の証明（NFR4）
```

### Data Flow

```
SKILL.md（2 つのコピー） → 本文の読み込み → 手順ごとの分割 → 各検査 → 成否
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/skills/contributor-consent/SKILL.md`: 検査対象
- `em-review/skills/contributor-consent/SKILL.md`: 検査対象
- `tests/test_muse_consent_no_new_questions.py`: 既存の除外を保つ（AC-8）

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
em-workflow/skills/contributor-consent/SKILL.md   # 必要な場合だけ変更（FR1）
em-review/skills/contributor-consent/SKILL.md     # 必要な場合だけ変更（FR1）
tests/
└── test_contributor_consent_skill.py             # FR2〜FR6
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/contributor-consent-command-path/**`
- `test-docs/contributor-consent-command-path/**`

`feature-docs/contributor-consent-command-path/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/contributor-consent-command-path/**` covers `test-docs/contributor-consent-command-path/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/contributor-consent-command-path/` directory at all; the declared
`test-docs/contributor-consent-command-path/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 両方の SKILL.md を読み込み、手順 5 の同意の分岐がスキルの実行する `--record` のコマンド 1 つに、取り消しの分岐が `--remove` のコマンド 1 つに対応することを確かめる - 両方のコピーで対応が成り立つ（FR3）
- [ ] TS-2: 両方のコピーの辞退と維持の分岐が何も実行しないと述べ、手順 6 が CLI を呼ばずに書き込みなしの行を出力すると述べていることを確かめる - 両方のコピーで成り立つ（FR3）
- [ ] TS-3: 両方のコピーのフェンスブロックとユーザー向けリテラルを 2 種類に分類する - ユーザーに見せるテキストが環境変数参照を含まず、手順 2 と手順 5 のコマンドがスキルの実行するコマンドに分類される（FR4）
- [ ] TS-4: 両方のコピーの手順 5 を確かめる - スキルがコマンドを実行すると述べ、ユーザーの端末での実行指示を含まない（FR5）
- [ ] TS-5: 合成テキストで変数の検査を行う - `${CLAUDE_PLUGIN_ROOT}` または `$HOME` を含むユーザーに見せるテキストは検出され、`$(pwd)` だけを含むテキストや変数を含まないテキストは検出されない（FR4、NFR4）
- [ ] TS-6: 手順 5 の `--record` または `--remove` のコマンドを取り除いた合成本文で対応の検査を行う - 検査が失敗する（FR3、NFR4）
- [ ] TS-7: 種類が不明なフェンスブロックを追加した合成本文で分類の検査を行う - 検査が失敗する（FR4、NFR4）
- [ ] TS-8: `tests/test_contributor_consent_skill.py` を確かめる（テストまたはレビューによる静的確認） - コマンドの文言固定を含まず、コマンドを「presented」とする記述を含まない（FR2、FR6）

### Integration Tests
- [ ] TS-9: `python3 -m unittest discover -s tests` を実行する - 既存のテスト（スキルのテストの AC-1〜AC-6 と task0009 の AC-2 / AC-3 / AC-5、および `tests/test_muse_consent_no_new_questions.py`）がすべて通る（FR1、FR7、NFR1、NFR2）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
該当なし

### Performance Tests
該当なし

## Security Considerations

- **Data Protection:** ドキュメントに Notion の URL とホームディレクトリ配下の絶対パスを書かない（NFR5）
- その他の項目は該当なし

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed

## Assumptions

- A1: 実装では plugin.json と marketplace.json の version を変更しない。main への push 時に plugin-version-bump のワークフローが、ディレクトリに変更のあった em-workflow と em-review の patch を上げ、それでタスクの version の完了項目を満たす。SPEC と受け入れ基準には version の変更を書かない。
- A2: Claude Code はスキルの読み込み時にスキル本文の `${CLAUDE_PLUGIN_ROOT}` を置換する。そのため、スキルが実行するコマンドはプラグインの絶対パスに解決される。
- A3: 手順 5 のスキルが実行する設計が現在の仕様である（ユーザーの端末に貼り付ける経路はすでに取り除かれている）。タスク説明の再現手順は以前の状態を述べている。
- A4: 2 つの SKILL.md のコピーは変更不要の見込みである。テストとの整合のために変更が必要になった場合は、両方に同じ変更を入れる。
- A5: 既存の不変条件（AskUserQuestion が 1 つ、6 つの手順、固定行、CLI のみの行、2 つのコピーが名前以外で同一）はそのまま保つ。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/contributor-consent-command-path/REQUIREMENTS.md`
- `em-workflow/skills/contributor-consent/SKILL.md`
- `em-review/skills/contributor-consent/SKILL.md`
- `tests/test_contributor_consent_skill.py`
- `tests/test_muse_consent_no_new_questions.py`

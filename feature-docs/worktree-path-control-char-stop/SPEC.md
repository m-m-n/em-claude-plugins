# Feature: worktree-path-control-char-stop

## Overview

implement フェーズで、制御文字または行区切り文字を含む正規化済みの worktree_path が implementer の起動プロンプトに渡らないようにする。
そのような path を見つけたときは、implementer の起動プロンプトを組み立てる前にフェーズを止め、該当タスクを報告する。

## Objectives

- implement フェーズで、制御文字または行区切り文字を含む正規化済みの worktree_path が implementer の起動プロンプトに渡ることがない。
- そのような path を見つけたときは、implementer の起動プロンプトを 1 つも組み立てる前にフェーズを止め、該当タスクを報告する。

## Acceptance Criteria

### AC1（FR1, FR2, FR3）
- [ ] implement-phase.md の Step I.2.a に、選択された全タスクの正規化済み worktree_path について Unicode Cc 文字（U+0000-U+001F、U+007F、U+0080-U+009F）、U+2028、U+2029 を検査することと、1 件でも該当すればフェーズを ABORT し、該当タスクの ID を報告し、どのタスクの起動プロンプトも組み立てないことが書かれている。

### AC2（FR1）
- [ ] この検査は、Step I.2.a の Canonical worktree path の段落より後、起動ループの段落より前に置かれている。

### AC3（FR4, NFR2）
- [ ] tests/test_canonical_worktree_path_docs.py が、現行のドキュメントに対して AC1 と AC2 を検査する。検査を欠く写し、文字集合を欠く写し、起動前の ABORT の記述を欠く写し、検査を起動ループの段落より後ろへ移した写しは、それぞれ検査に失敗する。

### AC4（NFR1, NFR3）
- [ ] tests/test_canonical_worktree_path_docs.py の既存テストすべてと、全体スイート `python3 -m unittest discover -s tests` が通る。

## Technical Requirements

### Functional Requirements

- **FR1: 起動ループの前に、選択された全タスクの正規化済み worktree_path を検査する**
  em-workflow/references/implement-phase.md の Step I.2.a は、今回 Step I.2.a に入った時点で選択されたすべてのタスクについて、正規化済み worktree_path（Canonical worktree path の段落が出す値）を検査する。検査はそれらの値を解決した後、起動ループの段落（"Launch each selected task as a BACKGROUND ..."）より前に行う。worktree を `git worktree add -b` で作った直後の場合も、Resume guard のもとで再利用した場合も、検査の対象になる。

- **FR2: 拒否する文字集合**
  検査は、Unicode 一般カテゴリ Cc の文字（U+0000-U+001F、U+007F、U+0080-U+009F）、U+2028、U+2029 のいずれかを含む正規化済み worktree_path を拒否する。

- **FR3: 起動プロンプトを組み立てる前にフェーズを中止する**
  選択されたタスクのうち 1 つ以上の正規化済み worktree_path が拒否対象の文字を含むとき、オーケストレーターはどの選択タスクについても implementer の起動プロンプトを組み立てず、implementer を起動せず、implement フェーズを ABORT し、該当するタスク ID を報告する。値を除去・エスケープ・置換して処理を続けることはしない。未解決の `$WT_ROOT/{T}` 文字列を代わりに渡すこともしない。

- **FR4: ドキュメントテスト**
  tests/test_canonical_worktree_path_docs.py に、現行の Step I.2.a の節が FR1-FR3 を述べていることの検査を加える。対象は、選択された全タスクへの検査、拒否する文字集合、起動プロンプトを組み立てる前の中止と該当タスクの報告、正規化の手順より後かつ起動ループの段落より前という配置の 4 点。あわせて、それぞれを欠いた偽の写しが検査に失敗することを確かめる。

### Non-Functional Requirements

- **NFR1: 既存のドキュメントテストが通り続ける**
  tests/test_canonical_worktree_path_docs.py の既存テストはすべて、変更を加えずに、編集後の implement-phase.md に対して通る。具体的には次のとおり。
  - worktree が存在した時点で `$WT_ROOT/{T}` を strict realpath で解決する文はちょうど 1 つ。
  - "strict realpath"、"`$WT_ROOT/{T}`"、"worktree exists" をまとめて含むブロックはちょうど 1 つ。
  - フォールバックしない旨の文と、値を引き渡す旨の文は、それぞれ一意のまま。
  - Resume guard / 承認ゲート / 起動ループの各段落の書き出しは、それぞれ一意のまま。
  - assignment payload のブロックは行の順序を保つ。
  - Step I.2.a のどの文も、path 条件のマーカー（CONDITION_MARKERS）を 3 つ以上含まない。

- **NFR2: 標準ライブラリのみ**
  追加するテストコードは Python 標準ライブラリだけを import する。ドキュメントの検査は見出しによる切り出しと安定した語句で行い、行番号には頼らない。

- **NFR3: 全体スイート**
  `python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### 変更対象

- em-workflow/references/implement-phase.md の Step I.2.a: FR1-FR3 の検査と中止の記述を、Canonical worktree path の段落より後、起動ループの段落より前に加える。
- tests/test_canonical_worktree_path_docs.py: FR4 の検査を加える。既存テストは変更しない（NFR1）。

### 処理の流れ（Step I.2.a 内）

```
Canonical worktree path の段落で、選択された全タスクの worktree_path を解決
  → 全タスクの正規化済み worktree_path を FR2 の文字集合で検査
    → 1 件以上該当: 起動プロンプトを 1 つも組み立てずにフェーズを ABORT し、該当タスク ID を報告
    → 該当なし: 起動ループの段落へ進む
```

### Dependencies

**Internal Dependencies:**
- em-workflow/references/implement-phase.md の Step I.2.a: Canonical worktree path の段落、Resume guard の段落、起動ループの段落。
- tests/test_canonical_worktree_path_docs.py の既存テストと CONDITION_MARKERS。

**External Dependencies:**
- なし（Python 標準ライブラリのみ。NFR2）

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を示す。この機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

各 SPEC は、機能固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップが生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、規則は繰り返さない。

`test-docs/{feature}/**` はタスクごとのテスト記録 `test-docs/{feature}/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、規則は繰り返さない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載がないことを外したとは見なさない。外すのは意図的で明示的な絞り込みに限る。

この宣言は上位集合としての主張である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない機能は `test-docs/{feature}/` ディレクトリを生成しないが、その場合も `test-docs/{feature}/**` の宣言は正しい。宣言したパスが実際に作られなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS1（AC1）: `python3 -m unittest tests.test_canonical_worktree_path_docs` を実行する - 現行の Step I.2.a の節は、制御文字の検査（文字集合、選択された全タスク、ABORT、該当タスクの報告、起動プロンプトを組み立てないこと）について問題を出さない。
- [ ] TS2（AC2）: 配置を検査する - 現行の節は検査を正規化の段落より後、起動ループの段落より前に置いている。検査を起動ループの段落より後ろへ移した偽の写しは検出される。
- [ ] TS3（AC3）: 偽の写しを検査する - 検査を取り除いた写し、文字集合を LF だけに減らした写し、中止の記述をエスケープして続行する記述に差し替えた写しは、それぞれ検出される。

### Integration Tests

- [ ] TS4（AC4）: `python3 -m unittest discover -s tests` を実行する - tests/test_canonical_worktree_path_docs.py の既存の AC-1 から AC-4 のテストを含めて通る。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A1:** 拒否する文字集合は Unicode Cc（U+0000-U+001F、U+007F、U+0080-U+009F）に U+2028 / U+2029 を加えたもの。
- **A2:** 1 件でも該当すれば、起動プロンプトを 1 つも組み立てる前に implement フェーズ全体を中止する。該当タスクはタスク ID で報告する。
- **A3:** 中止時に worktree やブランチを削除する手順は加えない。今回 Step I.2.a に入ってから作成済みの worktree はそのまま残す。
- **A4:** em-workflow/hooks/queue_launch_guard.py と em-workflow/hooks/bash_guard.py はこの機能では変更しない。
- **A5:** tests/test_canonical_worktree_path_docs.py の既存テスト（正規化の文の一意性、段落配置の目印、payload の行順、path 条件の繰り返し記述のしきい値）は、新しい記述に対する制約として維持する。
- **A6:** 修正版への追従、または暫定的な緩和策の記録に関する完了条件の項目は SPEC の外で追跡する。この機能がその修正であり、SPEC にはその項目を置かない。

## Success Criteria

- [ ] FR1-FR4 がすべて実装され、テストされている
- [ ] TS1-TS4 がすべて通る
- [ ] NFR1-NFR3 を満たしている

## Open Questions

なし（`status: tbd` の要件はない）

## References

- em-workflow/references/implement-phase.md（Step I.2.a）
- tests/test_canonical_worktree_path_docs.py

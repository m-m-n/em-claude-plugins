# Feature: wake-task-cleanup-script

要件定義書: `feature-docs/wake-task-cleanup-script/REQUIREMENTS.md`

## Overview

implement の wake 手順 4（タスク worktree の削除とタスクブランチの削除）を、em-workflow/scripts/ に置くスクリプトで実行する。implement-phase.md の手順 4 は git コマンドを直接書かず、このスクリプトを呼ぶ形にする。スクリプトは強制しない削除だけを使い、結果を標準出力の JSON 1 つで返す。

## Objectives

- implement の wake 手順 4（タスク worktree の削除とタスクブランチの削除）を em-workflow/scripts/ のスクリプトで実行し、オーケストレーターがその場で git コマンドを組み立てないようにする
- 呼び出し元の作業ディレクトリに関係なく、integration に取り込み済みのタスクブランチを強制しない削除で消せるようにする

## User Stories

### US1: wake 手順 4 の後片付けをスクリプトで行う
オーケストレーターとして、wake 手順 4 でスクリプトを呼んでタスク worktree とタスクブランチを片付けたい。その場で git コマンドを組み立てずに済み、残したものを JSON から報告に書けるようにするため。

**Acceptance Criteria:**
- [ ] AC1: wake 手順 4 の後片付けを行うスクリプトが em-workflow/scripts/ にあり、入力は後片付けに必要な値だけである
- [ ] AC2: スクリプトは git worktree remove と、integration worktree を基準にした git branch -d を実行し、-D、--force、-f を使わない（スクリプトの中身をテストで確かめる）
- [ ] AC3: ブランチを消せなかったとき、残したブランチ名と理由を機械で読める形で返す。手順 4 は、その値を wake の報告に書くと定めている
- [ ] AC4: implement-phase.md の手順 4 に、git コマンドを直接書いた行が無く、スクリプトを呼ぶ形になっている
- [ ] AC5: メインのツリー（タスクブランチを取り込んでいないブランチ）を作業ディレクトリにして呼んでも、integration に取り込み済みのタスクブランチと、その worktree が消えることをテストで確かめる
- [ ] AC6: integration に取り込まれていないタスクブランチは消えずに残り、残した名前と理由が返ることをテストで確かめる
- [ ] AC7: 不正な feature やタスク ID を渡すと、git を実行せずに 0 以外で終了することをテストで確かめる
- [ ] AC8: タスク worktree の削除が失敗したとき（未コミットの変更がある等）、ブランチ削除を試さず、worktree とブランチの両方が残り、それぞれの理由が返ることをテストで確かめる
- [ ] AC9: worktree とブランチの片方または両方が既に無いとき、その対象が「既に無い」として返り、残りの対象は通常どおり片付くことをテストで確かめる。worktree の不在は git の登録一覧で判定している（ディレクトリだけ消えて登録が残っている場合を「既に無い」と返さない）
- [ ] AC10: worktree やブランチを残したときも終了コードは 0 で、結果は標準出力の JSON に入ることをテストで確かめる。手順 4 は JSON を読んで報告に書くと定めている

## Technical Requirements

### Functional Requirements
- **FR1:** 後片付けスクリプト — wake 手順 4 の後片付けを行うスクリプトを em-workflow/scripts/ に置く。入力は integration worktree、feature、タスク ID など、後片付けに必要な値だけにする。
- **FR2:** 実行するコマンド — スクリプトは git worktree remove でタスク worktree を消し、integration worktree を基準にした git branch -d で em-workflow/{feature}/{T} を消す。-D、--force、-f は使わない。
- **FR3:** 残したブランチの報告 — ブランチを消せなかったときは、残したブランチ名と理由を機械で読める形で返す。オーケストレーターはその値を wake フェーズの報告に書く。
- **FR4:** 手順書の書き換え — implement-phase.md の手順 4 は git コマンドを直接書かず、${CLAUDE_PLUGIN_ROOT}/scripts/ で解決したスクリプト（Step I.0 step 4 と同じ方法）を呼ぶ。強制削除に頼らないこと、手順 3 の status が変わらないこと、手順 5 が今までどおり進むことは残す。
- **FR5:** 入力の検証 — feature とタスク ID を、プラグインが既に feature 名とタスク ID に使っている検証用の正規表現で確かめ、integration worktree のパスの形も確かめる。合わなければ git を 1 つも実行せずに 0 以外で終了する。
- **FR6:** worktree の削除に失敗したとき — タスク worktree の git worktree remove が失敗したときは、そのタスクのブランチ削除を試さない。worktree を残したこと、git が返した理由、ブランチ削除を見送ったことと見送った理由を結果の JSON に入れて返す。
- **FR7:** 対象が既に無いとき — タスク worktree やタスクブランチが既に無いときは、片付け済みとして扱い、対象ごとに「既に無い」を「今回消した」と区別して返す。worktree が無いかどうかは git の worktree 登録一覧（git worktree list --porcelain）で、ブランチが無いかどうかは git の ref 解決（refs/heads/em-workflow/{feature}/{T}）で判定し、パスの有無だけでは判定しない。
- **FR8:** 結果の返し方と終了コード — 結果は標準出力に JSON 1 つで返し、終了コードは 0 にする。worktree やブランチを残したときも 0 にする。0 以外で終了するのは、入力が不正なときと内部エラーのときだけにする。手順 4 は、終了コードだけでなく JSON を読み、残したブランチ名と理由を wake フェーズの報告に書くと定める。

### Non-Functional Requirements
- **NFR1:** スクリプトの結果は、呼び出し元の作業ディレクトリ（メインのツリーを含む）に左右されない
- **NFR2:** 手順書に書く呼び出し行は、destructive-guard.py と interpreter-mismatch-guard.py のどちらでも ask / deny にならない
- **NFR3:** テストは標準ライブラリの unittest だけで書き、一時ディレクトリに作った使い捨ての git リポジトリを使う
- **NFR4:** plugin.json と marketplace.json の version は変えない（main への push 時に Actions が patch を上げる）

## Implementation Approach

### Architecture

**Component Diagram:**
```
implement-phase.md 手順 4（オーケストレーター）
  │  ${CLAUDE_PLUGIN_ROOT}/scripts/ で解決したスクリプトを呼ぶ（Step I.0 step 4 と同じ方法）
  ▼
em-workflow/scripts/ の後片付けスクリプト
  │  入力: integration worktree / feature / タスク ID
  ▼
git（git worktree list --porcelain / git worktree remove / ref 解決 / git branch -d）
```

### Data Flow

```
入力の検証（FR5）
  ├─ 不正 → git を 1 つも実行せずに 0 以外で終了
  └─ 正常
      ↓
タスク worktree の登録を git worktree list --porcelain で確かめる（FR7）
  ├─ 登録なし → worktree は「既に無い」
  └─ 登録あり（ディレクトリが無くても登録があれば含む） → git worktree remove（FR2）
        ├─ 成功 → worktree は「今回消した」
        └─ 失敗 → worktree を残し、git の理由を記録。ブランチ削除は見送り、見送った理由を記録（FR6）
      ↓（worktree が「既に無い」か「今回消した」のとき）
refs/heads/em-workflow/{feature}/{T} の ref 解決（FR7）
  ├─ 解決できない → ブランチは「既に無い」
  └─ 解決できる → integration worktree を基準にした git branch -d（FR2）
        ├─ 成功 → ブランチは「今回消した」
        └─ 失敗 → ブランチを残し、ブランチ名と git の理由を記録（FR3）
      ↓
標準出力に JSON 1 つを出して終了コード 0（FR8）
```

- -D、--force、-f は使わない（FR2）
- git worktree prune は実行しない
- 結果は呼び出し元の作業ディレクトリに左右されない（NFR1）

### API Design

#### スクリプトの呼び出し

**入力:**
- integration worktree
- feature
- タスク ID

**出力（標準出力の JSON 1 つ）:**
- タスク worktree の結果: 「今回消した」「既に無い」「残した」のいずれかと、残したときは git が返した理由（FR6、FR7）
- タスクブランチの結果: 「今回消した」「既に無い」「残した」「削除を見送った」のいずれかと、残したときはブランチ名と理由、見送ったときは見送った理由（FR3、FR6、FR7）

**終了コード:**
- 0: 入力が正しく、内部エラーが無いとき（worktree やブランチを残したときも含む）
- 0 以外: 入力が不正なとき、内部エラーのとき

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- implement-phase.md: 手順 4 をスクリプトの呼び出しに書き換える
- プラグインが既に feature 名とタスク ID に使っている検証用の正規表現: FR5 の入力検証に使う
- destructive-guard.py / interpreter-mismatch-guard.py: 手順 4 の呼び出し行が ask / deny にならないことを確かめる対象（NFR2）

**External Dependencies:**
- git: worktree とブランチの操作

### File Structure

```
em-workflow/
├── scripts/
│   └── （新規）wake 手順 4 の後片付けスクリプト
└── implement-phase.md の手順 4（書き換え）
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つをデフォルトで宣言する。

- `feature-docs/wake-task-cleanup-script/**`
- `test-docs/wake-task-cleanup-script/**`

`feature-docs/wake-task-cleanup-script/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` で、この節は引用のみでルールは再掲しない。

`test-docs/wake-task-cleanup-script/**` に含まれるもの: タスクごとのテスト記録 `test-docs/wake-task-cleanup-script/{T}.tests.yaml`。生成主体は `implement-phase.md` で、この節は引用のみでルールは再掲しない。

この 2 つのデフォルトの宣言は、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセットの主張であり、検証時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要があるが、一致する必要は無い。implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` はその場合も正しい。宣言したパスが生成されなくても違反にはならない。

## Test Scenarios

### Integration Tests
- [ ] TS-1: integration ブランチに取り込み済みのタスクブランチと worktree を作り、取り込んでいないメインのツリーを作業ディレクトリにしてスクリプトを呼ぶ - worktree の登録とブランチが消え、終了コード 0、JSON は両方を「今回消した」と返す（AC5）
- [ ] TS-2: integration に取り込んでいないタスクブランチで呼ぶ - worktree は消え、ブランチは残り、JSON に残したブランチ名と git の理由が入る。終了コードは 0（AC6）
- [ ] TS-3: タスク worktree に未コミットの変更を置いて呼ぶ - worktree とブランチの両方が残り、ブランチ削除を試していないことと、それぞれの理由が JSON に入る。終了コードは 0（AC8）

### Edge Cases
- [ ] TS-4: ブランチだけが既に無い状態、worktree だけが既に無い状態、両方無い状態でそれぞれ呼ぶ - 無い対象は「既に無い」、残りの対象は通常どおりの結果になる（AC9）
- [ ] TS-5: worktree のディレクトリだけを消し、git の登録を残した状態で呼ぶ - 「既に無い」とは返さない（AC9）
- [ ] TS-6: feature やタスク ID に不正な値（パス区切り、'integration'、空文字、先頭がハイフン等）を渡す - git を 1 つも実行せずに 0 以外で終了し、integration ブランチと integration worktree は変わらない（AC7）

### Static Checks
- [ ] TS-7: スクリプトの本文に -D、--force、-f の削除フラグが無いことを確かめる（AC2）
- [ ] TS-8: implement-phase.md の手順 4 に git worktree remove / git branch の行が無く、スクリプトの呼び出し行があり、JSON を読んで残したブランチ名と理由を wake の報告に書くと定め、強制削除に頼らない文言・手順 3 の status が変わらない文言・手順 5 が進む文言が残っていることを確かめる（AC4、AC3、AC10）
- [ ] TS-9: 手順 4 の新しい呼び出し行を destructive-guard.py と interpreter-mismatch-guard.py に通し、ask / deny にならないことを確かめる（NFR2）

テストは標準ライブラリの unittest だけで書き、一時ディレクトリに作った使い捨ての git リポジトリを使う（NFR3）。

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 未検出

### Performance Tests
該当なし。

## Security Considerations

- **Input Validation:** feature とタスク ID を、プラグインが既に feature 名とタスク ID に使っている検証用の正規表現で確かめ、integration worktree のパスの形も確かめる。合わなければ git を 1 つも実行せずに 0 以外で終了する（FR5）
- **Destructive Operations:** -D、--force、-f は使わない（FR2）。git worktree prune は実行しない
- 上記以外（認証・認可・XSS・SQL インジェクション・CSRF）は該当なし

## Error Handling

### Error Codes

| 状況 | 終了コード | 結果 |
|------|------------|------|
| 入力が不正 | 0 以外 | git を 1 つも実行しない |
| 内部エラー | 0 以外 | — |
| タスク worktree の削除に失敗 | 0 | JSON に worktree を残したこと・git の理由・ブランチ削除を見送ったことと見送った理由が入る |
| タスクブランチの削除に失敗 | 0 | JSON に残したブランチ名と理由が入る |

### Error Flow

```
git の削除が失敗 → 対象を残した扱いで理由を JSON に入れる → 終了コード 0
手順 4 → JSON を読む → 残したブランチ名と理由を wake フェーズの報告に書く → 手順 3 の status は変えず手順 5 に進む
```

## Performance Optimization

該当なし。

## Assumptions

- A-worktree-remove-failure: タスク worktree の削除に失敗したときは、ブランチ削除を試さず、両方の理由を返す
- A-worktree-remove-failure-risk: タスク worktree が別のブランチに切り替わっていた場合、消せるはずのタスクブランチも残る。これは許容し、残したことを報告に書く
- A-already-absent: worktree やブランチが既に無いときは片付け済みとして扱い、対象ごとに「既に無い」と区別して返す。不在は、worktree は git の登録一覧、ブランチは git の ref 解決で判定し、パスの有無だけでは判定しない
- A-registered-but-missing-dir: worktree のディレクトリが無いのに git の登録が残っている場合は「既に無い」とせず、git worktree remove を試し、失敗したら FR6 と同じく worktree を残した扱いで理由を返す。git worktree prune は実行しない
- A-exit-status: 結果は標準出力の JSON で返し、残したものがあっても終了コードは 0。入力不正と内部エラーだけ 0 以外
- A-exit-status-risk: 呼び出し側が終了コードだけを見ると残したものを見落とすため、手順 4 には JSON を読んで残したブランチ名と理由を wake の報告に書くことを明記する
- A-version: plugin.json と marketplace.json の version は変えない
- A-step4-wording-pinned: 手順 4 の見出し「4. **Clean up** every newly-merged task's worktree and branch:」、失敗時の決まりの文言、手順 5 の後の batch mode 段落の書き出しは変えない

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

なし。

## References

- 要件定義書: `feature-docs/wake-task-cleanup-script/REQUIREMENTS.md`
- implement-phase.md: implement フェーズの手順書（手順 4 を書き換える）

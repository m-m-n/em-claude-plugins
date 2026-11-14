# Feature: design-mock-hot-reload

## Overview

`/em-workflow:design` の合意ループ（Step 4）で、対象 feature のモックをローカルの開発用サーバーで配信し、モックの書き換えをブラウザにホットリロードで反映する。締め（Step 6）でサーバーを `TaskStop` で止める。モックの表示状態は URL のクエリ `?state=<name>` で切り替えられるようにする。

要件は `feature-docs/design-mock-hot-reload/REQUIREMENTS.md` を参照する。

## Objectives

- `/em-workflow:design` の合意ループで、ブラウザでモックを確認 → チャットで指示 → 修正がホットリロードで即反映、の流れを回せるようにする。
- モックの表示状態（SPEC の空・エラー等）を URL のクエリで切り替えられるようにする。

## User Stories

### US1: 合意ループでモックをホットリロードで確認する
`/em-workflow:design` の利用者として、合意ループでモックの URL を案内され、修正がブラウザに自動で反映されるようにしたい。

**Acceptance Criteria:**
- [ ] AC-1: `em-workflow/skills/design/SKILL.md` の Step 4 に、モックを配信するローカルの開発用サーバー（例: `bun ./<mock>.html`）を `run_in_background` で起動し、URL をユーザーに案内する手順がある
- [ ] AC-2: 同じファイルの Step 6 に、起動したサーバーを `TaskStop` で止める手順がある。frontmatter の `allowed-tools` に `TaskStop` がある
- [ ] AC-3: モックを書き換えるとブラウザ側が自動で更新される（開発用サーバーの機能による。モックのファイルに再読み込みのコードは入れない）
- [ ] AC-7: design SKILL.md にプロセスを止めるシグナル送出コマンドが出てこない

### US2: URL のクエリで表示状態を切り替える
`/em-workflow:design` の利用者として、`?state=<name>` を付けたモックの URL で、その状態のセクションだけを見たい。

**Acceptance Criteria:**
- [ ] AC-4: `em-workflow/agents/designer.md` のモック規律に、URL のクエリ（`?state=<name>`）で表示状態を切り替える規則がある。クエリが無いときは全状態を表示する
- [ ] AC-5: モック規律の 1 ファイル完結・トークンの CSS 変数・SPEC 状態網羅の 3 点が designer.md に残っていて、design SKILL.md Step 4 の要約も残っている

### US3: 開発用サーバーが使えない環境で合意ループを回す
`/em-workflow:design` の利用者として、開発用サーバーのコマンドが無い環境でも、これまでどおりモックを直接開いて合意ループを回したい。

**Acceptance Criteria:**
- [ ] AC-6: 開発用サーバーのコマンドが無い、または起動に失敗したときの扱い（ファイルを直接開いてもらい、手で再読み込みしてもらう）が design SKILL.md に書かれている
- [ ] AC-8: 既存のテスト（`tests/test_refitted_worker_agents.py` と `tests/test_muse_consent_no_new_questions.py` を含む）が `python3 -m unittest discover -s tests` で全部通る

## Technical Requirements

### Functional Requirements
- **FR1:** 合意ループでの開発用サーバー起動と URL 案内 — `em-workflow/skills/design/SKILL.md` の Step 4（合意ループ）に、対象 feature のモックを配信するローカルの開発用サーバー（例: `bun ./<mock>.html`）を Bash の `run_in_background` で起動し、サーバーの出力に出た URL をユーザーに案内する手順を書く。「モックはブラウザで開いてもらう」の記述はこの手順に置き換える。
- **FR2:** 締めでの TaskStop による停止 — Step 6（締め）で、FR1 で起動したサーバーのタスクを `TaskStop` で止める手順を書く。サーバーを起動していない場合は何もしない。タスクがすでに終わっていて止められなくても締めを続ける。design SKILL.md の frontmatter `allowed-tools` に `TaskStop` を加える。
- **FR3:** 書き換え時の自動更新 — モックファイルを書き換えると、開発用サーバーの機能によりブラウザ側が自動で更新される。モックのファイル自体には再読み込みのためのコードを書かない。
- **FR4:** URL クエリによる表示状態の切り替え — `em-workflow/agents/designer.md` の Design Artifact Rules にあるモック規律に、URL のクエリ `?state=<name>` で `data-state="<name>"` のセクションだけを表示する切り替えを入れる。切り替えはモック内のインラインの素の JavaScript で行う（フレームワーク不使用・外部リクエストなし）。クエリが無いときは、これまでどおり全状態のセクションを並べて表示する。
- **FR5:** 開発用サーバーのコマンドが無い環境での扱い — Step 4 でサーバーを起動する前に、コマンドがあるか（例: `command -v bun`）を timeout を指定した Bash で確かめる。コマンドが無いとき、または起動に失敗したときは、今の手順に戻る。モックファイルのパスを案内し、ユーザーにブラウザで直接開いてもらう。修正後はユーザーが手で再読み込みする。この場合も `?state=` での切り替えは使える。新しい `AskUserQuestion` は足さない。
- **FR6:** モック規律の維持 — モック規律の既存 3 点を崩さない。1 ファイルで完結する（インライン CSS、外部リクエストなし、JS フレームワークなし）、トークンを CSS カスタムプロパティとして埋め込む、SPEC に出てくる状態を全部入れる。design SKILL.md Step 4 のモック規律の要約（self-contained / token CSS 変数 / SPEC 状態網羅）も残す。

### Non-Functional Requirements
- **NFR1 - プロセス停止は TaskStop のみ:** design SKILL.md の手順に、プロセスを止めるシグナル送出コマンドを書かない。開発用サーバーの停止は `TaskStop` だけで行う。
- **NFR2 - version を触らない:** `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version を変えない。
- **NFR3 - 対話の質問数を増やさない:** `em-workflow/skills/design/SKILL.md` に出てくる `AskUserQuestion` は 2 回のまま（`tests/test_muse_consent_no_new_questions.py` で固定されている）。
- **NFR4 - 書き込み範囲の境界:** design SKILL.md の「境界」節にある書き込み先の制限を変えない。開発用サーバーの起動は、書き込み先を増やす手順にしない。
- **NFR5 - ローカルだけで配信する:** 開発用サーバーはローカルの開発用として案内する。手順に書く URL は、サーバーの出力に出たローカルの URL にする。

## Implementation Approach

### Architecture

**System Architecture:**

変更対象は Markdown の 2 ファイル。

- `em-workflow/skills/design/SKILL.md`
    - frontmatter `allowed-tools` に `TaskStop` を加える（FR2）。
    - Step 4: コマンドの確認（FR5）→ `run_in_background` での起動と URL 案内（FR1）→ 使えないときの現行手順（FR5）。モック規律の要約は残す（FR6）。
    - Step 6: 起動したサーバーを `TaskStop` で止める（FR2）。
- `em-workflow/agents/designer.md`
    - Design Artifact Rules の Mockups の項に `?state=<name>` の切り替え規則を入れ、小さなインラインスクリプトを認める書き方に直す（FR4）。既存 3 点は残す（FR6）。

**Component Diagram:**
```
design SKILL.md (Step 4) --run_in_background--> 開発用サーバー --配信--> ブラウザ
design SKILL.md (Step 6) --TaskStop----------> 開発用サーバー
designer.md (モック規律) --規則--> モック HTML（?state= の切り替えスクリプトを含む）
```

### Data Flow

```
Step 4 開始
  → 対象 feature のモックがあるか
      無い → 起動しない
      ある → timeout を指定した Bash で command -v bun 等を確かめる
          無い / 起動に失敗 → モックのパスを案内し、直接開いてもらう（手で再読み込み）
          ある → run_in_background で起動 → 出力の url / Routes 行から URL を読んで案内
  → 合意ループ（モックを書き換え → ブラウザが自動で更新）
      モックが増え、起動中のサーバーが配信していない → TaskStop で止め、全モックを対象に起動し直す
Step 6
  → 起動したサーバーがあれば TaskStop で止める（すでに終わっていても締めを続ける）
```

### 決定事項

- サーバーは対象 feature のモックがあるときだけ、Step 4 で起動する。システム全体スコープでモックを扱わないときは起動しない。
- `tokens.html` はサーバーの対象に含めず、これまでどおり直接開いてもらう。
- ポートは決め打ちしない。サーバーの出力の `url` / `Routes` 行から URL を読んで案内する。
- ループの途中でモックが増えたら、`TaskStop` で止め、その feature の全モックを起動対象にして 1 つのサーバーとして起動し直す。複数のモックを渡すと、各モックは `/<ファイル名から拡張子を除いた名前>` で配信される（Bun 1.4.4 で確認）。
- 開発用サーバーのコマンドが無い・起動に失敗したときは、質問せず現行手順に戻る。
- `?state=<name>` はモック内の小さなインラインの素の script が読み、一致する `data-state` セクションだけを表示する。無指定・未知の値は全状態を表示する。
- 自動更新は開発用サーバーの機能に任せる。開発用サーバーが配信時に差し込む更新用スクリプトはモックのファイルには含まれない。モック規律の外部リクエストなしは、ファイルの中身に対する規則として保つ。
- designer エージェント（develop の design ステップ）はサーバーを起動しない。tools に Bash を足さず、クエリ切り替えの規則に沿ったモックを書くだけにする。
- designer.md の既存の文言のうち `tests/test_refitted_worker_agents.py` が固定しているもの（autonomy の宣言、Boundaries、write policy の文など）は変えない。
- WebMCP への対応はスコープ外。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `tests/test_muse_consent_no_new_questions.py`: design SKILL.md の `AskUserQuestion` の数（2 回）を固定している。
- `tests/test_refitted_worker_agents.py`: designer.md の既存の文言を固定している。

**External Dependencies:**
- bun: ローカルの開発用サーバーの例。無い環境では FR5 の手順に戻る。

### File Structure

```
em-workflow/
├── skills/
│   └── design/
│       └── SKILL.md      # Step 4 / Step 6 / allowed-tools
└── agents/
    └── designer.md       # Design Artifact Rules のモック規律
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/design-mock-hot-reload/**`
- `test-docs/design-mock-hot-reload/**`

`feature-docs/design-mock-hot-reload/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/design-mock-hot-reload/**` covers
`test-docs/design-mock-hot-reload/{T}.tests.yaml`, the per-task test record.
It is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/design-mock-hot-reload/` directory at all; the declared
`test-docs/design-mock-hot-reload/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: design SKILL.md の Step 4 の節に `run_in_background` と開発用サーバーのコマンド例、URL の案内があることを確かめる静的テスト - AC-1（FR1, NFR5）
- [ ] TS-2: Step 6 の節に `TaskStop` があり、frontmatter の `allowed-tools` に `TaskStop` があることを確かめる静的テスト - AC-2（FR2）
- [ ] TS-3: designer.md の Design Artifact Rules の Mockups の項に `?state=` と `data-state` があり、クエリが無いときに全状態を表示する旨があることを確かめる静的テスト - AC-4（FR4）
- [ ] TS-4: designer.md の Mockups の項に self-contained / CSS custom properties / SPEC の状態の必須が残っていること、design SKILL.md Step 4 にモック規律の要約が残っていることを確かめる静的テスト - AC-5（FR6）
- [ ] TS-5: design SKILL.md にコマンドが無いときの扱い（直接開く・手で再読み込み）が書かれていることを確かめる静的テスト - AC-6（FR5）
- [ ] TS-6: design SKILL.md 全体にプロセスを止めるシグナル送出コマンドが単語として出てこないことを確かめる静的テスト - AC-7（NFR1）

### Manual Tests
- [ ] TS-7: ホットリロードの実際の動作は単体テストにできないため、手動で確認する。サーバーを `run_in_background` で起動し、モックを書き換えてブラウザが更新されることを見て、`TaskStop` で止める - AC-3（FR3）

### Integration Tests
- [ ] TS-8: `python3 -m unittest discover -s tests` で全体を回す - AC-8（NFR3, FR6）

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし

### Edge Cases
- 開発用サーバーのコマンドが無い、または起動に失敗する: 現行手順に戻る（TS-5）
- `?state=` が無い、または値に当たるセクションが無い: 全状態のセクションを表示する（TS-3）

### Performance Tests

該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `?state=` の値に当たる `data-state` セクションが無いときは全状態を表示する。
- **Data Protection:** 開発用サーバーはローカルの開発用として案内し、案内する URL はサーバーの出力に出たローカルの URL にする（NFR5）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
コマンドが無い / 起動に失敗 → モックのパスを案内し、直接開いてもらう（手で再読み込み）
Step 6 でタスクがすでに終わっていて止められない → 締めを続ける
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 〜 AC-8 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/design-mock-hot-reload/REQUIREMENTS.md`

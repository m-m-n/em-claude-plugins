# Feature: destructive-guard-rm-reason-positions

## Overview

destructive-guard の rm 拒否理由・確認理由に出る位置表記（`N番目のrmのM番目の対象`）の N と M を、元のコマンド文字列を左から読んだときの rm と対象の位置に合わせる。複数対象をまとめた rm-recursive の理由文には、対象ごとに位置表記と代替コマンドの雛形を入れる。判定と rule id は変えない。

要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- destructive-guard の rm 拒否理由・確認理由に出る位置表記（N番目のrmのM番目の対象）が、元のコマンド文字列を左から読んだときの rm と対象の位置に一致する
- 複数対象をまとめた rm-recursive の理由文にも、対象ごとに位置と代替コマンドの雛形が入る
- 判定（deny / ask / allow）と rule id は変えない

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** 呼び出し番号は元のコマンド上の出現順。rm の呼び出し番号（N番目のrm）は、元のコマンド文字列に rm のコマンド語が現れる順（左から 1 始まり）で振る。`$(…)`・バッククォートの本文、`bash -c` / eval / here-string のペイロード、シェルに渡るヒアドキュメント本文の中にある rm も、元の文字列上の位置で順序を決める。置換で始まる文（`$(which rm) -rf x` など）では、その置換トークンの位置を rm の位置とする。番号は全文を走査し終えてから振り、その後で理由文を組み立てる。
- **FR2:** 複数の経路で判定しても呼び出し番号は 1 つ。同じ rm を複数の経路で判定しても（置換で始まる文を `route_substitution_headed_statement()` と通常経路の両方で `check_rm()` に渡すなど）、呼び出し番号は 1 つだけ消費する。同じトークンには、どの経路でも同じ対象番号が付く。対象番号は元の引数位置に対応する。
- **FR3:** 対象番号は `--` を考慮した元のオペランド位置。対象番号（M番目の対象）は `--` を考慮した元のオペランド位置で数える。最初の `--` より前では `-` で始まる語はオプションで数えない。最初の `--` 自体は数えない。`--` より後ろの語は、`-` で始まる語や 2 つ目以降の `--` も含めて全部オペランドとして数える。`.is_operator` の語は今までどおり数えない。何を判定するかは変えず、変わるのは番号だけ（`--` の後ろの `-` 始まりのオペランドは、今までどおり判定しない）。
- **FR4:** まとめた rm-recursive の理由文に代替コマンドの雛形を入れる。最も強い判定に複数の対象が並んで `strongest_rm_decision()` が理由文を 1 つにまとめる場合、単独なら `deletion_alternative()` の雛形が付く rm-recursive の対象については、位置表記とその雛形（gio trash / mv / 制御文字の定型文）を対にして並べる。雛形の選び方（gio の有無、HOME 配下か、制御文字の有無）は変えない。対象の生文字列は入れない。単独でも雛形が付かない対象（rm-root、rm-unresolvable、一部が置換の rm-recursive）には雛形を付けない。
- **FR5:** 判定・rule id・既存の文言を保つ。どのコマンドでも判定と rule id は変えない。rm-root の理由文は今までどおり `RM_ROOT_SHAPE` のトークンをそのまま出す。`CLAUDE_BATCH` 下で ask を deny に落とす文言も変えない。置換だけでできた対象に付ける固定の目印 [`$(...)`] も残す。
- **FR6:** 回帰テスト。再現手順の 4 つのコマンドと `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` について、理由文の位置表記と代替コマンドの雛形を確かめる unittest を `tests/` の下に追加する。テストはフックを subprocess で起動し、PreToolUse の JSON を標準入力から渡す。
- **FR7:** 番号の振り方を書いたコメント・docstring を実装に合わせる。`rm_target_designation()`、`check_rm()`、`route_substitution_headed_statement()` の docstring と、`main()` の呼び出し番号カウンタのコメントを、FR1-FR3 の番号の振り方に合わせて書き直す。

### Non-Functional Requirements
- **NFR1:** 同じコマンド文字列からは、いつも同じ位置表記と同じ理由文が出る
- **NFR2:** 理由文に rm 対象の生文字列を入れない。フックの stdout に制御文字を出さない（destructive-guard-rm-holes の FR4 / NFR3 を保つ）
- **NFR3:** テストは Python 標準ライブラリの unittest だけを使う。HOME と PATH はテスト側で明示して渡す
- **NFR4:** プラグインの version は触らない（`.claude/rules/core-plugin-version-bump.md`）

## Implementation Approach

### Architecture

変更対象は destructive-guard フックの理由文の組み立てと番号付けだけ。判定の処理は変えない（FR5）。

**Component Diagram:**
```
main()                                  呼び出し番号カウンタ（FR1, FR7）
├── route_substitution_headed_statement()  置換で始まる文の経路（FR2, FR7）
├── check_rm()                          通常経路（FR2, FR7）
├── rm_target_designation()             位置表記の N / M（FR1, FR3, FR7）
└── strongest_rm_decision()             まとめた理由文（FR4）
    └── deletion_alternative()          代替コマンドの雛形（FR4）
```

### Data Flow

```
コマンド文字列 → 全文を走査（rm のコマンド語と元の文字列上の位置を集める）
              → 呼び出し番号を出現順で振る（FR1, FR2）
              → 対象番号を元のオペランド位置で振る（FR3）
              → 理由文を組み立てる（FR4, FR5）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- destructive-guard-rm-holes の FR4 / NFR3: 理由文に対象の生文字列を入れない・stdout に制御文字を出さない取り決めを保つ（NFR2）

**External Dependencies:**
- Python 標準ライブラリの unittest（NFR3）

### File Structure

```
tests/
└── （FR6 の回帰テスト。既存の tests/test_destructive_guard_rm_reason.py と並ぶ）
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

この SPEC は、フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/destructive-guard-rm-reason-positions/**`
- `test-docs/destructive-guard-rm-reason-positions/**`

`feature-docs/destructive-guard-rm-reason-positions/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照する（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-rm-reason-positions/**` に含まれるもの: タスクごとのテスト記録 `test-docs/destructive-guard-rm-reason-positions/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照する（引用のみ、ルールは再掲しない）。

この 2 つの既定の宣言は、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセットの主張であり、検証時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/destructive-guard-rm-reason-positions/` ディレクトリを生成しないが、その場合も宣言された `test-docs/destructive-guard-rm-reason-positions/**` は正しい。宣言されたパスが生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS1（AC1 / FR1, FR5）: `echo "$(rm -rf /var/x)"; rm -rf /tmp/y` を渡し、deny / rm-recursive で、位置表記が「1番目のrmの1番目の対象」だけであることを確かめる
- [ ] TS2（AC2 / FR1, FR5）: `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` を渡し、拒否対象が「1番目のrmの1番目の対象」と示されることを確かめる
- [ ] TS3（AC1 / FR1, FR5）: 入れ子の形 `rm -rf $(rm -rf /var/x)` を渡し、内側の rm の対象が「2番目のrmの1番目の対象」と示されることを確かめる（外側の rm が先に現れる）
- [ ] TS4（AC3 / FR2, FR5）: `$(printf rm) rm -rf /tmp/cache; rm -rf /var/valuable` を渡し、位置表記の呼び出し番号が {1, 2} だけで、`/var/valuable` が「2番目のrmの1番目の対象」であることを確かめる
- [ ] TS5（AC4 / FR3, FR5）: `rm -rf -- -cache /tmp/scratch /var/valuable` を渡し、拒否対象が「1番目のrmの3番目の対象」と示されることを確かめる
- [ ] TS6（AC5 / FR4, FR5, NFR2）: HOME を固定し、`rm -rf /var/a /var/b` を gio ありと gio なしで、HOME 配下の 2 対象を gio ありで渡す。まとめた理由文で、どちらの位置にも雛形が付き、対象の文字列が無いことを確かめる

### Integration Tests
- [ ] TS7（AC6 / FR5）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行し、全件成功することを確かめる
- [ ] TS8（AC7 / FR6, NFR3）: `python3 -m unittest discover -s tests` を実行し、全件成功することを確かめる

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 置換で始まり、置換の中身から rm と読める文（`$(printf rm) rm -rf /tmp/cache`）: 置換トークンを rm のコマンド語として扱い、書いてある `rm` の語は 1 番目の対象、`/tmp/cache` は 2 番目の対象になる。どちらの経路でも同じ番号を使う（前提 A1）
- [ ] 置換から rm と読めない文（`$(foo) rm -rf /x`）: 今までどおり書いてある `rm` がコマンド語になる（前提 A1）
- [ ] `--` の後ろにある `-` 始まりのオペランド: 番号には入れるが判定はしない（前提 A2）
- [ ] `--` の無い単独の `-`: 今までどおりオペランドとして数えない（前提 A3）
- [ ] 判定が 1 件だけのとき: 今までどおりその対象の理由文をそのまま使う（前提 A5）

### Performance Tests
該当なし

## Security Considerations

- **Input Validation:** 何を判定するかは変えない（FR3, FR5）
- **Data Protection:** 理由文に rm 対象の生文字列を入れない。フックの stdout に制御文字を出さない（NFR2）

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: `echo "$(rm -rf /var/x)"; rm -rf /tmp/y` の理由文が `/var/x` を「1番目のrmの1番目の対象」と示し、「2番目のrm」を含まない。判定は deny、rule id は rm-recursive のまま
- [ ] AC2: `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` の理由文が拒否対象を「1番目のrmの1番目の対象」と示す。判定と rule id は変わらない
- [ ] AC3: `$(printf rm) rm -rf /tmp/cache; rm -rf /var/valuable` の理由文に「3番目のrm」が出ない。位置表記は「1番目のrm」と「2番目のrm」だけで、`/var/valuable` は「2番目のrmの1番目の対象」と示される。判定と rule id は変わらない
- [ ] AC4: `rm -rf -- -cache /tmp/scratch /var/valuable` の理由文が `/var/valuable` を「1番目のrmの3番目の対象」と示す。判定と rule id は変わらない
- [ ] AC5: `rm -rf /var/a /var/b` の理由文に、「1番目のrmの1番目の対象」と「1番目のrmの2番目の対象」のそれぞれについて代替コマンドの雛形（gio trash か mv）が入り、`/var/a` も `/var/b` も含まない。HOME 配下で gio がある場合は gio trash、gio が無い場合や HOME の外では mv の雛形になる
- [ ] AC6: `python3 em-workflow/hooks/tests/run-destructive-guard.py` の既存ケースで、判定が 1 件も変わらない
- [ ] AC7: AC1-AC5 を確かめる回帰テストが tests/ の下にあり、`python3 -m unittest discover -s tests` が成功する（既存の tests/test_destructive_guard_rm_reason.py も含む）

## Assumptions

- A1: 置換で始まり、置換の中身から rm と読める文（`$(printf rm) rm -rf /tmp/cache`）では、置換トークンを rm のコマンド語として扱い、その後ろの語からオペランドを数える。この場合、書いてある `rm` の語は 1 番目の対象、`/tmp/cache` は 2 番目の対象になる。どちらの経路でも同じ番号を使う。この文で deny になるのは置換経由の経路が `rm` の語を対象として判定するためで、FR5 で判定を変えないので、この対象にも位置表記が要る。判定される対象すべてに重ならない番号を付けられる数え方はこれだけ。置換から rm と読めない文（`$(foo) rm -rf /x`）では、今までどおり書いてある `rm` がコマンド語になる
- A2: `--` の後ろにある `-` 始まりのオペランドは、番号には入れるが判定はしない。`rm -rf -- -targets` が allow になるのは前からある判定の穴で、FR5 によりこの機能の範囲外（round1.yaml a7026abc0ff69de7 の suggestion）
- A3: `--` の無い単独の `-` は、今までどおりオペランドとして数えない。FR3 の範囲は `--` の扱いだけ
- A4: 位置表記の書式 `N番目のrmのM番目の対象`（置換だけの対象に付ける [`$(...)`] を含む）は変えない。変わるのは N と M の値だけ
- A5: 判定が 1 件だけのときの理由文は、今までどおりその対象の理由文をそのまま使う。FR4 が変えるのは、最も強い判定に対象が 2 つ以上並ぶときのまとめた理由文だけ
- A6: destructive-guard-cases.json に追加は不要（判定は変わらず、誤爆も見逃しも新しく見つかっていない）。理由文の検証は unittest 側に置く

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/destructive-guard-rm-reason-positions/REQUIREMENTS.md`
- `.claude/rules/core-plugin-version-bump.md`

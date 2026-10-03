# Feature: destructive-guard-herestring-subst-only

## Overview

`em-workflow/hooks/destructive-guard.py` の `extract_shell_payload_anchored()` の here-string（`<<<`）分岐で、here-string の対象がコマンド置換だけのシェル呼び出し（例: `bash <<< $(echo hi)`）を含む複合コマンドを渡すと `IndexError` が起き、フックが exit 1 で終わる。この修正で範囲外参照をなくし、同じコマンド列の後続の破壊的コマンドを通常どおり判定する。

## Objectives

- here-string（<<<）の対象がコマンド置換だけのシェル呼び出しを含む複合コマンドで、destructive-guard が IndexError で落ちず、同じコマンド列の破壊的コマンドを通常どおり判定する（fail-open の解消）

## Acceptance Criteria

- [ ] AC-1: `bash <<< $(echo hi); rm -rf /var/b` でフックが exit 0 で deny を返す
- [ ] AC-2: ``sh <<< `x`; rm -rf /var/b`` でフックが exit 0 で deny を返す
- [ ] AC-3: destructive-guard-cases.json に AC-1 / AC-2 のケースがあり、`python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する
- [ ] AC-4: 既存の here-string 関連ケース（`bash <<<$(true) 'rm -rf /home/sakura/valuable'` の deny、`bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` の allow など）の判定が変わらない

## Technical Requirements

### Functional Requirements

- **FR1: here-string 分岐の範囲外参照をなくす** — `em-workflow/hooks/destructive-guard.py` の `extract_shell_payload_anchored()` の here-string 分岐で、`j = _payload_index(words, 1)` の直後の条件を `0 < j < len(words) and not getattr(words[j], "substitution_only", False)` にする。`j` が `words` の範囲外のときは `words[j]` を参照せず、既存のフォールバック（`marked_redirects[i + 1]` を返す）に進む。
- **FR2: 後続の破壊的コマンドを判定する** — `bash <<< $(echo hi); rm -rf /var/b` と ``sh <<< `x`; rm -rf /var/b`` を PreToolUse 入力として渡したとき、フックは traceback を出さず exit 0 で終わり、後続の `rm -rf /var/b` に対して deny を出す。
- **FR3: 再発検出ケースを修正前に追加する** — 修正の前に `em-workflow/hooks/tests/destructive-guard-cases.json` に `["deny", "here-string 置換のみ + 後続 rm", "bash <<< $(echo hi); rm -rf /var/b"]` を追加する。バッククォート形 ``sh <<< `x`; rm -rf /var/b`` も deny ケースとして追加する。既存の deny / ask ケースは消さない。

### Non-Functional Requirements

- **NFR1: here-string 分岐以外の挙動を変えない** — here-string 分岐以外（`-c` 分岐、`eval` 分岐、`_payload_index()` 本体）の挙動は変えない。
- **NFR2: version を変更しない** — `plugin.json` / `marketplace.json` の version は変更しない（patch は main への push 時に Actions が上げる）。

## Assumptions

- `words` が `['bash']` のように 1 要素のとき、修正後は `marked_redirects[i + 1]`（置換プレースホルダ）をペイロードとして返す既存フォールバックに進む。後続の `rm -rf /var/b` は同じコマンド列の別の文として通常どおり判定される。
- バッククォート形の再現手順も再発検出ケースとして追加する（タスク記述の完了の定義が明示するのは `$()` 形のみ）。
- `bash <<< $(echo hi)` 単独（後続 rm なし）の判定はこの修正で新たに固定しない。
- `_payload_index()` の「START が範囲外なら START を返す」という契約は変えず、呼び出し側で範囲を確認する。

## Implementation Approach

### 変更箇所

- `em-workflow/hooks/destructive-guard.py` — `extract_shell_payload_anchored()` の here-string 分岐、`j = _payload_index(words, 1)` の直後の条件（FR1）
- `em-workflow/hooks/tests/destructive-guard-cases.json` — deny ケース 2 件の追加（FR3）

### 手順

1. `destructive-guard-cases.json` に FR3 の 2 ケースを追加する。
2. 修正前のコードでスイートを実行し、追加ケースが FAIL（exit 1）になることを確認する（TS-4）。
3. FR1 の条件変更を入れる。
4. `python3 em-workflow/hooks/tests/run-destructive-guard.py` で全件 pass を確認する（TS-1〜TS-3）。

### Dependencies

**Internal Dependencies:**
- `_payload_index()`: 既存の契約のまま呼び出し側で使う（NFR1）
- `em-workflow/hooks/tests/run-destructive-guard.py`: ケーススイートの実行

**External Dependencies:**
- なし

## Declared Change Set

上の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

機能固有のパスに加えて、ワークフローが生成する次の 2 エントリを既定で宣言する。

- `feature-docs/destructive-guard-herestring-subst-only/**`
- `test-docs/destructive-guard-herestring-subst-only/**`

`feature-docs/destructive-guard-herestring-subst-only/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。

`test-docs/destructive-guard-herestring-subst-only/**` はタスクごとのテスト記録 `test-docs/destructive-guard-herestring-subst-only/{T}.tests.yaml` を含む。`implement-phase.md` が生成・所有する。

この 2 エントリは SPEC で明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言で、verify 時に観測した実際の変更集合が宣言集合に含まれていればよい。宣言したパスが実在しなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-1: `bash <<< $(echo hi); rm -rf /var/b` を入力し、判定が deny（exit 0）であることをケーススイートで確認する（FR1, FR2, FR3 / AC-1）
- [ ] TS-2: ``sh <<< `x`; rm -rf /var/b`` を入力し、判定が deny（exit 0）であることをケーススイートで確認する（FR1, FR2, FR3 / AC-2）
- [ ] TS-3: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行し、既存ケースを含め全件 pass することを確認する（NFR1 / AC-3, AC-4）
- [ ] TS-4: 修正前のコードで TS-1 のケースが FAIL（exit 1）になることを確認してから修正する（FR3）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] `words` が 1 要素（`['bash']`）のとき、`words[j]` を参照せず `marked_redirects[i + 1]` のフォールバックに進む（FR1）

## Error Handling

- 対象入力でフックが traceback を出さず exit 0 で終わる（FR2）

## Success Criteria

- [ ] FR1〜FR3 が実装され、テストされている
- [ ] TS-1〜TS-4 が通る
- [ ] AC-1〜AC-4 を満たす

## Open Questions

- なし

## References

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
- `.claude/rules/hook-tests.md`

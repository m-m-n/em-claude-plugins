---
name: security-review-model
description: セキュリティ観点の Codex レビューで使うモデルの指定と更新手順。「新しい Astra が出たから更新して」「セキュリティレビューのモデルを変えて」のように、セキュリティレビューのモデルを変える・確かめる依頼を受けたときに使う。
---

# セキュリティレビューのモデル

## 方針

- セキュリティ観点の Codex レビューは、Codex の最上位モデルを使う。
- それ以外の観点は `model` を書かず、Codex の推奨既定モデルを使う。
- 推論の深さはラッパーが固定する `xhigh` のままにする。

## 指定している場所

次の 2 ファイルの security 観点の codex エントリ。2 つは同じ値に揃える。

- `em-workflow/references/reviewers.yaml`
- `em-review/references/reviewers.yaml`

```yaml
  - perspective: security
    ...
      - {harness: codex, model: <slug>}
```

## 更新手順

1. `codex debug models` で一覧を取得し、正式名称（`slug`）を確かめる。
   表示名（`display_name`）ではなく `slug` を指定する。

    ```
    codex debug models | python3 -c '
    import json,sys
    d=json.JSONDecoder().raw_decode(sys.stdin.read().lstrip())[0]
    for m in d["models"]:
        print(m["slug"], "|", m["display_name"], "|", m.get("visibility"), "|",
              [e["effort"] for e in m.get("supported_reasoning_levels", [])])
    '
    ```

2. 対象モデルが `xhigh` に対応していることを確かめる。
3. その `slug` で 1 回呼べることを確かめる。

    ```
    cd /tmp && codex exec --color never --skip-git-repo-check --ignore-user-config \
      -s read-only -m <slug> -c 'model_reasoning_effort="xhigh"' "Reply with just OK" </dev/null
    ```

4. 上の 2 ファイルの security の codex エントリを `<slug>` に書き換える。
5. テストの期待値にある `slug` も同じ値に書き換える。
    - `tests/test_reviewers_primary_chains.py` の `EXPECTED_CHAINS`
    - `tests/test_contributor_tier_criteria.py` の `EM_REVIEW_EXPECTED_CHAINS`
6. テストを走らせる。

    ```
    python3 -m unittest tests.test_codex_wrapper_model_flag \
      tests.test_reviewers_primary_chains tests.test_contributor_tier_criteria
    ```

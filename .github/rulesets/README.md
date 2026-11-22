# Repository rulesets

`main-non-fast-forward.json` in this directory defines the repository ruleset `main-non-fast-forward`. It forbids non-fast-forward updates of `main` and has no bypass actor. The file is the request body of the GitHub REST API call that creates a repository ruleset.

Merging the file does not create the ruleset on GitHub. The ruleset takes effect only after a maintainer runs the procedure below.

The ruleset named `main` already exists and is a separate ruleset. The existing `main` ruleset is not changed by this procedure.

## Create and confirm the ruleset

Run the steps in order, in one shell session, from the root of a clone of the repository.

### 1. Preconditions

- The pull request that adds `.github/rulesets/main-non-fast-forward.json` is merged, and the clone is on `main` with that merge pulled.
- `gh` is authenticated (`gh auth status`) with permission to administer the repository's rulesets.

`{owner}` and `{repo}` in the commands below are filled in by `gh` from the clone's remote.

### 2. Check for an existing ruleset of the same name, and record `main`

Look for a ruleset named `main-non-fast-forward`, so that the creation does not make a duplicate:

```sh
gh api repos/{owner}/{repo}/rulesets --jq '.[] | select(.name == "main-non-fast-forward") | .id'
```

No output means that no such ruleset exists yet; go on. A printed id means that it already exists: do not run step 3, and go on to step 4.

Record the existing `main` ruleset, for the comparison in step 5. The first command must print its id:

```sh
MAIN_ID=$(gh api repos/{owner}/{repo}/rulesets --jq '.[] | select(.name == "main") | .id')
gh api "repos/{owner}/{repo}/rulesets/$MAIN_ID" --jq '.' > /tmp/main-ruleset-before.json
```

### 3. Create the ruleset

Post the definition file as the request body to the repository rulesets endpoint:

```sh
gh api --method POST repos/{owner}/{repo}/rulesets --input .github/rulesets/main-non-fast-forward.json
```

### 4. Confirm the created ruleset

List the repository's rulesets. `main-non-fast-forward` appears next to `main`:

```sh
gh api repos/{owner}/{repo}/rulesets --jq '.[] | {id, name, target, enforcement}'
```

Show the new ruleset:

```sh
NEW_ID=$(gh api repos/{owner}/{repo}/rulesets --jq '.[] | select(.name == "main-non-fast-forward") | .id')
gh api "repos/{owner}/{repo}/rulesets/$NEW_ID" --jq '{name, target, enforcement, bypass_actors, ref_name: .conditions.ref_name, rules: [.rules[].type]}'
```

The output must show all of the following:

- `name` is `main-non-fast-forward`
- `target` is `branch`
- `enforcement` is `active`
- `bypass_actors` is `[]`
- `ref_name` has `include` exactly `["refs/heads/main"]` and `exclude` `[]`
- `rules` is exactly `["non_fast_forward"]`, a single rule of type `non_fast_forward`

### 5. Confirm that the existing `main` ruleset is unchanged

Compare the `main` ruleset with the record taken in step 2. No output from `diff` means that it is unchanged:

```sh
gh api "repos/{owner}/{repo}/rulesets/$MAIN_ID" --jq '.' | diff /tmp/main-ruleset-before.json -
```

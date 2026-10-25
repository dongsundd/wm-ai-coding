---
name: code-commit
description: Prepare and perform scoped local Git commits under existing authorization
  when development-workflow selects a commit operation during development or delivery.
---

# Code Commit

Run only from a controller operation handoff for apply, verify, close or archive. A local commit can occur during development; it does not complete a task, replace testing or advance a stage. Push, merge and publication are separate actions requiring their own authorization.

Consumes explicit file scope, current diff, required passing check argv, commit message and an existing execution authorization reference. Produces a preview or local commit ID and its actual paths.

1. Inspect Git status, staged and unstaged changes, project commit conventions and current acceptance. Preserve unrelated user edits. Never blanket-stage the repository, discard changes, bypass hooks or amend history implicitly.
2. Choose only user-authorized paths. If a selected file mixes unrelated work, return a scoped staging plan for the host; do not silently include it. Existing unrelated staged paths must remain untouched and block a broad commit.
3. Run required checks and re-inspect the final diff. Changes made by checks need review and another check run.
4. Present the concrete scope and message when execution is not yet authorized. Existing authorization persists; do not ask again when it already covers the exact action.
5. When authorized, stage only the reviewed paths and create one local commit. Report its hash and paths; report hook-induced unexpected changes accurately rather than claiming the intended scope succeeded.

An optional deterministic helper is [commit.py](scripts/commit.py). Default mode previews without staging or committing. Execute requires `--execute --authorization-reference <existing-reference>` plus `--files`, `--message` and a final `--check <executable> <args...>`. It uses argv without shell interpolation and refuses unrelated staged paths, unsupported file scope, dirty check outputs or an expanded hook commit. It does not authenticate the reference or resolve mixed hunks.

Example, with repository path, scope and check adjusted to the project:

```text
python scripts/commit.py --repo <repo> --files src/example.py tests/test_example.py --message "Fix example handling" --check python -m unittest discover -s tests
```

The helper cannot determine whether all changes inside a selected file are intended; the host must review them. It never runs push, merge or publish. Failure leaves reviewable state and a concrete reason; do not reset user work to conceal it.

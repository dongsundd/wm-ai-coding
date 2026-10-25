---
name: development-workflow
description: Coordinate software development from requirements through design, planning,
  implementation, verification and archive. Select the legal stage before invoking
  another WM skill.
---

# Development Workflow

This is the only WM development controller. The host owns the model loop, permissions and sandbox; WM owns process contracts and evidence. Preserve existing user authorization.

Read `wm --repo <repo> brief` and [workflow](references/workflow.md). Read [runtime](references/runtime.md) for the current operation. Use `status` or `recovery --change <name>` for details; initialize explicitly with `init --no-gitignore` only when needed. Migrate changed workflow/registry checksums before resuming. Never recreate missing historical evidence.

## Stage routing

| State | Primary skill | Required support in order | Exit evidence |
|---|---|---|---|
| clarify | requirements-analysis | none; requirements-research and browser-research when facts are missing | Goals, boundaries, constraints and unresolved questions |
| specify | requirements-specification | technical-design, conditional frontend-design, test-design | Proposal, delta specs, complete design, test design and existing approval |
| tasks | development-planning | none | Sole tasks.md, runnable Check definitions and task baseline |
| apply | feature-development | TDD and applicable profiles; test-execution as needed | Each independent task's current acceptance and receipt |
| verify | change-verification | test-execution, code-review | Current checks, review, requirement/scenario run-ID coverage and verification.json |
| close | specification-sync | none | Validated specification transform and synchronized snapshot |
| archive | change-archive | none | Portable archive evidence and integrity manifest |

Keep these seven stable state IDs. Skills are capabilities, not extra workflow states. Research is conditional; tests and implementation iterate. Git commits can occur during development and are not an archive prerequisite.

## Execute a handoff

1. Select the earliest incomplete legal stage. Announce the change, stage and task. Keep process artifacts under `sdd/`; tasks.md is the only implementation plan.
2. Create the primary `wm handoff --scope <repo-relative-paths>` before work. It records scope and does not invoke a model.
3. Invoke a support/profile with `handoff --skill <name> --parent <running-primary-id> --scope <subset>`. Required supports return in order to that same parent. Run conditional frontend-design after technical-design and before test-design. Only frontend-design writes `## Frontend design`.
4. Finish supports with their actual artifact paths, then finish the primary and call advance. The runtime rejects missing, reversed, stale or unrelated-parent required evidence. Scope or input changes require reconciliation and repeated affected work.
5. During apply, execute one ready independently acceptable task. Use TDD for behavior changes, reproduced root-cause debugging and applicable technology profiles. Every task declares Check IDs; run `wm check`, mark only accepted work, finish-handoff and advance. Continue ready tasks under existing authorization.

CodeGraph structural evidence or its exact unavailable/stale condition plus targeted fallback belongs in design. Record frontend applicability explicitly; confirm design only after technical, frontend and test design are complete. Do not infer consent from files.

`change-initialization` scaffolds an assigned change; `change-management` updates planning and returns to the earliest invalid gate. `git-worktree-management` supplies optional workspace isolation. `code-commit` handles separately authorized local commits; never infer authorization to push, merge or publish.

## Verification and delivery

Run fresh focused and relevant broad tests, static/build checks, applicable browser evidence and coverage. Required test-execution owns actual runs; code-review records findings with honest self/independent mode; change-verification reconciles all evidence. Resolve blockers before closure. Use `wm review` and `verification-summary`; report skipped or failed checks accurately.

Sync against the captured durable preimage, validate and baseline it, then archive. Batch archive iterates an explicit list serially with each change's own gates and handoff. Archived, integrity-valid and delivered are distinct claims.

Use doctor, eval and verify-archive for diagnostics. Host-specific hooks require trust and supported events; they are not full write isolation. Parallel batch checks require distinct host-prepared workspaces, serial integration and final revalidation. Do not start independent reviewers unless requested or otherwise authorized.

Legacy invocation names normalize through registry aliases. They do not create duplicate discoverable skill directories. Reinstall or reload rebuilt packages to update installed caches; source edits alone do not do so.

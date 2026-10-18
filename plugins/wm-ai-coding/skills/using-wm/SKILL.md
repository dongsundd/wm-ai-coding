---
name: using-wm
description: Use when a software-development request may create or change code, OpenSpec artifacts, implementation plans, verification evidence, synchronized specifications, or archived changes.
---

# Using WM

`using-wm` is the single user-facing workflow entry for this plugin. OpenSpec owns the development lifecycle and its artifacts. Independent skills provide focused stage behavior only after this harness selects the change and stage.

## Entry ownership

- Enter here for features, fixes, refactors, planning, implementation, review, verification, synchronization, archival, and delivery.
- A user naming an OpenSpec or supporting skill does not bypass this harness.
- Stage skills never choose the next stage and never invoke one another. They return control to `using-wm`.
- `tasks.md` is the only implementation plan. Do not create a second Superpowers plan.

## Start

1. Read [references/workflow.md](references/workflow.md) completely.
2. Inspect repository instructions, Git status, tests, and active `sdd/changes/` state.
3. Run `wm --repo <repo> status --change <change-name>` for objective evidence. If the project is not initialized, run `wm --repo <repo> init` first. The compatibility wrapper under this skill delegates to the same CLI.
4. Confirm CodeGraph MCP and the repository index are available and current before analyzing an existing codebase.
5. Select the earliest incomplete legal stage. Announce the selected change and stage when handing work to a stage skill.
6. Preserve `<repo>/sdd/` as the only process-artifact root.

The CLI reports evidence, not approval. Never infer user approval merely because a file exists. On every start or resumed session, read `.wm/state.json` through `wm status --json` semantics before choosing work.

## Harness handoff contract

Before invoking an independent stage skill, provide:

- controller: `using-wm`;
- selected change name and direct-root path;
- selected stage;
- satisfied entry gates and unresolved risks;
- exact artifact or task scope;
- instruction to perform only that stage and return control to `using-wm`.

If a skill reports new scope or a failed gate, update the OpenSpec artifacts or stop for the required decision. Do not silently skip to another stage.

## Canonical lifecycle

| Stage | Independent skill | Required exit evidence |
|---|---|---|
| Clarify | `brainstorming` | Intent, goals, non-goals, constraints, and approved design direction |
| Impact | `analyze-codegraph-impact` | Current implementation path, blast radius, dependencies, related tests, and graph-opaque checks in `design.md` |
| Plan | OpenSpec proposal/spec/design/task skills | `proposal.md`, delta specs, `design.md`, and valid `tasks.md` |
| Apply | `openspec-apply-change` | Each task's minimum independently acceptable loop implemented and verified |
| Verify | `openspec-verify-change` | Requirements, code, tests, tasks, CodeGraph recheck, and fresh commands agree in `verification.md` |
| Close | `openspec-sync-specs`, then archive skill | Durable specs synchronized and verified change archived |
| Deliver | Harness-owned delivery | Final diff, risks, and only user-authorized integration actions |

Use `research-with-playwright` only for browser-visible research or acceptance evidence. Load HarmonyOS, Python, or Rust profiles only when the CodeGraph impact scope touches that technology.

## Technology profile selection

- Select `harmonyos-ai-coding`, `python-ai-coding`, and/or `rust-ai-coding` from repository evidence and the CodeGraph impact scope.
- Record activated profiles and repository-defined commands in `design.md` and each affected task.
- Profiles constrain a stage or task; they do not create another workflow or approval point.
- Do not pause between tasks after approved execution begins. Record evidence and continue to the next ready task.

## Design gate

For an existing codebase, do not finalize design or create detailed tasks until `design.md` contains a complete `## CodeGraph impact analysis` section with:

- repository and freshness evidence;
- concrete entry points and symbols;
- callers, callees, and dependency paths;
- direct and transitive blast radius;
- related tests and test gaps;
- graph-opaque targeted checks;
- expected changes and explicitly unaffected boundaries.

If CodeGraph is unavailable, stale, or pointed at another repository, stop this gate and report the exact setup action. Broad search is not a substitute.

## Minimum task gate

Every implementation task must form a **minimum independently acceptable loop**:

- one observable outcome;
- requirement or scenario reference;
- bounded files or components;
- `Consumes` and `Produces` interfaces, including `none` where applicable;
- explicit acceptance criteria;
- exact independently runnable verification command and expected result.

Split a task when a reviewer could reject one outcome while accepting another. Fold setup, configuration, migration, and documentation into the outcome that needs them unless they independently deliver testable behavior. A task that depends on later tasks for all verification is not ready.

## Apply discipline

- Work one ready task at a time unless the task graph proves independence and the environment permits parallel execution.
- Use RED-GREEN-REFACTOR for behavior changes.
- Debug from reproduced evidence and root cause, not speculative fixes.
- Mark a checkbox complete only after that task's own acceptance and verification pass.
- When implementation reveals missing scope, update proposal/spec/design/tasks before continuing.
- After an approved execution starts, continue through ready tasks without asking whether to proceed.

## Verification and closure

- Map every changed requirement and scenario to implementation and tests.
- Run focused tests, the relevant full suite, static checks, and build/package checks with fresh output.
- Re-run CodeGraph and compare actual dependencies with the predicted blast radius.
- Record browser and technology-profile evidence when applicable.
- Resolve blocking specification and quality findings before closure.
- Sync and archive only after verification and only within the authorization already provided.
- Never merge, push, publish, discard, or perform destructive Git operations without authorization.

## Handoff

Report the change name, current stage, completed artifacts and tasks, fresh verification evidence, requirement coverage, and residual risks.

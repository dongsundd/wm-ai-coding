# WM OpenSpec Workflow

## Ownership

`using-wm` is the only user-facing controller. OpenSpec artifacts are the development source of truth. Every other skill is an independently maintained stage or profile that runs only from a harness handoff and returns control afterward.

Use direct-root paths only:

```text
sdd/
  config.yaml
  specs/
  changes/<change-name>/
    proposal.md
    specs/**/spec.md
    design.md
    tasks.md
    verification.md
```

Do not create `openspec/`, `sdd/openspec/`, `docs/superpowers/`, `sdd/designs/`, or `sdd/plans/`.

## Legal stages

| Stage | Entry gates | Exit evidence |
|---|---|---|
| Clarify | User intent exists | Approved goals, boundaries, constraints, and design direction |
| Impact | Target repository identified | Complete `design.md#CodeGraph impact analysis` |
| Specify | Clarification and current-system evidence available | Proposal, scenarios, design decisions, and traceable requirements |
| Tasks | Approved design and CodeGraph gate complete | Valid minimum independently acceptable task loops in `tasks.md` |
| Apply | Task contract valid | Each selected task passes its own acceptance and verification |
| Verify | All tasks complete | Fresh requirement, test, build, review, and CodeGraph recheck evidence |
| Close | Verification has no blocking gaps | Specs synchronized and change archived within authorization |
| Deliver | Closure decision known | Final diff, evidence, risks, and authorized integration result |

Always resume from the earliest incomplete gate. A requested later operation does not permit skipping earlier gates.

## Clarification and design

Use `brainstorming` to clarify consequential requirements and compare credible approaches. Store the accepted result in the active change's `design.md`, not a parallel document.

Before detailed design exits, use `analyze-codegraph-impact`. CodeGraph is the primary source for implementation paths, symbols, callers/callees, dependencies, blast radius, and related tests. Use targeted file or text inspection only for graph-opaque configuration, templates, generated names, reflection, runtime registration, migrations, or documentation, and record why.

For browser-visible work, use `research-with-playwright` and separate observed behavior, inference, and desired behavior. Store only necessary screenshots, traces, and attachments under the active change.

## OpenSpec artifacts

- Proposal states why, goals, non-goals, scope, compatibility, and risk.
- Delta specs use stable requirement identifiers and observable scenarios.
- Design records decisions, alternatives, interfaces, failures, migration, CodeGraph evidence, and unresolved questions.
- `tasks.md` is the only implementation plan.
- Verification maps requirements to code, tests, reviews, builds, graph recheck, and residual risk.

OpenSpec stage skills never select one another. `using-wm` inspects state after every handoff and chooses the next legal stage.

## Task quality

Each task has exactly one observable outcome, requirement references, bounded scope, consumed and produced interfaces, acceptance criteria, and an independently runnable verification command with expected result.

Split outcomes that can be accepted or rejected separately. Do not create standalone setup, configuration, documentation, or cleanup tasks unless they independently deliver verifiable behavior. Do not accept a task whose only proof arrives after later tasks.

## Implementation

Use the relevant technology profile selected from CodeGraph scope. For behavior changes, use the independent TDD skill inside the assigned task. For unexpected failures, use systematic debugging without expanding task scope. Worktrees are optional infrastructure selected by the harness, not a parallel workflow.

Task completion requires its own acceptance evidence. When implementation reveals a missing requirement or affected component, stop that slice, update proposal/spec/design/tasks as needed, regain any required approval, and resume from the resulting gate.

## Verification and closure

Verification includes specification compliance and code quality in one OpenSpec-owned gate. It requires fresh focused and broad tests, applicable static/build checks, task-state consistency, and a CodeGraph comparison of predicted and observed impact.

Do not sync or archive merely because checkboxes are marked. Do not claim readiness when a required check was skipped. Sync durable specs before archival when deltas apply. Delivery actions remain subject to user authorization.


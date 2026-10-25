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
| Specify | Clarification available | Proposal, scenarios, design decisions, structural analysis, and traceable requirements |
| Tasks | Approved design complete | Valid minimum independently acceptable task loops in `tasks.md` |
| Apply | Task contract valid | Each selected task passes its own acceptance and verification |
| Verify | All tasks complete | Fresh requirement, test, build, and review evidence |
| Close | Verification has no blocking gaps | Durable specs synchronized and their snapshot recorded |
| Archive | Synchronized-spec snapshot is current | Verified change archived within authorization |
| Deliver | Closure decision known | Final diff, evidence, risks, and authorized integration result |

Always resume from the earliest incomplete gate. A requested later operation does not permit skipping earlier gates.

The executable command, handoff, verification-plan and recovery contracts are specified
in [runtime.md](runtime.md). Every transition checks earlier gates against current files;
saved stage labels alone do not authorize later work. Record frontend applicability
explicitly and attach an existing authorization reference to design approval.

## Clarification and design

Use `brainstorming` to clarify consequential requirements and compare credible approaches. Store the accepted result in the active change's `design.md`, not a parallel document.

After requirements are understood, use the CodeGraph MCP during design to understand implementation paths, symbols, callers/callees, dependencies, blast radius, and related tests. Record this evidence and its design implications in `design.md#Structural analysis`. Use targeted file or text inspection for graph-opaque configuration, templates, generated names, reflection, runtime registration, migrations, or documentation, and record why.

Structural analysis is a design exit gate. When CodeGraph is unavailable, stale, or pointed at another repository, record the exact condition and targeted fallback evidence in the same section. For greenfield or non-code work, record why it is not applicable. Do not proceed with undocumented broad search.

OpenSpec creates or updates the surrounding `design.md` structure first. When `frontend_surface_changed` is true, invoke `frontend-design` serially inside `specify` and complete `design.md#Frontend design` before approval and task decomposition. OpenSpec artifact writers preserve that owned section byte-for-byte on later edits; `frontend-design` modifies only that section and never replaces the document. This is a conditional substep, not another workflow state or entry. For browser-visible research, use `research-with-playwright` and separate observed behavior, inference, and desired behavior. Store only necessary screenshots, traces, and attachments under the active change.

## OpenSpec artifacts

- Proposal states why, goals, non-goals, scope, compatibility, and risk.
- Delta specs use stable requirement identifiers and observable scenarios.
- Design records decisions, alternatives, interfaces, failures, migration, available structural evidence, and unresolved questions.
- `tasks.md` is the only implementation plan.
- Verification maps requirements to code, tests, reviews, builds, graph recheck, and residual risk.

OpenSpec stage skills never select one another. `using-wm` inspects state after every handoff and chooses the next legal stage.

## Task quality

Each task has exactly one observable outcome, requirement references, bounded scope, consumed and produced interfaces, acceptance criteria, and an independently runnable verification command with expected result.

Use unique task numbers. Optional `- Depends on: task-<number>, task-<number>` edges
are validated for missing targets and cycles. Apply selects only ready tasks.

Split outcomes that can be accepted or rejected separately. Do not create standalone setup, configuration, documentation, or cleanup tasks unless they independently deliver verifiable behavior. Do not accept a task whose only proof arrives after later tasks.

## Implementation

Use the relevant technology profile selected from the affected code scope. For behavior changes, use the independent TDD skill inside the assigned task. For unexpected failures, use systematic debugging without expanding task scope. Worktrees are optional infrastructure selected by the harness, not a parallel workflow.

Task completion requires its own acceptance evidence. When implementation reveals a missing requirement or affected component, stop that slice, update proposal/spec/design/tasks as needed, regain any required approval, and resume from the resulting gate.

## Verification and closure

Verification includes specification compliance and code quality in one OpenSpec-owned gate. It requires fresh focused and broad tests, applicable static/build checks, and task-state consistency. When CodeGraph is available, comparing predicted and observed impact is recommended. A report passes the runtime gate only when it explicitly states readiness for archive and contains no `not verified` checks.

Do not sync or archive merely because checkboxes are marked. Do not claim readiness when a required check was skipped. Sync durable specs before archival when deltas apply, then run `wm --repo <repo> baseline specs --change <change-name>` to record the synchronized snapshot. Archive is blocked if that snapshot is absent or the durable specs change afterward. Delivery actions remain subject to user authorization.

Final verification also requires a coverage manifest and current successful `wm check`
records. Archive uses `wm archive` and its persisted recovery intent rather than a manual
move. The host retains responsibility for actual tool permissions and sandboxing.

## Protocol v2 closure

See runtime.md for parent/support handoffs, required Check IDs and task receipts, environment declarations, structured review and coverage, deterministic sync and portable archive manifests. Deliver is a host-owned action after archive, not a workflow state. Missing historical assets remain integrity failures.

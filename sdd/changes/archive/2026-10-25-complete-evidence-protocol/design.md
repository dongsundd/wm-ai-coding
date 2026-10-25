# Design

User approved the cross-validated plan and requested implementation plus item-by-item audit.
Authorization: conversation:user:confirm-plan-create-todo-and-implement.

## Structural analysis
CodeGraph status: D:/Workspaces/wm-ai-coding, current at inspection (0 changes).
Explore StateMachine.advance/handoff, StateStore.write, verification_findings: CLI callers and both runtime/hardening suites are affected.
Targeted configuration reads cover workflow.yaml, manifests, Git ignore policy and skill contracts (graph-opaque ownership rules).
Changes span workflow registry, task acceptance, integrity, run identity, host adapters, sync, structured review, diagnostics, tests and docs.
Existing missing archive is retained and reported; no synthetic recovery or deletion. Host loop/sandbox remain host-owned.

## Decisions
Stable task IDs; parent/child handoff stack; accept a task against its completion snapshot and recheck integrated source at final verification.
Schema-versioned new protocol; migration invalidates incomplete legacy evidence, never invents approval.
Host-specific hook outputs and bounded brief; shell is conservatively denied unless an explicit command is declared, no claim of sandbox coverage.
Structured delta transforms validate preserved bodies and preimages. Portable evidence includes logs, task/report files and file manifest.
Environment declarations use hashes, executable/runtime identity and artifact hashes. No arbitrary environment capture.
Archive lifecycle, integrity and delivery are separate. State/outbox writes recover events after partial failure.
Parallelism executes independent declared checks in distinct existing workspaces, with source guards and serial integration; host supplies agents and worktrees.

## Technology profiles
Python >=3.11, unittest; no new runtime dependency beyond existing PyYAML. Run focused tests, full suite, compilation and isolated wheel smoke checks.
Frontend surface changed: false. Playwright UI acceptance: not applicable (CLI/plugin); hook formats verified against official host documentation and protocol tests.

## Risks
Hooks depend on host support/trust; model-review independence is recorded but not authenticated. Old missing archive remains an explicit integrity finding.

---
name: development-planning
description: Use only when `development-workflow` selects creation of the next legal OpenSpec artifact for a change.
license: MIT
metadata:
  author: openspec
  version: "1.0"
---

## Controller contract

Run only from a `development-workflow` handoff naming the change, stage, task and exact scope.
A direct user request routes through `development-workflow`. Perform only the assigned operation,
then return its result to the controller; never invoke another stage skill.

Use `<repo>/sdd/config.yaml`, `<repo>/sdd/specs/` and
`<repo>/sdd/changes/<change>/` directly. Use filesystem operations and the `wm` CLI.
Do not run the official OpenSpec CLI or create an `openspec/` directory.
`tasks.md` is the sole implementation plan. Preserve existing authorization: do not
invent approval or demand a new request when execution is already authorized.
Host permissions and sandbox policy remain authoritative.

Before work read `wm --repo <repo> recovery --change <change>`. The controller records
`wm handoff --scope <repo-relative-paths>`; return with `wm finish-handoff <id>` and
`--result completed --output <existing-paths>`, or a failed/blocked/scope_changed result
with `--reason`. Output paths are repository-relative. The controller owns advancement. A matching completed stage/task handoff is required.
Support/profile calls use `wm handoff --skill <name> --parent <running-id>` and return to that parent; they never advance the stage.

When editing `design.md`, preserve an existing `## Frontend design` section
byte-for-byte. Only `frontend-design` writes that section.

## Tasks operation

Create or revise only the next artifact explicitly assigned by the controller.
When selected for the `tasks` stage, read the approved proposal, delta specs and design,
then write `tasks.md`. Never implement product code in this stage.

Read the approved `test-design.md` as an input. Preserve its requirement/scenario coverage, expected outcomes, environment and data constraints when assigning checks to tasks. Create or update the existing verification-plan.json with executable argv and matching task/Check IDs; do not create a second implementation plan. Planned tests must be implemented before their task's acceptance can pass.

Each task uses a unique `### Task <number>: <outcome>` heading and six non-empty fields:

- [ ] Requirement: exact requirement/scenario reference
- [ ] Outcome: one independently acceptable observable result
- [ ] Files: bounded files or components
- [ ] Interfaces: Consumes ...; Produces ... (or none)
- [ ] Acceptance: explicit expected behavior
- [ ] Verification: exact runnable command and expected result

Every task also declares `- Check: <id>`; the verification-plan check uses matching `task: task-N`.
Only runs from that task's root handoff can establish its acceptance.

Declare dependencies with `- Depends on: task-<number>, task-<number>` (or none).
The runtime validates the graph and selects ready tasks in document order.
Order dependent tasks after their prerequisites where practical. Split independently rejectable outcomes.
Do not create a task whose only validation depends on a later task. Record affected
technology profiles and checks. The controller records `wm baseline tasks` after the
approved planning inputs pass their gates, then advances to apply.

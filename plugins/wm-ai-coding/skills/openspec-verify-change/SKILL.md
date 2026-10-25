---
name: openspec-verify-change
description: Use only when `using-wm` selects verification of an implemented OpenSpec change.
license: MIT
metadata:
  author: openspec
  version: "1.0"
---

## Controller contract

Run only from a `using-wm` handoff naming the change, stage, task and exact scope.
A direct user request routes through `using-wm`. Perform only the assigned operation,
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

## Verify operation

Review specification compliance and code quality against current proposal/spec/design,
completed tasks, actual diff and tests. Compare predicted impact with actual dependencies
when CodeGraph is available. Do not infer success from checkboxes or report prose.

Create `verification-plan.json` as documented in
`../using-wm/references/runtime.md`. Declare exact argv checks for focused/full tests,
applicable static/build checks, and coverage for every changed requirement and scenario.
Run each using `wm --repo <repo> check <check-id> --change <change>` through the host's
normal permission boundary. A command is authorized by the task context, not by merely
appearing in JSON. Local run records preserve status, logs and input fingerprints.

Write `verification.md` mapping requirements and scenarios to code, tests, run IDs,
review findings and residual risks. Include applicable browser/profile evidence.
Resolve blocking findings. Say `Ready for archive` only after all required checks pass;
otherwise record incomplete checks explicitly and return blocked. The controller
rechecks cumulative gates, coverage and fresh run records before advancing.

Use `wm review --file <structured-input>` to record actual reviewer identity/mode and blocking findings. Browser evidence is conditional and must bind target, artifacts and run IDs. Then run `wm verification-summary` to produce structured coverage. Never claim an independent reviewer ran unless one actually did.

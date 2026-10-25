---
name: openspec-apply-change
description: Use only when `using-wm` selects the apply stage for an OpenSpec change with valid design and task gates.
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

## Apply operation

Read the approved artifacts and the current task in `wm recovery`. Apply only that
minimum independently acceptable loop. Load applicable Python/Rust/HarmonyOS profiles;
use TDD for behavior changes and systematic debugging for reproduced failures, under
controller handoffs. Do not silently expand scope or alter requirements.

Run the task's declared checks through `wm check` from its root handoff. The return records an acceptance receipt; final verification separately checks current integrated source.
Run the task's own acceptance command. Update checkboxes only after its checks pass.
Return changed files, tests and acceptance evidence. The controller calls `wm advance`
to select the next task and continues without another approval when already authorized.
A checkbox is task progress; final verification additionally requires executed check
records bound to the current workspace and declared coverage.

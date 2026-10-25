---
name: openspec-bulk-archive-change
description: Use only when `using-wm` selects an authorized bulk-archive stage for multiple verified OpenSpec changes.
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

## Bulk archive operation

Use only the explicit list of verified changes supplied by `using-wm`. Validate each
change's current gates and existing authorization separately. Conflicting deltas must
be resolved by the controller before synchronization. Do not infer an order from names.

For each eligible change invoke `wm archive --change <change>` serially. Stop on a
failure and report completed and pending changes; retries are idempotent. Do not invoke
sync or another stage skill, ignore gates, or move directories manually.

---
name: openspec-new-change
description: Use only when `using-wm` selects creation of a new OpenSpec change after clarification.
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

## Operation

After clarification, create only the assigned direct-root change scaffold. Choose no
stage independently. Do not fabricate approved artifacts or overwrite an existing
change. Return the created paths and unresolved questions to `using-wm`.

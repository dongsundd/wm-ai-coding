---
name: openspec-archive-change
description: Use only when `using-wm` selects the archive stage for a verified OpenSpec change.
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

## Archive operation

Run only for the verified archive stage and within existing user authorization. Read
`wm recovery` and resolve stale evidence before moving anything. Synchronization belongs
to the earlier close stage; return to the controller if it is incomplete.

Call `wm --repo <repo> archive --change <change>` instead of moving directories manually.
The runtime records an intent, validates gates, moves the change under
`sdd/changes/archive/YYYY-MM-DD-<change>`, and settles archived state. It refuses target
collisions. Retry the same command after an interruption to recover the recorded move.
This command settles the archive-stage handoff itself; do not call `finish-handoff`
after the original artifact paths have moved.

Return the archive path, evidence and residual risks. Never bypass incomplete tasks,
failed checks or unsynchronized specs by offering an archive-without-verification option.
The controller owns delivery and any separately authorized Git integration.

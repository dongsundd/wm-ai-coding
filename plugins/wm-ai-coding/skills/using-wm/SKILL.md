---
name: using-wm
description: Use for software development, planning, implementation, review, verification, recovery and delivery. Select the change and legal stage before invoking another WM skill.
---

# Using WM

This is the only WM development controller. The host owns the model loop, permissions and sandbox; WM owns process contracts and evidence. Preserve existing user authorization.

1. Read `wm --repo <repo> brief`; use `status`/`recovery --change <name>` for details. Initialize explicitly with `init --no-gitignore` when needed. Read [workflow](references/workflow.md) once and [runtime](references/runtime.md) for the selected operation. Migrate changed protocol/registry checksums; never reconstruct missing historical evidence.
2. Select the earliest incomplete legal stage. Announce change, stage and task. All process artifacts live directly under `sdd/`; `tasks.md` is the only implementation plan.
3. Before a stage, create `wm handoff --scope <paths>`. It records work but does not invoke a model. Support skills and profiles use `handoff --skill <name> --parent <running-id>` with a subset of parent scope. Read only references needed by that scope; return control here after each result.
4. Execute one independently acceptable task. Use applicable technology profiles, TDD for behavior changes and reproduced root-cause debugging. Every task declares `- Check: <id>`; run it with `wm check`. Mark progress only after acceptance passes, then `finish-handoff` and `advance`. Continue ready tasks under existing authorization.
5. Gates recheck actual files. Failures/scope changes block; settle interrupted handoffs before resume. Design/spec changes require reconciliation and any approval already required by their scope. Do not infer consent from files.

During specify, record current CodeGraph structural evidence (or exact unavailable/stale condition and targeted fallback). Record frontend applicability explicitly. If true, the stage writer creates design first, then `frontend-design` owns only `## Frontend design`; preserve that section on other edits. Approve the completed planning fingerprint before task baselining.

Final verification needs current executed checks, requirement/scenario run-ID coverage, structured review and `verification.json`. Frontend changes additionally need current browser evidence with target and declared artifacts. Record self-review honestly when no independent reviewer ran. Sync against the captured durable preimage, validate and baseline the transform, then archive portable evidence with a file manifest. Archived, integrity-valid and delivered are distinct claims.

Use `doctor`, `eval` and `verify-archive` for health/contract/integrity checks. Hooks are host-specific guardrails requiring supported events and trust; they are not complete write isolation. Parallel `batch` checks require distinct host-prepared workspaces; integrate serially and reverify the final target. Never merge, push or publish without existing authorization.

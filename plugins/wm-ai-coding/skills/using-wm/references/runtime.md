# WM runtime protocol v2

WM is a local development controller. It does not authenticate reviewers, run the model loop, sandbox subprocesses, enforce every write path or create tamper-proof attestations. Host permissions remain authoritative.

## Start, migration and recovery

All CLI output is JSON. `wm --repo <repo> init --no-gitignore` initializes state without modifying Git policy. `init` without that switch additionally maintains managed ignore rules and may remove active process artifacts from the Git index, only within repository authorization. Archived tasks, reports and portable evidence are retained.

Use `reconcile`, `select <change>`, `status --json`, `brief --change <name>`, `recovery --change <name>` and `doctor`. Brief is bounded to 2KB. Doctor is read-only; missing assets are never generated as a repair. `validate`, `verify-archive`, `doctor`, `batch`, and `eval` return nonzero for an invalid result.

`workflow.yaml` plus `skills/registry.yaml` determine the protocol checksum. `migrate` keeps archived history, invalidates active old task receipts/handoffs and returns implementation-stage work to task baselining. Planning authorization must still match its current fingerprint. No upgrade invents consent or restores missing files.

## Planning and tasks

`wm condition frontend_surface_changed true|false --change <name>` records applicability. True requires a non-empty Frontend design section. Structural analysis is mandatory before tasks (record exact CodeGraph condition and fallback when unavailable). `approve design --reference <existing-authorization>` records an operator/host assertion bound to proposal, delta specs, design and frontend condition. `baseline tasks` binds task definitions to those inputs.

Each task has a unique `### Task N: outcome` heading, the six checkbox fields Requirement/Outcome/Files/Interfaces/Acceptance/Verification, optional `- Depends on: task-N`, and one or more `- Check: <check-id>` lines. Interfaces states Consumes/Produces, including none where applicable. Dependencies cannot be missing, cyclic or completed out of order. Each Check must resolve to an executable check with matching `task`.

Checkboxes are normalized out of the definition hash. Completing a task requires a current successful run from the same root handoff, then a completed handoff and `advance`. A saved receipt records its completion snapshot. Later source edits do not erase that historical fact; final integration is separately reverified against current full source. Changes to planning/task definitions invalidate those receipts.

## Handoffs

```
wm handoff --change <name> --scope src tests sdd/changes/<name>
wm handoff --change <name> --skill python-ai-coding --parent <id> --scope src
wm finish-handoff <id> --change <name> --result completed --output <existing-files>
wm advance --change <name>
```

The registry distinguishes stage, support, profile and operation roles. Support/profile calls require a running parent and cannot expand its scope. Completion returns to the parent. Only the controller advances; a stale stage/task handoff cannot advance the next task. Packets contain task/workspace/trace identities and a before-file inventory. Completed returns compare actual changed/deleted/created files with scope, including process documents; `.wm` and standard generated/cache directories are excluded. This is a guardrail, not a filesystem security boundary.

Failed/blocked/scope_changed returns require a reason and block the change. Resume after resolving the cause. A running legacy packet lacking inventory must be settled as failed and retried. Archive settles its handoff itself because paths move.

New/update/bulk archive skills are registered operations at legal stages; they cannot bypass gates, synthesize approvals or implement another stage. Bulk archive is controller iteration over separately verified changes.

## Executed checks and environment

`verification-plan.json` is a coverage declaration, not another implementation plan:

```json
{"checks":[{"id":"task-1","task":"task-1","kind":"test","argv":["python","-m","unittest"],"requirements":["auth::R1"],"scenarios":["auth::R1::success"],"environment":["APP_MODE"],"artifacts":["requirements.lock"]}]}
```

Run `wm check <id> --change <name> --timeout 300`. Argv executes with shell=False, bounded timeout, repository cwd, host privileges and file-backed stdout/stderr. Timeout stops the direct process, not all descendants; checks must not leave background workers. No manifest grants authorization by itself.

Runs under `.wm/runs/<id>` record check/task/stage/handoff/workspace/trace identities, inputs/outputs, elapsed time, output sizes and log hashes. Environment identity includes runtime/Python identity, resolved executable bytes, hashes of explicitly declared environment values and declared artifact bytes. It does not capture all external services, symlink targets, installed packages or process environment. Declare relevant lock files/generated outputs and target versions explicitly; never use the fingerprint as a hermetic-build claim.

Source hashing includes untracked files but omits `.git`, `.wm`, `sdd`, CodeGraph/browser metadata, worktrees and standard dependency/build/cache folders. It conservatively rehashes current bytes, not just mtimes. Final checks must all pass, be the latest attempts and match current plan/source/environment with intact logs. A source-mutating check is not current acceptance.

## Structured verification and review

Write a review input JSON with `reviewer`, `mode` (self or independent), and findings containing severity (blocking/warning/info), message and resolved boolean. `wm review --file <input> --change <name>` binds the asserted review to planning and source. Independent means host-asserted identity, not authenticated independence. Unresolved blocking findings or stale review fail verification.

For frontend acceptance declare a browser check with `kind: browser`, exact `target`, scenario coverage and non-empty `artifacts`; run it and pass its run IDs as `browser_runs` in the review input. Artifacts must exist and are fingerprinted. CLI-only changes record browser acceptance as not applicable rather than fabricating browser runs.

After checks and review, `wm verification-summary --change <name>` writes `verification.json` only if evidence is valid. Every requirement/scenario maps to corresponding latest run IDs. `verification.md` explains semantic review, residual risks and Ready for archive; prose alone is insufficient.

## Specification sync and archive

Entering close captures the durable spec preimage. `wm sync --change <name>` applies explicit ADDED/MODIFIED/REMOVED/RENAMED requirement-block transforms, preserving unaffected content; missing/conflicting targets fail. RENAMED uses consecutive `- FROM: ` and `- TO: ` backtick requirement headings. `baseline specs` independently compares the entire expected tree, not just names. Interrupted sync accepts only old-or-expected per-file values; unrelated drift blocks. Explicit approved REMOVED deltas can retire a last capability.

`wm archive` validates all gates, exports final and task-acceptance runs/logs plus receipts, writes archive-manifest.json, persists move intent and renames to `sdd/changes/archive/YYYY-MM-DD-name`. Retry interrupted moves. Identity covers JSON, Markdown, logs and attachments. Manifest hashes detect changes; they are not authenticated attestations.

`wm verify-archive <directory>` works without `.wm` state. Status and recovery report lifecycle separately from current integrity. Missing/changed/unknown assets never return delivered. Archived is not proof of integration or deployment. Old missing history remains an explicit finding until trustworthy assets are restored externally.

## Host adapters, batching and diagnostics

Plugin hooks are generated separately for Codex and Claude; trust and event support are host concerns. DSH uses the exported normalized bridge contract and requires host-side event integration. `wm hook <host> <event>` accepts JSON on stdin. PreToolUse checks explicit write/patch targets, denies direct runtime-state edits, and permits only literal controller invocations or exact declared shell checks; complex shell operations require host review. Already-running shell input, specialized/hosted tools, background processes and external writes may bypass hooks. Stop permits pause; explicit completion claims require valid closure.

`wm batch --file <jobs.json> --max-parallel 2` executes checks in distinct existing workspaces supplied by the host. Jobs have task/workspace/check; the controller resolves argv from that task's declared check and verifies readiness against the task graph. The low-level runner also rejects unresolved dependencies. Duplicate/nested workspaces are rejected; source mutation fails results. No agents are launched and no code is merged. Batch results never advance tasks: integrate serially and run final checks in the target workspace.

`wm eval` reports named deterministic protocol cases, not live model routing accuracy. Run the unittest suites for broader regressions. State revisions and handoff/run trace IDs correlate local events; token/cost and complete model/tool traces remain host-owned. A durable event outbox makes a committed state successful even if event append fails; `flush_events` replays pending entries idempotently.

Build releases with `python scripts/build_release.py`; manifests share version 0.8.0 and a content manifest. Rebuild after source changes. Reinstall/reload the released plugin to replace stale caches; source edits never silently rewrite installed plugins. Python >=3.11, existing PyYAML and globally available MCP binaries are required. Cross-platform launcher resolves platform executable names without implicit installs.

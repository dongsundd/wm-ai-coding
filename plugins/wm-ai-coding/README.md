# WM AI Coding Harness

WM is a development workflow and evidence controller for a host coding agent.
It routes reusable skills through an OpenSpec-style lifecycle, records scoped
handoffs, executes acceptance checks, and preserves portable archive evidence.
The host supplies the model loop, tool permissions, sandbox and agent sessions.

## Install and start

Use Python 3.11 or newer and install this directory with `pip install .`.
Install the global CodeGraph and Playwright MCP executables separately; run
`python scripts/dependency_preflight.py --json` to inspect availability. MCP
configuration uses a platform-neutral executable resolver and never installs
dependencies implicitly.

Ask the host to use `using-wm`. Start a repository with
`wm --repo <repo> init --no-gitignore`, then inspect `status`, `brief` and `doctor`.
Only opt into managed Git-index maintenance when repository policy permits it.
Read [the runtime protocol](skills/using-wm/references/runtime.md) for the full
planning, task, review, specification-sync and archive contracts.

## Releases and hosts

`python scripts/build_release.py` generates version-aligned portable, Codex and
Claude manifests and seals bundle content. Rebuild after any package change.
`python scripts/smoke_release.py --mcp` checks the bundle and locally initializes
both MCP servers without running browser actions.

Codex and Claude use separate explicit hook files; there is deliberately no
shared default `hooks/hooks.json`. Reload or reinstall the new release to replace
old cached code. Review/trust hooks in the host before relying on them. The DSH
normalized hook bridge is available to an integrating host plugin; this package
does not automatically install a Cordis plugin. Hook/schema tests do not establish
live host event activation. No marketplace publication is performed by the build.

## Verification and limits

Run `python -m unittest discover -s tests` from this directory and `wm eval` for
named deterministic protocol cases. These checks do not measure model routing
accuracy, token cost or independent-review quality. Review mode explicitly records
self or host-asserted independent review.

Task receipts preserve completion-time evidence; final verification checks current
integrated source. Archive manifests and bundled logs remain usable without local
`.wm` state. `wm verify-archive <directory>` checks integrity without claiming
authenticated attestation. Missing historical artifacts are reported, not recreated.

Batch checks use disjoint host-prepared workspaces. They do not launch coding
agents, merge worktrees or replace final acceptance in the integration checkout.
Process timeouts stop the direct subprocess; do not leave background descendants.

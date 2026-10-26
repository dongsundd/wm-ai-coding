# WM AI Coding Harness

WM is a development workflow and evidence controller for a host coding agent.
It routes reusable skills through an OpenSpec-style lifecycle, records scoped
handoffs, executes acceptance checks, and preserves portable archive evidence.
The host supplies the model loop, tool permissions, sandbox and agent sessions.

## Install and start

Use Python 3.11 or newer. Run `python scripts/wm.py --help` directly, or
install the optional `wm` command with `pip install ./scripts`.
Install the global CodeGraph and Playwright MCP executables separately; run
`python scripts/wm.py preflight --json` to inspect availability. MCP
configuration uses a platform-neutral executable resolver and never installs
dependencies implicitly.

Ask the host to use `development-workflow`. Start a repository with
`wm --repo <repo> init --no-gitignore`, then inspect `status`, `brief` and `doctor`.
Only opt into managed Git-index maintenance when repository policy permits it.
Read [the runtime protocol](skills/development-workflow/references/runtime.md) for the full
planning, task, review, specification-sync and archive contracts.

`scripts/wm.py` is the shared source entrypoint for workflow, hook, MCP,
dependency and release commands. Runtime modules live under
`scripts/wm_ai_coding/{commands,lifecycle,evidence,integrations,infrastructure}`.
Development tests live under `scripts/tests/{unit,integration,acceptance,support}`;
shared paths and fixtures belong to `support`, and tests are excluded from wheels.
Each tool command owns its arguments, process input/output and exit codes;
`commands/registry.py` registers the real argument definitions and handlers for
both help and execution. Integration services accept explicit values and return
data or results, without CLI entrypoints or process stream handling.
Workflow commands take `--repo` before the subcommand; tool arguments follow
their command, for example `wm preflight --project <repo> --json`.
`wm --repo <repo> hook <host> <event>` uses the explicit repository; without
`--repo`, hook context is discovered from the payload's `cwd`.

Version 0.9.1 organizes [24 skills by development activity](skills/README.md):
requirements research and analysis, specification, technical/frontend/test design,
planning, implementation, tests, review, local commits, specification sync and archive.
The seven runtime states remain stable. Required design and verification supports
have ordered, current handoff evidence. Old WM handoff names normalize through
registry aliases; host skill discovery and filesystem paths use the new names.
Run `wm migrate` after upgrading and rebaseline active tasks; historical archives
are not rewritten. Test design is required before implementation.

## Releases and hosts

Host adapters share the startup contract and fresh WM brief. Claude uses native
command hooks; OpenCode v2 uses the directory plugin at
`.opencode/plugins/wm-ai-coding` (`id`/`setup`, skills, MCP and session/tool hooks).
OpenCode v1 is not supported. Add the installed **directory** to `plugins` in a
project `opencode.json`, for example `{"plugins":["D:/plugins/wm-ai-coding/.opencode/plugins/wm-ai-coding"]}`.
Keep the whole bundle at that installation path; do not copy only the JS file.
Set the OpenCode plugin's `python` option or `WM_PYTHON` if Python is not on PATH.
Python 3.11+, PyYAML, CodeGraph and Playwright MCP executables must be available
in the host execution environment. Run `wm preflight` to diagnose dependencies.

Claude can load a local installed bundle with `claude --plugin-dir <bundle>`;
review/trust plugin hooks through the host's supported flow. Codex uses its
marketplace/plugin mechanism. No installer here edits personal/global config.
`metadata.json` owns shared release metadata. `.mcp.json` is Claude-specific;
`.codex.mcp.json` uses a plugin-relative working directory and script path;
portable `mcp.json` uses `${PLUGIN_ROOT}` expansion. OpenCode
registers MCP servers through native transforms with resolved installed paths.

Build the shared source, then produce a native installation bundle with
`python scripts/wm.py release package --host codex --output <new-directory>`
(also supports `claude` and `opencode`). Codex 0.164 selects the compatibility
manifest only when the native bundle omits root `plugin.json`; otherwise that
portable manifest shadows hook discovery. Install the emitted Codex directory,
not the shared source checkout. Each native bundle is sealed independently and
records its shared-source digest in `distribution.json`.

Allowed Claude operations defer to the normal host permission flow; WM denials
remain explicit. Claude restores context through SessionStart (including compact),
not PreCompact output. Stop does not infer completion intent from conversational
text; explicit WM gates remain authoritative and pausing is legal. Hooks are
guardrails and do not isolate every subprocess, external write or MCP side effect.

`python scripts/wm.py release build` generates version-aligned portable, Codex and
Claude manifests and seals bundle content. Rebuild after any package change.
`python scripts/wm.py release verify --mcp` checks the bundle and locally initializes
both MCP servers without running browser actions.

Codex and Claude use separate explicit hook files; there is deliberately no
shared default `hooks/hooks.json`. Reload or reinstall the new release to replace
old cached code. Review/trust hooks in the host before relying on them. The DSH
normalized hook bridge is available to an integrating host plugin; this package
does not automatically install a Cordis plugin. Hook/schema tests do not establish
live host event activation. No marketplace publication is performed by the build.

## Verification and limits

Run `python -m unittest discover -s scripts/tests -v` from this directory and `wm eval` for
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

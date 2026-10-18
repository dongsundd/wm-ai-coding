---
name: analyze-codegraph-impact
description: Use only when `using-wm` selects CodeGraph impact analysis or post-implementation impact recheck for an OpenSpec change.
---

## Harness entry contract

Execute only from a `using-wm` handoff that names the change and analysis stage. A direct user request must enter `using-wm`. Record the assigned evidence, then return control to `using-wm`.

# Analyze CodeGraph Impact

Use CodeGraph as the primary source of structural code understanding. Do not begin broad repository grep, filename guessing, or sequential file reading before graph analysis.

## Gate

1. Confirm the CodeGraph MCP server and repository index are available and current.
2. If unavailable, stale, or pointed at another repository, stop the design gate and report the exact condition plus the setup action needed. Do not silently replace CodeGraph with grep.
3. Read [references/analysis-contract.md](references/analysis-contract.md) completely.
4. Select the current SDD change under `sdd/changes/<change-name>/`.

## Analyze

Use the available CodeGraph tool schemas rather than guessing arguments. Prefer this sequence:

1. Call `get_ai_context` or `get_curated_context` with the requested behavior to orient the analysis.
2. Use `find_entry_points` and `symbol_search` to identify candidate entry points and domain symbols.
3. Use `get_detailed_symbol`, `get_callers`, `get_callees`, and `get_call_graph` to establish runtime flow.
4. Use `get_dependency_graph`, `find_by_imports`, and `traverse_graph` to establish module and cross-layer dependencies.
5. Call `analyze_impact` for every symbol or module expected to change. Include rename/delete analysis when applicable.
6. Use `find_related_tests` for each affected production symbol.
7. Use `get_edit_context` immediately before planning edits to collect callers, tests, history, and relevant context.

Use direct file reads only to verify graph findings or inspect exact code returned by the graph. Use targeted text search only for data the graph does not model, such as configuration keys, generated names, templates, migrations, documentation, or dynamic registration. Label every fallback and explain why graph analysis could not answer it.

## Record

Write or refresh `## CodeGraph impact analysis` in `sdd/changes/<change-name>/design.md` using the reference template. Include:

- index identity or freshness evidence;
- entry points and primary symbols;
- callers, callees, and dependency paths;
- predicted direct and transitive blast radius;
- related tests and test gaps;
- dynamic or graph-opaque areas requiring targeted verification;
- files/modules likely to change and explicitly unaffected boundaries;
- the CodeGraph tools used and material results.

Do not advance to detailed tasks or implementation until this section exists and the affected scope is reflected in `design.md`.

## Recheck

After implementation, use CodeGraph again to compare the implemented diff with the predicted blast radius. Record missed dependencies, unexpected graph changes, and related-test coverage in `verification.md`. A new affected component requires updating `design.md` and `tasks.md` before declaring completion.

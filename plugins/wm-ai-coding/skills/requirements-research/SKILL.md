---
name: requirements-research
description: Collect user, domain, current-system and reference-product facts when
  development-workflow selects a bounded requirements investigation.
---

# Requirements Research

Execute only as a support handoff under the active clarify or specify primary. Return evidence to development-workflow; do not select another skill or advance the stage.

Consumes a research question, decisions it will inform, sources and permitted scope. Produces `design.md#Requirements research` with source/date, finding, observed fact or inference, confidence, limitations and requirement implications.

1. Reuse user-provided material, durable specs, existing code/docs and connected sources before asking the user to repeat facts.
2. Research only uncertainties that affect the desired outcome. Record current behavior separately from desired behavior; do not turn a reference product into an implicit requirement.
3. For external facts that may change, verify authoritative current sources and record direct source attribution. For browser interaction evidence, return a bounded browser-research request to the controller.
4. Compare alternatives when evidence warrants it. Include contradictory findings and unresolved gaps rather than selecting convenient examples.
5. Stop when the bounded question is answered or the evidence limitation is clear. Report which decisions still belong to the user.

If the existing request and repository already supply sufficient facts, the controller may record research as not applicable with a reason. This skill is not mandatory product discovery for every small change.

No product implementation, task decomposition, external mutation or independent approval is implied. Exit with traceable findings that requirements-analysis can use.

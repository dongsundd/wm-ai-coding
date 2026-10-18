---
name: web-ai-coding
description: Use only when `using-wm` selects this profile for requirements involving a visible Web or app page, screen, frontend component, layout, interaction, responsive behavior, accessibility, or an existing design system.
---

## Harness entry contract

Execute only from a `using-wm` handoff whose CodeGraph scope activates Web work. A direct user request must enter `using-wm`. Apply this profile only to the assigned stage or task, then return control to `using-wm`.

# Web and app page design

Treat Web and app page design plus frontend engineering as one deliverable: establish an intentional direction, implement it through the repository's existing system, and prove it on the applicable rendered surface.

## Establish current-system evidence

- Use CodeGraph to locate routes, page shells, components, styling, tokens, state, assets, and related tests before design decisions.
- Inspect an existing Web UI with `research-with-playwright`; inspect app UI with the repository's device, emulator, or platform preview tools.
- Treat user direction, supplied references, existing product behavior, and the repository design system as authoritative.
- Do not replace an established framework, component library, or styling strategy without an approved architectural reason.

Record the activated framework, design system, browser targets, repository commands, and Playwright applicability under `## Technology profiles` in `design.md`.

## Define the design contract

Before implementation, make the accepted direction concrete:

- identify the primary task, information hierarchy, and first-viewport priority;
- define typography, color roles, spacing rhythm, density, containers, and responsive breakpoints from existing tokens where available;
- inventory visible copy, controls, assets, components, variants, and interaction states;
- include loading, empty, error, disabled, focus, validation, permission, and reduced-motion behavior where relevant;
- prefer a few strong visual decisions over repetitive cards, decorative badges, fake metrics, or generic dashboard patterns.

For an established product, extend its visual language. For a greenfield surface without a design system, define the smallest coherent token set needed by the requested interface; do not build a general-purpose system speculatively.

## Implement faithfully

- Use semantic HTML and the repository's component and styling conventions.
- Keep components focused; share repeated behavior and styling through existing primitives or explicit variants.
- Preserve exact approved copy, hierarchy, order, density, and interaction behavior.
- Make layouts work at the repository's supported viewport sizes without horizontal overflow or hidden critical actions.
- Provide visible keyboard focus, logical tab order, labels, accessible names, sufficient contrast, and non-color status cues.
- Use animation only when it communicates state or spatial continuity; honor reduced-motion preferences.
- Do not introduce placeholder content, gratuitous dependencies, remote assets, or a new frontend stack unless the approved design requires them.

## Verify the rendered result

- Run focused component tests and the repository's full relevant checks.
- For Web, use `research-with-playwright` for rendered desktop and mobile evidence, critical journeys, keyboard behavior, and browser-visible states.
- For apps, use a device, emulator, or platform preview plus the platform Profile's build and test requirements; Playwright is not a substitute for native rendering evidence.
- Compare implementation against the accepted design and existing product, not merely against DOM assertions.
- Check console errors, broken assets, overflow, layout shifts, empty/error states, and accessible interaction.
- Record browser evidence and any intentional visual deviations in `verification.md`.

## continuous execution

This profile is an overlay inside `using-wm`, not an independent workflow or approval point. Continue through approved tasks without pausing between them. Pause only for a new visual direction, framework or dependency change, destructive migration, or scope that changes the approved observable behavior.

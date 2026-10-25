# WM AI Coding skills

`development-workflow` is the only development controller. It selects the change and earliest legal stage, creates scoped handoffs and verifies current evidence. Other skills return to it without selecting another stage.

## Development lifecycle

| Development activity | Skill | Runtime placement |
|---|---|---|
| 需求调研 / Requirements research | requirements-research | Conditional clarify/specify support |
| 需求分析 / Requirements analysis | requirements-analysis | clarify primary |
| 需求规格 / Requirements specification | requirements-specification | specify primary |
| 技术设计 / Technical design | technical-design | First required specify support |
| 界面设计 / Frontend design | frontend-design | Conditional support after technical design |
| 测试设计 / Test design | test-design | Final required specify support, before design approval |
| 开发规划 / Development planning | development-planning | tasks primary, sole tasks.md |
| 功能开发 / Feature development | feature-development | apply primary, one ready task at a time |
| 测试执行 / Test execution | test-execution | apply support; first required verify support |
| 代码评审 / Code review | code-review | Required verify support after tests |
| 综合验证 / Change verification | change-verification | verify primary |
| 代码提交 / Code commit | code-commit | Authorized local operation in apply/verify/close/archive |
| 规格同步 / Specification sync | specification-sync | close primary |
| 变更归档 / Change archive | change-archive | archive primary; serial batch mode |

The seven main states remain clarify → specify → tasks → apply → verify → close → archive. Research is conditional, development and tests iterate, and commits may occur during development. Delivery is a host action, not an additional state.

## Management and supporting capabilities

| Category | Skills |
|---|---|
| Controller | development-workflow |
| Change operations | change-initialization, change-management |
| Browser observation | browser-research |
| Development methods | test-driven-development, systematic-debugging |
| Workspace isolation | git-worktree-management |
| Technology profiles | python-development, rust-development, harmonyos-development |

There are 24 canonical skill directories. Names use lowercase ASCII letters, digits and single hyphens, are shorter than 64 characters, and match their SKILL.md name. Chinese labels describe stages; they are not skill identifiers.

## Upgrade and compatibility

| Previous name | Canonical destination |
|---|---|
| using-wm | development-workflow |
| brainstorming | requirements-analysis |
| openspec-new-change | change-initialization |
| openspec-propose | requirements-specification; technical design now runs as a required support |
| openspec-continue-change | development-planning |
| openspec-update-change | change-management |
| openspec-apply-change | feature-development |
| openspec-verify-change | change-verification |
| openspec-sync-specs | specification-sync |
| openspec-archive-change | change-archive |
| openspec-bulk-archive-change | change-archive batch mode, with separate handoffs per change |
| research-with-playwright | browser-research during clarify/specify; test-execution during apply/verify |
| using-git-worktrees | git-worktree-management |
| python-ai-coding | python-development |
| rust-ai-coding | rust-development |
| harmonyos-ai-coding | harmonyos-development |

frontend-design, test-driven-development and systematic-debugging retain their names. Requirements research, technical design, test design, test execution, code review and code commit have dedicated responsibilities; see their SKILL.md files.

Aliases normalize WM CLI handoff/role requests, not host slash-command discovery or removed filesystem paths. Use canonical names in new prompts and paths. Reinstall/reload version 0.9.1 to replace old plugin caches. Run `wm migrate` explicitly when the workflow checksum changes. Active execution returns to task baselining; if test-design.md is missing, rewind to specify, complete planning and reconcile/approve it under the existing authorization. Archived bytes and diagnostic history are not rewritten. Missing history remains an integrity failure.

See [runtime protocol](development-workflow/references/runtime.md) for commands, current-evidence gates, ordered support returns, review, recovery and archive. OpenSpec-style artifacts remain the source of truth under sdd; the official OpenSpec CLI and an openspec/ root are not used.

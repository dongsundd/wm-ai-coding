# WM AI Coding skills

`using-wm` is the plugin's only user-facing development workflow entry.

The other skill directories remain independent modules for OpenSpec lifecycle stages, CodeGraph analysis, brainstorming, browser research, technology profiles, TDD, debugging, and optional workspace isolation. They execute only from a `using-wm` handoff and return control to the harness when their assigned stage is complete.

Do not invoke an `openspec-*` or supporting skill as a parallel workflow. Direct requests for propose, update, apply, verify, sync, archive, or bulk archive enter `using-wm`, which checks the active change and earliest incomplete gate before routing the operation.


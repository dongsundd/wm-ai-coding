<WM_BOOTSTRAP>
WM is the development workflow controller. The host owns tools, permissions and the model loop.

For a software development request, load development-workflow before writing product code.
For read-only analysis, answer the question without initializing state or inventing implementation tasks.
Use the host's native skill loader; if unavailable, read skills/development-workflow/SKILL.md
from the installed plugin root. Follow its references relative to that skill directory.

Run `wm --repo <repo> brief`; use `recovery --change <name>` for current gates.
If wm is not on PATH, use `python <installed-plugin-root>/scripts/wm.py`.
Initialize only when needed with `wm --repo <repo> init --no-gitignore`.
Keep seven states: clarify, specify, tasks, apply, verify, close, archive.
Create a scoped handoff before changes. Required supports return to their parent.
Run declared checks through WM and keep real evidence; never manufacture approval or completion.
An explicit finish-handoff/advance result establishes eligibility, not a natural-language claim.
Pausing or reporting unfinished work is allowed. Do not start subagents unless authorized.
Workers follow their assigned parent task and scope instead of restarting the controller workflow.
</WM_BOOTSTRAP>

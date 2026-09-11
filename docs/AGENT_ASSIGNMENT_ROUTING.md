# Real Agent development assignment: T-002

Use the installed Pi Development Harness tools to implement action-based model routing in this project. The user authorized this work and publication later; this task only changes and validates source.

Plan the current task with modules `backend`, `frontend`, `qa`; scope `yang/chat.py`, `web/src/04_agent.js`, `tests/test_chat.py`; kind bugfix; impact behavior. Acceptance criteria: two configured models can route ask and name to different IDs; invalid configured model IDs produce a clear error; existing default behavior remains compatible; frontend passes an action; actual project-tests and web-syntax runners pass.

Read relevant files first. Use a `worker` subagent for the backend routing and its tests, with scope limited to yang/chat.py and tests/test_chat.py. Have the parent implement the frontend action forwarding within web/src/04_agent.js. The existing ask/angle/collide/rewrite route keys must remain supported. Do not change other source files. There is an older local SQLite database outside the repository; do not read or copy it, and never print credentials.

Inspect and accept the child's result, synchronize knowledge for affected modules with concrete evidence, run both configured validation runners, and finish through development_task with one acceptance explanation per planned criterion. Do not substitute a plain final response for task completion. Never claim tests ran without invoking development_check. If a tool fails, report and repair the cause rather than bypassing the harness.

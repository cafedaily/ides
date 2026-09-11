# T-001: Real SSE streaming and cancellation

Use the installed harness for this project. The user authorized the entire development plan, but this task does not deploy anything.

Plan modules backend, frontend, qa; scope yang/chat.py, yang/server.py, yang/auth.py, web/src/03_api.js, web/src/04_agent.js, web/src/06_idea.js, tests/test_chat.py, tests/test_streaming.py, tests/test_security.py. Kind feature, impact behavior.

Acceptance:
1. POST /api/chat with stream=true forwards stream=true to the selected OpenAI-compatible upstream and relays real SSE deltas as they arrive. Keep the existing non-stream response compatible. Use event data objects {type:"delta",text:"..."}, {type:"done"}, {type:"error",error:"..."}. Send Content-Type text/event-stream, no-store, X-Accel-Buffering:no, and flush every event.
2. Private route authentication and same-origin checks run before streaming. Invalid input is rejected clearly. Do not expose upstream keys or raw internal error details in either stream or non-stream errors.
3. Frontend fetch stream parsing handles split UTF-8 chunks/frames, accumulates text, invokes existing onText callbacks incrementally, and passes AbortSignal. Preserve action-based model routing and JSON-mode outputs. Existing ask/angle/collide UI should visibly update while generated text arrives.
4. Cancelling generation aborts fetch and does not save a partial generated question. Downstream disconnect closes the upstream response; no fake streaming by splitting a fully buffered answer.
5. Add ephemeral-port HTTP tests proving the first delta is received BEFORE a controlled upstream completion barrier is released. Cover upstream errors and malformed frames, and preserve the current routing tests and web syntax checks.
6. Correct the authentication review findings within scope: production cannot disable Secure cookies using YANG_AUTH_SECURE_COOKIE=0; reject unsupported Transfer-Encoding and close connections after invalid Content-Length/body framing errors. Add focused regressions.
7. Run project-tests and web-syntax using development_check, synchronize backend/frontend/qa knowledge and complete the task with exact acceptance evidence.

Use a worker subagent for a concrete bounded subset (for example the upstream streaming generator and HTTP tests). Parent must inspect and accept results and integrate frontend/server changes. Do not modify store.py or implement synchronization, graph algorithms or the login UI in this task. Do not read credentials/databases outside the repository. Never publish, deploy or start a persistent site service in this task.

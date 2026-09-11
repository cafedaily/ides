# T-003: Public deployment authentication and secret handling

The user explicitly authorized completing this project and deploying it at ideas.cafedaily.top. Implement and validate the backend prerequisites using the installed 0.2.1 harness. Do not deploy in this task.

Plan modules backend and qa; scope yang/auth.py, yang/server.py, yang/api.py, yang/store.py, yang/cli.py, tests/test_security.py. Kind feature, impact behavior. Acceptance criteria:

1. In production mode an absent/weak YANG_AUTH_TOKEN prevents unsafe startup. Normal loopback development and existing tests without production mode remain compatible.
2. Private API requests without valid bearer or signed HttpOnly session cookie return 401. GET /api/health remains public but exposes no private counts/configuration to anonymous users. Provide GET /api/session, POST /api/login and POST /api/logout for the later frontend.
3. Login validates a token provided as JSON {token}, supports no credentials in query strings, has bounded failed-attempt throttling, and issues an expiring HttpOnly SameSite=Strict cookie. YANG_PUBLIC_ORIGIN governs same-origin mutation checks. Production cookies are Secure. Cross-origin cookie mutations must fail, while explicit bearer clients can use the API.
4. GET /api/state never returns model keys. State/config updates preserve existing model keys by ID when the key is omitted or left blank; an explicit clear_key=true clears it. keyConfigured metadata indicates presence. Import/export behavior remains compatible and plain exports never leak keys.
5. Validate Content-Length, reject negative/malformed lengths, cap request bodies, set finite socket timeout, and keep internal error details out of client responses. Static file access must use a contained resolved path rather than an unsafe string-prefix check.
6. CLI's default database location should be outside the source tree, while explicit --db/YANG_DB keep working. Bind non-loopback without an auth token must be refused unless an explicit unsafe development flag is set. Keep the backend stdlib-only.
7. Add real HTTP integration tests on ephemeral ports, covering login, unauthorized reads/writes, cookie/bearer flows, origin rejection, redacted/preserved/cleared model keys, malformed body lengths, and existing local behavior. Run project-tests and web-syntax through development_check and finish only when both pass.

Use a worker subagent for a concrete subset, inspect and accept its output, then review integration as parent. Do not read user databases or credentials outside this repository. Test credentials must be clearly synthetic. Do not modify chat.py or frontend files; streaming and the frontend authentication UI will be handled by subsequent tasks. Do not weaken the harness profile or bypass checks. Synchronize backend and qa knowledge before completion.

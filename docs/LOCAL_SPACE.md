# Local-space application contract

The current web application is a static, browser-local personal workspace. Fresh startup contains no sample ideas, no preconfigured models and no account login. The flow is create space, configure a user-owned model, build ideas, export or import data.

## Persistence

Each space uses an independent `yang.space.v3.<id>` IndexedDB database. The `kv` object store contains one atomic snapshot with `revision` and `state`. Record or configuration changes are queued while a write is in flight. Transactions reject stale revisions and preserve the current window's draft in sessionStorage. The space index is stored in `yang.spaces.v3`, and the last selected space ID in `yang.active.v3`.

API keys are part of the local configuration and persist only on the current device. Ordinary JSONL exports redact keys; encrypted exports include them. Import validates the file before applying records. Model configuration import is explicitly opt-in. Existing legacy local storage namespaces and remote SQLite files are retained rather than deleted or implicitly merged.

## Network

The frontend makes no application-server API requests. Its only application-initiated network requests are explicit model tests and model operations, sent directly to the configured OpenAI-compatible endpoint. Requests omit cookies, suppress referrers and reject redirects. Authentication and rate errors are surfaced without forwarding raw provider errors. Providers must support browser CORS.

Calling a remote model sends the relevant prompt and selected idea context to that provider. Local persistence does not mean model inference is offline. No configured provider is bundled or inherited from the historical server configuration.

## UI

Settings are separated into space, models and transfer tabs. Configuration uses explicit save actions, connection tests, masked/revealable keys, a default model and optional per-action routes. Model test failures preserve entered values. Model actions do not silently substitute a bundled model or a question bank after an error. Onboarding and settings use responsive layouts, associated labels, live feedback and light/dark/reduced-motion states.

## Deployment boundary

The updated `ides.service` runs a static HTTP server bound to loopback and serves only `dist/`. It does not load the old environment file or invoke the Python application's database/model endpoints. Deployment scripts preserve old data directories for operator-controlled migration. The Nginx/TLS boundary is unchanged. Source changes alone do not alter the running deployment.

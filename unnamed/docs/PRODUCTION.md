# Production deployment

## Required configuration
1. Set `APP_ENV=production` and a strong `API_KEY`.
2. Set `LLM_API_KEY` and a model available to your account.
3. Keep `ALLOW_GITHUB_PUSH=false` and `ALLOW_PR_CREATION=false` until the deployment has been validated.
4. Persist `/app/workspace` because run state and audit logs live there.
5. Put the API behind TLS and an ingress/WAF.
6. Use `SANDBOX_MODE=docker` with a dedicated runner image or a stronger external sandbox service.

## GitHub write workflow
When ready, provide a least-privilege GitHub token, enable both write flags, and test against a disposable repository. The service pushes an AI-SRE branch and creates a PR only after verification passes.

## Scaling
The current store is SQLite and is intended for a single API node. For horizontal scaling, replace `RunStore` with PostgreSQL and move execution into a durable worker queue (for example Redis + a worker service). The domain APIs and agent/tool boundaries do not need to change.

## Observability
The run record includes tool calls, LLM calls/tokens, elapsed time, patch attempts, verification outcomes and audit events. Export these fields to your telemetry backend in a production adapter.

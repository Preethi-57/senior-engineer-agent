# Local production-style deployment

## Prerequisites
- Docker Desktop with Linux containers and Compose
- OpenAI API key
- Optional GitHub App credentials for real PR creation

## Start
1. Copy `.env.example` to `.env`.
2. Set `LLM_API_KEY`.
3. Keep GitHub push/PR disabled until you have tested locally.
4. Run `docker compose up --build`.

Services:
- API: http://localhost:8000/docs
- Dashboard: http://localhost:5173
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

The backend and worker share the workspace. Redis provides durable queued jobs and PostgreSQL stores run state. Repository commands execute through the policy boundary; when `SANDBOX_MODE=docker`, analysis/test commands run in network-disabled containers with dropped capabilities and resource limits.

## GitHub
For local PR testing, configure a GitHub App and enable `ALLOW_GITHUB_PUSH=true` and `ALLOW_PR_CREATION=true`. Prefer a dedicated test repository. Never use a personal PAT with broad permissions.

## Stop
`docker compose down` preserves named volumes. Use `docker compose down -v` only when you intentionally want to erase local database/queue/observability data.

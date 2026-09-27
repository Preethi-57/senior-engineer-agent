# AI-SRE Agent — Local Production Stack

This repository is the local deployment target for the AI-SRE platform. It is intentionally not an LLM wrapper: the model operates inside an orchestrator that supplies repository evidence and invokes a typed tool/policy layer. Static analysis, AST checks, RAG, sandboxed execution, tests, security scanners, post-fix verification, and evaluation remain application-owned components.

## Start locally

1. Install Docker Desktop.
2. Copy `.env.local.example` to `.env`.
3. Put your OpenAI API key in `LLM_API_KEY`.
4. Run `docker compose up --build`.

Open:
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

The first `docker compose up --build` downloads the required images and Python/Node dependencies. Do not commit `.env` or credentials.

## Local architecture

- PostgreSQL: durable run state
- Redis: queued analysis/remediation jobs
- Backend: FastAPI + SRE orchestrator + RAG + MCP/tool policy layer
- Worker: consumes Redis jobs and executes long-running analysis/remediation
- Sandbox: Docker execution with network disabled, dropped capabilities and resource limits
- Prometheus/Grafana: local operational metrics
- Frontend: React dashboard

## GitHub

Keep GitHub writes disabled while testing. For real PR creation, use a dedicated GitHub App with least-privilege permissions and enable both `ALLOW_GITHUB_PUSH` and `ALLOW_PR_CREATION`. Test against a repository you control.

## Verification

Without Docker, the source-level checks can still be run:

```bash
pytest -q backend/tests
python benchmark/run_benchmark.py
python -m compileall -q backend/app
```

Docker is required to validate the complete local multi-service stack and Docker sandbox.

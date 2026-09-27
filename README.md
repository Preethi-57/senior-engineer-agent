# AI-SRE Agent

A production-oriented AI Software Reliability Engineer that combines LLM reasoning with repository analysis, RAG, typed MCP tools, approval-gated remediation, isolated verification, GitHub PR automation and measurable evaluation.

## What makes this more than an LLM wrapper

The model does **not** own the system. The platform owns:

- repository cloning, size limits and indexing
- AST/static analysis and dependency/security scanners
- repository dependency graph
- chunked local RAG retrieval
- typed MCP/tool boundaries and command policy
- human approval before writes
- isolated remediation workspace
- tests, compile/lint/security verification
- post-fix re-analysis
- repair attempts when verification fails
- run persistence and audit logs
- GitHub branch/push/PR lifecycle, explicitly disabled by default
- evaluation metrics and benchmark methodology

The LLM is used for cross-file reasoning, root-cause analysis, remediation planning and patch generation from bounded evidence.

## Architecture

```text
                         AI-SRE PLATFORM
                              |
                 +------------+-------------+
                 |                          |
          SRE Orchestrator           Repository Engine
                 |                          |
          +------+-------+           +------+------+
          |      |       |           |      |      |
         RAG   Agents   State        AST   Graph   Index
          |      |                   |      |
          +------+-------------------+------+
                         |
                    MCP TOOL LAYER
                         |
              +----------+-----------+
              |          |            |
            GitHub    Sandbox    Observability
              |          |            |
              +----------+------------+
                         |
                  EXECUTION ENGINE
                         |
              +----------+-----------+
              |          |           |
            Tests     Security   Benchmarks
              |          |           |
              +----------+-----------+
                         |
                    VERIFICATION
                         |
                   +-----+-----+
                   |           |
                  PASS        FAIL
                   |           |
                  PR       Repair loop
```

## End-to-end flow

1. User supplies an authorized GitHub repository.
2. AI-SRE clones it into a bounded workspace.
3. Repository files are indexed and a dependency graph is built.
4. Deterministic analyzers and security scanners produce evidence.
5. Five specialist agents reason over retrieved evidence:
   - Security
   - Reliability
   - Architecture
   - Scalability
   - Performance
6. Findings and evidence are presented for human approval.
7. Approved findings are patched in a detached execution workspace.
8. Verification runs compile, tests, lint and security/dependency checks.
9. If verification fails, the repair agent gets the failure evidence and may make one corrective attempt.
10. The repository is re-analyzed to check whether the original finding disappeared.
11. When GitHub writes are explicitly enabled, a verified branch is pushed and a PR is created.

## Quick start

### 1. Configure

```bash
cp .env.example .env
```

Set at minimum:

```env
LLM_API_KEY=...
LLM_MODEL=gpt-5.6
```

For local development, leave the GitHub write flags disabled.

### 2. Backend

```bash
cd backend
python -m venv .venv
# activate the venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Optional frontend environment:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_API_KEY=
```

### 4. Docker

```bash
cp .env.example .env
docker compose up --build
```

## Production controls

For production:

```env
APP_ENV=production
API_KEY=<strong-secret>
SANDBOX_MODE=docker
ALLOW_GITHUB_PUSH=true
ALLOW_PR_CREATION=true
```

Use a least-privilege GitHub token and a dedicated sandbox runner. See `docs/PRODUCTION.md` and `SECURITY.md`.

## Evaluation

The included seeded benchmark is a regression smoke test, not a real-world accuracy claim. It currently contains seven known issues and the deterministic baseline detects all seven.

```text
Ground truth: 7
Predicted:    7
Precision:    1.00
Recall:       1.00
F1:           1.00
```

The intended serious evaluation compares:

- static/deterministic baseline
- LLM specialists
- combined AI-SRE system

across seeded and historical issues on multiple repositories. See `docs/EVALUATION.md`.

## Verification performed for this release

- Backend tests: 6/6 passing
- Seeded benchmark: 7/7 detected
- Python compilation: passing
- FastAPI smoke test: passing
- Durable SQLite persistence smoke test: passing

The local environment used for packaging did not have the `ruff` executable installed, so the local `ruff check` command could not be executed here; the dependency and CI configuration includes Ruff for a clean deployment environment.

# Security model

AI-SRE is designed for authorized repositories only. Do not point it at systems you do not own or have explicit permission to assess.

## Controls
- Analysis is read-only until a human approves finding IDs.
- LLMs receive bounded repository evidence, not unrestricted shell access.
- Tool execution is allowlisted and shell operators/path traversal are rejected.
- Secrets are redacted from tool output and LLM-visible evidence where possible.
- Remediation happens in a detached workspace.
- Verification runs before PR creation.
- GitHub push and PR creation are disabled by default and require explicit configuration.
- API key authentication is required when `APP_ENV=production`.
- Rate limiting is applied per client address.
- Repository size/file-count limits prevent unbounded indexing.

## Production sandbox
Set `SANDBOX_MODE=docker` and provide a prebuilt runner image containing the repository's test dependencies. The runner should have no network access, dropped Linux capabilities, a read-only root filesystem and bounded CPU/memory/process limits. For higher assurance, use a dedicated sandbox service or microVM runtime rather than mounting the host Docker socket into the API service.

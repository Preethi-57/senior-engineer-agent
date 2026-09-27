from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = ""
    workspace_root: str = "/app/workspace"
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-5.6"
    llm_timeout_seconds: int = 120
    github_token: str = ""
    allow_github_push: bool = False
    allow_pr_creation: bool = False
    github_api_base: str = "https://api.github.com"
    command_timeout_seconds: int = 120
    max_file_bytes: int = 500000
    max_repo_files: int = 20000
    max_repo_bytes: int = 250_000_000
    rag_top_k: int = 8
    max_concurrent_runs: int = 2
    sandbox_mode: str = "process"
    sandbox_image: str = "python:3.12-slim"
    rate_limit_per_minute: int = 30
    database_path: str = ""
    database_url: str = ""
    redis_url: str = "redis://redis:6379/0"
    job_queue_name: str = "ai-sre:jobs"
    metrics_enabled: bool = True
    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_app_installation_id: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    @property
    def workspace(self) -> Path:
        p = Path(self.workspace_root)
        if not p.is_absolute():
            candidates = [
                Path.cwd(),
                Path("/app"),
                Path(__file__).resolve().parents[2],
                Path(__file__).resolve().parents[3],
                Path("/tmp"),
            ]
            for candidate in candidates:
                if not candidate.exists():
                    continue
                target = candidate / self.workspace_root
                try:
                    target.mkdir(parents=True, exist_ok=True)
                    return target
                except PermissionError:
                    continue
            p = Path.cwd() / self.workspace_root
        try:
            p.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback = Path("/tmp") / "ai-sre-workspace"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        return p

    @property
    def database(self) -> Path:
        if self.database_path:
            p=Path(self.database_path)
            if not p.is_absolute(): p=self.workspace/p
        else:
            p=self.workspace/"ai_sre.db"
        p.parent.mkdir(parents=True,exist_ok=True)
        return p

settings=Settings()

"""MCP server exposing the same typed, policy-bounded tools used by AI-SRE.

The LLM never receives unrestricted shell access. MCP tools validate repository
paths and delegate execution to the allowlisted ToolRegistry.
"""
from pathlib import Path

from .core.settings import settings
from .tools.registry import ToolRegistry
from .tools.repo_tools import RepoTools
from .services.rag import RAGIndex

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("Install backend requirements to run the MCP server.") from exc

mcp=FastMCP("ai-sre-agent")


def _root(repo_path: str) -> Path:
    root=Path(repo_path).resolve()
    workspace=settings.workspace.resolve()
    if not root.exists() or not root.is_dir(): raise ValueError("Repository path does not exist")
    if not root.is_relative_to(workspace): raise ValueError("Repository path must be inside the configured workspace")
    return root

@mcp.tool()
def inspect_repository(repo_path:str)->dict:
    root=_root(repo_path); files=RepoTools(ToolRegistry()).files(root)
    return {"root":str(root),"files":[str(x.relative_to(root)) for x in files[:2000]],"count":len(files)}

@mcp.tool()
def read_source_file(repo_path:str, relative_path:str)->str:
    root=_root(repo_path); path=(root/relative_path).resolve()
    if not path.is_relative_to(root): raise ValueError("Path traversal rejected")
    return path.read_text(errors="replace")[:settings.max_file_bytes]

@mcp.tool()
def search_repository(repo_path:str, query:str)->list[dict]:
    root=_root(repo_path); files=RepoTools(ToolRegistry()).files(root); rag=RAGIndex(root,files,settings.max_file_bytes)
    return rag.search(query,settings.rag_top_k)

@mcp.tool()
def run_command(repo_path:str, command:str)->dict:
    root=_root(repo_path); return ToolRegistry(settings.command_timeout_seconds).shell(command,root)

@mcp.tool()
def run_tests(repo_path:str)->dict:
    return run_command(repo_path,"pytest -q")

@mcp.tool()
def run_security_scans(repo_path:str)->dict:
    root=_root(repo_path); registry=ToolRegistry(settings.command_timeout_seconds); out={}
    for name,cmd in [("bandit","bandit -r . -q"),("pip_audit","pip-audit"),("semgrep","semgrep --config auto --json .")]:
        try: out[name]=registry.shell(cmd,root)
        except Exception as exc: out[name]={"returncode":-1,"stderr":str(exc)}
    return out

@mcp.tool()
def git_diff(repo_path:str)->str:
    return RepoTools(ToolRegistry()).diff(_root(repo_path))

if __name__=="__main__": mcp.run()

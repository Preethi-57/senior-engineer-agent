from __future__ import annotations
import re
import httpx
from pathlib import Path
from ..core.settings import settings
from ..tools.registry import ToolRegistry

_GH=re.compile(r"^https://github\.com/([^/]+)/([^/#]+?)(?:\.git)?/?$")

def parse_github_url(url:str):
    m=_GH.match(url.strip())
    return (m.group(1),m.group(2)) if m else None

class GitHubService:
    def __init__(self, registry:ToolRegistry): self.registry=registry
    def push_branch(self, root:Path, branch:str):
        if not settings.allow_github_push or not settings.github_token: raise PermissionError("GitHub push is disabled or GITHUB_TOKEN is missing")
        self.registry.git_push(root, branch, settings.github_token)
    async def create_pr(self, repo_url:str, head:str, base:str, title:str, body:str):
        if not settings.allow_pr_creation or not settings.github_token: raise PermissionError("PR creation is disabled or GITHUB_TOKEN is missing")
        parsed=parse_github_url(repo_url)
        if not parsed: raise ValueError("PR creation currently supports github.com repositories only")
        owner,repo=parsed
        url=f"{settings.github_api_base.rstrip('/')}/repos/{owner}/{repo}/pulls"
        headers={"Authorization":f"Bearer {settings.github_token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post(url,headers=headers,json={"title":title,"head":head,"base":base,"body":body})
            r.raise_for_status(); data=r.json()
        return {"url":data.get("html_url"),"number":data.get("number"),"id":data.get("id")}

from __future__ import annotations
import shutil, subprocess
from pathlib import Path
from .registry import ToolRegistry
from ..core.settings import settings
IGNORED={".git",".venv","venv","build","dist","node_modules","__pycache__",".mypy_cache",".pytest_cache","coverage"}
class RepoTools:
    def __init__(self,registry:ToolRegistry): self.r=registry
    def clone(self,url:str,dest:Path,branch:str|None=None,token:str|None=None):
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists(): shutil.rmtree(dest)
        cmd=["git","clone","--depth","1","--no-tags"]
        if branch: cmd += ["--branch",branch]
        cmd += [url,str(dest)]
        env=None
        if token:
            env={**__import__('os').environ,"GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"http.extraHeader","GIT_CONFIG_VALUE_0":f"Authorization: Bearer {token}"}
        def run():
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=300,env=env)
            if p.returncode: raise RuntimeError(p.stderr[-5000:])
            return p
        return self.r.run("git",run)
    def files(self,root:Path):
        out=[]; total=0
        for p in root.rglob("*"):
            if not p.is_file() or any(x in IGNORED for x in p.parts): continue
            try: total+=p.stat().st_size
            except OSError: continue
            if len(out)>=settings.max_repo_files or total>settings.max_repo_bytes: break
            out.append(p)
        return out
    def read(self,path:Path,max_bytes=500000): return path.read_bytes()[:max_bytes].decode("utf-8",errors="replace")
    def diff(self,root:Path): return subprocess.run(["git","diff"],cwd=root,capture_output=True,text=True).stdout
    def status(self,root:Path): return subprocess.run(["git","status","--short"],cwd=root,capture_output=True,text=True).stdout
    def create_branch(self,root:Path,name:str): subprocess.run(["git","checkout","-b",name],cwd=root,check=True,capture_output=True)
    def commit(self,root:Path,message:str):
        subprocess.run(["git","add","-A"],cwd=root,check=True,capture_output=True)
        subprocess.run(["git","-c","user.name=AI-SRE Agent","-c","user.email=ai-sre-agent@localhost","commit","-m",message],cwd=root,check=True,capture_output=True)

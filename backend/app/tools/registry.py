from __future__ import annotations
import os, shlex, subprocess, time
from pathlib import Path
from typing import Callable
from ..core.security import redact_secrets
from ..core.settings import settings
from ..models.domain import ToolEvent

class ToolRegistry:
    """Policy boundary. Shell is deliberately constrained to known binaries and
    rejects shell syntax, absolute paths and parent traversal."""
    def __init__(self, timeout:int|None=None):
        self.timeout=timeout or settings.command_timeout_seconds; self.events:list[ToolEvent]=[]
        self.allow={"git","pytest","python","python3","ruff","bandit","pip-audit","semgrep","npm","node","go","cargo","mvn","gradle"}
    def run(self,name:str,fn:Callable,*args,**kwargs):
        started=time.perf_counter(); ok=False; metadata={}
        try: result=fn(*args,**kwargs); ok=True; return result
        except Exception as exc: metadata["error"]=redact_secrets(str(exc)); raise
        finally: self.events.append(ToolEvent(tool=name,action=getattr(fn,"__name__",name),success=ok,duration_ms=(time.perf_counter()-started)*1000,metadata=metadata))
    def shell(self,command:str,cwd:Path,timeout:int|None=None)->dict:
        if not cwd.resolve().is_relative_to(settings.workspace.resolve()): raise PermissionError("Execution directory outside workspace")
        if any(x in command for x in ["&&","||",";","|","`","$(",">","<"]): raise PermissionError("Shell operators are not allowed")
        parts=shlex.split(command)
        if not parts or parts[0] not in self.allow: raise PermissionError(f"Command not allowlisted: {parts[0] if parts else command}")
        if any(part.startswith("/") or ".." in Path(part).parts for part in parts[1:]): raise PermissionError("Unsafe command argument")
        started=time.perf_counter(); ok=False
        env={k:v for k,v in os.environ.items() if k in {"PATH","HOME","LANG","LC_ALL","PYTHONPATH"}}
        try:
            if settings.sandbox_mode == "docker":
                rel=cwd.resolve().relative_to(settings.workspace.resolve())
                mount=f"{cwd.resolve()}:/workspace:rw"
                docker=["docker","run","--rm","--network","none","--cap-drop","ALL","--security-opt","no-new-privileges","--pids-limit","256","--memory","1g","--cpus","2","--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=256m","-v",mount,"-w","/workspace",settings.sandbox_image,*parts]
                proc=subprocess.run(docker,capture_output=True,text=True,timeout=timeout or self.timeout,env={k:v for k,v in os.environ.items() if k in {"PATH","HOME","LANG","LC_ALL"}})
            else:
                proc=subprocess.run(parts,cwd=cwd,capture_output=True,text=True,timeout=timeout or self.timeout,env=env)
            ok=proc.returncode==0
            return {"returncode":proc.returncode,"stdout":redact_secrets(proc.stdout[-30000:]),"stderr":redact_secrets(proc.stderr[-30000:]),"duration_ms":(time.perf_counter()-started)*1000}
        finally: self.events.append(ToolEvent(tool="shell",action=" ".join(parts),success=ok,duration_ms=(time.perf_counter()-started)*1000,metadata={"sandbox_mode":settings.sandbox_mode}))
    def git_push(self,root:Path,branch:str,token:str):
        # Token is passed through git's extraHeader and never appears in the URL or logs.
        env={"GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"http.extraHeader","GIT_CONFIG_VALUE_0":f"Authorization: Bearer {token}"}
        proc=subprocess.run(["git","push","origin",branch],cwd=root,capture_output=True,text=True,timeout=self.timeout,env={**os.environ,**env})
        if proc.returncode: raise RuntimeError(redact_secrets(proc.stderr or proc.stdout))
        self.events.append(ToolEvent(tool="git",action="push",success=True,duration_ms=0))

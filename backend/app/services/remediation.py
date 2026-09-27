from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from ..models.domain import FixProposal, Finding
from .llm import get_provider


class RemediationEngine:
    def __init__(self, root: Path, rag=None, provider=None):
        self.root = root
        self.rag = rag
        self.provider = provider or get_provider()

    def apply(self, finding: Finding, proposal: FixProposal):
        """Backward-compatible deterministic application used by unit tests.
        Production execution uses generate_patch -> apply_edits after approval.
        """
        plan = self._deterministic_patch(finding)
        if not plan.get("edits"):
            return {"applied": False, "reason": plan.get("reason", "No safe deterministic patch")}
        result = self.apply_edits(plan["edits"])
        return {"applied": result.get("applied", False), "diff": result.get("diff", "")}

    async def generate_patch(self, finding: Finding, proposal: FixProposal) -> dict[str, Any]:
        """Generate an explicit edit plan after approval; never writes the repo."""
        provider = self.provider
        if provider.__class__.__name__ != "DisabledProvider":
            try:
                context = self.rag.context(self.rag.search(finding.title + " " + finding.description, k=6), max_chars=10000) if self.rag else ""
                system = """You are the patch engineer for an AI-SRE platform. Produce a minimal safe edit after a human has approved the finding. Return JSON only: {edits:[{file_path,old_text,new_text}], rationale}. old_text must be an exact substring of the supplied file evidence. Never invent file paths. Do not change unrelated code."""
                user=f"Approved finding:\n{finding.model_dump_json()}\nProposal:\n{proposal.model_dump_json()}\nEvidence:\n{context}"
                data=await provider.complete_json(system,user,{"edits":[]})
                if data.get("edits"):
                    return self._validate_edits(data["edits"])
            except Exception as exc:
                return {"applied":False,"reason":f"LLM patch generation failed: {exc}"}
        return self._deterministic_patch(finding)

    async def generate_repair(self, finding: Finding, proposal: FixProposal, verification: dict[str, Any]):
        context=self.rag.context(self.rag.search(finding.title + " " + finding.description, k=6), max_chars=9000) if self.rag else ""
        system="""You are the repair engineer in an AI-SRE platform. A previously approved patch did not verify. Produce a minimal corrective edit plan as JSON {edits:[{file_path,old_text,new_text}],rationale}. Only edit files named in the finding/proposal or directly required by the same root cause. old_text must exactly match current source evidence. Do not disable tests or scanners."""
        user=f"Finding:\n{finding.model_dump_json()}\nProposal:\n{proposal.model_dump_json()}\nVerification failure:\n{verification}\nRepository evidence:\n{context}"
        try:
            data=await self.provider.complete_json(system,user,{"edits":[]})
            return self._validate_edits(data.get("edits",[]))
        except Exception as exc:
            return {"applied":False,"reason":f"repair generation failed: {exc}"}

    def _validate_edits(self, edits):
        validated=[]
        for edit in edits:
            path=str(edit.get("file_path",""))
            old=str(edit.get("old_text","")); new=str(edit.get("new_text",""))
            target=(self.root/path).resolve()
            if not path or not target.is_file() or not target.is_relative_to(self.root.resolve()):
                continue
            current=target.read_text(errors="replace")
            if not old or old not in current:
                continue
            validated.append({"path":path,"old":old,"new":new})
        return {"applied":False,"reason":"Patch validated; awaiting write step","edits":validated}

    def apply_edits(self, edits):
        diffs=[]
        for edit in edits:
            path=(self.root/edit["path"]).resolve()
            if not path.is_relative_to(self.root.resolve()):
                raise PermissionError("Patch path escapes repository")
            before=path.read_text(errors="replace")
            if edit["old"] not in before:
                raise ValueError(f"Patch context no longer matches: {edit['path']}")
            after=before.replace(edit["old"],edit["new"],1)
            path.write_text(after)
            diffs.append("".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=edit["path"],tofile=edit["path"])))
        return {"applied":bool(edits),"diff":"\n".join(diffs)}

    def _deterministic_patch(self,finding):
        if not finding.files: return {"applied":False,"reason":"No files"}
        rel=finding.files[0]; path=(self.root/rel).resolve()
        if not path.is_file() or not path.is_relative_to(self.root.resolve()): return {"applied":False,"reason":"Invalid target"}
        before=path.read_text(errors="replace"); after=before
        if finding.title=="Bare exception handler":
            after=re.sub(r"(^\s*)except\s*:\s*$",r"\1except Exception as exc:\n\1    raise RuntimeError('Unhandled application error') from exc",after,flags=re.M)
        elif finding.title=="Shell command execution enabled": after=after.replace("shell=True","shell=False")
        elif finding.title=="Hardcoded credential-like value":
            pattern=r"(?i)(password|api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"
            after=re.sub(pattern,lambda m:f"{m.group(1)} = os.getenv('{m.group(1).upper()}')",after)
            if after!=before and "import os" not in after: after="import os\n"+after
        elif finding.title=="Blocking sleep in application code":
            after=after.replace("time.sleep(","await asyncio.sleep(")
            if after!=before and "import asyncio" not in after: after="import asyncio\n"+after
        else: return {"applied":False,"reason":"No deterministic safe fixer; LLM patching is required."}
        if after==before:return {"applied":False,"reason":"Pattern not matched"}
        return self._validate_edits([{"file_path":rel,"old_text":before,"new_text":after}])


class VerificationService:
    def __init__(self, root, tools): self.root=root; self.tools=tools
    @staticmethod
    def is_success(results:dict[str,Any])->bool:
        required=("compile","pytest","ruff","bandit","pip_audit")
        return all(results.get(k,{}).get("returncode") == 0 for k in required)
    def run(self):
        results={}
        commands=[("compile","python -m compileall -q ."),("pytest","pytest -q"),("ruff","ruff check ."),("bandit","bandit -r . -q"),("pip_audit","pip-audit")]
        for name,cmd in commands:
            try: results[name]=self.tools.shell(cmd,self.root)
            except Exception as e: results[name]={"returncode":-1,"stdout":"","stderr":str(e)}
        return results

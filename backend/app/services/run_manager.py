from __future__ import annotations
import asyncio, difflib, shutil, subprocess
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from ..agents.orchestrator import Orchestrator
from ..core.logging import AuditLogger
from ..core.persistence import RunStore
from ..core.settings import settings
from ..models.domain import Run,RunCreate,RunMetrics,RunStatus
from ..tools.registry import ToolRegistry
from ..tools.repo_tools import RepoTools
from .rag import RAGIndex
from .repository import RepositoryModel
from .remediation import RemediationEngine, VerificationService
from .github import GitHubService, parse_github_url
from .job_queue import queue
from .metrics import runs_total, findings_total, llm_calls_total, tool_calls_total, run_duration, active_runs

class RunManager:
    def __init__(self):
        self.store=RunStore(settings.database, settings.database_url); self.runs={}; self.tasks={}; self._load()
    def _load(self):
        for payload in self.store.list_payloads():
            try:
                r=Run.model_validate_json(payload); self.runs[r.id]=r
                if r.status in {RunStatus.ANALYZING,RunStatus.EXECUTING}: r.status=RunStatus.FAILED; r.error="Process restarted while run was active"; self._save(r)
            except Exception: continue
    def _save(self,run): self.runs[run.id]=run; self.store.save(run)
    def create(self,req:RunCreate):
        rid=str(uuid4()); run=Run(id=rid,repo_url=req.repo_url,branch=req.branch,status=RunStatus.CREATED,mode=req.mode,description=req.description); self._save(run); return run
    def enqueue(self,rid,kind="analyze"):
        return queue.enqueue(kind,rid)
    def get(self,rid):
        if rid not in self.runs: raise KeyError(rid)
        return self.runs[rid]
    async def analyze(self,rid):
        run=self.get(rid); started=perf_counter(); active_runs.inc(); run.status=RunStatus.ANALYZING; run.error=None; self._save(run)
        root=settings.workspace/"repos"/rid; registry=ToolRegistry(); audit=AuditLogger(settings.workspace/"runs"/rid/"audit.jsonl")
        try:
            RepoTools(registry).clone(run.repo_url,root,run.branch,settings.github_token or None)
            files=RepoTools(registry).files(root)
            rag=RAGIndex(root,files,settings.max_file_bytes)
            security={}
            for name,cmd in [("bandit","bandit -r . -q"),("pip_audit","pip-audit")]:
                try: security[name]=registry.shell(cmd,root)
                except Exception as e: security[name]={"returncode":-1,"stdout":"","stderr":str(e)}
            context={"file_count":len(files),"python_files":sum(p.suffix=='.py' for p in files),"javascript_typescript_files":sum(p.suffix in {'.js','.ts','.tsx','.jsx'} for p in files),"security_scans":security,"repository_graph":RepositoryModel(root,files).summary()}
            audit.event("repository_mapped",files=len(files),context={k:v for k,v in context.items() if k!='security_scans'})
            orchestrator=Orchestrator(root,rag,context); findings=await orchestrator.analyze(); proposals=await orchestrator.proposals(findings)
            run.findings=findings; run.proposals=proposals; run.tool_events=registry.events
            st=orchestrator.provider.stats; run.metrics=RunMetrics(findings=len(findings),critical_high_findings=sum(f.severity.value in {'critical','high'} for f in findings),tool_calls=len(registry.events),llm_calls=st.calls,llm_input_tokens=st.input_tokens,llm_output_tokens=st.output_tokens,elapsed_ms=(perf_counter()-started)*1000)
            run.status=RunStatus.AWAITING_APPROVAL; self._save(run); runs_total.labels("analyze","completed").inc(); run_duration.labels("analyze").observe(perf_counter()-started); active_runs.dec(); [findings_total.labels(f.category.value,f.severity.value).inc() for f in findings]; [llm_calls_total.inc() for _ in range(st.calls)]; [tool_calls_total.labels(e.tool,str(e.success).lower()).inc() for e in registry.events]; audit.event('analysis_complete',findings=len(findings))
            return run
        except Exception as e:
            run.status=RunStatus.FAILED; run.error=str(e); run.metrics.elapsed_ms=(perf_counter()-started)*1000; self._save(run); runs_total.labels("analyze","failed").inc(); run_duration.labels("analyze").observe(perf_counter()-started); active_runs.dec(); audit.event('analysis_failed',error=str(e)); return run
    def approve(self,rid,ids):
        run=self.get(rid)
        if run.status!=RunStatus.AWAITING_APPROVAL: raise ValueError("Run is not awaiting approval")
        chosen=set(ids); known={p.finding_id for p in run.proposals}; unknown=chosen-known
        if unknown: raise ValueError(f"Unknown finding ids: {sorted(unknown)}")
        for p in run.proposals: p.approved=p.finding_id in chosen
        run.metrics.approved_fixes=sum(p.approved for p in run.proposals); self._save(run); return run
    async def execute_async(self,rid):
        run=self.get(rid)
        if run.status!=RunStatus.AWAITING_APPROVAL: raise ValueError("Run must be awaiting approval")
        if not run.metrics.approved_fixes: raise ValueError("No approved fixes")
        started=perf_counter(); run.status=RunStatus.EXECUTING; self._save(run)
        source=Path(run.repo_path); execution=settings.workspace/"executions"/rid
        if execution.exists(): shutil.rmtree(execution)
        shutil.copytree(source,execution)
        registry=ToolRegistry(); files=RepoTools(registry).files(execution); rag=RAGIndex(execution,files,settings.max_file_bytes); engine=RemediationEngine(execution,rag)
        verification={}; applied=[]; repair_attempts=0
        try:
            for proposal in run.proposals:
                if not proposal.approved: continue
                finding=next((f for f in run.findings if f.id==proposal.finding_id),None)
                if not finding: continue
                plan=await engine.generate_patch(finding,proposal)
                if not plan.get('edits'): continue
                before=self._snapshot(execution)
                result=engine.apply_edits(plan['edits'])
                if not result.get('applied'): continue
                check=VerificationService(execution,registry).run()
                if not VerificationService.is_success(check):
                    self._restore(execution,before); repair_attempts+=1
                    repair=await engine.generate_repair(finding,proposal,check)
                    if repair.get('edits'):
                        retry=engine.apply_edits(repair['edits']); check=VerificationService(execution,registry).run()
                        if not retry.get('applied') or not VerificationService.is_success(check): self._restore(execution,before); continue
                proposal.patch_preview=result.get('diff',''); applied.append(proposal.finding_id); run.metrics.patches_applied+=1; verification=check
            if not verification: verification=VerificationService(execution,registry).run()
            post_files=RepoTools(registry).files(execution); post_rag=RAGIndex(execution,post_files,settings.max_file_bytes); post_orch=Orchestrator(execution,post_rag,{})
            post_findings=await post_orch.analyze()
            run.metrics.security_findings_before=sum(f.category.value=='security' for f in run.findings)
            run.metrics.security_findings_after=sum(f.category.value=='security' for f in post_findings)
            after_keys={(f.title,tuple(f.files)) for f in post_findings}
            resolved=sum(1 for f in run.findings if f.id in applied and (f.title,tuple(f.files)) not in after_keys)
            run.metrics.tests_passed=int(verification.get('pytest',{}).get('returncode')==0); run.metrics.tests_failed=int(not run.metrics.tests_passed)
            run.tool_events+=registry.events; run.metrics.tool_calls=len(run.tool_events); run.metrics.elapsed_ms=(perf_counter()-started)*1000
            run.status=RunStatus.COMPLETED; self._save(run)
            diff=self._tree_diff(source,execution); pr=None
            if applied and settings.allow_github_push and settings.allow_pr_creation:
                pr=await self._publish_pr(run,execution,applied)
            return {"run":run,"verification":verification,"post_findings":[f.model_dump() for f in post_findings],"resolved_findings":resolved,"diff":diff,"repair_attempts":repair_attempts,"pull_request":pr,"execution_workspace":str(execution)}
        except Exception as e:
            run.status=RunStatus.FAILED; run.error=str(e); run.metrics.elapsed_ms=(perf_counter()-started)*1000; run.tool_events+=registry.events; self._save(run); raise
    def execute(self,rid): return asyncio.run(self.execute_async(rid))
    async def _publish_pr(self,run,execution,applied):
        parsed=parse_github_url(run.repo_url)
        if not parsed: return None
        base=run.branch or self._default_branch(execution)
        branch=f"ai-sre/{run.id[:8]}"
        rt=RepoTools(ToolRegistry()); rt.create_branch(execution,branch); rt.commit(execution,f"fix: remediate {len(applied)} SRE finding(s)")
        gh=GitHubService(ToolRegistry()); gh.push_branch(execution,branch)
        return await gh.create_pr(run.repo_url,branch,base,f"AI-SRE remediation {run.id[:8]}",f"Automated remediation for {len(applied)} approved finding(s).\n\nRun: {run.id}\nVerification passed before PR creation.")
    @staticmethod
    def _default_branch(root):
        p=subprocess.run(['git','symbolic-ref','refs/remotes/origin/HEAD'],cwd=root,capture_output=True,text=True)
        return p.stdout.strip().split('/')[-1] if p.returncode==0 else 'main'
    @staticmethod
    def _snapshot(root):
        out={}
        for p in RepoTools(ToolRegistry()).files(root): out[str(p.relative_to(root))]=p.read_bytes()
        return out
    @staticmethod
    def _restore(root,snapshot):
        current={str(p.relative_to(root)):p for p in RepoTools(ToolRegistry()).files(root)}
        for rel,p in current.items():
            if rel not in snapshot: p.unlink()
        for rel,data in snapshot.items():
            p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
    @staticmethod
    def _tree_diff(before,after):
        bf={str(p.relative_to(before)):p for p in RepoTools(ToolRegistry()).files(before)}; af={str(p.relative_to(after)):p for p in RepoTools(ToolRegistry()).files(after)}; chunks=[]
        for rel in sorted(set(bf)|set(af)):
            old=bf[rel].read_text(errors='replace').splitlines(True) if rel in bf else []; new=af[rel].read_text(errors='replace').splitlines(True) if rel in af else []
            if old!=new: chunks.append(''.join(difflib.unified_diff(old,new,fromfile='before/'+rel,tofile='after/'+rel)))
        return '\n'.join(chunks)
    def report(self,rid):
        run=self.get(rid); return {'run':run.model_dump(),'evaluation':{'finding_count':len(run.findings),'high_critical':run.metrics.critical_high_findings,'patch_success_rate':run.metrics.patches_applied/run.metrics.approved_fixes if run.metrics.approved_fixes else 0,'test_pass_rate':1 if run.metrics.tests_passed else 0,'security_reduction':run.metrics.security_findings_before-run.metrics.security_findings_after}}
manager=RunManager()

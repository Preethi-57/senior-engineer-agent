from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .specialists import SecurityAgent, ReliabilityAgent, ArchitectureAgent, ScalabilityAgent, PerformanceAgent
from ..models.domain import Finding, FixProposal, Severity
from ..services.llm import get_provider


class Orchestrator:
    """Coordinates owned tools and specialist reasoning.

    Agents never execute shell commands directly. They receive evidence gathered
    by typed tools/RAG and return structured reasoning. Remediation is a separate,
    approval-gated phase.
    """
    def __init__(self, root: Path, rag, tool_context: dict[str, Any] | None = None):
        self.root, self.rag = root, rag
        self.tool_context = tool_context or {}
        self.provider = get_provider()

    async def analyze(self):
        agents = [
            SecurityAgent(self.root, self.rag, self.tool_context, self.provider),
            ReliabilityAgent(self.root, self.rag, self.tool_context, self.provider),
            ArchitectureAgent(self.root, self.rag, self.tool_context, self.provider),
            ScalabilityAgent(self.root, self.rag, self.tool_context, self.provider),
            PerformanceAgent(self.root, self.rag, self.tool_context, self.provider),
        ]
        results = await asyncio.gather(*(a.analyze_with_llm() for a in agents))
        findings=[]; seen=set()
        for batch in results:
            for f in batch:
                key=(f.category, f.title.lower(), tuple(f.files))
                if key in seen: continue
                seen.add(key); findings.append(f)
        order={Severity.CRITICAL:0,Severity.HIGH:1,Severity.MEDIUM:2,Severity.LOW:3,Severity.INFO:4}
        findings.sort(key=lambda f:(order[f.severity], -f.confidence))
        return findings

    async def proposals(self, findings):
        provider=self.provider; out=[]
        for finding in findings:
            # LLM proposal generation is evidence-grounded; if unavailable, a
            # deterministic proposal remains available for known safe transformations.
            proposal=await self._llm_proposal(provider, finding)
            out.append(proposal)
        return out

    async def _llm_proposal(self, provider, finding: Finding):
        summary=self._summary(finding)
        rationale=finding.root_cause
        tests=self._tests(finding)
        metrics=self._metrics(finding)
        try:
            context=self.rag.context(self.rag.search(finding.title + " " + finding.description, k=6), max_chars=9000)
            system="""You are the remediation planner in an AI-SRE system. Propose a safe, minimal code change for one finding. Do not claim a change is safe without evidence. Return JSON: {summary,rationale,files,test_plan,expected_metrics}. Do not output a patch here; patch generation occurs after explicit human approval."""
            user=f"Finding:\n{finding.model_dump_json()}\n\nRepository evidence:\n{context}"
            data=await provider.complete_json(system,user,{"summary":"","rationale":"","files":[],"test_plan":[],"expected_metrics":{}})
            return FixProposal(
                finding_id=finding.id,
                summary=str(data.get("summary") or summary),
                rationale=str(data.get("rationale") or rationale),
                files=[str(x) for x in data.get("files", finding.files)],
                test_plan=[str(x) for x in data.get("test_plan", tests if isinstance(tests,list) else [tests])],
                expected_metrics=data.get("expected_metrics") or metrics,
            )
        except Exception:
            return FixProposal(finding_id=finding.id, summary=summary, rationale=rationale, files=finding.files, test_plan=tests if isinstance(tests,list) else [tests], expected_metrics=metrics)

    def _summary(self,f):
        mapping={
            "Bare exception handler":"Replace bare exception handling with explicit exception types and preserve failure visibility.",
            "Hardcoded credential-like value":"Move credential material to runtime secret storage and read it only at execution time.",
            "Shell command execution enabled":"Remove shell interpretation and pass validated arguments as a structured command.",
            "Potential SQL injection":"Use parameterized query arguments rather than interpolating untrusted values.",
            "Blocking sleep in application code":"Use a non-blocking scheduling primitive when the execution context is asynchronous.",
            "Potential N+1 or repeated I/O in loop":"Batch or cache repeated I/O and add a query/request-count regression benchmark.",
        }
        return mapping.get(f.title,"Refactor the identified hotspot into a smaller, bounded and testable component.")

    def _tests(self,f):
        return {
            "security":["Add a regression test for the unsafe input/path.","Run SAST/dependency checks and confirm the finding is reduced without suppressions."],
            "scalability":["Measure I/O call count before and after.","Measure representative latency/throughput before and after."],
            "reliability":["Add a failure-path test proving the error remains observable."],
            "performance":["Run a representative latency/throughput benchmark."],
            "architecture":["Run the existing test suite and inspect dependency/coupling metrics."],
        }.get(f.category.value,["Add a focused regression test for the finding."])

    def _metrics(self,f):
        return {"success_criterion":"Issue-specific verification passes; existing tests do not regress; relevant security/performance/scalability metric improves."}

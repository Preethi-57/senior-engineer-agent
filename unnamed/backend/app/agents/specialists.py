from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any

from ..models.domain import Category, Finding, Severity
from ..services.llm import get_provider
from ..services.rag import RAGIndex


CATEGORY_RULES = {
    Category.SECURITY: "security vulnerabilities, unsafe input handling, secrets, injection, auth/authz, dangerous execution, insecure deserialization and dependency/security configuration",
    Category.RELIABILITY: "exceptions, retries, timeouts, resource handling, failure propagation, race conditions and operational failure modes",
    Category.ARCHITECTURE: "coupling, boundaries, dependency direction, layering, duplicated responsibilities and single points of failure",
    Category.SCALABILITY: "N+1 I/O, unbounded work, blocking operations, database access patterns, queues, caching and concurrency bottlenecks",
    Category.PERFORMANCE: "hot paths, expensive algorithms, blocking calls, repeated computation, serialization and latency/throughput bottlenecks",
}


class Specialist:
    name = "specialist"
    category = Category.RELIABILITY

    def __init__(self, root: Path, rag: RAGIndex, tool_context: dict[str, Any] | None = None, provider=None):
        self.root = root
        self.rag = rag
        self.tool_context = tool_context or {}
        self.provider = provider or get_provider()

    def pyfiles(self):
        return [p for p in self.root.rglob("*.py") if ".git" not in p.parts and "__pycache__" not in p.parts]

    def finding(self, severity, title, description, evidence, files, lines, root_cause, impact, confidence, source=None):
        key = f"{self.category.value}|{title}|{files}|{lines}"
        fid = hashlib.sha1(key.encode()).hexdigest()[:12]
        return Finding(
            id=fid,
            category=self.category,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence,
            files=files,
            line_refs=lines,
            root_cause=root_cause,
            impact=impact,
            confidence=max(0.0, min(1.0, confidence)),
            source_agent=source or self.name,
        )

    def deterministic(self) -> list[Finding]:
        return []

    def analyze(self) -> list[Finding]:
        return self.deterministic()

    async def analyze_with_llm(self) -> list[Finding]:
        deterministic = self.deterministic()
        provider = self.provider
        query = f"{self.category.value} {CATEGORY_RULES[self.category]}"
        retrieved = self.rag.search(query, k=8)
        evidence = self.rag.context(retrieved, max_chars=12000)
        system = f"""You are the {self.name} in an AI-SRE platform. Analyze only the supplied repository evidence.
You do not have direct filesystem or shell access. Do not invent files, lines, tests, metrics or vulnerabilities.
Focus on {CATEGORY_RULES[self.category]}.
A finding is useful only when it has concrete evidence and a plausible root cause. Prefer actionable issues over style opinions.
Return JSON only with this shape:
{{"findings":[{{"title":"...","severity":"critical|high|medium|low|info","description":"...","evidence":["..."],"files":["relative/path"],"line_refs":["12"],"root_cause":"...","impact":"...","confidence":0.0}}]}}
Maximum 5 findings. If evidence is insufficient, return an empty list."""
        user = f"Repository tool context:\n{self.tool_context}\n\nRetrieved repository evidence:\n{evidence}"
        try:
            data = await provider.complete_json(system, user, {"findings": []})
        except Exception:
            return deterministic
        llm_findings = self._parse_llm_findings(data)
        return self._merge(deterministic, llm_findings)

    def _parse_llm_findings(self, data: dict[str, Any]) -> list[Finding]:
        out = []
        for raw in data.get("findings", []) if isinstance(data, dict) else []:
            try:
                sev = Severity(str(raw.get("severity", "medium")).lower())
                files = [str(x) for x in raw.get("files", []) if str(x)]
                valid_files = [f for f in files if (self.root / f).resolve().is_relative_to(self.root.resolve()) and (self.root / f).exists()]
                if not valid_files:
                    continue
                lines = [str(x) for x in raw.get("line_refs", [])]
                out.append(self.finding(
                    sev, str(raw.get("title", "LLM finding")), str(raw.get("description", "")),
                    [str(x) for x in raw.get("evidence", [])], valid_files, lines,
                    str(raw.get("root_cause", "")), str(raw.get("impact", "")), float(raw.get("confidence", .6)), self.name + ":llm"
                ))
            except (ValueError, TypeError):
                continue
        return out

    @staticmethod
    def _merge(first: list[Finding], second: list[Finding]) -> list[Finding]:
        result = list(first)
        for item in second:
            duplicate = any(item.title.lower() == x.title.lower() and set(item.files) & set(x.files) for x in result)
            if not duplicate:
                result.append(item)
        return result


class SecurityAgent(Specialist):
    name = "security-agent"
    category = Category.SECURITY

    def deterministic(self):
        fs = []
        for p in self.pyfiles():
            try:
                text = p.read_text(errors="replace")
                tree = ast.parse(text)
                lines = text.splitlines()
            except Exception:
                continue
            rel = str(p.relative_to(self.root))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    fs.append(self.finding(Severity.HIGH, "Dynamic code execution", "User-controlled or dynamic data reaching eval/exec can execute arbitrary Python code.", [lines[node.lineno-1]], [rel], [str(node.lineno)], "Dynamic strings are being interpreted as code.", "An attacker may achieve arbitrary code execution if the input is attacker-controlled.", .98))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "executemany", "query"}:
                    for arg in node.args:
                        if isinstance(arg, (ast.JoinedStr, ast.BinOp)):
                            rendered = ast.get_source_segment(text, arg) or "dynamic SQL expression"
                            if re.search(r"(?i)\b(select|insert|update|delete)\b", rendered):
                                fs.append(self.finding(Severity.HIGH, "Potential SQL injection", "A SQL statement is constructed dynamically before execution.", [rendered], [rel], [str(node.lineno)], "SQL structure and data may be combined before execution.", "Attacker-controlled values can alter query semantics.", .92))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run":
                    if any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
                        fs.append(self.finding(Severity.HIGH, "Shell command execution enabled", "subprocess.run is configured with shell=True.", [lines[node.lineno-1]], [rel], [str(node.lineno)], "Command parsing is delegated to a shell.", "Untrusted command fragments can enable command injection.", .97))
            for i, line in enumerate(lines, 1):
                if re.search(r"(?i)(password|api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]", line):
                    fs.append(self.finding(Severity.HIGH, "Hardcoded credential-like value", "A credential-like literal is present in source code.", [line.strip()], [rel], [str(i)], "Secret material is stored in source instead of runtime secret storage.", "Secrets can leak through source control, logs or artifacts.", .96))
                if re.search(r"(?i)(select|insert|update|delete).*(%s|\+\s*\w+|f['\"])", line):
                    fs.append(self.finding(Severity.HIGH, "Potential SQL injection", "SQL appears to be constructed dynamically on a single source line.", [line.strip()], [rel], [str(i)], "SQL structure and data may be combined before execution.", "Attacker-controlled values can alter query semantics.", .84))
        return fs


class ReliabilityAgent(Specialist):
    name = "reliability-agent"
    category = Category.RELIABILITY

    def deterministic(self):
        fs=[]
        for p in self.pyfiles():
            try: tree=ast.parse(p.read_text(errors="replace")); lines=p.read_text(errors="replace").splitlines()
            except Exception: continue
            rel=str(p.relative_to(self.root))
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    fs.append(self.finding(Severity.MEDIUM,"Bare exception handler","A bare except catches every exception and can hide operational failures.",[lines[node.lineno-1]],[rel],[str(node.lineno)],"Exception handling is overly broad.","Failures may be swallowed, making incidents harder to detect and recover from.",.95))
        return fs


class ArchitectureAgent(Specialist):
    name="architecture-agent"
    category=Category.ARCHITECTURE

    def deterministic(self):
        fs=[]; imports={}
        py=set(str(p.relative_to(self.root)).replace('/','.')[:-3] for p in self.pyfiles())
        for p in self.pyfiles():
            try: tree=ast.parse(p.read_text(errors="replace"))
            except Exception: continue
            rel=str(p.relative_to(self.root)); imports[rel]=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Import): imports[rel]+= [x.name for x in n.names]
                elif isinstance(n,ast.ImportFrom) and n.module: imports[rel].append(n.module)
        for rel,mods in imports.items():
            local=[m for m in mods if any(m.replace('.','/') in x.replace('.','/') for x in imports)]
            if len(local)>=8:
                fs.append(self.finding(Severity.MEDIUM,"High module coupling",f"{rel} imports {len(local)} internal modules, indicating a potentially high-coupling boundary.",local[:8],[rel],[],"Responsibilities may be crossing module boundaries.","Changes can propagate widely and increase regression risk.",.72))
        return fs


class ScalabilityAgent(Specialist):
    name="scalability-agent"
    category=Category.SCALABILITY

    def deterministic(self):
        fs=[]
        for p in self.pyfiles():
            try: tree=ast.parse(p.read_text(errors="replace")); lines=p.read_text(errors="replace").splitlines()
            except Exception: continue
            rel=str(p.relative_to(self.root))
            for node in ast.walk(tree):
                if isinstance(node,(ast.For,ast.While)):
                    calls=[x for x in ast.walk(node) if isinstance(x,ast.Call)]
                    db=[x for x in calls if isinstance(x.func,ast.Attribute) and x.func.attr in {"execute","query","get","filter","find","find_one"}]
                    if db:
                        fs.append(self.finding(Severity.HIGH,"Potential N+1 or repeated I/O in loop","Database-like I/O is performed inside a loop and should be reviewed for batching/caching.",[lines[node.lineno-1]],[rel],[str(node.lineno)],"Per-item I/O can scale linearly with collection size.","Latency and database load can grow rapidly as traffic/data volume increases.",.86))
        return fs


class PerformanceAgent(Specialist):
    name="performance-agent"
    category=Category.PERFORMANCE

    def deterministic(self):
        fs=[]
        for p in self.pyfiles():
            try: text=p.read_text(errors="replace"); tree=ast.parse(text); lines=text.splitlines()
            except Exception: continue
            rel=str(p.relative_to(self.root))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="sleep":
                    fs.append(self.finding(Severity.MEDIUM,"Blocking sleep in application code","time.sleep can block the worker handling a request.",[lines[node.lineno-1]],[rel],[str(node.lineno)],"Synchronous sleep occupies a worker during waiting.","Throughput can degrade under concurrent load.",.91))
        return fs

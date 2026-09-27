from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl

class RunStatus(str, Enum):
    CREATED="created"; ANALYZING="analyzing"; AWAITING_APPROVAL="awaiting_approval"; EXECUTING="executing"; COMPLETED="completed"; FAILED="failed"
class Severity(str, Enum):
    CRITICAL="critical"; HIGH="high"; MEDIUM="medium"; LOW="low"; INFO="info"
class Category(str, Enum):
    SECURITY="security"; RELIABILITY="reliability"; ARCHITECTURE="architecture"; SCALABILITY="scalability"; PERFORMANCE="performance"; TESTING="testing"; DEPENDENCY="dependency"

class RunCreate(BaseModel):
    repo_url: str
    branch: str | None = None
    mode: str = "propose"
    description: str = "Analyze this repository for SRE issues."

class Finding(BaseModel):
    id: str
    category: Category
    severity: Severity
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    line_refs: list[str] = Field(default_factory=list)
    root_cause: str = ""
    impact: str = ""
    confidence: float = 0.5
    source_agent: str = ""
    ground_truth_id: str | None = None

class FixProposal(BaseModel):
    finding_id: str
    summary: str
    rationale: str
    files: list[str] = Field(default_factory=list)
    patch_preview: str = ""
    test_plan: list[str] = Field(default_factory=list)
    expected_metrics: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False

class ToolEvent(BaseModel):
    tool: str
    action: str
    success: bool
    duration_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)

class RunMetrics(BaseModel):
    findings: int = 0
    critical_high_findings: int = 0
    approved_fixes: int = 0
    patches_applied: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    security_findings_before: int = 0
    security_findings_after: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    elapsed_ms: float = 0
    before: dict[str, float] = Field(default_factory=dict)
    after: dict[str, float] = Field(default_factory=dict)

class Run(BaseModel):
    id: str
    repo_url: str
    branch: str | None = None
    status: RunStatus
    mode: str
    description: str
    repo_path: str = ""
    findings: list[Finding] = Field(default_factory=list)
    proposals: list[FixProposal] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    error: str | None = None

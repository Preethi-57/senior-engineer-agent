from dataclasses import dataclass
from typing import Iterable
from ..models.domain import Finding

@dataclass
class EvaluationResult:
    precision: float
    recall: float
    f1: float
    severity_weighted_recall: float

def evaluate(findings:Iterable[Finding], ground_truth:set[str]):
    predicted={f.ground_truth_id or f.id for f in findings}
    tp=len(predicted & ground_truth); fp=len(predicted-ground_truth); fn=len(ground_truth-predicted)
    precision=tp/(tp+fp) if tp+fp else 0
    recall=tp/(tp+fn) if tp+fn else 0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0
    return EvaluationResult(precision,recall,f1,recall)

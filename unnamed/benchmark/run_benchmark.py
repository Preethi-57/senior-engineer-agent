import sys, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.agents.specialists import SecurityAgent,ReliabilityAgent,ScalabilityAgent,PerformanceAgent
from app.services.rag import RAGIndex

root=Path(__file__).parent/"seed_repo"; files=list(root.glob("*.py")); rag=RAGIndex(root,files)
findings=[]
for cls in [SecurityAgent,ReliabilityAgent,ScalabilityAgent,PerformanceAgent]: findings += cls(root,rag).analyze()
truth={"Hardcoded credential-like value","Shell command execution enabled","Potential SQL injection","Potential N+1 or repeated I/O in loop","Blocking sleep in application code","Dynamic code execution","Bare exception handler"}
pred={f.title for f in findings}; tp=len(pred&truth); fp=len(pred-truth); fn=len(truth-pred)
p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0; f1=2*p*r/(p+r) if p+r else 0
result={"ground_truth":len(truth),"predicted":len(pred),"true_positive":tp,"false_positive":fp,"false_negative":fn,"precision":p,"recall":r,"f1":f1,"findings":sorted(pred)}
print(json.dumps(result,indent=2))

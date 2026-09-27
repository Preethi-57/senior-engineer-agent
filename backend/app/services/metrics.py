from prometheus_client import Counter, Histogram, Gauge
runs_total=Counter("ai_sre_runs_total","AI-SRE runs",["operation","status"])
findings_total=Counter("ai_sre_findings_total","Findings discovered",["category","severity"])
llm_calls_total=Counter("ai_sre_llm_calls_total","LLM calls")
tool_calls_total=Counter("ai_sre_tool_calls_total","Tool calls",["tool","success"])
run_duration=Histogram("ai_sre_run_duration_seconds","Run duration",["operation"])
active_runs=Gauge("ai_sre_active_runs","Active runs")

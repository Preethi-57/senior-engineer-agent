# AI-SRE Architecture

## Design goal

This is **not** a thin LLM wrapper. The model is one reasoning component inside a system that owns repository mapping, retrieval, tool policy, execution, remediation, verification and evaluation.

```text
                 React dashboard
                       |
                    FastAPI
                       |
               SRE Orchestrator
                       |
       +---------------+----------------+
       |               |                |
   RAG index      typed tools      run state/audit
       |               |
       |        +------+-------+
       |        |              |
       |      Git/FS        Sandbox
       |        |              |
       +--------+--------------+
                |
        specialist agents
   security / reliability / architecture
   scalability / performance
                |
          LLM reasoning
                |
       evidence-backed findings
                |
          human approval
                |
        patch generation engine
                |
      isolated execution workspace
                |
      tests / SAST / dependencies
                |
       post-fix re-analysis
                |
        measurable verification
```

## Separation of responsibilities

- **Deterministic analyzers:** AST checks, static scanners, dependency scanners, tests and benchmarks provide reproducible evidence.
- **RAG:** retrieves relevant source/config/documentation context rather than sending an entire repository to the model.
- **LLM specialists:** perform cross-file reasoning, root-cause analysis and remediation planning from bounded evidence.
- **MCP/tool layer:** exposes typed capabilities such as repository inspection, code search, tests and security scans. The model does not receive unrestricted shell access.
- **Policy boundary:** allowlists commands and rejects path traversal.
- **Approval gate:** no code modification happens during analysis.
- **Execution workspace:** approved changes are applied to a detached copy, not the source clone.
- **Verification:** existing tests, compile/lint/security checks and post-fix analysis determine whether the remediation actually worked.

## Agent roles

1. Security Agent
2. Reliability Agent
3. Architecture Agent
4. Scalability Agent
5. Performance Agent
6. Remediation Planner
7. Patch Engineer
8. Verification Engine

The first five run in parallel. The remediation planner is invoked only after findings exist; the patch engineer is invoked only after explicit approval.

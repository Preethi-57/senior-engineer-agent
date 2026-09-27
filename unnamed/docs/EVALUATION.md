# Evaluation methodology

The benchmark is intentionally split into **detection**, **remediation**, and **system efficiency**.

## 1. Detection benchmark

Freeze repositories and ground-truth issue IDs before an experiment. For each issue record category, severity, vulnerable file/location and expected root cause.

Compare:

- deterministic analyzers alone
- LLM specialists alone where possible
- combined AI-SRE system

Report precision, recall and F1 globally **and per category**. The included seeded benchmark is only a smoke benchmark; its 1.0 F1 must not be generalized to arbitrary repositories.

## 2. Remediation benchmark

A fix counts as successful only if:

1. the approved patch applies cleanly;
2. existing tests do not regress;
3. an issue-specific regression test passes where applicable;
4. the relevant security scanner no longer reports the issue without suppressing it;
5. the intended performance/scalability metric improves or does not regress;
6. post-fix re-analysis no longer identifies the original issue.

## 3. Efficiency

Record:

- wall-clock investigation time
- LLM calls
- input/output tokens
- tool calls
- retrieved chunks
- patch attempts
- verification iterations
- test runtime

## 4. Real-repository evaluation

Use multiple real open-source repositories of different sizes and frameworks. Add a frozen set of naturally occurring historical issues in addition to seeded issues. Never tune prompts/fixers against the final test split.

## 5. Suggested experiment table

| Experiment | Detection F1 | Patch success | Regression rate | Time/issue | LLM tokens | Tool calls |
|---|---:|---:|---:|---:|---:|---:|
| Static baseline | measure | n/a | measure | measure | 0 | measure |
| LLM specialists | measure | measure | measure | measure | measure | measure |
| AI-SRE combined | measure | measure | measure | measure | measure | measure |

The goal is to demonstrate **incremental value of the system architecture**, not to claim that the LLM itself is the product.

# Evaluation benchmark

The benchmark contains a deliberately vulnerable miniature repository so the project can validate the detection pipeline without relying on a network repository.

Ground truth:

- hardcoded credential-like value
- shell=True command execution
- SQL injection / dynamic SQL
- I/O inside loop / N+1 pattern
- blocking sleep
- dynamic code execution
- bare exception

The production workflow is designed for real repositories, but benchmark claims should use a fixed repository set and frozen issue labels so results are reproducible.

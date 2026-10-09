---
name: stage1
description: Delegate a complete Stage 1 task for a user-selected dataset through the native /skill:stage1 command. Use when explicitly invoked or when the user requests complete Stage 1, not for questions or discovery alone.
---

# Stage 1

Treat the appended user request as the dataset, objective and constraints for a
complete Stage 1 task. If absent, use the clearly selected dataset in this
conversation; ask for the dataset only if none is identifiable. Do not assume a
particular dataset or silently discard the user's budget or constraints.

Use the conversation workspace supplied in the runtime instructions. State its
path when starting. Write the final evidence report to `<workspace>/report.md`;
keep candidates under `<workspace>/environments/<name>/` and link their artifacts
from that report. Use absolute paths for generated files and shared raw data.
Existing runs are retained; do not automatically copy or move them into this
conversation. Raw data, product code and skills stay shared.

Read and follow `.deepagents/skills/discover-operation/SKILL.md`, then
`.deepagents/skills/generate-environment/SKILL.md`. You, the agent, own the
investigation: discover, prepare, build, evaluate, revise within budget, select
on validation, assess on held-out test, export the view and write the evidence
report. Continue through the authorized scope without requiring the user to
direct individual tools. Preserve native approvals and the Stage 2 boundary.

Reject invalid executions, including loop-capped or incomplete simulations,
before fidelity scoring or selection. A generated model is not automatically a
validated twin. If no candidate adequately represents the selected operation,
report **no acceptable candidate**, with failed experiments and the missing
mechanisms or evidence. Export an executable diagnostic model only with that
limitation clearly labeled; do not manufacture a successful selection. If no
model executes correctly, report the blocker and existing artifacts instead.

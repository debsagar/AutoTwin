---
name: stage2
description: Diagnose a selected process simulation, propose improvements, and run requested before-and-after scenario experiments. Use for Stage 2 or explicit process-improvement requests, not historical model calibration.
---

# Stage 2 — process improvement

Use the user's objective and constraints. A selected checkpoint is available as
`<workspace>/baseline/`, read-only. Read its README, selection and evidence before
choosing the model. Keep new analysis in this workspace; preserve the baseline.
A selected Stage 1 candidate in the current workspace can also be used: the
comparison tool preserves it and creates separate baseline/scenario copies. If
neither is available, ask which model to use or explain `--checkpoint NAME`.

The first task is diagnosis and an experiment proposal unless the user requests
scenario execution and supplies or accepts the necessary business assumptions.
Do not turn it into another unrestricted Stage 1 fitting search.

- Identify the operational objective, permitted changes and missing information
  that changes the decision: staffing qualifications, schedules, mandatory steps,
  costs, service targets and demand. Do useful diagnosis before asking; do not
  invent these as company facts.
- Trace important delays to case and activity evidence. Distinguish successful
  and rejected outcomes, rework, task intervals and gaps. Observed gaps are not
  automatically resource queues; simulation explanations remain model-dependent.
- Propose a small set of feasible changes and the evidence behind each. State
  the model parameter or rule involved, implementation assumptions and trade-offs.
- For the recommended experiment, specify baseline and scenario, demand and
  initial-state conditions, repeated runs, outcome definitions and uncertainty.
  Same seed numbers alone do not guarantee matched random draws; model errors
  need not cancel. Faster rejection is not faster successful fulfillment.
- For synthetic evaluation, a separate evaluator can apply the same intervention
  to the generating model after the proposal is fixed. That is a synthetic test,
  not proof of real-world impact. Do not access generating-model answers to choose
  an intervention. A checkpoint with prior reports is development evidence, not
  a blind assessment.

Write a concise `report.md` with evidence links, recommendations, missing business
inputs and the proposed experiment. Use code and delegation as needed; existing
wrappers do not limit analysis. Stop at the requested deliverable. Use `export_view`
for a supported local candidate copy when a visual artifact helps explain it.

Established starting points, not mandatory algorithms:
- Redesign heuristics and time/cost/quality/flexibility trade-offs:
  https://doi.org/10.1016/j.omega.2004.04.012
- Resource/roster optimization with Prosimos and explicit constraints:
  https://github.com/AutomatedProcessImprovement/optimos_v2
- Simulation inputs and units:
  https://github.com/AutomatedProcessImprovement/Prosimos

## Run a scenario when requested

`compare_scenario` handles task-duration scaling and resource headcount changes
on an existing workspace model bundle (including the mounted baseline). Inspect
its task labels and resource IDs before choosing changes. Supply the objective,
intervention assumptions, case count, repeated seeds and start date. Define a
successful-case activity where outcomes differ. Supply SLA/costs only when the
user provides or explicitly accepts them; inferred library defaults are not
business facts. Missing costs need not block a timing-only experiment.

The tool preserves both model copies, saves shared arrival schedules and run
logs, and exports `experiments/<name>/comparison.html` with `report.json`.
It checks case completion and reports uncertainty across repeated runs; it does
not certify the underlying model or choose the best business action. Read and
interpret the actual results, including outcome rates and uncertainty. Link the
results page in the final answer. Use workspace code for other justified changes;
this tool is a convenience, not the limit of your capabilities.

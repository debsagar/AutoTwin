---
name: stage2
description: Diagnose a selected frozen process simulation and propose business-process improvements and scenario experiments. Use for Stage 2 or explicit process-improvement requests, not historical model calibration.
---

# Stage 2 — process improvement

Use the user's objective and constraints. A selected checkpoint is available as
`<workspace>/baseline/`, read-only. Read its README, selection and evidence before
choosing the model. Keep new analysis in this workspace; preserve the baseline.
If no checkpoint is attached, explain how to start with `--checkpoint NAME`.

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

---
name: generate-environment
description: Complete Stage 1 from operational evidence to an executable, calibrated and assessed process simulation, with a final report and visualization.
---

# Complete Stage 1

You are the simulation analyst. Tools perform numerical work; you choose and
explain the scope, assumptions and experiments. Use existing authorization.
Do not require the user to know process-mining terminology or name each tool.

## Work through to a result

1. **Scope.** Read source documentation and use `inspect_log_scope` to choose a
   coherent cohort and chronological train/validation/test windows. Use
   `discover_process` only as a prefix overview. Record the case definition,
   dates, counts and exclusions returned by `prepare_environment`. Use its
   existing partition policy, not custom random sampling. If the size guard
   rejects the selection, first narrow to a documented process family or
   organizational cohort, or raise the guard within the compute budget. Do not
   shrink windows merely to fit the cap: cover ordinary case lifetimes and weekly
   work cycles. Before building, inspect retained multi-event traces and activity
   coverage against the claimed process. Reconsider scope if selection leaves
   mostly trivial traces. Do not optimize scope for a better score.
2. **Build a baseline.** `build_environment` fits train only and verifies execution
   with a baseline simulation. During authorized generation, choose and document
   missing-start estimation if required, unless the user prohibited it. State
   inferred calendars and missing-resource capacity as assumptions. Preserve
   baseline artifacts. Check execution and omitted behavior before calibration.
   Reject loop-capped, incomplete or otherwise invalid executions before scoring.
3. **Assess.** Read the `evaluate_environment` metric catalog. Select available
   published measures covering control flow and temporal behavior, rather than
   inventing a composite score. For completion-only logs, label completion spans
   and first-completion arrivals as proxies, not observed cycle/service times.
   Use several explicit seeds and report variation, units and observed case count.
   Use validation for this work; leave test untouched.
4. **Calibrate.** If a material discrepancy appears, use `inspect_environment`
   and the underlying files to examine repetitions, timing, routing and resources.
   State an explanation supported by evidence, then test a revision with `revise_environment` or a workspace experiment.
   Inspect installed library source and write code when the existing tool cannot
   express the investigation. Verify experimental models before scoring them. Compare candidates using `compare_evaluations`
   with the same validation data, seeds, case count, metrics and epoch. Report
   regressions and omitted activities. Do not change workforce or business rules
   merely to force a better fit. Retain the baseline if candidates are worse.
5. **Select and assess once.** Record the selected candidate and rationale before
   evaluating it on test with the chosen metrics and several seeds. Do not tune
   on test outcomes. If the final result is poor, say so; do not relabel validation
   as test or keep searching against the held-out results.
   Selection may conclude that no candidate is acceptable. Distinguish the best
   diagnostic model from one that adequately represents the selected operation;
   never select an invalid execution merely to finish the workflow.
6. **Deliver.** Call `export_view` for the selected model. Write one concise report
   in its environment directory linking the BPMN, parameters, manifest, evaluation
   reports and HTML. Include scope, assumptions, baseline versus selected
   validation results, final test results, failures and remaining limits. State
   which historical behaviors are supported and which uses need more evidence.

These steps describe a full Stage 1 request. For a narrower request, perform only
that scope. Reuse saved artifacts when resuming; check their provenance first.

## Keep the investigation bounded and honest

Use the user's experiment budget if provided. Otherwise, start with the baseline
and a small number of evidence-backed candidates. Stop when the model is useful for the stated scope, no evidence-backed improvement
remains after investigation, or the budget is reached. Lack of a tool option alone
is not a stopping condition. A missing
mechanism is a finding, not permission to invent one. Do not endlessly tune.

Verification asks whether the model executes correctly. Validation asks whether
it represents the selected historical behavior. Neither establishes that staffing
changes or new policies will have the predicted effect. There is no universal
log-distance pass threshold. Do not call a model a validated operational twin
solely because one metric improves.

The final report must also make the agent's work assessable: list the experiments
attempted, tool failures and recoveries, any user input needed, and which requested
artifacts were produced. Report time, model calls, tokens and cost only when the
runtime records them; otherwise mark them unavailable. Do not invent an agent
performance score. A faithful report of an inadequate model is a useful result.

Preserve raw data, original candidates and native approvals. Never read credentials
or bypass a rejected tool through shell execution. Stage 2 improvements are out
of scope until separately requested.

## References

- [Simod discovery and calibration](https://github.com/AutomatedProcessImprovement/Simod)
- [Simod, SoftwareX 2025](https://doi.org/10.1016/j.softx.2025.102157)
- [BPS quality evaluation, BPM 2023](https://doi.org/10.1007/978-3-031-41620-0_2)
- [Implemented log-distance measures](https://github.com/AutomatedProcessImprovement/log-distance-measures)

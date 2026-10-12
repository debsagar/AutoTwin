# Stage 2: diagnose, propose, then test a feasible change

Research guidance · 12 October 2026 · No application changes.

## Established basis

Use the ordinary simulation-study sequence: define the decision and inputs, inspect the baseline, propose feasible alternatives, design experiments, and assess validity for the intended use. Sargent distinguishes data validity, conceptual-model validity, implementation verification and operational validity; passing one does not replace the others. [Sargent, Winter Simulation Conference, 2003](https://www.informs-sim.org/wsc03papers/006.pdf).

The close technical precedent is **SIMOD → Prosimos**: discover and calibrate an executable business-process model from logs, then modify its scenario parameters for what-if analysis. SIMOD evaluates generated logs against validation data; its output separates BPMN structure from simulation parameters. This is a workflow precedent, not evidence that AutoTwin's interventions are accurate. [SIMOD, SoftwareX, 2025](https://doi.org/10.1016/j.softx.2025.102157). Prosimos explicitly represents processing times, arrivals, routing and resource availability, including differences between resources. [Prosimos, EDOC workshops, 2023](https://link.springer.com/chapter/10.1007/978-3-031-26886-1_23).

## Closest Stage 2 implementation: Optimos

**Optimos** already accepts BPMN, simulation parameters and organizational constraints, then simulates changes to resource allocation and calendars to explore cycle-time/cost tradeoffs. Its constraints include daily/weekly hours, consecutive hours and mandatory/forbidden work intervals. This is the strongest direct precedent for AutoTwin's next stage. [Optimos, BPM demonstrations, 2024](https://ceur-ws.org/Vol-3758/paper-23.pdf).

Reuse its **input contract and experiment pattern** now: baseline model + explicit constraints → feasible scenario → simulation → compared outcomes. Its [original official implementation](https://github.com/AutomatedProcessImprovement/roptimus-prime) documents CLI inputs and downloadable scenario parameters, making it a concrete later integration reference. Check supported constraints before adopting code; the README flags unimplemented fields. The [V2 repository](https://github.com/AutomatedProcessImprovement/optimos_v2) extends to batching and compares heuristic-guided search and reinforcement learning. Those searches, its Pareto-analysis suite and portal infrastructure are unnecessary for the first diagnosis/proposal task. This is a reuse recommendation, not a completed compatibility audit or integration.

## Inputs and baseline boundary

Start from the frozen [checkpoint](../runs/checkpoints/p2p_heuristics_v1/README.md) and its [assignment](../runs/checkpoints/p2p_heuristics_v1/STAGE2-TASK.md), working in copies. Preserve the selected topology and calibration. Record baseline hashes, log cohort, timestamp meanings, resource/calendar assumptions, evaluation limitations and the objective: reduce completion time for purchases reaching payment without bypassing approvals.

Before executing an intervention, specify admissible staffing and shift changes, skills, required controls, service targets and any cost limits. These are business inputs; a log cannot authorize them. The current first assignment deliberately leaves several unspecified.

**Calibration** changes a model to reproduce baseline observations. **Intervention** represents an operational decision under declared assumptions. Changing an estimated processing-time distribution until cycle time improves is not evidence of a feasible process improvement. Keep calibration fixed while comparing interventions; identify separately any revised baseline.

## Diagnosis and redesign

Separate paid and rejected paths before calculating completion metrics. Show counts, completion proportions and coverage. Inspect long-case distributions, repeated activities, task durations where starts exist, and gaps between activities. Connect each finding to cases and model elements. Completion-only gaps do not identify service, queueing, calendar closures or external delays. A simulated queue is a model explanation, not a measured fact.

Use established redesign heuristics as prompts, not automatic prescriptions. Reijers and Limam Mansar review their tradeoffs across time, cost, quality and flexibility. [Omega, 2005](https://research.tue.nl/en/publications/best-practices-in-business-process-redesign-an-overview-and-quali/). Examples include task elimination, parallelism, resequencing and specialist/generalist allocation, also examined in a practitioner study. [Limam Mansar and Reijers, Business Process Management Journal, 2007](https://pure.tue.nl/ws/files/1921798/Metis213736.pdf).

For AutoTwin, screen proposals explicitly:

- Capacity or calendar changes require evidence of a constrained resource, qualified staff and allowed hours.
- Parallelism or resequencing requires independent prerequisites; preserve approval and payment dependencies.
- Removing repeated work requires understanding why it occurs; required controls cannot simply disappear.

For each candidate, state the evidence, causal hypothesis, exact model lever, operational prerequisites and possible adverse effects. An unresolved prerequisite makes the proposal conditional.

## Experiment design after assumptions are chosen

Compare the unchanged baseline with one clearly specified alternative first. Fix demand, initial conditions, case mix, simulation horizon and completion/censoring rules. Report paid-case completion time, payment/rejection proportions, throughput and unfinished work; faster paid cases can otherwise conceal displaced work or changed selection. Include resource use and costs only when defined and supported.

Predeclare independent replicate seeds, a bounded run budget and the decision-relevant precision. Compare replicate-level outcomes and report differences with uncertainty, units and sample size. Distinguish run variability from uncertainty in estimated inputs and model structure; replication only addresses the former. Sensitivity runs can vary plausible uncertain inputs without presenting them as additional authorized interventions.

Common random numbers can improve precision when corresponding random inputs remain synchronized across scenarios. Merely reusing a seed can lose that correspondence as event ordering changes. [L’Ecuyer and Buist, WSC, 2006](https://www.informs-sim.org/wsc06papers/075.pdf). Report the coupling actually implemented; do not promise variance reduction, which can fail or reverse. [Wright and Ramsay, Management Science, 1979](https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.25.7.649).

## Independent synthetic check

The evaluator should retain the generating model separately, apply the same operational change to it, and estimate its baseline-to-intervention effect under matched experimental conditions. Compare predicted and generating-model effects: direction, magnitude, uncertainty, side effects and ranking if alternatives exist. Inspect incompatible lever semantics rather than forcing a comparison.

This is a proposed synthetic validation design, consistent with purpose-specific validation; it is not a new published method. Baseline historical agreement alone does **not** validate what-if predictions. Agreement with this generator establishes performance only for this synthetic setting. Freeze the recommendation before revealing generator results. The existing checkpoint contains held-out development evidence, so a genuinely blind task needs a separately prepared input bundle.

## Finite first task

Deliver one concise diagnosis, at most three conditional proposals and one experiment specification. Identify missing assumptions and explain the independent synthetic check. Stop before scenario implementation, inventing costs or claiming validated improvement. This follows the frozen assignment; a general optimizer, redesign framework and unrestricted recalibration are outside this task.

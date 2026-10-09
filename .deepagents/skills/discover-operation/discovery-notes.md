# What we learned from existing implementations

Source review: 2026-10-08. Source code was inspected; the external applications
were not installed or executed. The rules for AutoTwin below are design choices.

## Data-driven BPS: explicit input meaning and user control

Reviewed revision: `a8258fe80a6e28da5f344232ed04cb240ce4b686`.

- The upload validator requires `case_id`, `resource`, `activity`, `start_time`,
  and `end_time`. Its checks mainly concern headers and value types. They do not
  establish the business meaning of a field.
- The discovery page lets users select an uploaded log, choose Simod or
  AgentSimulator, change discovery settings, and inspect the resulting diagram.
- The XES converter pairs sorted start and complete rows by position. It checks
  equal counts, but does not verify matching case/activity identities for pairs.
  This is not a safe generic recipe for concurrent or incomplete event logs.
- The repository states that it is no longer maintained.

Sources:
- [Upload validator](https://github.com/5dv214vt25/Data-driven-BPS/blob/a8258fe80a6e28da5f344232ed04cb240ce4b686/backend/controller/src/eventlog_validator.py)
- [Discovery UI](https://github.com/5dv214vt25/Data-driven-BPS/blob/a8258fe80a6e28da5f344232ed04cb240ce4b686/frontend/src/pages/Discovery.tsx)
- [XES conversion](https://github.com/5dv214vt25/Data-driven-BPS/blob/a8258fe80a6e28da5f344232ed04cb240ce4b686/backend/controller/src/routes/utils/convert_files.py)
- [Workflow paper](https://ceur-ws.org/Vol-4032/paper-31.pdf)

## Simod: preprocessing changes the simulation assumptions

Reviewed upstream revision: `7e5de02e1b81ca4abb8d8dcd28b0ad315520b43e`.
The application above also contains a vendored Simod implementation, whose
`simod.py` and example configuration were inspected for the discovery sequence.

- Column roles are mapped through `EventLogIDs`.
- `Preprocessor.run` estimates start times if the column is absent or has nulls.
  The estimator is called with `replace_recorded_start_times=True`. It can also
  adjust durations for multitasking and estimate when activities became enabled.
- `EventLog.from_path` preprocesses the input before splitting it into partitions.
  AutoTwin should plan data separation before fitting estimators if it later
  claims held-out performance. Do not copy this sequence without checking leakage.
- Discovery estimates arrivals, process flow, resource behavior, and optional
  extra delays. Candidate settings are evaluated through simulated logs.
- Final outputs include a process model and simulation parameters. This establishes
  a concrete destination for preprocessing. It does not establish causal action
  effects for an arbitrary supply-chain export.

Sources:
- [Preprocessor](https://github.com/AutomatedProcessImprovement/Simod/blob/7e5de02e1b81ca4abb8d8dcd28b0ad315520b43e/src/simod/event_log/preprocessor.py)
- [Event log loading and splitting](https://github.com/AutomatedProcessImprovement/Simod/blob/7e5de02e1b81ca4abb8d8dcd28b0ad315520b43e/src/simod/event_log/event_log.py)
- [Discovery sequence inspected in the application](https://github.com/5dv214vt25/Data-driven-BPS/blob/a8258fe80a6e28da5f344232ed04cb240ce4b686/backend/simod/simod_src/src/simod/simod.py)
- [SoftwareX paper](https://doi.org/10.1016/j.softx.2025.102157)

## Decision for AutoTwin

The initial discovery-only prototype used these projects as method references.
Stage 1 now reuses PM4Py, PIX and Prosimos to generate an executable model.
Investigate the operation before choosing a simulation representation. Keep
recorded events, inferred timings, user statements, and proposed mechanisms
separate. Ask the user about uncertainty that changes the design. A good first
result links a data finding to a specific modeling decision.

## Shared operations and role-specific experiments

A process can contain several participants. Preserve their dependencies before
selecting an operator for evaluation. Organizational discovery concerns who does
work. Object-centric representations concern linked business objects. Resource-
centric simulation concerns participant behavior and handovers. These are separate
ideas; none alone establishes action effects or formal permissions.

- [OCEL 2.0](https://www.ocel-standard.org/specification/overview/): linked objects
  and events; a representation, not an automatic simulator.
- [AgentSimulator, Process Science 2025](https://link.springer.com/article/10.1007/s44311-025-00009-5):
  resource behavior and interactions, including centralized and autonomous work.

These sources were reviewed during the preceding product-direction discussion.
Use the user's improvement question to select detail. Begin with interactive
what-if comparisons. Agent replacement is one comparison; staffing, capacity,
priority, and approval changes are others.

## Stage 1 terminology and selected components (2026-10-08)

- **Process discovery**: infer control flow from observed event sequences.
  PM4Py's Inductive Miner supplies a structured model exported as BPMN.
- **Simulation model discovery / parameter estimation**: estimate arrivals,
  resource calendars, task durations and routing probabilities. PIX supplies
  these functions, also used by Simod. Missing starts require estimation, not
  renaming event gaps as service times.
- **Business-process simulation (BPS)**: execute the BPMN plus parameters in
  Prosimos, a discrete-event simulator. Model construction and simulation are
  different steps.
- **Model validation**: compare generated logs with held-out cases and report
  disagreement. A successful engine run is not validation of a real operation.
- **Digital twin**: would additionally need a defined connection/update loop
  to the real operation. A historical BPI-derived model does not provide that.

Stage 2 will cover interventions and agent evaluation. Stage 1 visualizations
show generated execution records, with an illustrative process layout. They
do not infer a physical warehouse floor from procurement events.

References checked for implementation:
- https://processintelligence.solutions/pm4py/examples/process-discovery/
- https://simod.readthedocs.io/en/latest/usage.html
- https://github.com/AutomatedProcessImprovement/pix-framework
- https://github.com/AutomatedProcessImprovement/Prosimos

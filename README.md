# AutoTwin — Stage 1

A conversational terminal agent that turns selected event-log evidence into a
candidate business-process simulation. The agent chooses scope and diagnostics;
tools execute extraction, discovery, simulation and comparison.

## Open the agent

```sh
cd /data/autotwin
uv run python main.py
```

Python 3.12 and uv are required. Credentials stay in local `.env`. Startup is
idle. Native Manual mode retains approvals for writing tools. Product skills
come only from `.deepagents/skills/`; sessions stay in `.dcode/`.

For example:

> Investigate the BPI 2019 data for a small procurement simulation. Inspect the
> coverage and propose suitable periods and a cohort. Explain what we lose by
> selecting them before building anything.

Or, with an existing model:

> Assess the environment named my-procurement. Choose useful diagnostics from
> the available timestamps and compare several simulation runs with validation
> data. Explain the mismatches and which assumptions deserve investigation.

No special tool names are required in conversation. Explicit skills remain
available as `/skill:discover-operation` and `/skill:generate-environment`.

## Capabilities

| Agent tool | Result |
|---|---|
| `discover_process` | Exploratory PM4Py paths and handovers from a disclosed file prefix. |
| `inspect_log_scope` | Full-file coverage, categories and monthly first/last observed case timestamps. |
| `prepare_environment` | Whole observed cases in caller-chosen train/validation/test windows; optional cohort filter, source hash and exclusion counts. |
| `build_environment` | PM4Py BPMN, PIX parameters and a 200-case Prosimos execution check, fitted on train only. |
| `evaluate_environment` | Available metric catalog or selected log-distance comparisons across caller-chosen seeds and partition. |
| `export_view` | Standalone offline Three.js replay of the generated baseline trace. |

Preparation takes explicit half-open windows, for example
`{"train":{"start":"2018-01-01","end":"2018-04-01"}}`; dates mean UTC
midnight. Validation and test windows are optional. There is no automatic split
ratio or category. `max_cases` rejects an oversized selection rather than
randomly dropping cases. An overlap or empty requested partition is rejected.

The XES mapping is trace ID, activity, completion timestamp, optional
`start_timestamp`, and resource. Other formats need a mapping/conversion first.

## Evaluation, not automatic certification

Building does not access validation or test files. Evaluation is a separate
agent choice. `metrics=None` returns the metric catalog without simulating;
otherwise supply metric names and explicit seeds. Results include each run,
mean, standard deviation, metric definitions and input hashes. They are written
to unique `evaluations/` folders; the model and baseline are unchanged.

Completion-only metrics cover activity trigrams, first-to-last completion spans,
first-completion arrival proxies, within-case completion timing and weekly
completion patterns. These use `log-distance-measures`. Full start-to-end cycle
time and first-start arrival metrics require recorded starts. Resource workload
metrics are not implemented. No metric threshold declares a model valid.

Important limits:

- Whole-case containment excludes crossing cases and favors shorter cases near
  boundaries. Category filtering can omit competing work. Neither restores the
  full operation; the agent must assess those exclusions.
- Completion-only logs do not measure work duration or true case arrivals.
  Missing starts require accepted PIX estimation. Inferred calendars are not
  staffing rosters; missing identities retain the prototype's assumed 200
  external slots, not measured employees.
- Evaluation starts with an empty system, without warm-up or existing backlog.
  A good historical distance does not establish intervention validity.
- The agent chooses scope and diagnostics. The current builder still uses fixed
  Inductive Miner and PIX fitting methods. Automated calibration/optimization and
  Stage 2 process changes or agent-policy evaluation are not implemented.

## Files and prior example

Models live in `runs/environments/<name>/`: manifest, named partition CSVs,
`train_fitted.csv`, BPMN, parameter JSON, baseline simulation, build report,
evaluations and optional HTML. Existing prepared names are not overwritten.
Rebuilding updates model/baseline; export the HTML again afterward.

`bpi2019-demo` and `artifacts/autotwin-stage1.html` are preserved **legacy**
examples using random reservoir selection and a random held-out split. Their
reported 40-day versus 67-day median spans are prototype diagnostics, not a
validated assessment. New preparation no longer uses that selection protocol.

The visualization represents process activity stations, not recovered warehouse
geometry. It replays simulator output; it does not run Python in the browser.

## Small implementation

`main.py` launches dcode. `process_mining.py` registers tools and the local skill
and approval compatibility overrides. `environment.py` prepares and builds;
`validation.py` runs comparisons; `viewer.py` and `visual/` export the replay.
Versions are pinned. No custom chat store or orchestration framework.

Focused developer checks:

```sh
uv run python temporal_selection_check.py
uv run python validation.py --selfcheck
uv run python viewer.py
```

These check implementation integrity, not operational validity. Real CLI evidence
for this revision is recorded under `runs/temporal-cli/`; Luna selected a
2-way-match cohort, generated a model, evaluated two seeds and reported a severe
mismatch. Successful tooling does not mean successful modeling. Development
history is in [PROJECT-LOG.jsonl](PROJECT-LOG.jsonl).

Methods: [generation skill](.deepagents/skills/generate-environment/SKILL.md).
Data: [Boudewijn van Dongen, BPI Challenge 2019](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1), CC BY 4.0.
Three.js attribution is in `visual/vendor/`.

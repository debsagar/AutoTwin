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

### Restart and resume

`uv run python main.py` starts a new conversation. To continue an interactive
conversation, use `uv run python main.py -r` (most recent) or
`uv run python main.py -r <thread-id>` (a specific conversation).
Each conversation writes to `runs/workspaces/<thread-id>/`. A new conversation
(including `/new`) gets a fresh workspace; resuming the same thread reuses it.
The directory is created on the first model/tool request, not while the UI is
idle. Raw `data/`, product code and skills stay shared; nothing is copied.
Old runs remain where they are and can be read explicitly. New conversations
do not inherit the previous chat or candidate names. Workspaces accumulate
until you remove them; restarting does not reset their files.

In the pinned CLI version, headless mode (`-n`) does not resume threads. A
headless-created thread can display its history in the interactive UI but cannot
continue there if its recorded tool policy differs. Start a new interactive
conversation and point it to the saved run instead. Do not disable approvals to
work around a policy mismatch.

The default CLI runs tools directly on this VM, not in a sandbox. Restarting
reloads Python code; it does not undo file changes or guarantee that interrupted
work has completed. Inspect the saved results before continuing.

## Run Stage 1 inside the CLI

Enter this in the interactive agent, not in your shell:

```text
/skill:stage1 data/bpi2019/BPI_Challenge_2019.xes — complete Stage 1, with at most two evidence-backed revisions
```

This native slash command delegates discovery, generation, validation, candidate
selection, final assessment, replay export and reporting to the agent. Replace
the dataset and constraints as needed. It preserves native tool approvals;
it does not launch a separate scripted workflow. Use `/reload` to refresh skills
in an already-open CLI, or restart to load changed Python tools.

The agent owns technical choices within that task. It asks only for missing
business facts essential to proceed. Invalid simulations cannot be selected;
the result can be **no acceptable candidate**. Stage 2 remains separate.

Ordinary conversation also works. Narrower skills remain available as
`/skill:discover-operation` and `/skill:generate-environment`.

## Capabilities

| Agent tool | Result |
|---|---|
| `discover_process` | Exploratory PM4Py paths and handovers from a disclosed file prefix. |
| `inspect_log_scope` | Full-file coverage, categories and monthly first/last observed case timestamps. |
| `prepare_environment` | Whole observed cases in caller-chosen train/validation/test windows; optional cohort filter, source hash and exclusion counts. |
| `build_environment` | PM4Py BPMN, PIX parameters and a 200-case execution check, with explicit discovery settings and replay diagnostics. |
| `inspect_environment` | Recorded/generated repetitions, timing and routing evidence for investigating a mismatch. |
| `revise_environment` | Separate candidate built from unchanged partitions, inherited settings and a recorded reason. |
| `compare_evaluations` | Metric results and settings, with experiment compatibility checks; no automatic winner. |
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
otherwise supply metric names and explicit seeds. Each evaluation also computes
PM4Py alignment-based fitness and precision against the observed split. Results include each run,
mean, standard deviation, metric definitions and input hashes. They are written
to unique `evaluations/` folders; the model and baseline are unchanged.

Completion-only metrics cover activity trigrams, first-to-last completion spans,
first-completion arrival proxies, within-case completion timing and weekly
completion patterns, plus absolute completion timestamps. These use `log-distance-measures`. Full start-to-end cycle
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
- The agent can investigate, revise and compare candidates. Supported discovery
  settings are Inductive Miner `noise_threshold` and PIX `gateway_method`
  (`discovery`, `equiprobable`, or `token_replay`), plus PIX `arrival_filter_outliers`.
  `token_replay` counts complete PM4Py training replays, including silent loop
  exits; it rejects incomplete replay and currently supports exclusive/parallel
  gateways. It does not make timing assumptions or intervention effects valid.
  Arrival filtering is an explicit assumption and can collapse batch-heavy
  arrivals to zero gaps. Pruning may omit rare behavior; equiprobable
  routing is an assumption, not learned behavior. No numerical optimizer or
  Stage 2 operational intervention/agent-policy evaluation is implemented.

## Files and prior example

Start with `runs/workspaces/<thread-id>/report.md`, the final Stage 1 report.
Models live in that workspace’s `environments/<name>/`: manifest, named partition CSVs,
`train_fitted.csv`, BPMN, parameter JSON, baseline simulation, build report,
evaluations and optional HTML. Existing prepared names are not overwritten.
Rebuilding updates model/baseline; export the HTML again afterward.

Older runs are retained as development evidence under `runs/`. Their results
are not the final Stage 1 assessment. Use the trial evidence below; a completed workflow is not a fidelity pass.

The visualization represents process activity stations, not recovered warehouse
geometry. It replays simulator output; it does not run Python in the browser.

## Small implementation

`main.py` launches dcode. `process_mining.py` registers tools and the local skill
and approval compatibility overrides. `environment.py` prepares and builds;
`validation.py` runs comparisons; `model_tools.py` inspects and revises models;
`viewer.py` and `visual/` export the replay with matching evaluation summaries.
Versions are pinned. `workspace.py` uses the native thread ID and supported
[extension middleware](https://docs.langchain.com/oss/deepagents/code/extensions)
to scope product tools and native file paths. Conversation
[persistence](https://docs.langchain.com/oss/python/langgraph/persistence) stays
with dcode; no custom chat store or orchestration framework. Native shell
commands start in the workspace but can access absolute paths: this is output
organization, not an OS sandbox. Standalone developer scripts retain the legacy
`runs/environments/` default.

Focused developer checks:

```sh
uv run python workspace_check.py
uv run python temporal_selection_check.py
uv run python validation.py --selfcheck
uv run python calibration_build_check.py
uv run python model_tools_check.py
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

## Stage 1 trial evidence

The fresh CLI task, full transcript, agent performance counts, selection record,
and final assessment are under `runs/stage1-transfer/`. The task uses the native
CLI with a bounded run; no additional orchestrator or automatic grading model.
Simulation fidelity and agent task completion are reported separately.

- `report.md`: agent's model assessment and artifact paths.
- `agent-metrics.json`: recorded calls, failures, runtime, tokens and cost.
- `selection.json`: candidate choice recorded before final test evaluation.
- `task.txt` and `transcript.json`: reproducible assignment and execution evidence.

Process fitness/precision measure structural conformance. Log distances measure
historical distribution similarity. Neither is a certificate of causal validity
or a claim that staffing changes will have a predicted effect.

The Terra comparison is in `runs/stage1-terra/` (actual model:
`openai/gpt-5.6-terra`). Its historical baseline and final-test distances are
invalid for selection: Prosimos terminated cases at its loop limit. The original
agent report is preserved; `review.md` records the correction. Current tools
reject these runs. Earlier Luna trials also showed large fidelity gaps.

### Routing fidelity follow-up

`gateway_method="token_replay"` fixes missed silent loop exits using complete
training replays. It leaves the BPMN, fitted timings, arrivals and resources
unchanged. Three-seed validation on the larger saved cohort reduced trigram
distance from 0.629 to 0.443 and completion-span distance from 1,047 to 410 hours.
Circadian distance did not improve (5.663 to 5.679 hours). These are validation
diagnostics, not a new held-out test or an operational-validity pass.

- `runs/stage1-fidelity/report.md`: controlled two-cohort investigation.
- `runs/stage1-fidelity-agent/report.md` and `review.md`: actual CLI agent run and independent audit.
- `runs/stage1-fidelity-agent/agent-metrics.json`: 28 tool calls, three recovered
  inspection-path errors, 319 seconds, recorded model cost about $0.075.
- `artifacts/autotwin-stage1.html`: current agent-generated diagnostic replay.

The comparison tool currently treats changed boundary-description prose as a
protocol difference. The independent audit verifies that the historical and new
runs used the same actual simulation settings; original reports are preserved.
Timing mismatch and unavailable bounded alignment conformance remain limitations.

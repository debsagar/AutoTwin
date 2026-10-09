# AutoTwin — Stage 1

A conversational terminal agent that turns a selected event log into a candidate
business-process simulation. The first working example is **BPI 2019 procurement**.

## Open the agent

```sh
cd /data/autotwin
uv run python main.py
```

Python 3.12 and uv are required. Credentials stay in the local `.env`.
Startup is idle. Manual mode keeps native approval prompts for writing tools.
Only AutoTwin's project skills are exposed; developer skills are excluded.

Inside the conversation, start with:

```text
/skill:discover-operation data/bpi2019/BPI_Challenge_2019.xes
```

To request the complete first stage, say:

> Generate an environment from data/bpi2019/BPI_Challenge_2019.xes called
> my-procurement. Use 1,000 invoice-before-GR cases. I accept estimated missing
> start times and synthetic external capacity for missing resource identities.
> Build the baseline and export the offline 3D view. Stop at Stage 1.

The agent calls tools, explains evidence and assumptions, and stops at your
requested scope. It does not run a pipeline just because data is present.

## What Stage 1 does

| Agent tool | Result |
|---|---|
| `discover_process` | Observed flows, variants and handovers through PM4Py. Default: first 5,000 cases, explicitly a file prefix. |
| `prepare_environment` | Selects a category with seeded reservoir sampling across the whole XES file; writes source hash, prerequisites, raw timestamps, and disjoint train/held-out cases. |
| `build_environment` | Uses PM4Py's Inductive Miner for BPMN, PIX for parameter estimation, and Prosimos for a 200-case discrete-event simulation. Reports held-out differences. |
| `export_view` | Writes a standalone Three.js HTML replay using the generated BPMN and execution trace. No server or internet is needed to open it. |

Generated files live in `runs/environments/<name>/`: `manifest.json`,
`train.csv`, `heldout.csv`, `train_fitted.csv`, `model.bpmn`, `parameters.json`,
`simulation.csv`, `simulation_statistics.csv`, `report.json`, and `environment.html`.
Existing prepared names are not silently overwritten. A requested rebuild updates
the model and run; export the view again after rebuilding.

The XES mapping is explicit: trace identifier, activity, completion timestamp,
optional `start_timestamp`, and resource. Other input formats still need a field
mapping/conversion discussion. This is not an arbitrary-file-to-twin promise.

## Inspect the working example

Open `runs/environments/bpi2019-demo/environment.html` in a browser, or copy it
to your local machine. Select a case, play, scrub time, step events, or click a
station. The scene represents the discovered process; its layout is illustrative,
not a recovered warehouse floor. It replays real **simulator output**.

The example selected 1,000 cases from 221,010 matching cases in the full log:
800 train and 200 held out. It generated **200 cases / 1,012 events**.
Median first-to-last completion span is about **40 days generated / 67 days
held out**. Its status is **`generated_unvalidated`**.

Important assumptions remain visible in the artifact and report:

- Missing starts are estimated on training cases only. They are not measured
  service times. Availability calendars are inferred, not staffing rosters.
- Missing resource identities use synthetic external slots to avoid making
  unrelated vendors queue behind one invented worker. These are not employees.
- Arrivals describe a thinned cohort, not the full company's workload.
- The case-level held-out comparison is diagnostic; it does not validate
  business rules, staffing interventions, or causal effects of new actions.

**Stage 2**—process changes, optimization, and agent evaluation—is not implemented.

## Small implementation

`main.py` launches dcode. `process_mining.py` exposes the four tools and local
runtime policy. `environment.py` builds the model using established libraries.
`viewer.py` and `visual/` export the view. `intake.py` retains read-only file
inspection helpers. The obsolete automatic intake script was removed.

The dcode extension and skill-isolation integration uses two narrowly scoped
compatibility overrides; tested versions are pinned in `pyproject.toml`/`uv.lock`.
Sessions are local in `.dcode/` (`/threads` in the terminal). No custom chat store.

Verification evidence is in `runs/stage1-cli/` and the example's `check.json`.
`uv run python runs/check_environment.py runs/environments/bpi2019-demo --rebuild`
checks complete-build reproducibility plus replay and scheduling invariants.
`uv run python viewer.py` checks offline export. These are development checks,
not alternative user workflows. No unit-test framework was added.

Methods and source references: [discovery notes](.deepagents/skills/discover-operation/discovery-notes.md).
Development history: [PROJECT-LOG.jsonl](PROJECT-LOG.jsonl).
Example data: [Boudewijn van Dongen, BPI Challenge 2019](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1), CC BY 4.0.
Three.js is vendored under MIT; attribution and source are in `visual/vendor/`.

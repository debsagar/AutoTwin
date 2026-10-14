# AutoTwin — handoff

Updated 2026-10-14 (end of day). Read this first, then replay `PROJECT-LOG.jsonl` (project-log skill) and verify files before answering status questions.

## Working with the user
Solo AI research engineer; reads on a phone. Plain language, lead with the result, define terms, simple percentage tables. Say what you ran. Fix bugs or list them as open.
State a limitation once and move on: repeated caveats and approval-asking were called "pedantic… greatly hampering progress" (2026-10-14). Ask only before spending API money, outward-facing or destructive actions. "discuss" = no edits/runs. Don't create markdown unless asked. Use ponytail (minimal code).

## The goal
The manager's vision: a "world model" of a company built from its CRM/ERP/MES data — linked process graphs, external state, events sampled probabilistically or by role-based agents; RL environments as a side use. The user: "less to do with having a fully evaled agent and more with just capabilities." Validation is a quick gate, not the product. Apromore is the feature reference (`docs/apromore-reference.md`); the moat is automation with human checkpoints.

Plan (paint-company example): one simulation model per process, linked by IDs, handoffs (one model's output = next model's arrivals) and shared stock.
1. **Done.** Baseline an anchor process that matches history.
2. **In progress.** Generate production and stock linked to purchasing (OCEL 2.0).
3. Simulate the link: production uses stock → reorder → purchase start times fed into the purchasing model (Prosimos `run_simulation(..., fixed_arrival_times=...)`, seconds after `starting_at`).
4. Add sales in front (deals → sales orders → batches).

## Step 1 result: two checkpoints (`runs/checkpoints/`, git-ignored; each has `checkpoint.json`, `model/`, `scripts/`)
| Checkpoint | What | Test result |
|---|---|---|
| `p2p_dfg_v2` | Synthetic purchasing log (`data/benchmark/p2p_synthetic.xes`); **the purchasing anchor for Steps 2–3** | mean case length 87% of real, weekly volume 99%, step-order distance 0.046; median 62% (two-cluster durations) |
| `bpi17_dfg_delays_v1` | Real loan process (BPI 2017, `data/bpi2017/bpi2017.xes.gz` → `scripts/twin/convert17.py`); proof the method works on real data, not part of the chain | passed all 5 limits: median 101%, mean 111%, worst week 83%, step order 0.215 |

What made models work (published methods):
- **Extraneous delays** (waiting not caused by staff, e.g. customer/vendor): `scripts/twin/add_delays.py` (Chapela-Campa & Dumas; library `extraneous-activity-delays`, now a dependency). Without it BPI 2017 cases were ~500× too short.
- **Directly-follows chain** for step order (as ServiceMiner): `scripts/twin/dfg_model.py`.
- **Arrival correction**: `scripts/twin/rescale_arrivals.py` (see open bug 1).
- Train/test months of similar volume (published practice, Chapela-Campa et al. 2024, doi 10.1016/j.is.2024.102447).
- Score with `scripts/twin/pass_check.py <bundle> <evaluation dir>`.
Failed datasets and why: BPI 2019 (no start times → staff durations guessed far too long), Levy 2014 factory log (225 cases, non-commercial licence), BPI 2012 (passed narrowly; not kept).

## Step 2 so far
`linked_world.py` (run `--check` for the 5 asserts): P2P events untouched (13,290) → 603 deliveries bring cans/lids/labels into stock → 68 generated daily paint batches (201,000 units) consume them; stock never negative, ends at 0. Output `runs/linked/p2p_paint.jsonocel` (OCEL 2.0, read back with pm4py) + `assumptions.json` (every made-up number). Crude part: purchasing does not react to production yet — that is Step 3.

## Open issues
1. **Arrival rate bug (product):** PIX fits inter-arrival gaps in calendar time, Prosimos samples them in arrival-calendar-open time → simulated volume ~1.3× too high (outlier filter on, default) or ~0.65× (off). Workaround script only.
2. Delay step and chain are scripts, not in the product build; the product agent cannot build a passing model alone yet (deferred by the user).
3. pm4py conformance check errors ("not an easy sound net") on chain+delay models; scores unaffected.
4. Upstream PIX bugs noted, not fixed: `total_granules = 1440 % minutes` (should be `//`); fallback calendar filters by all resources.
5. pm4py is AGPL v3 (commercial use needs open-sourcing or a licence) — product decision pending.

## Repo notes
- `data/`, `runs/` are git-ignored: checkpoints and data don't travel with a clone or worktree. Agent worktrees start from `main`, not `dev/scenario-comparison`.
- Tool settings added 2026-10-14: `prepare_environment(..., selection='started')`; build `calendar_type` (`differentiated_by_resource` default | `differentiated_by_pool` | `undifferentiated`); vendor (NOT_SET) capacity = one slot per training case; empty simulated cases counted, not fatal.
- Old Stage 2 benchmark work is archived in `attic/2026-10-14-stage2-optimizer-benchmark/`.
- Web app checkouts: `/data/autotwin-web` (stable, port 8123), `/data/autotwin-web-dev` (port 8124) — frontend is with the user and Astra.
- Two processes from 2026-10-08 (`main.py` PID 3835902 at ~100% CPU, `langgraph dev` PID 3835950) look stuck; stopping them is the user's call.
- Secrets in `/data/autotwin/.env`: never read, print or commit.

## Next action
Step 3: give `linked_world.py` a reorder rule (stock below a level → purchase requisition), turn those times into fixed arrivals for the P2P checkpoint model, simulate, and check stock stays consistent end to end.

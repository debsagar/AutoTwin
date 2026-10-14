# AutoTwin — handoff

Updated 2026-10-14 (end of day). Read this first, then replay `PROJECT-LOG.jsonl` (project-log skill) and verify files before answering status questions.

## Working with the user
Solo AI research engineer; reads on a phone (give artifact links over paths). Plain language, lead with the result, define terms, simple tables. Say what you ran. Fix bugs or list them as open.
State a limitation once and move on: repeated caveats and approval-asking were called "pedantic… greatly hampering progress" (2026-10-14). Ask only before spending API money, outward-facing or destructive actions. "discuss" = no edits/runs. Don't create markdown unless asked. Use ponytail (minimal code). Don't overcomplicate: the user rejected generalising `linked_world.py` now — "once we demonstrate the end to end workflow we can use the traces to figure out what the agent needs".

## The goal
The manager's vision: a "world model" of a company built from its CRM/ERP/MES data — linked process graphs, external state, events sampled probabilistically or by role-based agents; RL environments as a side use. The user: "less to do with having a fully evaled agent and more with just capabilities." Validation is a quick gate, not the product. Apromore is the feature reference (`docs/apromore-reference.md`); the moat is automation with human checkpoints (HITL).

**The meta point (user, 2026-10-14):** the product agent runs on the same class of model that built Steps 1–5 here (Opus-class). If this assistant can do it with a shell and Python, so can the agent given the same tools and recipe. The dev traces (this log, transcripts) are the spec for the agent's skills.

Progress page for the manager (artifact, link-shared): https://claude.ai/artifact/Nm8sTjHfD2zAus9vZ1wLQV — vision scorecard, CRM/ERP/MES map, Steps 1–5, what-ifs, 15-question coverage. Source HTML is in the old session scratchpad; republish by passing the URL.

## Steps (paint-company example, all in `linked_world.py`; outputs in `runs/linked/`, git-ignored)
| Step | What | Run | Result |
|---|---|---|---|
| 1 | Purchasing simulation model from the synthetic P2P log | checkpoint `runs/checkpoints/p2p_dfg_v2` | mean case length 87% of real, weekly volume 99%, median 62% |
| 2 | Real P2P deliveries → stock → generated daily paint batches; written as OCEL 2.0 | `--check` (asserts only) / no flag (writes `p2p_paint.jsonocel`) | 13,290 P2P events untouched, 603 deliveries, 68 batches, 201,000 units, stock never negative |
| 3 | Closed loop: stock below reorder level → requisition → P2P model simulates it (Prosimos, fixed arrivals) → delivery or rejection | `--reorder` | 580 requisitions, 38.6% rejected (history 39.7%), lead mean 2.58 d (history 2.27), 120,000/120,000 units, 0 days short |
| 4 | Sales model (public Order Management log) creates customer orders → FIFO order book → factory → Step 3 loop | `--sales` | 320 orders, 100,320 units ordered, 100,200 made, 22 days short (all by the 3,000/day cap, 0 by stock), order-to-made mean 1.17 d |
| 5 | What-ifs: any setting overridden on the command line; first outside factor `external.supplier_lead_factor` | `--sales section.key=value ...` → `runs/linked/whatif/<settings>/` | table below |

Every run checks: stock never negative, deliveries counted once, start + received − used = final per material, units made + owed = ordered, orders filled in arrival order. Mutation tests (4 per step) were caught; reruns are identical (seed 7).

Step 5 what-ifs (40 weekdays, seed 7, one run each):
| Scenario | Made / ordered | Owed at end | Days short (by stock) | Order→made mean |
|---|---|---|---|---|
| baseline | 100,200 / 100,320 | 120 | 22 (0) | 1.17 d |
| `external.supplier_lead_factor=2` | 93,000 / 100,320 | 7,320 | 33 (11) | 3.56 d |
| `external.supplier_lead_factor=3` | 84,000 / 100,320 | 16,320 | 34 (12) | 5.56 d |
| factor 3 + `reorder.reorder_level=30000` | 100,200 / 100,320 | 120 | 22 (0) | 1.17 d |
| `sales.units_per_item=104` (+30% sales) | 116,312 / 130,416 | 14,104 | 36 (0) | 4.46 d |
| +30% sales + `max_batch_units=3900` | 130,260 / 130,416 | 156 | 24 (3) | 1.24 d |

## Assumptions (everything not learned from data)
All made-up numbers live in `ASSUMPTIONS` at the top of `linked_world.py` and are written as `assumptions.json` next to each output.
- **Materials:** P2P has no materials or quantities. Delivered PO *i* brings 1,000 units of `['can_5L','lid','label'][i % 3]`.
- **Recipe:** one paint unit = 1 can + 1 lid + 1 label. Factory = one batch per weekday 08:00–14:00, max 3,000 units (`max_batch_units`). Production is a rule, not a learned model — no MES data.
- **Reorder (Step 3):** flat demand 3,000/weekday; reorder when on hand + on order < 15,000 per material; initial stock 15,000; requisitions raised at 14:00; one 1,000-unit lot per requisition; 2023-03-06, 40 weekdays; seed 7. A rejected requisition stops counting as on order when its case ends, so the rule reorders.
- **Sales (Step 4):** only simulated *order times* are used (see open issue 1). Order size = items per order drawn from real training orders × 80 paint units per item; 500 cases simulated, orders after the horizon dropped; seed 7.
- **Outside factor (Step 5):** `supplier_lead_factor` stretches requisition→delivery time of delivered cases; the P2P trace keeps its own step times. "+30% sales" = bigger orders, not more orders.
- **Shortcut:** Prosimos runs once per day on that day's requisitions, so requisitions from different days don't compete for purchasing staff (queueing understated). Upgrade: iterate whole-horizon runs.
- **Data:** no real company data. Purchasing = synthetic log (Chapela-Campa & Dumas, `data/benchmark/p2p_synthetic.xes`); sales = simulated public OCEL 2.0 Order Management log (Knopp & van der Aalst, doi 10.5281/zenodo.18373906, CC-BY 4.0, `data/sales/om/order-management.sqlite`). CRM is missing; ERP = sales orders + stock + purchasing; MES = the assumed rule.

## Checkpoints (`runs/checkpoints/`, git-ignored; each has `checkpoint.json`, `model/`, `scripts/`)
| Checkpoint | What | Test result |
|---|---|---|
| `p2p_dfg_v2` | purchasing anchor (Steps 1–5) | mean 87%, weekly volume 99%, step-order distance 0.046; median 62% fails (two-cluster durations) |
| `sales_om_dfg_delays_v1` | sales model (Step 4); log → `scripts/twin/convert_om.py` → XES, built with `scripts/twin/run_om.py` | 5 seeds: median 0.896×, mean 1.089×, worst week mean 1.005× but seed SD 0.143 > 0.10 → fail |
| `bpi17_dfg_delays_v1` | real loan log (BPI 2017); proof the method works on real data, not in the chain | passed all 5 limits |

Recipe that made models work (scripts in `scripts/twin/`, not in the product image):
- **Extraneous delays** (waiting not caused by staff): `add_delays.py` (Chapela-Campa & Dumas). Falls back to `train_fitted.csv` estimated starts when the log has completion times only.
- **Directly-follows chain** for step order: `dfg_model.py`. **Arrival correction:** `rescale_arrivals.py`. **Scoring:** `pass_check.py <bundle> <evaluation dir>`.
- Prosimos `run_simulation(fixed_arrival_times=...)` returns before flushing its log (empty CSV): call `SimDiffSetup` + `run_simpy_simulation` and `force_write()` yourself (done in `reorder()`).

Validation rigour from here (review, 2026-10-14): ~43% of log events went to data/fitting/validation, ~5% to linking. Keep one plausibility gate per model (median and mean within ~±30%, no empty cases) plus the cheap structural checks (balances, mutation tests, per-case step counts). No new datasets unless a step is blocked; synthetic data is fine for linked-world work if every invented number is labelled.

## Operator questions
15 real operator questions with sources: https://claude.ai/artifact/9wh4b5QTuWS9JeqjD6vyUL. Assessment (not yet answered): 4 answerable now on data on disk (Q3, 4, 5 BPI 2017; Q8 BPI 2019), 4 after downloading free BPI 2020 (Q1, 2, 6, 7), 3 fit the what-if machinery but lack data (Q10, 14, 15), 4 need data we don't have (Q9, 11, 12, 13). 8 of 15 need only history analysis, no simulation.

## Open issues
1. **Sales model loses once-per-order steps:** "confirm order" 0 times in 136/363 simulated test orders, 2–7 times in 87. Only order times are used.
2. **Sales weekend orders:** 16% simulated vs 5% real; Monday piles over the batch cap (part of the baseline's 22 short days).
3. **Steps 3–5 write CSVs, not OCEL** (`orders.csv`, `requisitions.csv`, `stock_ledger.csv`, `p2p_simulated.csv`); links between orders, batches and requisitions live only in code. Step 2's `event()` helper can be reused. OCEL is also the intended input format for a real company's CRM/ERP/MES export.
4. **The product agent can't run any of this:** `Dockerfile` copies only the core modules (not `scripts/` or `linked_world.py`), no skill describes the recipe, and `main.py:35` defaults to `openrouter:openai/gpt-5.6-luna`, not Claude.
5. **Arrival rate bug (product):** PIX fits inter-arrival gaps in calendar time, Prosimos samples them in arrival-calendar-open time → volume ~1.3× too high (outlier filter on) or ~0.65× (off). Workaround script only.
6. pm4py conformance check errors ("not an easy sound net") on chain+delay models; scores unaffected.
7. Upstream PIX bugs noted, not fixed: `total_granules = 1440 % minutes` (should be `//`); fallback calendar filters by all resources.
8. pm4py is AGPL v3 — product decision pending.
9. NumPy "generic timedelta" DeprecationWarnings at `linked_world.py` lines 151/187/212 come from pandas internals; harmless for now.

## Repo notes
- `data/`, `runs/` are git-ignored and exist only in `/data/autotwin`. Agent worktrees start from `main`, not `dev/scenario-comparison`.
- **Branches:** the only working line is `dev/scenario-comparison` (main is an ancestor, 4 commits behind → fast-forward). Only 3 worktrees exist: this one plus the two web checkouts (`dev/web-mvp`, `dev/web-insights`, frontend line, diverged; merge with Astra later). The other 14 local branches (`conversation-workspaces`, `dev/calibration-*`, `dev/log-validation`, `dev/stage1-*`, `dev/structure-repair`, `dev/temporal-*`, `feat/native-stage1`, `fix/termination-boundary`) are Oct 9–12 subagent leftovers: their code is already in this branch (checked 2026-10-14: 0 unapplied patches or every added line present except lines later rewritten). Local only, not on GitHub; safe to delete with the user's OK.
- Also downloaded, unused: `data/sales/o2c/3_o2c.zip`. Old checkpoint `p2p_heuristics_v1` superseded by `p2p_dfg_v2`.
- Old Stage 2 benchmark work is archived in `attic/2026-10-14-stage2-optimizer-benchmark/`.
- Web app checkouts: `/data/autotwin-web` (port 8123), `/data/autotwin-web-dev` (port 8124) — frontend is with the user and Astra.
- Two processes from 2026-10-08 (`main.py` PID 3835902 at ~97% CPU, `langgraph dev` PID 3835950) still running on 2026-10-14; stopping them is the user's call.
- Secrets in `/data/autotwin/.env`: never read, print or commit.

## Next actions (user's order: what-ifs first — done)
1. **Agent reproduces the chain:** mount `scripts/` and `linked_world.py` read-only into the agent sandbox, add one skill that turns this log into a recipe (steps, assumptions, the Prosimos workaround, the checks), switch the agent to Claude, ask it to redo Step 3 from the skill and match 580 requisitions / 0 days short (seed 7). Its failures show which tools are missing. Costs API money: confirm first.
2. **Plain-language what-if with HITL:** user asks "what if suppliers take 3× as long", agent proposes the setting change, person confirms, agent runs `--sales ...` and explains the table.
3. Write each run as one OCEL file (open issue 3); more outside factors (seasonality, holidays, prices); a role-playing agent (buyer/planner); a real company's records.

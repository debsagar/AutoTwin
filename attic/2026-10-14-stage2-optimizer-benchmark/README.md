# Stage 2 benchmark from published process optimisers (Optimos, bpm-r-opt)

**Retired:** 2026-10-14
**Lived:** 2026-10-13 to 2026-10-14
**Replaced by:** nothing yet. Focus moved to the Stage 1 "world model" idea (what company data we start from and what we do to it), which restarts as an idea with no code.

## The idea, in the words it was proposed in
The user wanted an existing benchmark with established tasks and grading for Stage 2 (the agent proposes and simulates process changes): "not another custom benchmark or months of infrastructure work." Later: "I dont want to commit to a benchmark which doesnt give us any idea of how our agent is." So we checked whether published staffing-optimiser benchmarks leave enough gap between dumb and good strategies to rank an agent.

## What was built
- `optimos-spike/optimos-grade-spike.py`: scores an external timetable through original Optimos (roptimus-prime 754a65c), using RosterManager + PoolInfo + perform_simulations.
- `optimos-spike/hr_pub.py`: helper for reading published bpm-r-opt allocations.
- `bpmropt-repro/`: written by a Sonnet subagent. Re-simulates published bpm-r-opt (5d52577) allocations with the repo's own Java simulator (`evalalloc.py`, `runproc.sh`, `sample.py`, `score.py`). Results are in `res_*.jsonl` and logs in `log_*.txt`.
- `headroom/policies.py`: two random baselines on a 20-evaluation budget.
  - `blind`: every pool size drawn uniformly from 1..cap. It ignores results.
  - `one_pool`: take a random point from the current best set, then shrink or grow one random pool. cap = the sum of the starting pool sizes.
- `headroom/worker.py`: evaluates the published front, the first 20 allocations of HC-STRICT and HC-FLEX, and the random policies per seed.
- `headroom/run2.sh PROC N_SIMS [SEEDS]`: launches the workers.
- `headroom/score.py`: produces the percentage table. Its output is saved in `headroom/score_output.txt`.

## What it produced
Optimos spike on loan_sc_lu (PROJECT-LOG.jsonl, 2026-10-13T09:12):
- The shipped start scored cost 22791 / cycle time 33094 s.
- Removing one shift scored 24692 / 60221 s.
- "Everyone 24/7" was rejected for all 20 resources.
- Only 6 of the 10 shipped starting timetables pass Optimos's own checks.

bpm-r-opt reproduction (PROJECT-LOG.jsonl, 2026-10-13T09:32):
- bpi_challenge_2012: cost −1.5% to +0.2%, cycle time within 0.8%.
- purchasing_example: cycle time within 4%, cost up to +9.3% on two rows.
- production: cost repeats ranged 1.22M–1.38M against 1.401M published.

Headroom check, 20 evaluations per strategy (`headroom/score_output.txt`). Column meanings:
- cost saved: with time no worse.
- time saved: with cost no higher.
- area: trade-off area as a % of the published best set.

purchasing_example (start cost 587635, time 183421):

| strategy | runs | cost saved | time saved | area |
|---|---|---|---|---|
| published best set | 1 | 75% | 17% | 100% |
| HC strict, first 20 | 1 | 37% | 9% | 42% |
| HC flex, first 20 | 1 | 41% | 8% | 46% |
| random one-pool change | 3 | 28% (17–35) | 14% (9–17) | 33% (23–38) |
| blind random | 4 | 0% (0–0) | 1% (0–2) | 0% (0–1) |

bpi_challenge_2012 (start cost 598245, time 3305):

| strategy | runs | cost saved | time saved | area |
|---|---|---|---|---|
| published best set | 1 | 87% | 0% | 100% |
| HC strict, first 20 | 1 | 28% | 0% | 51% |
| HC flex, first 20 | 1 | 28% | 1% | 51% |
| random one-pool change | 3 | 43% (26–72) | 0% (0–1) | 49% (29–82) |
| blind random | 3 | 7% (0–20) | 0% (0–1) | 28% (1–61) |

## Why it was retired
On 2026-10-14 the user said: "Store and archive thread 1, we will focus on thread 2 (we will start this from scratch again, not code only the idea)." The manager's world-model / Stage 1 data question took priority. The benchmark was not rejected on its merits; no decision was made between bpm-r-opt and the Optimos suite.

## World beliefs
- [kept] No public benchmark scores an LLM agent on simulation-based process improvement.
    how we know: two literature searches (PROJECT-LOG.jsonl 2026-10-13T09:19, 09:03)
    where it came from: I inferred it from the searches
    would be wrong if: a paper or repo turns up that grades an LLM agent's process changes with a simulator
    scope: searches up to 2026-10-13
- [kept] On bpm-r-opt purchasing_example, a 20-try budget separates strategies: blind guessing 0%, local search 33–46%, best known 100% trade-off area.
    how we know: headroom/score_output.txt
    where it came from: measured
    would be wrong if: the 2 missing random runs, or more seeds, close the gap between blind and one-pool
    scope: purchasing_example only, repo's Java simulator, 5 sims per evaluation
- [kept] On bpm-r-opt BPI 2012, no strategy reduces cycle time, and run-to-run spread is wide (one-pool area 29–82%). It cannot tell a good agent from a lucky one at 20 tries.
    how we know: headroom/score_output.txt
    where it came from: measured
    would be wrong if: more simulations per evaluation shrink the spread a lot
    scope: bpi_challenge_2012, 3 sims per evaluation, 3 seeds
- [kept] Every resource pool in bpm-r-opt and original Optimos costs 1 per hour. Cost is headcount × simulated hours, not real wages.
    how we know: PROJECT-LOG.jsonl 2026-10-13T09:12 and 09:32
    where it came from: read from code by me and the subagent
    would be wrong if: a cost_per_hour other than 1 is found in the shipped inputs
    scope: roptimus-prime 754a65c, bpm-r-opt 5d52577
- [kept] Published bpm-r-opt results do not transfer to Prosimos, because the Prosimos models in roptimus-prime were re-discovered with different pools (21 vs 6 for purchasing).
    how we know: PROJECT-LOG.jsonl 2026-10-13T09:32
    where it came from: subagent inspection
    would be wrong if: a matching Prosimos model with the same pools is found
    scope: purchasing_example
- [open] bpm-r-opt is usable as an AutoTwin Stage 2 benchmark behind a Python wrapper around the Java simulator (estimated 1–2 days).
    how we know: subagent estimate only; 5 of 8 processes are unchecked
    where it came from: subagent recommendation
    would be wrong if: the remaining processes reproduce badly, or the agent cannot express headcount-only moves
    scope: untested

## Method beliefs
- [kept] Before committing to a benchmark, measure the gap between a blind strategy and the best known result. A benchmark where blind guessing scores near the top cannot rank an agent.
    how we know: BPI 2012 vs purchasing contrast in headroom/score_output.txt
    where it came from: the user asked for it ("I dont want to commit to a benchmark which doesnt give us any idea of how our agent is")
    would be wrong if: n/a; this is a method choice
    scope: Stage 2 benchmark selection
- [kept] Optimisation benchmarks measure only improvement. Diagnosis, honest claims and consistency need separate checks: re-simulate the agent's claims, repeat runs, and check the named bottleneck.
    how we know: argued on 2026-10-13; not measured
    where it came from: I inferred it
    would be wrong if: n/a; this is a scope statement about what the benchmarks grade
    scope: Optimos-family benchmarks
- [kept] Result tables for the user are plain percentages with one sentence per column.
    how we know: the user said "i dont get the table" on 2026-10-13
    where it came from: user feedback
    would be wrong if: n/a
    scope: all reports

## Assumptions we made without being asked
- "Trade-off area" (normalised hypervolume in the box cost ≤ start, time ≤ 1.5×start) is my own measure, not the paper's. The paper's hyperarea saturates at 0.99996–1.0. The cost: the numbers are not comparable to anything published.
- Floor at 0 for "saved". Noise pushed the start over tolerance and blind random first scored −38%. The cost: tiny negative effects are hidden.
- 3 simulations per evaluation for BPI 2012 (instead of 5) to save time on an overloaded VM. The cost: wider spread on BPI.

## How to run it again
The heavy dependencies are not archived. The JDK 8, the bpm-r-opt clone (github.com/orlenyslp/bpm-r-opt @ 5d52577) and the roptimus-prime venv lived in the session scratchpad and will be gone.
1. Clone bpm-r-opt at 5d52577 into `work/`. Put a JDK 8 on PATH.
2. Edit the `S=` / `C=` paths at the top of `headroom/run2.sh` and `bpmropt-repro/runproc.sh` to point at your copy.
3. Run `./headroom/run2.sh purchasing_example 5 5`, then `python3 headroom/score.py purchasing_example`.

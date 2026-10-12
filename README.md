# AutoTwin

**Give AutoTwin a process event log. Get a process simulation, a report on how well it matches the log, and evidence for what to investigate next.**

Use it from the terminal: ask a question, let the agent inspect the data and run experiments, then review its results. You can follow its work and ask it to change direction.

## What goes in, what comes out

**Input:** an XES event log. Each event identifies a case (such as a purchase order), an activity, and when it finished. Recorded start times and resource identities help reconstruct timing and workload. Other file formats need conversion first.

**Output:**

- An executable process model: a BPMN diagram and simulation parameters.
- A comparison with recorded cases: process paths, completion times, arrival patterns, and differences across simulation runs.
- An interactive HTML replay showing cases moving through activities, with timing and evaluation results.
- A written report explaining the findings, assumptions, and remaining gaps.

The first stage reconstructs and checks the process. The next stage uses that model to investigate changes. Costs, service targets, staffing rules, and what can actually change need to come from you; the log does not establish them.

## Worked example: purchasing through invoice payment

We used a [published synthetic procurement log](https://zenodo.org/records/10435849): **1,000 cases, 13,290 events, and 24 activities**, covering requisitions, quotations, delivery, and payment. This is a generated research dataset, not a company's production history.

AutoTwin built a simulation, compared it with later recorded cases, and kept a frozen model for follow-up analysis. In the five-run final assessment, the mean cycle-time ratio was about **1.22×** the recorded value and cycle-time distance averaged **9.55 hours**. No false early endings were observed in those checks. Timing differences remained, so this is a development baseline, not a validated replica of a business.

We then asked it to **diagnose the baseline and propose one improvement without removing approvals**. It wrote and ran an analysis against the saved evidence:

| Finding in the validation data | Result |
|---|---:|
| Cases ending in invoice payment | 118 of 221 |
| Mean time to payment for those cases | 61.76 hours |
| Mean time across all cases, including early endings | 34.95 hours |
| Delivery and quotation-comparison intervals combined | 63.5% of paid-case time |

The distinction matters: early-ending cases make the overall average look faster. The activity intervals also include non-working hours; they are not all removable work.

**Proposed experiment:** use structured supplier quotes or a comparison template, modeled as a 20% reduction in quotation-comparison working duration. Keep approvals, staffing, schedules, and routing unchanged.

**Result so far:** diagnosis and an experiment proposal. The 20% saving is an assumption to test, not an achieved improvement. No intervention was run in this example.

## Clone and run

You need **Python 3.12**, [uv](https://docs.astral.sh/uv/getting-started/installation/), a running Docker engine, and an OpenRouter API key. Model calls incur API charges.

```sh
git clone https://github.com/debsagar/AutoTwin.git
cd AutoTwin
uv sync --frozen
export OPENROUTER_API_KEY="your-key"
docker build -t autotwin-worker:local .
uv run python main.py
```

The default model is `openrouter:openai/gpt-5.6-luna`. To choose another available model, append `--model openrouter:<model-id>` to the launch command.

### Try the example dataset

Before opening the CLI, download the published sample and convert it to XES:

```sh
uv run python scripts/fetch_example.py
uv run python main.py
```

Inside the CLI, enter:

```text
/skill:stage1 data/benchmark/p2p_synthetic.xes — reconstruct the process, validate against later cases, compare at most two evidence-backed revisions, and export the replay and report.
```

The download script verifies the archive and preserves case IDs, activities, resources, and start/end timestamps. It does not download the reference model into the agent's workspace.

This reproduces the **workflow on the same input**, not the exact saved conversation or scores: the agent chooses its analysis and model settings. Historical runs and checkpoints are not included in the repository.

### Read the results and continue

Each conversation saves its work under `runs/workspaces/<thread-id>/`. Start with `report.md`; model files and `environment.html` live under `environments/<candidate>/`. Open the HTML in a browser. On a remote VM, download it first; it works offline.

Resume your latest interactive conversation with:

```sh
uv run python main.py -r
```

Once a baseline is ready, ask in that conversation:

```text
Diagnose this baseline and propose one improvement experiment. Explain the evidence and the business inputs needed before running it.
```

Inputs remain read-only; generated files stay in the conversation's workspace. Rebuild the Docker image after changing tools or skills. Data, runs, local sessions, and credentials are excluded from Git.

For the next stage's methodology, see [the process-improvement workflow](docs/stage2-workflow.md).

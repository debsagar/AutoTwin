# Apromore reference for AutoTwin

Read from the Apromore user guide, version 10.6, on 2026-10-13. Every statement in
sections 2–9 comes from the page linked beside it. Where the guide is silent, this
file says "not documented" rather than guessing.

## 1. How to use this file

This is the working brief for the AutoTwin frontend. Sections 2–9 describe Apromore.
Sections 10–15 describe AutoTwin: the product direction, what exists, the interface
principles, the mockups and the open questions.

Owner direction (2026-10-13, recorded in `PROJECT-LOG.jsonl`):

- AutoTwin should **copy what Apromore produces**: the same inputs, measures, tables
  and reports. Do not design for novelty.
- AutoTwin delivers it differently: **an automated agent run with human
  checkpoints**, not a set of manual screens. The owner calls this the moat.
- Apromore's interface is considered too complicated. Copy its outputs, not its
  click paths.
- The product will run on a Sonnet- or Opus-class model. Guide and guard the agent;
  do not script it.

Guide root: https://documentation.apromore.org/index.html. Below, `[path]` means
`https://documentation.apromore.org/<path>`.

## 2. The user journey Apromore documents

From the quick start `[quickstart/index.html]`:

1. Create a project folder.
2. Upload a file; confirm the column mapping in the Log Importer.
3. Open the log in Process Discoverer: a process map with sliders and overlays.
4. Filter (example: cases longer than 14 days; cases containing one activity).
5. Open a dashboard: default tabs Overview, Activity, Resources.

Continuing into simulation `[simulation/…]`:

6. Switch the map to BPMN, save it with "Include simulation parameters".
7. Simulate; a simulated log is saved beside the model.
8. Edit the scenario, simulate again, select both simulated logs, open one dashboard.
9. Generate an automation assessment report, or download the dashboard view as PDF.

## 3. Input

### 3.1 File upload `[theapromoreportal/uploadafile.html]`

- Formats: CSV, Parquet, XLSX (exactly one sheet), optionally zipped or gzipped.
  CSV delimiters: comma, semicolon, tab.
- Stored internally as XES.
- Each column gets a data type (Integer, Real, String, Timestamp) and a tag:

| Tag | Columns allowed | Mandatory |
|---|---|---|
| Case ID | 1 | yes |
| Activity | 1 | yes |
| End Timestamp | 1 | yes |
| Start Timestamp | 1 | no |
| Resource | 1 | no |
| Role | 1 | no; required for cost |
| Case Attribute (constant per case) | many | no |
| Event Attribute (changes within a case) | many | no |
| Event Attribute (Perspective) | many | no; usable as a map perspective |
| Ignore | many | no |

- The importer guesses the Case ID and Activity columns and the timestamp format;
  the user checks and overrides.
- Per-column "Incognito" toggle encrypts values.
- **Missing start times:** an option estimates each start as the later of (a) the end
  of the previous activity in the case and (b) the time the resource finished its
  previous activity. Requires a Resource column. The guide warns it is unreliable
  when resources appear sporadically or multitask.
- **Bad rows:** the import still succeeds. The log shows a warning icon; the user can
  list invalid entries, download the first 1,000 errored rows, or discard the log.
- Since release 10.5, uploads come from the local machine only (web and cloud
  uploads were removed).
- Not documented: file size limits, reusable mapping templates.

### 3.2 Data pipelines `[datapipelines/createdatapipeline.html]`

A pipeline builds one event log from several tables.

- Sources: local CSV or Parquet, workspace files, other pipelines' outputs, an AWS S3
  bucket (single files or folders of micro-batches). MySQL and PostgreSQL extractors
  were retired in release 10.3.
- Stages, in order: Extract, Merge, Transform, Load.
- Merge: inner, full, left, right join; append (same process, consecutive periods);
  parent-child append (link a parent process to child processes through a shared key).
- Transform: choose columns; build new columns with IF/ELSE rules using value, delete
  row, concatenation, find and replace, regex extract, trim, arithmetic, max/min/average.
- Scheduling `[datapipelines/scheduledatapipeline.html]`: hourly, daily, weekly or
  monthly. Loading strategy: new log each run, append (with an optional retention
  window), or overwrite. A schema change fails the run unless "create new log when the
  schema is altered" is ticked.

### 3.3 Connectors `[connectors/index.html]`

One connector is listed: MuleSoft Anypoint. It authenticates and posts a finished
event log into Apromore. It does not build the log. No ERP or CRM connector is
documented in the user guide.

## 4. Understanding the process

### 4.1 Process Discoverer `[discovery/discovermodel.html]`

- Default view: a map where nodes are activities and arcs show what follows what.
- Abstraction sliders: nodes (default 100%), arcs (default 10%), and, in BPMN view,
  parallelism. Abstraction can be by case frequency, average frequency, or average,
  median or max duration.
- Display caps: 250 nodes, 1,000 arcs.
- Statistics bar: cases; case variants; variance ratio (1 − variants ÷ cases);
  activity instances; activities; case duration average, min, max; case cost average,
  min, max (N/A without a cost centre); log timeframe.
- Overlays: Frequency, Duration, Cost, each with total, mean or average, median, min,
  max, plus rework variants (total rework, rework duration, rework cost). Two metrics
  can be shown at once.
- Duration is end minus start. If the log has only end times, activities appear
  instantaneous and all time sits on the arcs.
- Perspectives: Activity, Resource, Role, and any column tagged as a perspective.
  Resource and Role perspectives show handovers.
- Inspectors: Case (with a per-case timeline, exportable), Case Variant (ID, activity
  instances, average duration, cases, percentage), Activity (predecessors and
  successors with frequency and duration).
- BPMN toggle redraws the map as a BPMN model. Save offers "Include simulation parameters".
- Exports: PDF, PNG, JSON.

### 4.2 Filters `[logfilters/filtercriteria.html]`

Case-level (keep or remove whole cases):

| Filter | Selects by |
|---|---|
| Attribute | attribute values, numeric ranges, any/all |
| Case variant | variant rank range |
| Case ID | ID |
| Timeframe | contained in, active in, start in, end in a period; relative periods |
| Performance | case duration, case length, processing time, waiting time, case utilization, node duration, arc duration; percentile option |
| Path | one activity directly or eventually follows another, with optional time bound |
| Rework | repeats: self-loop, short loop, indirect loop, with min and max counts |
| Blocks | AND/OR combinations of the above |

Event-level (keep parts of cases): Attribute, Timeframe, Frequency, Performance,
Path (directly follows or precedes), Between (events between two chosen nodes).

### 4.3 Variant comparison `[discovery/comparevariants.html]`

Two groups of cases (example: under versus over four weeks) on one map. Grey nodes
appear in both; blue and red nodes appear in only one. Case counts, activity counts
and activity instances are shown per group. Two logs at a time.

### 4.4 Conformance and animation `[conformancechecking/…]`

- Conformance: a log against a BPMN model. Left panel lists variants; clicking one
  overlays its path on the model with deviations coloured. Sort by percentage, cases,
  alignment, average duration, activity instances. No fitness score is described.
- Animation: each case is a token moving on the model, coloured by source log.
  Play, pause, speed, rewind. Several logs can play on one model.

## 5. Business inputs the log cannot supply

### 5.1 Calendars `[costskpisandcalendars/managecalendars.html]`

- Presets: 9–5 five business days; 24 h five business days; 24 h seven days. Or custom
  hours per day.
- Time zone. Public holidays by year, country and state. Custom holidays.
- Option "Apply calendar to waiting times": when on, off-hours are excluded from
  waiting time and case duration. Example: end 16:55, next start 09:05 the next
  business day gives 10 minutes of waiting.

### 5.2 Costs `[costskpisandcalendars/managecostcenters.html]`

- Requires a Role column.
- Per role: cost per hour and a calendar. One currency for the cost centre.
- Cost follows calendar-adjusted processing time. Example: a task from Thursday 16:50
  to Friday 09:10 is 20 minutes for a 9–5 role and 16 h 20 min for a 24/7 role.
- Cost then appears as a map overlay, a filter measure (case cost), and a chart measure.

### 5.3 KPIs and metrics `[kpisandmetrics/…]`

- A KPI tracks a service target. It has a name, a population (which cases), a
  condition (example: case duration is less than or equal to N), and a target.
- Target forms: comparison operator and number; min–max range; mean plus tolerance
  percentage; custom ranges with colours.
- Status: fulfilled (green), violated (red), optional amber band.
- Case-level KPIs count cases meeting a condition. Process-level KPIs test a metric
  against a target.
- Custom metric: a formula built from blocks (predefined metric, attribute, operator,
  value, variable). Example: cases ÷ total unique resources.
- Breach notifications fire when the log updates and the status changes.

### 5.4 Root cause analysis `[kpisandmetrics/performrootcauseanalysis.html]`

- Started from a KPI. Scope: all attributes and statistics, or a chosen subset
  (case attributes, activity frequency, resource frequency, start date, end date,
  longest activity).
- For each condition it reports violation rate, inverse violation rate, risk increase
  (difference), risk ratio (quotient), and sub-population size.
- Shown as cards with a sentence, for example: "violation rate is 7% when Invoice
  Amount is 50K or more, versus 3% otherwise".
- Default: only sub-populations above 10%, sorted by risk increase. Decision tree
  mining picks the findings.
- A condition that lowers risk is reported as a positive finding.

## 6. Measures

Definitions from `[performancedashboard/addchartstodashboard.html]` and
`[litedashboard/addakpiormetric.html]`. These are the terms operators see.

| Measure | Definition |
|---|---|
| Case duration | Start to end of a case |
| Case length | Number of activity instances in a case |
| Case cost | Total cost of a case; needs a cost centre |
| Processing time | Time someone was actively working; average, max or total |
| Waiting time | Time nobody was working; average, max or total |
| Case utilization | Processing time ÷ case duration; needs start and end times |
| Role utilization | Share of a role's working hours spent on activities |
| Work in progress | Cases not yet exited within the interval |
| Throughput | Cases that exited within the interval |
| Cases in the queue | Cases waiting after a chosen activity |
| Time in the queue | Total, min, median, average or max queueing time |
| Rework | Repeats of an activity within a case; also rework duration and rework cost |
| Variability ratio | Case variants ÷ cases |
| Handover metrics | Frequency, duration and rework between activities, resources or roles |

## 7. Dashboards and reports

### 7.1 Default dashboard `[performancedashboard/viewdashboards.html]`

- **Overview:** tiles for activity instances, active cases over time, case variants,
  case duration, log timeframe. Charts: activity instances over time, work in
  progress, case variants, case duration. Tables: cases; case variants.
- **Activities:** tiles for activities, average activity frequency, average activity
  duration. Charts of per-activity frequency and duration.
- **Resources:** case frequency, total frequency, average, min and max duration per resource.

### 7.2 Tables `[performancedashboard/addtablestodashboard.html]`

| Table | Columns |
|---|---|
| Cases | case ID, activity instances, start time, end time, duration |
| Case variants | variant ID, activity instances, cases, min, median, average, max duration |
| Case attribute overview | value, cases, frequency %, min, average, max duration |
| Event attribute overview | aggregate statistics per activity, role or resource |
| First touch statistics | per first-touch resource and activity: cases, variants, variability ratio, case duration and first-to-last duration statistics |

### 7.3 Charts

Line, spline, column, area, bar, scatter, pie, polar variants, heat map, tree map,
bubble. Trend charts take up to three measures. Time bins from hours to years.

### 7.4 Comparison and export `[performancedashboard/additionaldashboardfunctionality.html]`

- Selecting two or more logs and opening a dashboard shows them together; a "Split"
  option separates them per chart.
- Any view downloads as "PDF report (from this view)". Charts export as PNG, JPEG,
  PDF, SVG, CSV, XLS.

## 8. Simulation

### 8.1 Discovery from the log `[simulation/discoversimulationscenariofromlog.html]`

Discovered: case start and count; inter-arrival distribution; per-task duration
distribution (normal, exponential, fixed, uniform); probability per gateway branch;
timetables if the log defines them; case attributes with type and distribution;
roles, the tasks each performed, headcount per role, unit cost per role if a cost
centre exists.

- Headcount = total work time of the role ÷ log time span, rounded up. Example: 180
  minutes of work in a 120-minute log gives 2.
- Only case attributes are discovered; event attributes are added by hand.
- Not documented: any comparison of the simulated log with the original log. Release
  10.5 says the Copilot builds a "calibrated baseline model"; the method is not described.

### 8.2 Scenario parameters `[simulation/editsimulationscenerio.html]`

| Tab | Parameters |
|---|---|
| General | start date and time; time zone; currency; inter-arrival time (fixed, normal, exponential, uniform, triangular, log-normal, gamma) tied to an arrival timetable, several allowed; run by duration or by case count; option to finish open cases |
| General, advanced | cases in queue at start; cases excluded at start and end (warm-up, cool-down); max branching probability error %; deterministic mode |
| Attributes | categorical (probabilities summing to 100%) or numerical (distribution); tasks may update them |
| Gateways | per branch a probability with an optional max count per case, or a condition on attributes |
| Tasks | role pools; processing-time distribution (waiting excluded); fixed cost; external delay |
| Roles | single role or role group; timetable; number of resources; cost per hour; performance handicap % (10% turns 15 min into 16.5 min); max overtime in minutes |
| Timetables | named calendars of timeslots; default Monday–Friday 09:00–17:00 |
| Events | timer durations |
| Transition time | delay per arc, with distribution |
| Priorities | integer 1–10 assigned by attribute rules |

### 8.3 Running and comparing `[simulation/simulateprocess.html]`

- Output is a simulated log. Missing mandatory fields are listed as errors.
- Dashboard on a simulated log shows: case duration, case duration within the
  timetable, case waiting time, cycle time, waiting time, cost.
- Comparison: change a parameter (example: add one Senior Engineer), save a second
  simulated log, select both, open one dashboard.

### 8.4 Limits `[simulation/upperlimitsforsimulation.html]`

| Limit | Value | Usual cause |
|---|---|---|
| BPMN elements processed | 2,000,000 | rework loop that almost never exits |
| Simulated length | 5 years | arrivals faster than resources can process |
| Period generating cases | 1,000 days | long inter-arrival time with many cases |
| Tasks in one resource queue | 10,000 | too few resources for the arrival rate |
| Cases per scenario | 20,000 | |
| Resources per role | 1,000 | |
| Roles | 1,000 | |

### 8.5 Automation assessment report `[performancedashboard/generatepaarreport.html]`

- Inputs: as-is model and simulated log; what-if model and simulated log, where the
  automated tasks are assigned to a "bot" resource.
- Per selected task: change in resource cost, average task duration, average task
  cost, average monthly frequency. Plus a generated description of the benefits.
- Downloads as a Word file.

## 9. Chat assistants (Copilot)

All are off by default, enabled on request, and capped at 20 prompts a day.

| Assistant | Does | Documented limits |
|---|---|---|
| Discovery `[discovery/copilotforprocessdiscovery.html]` | Answers questions about the open log: most frequent activity, bottlenecks, role capacity, whether regions meet a stated target. Creates filters in the background and compares against the unfiltered log. Highlights named activities on the map. | Filters only on case attributes and timeframes; at most 10 filters per prompt; attributes with at most 50 distinct values |
| KPIs `[kpisandmetrics/copilotforkpis.html]` | Lists KPIs and whether each is met; runs root cause analysis; splits by attribute or period first | Case-level KPIs only; one KPI per root cause query |
| Simulation `[simulation/copilotforsimulation.html]` | Runs what-ifs in the background against an attached baseline labelled "Before". Examples: add 2 FTEs to a role; fully or 60% automate an activity; demand up 20%; several changes in one question; compare two scenarios | Without an attached model it uses an uncalibrated baseline |

Release notes `[releasenotes/releasenotes.html]`: assistant introduced in 10.1 (June
2024); builds the baseline simulation model itself from 10.5 (October 2025); moved to
Claude Sonnet 4.5 in 10.5.1–10.5.2 (February 2026); answers goal questions such as a
roadmap to improve on-time performance or reduce operating costs from 10.6 (August 2026).

## 10. Product shape

A person uploads a table of events and starts a run. The agent goes through the
Apromore journey on its own and stops only where a human knows something the data
does not, or has to take responsibility for a choice.

Proposed checkpoints. The owner has not yet approved this list. The agent proposes;
the person approves, edits, or rejects with a reason.

| Step | Agent does | Checkpoint |
|---|---|---|
| 1 Intake | read file, guess columns, convert, list bad rows | confirm mapping |
| 2 Understand | map, statistics, variants, bottlenecks | confirm scope; answer odd findings |
| 3 Business inputs | propose calendars and roles | enter target, cost per role, what cannot change |
| 4 Model of today | build and check the simulation | accept the model |
| 5 Diagnose | root causes, proposed changes | pick or edit the changes to test |
| 6 Compare | run each change against today, write report | sign off |

A run may also go straight through with every proposal auto-approved. All four
Stage 2 runs so far did this; the checkpoints then become stated assumptions.

Packaging, as researched on 2026-10-13 and not yet built:

- The CLI already runs the agent behind a local `langgraph dev` server and talks to
  it as a client. A web frontend is the same arrangement with a different client.
- The tools are plain Python functions, the sandbox routing is a LangChain
  middleware, the skills are files. `langgraph-cli` and `langgraph-api` are installed.
- LangChain documents a React hook, `useStream` from `@langchain/react`, exposing
  messages, todos, subagents, tool calls and interrupts, and publishes a Next.js app,
  `langchain-ai/deep-agents-ui`.
- Open risk: `install_runtime_policy` in `process_mining.py` patches CLI internals for
  skills, subagent sandboxing and approvals. Re-expressing these outside the CLI may
  change agent behaviour. Not tested.
- The Docker worker needs a local Docker engine, so the first host is a single VM.

## 11. What exists in AutoTwin

State of the repository on 2026-10-13 at commit `18c2151`.

### 11.1 Capability against Apromore

| Apromore capability | AutoTwin has | Missing |
|---|---|---|
| CSV, XLSX, Parquet upload stored as XES (3.1) | XES reading only | Conversion to XES |
| Guessed column mapping, error report (3.1) | Nothing | Mapping proposal and bad-row report |
| Start-time estimation (3.1) | `estimate_missing_starts` on `build_environment` | Surfacing it at intake |
| Map, statistics bar, inspectors (4.1) | `discover_process`, `inspect_log_scope` return the numbers | A rendered map with overlays; tables |
| Calendars (5.1) | Discovered by the simulation fit | User correction |
| Cost per role, currency (5.2) | `compare_scenario` accepts a currency, an hourly rate per resource ID and a fixed scenario cost. No run has supplied them | Per-role entry; cost per case; money per year |
| KPI with target (5.3) | `compare_scenario` accepts `sla_hours` and reports the breach rate. No run has supplied it | Target percentage; green/red status |
| Root cause cards (5.4) | The agent writes its own diagnosis and a decision note with alternatives | Standard "target missed when…" cards; they need a target |
| Measures in section 6 | Cycle time, 90th percentile, share reaching an outcome | Waiting against processing time, utilisation, rework, cost |
| Default dashboard (7.1) | Nothing | Overview, Activities, Resources |
| Simulation discovery (8.1) | `prepare_environment`, `build_environment`, `revise_environment` | — |
| Check of the model against later cases | `evaluate_environment`, `compare_evaluations` | A plain-language trust statement |
| Scenario parameters (8.2) | `parameters.json`; `compare_scenario` changes task duration and resource headcount | Routing, calendars, demand, priorities as supported change types |
| As-is against what-if (8.3) | `compare_scenario`: shared arrivals, paired runs, 95% range, completion checks, offline `comparison.html` | Several changes in one table |
| Automation report, PDF (8.5, 7.4) | `report.md` per run | Plain-language summary |
| Token animation (4.4) | `export_view` replay | — |
| Assistants (9) | The agent itself | — |

### 11.2 Evidence from the Stage 2 runs

Four unattended runs on the frozen `p2p_heuristics_v1` checkpoint, 2026-10-13.

| Run | Change | Pairs × cases | Paid-case cycle time | Difference (95% range) |
|---|---|---|---|---|
| `01a133da` | Create Quotation comparison Map ×0.8 | 30 × 500 | 79.62 → 70.53 h | −9.09 h (−13.17 to −5.00) |
| `01a133f2` | Analyze Request for Quotation ×0.8 | 5 × 221 | see its report | |
| `01a1340f` | Create Quotation comparison Map ×0.8 | 20 × 500 | 78.76 → 70.61 h | −8.15 h (−15.25 to −1.06) |
| `01a13466` | Create Quotation comparison Map ×0.8 | 5 × 250 | 73.33 → 65.84 h | −7.50 h (−14.41 to −0.58) |

What these show:

- A full what-if runs without supervision: diagnosis, decision note written before the
  simulation, paired runs, comparison page, report.
- With 20 to 30 pairs the range excludes zero for paid cases. With 5 pairs it barely does.
- The agent goes past the tool when it needs to. Run `01a1340f` wrote its own code for
  paid-case tail times, throughput, a time decomposition, and a check that all 12,219
  paid traces keep every approval step.
- Every run tested the same kind of change. No run supplied a target or costs, and none
  changed headcount.
- The agent will not call the result a forecast. Stage 1 kept this model as a
  "structural diagnostic" with a held-out cycle-time distance of 9.55 ± 6.03 h, about
  the size of the predicted effect. Conclusions read "investigate further; do not
  deploy on this simulation alone".
- Reports are written for a statistician: "Student-t interval", "does not establish
  non-inferiority", "outcome proxy".
- One defect: `inspect_environment` does not resolve the mounted `baseline/` path.
- All runs used one synthetic dataset. On BPI Challenge 2019, Stage 1 did worse.

### 11.3 Summary

- **Working:** model of today, diagnosis, one what-if, comparison, written report.
- **Built but untried:** target, costs, headcount change.
- **Missing:** spreadsheet intake, plain-language output, pauses for the human, any screen.
- **Biggest unknown:** a real company's data.

## 12. Interface principles

The first mockup failed the owner's review as "way too overloaded" and "more like a
Claude artifact than an actual product". The second applies the following. Cited from
memory, not re-read.

| Source | Rule applied |
|---|---|
| Nielsen, ten usability heuristics (1994) | Minimalist design; recognition over recall |
| Nielsen Norman Group, progressive disclosure | Show what the current decision needs; put evidence one click away |
| Hick's law; Sweller, cognitive load theory | Fewer choices and fewer elements per screen |
| Krug, *Don't Make Me Think* | Each screen has one obvious purpose |
| Shneiderman's mantra | Overview first, zoom and filter, details on demand |
| Tufte; Few, *Information Dashboard Design* | Remove ink that carries no data; a dashboard answers one question |
| Amershi et al., "Guidelines for Human-AI Interaction" (CHI 2019) | Say what the system can do and how well; make correction easy; explain why |
| Horvitz, "Principles of Mixed-Initiative User Interfaces" (1999) | Weigh the cost of interrupting before asking |
| Wathan and Schoger, *Refactoring UI* | Hierarchy through weight and spacing, not boxes |

Rules for AutoTwin screens:

1. One decision per screen, one primary button.
2. Each checkpoint is a question in plain words with the agent's proposal filled in.
3. Evidence sits behind a single disclosure line such as "How I checked".
4. The run page says whose turn it is before anything else.
5. Process, dashboard and comparison are separate destinations, not side panes.
6. One accent colour, one status marker, almost no boxes.
7. Every checkpoint states how sure the agent is and offers "Something's wrong",
   which hands the reason back to the agent.
8. Use an operator's words. Say "paid orders finish within 72 hours", not "SLA breach
   rate among successful cases".

## 13. Mockups

Private artifact, owner access only: https://claude.ai/artifact/LK76gaMJUi8CKmvErTi6sx.
Source is not in the repository. All figures in it are invented examples.

| Screen | Shows | Behind it today |
|---|---|---|
| Runs | list with status, one "New run" button | Workspace folders exist; nothing lists them |
| New run | drop zone for CSV, Excel, Parquet | Missing; XES only |
| Run | "Your turn", six steps, links to results | Untested; no run has paused |
| 1 Intake | "Is this how your file should be read?" | Missing |
| 2 Understand | one question about odd cases | Partly; the agent finds such cases itself |
| 3 Inputs | target, cost per role, what must not change | Partly; accepted by the tool, never used |
| 4 Model | one sentence, two numbers, Accept | Exists, in research language |
| 5 Diagnose | changes to tick | Partly; decision note exists, no target-based cards |
| 6 Compare | headline, three numbers, Sign off | Exists for one change |
| Process | map with Frequency, Duration, Cost | Partly; replay only |
| Dashboard | headline, four figures, two charts | Missing |
| Comparison | today against each change, with ranges | Exists for one change |

Three things in the comparison mockup have no source in real output: two changes in
one table, the "busy" rows, and a confident headline. The real page is
`experiments/<name>/comparison.html` in any Stage 2 workspace; compare against it.

## 14. What customers and operators expect

Evidence is weaker here than in sections 2–9. Figures are vendor-published
headlines; full case studies were not read. Review themes come from a third-party
aggregator. Nobody has shown AutoTwin to an operator.

| Customer (as described) | Aim | Reported result |
|---|---|---|
| European insurer, motor claims | fewer service-target violations | EUR 15 million a year; 25% fewer 30-day violations |
| Retail e-commerce | meet service targets | fulfilment within target from 74% to over 90%; 10% less effort |
| IT services, Jira | faster ticket resolution | 35% faster issue-to-resolution |
| Bank | faster loan processing | 50 hours to 7 hours |
| University admissions | faster turnaround | 28% shorter turnaround |
| Hospital, cardiac patients | fewer discharge delays | 25% fewer delays |
| Gas provider | faster well intervention | 15% faster cycles |
| Freight forwarder | fewer fulfilment errors | 75% fewer errors |
| Meat processor | less waste | USD 800,000+ a year |
| Pension fund | faster claims | AUD 600,000+ return |

Results are stated as time, target compliance, cost, and error or rework rate. None is
stated as model accuracy. No quantified simulation outcome was found.

Reported likes: depth of discovery, visual analytics, speed to deploy, visibility of
bottlenecks. Reported dislikes: learning curve, wish for richer dashboards and
reporting, integrations, quote-based pricing.

| Expectation | AutoTwin today |
|---|---|
| Use their own spreadsheet export | No |
| See the process and where time goes | Numbers yes, picture partly, plain words no |
| Results as time saved | Yes |
| Results against a target, and as cost | Built, never exercised |
| Money per year | No |
| What the change costs to make | A fixed scenario cost is accepted; never used |
| A clear recommendation | Honest but hedged |
| Try their own change by asking | Yes for a task duration; headcount untried; other kinds unproven |
| Evidence the model can be trusted | Yes |
| No terminal | No |
| Works on their real data | Unproven |

Sources:
https://www.casestudies.com/company/apromore,
https://apromore.com/customer-stories,
https://www.rfp.wiki/it-security/process-mining-platforms/apromore/alternatives-and-competitors,
https://apromore.org/industry-verticals/.

## 15. Open questions and scope

Open:

- Are the six checkpoints the right ones? Not yet approved.
- Does the agent behave the same outside the CLI (section 10)?
- How does the comparison screen read when a change helps a little, with a trade-off?
- Does "range over N runs" mean anything to an operator, or does it read as noise?
- How should a hedged, honest conclusion be worded for an operator?

Next cheap test, from the terminal: one run that supplies a target, hourly rates and a
headcount change. It exercises everything built but untried.

Out of the first version: data pipelines and scheduling (3.2), filters beyond
timeframe and attribute (4.2), conformance (4.4), model editor and model comparison,
sharing roles, accounts. Not copied: Compliance Center, predictive monitoring, task
mining; these are separately licensed add-ons in Apromore.

Not read in the Apromore guide: task mining sub-pages, release notes before 10.0,
dashboard layout mechanics, filter templates, Compliance Center administration.

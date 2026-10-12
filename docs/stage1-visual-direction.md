# Stage 1 visual direction

Research and proposal · 12 October 2026 · No application changes in this document.

## Recommendation

Make the generated environment an **inspectable analyst artifact** returned by the
agent's `export_view` tool. Lead with a readable 2D process map, linked case
evidence, and a compact validation summary. Retain offline export and the
conversation as the place to request investigation, revision, and evaluation.
Animation should answer a timing question; spatial depth adds little to a log
that contains no recovered physical layout.

This is a design proposal informed by the documented workflows below, not a
claim that another product implements AutoTwin's simulation workflow.

## What established tools actually support

| Official reference | Documented workflow | Implication for AutoTwin |
| --- | --- | --- |
| [SAP Signavio feature scope](https://help.sap.com/doc/dbe5b7e54b9e4bccade17c4c4fbac1d1/SHIP/en-US/FeatureScopeDescriptionSAPSignavioProcessIntelligence_EN.pdf) | Process Discovery presents event-log maps, initially emphasizing common paths; Variant Explorer exposes variants; Process Conformance can compare a variant with BPMN. These features appear in the document's Legacy Package section. | Make process structure, observed behavior, and conformance distinct views. Do not present a mined map as an executable simulation specification. |
| [SAP Signavio customizable metrics](https://help.sap.com/docs/signavio-process-intelligence/user-guide/customizable-metrics) | Case-level metrics support variant analysis; event-level metrics appear on process discovery diagrams. Filters update metric results. | State the denominator and selected cohort. Distinguish event count, unique case count, and case span. |
| [Celonis 4.6 Variant Explorer](https://help.celonis.com/cpm46/en/the-variant-explorer) | Variant selection updates the map; variants can be ranked by frequency or throughput time; undisplayed variants are grouped as others. | A short ranked path list is more useful than displaying every path at once. Always disclose coverage and remaining cases. This is a historical interaction reference, not a claim about the latest Celonis UI. |
| [Celonis 4.6 Case Explorer](https://help.celonis.com/cpm46/en/case-explorer) | Sortable case tables open case details and associated activities. | Give every aggregate an inspectable case/event route. |
| [Fluxicon Disco](https://www.fluxicon.com/disco/) | Maps support metric overlays, adjustable detail and activity/path filters; statistics and case histories support drilldown. Animation includes playback, speed and a time navigator. | Connect map selection, readable statistics and cases; use animation as an optional inspection mode. |
| [Disco official tour](https://fluxicon.com/disco/files/Disco-Tour.pdf) | The tour explicitly distinguishes replaying recorded events from simulation. | Label AutoTwin's replay as generated execution. Never imply it reproduces a historical case. |

The common interaction pattern is **overview → select behavior → inspect cases**.
That synthesis is our inference from these references. Visual polish alone does
not establish usability; the proposed flow still needs analyst testing.

## Current AutoTwin starting point

Inspected [README](../README.md), [exporter](../viewer.py),
[HTML template](../visual/template.html) and [replay script](../visual/replay.js).
The root `AGENTS.md` is empty; there is no docs child contract.

Useful foundations already exist: a self-contained offline artifact, actual
generated records, selected-case replay, scrubbing and event stepping. The
exporter rejects failed current builds and loop-capped baselines, embeds a
manifest, and includes only evaluation reports whose recorded input hashes still
match the artifacts.

The presentation makes analysis harder than necessary: gateways are collapsed,
stations occupy illustrative coordinates, the camera orbits, evidence is mostly
raw JSON, and procurement/BPI 2019 labels are hard-coded. Node details count
activity-name matches; duplicate activity names can therefore be ambiguous.

## Small first version

One generated HTML file, native HTML/CSS/SVG/JavaScript, existing dependencies,
and three sections. No new application server or dashboard framework.

### 1. Environment

- Header: candidate name, **Generated baseline**, build/evaluation state, case
  count and time range. Derive dataset labels from the manifest.
- Main canvas: 2D BPMN structure with visible gateways, clear task labels,
  directional edges, fit-to-view and zoom. Preserve node IDs. Any simplified
  view must disclose hidden structure and offer the complete model.
- Selected-node inspector: identity, kind, generated event count, affected cases
  and available parameter evidence. Do not infer exclusive/parallel semantics
  from a flattened activity graph.
- Compact scope strip: training dates and cohort, exclusion counts, timestamp
  availability and major assumptions, with links to complete evidence.

Use layout bounds already in BPMN when meaningful. A fallback must be labeled
as layout, never operational geometry. Readability and full labels take priority
over a simulated factory floor.

### 2. Cases and replay

- Searchable generated-case list with event count and generated elapsed span.
  Selecting a case highlights its activities and opens its event table.
- Event timeline: enable → start → end, exact timestamps, activity and resource;
  distinguish generated waiting and execution with text as well as color.
- Play/pause, next event, scrub and visible simulation time; start paused and
  honor reduced-motion preferences. Scrubbing and stepping must reach the same
  state at the same timestamp. Show concurrent events rather than fabricating
  a single serial token.
- Avoid animating travel along model edges unless the execution trace supplies
  that path. An activity sequence alone cannot identify every gateway traversal.

### 3. Validation and evidence

- Present existing compatible evaluations in a readable table: partition,
  seeds, case count, metric definition, mean and standard deviation; include
  conformance results when present. Keep raw reports downloadable/expandable.
- Explain each metric's direction and units from its recorded definition.
  Do not invent a combined fidelity score or automatic acceptance badge.
- Show missing evaluations as “Not evaluated.” Distinguish missing starts,
  estimated service durations, assumed resource capacity and inferred calendars.
- Give evidence its source file, artifact hash and scope. Keep observed,
  estimated and simulated quantities visibly identified.

## Next additions, only when needed

1. **Variants:** ranked generated paths with case count, share, cumulative
   coverage and an explicit remainder. Selecting one filters cases and highlights
   its activities. Disclose timestamp tie ordering; concurrency can make a
   serialized path misleading.
2. **Observed versus generated distributions:** common-bin histograms or ECDFs
   for metrics already evaluated. Export these summaries from the exact compared
   runs and partitions; a baseline replay is not a substitute for seeded
   evaluation output. Do not suggest a one-to-one historical/generated case match.
3. **Candidate comparison:** same metric definitions and compatible experiments,
   with paired values and uncertainty. Reuse `compare_evaluations` checks.

For completion-only logs, label first-to-last completion spans literally; do not
call them full cycle time or infer measured service/waiting time. Displaying held-
out case details is an agent decision after final assessment, not a default
export behavior that invites further tuning on the test set.

## Visual and interaction treatment

Use a calm neutral surface, strong typography, generous spacing, restrained
accent colors and aligned numbers with explicit units. Reserve color for meaning:
selection, execution state and source type. Keep a visible legend and keyboard
focus; offer a table equivalent for graph information. Put detail in a persistent
inspector instead of accumulating tooltips. Keep selection stable when switching
sections, show active filters with counts, and provide a clear reset.

These are proposed design choices, not vendor-derived requirements. Stage 1
does not need a 3D warehouse, a configurable BI builder, live operational control,
or a visual model editor to deliver the first useful inspection artifact.

## Agent-tool integration and review criteria

Keep `export_view(name)` as the entry point. The agent builds and evaluates a
candidate, exports its current evidence, then links the artifact from `report.md`.
The browser inspects those files; it does not silently rebuild or choose a winner.
Preserve hash checks and failed-run rejection. A later build requires re-export.

Verify in an offline real browser that an analyst can:

1. Identify the candidate, scope and evaluation state without opening JSON.
2. Select a task, find its generated cases, and inspect exact event evidence.
3. See branches, loops and concurrent activity without invented physical travel.
4. Distinguish recorded evidence, modeling assumptions and generated outcomes.
5. Find evaluation limitations and return to the agent with a specific question.

Include long/duplicate labels, missing evaluations, concurrent events, narrow
screens and keyboard-only use in review. Every visible number should reconcile
with the named source artifact and selected scope.

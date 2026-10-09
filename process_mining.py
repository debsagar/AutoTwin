"""Process discovery and Stage 1 tools for the native terminal agent."""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def discover_process(path: str, max_cases: int = 5000) -> dict:
    """Mine an XES event log under data/. Return observed flows, variants and
    resource handovers. max_cases selects a file prefix, NOT a random sample
    (1..50000). No files are changed. Gaps are elapsed time, not work duration.
    """
    import pm4py
    from pm4py.objects.log.importer.xes import importer
    from pm4py.objects.log.obj import EventLog, Trace

    root = Path(__file__).resolve().parent / "data"
    source = Path(path).resolve()
    if not source.is_relative_to(root.resolve()) or source.suffix.lower() != ".xes":
        raise ValueError("Select an .xes file inside AutoTwin's data directory.")
    if isinstance(max_cases, bool) or not 1 <= max_cases <= 50000:
        raise ValueError("max_cases must be between 1 and 50000.")
    # ponytail: bounded prefix keeps interactive calls small; full-log jobs come later.
    log = importer.apply(str(source), parameters={
        "max_traces": max_cases, "show_progress_bar": False,
        "timestamp_sort": False,
    })
    activities, variants, resources, handovers = Counter(), Counter(), Counter(), Counter()
    categories, gaps = Counter(), defaultdict(list)
    empty = missing_resource = ties = out_of_order = 0
    dates = []
    for index, trace in enumerate(log):
        if not trace:
            empty += 1
            continue
        for event in trace:
            if not event.get("concept:name") or "time:timestamp" not in event:
                raise ValueError("Every event needs concept:name and time:timestamp; inspect the source before mining.")
        out_of_order += int(any(a["time:timestamp"] > b["time:timestamp"] for a, b in zip(trace, trace[1:])))
        trace = Trace(sorted(trace, key=lambda e: e["time:timestamp"]), attributes=trace.attributes)
        log[index] = trace
        names = tuple(e["concept:name"] for e in trace)
        variants[names] += 1
        activities.update(names)
        categories[str(trace.attributes.get("Item Category", "(absent)"))] += 1
        for event in trace:
            dates.append(event["time:timestamp"])
            resource = event.get("org:resource")
            if resource is None or str(resource).strip().lower() in {"", "none", "nan"}:
                missing_resource += 1
            else:
                resources[str(resource)] += 1
        for a, b in zip(trace, trace[1:]):
            hours = (b["time:timestamp"] - a["time:timestamp"]).total_seconds() / 3600
            ties += int(hours == 0)
            gaps[a["concept:name"], b["concept:name"]].append(hours)
            ra, rb = a.get("org:resource"), b.get("org:resource")
            if all(r is not None and str(r).strip().lower() not in {"", "none", "nan"} for r in (ra, rb)) and ra != rb:
                handovers[str(ra), str(rb)] += 1
    nonempty = EventLog(t for t in log if t)
    dfg, starts, ends = pm4py.discover_dfg(nonempty) if nonempty else ({}, {}, {})
    return {
        "source": str(source.relative_to(root.parent)),
        "scope": {"cases": len(log), "events": sum(activities.values()), "max_cases": max_cases,
                  "selection": "file prefix, not random", "limit_reached": len(log) == max_cases},
        "mapping": {"case": "XES trace", "activity": "concept:name", "timestamp": "time:timestamp", "resource": "org:resource"},
        "date_range": [min(dates).isoformat(), max(dates).isoformat()] if dates else [],
        "quality": {"empty_cases": empty, "cases_sorted": out_of_order, "adjacent_timestamp_ties": ties,
                    "events_without_resource": missing_resource},
        "activities": dict(activities), "start_activities": starts, "end_activities": ends,
        "item_categories": dict(categories), "distinct_resources": len(resources),
        "distinct_edges": len(dfg), "top_edges": [
            {"from": a, "to": b, "count": n, "median_elapsed_hours": median(gaps[a, b])}
            for (a, b), n in Counter(dfg).most_common(20)],
        "distinct_variants": len(variants), "top_variants": [
            {"activities": list(v), "cases": n} for v, n in variants.most_common(10)],
        "top_resource_handovers": [
            {"from": a, "to": b, "count": n} for (a, b), n in handovers.most_common(10)],
        "limits": ["Top edges/variants/handovers are truncated; counts use the selected prefix.",
                   "Equal timestamps retain file order; their causal order is unknown.",
                   "Elapsed gaps include waiting and off-hours; they are not active service times.",
                   "A resource change is an observed sequence, not proof of a team or responsibility transfer.",
                   "A directly-follows graph describes history; it is not a simulator or proof of causation."],
    }


def prepare_environment(path: str, name: str, max_cases: int = 5000,
                        case_attribute: str = "Item Category",
                        case_value: str = "3-way match, invoice before GR") -> dict:
    """Prepare Stage 1 evidence and proposed assumptions; writes an environment
    workspace. Review the returned assumptions before building unless the user
    has explicitly authorized the full Stage 1 workflow.
    """
    from environment import prepare_environment as prepare
    return prepare(path, name, max_cases, case_attribute, case_value)


def build_environment(name: str, estimate_missing_starts: bool = False) -> dict:
    """Build the executable Stage 1 environment from prepared evidence. Writes
    generated artifacts. Missing starts require an explicitly accepted estimation
    policy; estimated service durations are assumptions, not observed evidence.
    """
    from environment import build_environment as build
    return build(name, estimate_missing_starts)


def export_view(name: str) -> dict:
    """Write a standalone offline Three.js replay of a built environment.
    Uses its generated BPMN, simulation trace and validation report. This exports
    a view; it does not run a new simulation or change the model.
    """
    from viewer import export_view as export
    return export(name)


def install_runtime_policy():
    """Local dcode compatibility override: product skills only, native approvals.

    dcode currently has no skill-source allowlist or extension approval registrar.
    Explicit skill invocation has separate discovery and containment roots;
    keep those aligned with the runtime middleware and startup listing.
    Run in both launcher and extension: the server is a separate Python process.
    No installed library is changed. Revisit these two overrides when dcode adds
    supported configuration for skill sources and custom tool approval policies.
    """
    from deepagents_code import agent

    root = Path(__file__).resolve().parent
    from deepagents_code.skills import invocation
    from deepagents_code.skills.load import list_skills

    def product_skills_and_roots(assistant_id, **kwargs):
        skills_root = root / ".deepagents" / "skills"
        return list_skills(project_skills_dir=skills_root), [skills_root.resolve()]

    invocation.discover_skills_and_roots = product_skills_and_roots
    agent.get_skill_sources = lambda assistant_id="autotwin", project_context=None: [
        (str(root / ".deepagents" / "skills"), "AutoTwin")]
    if getattr(agent._add_interrupt_on, "_autotwin", False):
        return
    native_interrupts = agent._add_interrupt_on

    def interrupts(**kwargs):
        policies = native_interrupts(**kwargs)
        for name in ("prepare_environment", "build_environment", "export_view"):
            policies[name] = {
                **policies["write_file"],
                "description": f"{name}: write AutoTwin environment artifacts.",
            }
        return policies

    interrupts._autotwin = True
    agent._add_interrupt_on = interrupts


async def extension(api):
    import sys

    # The native server loads extensions by path, outside this project's imports.
    root = str(Path(__file__).resolve().parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    install_runtime_policy()
    for tool in (discover_process, prepare_environment, build_environment, export_view):
        api.register_tool(tool)

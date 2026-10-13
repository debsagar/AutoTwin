"""Stage 1: discover and execute a bounded process environment, never optimize it."""
import csv
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from workspace import output_root, subprocess_env

ROOT = Path(__file__).resolve().parent

SEED = 42
COLUMNS = ['case_id', 'activity', 'resource', 'start_time', 'end_time']


def _bundle(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
        raise ValueError('Use a name of 1..80 letters, numbers, underscores or hyphens.')
    return output_root(ROOT) / 'environments' / name


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + '\n')


def _date(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp has no timezone; explicit timezone mapping is required.')
    return dt.astimezone(timezone.utc)


def _source(path):
    source = Path(path)
    source = (ROOT / source).resolve() if not source.is_absolute() else source.resolve()
    if not source.is_relative_to((ROOT / 'data').resolve()) or source.suffix.lower() != '.xes':
        raise ValueError('Select an .xes file inside data/.')
    return source


def _source_digest(source):
    digest = hashlib.sha256()
    with source.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _traces(source, case_attribute):
    """Yield all recorded rows, retaining complete observed traces in a streaming read."""
    seen = set()
    context = ET.iterparse(source, events=('start', 'end'))
    _, xml_root = next(context)
    for event, element in context:
        if event != 'end' or element.tag.rsplit('}', 1)[-1] != 'trace':
            continue
        attrs = {c.get('key'): c.get('value') for c in element if c.get('key')}
        case_id = attrs.get('concept:name')
        if not case_id or case_id in seen:
            raise ValueError(f'Missing or duplicate case identifier: {case_id!r}.')
        seen.add(case_id)
        rows = []
        for child in element:
            if child.tag.rsplit('}', 1)[-1] != 'event':
                continue
            a = {c.get('key'): c.get('value') for c in child}
            if not a.get('concept:name') or not a.get('time:timestamp'):
                raise ValueError(f'Case {case_id} has an event without activity or completion timestamp.')
            end = _date(a['time:timestamp'])
            start = _date(a['start_timestamp']) if a.get('start_timestamp') else None
            if start and start > end:
                raise ValueError(f'Case {case_id} has a start after completion.')
            resource = a.get('org:resource')
            missing = resource is None or resource.strip().lower() in {'', 'none', 'nan'}
            rows.append([case_id, a['concept:name'], 'NOT_SET' if missing else resource,
                         start.isoformat() if start else '', end.isoformat()])
        yield attrs.get(case_attribute, '(absent)'), rows
        element.clear()
        xml_root.clear()


def _span(rows):
    dates = [_date(value) for row in rows for value in row[3:5] if value]
    return min(dates), max(dates)


_SCOPE_CAVEAT = ('Spans use recorded starts when present and completion timestamps. Completion-only '
                 'first observations are not measured case arrivals; full observed traces do not '
                 'prove complete process histories. Category filtering omits other-category workload.')


def inspect_log_scope(path: str, case_attribute: str = 'Item Category',
                      case_value: str | None = None) -> dict:
    """Read-only inventory for choosing explicit windows; no preparation or fitting."""
    source = _source(path)
    if not isinstance(case_attribute, str) or not case_attribute or (case_value is not None and not isinstance(case_value, str)):
        raise ValueError('Specify a case attribute and optional category string.')
    categories, first_months, last_months = Counter(), Counter(), Counter()
    counts = Counter(dict.fromkeys(['source_events', 'matching_cases', 'matching_events', 'matching_empty_cases',
                                   'other_category_cases_excluded', 'other_category_events_excluded', 'missing_starts'], 0))
    earliest = latest = None
    for category, rows in _traces(source, case_attribute):
        categories[category] += 1
        counts['source_events'] += len(rows)
        if case_value is not None and category != case_value:
            counts['other_category_cases_excluded'] += 1
            counts['other_category_events_excluded'] += len(rows)
            continue
        counts['matching_cases'] += 1
        counts['matching_events'] += len(rows)
        if not rows:
            counts['matching_empty_cases'] += 1
            continue
        begin, finish = _span(rows)
        earliest = min(earliest, begin) if earliest else begin
        latest = max(latest, finish) if latest else finish
        first_months[begin.strftime('%Y-%m')] += 1
        last_months[finish.strftime('%Y-%m')] += 1
        counts['missing_starts'] += sum(not row[3] for row in rows)
    return {'source': str(source), 'source_sha256': _source_digest(source), 'case_attribute': case_attribute, 'case_value': case_value,
            'source_cases': sum(categories.values()), 'categories': dict(categories), **dict(counts),
            'observed_date_range': [earliest.isoformat(), latest.isoformat()] if earliest else None,
            'monthly_first_observations': dict(sorted(first_months.items())),
            'monthly_last_observations': dict(sorted(last_months.items())), 'caveat': _SCOPE_CAVEAT}


def prepare_environment(path: str, name: str, partitions: dict,
                        max_cases: int = 5000, case_attribute: str = 'Item Category',
                        case_value: str | None = None) -> dict:
    """Select whole observed cases in [start, end); date-only bounds mean UTC midnight."""
    source = _source(path)
    if type(max_cases) is not int or not 1 <= max_cases <= 50000:
        raise ValueError('max_cases must be an integer from 1 to 50000; it is a fail guard, not a sample size.')
    if not isinstance(case_attribute, str) or not case_attribute or (case_value is not None and not isinstance(case_value, str)):
        raise ValueError('Specify a case attribute and optional category string.')
    if not isinstance(partitions, dict) or 'train' not in partitions or set(partitions) - {'train', 'validation', 'test'}:
        raise ValueError('Supply train and optional validation/test partitions with start and end timestamps.')
    windows = {}
    for split, bounds in partitions.items():
        if not isinstance(bounds, dict) or set(bounds) != {'start', 'end'} or not all(isinstance(v, str) for v in bounds.values()):
            raise ValueError(f'{split} requires start and end timestamp strings.')
        begin, finish = (_date(value + 'T00:00:00+00:00' if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else value)
                         for value in (bounds['start'], bounds['end']))
        if begin >= finish:
            raise ValueError(f'{split} start must be before end.')
        windows[split] = (begin, finish)
    ordered = sorted(windows.values())
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Time partitions must not overlap.')
    chronological = [windows[s] for s in ('train', 'validation', 'test') if s in windows]
    if chronological != sorted(chronological):
        raise ValueError('Time partitions must follow train, validation, test chronological order.')
    bundle = _bundle(name)
    if bundle.exists():
        raise FileExistsError(f'{bundle} already exists; use a new name.')
    splits = {split: [] for split in windows}
    categories, quality = Counter(), Counter()
    excluded = Counter(dict.fromkeys(['other_category_cases', 'other_category_events', 'boundary_crossing_cases',
                                     'boundary_crossing_events', 'outside_windows_cases', 'outside_windows_events'], 0))
    selected = eligible = empty = 0
    earliest = latest = None
    for category, rows in _traces(source, case_attribute):
        categories[category] += 1
        if case_value is not None and category != case_value:
            excluded['other_category_cases'] += 1
            excluded['other_category_events'] += len(rows)
            continue
        if not rows:
            empty += 1
            continue
        eligible += 1
        begin, finish = _span(rows)
        split = next((s for s, (left, right) in windows.items() if left <= begin and finish < right), None)
        if split is None:
            crossing = any(begin < boundary <= finish for window in windows.values() for boundary in window)
            excluded['boundary_crossing_cases' if crossing else 'outside_windows_cases'] += 1
            excluded['boundary_crossing_events' if crossing else 'outside_windows_events'] += len(rows)
            continue
        selected += 1
        if selected > max_cases:
            raise ValueError(f'Selected cases exceed max_cases={max_cases}; choose narrower windows or raise the guard. No cases were sampled or written.')
        earliest = min(earliest, begin) if earliest else begin
        latest = max(latest, finish) if latest else finish
        quality['cases_reordered_by_completion'] += int(rows != sorted(rows, key=lambda r: r[4]))
        rows.sort(key=lambda r: r[4])
        quality['missing_starts'] += sum(not row[3] for row in rows)
        quality['missing_resources'] += sum(row[2] == 'NOT_SET' for row in rows)
        quality['dates_outside_2018_2019'] += sum(_date(row[4]).year not in {2018, 2019} for row in rows)
        quality['adjacent_completion_ties'] += sum(a[4] == b[4] for a, b in zip(rows, rows[1:]))
        splits[split].append(rows)
    if not splits['train']:
        raise ValueError('Train window contains no nonempty observed cases.')
    if any(not traces for traces in splits.values()):
        raise ValueError('Each requested partition must contain nonempty observed cases.')
    source_digest = _source_digest(source)
    bundle.mkdir(parents=True)
    for split, traces in splits.items():
        with (bundle / f'{split}.csv').open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerows(row for trace in traces for row in trace)
    manifest = {
        'name': name, 'status': 'prepared', 'source': str(source), 'source_sha256': source_digest,
        'mapping': {'case': 'trace concept:name', 'activity': 'concept:name', 'completion': 'time:timestamp',
                    'start': 'start_timestamp when present', 'resource': 'org:resource'},
        'scope': {'case_attribute': case_attribute, 'case_value': case_value,
                  'source_cases': sum(categories.values()), 'categories': dict(categories),
                  'matching_nonempty_cases': eligible, 'matching_empty_cases_excluded': empty,
                  'selected_cases': selected, 'selection': 'full observed cases contained in named time windows [start, end)',
                  'max_cases_guard': max_cases,
                  'partitions': {s: {'start': a.isoformat(), 'end': b.isoformat()} for s, (a, b) in windows.items()},
                  'split': {s: {'cases': len(v), 'events': sum(map(len, v)),
                                'single_event_cases': sum(len(trace) == 1 for trace in v),
                                'activity_events': dict(Counter(row[1] for trace in v for row in trace))}
                            for s, v in splits.items()},
                  'excluded': dict(excluded), 'caveat': _SCOPE_CAVEAT},
        'quality': dict(quality), 'date_range': [earliest.isoformat(), latest.isoformat()],
        'prerequisites': {'measured_starts_available': quality['missing_starts'] == 0,
                          'missing_start_estimation_requires_explicit_consent': quality['missing_starts'] > 0},
        'assumptions': ['NOT_SET represents missing external identities. Build supplies synthetic slots; this capacity is assumed.',
                        'Equal completion timestamps preserve file order; causal order is unknown.',
                        'Unusual years are retained and counted, not silently discarded.', _SCOPE_CAVEAT,
                        'Boundary-crossing observed cases are excluded in full; their events are never truncated.'],
        'not_supported': ['Measured service durations without starts', 'Causal what-if claims',
                          'Stage 2 optimization or policy evaluation'],
        'sources': ['https://github.com/AutomatedProcessImprovement/pix-framework',
                    'https://github.com/AutomatedProcessImprovement/Prosimos', 'https://pm4py.fit.fraunhofer.de/'],
    }
    _write_json(bundle / 'manifest.json', manifest)
    return manifest


def _discovery_settings(settings=None):
    """Validate only discovery options supported by the installed libraries."""
    if settings is None:
        settings = {}
    if not isinstance(settings, dict) or set(settings) - {'discovery_method', 'noise_threshold', 'gateway_method', 'arrival_filter_outliers'}:
        raise ValueError('settings accepts discovery_method, noise_threshold, gateway_method, and arrival_filter_outliers only.')
    result = {'discovery_method': 'inductive', 'noise_threshold': 0.0, 'gateway_method': 'discovery', 'arrival_filter_outliers': True, **settings}
    if result['discovery_method'] not in ('inductive', 'heuristics'):
        raise ValueError('discovery_method must be inductive or heuristics.')
    if result['discovery_method'] == 'heuristics' and result['noise_threshold'] != 0:
        raise ValueError('noise_threshold applies only to inductive discovery.')
    noise = result['noise_threshold']
    if type(noise) not in (int, float) or not math.isfinite(noise) or not 0 <= noise <= 1:
        raise ValueError('noise_threshold must be a finite number from 0 to 1.')
    if result['gateway_method'] not in ('discovery', 'equiprobable', 'token_replay'):
        raise ValueError('gateway_method must be discovery, equiprobable, or token_replay.')
    if type(result['arrival_filter_outliers']) is not bool:
        raise ValueError('arrival_filter_outliers must be boolean.')
    result['noise_threshold'] = float(noise)
    return result


def build_environment(name: str, estimate_missing_starts: bool = False, settings: dict | None = None) -> dict:
    """Build PM4Py/PIX parameters and execute a seeded 200-case Prosimos baseline."""
    settings = _discovery_settings(settings)
    bundle = _bundle(name)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    if type(estimate_missing_starts) is not bool:
        raise ValueError('estimate_missing_starts must be a boolean.')
    if manifest['quality'].get('missing_starts', 0) and not estimate_missing_starts:
        return {'status': 'needs_start_estimation_consent', 'name': name,
                'reason': 'Completion-only events do not measure service durations. Explicitly enable PIX start estimation.'}
    (bundle / 'report.json').unlink(missing_ok=True)
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--build', name,
                                 str(int(estimate_missing_starts)), json.dumps(settings)], capture_output=True, text=True,
                                timeout=600, cwd=bundle, env={**subprocess_env(), 'PYTHONHASHSEED': str(SEED)})
    except subprocess.TimeoutExpired:
        manifest['status'] = 'build_failed'
        manifest['error'] = 'Build exceeded the 600 second timeout.'
        (bundle / 'build.log').write_text(manifest['error'] + '\n')
        _write_json(bundle / 'manifest.json', manifest)
        return {'status': 'build_failed', 'name': name, 'error': manifest['error'], 'bundle': str(bundle)}
    (bundle / 'build.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        manifest['status'] = 'build_failed'
        manifest['error'] = result.stderr[-4000:]
        _write_json(bundle / 'manifest.json', manifest)
        return {'status': 'build_failed', 'name': name, 'error': manifest['error'], 'bundle': str(bundle)}
    return json.loads((bundle / 'report.json').read_text())


def _discover_bpmn(train, settings, uuid_rng=None):
    import pm4py
    if settings['discovery_method'] == 'heuristics':
        net, initial, final = pm4py.discover_petri_net_heuristics(train, activity_key='activity', case_id_key='case_id', timestamp_key='end_time')
        from pm4py.algo.analysis.woflan import algorithm as woflan
        if not woflan.apply(net, initial, final, parameters={'print_diagnostics': False}):
            raise ValueError('Heuristics discovery produced an unsound net; candidate rejected.')
        if uuid_rng is not None:
            uuid_rng.seed(SEED)
        return pm4py.convert_to_bpmn(net, initial, final)
    tree = pm4py.discover_process_tree_inductive(train, activity_key='activity', case_id_key='case_id', timestamp_key='end_time', noise_threshold=settings['noise_threshold'])
    from pm4py.objects.process_tree.obj import Operator
    def canonicalize(node):
        for child in node.children:
            canonicalize(child)
        if node.operator in {Operator.XOR, Operator.PARALLEL, Operator.OR}:
            node.children.sort(key=str)
    canonicalize(tree)
    if uuid_rng is not None:
        uuid_rng.seed(SEED)
    return pm4py.convert_to_bpmn(tree)


def _build(name, estimate, settings=None):
    settings = _discovery_settings(settings)
    # Child-process-only UUID stream: BPMN IDs affect set iteration and PIX replay.
    import uuid
    uuid_rng = random.Random(SEED)
    original_uuid4 = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int=uuid_rng.getrandbits(128), version=4)
    import numpy as np
    import pandas as pd
    import pm4py
    from pix_framework.io.event_log import EventLogIDs
    from pix_framework.io.bpm_graph import BPMNGraph
    from pix_framework.enhancement.start_time_estimator.config import Configuration
    from pix_framework.enhancement.start_time_estimator.estimator import StartTimeEstimator
    from pix_framework.discovery.case_arrival import discover_case_arrival_model
    from pix_framework.discovery.resource_model import discover_resource_model
    from pix_framework.discovery.resource_calendar_and_performance.calendar_discovery_parameters import CalendarDiscoveryParameters, CalendarType
    from pix_framework.discovery.gateway_probabilities import compute_gateway_probabilities, GatewayProbabilitiesDiscoveryMethod
    from prosimos.simulation_engine import run_simulation
    random.seed(SEED)
    np.random.seed(SEED)
    bundle = _bundle(name)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    ids = EventLogIDs(case='case_id', activity='activity', resource='resource', start_time='start_time', end_time='end_time')
    train = pd.read_csv(bundle / 'train.csv', dtype={'case_id': str, 'activity': str, 'resource': str},
                        keep_default_na=False, na_values={'start_time': ['']})
    for col in ['start_time', 'end_time']:
        train[col] = pd.to_datetime(train[col], utc=True, format='mixed')
    if train.start_time.isna().any():
        if not estimate:
            raise ValueError('Missing starts require explicit estimation consent.')
        train = StartTimeEstimator(train, Configuration(log_ids=ids, reuse_current_start_times=True)).estimate(replace_recorded_start_times=True)
    if train.start_time.isna().any() or (train.start_time > train.end_time).any():
        raise ValueError('Start estimation left invalid durations.')
    train.to_csv(bundle / 'train_fitted.csv', index=False)
    bpmn = _discover_bpmn(train, settings, uuid_rng)
    # PM4Py stores flows in identity-hashed sets; stable export order matters to replay.
    nodes, flows = list(bpmn.get_nodes()), list(bpmn.get_flows())
    bpmn.get_nodes = lambda: sorted(nodes, key=lambda n: str(n.get_id()))
    bpmn.get_flows = lambda: sorted(flows, key=lambda f: str(f.get_id()))
    pm4py.write_bpmn(bpmn, str(bundle / 'model.bpmn'), auto_layout=False)
    uuid.uuid4 = original_uuid4
    graph = BPMNGraph.from_bpmn_path(bundle / 'model.bpmn')
    # PIX discovers resource distributions by activity name; Prosimos requires BPMN IDs.
    tasks = [node for node in bpmn.get_nodes() if isinstance(node, pm4py.objects.bpmn.obj.BPMN.Task)]
    task_ids = {node.get_name(): node.get_id() for node in tasks}
    if len(task_ids) != len(tasks):
        raise ValueError('Discovered BPMN has duplicate activity labels; resource mapping would be ambiguous.')
    resource = discover_resource_model(train, ids, CalendarDiscoveryParameters(discovery_type=CalendarType.DIFFERENTIATED_BY_RESOURCE)).to_dict()
    resource['task_resource_distribution'] = [d for d in resource['task_resource_distribution'] if d['task_id'] in task_ids]
    for distribution in resource['task_resource_distribution']:
        distribution['task_id'] = task_ids[distribution['task_id']]
    for profile in resource['resource_profiles']:
        for r in profile['resource_list']:
            r['assignedTasks'] = [task_ids[t] for t in r['assignedTasks'] if t in task_ids]
            if r['id'] == 'NOT_SET':
                r['amount'] = 200  # assumed external capacity for this 200-case baseline
                r['cost_per_hour'] = 0
    model_train = train[train.activity.isin(task_ids)]
    manifest['discovery_settings'] = settings
    if settings['gateway_method'] == 'token_replay':
        gateways, manifest['gateway_replay'] = _token_gateway_probabilities(model_train, pm4py.read_bpmn(str(bundle / 'model.bpmn')))
    else:
        manifest['gateway_replay'] = _gateway_replay_diagnosis(model_train, ids, graph)
        gateways = [g.to_dict() for g in compute_gateway_probabilities(
            model_train, ids, graph, GatewayProbabilitiesDiscoveryMethod(settings['gateway_method']))]
    manifest['gateway_replay']['activities_omitted_by_discovery'] = train[~train.activity.isin(task_ids)].activity.value_counts().to_dict()
    manifest['gateway_replay']['training_cases'] = int(train.case_id.nunique())
    manifest['gateway_replay']['training_events'] = len(train)
    manifest['gateway_replay']['replayed_events'] = len(model_train)
    parameters = {**resource, **discover_case_arrival_model(train, ids, filter_outliers=settings['arrival_filter_outliers']).to_dict(),
                  'gateway_branching_probabilities': gateways}
    _write_json(bundle / 'parameters.json', parameters)
    random.seed(SEED)
    np.random.seed(SEED)
    run_simulation(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), 200,
                   str(bundle / 'simulation_statistics.csv'), str(bundle / 'simulation.csv'),
                   starting_at=train.start_time.min().isoformat())
    simulated = pd.read_csv(bundle / 'simulation.csv', keep_default_na=False)
    _report(bundle, manifest, simulated, estimate)


def _token_gateway_probabilities(train, bpmn):
    """Count complete, fitting training replays, including silent loop exits."""
    import pm4py
    from pm4py.objects.conversion.bpmn.variants import to_petri_net
    from pm4py.objects.petri_net.utils import reduction
    if any(isinstance(n, pm4py.objects.bpmn.obj.BPMN.InclusiveGateway) for n in bpmn.get_nodes()):
        raise ValueError('Gateway token replay supports exclusive and parallel gateways only.')
    net, initial, final, flow_places, _ = to_petri_net.apply(
        bpmn, parameters={'return_flow_trans_map': True})
    branches = {flow: place for flow, place in sorted(flow_places.items(), key=lambda item: str(item[0].get_id()))
                if isinstance(flow.get_source(), pm4py.objects.bpmn.obj.BPMN.ExclusiveGateway)
                and len(flow.get_source().get_out_arcs()) > 1}
    transitions = {next(iter(place.in_arcs)).source: flow for flow, place in branches.items()}
    # Preserve branch identities while PM4Py removes long invisible chains.
    # Restore invisibility before replay: these are never fabricated log events.
    for transition in transitions:
        transition.label = transition.name
    reduction.apply_simple_reduction(net)
    for transition in transitions:
        transition.label = None
    if not transitions.keys() <= net.transitions:
        raise ValueError('Petri reduction removed a gateway branch transition.')
    replay = pm4py.conformance_diagnostics_token_based_replay(
        train, net, initial, final, activity_key='activity', timestamp_key='end_time', case_id_key='case_id')
    fitted = sum(r['trace_is_fit'] and r['missing_tokens'] == 0 and r['remaining_tokens'] == 0 for r in replay)
    if fitted != len(replay):
        raise ValueError(f'Gateway token replay fits {fitted}/{len(replay)} training cases; refusing incomplete branch counts.')
    counts = Counter(str(transitions[t].get_id()) for r in replay for t in r['activated_transitions'] if t in transitions)
    frequencies = {}
    for flow in branches:
        frequencies.setdefault(str(flow.get_source().get_id()), {})[str(flow.get_id())] = counts[str(flow.get_id())]
    probabilities = []
    for gateway, paths in frequencies.items():
        total = sum(paths.values())
        if not total:
            raise ValueError(f'Gateway {gateway} has no fitting training observations.')
        probabilities.append({'gateway_id': gateway, 'probabilities': [
            {'path_id': path, 'value': count / total} for path, count in paths.items()]})
    return probabilities, {'method': 'PM4Py token replay on reduced Petri net; complete training traces in completion order',
                           'cases': len(replay), 'cases_fitting_complete_replay': fitted,
                           'branch_frequencies': frequencies,
                           'caveat': 'Training replay fit does not establish timing fidelity. Silent routing can be ambiguous; gateway draws assume independent stationary probabilities.'}


def _gateway_replay_diagnosis(train, ids, graph):
    """Expose PIX evidence; firing observed tasks does not prove terminal routing."""
    from pix_framework.io.bpm_graph import BPMNNodeType
    arcs, fully_fired, unfired = {}, 0, Counter()
    for _, events in train.groupby(ids.case):
        sequence = events.sort_values([ids.start_time, ids.end_time])[ids.activity].tolist()
        correct, fired, _ = graph.replay_trace(sequence, arcs)
        fully_fired += int(correct)
        unfired.update(activity for activity, did_fire in zip(sequence, fired) if not did_fire)
    return {'cases': int(train[ids.case].nunique()), 'cases_all_observed_tasks_fired': fully_fired,
            'unfired_observed_tasks': dict(unfired),
            'branch_frequencies': {node.id: {flow: arcs.get(flow, 0) for flow in node.outgoing_flows}
                                   for node in graph.element_info.values()
                                   if node.type in (BPMNNodeType.EXCLUSIVE_GATEWAY, BPMNNodeType.INCLUSIVE_GATEWAY)
                                   and len(node.outgoing_flows) > 1},
            'caveat': 'PIX heuristic replay frequencies can omit invisible terminal paths. All observed tasks fired is not a complete alignment or proof that branch probabilities reproduce the training log.'}


def _termination_evidence(folder):
    """Prosimos writes capped cases as ordinary rows; inspect its explicit warnings."""
    path = folder / 'simulation_warnings.txt'
    warnings = path.read_text() if path.exists() else ''
    cases = sorted(set(re.findall(r'Infinite loop was detected in case #(\S+) on element', warnings)))
    return {'warning_file_present': path.exists(), 'terminated_case_count': len(cases),
            'terminated_case_ids': cases,
            'completion_verified': False,
            'interpretation': 'Counts describe logged cases, not verified process completion. No termination warning alone does not prove every case reached an end event.'}


def _report(bundle, manifest, simulated, estimated):
    import pandas as pd
    from importlib.metadata import version
    simulated.columns = [c.strip() for c in simulated.columns]
    def summary(frame, case, activity, start, end):
        begin, finish = pd.to_datetime(frame[start], utc=True, format='mixed'), pd.to_datetime(frame[end], utc=True, format='mixed')
        span = pd.DataFrame({'case': frame[case], 'begin': begin, 'finish': finish}).groupby('case').agg({'begin': 'min', 'finish': 'max'})
        counts = frame[activity].value_counts()
        return {'cases': len(span), 'events': len(frame), 'activity_share': (counts / len(frame)).to_dict(),
                'median_case_span_hours': float(((span.finish - span.begin).dt.total_seconds() / 3600).median()),
                'events_per_case': float(len(frame) / len(span))}
    generated = summary(simulated, 'case_id', 'activity', 'end_time', 'end_time')
    generated['median_full_span_hours'] = summary(simulated, 'case_id', 'activity', 'start_time', 'end_time')['median_case_span_hours']
    valid = generated['cases'] == 200 and len(simulated) > 0 and (pd.to_datetime(simulated.start_time, utc=True) <= pd.to_datetime(simulated.end_time, utc=True)).all()
    termination = _termination_evidence(bundle)
    valid = valid and not termination['terminated_case_count']
    fitted = pd.read_csv(bundle / 'train_fitted.csv', keep_default_na=False)
    missing = fitted[fitted.resource == 'NOT_SET']
    estimated_duration = (pd.to_datetime(missing.end_time, utc=True, format='mixed') - pd.to_datetime(missing.start_time, utc=True, format='mixed')).dt.total_seconds() / 3600
    report = {'status': 'generated_unvalidated' if valid else 'simulation_check_failed', 'name': manifest['name'], 'bundle': str(bundle),
              'simulation': {'engine': 'Prosimos', 'seed': SEED, 'requested_cases': 200, 'valid_trace': bool(valid),
                             'termination': termination},
              'discovery_settings': manifest['discovery_settings'],
              'gateway_replay': manifest['gateway_replay'],
              'generated': generated,
              'evaluation': 'Not evaluated by build. Use evaluate_environment with an explicit split, metrics and seeds.',
              'assumptions': {'starts': 'PIX estimated on training cases only' if estimated else 'recorded',
                              'durations': 'estimated, not measured service times' if estimated else 'recorded start-to-end elapsed durations',
                              'calendars': 'PIX inferred availability, not documented staffing rosters',
                              'resource_cost': 'PIX default 20 per hour; not an observed financial input',
                              'missing_resources': 'NOT_SET uses 200 synthetic external slots and zero cost; assumed capacity, not measured staffing',
                              'estimated_start_range': [str(fitted.start_time.min()), str(fitted.start_time.max())],
                              'arrivals': 'fitted on selected training cases; category and boundary exclusions can omit competing workload'},
              'diagnosis': {'synthetic_resource_training_events': len(missing),
                            'synthetic_resource_median_estimated_duration_hours': float(estimated_duration.median()) if len(missing) else None,
                            'interpretation': 'Missing identities use 200 synthetic external slots to avoid a single-vendor bottleneck. Inferred durations and external capacity remain assumptions; timing fidelity is unvalidated.'},
              'versions': {p: version(p) for p in ['pm4py', 'pix-framework', 'prosimos']},
              'artifacts': ['model.bpmn', 'parameters.json', 'simulation.csv', 'simulation_statistics.csv', 'train_fitted.csv', 'build.log']}
    manifest.pop('error', None)
    manifest['status'] = report['status']
    manifest['build'] = report['assumptions']
    _write_json(bundle / 'manifest.json', manifest)
    _write_json(bundle / 'report.json', report)


if __name__ == '__main__' and len(sys.argv) in (4, 5) and sys.argv[1] == '--build':
    _build(sys.argv[2], bool(int(sys.argv[3])), json.loads(sys.argv[4]) if len(sys.argv) == 5 else None)

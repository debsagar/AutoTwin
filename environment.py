"""Stage 1: discover and execute a bounded process environment, never optimize it."""
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
SEED = 42
COLUMNS = ['case_id', 'activity', 'resource', 'start_time', 'end_time']


def _bundle(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
        raise ValueError('Use a name of 1..80 letters, numbers, underscores or hyphens.')
    return ROOT / 'runs' / 'environments' / name


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + '\n')


def _date(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp has no timezone; explicit timezone mapping is required.')
    return dt.astimezone(timezone.utc)


def prepare_environment(path: str, name: str, max_cases: int = 5000,
                        case_attribute: str = 'Item Category',
                        case_value: str = '3-way match, invoice before GR') -> dict:
    """Normalize a whole-log reservoir cohort and split cases before any fitting.
    Original files are read only. Missing starts require explicit build consent.
    """
    source = Path(path).resolve()
    if not source.is_relative_to((ROOT / 'data').resolve()) or source.suffix.lower() != '.xes':
        raise ValueError('Select an .xes file inside data/.')
    if type(max_cases) is not int or not 10 <= max_cases <= 50000:
        raise ValueError('max_cases must be an integer from 10 to 50000.')
    if not isinstance(case_attribute, str) or not case_attribute or not isinstance(case_value, str):
        raise ValueError('Specify a case attribute and category string.')
    bundle = _bundle(name)
    if bundle.exists():
        raise FileExistsError(f'{bundle} already exists; use a new name.')
    rng, sampled, categories = random.Random(SEED), [], Counter()
    total = eligible = empty = 0
    quality = Counter()
    # ponytail: XML streaming plus a bounded reservoir; no full-log dataframe.
    context = ET.iterparse(source, events=('start', 'end'))
    _, xml_root = next(context)
    for event, element in context:
        if event != 'end' or element.tag.rsplit('}', 1)[-1] != 'trace':
            continue
        total += 1
        attrs = {c.get('key'): c.get('value') for c in element if c.get('key')}
        category = attrs.get(case_attribute, '(absent)')
        categories[category] += 1
        if category == case_value:
            rows = []
            case_id = attrs.get('concept:name')
            if not case_id:
                raise ValueError(f'Trace {total} has no case identifier.')
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
                missing_resource = resource is None or resource.strip().lower() in {'', 'none', 'nan'}
                rows.append([case_id, a['concept:name'], 'NOT_SET' if missing_resource else resource,
                             start.isoformat() if start else '', end.isoformat()])
            if not rows:
                empty += 1
            else:
                eligible += 1
                if len(sampled) < max_cases:
                    sampled.append(rows)
                else:
                    j = rng.randrange(eligible)
                    if j < max_cases:
                        sampled[j] = rows
        element.clear()
        xml_root.clear()
    if len(sampled) < 10:
        raise ValueError(f'Only {len(sampled)} nonempty cases match {case_attribute}={case_value!r}; need 10.')
    ids = [r[0][0] for r in sampled]
    if len(set(ids)) != len(ids):
        raise ValueError('Selected cases have duplicate identifiers.')
    rng.shuffle(sampled)
    heldout = max(1, round(len(sampled) * .2))
    splits = {'heldout': sampled[:heldout], 'train': sampled[heldout:]}
    dates = []
    for rows in sampled:
        quality['cases_reordered_by_completion'] += int(rows != sorted(rows, key=lambda r: r[4]))
        rows.sort(key=lambda r: r[4])  # stable order preserves ties, whose causal order is unknown
        for row in rows:
            dt = _date(row[4])
            dates.append(dt)
            quality['missing_starts'] += not bool(row[3])
            quality['missing_resources'] += row[2] == 'NOT_SET'
            quality['dates_outside_2018_2019'] += dt.year not in {2018, 2019}
        quality['adjacent_completion_ties'] += sum(a[4] == b[4] for a, b in zip(rows, rows[1:]))
    digest = hashlib.sha256()
    with source.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    bundle.mkdir(parents=True)
    for split, traces in splits.items():
        with (bundle / f'{split}.csv').open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerows(row for trace in traces for row in trace)
    manifest = {
        'name': name, 'status': 'prepared', 'source': str(source), 'source_sha256': digest.hexdigest(),
        'mapping': {'case': 'trace concept:name', 'activity': 'concept:name', 'completion': 'time:timestamp',
                    'start': 'start_timestamp when present', 'resource': 'org:resource'},
        'scope': {'case_attribute': case_attribute, 'case_value': case_value, 'source_cases': total,
                  'categories': dict(categories), 'matching_nonempty_cases': eligible,
                  'matching_empty_cases_excluded': empty, 'selected_cases': len(sampled),
                  'selection': 'seeded reservoir across entire file', 'seed': SEED,
                  'split': {s: {'cases': len(v), 'events': sum(map(len, v))} for s, v in splits.items()},
                  'excluded': 'Other categories and matching empty cases; no date exclusions.'},
        'quality': dict(quality), 'date_range': [min(dates).isoformat(), max(dates).isoformat()],
        'prerequisites': {'measured_starts_available': quality['missing_starts'] == 0,
                          'missing_start_estimation_requires_explicit_consent': quality['missing_starts'] > 0},
        'assumptions': ['NOT_SET represents missing external identities. Build supplies 200 synthetic slots to avoid treating all vendors as one worker; this capacity is assumed.',
                        'Equal completion timestamps preserve file order; causal order is unknown.',
                        'Unusual years are retained and counted, not silently discarded.',
                        'Sampled case arrivals understate full-cohort workload; this is a bounded cohort environment.'],
        'not_supported': ['Measured service durations without starts', 'Causal what-if claims',
                          'Stage 2 optimization or policy evaluation'],
        'sources': ['https://github.com/AutomatedProcessImprovement/pix-framework',
                    'https://github.com/AutomatedProcessImprovement/Prosimos', 'https://pm4py.fit.fraunhofer.de/'],
    }
    _write_json(bundle / 'manifest.json', manifest)
    return manifest


def build_environment(name: str, estimate_missing_starts: bool = False) -> dict:
    """Build PM4Py/PIX parameters and execute a seeded 200-case Prosimos baseline."""
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
                                 str(int(estimate_missing_starts))], capture_output=True, text=True,
                                timeout=600, env={**os.environ, 'PYTHONHASHSEED': str(SEED)})
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


def _build(name, estimate):
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
    from pix_framework.discovery.gateway_probabilities import compute_gateway_probabilities
    from prosimos.simulation_engine import run_simulation
    random.seed(SEED)
    np.random.seed(SEED)
    bundle = _bundle(name)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    ids = EventLogIDs(case='case_id', activity='activity', resource='resource', start_time='start_time', end_time='end_time')
    train = pd.read_csv(bundle / 'train.csv', dtype={'case_id': str, 'resource': str})
    for col in ['start_time', 'end_time']:
        train[col] = pd.to_datetime(train[col], utc=True)
    if train.start_time.isna().any():
        if not estimate:
            raise ValueError('Missing starts require explicit estimation consent.')
        train = StartTimeEstimator(train, Configuration(log_ids=ids, reuse_current_start_times=True)).estimate(replace_recorded_start_times=True)
    if train.start_time.isna().any() or (train.start_time > train.end_time).any():
        raise ValueError('Start estimation left invalid durations.')
    train.to_csv(bundle / 'train_fitted.csv', index=False)
    tree = pm4py.discover_process_tree_inductive(train, activity_key='activity', case_id_key='case_id', timestamp_key='end_time')
    from pm4py.objects.process_tree.obj import Operator
    def canonicalize(node):
        for child in node.children:
            canonicalize(child)
        if node.operator in {Operator.XOR, Operator.PARALLEL, Operator.OR}:
            node.children.sort(key=str)
    canonicalize(tree)
    uuid_rng.seed(SEED)
    bpmn = pm4py.convert_to_bpmn(tree)
    # PM4Py stores flows in identity-hashed sets; stable export order matters to replay.
    nodes, flows = list(bpmn.get_nodes()), list(bpmn.get_flows())
    bpmn.get_nodes = lambda: sorted(nodes, key=lambda n: str(n.get_id()))
    bpmn.get_flows = lambda: sorted(flows, key=lambda f: str(f.get_id()))
    pm4py.write_bpmn(bpmn, str(bundle / 'model.bpmn'), auto_layout=False)
    uuid.uuid4 = original_uuid4
    graph = BPMNGraph.from_bpmn_path(bundle / 'model.bpmn')
    # PIX discovers resource distributions by activity name; Prosimos requires BPMN IDs.
    task_ids = {node.get_name(): node.get_id() for node in bpmn.get_nodes() if isinstance(node, pm4py.objects.bpmn.obj.BPMN.Task)}
    resource = discover_resource_model(train, ids, CalendarDiscoveryParameters(discovery_type=CalendarType.DIFFERENTIATED_BY_RESOURCE)).to_dict()
    for distribution in resource['task_resource_distribution']:
        distribution['task_id'] = task_ids[distribution['task_id']]
    for profile in resource['resource_profiles']:
        for r in profile['resource_list']:
            r['assignedTasks'] = [task_ids[t] for t in r['assignedTasks']]
            if r['id'] == 'NOT_SET':
                r['amount'] = 200  # assumed external capacity for this 200-case baseline
                r['cost_per_hour'] = 0
    parameters = {**resource, **discover_case_arrival_model(train, ids, filter_outliers=False).to_dict(),
                  'gateway_branching_probabilities': [g.to_dict() for g in compute_gateway_probabilities(train, ids, graph)]}
    _write_json(bundle / 'parameters.json', parameters)
    random.seed(SEED)
    np.random.seed(SEED)
    run_simulation(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), 200,
                   str(bundle / 'simulation_statistics.csv'), str(bundle / 'simulation.csv'),
                   starting_at=train.start_time.min().isoformat())
    simulated = pd.read_csv(bundle / 'simulation.csv')
    heldout = pd.read_csv(bundle / 'heldout.csv', dtype={'case_id': str})
    _report(bundle, manifest, heldout, simulated, estimate)


def _report(bundle, manifest, heldout, simulated, estimated):
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
    observed = summary(heldout, 'case_id', 'activity', 'end_time', 'end_time')
    generated = summary(simulated, 'case_id', 'activity', 'end_time', 'end_time')
    generated['median_full_span_hours'] = summary(simulated, 'case_id', 'activity', 'start_time', 'end_time')['median_case_span_hours']
    shares = set(observed['activity_share']) | set(generated['activity_share'])
    difference = sum(abs(observed['activity_share'].get(a, 0) - generated['activity_share'].get(a, 0)) for a in shares) / 2
    valid = generated['cases'] == 200 and len(simulated) > 0 and (pd.to_datetime(simulated.start_time, utc=True) <= pd.to_datetime(simulated.end_time, utc=True)).all()
    fitted = pd.read_csv(bundle / 'train_fitted.csv')
    missing = fitted[fitted.resource == 'NOT_SET']
    estimated_duration = (pd.to_datetime(missing.end_time, utc=True, format='mixed') - pd.to_datetime(missing.start_time, utc=True, format='mixed')).dt.total_seconds() / 3600
    report = {'status': 'generated_unvalidated' if valid else 'simulation_check_failed', 'name': manifest['name'], 'bundle': str(bundle),
              'simulation': {'engine': 'Prosimos', 'seed': SEED, 'requested_cases': 200, 'valid_trace': bool(valid)},
              'heldout': observed, 'generated': generated,
              'comparison': {'activity_share_total_variation': difference,
                             'case_span_ratio': generated['median_case_span_hours'] / observed['median_case_span_hours'] if observed['median_case_span_hours'] else None,
                             'interpretation': 'Diagnostic only; mismatch is reported without calibration or a forced pass. Both case spans use first-to-last completion, and exclude first service. Generated full span is separately reported.'},
              'assumptions': {'starts': 'PIX estimated on training cases only' if estimated else 'recorded',
                              'durations': 'estimated, not measured service times' if estimated else 'recorded start-to-end elapsed durations',
                              'calendars': 'PIX inferred availability, not documented staffing rosters',
                              'resource_cost': 'PIX default 20 per hour; not an observed financial input',
                              'missing_resources': 'NOT_SET uses 200 synthetic external slots and zero cost; assumed capacity, not measured staffing',
                              'estimated_start_range': [str(fitted.start_time.min()), str(fitted.start_time.max())],
                              'arrivals': 'fitted on thinned training cohort; not full source workload'},
              'diagnosis': {'synthetic_resource_training_events': len(missing),
                            'synthetic_resource_median_estimated_duration_hours': float(estimated_duration.median()) if len(missing) else None,
                            'interpretation': 'Missing identities use 200 synthetic external slots to avoid a single-vendor bottleneck. Long inferred durations and sampled arrivals remain assumptions; timing fidelity is unvalidated.'},
              'versions': {p: version(p) for p in ['pm4py', 'pix-framework', 'prosimos']},
              'artifacts': ['model.bpmn', 'parameters.json', 'simulation.csv', 'simulation_statistics.csv', 'train_fitted.csv', 'build.log']}
    manifest.pop('error', None)
    manifest['status'] = report['status']
    manifest['build'] = report['assumptions']
    _write_json(bundle / 'manifest.json', manifest)
    _write_json(bundle / 'report.json', report)


if __name__ == '__main__' and len(sys.argv) == 4 and sys.argv[1] == '--build':
    _build(sys.argv[2], bool(int(sys.argv[3])))

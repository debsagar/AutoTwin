"""Read model evidence and build isolated, explicitly justified candidates."""
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from xml.etree import ElementTree as ET

import environment

from environment import _bundle, _date, _source_digest, _write_json, build_environment


def _summary(values):
    return {'count': len(values), 'min': min(values), 'median': median(values),
            'max': max(values), 'mean': sum(values) / len(values)} if values else {'count': 0}


def _traces(path):
    cases = defaultdict(list)
    with path.open(newline='') as handle:
        for row in csv.DictReader(handle, skipinitialspace=True):
            cases[row['case_id']].append(row)
    activities, durations, repetitions = Counter(), defaultdict(list), defaultdict(list)
    variants, lengths, spans = Counter(), [], []
    for rows in cases.values():
        rows.sort(key=lambda r: _date(r['end_time']))
        counts = Counter(r['activity'] for r in rows)
        activities.update(counts)
        for activity, count in counts.items():
            repetitions[activity].append(count)
        for row in rows:
            if row.get('start_time'):
                durations[row['activity']].append((_date(row['end_time']) - _date(row['start_time'])).total_seconds() / 3600)
        variants[tuple(r['activity'] for r in rows)] += 1
        lengths.append(len(rows))
        spans.append((_date(rows[-1]['end_time']) - _date(rows[0]['end_time'])).total_seconds() / 3600)
    return {'path': str(path), 'sha256': _source_digest(path), 'cases': len(cases),
            'events': sum(activities.values()), 'events_per_case': _summary(lengths),
            'completion_span_hours': _summary(spans),
            'activities': {a: {'events': count, 'cases_present': len(repetitions[a]),
                               'occurrences_per_present_case': _summary(repetitions[a]),
                               'cases_repeating': sum(n > 1 for n in repetitions[a]),
                               'start_to_end_hours': _summary(durations[a])}
                           for a, count in sorted(activities.items())},
            'trace_variants': {'distinct': len(variants), 'top': [
                {'activities': list(v[:20]), 'length': len(v), 'cases': n,
                 'truncated': len(v) > 20} for v, n in variants.most_common(5)]},
            'duration_caveat': 'Recorded or fitted start-to-end elapsed durations include waiting/off-hours; completion-only rows have no duration.'}


def _model(bundle):
    if not (bundle / 'model.bpmn').exists():
        return None
    nodes = {e.get('id'): e for e in ET.parse(bundle / 'model.bpmn').iter() if e.get('id')}
    flows = {k: e for k, e in nodes.items() if e.tag.rsplit('}', 1)[-1] == 'sequenceFlow'}
    outgoing = defaultdict(list)
    for flow in flows.values():
        outgoing[flow.get('sourceRef')].append(flow.get('targetRef'))

    def next_labels(node):
        pending, seen, labels = [node], set(), set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            element = nodes.get(current)
            if element is None:
                continue
            kind = element.tag.rsplit('}', 1)[-1]
            if kind == 'task' or kind == 'endEvent':
                labels.add(element.get('name') or kind)
            else:
                pending.extend(outgoing[current])
        return sorted(labels)

    parameters = json.loads((bundle / 'parameters.json').read_text())
    gateways = []
    for gateway in parameters.get('gateway_branching_probabilities', []):
        paths = []
        for branch in gateway['probabilities']:
            flow = flows.get(branch['path_id'])
            paths.append({**branch, 'target': flow.get('targetRef') if flow is not None else None,
                          'next_activity_labels': next_labels(flow.get('targetRef')) if flow is not None else []})
        gateways.append({'gateway_id': gateway['gateway_id'], 'outgoing': paths})
    return {'tasks': {k: e.get('name') for k, e in nodes.items() if e.tag.rsplit('}', 1)[-1] == 'task'},
            'gateways': gateways[:100], 'gateway_count': len(gateways), 'gateways_truncated': len(gateways) > 100,
            'arrival_time_distribution': parameters.get('arrival_time_distribution'),
            'parameters_path': str(bundle / 'parameters.json'),
            'resource_summary': {'profiles': len(parameters.get('resource_profiles', [])),
                'resources': sum(len(p['resource_list']) for p in parameters.get('resource_profiles', [])),
                'task_distributions': len(parameters.get('task_resource_distribution', [])),
                'calendar_ids': [c['id'] for c in parameters.get('resource_calendars', [])][:100],
                'calendar_count': len(parameters.get('resource_calendars', []))}}


def _evaluation_report(bundle, evaluation):
    path = (environment.ROOT / evaluation).resolve()
    if path.is_dir():
        path /= 'report.json'
    if not path.is_relative_to((bundle / 'evaluations').resolve()) or path.name != 'report.json':
        raise ValueError('Select a report.json inside this environment\'s evaluations/.')
    return path, json.loads(path.read_text())


def inspect_environment(name: str, split: str = 'train', evaluation: str | None = None,
                        seed: int | None = None) -> dict:
    """Inspect observed/model/generated evidence; evaluation and seed select a replication."""
    if split not in ('train', 'validation', 'test', 'heldout'):
        raise ValueError('Choose train, validation, test, or legacy heldout.')
    bundle = _bundle(name)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    built = manifest.get('status') == 'generated_unvalidated'
    result = {'name': name, 'manifest': manifest, 'observed': _traces(bundle / f'{split}.csv'),
              'model': _model(bundle) if built else None}
    if not built:
        result['model_unavailable'] = 'No successful current build; stale model and baseline files are not inspected.'
    if built and (bundle / 'train_fitted.csv').exists() and split == 'train':
        result['fitted_train'] = _traces(bundle / 'train_fitted.csv')
    if evaluation is not None:
        path, report = _evaluation_report(bundle, evaluation)
        result['evaluation'] = report
        if seed is not None:
            if type(seed) is not int or seed not in report['seeds']:
                raise ValueError('Select an integer seed recorded in the evaluation.')
            generated = path.parent / f'seed-{seed}' / 'simulation.csv'
            result['generated'] = _traces(generated) if generated.exists() else {'missing': str(generated)}
            log = generated.parent / 'simulation.log'
            if log.exists():
                result['simulation_log_tail'] = log.read_text()[-4000:]
    elif seed is not None:
        raise ValueError('seed requires an evaluation report.')
    elif built and (bundle / 'simulation.csv').exists():
        result['generated'] = _traces(bundle / 'simulation.csv')
    log = bundle / 'build.log'
    if log.exists():
        result['build_log_tail'] = log.read_text()[-4000:]
    return result


def revise_environment(source: str, name: str, reason: str, settings: dict) -> dict:
    """Build a distinct candidate from unchanged partitions, recording rationale/settings."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Provide an evidence-based reason for the candidate.')
    if not isinstance(settings, dict):
        raise ValueError('settings must be a dictionary of build arguments.')
    original, candidate = _bundle(source), _bundle(name)
    manifest = json.loads((original / 'manifest.json').read_text())
    if candidate.exists():
        raise FileExistsError('Candidate already exists; choose a new name.')
    partitions = [original / f'{split}.csv' for split in ('train', 'validation', 'test', 'heldout')
                  if (original / f'{split}.csv').exists()]
    if not any(p.name == 'train.csv' for p in partitions):
        raise ValueError('Source requires train.csv.')
    from environment import _discovery_settings
    settings = _discovery_settings({**manifest.get('discovery_settings', {}), **settings})
    estimate = manifest.get('build', {}).get('starts', '').startswith('PIX estimated')
    candidate.mkdir(parents=True)
    for path in partitions:
        shutil.copyfile(path, candidate / path.name)
    manifest = {k: v for k, v in manifest.items() if k not in ('build', 'build_settings', 'discovery_settings', 'error')}
    manifest.update(name=name, status='prepared', revision={'source_environment': source,
                    'source_manifest_sha256': _source_digest(original / 'manifest.json'),
                    'reason': reason.strip(), 'settings': settings,
                    'partition_sha256': {p.name: _source_digest(p) for p in partitions}})
    _write_json(candidate / 'manifest.json', manifest)
    return build_environment(name, estimate_missing_starts=estimate, settings=settings)


def compare_evaluations(paths: list[str]) -> dict:
    """Compare report files or evaluation directories without choosing a winner."""
    if not isinstance(paths, list) or len(paths) < 2:
        raise ValueError('Supply at least two evaluation report paths.')
    paths = [environment.ROOT / p for p in paths]
    paths = [str(p / 'report.json') if p.is_dir() else str(p) for p in paths]
    reports = [json.loads(Path(p).read_text()) for p in paths]
    def protocol(report):
        return {k: report[k] for k in ('split', 'cases', 'observed_cases', 'observed_events',
                                      'seeds', 'starting_at', 'metric_definitions', 'boundary_policy', 'epoch_policy', 'versions')} | {
                    'observed_sha256': report['input_sha256'][report['split'] + '.csv'],
                    'train_sha256': report['input_sha256'].get('train.csv')}
    if any(r['status'] != 'evaluated' for r in reports):
        raise ValueError('All reports must be completed evaluations.')
    baseline = protocol(reports[0])
    differences = [{k: {'baseline': baseline[k], 'candidate': value}
                    for k, value in protocol(r).items() if baseline[k] != value}
                   for r in reports[1:]]
    return {'comparable': not any(differences), 'protocol_differences': differences,
            'protocol': baseline, 'evaluations': [
        {'path': p, 'name': r['name'], 'summary': r['summary'], 'conformance': r.get('conformance'),
         'input_sha256': r['input_sha256'], 'model_provenance': r.get('model_provenance'),
         'replications': [{k: v for k, v in run.items() if k != 'metric_definitions'}
                          for run in r['replications']]} for p, r in zip(paths, reports)]}

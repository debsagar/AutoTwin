"""Stage 2: explicit parameter changes, shared demand, repeated comparisons."""
import copy
import csv
import json
import math
import random
import re
import shutil
from datetime import timedelta
from statistics import mean, stdev
from importlib.metadata import version
from xml.etree import ElementTree as ET

from environment import ROOT, _date, _source_digest, _write_json
from workspace import output_root


def _positive(value, name, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (value == 0 and not zero):
        raise ValueError(f'{name} must be a finite {"nonnegative" if zero else "positive"} number.')


def _revise(parameters, model, changes):
    from pix_framework.statistics.distribution import DurationDistribution
    result = copy.deepcopy(parameters)
    labels = {e.get('id'): e.get('name') for e in ET.parse(model).iter() if e.tag.rsplit('}', 1)[-1] == 'task'}
    resources = {r['id']: r for p in result['resource_profiles'] for r in p['resource_list']}
    if not changes or len(changes) > 20:
        raise ValueError('Supply 1..20 explicit changes.')
    seen = set()
    for change in changes:
        kind = change.get('kind')
        if kind == 'task_duration':
            if set(change) != {'kind', 'activity', 'factor'}:
                raise ValueError('task_duration needs activity and factor only.')
            _positive(change['factor'], 'factor')
            matches = [k for k, v in labels.items() if v == change['activity']]
            if len(matches) != 1:
                raise ValueError('Activity label must identify exactly one task.')
            key = (kind, matches[0])
            rows = [r for r in result['task_resource_distribution'] if r['task_id'] == matches[0]]
            if len(rows) != 1 or not rows[0]['resources']:
                raise ValueError('Task has no unambiguous duration distributions.')
            for distribution in rows[0]['resources']:
                scaled = DurationDistribution.from_dict(distribution)
                # PIX's scale_distribution multiplies None for fixed/uniform inputs.
                for field in ('mean', 'std', 'min', 'max', 'var'):
                    value = getattr(scaled, field)
                    if value is not None:
                        setattr(scaled, field, value * change['factor'] ** (2 if field == 'var' else 1))
                distribution.update(scaled.to_prosimos_distribution())
        elif kind == 'resource_amount':
            if set(change) != {'kind', 'resource_id', 'amount'}:
                raise ValueError('resource_amount needs resource_id and amount only.')
            amount = change['amount']
            if type(amount) is not int or not 1 <= amount <= 100:
                raise ValueError('Resource amount must be an integer from 1 to 100.')
            if change['resource_id'] not in resources:
                raise ValueError('Unknown resource ID.')
            key = (kind, change['resource_id'])
            resources[change['resource_id']]['amount'] = amount
        else:
            raise ValueError('Supported changes: task_duration, resource_amount. Use workspace code for other experiments.')
        if key in seen:
            raise ValueError('Duplicate change target.')
        seen.add(key)
    return result


def _setup(bundle, cases, epoch):
    from prosimos.simulation_setup import SimDiffSetup
    setup = SimDiffSetup(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), False, cases)
    setup.set_starting_datetime(_date(epoch))
    return setup


def _seed(seed):
    import numpy as np
    random.seed(seed)
    np.random.seed(seed)


def _run(bundle, folder, cases, epoch, arrivals, seed, success, sla):
    import pandas as pd
    from prosimos.simulation_engine import run_simpy_simulation
    from prosimos.warning_logger import warning_logger
    setup = _setup(bundle, cases, epoch)
    _seed(seed)
    warning_logger.clear_warnings()
    folder.mkdir()
    with (folder / 'simulation.csv').open('w') as log, (folder / 'statistics.csv').open('w') as stats:
        # Prosimos 2.1 returns early for fixed arrivals; explicitly flush its writers.
        env = run_simpy_simulation(setup, csv.writer(stats), csv.writer(log), arrivals)
        env.log_writer.force_write()
        env.log_info.save_joint_statistics(env)
    warnings = warning_logger.get_all_warnings()
    _write_json(folder / 'warnings.json', warnings)
    executions = setup.bpmn_graph.simulation_execution_stats
    complete = all(executions.get_element_executions(i, setup.bpmn_graph.end_event) > 0
                   and not any(env.all_process_states[i].tokens.values()) for i in range(cases))
    if not complete or any('Infinite loop' in w for w in warnings):
        raise ValueError('Simulation did not complete every case; inspect run artifacts.')
    df = pd.read_csv(folder / 'simulation.csv')
    df['end_time'] = pd.to_datetime(df.end_time, format='mixed', utc=True)
    ends = df.groupby('case_id').end_time.max().reindex(range(cases))
    if ends.isna().any():
        raise ValueError('Missing case traces.')
    starts = pd.Series([pd.Timestamp(epoch) + timedelta(seconds=a) for a in arrivals])
    cycles = (ends - starts).dt.total_seconds() / 3600
    success_ids = set(df.loc[df.activity == success, 'case_id']) if success else set()
    selected = cycles.loc[sorted(success_ids)] if success else cycles
    metrics = {'seed': seed, 'mean_cycle_hours': float(cycles.mean()),
               'p90_cycle_hours': float(cycles.quantile(.9)),
               'success_rate': len(success_ids) / cases if success else None,
               'successful_cycle_hours': float(selected.mean()) if success_ids else None,
               'sla_breach_rate': float((selected > sla).mean()) if sla is not None and len(selected) else None,
               'staffed_cost': None, 'completed_cases': cases}
    return metrics, setup, ends.max().to_pydatetime()


def compare_scenario(source: str, name: str, objective: str, assumption: str,
                     changes: list[dict], cases: int, seeds: list[int], starting_at: str,
                     success_activity: str | None = None, sla_hours: float | None = None,
                     costs: dict | None = None) -> dict:
    """Compare a copied baseline with explicit task-duration/resource-amount changes.
    source is a bundle directory in this workspace (including baseline/).
    costs, when supplied: currency, hourly_rates (every original resource ID),
    scenario_fixed_cost. Rates are supplied assumptions, never inferred defaults.
    """
    from scipy.stats import t
    from scenario_view import export_comparison
    root = output_root(ROOT).resolve()
    source = (root / source).resolve()
    if not source.is_relative_to(root):
        raise ValueError('Choose a model bundle within this workspace, including baseline/.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
        raise ValueError('Invalid experiment name.')
    if not objective.strip() or not assumption.strip():
        raise ValueError('Record the objective and intervention assumptions.')
    if type(cases) is not int or not 1 <= cases <= 5000:
        raise ValueError('cases must be 1..5000.')
    if not 3 <= len(seeds) <= 50 or len(set(seeds)) != len(seeds) or any(type(s) is not int or not 0 <= s < 1000000000 for s in seeds):
        raise ValueError('Supply 3..50 distinct integer seeds in [0, 1000000000).')
    _date(starting_at)
    if sla_hours is not None:
        _positive(sla_hours, 'sla_hours')
    for filename in ('model.bpmn', 'parameters.json'):
        if not (source / filename).resolve().is_relative_to(root):
            raise ValueError('Model files must remain within this workspace.')
    hashes = {f: _source_digest(source / f) for f in ('model.bpmn', 'parameters.json')}
    labels = {e.get('name') for e in ET.parse(source / 'model.bpmn').iter() if e.tag.rsplit('}', 1)[-1] == 'task'}
    if success_activity is not None and success_activity not in labels:
        raise ValueError('success_activity must be an existing activity label.')
    params = json.loads((source / 'parameters.json').read_text())
    revised = _revise(params, source / 'model.bpmn', changes)
    if costs is not None:
        ids = {r['id'] for p in params['resource_profiles'] for r in p['resource_list']}
        if set(costs) != {'currency', 'hourly_rates', 'scenario_fixed_cost'} or set(costs['hourly_rates']) != ids or not costs['currency'].strip():
            raise ValueError('Costs require currency, hourly_rates for every resource ID, and scenario_fixed_cost.')
        for value in [*costs['hourly_rates'].values(), costs['scenario_fixed_cost']]:
            _positive(value, 'cost', zero=True)
    output = (root / 'experiments' / name).resolve()
    if not output.is_relative_to(root):
        raise ValueError('Experiment output must remain within this workspace.')
    output.mkdir(parents=True, exist_ok=False)
    report = {'name': name, 'objective': objective, 'assumption': assumption, 'changes': changes,
              'source': str(source), 'source_sha256': hashes, 'costs': costs,
              'versions': {p: version(p) for p in ('prosimos', 'pix-framework')},
              'protocol': {'cases': cases, 'seeds': seeds, 'starting_at': starting_at,
                           'success_activity': success_activity, 'sla_hours': sla_hours,
                           'arrivals': 'Same generated arrival offsets within each pair; independent process RNG seeds.',
                           'process_seeds': 'baseline=3*seed+1, scenario=3*seed+2; arrival generation=seed',
                           'initial_state': 'Empty system, all arriving cases run to completion; no warm-up removal.',
                           'cycle': 'Arrival to final activity completion, hours.',
                           'success': 'Case contains the selected activity; this is a declared outcome proxy.',
                           'sla': 'Among successful cases if an outcome is supplied, otherwise all cases.',
                           'cost': 'Scheduled resource hours through the later completion of each pair, at supplied rates; scenario adds fixed implementation cost. Idle scheduled time is included.',
                           'uncertainty': 'Student-t 95% interval of paired replicate mean differences; simulation noise only.'},
              'baseline': {'runs': []}, 'scenario': {'runs': []}, 'comparison': {},
              'warnings': ['All results are model predictions, not observed business effects.',
                           'Historical fidelity does not establish intervention validity; model errors need not cancel.',
                           'Task duration changes assume the proposed intervention achieves that reduction without changing quality or routing.',
                           'Success mix can differ between independent process draws; compare outcome rate alongside successful-case duration.'],
              'status': 'running'}
    if costs is None:
        report['warnings'].append('Costs not supplied. Existing fitted cost defaults are not used; no financial recommendation.')
    _write_json(output / 'report.json', report)
    try:
        for label, config in [('baseline', params), ('scenario', revised)]:
            bundle = output / label
            bundle.mkdir()
            shutil.copyfile(source / 'model.bpmn', bundle / 'model.bpmn')
            if costs:
                config = copy.deepcopy(config)
                for profile in config['resource_profiles']:
                    for resource in profile['resource_list']:
                        resource['cost_per_hour'] = costs['hourly_rates'][resource['id']]
            _write_json(bundle / 'parameters.json', config)
        for seed in seeds:
            setup = _setup(output / 'baseline', cases, starting_at)
            _seed(seed)
            elapsed, arrivals = 0.0, []
            for _ in range(cases):
                arrivals.append(elapsed)
                elapsed += setup.next_arrival_time(_date(starting_at) + timedelta(seconds=elapsed))
            _write_json(output / f'arrivals-{seed}.json', arrivals)
            pair = []
            for index, label in enumerate(('baseline', 'scenario')):
                metrics, setup, end = _run(output / label, output / label / f'seed-{seed}', cases,
                                           starting_at, arrivals, seed * 3 + index + 1, success_activity, sla_hours)
                metrics['seed'] = seed
                pair.append((metrics, setup, end))
            if costs:
                horizon = max(p[2] for p in pair)
                for index, (metrics, setup, _) in enumerate(pair):
                    metrics['staffed_cost'] = sum(setup.get_resource_calendar(r).find_working_time(_date(starting_at), horizon)
                                                / 3600 * info.cost_per_hour for r, info in setup.resources_map.items())
                    metrics['staffed_cost'] += costs['scenario_fixed_cost'] if index else 0
                    metrics['cost_horizon_end'] = horizon.isoformat()
            for label, (metrics, _, _) in zip(('baseline', 'scenario'), pair):
                report[label]['runs'].append(metrics)
            _write_json(output / 'report.json', report)
        for metric in ('mean_cycle_hours', 'p90_cycle_hours', 'success_rate', 'successful_cycle_hours', 'sla_breach_rate', 'staffed_cost'):
            a = [r[metric] for r in report['baseline']['runs']]
            b = [r[metric] for r in report['scenario']['runs']]
            if None in a or None in b:
                report['comparison'][metric] = None
                continue
            delta = [y - x for x, y in zip(a, b)]
            report['comparison'][metric] = {'baseline_mean': mean(a), 'scenario_mean': mean(b),
                                            'delta': mean(delta), 'ci95_half_width': float(t.ppf(.975, len(delta)-1) * stdev(delta) / math.sqrt(len(delta)))}
        if hashes != {f: _source_digest(source / f) for f in hashes}:
            raise ValueError('Source changed during experiment.')
        report['status'] = 'completed_model_comparison'
        report['html'] = export_comparison(report, output)
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        _write_json(output / 'report.json', report)
    return {'status': report['status'], 'report': str(output / 'report.json'), 'html': report['html'],
            'comparison': report['comparison'], 'warnings': report['warnings']}

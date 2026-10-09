"""Numerical diagnostics for an existing model; no fitting or pass threshold.

Distances use the official AutomatedProcessImprovement/log-distance-measures
package. Completion variants map the API's start field to the completion column
explicitly; no observed starts are imputed, copied, or persisted.
"""
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from statistics import mean, pstdev

from environment import _bundle, _date, _write_json

# Each entry specifies a quantity, rather than choosing a metric policy.
METRICS = {
    'ngram': {'units': 'dimensionless [0,1]',
              'definition': 'Trigram count L1 distance divided by total trigram counts of both logs, including trace boundary markers; completion order.',
              'caveats': 'Completion order is not causal execution order; ties have unknown order. Counts are not per-case frequencies; unequal cohort sizes can produce distance for the same variant mix.'},
    'completion_span': {'units': 'hours (1-hour bins)',
                        'definition': 'Wasserstein distance of last minus first completion per case.',
                        'caveats': 'Excludes service before first completion; not full cycle time.'},
    'first_completion_arrivals': {'units': 'hours (1-hour bins)',
                                 'definition': 'Wasserstein distance of first completions per case, aligning each log to its own earliest completion.',
                                 'caveats': 'First completion is an arrival proxy, not a measured arrival. Origin alignment removes epoch difference, not horizon or cohort thinning.'},
    'relative_completion': {'units': 'hours (1-hour bins)',
                            'definition': 'Wasserstein distance of event completions relative to first completion of their case.',
                            'caveats': 'Events weighted equally; excludes service before first completion.'},
    'circadian_completion': {'units': 'hours of day',
                             'definition': 'Mean of seven weekday Wasserstein distances of completion hour in UTC.',
                             'caveats': 'UTC, not local working time. Official metric assigns 23 hours when only one log has events on a weekday; absent in both counts zero. Not a circular-hour distance.'},
    'cycle_time': {'units': 'hours (1-hour bins)',
                   'definition': 'Wasserstein distance of last completion minus first measured start per case.',
                   'caveats': 'Requires every observed start; start-to-end elapsed time includes waiting and off-hours.'},
    'arrivals': {'units': 'hours (1-hour bins)',
                'definition': 'Wasserstein distance of first measured start per case, aligning each log to its own earliest start.',
                'caveats': 'Requires every observed start; first activity start is not necessarily process arrival.'},
}


def _read(path):
    import pandas as pd
    frame = pd.read_csv(path, dtype={'case_id': str, 'activity': str, 'resource': str},
                        keep_default_na=False, na_values={'start_time': ['']})
    frame.columns = frame.columns.str.strip()
    if frame.empty or not {'case_id', 'activity', 'end_time'} <= set(frame):
        raise ValueError(f'{path.name} needs nonempty cases, activities and completions.')
    if frame[['case_id', 'activity', 'end_time']].isna().any().any() or (frame[['case_id', 'activity', 'end_time']] == '').any().any():
        raise ValueError(f'{path.name} has missing case, activity or completion values.')
    for column in ('start_time', 'end_time'):
        if column in frame:
            # Reject naive timestamps rather than silently assigning UTC.
            values = frame[column].dropna()
            for value in values:
                _date(value)
            frame[column] = pd.to_datetime(frame[column], utc=True, format='mixed')
    if 'start_time' in frame and (frame.start_time > frame.end_time).any():
        raise ValueError(f'{path.name} has starts after completions.')
    return frame


def _distances(observed, generated, metrics):
    from log_distance_measures.config import EventLogIDs, AbsoluteTimestampType
    from log_distance_measures.n_gram_distribution import n_gram_distribution_distance
    from log_distance_measures.cycle_time_distribution import cycle_time_distribution_distance
    from log_distance_measures.case_arrival_distribution import case_arrival_distribution_distance
    from log_distance_measures.relative_event_distribution import relative_event_distribution_distance
    from log_distance_measures.circadian_event_distribution import circadian_event_distribution_distance
    completion_ids = EventLogIDs(case='case_id', activity='activity', start_time='end_time', end_time='end_time')
    measured_ids = EventLogIDs(case='case_id', activity='activity', start_time='start_time', end_time='end_time')
    result = {}
    for metric in metrics:
        ids = measured_ids if metric in ('cycle_time', 'arrivals') else completion_ids
        args = (observed, ids, generated, ids)
        if metric == 'ngram':
            distance = n_gram_distribution_distance(*args, n=3, normalize=True)
        elif metric in ('completion_span', 'cycle_time'):
            distance = cycle_time_distribution_distance(*args, bin_size=timedelta(hours=1))
        elif metric in ('first_completion_arrivals', 'arrivals'):
            # Absolute arrival distance needs a common origin; use relative
            # elapsed arrivals without disturbing circadian timestamps.
            left, right = observed.copy(), generated.copy()
            origin = observed[ids.start_time].min()
            right[ids.start_time] += origin - generated[ids.start_time].min()
            distance = case_arrival_distribution_distance(left, ids, right, ids)
        elif metric == 'relative_completion':
            distance = relative_event_distribution_distance(*args, discretize_type=AbsoluteTimestampType.END)
        else:
            distance = circadian_event_distribution_distance(*args, discretize_type=AbsoluteTimestampType.END)
        if not math.isfinite(distance):
            raise ValueError(f'{metric} returned a non-finite distance.')
        result[metric] = float(distance)
    return result


def _digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def evaluate_environment(name: str, split: str = 'validation', metrics: list[str] | None = None,
                         seeds: list[int] | None = None, cases: int | None = None,
                         starting_at: str | None = None) -> dict:
    """Compare a built model with an explicitly chosen observed split and seeds.

    metrics=None returns the metric catalog without writing or simulating.
    For a run, supply metric names and unique seeds (0..2**32-1). cases defaults
    to observed split case count. starting_at defaults to the earliest observed
    completion: a model epoch, not measured arrival. Writes unique evaluations/
    artifacts and never overwrites baseline/model/split files. No pass threshold.
    """
    if split not in ('train', 'validation', 'test', 'heldout'):
        raise ValueError('split must be train, validation, test, or legacy heldout.')
    bundle = _bundle(name)
    observed_path = bundle / f'{split}.csv'
    observed = _read(observed_path)
    measured = 'start_time' in observed and observed.start_time.notna().all()
    available = {key: value for key, value in METRICS.items() if measured or key not in ('cycle_time', 'arrivals')}
    if metrics is None:
        return {'name': name, 'split': split, 'available_metrics': available,
                'unavailable': {} if measured else {'cycle_time': 'Missing measured starts', 'arrivals': 'Missing measured starts'},
                'resource_workload': 'Not implemented: synthetic/missing resource identities and estimated starts do not establish measured workload.',
                'requires': 'Choose metrics and explicit seeds to run. No validation or pass threshold is selected automatically.'}
    if not isinstance(metrics, list) or not metrics or any(not isinstance(m, str) or m not in available for m in metrics) or len(set(metrics)) != len(metrics):
        raise ValueError(f'metrics must be a nonempty unique list from {list(available)}.')
    if not isinstance(seeds, list) or not seeds or len(seeds) > 100 or any(type(s) is not int or not 0 <= s < 2**32 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('Provide 1..100 unique integer seeds in 0..2**32-1.')
    if cases is None:
        cases = int(observed.case_id.nunique())
    if type(cases) is not int or not 1 <= cases <= 50000:
        raise ValueError('cases must be an integer from 1 to 50000.')
    epoch = _date(starting_at) if starting_at is not None else observed.end_time.min().to_pydatetime()
    inputs = {path.name: _digest(path) for path in (observed_path, bundle / 'model.bpmn', bundle / 'parameters.json')}
    parent = bundle / 'evaluations'
    parent.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f'{split}-', dir=parent))
    report = {'status': 'running', 'name': name, 'split': split, 'directory': str(output),
              'cases': cases, 'observed_cases': int(observed.case_id.nunique()), 'observed_events': len(observed),
              'seeds': seeds, 'starting_at': epoch.isoformat(),
              'observed_completion_range': [observed.end_time.min().isoformat(), observed.end_time.max().isoformat()],
              'boundary_policy': 'Simulated system starts empty with no warm-up and runs the requested cases to completion. No observed or simulated boundary events are excluded. Observed and simulated horizons and case counts may differ; sampled observed cohorts may include cases that began before their first recorded completion.',
              'epoch_policy': 'Explicit model epoch' if starting_at is not None else 'Earliest observed completion; model epoch, not measured arrival',
              'input_sha256': inputs, 'metric_definitions': {m: METRICS[m] for m in metrics},
              'versions': {p: version(p) for p in ('log-distance-measures', 'prosimos', 'numpy', 'pandas')},
              'source': 'https://github.com/AutomatedProcessImprovement/log-distance-measures',
              'interpretation': 'Numerical diagnostics; lower distances mean closer distributions under these definitions. No automatic pass threshold. Sampled cohorts do not measure full process workload.',
              'replications': []}
    _write_json(output / 'report.json', report)
    try:
        for seed in seeds:
            run = output / f'seed-{seed}'
            run.mkdir()
            process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--simulate',
                                      str(bundle.resolve()), str(run.resolve()), str(seed), str(cases), epoch.isoformat()],
                                     cwd=run, env={**os.environ, 'PYTHONHASHSEED': str(seed)},
                                     capture_output=True, text=True, timeout=600)
            (run / 'simulation.log').write_text(process.stdout + process.stderr)
            if process.returncode:
                raise RuntimeError(f'Seed {seed} failed; see {run / "simulation.log"}.')
            generated = _read(run / 'simulation.csv')
            if generated.case_id.nunique() != cases or 'start_time' not in generated or generated.start_time.isna().any():
                raise ValueError(f'Seed {seed} generated incomplete cases or starts.')
            report['replications'].append({'seed': seed, 'cases': int(generated.case_id.nunique()),
                                           'events': len(generated),
                                           'completion_range': [generated.end_time.min().isoformat(), generated.end_time.max().isoformat()], 'metrics': _distances(observed, generated, metrics),
                                           'metric_definitions': report['metric_definitions']})
            _write_json(output / 'report.json', report)
        report['summary'] = {m: {'mean': mean(r['metrics'][m] for r in report['replications']),
                                 'std': pstdev(r['metrics'][m] for r in report['replications']),
                                 'std_definition': 'Population standard deviation across supplied replications',
                                 'replications': len(seeds), **METRICS[m]} for m in metrics}
        report['status'] = 'evaluated'
    except Exception as error:
        report['status'] = 'evaluation_failed'
        report['error'] = str(error)
        _write_json(output / 'report.json', report)
        raise
    _write_json(output / 'report.json', report)
    return report


def _simulate(bundle, output, seed, cases, epoch):
    import numpy as np
    from prosimos.simulation_engine import run_simulation
    random.seed(seed)
    np.random.seed(seed)
    run_simulation(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), cases,
                   str(output / 'statistics.csv'), str(output / 'simulation.csv'), starting_at=epoch)


def _selfcheck():
    import pandas as pd
    from pandas.testing import assert_frame_equal
    with tempfile.TemporaryDirectory() as folder:
        sample = Path(folder) / 'literal.csv'
        sample.write_text('case_id,activity,resource,start_time,end_time\nNA,null,NA,,2020-01-06T08:00:00Z\n')
        parsed = _read(sample)
        assert parsed.case_id.iloc[0] == 'NA' and parsed.activity.iloc[0] == 'null'
        assert parsed.resource.iloc[0] == 'NA' and parsed.start_time.isna().all()
    original = pd.DataFrame({'case_id': ['a', 'a', 'b'], 'activity': ['A', 'B', 'A'],
                             'end_time': pd.to_datetime(['2020-01-06T08:00Z', '2020-01-06T10:00Z', '2020-01-07T08:00Z'])})
    saved = original.copy(deep=True)
    completion = list(METRICS)[:5]
    assert all(value == 0 for value in _distances(original, original.copy(), completion).values())
    shifted = original.copy()
    shifted.end_time += timedelta(days=700)
    assert all(value == 0 for value in _distances(original, shifted, completion).values())
    changed = original.copy()
    changed.loc[1, 'activity'] = 'C'
    assert _distances(original, changed, ['ngram'])['ngram'] > 0
    assert_frame_equal(original, saved)
    print('validation selfcheck passed')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selfcheck']:
        _selfcheck()
    elif len(sys.argv) == 7 and sys.argv[1] == '--simulate':
        _simulate(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
    else:
        raise SystemExit('Use --selfcheck or call evaluate_environment().')

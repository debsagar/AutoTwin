"""Score one evaluation folder against the pre-registered Stage 1 pass limits (PROJECT-LOG 2026-10-14).
usage: python pass_check.py <environment dir> <evaluation dir>
"""
import json, sys
from pathlib import Path
from statistics import mean, pstdev
import pandas as pd

env, ev = Path(sys.argv[1]), Path(sys.argv[2])
report = json.loads((ev / 'report.json').read_text())
split = report['split']
scope = json.loads((env / 'manifest.json').read_text())['scope']
win = scope['partitions'][split]
by_start = 'first observation' in scope['selection']  # selection='started': same start-only rule on both sides
lo, hi = pd.Timestamp(win['start']), pd.Timestamp(win['end'])
weeks = (hi - lo).days / 7


def cases(path):
    d = pd.read_csv(path, usecols=['case_id', 'end_time'])
    d['end_time'] = pd.to_datetime(d['end_time'], utc=True, format='mixed')
    g = d.groupby('case_id')['end_time'].agg(['min', 'max'])
    inside = g[(g['min'] >= lo) & ((g['min'] < hi) if by_start else (g['max'] < hi))]  # same rule prepare_environment applied to the real cases
    week = ((inside['min'] - lo).dt.days // 7)
    weekly = week[week < int(weeks)].value_counts().reindex(range(int(weeks)), fill_value=0)  # full weeks only
    return (inside['max'] - inside['min']).dt.total_seconds() / 3600, weekly


real_dur, real_n = cases(env / f'{split}.csv')
rows = []
for seed in sorted(ev.glob('seed-*')):
    dur, n = cases(seed / 'simulation.csv')
    worst = max(n / real_n - 1, key=abs)  # the week furthest from real, as a signed ratio - 1
    rows.append({'median': dur.median() / real_dur.median(), 'mean': dur.mean() / real_dur.mean(), 'weekly': 1 + worst})

out = {'split': split, 'seeds': len(rows), 'real_cases_per_week': real_n.tolist(),
       'real_median_h': round(real_dur.median(), 1), 'real_mean_h': round(real_dur.mean(), 1)}
ok = True
for k, limit in [('median', .25), ('mean', .25), ('weekly', .20)]:
    vals = [r[k] for r in rows]
    m, sd = mean(vals), pstdev(vals)
    passed = abs(m - 1) <= limit and sd <= .10 * m
    ok &= passed
    out[k] = {'ratio_mean' if k != 'weekly' else 'worst_week_ratio_mean': round(m, 3), 'sd': round(sd, 3), 'pass': passed}
ng = report['summary']['ngram']['mean']
out['trigram'] = {'value': round(ng, 3), 'pass': ng <= .25}
loops = sum(p.read_text().count('Infinite loop') for p in ev.glob('seed-*/*warn*'))
out['clean_runs'] = {'loop_terminations': loops, 'pass': loops == 0}  # ponytail: Prosimos' own loop-kill warning only; end-event check not done here
out['empty_cases_per_seed'] = [r.get('empty_cases', 0) for r in report['replications']]
out['PASS'] = ok and out['trigram']['pass'] and out['clean_runs']['pass']
print(json.dumps(out, indent=1, default=bool))

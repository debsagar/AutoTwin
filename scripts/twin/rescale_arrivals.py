"""Rescale a bundle's case-inter-arrival distribution so the expected arrivals per week equal the TRAIN
cases per week. Reason: Prosimos samples inter-arrival gaps in arrival-calendar-open time, while the
outlier-filtered pix fit (arrival_filter_outliers=True) gives a mean that yields ~1.3x too many cases/week
(and the unfiltered fit ~0.65x). Uses train.csv, the train window length and the arrival calendar only.
usage: python rescale_arrivals.py <source bundle> <target bundle>"""
import json, shutil, sys
from datetime import datetime
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
shutil.copytree(src, dst, ignore=shutil.ignore_patterns('evaluations', 'delay-work'))
p = json.loads((dst / 'parameters.json').read_text())
m = json.loads((dst / 'manifest.json').read_text())
w = m['scope']['partitions']['train']
weeks = (datetime.fromisoformat(w['end']) - datetime.fromisoformat(w['start'])).total_seconds() / (7 * 86400)
per_week = m['scope']['split']['train']['cases'] / weeks
t = lambda s: sum(int(x) * f for x, f in zip(s.split(':'), (3600, 60, 1)))
open_s = sum(t(c['endTime']) - t(c['beginTime']) for c in p['arrival_time_calendar'])  # one entry per weekday here
assert all(c['from'] == c['to'] for c in p['arrival_time_calendar'])
d = p['arrival_time_distribution']
assert d['distribution_name'] == 'expon', d
old = d['distribution_params'][0]['value']
new = open_s / per_week
d['distribution_params'][0]['value'] = new
d['distribution_params'][2]['value'] = max(d['distribution_params'][2]['value'], 20 * new)  # keep truncation negligible
(dst / 'parameters.json').write_text(json.dumps(p))
m['name'] = dst.name
m['revision'] = {'source_environment': src.name, 'previous_revision': m.get('revision'),
                 'reason': f'Inter-arrival mean rescaled {old:.1f}s -> {new:.1f}s so expected arrivals = train {per_week:.1f} cases/week over {open_s/3600:.0f} calendar-open hours/week.'}
(dst / 'manifest.json').write_text(json.dumps(m, indent=2))
print(m['revision']['reason'])

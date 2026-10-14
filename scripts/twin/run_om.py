"""Sales (Order Management) twin: prepare + build, then score a split with pass_check.
usage: python scripts/twin/run_om.py prep <name> <settings-json> | val <name> | test <name>"""
import json, sys, subprocess, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import environment as env, validation as val
METRICS = ['ngram', 'completion_span', 'first_completion_arrivals', 'relative_completion', 'circadian_completion',
           'absolute_completion']
# Fixed from monthly order counts only (PROJECT-LOG 2026-10-14 Step 4 decision).
PARTS = {'train': {'start': '2023-06-01', 'end': '2023-10-01'},
         'validation': {'start': '2023-10-01', 'end': '2023-12-01'},
         'test': {'start': '2023-12-01', 'end': '2024-02-01'}}
mode, name = sys.argv[1], sys.argv[2]
t = time.time()


def score(split, seeds):
    r = val.evaluate_environment(name, split, METRICS, seeds)
    print('evaluated', round(time.time() - t), r['directory'], flush=True)
    print(subprocess.run([sys.executable, str(ROOT / 'scripts/twin/pass_check.py'), str(env._bundle(name)), r['directory']],
                         capture_output=True, text=True).stdout, flush=True)


if mode == 'prep':
    m = env.prepare_environment('data/sales/om/orders.xes', name, PARTS, 5000, 'concept:name', None, 'started')
    print('prepared', {k: v['cases'] for k, v in m['scope']['split'].items()}, m['scope']['excluded'], m['quality'], flush=True)
    b = env.build_environment(name, True, json.loads(sys.argv[3]))   # completion-only log: PIX start estimation
    print('built', round(time.time() - t), b.get('status'), str(b.get('error', ''))[-1500:], flush=True)
    if b.get('status') == 'generated_unvalidated' and '--noval' not in sys.argv:
        score('validation', [11, 22, 33])
else:
    score(mode if mode == 'test' else 'validation', [101, 202, 303, 404, 505] if mode == 'test' else [11, 22, 33])

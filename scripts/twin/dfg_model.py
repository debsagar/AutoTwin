"""Replace a bundle's control flow with a first-order Markov chain over activities (directly-follows
frequencies from train.csv, the control-flow model ServiceMiner uses). Keeps task ids, resources,
calendars and arrivals from the source bundle.
usage: python dfg_model.py <source bundle> <target bundle>"""
import html, json, re, shutil, sys
from xml.sax.saxutils import quoteattr
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir()
for f in ['train.csv', 'validation.csv', 'test.csv', 'train_fitted.csv', 'manifest.json']:
    if (src / f).exists(): shutil.copy(src / f, dst / f)
tasks = dict((html.unescape(name), tid) for tid, name in re.findall(r'<bpmn:task id="([^"]+)" name="([^"]+)"', (src / 'model.bpmn').read_text()))

train = pd.read_csv(src / 'train.csv')
train['start_time'] = pd.to_datetime(train.start_time, utc=True, format='mixed')
follows = defaultdict(Counter)  # 'START' and 'END' are the case boundaries
for _, trace in train.sort_values(['case_id', 'start_time', 'end_time']).groupby('case_id'):
    seq = ['START'] + [a for a in trace.activity if a in tasks] + ['END']
    for a, b in zip(seq, seq[1:]):
        follows[a][b] += 1

flows, nodes, probs = [], [], []
inc, out = defaultdict(list), defaultdict(list)
def flow(a, b):
    fid = f'flow_{len(flows)}'
    flows.append((fid, a, b)); out[a].append(fid); inc[b].append(fid)
    return fid
join = {name: f'join_{i}' for i, name in enumerate(tasks)}
for name, tid in tasks.items():
    flow(join[name], tid)
for a in ['START'] + list(tasks):
    node = 'start' if a == 'START' else tasks[a]
    split = f'split_{len(probs)}'
    flow(node, split)
    total = sum(follows[a].values()) or 1
    paths = [{'path_id': flow(split, 'end' if b == 'END' else join[b]), 'value': n / total} for b, n in follows[a].items()]
    if not paths:  # activity never seen followed by anything: let it end
        paths = [{'path_id': flow(split, 'end'), 'value': 1.0}]
    probs.append({'gateway_id': split, 'probabilities': paths})

def el(tag, i, name=''):
    body = ''.join(f'<incoming>{f}</incoming>' for f in inc[i]) + ''.join(f'<outgoing>{f}</outgoing>' for f in out[i])
    return f'<{tag} id="{i}"{f" name={quoteattr(name)}" if name else ""}>{body}</{tag}>'
parts = [el('startEvent', 'start'), el('endEvent', 'end')]
parts += [el('task', tid, name) for name, tid in tasks.items()]
parts += [el('exclusiveGateway', g) for g in list(join.values()) + [p['gateway_id'] for p in probs]]
parts += [f'<sequenceFlow id="{f}" sourceRef="{a}" targetRef="{b}"/>' for f, a, b in flows]
(dst / 'model.bpmn').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" '
                                'targetNamespace="http://autotwin/dfg"><process id="dfg" isExecutable="false">' + ''.join(parts) + '</process></definitions>\n')
params = json.loads((src / 'parameters.json').read_text())
params['gateway_branching_probabilities'] = probs
(dst / 'parameters.json').write_text(json.dumps(params))
m = json.loads((dst / 'manifest.json').read_text()); m['name'] = dst.name
m['revision'] = {'source_environment': src.name, 'reason': 'Control flow replaced by a directly-follows Markov chain fit on train.csv (ServiceMiner-style); resources, calendars, arrivals unchanged.'}
(dst / 'manifest.json').write_text(json.dumps(m, indent=2))
print({a: dict(c.most_common(3)) for a, c in follows.items()})

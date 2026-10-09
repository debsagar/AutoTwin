"""Export an offline replay of a generated process environment."""
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def export_view(name: str) -> dict:
    if not name or Path(name).name != name or name in {'.', '..'}:
        raise ValueError('name must be one environment directory name')
    bundle = ROOT / 'runs' / 'environments' / name
    manifest = json.loads((bundle / 'manifest.json').read_text())
    if manifest.get('status') != 'generated_unvalidated':
        raise ValueError('Export requires a successful current build; stale artifacts are not exported.')
    tree = ET.parse(bundle / 'model.bpmn')
    nodes, edges, positions = [], [], {}
    for element in tree.iter():
        kind = element.tag.rsplit('}', 1)[-1]
        if kind == 'BPMNShape':
            bounds = next((child for child in element if child.tag.endswith('Bounds')), None)
            if bounds is not None:
                positions[element.get('bpmnElement')] = [float(bounds.get('x')), float(bounds.get('y'))]
        if kind in {'task', 'startEvent', 'endEvent', 'exclusiveGateway', 'parallelGateway', 'inclusiveGateway'}:
            nodes.append({'id': element.get('id'), 'name': element.get('name') or kind, 'kind': kind})
        elif kind == 'sequenceFlow':
            edges.append([element.get('sourceRef'), element.get('targetRef')])
    # Render activity stations; connect them through intervening routing gateways.
    visible = {node['id'] for node in nodes if 'Gateway' not in node['kind']}
    adjacency = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
    collapsed = set()
    for source in visible:
        pending, seen = list(adjacency.get(source, [])), set()
        while pending:
            target = pending.pop()
            if target in seen:
                continue
            seen.add(target)
            if target in visible:
                collapsed.add((source, target))
            else:
                pending.extend(adjacency.get(target, []))
    nodes = [node for node in nodes if node['id'] in visible]
    edges = sorted(collapsed)
    # Miners can emit placeholder drawing coordinates; use a disclosed grid then.
    if len(set(map(tuple, positions.values()))) < 2:
        positions = {}
    for index, node in enumerate(nodes):
        node['position'] = positions.get(node['id'], [index % 6 * 240, index // 6 * 180])
    with (bundle / 'simulation.csv').open(newline='') as stream:
        records = list(csv.DictReader(stream))
    for row in records:
        for key in ('enable_time', 'start_time', 'end_time'):
            row[key] = datetime.fromisoformat(row[key]).timestamp() * 1000
    report = json.loads((bundle / 'report.json').read_text())
    model_hash = hashlib.sha256((bundle / 'model.bpmn').read_bytes()).hexdigest()
    report['evaluations'] = []
    for path in sorted((bundle / 'evaluations').glob('*/report.json')):
        evaluation = json.loads(path.read_text())
        inputs = evaluation.get('input_sha256', {})
        if evaluation.get('status') == 'evaluated' and inputs.get('model.bpmn') == model_hash and all(
                (bundle / name).is_file() and hashlib.sha256((bundle / name).read_bytes()).hexdigest() == digest
                for name, digest in inputs.items()):
            report['evaluations'].append({k: evaluation[k] for k in
                ('split', 'cases', 'seeds', 'starting_at', 'summary', 'interpretation')})
    data = {'name': name, 'nodes': nodes, 'edges': edges, 'records': records,
            'report': report, 'manifest': manifest}
    # Embedded scripts stay inert even when a source label contains HTML.
    encoded = json.dumps(data).replace('<', '\\u003c')
    template = (ROOT / 'visual' / 'template.html').read_text()
    html = template.replace('/* THREE_LIBRARY */', (ROOT / 'visual/vendor/three.min.js').read_text())
    html = html.replace('/* REPLAY_DATA */', encoded).replace('/* REPLAY_SCRIPT */', (ROOT / 'visual/replay.js').read_text())
    output = bundle / 'environment.html'
    output.write_text(html)
    return {'name': name, 'html': str(output), 'cases': len({r['case_id'] for r in records}), 'events': len(records)}


def _self_check():
    """Small export check: hostile labels, placeholder layout and offline assets."""
    import tempfile
    global ROOT
    original = ROOT
    with tempfile.TemporaryDirectory() as temporary:
        ROOT = Path(temporary)
        (ROOT / 'visual').symlink_to(original / 'visual', target_is_directory=True)
        bundle = ROOT / 'runs/environments/check'
        bundle.mkdir(parents=True)
        (bundle / 'model.bpmn').write_text('<definitions><process><task id="a" name="&lt;/script&gt;"/><task id="b" name="B"/><sequenceFlow sourceRef="a" targetRef="b"/></process></definitions>')
        (bundle / 'simulation.csv').write_text('case_id,activity,enable_time,start_time,end_time,resource\n0,B,2020-01-01T00:00:00+00:00,2020-01-01T01:00:00+00:00,2020-01-01T02:00:00+00:00,R\n')
        for name in ('report.json', 'manifest.json'):
            (bundle / name).write_text(json.dumps({'status': 'generated_unvalidated'}))
        try:
            result = export_view('check')
            html = Path(result['html']).read_text()
            encoded = html.split('const DATA=', 1)[1].split(';\n', 1)[0]
            data = json.loads(encoded)
            assert data['nodes'][0]['name'] == '</script>'
            assert data['nodes'][0]['position'] != data['nodes'][1]['position']
            assert result['events'] == result['cases'] == 1
            assert '/* THREE_LIBRARY */' not in html
            try:
                export_view('../outside')
            except ValueError:
                pass
            else:
                raise AssertionError('accepted path traversal')
        finally:
            ROOT = original


if __name__ == '__main__':
    _self_check()
    print('viewer self-check passed')

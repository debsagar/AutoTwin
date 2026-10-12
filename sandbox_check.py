"""Real isolation checks; requires docker build -t autotwin-worker:local ."""
from pathlib import Path
import json
import shutil
import uuid
import hashlib
from unittest.mock import patch
import workspace
from sandbox import call, ROOT

w = ROOT / 'runs/workspaces' / ('sandbox-check-' + uuid.uuid4().hex)
w.mkdir(parents=True)
try:
    r = call(w, 'execute', {'command': '''python - <<'CODE'
import os, socket
from pathlib import Path
assert not Path('/data/autotwin/.env').exists()
assert not Path('/var/run/docker.sock').exists()
assert not any('API_KEY' in k for k in os.environ)
assert not Path('/home/azureuser').exists()
assert len(list(Path('/data/autotwin/runs/workspaces').iterdir())) == 1
for p in ['/data/autotwin/data/sandbox-write-check', '/data/autotwin/environment.py']:
 try:
  with open(p,'a') as f:f.write('forbidden')
 except OSError:pass
 else:raise AssertionError(p)
try: socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError:pass
else:raise AssertionError('network escape')
import pm4py, prosimos, pix_framework
Path('proof.txt').write_text('persisted')
print('isolation passed')
CODE'''})
    assert r['exit_code'] == 0, r
    assert (w/'proof.txt').read_text() == 'persisted'
    r = call(w, 'read_file', {'file_path': str(w/'proof.txt')})
    assert r['exit_code'] == 0 and 'persisted' in r['output'], r
    r = call(w, 'write_file', {'file_path': str(w/'second.txt'), 'content': 'native write'})
    assert r['exit_code'] == 0 and (w/'second.txt').read_text() == 'native write', r
    r = call(w, 'inspect_log_scope', {'path': 'data/benchmark/p2p_synthetic.xes'})
    assert r['exit_code'] == 0 and '1000' in r['output'], r
    r = call(w, 'prepare_environment', {'path':'data/benchmark/p2p_synthetic.xes', 'name':'proof',
             'partitions':{'train':{'start':'2023-01-01','end':'2023-02-01'},
                           'validation':{'start':'2023-02-01','end':'2023-03-01'}}})
    assert r['exit_code'] == 0, r
    r = call(w, 'build_environment', {'name':'proof', 'settings':{'discovery_method':'heuristics'}})
    assert r['exit_code'] == 0 and (w/'environments/proof/model.bpmn').exists(), r
    assert (w/'environments/proof/simulation.csv').stat().st_size > 100
    print('Sandbox checks passed: isolation, network, imports, persistence, file tools, process tool.')
finally:
    shutil.rmtree(w)

# Checkpoint sessions see only the selected frozen baseline, never raw/reference data.
thread = 'checkpoint-check-' + uuid.uuid4().hex
w = ROOT / 'runs/workspaces' / thread
binding = ROOT / '.dcode/checkpoint-bindings' / (thread + '.json')
source = workspace.validate_checkpoint('p2p_heuristics_v1')
def hashes():
    return {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob('*') if p.is_file()}
before = hashes()
try:
    with patch.object(workspace, 'requested_checkpoint', source.name):
        assert workspace.bind_checkpoint(thread) == source
    w.mkdir(parents=True)
    assert not list(w.iterdir())
    r = call(w, 'execute', {'command': '''python - <<'CODE'
from pathlib import Path
import json
assert Path('baseline/checkpoint.json').is_file()
assert json.loads(Path('baseline/checkpoint.json').read_text())['status'] == 'frozen_development_baseline'
assert not Path('/data/autotwin/data').exists()
assert not Path('/data/autotwin/data/benchmark/reference').exists()
assert not Path('/data/autotwin/runs/checkpoints').exists()
assert not Path('/data/autotwin/.dcode').exists()
assert len(list(Path('/data/autotwin/runs/workspaces').iterdir())) == 1
for path in ['baseline/checkpoint.json', 'baseline/new-file']:
 try: Path(path).write_text('must fail')
 except OSError: pass
 else: raise AssertionError('baseline writable: ' + path)
Path('report.md').write_text('fresh checkpoint task')
CODE'''})
    assert r['exit_code'] == 0, r
    with patch.object(workspace, 'requested_checkpoint', None):
        assert workspace.bind_checkpoint(thread) == source
    r = call(w, 'read_file', {'file_path': str(w / 'report.md')})
    assert r['exit_code'] == 0 and 'fresh checkpoint task' in r['output'], r
    r = call(w, 'write_file', {'file_path': str(w / 'baseline/checkpoint.json'), 'content': 'must fail'})
    assert r['exit_code'] != 0, r
    assert hashes() == before
    print('Checkpoint sandbox checks passed: readonly baseline, unchanged source, persistent binding, no siblings/reference data.')
finally:
    shutil.rmtree(w, ignore_errors=True)
    binding.unlink(missing_ok=True)

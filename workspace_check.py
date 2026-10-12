"""Check routing without a model; sandbox_check.py checks actual isolation."""
import asyncio
import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from langgraph.prebuilt.tool_node import ToolCallRequest
import workspace


def request(thread, name, args):
    return ToolCallRequest(tool_call={'name': name, 'args': args, 'id': 'check', 'type': 'tool_call'},
                           tool=None, state={}, runtime=SimpleNamespace(context={'thread_id': thread}))


async def check(root):
    middleware = workspace.middleware()
    async def forbidden(req):
        raise AssertionError('Sandbox tool reached host handler')
    def capture(folder, name, args):
        return {'exit_code': 0, 'workspace': str(folder), 'name': name, 'args': args}
    with patch('sandbox.call', capture):
        a, b = await asyncio.gather(*[
            middleware.awrap_tool_call(request(t, 'execute', {'command': 'python probe.py'}), forbidden)
            for t in ['one', 'two']])
        a, b = json.loads(a.content), json.loads(b.content)
        assert a['workspace'] != b['workspace']
        resumed = await middleware.awrap_tool_call(request('one', 'execute', {'command':'pwd'}), forbidden)
        assert json.loads(resumed.content)['workspace'] == a['workspace']
        for tool in ['read_file', 'write_file']:
            r = await middleware.awrap_tool_call(request('one', tool, {'file_path':'report.md'}), forbidden)
            assert json.loads(r.content)['args']['file_path'] == a['workspace'] + '/report.md'
        r = await middleware.awrap_tool_call(request('one', 'write_file', {'file_path':str(root/'data/raw')}), forbidden)
        assert r.status == 'error'
        r = await middleware.awrap_tool_call(request('one', 'unknown_host_tool', {}), forbidden)
        assert r.status == 'error'
    assert workspace._thread.get() is None



def checkpoint_checks(root):
    folder = root / 'runs/checkpoints/example'
    folder.mkdir(parents=True)
    (folder / 'proof.txt').write_text('frozen')
    digest = hashlib.sha256(b'frozen').hexdigest()
    (folder / 'SHA256SUMS').write_text(f'{digest}  proof.txt\n')
    def rejected(action):
        try:
            action()
        except (ValueError, OSError):
            return
        raise AssertionError('Invalid checkpoint accepted')
    assert workspace.validate_checkpoint('example', root) == folder
    for name in ['../example', '/example', '', 'missing']:
        rejected(lambda: workspace.validate_checkpoint(name, root))
    with patch.object(workspace, 'requested_checkpoint', 'example'):
        assert workspace.bind_checkpoint('fresh', root) == folder
    with patch.object(workspace, 'requested_checkpoint', None):
        assert workspace.bind_checkpoint('fresh', root) == folder
        workspace.bind_checkpoint('unbound', root)
    with patch.object(workspace, 'requested_checkpoint', 'other'):
        rejected(lambda: workspace.bind_checkpoint('fresh', root))
    with patch.object(workspace, 'requested_checkpoint', 'example'):
        rejected(lambda: workspace.bind_checkpoint('unbound', root))
        (root / 'runs/workspaces/legacy').mkdir(parents=True)
        rejected(lambda: workspace.bind_checkpoint('legacy', root))
    (folder / 'extra').write_text('unlisted')
    rejected(lambda: workspace.validate_checkpoint('example', root))
    (folder / 'extra').unlink()
    (folder / 'proof.txt').write_text('tampered')
    rejected(lambda: workspace.validate_checkpoint('example', root))
    (folder / 'proof.txt').unlink()
    (folder / 'proof.txt').symlink_to(root / 'outside')
    rejected(lambda: workspace.validate_checkpoint('example', root))

if __name__ == '__main__':
    original = workspace.output_root
    with TemporaryDirectory() as temporary:
        root=Path(temporary)
        with patch.object(workspace,'ROOT',root), patch.object(workspace,'output_root',lambda:original(root)):
            asyncio.run(check(root))
            checkpoint_checks(root)
    print('Workspace routing checks passed.')

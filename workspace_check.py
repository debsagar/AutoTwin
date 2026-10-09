"""Run with uv run python workspace_check.py; no model or raw log needed."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
import environment
import viewer
import workspace


def request(thread, name='prepare_environment', args=None):
    return ToolCallRequest(tool_call={'name': name, 'args': args or {}, 'id': 'check', 'type': 'tool_call'},
                           tool=None, state={}, runtime=SimpleNamespace(context={'thread_id': thread}))


async def check(root):
    middleware = workspace.middleware()
    async def run(thread):
        async def handler(req):
            before = environment._bundle('same-name')
            await asyncio.sleep(0)
            assert environment._bundle('same-name') == before
            assert viewer.output_root(viewer.ROOT) / 'environments/same-name' == before
            assert workspace.artifact_path('report.md') == before.parent.parent / 'report.md'
            env = workspace.subprocess_env()
            assert env['AUTOTWIN_THREAD_ID'] == thread
            child = subprocess.check_output([sys.executable, '-c',
                'import environment, sys; from pathlib import Path; environment.ROOT = Path(sys.argv[1]); '
                'print(environment._bundle("same-name"))', str(root)], env=env, text=True).strip()
            assert Path(child) == before
            return before
        return await middleware.awrap_tool_call(request(thread), handler)
    first, second = await asyncio.gather(run('thread-a'), run('thread-b'))
    assert first != second and first == await run('thread-a')
    assert workspace._thread.get() is None
    assert 'AUTOTWIN_THREAD_ID' not in os.environ
    model = ModelRequest(model=None, messages=[], system_message=SystemMessage(content='Product'),
                         runtime=SimpleNamespace(context={'thread_id': 'empty-conversation'}))
    assert 'empty-conversation' in middleware.model_request(model).system_message.text
    assert (root / 'runs/workspaces/empty-conversation').is_dir()
    def capture(req):
        return req.tool_call['args']
    result = middleware.wrap_tool_call(request('thread-a', 'write_file', {'file_path': 'report.md'}), capture)
    assert result['file_path'] == str(first.parent.parent / 'report.md')
    read = middleware.wrap_tool_call(request('thread-a', 'read_file', {'file_path': 'report.md'}), capture)
    assert read == result
    for path in ['../../outside.md', str(root / 'data/raw.xes')]:
        result = middleware.wrap_tool_call(request('thread-a', 'edit_file', {'file_path': path}), capture)
        assert isinstance(result, ToolMessage) and result.status == 'error'
    link = first.parent.parent / 'escape'
    link.symlink_to(root, target_is_directory=True)
    result = middleware.wrap_tool_call(request('thread-a', 'write_file', {'file_path': 'escape/no.md'}), capture)
    assert result.status == 'error'
    result = middleware.wrap_tool_call(request('thread-a', 'execute', {'command': 'pwd; echo "$AUTOTWIN_THREAD_ID"'}), capture)
    lines = subprocess.check_output(['bash', '-c', result['command']], text=True).splitlines()
    assert lines == [str(first.parent.parent), 'thread-a']
    assert environment._bundle('legacy') == root / 'runs/environments/legacy'
    from blockbuster import blockbuster_ctx
    async def passthrough(req):
        return req
    with blockbuster_ctx(scanned_modules=[workspace]):
        await middleware.awrap_model_call(model, passthrough)
        await middleware.awrap_tool_call(request('thread-a', 'read_file', {'file_path': 'report.md'}), passthrough)


if __name__ == '__main__':
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        # Helpers' default roots are source locations; replace defaults for disposable checks.
        original_output = workspace.output_root
        original_artifact = workspace.artifact_path
        with patch.object(environment, 'ROOT', root), patch.object(viewer, 'ROOT', root), \
             patch.object(workspace, 'ROOT', root), \
             patch.object(workspace, 'output_root', lambda supplied=None: original_output(supplied or root)), \
             patch.object(workspace, 'artifact_path', lambda path: original_artifact(path, root)):
            asyncio.run(check(root))
    print('workspace checks passed: new/resume/concurrency, subprocess, native file/shell paths')

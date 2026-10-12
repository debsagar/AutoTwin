"""Conversation output paths; native dcode owns conversation persistence."""
import asyncio
import hashlib
from contextvars import ContextVar
import os
from pathlib import Path
import re
import json
from subprocess import TimeoutExpired

ROOT = Path(__file__).resolve().parent
_thread = ContextVar('autotwin_thread', default=None)
requested_checkpoint = os.getenv("AUTOTWIN_CHECKPOINT")


def validate_checkpoint(name, root=None):
    root = ROOT if root is None else root
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', name):
        raise ValueError('Invalid checkpoint name.')
    folder = root / 'runs/checkpoints' / name
    if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != (root / 'runs/checkpoints').resolve():
        raise ValueError('Checkpoint must be a real directory under runs/checkpoints.')
    paths = list(folder.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Checkpoint symlinks are not allowed.')
    manifest = folder / 'SHA256SUMS'
    listed = set()
    for line in manifest.read_text().splitlines():
        digest, relative = line.split('  ', 1)
        path = folder / relative
        if (not re.fullmatch(r'[0-9a-f]{64}', digest) or Path(relative).is_absolute()
                or '..' in Path(relative).parts or relative in listed or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError(f'Checkpoint integrity failed: {relative}')
        listed.add(relative)
    actual = {str(p.relative_to(folder)) for p in paths if p.is_file() and p != manifest}
    if listed != actual:
        raise ValueError('Checkpoint checksum manifest does not cover exactly its files.')
    return folder


def bind_checkpoint(thread, root=None):
    """Host-only binding; native dcode remains the sole conversation store."""
    root = ROOT if root is None else root
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', thread):
        raise ValueError('Invalid native conversation ID.')
    binding = root / '.dcode/checkpoint-bindings' / (thread + '.json')
    if binding.exists():
        name = json.loads(binding.read_text())['checkpoint']
        if requested_checkpoint is not None and requested_checkpoint != name:
            raise ValueError('Cannot rebind an existing conversation to a different checkpoint; start a new conversation.')
    else:
        if requested_checkpoint and (root / 'runs/workspaces' / thread).exists():
            raise ValueError('Checkpoint attachment requires a fresh conversation workspace.')
        name = requested_checkpoint
        if name:
            validate_checkpoint(name, root)
        binding.parent.mkdir(parents=True, exist_ok=True)
        try:
            with binding.open('x') as handle:
                json.dump({'checkpoint': name}, handle)
        except FileExistsError:
            return bind_checkpoint(thread, root)
    return validate_checkpoint(name, root) if name else None


def checkpoint_for(workspace):
    binding = ROOT / '.dcode/checkpoint-bindings' / (workspace.name + '.json')
    name = json.loads(binding.read_text())['checkpoint'] if binding.exists() else None
    return validate_checkpoint(name) if name else None


def output_root(root=ROOT):
    """Keep standalone scripts on legacy paths; native conversations get a workspace."""
    thread = _thread.get() or os.getenv('AUTOTWIN_THREAD_ID')
    if not thread:
        return root / 'runs'
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', thread):
        raise ValueError('Invalid native conversation ID.')
    workspace = root / 'runs' / 'workspaces' / thread
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def artifact_path(path, root=ROOT):
    base = output_root(root)
    return (root if base == root / "runs" else base) / path


def subprocess_env():
    env = dict(os.environ)
    if _thread.get():
        env['AUTOTWIN_THREAD_ID'] = _thread.get()
    return env


def conversation_id(runtime):
    context = runtime.context
    thread = context.get('thread_id') if isinstance(context, dict) else getattr(context, 'thread_id', None)
    if not thread:
        config = getattr(runtime, 'config', None)
        if config is None:
            from langgraph.config import get_config
            config = get_config()
        thread = config.get('configurable', {}).get('thread_id')
    if not thread:
        raise ValueError('AutoTwin requires a native conversation ID.')
    return thread


def middleware():
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import SystemMessage, ToolMessage

    class ConversationWorkspace(AgentMiddleware):
        def model_request(self, request):
            token = _thread.set(conversation_id(request.runtime))
            try:
                baseline = bind_checkpoint(_thread.get())
                workspace = output_root()
            finally:
                _thread.reset(token)
            instruction = (f'\nTask workspace: {workspace}. All tool execution and filesystem access are '
                           'inside an isolated Docker worker. You can write and run your own code, inspect '
                           'installed libraries and read product source. Only this workspace is writable '
                           'and persistent. '
                           + (f'Frozen checkpoint: {baseline.name}, mounted read-only at {workspace / "baseline"}. '
                              'Raw data and benchmark reference answers are unavailable. This checkpoint contains '
                              'previously seen test results: DEVELOPMENT evidence, not blind evaluation. '
                              'Read baseline/README.md and baseline/checkpoint.json first. '
                              if baseline else f'Raw datasets at {ROOT / "data"} are read-only. ') +
                           f'Product skills are at {ROOT / ".deepagents/skills"}. '
                           'Other conversations, host files and credentials are not mounted. '
                           'Shell network is disabled; use web_search/fetch_url for research. '
                           'Each command starts a fresh worker; persist progress in files, not background '
                           'processes. Python and the simulation dependencies are installed; use python. '
                           'Use experiments/ for investigations, environments/ for candidates and report.md '
                           'as the task entrypoint. On resume read report.md and existing evidence first. '
                           'The supplied tools are conveniences, not the limit of your capabilities. '
                           'Investigate unexpected results yourself before reporting a blocker.')
            blocks = list(request.system_message.content_blocks) if request.system_message else []
            return request.override(system_message=SystemMessage(content=[*blocks, {'type': 'text', 'text': instruction}]))

        def wrap_model_call(self, request, handler):
            return handler(self.model_request(request))

        async def awrap_model_call(self, request, handler):
            return await handler(await asyncio.to_thread(self.model_request, request))

        def tool_request(self, request):
            bind_checkpoint(_thread.get())
            workspace = output_root()
            call = request.tool_call
            args = dict(call['args'])
            if call['name'] in {'write_file', 'edit_file', 'delete'}:
                path = Path(args['file_path'])
                path = (workspace / path).resolve()
                if not path.is_relative_to(workspace.resolve()):
                    return ToolMessage(content=f'Write rejected: generated files must stay inside {workspace}.',
                                       tool_call_id=call['id'], status='error')
                args['file_path'] = str(path)
            elif call['name'] in {'read_file', 'ls', 'glob', 'grep'}:
                key = 'file_path' if call['name'] == 'read_file' else 'path'
                path = Path(args.get(key) or '.')
                if not path.is_absolute():
                    base = ROOT if path.parts and path.parts[0] in {'data', '.deepagents'} else workspace
                    path = base / path
                args[key] = str(path.resolve())
            from sandbox import call as sandbox_call, FILES, PROCESS
            if call['name'] in {*FILES, *PROCESS, 'execute'}:
                try:
                    result = sandbox_call(workspace, call['name'], args)
                    return ToolMessage(content=json.dumps(result), tool_call_id=call['id'],
                                       status='success' if result['exit_code'] == 0 else 'error')
                except (OSError, ValueError, RuntimeError, TimeoutExpired) as error:
                    return ToolMessage(content=str(error), tool_call_id=call['id'], status='error')
            # Only network research and native planning/delegation stay in the controller.
            if call['name'] not in {'web_search', 'fetch_url', 'write_todos', 'task', 'ask_user', 'compact_conversation'}:
                return ToolMessage(content=f'Tool {call["name"]} is not enabled in this sandbox.',
                                   tool_call_id=call['id'], status='error')
            return request.override(tool_call={**call, 'args': args})

        def wrap_tool_call(self, request, handler):
            token = _thread.set(conversation_id(request.runtime))
            try:
                prepared = self.tool_request(request)
                return prepared if isinstance(prepared, ToolMessage) else handler(prepared)
            finally:
                _thread.reset(token)

        async def awrap_tool_call(self, request, handler):
            token = _thread.set(conversation_id(request.runtime))
            try:
                prepared = await asyncio.to_thread(self.tool_request, request)
                return prepared if isinstance(prepared, ToolMessage) else await handler(prepared)
            finally:
                _thread.reset(token)

    return ConversationWorkspace()

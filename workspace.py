"""Conversation output paths; native dcode owns conversation persistence."""
from contextvars import ContextVar
import os
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parent
_thread = ContextVar('autotwin_thread', default=None)


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
                workspace = output_root()
            finally:
                _thread.reset(token)
            instruction = (f'\nAutoTwin conversation workspace: {workspace}. All generated files, '
                           f'reports, scratch files and environments belong here. Native execute starts here. '
                           f'Shared raw inputs are read-only at {ROOT / "data"}; use absolute paths to read them. '
                           f'Product code and skills remain at {ROOT}; read skills by absolute path. '
                           'At the start of a task identify this workspace to the user; use absolute artifact '
                           'paths in tool calls. The final Stage 1 entrypoint is workspace/report.md; '
                           'candidates belong under workspace/environments/<name>/. Do not modify shared inputs, product '
                           'code, or other conversations. This is output organization, not an OS sandbox.')
            blocks = list(request.system_message.content_blocks) if request.system_message else []
            return request.override(system_message=SystemMessage(content=[*blocks, {'type': 'text', 'text': instruction}]))

        def wrap_model_call(self, request, handler):
            return handler(self.model_request(request))

        async def awrap_model_call(self, request, handler):
            return await handler(self.model_request(request))

        def tool_request(self, request):
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
            elif call['name'] == 'execute':
                args['command'] = (f'cd {shlex.quote(str(workspace))} || exit; '
                                   f'export AUTOTWIN_THREAD_ID={shlex.quote(_thread.get())} '
                                   f'PYTHONPATH={shlex.quote(str(ROOT))}${{PYTHONPATH:+:$PYTHONPATH}}; '
                                   + args['command'])
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
                prepared = self.tool_request(request)
                return prepared if isinstance(prepared, ToolMessage) else await handler(prepared)
            finally:
                _thread.reset(token)

    return ConversationWorkspace()

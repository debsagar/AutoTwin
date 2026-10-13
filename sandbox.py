"""One disposable Docker process per tool call; only task files persist."""
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
IMAGE = 'autotwin-worker:local'
FILES = {'read_file': 'read', 'write_file': 'write', 'edit_file': 'edit',
         'delete': 'delete', 'ls': 'ls', 'glob': 'glob', 'grep': 'grep'}
PROCESS = {'discover_process', 'inspect_log_scope', 'prepare_environment', 'build_environment',
           'inspect_environment', 'revise_environment', 'evaluate_environment',
           'compare_evaluations', 'export_view', 'compare_scenario'}


def call(workspace, name, args, timeout=1800):
    """No host environment, credentials, Docker socket or other task mounts."""
    workspace = Path(workspace)
    if workspace.is_symlink():
        raise ValueError('Workspace symlinks are not allowed.')
    workspace = workspace.resolve()
    base = ROOT / 'runs/workspaces'
    if workspace.parent != base.resolve() or workspace.is_symlink():
        raise ValueError('Sandbox requires a task workspace directly under runs/workspaces.')
    if name == 'execute' and args.get('timeout') is not None:
        timeout = max(1, min(int(args['timeout']), timeout))
    from workspace import checkpoint_for
    baseline = checkpoint_for(workspace)
    mounts = (['--mount', f'type=bind,src={baseline},dst={workspace / "baseline"},readonly']
              if baseline else ['--mount', f'type=bind,src={ROOT / "data"},dst={ROOT / "data"},readonly'])
    container = 'autotwin-' + uuid.uuid4().hex
    command = ['docker', 'run', '--rm', '-i', '--name', container, '--network=none',
               '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
               '--pids-limit=256', '--memory=8g', '--cpus=4',
               '--user', f'{os.getuid()}:{os.getgid()}', '--tmpfs', '/tmp:rw,nosuid,size=1g',
               '--mount', f'type=bind,src={workspace},dst={workspace}',
               *mounts,
               '--workdir', str(workspace), '--env', f'AUTOTWIN_THREAD_ID={workspace.name}',
               IMAGE, 'python', str(ROOT / 'sandbox.py')]
    try:
        result = subprocess.run(command, input=json.dumps({'name': name, 'args': args}),
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return {'exit_code': result.returncode, 'output': result.stdout[-24000:],
                'truncated': len(result.stdout) > 24000}

    finally:
        subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def worker():
    request = json.load(sys.stdin)
    name, args = request['name'], request['args']
    if name == 'execute':
        result = subprocess.run(['bash', '-c', args['command']], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout); return result.returncode
    if name in FILES:
        args.pop("output_mode", None)  # Return structured matches for all grep modes.
        from deepagents.backends.filesystem import FilesystemBackend
        result = getattr(FilesystemBackend(root_dir=os.getcwd(), virtual_mode=False), FILES[name])(**args)
    elif name in PROCESS:
        import process_mining
        result = getattr(process_mining, name)(**args)
    else:
        raise ValueError(f'Unsupported sandbox operation: {name}')
    print(json.dumps(dataclasses.asdict(result) if dataclasses.is_dataclass(result) else result, default=str))
    return 1 if getattr(result, 'error', None) else 0


if __name__ == '__main__':
    sys.exit(worker())

"""Open AutoTwin in the native Deep Agents terminal UI; no startup task."""
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    os.environ["DEEPAGENTS_HOME"] = str(root / ".dcode")
    os.environ["DEEPAGENTS_CODE_ONBOARDING"] = "false"
    os.environ["DEEPAGENTS_CODE_EXPERIMENTAL"] = "1"
    import argparse
    import workspace
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--checkpoint')
    selected, native_args = parser.parse_known_args()
    workspace.requested_checkpoint = selected.checkpoint
    if selected.checkpoint:
        os.environ["AUTOTWIN_CHECKPOINT"] = selected.checkpoint
    else:
        os.environ.pop("AUTOTWIN_CHECKPOINT", None)
    help_requested = any(arg in {'--help', '-h'} for arg in native_args)
    if selected.checkpoint and not help_requested:
        workspace.validate_checkpoint(selected.checkpoint)
    if help_requested:
        print('AutoTwin option: --checkpoint NAME mounts a frozen development baseline in a fresh conversation.')
    import subprocess
    from sandbox import IMAGE
    if not help_requested and subprocess.run(['docker', 'image', 'inspect', IMAGE], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        raise SystemExit('Build the task sandbox first: docker build -t autotwin-worker:local .')
    from process_mining import install_runtime_policy
    install_runtime_policy()
    sys.argv = ["dcode", "--agent", "autotwin", "--model",
                os.getenv("AUTOTWIN_MODEL", "openrouter:openai/gpt-5.6-luna"),
                "--extension", str(root / "process_mining.py"),
                "--no-tracing", "--no-mcp", "--no-interpreter", *native_args]
    from deepagents_code import cli_main
    cli_main()

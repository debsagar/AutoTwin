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
    from process_mining import install_runtime_policy
    install_runtime_policy()
    sys.argv = ["dcode", "--agent", "autotwin", "--model",
                os.getenv("AUTOTWIN_MODEL", "openrouter:openai/gpt-5.6-luna"),
                "--extension", str(root / "process_mining.py"),
                "--no-tracing", "--no-mcp", "--no-interpreter", *sys.argv[1:]]
    from deepagents_code import cli_main
    cli_main()

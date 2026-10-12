FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
WORKDIR /data/autotwin
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && apt-get update && apt-get install -y --no-install-recommends ripgrep && rm -rf /var/lib/apt/lists/*
COPY main.py workspace.py process_mining.py environment.py model_tools.py validation.py viewer.py sandbox.py ./
COPY .deepagents ./.deepagents
COPY visual ./visual
ENV PATH="/data/autotwin/.venv/bin:$PATH" PYTHONPATH=/data/autotwin PYTHONDONTWRITEBYTECODE=1 HOME=/tmp

# Autonomous DevOps & Auto-Fix Agent

An AI-powered agent that monitors a Python codebase, detects failing tests, and automatically writes and commits fixes. Built using the ReAct (Reasoning + Acting) framework with Google Gemini as the reasoning engine.

## What It Does

The agent runs inside a Docker sandbox. It executes the test suite, reads the error output, reasons about what went wrong, reads the broken source code, writes a fix, and re-runs the tests to verify. If the fix works, it creates a branch and commits the changes automatically. If it does not work, it tries again — up to 5 attempts.

The full loop looks like this:

```
Run tests → Tests fail → Read errors → Read source code → Write fix → Re-run tests
    ↑                                                                        │
    └────────────────── Loop until all tests pass or max attempts ───────────┘
```

## How It Works

The agent uses the ReAct framework — a loop of Thought, Action, and Observation:

1. **Thought** — The LLM analyzes the test failures and decides what to do next
2. **Action** — The LLM calls a tool (run tests, read a file, or write a fix)
3. **Observation** — The tool result is sent back to the LLM
4. **Repeat** — The LLM uses the new information to take the next step

Every tool call passes through a security guardrail layer before execution. The guardrails block dangerous operations like modifying test files, writing malicious code, or accessing paths outside the workspace.

Every action is logged as structured JSON to `logs/agent_runs.jsonl` for full auditability.

## Tech Stack

- **Python 3.11** — Core language for the agent and all tools
- **Google Gemini API** (gemini-1.5-flash) — LLM for reasoning and code generation
- **google-genai SDK** — Official Python client for the Gemini API with function calling support
- **Docker** — Isolated sandbox environment where the agent reads, writes, and tests code
- **PyTest** — Test framework used to detect failures and verify fixes
- **Git** — Version control inside the container for branching and committing fixes

## Project Structure

```
autonomous-devops-agent/
├── agent/
│   ├── __init__.py           — Package init
│   ├── config.py             — Loads settings from .env
│   ├── guardrails.py         — Security validation for all tool calls
│   ├── git_operations.py     — High-level git workflow (branch + commit)
│   ├── llm_client.py         — Manages conversation with Gemini API
│   ├── logger.py             — Structured JSON logging
│   ├── main.py               — Entry point (python -m agent.main)
│   ├── prompt_templates.py   — System prompt and tool declarations
│   └── react_loop.py         — Core ReAct loop orchestration
├── tools/
│   ├── __init__.py           — Package init
│   ├── test_runner.py        — Runs PyTest inside Docker
│   ├── file_reader.py        — Reads files inside Docker
│   ├── file_writer.py        — Writes files inside Docker
│   └── git_manager.py        — Low-level git commands inside Docker
├── sandbox/
│   ├── calculator.py         — Sample code with intentional bugs
│   └── tests/
│       ├── __init__.py       — Package init
│       └── test_calculator.py — 12 tests (6 pass, 6 fail by design)
├── logs/
│   └── .gitkeep              — Keeps the empty logs directory in git
├── .env.example              — Template for environment variables
├── .gitignore                — Blocks .env, docs/, logs, and caches
├── Dockerfile                — Builds the sandbox container
├── docker-compose.yml        — Orchestrates the sandbox service
├── requirements.txt          — Python dependencies
└── README.md                 — This file
```

## How to Run

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- A free Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### Setup

```bash
# Clone the repository
git clone https://github.com/NakuSurrey/autonomous-devops-agent.git
cd autonomous-devops-agent

# Create the .env file from the template
cp .env.example .env

# Add your Gemini API key to .env
# Open .env and replace "your_gemini_api_key_here" with your actual key

# Install Python dependencies
pip install -r requirements.txt

# Build and start the Docker sandbox
docker-compose up -d --build
```

### Run the Agent

```bash
python -m agent.main
```

The agent will:
1. Run the test suite inside the Docker container
2. Detect the 6 failing tests
3. Reason about each failure using Gemini
4. Write fixes to the source code
5. Re-run tests to verify each fix
6. Create a branch and commit the successful fix

### View Logs

After a run, check the structured log file:

```bash
cat logs/agent_runs.jsonl
```

Each line is a JSON object with: timestamp, run ID, event type, attempt number, and content.

## Security

The agent includes a guardrail layer that validates every tool call before execution:

- Blocks writes to test files, config files, and agent source code
- Blocks dangerous content patterns (system imports, eval, exec, subprocess)
- Blocks path traversal attacks and absolute paths
- Blocks reads to sensitive files (.env)
- Validates git commits to ensure only source files are modified

## Key Design Decisions

- **Docker isolation** — All code execution happens inside a container with no network access. The host machine is never at risk.
- **COPY strategy** — Sandbox files are copied into the container at build time, not mounted. The agent cannot access anything outside the container.
- **ReAct loop** — The agent iterates instead of doing one-shot generation. This lets it learn from failed fix attempts and try different approaches.
- **Structured logging** — Every action is recorded as JSON for debugging and auditing. Each run gets a unique ID for traceability.
- **Conventional Commits** — Auto-generated commit messages follow the `fix:` prefix standard.

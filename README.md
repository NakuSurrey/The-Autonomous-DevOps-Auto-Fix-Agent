<h1 align="center">Autonomous DevOps & Auto-Fix Agent</h1>

<p align="center">
  <strong>AI agent that finds failing tests, diagnoses bugs, writes code fixes, and commits them — zero human input.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Gemini-API-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/Docker-Sandboxed-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/SFT-Fine--Tuning%20Ready-FF6F00?style=flat-square&logo=huggingface&logoColor=white" alt="SFT">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
</p>

<br>

<p align="center">
  <img src="assets/demo-terminal.svg" alt="Agent Demo" width="800">
</p>

---

## What It Does

Give this agent a codebase with failing tests. It will:

1. **Run the tests** — detect what is broken
2. **Read the errors** — understand the failure
3. **Read the source code** — find the bug
4. **Write a fix** — patch the code
5. **Re-run the tests** — verify the fix works
6. **Commit the fix** — create a branch with a conventional commit message

Everything runs inside an **isolated Docker container**. The agent cannot touch the host machine.

After each run, the agent's logs can be **exported as SFT training data** to fine-tune a local model (Llama 3, Mistral) that replicates the agent's behavior.

---

## Skills Demonstrated

| Skill | Where it shows up |
|---|---|
| **AI Agent Design (ReAct Framework)** | `react_loop.py` — iterative Thought → Action → Observation loop |
| **LLM Tool Use / Function Calling** | `llm_client.py` + `prompt_templates.py` — Gemini function calling protocol |
| **Containerized Execution** | `Dockerfile` + `docker-compose.yml` — sandboxed code execution |
| **Security Engineering** | `guardrails.py` — 25 dangerous pattern checks, path traversal blocking |
| **Structured Observability** | `logger.py` — JSON Lines logging with unique run IDs |
| **SFT Data Pipeline** | `sft_data_collector.py` + `sft_exporter.py` — log-to-training-data pipeline |
| **Model Evaluation** | `evaluator.py` — scoring framework: pass rate, efficiency, tool usage |
| **Git Automation** | `git_operations.py` — autonomous branching and conventional commits |

---

## Architecture

```
                          ┌──────────────────────────┐
                          │     python -m agent.main  │
                          └────────────┬─────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
        Default Mode           --export-sft              --evaluate
       (fix bugs)           (export training data)    (benchmark agent)
              │                        │                        │
              ▼                        ▼                        ▼
      react_loop.py          sft_exporter.py           evaluator.py
              │                        │                        │
    ┌─────────┴─────────┐             │               ┌────────┴────────┐
    │                   │              │               │                 │
    ▼                   ▼              ▼               ▼                 ▼
 llm_client.py    guardrails.py   sft_dataset.jsonl  reset_sandbox   eval_report.json
 (Gemini API)     (security)      (HuggingFace)      (Docker)        (scores)
    │                   │
    ▼                   ▼
 ┌────────────────────────────────────────┐
 │  DOCKER CONTAINER (no network access)  │
 │                                        │
 │  test_runner.py  → runs pytest         │
 │  file_reader.py  → reads source code   │
 │  file_writer.py  → writes fixed code   │
 │  git_manager.py  → git add, commit     │
 └────────────────────────────────────────┘
```

---

## SFT Data Pipeline

<p align="center">
  <img src="assets/sft-pipeline.svg" alt="SFT Pipeline" width="800">
</p>

Every successful fix run is a complete training example: "given this error, here is how to fix it step by step."

The pipeline collects these examples and exports them in **Alpaca format** (`instruction`, `input`, `output`) or **conversational format** (`system`, `user`, `assistant`) — both accepted by HuggingFace fine-tuning tools (Unsloth, PEFT, TRL).

```bash
python -m agent.main --export-sft          # Alpaca format
python -m agent.main --export-sft --chat   # Conversational format
python -m agent.main --evaluate            # Score the agent's performance
```

---

## Quick Start

```bash
git clone https://github.com/NakuSurrey/The-Autonomous-DevOps-Auto-Fix-Agent.git
cd The-Autonomous-DevOps-Auto-Fix-Agent

cp .env.example .env
# Add your free Gemini API key: https://aistudio.google.com/app/apikey

pip install -r requirements.txt
docker-compose up -d --build

python -m agent.main
```

---

## Project Structure

```
.
├── agent/
│   ├── react_loop.py ........... Core ReAct loop (Thought → Action → Observation)
│   ├── llm_client.py ........... Gemini API with function calling
│   ├── prompt_templates.py ..... System prompt + tool declarations
│   ├── guardrails.py ........... Security validation (25 patterns)
│   ├── logger.py ............... Structured JSON logging (.jsonl)
│   ├── git_operations.py ....... Autonomous branching + commits
│   ├── sft_data_collector.py ... Extracts training pairs from logs
│   ├── sft_exporter.py ......... Exports HuggingFace-compatible datasets
│   ├── evaluator.py ............ Agent scoring and eval reports
│   ├── config.py ............... Environment variable loader
│   └── main.py ................. Entry point (3 modes)
├── tools/
│   ├── test_runner.py .......... Runs PyTest inside Docker
│   ├── file_reader.py .......... Reads files inside Docker
│   ├── file_writer.py .......... Writes files inside Docker
│   ├── git_manager.py .......... Low-level git commands
│   └── evaluation_runner.py .... Sandbox reset for eval
├── sandbox/
│   ├── calculator.py ........... Sample code (3 intentional bugs)
│   └── tests/test_calculator.py  12 tests (6 pass, 6 fail)
├── Dockerfile .................. Sandbox container definition
├── docker-compose.yml .......... Container orchestration
└── .env.example ................ Configuration template
```

---

## Security

Every tool call passes through `guardrails.py` before execution:

- **Path traversal blocking** — `../` and absolute paths rejected
- **Protected file enforcement** — Cannot write to tests, `.env`, Dockerfile, agent source code
- **Dangerous code pattern detection** — 25 patterns blocked: `eval(`, `exec(`, `import os`, `subprocess.`, `sys.exit(`, and more
- **Git commit validation** — Protected files cannot appear in commit changesets

---

## Tech Stack

| Tool | Role |
|---|---|
| Python 3.11 | Agent core + all tool functions |
| Google Gemini API | LLM reasoning + function calling |
| Docker | Isolated sandbox with no network access |
| PyTest | Test detection and fix verification |
| Git | Automated branching and conventional commits |
| JSONL | Structured logging + SFT dataset format |

---

## Design Decisions

**Docker isolation** — The agent writes and executes code. Running that on the host is unsafe. Docker provides a throwaway environment.

**ReAct over single-shot** — One-shot code generation fails often. The loop lets the agent learn from failed fix attempts and try different approaches.

**Guardrails as a separate layer** — Security checks live in one module, not scattered across tools. Single place to audit, single place to update.

**Alpaca format for SFT** — The most widely supported fine-tuning format. Every major tool accepts it.

**Full rebuild for evaluation** — `docker-compose down + up --build` guarantees a clean sandbox. Slower than git reset, but correctness matters in benchmarks.

---

<p align="center">
  Built with Python, Gemini, and Docker<br>
  <a href="https://github.com/NakuSurrey/The-Autonomous-DevOps-Auto-Fix-Agent">github.com/NakuSurrey/The-Autonomous-DevOps-Auto-Fix-Agent</a>
</p>

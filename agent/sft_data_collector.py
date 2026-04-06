"""
sft_data_collector.py — Extracts SFT Training Pairs from Agent Logs

WHAT THIS FILE DOES:
    Reads the structured .jsonl log file and extracts successful fix
    runs. For each successful run, it builds a training pair:
      - INPUT:  the test failure output (what the agent saw)
      - OUTPUT: the full ReAct conversation trace (what the agent did)

    The result is a list of training pairs that can be used to
    fine-tune a smaller model to behave like the agent.

WHY IT EXISTS:
    The agent generates valuable data every time it runs. A successful
    fix is a complete example of: "given this error, here is exactly
    how to diagnose and fix it." Without this file, all that data
    just sits in the log file doing nothing. This file turns raw
    logs into structured training data.

WHERE IT SITS IN THE CODEBASE:
    agent/sft_data_collector.py
    ├── Reads from: logs/agent_runs.jsonl (written by agent/logger.py)
    ├── Used by: agent/sft_exporter.py (converts pairs to HuggingFace format)
    └── Does NOT depend on the LLM client, tools, or the ReAct loop

HOW SFT (Supervised Fine-Tuning) WORKS:
    SFT trains a model on pairs of (input, expected_output).
    The model learns: "when I see input X, I should produce output Y."

    For our agent:
      input  = "These tests failed with these errors"
      output = "THOUGHT: ... ACTION: read_file(...) OBSERVATION: ...
                THOUGHT: ... ACTION: write_file(...) OBSERVATION: ...
                ALL_TESTS_PASSED"

    A small model fine-tuned on many such pairs can learn to replicate
    the ReAct loop behavior without needing Gemini.

DATA FLOW:
    logs/agent_runs.jsonl
        │
        │  (this file reads it)
        ▼
    List of successful runs (grouped by run_id)
        │
        │  (this file formats each run)
        ▼
    List of SFT training pairs:
        [
            {
                "run_id": "a3f2b1c4",
                "instruction": "Fix the failing tests...",
                "input": "<test failure output>",
                "output": "<full ReAct trace>"
            },
            ...
        ]
"""

import json
from pathlib import Path
from typing import Optional

from agent.config import PROJECT_ROOT


# ==========================================================
# CONSTANTS
# ==========================================================

# where the log file lives
LOG_FILE = PROJECT_ROOT / "logs" / "agent_runs.jsonl"

# the instruction prefix for every training pair — tells the
# model what its job is (same context the system prompt gives)
SFT_INSTRUCTION = (
    "You are an Autonomous DevOps Agent. Analyze the failing test output below. "
    "Use the ReAct framework (Thought → Action → Observation) to diagnose the bug, "
    "read the source code, write a fix, and verify all tests pass."
)


def load_log_entries(log_path: Optional[Path] = None) -> list[dict]:
    """
    Reads all entries from the .jsonl log file.

    Parameters:
        log_path (Path): Path to the log file. Defaults to LOG_FILE.

    Returns:
        list[dict]: Every log entry as a Python dict.

    HOW IT WORKS:
        Step 1 → Open the .jsonl file
        Step 2 → Read each line
        Step 3 → Parse each line as JSON
        Step 4 → Skip any lines that fail to parse (corrupted entries)
        Step 5 → Return the full list
    """
    path = log_path or LOG_FILE

    if not path.exists():
        return []

    entries = []

    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                # skip corrupted lines — don't crash the whole pipeline
                print(f"[SFT COLLECTOR] Skipped corrupted line {line_number}")

    return entries


def group_by_run(entries: list[dict]) -> dict[str, list[dict]]:
    """
    Groups log entries by their run_id.

    Parameters:
        entries (list[dict]): All log entries from the .jsonl file.

    Returns:
        dict: Keys are run_ids, values are lists of entries for that run.

    HOW IT WORKS:
        Step 1 → Create an empty dict
        Step 2 → For each entry, look at its run_id
        Step 3 → Append the entry to the list for that run_id
        Step 4 → Return the dict

    EXAMPLE:
        Input:  [{"run_id": "abc", ...}, {"run_id": "abc", ...}, {"run_id": "def", ...}]
        Output: {"abc": [{...}, {...}], "def": [{...}]}
    """
    runs = {}

    for entry in entries:
        run_id = entry.get("run_id", "unknown")
        if run_id not in runs:
            runs[run_id] = []
        runs[run_id].append(entry)

    return runs


def is_successful_run(run_entries: list[dict]) -> bool:
    """
    Checks if a run ended successfully (all tests passed).

    Parameters:
        run_entries (list[dict]): All log entries for one run.

    Returns:
        bool: True if the run ended with success.

    HOW IT WORKS:
        Step 1 → Look at the last few entries
        Step 2 → Check if any has event_type "success"
        Step 3 → Also check metadata for "success": true
    """
    # check the last 5 entries (the success event is near the end)
    tail = run_entries[-5:] if len(run_entries) >= 5 else run_entries

    for entry in tail:
        if entry.get("event_type") == "success":
            return True
        # also check metadata in case the event_type was logged differently
        meta = entry.get("metadata", {})
        if meta.get("success") is True:
            return True

    return False


def extract_test_failure(run_entries: list[dict]) -> str:
    """
    Finds the initial test failure output from a run.

    This is the INPUT side of the SFT pair — what the agent saw.

    Parameters:
        run_entries (list[dict]): All log entries for one run.

    Returns:
        str: The test failure output, or empty string if not found.

    HOW IT WORKS:
        Step 1 → Scan entries for event_type "test_failure"
        Step 2 → Return the content of the first match
    """
    for entry in run_entries:
        if entry.get("event_type") == "test_failure":
            return entry.get("content", "")

    return ""


def extract_react_trace(run_entries: list[dict]) -> str:
    """
    Builds the full ReAct conversation trace from a run.

    This is the OUTPUT side of the SFT pair — what the agent did.

    Parameters:
        run_entries (list[dict]): All log entries for one run.

    Returns:
        str: The formatted ReAct trace.

    HOW IT WORKS:
        Step 1 → Filter for event types that form the ReAct trace:
                 thought, action, observation, guardrail_block
        Step 2 → Format each entry as "TYPE: content"
        Step 3 → Join them with newlines
        Step 4 → Append "ALL_TESTS_PASSED" at the end (since the run succeeded)

    WHAT THE OUTPUT LOOKS LIKE:
        THOUGHT: The test shows subtract(5, 3) expected 2 but got 8...
        ACTION: LLM called: read_file({"file_path": "calculator.py"})
        OBSERVATION: Contents of calculator.py: ...
        THOUGHT: Found the bug — subtract uses + instead of - ...
        ACTION: LLM called: write_file({"file_path": "calculator.py", ...})
        OBSERVATION: File written successfully.
        ACTION: LLM called: run_tests({"test_path": "tests/"})
        OBSERVATION: Test result: PASSED ...
        ALL_TESTS_PASSED
    """
    # event types that make up the ReAct trace
    trace_types = {"thought", "action", "observation", "guardrail_block"}

    trace_lines = []

    for entry in run_entries:
        event_type = entry.get("event_type", "")
        content = entry.get("content", "")

        if event_type in trace_types and content:
            label = event_type.upper()
            trace_lines.append(f"{label}: {content}")

    # mark the end of a successful trace
    trace_lines.append("ALL_TESTS_PASSED")

    return "\n".join(trace_lines)


def collect_training_pairs(log_path: Optional[Path] = None) -> list[dict]:
    """
    Main function. Reads logs and returns SFT training pairs.

    Parameters:
        log_path (Path): Path to the log file. Defaults to LOG_FILE.

    Returns:
        list[dict]: Each dict has:
            "run_id"      (str): Which run this pair came from
            "instruction" (str): The task description (same for all pairs)
            "input"       (str): The test failure output
            "output"      (str): The full ReAct trace that fixed it
            "attempts"    (int): How many attempts the agent used

    HOW IT WORKS:
        Step 1 → Load all log entries from the .jsonl file
        Step 2 → Group entries by run_id
        Step 3 → Filter for successful runs only
        Step 4 → For each successful run:
                   a) Extract the test failure (input)
                   b) Extract the ReAct trace (output)
                   c) Build the training pair dict
        Step 5 → Return the list of all pairs
    """
    entries = load_log_entries(log_path)

    if not entries:
        print("[SFT COLLECTOR] No log entries found. Run the agent first.")
        return []

    runs = group_by_run(entries)
    pairs = []

    for run_id, run_entries in runs.items():
        # only keep successful runs — failed runs are not good training data
        if not is_successful_run(run_entries):
            continue

        test_failure = extract_test_failure(run_entries)
        react_trace = extract_react_trace(run_entries)

        # skip if we couldn't extract the key pieces
        if not test_failure or not react_trace:
            print(f"[SFT COLLECTOR] Skipped run {run_id} — missing test failure or trace")
            continue

        # extract attempt count from the run's metadata
        attempts = 0
        for entry in run_entries:
            meta = entry.get("metadata", {})
            if "attempts" in meta:
                attempts = meta["attempts"]

        pairs.append({
            "run_id": run_id,
            "instruction": SFT_INSTRUCTION,
            "input": test_failure,
            "output": react_trace,
            "attempts": attempts,
        })

    print(f"[SFT COLLECTOR] Extracted {len(pairs)} training pair(s) from {len(runs)} total run(s).")
    return pairs

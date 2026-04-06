"""
evaluator.py — Agent Performance Evaluation System

WHAT THIS FILE DOES:
    Runs the agent against the sandbox and scores the result.
    Measures: pass/fail, number of attempts used, total tool calls,
    duration, and which tools were used. Writes a structured
    evaluation report to data/eval_report.json.

WHY IT EXISTS:
    Without evaluation, there is no way to know if the agent is
    getting better or worse. When you fine-tune a local model and
    swap it in for Gemini, you need a benchmark to compare:
      - "Gemini fixed all tests in 2 attempts with 8 tool calls"
      - "My fine-tuned model fixed all tests in 3 attempts with 12 tool calls"
    This file produces that benchmark.

WHERE IT SITS IN THE CODEBASE:
    agent/evaluator.py
    ├── Reads from: logs/agent_runs.jsonl (after running the agent)
    ├── Uses: tools/evaluation_runner.py (resets sandbox before each run)
    ├── Uses: agent/react_loop.py (runs the agent)
    ├── Writes to: data/eval_report.json (the evaluation report)
    └── Can be run standalone: python -m agent.evaluator

HOW EVALUATION WORKS:
    Step 1 → Reset the sandbox to the original broken state
    Step 2 → Run the agent (the full ReAct loop)
    Step 3 → Read the logs for this run
    Step 4 → Score the run: pass/fail, attempts, tools, duration
    Step 5 → Write the evaluation report to data/eval_report.json
    Step 6 → Print a summary to the terminal
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.config import PROJECT_ROOT, GEMINI_MODEL, MAX_FIX_ATTEMPTS


# ==========================================================
# CONSTANTS
# ==========================================================

DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = PROJECT_ROOT / "logs" / "agent_runs.jsonl"
DEFAULT_REPORT_FILE = DATA_DIR / "eval_report.json"


def _ensure_data_dir():
    """Creates the data/ directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def score_run(run_result: dict, run_entries: list[dict]) -> dict:
    """
    Scores a single agent run.

    Parameters:
        run_result (dict): The return value from run_react_loop().
                           Has keys: "success", "attempts", "history", "branch"
        run_entries (list[dict]): Log entries for this specific run.

    Returns:
        dict with all scoring metrics:
            "passed"         (bool):  Did all tests pass?
            "attempts_used"  (int):   How many attempts the agent used
            "max_attempts"   (int):   The configured maximum
            "total_tool_calls" (int): How many tools were called
            "tools_used"     (dict):  Count per tool name
            "guardrail_blocks" (int): How many tool calls were blocked
            "thoughts"       (int):   How many reasoning steps
            "duration_seconds" (float): Total run time
            "efficiency"     (float): Score from 0.0 to 1.0

    HOW EFFICIENCY IS CALCULATED:
        efficiency = 1.0 - (attempts_used - 1) / max_attempts

        If the agent fixes everything on attempt 1 → efficiency = 1.0
        If the agent uses all 5 attempts         → efficiency = 0.2
        If the agent fails                        → efficiency = 0.0

        This rewards agents that fix bugs quickly.
    """
    passed = run_result.get("success", False)
    attempts = run_result.get("attempts", 0)

    # count tool calls by type
    tools_used = {}
    total_tool_calls = 0
    guardrail_blocks = 0
    thoughts = 0
    duration_seconds = 0.0

    for entry in run_entries:
        event_type = entry.get("event_type", "")

        if event_type == "action":
            total_tool_calls += 1
            # extract tool name from metadata if available
            meta = entry.get("metadata", {})
            tool_name = meta.get("tool_name", "unknown")
            tools_used[tool_name] = tools_used.get(tool_name, 0) + 1

        elif event_type == "guardrail_block":
            guardrail_blocks += 1

        elif event_type == "thought":
            thoughts += 1

        # extract duration from the run-end entry
        meta = entry.get("metadata", {})
        if "duration_seconds" in meta:
            duration_seconds = meta["duration_seconds"]

    # calculate efficiency
    if not passed:
        efficiency = 0.0
    elif attempts == 0:
        # tests already passed — nothing to fix
        efficiency = 1.0
    else:
        efficiency = max(0.0, 1.0 - (attempts - 1) / MAX_FIX_ATTEMPTS)

    return {
        "passed": passed,
        "attempts_used": attempts,
        "max_attempts": MAX_FIX_ATTEMPTS,
        "total_tool_calls": total_tool_calls,
        "tools_used": tools_used,
        "guardrail_blocks": guardrail_blocks,
        "thoughts": thoughts,
        "duration_seconds": duration_seconds,
        "efficiency": round(efficiency, 3),
    }


def get_latest_run_entries() -> tuple[str, list[dict]]:
    """
    Reads the log file and returns entries for the most recent run.

    Returns:
        tuple: (run_id, list of entries for that run)

    HOW IT WORKS:
        Step 1 → Read all log entries
        Step 2 → Find the last run_id that appears
        Step 3 → Filter entries for that run_id
        Step 4 → Return the run_id and its entries
    """
    if not LOG_FILE.exists():
        return ("", [])

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        return ("", [])

    # find the last run_id
    last_run_id = entries[-1].get("run_id", "")

    # filter for that run
    run_entries = [e for e in entries if e.get("run_id") == last_run_id]

    return (last_run_id, run_entries)


def write_eval_report(
    run_id: str,
    scores: dict,
    report_path: Optional[Path] = None,
) -> dict:
    """
    Writes the evaluation report to a JSON file.

    Parameters:
        run_id (str): The run_id that was evaluated.
        scores (dict): The scoring metrics from score_run().
        report_path (Path): Where to write the report.

    Returns:
        dict with "success" and "file_path".

    THE REPORT STRUCTURE:
        {
            "evaluation": {
                "run_id": "a3f2b1c4",
                "model": "gemini-1.5-flash",
                "evaluated_at": "2026-04-06T12:00:00+00:00",
                "scores": { ... all metrics ... }
            }
        }
    """
    _ensure_data_dir()
    path = report_path or DEFAULT_REPORT_FILE

    report = {
        "evaluation": {
            "run_id": run_id,
            "model": GEMINI_MODEL,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "scores": scores,
        }
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "file_path": str(path),
        }

    except IOError as e:
        return {
            "success": False,
            "file_path": str(path),
            "message": f"Failed to write report: {e}",
        }


def print_eval_summary(run_id: str, scores: dict):
    """
    Prints a human-readable evaluation summary to the terminal.
    """
    print()
    print("=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)
    print(f"  Run ID:         {run_id}")
    print(f"  Model:          {GEMINI_MODEL}")
    print(f"  Result:         {'PASSED' if scores['passed'] else 'FAILED'}")
    print(f"  Attempts:       {scores['attempts_used']} / {scores['max_attempts']}")
    print(f"  Efficiency:     {scores['efficiency']:.1%}")
    print(f"  Tool Calls:     {scores['total_tool_calls']}")
    print(f"  Thoughts:       {scores['thoughts']}")
    print(f"  Guardrail Blocks: {scores['guardrail_blocks']}")
    print(f"  Duration:       {scores['duration_seconds']:.1f}s")
    print()
    print("  Tools Used:")
    for tool_name, count in scores["tools_used"].items():
        print(f"    {tool_name}: {count}")
    print("=" * 60)


def run_evaluation(reset_sandbox: bool = True) -> dict:
    """
    Full evaluation pipeline: reset → run agent → score → report.

    Parameters:
        reset_sandbox (bool): If True, reset the Docker sandbox to the
                              original broken state before running. Defaults to True.

    Returns:
        dict with:
            "success"  (bool)
            "run_id"   (str)
            "scores"   (dict)
            "report"   (dict)

    HOW IT WORKS:
        Step 1 → Reset the sandbox (rebuild Docker container)
        Step 2 → Run the agent (full ReAct loop)
        Step 3 → Read the log entries for this run
        Step 4 → Score the run
        Step 5 → Write the evaluation report
        Step 6 → Print the summary
        Step 7 → Return everything
    """
    # Step 1: Reset sandbox if requested
    if reset_sandbox:
        from tools.evaluation_runner import reset_sandbox as do_reset
        print("[EVALUATOR] Resetting sandbox to original broken state...")
        reset_result = do_reset()
        if not reset_result["success"]:
            print(f"[EVALUATOR] WARNING: Sandbox reset failed: {reset_result['message']}")
            print("[EVALUATOR] Continuing anyway — the sandbox may not be in a clean state.")

    # Step 2: Run the agent
    print("[EVALUATOR] Running the agent...")
    from agent.react_loop import run_react_loop
    run_result = run_react_loop()

    # Step 3: Get the log entries for the latest run
    run_id, run_entries = get_latest_run_entries()

    if not run_id:
        return {
            "success": False,
            "run_id": "",
            "scores": {},
            "report": {"success": False, "message": "No log entries found after run."},
        }

    # Step 4: Score the run
    scores = score_run(run_result, run_entries)

    # Step 5: Write the report
    report = write_eval_report(run_id, scores)

    # Step 6: Print summary
    print_eval_summary(run_id, scores)

    # Step 7: Return everything
    return {
        "success": True,
        "run_id": run_id,
        "scores": scores,
        "report": report,
    }


# ==========================================================
# STANDALONE ENTRY POINT
# ==========================================================
# Run with: python -m agent.evaluator
#
# This lets you evaluate the agent from the command line
# without going through main.py.
# ==========================================================

if __name__ == "__main__":
    from agent.config import validate_config

    try:
        validate_config()
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    # check for --no-reset flag
    skip_reset = "--no-reset" in sys.argv

    result = run_evaluation(reset_sandbox=not skip_reset)

    sys.exit(0 if result["scores"].get("passed", False) else 1)

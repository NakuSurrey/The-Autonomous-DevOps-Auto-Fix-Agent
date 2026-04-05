"""
logger.py — Structured JSON Logger

WHAT THIS FILE DOES:
    Creates structured log entries (JSON format) and writes them
    to a .jsonl file. Every action the agent takes — thoughts,
    tool calls, observations, errors — gets logged as one JSON
    line in the log file.

WHY IT EXISTS:
    Without this file, the only record of what the agent did is
    the terminal output (which disappears when you close the
    terminal). This file creates a permanent, machine-readable
    record of every agent run. You can open the .jsonl file
    later to see exactly what happened, step by step.

WHERE IT SITS IN THE CODEBASE:
    agent/logger.py
    ├── Reads from: agent/config.py (LOG_LEVEL, PROJECT_ROOT)
    ├── Used by: agent/react_loop.py (replaces raw print() calls)
    ├── Writes to: logs/agent_runs.jsonl
    └── Does NOT depend on any tools or the LLM client

HOW .JSONL FORMAT WORKS:
    .jsonl = "JSON Lines" — each line in the file is one complete
    JSON object. NOT a JSON array. This means:
      - You can append new entries without reading the whole file
      - Each line is independent — a corrupted line doesn't break others
      - You can stream entries in real time (one line = one event)
    Example file contents:
      {"timestamp": "2026-04-05T12:00:01", "event": "system", ...}
      {"timestamp": "2026-04-05T12:00:02", "event": "action", ...}
      {"timestamp": "2026-04-05T12:00:03", "event": "observation", ...}
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.config import LOG_LEVEL, PROJECT_ROOT


# ==========================================================
# CONSTANTS
# ==========================================================

# Where log files are stored
LOG_DIR = PROJECT_ROOT / "logs"

# The log file name
LOG_FILE = LOG_DIR / "agent_runs.jsonl"

# Valid log levels, ordered from most verbose to least verbose.
# "DEBUG" logs everything. "ERROR" logs only errors.
# Each level includes itself and everything MORE severe.
#
# DEBUG → logs DEBUG, INFO, WARNING, ERROR
# INFO  → logs INFO, WARNING, ERROR (skips DEBUG)
# WARNING → logs WARNING, ERROR (skips DEBUG and INFO)
# ERROR → logs only ERROR
LOG_LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
}

# Map event types to log levels.
# This determines which events get logged at which level.
EVENT_LEVEL_MAP = {
    "system": "INFO",
    "thought": "DEBUG",
    "action": "INFO",
    "observation": "DEBUG",
    "tool_result": "DEBUG",
    "test_failure": "INFO",
    "error": "ERROR",
    "warning": "WARNING",
    "user_message": "INFO",
    "success": "INFO",
    "give_up": "WARNING",
}


class AgentLogger:
    """
    Logs agent events as structured JSON lines to a file.

    HOW IT WORKS:
        Step 1 → On creation, generates a unique run_id for this run
        Step 2 → Ensures the logs/ directory exists
        Step 3 → Each log() call creates a JSON object with:
                    - timestamp (when it happened)
                    - run_id (which run this belongs to)
                    - attempt (which fix attempt, if applicable)
                    - event_type (what kind of event: action, thought, etc.)
                    - content (the actual data)
        Step 4 → The JSON object is written as one line to the .jsonl file
        Step 5 → The same event is also printed to the terminal (for real-time watching)

    WHY A CLASS (not just functions):
        The logger needs to remember state between calls:
          - run_id: stays the same for the entire run
          - attempt: changes as the agent tries different fixes
          - log file handle: stays open for the entire run
        A class bundles this state together. Functions alone
        would need global variables, which are harder to manage.
    """

    def __init__(self):
        """
        Creates a new logger for one agent run.

        WHAT HAPPENS:
            Step 1 → Generate a unique run_id (UUID) for this run
            Step 2 → Record the start time
            Step 3 → Set the current attempt to 0
            Step 4 → Set the configured log level
            Step 5 → Ensure the log directory exists
        """

        # --------------------------------------------------
        # run_id: A unique identifier for this entire run.
        # uuid4() generates a random 128-bit ID like:
        #   "a3f2b1c4-5678-4d90-abcd-ef1234567890"
        # We take the first 8 characters for readability:
        #   "a3f2b1c4"
        # This lets you find all log entries for one run.
        # --------------------------------------------------
        self.run_id: str = str(uuid.uuid4())[:8]

        # --------------------------------------------------
        # start_time: When this run began.
        # Used later to calculate total run duration.
        # --------------------------------------------------
        self.start_time: datetime = datetime.now(timezone.utc)

        # --------------------------------------------------
        # attempt: Which fix attempt we are currently on.
        # Starts at 0 (before any attempts).
        # react_loop.py will call set_attempt() to update this.
        # --------------------------------------------------
        self.attempt: int = 0

        # --------------------------------------------------
        # current_log_level: The minimum severity level to log.
        # Read from config.py (which reads from .env).
        # Default is "INFO" if the value in .env is invalid.
        # --------------------------------------------------
        configured_level = LOG_LEVEL.upper()
        if configured_level not in LOG_LEVELS:
            configured_level = "INFO"
        self.current_log_level: int = LOG_LEVELS[configured_level]

        # --------------------------------------------------
        # Ensure the log directory exists.
        # mkdir(parents=True) creates parent folders if needed.
        # exist_ok=True means "don't crash if it already exists."
        # --------------------------------------------------
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------
        # event_count: Tracks how many events have been logged
        # in this run. Useful for ordering events.
        # --------------------------------------------------
        self.event_count: int = 0

    def set_attempt(self, attempt: int):
        """
        Updates the current attempt number.

        Called by react_loop.py at the start of each attempt.
        All subsequent log entries will include this attempt number.
        """
        self.attempt = attempt

    def _should_log(self, event_type: str) -> bool:
        """
        Checks if an event should be logged based on the current log level.

        HOW IT WORKS:
            Step 1 → Look up the event type in EVENT_LEVEL_MAP
            Step 2 → Get the numeric level of that event
            Step 3 → Compare to the current log level
            Step 4 → If event level >= current level → log it
                      If event level <  current level → skip it

        Example:
            LOG_LEVEL = "INFO" (numeric: 1)
            event_type = "thought" → mapped to "DEBUG" (numeric: 0)
            0 < 1 → DO NOT log this event

            event_type = "action" → mapped to "INFO" (numeric: 1)
            1 >= 1 → DO log this event
        """

        # Get the level name for this event type.
        # Default to "INFO" for unknown event types.
        level_name = EVENT_LEVEL_MAP.get(event_type, "INFO")

        # Get the numeric value.
        level_value = LOG_LEVELS.get(level_name, 1)

        # Compare: only log if the event is important enough.
        return level_value >= self.current_log_level

    def log(self, event_type: str, content: str, metadata: dict = None):
        """
        Logs a single event.

        Parameters:
            event_type (str): What kind of event this is.
                              Examples: "system", "action", "thought",
                              "observation", "error", "warning"
            content (str):    The actual data for this event.
                              Examples: "Running initial test suite...",
                              "LLM called: read_file({...})"
            metadata (dict):  Optional extra data to include.
                              Examples: {"tool_name": "run_tests",
                                         "tool_args": {"test_path": "tests/"}}

        HOW IT WORKS:
            Step 1 → Check if this event should be logged (based on log level)
            Step 2 → Build a JSON-compatible dict with all fields
            Step 3 → Write the dict as one JSON line to the log file
            Step 4 → Print to terminal for real-time watching
        """

        # --------------------------------------------------
        # Step 1: Check log level
        # --------------------------------------------------
        if not self._should_log(event_type):
            # Still print to terminal even if not logging to file.
            # This way the user can always see what the agent is doing.
            self._print_to_terminal(event_type, content)
            return

        # --------------------------------------------------
        # Step 2: Build the log entry
        # --------------------------------------------------
        self.event_count += 1

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_number": self.event_count,
            "attempt": self.attempt,
            "event_type": event_type,
            "content": content[:5000],  # Truncate very long content
        }

        # Add metadata if provided
        if metadata:
            entry["metadata"] = metadata

        # --------------------------------------------------
        # Step 3: Write to the log file
        # --------------------------------------------------
        # "a" = append mode. Adds to the end of the file.
        # Does not overwrite existing entries.
        # json.dumps() converts the dict to a JSON string.
        # We write one line per entry (JSONL format).
        # --------------------------------------------------
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError as e:
            # If we can't write to the log file, print a warning
            # but don't crash the agent. Logging is important but
            # not worth stopping the entire fix attempt over.
            print(f"[LOGGER WARNING] Could not write to log file: {e}")

        # --------------------------------------------------
        # Step 4: Print to terminal
        # --------------------------------------------------
        self._print_to_terminal(event_type, content)

    def _print_to_terminal(self, event_type: str, content: str):
        """
        Prints an event to the terminal for real-time watching.

        This keeps the same visual format that react_loop.py
        originally used with its log_event() function.
        """
        print(f"\n{'='*60}")
        print(f"[{event_type.upper()}]")
        print(f"{'='*60}")
        print(content)

    def log_run_start(self, model: str, max_attempts: int):
        """
        Logs the start of an agent run.
        Called once at the beginning, before any tests run.
        """
        self.log(
            "system",
            f"Agent run started. Run ID: {self.run_id}",
            metadata={
                "model": model,
                "max_attempts": max_attempts,
                "start_time": self.start_time.isoformat(),
            }
        )

    def log_run_end(self, success: bool, attempts: int):
        """
        Logs the end of an agent run.
        Called once after the loop finishes (success or failure).
        """
        end_time = datetime.now(timezone.utc)
        duration_seconds = (end_time - self.start_time).total_seconds()

        self.log(
            "success" if success else "give_up",
            f"Agent run finished. Success: {success}. "
            f"Attempts: {attempts}. Duration: {duration_seconds:.1f}s",
            metadata={
                "success": success,
                "attempts": attempts,
                "duration_seconds": round(duration_seconds, 1),
                "end_time": end_time.isoformat(),
            }
        )

    def log_tool_call(self, tool_name: str, tool_args: dict):
        """
        Logs when the LLM requests a tool call.
        """
        self.log(
            "action",
            f"LLM called: {tool_name}({tool_args})",
            metadata={
                "tool_name": tool_name,
                "tool_args": tool_args,
            }
        )

    def log_tool_result(self, tool_name: str, result: str, success: bool = True):
        """
        Logs the result of a tool execution.
        Truncates very long results to keep log files manageable.
        """
        self.log(
            "observation",
            f"Result of {tool_name}:\n{result[:2000]}",
            metadata={
                "tool_name": tool_name,
                "success": success,
                "result_length": len(result),
            }
        )

    def log_thought(self, thought: str):
        """
        Logs an LLM text response (a "thought" in ReAct terms).
        """
        self.log("thought", thought)

    def log_error(self, error_message: str, context: str = ""):
        """
        Logs an error that occurred during the run.
        """
        self.log(
            "error",
            error_message,
            metadata={"context": context} if context else None,
        )

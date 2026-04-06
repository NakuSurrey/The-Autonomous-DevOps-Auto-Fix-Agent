"""
sft_exporter.py — Exports SFT Training Data in HuggingFace Format

WHAT THIS FILE DOES:
    Takes the training pairs from sft_data_collector.py and writes
    them to a .jsonl file in the format that HuggingFace training
    libraries (Unsloth, PEFT, TRL) expect.

WHY IT EXISTS:
    sft_data_collector.py extracts raw training pairs. But fine-tuning
    tools need data in a specific format. Different tools expect
    different formats. This file handles the formatting so the
    collector stays clean and format-independent.

WHERE IT SITS IN THE CODEBASE:
    agent/sft_exporter.py
    ├── Reads from: agent/sft_data_collector.py (training pairs)
    ├── Writes to: data/sft_dataset.jsonl (the exported dataset)
    └── Does NOT depend on the LLM client, tools, or the ReAct loop

SUPPORTED EXPORT FORMATS:
    1. "alpaca" — the most common SFT format:
       {"instruction": "...", "input": "...", "output": "..."}

    2. "conversational" — for chat-based fine-tuning:
       {"messages": [
           {"role": "system", "content": "..."},
           {"role": "user", "content": "..."},
           {"role": "assistant", "content": "..."}
       ]}

DATA FLOW:
    agent/sft_data_collector.py
        │
        │  collect_training_pairs() returns a list of dicts
        ▼
    THIS FILE (sft_exporter.py)
        │
        │  formats each pair into the target format
        │  writes each formatted pair as one JSON line
        ▼
    data/sft_dataset.jsonl ← ready for fine-tuning
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.config import PROJECT_ROOT
from agent.sft_data_collector import collect_training_pairs


# ==========================================================
# CONSTANTS
# ==========================================================

# where exported datasets go
DATA_DIR = PROJECT_ROOT / "data"

# default output file name
DEFAULT_EXPORT_FILE = DATA_DIR / "sft_dataset.jsonl"


def _ensure_data_dir():
    """
    Creates the data/ directory if it does not exist.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def export_alpaca_format(
    pairs: list[dict],
    output_path: Optional[Path] = None,
) -> dict:
    """
    Exports training pairs in Alpaca format.

    Alpaca format is the most widely supported SFT format.
    Every major fine-tuning tool accepts it: Unsloth, PEFT,
    TRL (from HuggingFace), Axolotl, LLaMA-Factory.

    Each line in the output file looks like:
        {
            "instruction": "You are an Autonomous DevOps Agent...",
            "input": "<test failure output>",
            "output": "<full ReAct trace>"
        }

    Parameters:
        pairs (list[dict]): Training pairs from sft_data_collector.
        output_path (Path): Where to write the file. Defaults to data/sft_dataset.jsonl.

    Returns:
        dict with:
            "success"    (bool): True if export worked
            "file_path"  (str):  Path to the exported file
            "count"      (int):  How many pairs were exported
            "message"    (str):  Description of what happened

    HOW IT WORKS:
        Step 1 → Create the data/ directory if needed
        Step 2 → Open the output file for writing
        Step 3 → For each training pair:
                   a) Build the Alpaca-format dict
                   b) Write it as one JSON line
        Step 4 → Return the result summary
    """
    _ensure_data_dir()
    path = output_path or DEFAULT_EXPORT_FILE

    if not pairs:
        return {
            "success": False,
            "file_path": str(path),
            "count": 0,
            "message": "No training pairs to export. Run the agent first to generate data.",
        }

    try:
        with open(path, "w", encoding="utf-8") as f:
            for pair in pairs:
                alpaca_entry = {
                    "instruction": pair["instruction"],
                    "input": pair["input"],
                    "output": pair["output"],
                }
                f.write(json.dumps(alpaca_entry, ensure_ascii=False) + "\n")

        return {
            "success": True,
            "file_path": str(path),
            "count": len(pairs),
            "message": f"Exported {len(pairs)} training pair(s) to {path}",
        }

    except IOError as e:
        return {
            "success": False,
            "file_path": str(path),
            "count": 0,
            "message": f"Failed to write export file: {e}",
        }


def export_conversational_format(
    pairs: list[dict],
    output_path: Optional[Path] = None,
) -> dict:
    """
    Exports training pairs in conversational (chat) format.

    This format is used for chat-based fine-tuning where the model
    learns from multi-turn conversations. Tools like TRL's
    SFTTrainer accept this format directly.

    Each line in the output file looks like:
        {
            "messages": [
                {"role": "system", "content": "You are an Autonomous DevOps Agent..."},
                {"role": "user", "content": "<test failure output>"},
                {"role": "assistant", "content": "<full ReAct trace>"}
            ]
        }

    Parameters:
        pairs (list[dict]): Training pairs from sft_data_collector.
        output_path (Path): Where to write the file.

    Returns:
        dict: Same structure as export_alpaca_format.

    HOW IT WORKS:
        Step 1 → Create the data/ directory if needed
        Step 2 → Open the output file for writing
        Step 3 → For each training pair:
                   a) Build the messages list (system + user + assistant)
                   b) Write it as one JSON line
        Step 4 → Return the result summary
    """
    _ensure_data_dir()
    path = output_path or (DATA_DIR / "sft_dataset_chat.jsonl")

    if not pairs:
        return {
            "success": False,
            "file_path": str(path),
            "count": 0,
            "message": "No training pairs to export.",
        }

    try:
        with open(path, "w", encoding="utf-8") as f:
            for pair in pairs:
                chat_entry = {
                    "messages": [
                        {"role": "system", "content": pair["instruction"]},
                        {"role": "user", "content": pair["input"]},
                        {"role": "assistant", "content": pair["output"]},
                    ]
                }
                f.write(json.dumps(chat_entry, ensure_ascii=False) + "\n")

        return {
            "success": True,
            "file_path": str(path),
            "count": len(pairs),
            "message": f"Exported {len(pairs)} training pair(s) to {path}",
        }

    except IOError as e:
        return {
            "success": False,
            "file_path": str(path),
            "count": 0,
            "message": f"Failed to write export file: {e}",
        }


def export_dataset_with_metadata(
    output_path: Optional[Path] = None,
    format: str = "alpaca",
) -> dict:
    """
    Full pipeline: collect pairs from logs → export to file.

    This is the main entry point. Call this to go from raw logs
    to a ready-to-use SFT dataset in one step.

    Parameters:
        output_path (Path): Where to write the file. Defaults depend on format.
        format (str): "alpaca" or "conversational". Defaults to "alpaca".

    Returns:
        dict with:
            "success"    (bool)
            "file_path"  (str)
            "count"      (int)
            "format"     (str)
            "message"    (str)
            "metadata"   (dict): Extra info about the export (timestamp, source)

    HOW IT WORKS:
        Step 1 → Call collect_training_pairs() to read logs and build pairs
        Step 2 → Choose the export format
        Step 3 → Call the format-specific export function
        Step 4 → Add metadata to the result
        Step 5 → Return the result
    """
    # Step 1: Collect training pairs from logs
    pairs = collect_training_pairs()

    # Step 2 + 3: Export in the chosen format
    if format == "conversational":
        result = export_conversational_format(pairs, output_path)
    else:
        result = export_alpaca_format(pairs, output_path)

    # Step 4: Add metadata
    result["format"] = format
    result["metadata"] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_log": str(LOG_FILE),
        "total_runs_in_log": len(pairs),
    }

    return result


# reference to LOG_FILE for metadata — imported from sft_data_collector
from agent.sft_data_collector import LOG_FILE  # noqa: E402

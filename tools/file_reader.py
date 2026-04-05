"""
file_reader.py — Reads a File Inside the Docker Container

WHAT THIS FILE DOES:
    Reads the contents of any file inside the sandbox container
    and returns it as a string.

WHY IT EXISTS:
    When a test fails, the agent needs to SEE the code that is broken.
    This file gives the agent the ability to read any file inside
    the container — without touching files on your real machine.

WHERE IT SITS IN THE CODEBASE:
    tools/file_reader.py
    ├── Reads from: agent/config.py (container name, workspace path)
    ├── Used by: agent/react_loop.py (Phase 3) when LLM decides to read a file
    └── Depends on: Docker container running (Phase 1)

HOW IT WORKS:
    Step 1 → Builds the command: docker exec <container> cat <filepath>
    Step 2 → subprocess sends "cat" into the container
    Step 3 → "cat" reads the file and prints its contents to stdout
    Step 4 → subprocess captures that stdout and returns it as a string
"""

import subprocess
from agent.config import SANDBOX_CONTAINER_NAME, SANDBOX_WORKSPACE_PATH


def read_file(file_path: str) -> dict:
    """
    Reads a file from inside the sandbox container.

    Parameters:
        file_path (str): Path to the file, relative to the workspace root.
                         Example: "calculator.py" or "tests/test_calculator.py"

    Returns:
        dict with three keys:
            "success"  (bool) — True if the file was read, False if it failed
            "content"  (str)  — The full file contents (if success=True)
                                 or an error message (if success=False)
            "file_path"(str)  — The full path inside the container
    """

    # --------------------------------------------------
    # Step 1: Build the full path inside the container
    # --------------------------------------------------
    # If file_path = "calculator.py"
    # full_path becomes "/workspace/calculator.py"
    # --------------------------------------------------
    full_path = f"{SANDBOX_WORKSPACE_PATH}/{file_path}"

    # --------------------------------------------------
    # Step 2: Build and execute the command
    # --------------------------------------------------
    # "cat" is a Linux command that reads a file and prints
    # its entire contents to the terminal (stdout).
    # We run "cat" INSIDE the container using "docker exec".
    # --------------------------------------------------
    command = [
        "docker", "exec",
        SANDBOX_CONTAINER_NAME,
        "cat", full_path,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # --------------------------------------------------
        # Step 3: Check if it worked
        # --------------------------------------------------
        # returncode 0 = success
        # returncode 1 = file not found or permission denied
        # --------------------------------------------------
        if result.returncode == 0:
            return {
                "success": True,
                "content": result.stdout,
                "file_path": full_path,
            }
        else:
            return {
                "success": False,
                "content": f"ERROR: Could not read file '{full_path}'. "
                           f"Reason: {result.stderr.strip()}",
                "file_path": full_path,
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "content": f"ERROR: Reading file '{full_path}' timed out after 10 seconds.",
            "file_path": full_path,
        }

    except Exception as e:
        return {
            "success": False,
            "content": f"ERROR: Unexpected error reading file: {str(e)}",
            "file_path": full_path,
        }

"""
file_writer.py — Writes a File Inside the Docker Container

WHAT THIS FILE DOES:
    Takes a string of code (the fix) and writes it to a file
    inside the sandbox container, replacing the old contents.

WHY IT EXISTS:
    After the agent figures out what the fix should be, it needs
    to actually APPLY the fix by writing the corrected code to
    the file. Without this, the agent can think but cannot act.

WHERE IT SITS IN THE CODEBASE:
    tools/file_writer.py
    ├── Reads from: agent/config.py (container name, workspace path)
    ├── Used by: agent/react_loop.py (Phase 3) when LLM generates a fix
    └── Depends on: Docker container running (Phase 1)

HOW IT WORKS:
    Step 1 → Receives the file path and the new content (the fix)
    Step 2 → Builds a command that pipes the content into the container
    Step 3 → Inside the container, "tee" writes the content to the file
    Step 4 → Returns success or failure

WHY WE USE "tee" INSTEAD OF REDIRECTING WITH ">":
    "docker exec" does not support shell redirection (the ">" operator).
    ">" is a shell feature, but "docker exec" runs a single command,
    not a shell. "tee" is a program that reads from stdin and writes
    to a file — it works without needing a shell.
"""

import subprocess
from agent.config import SANDBOX_CONTAINER_NAME, SANDBOX_WORKSPACE_PATH


def write_file(file_path: str, content: str) -> dict:
    """
    Writes content to a file inside the sandbox container.
    This REPLACES the entire file with the new content.

    Parameters:
        file_path (str): Path to the file, relative to the workspace root.
                         Example: "calculator.py"
        content   (str): The complete new file contents to write.

    Returns:
        dict with three keys:
            "success"   (bool) — True if the file was written successfully
            "message"   (str)  — Confirmation or error message
            "file_path" (str)  — The full path inside the container
    """

    # --------------------------------------------------
    # Step 1: Build the full path inside the container
    # --------------------------------------------------
    full_path = f"{SANDBOX_WORKSPACE_PATH}/{file_path}"

    # --------------------------------------------------
    # Step 2: Build the command
    # --------------------------------------------------
    # We use "docker exec -i" with "tee" to write content:
    #
    #   echo "content" | docker exec -i container tee /workspace/file.py
    #
    # But we do this in Python using subprocess.
    #
    # "-i" flag means "interactive" — it allows us to send data
    # through stdin (standard input) to the command inside the container.
    #
    # "tee <path>" reads from stdin and writes to the file at <path>.
    # We redirect tee's stdout to /dev/null so it doesn't echo
    # the content back to us.
    # --------------------------------------------------
    command = [
        "docker", "exec", "-i",
        SANDBOX_CONTAINER_NAME,
        "tee", full_path,
    ]

    try:
        # --------------------------------------------------
        # Step 3: Execute the command with content as stdin
        # --------------------------------------------------
        # input=content → sends the content string as stdin
        #                  to the "tee" command inside the container
        # tee reads that stdin and writes it to the file
        # --------------------------------------------------
        result = subprocess.run(
            command,
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Successfully wrote {len(content)} characters "
                           f"to '{full_path}'.",
                "file_path": full_path,
            }
        else:
            return {
                "success": False,
                "message": f"ERROR: Could not write to '{full_path}'. "
                           f"Reason: {result.stderr.strip()}",
                "file_path": full_path,
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"ERROR: Writing to '{full_path}' timed out after 10 seconds.",
            "file_path": full_path,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"ERROR: Unexpected error writing file: {str(e)}",
            "file_path": full_path,
        }

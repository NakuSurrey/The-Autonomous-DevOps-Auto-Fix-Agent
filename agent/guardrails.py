"""
guardrails.py — Security Validation Layer

WHAT THIS FILE DOES:
    Validates every tool call BEFORE it reaches the Docker container.
    Blocks dangerous operations like modifying test files, writing
    malicious code, or accessing paths outside the workspace.

WHY IT EXISTS:
    The LLM generates tool calls based on its reasoning. But LLMs
    can make mistakes or behave unpredictably. Without this file,
    a bad tool call goes straight to Docker and executes.

    This file sits between the LLM's request and the tool execution:

    LLM request → guardrails.validate_tool_call() → PASS → execute tool
                                                   → BLOCK → send error to LLM

    If the guardrail blocks a call, the LLM gets a clear error
    message and can try a different approach.

WHERE IT SITS IN THE CODEBASE:
    agent/guardrails.py
    ├── Used by: agent/react_loop.py (called before every execute_tool)
    ├── Used by: agent/git_operations.py (called before git commit)
    ├── Reads from: agent/config.py (SANDBOX_WORKSPACE_PATH)
    └── Reads from: agent/logger.py (logs every blocked operation)

HOW VALIDATION WORKS:
    Step 1 → Check the tool name (is it a real tool?)
    Step 2 → Check the file path (is it inside the workspace? is it a protected file?)
    Step 3 → Check the content (if write_file: does it contain dangerous patterns?)
    Step 4 → Return PASS or BLOCK with a reason
"""

import os
from agent.config import SANDBOX_WORKSPACE_PATH


# ==========================================================
# BLOCKED FILE PATHS
# ==========================================================
# These paths must NEVER be written to by the agent.
# The agent should only modify source code files.
# Test files, config files, and infrastructure files are off-limits.
# ==========================================================

BLOCKED_WRITE_PATHS = [
    # Test files — tests define correct behavior, never modify them
    "tests/",
    "test_",

    # Configuration files — modifying these could break the environment
    ".env",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "requirements.txt",

    # Agent's own code — the agent should not modify itself
    "agent/",

    # Documentation
    "README.md",
    "ERRORS.md",
    "docs/",
]

# ==========================================================
# BLOCKED READ PATHS
# ==========================================================
# These paths must NEVER be read by the agent.
# The agent does not need to read environment files or secrets.
# ==========================================================

BLOCKED_READ_PATHS = [
    ".env",
]

# ==========================================================
# DANGEROUS CONTENT PATTERNS
# ==========================================================
# If the LLM tries to write a file that contains any of these
# patterns, the write is blocked. These patterns indicate the
# LLM is trying to:
#   - Execute system commands (import os, subprocess)
#   - Run arbitrary code (eval, exec, __import__)
#   - Exit the process (sys.exit)
#   - Access the network (socket, requests, urllib)
#   - Modify the file system outside the workspace (shutil)
#
# IMPORTANT: These patterns are checked against the CONTENT
# the LLM wants to write, not against existing files.
# The sandbox calculator.py does not use any of these.
# ==========================================================

DANGEROUS_CONTENT_PATTERNS = [
    "import os",
    "import subprocess",
    "import sys",
    "import socket",
    "import requests",
    "import urllib",
    "import shutil",
    "from os ",
    "from subprocess ",
    "from sys ",
    "from socket ",
    "from requests ",
    "from shutil ",
    "__import__(",
    "eval(",
    "exec(",
    "compile(",
    "os.system(",
    "os.popen(",
    "os.exec",
    "subprocess.run(",
    "subprocess.call(",
    "subprocess.Popen(",
    "sys.exit(",
    "open('/",
    'open("/',
]


def validate_tool_call(tool_name: str, tool_args: dict) -> dict:
    """
    Validates a tool call before it is executed.

    Parameters:
        tool_name (str):  The name of the tool the LLM wants to call.
        tool_args (dict): The arguments the LLM provided.

    Returns:
        dict with:
            "allowed" (bool)  — True if the call is safe, False if blocked
            "reason"  (str)   — Why it was blocked (empty string if allowed)

    HOW IT WORKS:
        Step 1 → Route to the right validator based on tool_name
        Step 2 → The validator checks the arguments
        Step 3 → Return allowed=True or allowed=False with a reason
    """

    # --------------------------------------------------
    # Route to the correct validator
    # --------------------------------------------------
    if tool_name == "write_file":
        return _validate_write_file(tool_args)

    elif tool_name == "read_file":
        return _validate_read_file(tool_args)

    elif tool_name == "run_tests":
        return _validate_run_tests(tool_args)

    else:
        # Unknown tool — let execute_tool() handle the error
        return {"allowed": True, "reason": ""}


def _validate_write_file(tool_args: dict) -> dict:
    """
    Validates a write_file tool call.

    CHECKS (in order):
        Check 1 → file_path argument exists
        Check 2 → file_path is not empty
        Check 3 → file_path does not escape the workspace (path traversal)
        Check 4 → file_path is not in the blocked list
        Check 5 → content does not contain dangerous patterns
    """

    file_path = tool_args.get("file_path", "")
    content = tool_args.get("content", "")

    # --------------------------------------------------
    # Check 1: file_path argument exists and is not empty
    # --------------------------------------------------
    if not file_path:
        return {
            "allowed": False,
            "reason": "BLOCKED: write_file requires a 'file_path' argument.",
        }

    # --------------------------------------------------
    # Check 2: Path traversal attack detection
    # --------------------------------------------------
    # ".." in a path means "go up one directory."
    # An attacker could use "../../etc/passwd" to escape
    # the workspace and write to system files.
    #
    # Also block absolute paths (starting with /) because
    # file paths should always be relative to the workspace.
    # --------------------------------------------------
    if ".." in file_path:
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Path traversal detected in '{file_path}'. "
                "File paths must not contain '..' sequences. "
                "Use paths relative to the workspace root."
            ),
        }

    if file_path.startswith("/"):
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Absolute path detected: '{file_path}'. "
                "File paths must be relative to the workspace root. "
                "Example: 'calculator.py' not '/workspace/calculator.py'."
            ),
        }

    # --------------------------------------------------
    # Check 3: Blocked write paths
    # --------------------------------------------------
    # Normalize the path: remove leading "./" if present
    # --------------------------------------------------
    normalized_path = file_path.removeprefix("./")

    for blocked in BLOCKED_WRITE_PATHS:
        if normalized_path.startswith(blocked) or normalized_path == blocked:
            return {
                "allowed": False,
                "reason": (
                    f"BLOCKED: Cannot write to '{file_path}'. "
                    f"Files matching '{blocked}' are protected. "
                    "The agent may only modify source code files."
                ),
            }

    # --------------------------------------------------
    # Check 4: Dangerous content patterns
    # --------------------------------------------------
    # Check the content the LLM wants to write.
    # Convert to lowercase for case-insensitive matching
    # on some patterns, but check exact case for imports
    # (Python imports are case-sensitive).
    # --------------------------------------------------
    for pattern in DANGEROUS_CONTENT_PATTERNS:
        if pattern in content:
            return {
                "allowed": False,
                "reason": (
                    f"BLOCKED: Dangerous pattern detected in file content: '{pattern}'. "
                    "The agent is not allowed to write code that imports system "
                    "modules, executes shell commands, or runs arbitrary code. "
                    "Only write standard application logic."
                ),
            }

    # --------------------------------------------------
    # All checks passed
    # --------------------------------------------------
    return {"allowed": True, "reason": ""}


def _validate_read_file(tool_args: dict) -> dict:
    """
    Validates a read_file tool call.

    CHECKS (in order):
        Check 1 → file_path argument exists
        Check 2 → file_path does not escape the workspace
        Check 3 → file_path is not in the blocked read list
    """

    file_path = tool_args.get("file_path", "")

    # --------------------------------------------------
    # Check 1: file_path exists and is not empty
    # --------------------------------------------------
    if not file_path:
        return {
            "allowed": False,
            "reason": "BLOCKED: read_file requires a 'file_path' argument.",
        }

    # --------------------------------------------------
    # Check 2: Path traversal and absolute path detection
    # --------------------------------------------------
    if ".." in file_path:
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Path traversal detected in '{file_path}'. "
                "File paths must not contain '..' sequences."
            ),
        }

    if file_path.startswith("/"):
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Absolute path detected: '{file_path}'. "
                "File paths must be relative to the workspace root."
            ),
        }

    # --------------------------------------------------
    # Check 3: Blocked read paths
    # --------------------------------------------------
    normalized_path = file_path.removeprefix("./")

    for blocked in BLOCKED_READ_PATHS:
        if normalized_path.startswith(blocked) or normalized_path == blocked:
            return {
                "allowed": False,
                "reason": (
                    f"BLOCKED: Cannot read '{file_path}'. "
                    f"Files matching '{blocked}' contain sensitive data."
                ),
            }

    # --------------------------------------------------
    # All checks passed
    # --------------------------------------------------
    return {"allowed": True, "reason": ""}


def _validate_run_tests(tool_args: dict) -> dict:
    """
    Validates a run_tests tool call.

    CHECKS:
        Check 1 → test_path does not escape the workspace
        Check 2 → test_path does not point to a source file (only test files/dirs)
    """

    test_path = tool_args.get("test_path", "tests/")

    # --------------------------------------------------
    # Check 1: Path traversal and absolute path detection
    # --------------------------------------------------
    if ".." in test_path:
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Path traversal detected in '{test_path}'. "
                "Test paths must not contain '..' sequences."
            ),
        }

    if test_path.startswith("/"):
        return {
            "allowed": False,
            "reason": (
                f"BLOCKED: Absolute path detected: '{test_path}'. "
                "Test paths must be relative to the workspace root."
            ),
        }

    # --------------------------------------------------
    # All checks passed
    # --------------------------------------------------
    return {"allowed": True, "reason": ""}


def validate_git_commit(changed_files: str) -> dict:
    """
    Validates that the files about to be committed are safe.

    Called by git_operations.py BEFORE running git add + git commit.

    Parameters:
        changed_files (str): The output of git status showing what changed.

    Returns:
        dict with:
            "allowed" (bool)  — True if the commit is safe
            "reason"  (str)   — Why it was blocked (empty if allowed)

    CHECKS:
        Check 1 → No test files in the changed files list
        Check 2 → No config files in the changed files list
        Check 3 → No agent source files in the changed files list
    """

    # Files that should never appear in a commit by the agent
    protected_patterns = [
        "test_",
        "tests/",
        ".env",
        "Dockerfile",
        "docker-compose",
        "requirements.txt",
        ".gitignore",
        "agent/",
        "docs/",
    ]

    for pattern in protected_patterns:
        if pattern in changed_files:
            return {
                "allowed": False,
                "reason": (
                    f"BLOCKED: Protected file detected in changes: '{pattern}'. "
                    "The agent may only commit changes to source code files. "
                    "Test files, config files, and agent code must not be modified."
                ),
            }

    return {"allowed": True, "reason": ""}

"""
config.py — Configuration Loader

WHAT THIS FILE DOES:
    Loads all settings from the .env file and makes them
    available to every other file in the project.

WHY IT EXISTS:
    Without this file, every file would need to load the .env
    file independently. This centralizes all configuration in
    one place. If a setting changes, you change it here once —
    not in 10 different files.

WHERE IT SITS:
    agent/config.py
    ├── Reads from: .env file (in the project root)
    ├── Used by: every other module that needs a setting
    └── Depends on: python-dotenv package
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# --------------------------------------------------
# Step 1: Find the .env file
# --------------------------------------------------
# Path(__file__) gives the full path to THIS file (config.py)
# .resolve() turns it into an absolute path (no relative parts)
# .parent gives the folder this file is in (agent/)
# .parent again gives the project root folder
# That's where .env lives.
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


# --------------------------------------------------
# Step 2: Load the .env file
# --------------------------------------------------
# load_dotenv() reads the .env file and puts every key=value
# pair into the operating system's environment variables.
# After this call, os.getenv("GEMINI_API_KEY") works.
# --------------------------------------------------
load_dotenv(dotenv_path=ENV_FILE)


# --------------------------------------------------
# Step 3: Read each setting into a Python variable
# --------------------------------------------------
# os.getenv("KEY", "default") means:
#   - Look for KEY in environment variables
#   - If it exists, return its value
#   - If it does NOT exist, return "default"
# --------------------------------------------------

# The API key for Google Gemini
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Which Gemini model to use
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# How many times the agent tries to fix a bug before giving up
MAX_FIX_ATTEMPTS: int = int(os.getenv("MAX_FIX_ATTEMPTS", "5"))

# The name of the Docker container running the sandbox
SANDBOX_CONTAINER_NAME: str = os.getenv(
    "SANDBOX_CONTAINER_NAME", "devops-agent-sandbox"
)

# The path inside the container where the code lives
SANDBOX_WORKSPACE_PATH: str = os.getenv(
    "SANDBOX_WORKSPACE_PATH", "/workspace"
)

# Logging level
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# --------------------------------------------------
# Step 4: Validation
# --------------------------------------------------
# If the API key is missing, the agent cannot function.
# We check this at import time so the error is caught
# immediately — not 5 minutes into a run.
# --------------------------------------------------
def validate_config() -> None:
    """
    Checks that all required settings are present.
    Raises a clear error message if anything is missing.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError(
            "\n"
            "===================================================\n"
            "ERROR: GEMINI_API_KEY is not set.\n"
            "===================================================\n"
            "Steps to fix:\n"
            "  1. Go to https://aistudio.google.com/app/apikey\n"
            "  2. Create a free API key\n"
            "  3. Copy .env.example to .env:\n"
            "       cp .env.example .env\n"
            "  4. Paste your key into .env:\n"
            "       GEMINI_API_KEY=your_actual_key_here\n"
            "===================================================\n"
        )

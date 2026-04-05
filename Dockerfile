# ============================================
# Autonomous DevOps & Auto-Fix Agent - Sandbox Container
# ============================================
# This Dockerfile builds the isolated sandbox where the agent
# runs tests, reads files, writes fixes, and commits with git.
# Nothing the agent does inside this container can affect your
# real machine.
# ============================================

# Base image: Python 3.11 on a slim Debian build
# "slim" means it has the minimum packages needed — keeps the image small
FROM python:3.11-slim

# Install system dependencies:
#   git        — version control (agent commits fixes here)
#   gcc        — C compiler (some Python packages need it to install)
#   --no-install-recommends — skip optional packages to keep image small
RUN apt-get update && \
    apt-get install -y --no-install-recommends git gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install pytest inside the container
# The agent runs "pytest" inside this container to test the code
RUN pip install --no-cache-dir pytest

# Create the workspace directory inside the container
# This is where the dummy repo (calculator + tests) will live
RUN mkdir -p /workspace

# Copy the sandbox files (calculator + tests) INTO the container
# COPY means: take files from your real machine and place them
# inside the container. After this, the container has its own
# independent copy — changes inside do NOT affect your real files.
COPY sandbox/ /workspace/

# Initialize a git repository inside the container's workspace
# This git repo is completely separate from any repo on your machine
RUN cd /workspace && \
    git init && \
    git config user.email "devops-agent@auto-fix.local" && \
    git config user.name "DevOps Auto-Fix Agent" && \
    git add -A && \
    git commit -m "Initial commit: calculator with intentional bugs"

# Set the working directory
# Any command that runs inside this container starts in /workspace
WORKDIR /workspace

# Keep the container running so the agent can send commands to it
# "tail -f /dev/null" means: do nothing but stay alive forever
# Without this, the container would start and immediately stop
CMD ["tail", "-f", "/dev/null"]

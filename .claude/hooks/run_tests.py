#!/usr/bin/env python3
"""PostToolUse hook for Kimika: run pytest after Claude edits a Python file.

- Only runs for .py files, and only once a tests/ folder exists.
- On failure, exits 2 so the test output is sent back to Claude to fix.
- On success, stays quiet apart from a one-line summary.
"""
import json
import os
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    args = data.get("tool_input", {}) or {}
    path = args.get("file_path") or args.get("notebook_path") or ""
    if not path.endswith(".py"):
        sys.exit(0)

    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if not os.path.isdir(os.path.join(project, "tests")):
        sys.exit(0)  # nothing to run yet (early scaffold steps)

    # Prefer the project's virtual environment, where pytest is installed
    python = sys.executable
    for candidate in (".venv/bin/python", "venv/bin/python", ".venv/Scripts/python.exe", "venv/Scripts/python.exe"):
        full = os.path.join(project, candidate)
        if os.path.exists(full):
            python = full
            break

    try:
        result = subprocess.run(
            [python, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        sys.exit(0)
    except subprocess.TimeoutExpired:
        print("pytest timed out after 120s. Check for tests making network calls.", file=sys.stderr)
        sys.exit(2)

    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0 or result.returncode == 5:  # 5 = no tests collected
        last = output.splitlines()[-1] if output else "no tests yet"
        print(f"pytest: {last}")
        sys.exit(0)

    if "No module named pytest" in output:
        # Don't block edits during setup; just remind once per edit
        print("Note: pytest isn't installed yet, so tests were skipped. Run: pip install pytest")
        sys.exit(0)

    tail = "\n".join(output.splitlines()[-40:])
    print(f"Tests failed after editing {os.path.basename(path)}. Fix before continuing:\n{tail}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()

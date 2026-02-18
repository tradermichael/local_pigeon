"""
Environment variable persistence utilities.

Extracted from app.py for reuse across CLI and UI.
"""

import os

from local_pigeon.config import get_data_dir


def save_env_var(key: str, value: str) -> None:
    """Save an environment variable to the .env file and current process.

    Reads the existing .env in the data directory, updates or inserts
    the key, and writes it back.  Also sets the var in the running process.
    """
    os.environ[key] = value

    data_dir = get_data_dir()
    env_path = data_dir / ".env"

    # Read existing entries
    existing: dict[str, str] = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k] = v

    existing[key] = value

    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

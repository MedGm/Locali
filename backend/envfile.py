"""Read KEY=VALUE lines from a .env file into the environment, without overriding what is set.

The backend, the web app (next.config.ts) and scripts/run.sh all read the same root .env, so the
API token and model keys are written once. A value given on the command line still wins.
"""

import os
import re
from pathlib import Path

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_env(path: str | Path) -> list[str]:
    """Returns the names that were set from the file."""
    path = Path(path)
    if not path.is_file():
        return []
    loaded = []
    for raw in path.read_text().splitlines():
        m = _LINE.match(raw)
        if not m or raw.lstrip().startswith("#"):
            continue
        name, value = m.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded

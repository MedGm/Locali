"""Wrap a spike/training script into a Kaggle notebook.

Kaggle runs notebooks reliably, but a notebook has no __file__ for subprocess re-entry.
The notebook therefore writes the script to /kaggle/working and runs it as a real file.

    python training/kaggle/build_notebook.py training/kaggle/w1-spikes/w1_spikes.py
    python training/kaggle/build_notebook.py training/kaggle/baselines/kaggle_baselines.py LIMIT=3

KEY=VALUE arguments become environment variables of the script run (Kaggle notebooks cannot
receive environment variables from the CLI). The placeholder __LOCALI_COMMIT__ in the script is
replaced by the current git HEAD, so the job runs exactly the pushed code.
"""

import json
import subprocess
import sys
from pathlib import Path


def build(script: Path, env: dict[str, str] | None = None) -> Path:
    source = script.read_text()
    if "__LOCALI_COMMIT__" in source:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        source = source.replace("__LOCALI_COMMIT__", head)
    env = env or {}
    cells = [
        (
            "markdown",
            (
                f"# {script.stem}\n\nGenerated from `{script.name}` by `build_notebook.py`. "
                "Edit the script, not this notebook."
            ),
        ),
        ("code", f"%%writefile /kaggle/working/{script.name}\n{source}"),
        # `!python` output is buffered until the cell ends in Kaggle batch runs; stream it instead.
        (
            "code",
            (
                "import os\n"
                "import subprocess\n"
                "import sys\n\n"
                f"env = {{**os.environ, **{env!r}}}\n"
                f"proc = subprocess.Popen([sys.executable, '-u', '/kaggle/working/{script.name}'],\n"
                "                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)\n"
                "for line in proc.stdout:\n"
                "    print(line, end='', flush=True)\n"
                "print('exit code', proc.wait())"
            ),
        ),
    ]
    notebook = {
        "cells": [
            {
                "cell_type": kind,
                "id": f"cell-{i}",
                "metadata": {},
                "source": text.splitlines(keepends=True),
                **({"outputs": [], "execution_count": None} if kind == "code" else {}),
            }
            for i, (kind, text) in enumerate(cells)
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    out = script.with_suffix(".ipynb")
    out.write_text(json.dumps(notebook, indent=1))
    return out


if __name__ == "__main__":
    pairs = dict(arg.split("=", 1) for arg in sys.argv[2:])
    print(build(Path(sys.argv[1]), pairs))

"""Wrap a spike/training script into a Kaggle notebook.

Kaggle runs notebooks reliably, but a notebook has no __file__ for subprocess re-entry.
The notebook therefore writes the script to /kaggle/working and runs it as a real file.

    python training/kaggle/build_notebook.py training/kaggle/w1-spikes/w1_spikes.py
"""

import json
import sys
from pathlib import Path


def build(script: Path) -> Path:
    source = script.read_text()
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
                "import subprocess\n"
                "import sys\n\n"
                f"proc = subprocess.Popen([sys.executable, '-u', '/kaggle/working/{script.name}'],\n"
                "                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)\n"
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
    print(build(Path(sys.argv[1])))

"""GPU energy from an `nvidia-smi` power log.

Log format (one line per GPU per sample):
    nvidia-smi --query-gpu=timestamp,index,power.draw,memory.used --format=csv,noheader,nounits -lms 1000

Energy is the trapezoidal integral of board power over a run's time window, summed over the GPUs
the run used. It covers the whole board (idle draw included), like RAPL covers the whole CPU
package. Timestamps are the machine's local time, so integrate on the machine that wrote the log.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path


@dataclass
class PowerSample:
    time: float  # POSIX seconds
    gpu: int
    watts: float
    memory_mib: float


def parse_power_log(text: str) -> list[PowerSample]:
    samples = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            # nvidia-smi writes local time: interpret it as such, explicitly
            when = datetime.strptime(parts[0], "%Y/%m/%d %H:%M:%S.%f").astimezone().timestamp()
            samples.append(PowerSample(when, int(parts[1]), float(parts[2]), float(parts[3])))
        except ValueError:
            continue  # header or "[N/A]"
    return samples


def energy_joules(samples: list[PowerSample], gpus: list[int], start: float, end: float) -> float | None:
    total, found = 0.0, False
    for gpu in gpus:
        points = sorted((s.time, s.watts) for s in samples if s.gpu == gpu and start <= s.time <= end)
        for (t0, w0), (t1, w1) in pairwise(points):
            total += (w0 + w1) / 2 * (t1 - t0)
            found = True
    return total if found else None


def attach_gpu_energy(run_dir: Path, log_text: str, gpus: list[int], start: float, end: float) -> dict:
    samples = parse_power_log(log_text)
    joules = energy_joules(samples, gpus, start, end)
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    n = summary.get("metrics", {}).get("n") or 0
    peak_mib = max((s.memory_mib for s in samples if s.gpu in gpus and start <= s.time <= end), default=None)
    summary["gpu_energy"] = {
        "gpus": gpus,
        "window_s": round(end - start, 1),
        "total_j": round(joules, 1) if joules is not None else None,
        "j_per_task": round(joules / n, 2) if joules is not None and n else None,
        "peak_memory_mib_per_gpu": peak_mib,
        "method": "trapezoidal integral of nvidia-smi power.draw at 1 s, whole board",
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary["gpu_energy"]

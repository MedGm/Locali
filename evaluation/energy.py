"""CPU package energy from Intel RAPL (Linux powercap).

The counter is root-readable by default (mitigation for the PLATYPUS side channel). When it
cannot be read, measurements report None instead of failing the run.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

RAPL_PACKAGE = Path("/sys/class/powercap/intel-rapl:0")


@dataclass
class EnergyReading:
    joules: float | None = None


class RaplMeter:
    def __init__(
        self,
        energy_file: Path = RAPL_PACKAGE / "energy_uj",
        max_range_file: Path = RAPL_PACKAGE / "max_energy_range_uj",
    ):
        self.energy_file = energy_file
        self.max_range_file = max_range_file
        self.available = self._read(energy_file) is not None

    @staticmethod
    def _read(path: Path) -> int | None:
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            return None

    @contextmanager
    def measure(self) -> Iterator[EnergyReading]:
        reading = EnergyReading()
        start = self._read(self.energy_file) if self.available else None
        try:
            yield reading
        finally:
            end = self._read(self.energy_file) if start is not None else None
            if start is not None and end is not None:
                delta = end - start
                if delta < 0:  # counter wrapped around
                    delta += self._read(self.max_range_file) or 0
                reading.joules = delta / 1e6

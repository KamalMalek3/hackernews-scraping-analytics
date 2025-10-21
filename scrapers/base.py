from __future__ import annotations

import csv
import dataclasses
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclasses.dataclass
class ScraperStats:
    """Holds networking and performance data for a run."""

    method: str
    total_time_s: float
    total_requests: int
    total_bytes: int
    avg_latency_ms: float

    def to_row(self) -> Dict[str, float]:
        return {
            "method": self.method,
            "total_time_s": self.total_time_s,
            "total_requests": self.total_requests,
            "total_bytes": self.total_bytes,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclasses.dataclass
class RequestEvent:
    """Per-request instrumentation data."""

    url: str
    method: str
    status_code: int
    elapsed_ms: float
    bytes_read: int
    timestamp: float

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ScraperResult:
    """Container for scraping output and metrics."""

    records: List[Dict[str, Optional[str]]]
    stats: ScraperStats
    raw_events: Optional[List[RequestEvent]] = None

    def dump_csv(self, path: Path) -> None:
        if not self.records:
            raise ValueError("ScraperResult.records is empty; nothing to write.")
        fieldnames = list(self.records[0].keys())
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.records)


def write_stats_csv(
    stats: Iterable[ScraperStats], path: Path, mode: str = "w"
) -> None:
    stats = list(stats)
    if not stats:
        raise ValueError("No stats to write.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(stats[0].to_row().keys())
    with path.open(mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for stat in stats:
            writer.writerow(stat.to_row())


class Timer:
    """Context manager to measure elapsed time in seconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed(self) -> float:
        if not hasattr(self, "_end"):
            return time.perf_counter() - self._start
        return self._end - self._start

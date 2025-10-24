#!/usr/bin/env python3
"""
Collects interface bandwidth statistics to complement live nload monitoring.

The sampler reads rx/tx byte counters from /sys/class/net and writes a CSV file.
Optional plotting (matplotlib) produces a PNG line chart mirroring the trends
you would see in nload.
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class Sample:
    elapsed: float
    timestamp_iso: str
    rx_mbps: float
    tx_mbps: float


def read_bytes(path: Path) -> int:
    return int(path.read_text().strip())


def sample_interface(interface: str, duration: int, interval: float) -> List[Sample]:
    base = Path("/sys/class/net") / interface / "statistics"
    if not base.exists():
        raise FileNotFoundError(
            f"Interface '{interface}' not found under /sys/class/net."
        )

    rx_path = base / "rx_bytes"
    tx_path = base / "tx_bytes"
    rx_prev = read_bytes(rx_path)
    tx_prev = read_bytes(tx_path)
    time_prev = time.time()
    time_start = time_prev
    samples: List[Sample] = []

    # The first delta arrives after one interval.
    while True:
        time.sleep(interval)
        now = time.time()
        elapsed = now - time_start
        if elapsed > duration:
            break

        rx_curr = read_bytes(rx_path)
        tx_curr = read_bytes(tx_path)
        delta_t = now - time_prev
        if delta_t <= 0:
            continue

        rx_rate = (rx_curr - rx_prev) * 8 / 1_000_000 / delta_t
        tx_rate = (tx_curr - tx_prev) * 8 / 1_000_000 / delta_t

        samples.append(
            Sample(
                elapsed=round(elapsed, 2),
                timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                rx_mbps=max(rx_rate, 0.0),
                tx_mbps=max(tx_rate, 0.0),
            )
        )

        rx_prev = rx_curr
        tx_prev = tx_curr
        time_prev = now

    return samples


def write_csv(path: Path, samples: Iterable[Sample]) -> None:
    fieldnames = ["timestamp_iso", "elapsed_s", "rx_mbps", "tx_mbps"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for sample in samples:
            writer.writerow(
                {
                    "timestamp_iso": sample.timestamp_iso,
                    "elapsed_s": f"{sample.elapsed:.2f}",
                    "rx_mbps": f"{sample.rx_mbps:.6f}",
                    "tx_mbps": f"{sample.tx_mbps:.6f}",
                }
            )


def plot(samples: List[Sample], png_path: Path) -> None:
    import matplotlib.pyplot as plt

    if not samples:
        raise RuntimeError("No samples collected; unable to render chart.")

    elapsed = [s.elapsed for s in samples]
    rx = [s.rx_mbps for s in samples]
    tx = [s.tx_mbps for s in samples]

    plt.figure(figsize=(10, 5))
    plt.plot(elapsed, rx, label="Incoming (Mbps)", color="#1f77b4")
    plt.plot(elapsed, tx, label="Outgoing (Mbps)", color="#ff7f0e")
    plt.xlabel("Elapsed Time (s)")
    plt.ylabel("Throughput (Mbps)")
    plt.title("Interface Bandwidth Sample")
    plt.grid(True, linewidth=0.4, alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=150)
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample interface bandwidth and optionally plot a chart."
    )
    parser.add_argument(
        "--interface",
        "-i",
        required=True,
        help="Network interface (e.g., eth0).",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=60,
        help="Total sampling duration in seconds.",
    )
    parser.add_argument(
        "--interval",
        "-s",
        type=float,
        default=1.0,
        help="Sampling interval in seconds.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="CSV file where sampled data will be stored.",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=None,
        help="Optional PNG path for rendering a line chart.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = sample_interface(args.interface, args.duration, args.interval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.output, samples)
    if args.plot is not None:
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        plot(samples, args.plot)


if __name__ == "__main__":
    main()


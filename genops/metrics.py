"""
metrics.py
Honest measurement. Timer wraps real wall-clock work (no fabricated 60/40
splits). Audit log appends one row per request for the governance trail.
"""
import os
import csv
import time

LOG_PATH = "sandbox_metrics.csv"
_HEADER = ["timestamp", "resource_id", "stack", "verdict", "duration_s", "mode"]


class Timer:
    """Context manager that records real elapsed seconds."""
    def __enter__(self):
        self._start = time.perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, *exc):
        self.elapsed = round(time.perf_counter() - self._start, 3)
        return False


def log_audit(row: list, path: str = LOG_PATH) -> None:
    is_new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(_HEADER)
        writer.writerow(row)


def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

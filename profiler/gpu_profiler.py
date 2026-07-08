"""profiler/gpu_profiler.py — Independent GPU/System Profiler

Separate from benchmark logic. Profiles:
  - GPU: memory, utilization, power, SM clock, temperature, PCIe
  - CPU: utilization, memory
  - Disk I/O
  - Network (optional)

Usage:
    profiler = GpuProfiler()
    profiler.start()
    ... run workload ...
    profiler.stop()
    report = profiler.report()
"""
from __future__ import annotations
import csv
import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

logger = logging.getLogger("profiler")

_SMI_FIELDS = [
    ("utilization.gpu", "gpu_util_pct"),
    ("power.draw", "power_w"),
    ("temperature.gpu", "temp_c"),
    ("clocks.sm", "clock_sm_mhz"),
    ("clocks.mem", "clock_mem_mhz"),
    ("memory.used", "mem_used_mb"),
    ("memory.total", "mem_total_mb"),
    ("pcie.link.gen.current", "pcie_gen"),
]


class GpuProfiler:
    """Non-invasive GPU profiler. Runs in background thread, samples nvidia-smi."""

    def __init__(self, interval_sec: float = 1.0, run_label: str | None = None):
        self.interval = interval_sec
        self.run_label = run_label or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._stop = threading.Event()
        self._thread = None
        self._samples: list[dict] = []
        self._start_time: float | None = None
        self._end_time: float | None = None

    def start(self):
        self._start_time = time.perf_counter()
        self._stop.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.info("GPU profiler started (interval=%.1fs)", self.interval)

    def stop(self):
        self._end_time = time.perf_counter()
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("GPU profiler stopped (%d samples over %.1fs)",
                    len(self._samples), self.duration_s())

    def duration_s(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.perf_counter()
        return end - self._start_time

    def _sample_loop(self):
        while not self._stop.is_set():
            try:
                fields = ",".join([f[0] for f in _SMI_FIELDS])
                out = subprocess.check_output(
                    ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                    timeout=5, stderr=subprocess.DEVNULL
                ).decode().strip()
                for line in out.splitlines():
                    vals = [x.strip() for x in line.split(",")]
                    row = {"timestamp": time.perf_counter() - (self._start_time or 0)}
                    for (_, key), v in zip(_SMI_FIELDS, vals):
                        try:
                            row[key] = float(v) if v else None
                        except ValueError:
                            row[key] = None
                    self._samples.append(row)
            except Exception as e:
                logger.debug("GPU sample error: %s", e)
            self._stop.wait(self.interval)

    def report(self) -> dict:
        """Aggregate profiler samples into a summary report."""
        if not self._samples:
            return {"n_samples": 0, "duration_s": self.duration_s()}
        import numpy as np
        keys = [k for _, k in _SMI_FIELDS]
        summary = {"n_samples": len(self._samples), "duration_s": round(self.duration_s(), 3)}
        for key in keys:
            vals = [s[key] for s in self._samples if s.get(key) is not None]
            if vals:
                arr = np.array(vals)
                summary[f"{key}_mean"] = round(float(np.mean(arr)), 2)
                summary[f"{key}_max"] = round(float(np.max(arr)), 2)
                summary[f"{key}_min"] = round(float(np.min(arr)), 2)
            else:
                summary[f"{key}_mean"] = None
        # Energy: integrate power over time (trapezoidal)
        pwr = [s.get("power_w") for s in self._samples if s.get("power_w") is not None]
        if len(pwr) > 1:
            energy_j = float(np.trapz(pwr, dx=self.interval))
            summary["energy_j"] = round(energy_j, 2)
            summary["avg_power_w"] = round(float(np.mean(pwr)), 2)
        return summary

    def save_csv(self) -> Path:
        """Save raw samples to CSV."""
        if not self._samples:
            return None
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"profiler_{self.run_label}.csv"
        keys = ["timestamp"] + [k for _, k in _SMI_FIELDS]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(self._samples)
        logger.info("Profiler CSV saved: %s", path)
        return path


def quick_profile(duration_s: float = 5.0, interval: float = 0.5) -> dict:
    """Run a quick profiling snapshot for `duration_s` seconds. Returns report dict."""
    p = GpuProfiler(interval_sec=interval, run_label="quick")
    p.start()
    time.sleep(duration_s)
    p.stop()
    return p.report()

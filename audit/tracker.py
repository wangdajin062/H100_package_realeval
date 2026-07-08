"""audit/tracker.py — Automatic Experiment Audit Trail

Every run auto-generates:
  audit/
    {run_id}/
      run.json          — experiment config, timestamps
      environment.json  — Python, torch, CUDA, driver versions
      git.json          — commit hash, dirty flag, branch
      hardware.json     — GPU model, count, compute capability, memory
      dataset.json      — paths, hashes, sample counts
      model.json        — model paths, quantization, dtype, parameter count
      prompt.json       — prompt template hash, token counts
      metric.json       — all computed metrics with provenance
      profiler.json     — GPU profiling summary
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_ROOT = ROOT / "outputs" / "audit"


class RunTracker:
    """Tracks a single experiment run, writing audit files on completion."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = AUDIT_ROOT / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}

    # ── Collectors ──

    def capture_environment(self) -> dict:
        info = {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "executable": sys.executable,
        }
        try:
            import torch
            info["torch_version"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_version"] = torch.version.cuda
        except Exception:
            info["torch_version"] = "not_installed"
        try:
            import transformers
            info["transformers_version"] = transformers.__version__
        except Exception:
            pass
        try:
            import numpy
            info["numpy_version"] = numpy.__version__
        except Exception:
            pass
        # NVIDIA driver
        try:
            drv = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                timeout=5, stderr=subprocess.DEVNULL
            ).decode().strip().splitlines()
            info["nvidia_driver"] = drv[0] if drv else None
        except Exception:
            info["nvidia_driver"] = None
        self._data["environment"] = info
        return info

    def capture_git(self) -> dict:
        info = {}
        try:
            info["commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], timeout=5, stderr=subprocess.DEVNULL,
                cwd=str(ROOT)
            ).decode().strip()
        except Exception:
            info["commit"] = None
        try:
            info["branch"] = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5, stderr=subprocess.DEVNULL,
                cwd=str(ROOT)
            ).decode().strip()
        except Exception:
            info["branch"] = None
        try:
            porcelain = subprocess.check_output(
                ["git", "status", "--porcelain"], timeout=5, stderr=subprocess.DEVNULL,
                cwd=str(ROOT)
            ).decode().strip()
            info["dirty"] = len(porcelain) > 0
        except Exception:
            info["dirty"] = None
        self._data["git"] = info
        return info

    def capture_hardware(self) -> dict:
        info = {"cpu_count": os.cpu_count()}
        try:
            import torch
            if torch.cuda.is_available():
                info["gpu_count"] = torch.cuda.device_count()
                info["gpu_names"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
                info["compute_capability"] = [list(torch.cuda.get_device_capability(i))
                                              for i in range(torch.cuda.device_count())]
                info["bf16_supported"] = torch.cuda.is_bf16_supported()
        except Exception:
            pass
        try:
            mem = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                timeout=5, stderr=subprocess.DEVNULL
            ).decode().strip().splitlines()
            info["gpu_memory_mb"] = [int(x.strip()) for x in mem if x.strip()]
        except Exception:
            pass
        self._data["hardware"] = info
        return info

    def capture_dataset(self, dataset_paths: list[str] | None = None) -> dict:
        info = {"paths": dataset_paths or [], "hashes": {}}
        for p in (dataset_paths or []):
            path = Path(p)
            if path.exists():
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                info["hashes"][str(path)] = h.hexdigest()[:16]
            else:
                info["hashes"][str(path)] = None
        self._data["dataset"] = info
        return info

    def capture_model(self, config: dict | None = None) -> dict:
        info = {}
        models = (config or {}).get("models", {})
        for key, val in models.items():
            info[key] = str(val)
        self._data["model"] = info
        return info

    def capture_prompt(self, prompt_template: str | None = None) -> dict:
        info = {"template": prompt_template}
        if prompt_template:
            info["template_hash"] = hashlib.sha256(prompt_template.encode()).hexdigest()[:16]
        self._data["prompt"] = info
        return info

    def capture_config(self, config: dict | None = None) -> dict:
        info = dict(config or {})
        info["config_hash"] = hashlib.sha256(
            json.dumps(config or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:16]
        self._data["run"] = info
        return info

    def capture_metrics(self, metrics: dict) -> dict:
        self._data["metric"] = metrics
        return metrics

    def capture_profiler(self, profiler_report: dict) -> dict:
        self._data["profiler"] = profiler_report
        return profiler_report

    # ── Persist ──

    def write_all(self) -> list[Path]:
        """Write all captured data to audit files. Returns list of paths."""
        paths = []
        for name, data in self._data.items():
            p = self.run_dir / f"{name}.json"
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            paths.append(p)
        # Write a manifest
        manifest = {"run_id": self.run_id, "timestamp": datetime.now().isoformat(),
                    "files": [p.name for p in paths]}
        (self.run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2))
        paths.append(self.run_dir / "manifest.json")
        return paths

    def collect_all(self, config: dict | None = None, dataset_paths: list[str] | None = None,
                    prompt_template: str | None = None) -> dict:
        """Capture all provenance at once. Returns the full audit dict."""
        self.capture_environment()
        self.capture_git()
        self.capture_hardware()
        self.capture_config(config)
        if dataset_paths:
            self.capture_dataset(dataset_paths)
        self.capture_model(config)
        if prompt_template:
            self.capture_prompt(prompt_template)
        return dict(self._data)

"""realeval/io/serialization.py — 配置加载与实验结果序列化。

配置加载：
  - 基础配置始终为 ``config/experiments.yaml``；
  - 通过 ``--config`` 传入的 YAML 作为覆盖层深度合并；
  - 支持 ``REALEVAL_SECTION__KEY`` 形式的环境变量覆盖。

结果序列化：
  - 单次实验 → ``outputs/results/expN_YYYYMMDD_HHMMSS.json``；
  - 全量归并 → ``outputs/results/all_experiments.json``（paper_data.py 候补来源）。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from realeval.io.paths import (
    ALL_EXPERIMENTS_FILE,
    PREDICTIONS,
    RESULTS,
    get_results_dir,
)

logger = logging.getLogger("realeval.io.serialization")

DEFAULT_CONFIG_PATH: Path = Path(__file__).resolve().parent.parent.parent / "config" / "experiments.yaml"


def _resolve_env_overrides(config: dict[str, Any], prefix: str = "REALEVAL_") -> dict[str, Any]:
    """将 ``REALEVAL_`` 前缀的环境变量应用为配置覆盖。

    值通过 ``yaml.safe_load`` 解析以实现正确的类型推断。如需保留字面字符串，
    请在环境变量值外加引号。
    """
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        keys = env_key[len(prefix):].lower().split("__")
        d: Any = config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        try:
            d[keys[-1]] = yaml.safe_load(env_val)
        except Exception:
            d[keys[-1]] = env_val
    return config


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """递归合并 ``over`` 到 ``base``；叶节点冲突时 ``over`` 优先。"""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置并应用环境变量覆盖。

    Args:
        path: 覆盖层 YAML 路径（如 ``config/h100.yaml``）。若未提供或等于
            ``config/experiments.yaml``，则只加载基础配置。

    Returns:
        合并后的配置字典。
    """
    base_path = DEFAULT_CONFIG_PATH
    with open(base_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    if path is not None:
        overlay_path = Path(path).resolve()
        if overlay_path != base_path.resolve():
            with open(overlay_path, encoding="utf-8") as f:
                overlay: dict[str, Any] = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, overlay)

    return _resolve_env_overrides(cfg)


def _atomic_write(path: Path, text: str) -> None:
    """Atomically write *text* to *path*.

    Writes to a temp file in the same directory then ``os.replace`` (atomic on
    POSIX and Windows) so a crash mid-write never leaves a truncated JSON behind
    (audit P2-13).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_results(exp_short: str, result: dict[str, Any]) -> Path:
    """将单次实验结果保存为带时间戳的 JSON 文件。

    同时在 ``outputs/predictions/`` 保留副本，用于 Dataset→Prediction 溯源。

    Returns:
        保存的 ``outputs/results/expN_YYYYMMDD_HHMMSS.json`` 路径。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = get_results_dir() / f"{exp_short}_{ts}.json"
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    _atomic_write(path, text)

    pred_dir = PREDICTIONS
    pred_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(pred_dir / f"{exp_short}_{ts}.json", text)

    logger.debug("结果已保存：%s", path)
    return path


def save_all_results(all_results: dict[str, dict[str, Any]]) -> Path:
    """将所有实验结果汇总写入 ``all_experiments.json``。

    ``paper_data.py`` 在加载单次实验 JSON 之后，会检查此文件作为候补来源。
    已有键不会被覆盖（保持最新单次结果优先原则）。

    Returns:
        ``outputs/results/all_experiments.json`` 路径。
    """
    get_results_dir()

    existing: dict[str, Any] = {}
    if ALL_EXPERIMENTS_FILE.exists():
        try:
            existing = json.loads(ALL_EXPERIMENTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    merged = {**existing, **all_results}
    _atomic_write(
        ALL_EXPERIMENTS_FILE,
        json.dumps(merged, ensure_ascii=False, indent=2, default=str),
    )
    logger.info("全量实验结果已写入：%s（共 %d 个实验）", ALL_EXPERIMENTS_FILE, len(merged))
    return ALL_EXPERIMENTS_FILE


def load_all_results() -> dict[str, dict[str, Any]]:
    """加载 ``all_experiments.json``（若不存在则返回空字典）。"""
    if not ALL_EXPERIMENTS_FILE.exists():
        return {}
    try:
        return json.loads(ALL_EXPERIMENTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("无法加载 all_experiments.json：%s", exc)
        return {}

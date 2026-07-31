"""realeval/io.py — 配置加载与实验结果保存

配置加载：基于 YAML 文件，支持 REALEVAL_DATA__KEY__SUBKEY 环境变量覆盖。
结果保存：
  - 单次实验 → outputs/results/{exp_short}_{timestamp}.json
  - 全量归并 → outputs/results/all_experiments.json（供 paper_data.py 消费）
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "outputs" / "results"

# all_experiments.json 是 paper_data.py 的候补加载路径
ALL_EXPERIMENTS_FILE = RESULTS / "all_experiments.json"


def _ensure_results_dir() -> Path:
    """按需创建 results 目录。"""
    RESULTS.mkdir(parents=True, exist_ok=True)
    return RESULTS


def _resolve_env_overrides(config: dict[str, Any], prefix: str = "REALEVAL_") -> dict[str, Any]:
    """将 REALEVAL_ 前缀的环境变量应用为配置覆盖（RealEval-v2 合约）。
    值通过 yaml.safe_load 解析以实现正确的类型推断。
    警告：yaml.safe_load 会把 "yes"/"no"/"on"/"off" 解析为布尔值，
    如需保留字面字符串，请在环境变量中加引号。
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
    """将 `over` 递归合并到 `base`（叶节点冲突时 over 优先）。"""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | None = None) -> dict[str, Any]:
    """加载 YAML 配置，并应用环境变量覆盖。

    基础配置始终来自 config/experiments.yaml。若 path 指向其他文件
    （如 config/h100.yaml），则深度合并到基础配置之上，覆盖层只需声明
    需要变更的字段（hardware/runtime/output），无需重复 models/data 等字段。
    """
    base_path = ROOT / "config" / "experiments.yaml"
    with open(base_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}
    if path is not None and Path(path).resolve() != base_path.resolve():
        with open(path, encoding="utf-8") as f:
            overlay: dict[str, Any] = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, overlay)
    return _resolve_env_overrides(cfg)


def save_results(exp_short: str, result: dict[str, Any]) -> Path:
    """将单次实验结果保存为带时间戳的 JSON 文件。

    保存路径：outputs/results/{exp_short}_{timestamp}.json
    同时在 outputs/predictions/ 保留副本（Dataset→Prediction 溯源链）。
    返回保存路径。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _ensure_results_dir() / f"{exp_short}_{ts}.json"
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    path.write_text(text, encoding="utf-8")

    pred_dir = ROOT / "outputs" / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / f"{exp_short}_{ts}.json").write_text(text, encoding="utf-8")

    logger.debug("结果已保存：%s", path)
    return path


def save_all_results(all_results: dict[str, dict[str, Any]]) -> Path:
    """将所有实验结果汇总写入 all_experiments.json。

    paper_data.py 在加载单次实验 JSON 之后，会检查此文件作为候补来源：
        outputs/results/all_experiments.json

    格式：{ "exp1": {...}, "exp2": {...}, ... }

    已有键不会被覆盖（保持最新单次结果优先原则）。
    返回文件路径。
    """
    _ensure_results_dir()

    # 加载已有内容（若存在），以防多次调用丢失之前的键
    existing: dict[str, Any] = {}
    if ALL_EXPERIMENTS_FILE.exists():
        try:
            existing = json.loads(ALL_EXPERIMENTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    merged = {**existing, **all_results}
    ALL_EXPERIMENTS_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("全量实验结果已写入：%s（共 %d 个实验）", ALL_EXPERIMENTS_FILE, len(merged))
    return ALL_EXPERIMENTS_FILE


def load_all_results() -> dict[str, dict[str, Any]]:
    """加载 all_experiments.json（若不存在则返回空字典）。"""
    if not ALL_EXPERIMENTS_FILE.exists():
        return {}
    try:
        return json.loads(ALL_EXPERIMENTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("无法加载 all_experiments.json：%s", exc)
        return {}

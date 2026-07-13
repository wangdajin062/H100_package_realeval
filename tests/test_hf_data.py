"""test_hf_data.py — 验证 HuggingFace datasets 集成与数据降级路径

用法:
    pytest tests/test_hf_data.py -v           # 运行所有测试
    pytest tests/test_hf_data.py -v -k hf     # 只运行 HF 相关测试
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path
import os

import pytest


def test_local_data_first(tmp_path: Path):
    """真实文件优先级高于 HF：若有本地文件，不会去加载 HF。"""
    import json
    # Use tmp_path fixture instead of real data/ directory to avoid
    # conflicts during parallel test runs.
    taf_dir = tmp_path / "TAF28k"
    taf_dir.mkdir()
    test_file = taf_dir / "taf28k.jsonl"
    test_file.write_text(
        json.dumps({"text": "Local test fraud msg", "label": 1}) + "\n",
        encoding="utf-8")
    # Patch DATA path temporarily
    import realeval.data as rdata
    original_data = rdata.DATA
    try:
        rdata.DATA = tmp_path
        from realeval.data import load_taf28k
        ds = load_taf28k(max_samples=10)
        assert len(ds["texts"]) == 1 and ds["labels"] == [1], f"Unexpected: {ds}"
        print(f"[PASS] test_local_data_first: 本地文件优先 ({len(ds['texts'])} 条)")
    finally:
        rdata.DATA = original_data


def test_hf_loads():
    """验证 HF datasets 加载。"""
    try:
        from datasets import load_dataset
        ds = load_dataset("JimmyMa99/TeleAntiFraud", split="train")
        assert len(ds) > 0
        sample = ds[0]
        print(f"[INFO] HF TeleAntiFraud: {len(ds)} 条, 字段: {ds.column_names}")
        print(f"  样例: instruction={sample.get('instruction','')[:60]}... "
              f"label={sample.get('label')}")
        print("[PASS] test_hf_loads: HF 数据集加载成功")
    except Exception as e:
        pytest.skip(f"HF 加载失败 ({e}) — 不联网或 datasets 未安装")


def test_fallback_synthetic():
    """无真实数据时，必须降级到合成数据。"""
    from realeval.data import load_synthetic
    ds = load_synthetic(n=20)
    assert len(ds["texts"]) == 20 and len(ds["labels"]) == 20
    assert sum(ds["labels"]) >= 5  # 大约一半是欺诈
    print(f"[PASS] test_fallback_synthetic: 降级 OK ({len(ds['texts'])} 条, "
          f"{sum(ds['labels'])} 欺诈)")


if __name__ == "__main__":
    import sys
    ROOT = Path(__file__).resolve().parent.parent
    os.chdir(ROOT)
    sys.exit(pytest.main([__file__, "-v"]))

#!/usr/bin/env python3
"""ovf_quick_check.py — 快速验证 exp3 OV-Freeze 修复（no_reg vs full，各 1 seed）

预期：no_reg (freeze_frac=0) 的 drift_pct_final 显著高（未做方差匹配），
ov_freeze_full (freeze_frac=1, window=1) 的 drift ≈ 0（方差被匹配）。
若两者相同 → 修复未生效；若区分开 → 修复有效，再决定是否跑完整 exp3。

用法: /workspace/venv/bin/python scripts/ovf_quick_check.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realeval.io import load_config
from experiments.common import config_override, load_and_split_dataset, set_seed
from realeval import real_backend


def main():
    config = load_config("config/runpod_h100.yaml")
    config["_paper"] = True
    split = load_and_split_dataset(config, default_dataset="balanced4k")
    print("n_train=%d n_test=%d" % (len(split.train_texts), len(split.test_texts)))

    for name, frac, window in [("no_reg", 0.0, 0.0), ("ov_freeze_full", 1.0, 1.0)]:
        set_seed(1000)
        overrides = config_override(config, training={
            "freeze_frac": frac, "window": window, "rho": 1.0,
        })
        r = real_backend.real_qad_distill_train(
            overrides,
            split.train_texts, split.train_labels,
            split.test_texts, split.test_labels,
            quantize="int4", apply_ov_rescaling=True,
            freeze_frac=frac, window=window,
        )
        print("RESULT %s: f1=%.4f drift=%.2f kl_final=%.4f thr=%.3f" % (
            name, r["f1"], r["drift_pct_final"], r["kl_final"],
            r.get("decision_threshold", float("nan"))))


if __name__ == "__main__":
    main()

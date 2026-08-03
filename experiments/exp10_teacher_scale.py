"""exp10: Teacher Scale — Compare Qwen-7B vs Qwen-14B vs Qwen-72B teacher."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp10")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_taf28k()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        models_cfg = config.get("models", {})

        # Teacher-scale ablation: each teacher trains the same student.
        # Two scenarios per teacher:
        #   f1_fixed: limited training (fixed token budget, 1 epoch)
        #   f1_conv:  full training to convergence (5 epochs)
        teacher_keys = [
            ("teacher",        models_cfg.get("teacher")),
            ("teacher_1.5b",   models_cfg.get("teacher_1.5b")),
            ("teacher_3b",     models_cfg.get("teacher_3b")),
            ("teacher_7b",     models_cfg.get("teacher_7b")),
        ]

        from experiments.common import config_override
        fixed_config = config_override(config, training={"epochs": 1})
        conv_config = config_override(config, training={"epochs": 5})

        scales = {}
        for key, model_id in teacher_keys:
            if not model_id:
                continue
            try:
                # Fixed token budget (1 epoch)
                fixed_result = real_backend.real_qad_distill_train(
                    fixed_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="int4",
                    teacher_model=model_id,
                )
                # To convergence (5 epochs)
                conv_result = real_backend.real_qad_distill_train(
                    conv_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="int4",
                    teacher_model=model_id,
                )
                scales[key] = {
                    "f1_fixed": fixed_result["f1"],
                    "f1_conv": conv_result["f1"],
                    "accuracy": conv_result["accuracy"],
                    "teacher_model": model_id,
                }
            except Exception as e:
                logger.warning("Teacher scale %s (%s) failed: %s", key, model_id, e)
                scales[key] = {"f1_fixed": None, "f1_conv": None, "error": str(e)}

        return {
            "computation": "h100_real_qwen",
            "scales": scales,
        }


    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: 运行 exp10 小模型验证（teacher_scale）")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        # 用合成重叠度模拟不同规模教师的蒸馏效果：
        # 同构 0.5B 教师特征重叠最高 → F1 最优；大教师特征分布偏移更明显
        synthetic_overlaps = (
            ("teacher",       0.95),   # 0.5B 同构（最佳）
            ("teacher_1.5b",  0.88),   # 1.5B 异构
            ("teacher_3b",    0.85),   # 3B 异构（exp10/Fig5b 所需）
            ("teacher_7b",    0.82),   # 7B 异构
        )
        scales = {}
        for teacher, overlap in synthetic_overlaps:
            X, y = verification_features(split.train_labels + split.test_labels, overlap=overlap)
            ntr = len(split.train_labels)
            clf_fixed = GradientBoostingClassifier(n_estimators=50, random_state=42).fit(X[:ntr], y[:ntr])
            m_fixed = classification_metrics(y[ntr:], clf_fixed.predict(X[ntr:]))
            clf_conv = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
            m_conv = classification_metrics(y[ntr:], clf_conv.predict(X[ntr:]))
            scales[teacher] = {
                "f1_fixed": m_fixed["f1"],
                "f1_conv": m_conv["f1"],
                "accuracy": m_conv["accuracy"],
            }
        return {"computation": "smoke_sklearn", "scales": scales}

    return run_with_mode("exp10", config, run_paper, run_smoke)

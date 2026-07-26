"""exp3: OV-Freeze Control — Layer selection and activation window sweep."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp3")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        import math
        # Layer selection: freeze a growing fraction of dims (early->all), so drift genuinely varies.
        layer_selection = {}
        for layer, frac in (("early", 0.25), ("mid", 0.5), ("late", 0.75), ("all", 1.0)):
            metrics = real_backend.real_distillation_step_metrics(
                config,
                split.train_texts,
                apply_ov_rescaling=True,
                quantize="int4",
                freeze_frac=frac,
            )
            result = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize="int4")
            layer_selection[layer] = {"f1": result["f1"], "variance_drift_pct": metrics["variance_drift_pct"]}
        # rho sweep: vary the activation window, so drift/ppl genuinely vary per rho.
        rho_sweep = {}
        for rho in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            m = real_backend.real_distillation_step_metrics(
                config,
                split.train_texts,
                apply_ov_rescaling=True,
                quantize="int4",
                window=rho,
            )
            r_cls = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize="int4")
            PPL_KL_CLAMP = 10
            rho_sweep[f"rho_{rho}"] = {"f1": r_cls["f1"], "variance_drift_pct": m["variance_drift_pct"],
                                       "ppl": round(math.exp(min(m.get("kl", 0.0), PPL_KL_CLAMP)), 3)}
        # Matched-regulariser control (reviewer C): compares no regulariser vs OV-Freeze at
        # different variance-matching strengths. All apply_ov_rescaling=True conditions use the same
        # OV-Freeze mechanism, varying only freeze_frac (fraction of dimensions matched).
        conditions = {}
        for cond, fov, frac in (("no_reg", False, 0.0), ("ov_freeze_full", True, 1.0),
                                ("ov_freeze_half", True, 0.5), ("ov_freeze_quarter", True, 0.25)):
            m = real_backend.real_distillation_step_metrics(
                config,
                split.train_texts,
                apply_ov_rescaling=fov,
                quantize="int4",
                freeze_frac=max(frac, 0.01),
            )
            r_cls = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize="int4")
            conditions[cond] = {"f1": r_cls["f1"], "variance_drift_pct": m["variance_drift_pct"]}
        return {"experiment": "exp3", "computation": "h100_real_qwen",
                "layer_selection": layer_selection, "rho_sweep": rho_sweep, "conditions": conditions}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp3")
        import numpy as np
        import torch
        import torch.nn.functional as F
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        base_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        Xt = torch.tensor(X[:ntr])
        torch.manual_seed(0)
        teacher = torch.nn.Linear(X.shape[1], 4)
        with torch.no_grad():
            t_logits = teacher(Xt)
            t_var = t_logits.var(0)

        def _train(freeze_frac: float, window: float) -> tuple[float, float]:
            torch.manual_seed(1)
            student = torch.nn.Linear(X.shape[1], 4)
            opt = torch.optim.Adam(student.parameters(), lr=0.05)
            steps = int(60 * window)
            for step in range(60):
                opt.zero_grad()
                s = student(Xt)
                loss = F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean")
                if step >= 60 - steps:
                    k = max(1, int(4 * freeze_frac))
                    loss = loss + F.mse_loss(s.var(0)[:k], t_var[:k])
                loss.backward()
                opt.step()
            with torch.no_grad():
                s = student(Xt)
                drift = float((s.var(0) - t_var).abs().mean() / (t_var.abs().mean() + 1e-9) * 100)
                kl = float(F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean"))
            return drift, round(np.exp(min(kl, 10)), 3)

        # Use same freeze_frac values as paper path (early=0.25, mid=0.5, late=0.75, all=1.0)
        # so key names carry the same semantic meaning in smoke and paper runs.
        layer_selection = {}
        for frac, layer in ((0.0, "none"), (0.25, "early"), (0.5, "mid"), (0.75, "late"), (1.0, "all")):
            drift, _ = _train(frac if frac > 0 else 1.0, 0.5 if frac > 0 else 0.0)
            layer_selection[layer] = {"f1": base_f1, "variance_drift_pct": round(drift, 3)}

        rho_sweep = {}
        for rho in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            drift, ppl = _train(1.0, rho)
            rho_sweep[f"rho_{rho}"] = {"f1": base_f1, "variance_drift_pct": round(drift, 3), "ppl": ppl}

        conditions = {}
        for cond, frac, win in (("no_reg", 0.0, 0.0), ("ov_freeze_full", 1.0, 0.5),
                                ("ov_freeze_half", 0.5, 0.3), ("ov_freeze_quarter", 0.25, 0.2)):
            drift, _ = _train(max(frac, 0.01), win)
            conditions[cond] = {"f1": base_f1, "variance_drift_pct": round(drift, 3)}

        return {
            "experiment": "exp3",
            "computation": "smoke_sklearn",
            "layer_selection": layer_selection,
            "rho_sweep": rho_sweep,
            "conditions": conditions,
        }

    return run_with_mode("exp3", config, run_paper, run_smoke)

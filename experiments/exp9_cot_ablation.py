"""exp9: CoT Ablation — Compare chain-of-thought cloud review vs direct fusion.

论文 CoT 消融（tab:cot-ablation-en）对比「完整 pipeline（异步 CoT 云端评审）」与
「direct risk-score fusion（跳过 CoT）」，在 NVFP4 QAD + OV-Freeze 上，覆盖两个
数据集：TAF-28k（多模态融合）与 AdvFraud-3k（纯文本对抗）。审计 P1-8 修正旧实现的
四点缺陷——(1) 仅纯文本 → TAF-28k 改为 sigmoid-linear 决策级融合（文本 CoT 开关 +
128-d F_v 声学分支）；(2) 单数据集 → 补 AdvFraud-3k 纯文本臂；(3) 单 seed → 推理
确定性下 n_seeds=1 诚实标注（±std 由 claim_engine 训练侧多 seed 实现，同 exp11/14）；
(4) QAD 产物缺失静默退回 base → 打 model_source="base_qwen" 标记。
"""
from __future__ import annotations
import logging
from experiments.framework import run_with_mode

logger = logging.getLogger("exp9")


def run(config: dict) -> dict:
    from realeval import data
    import numpy as np

    max_samples = config.get("data", {}).get("max_samples", 2000)

    def _try_load_taf28k_fv() -> np.ndarray | None:
        """加载 128-d F_v NPZ（论文音频分支口径，audit P1-12）；缺失返回 None。"""
        from realeval.data import _data_root
        fv_path = _data_root() / "TAF28k" / "taf28k_fv.npz"
        if not fv_path.exists():
            return None
        try:
            z = np.load(fv_path, allow_pickle=True)
            emb = np.asarray(z["embeddings"])
            return emb[:max_samples] if max_samples else emb
        except (KeyError, OSError) as e:
            logger.info("TAF28k F_v NPZ unavailable: %s", e)
            return None

    # ── TAF-28k 多模态（text + 128-d F_v 声学）──────────────────────────────
    taf_ds = data.load_taf28k(max_samples=max_samples, source="multimodal")
    taf_texts, taf_labels = taf_ds["texts"], taf_ds["labels"]
    taf_audio = taf_ds.get("embeddings")
    _fv = _try_load_taf28k_fv()
    if _fv is not None:
        taf_audio = _fv
    taf_synthetic = False
    if not taf_texts or taf_audio is None:
        taf_ds = data.load_synthetic(n=200)
        taf_texts, taf_labels = taf_ds["texts"], taf_ds["labels"]
        taf_audio = taf_ds["embeddings"]
        taf_synthetic = True
    _n = min(len(taf_texts), len(taf_audio))
    taf_texts, taf_labels, taf_audio = taf_texts[:_n], taf_labels[:_n], np.asarray(taf_audio[:_n])

    # ── AdvFraud-3k 纯文本（对抗变体，无声学分支）───────────────────────────
    adv_ds = data.load_advfraud3k(max_samples=max_samples)
    adv_texts, adv_labels = adv_ds["texts"], adv_ds["labels"]
    adv_synthetic = False
    if not adv_texts:
        adv_ds = data.load_synthetic(n=200)
        adv_texts, adv_labels = adv_ds["texts"], adv_ds["labels"]
        adv_synthetic = True

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from experiments.common import shared_test_indices, resolve_qad_path

        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None
        model_source = "exp1_qad" if finetuned_path else "base_qwen"

        # 泄漏安全 test 分区（TAF-28k 与 exp1 共享 manifest；AdvFraud 独立 key）。
        taf_test_idx = shared_test_indices("taf28k", taf_texts, taf_labels)
        taf_test_texts = [taf_texts[i] for i in taf_test_idx]
        taf_test_labels = [taf_labels[i] for i in taf_test_idx]
        taf_test_audio = taf_audio[taf_test_idx]
        _tset = set(taf_test_idx)
        taf_train_idx = [i for i in range(_n) if i not in _tset]
        taf_train_texts = [taf_texts[i] for i in taf_train_idx]
        taf_train_labels = [taf_labels[i] for i in taf_train_idx]
        taf_train_audio = taf_audio[taf_train_idx]

        adv_test_idx = shared_test_indices("advfraud", adv_texts, adv_labels)
        adv_test_texts = [adv_texts[i] for i in adv_test_idx]
        adv_test_labels = [adv_labels[i] for i in adv_test_idx]

        def _text_branch(texts, labels, use_cot):
            """QAD 学生文本分支（with/without CoT）。返回 probs（fine-tuned 路径）
            或 scores（base 路径），兜底 preds，供 fusion 的 text soft score 使用。"""
            return real_backend.real_llm_classify(
                config, texts, labels, quantize="nvfp4",
                finetuned_path=finetuned_path, use_cot=use_cot,
                return_preds=True, return_probs=True, return_scores=True)

        def _soft_scores(txt):
            return txt.get("probs") or txt.get("scores") or txt.get("preds")

        arms = {}
        for arm, use_cot in (("with_cot", True), ("without_cot", False)):
            # ── TAF-28k 融合臂：文本 CoT 开关 + 128-d F_v → sigmoid-linear 融合 ──
            test_txt = _text_branch(taf_test_texts, taf_test_labels, use_cot)
            train_txt = _text_branch(taf_train_texts, taf_train_labels, use_cot)
            fit_data = {"texts": taf_train_texts, "labels": taf_train_labels,
                        "audio": taf_train_audio,
                        "text_scores": _soft_scores(train_txt)}
            fusion = real_backend.real_fusion_classify(
                config, taf_test_texts, taf_test_labels, taf_test_audio,
                quantize="nvfp4", fusion_strategy="sigmoid_linear",
                fit_data=fit_data, text_scores=_soft_scores(test_txt))
            # ── AdvFraud-3k 纯文本臂 ──
            adv = _text_branch(adv_test_texts, adv_test_labels, use_cot)
            arms[arm] = {
                "f1": fusion.get("f1"),
                "fpr": fusion.get("fpr"),
                "advfraud_f1": adv.get("f1"),
                "fusion_degraded": fusion.get("fusion_degraded", False),
                "n_seeds": 1,
                "note": "TAF-28k = sigmoid-linear decision fusion (text CoT switch + 128-d F_v acoustic); AdvFraud-3k = text-only head. n_seeds=1 (deterministic inference; multi-seed std via claim_engine train-side).",
            }
        return {"computation": "h100_real_qwen", **arms,
                "model_source": model_source,
                "is_synthetic": taf_synthetic or adv_synthetic}

    return run_with_mode("exp9", config, run_paper)

"""exp13: Fusion Strategy — Compare the paper's decision-level fusion heads (softmax-linear,
sigmoid-linear (ours), Transformer) over text + acoustic risk scores (Eq. fusion)."""
from __future__ import annotations
import logging
from experiments.framework import run_with_mode

logger = logging.getLogger("exp13")


def run(config: dict) -> dict:
    from realeval import data
    import numpy as np

    max_samples = config.get("data", {}).get("max_samples", 2000)

    def _try_load_taf28k_fv() -> np.ndarray | None:
        """加载 128-d F_v NPZ（build_chifraud_fv.py 输出）；缺失则返回 None。"""
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

    # Load multimodal data: text (JSONL) + acoustic F_v embeddings (NPZ) aligned by index.
    # 论文音频分支是 128-d F_v（64-d FBANK + 64-d Whisper-proj），而非 taf28k.npz 的
    # 384-d Whisper（audit P1-12）。F_v NPZ 优先，退回 legacy NPZ，再退回 synthetic。
    ds = data.load_taf28k(max_samples=max_samples, source="multimodal")
    texts, labels = ds["texts"], ds["labels"]
    audio_emb = ds.get("embeddings")
    _fv = _try_load_taf28k_fv()
    if _fv is not None:
        audio_emb = _fv
    is_synthetic = False
    if not texts or audio_emb is None:
        # Fall back to synthetic with both text and acoustic-style embeddings
        ds = data.load_synthetic(n=200)
        texts, labels = ds["texts"], ds["labels"]
        audio_emb = ds["embeddings"]
        is_synthetic = True
    n = min(len(texts), len(audio_emb))
    texts, labels, audio_emb = texts[:n], labels[:n], np.asarray(audio_emb[:n])
    # Leakage-safe test partition shared with exp1/exp5/exp14 (P1-M1): one index set
    # applied to text, labels AND the aligned acoustic embeddings, instead of a
    # positional tail slice that overlaps exp1's training data.
    from experiments.common import shared_test_indices
    test_idx = shared_test_indices("taf28k", texts, labels)
    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    test_audio = audio_emb[test_idx]
    # Training complement for the fusion-head fit (paper protocol, audit P2-4): the
    # acoustic calibrator and fusion heads fit on the non-test remainder, not on a
    # self-split of the evaluation set.
    _test_set = set(test_idx)
    train_idx = [i for i in range(n) if i not in _test_set]
    train_texts = [texts[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    train_audio = audio_emb[train_idx]

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import time
        # Real decision-level fusion on H100: Qwen risk vote (text) + calibrated acoustic score,
        # combined by the paper's three fusion heads. `params` is each head's TOTAL parameter
        # count (for the linear heads this equals the trained scalars; the transformer head
        # includes frozen random attention features — its trained-only count is reported in
        # head.n_params_trained).
        strategies = {}
        # Hoist the expensive text-branch inference out of the per-strategy loop: the
        # same texts are scored once and shared by all three fusion heads (was 3x).
        # 文本分支必须用 QAD 训练产物（audit P1-12）：原 zero-shot 基座无蒸馏，语义错位。
        from experiments.common import resolve_qad_path
        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None
        test_txt = real_backend.real_llm_classify(
            config, test_texts, test_labels, quantize="nvfp4",
            finetuned_path=finetuned_path,
            return_preds=True, return_scores=True)
        train_txt = real_backend.real_llm_classify(
            config, train_texts, train_labels, quantize="nvfp4",
            finetuned_path=finetuned_path,
            return_preds=True, return_scores=True)
        fit_data = {"texts": train_texts, "labels": train_labels, "audio": train_audio,
                    "text_scores": train_txt.get("scores") or train_txt["preds"]}
        eval_scores = test_txt.get("scores") or test_txt["preds"]
        for sname in ("softmax_linear", "sigmoid_linear", "transformer"):
            t0 = time.perf_counter()
            result = real_backend.real_fusion_classify(
                config, test_texts, test_labels, test_audio,
                quantize="nvfp4", fusion_strategy=sname,
                fit_data=fit_data, text_scores=eval_scores)
            # 端到端计时（含 fusion head fit：L-BFGS + 5-fold CV / grid search /
            # transformer head 在 train 上拟合），非纯推理——fusion head 拟合与推理在
            # real_fusion_classify 内耦合，无法分离计时（audit P1-12 诚实标注）。
            lat_ms = (time.perf_counter() - t0) / max(1, len(test_texts)) * 1000
            strategies[sname] = {
                "f1": result["f1"], "accuracy": result["accuracy"],
                "params": result.get("fusion_params", "NOT_MEASURED"),
                "head": result.get("fusion_head"),
                "degraded": result.get("fusion_degraded", False),
                "latency_ms": round(lat_ms, 4),
                "latency_note": "end-to-end (includes fusion-head fit, not inference-only)",
            }
        return {"computation": "h100_real_qwen", "strategies": strategies,
                "headline_strategy": "sigmoid_linear",
                "is_synthetic": is_synthetic}

    return run_with_mode("exp13", config, run_paper)

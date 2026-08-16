"""realeval/qdq.py — NBE QDQ fake-quantisation (paper Eq.(eq:nbe)).

Numerical Behaviour Emulation (NBE): the paper's QAD student is quantised to
NVFP4, but H100 GPUs have no native NVFP4 support. NBE reproduces NVFP4 numerics
by embedding quantise-dequantise (QDQ) fake-quant operators in the forward graph:

    Ŵ = clamp(round(W / s), q_min, q_max) · s,   s = s_block · s_tensor    (Eq.(eq:nbe))

with a straight-through estimator (STE) so the student trains quantisation-aware
(QAT). This is distinct from the bitsandbytes int4/nf4 path (post-training
quantisation, PTQ): NBE keeps the weights in bf16/fp32 and quantises them on the
forward pass, so the gradient flows back through the quantiser into the weight.

Block size follows the paper's Table 2 spec for the NVFP4 server track:
``block size = 16`` (per-16-element scale), with an FP8 E4M3 scale factor. The
scale is computed in float32 here — a numerically-equivalent approximation of the
FP8 E4M3 storage format (deviation < 0.3% per the paper's NBE verification note).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

# 4-bit grid (16 levels). The paper's Eq.(eq:nbe) formulates NBE as a symmetric
# round/clamp: Ŵ = clamp(round(W/s), q_min, q_max)·s. q_min/q_max are NOT given
# explicitly in the paper; -8..7 is the standard 4-bit symmetric integer grid.
# NOTE: hardware NVFP4 is FP4 (E2M1) with a non-uniform grid (0, ±0.5, ±1, ±1.5,
# ±2, ±3, ±4, ±6); the round/clamp of Eq.(eq:nbe) implies a uniform int4 grid
# instead. The exact q_min/q_max (and int4-vs-FP4 grid) is an open author-facing
# clarification — see the σ/quantisation audit note.
QMIN, QMAX = -8, 7
DEFAULT_BLOCK_SIZE = 16  # paper Table 2: NVFP4 block size = 16


def _per_block_scale(w: torch.Tensor, block_size: int) -> torch.Tensor:
    """Composite per-block scale s = s_block · s_tensor, broadcast back to w.shape.

    s_tensor = max(|W|) / QMAX                 (coarse tensor-level scale)
    s_block  = max(|W_b|) / (s_tensor · QMAX)  (per-block refinement)
    so the effective scale per block is s_block · s_tensor = max(|W_b|) / QMAX —
    a standard per-block symmetric max-abs scale. The two factors are kept
    separate to mirror Eq.(eq:nbe)'s s = s_block · s_tensor structure.
    """
    dev = w.device
    flat = w.detach().to(torch.float32).reshape(-1)
    n = flat.numel()
    if n == 0:
        return torch.ones_like(w)
    pad = (-n) % block_size
    if pad:
        flat = torch.cat([flat, torch.zeros(pad, device=dev, dtype=torch.float32)])
    blocks = flat.reshape(-1, block_size)
    amax = flat.abs().max()
    s_tensor = (amax / QMAX).clamp_min(1e-8)
    s_block = (blocks.abs().amax(dim=1) / (s_tensor * QMAX)).clamp_min(1e-8)
    scale = (s_block * s_tensor).reshape(-1, 1).repeat(1, block_size).reshape(-1)[:n]
    return scale.reshape(w.shape)


def fake_quant(w: torch.Tensor, block_size: int = DEFAULT_BLOCK_SIZE) -> torch.Tensor:
    """STE fake-quant (Eq.(eq:nbe)): forward returns Ŵ, gradient passes through unchanged."""
    scale = _per_block_scale(w, block_size)
    w32 = w.to(torch.float32)
    q = torch.clamp(torch.round(w32 / scale), QMIN, QMAX)
    w_hat = (q * scale).to(w.dtype)
    return w + (w_hat - w).detach()


class QDQLinear(nn.Module):
    """nn.Linear wrapper that fake-quantises its weight in the forward pass.

    State-dict transparent: ``_save_to_state_dict`` / ``_load_from_state_dict``
    delegate to the wrapped Linear, so ``save_pretrained`` / ``load_state_dict``
    see ``weight`` / ``bias`` keys (not ``linear.weight`` / ``linear.bias``) — a
    QDQ-wrapped model round-trips through the same checkpoint layout as the
    unwrapped model. A QAT-trained NBE checkpoint therefore reloads as a plain
    Qwen checkpoint and is re-wrapped by ``apply_qdq`` at inference time.
    """

    def __init__(self, linear: nn.Linear, block_size: int = DEFAULT_BLOCK_SIZE):
        super().__init__()
        self.linear = linear
        self.block_size = block_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = fake_quant(self.linear.weight, self.block_size)
        return F.linear(x, w, self.linear.bias)

    def _save_to_state_dict(self, destination, prefix, keep_vars):
        self.linear._save_to_state_dict(destination, prefix, keep_vars)

    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                              missing_keys, unexpected_keys, error_msgs):
        self.linear._load_from_state_dict(
            state_dict, prefix, local_metadata, strict,
            missing_keys, unexpected_keys, error_msgs)


def apply_qdq(module: nn.Module, block_size: int = DEFAULT_BLOCK_SIZE) -> nn.Module:
    """Replace every nn.Linear in-place with a QDQLinear wrapper (mutates module).

    Idempotent: already-wrapped QDQLinear leaves are skipped.
    """
    for name, child in list(module.named_children()):
        if isinstance(child, QDQLinear):
            continue
        if isinstance(child, nn.Linear):
            setattr(module, name, QDQLinear(child, block_size))
        else:
            apply_qdq(child, block_size)
    return module

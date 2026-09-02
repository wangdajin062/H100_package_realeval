"""realeval/acoustic_embedding.py — the real 128-d acoustic embedding F_v constructor.

The paper's acoustic embedding (Eq.~eq:f-v) is the concatenation of two 64-d
components:

    F_v = [ f_mfcc(64 time-averaged FBANK) ; psi(W_proj . h_bar_w)(64 Whisper-proj) ]

where ``h_bar_w`` is the globally-pooled Whisper-tiny encoder hidden state and
``W_proj`` is a 64 x 384 projection followed by a non-linearity ``psi``.

This module provides the from-scratch constructor that exp7 needs to run the
GLO / speaker-ID / ASV-EER privacy attacks against the *actual deployed* F_v
(R2 A-road), replacing the pre-computed proxy NPZ embeddings produced by
``data/scripts/build_audio_npz.py`` (which tiles a 20-d MFCC to 128-d and is
*not* the paper's F_v).

Every function that needs an optional dependency (librosa, whisper) degrades to
an explicit ``unavailable`` state rather than fabricating an embedding or a
privacy number — matching the honesty discipline used across ``realeval/``.
"""
from __future__ import annotations

import logging
from typing import Callable

import numpy as np

logger = logging.getLogger("acoustic_embedding")

# F_v layout constants (must match config ``audio.mfcc_dim`` / ``audio.whisper_proj_dim``).
FBANK_DIM = 64
WHISPER_PROJ_DIM = 64
F_V_DIM = FBANK_DIM + WHISPER_PROJ_DIM  # 128
WHISPER_ENCODER_DIM = 384               # Whisper-tiny encoder hidden size


def time_averaged_fbank(
    wav: np.ndarray,
    sr: int = 16000,
    n_mels: int = FBANK_DIM,
    *,
    n_fft: int = 400,
    hop_length: int = 160,
) -> np.ndarray | None:
    """64-d time-averaged log-mel FBANK (the ``f_mfcc`` half of F_v).

    Returns a float32 vector of length ``n_mels``, or ``None`` if librosa is not
    installed (caller records the honest unavailable state).
    """
    try:
        import librosa
    except ImportError:
        return None
    y = np.asarray(wav, dtype=np.float32)
    if y.size == 0:
        return None
    mel = librosa.feature.melspectrogram(
        y=y, sr=sr, n_mels=n_mels, n_fft=n_fft, hop_length=hop_length)
    logmel = librosa.power_to_db(mel, ref=np.max)
    return logmel.mean(axis=1).astype(np.float32)


def whisper_pooled_hidden(wav: np.ndarray, sr: int = 16000, model=None) -> np.ndarray | None:
    """Globally-pooled Whisper-tiny *encoder* hidden state ``h_bar_w`` (384-d).

    ``model`` may be a pre-loaded ``whisper.load_model("tiny")`` instance (or a
    ``.encoder``-only wrapper); when ``None`` it is loaded lazily. Returns
    ``None`` when whisper is unavailable (honest unavailable state).
    """
    try:
        import torch
        import whisper
    except ImportError:
        return None
    try:
        m = model or whisper.load_model("tiny")
        y = np.asarray(wav, dtype=np.float32)
        # Whisper expects float32 mono at 16k; pad to a minimal length.
        if y.size < 1600:
            y = np.pad(y, (0, 1600 - y.size))
        mel = whisper.log_mel_spectrogram(y)
        with torch.no_grad():
            enc = m.encoder(mel.unsqueeze(0))
        # Global mean-pool over the time axis (dim 1) -> (1, encoder_dim).
        pooled = enc.mean(dim=1).squeeze(0).cpu().numpy().astype(np.float32)
        return pooled
    except Exception as e:  # pragma: no cover - optional stack
        logger.warning("whisper_pooled_hidden failed: %s", e)
        return None


def _project_whisper(h_w: np.ndarray, w_proj: np.ndarray, projector=None) -> np.ndarray | None:
    """Apply ``psi(W_proj . h_bar_w)`` to the pooled hidden state.

    ``projector`` defaults to a signed-sqrt non-linearity; pass any callable
    ``(np.ndarray) -> np.ndarray`` to reproduce the paper's ``psi``.
    """
    if h_w is None or w_proj is None:
        return None
    try:
        z = w_proj @ np.asarray(h_w, dtype=np.float32)          # (64, 384) @ (384,) -> (64,)
        if projector is None:
            z = np.sign(z) * np.sqrt(np.abs(z) + 1e-8)          # psi: signed-sqrt
        else:
            z = np.asarray(projector(z), dtype=np.float32)
        return z.astype(np.float32)
    except Exception as e:  # pragma: no cover - shape/optional stack
        logger.warning("_project_whisper failed: %s", e)
        return None


def build_fv_from_wav(
    wav: np.ndarray,
    sr: int = 16000,
    *,
    w_proj: np.ndarray | None = None,
    projector=None,
    whisper_model=None,
    n_mels: int = FBANK_DIM,
    proj_dim: int = WHISPER_PROJ_DIM,
) -> np.ndarray | None:
    """Construct the real 128-d F_v for one waveform.

    Returns ``None`` (honest unavailable) when any required component is missing
    (librosa absent, whisper absent, or no ``w_proj`` matrix). The caller must
    record that state rather than fall back to a proxy number.
    """
    fbank = time_averaged_fbank(wav, sr, n_mels=n_mels)
    if fbank is None:
        return None
    h_w = whisper_pooled_hidden(wav, sr, model=whisper_model)
    wproj = _project_whisper(h_w, w_proj, projector)
    if wproj is None or wproj.shape[0] != proj_dim:
        return None
    return np.concatenate([fbank[:proj_dim], wproj]).astype(np.float32)


def load_w_proj(path: str | None = None, *, shape: tuple[int, int] = (64, 384)) -> np.ndarray | None:
    """Load the trained ``W_proj`` projection matrix (64 x 384) from a .npy file.

    ``path`` may be absolute, or relative to ``<data_root>/acoustic/w_proj.npy``.
    Returns ``None`` when the matrix is absent — the F_v constructor then reports
    unavailable (never fabricates a random projection as if it were the trained one).
    """
    from pathlib import Path
    import numpy as np
    p = Path(path) if path else None
    if p is None or not p.is_absolute():
        from realeval.data import _data_root
        p = (p or Path("acoustic") / "w_proj.npy")
        p = Path(_data_root()) / p if not p.is_absolute() else p
    if not p.exists():
        return None
    w = np.load(p).astype(np.float32)
    if w.shape != shape:
        logger.warning("w_proj shape %s != expected %s", w.shape, shape)
    return w


def fbank_identity_proj_fn(fv: np.ndarray) -> Callable:
    """Build the GLO ``proj_fn`` for the *real* F_v.

    The FBANK half ``F_v[:, :64]`` is stored in the clear (an identity map — the
    attacker recovers it exactly), while the Whisper-proj half ``F_v[:, 64:]`` is held
    fixed and is *not* a function of the FBANK input being optimised. The returned
    callable is vectorised: ``torch.Tensor (n, 64) -> (n, 128)``, appending the first
    ``x.shape[0]`` rows of the Whisper-proj half. The GLO loop calls it once per sample
    with a single-row ``(1, 64)`` input, so those calls pin to row 0's Whisper constant;
    this is immaterial because that term is constant w.r.t. the optimised FBANK input
    and ``glo_reconstruction_attack`` reports the correlation on the FBANK half only.

    This is the honest reconstruction model: privacy under the GLO attack rests on
    time-averaging destroying the temporal dynamics (measured by WER/PESQ/STOI/MOS
    on the reconstructed waveform), *not* on the FBANK half being non-invertible —
    the reconstruction correlation here converges to ~1.0 by construction.
    """
    import torch
    fv = np.asarray(fv, dtype=np.float32)
    if fv.ndim != 2 or fv.shape[1] < F_V_DIM:
        raise ValueError(f"real F_v must be (n, {F_V_DIM}), got {fv.shape}")
    whisper_half = torch.tensor(fv[:, FBANK_DIM:], dtype=torch.float32)

    def proj_fn(x):
        if x.dim() == 1:
            x = x.unsqueeze(0)
        # Single-row calls (the per-sample GLO step) pin to row 0's Whisper constant —
        # immaterial: it is constant w.r.t. x and the reported corr is FBANK-half only.
        w = whisper_half[:x.shape[0]]
        return torch.cat([x, w], dim=1)

    return proj_fn


def griffin_lim_fbank(
    fbank_vector: np.ndarray,
    sr: int = 16000,
    *,
    n_mels: int = FBANK_DIM,
    n_frames: int = 300,
    n_iter: int = 32,
    n_fft: int = 400,
    hop_length: int = 160,
) -> np.ndarray | None:
    """Reconstruct a waveform from a *time-averaged* FBANK vector.

    The averaged vector is tiled across ``n_frames`` (the paper's ~300 frames per
    3-s window) and inverted with Griffin-Lim. Because temporal dynamics were
    collapsed by averaging, the reconstruction is a near-constant pitch contour —
    this is exactly what drives the paper's WER >= 0.95 privacy claim. Returns
    ``None`` if librosa is absent.
    """
    try:
        import librosa
    except ImportError:
        return None
    v = np.asarray(fbank_vector, dtype=np.float32)
    if v.ndim == 1:
        v = np.tile(v[:, None], (1, n_frames))
    else:
        v = v[:, :n_frames]
    mel = librosa.db_to_power(v, ref=1.0)
    inv = librosa.feature.inverse.mel_to_stft(mel, sr=sr, n_fft=n_fft)
    y = librosa.griffinlim(inv, n_iter=n_iter, hop_length=hop_length,
                           win_length=n_fft, n_fft=n_fft)
    return y.astype(np.float32)

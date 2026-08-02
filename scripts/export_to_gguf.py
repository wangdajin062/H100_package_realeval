"""Export a trained QAD student (base + LoRA adapter) to Q4_K_M GGUF for mobile/edge deployment.

Target mobile runtime: Snapdragon 8 Gen 3 / llama.cpp compatible Q4_K_M GGUF (~240 MB).

FIX (2026-08-02): the previous version fed `outputs/models/exp1_qad` directly to
`llama_cpp.convert`. That directory only holds the PEFT LoRA adapter (adapter_model.safetensors,
no config.json / no base weights), so conversion failed and the exported model lost the domain
tuning entirely. This version:

  1. resolves the base model (defaults to the adapter's recorded base),
  2. loads base + adapter and runs ``PeftModel.merge_and_unload()``,
  3. saves the merged full transformers model to a scratch dir,
  4. converts that complete directory to GGUF with llama-cpp-python.

Note: the mobile GGUF path is *generative* (llama.cpp prompts the model for a 0/1 verdict,
see realeval/gguf_backend.py), so the `head.pt` classification head is intentionally NOT
exported — GGUF cannot carry a custom head and the edge scorer never uses it.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[export_gguf] %(levelname)s %(message)s")
logger = logging.getLogger("export_gguf")

DEFAULT_QUANT = "q4_k_m"
SUPPORTED_QUANTS = {"q4_k_m", "q4_0", "q4_1"}


# ── model / path helpers ──────────────────────────────────────────────────────

def _resolve_base_model(source_dir: Path, base_model: str | None) -> str:
    """Pick the base model: CLI override > adapter_config.json > package default."""
    if base_model:
        return base_model
    cfg = source_dir / "adapter_config.json"
    if cfg.is_file():
        try:
            recorded = json.loads(cfg.read_text(encoding="utf-8")).get("base_model_name_or_path")
        except Exception:
            recorded = None
        if recorded:
            logger.info("Using base model recorded in adapter_config.json: %s", recorded)
            return str(recorded)
    return "Qwen/Qwen2.5-0.5B-Instruct"


def _resolve_local_path(model_ref: str) -> str:
    """Map a HF id to a local checkpoint when it exists (RunPod /workspace/models), else keep id."""
    try:
        from realeval.paths import resolve_model
        resolved = resolve_model(model_ref)
        if resolved != model_ref:
            logger.info("Base model resolved to local path: %s", resolved)
        return resolved
    except ImportError:
        return model_ref


# ── step 1: load base + merge adapter ─────────────────────────────────────────

def merge_and_save(source_dir: Path, base_model: str, out_dir: Path) -> None:
    """Load base + LoRA, merge, save a complete transformers directory to out_dir."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_ref = _resolve_local_path(base_model)

    logger.info("Loading base model %s (bf16)...", base_ref)
    model = AutoModelForCausalLM.from_pretrained(base_ref, torch_dtype=torch.bfloat16)
    tokenizer = AutoTokenizer.from_pretrained(base_ref)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info("Loading LoRA adapter from %s and merging...", source_dir)
    model = PeftModel.from_pretrained(model, str(source_dir))
    model = model.merge_and_unload()
    model.eval()

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Saving merged model to %s ...", out_dir)
    model.save_pretrained(out_dir, safe_serialization=True)
    tokenizer.save_pretrained(out_dir)

    # Surface which source produced this file.
    (out_dir / "EXPORT_SOURCE.txt").write_text(
        f"merged from base={base_model}\nadapter={source_dir}\n", encoding="utf-8")


# ── step 2: GGUF conversion (llama-cpp-python → llama.cpp convert_hf_to_gguf.py) ──

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _convert_gguf(model_dir: Path, output_path: Path, quant_type: str) -> None:
    # Attempt 1: llama-cpp-python Python API (absent in some versions).
    try:
        import llama_cpp
        if hasattr(llama_cpp, "convert"):
            try:
                llama_cpp.convert(model_path=str(model_dir), outfile=str(output_path),
                                  quantize=quant_type, format="gguf")
                if output_path.is_file():
                    return
            except Exception as exc:
                logger.warning("llama_cpp.convert failed: %s; trying CLI", exc)
    except ImportError:
        pass

    # Attempt 2: `python -m llama_cpp.convert` CLI.
    try:
        _run([sys.executable, "-m", "llama_cpp.convert",
              "--model", str(model_dir), "--outfile", str(output_path),
              "--format", "gguf", "--quantize", quant_type])
        if output_path.is_file():
            return
    except Exception as exc:
        logger.warning("python -m llama_cpp.convert failed: %s", exc)

    # Attempt 3: llama.cpp official convert_hf_to_gguf.py.
    candidates = [
        Path("/workspace/llama.cpp/convert_hf_to_gguf.py"),
        Path(__file__).resolve().parent.parent / "llama.cpp" / "convert_hf_to_gguf.py",
    ]
    convert_script = next((c for c in candidates if c.is_file()), None)
    if convert_script is None:
        raise RuntimeError(
            "No GGUF converter available. Clone llama.cpp to /workspace/llama.cpp "
            "(`git clone --depth 1 https://github.com/ggerganov/llama.cpp`) or install "
            "a llama-cpp-python build that ships `llama_cpp.convert`.")
    logger.info("Converting via llama.cpp %s (--outtype %s) ...", convert_script, quant_type)
    try:
        _run([sys.executable, str(convert_script), str(model_dir),
              "--outfile", str(output_path), "--outtype", quant_type])
    except subprocess.CalledProcessError as exc:
        # Fall back to f16 output then quantise separately if --outtype rejected.
        f16 = output_path.with_name(output_path.name + ".f16")
        _run([sys.executable, str(convert_script), str(model_dir),
              "--outfile", str(f16), "--outtype", "f16"])
        logger.warning("Direct %s output unsupported; converting f16 then quantising.", quant_type)
        raise RuntimeError(
            "llama.cpp convert finished in f16 but separate quantisation "
            "(llama-quantize) is not available in this build.") from exc
    if not output_path.is_file():
        raise RuntimeError(f"GGUF was not produced after conversion at {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge a trained QAD LoRA adapter into the base Qwen and export Q4_K_M GGUF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--source", required=True,
                   help="Trained adapter/model directory, e.g. outputs/models/exp1_qad")
    p.add_argument("--base-model", default=None,
                   help="Base model (HF id or local path). Defaults to adapter_config.json's base.")
    p.add_argument("--output", default=None,
                   help="Output GGUF path (defaults to <source_dir>_q<quant>.gguf)")
    p.add_argument("--quant-type", default=DEFAULT_QUANT, choices=sorted(SUPPORTED_QUANTS))
    p.add_argument("--keep-checkpoint", action="store_true",
                   help="Keep the merged full-precision checkpoint dir alongside the GGUF.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source)
    if not (source_dir / "adapter_config.json").is_file():
        logger.error("--source %s is not a PEFT adapter dir (adapter_config.json missing).", source_dir)
        return 2

    base_model = _resolve_base_model(source_dir, args.base_model)
    output_path = (Path(args.output) if args.output else
                   source_dir.with_name(f"{source_dir.name}_q{args.quant_type}.gguf"))

    scratch = Path(tempfile.mkdtemp(prefix="gguf_merge_"))
    merged_dir = scratch / "merged"
    try:
        merge_and_save(source_dir, base_model, merged_dir)
        _convert_gguf(merged_dir, output_path, args.quant_type)
        if not output_path.is_file():
            logger.error("GGUF was not produced at %s", output_path)
            return 1
        size_mb = output_path.stat().st_size / 1e6
        logger.info("Export completed: %s (%.1f MB)", output_path, size_mb)
        if args.keep_checkpoint:
            kept = output_path.with_suffix("") + "_merged"
            shutil.move(str(merged_dir), str(kept))
            logger.info("Merged checkpoint kept at %s", kept)
        return 0
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

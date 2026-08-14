#!/usr/bin/env python3
"""apply_all_fixes.py — Apply every root-cause fix in place, on the live workspace.

.. deprecated:: 2026-08-14
    The in-place fixes this script applied (group_split, student_loader wiring,
    exp1 split) are now merged into the source tree itself. This script embeds
    stale copies of that source; do not run it on a current checkout — it may
    revert or shadow the merged fixes. Kept for historical reference only.

Run from /workspace:

    python3 apply_all_fixes.py --check     # report only, change nothing
    python3 apply_all_fixes.py             # apply
    python3 apply_all_fixes.py --verify    # re-run the post-conditions only

What it does, in order:

    STEP 0  locate the realeval package that Python actually imports
            (three copies exist; patching the wrong one is a silent no-op)
    STEP 1  append group_split + load_dataset to that data.py
    STEP 2  install student_loader.py next to it and wire real_backend to use it
    STEP 3  repoint exp1's naive shuffle at group_split
    STEP 4  declare the adapter variants in config/experiments.yaml
    STEP 5  verify: import, zero-overlap split, adapter discovery

Every edit writes a .bak first and is idempotent — re-running is safe.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

OK, BAD, WARN, SKIP = "[ OK ]", "[FAIL]", "[WARN]", "[SKIP]"
CHANGES: list[str] = []


def say(tag: str, msg: str):
    print(f"{tag} {msg}")


def backup(p: Path) -> Path:
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        shutil.copy2(p, b)
        say(OK, f"backup -> {b}")
    return b


# ═══════════════════════════════════════════════════════════════════════════
# STEP 0 — which realeval is actually imported?
# ═══════════════════════════════════════════════════════════════════════════
def step0_locate() -> tuple[Path, Path]:
    print("\n" + "=" * 76)
    print("  STEP 0  locate the imported realeval package")
    print("=" * 76)

    try:
        import realeval.data as d
        data_py = Path(d.__file__).resolve()
    except Exception as e:
        say(BAD, f"cannot import realeval.data: {e}")
        say(WARN, "Set PYTHONPATH to the repo root first, e.g.")
        say(WARN, "  export PYTHONPATH=/workspace/H100_package_realeval:$PYTHONPATH")
        sys.exit(1)

    pkg_root = data_py.parent            # .../realeval
    repo_root = pkg_root.parent          # the dir containing realeval/
    say(OK, f"realeval.data  -> {data_py}")
    say(OK, f"package root   -> {pkg_root}")
    say(OK, f"repo root      -> {repo_root}")

    # Show the decoys so the user knows what is being ignored.
    others = subprocess.run(
        ["bash", "-lc",
         "ls -d /workspace/*/realeval /workspace/realeval 2>/dev/null | sort -u"],
        capture_output=True, text=True).stdout.strip().splitlines()
    decoys = [o for o in others if Path(o).resolve() != pkg_root]
    if decoys:
        say(WARN, f"other realeval copies present (NOT patched): {', '.join(decoys)}")
        say(WARN, "delete or symlink them once this run is green, to avoid confusion")
    return repo_root, data_py


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — group_split + load_dataset
# ═══════════════════════════════════════════════════════════════════════════
GROUP_SPLIT_SRC = r'''

# ─────────────────────────────────────────────────────────────────────────────
# Leakage-safe splitting (added by apply_all_fixes.py)
# ─────────────────────────────────────────────────────────────────────────────
def _normalise_for_grouping(text: str) -> str:
    """Canonical form used to detect near-duplicate messages.

    TAF-28k is templated fraud SMS: only digits, URLs and whitespace vary between
    siblings of the same template. Collapsing those makes siblings hash identically,
    so group_split can keep a whole template family on one side of the split.
    """
    import re
    t = (text or "").lower().strip()
    t = re.sub(r"https?://\S+", " <url> ", t)   # URLs first (they contain digits)
    t = re.sub(r"\d+", " <num> ", t)            # one rule for every digit run
    t = re.sub(r"[^\w\s<>]", " ", t)            # punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t


def group_split(texts, labels, test_ratio: float = 0.2, seed: int = 42):
    """Split into (train_idx, test_idx) so duplicate/templated texts never straddle.

    Groups by a hash of the normalised text, then fills the test side per label so the
    class balance survives whole-group assignment. Returns two sorted index lists.
    """
    import hashlib
    import random
    from collections import Counter, defaultdict

    groups = defaultdict(list)
    for i, t in enumerate(texts):
        key = hashlib.md5(_normalise_for_grouping(t).encode("utf-8")).hexdigest()
        groups[key].append(i)

    keys = sorted(groups.keys())
    random.Random(seed).shuffle(keys)

    def _dominant_label(idxs):
        vals = [int(labels[i]) for i in idxs]
        return max(set(vals), key=vals.count) if vals else 0

    label_counts = Counter(int(l) for l in labels)
    targets = {l: int(c * test_ratio) for l, c in label_counts.items()}
    filled = {l: 0 for l in label_counts}

    test_idx, train_idx = [], []
    for k in keys:
        g = groups[k]
        dl = _dominant_label(g)
        if filled.get(dl, 0) < targets.get(dl, 0):
            test_idx.extend(g)
            for i in g:
                filled[int(labels[i])] = filled.get(int(labels[i]), 0) + 1
        else:
            train_idx.extend(g)

    achieved = len(test_idx) / max(1, len(texts))
    if abs(achieved - test_ratio) > 0.5 * test_ratio:
        import warnings
        warnings.warn(
            f"group_split: requested test_ratio={test_ratio:.2f} but achieved "
            f"{achieved:.2f} from {len(groups)} groups over {len(texts)} samples; "
            "the corpus is dominated by a few large duplicate clusters.",
            RuntimeWarning)

    return sorted(train_idx), sorted(test_idx)


def load_dataset(name: str = "taf28k", max_samples: int | None = None) -> dict:
    """Uniform entry point over the per-corpus loaders (expected by exp14 and B6)."""
    n = (name or "taf28k").lower()
    if n in ("taf28k", "taf-28k", "balanced4k", "balanced_4k"):
        return load_taf28k(max_samples=max_samples)
    if n in ("chifraud", "chi_fraud"):
        return load_chifraud(max_samples=max_samples)
    if n in ("chifraud_balanced", "chifraud-balanced"):
        return load_chifraud_balanced()
    if n in ("advfraud", "advfraud3k", "advfraud-3k"):
        return load_advfraud3k(max_samples=max_samples)
    if n in ("spam11358", "spam"):
        return load_spam11358()
    if n == "synthetic":
        return load_synthetic(n=max_samples or 100)
    raise ValueError(f"unknown dataset: {name}")
'''


def step1_group_split(data_py: Path, check: bool):
    print("\n" + "=" * 76)
    print("  STEP 1  add group_split + load_dataset")
    print("=" * 76)
    src = data_py.read_text(encoding="utf-8")
    have_gs = "def group_split" in src
    have_ld = "def load_dataset" in src
    say(OK if have_gs else WARN, f"group_split present : {have_gs}")
    say(OK if have_ld else WARN, f"load_dataset present: {have_ld}")

    if have_gs and have_ld:
        say(SKIP, "both already defined")
        return
    if check:
        say(WARN, "--check: would append the missing definitions")
        return

    backup(data_py)
    add = GROUP_SPLIT_SRC
    if have_gs:                       # keep only load_dataset
        add = "\n\n" + add[add.index("def load_dataset"):]
    elif have_ld:                     # keep only group_split
        add = add[:add.index("def load_dataset")]
    data_py.write_text(src.rstrip() + "\n" + add, encoding="utf-8")
    say(OK, f"appended to {data_py}")
    CHANGES.append(f"data.py: +group_split +load_dataset")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — student_loader + real_backend wiring
# ═══════════════════════════════════════════════════════════════════════════
STUDENT_LOADER_SRC = r'''"""student_loader.py — resolve a student_variant to a LoRA adapter and load it.

Added by apply_all_fixes.py. Without this, cluster/train_sft.py writes an adapter to
outputs/sft_checkpoints/ that no experiment ever loads, so every downstream experiment
silently scores the untuned base model.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

ADAPTER_ROOT = Path(os.environ.get("REALEVAL_ADAPTER_ROOT",
                                   "/workspace/outputs/sft_checkpoints"))
BASE_MODEL_DEFAULT = "Qwen/Qwen2.5-0.5B-Instruct"


def _is_adapter_dir(p: Path) -> bool:
    return (p / "adapter_config.json").is_file()


def _latest_checkpoint(root: Path):
    if not root.is_dir():
        return None
    cands = [d for d in root.glob("checkpoint-*") if _is_adapter_dir(d)]
    if not cands:
        return root if _is_adapter_dir(root) else None

    def _step(d):
        try:
            return int(d.name.split("-")[-1])
        except ValueError:
            return -1
    return max(cands, key=_step)


def discover_adapters(root: Path = ADAPTER_ROOT) -> dict:
    found = {}
    if not root.is_dir():
        return found
    latest = _latest_checkpoint(root)
    if latest:
        found["latest"] = latest
    for d in sorted(root.iterdir()):
        if d.is_dir() and _is_adapter_dir(d):
            found[d.name] = d
    return found


def resolve_adapter(variant: str, config: dict | None = None,
                    adapter_path=None):
    """Explicit path -> config['students'][variant] -> ROOT/<variant> -> newest ckpt."""
    if adapter_path:
        p = Path(adapter_path)
        if _is_adapter_dir(p):
            return p
        warnings.warn(f"adapter_path {p} has no adapter_config.json", RuntimeWarning)

    if config:
        declared = (config.get("students") or {}).get(variant)
        if declared and _is_adapter_dir(Path(declared)):
            return Path(declared)

    if variant in ("base", None, ""):
        return None

    per_variant = ADAPTER_ROOT / variant
    if _is_adapter_dir(per_variant):
        return per_variant
    return _latest_checkpoint(ADAPTER_ROOT)


def attach_adapter(model, variant: str = "base", config: dict | None = None,
                   adapter_path=None, merge: bool = True, quantize=None):
    """Attach a LoRA adapter to an already-loaded base model.

    Raises when a non-base variant is requested but no adapter exists — silently
    returning the base model is the failure mode that produced identical F1 across
    all thirteen ablation arms.
    """
    adapter = resolve_adapter(variant, config, adapter_path)
    if adapter is None:
        if variant not in ("base", None, ""):
            raise RuntimeError(
                f"student_variant='{variant}' requested but no LoRA adapter found under "
                f"{ADAPTER_ROOT}. Train one (cluster/train_sft.py) or pass adapter_path. "
                "Refusing to fall back to the base model.")
        return model

    from peft import PeftModel
    print(f"[student_loader] variant={variant} + adapter {adapter}")
    model = PeftModel.from_pretrained(model, str(adapter))
    if merge and quantize not in ("int4", "nf4", "int8"):
        model = model.merge_and_unload()
        print("[student_loader] adapter merged")
    return model


def load_student(config: dict | None = None, variant: str = "base",
                 quantize=None, adapter_path=None, base_model=None, merge: bool = True):
    """Load base + adapter in one call. Returns (model, tokenizer)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_id = (base_model or (config or {}).get("models", {}).get("teacher")
               or BASE_MODEL_DEFAULT)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    kwargs = {"torch_dtype": torch.bfloat16}
    if quantize in ("int4", "nf4"):
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4" if quantize == "nf4" else "fp4",
            bnb_4bit_compute_dtype=torch.bfloat16)
        kwargs["device_map"] = {"": 0} if device == "cuda" else "cpu"
    elif quantize == "int8":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        kwargs["device_map"] = {"": 0} if device == "cuda" else "cpu"
    elif quantize == "fp32":
        kwargs["torch_dtype"] = torch.float32

    tok = AutoTokenizer.from_pretrained(base_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_id, **kwargs)
    if "device_map" not in kwargs:
        model = model.to(device)

    model = attach_adapter(model, variant, config, adapter_path, merge, quantize)
    model.eval()
    return model, tok
'''


def step2_student_loader(pkg_root: Path, check: bool):
    print("\n" + "=" * 76)
    print("  STEP 2  install student_loader + wire real_backend")
    print("=" * 76)

    loader = pkg_root / "student_loader.py"
    if loader.exists() and "def attach_adapter" in loader.read_text():
        say(SKIP, f"{loader} already installed")
    elif check:
        say(WARN, f"--check: would create {loader}")
    else:
        loader.write_text(STUDENT_LOADER_SRC, encoding="utf-8")
        say(OK, f"created {loader}")
        CHANGES.append("realeval/student_loader.py created")

    # ── wire real_backend ──
    rb = pkg_root / "real_backend.py"
    if not rb.exists():
        say(WARN, f"{rb} not found — wire load_student in by hand")
        return
    src = rb.read_text(encoding="utf-8")
    if "student_loader" in src:
        say(SKIP, "real_backend already references student_loader")
        return

    # Find where the model is loaded and inject the adapter attach right after.
    pat = re.compile(
        r"(^\s*)(model,\s*tok(?:enizer)?\s*=\s*models\.load_causal_lm\([^\n]*\)\s*)$",
        re.M)
    m = pat.search(src)
    if not m:
        say(WARN, "could not locate `models.load_causal_lm(...)` in real_backend.py")
        say(WARN, "add these two lines yourself right after the model is loaded:")
        print("""
    from realeval.student_loader import attach_adapter
    model = attach_adapter(model, config.get("student_variant", "base"),
                           config, quantize=quantize)
""")
        return
    if check:
        say(WARN, f"--check: would inject attach_adapter after line "
                  f"{src[:m.start()].count(chr(10)) + 1}")
        return

    backup(rb)
    indent = m.group(1)
    inject = (f"{m.group(0)}\n"
              f"{indent}# Attach the tuned LoRA adapter when a student_variant is set.\n"
              f"{indent}from realeval.student_loader import attach_adapter\n"
              f"{indent}model = attach_adapter(model, config.get('student_variant', 'base'),\n"
              f"{indent}                       config, quantize=quantize)")
    rb.write_text(src[:m.start()] + inject + src[m.end():], encoding="utf-8")
    say(OK, f"wired attach_adapter into {rb}")
    CHANGES.append("real_backend.py: attach_adapter wired")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — exp1 naive shuffle -> group_split
# ═══════════════════════════════════════════════════════════════════════════
def step3_exp1_split(repo_root: Path, check: bool):
    print("\n" + "=" * 76)
    print("  STEP 3  repoint exp1's split at group_split")
    print("=" * 76)

    cands = list((repo_root / "experiments").glob("exp1*.py"))
    if not cands:
        say(WARN, "experiments/exp1*.py not found")
        return
    exp1 = cands[0]
    src = exp1.read_text(encoding="utf-8")

    if "group_split" in src:
        say(SKIP, f"{exp1.name} already uses group_split")
        return

    # Match the naive pattern seen in the audit:
    #   split = int(len(texts) * 0.8)
    #   train_texts = [texts[i] for i in idx[:split]]  ... etc
    # Match the naive block: `split = int(len(texts) * 0.8)` followed by the four
    # list comprehensions that slice idx[:split] / idx[split:]. Tolerates comment
    # lines and blank lines interleaved.
    pat = re.compile(
        r"(^[ \t]*)split[ \t]*=[ \t]*int\(len\(texts\)[ \t]*\*[ \t]*0\.8\)[^\n]*\n"
        r"(?:[ \t]*(?:#[^\n]*)?\n)*"
        r"(?:[ \t]*(?:train|test)_(?:texts|labels)[ \t]*=[ \t]*\[[^\]]*\][^\n]*\n"
        r"(?:[ \t]*(?:#[^\n]*)?\n)*){2,4}",
        re.M)
    m = pat.search(src)
    if not m:
        say(WARN, "naive-shuffle block not matched; showing lines 20-40 for manual edit:")
        for i, line in enumerate(src.splitlines()[19:40], start=20):
            print(f"    {i:3d}: {line}")
        say(WARN, "replace that block with:")
        print("""
    from realeval.data import group_split
    train_idx, test_idx = group_split(texts, labels, test_ratio=0.2, seed=_seed)
    train_texts  = [texts[i] for i in train_idx]
    train_labels = [int(labels[i]) for i in train_idx]
    test_texts   = [texts[i] for i in test_idx]
    test_labels  = [int(labels[i]) for i in test_idx]
""")
        return
    if check:
        say(WARN, f"--check: would replace the shuffle block at line "
                  f"{src[:m.start()].count(chr(10)) + 1}")
        return

    backup(exp1)
    indent = m.group(1)
    seed_expr = "_seed" if "_seed" in src else "config.get('reproducibility', {}).get('seed', 42)"
    repl = (
        f"{indent}# Leakage-safe split: template siblings must not straddle train/test.\n"
        f"{indent}from realeval.data import group_split\n"
        f"{indent}train_idx, test_idx = group_split(texts, labels, test_ratio=0.2, "
        f"seed={seed_expr})\n"
        f"{indent}train_texts  = [texts[i] for i in train_idx]\n"
        f"{indent}train_labels = [int(labels[i]) for i in train_idx]\n"
        f"{indent}test_texts   = [texts[i] for i in test_idx]\n"
        f"{indent}test_labels  = [int(labels[i]) for i in test_idx]\n")
    exp1.write_text(src[:m.start()] + repl + src[m.end():], encoding="utf-8")
    say(OK, f"{exp1.name}: naive shuffle -> group_split")
    CHANGES.append(f"{exp1.name}: group_split")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — declare adapter variants in the config
# ═══════════════════════════════════════════════════════════════════════════
def step4_config(repo_root: Path, check: bool):
    print("\n" + "=" * 76)
    print("  STEP 4  declare adapter variants in config/experiments.yaml")
    print("=" * 76)

    cfg = repo_root / "config" / "experiments.yaml"
    if not cfg.exists():
        say(WARN, f"{cfg} not found — skipping")
        return
    src = cfg.read_text(encoding="utf-8")
    if re.search(r"^students:", src, re.M):
        say(SKIP, "students: block already present")
        return

    root = Path(os.environ.get("REALEVAL_ADAPTER_ROOT",
                               "/workspace/outputs/sft_checkpoints"))
    found = {}
    if root.is_dir():
        for d in sorted(root.glob("checkpoint-*")):
            if (d / "adapter_config.json").is_file():
                found[d.name] = str(d)
    latest = max(found.items(), key=lambda kv: int(kv[0].split("-")[-1]))[1] if found else None

    block = "\n# LoRA adapters produced by cluster/train_sft.py (added by apply_all_fixes.py)\n"
    block += "students:\n"
    block += f"  qad_ovf: {latest or f'{root}/checkpoint-XXX  # TRAIN ME'}\n"
    block += f"  # qad_no_ovf: /workspace/outputs/sft_no_ovf/checkpoint-XXX\n"
    block += f"  # bitdistiller: /workspace/outputs/sft_bitdistiller/checkpoint-XXX\n"

    if check:
        say(WARN, "--check: would append:")
        print(block)
        return
    backup(cfg)
    cfg.write_text(src.rstrip() + "\n" + block, encoding="utf-8")
    say(OK, f"appended students: block ({'found ' + latest if latest else 'placeholder'})")
    CHANGES.append("experiments.yaml: students: block")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — verify
# ═══════════════════════════════════════════════════════════════════════════
def step5_verify(repo_root: Path):
    print("\n" + "=" * 76)
    print("  STEP 5  verification")
    print("=" * 76)
    failures = 0

    # 5a import
    try:
        for mod in ("realeval.data", "realeval.student_loader"):
            importlib.invalidate_caches()
            m = importlib.import_module(mod)
            importlib.reload(m)
        from realeval.data import group_split, load_dataset       # noqa: F401
        from realeval.student_loader import discover_adapters     # noqa: F401
        say(OK, "imports: group_split, load_dataset, discover_adapters")
    except Exception as e:
        say(BAD, f"import failed: {e}")
        failures += 1
        return failures

    # 5b split has zero overlap
    try:
        from realeval.data import group_split, load_taf28k
        ds = load_taf28k(max_samples=4000)
        texts, labels = ds["texts"], ds["labels"]
        if not texts:
            say(WARN, "TAF-28k empty; split check skipped")
        else:
            tr, te = group_split(texts, labels, 0.2, 42)
            a = {texts[i].strip() for i in tr}
            b = {texts[i].strip() for i in te}
            ov = len(a & b)
            pos_tr = sum(int(labels[i]) for i in tr) / max(1, len(tr))
            pos_te = sum(int(labels[i]) for i in te) / max(1, len(te))
            say(OK if ov == 0 else BAD,
                f"split: n_train={len(tr)} n_test={len(te)} exact-overlap={ov} "
                f"pos_ratio train/test = {pos_tr:.2f}/{pos_te:.2f}")
            failures += (ov != 0)
    except Exception as e:
        say(BAD, f"split check failed: {e}")
        failures += 1

    # 5c adapter discovery
    try:
        from realeval.student_loader import discover_adapters
        found = discover_adapters()
        if found:
            for k, v in found.items():
                say(OK, f"adapter {k:16s} -> {v}")
        else:
            say(WARN, "no adapters discovered; set REALEVAL_ADAPTER_ROOT or train one")
    except Exception as e:
        say(BAD, f"adapter discovery failed: {e}")
        failures += 1

    # 5d real_backend wiring
    rb = repo_root / "realeval" / "real_backend.py"
    if rb.exists():
        say(OK if "student_loader" in rb.read_text() else WARN,
            f"real_backend references student_loader: "
            f"{'student_loader' in rb.read_text()}")
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only")
    ap.add_argument("--verify", action="store_true", help="verification only")
    args = ap.parse_args()

    repo_root, data_py = step0_locate()
    pkg_root = data_py.parent

    if args.verify:
        sys.exit(1 if step5_verify(repo_root) else 0)

    step1_group_split(data_py, args.check)
    step2_student_loader(pkg_root, args.check)
    step3_exp1_split(repo_root, args.check)
    step4_config(repo_root, args.check)

    if args.check:
        print("\n--check complete; nothing was written.")
        return

    failures = step5_verify(repo_root)

    print("\n" + "=" * 76)
    print("  SUMMARY")
    print("=" * 76)
    for c in CHANGES:
        say(OK, c)
    if not CHANGES:
        say(SKIP, "no changes were needed")
    print(f"\n  verification failures: {failures}")
    print("""
  Next:
    1. rerun exp1 -> exp3 -> exp5
    2. exp3's thirteen ablation arms must now show DIFFERENT F1 values.
       If they are still identical, the adapter is not reaching the scored model:
         python3 -c "from realeval.student_loader import discover_adapters as d; print(d())"
    3. exp5 accuracy should leave the 0.50 chance line.
""")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

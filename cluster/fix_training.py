#!/usr/bin/env python3
"""fix_training.py — 修复 train_sft.py 的训练缺陷（合并 fix_collator / fix_train_sft）

用法:
  python cluster/fix_training.py --check            # 仅检查，不修改
  python cluster/fix_training.py                    # 应用全部修复
  python cluster/fix_training.py --fix collator     # 仅修复 collator padding
  python cluster/fix_training.py --fix label        # 仅修复 label masking
  python cluster/fix_training.py --self-test        # 验证 tokenize_fn 正确性

修复内容:
  1. collator: 将 DataCollatorWithPadding 替换为 _PadCollator（同时 padding labels）
  2. label:   修复 tokenize_fn 中 answer token 被错误 mask 为 -100 的问题
"""
from __future__ import annotations
import argparse, re, shutil, sys
from pathlib import Path

# train_sft.py 与本脚本同目录（cluster/），随仓库部署位置自适应（pod 上为 /workspace/H100_package_realeval）
TRAIN_SFT = Path(__file__).resolve().parent / "train_sft.py"

# ── collator 修复 ────────────────────────────────────────────────────────────

COLLATOR_SRC = '''

class _PadCollator:
    """Pad input_ids/attention_mask with pad_token_id and labels with -100.

    DataCollatorWithPadding ignores `labels`, so ragged label rows reach torch.tensor()
    and raise. Padding all three here keeps every row the same length and keeps the pad
    positions out of the loss.
    """
    def __init__(self, tokenizer):
        self.pad_id = tokenizer.pad_token_id

    def __call__(self, features):
        import torch
        maxlen = max(len(f["input_ids"]) for f in features)
        ids, labels, attn = [], [], []
        for f in features:
            gap = maxlen - len(f["input_ids"])
            ids.append(list(f["input_ids"]) + [self.pad_id] * gap)
            labels.append(list(f["labels"]) + [-100] * gap)
            am = list(f.get("attention_mask", [1] * len(f["input_ids"])))
            attn.append(am + [0] * gap)
        return {"input_ids": torch.tensor(ids, dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long),
                "attention_mask": torch.tensor(attn, dtype=torch.long)}

'''


def fix_collator(src: str, check: bool = False) -> tuple[str, bool]:
    """替换 DataCollatorWithPadding → _PadCollator。"""
    if "class _PadCollator" in src:
        print("[SKIP] collator already patched")
        return src, True

    if check:
        print("[CHECK] would insert _PadCollator + wire Trainer")
        return src, False

    # 1. 移除 tokenize_fn 内的 per-batch padding
    old_pad = re.search(
        r"\n        maxlen = max\(len\(x\) for x in input_ids_list\)\n"
        r".*?attn_list\[i\]\s*\+= \[0\] \* gap\n", src, re.S)
    if old_pad:
        src = src[:old_pad.start()] + "\n" + src[old_pad.end():]
        print("[ OK ] removed per-batch padding from tokenize_fn")
    else:
        print("[WARN] padding block not found (may already be absent)")

    # 2. 插入 _PadCollator 类
    m = re.search(r"\ndef main\(\):", src)
    if not m:
        print("[FAIL] 'def main():' not found")
        return src, False
    src = src[:m.start()] + COLLATOR_SRC + src[m.start():]
    print("[ OK ] inserted _PadCollator")

    # 3. 将 Trainer 指向 _PadCollator
    before = src
    src = re.sub(r"data_collator\s*=\s*[^,\n)]+", "data_collator=_PadCollator(tokenizer)", src)
    if src != before:
        print("[ OK ] Trainer now uses _PadCollator")
    else:
        print("[WARN] no data_collator= argument found; add it to the Trainer call manually")

    return src, True


# ── label masking 修复 ───────────────────────────────────────────────────────

NEW_TOKENIZE_FN = '''    def tokenize_fn(examples):
        """Build (input_ids, labels) with an exact prompt/answer boundary.

        Prompt and answer are tokenised independently with add_special_tokens=False and
        concatenated, so the supervision boundary is known by construction and cannot
        drift with the tokeniser's merge rules.
        """
        PROMPT = ("Determine if the following text is fraud or normal.\\n\\n"
                  "Text: {text}\\n\\nAnswer:")
        input_ids_list, labels_list, attn_list = [], [], []

        for t, l in zip(examples["text"], examples["label"]):
            answer = " fraud" if l == 1 else " normal"
            p_ids = tokenizer(PROMPT.format(text=t), add_special_tokens=False)["input_ids"]
            a_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
            if tokenizer.eos_token_id is not None:
                a_ids = a_ids + [tokenizer.eos_token_id]

            # Truncate the PROMPT only, never the answer, so supervision always survives.
            budget = 256 - len(a_ids)
            if len(p_ids) > budget:
                p_ids = p_ids[:budget]

            ids = p_ids + a_ids
            input_ids_list.append(ids)
            labels_list.append([-100] * len(p_ids) + a_ids[:])
            attn_list.append([1] * len(ids))

        maxlen = max(len(x) for x in input_ids_list)
        pad_id = tokenizer.pad_token_id
        for i in range(len(input_ids_list)):
            gap = maxlen - len(input_ids_list[i])
            input_ids_list[i] += [pad_id] * gap
            labels_list[i]    += [-100] * gap
            attn_list[i]      += [0] * gap

        n_sup = sum(1 for row in labels_list for x in row if x != -100)
        if n_sup == 0:
            raise RuntimeError(
                "tokenize_fn produced zero supervised tokens; training would report "
                "loss=0.0 and learn nothing.")

        return {"input_ids": input_ids_list, "labels": labels_list,
                "attention_mask": attn_list}
'''


def fix_label_masking(src: str, check: bool = False) -> tuple[str, bool]:
    """修复 tokenize_fn 的 label masking 缺陷。"""
    if "produced zero supervised tokens" in src:
        print("[SKIP] label masking already patched")
        return src, True

    m = re.search(r"^    def tokenize_fn\(examples\):.*?^        return enc\n", src, re.S | re.M)
    if not m:
        print("[FAIL] tokenize_fn not found; patch by hand")
        return src, False

    print(f"[ OK ] found tokenize_fn at line {src[:m.start()].count(chr(10)) + 1}")
    if check:
        print("[CHECK] would replace tokenize_fn")
        return src, False

    src = src[:m.start()] + NEW_TOKENIZE_FN + src[m.end():]
    # 同时移除 DataCollatorWithPadding（label masking 修复与 collator 冲突时使用 None）
    src = src.replace("DataCollatorWithPadding(tokenizer=tokenizer)", "None")
    print("[ OK ] tokenize_fn replaced")
    return src, True


# ── 自检 ─────────────────────────────────────────────────────────────────────

def self_test() -> bool:
    """验证新 tokenize_fn 产生的 supervised tokens > 0。"""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    PROMPT = "Determine if the following text is fraud or normal.\n\nText: {text}\n\nAnswer:"
    samples = [("亲,账号csll2250余额32元可提现登166956ky.cc戳xm", 1),
               ("小李，下午八点开会，请准时参加", 0),
               ("Hey, are we still on for lunch tomorrow?", 0)]
    total = 0
    for text, label in samples:
        answer = " fraud" if label == 1 else " normal"
        p = tok(PROMPT.format(text=text), add_special_tokens=False)["input_ids"]
        a = tok(answer, add_special_tokens=False)["input_ids"] + [tok.eos_token_id]
        labels = [-100] * len(p) + a
        n = sum(1 for x in labels if x != -100)
        total += n
        print(f"  prompt={len(p):3d} answer={len(a)} supervised={n} "
              f"tokens={tok.convert_ids_to_tokens(a)}")
    print()
    print(("[ OK ]" if total > 0 else "[FAIL]"), f"{total} supervised tokens")
    return total > 0


# ── 主入口 ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="修复 train_sft.py 的训练缺陷")
    ap.add_argument("--check", action="store_true", help="仅检查，不写入")
    ap.add_argument("--self-test", action="store_true", help="验证 tokenize_fn 正确性")
    ap.add_argument("--fix", choices=["collator", "label", "all"], default="all",
                    help="选择修复项（默认 all）")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(0 if self_test() else 1)

    if not TRAIN_SFT.exists():
        print(f"[FAIL] {TRAIN_SFT} not found")
        sys.exit(1)

    src = TRAIN_SFT.read_text(encoding="utf-8")
    if not args.check:
        shutil.copy2(TRAIN_SFT, TRAIN_SFT.with_suffix(".py.bak_fix"))
        print(f"[backup] -> {TRAIN_SFT.with_suffix('.py.bak_fix')}")

    changed = False

    if args.fix in ("collator", "all"):
        src, ok = fix_collator(src, check=args.check)
        changed = changed or ok

    if args.fix in ("label", "all"):
        src, ok = fix_label_masking(src, check=args.check)
        changed = changed or ok

    if not args.check and changed:
        TRAIN_SFT.write_text(src, encoding="utf-8")
        print(f"\n[ OK ] {TRAIN_SFT} patched")
    elif args.check:
        print("\n[CHECK] --check complete; nothing was written.")
    else:
        print("\n[SKIP] no changes needed")


if __name__ == "__main__":
    main()

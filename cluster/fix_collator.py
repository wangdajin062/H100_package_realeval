#!/usr/bin/env python3
"""Fix the length mismatch between per-map-batch padding and the Trainer's collator.

tokenize_fn padded within each datasets.map batch, so different batches got different
lengths (93 vs 119). DataCollatorWithPadding then pads input_ids but not labels, and
building the tensor fails.

Fix: tokenize WITHOUT padding, and use a collator that pads input_ids, attention_mask
and labels together (labels padded with -100 so they stay out of the loss).
"""
from pathlib import Path
import re, shutil, sys

P = Path("/workspace/cluster/train_sft.py")
src = P.read_text(encoding="utf-8")

if "class _PadCollator" in src:
    print("already patched"); sys.exit(0)

shutil.copy2(P, P.with_suffix(".py.bak_collator"))
print("backup ->", P.with_suffix(".py.bak_collator"))

# 1. drop the in-tokenizer padding block
old_pad = re.search(
    r"\n        maxlen = max\(len\(x\) for x in input_ids_list\)\n"
    r".*?attn_list\[i\]\s*\+= \[0\] \* gap\n", src, re.S)
if old_pad:
    src = src[:old_pad.start()] + "\n" + src[old_pad.end():]
    print("removed per-batch padding from tokenize_fn")
else:
    print("WARN: padding block not found (may already be absent)")

# 2. insert a collator that pads labels too
collator_src = '''

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
m = re.search(r"\ndef main\(\):", src)
src = src[:m.start()] + collator_src + src[m.start():]
print("inserted _PadCollator")

# 3. point Trainer at it
before = src
src = re.sub(r"data_collator\s*=\s*[^,\n)]+", "data_collator=_PadCollator(tokenizer)", src)
if src != before:
    print("Trainer now uses _PadCollator")
else:
    print("WARN: no data_collator= argument found; add it to the Trainer call manually")

P.write_text(src, encoding="utf-8")
print("patched")

#!/usr/bin/env python3
"""Repair the label-masking defect that made training a no-op.

The original tokenize_fn tokenised prompt and full text separately, then masked
range(prompt_len). For this template both tokenise to the SAME length -- the trailing
space in "Answer: " is its own token and " fraud" occupies that position -- so the mask
covered the answer too and every label became -100 (loss 0.0, grad_norm 0.0, eval nan).
"""
from __future__ import annotations
import argparse, re, shutil, sys
from pathlib import Path

TRAIN_SFT = Path("/workspace/cluster/train_sft.py")

NEW_FN = '''    def tokenize_fn(examples):
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


def patch(check=False):
    if not TRAIN_SFT.exists():
        print("[FAIL]", TRAIN_SFT, "not found"); return False
    src = TRAIN_SFT.read_text(encoding="utf-8")
    if "produced zero supervised tokens" in src:
        print("[SKIP] already patched"); return True
    m = re.search(r"^    def tokenize_fn\(examples\):.*?^        return enc\n", src, re.S | re.M)
    if not m:
        print("[FAIL] tokenize_fn not found; patch by hand"); return False
    print("found tokenize_fn at line", src[:m.start()].count("\n") + 1)
    if check:
        print("[CHECK] would replace it"); return True
    shutil.copy2(TRAIN_SFT, TRAIN_SFT.with_suffix(".py.bak_mask"))
    print("backup ->", TRAIN_SFT.with_suffix(".py.bak_mask"))
    src = src[:m.start()] + NEW_FN + src[m.end():]
    src = src.replace("DataCollatorWithPadding(tokenizer=tokenizer)", "None")
    TRAIN_SFT.write_text(src, encoding="utf-8")
    print("[ OK ] tokenize_fn replaced")
    return True


def self_test():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    PROMPT = ("Determine if the following text is fraud or normal.\n\n"
              "Text: {text}\n\nAnswer:")
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if patch(a.check) else 1)

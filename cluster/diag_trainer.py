#!/usr/bin/env python3
"""Reproduce the Trainer NaN by turning one knob at a time."""
import sys, itertools
sys.path.insert(0, "/workspace")
import torch
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          Trainer, TrainingArguments)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset as HFDataset
from realeval.data import load_text_corpus, group_split

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
PROMPT = ("Determine if the following text is fraud or normal.\n\n"
          "Text: {text}\n\nAnswer:")

tok = AutoTokenizer.from_pretrained(MODEL)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token


class PadCollator:
    def __init__(self, pad_id): self.pad_id = pad_id
    def __call__(self, feats):
        L = max(len(f["input_ids"]) for f in feats)
        ids, lab, att = [], [], []
        for f in feats:
            g = L - len(f["input_ids"])
            ids.append(list(f["input_ids"]) + [self.pad_id]*g)
            lab.append(list(f["labels"]) + [-100]*g)
            att.append(list(f["attention_mask"]) + [0]*g)
        return {"input_ids": torch.tensor(ids), "labels": torch.tensor(lab),
                "attention_mask": torch.tensor(att)}


def build_ds(n=128):
    ds = load_text_corpus("balanced4k", max_samples=n)
    rows = {"input_ids": [], "labels": [], "attention_mask": []}
    for t, l in zip(ds["texts"], ds["labels"]):
        p = tok(PROMPT.format(text=t), add_special_tokens=False)["input_ids"][:200]
        a = tok(" fraud" if l == 1 else " normal", add_special_tokens=False)["input_ids"]
        a = a + [tok.eos_token_id]
        rows["input_ids"].append(p + a)
        rows["labels"].append([-100]*len(p) + a)
        rows["attention_mask"].append([1]*(len(p)+len(a)))
    return HFDataset.from_dict(rows)


def run(tag, **over):
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj","k_proj","v_proj","o_proj",
                        "gate_proj","up_proj","down_proj"]))
    cfg = dict(output_dir="/tmp/diag_out", num_train_epochs=1,
               per_device_train_batch_size=8, gradient_accumulation_steps=4,
               learning_rate=2e-5, warmup_ratio=0.1, lr_scheduler_type="cosine",
               logging_steps=1, max_steps=4, save_strategy="no",
               eval_strategy="no", bf16=True, dataloader_num_workers=4,
               report_to="none")
    cfg.update(over)
    tr = Trainer(model=model, args=TrainingArguments(**cfg),
                 train_dataset=build_ds(), data_collator=PadCollator(tok.pad_token_id))
    hist = tr.train().metrics
    logs = [l for l in tr.state.log_history if "loss" in l]
    losses = [round(l["loss"], 4) for l in logs]
    gns = [l.get("grad_norm") for l in logs]
    ok = all(g is not None and g == g and g != float("inf") for g in gns)
    print(f"  [{'OK  ' if ok else 'NaN '}] {tag:38s} loss={losses}  grad_norm={gns}")
    del model, tr
    torch.cuda.empty_cache()


print("=== baseline (mirrors train_sft.py) ===")
run("as-is")
print("\n=== one knob at a time ===")
run("dataloader_num_workers=0", dataloader_num_workers=0)
run("gradient_accumulation_steps=1", gradient_accumulation_steps=1)
run("ga=1 + workers=0", gradient_accumulation_steps=1, dataloader_num_workers=0)
run("max_grad_norm=0.3", max_grad_norm=0.3)
run("bf16=False (fp32)", bf16=False)

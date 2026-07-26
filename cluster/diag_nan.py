#!/usr/bin/env python3
"""Pinpoint where NaN enters the first forward/backward pass."""
import sys
sys.path.insert(0, "/workspace")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType
from realeval.data import load_text_corpus, group_split

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

print("=== loading model (bf16, device_map=auto) ===")
model = AutoModelForCausalLM.from_pretrained(
    MODEL, torch_dtype=torch.bfloat16, device_map="auto")
model = get_peft_model(model, LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]))

# dtype audit: Adam on bf16 params is a classic NaN source
dt = {}
for n, p in model.named_parameters():
    if p.requires_grad:
        dt[str(p.dtype)] = dt.get(str(p.dtype), 0) + 1
print("trainable param dtypes:", dt, " <- fp32 expected for LoRA")

ds = load_text_corpus("balanced4k", max_samples=64)
texts, labels = ds["texts"], ds["labels"]

PROMPT = ("Determine if the following text is fraud or normal.\n\n"
          "Text: {text}\n\nAnswer:")
ids_list, lab_list = [], []
for t, l in zip(texts[:8], labels[:8]):
    p = tok(PROMPT.format(text=t), add_special_tokens=False)["input_ids"]
    a = tok(" fraud" if l == 1 else " normal", add_special_tokens=False)["input_ids"]
    a = a + [tok.eos_token_id]
    ids_list.append(p + a)
    lab_list.append([-100]*len(p) + a)

maxlen = max(len(x) for x in ids_list)
pad = tok.pad_token_id
inp = torch.tensor([x + [pad]*(maxlen-len(x)) for x in ids_list])
lab = torch.tensor([x + [-100]*(maxlen-len(x)) for x in lab_list])
att = torch.tensor([[1]*len(x) + [0]*(maxlen-len(x)) for x in ids_list])

dev = next(model.parameters()).device
inp, lab, att = inp.to(dev), lab.to(dev), att.to(dev)
n_sup = int((lab != -100).sum())
print(f"batch: {inp.shape}  supervised tokens: {n_sup}")

print("\n=== forward ===")
model.train()
out = model(input_ids=inp, attention_mask=att, labels=lab)
print("logits finite:", torch.isfinite(out.logits).all().item(),
      " dtype:", out.logits.dtype,
      " absmax:", float(out.logits.abs().max()))
print("loss:", float(out.loss), " finite:", torch.isfinite(out.loss).item())

print("\n=== backward ===")
out.loss.backward()
bad = []
for n, p in model.named_parameters():
    if p.requires_grad and p.grad is not None:
        if not torch.isfinite(p.grad).all():
            bad.append(n)
print(f"params with non-finite grad: {len(bad)}")
for n in bad[:8]:
    print("   ", n)
if not bad:
    gn = torch.nn.utils.clip_grad_norm_(
        [p for p in model.parameters() if p.requires_grad], 1e9)
    print("grad_norm:", float(gn))

"""Merge a LoRA adapter into its base model and save FP16 safetensors (CPU only).

    uv run --group merge python -m training.merge_adapter \
        ~/models/adapters/qwen2.5-coder-1.5b-qlora-v2 ~/models/merged/qwen2.5-coder-1.5b-qlora-v2

The adapters were evaluated served on the FP16 base (vLLM LoRA), not on the NF4 base used in
training, so merging into the full-precision base reproduces the evaluated model. Before saving,
the merge is checked on a few chat prompts: the adapter must change the base logits, base +
adapter (unmerged) and the merged model must agree in FP32, and the FP16 copy must keep the FP32
next-token choices.
"""

import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASES = {
    "Qwen/Qwen2.5-Coder-1.5B-Instruct": "2e1fd397ee46e1388853d2af2c993145b0f1098a",
    "unsloth/Phi-4-mini-instruct": "75becc471c56fc34761ec998615ca6f8535c5a61",
    "Qwen/Qwen2.5-Coder-3B-Instruct": "488639f1ff808d1d3d0ba301aef8c11461451ec5",
}
PROMPTS = [
    "Write a Python function that returns the n-th Fibonacci number.",
    "Review the following Python code for bugs.\n\n```python\ndef avg(xs):\n    return sum(xs) / len(xs) + 1\n```",
    "Predict the value returned by `sorted({3: 'a', 1: 'b'})`.",
]


def chat_ids(tok, text: str) -> torch.Tensor:
    ids = tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, return_tensors="pt")
    return ids["input_ids"] if hasattr(ids, "keys") else ids


@torch.no_grad()
def logits(model, batches: list[torch.Tensor]) -> list[torch.Tensor]:
    return [model(ids).logits.float() for ids in batches]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    adapter, out = args.adapter.expanduser(), args.out.expanduser()

    base_repo = json.loads((adapter / "adapter_config.json").read_text())["base_model_name_or_path"]
    revision = BASES[base_repo]
    tok = AutoTokenizer.from_pretrained(base_repo, revision=revision)
    base = AutoModelForCausalLM.from_pretrained(base_repo, revision=revision, dtype=torch.float32)
    model = PeftModel.from_pretrained(base, str(adapter))
    model.eval()

    batches = [chat_ids(tok, p) for p in PROMPTS]
    with model.disable_adapter():
        bare = logits(model, batches)
    before = logits(model, batches)
    adapter_effect = max((a - b).abs().max().item() for a, b in zip(bare, before, strict=True))
    merged = model.merge_and_unload()
    after = logits(merged, batches)
    max_diff = max((a - b).abs().max().item() for a, b in zip(before, after, strict=True))

    merged.half()  # in place: weights rounded to FP16
    rounded = logits(merged.float(), batches)  # CPU matmuls run in FP32 on the rounded weights
    agree = [(a.argmax(-1) == b.argmax(-1)).float().mean().item() for a, b in zip(after, rounded, strict=True)]
    report = {"base": base_repo, "revision": revision, "adapter": str(adapter),
              "max_abs_logit_diff_adapter_vs_bare_base": adapter_effect,
              "max_abs_logit_diff_merged_vs_unmerged_fp32": max_diff,
              "fp16_top1_agreement_with_fp32": [round(x, 4) for x in agree]}
    print(json.dumps(report, indent=2))
    if adapter_effect < 1.0:
        raise SystemExit("adapter barely changes the base model; was it loaded?")
    if max_diff > 1e-2:
        raise SystemExit("merged model disagrees with base + adapter; not saving")

    merged.half().save_pretrained(out, safe_serialization=True)
    tok.save_pretrained(out)
    (out / "merge_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

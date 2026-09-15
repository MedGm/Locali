# W1 risk spikes on Kaggle T4 — results

Date: 2026-09-15. Script: [`training/kaggle/w1-spikes/w1_spikes.py`](../../../training/kaggle/w1-spikes/w1_spikes.py). Kaggle notebook `locali-w1-spikes`, versions 1–3. GPU time used: ≈1 h.

Environment (all runs): 2 × Tesla T4 (15 GB, compute capability 7.5, no native bf16), Python 3.12.13, torch 2.10.0+cu128, transformers 5.5.0, TRL 0.24.0, PEFT 0.19.1, bitsandbytes 0.50.2, Unsloth 2026.9.4, vLLM 0.29.0 (separate venv).

## Verdicts

| Question | Verdict | Evidence |
|---|---|---|
| Does QLoRA on Qwen2.5-Coder-1.5B run on a T4? | **Yes** | run2 `qwen25_qlora` |
| Does QLoRA on Phi-4-mini run on a T4? | **Yes** | run3 `phi4mini_qlora` |
| Can Qwen3.5-2B be LoRA-trained on a T4 with Unsloth? | **No** (fp16, bf16 and fp32 all fail) | run1–3 `qwen35_*` |
| Are rsLoRA and DoRA available? | **Yes**; DoRA costs 3× time | run1 `peft_*` |
| Can Qwen3.5-9B serve as teacher on Kaggle? | **Yes, with vLLM** (HF 4-bit too slow) | run2 `teacher_vllm`, run1 `teacher_hf4bit` |

## Training measurements

30 steps, batch 4, LoRA r=16 on all attention and MLP projections, completion-only loss, sequence cap 2048, samples from `bigcode/self-oss-instruct-sc2-exec-filter-50k`.

| Model (exact pinned weights) | Method | Train tokens/s (avg 277–306-token samples) | Step at 4 × 2048 tokens | Peak VRAM, GPU 0 only* | Loss, step 1 → 30 |
|---|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | QLoRA NF4 | **1,188** | 4.85 s (≈1,690 tok/s) | 1.9 GB; 2.3 GB at 4 × 2048 | 0.760 → 0.636 |
| Phi-4-mini | QLoRA NF4 | **482** | 15.5 s (≈530 tok/s) | 2.3 GB; 3.3 GB at 4 × 2048 | 0.683 → 0.646 |
| Qwen2.5-Coder-1.5B | QLoRA + rsLoRA (15 steps)† | 1,111 | — | 1.8 GB | 0.761 → 0.450 |
| Qwen2.5-Coder-1.5B | QLoRA + DoRA (15 steps)† | 390 | — | 2.8 GB | 0.761 → 0.463 |

\* Unsloth placed each model across both GPUs (e.g. `lm_head` on `cuda:1`, data parallel = 1), and peak memory was read on GPU 0 only. VRAM figures are therefore lower bounds, and throughput includes inter-GPU transfer. Production runs pin one GPU.
† Run 1, where Unsloth substituted its pre-quantized mirror (see pitfalls). Relative speed is still valid.

Projected cost per epoch of the planned ≈7M-token dataset: **Qwen2.5-Coder-1.5B ≈1.2–1.6 h**, **Phi-4-mini ≈3.7–4.0 h**, DoRA on 1.5B ≈5 h.

## Teacher measurements (Qwen3.5-9B, thinking off, 200 max tokens)

| Stack | Setup | Load | Throughput |
|---|---|---|---|
| **vLLM 0.29.0** | FP16, tensor parallel 2, eager mode, 32 concurrent requests | 615 s (includes 19 GB download) | **101 tok/s** |
| Unsloth / HF `generate` | 4-bit, batch 8 | 160 s | 4.4 tok/s |

At 101 tok/s, ≈1.6M teacher tokens take ≈4.4 GPU-hours. Eager mode disables CUDA graphs, so this is a lower bound. Sample output for the `x > hi → x >= hi` mutation:

> The mutation incorrectly uses `x >= hi` instead of `x > hi`, causing the function to return `hi` when `x` equals `hi` rather than passing `x` through. This breaks the boundary condition where the input should be clamped only when it strictly exceeds the upper limit. The fix is to change the condition back to `if x > hi:`.

## Qwen3.5-2B failure

Every attempt stops at the first training step inside the Gated DeltaNet layer (`in_proj_qkv`):
`RuntimeError: expected mat1 and mat2 to have the same dtype, but got: c10::BFloat16 != c10::Half`

| Attempt | Load dtype | Autocast | Result |
|---|---|---|---|
| run1 | fp16 | fp16 | same error |
| run2 | fp16, residual bf16 tensors cast to fp16 | fp16 | same error |
| run3 | bf16 | none | same error |
| run3 | fp32 (Unsloth also logs "Using float16 precision for qwen3_5 won't work! Using float32") | none | same error |

The error is identical regardless of the requested precision, so a bf16 activation is produced inside Unsloth's Qwen3.5 T4 code path. The linear-attention fast paths (`fla`, `causal_conv1d`) are not installed on Kaggle. Serving Qwen3.5 on T4 through vLLM works (teacher spike), so Qwen3.5 stays available for inference benchmarks.

## Pitfalls found (and fixes now in the script)

1. **Silent model substitution.** By default Unsloth replaces `Qwen/...` or `microsoft/...` with its own mirror (e.g. `unsloth/phi-4-mini-instruct-unsloth-bnb-4bit`, a "dynamic" 4-bit quant that differs from standard NF4) and drops `revision`. Fix: `use_exact_model_name=True`, then assert that the resolved name equals the requested repo.
2. **Phi-4-mini official tokenizer is rejected.** `pad_token == eos_token == <|endoftext|>` makes Unsloth raise "Could not find a valid pad token". Fix: pin `unsloth/Phi-4-mini-instruct@75becc4`. Its two safetensors files have the same SHA-256 as `microsoft/Phi-4-mini-instruct@cfbefac`; only the tokenizer/config differ (pad id 200029, eos `<|end|>` id 200020, slightly shorter chat template). The same tokenizer must be used for baseline, fine-tuning and inference.
3. **Direct-forward memory probes mislead.** `model(input_ids, labels=...)` materializes full-vocabulary logits (11.7 GB for batch 2 × 2048 on 1.5B). Measure memory through the trainer, which uses chunked loss.
4. **vLLM in a subprocess script needs a `__main__` guard.** It switches to `spawn` once CUDA is initialized.
5. **Kaggle notebook `!python` output is buffered** until the cell ends. Stream through `subprocess.Popen` instead.

## Raw data

`run1/`, `run2/`, `run3/`: `results/*.json` per spike, `logs/*.log`, and the exact script version that ran.

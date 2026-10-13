# Merged QLoRA v2 model and GGUF exports

Merged on 2026-10-13 on the laptop (CPU, FP32), with `training/merge_adapter.py`, from
`~/models/adapters/qwen2.5-coder-1.5b-qlora-v2` into Qwen2.5-Coder-1.5B-Instruct @ `2e1fd39`.

Checks from `merge_report.json`:

- the adapter moves the base logits by up to 19.75, so it was loaded
- merged vs base + unmerged adapter, FP32: max logit difference 7e-5
- FP16 copy keeps the FP32 next-token choice at every position of the 3 check prompts

GGUF files were made with llama.cpp at `987498f` (`convert_hf_to_gguf.py --outtype f16`, then
`llama-quantize`):

| File | Size | Bits/weight |
|---|---|---|
| qwen2.5-coder-1.5b-qlora-v2-f16.gguf | 2.9 GiB | 16.0 |
| qwen2.5-coder-1.5b-qlora-v2-q8_0.gguf | 1.5 GiB | 8.5 |
| qwen2.5-coder-1.5b-qlora-v2-q4_k_m.gguf | 0.9 GiB | 5.1 |

Checksums in `sha256.txt`. The files live in `~/models/` (not in git). The quality, speed and
energy of each format are measured in the quantization ladder.

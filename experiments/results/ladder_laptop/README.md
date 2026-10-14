# Quantization ladder on the laptop CPU

Runs on 2026-10-14 on the laptop: i5-10210U, 4 threads, 16 GB RAM, no GPU. llama.cpp `987498f`,
`llama-server` with one slot, greedy decoding, 4096 context. Energy is the CPU package counter
(RAPL), measured per item. Script: `experiments/scripts/laptop_ladder.sh`.

Models:

- **base**: Qwen2.5-Coder-1.5B-Instruct. Q4_K_M is Qwen's official GGUF. F16 I converted from the
  same revision (`2e1fd39`).
- **ft**: the QLoRA v2 fine-tune merged into the base
  ([merge check](../merge_qwen25_qlora_v2/README.md)), then exported as F16 and quantized to Q8_0
  and Q4_K_M with `llama-quantize`.

The base Q4_K_M answers on HumanEval+ and MBPP+ come from the earlier laptop baseline run
(2026-10-12, `../baselines/`). Greedy runs reproduce exactly, so the answers are comparable, but
its timing was taken with the default prompt cache.

## Before quantizing: does merging change anything?

I served the merged FP16 model with vLLM on a Kaggle T4 (`../merged_qwen25_qlora_v2_t4/`) and
paired it with the evaluated base + adapter answers on all 12 tasks. At most 2 items differed per
task, and nothing was close to significant. Merging is safe.

## Quality (pass@1, %)

| | base F16 | base Q4_K_M | ft F16 | ft Q8_0 | ft Q4_K_M |
|---|---|---|---|---|---|
| HumanEval+ (163) | 65.0 | 67.5 | 64.4 | 63.2 | 60.1 |
| MBPP+ (377) | 56.2 | 60.5 | 60.2 | 59.4 | 58.1 |
| HumanEvalFix (164) | | 22.0 | 32.3 | | 29.9 |

Paired exact McNemar tests (items only the first one solved / only the second one solved):

| Comparison | HumanEval+ | MBPP+ | HumanEvalFix |
|---|---|---|---|
| ft F16 vs ft Q8_0 | 2 / 0, p = 0.50 | 6 / 3, p = 0.51 | |
| ft F16 vs ft Q4_K_M | 14 / 7, p = 0.19 | 23 / 15, p = 0.26 | 8 / 4, p = 0.39 |
| base F16 vs base Q4_K_M | 14 / 18, p = 0.60 | 15 / 31, **p = 0.026** | |
| base F16 vs ft F16 | 19 / 18, p = 1 | 24 / 39, p = 0.077 | |
| base Q4_K_M vs ft Q4_K_M | 23 / 11, p = 0.058 | 43 / 34, p = 0.36 | 8 / 21, **p = 0.024** |

What I take from it:

- **Q8_0 is lossless here.** Against F16 it changes 2 of 163 and 9 of 377 answers.
- **Q4_K_M costs the fine-tuned model 2–4 points**: −4.3 on HumanEval+, −2.1 on MBPP+, −2.4 on
  HumanEvalFix. None of these is significant on its own, but all three point the same way.
- **Q4_K_M did not hurt the base model, and on MBPP+ it scored higher (+4.3, p = 0.026).** Base F16
  on the laptop gives exactly the same scores as base FP16 under vLLM on the T4 (65.0 / 56.2), so the
  runtime is not the cause. I don't have an explanation beyond quantization noise happening to
  favour the base model. It is one test among many here, so I wouldn't build on it.
- Because of that, **which base you compare against matters.** At equal precision (F16) the fine-tune
  matches the base on HumanEval+ and is ahead on MBPP+ (+4.0, p = 0.077), close to the T4 result
  (+5.8, p = 0.005). At Q4_K_M the base's lucky MBPP+ score hides that gain.
- **The bug-repair gain survives quantization.** On HumanEvalFix the Q4_K_M fine-tune beats the
  Q4_K_M base by 8 points (p = 0.024). The F16 fine-tune is 2.4 points higher still.

## Speed, energy and memory

| | base F16 | base Q4_K_M | ft F16 | ft Q8_0 | ft Q4_K_M |
|---|---|---|---|---|---|
| Decode speed (tokens/s) | 5.8 | 16.8 | 5.8 | 10.4 | 16.1 |
| Output tokens, HumanEval+ | 227 | 209 | 145 | 143 | 112 |
| Output tokens, MBPP+ | 102 | 99 | 50 | 49 | 52 |
| Seconds per item, HumanEval+ | 41.5 | 14.6 | 27.3 | 16.5 | 9.1 |
| Energy per item, HumanEval+ (J) | 625 | 224 | 411 | 250 | 141 |
| Energy per *solved* item, HumanEval+ (J) | 962 | 332 | 638 | 396 | 234 |
| Energy per solved item, MBPP+ (J) | 495 | 169 | 238 | 146 | 107 |
| Energy per solved item, HumanEvalFix (J) | | 756 | 833 | | 471 |
| Peak RAM of llama-server (GB) | 3.27 | 1.29 | 3.21 | 1.79 | 1.16 |
| GGUF file (GiB) | 2.9 | 1.0 | 2.9 | 1.5 | 0.9 |

The peak RAM is measured with memory mapping and the prompt cache turned off (load plus one
request, `memory_footprint.tsv`). In the night-1 log the peaks are about 2 GB higher. There,
llama-server's host prompt cache (up to 8 GiB by default) grew with every new prompt, and
memory-mapped Q4_K weights were counted twice. The script now runs with
`--load-mode none --cache-ram 0`.

- **Decoding speed tracks model size**, as expected for a memory-bound CPU: Q4_K_M is 2.8× and
  Q8_0 1.8× faster than F16.
- **The fine-tune writes about a third fewer tokens** (HumanEval+ 145 vs 227 at F16, MBPP+ 50 vs
  102), so it uses less time and energy per answer than the base at the same precision. At F16 that
  is 34 % less energy per HumanEval+ item and 52 % less per solved MBPP+ item.
- **Cheapest per correct answer:** the fine-tuned Q4_K_M on every task. On HumanEvalFix it uses
  471 J per fixed bug, against 756 J for the base Q4_K_M, because it fixes more bugs with shorter
  answers.

## What I'll deploy

**Q8_0 as the default** for the assistant on the laptop. It loses nothing measurable against F16, needs 1.8 GB of RAM and
runs at about 10 tokens/s. **Q4_K_M as the fast option** (1.2 GB, 16 tokens/s): it is the most
energy-efficient per correct answer, and its 2–4 point loss is the price.

## Caveats

- One run per configuration. Night 2 (base F16, all HumanEvalFix runs) ran during the day, so its
  timing and energy may include some background load. Night 1 ran at night with the laptop idle.
- Base F16 and the fine-tuned Q8_0 were not run on HumanEvalFix, to keep night 2 within a day.
- CPU energy only (RAPL package). It leaves out RAM and the rest of the laptop.

# Draft-model speculative decoding for the 3B on the laptop

Does a small draft model speed up the deployed 3B (run D, Q4_K_M, `../../3_finetune_3b/finetune_qwen25_3b_qlora_mixv3b_diag`)
on the laptop CPU, and does a draft fine-tuned on the same kind of data (the 1.5B QLoRA v2) do
better than a base draft? `experiments/scripts/laptop/laptop_3b_speculative.sh`, llama.cpp 987498f, 4
threads (target and draft share them), one request at a time, greedy, all 164 HumanEvalFix
problems, RAPL package energy per request, mains power, nothing else running (2026-11-02, 01:00 to
05:41). All drafts Q4_K_M. n-gram row from `../laptop_3b_energy_runD` (same model, same day, earlier).

| Decoding | Fixed | J per problem | J per fixed bug | s per problem | of which time to first token | Draft acceptance | Peak RAM |
|---|---|---|---|---|---|---|---|
| Plain | 100 | 305 | 501 | 16.9 | 8.9 | - | 2.20 GB |
| **n-gram lookup (deployed)** | **100** | **278** | **456** | **15.2** | 8.9 | 0.51 | 2.23 GB |
| Draft 0.5B base, n=4 | 100 | 314 | 516 | 17.3 | 10.8 | 0.89 | 2.81 GB |
| Draft 1.5B base, n=4 | 98 | 399 | 668 | 22.0 | 13.1 | 0.96 | 3.39 GB |
| Draft 1.5B fine-tuned, n=4 | 99 | 403 | 668 | 22.2 | 13.3 | 0.97 | 3.39 GB |
| Draft 1.5B fine-tuned, n=8 | 99 | 408 | 675 | 22.5 | 13.1 | 0.92 | 3.39 GB |

Acceptance is accepted / drafted tokens summed over all requests (server logs). Output length is
69 tokens in every setting.

## What it says

- **No draft model beats n-gram lookup, and the 1.5B drafts are slower than no speculation at all**
  (+31 % time, +33 % energy per fixed bug). The answers are short (69 tokens) and the prompts long
  (327 tokens), so most of the time is prompt processing, and the draft has to process the prompt
  too: time to first token goes from 8.9 s to 13 s. Draft and target share 4 cores, so the draft's
  work is not hidden.
- The 0.5B draft does save decode time (6.5 s vs 8.0 s plain, same as n-gram's 6.3 s), but loses
  it again in prompt processing (+1.9 s). n-gram lookup gets the same decode saving for free.
- **Fine-tuning the draft on the same data does not matter**: acceptance 0.97 vs 0.96 for the base
  1.5B. Both 1.5B models already agree with the 3B on almost every token of a code repair, because
  most of the answer is copied from the buggy input. A longer draft (n=8) lowers acceptance and
  changes nothing else.
- Answers are not bit-identical to plain decoding (155 to 159 of 164 identical texts; n-gram 156):
  verification runs the target on a batch of tokens, which changes floating-point rounding. Only
  1 to 3 pass/fail outcomes change, in both directions.

On a 4-core CPU with repair-style prompts, speculative decoding pays only when drafting costs
nothing (n-gram lookup). A draft model could pay on a GPU, where it runs beside the target, or for
long answers where decoding dominates; neither is Locali's laptop case.

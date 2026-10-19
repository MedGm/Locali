# Speculative decoding on the laptop CPU

The deployed model (fine-tuned 1.5B, Q8_0 GGUF) on the laptop CPU, with a 0.5B draft model or with
n-gram lookup, against plain decoding. Same harness as the quantization ladder
(`../ladder_laptop`), energy from RAPL (whole CPU package).

Run on 2026-10-19, 00:42-07:59, unattended, mains power, by `experiments/scripts/laptop_speculative.sh`
with `RUN="ngram-simple none draft-q4-n4 draft-q4-n8 draft-q8-n8"`: llama.cpp 987498f, 4 threads (and
4 for the draft), greedy, 768 tokens, one request at a time. Draft model:
Qwen2.5-Coder-0.5B-Instruct GGUF (Q4_K_M or Q8_0) @ebb2015. The pilot (20 problems,
`../speculative_laptop_pilot`) chose the settings; `ngram-mod` was dropped there.

| Setting | HE+ passed (163) | HE+ tok/s | HE+ J per correct | Fix passed (164) | Fix tok/s | Fix J per correct | Acceptance HE+ / fix |
|---|---|---|---|---|---|---|---|
| none | 103 | 10.2 | 387 | 52 | 10.4 | 607 | |
| **ngram-simple** | 102 | **15.1** | **288 (−25 %)** | 53 | **16.3** | **478 (−21 %)** | 0.76 / 0.58 |
| draft Q4, 4 tokens | 105 | 12.0 | 367 (−5 %) | 53 | 11.5 | 665 (+10 %) | 0.91 / 0.89 |
| draft Q4, 8 tokens | 105 | 12.2 | 362 (−6 %) | 53 | 11.3 | 663 (+9 %) | 0.82 / 0.79 |
| draft Q8, 8 tokens | 105 | 11.3 | 378 (−2 %) | 53 | *see below* | *see below* | 0.81 / 0.79 |

**The draft Q8 / repair row is not a valid measurement.** From 07:26 to 07:58 the second-seed
answers were being scored in the Docker sandbox on the same machine, overlapping most of that run
(07:02-07:59), so its time and energy (9.1 tok/s, 887 J per correct) are inflated. Its answers
and pass count are fine. The run is kept as recorded in `spoiled/`, and was repeated.

## What it says

- **On a CPU the draft model hardly pays.** It is accepted 79-91 % of the time, yet saves at most
  6 % energy on HumanEval+ and costs 9-10 % more on repair: the 0.5B draft runs on the same four
  cores, and checking a batch of drafted tokens is not free on a CPU the way it is on a GPU. It also
  reads the prompt, so time to first token goes up (repair: 5.7 s → 7.9 s).
- **n-gram lookup is the setting to ship:** about 1.5x faster and 21-25 % less energy per correct
  answer, no second model, no extra memory (1.89 GB peak vs 2.48-2.66 GB with a draft).
- **Speculation changes answers on a CPU.** Greedy speculative decoding should reproduce plain
  decoding, but 14 of 163 HumanEval+ answers differ with the draft model and 8 with n-gram, because
  the target scores several tokens at once and Q8 matrix products round differently in a batch.
  The pass counts move by −1 to +2, not significant (exact McNemar, p ≥ 0.5).

## Limits

One run per setting, one machine. RAPL covers the whole package, idle included. The ladder run of
14 October measured plain Q8 at 10.4 tok/s and 250 J per task, in line with `none` here (10.2,
244 J), so the conditions were stable apart from the overlap above.

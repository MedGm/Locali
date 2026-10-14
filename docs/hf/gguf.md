---
base_model: MedGm/Llama-Locali-Qwen2.5-Coder-1.5B
license: apache-2.0
language: [en]
tags: [code, gguf, llama.cpp, built-with-llama]
---

# Llama-Locali-Qwen2.5-Coder-1.5B-GGUF

GGUF files of [Llama-Locali-Qwen2.5-Coder-1.5B](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B)
for llama.cpp. This is what the Locali assistant runs on a laptop without a GPU. What the model was
trained for and how it scores is on the [adapter page](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA).

| File | Size | Bits/weight |
|---|---|---|
| `llama-locali-qwen2.5-coder-1.5b-q8_0.gguf` | 1.5 GiB | 8.5 |
| `llama-locali-qwen2.5-coder-1.5b-q4_k_m.gguf` | 0.9 GiB | 5.1 |

Made with llama.cpp `987498f`: `convert_hf_to_gguf.py --outtype f16`, then `llama-quantize`.
The F16 GGUF is not uploaded; one command rebuilds it from the merged model.

Measured on a laptop CPU (i5-10210U, 4 threads, llama.cpp), greedy decoding, pass@1 in %:

| | F16 | Q8_0 | Q4_K_M |
|---|---|---|---|
| HumanEval+ | 64.4 | 63.2 | 60.1 |
| MBPP+ | 60.2 | 59.4 | 58.1 |
| HumanEvalFix | 32.3 | | 29.9 |
| Decode speed (tokens/s) | 5.8 | 10.4 | 16.1 |
| Peak RAM (GB) | 3.2 | 1.8 | 1.2 |

Q8_0 changed 2 of 163 and 9 of 377 answers against F16, so I treat it as lossless. Q4_K_M is 2–4
points lower on all three tasks (not significant on any one of them) and nearly three times faster.
I use Q8_0 by default and Q4_K_M when speed matters. Details, energy per answer and the paired tests:
`experiments/results/ladder_laptop/README.md` in the [project repository](https://github.com/MedGm/Locali).

```
llama-server -m llama-locali-qwen2.5-coder-1.5b-q4_k_m.gguf -c 4096
```

Built with Llama. Apache-2.0, with the [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/)
naming and attribution terms applying because of the training data.

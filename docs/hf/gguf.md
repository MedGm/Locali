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

How much quality each format loses is not measured yet. I'm running the same benchmarks on F16,
Q8_0 and Q4_K_M (paired tests, plus speed and energy on a laptop CPU), and will add the table here.

```
llama-server -m llama-locali-qwen2.5-coder-1.5b-q4_k_m.gguf -c 4096
```

Built with Llama. Apache-2.0, with the [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/)
naming and attribution terms applying because of the training data.

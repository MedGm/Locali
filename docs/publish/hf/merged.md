---
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
library_name: transformers
license: apache-2.0
language: [en]
tags: [code, merged-lora, built-with-llama]
datasets: [MedGm/locali-mix-v2]
---

# Llama-Locali-Qwen2.5-Coder-1.5B

[Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA)
merged into Qwen2.5-Coder-1.5B-Instruct (revision `2e1fd39`), saved in FP16. Training details,
results and limitations are on that page. The name prefix is explained there too (Llama 3.1
licence).

The adapter was evaluated served on the FP16 base, so merging into the full-precision base
reproduces the evaluated model. I checked the merge on three chat prompts:

- base + unmerged adapter vs merged model, FP32: largest logit difference 7e-5
- FP16 copy vs FP32: same next token at every position

The merge script is `training/merge_adapter.py` in the [project repository](https://github.com/MedGm/Locali).

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

tok = AutoTokenizer.from_pretrained("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B")
model = AutoModelForCausalLM.from_pretrained("MedGm/Llama-Locali-Qwen2.5-Coder-1.5B", torch_dtype="auto")
```

or `vllm serve MedGm/Llama-Locali-Qwen2.5-Coder-1.5B`.

Built with Llama. Apache-2.0, with the [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/)
naming and attribution terms applying because of the training data.

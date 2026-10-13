---
library_name: peft
license: apache-2.0
language: [en]
tags: [code, lora, qlora, rslora, unsloth, built-with-llama]
datasets: [MedGm/locali-mix-v2]
---

# Llama-Locali-adapters

The other adapters from the Locali fine-tuning experiments. They are here so the comparisons in the
project report can be reproduced. The adapter I actually use is
[Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA).
The name prefix is explained on that page (Llama 3.1 licence).

| Folder | Base model | Method | Data | Training time |
|---|---|---|---|---|
| `qwen2.5-coder-1.5b-qlora-v1` | Qwen2.5-Coder-1.5B-Instruct `2e1fd39` | QLoRA (NF4) | mixture v1 | 1 h 58 min |
| `qwen2.5-coder-1.5b-lora16-v2` | Qwen2.5-Coder-1.5B-Instruct `2e1fd39` | LoRA on the 16-bit base | mixture v2 | 2 h 17 min |
| `qwen2.5-coder-1.5b-rslora-v2` | Qwen2.5-Coder-1.5B-Instruct `2e1fd39` | QLoRA + rank-stabilised scaling | mixture v2 | 2 h 34 min |
| `phi-4-mini-qlora-v2` | unsloth/Phi-4-mini-instruct `75becc4` (same weights as microsoft/Phi-4-mini-instruct) | QLoRA (NF4) | mixture v2 | 5 h 58 min |

All of them use r = 16, alpha = 16, all projections, 2 epochs, lr 2e-4, seed 3407, one Kaggle T4.
Mixture v1 is a subset of [locali-mix-v2](https://huggingface.co/datasets/MedGm/locali-mix-v2):
the rows without the T4 traces, the second family of bug operators and the extra clean reviews.

What I found, in short:

- **v1 → v2:** the v1 adapter lost 4.6 points on CRUXEval-O. Adding execution-trace data in v2
  removed that loss. v1 also only improved on bug types close to its training faults.
- **QLoRA vs 16-bit LoRA vs rsLoRA (same data):** no consistent winner. Quantizing the frozen base to
  NF4 cost nothing measurable and saved 36 % of peak memory. Each variant beat the others on one or
  two tasks, by amounts that one seed cannot separate from noise.
- **Phi-4-mini:** it gained where the training answers were better than what it already did
  (in-distribution repair +30 points, review +22, secure code generation +17). It lost where base
  Phi was already better than our targets (repair in our prompt format −22, in-distribution test
  writing −11). It also became worse at using the function name a prompt asks for, which costs it
  6 points on MBPP+.

Tables and significance tests: `experiments/results/finetune_v2/README.md` and
`experiments/results/finetune_qwen25_qlora_v1/README.md` in the
[project repository](https://github.com/MedGm/Locali).

Load one with `subfolder`:

```python
from peft import PeftModel
model = PeftModel.from_pretrained(base_model, "MedGm/Llama-Locali-adapters", subfolder="qwen2.5-coder-1.5b-rslora-v2")
```

Built with Llama. The Qwen adapters are Apache-2.0. The Phi-4-mini adapter follows its base model's
MIT licence. The [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) naming and
attribution terms apply to all of them because of the training data.

## vLLM on one T4

| Server | Concurrent requests | Items | Wall time | Throughput | Mean TTFT | Mean request time | GPU energy per item | pass@1 | Same answer as reference |
|---|---|---|---|---|---|---|---|---|---|
| prefix cache on, eager | 1 | 64 | 528 s | 29.9 tok/s | 0.100 s | 8.24 s | 551 J | 71.9 | 64/64 |
| prefix cache on, eager | 4 | 64 | 132 s | 119.8 tok/s | 0.177 s | 7.97 s | 138 J | 70.3 | 59/64 |
| prefix cache on, eager | 16 | 64 | 39 s | 406.7 tok/s | 0.379 s | 8.53 s | 37 J | 71.9 | 58/64 |
| prefix cache on, eager, warm (second pass) | 16 | 64 | 36 s | 440.5 tok/s | 0.182 s | 7.80 s | 37 J | 71.9 | 62/64 |
| prefix cache off, eager | 1 | 64 | 471 s | 33.5 tok/s | 0.086 s | 7.36 s | 493 J | 70.3 | 61/64 |
| prefix cache off, eager | 4 | 64 | 127 s | 125.2 tok/s | 0.135 s | 7.64 s | 131 J | 70.3 | 58/64 |
| prefix cache off, eager | 16 | 64 | 39 s | 408.5 tok/s | 0.404 s | 8.55 s | 39 J | 71.9 | 61/64 |
| prefix cache on, CUDA graphs | 1 | 64 | 326 s | 48.7 tok/s | 0.127 s | 5.09 s | 336 J | 71.9 | 59/64 |
| prefix cache on, CUDA graphs | 16 | 64 | 31 s | 505.1 tok/s | 0.389 s | 7.03 s | 31 J | 71.9 | 59/64 |

## transformers on one T4

transformers 5.16.1, torch 2.11.0+cu128, Tesla T4, FP16, greedy.

| Run | Batch | Prompts | New tokens (max) | KV cache | Wall time | Tokens/s | Peak memory | Usable answers | Same answers as |
|---|---|---|---|---|---|---|---|---|---|
| sdpa__b1 | 1 | 16 | 256 | on | 153.8 s | 23.5 | 3.16 GB | 16/16 | — |
| sdpa__b8 | 8 | 16 | 256 | on | 22.1 s | 162.9 | 3.47 GB | 16/16 | 14/16 (sdpa__b1) |
| sdpa__b1__cache-on__128 | 1 | 4 | 128 | on | 22.2 s | 23.1 | 3.14 GB | 4/4 | — |
| sdpa__b1__cache-off__128 | 1 | 4 | 128 | off | 46.0 s | 11.1 | 3.15 GB | 4/4 | 4/4 (sdpa__b1__cache-on__128) |
| eager__b1 | 1 | 16 | 256 | on | 163.5 s | 25.1 | 3.15 GB | 0/16 | 0/16 (sdpa__b1) |
| eager__b8 | 8 | 16 | 256 | on | 22.4 s | 183.2 | 3.52 GB | 0/16 | 0/16 (sdpa__b1) |

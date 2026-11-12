# Run G on the laptop, at 4 and 5 bits

Same measurement as `../laptop_3b_energy_runE`, on run G
(`../../3_finetune_3b/finetune_qwen25_3b_qlora_mixv3r`): both files built in one job by
`training/kaggle/deploy/gguf` with `ADAPTER=mixv3r QUANT=Q4_K_M,Q5_K_M`, llama.cpp 987498f with
n-gram lookup, 4 threads, one request at a time, greedy, all 164 HumanEvalFix problems, RAPL
package energy per request. The two files were measured one after the other in the same evening,
nothing else running (2026-11-12, `experiments/scripts/laptop/laptop_runG.sh`).

| HumanEvalFix, laptop CPU, n-gram | Size | Fixed | s per problem | J per problem | J per fixed bug | Peak RAM |
|---|---|---|---|---|---|---|
| **run G, Q4_K_M (the default)** | 1.93 GB | 93 (56.7 %) | 17.6 | 233 | 410 | 2.23 GB |
| run G, Q5_K_M | 2.22 GB | 102 (62.2 %) | 30.8 | 403 | 647 | 2.51 GB |

Same answers length (68 tokens) and n-gram acceptance (0.52) for both.

## 4 bits or 5

- The 5-bit file fixes 9 more bugs: 11 fixed only at 5 bits, 2 only at 4, exact McNemar p = 0.022.
  It is the second time: run E on the T4 gave 102 against 93 (p = 0.035,
  `../../8_improve/quant`), and run E on this laptop 102 against 95 (`../laptop_3b_energy_runE_q5`).
  The 4-bit file loses repair fixes; this is no longer noise.
- The 5-bit file is 1.75 times slower and uses 1.73 times the energy. It is not the disk or the
  load: llama.cpp reads the prompt at 15 tokens per second in 5 bits against 29 in 4 bits on this
  CPU (a 20-problem check of both files back to back gave the same ratio).
- The 4-bit file stays the default. The assistant retries a failed fix with the test error
  (`../../7_assistant/repair_step_runE`: 95, 102, 106 fixed within one, two, three attempts in
  4 bits, 295 calls for 164 bugs, so about 27 s per bug), which gives more fixes than one 5-bit
  attempt for less time. The 5-bit file is in the model list for who prefers one slower, better
  attempt.

## Run G against run E

In 4 bits: 93 against 95, 10 fixed only by G and 12 only by E, p = 0.83. In 5 bits: 102 each.
On this benchmark the two runs are the same model, as on the T4 (103 against 104); what run G
adds is on real bugs, which were measured at 16 bits only (106 of 382 against 56). The real-bug
check has not been run on the laptop files.

The seconds and joules of run E's table (15.2 s, 277 J per problem on 5 November) are not
comparable with these: the laptop drew 13 W here against 18 W then (another power state), so it was
slower and used less energy per problem. Within this folder the two files ran under the same
conditions.

`qwen2.5-coder-3b-locali-mixv3r.merge_report.json`: the merged model matches the adapter on top of
the base (largest logit difference 5.5e-5, same top-1 token on every checked position).

Code and text written with AI help (Claude); every figure above comes from the files in this folder.

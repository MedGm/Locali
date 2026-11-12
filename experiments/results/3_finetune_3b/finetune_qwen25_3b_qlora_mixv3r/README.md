# Run G: Qwen2.5-Coder-3B + QLoRA on mixture v3r (real bugs added)

Same recipe and seed as run E (`../finetune_qwen25_3b_qlora_mixv3s`). The data is run E's plus
1,441 real bugs from 546 AtCoder tasks of ConDefects, contests before 2024-02-01, written in the
prompt of the real-bug check (`training/data/real_bugs.py`, `build_mix_v3r.py`, private Kaggle
dataset `locali-mix-v3r`). The check uses contests from 2024-02-01 on: no task is shared (checked
again after the run, 0 of its 129 tasks are in the training source), and rows sharing 13 words in a
row with one of its 382 programs were dropped before training.

Rules written before the run: `docs/preregistration-runs-fg.md`.
`training/kaggle/train/finetune-3b-v3r`, 2026-11-12, commit d9f08fe, 5.5 h, final loss 0.195
(E: 0.207). Real-bug answers: `training/kaggle/evaluate/repair_prereg` with
`ADAPTERS=mixv3r ONLY=qwen2.5-coder-3b-ft-qlora-mixv3r`, commit b6f3ccb (`real_bugs/`). Everything
scored locally in the sandbox. Adapter (not in git): external drive `runG/adapter`, private Kaggle
dataset `locali-adapter-mixv3r`.

## Primary: training on real bugs helps on real bugs

ConDefects, 382 real bugs from contests after the training ones (exact McNemar). The answers of the
base and of run E are those of the registered check (`../../4_final_checks/repair_prereg_t4`).

| | fixed | |
|---|---|---|
| 3B base | 54 | 14.1 % |
| run E | 56 | 14.7 % |
| **run G** | **106** | **27.7 %** |

G against the base: 70 bugs fixed only by G, 18 only by the base, **p = 2e-8**. The registered claim
holds. G against E: 54 only G, 4 only E, p = 3e-12. 18 of G's answers are cut off at 1,024 tokens,
as for the other models.

To be said with it, as registered: run G was trained on bugs from the same site, written in the
same prompt as the check. The gain shows that real examples help on bugs of this kind. It does not
show a gain on bugs from elsewhere: on QuixBugs, the only set here from another source, G fixes 29
of 40 against 28 for run E (p = 1) and 21 for the base (p = 0.06).

## Secondary, G against E

| Task | n | E | G | only E / only G | p |
|---|---|---|---|---|---|
| ConDefects | 382 | 56 | 106 | 4 / 54 | 3e-12 |
| QuixBugs | 40 | 28 | 29 | 1 / 2 | 1 |
| HumanEvalFix, benchmark format | 164 | 104 | 103 | 7 / 6 | 1 |
| HumanEval+ | 163 | 122 | 123 | 4 / 5 | 1 |
| MBPP+ | 377 | 242 | 244 | 9 / 11 | 0.82 |
| Test generation: bug caught | 164 | 135 | 136 | 3 / 4 | 1 |

Only ConDefects differs, and it stays significant after the Holm correction over the six tests
(p = 2e-11).

Not registered: completion 107 → 101 (8 only E, 2 only G, p = 0.11), CRUXEval-O 349 → 347
(p = 0.87), test generation with every test valid 131 → 124 (p = 0.23), HumanEvalFix in the
repair format 59 → 54 (p = 0.41) and 106 with the code asked first. Unpaired: bug detection
66.5 → 67.4 %, vulnerability detection 54.5 → 55.2 %, refactoring behaviour preserved 87.7 → 90.2 %
and improved 30.7 → 26.4 %, insecure code 17.4 → 20.7 %. Explaining code has not been run for G.
The internal held-out sets are not scored here.

## What it shows

- 1,441 real examples (8 % of the training rows) double the number of real bugs fixed, and cost
  nothing that these benchmarks can measure.
- Runs B to E were trained on bugs written by a model and never moved this number (54 to 57).
  The data was the limit, not the recipe.
- The planted-bug benchmarks do not see the difference: HumanEvalFix is the same for E and G.

Run G is not the default yet: that needs the 4-bit file and the laptop measurement, as for run E.

Code and text written with AI help (Claude).
